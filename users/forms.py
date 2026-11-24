"""
Profile form for the account settings page. Auth forms are allauth's; see
users/allauth_forms.py.
"""

from django import forms
from django.core.exceptions import ValidationError

from .models import User


class UserProfileForm(forms.ModelForm):
    """Profile picture and short bio, edited on the account settings page."""

    remove_picture = forms.BooleanField(required=False, label="Ukloni sliku")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "profile_picture", "bio"]
        widgets = {
            "profile_picture": forms.FileInput(attrs={"accept": "image/*"}),
            "bio": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Nekoliko reči o sebi"}
            ),
        }

    def clean_profile_picture(self):
        """Validate a newly uploaded picture."""
        picture = self.cleaned_data.get("profile_picture")
        if picture and picture != self.initial.get("profile_picture"):
            if picture.size > 5 * 1024 * 1024:
                raise ValidationError("Veličina slike ne sme biti veća od 5MB.")
            valid_extensions = ["jpg", "jpeg", "png", "gif", "webp"]
            if picture.name.split(".")[-1].lower() not in valid_extensions:
                raise ValidationError(
                    f'Dozvoljeni formati: {", ".join(valid_extensions)}.'
                )
        return picture

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("remove_picture") and "profile_picture" not in (
            self.files or {}
        ):
            user.profile_picture = None
        if commit:
            user.save()
        return user
