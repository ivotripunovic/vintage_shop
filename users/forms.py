"""
Authentication forms for user registration, login, and password management.
"""

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from django.core.exceptions import ValidationError
from .models import User


class UserRegistrationForm(UserCreationForm):
    """Form for user registration (buyer or seller)."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'your@email.com'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'First name (optional)'
        })
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Last name (optional)'
        })
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Password'
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Confirm password'
        })
    )
    user_type = forms.ChoiceField(
        choices=[
            ('buyer', 'Želim da kupujem'),
            ('seller', 'Želim da prodajem'),
            ('both', 'Kupujem i prodajem'),
        ],
        widget=forms.RadioSelect(attrs={
            'class': 'mr-2'
        })
    )

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password1', 'password2', 'user_type')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Ova e-mail adresa je već registrovana.')
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError('Lozinke se ne poklapaju.')
        return password2

    def save(self, commit=True):
        """Save user with appropriate roles."""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email']  # Use email as username
        
        # Set user type based on choice
        user_type = self.cleaned_data.get('user_type')
        if user_type == 'buyer':
            user.is_buyer = True
            user.is_seller = False
        elif user_type == 'seller':
            user.is_buyer = False
            user.is_seller = True
        else:  # both
            user.is_buyer = True
            user.is_seller = True
        
        if commit:
            user.save()
        return user


class UserLoginForm(forms.Form):
    """Form for user login."""

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'your@email.com',
            'autofocus': True
        })
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Your password'
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'mr-2'
        })
    )

    def clean(self):
        """Authenticate user."""
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')
        
        if email and password:
            # Django auth backend uses USERNAME_FIELD, which we set to email
            self.user = authenticate(username=email, password=password)
            if self.user is None:
                raise ValidationError('Pogrešna e-mail adresa ili lozinka.')
            if not self.user.is_active:
                raise ValidationError('Ovaj nalog je deaktiviran.')
        return self.cleaned_data

    def get_user(self):
        """Return authenticated user."""
        return getattr(self, 'user', None)


class UserPasswordResetForm(forms.Form):
    """Form to request password reset via email."""

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'your@email.com'
        })
    )

    def clean_email(self):
        """Check if email exists."""
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise ValidationError('Nije pronađen nalog sa ovom e-adresom.')
        return email

    def get_user(self):
        """Return user with this email."""
        email = self.cleaned_data.get('email')
        return User.objects.get(email=email)


class UserPasswordSetForm(SetPasswordForm):
    """Form to set a new password (used in password reset)."""

    error_messages = {
        **SetPasswordForm.error_messages,
        "password_mismatch": "Lozinke se ne poklapaju.",
    }

    new_password1 = forms.CharField(
        label='Nova lozinka',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Nova lozinka'
        })
    )
    new_password2 = forms.CharField(
        label='Potvrda lozinke',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Potvrdite novu lozinku'
        })
    )


class UserPasswordChangeForm(forms.Form):
    """Form to change password for logged-in users."""

    old_password = forms.CharField(
        label='Current Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Your current password'
        })
    )
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'New password'
        })
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Confirm new password'
        })
    )

    def __init__(self, user, *args, **kwargs):
        """Initialize form with user instance."""
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        """Validate old password."""
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise ValidationError('Trenutna lozinka nije ispravna.')
        return old_password

    def clean(self):
        """Validate new passwords match."""
        new_password1 = self.cleaned_data.get('new_password1')
        new_password2 = self.cleaned_data.get('new_password2')
        
        if new_password1 and new_password2:
            if new_password1 != new_password2:
                raise ValidationError('Nove lozinke se ne poklapaju.')
            if new_password1 == self.cleaned_data.get('old_password'):
                raise ValidationError('Nova lozinka mora biti različita od trenutne.')
        
        return self.cleaned_data

    def save(self):
        """Set new password."""
        self.user.set_password(self.cleaned_data['new_password1'])
        self.user.save()
        return self.user
