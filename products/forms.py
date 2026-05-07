"""
Forms for product management (CRUD operations).
"""

from django import forms
from django.core.exceptions import ValidationError
from .models import Product, ProductImage, ProductCategory, ProductCondition


class ProductForm(forms.ModelForm):
    """Form for creating and editing products."""

    class Meta:
        model = Product
        fields = ['title', 'description', 'price', 'category', 'condition', 'stock', 'status']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Naziv proizvoda',
                'maxlength': '255'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Detaljan opis proizvoda',
                'rows': 6
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': '0.00',
                'min': '0.01',
                'step': '0.01'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
            }),
            'condition': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': '1',
                'min': '0'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
            }),
        }

    def clean_title(self):
        """Validate title is not empty."""
        title = self.cleaned_data.get('title')
        if not title or len(title.strip()) == 0:
            raise ValidationError('Naziv proizvoda je obavezan.')
        return title.strip()

    def clean_description(self):
        description = self.cleaned_data.get('description')
        if not description or len(description.strip()) == 0:
            raise ValidationError('Opis proizvoda je obavezan.')
        return description.strip()

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price and price <= 0:
            raise ValidationError('Cena mora biti veća od 0.')
        return price

    def clean_stock(self):
        stock = self.cleaned_data.get('stock')
        if stock is not None and stock < 0:
            raise ValidationError('Zalihe ne mogu biti negativne.')
        return stock


class ProductImageForm(forms.ModelForm):
    """Form for uploading product images."""

    class Meta:
        model = ProductImage
        fields = ['image', 'alt_text']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg',
                'accept': 'image/*'
            }),
            'alt_text': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Opis slike (za pristupačnost)',
                'maxlength': '255'
            }),
        }

    def clean_image(self):
        """Validate image file."""
        image = self.cleaned_data.get('image')
        if not image:
            raise ValidationError('Slika je obavezna.')

        if image.size > 20 * 1024 * 1024:
            raise ValidationError('Veličina slike ne sme biti veća od 20MB.')

        valid_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
        file_ext = image.name.split('.')[-1].lower()
        if file_ext not in valid_extensions:
            raise ValidationError(f'Dozvoljeni formati: {", ".join(valid_extensions)}.')
        
        return image


class ProductImageFormSet(forms.BaseInlineFormSet):
    """FormSet for managing multiple product images."""
    
    def clean(self):
        """Ensure at least one image is uploaded for published products."""
        super().clean()
        
        # Check if parent form has any valid forms
        valid_forms = [f for f in self.forms if f.cleaned_data and not f.cleaned_data.get('DELETE', False)]
        
        # This will be handled in the view, just basic validation here
        if len(valid_forms) == 0 and not self.instance.pk:
            # For new products, at least one image will be required in the view
            pass


class BulkProductImageForm(forms.Form):
    """Form for bulk uploading multiple product images at once."""

    images = forms.FileField(
        required=True,
        label='Odaberite slike',
        help_text='Možete odabrati više slika odjednom. Svaka slika će biti dodana proizvodu.',
        widget=forms.FileInput(attrs={
            'accept': 'image/*',
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow multiple files by modifying the widget's input tag
        self.fields['images'].widget.attrs['multiple'] = True
        
    def clean(self):
        """Validate all image files."""
        cleaned_data = super().clean()
        
        # Get files list
        files = self.files.getlist('images')
        
        if not files:
            raise ValidationError('Potrebna je barem jedna slika.')

        valid_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']

        for file in files:
            if file.size > 20 * 1024 * 1024:
                raise ValidationError(f'{file.name}: Veličina slike ne sme biti veća od 20MB.')

            file_ext = file.name.split('.')[-1].lower()
            if file_ext not in valid_extensions:
                raise ValidationError(f'{file.name}: Dozvoljeni formati: {", ".join(valid_extensions)}.')
        
        # Store the validated files in cleaned_data
        cleaned_data['images'] = files
        return cleaned_data
