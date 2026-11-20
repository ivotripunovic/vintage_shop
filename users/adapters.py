from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.db import transaction


class AccountAdapter(DefaultAccountAdapter):
    # USE_I18N is off, so allauth's messages would render in English. Only
    # the keys reachable with email login are overridden; see also
    # users/allauth_forms.py for messages that bypass the adapter.
    error_messages = {
        **DefaultAccountAdapter.error_messages,
        "account_inactive": "Ovaj nalog trenutno nije aktivan.",
        "cannot_remove_primary_email": "Ne možete ukloniti glavnu email adresu.",
        "duplicate_email": "Ova email adresa je već povezana sa vašim nalogom.",
        "email_password_mismatch": "Email adresa ili lozinka nisu ispravni.",
        "email_taken": "Nalog sa ovom email adresom već postoji.",
        "enter_current_password": "Unesite vašu trenutnu lozinku.",
        "incorrect_password": "Pogrešna lozinka.",
        "invalid_or_expired_key": "Link je nevažeći ili je istekao.",
        "invalid_login": "Prijava nije uspela.",
        "invalid_password_reset": "Link za resetovanje lozinke je nevažeći.",
        "too_many_login_attempts": (
            "Previše neuspelih pokušaja prijave. Pokušajte ponovo kasnije."
        ),
        "unknown_email": "Nijedan nalog nije povezan sa ovom email adresom.",
        "unverified_primary_email": ("Vaša glavna email adresa mora biti potvrđena."),
        "same_as_current": "Nova vrednost mora biti različita od trenutne.",
        "rate_limited": "Previše zahteva. Sačekajte malo pa pokušajte ponovo.",
    }

    def populate_username(self, request, user):
        """Auto-generate a unique username from email (username field is not used for auth)."""
        from allauth.account.utils import user_email, user_username

        email = user_email(user)
        if email:
            base = email.split("@")[0]
            username = base
            from django.contrib.auth import get_user_model

            User = get_user_model()
            i = 1
            while User.objects.filter(username=username).exists():
                username = f"{base}{i}"
                i += 1
            user_username(user, username)

    def send_mail(self, template_prefix, email, context):
        """allauth renders emails without context processors; add SITE_NAME so
        templates/account/email/* do not fall back to the Sites record."""
        from django.conf import settings

        context = {**context, "SITE_NAME": settings.SITE_NAME}
        return super().send_mail(template_prefix, email, context)

    def get_signup_redirect_url(self, request):
        from django.urls import reverse

        return reverse("social-signup-complete")

    def get_login_redirect_url(self, request):
        return "/"


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """Decide what happens to a social login that is not yet linked.

        - Already linked, or connecting an account while logged in: hand over
          to allauth unchanged.
        - The email matches exactly one local user and the provider verified
          it: link the social account to that user and log in. If the local
          email was never verified, its password and pending tokens are
          invalidated first (see ``_connect_existing_user``).
        - The email matches a user but cannot be linked safely (provider did
          not verify it, ambiguous match, inactive user): send them to the
          login page instead of letting allauth attempt a signup.
        - The email is already verified for a *different* account (emails
          differing only in case): not linked; send them to the login page.
        - No matching user: a new account, from the login page as well as the
          signup page (#78), but only for an email the provider verified.
          Without one (no email, or Facebook with VERIFIED_EMAIL=False) the
          user signs up by email and connects the social account later;
          otherwise anyone could claim an address through the social signup
          form and keep a social login on it.
        """
        from allauth.core.exceptions import ImmediateHttpResponse
        from django.contrib import messages
        from django.shortcuts import redirect

        if sociallogin.is_existing:
            return
        if sociallogin.state.get("process") == "connect" or (
            request.user.is_authenticated
        ):
            return

        email = sociallogin.user.email
        matches = self._users_with_email(email) if email else []

        if matches:
            user = self._pick_user(matches, email)
            if (
                user is not None
                and user.is_active
                and self._provider_verified(sociallogin, email)
                and not self._verified_for_another_user(email, user)
            ):
                self._connect_existing_user(request, sociallogin, user)
                return
            messages.error(
                request,
                "Nalog sa ovom email adresom već postoji. "
                "Prijavite se email adresom i lozinkom.",
            )
            raise ImmediateHttpResponse(redirect("account_login"))

        if email:
            from allauth.account.models import EmailAddress

            # allauth's signup counts any EmailAddress row as "taken" and
            # would answer with an "account already exists" email and no
            # login. No User has this address (matches is empty), so another
            # account's *unverified* row is an unproven claim (e.g. a pending
            # email change); the provider has just proven ownership, so it
            # goes.
            EmailAddress.objects.filter(email__iexact=email, verified=False).delete()
            if self._verified_for_another_user(email, None):
                # A verified extra address of another account (for example
                # from its own provider) stays theirs
                messages.error(
                    request,
                    "Ova email adresa je već povezana sa drugim nalogom. "
                    "Prijavite se tim nalogom ili koristite drugu adresu.",
                )
                raise ImmediateHttpResponse(redirect("account_login"))

        if not (email and self._provider_verified(sociallogin, email)):
            messages.error(
                request,
                "Ovaj nalog nije podelio potvrđenu email adresu. Registrujte se "
                "email adresom, pa ga povežite u podešavanjima naloga.",
            )
            raise ImmediateHttpResponse(redirect("account_signup"))

    @staticmethod
    def _verified_for_another_user(email, user):
        """allauth holds this address verified for an account other than
        ``user`` (any account when ``user`` is None)."""
        from allauth.account.models import EmailAddress

        return (
            EmailAddress.objects.filter(email__iexact=email, verified=True)
            .exclude(user=user)
            .exists()
        )

    @staticmethod
    def _users_with_email(email):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return list(User.objects.filter(email__iexact=email)[:3])

    @staticmethod
    def _pick_user(matches, email):
        """Return the single user to link, or None if the match is ambiguous.

        Emails are unique only case-sensitively, so ``Foo@x.com`` and
        ``foo@x.com`` can both exist; only an exact-case match settles that.
        """
        if len(matches) == 1:
            return matches[0]
        exact = [u for u in matches if u.email == email]
        return exact[0] if len(exact) == 1 else None

    @staticmethod
    def _provider_verified(sociallogin, email):
        """True if the provider vouches that this email belongs to the user."""
        return any(
            address.verified and address.email.lower() == email.lower()
            for address in sociallogin.email_addresses
        )

    @staticmethod
    def _connect_existing_user(request, sociallogin, user):
        """Link the social account to a user who registered with email/password.

        If that user's email is not verified (never verified, or made
        unverified by an admin edit), the account may belong to whoever
        registered the address first rather than its owner. The provider has
        now proven ownership, so everything that stranger could still use is
        revoked first: the password (and with it any reset link), other
        social logins and other email addresses (a reset could be sent to
        one of those).

        Without linking, allauth treats the login as a new signup, finds the
        email taken and sends an "account already exists" email instead.
        """
        from allauth.account.models import EmailAddress

        with transaction.atomic():
            if not user.email_verified:
                user.socialaccount_set.all().delete()
                EmailAddress.objects.filter(user=user).exclude(
                    email__iexact=user.email
                ).delete()
                # Also voids password reset links, which are tied to the
                # password hash
                user.set_unusable_password()
                user.save(update_fields=["password"])
                user.mark_email_verified()
            sociallogin.connect(request, user)
