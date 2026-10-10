"""
Checks that a waitlist email is on a real, mail-receiving, non-throwaway domain.
"""

import difflib
import logging

import dns.exception
import dns.resolver
from disposable_email_domains import blocklist as DISPOSABLE_DOMAINS
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Providers people commonly mistype; a near miss is flagged as a typo
TYPO_TARGETS = [
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "live.com",
    "gmx.com",
    "yandex.com",
    "mts.rs",
    "eunet.rs",
    "sbb.rs",
]
# Real providers that happen to look like a typo of one of the targets
KNOWN_DOMAINS = set(TYPO_TARGETS) | {
    "ymail.com",
    "googlemail.com",
    "mail.com",
    "email.com",
    "msn.com",
    "aol.com",
    "me.com",
    "mac.com",
    "proton.me",
    "protonmail.com",
    "gmx.net",
}
# Mistyped TLDs, keyed by the TLD they were meant to be
TLD_TYPOS = {
    "com": {"con", "cm", "co", "comm", "om", "cpm", "vom", "xom", "ocm", "coom"},
    "rs": {"sr", "rss", "r"},
}
NAME_TYPO_CUTOFF = 0.8

DNS_TIMEOUT_SECONDS = 3
DNS_CACHE_OK_SECONDS = 60 * 60 * 24
DNS_CACHE_FAIL_SECONDS = 60 * 60 * 6

# Cached per-domain DNS verdicts
DOMAIN_OK = "ok"
DOMAIN_NO_MAIL = "no_mail"
DOMAIN_UNKNOWN = "unknown"


def suggest_domain(domain):
    """Return the common provider the domain looks like a typo of, or None."""
    if domain in KNOWN_DOMAINS:
        return None
    name, _, tld = domain.rpartition(".")
    for target in TYPO_TARGETS:
        target_name, _, target_tld = target.rpartition(".")
        # gmail.con -> gmail.com
        if name == target_name and tld in TLD_TYPOS.get(target_tld, ()):
            return target
        # gmial.com -> gmail.com (same TLD, so yahoo.co.uk is never flagged)
        if (
            tld == target_tld
            and difflib.SequenceMatcher(None, name, target_name).ratio()
            >= NAME_TYPO_CUTOFF
        ):
            return target
    return None


def is_disposable(domain):
    """True if the domain, or any parent domain, is a known throwaway provider."""
    parts = domain.split(".")
    return any(".".join(parts[i:]) in DISPOSABLE_DOMAINS for i in range(len(parts) - 1))


def _lookup_domain(domain):
    """Resolve MX records, falling back to A/AAAA as RFC 5321 allows."""
    resolver = dns.resolver.Resolver()
    resolver.lifetime = DNS_TIMEOUT_SECONDS
    try:
        answers = resolver.resolve(domain, "MX")
        hosts = [str(r.exchange).rstrip(".") for r in answers]
        # Null MX (RFC 7505): the domain explicitly accepts no mail
        if not any(hosts):
            return DOMAIN_NO_MAIL
        return DOMAIN_OK
    except dns.resolver.NXDOMAIN:
        return DOMAIN_NO_MAIL
    except dns.resolver.NoAnswer:
        pass
    except (dns.exception.Timeout, dns.resolver.NoNameservers):
        return DOMAIN_UNKNOWN

    for record_type in ("A", "AAAA"):
        try:
            resolver.resolve(domain, record_type)
            return DOMAIN_OK
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            continue
        except (dns.exception.Timeout, dns.resolver.NoNameservers):
            return DOMAIN_UNKNOWN
    return DOMAIN_NO_MAIL


def domain_accepts_mail(domain):
    """
    True unless DNS shows the domain can't receive mail. Timeouts count as
    True, since the confirmation link will still catch a dead address.
    """
    cache_key = f"waitlist:dns:{domain}"
    verdict = cache.get(cache_key)
    if verdict is None:
        verdict = _lookup_domain(domain)
        timeout = (
            DNS_CACHE_OK_SECONDS if verdict == DOMAIN_OK else DNS_CACHE_FAIL_SECONDS
        )
        if verdict != DOMAIN_UNKNOWN:
            cache.set(cache_key, verdict, timeout)
        else:
            logger.warning("DNS lookup for %s timed out; accepting", domain)
    return verdict != DOMAIN_NO_MAIL


def validate_waitlist_email(email):
    """Raise ValidationError if the (already normalised) email is unusable."""
    local_part, _, domain = email.rpartition("@")

    suggestion = suggest_domain(domain)
    if suggestion:
        raise ValidationError(
            f"Da li ste mislili {local_part}@{suggestion}?", code="typo"
        )

    if is_disposable(domain):
        raise ValidationError(
            "Privremene email adrese nisu dozvoljene.", code="disposable"
        )

    if getattr(settings, "WAITLIST_CHECK_DNS", True) and not domain_accepts_mail(
        domain
    ):
        raise ValidationError(
            "Ovaj email domen ne postoji ili ne prima poštu.", code="no_mail"
        )
