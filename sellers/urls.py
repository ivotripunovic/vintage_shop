"""
URL patterns for seller-related views.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Browse shops (public)
    path('', views.shops_browse_view, name='shops_browse'),
    path('<slug:shop_slug>/', views.shop_detail_view, name='shop_detail'),
    
    # Onboarding
    path('register/', views.seller_register_view, name='seller_register'),
    path('shop-setup/', views.seller_shop_setup_view, name='seller_shop_setup'),
    path('bank-details/', views.seller_bank_details_view, name='seller_bank_details'),
    
    # Dashboard and settings
    path('dashboard/', views.seller_dashboard_view, name='seller_dashboard'),
    path('settings/', views.seller_settings_view, name='seller_settings'),
    
    # Products
    path('products/', views.seller_products_list_view, name='seller_products_list'),
]
