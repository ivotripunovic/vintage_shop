"""
User authentication views (registration, login, logout, password reset).
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse

from .models import User
from .forms import (
    UserRegistrationForm,
    UserLoginForm,
    UserPasswordResetForm,
    UserPasswordSetForm,
    UserPasswordChangeForm,
)


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
                f'Account created! Check your email at {user.email} to verify your account.'
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
                    f'Please verify your email. Check {user.email} for verification link.'
                )
                return redirect('verify-email-resend', email=user.email)
            
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # Redirect to next page or home
            next_url = request.GET.get('next', 'home')
            messages.success(request, f'Welcome back, {user.email}!')
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
    messages.success(request, 'You have been logged out.')
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
                f'Password reset instructions have been sent to {user.email}.'
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
    # For MVP, we use a simple token approach stored in session
    # In production, use django-rest-auth or django-allauth for better security
    
    token_data = request.session.get('password_reset_token')
    if not token_data or token_data.get('token') != token:
        messages.error(request, 'Invalid or expired password reset link.')
        return redirect('password-reset-request')
    
    user_id = token_data.get('user_id')
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('password-reset-request')
    
    if request.method == 'POST':
        form = UserPasswordSetForm(user, request.POST)
        if form.is_valid():
            form.save()
            
            # Clear token
            if 'password_reset_token' in request.session:
                del request.session['password_reset_token']
            
            messages.success(request, 'Your password has been reset. Please login.')
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
    # For MVP, store verification token in session
    # In production, use a token model or JWT
    
    token_data = request.session.get('email_verification_token')
    if not token_data or token_data.get('token') != token:
        messages.error(request, 'Invalid or expired verification link.')
        return redirect('home')
    
    user_id = token_data.get('user_id')
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('home')
    
    # Mark email as verified
    user.email_verified = True
    user.save()
    
    # Clear token
    if 'email_verification_token' in request.session:
        del request.session['email_verification_token']
    
    messages.success(request, 'Email verified! You can now login.')
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
                messages.info(request, 'This email is already verified.')
            else:
                send_verification_email(user)
                messages.success(request, f'Verification email sent to {email}.')
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email.')
    
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
            messages.success(request, 'Your password has been changed.')
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
    
    # Store token in session (for MVP)
    # In production, create a token model or use JWT
    # For now, we'll use a simple approach with the token in the URL
    
    verification_url = f"{settings.SITE_DOMAIN}/auth/verify-email/{token}/"
    
    subject = 'Verify your Vintage Shop email'
    message = f"""
Hello {user.first_name or user.email},

Welcome to Vintage Shop! Please verify your email by clicking the link below:

{verification_url}

This link will expire in 24 hours.

If you didn't create this account, please ignore this email.

Best regards,
Vintage Shop Team
    """
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        
        # For MVP, we'll store the token validation in a simple way
        # In production, use a proper token model
    except Exception as e:
        print(f"Error sending verification email: {e}")


def send_password_reset_email(user):
    """Send password reset link to user."""
    token = get_random_string(50)
    
    reset_url = f"{settings.SITE_DOMAIN}/auth/reset-password/{token}/"
    
    subject = 'Reset your Vintage Shop password'
    message = f"""
Hello {user.first_name or user.email},

Click the link below to reset your password:

{reset_url}

This link will expire in 1 hour.

If you didn't request a password reset, please ignore this email.

Best regards,
Vintage Shop Team
    """
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except Exception as e:
        print(f"Error sending password reset email: {e}")
