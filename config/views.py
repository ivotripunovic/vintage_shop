"""
Core views for Vintage Shop.
"""

from django.shortcuts import render


def home_view(request):
    """Home page view."""
    context = {
        'page_title': 'Home',
    }
    return render(request, 'core/home.html', context)
