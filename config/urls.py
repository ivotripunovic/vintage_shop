"""
URL configuration for Vintage Shop project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""

from allauth.urls import build_provider_urlpatterns
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from core.views import (
    health,
    install_app,
    manifest,
    robots,
    waitlist_confirm,
    waitlist_subscribe,
    waitlist_unsubscribe,
)

from . import views

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # Authentication
    # allauth: signup, login, logout, verification, password, email change
    path("auth/", include("allauth.account.urls")),
    path("auth/", include("users.urls")),
    path("auth/social/", include("allauth.socialaccount.urls")),
    path("auth/social/", include(build_provider_urlpatterns())),
    # allauth was mounted here before #77
    re_path(
        r"^auth/accounts/(?P<rest>.*)$",
        RedirectView.as_view(url="/auth/%(rest)s", query_string=True),
    ),
    # Sellers
    path("seller/", include("sellers.urls")),
    # Products
    path("products/", include("products.urls")),
    # Chat
    path("chat/", include("chat.urls")),
    # Favourite sellers and wishlist
    path("favourites/", include("favourites.urls")),
    # Sales marked by sellers
    path("sales/", include("orders.urls")),
    # Ratings between buyers and sellers
    path("ratings/", include("ratings.urls")),
    # Home & Core
    path("", views.home_view, name="home"),
    path(
        "favicon.ico",
        RedirectView.as_view(url=settings.STATIC_URL + "favicon.ico", permanent=True),
    ),
    path("manifest.webmanifest", manifest, name="manifest"),
    path("install/", install_app, name="install_app"),
    path("robots.txt", robots, name="robots"),
    path("health/", health, name="health"),
    path("waitlist/subscribe/", waitlist_subscribe, name="waitlist_subscribe"),
    path("waitlist/confirm/<str:token>/", waitlist_confirm, name="waitlist_confirm"),
    path(
        "waitlist/unsubscribe/<str:token>/",
        waitlist_unsubscribe,
        name="waitlist_unsubscribe",
    ),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
