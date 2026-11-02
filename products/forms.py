"""
Forms for product management (CRUD operations).
"""

import re
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .models import Product, ProductCategory, ProductCondition, ProductImage

MB = 1024 * 1024
# Per photo, and per upload request: nginx rejects bodies over 20 MB
# (client_max_body_size in deploy/nginx.conf) before Django sees them.
MAX_IMAGE_MB = 10
MAX_UPLOAD_MB = 19

# Whole dinars, optionally grouped by thousands (4500, 4.500, 4 500), with
# zero decimals allowed out of habit (4500,00); 4500,50 is rejected.
PRICE_PATTERN = re.compile(r"^(?P<whole>\d+|\d{1,3}(?:[. ]\d{3})+)(?:[.,]0{1,2})?$")
MAX_PRICE = 99_999_999  # Product.price has 10 digits, 2 of them decimals


def format_rsd(value):
    """Format a whole-dinar amount with dots between thousands: 4.500."""
    return f"{int(value):,}".replace(",", ".")


class PriceInput(forms.TextInput):
    """Text input showing whole dinars grouped by thousands."""

    def format_value(self, value):
        if isinstance(value, (int, Decimal)):
            return format_rsd(value)
        return super().format_value(value)


class ProductForm(forms.ModelForm):
    """Form for creating and editing products."""

    class Meta:
        model = Product
        fields = [
            "title",
            "description",
            "price",
            "category",
            "condition",
            "stock",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Naziv proizvoda",
                    "maxlength": "255",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Detaljan opis proizvoda",
                    "rows": 6,
                }
            ),
            "price": PriceInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "npr. 4.500",
                    "inputmode": "numeric",
                    "autocomplete": "off",
                }
            ),
            "category": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                }
            ),
            # Rendered as cards with descriptions in product_form.html
            "condition": forms.RadioSelect,
            "stock": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "min": "0",
                }
            ),
        }

    # Status is not edited here: the views save drafts and publish through
    # publish_error(), so the photo and listing limit rules always apply.

    # Whole dinars as text, so sellers can type thousands separators
    price = forms.CharField(label="Cena (RSD)", widget=Meta.widgets["price"])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, message in [
            ("title", "Naziv proizvoda je obavezan."),
            ("description", "Opis proizvoda je obavezan."),
            ("price", "Unesite cenu."),
        ]:
            self.fields[name].error_messages["required"] = message
        # Buyers browse and filter by both, so a listing needs them
        self.fields["category"].required = True
        self.fields["category"].empty_label = "Izaberite kategoriju"
        self.fields["category"].error_messages["required"] = "Izaberite kategoriju."
        self.fields["condition"].required = True
        self.fields["condition"].empty_label = None
        self.fields["condition"].error_messages["required"] = "Izaberite stanje."
        self.fields["stock"].required = False
        if not self.instance.pk:
            self.fields["stock"].initial = 1

    def clean_title(self):
        """Validate title is not empty."""
        title = self.cleaned_data.get("title")
        if not title or len(title.strip()) == 0:
            raise ValidationError("Naziv proizvoda je obavezan.")
        return title.strip()

    def clean_description(self):
        description = self.cleaned_data.get("description")
        if not description or len(description.strip()) == 0:
            raise ValidationError("Opis proizvoda je obavezan.")
        return description.strip()

    def clean_price(self):
        raw = (self.cleaned_data.get("price") or "").strip()
        match = PRICE_PATTERN.match(raw)
        if not match:
            raise ValidationError("Unesite cenu u celim dinarima, npr. 4.500.")
        price = int(re.sub(r"[. ]", "", match["whole"]))
        if price <= 0:
            raise ValidationError("Cena mora biti veća od 0.")
        if price > MAX_PRICE:
            raise ValidationError(
                f"Cena može biti najviše {format_rsd(MAX_PRICE)} RSD."
            )
        return Decimal(price)

    def clean_stock(self):
        stock = self.cleaned_data.get("stock")
        if stock is None:
            return 1  # the field sits in a collapsed section; one item by default
        if stock < 0:
            raise ValidationError("Zalihe ne mogu biti negativne.")
        return stock


class ProductImageForm(forms.ModelForm):
    """Form for uploading product images."""

    class Meta:
        model = ProductImage
        fields = ["image", "alt_text"]
        widgets = {
            "image": forms.FileInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg",
                    "accept": "image/*",
                }
            ),
            "alt_text": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                    "placeholder": "Opis slike (za pristupačnost)",
                    "maxlength": "255",
                }
            ),
        }

    def clean_image(self):
        """Validate image file."""
        image = self.cleaned_data.get("image")
        if not image:
            raise ValidationError("Slika je obavezna.")

        if image.size > MAX_IMAGE_MB * MB:
            raise ValidationError(
                f"Veličina slike ne sme biti veća od {MAX_IMAGE_MB} MB."
            )

        valid_extensions = ["jpg", "jpeg", "png", "gif", "webp"]
        file_ext = image.name.split(".")[-1].lower()
        if file_ext not in valid_extensions:
            raise ValidationError(f'Dozvoljeni formati: {", ".join(valid_extensions)}.')

        return image


class ProductImageFormSet(forms.BaseInlineFormSet):
    """FormSet for managing multiple product images."""

    def clean(self):
        """Ensure at least one image is uploaded for published products."""
        super().clean()

        # Check if parent form has any valid forms
        valid_forms = [
            f
            for f in self.forms
            if f.cleaned_data and not f.cleaned_data.get("DELETE", False)
        ]

        # This will be handled in the view, just basic validation here
        if len(valid_forms) == 0 and not self.instance.pk:
            # For new products, at least one image will be required in the view
            pass


class BulkProductImageForm(forms.Form):
    """Form for bulk uploading multiple product images at once."""

    images = forms.FileField(
        required=True,
        label="Odaberite slike",
        help_text="Možete odabrati više slika odjednom.",
        widget=forms.FileInput(
            attrs={
                "accept": "image/*",
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow multiple files by modifying the widget's input tag
        self.fields["images"].widget.attrs["multiple"] = True

    def clean(self):
        """Validate all image files."""
        cleaned_data = super().clean()

        # Get files list
        files = self.files.getlist("images")

        if not files:
            raise ValidationError("Potrebna je barem jedna slika.")

        valid_extensions = ["jpg", "jpeg", "png", "gif", "webp"]

        if sum(file.size for file in files) > MAX_UPLOAD_MB * MB:
            raise ValidationError(
                f"Izabrane slike zajedno prelaze {MAX_UPLOAD_MB} MB. "
                "Otpremite ih u više navrata."
            )

        for file in files:
            if file.size > MAX_IMAGE_MB * MB:
                raise ValidationError(
                    f"{file.name}: Veličina slike ne sme biti veća od "
                    f"{MAX_IMAGE_MB} MB."
                )

            file_ext = file.name.split(".")[-1].lower()
            if file_ext not in valid_extensions:
                raise ValidationError(
                    f'{file.name}: Dozvoljeni formati: {", ".join(valid_extensions)}.'
                )

        # Store the validated files in cleaned_data
        cleaned_data["images"] = files
        return cleaned_data
