from django.utils import timezone

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
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

    def get_signup_redirect_url(self, request):
        from django.urls import reverse
        return reverse("social-signup-complete")

    def get_login_redirect_url(self, request):
        return "/"


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """Block social login if no account exists with the provider's email.
        Allow signup process (coming from the register page) to pass through."""
        from allauth.core.exceptions import ImmediateHttpResponse
        from django.contrib import messages
        from django.contrib.auth import get_user_model
        from django.shortcuts import redirect

        # Allow registration flow initiated from the register page
        if sociallogin.state.get("process") == "signup":
            return

        if sociallogin.is_existing:
            return

        email = sociallogin.user.email
        if email:
            User = get_user_model()
            if User.objects.filter(email=email).exists():
                return

        messages.error(
            request,
            "Ne postoji nalog za ovaj Google nalog. Molimo vas da se najpre registrujete.",
        )
        raise ImmediateHttpResponse(redirect("/auth/register/"))

    def save_user(self, request, sociallogin, form=None):
        """Mark social users as buyers with verified email."""
        user = super().save_user(request, sociallogin, form)
        user.is_buyer = True
        user.email_verified = True
        user.email_verified_at = timezone.now()
        user.save(update_fields=["is_buyer", "email_verified", "email_verified_at"])
        return user
