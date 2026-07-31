"""
URL configuration for Vintage Shop project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from allauth.urls import build_provider_urlpatterns
from . import views
from core.views import waitlist_subscribe

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # Authentication
    path("auth/", include("users.urls")),
    path("auth/social/", include("allauth.socialaccount.urls")),
    path("auth/social/", include(build_provider_urlpatterns())),
    # allauth.account.urls is not used directly but must be mounted so allauth's
    # internal reverse() calls (e.g. account_signup) resolve during the OAuth flow.
    path("auth/accounts/", include("allauth.account.urls")),
    # Sellers
    path("seller/", include("sellers.urls")),
    # Products
    path("products/", include("products.urls")),
    # Chat
    path("chat/", include("chat.urls")),
    # Home & Core
    path("", views.home_view, name="home"),
    path("waitlist/subscribe/", waitlist_subscribe, name="waitlist_subscribe"),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
