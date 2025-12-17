"""
URL routing for user authentication.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Email Verification
    path('verify-email/<str:token>/', views.verify_email_view, name='verify-email'),
    path('verify-email-resend/', views.verify_email_resend_view, name='verify-email-resend'),
    
    # Password Reset
    path('password-reset/', views.password_reset_request_view, name='password-reset-request'),
    path('reset-password/<str:token>/', views.password_reset_confirm_view, name='password-reset-confirm'),
    
    # Account Management
    path('password-change/', views.password_change_view, name='password-change'),
    path('settings/', views.account_settings_view, name='account-settings'),
]
