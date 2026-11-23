"""
URL routing for the users app.

Sign-up, login, logout, email verification, password reset/change and email
change are allauth's (mounted at /auth/ in config/urls.py, #77). The paths
the custom flow used redirect to their allauth equivalents so old links and
bookmarks keep working.
"""

from django.urls import path
from django.views.generic import RedirectView

from . import views


def _to(pattern_name):
    return RedirectView.as_view(pattern_name=pattern_name, query_string=True)


urlpatterns = [
    # Old custom-flow paths
    path("register/", _to("account_signup")),
    path("password-reset/", _to("account_reset_password")),
    # Reset links expire after an hour; ask for a new one
    path(
        "reset-password/<str:token>/",
        RedirectView.as_view(url="/auth/password/reset/"),
    ),
    path("password-change/", _to("account_change_password")),
    path("verify-email-resend/", _to("account_email")),
    # Links from the old custom verification emails (all expired, #79)
    path("verify-email/<str:token>/", RedirectView.as_view(url="/auth/login/")),
    # Account Management
    path("settings/", views.account_settings_view, name="account-settings"),
    # The old welcome page after signup, with its buyer/seller choice (#89)
    path("social/welcome/", RedirectView.as_view(url="/")),
]
