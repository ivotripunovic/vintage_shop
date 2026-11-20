from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.utils import timezone


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

    def save_user(self, request, user, form, commit=True):
        """allauth creates this user's EmailAddress itself; see users.signals."""
        from .signals import SKIP_SYNC_ATTR

        # Restore, not clear: social signup with a form calls this from
        # inside SocialAccountAdapter.save_user, which set the flag first
        previous = getattr(user, SKIP_SYNC_ATTR, False)
        setattr(user, SKIP_SYNC_ATTR, True)
        try:
            return super().save_user(request, user, form, commit=commit)
        finally:
            setattr(user, SKIP_SYNC_ATTR, previous)

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

        if not (email and self._provider_verified(sociallogin, email)):
            messages.error(
                request,
                "Ovaj nalog nije podelio potvrđenu email adresu. Registrujte se "
                "email adresom, pa ga povežite u podešavanjima naloga.",
            )
            raise ImmediateHttpResponse(redirect("account_signup"))

    @staticmethod
    def _verified_for_another_user(email, user):
        """allauth holds this address verified for a different account."""
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

        If that user's email was never verified, the account may belong to
        whoever registered the address first, not to its owner. The provider
        has now proven ownership, so everything that stranger could still use
        is revoked first: the password, unused links, and other social logins.

        Without this, allauth treats the login as a new signup, finds the email
        taken and sends an "account already exists" email instead of logging in.
        """
        if not user.email_verified:
            # Someone else may have registered this unverified email; the
            # provider has now proven ownership, so lock out that password
            # and any reset/verification links issued to it.
            user.verification_tokens.filter(is_used=False).update(
                is_used=True, used_at=timezone.now()
            )
            # ...and any social login someone attached to it before
            user.socialaccount_set.all().delete()
            user.set_unusable_password()
            user.email_verified = True
            user.email_verified_at = timezone.now()
            user.save(update_fields=["password", "email_verified", "email_verified_at"])
        sociallogin.connect(request, user)

    def save_user(self, request, sociallogin, form=None):
        """Save a new social signup.

        pre_social_login only lets a signup through for an email the provider
        verified. allauth creates the EmailAddress rows (setup_user_email)
        during super().save_user, marked verified where the provider vouched
        for them, and the sync mirrors that onto User.email_verified (no more
        forcing it to True). Like email signup, no roles are set (#77).
        """
        from .email_sync import sync_primary_email
        from .signals import SKIP_SYNC_ATTR

        previous = getattr(sociallogin.user, SKIP_SYNC_ATTR, False)
        setattr(sociallogin.user, SKIP_SYNC_ATTR, True)
        try:
            user = super().save_user(request, sociallogin, form)
        finally:
            setattr(sociallogin.user, SKIP_SYNC_ATTR, previous)
        sync_primary_email(user)
        return user
