"""
Forms for seller onboarding and account management.
"""

from django import forms
from django.core.exceptions import ValidationError
from .models import Seller, SellerSubscription
from users.models import User


class SellerRegistrationForm(forms.Form):
    """Form for seller registration during onboarding."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'your@email.com'
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

    def clean_email(self):
        """Validate that email is unique."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered.')
        return email

    def clean_password2(self):
        """Validate that passwords match."""
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError('Passwords do not match.')
        return password2


class ShopSetupForm(forms.ModelForm):
    """Form for seller to set up their shop."""

    class Meta:
        model = Seller
        fields = ['shop_name', 'shop_slug', 'shop_description', 'shop_image', 'location']
        widgets = {
            'shop_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Your shop name',
                'maxlength': '255'
            }),
            'shop_slug': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'shop-name (lowercase, no spaces)',
                'maxlength': '50'
            }),
            'shop_description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Tell buyers about your shop',
                'rows': 4
            }),
            'shop_image': forms.FileInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg',
                'accept': 'image/*'
            }),
            'location': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Your location (city, country)',
                'maxlength': '255'
            }),
        }

    def clean_shop_slug(self):
        """Validate shop slug is unique and properly formatted."""
        shop_slug = self.cleaned_data.get('shop_slug')
        if not shop_slug:
            raise ValidationError('Shop slug is required.')
        
        # Check if slug already exists
        if Seller.objects.filter(shop_slug=shop_slug).exists():
            raise ValidationError('This shop name is already taken.')
        
        # Validate slug format (lowercase, no spaces, alphanumeric + hyphens)
        if not shop_slug.replace('-', '').replace('_', '').isalnum():
            raise ValidationError('Shop name can only contain letters, numbers, hyphens, and underscores.')
        
        return shop_slug.lower()


class BankDetailsForm(forms.ModelForm):
    """Form for seller to enter bank details."""

    class Meta:
        model = Seller
        fields = ['bank_account_holder', 'bank_name', 'bank_account_number']
        widgets = {
            'bank_account_holder': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Full name as it appears on account',
                'maxlength': '255'
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Bank name',
                'maxlength': '255'
            }),
            'bank_account_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'IBAN or account number',
                'maxlength': '50'
            }),
        }

    def clean_bank_account_number(self):
        """Validate bank account number is not empty."""
        account_number = self.cleaned_data.get('bank_account_number')
        if not account_number or len(account_number) < 8:
            raise ValidationError('Please enter a valid account number or IBAN.')
        return account_number


class SellerAccountSettingsForm(forms.ModelForm):
    """Form for seller to update their account settings."""

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'your@email.com'
        })
    )

    class Meta:
        model = Seller
        fields = ['shop_name', 'shop_description', 'shop_image', 'location']
        widgets = {
            'shop_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Your shop name'
            }),
            'shop_description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Tell buyers about your shop',
                'rows': 4
            }),
            'shop_image': forms.FileInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg',
                'accept': 'image/*'
            }),
            'location': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Your location'
            }),
        }

    def __init__(self, user, *args, **kwargs):
        """Initialize form with user instance."""
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['email'].initial = user.email

    def clean_email(self):
        """Validate that new email is unique if changed."""
        email = self.cleaned_data.get('email')
        if email != self.user.email:
            if User.objects.filter(email=email).exists():
                raise ValidationError('This email is already in use.')
        return email

    def save(self, commit=True):
        """Save seller and update user email."""
        seller = super().save(commit=False)
        # Update user email if changed
        email = self.cleaned_data.get('email')
        if email != self.user.email:
            self.user.email = email
            self.user.username = email
            self.user.save()
        
        if commit:
            seller.save()
        return seller
