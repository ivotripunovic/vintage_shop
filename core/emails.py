"""
Waitlist emails: confirmation links, unsubscribe links and the launch announcement.
"""

import logging
import threading

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMessage, send_mail
from django.db import transaction
from django.urls import reverse

logger = logging.getLogger(__name__)

CONFIRM_SALT = "core.waitlist.confirm"
UNSUBSCRIBE_SALT = "core.waitlist.unsubscribe"
CONFIRM_MAX_AGE_SECONDS = 60 * 60 * 24 * 7


def make_confirm_token(email):
    return signing.dumps(email, salt=CONFIRM_SALT)


def read_confirm_token(token):
    """Return the email in a confirmation token; raises BadSignature if invalid/expired."""
    return signing.loads(token, salt=CONFIRM_SALT, max_age=CONFIRM_MAX_AGE_SECONDS)


def make_unsubscribe_token(email):
    return signing.dumps(email, salt=UNSUBSCRIBE_SALT)


def read_unsubscribe_token(token):
    """Return the email in an unsubscribe token; raises BadSignature if invalid."""
    return signing.loads(token, salt=UNSUBSCRIBE_SALT)


def _absolute_url(name, token):
    return f"{settings.SITE_DOMAIN}{reverse(name, args=[token])}"


def _send_confirmation_now(email):
    site_name = settings.SITE_NAME
    confirm_url = _absolute_url("waitlist_confirm", make_confirm_token(email))
    subject = f"Potvrdite prijavu na {site_name}"
    body = f"""Zdravo,

Hvala što ste se prijavili za vesti o otvaranju {site_name}.

Potvrdite vašu email adresu klikom na link:
{confirm_url}

Link važi 7 dana. Ako se niste vi prijavili, samo ignorišite ovu poruku.

Srdačan pozdrav,
Tim {site_name}
"""
    logger.info(
        "Sending waitlist confirmation to %s via %s", email, settings.EMAIL_BACKEND
    )
    try:
        send_mail(
            subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False
        )
    except Exception:
        logger.exception("Failed to send waitlist confirmation to %s", email)


def send_waitlist_confirmation(email):
    """
    Send the confirmation link once the current transaction commits. Runs in a
    background thread by default, so a slow SMTP server never ties up one of
    the few gunicorn workers.
    """
    if getattr(settings, "WAITLIST_EMAIL_ASYNC", True):

        def start_thread():
            threading.Thread(
                target=_send_confirmation_now, args=(email,), daemon=True
            ).start()

        transaction.on_commit(start_thread)
    else:
        transaction.on_commit(lambda: _send_confirmation_now(email))


def build_launch_message(email, connection=None):
    site_name = settings.SITE_NAME
    unsubscribe_url = _absolute_url(
        "waitlist_unsubscribe", make_unsubscribe_token(email)
    )
    subject = f"{site_name} je otvoren!"
    body = f"""Zdravo,

Prijavili ste se da vam javimo kada krenemo — {site_name} je sada otvoren!

Pogledajte prve vintage komade:
{settings.SITE_DOMAIN}/

Srdačan pozdrav,
Tim {site_name}

---
Ne želite više poruke? Odjavite se ovde:
{unsubscribe_url}
"""
    return EmailMessage(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        connection=connection,
        headers={"List-Unsubscribe": f"<{unsubscribe_url}>"},
    )
