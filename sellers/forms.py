"""
Forms for seller onboarding and account management.
"""

from django import forms
from django.core.exceptions import ValidationError

from .models import (
    TRADER_STATEMENT,
    Seller,
    free_shop_slug,
    is_shop_slug_free,
    shop_slug_from_name,
)


class ShopSetupForm(forms.ModelForm):
    """Open a shop or edit it. Left empty, the URL comes from the shop name."""

    class Meta:
        model = Seller
        fields = [
            "shop_name",
            "shop_slug",
            "shop_description",
            "shop_image",
            "location",
        ]
        widgets = {
            "shop_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Your shop name",
                    "maxlength": "255",
                }
            ),
            "shop_slug": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "shop-name (lowercase, no spaces)",
                    "maxlength": "50",
                }
            ),
            "shop_description": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Tell buyers about your shop",
                    "rows": 4,
                }
            ),
            "shop_image": forms.FileInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg",
                    "accept": "image/*",
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Your location (city, country)",
                    "maxlength": "255",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["shop_slug"].required = False
        self.fields["shop_slug"].widget.attrs[
            "placeholder"
        ] = "Prazno: pravi se od naziva prodavnice"

    def clean_shop_slug(self):
        """A typed slug must be free; an empty one is filled in clean()."""
        typed = self.cleaned_data.get("shop_slug") or ""
        if not typed:
            return ""
        # Validate what will be saved, e.g. "my_shop_" is saved as "my_shop"
        shop_slug = shop_slug_from_name(typed)
        if not shop_slug:
            raise ValidationError("Unesite slova ili brojeve.")
        if not is_shop_slug_free(shop_slug, exclude_pk=self.instance.pk):
            raise ValidationError("Ova adresa prodavnice je zauzeta.")
        return shop_slug

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("shop_slug") and "shop_slug" not in self.errors:
            if self.instance.pk:
                cleaned["shop_slug"] = self.instance.shop_slug
            else:
                cleaned["shop_slug"] = free_shop_slug(
                    shop_slug_from_name(cleaned.get("shop_name"))
                )
        return cleaned


class BankDetailsForm(forms.ModelForm):
    """Form for seller to enter bank details."""

    class Meta:
        model = Seller
        fields = ["bank_account_holder", "bank_name", "bank_account_number"]
        widgets = {
            "bank_account_holder": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Full name as it appears on account",
                    "maxlength": "255",
                }
            ),
            "bank_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Bank name",
                    "maxlength": "255",
                }
            ),
            "bank_account_number": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "IBAN or account number",
                    "maxlength": "50",
                }
            ),
        }

    def clean_bank_account_number(self):
        """Validate bank account number is not empty."""
        account_number = self.cleaned_data.get("bank_account_number")
        if not account_number or len(account_number) < 8:
            raise ValidationError("Please enter a valid account number or IBAN.")
        return account_number


STORE_FIELDS = ("shop_name", "shop_description", "shop_image")


class SellerAccountSettingsForm(forms.ModelForm):
    """Seller settings. The store fields only for a seller with a store."""

    is_trader = forms.BooleanField(
        required=False,
        label=TRADER_STATEMENT,
        widget=forms.CheckboxInput(attrs={"class": "mt-1"}),
    )

    class Meta:
        model = Seller
        fields = ["shop_name", "shop_description", "shop_image", "location"]
        widgets = {
            "shop_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Your shop name",
                }
            ),
            "shop_description": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Tell buyers about your shop",
                    "rows": 4,
                }
            ),
            "shop_image": forms.FileInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg",
                    "accept": "image/*",
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Your location",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        """Initialize form with user instance."""
        self.user = user
        super().__init__(*args, **kwargs)
        if not self.instance.has_store:
            for name in STORE_FIELDS:
                del self.fields[name]
        # An outdated confirmation starts unticked so the seller re-confirms
        self.fields["is_trader"].initial = (
            self.instance.is_trader and not self.instance.trader_statement_outdated
        )

    def save(self, commit=True):
        """Save the seller; the account email is changed at /auth/email/."""
        seller = super().save(commit=False)

        # Keep the original confirmation while the statement is unchanged
        if not self.cleaned_data.get("is_trader"):
            seller.clear_trader()
        elif not seller.is_trader or seller.trader_statement_outdated:
            seller.confirm_trader()

        if commit:
            seller.save()
            self._save_m2m()
        else:
            self.save_m2m = self._save_m2m
        return seller
