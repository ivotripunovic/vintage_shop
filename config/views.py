"""
Core views for Vintage Shop.
"""

from django.shortcuts import render
from products.models import Product, ProductCategory


def home_view(request):
    """Home page view."""
    # Get featured products (latest published products)
    featured_products = Product.objects.filter(status='published').order_by('-created_at')[:6]
    
    # Get all categories
    categories = ProductCategory.objects.all()
    
    context = {
        'page_title': 'Home',
        'featured_products': featured_products,
        'categories': categories,
    }
    return render(request, 'core/home.html', context)
