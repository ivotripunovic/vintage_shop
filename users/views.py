"""
User authentication views (registration, login, logout, password reset).
"""

import logging

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.utils.crypto import get_random_string
from django.core.mail import send_mail, BadHeaderError
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)

from .models import User, VerificationToken
from .forms import (
    UserRegistrationForm,
    UserLoginForm,
    UserPasswordResetForm,
    UserPasswordSetForm,
    UserPasswordChangeForm,
)
from django.utils import timezone
from datetime import timedelta


@csrf_protect
@require_http_methods(["GET", "POST"])
def register_view(request):
    """Register a new user (buyer or seller)."""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # Set email as not verified initially
            user.email_verified = False
            user.save()
            
            # Send verification email
            send_verification_email(user)
            
            messages.success(
                request,
                f'Nalog je kreiran! Proverite e-poštu na adresi {user.email} da biste verifikovali nalog.'
            )
            return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = UserRegistrationForm()
    
    context = {
        'form': form,
        'page_title': 'Register',
    }
    return render(request, 'users/register.html', context)


@csrf_protect
@require_http_methods(["GET", "POST"])
def login_view(request):
    """Login user."""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            user = form.get_user()
            
            # Check if email is verified
            if not user.email_verified:
                messages.warning(
                    request,
                    f'Molimo verifikujte e-poštu. Proverite {user.email} za link za verifikaciju.'
                )
                return redirect('verify-email-resend')
            
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # Redirect to next page or home
            next_url = request.GET.get('next', 'home')
            messages.success(request, f'Dobrodošli, {user.email}!')
            return redirect(next_url)
        else:
            for error in form.non_field_errors():
                messages.error(request, error)
    else:
        form = UserLoginForm()
    
    context = {
        'form': form,
        'page_title': 'Login',
    }
    return render(request, 'users/login.html', context)


@require_http_methods(["GET"])
@login_required(login_url='login')
def logout_view(request):
    """Logout user."""
    logout(request)
    messages.success(request, 'Uspešno ste se odjavili.')
    return redirect('home')


@csrf_protect
@require_http_methods(["GET", "POST"])
def password_reset_request_view(request):
    """Request password reset via email."""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = UserPasswordResetForm(request.POST)
        if form.is_valid():
            user = form.get_user()
            send_password_reset_email(user)
            
            messages.success(
                request,
                f'Uputstva za resetovanje lozinke su poslata na {user.email}.'
            )
            return redirect('login')
        else:
            for error in form.non_field_errors():
                messages.error(request, error)
    else:
        form = UserPasswordResetForm()
    
    context = {
        'form': form,
        'page_title': 'Reset Password',
    }
    return render(request, 'users/password_reset_request.html', context)


@csrf_protect
@require_http_methods(["GET", "POST"])
def password_reset_confirm_view(request, token):
    """Confirm password reset with token."""
    try:
        token_obj = VerificationToken.objects.get(
            token=token,
            token_type=VerificationToken.TOKEN_TYPE_PASSWORD
        )
    except VerificationToken.DoesNotExist:
        messages.error(request, 'Link za resetovanje lozinke je nevažeći ili je istekao.')
        return redirect('password-reset-request')

    if not token_obj.is_valid():
        messages.error(request, 'Link za resetovanje lozinke je nevažeći ili je istekao.')
        return redirect('password-reset-request')
    
    user = token_obj.user
    
    if request.method == 'POST':
        form = UserPasswordSetForm(user, request.POST)
        if form.is_valid():
            form.save()
            
            # Mark token as used
            token_obj.mark_used()
            
            messages.success(request, 'Vaša lozinka je resetovana. Molimo prijavite se.')
            return redirect('login')
    else:
        form = UserPasswordSetForm(user)
    
    context = {
        'form': form,
        'page_title': 'Reset Password',
    }
    return render(request, 'users/password_reset_confirm.html', context)


@require_http_methods(["GET", "POST"])
def verify_email_view(request, token):
    """Verify email with token."""
    try:
        token_obj = VerificationToken.objects.get(
            token=token,
            token_type=VerificationToken.TOKEN_TYPE_EMAIL
        )
    except VerificationToken.DoesNotExist:
        messages.error(request, 'Link za verifikaciju je nevažeći ili je istekao.')
        return redirect('home')

    if not token_obj.is_valid():
        messages.error(request, 'Link za verifikaciju je nevažeći ili je istekao.')
        return redirect('home')
    
    # Mark email as verified
    user = token_obj.user
    user.email_verified = True
    user.email_verified_at = timezone.now()
    user.save()
    
    # Mark token as used
    token_obj.mark_used()
    
    messages.success(request, 'E-pošta je verifikovana! Možete se prijaviti.')
    return redirect('login')


@csrf_protect
@require_http_methods(["GET", "POST"])
def verify_email_resend_view(request):
    """Resend email verification."""
    if request.method == 'POST':
        email = request.POST.get('email', '')
        try:
            user = User.objects.get(email=email)
            if user.email_verified:
                messages.info(request, 'Ova e-pošta je već verifikovana.')
            else:
                send_verification_email(user)
                messages.success(request, f'Verifikacioni e-mail je poslat na {email}.')
        except User.DoesNotExist:
            messages.error(request, 'Nije pronađen nalog sa ovom e-adresom.')
    
    context = {
        'page_title': 'Verify Email',
    }
    return render(request, 'users/verify_email_resend.html', context)


@csrf_protect
@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def password_change_view(request):
    """Change password for logged-in user."""
    if request.method == 'POST':
        form = UserPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vaša lozinka je promenjena.')
            return redirect('account-settings')
    else:
        form = UserPasswordChangeForm(request.user)
    
    context = {
        'form': form,
        'page_title': 'Change Password',
    }
    return render(request, 'users/password_change.html', context)


@login_required(login_url='login')
def account_settings_view(request):
    """User account settings page."""
    context = {
        'page_title': 'Account Settings',
    }
    return render(request, 'users/account_settings.html', context)


# ============================================================================
# Email Sending Utilities
# ============================================================================

def send_verification_email(user):
    """Send email verification link to user."""
    token = get_random_string(50)
    VerificationToken.objects.create(
        user=user,
        token=token,
        token_type=VerificationToken.TOKEN_TYPE_EMAIL,
        expires_at=timezone.now() + timedelta(hours=24),
    )

    verification_url = f"{settings.SITE_DOMAIN}/auth/verify-email/{token}/"
    site_name = settings.SITE_NAME
    name = user.first_name or user.email
    subject = f"Potvrdite vašu {site_name} adresu e-pošte"
    message = f"""Zdravo {name},

Dobrodošli na {site_name}! Potvrdite vašu adresu e-pošte klikom na link ispod:

{verification_url}

Link ističe za 24 sata.

Ako niste kreirali nalog, zanemarite ovu poruku.

Srdačan pozdrav,
Tim {site_name}
"""

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except BadHeaderError:
        logger.error("Invalid header in verification email for user %s", user.pk)
    except Exception:
        logger.exception("Failed to send verification email to user %s", user.pk)


def send_password_reset_email(user):
    """Send password reset link to user."""
    token = get_random_string(50)
    VerificationToken.objects.create(
        user=user,
        token=token,
        token_type=VerificationToken.TOKEN_TYPE_PASSWORD,
        expires_at=timezone.now() + timedelta(hours=1),
    )

    reset_url = f"{settings.SITE_DOMAIN}/auth/reset-password/{token}/"
    site_name = settings.SITE_NAME
    name = user.first_name or user.email
    subject = f"Resetovanje lozinke na {site_name}"
    message = f"""Zdravo {name},

Kliknite na link ispod da resetujete vašu lozinku:

{reset_url}

Link ističe za 1 sat.

Ako niste tražili resetovanje lozinke, zanemarite ovu poruku.

Srdačan pozdrav,
Tim {site_name}
"""

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except BadHeaderError:
        logger.error("Invalid header in password reset email for user %s", user.pk)
    except Exception:
        logger.exception("Failed to send password reset email to user %s", user.pk)
