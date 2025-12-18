"""
URL patterns for product-related views.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Browse products (public)
    path('', views.products_browse_view, name='products_browse'),
    
    # Category browsing (public)
    path('category/<int:category_id>/', views.category_products_view, name='category_products'),
    
    # Product detail (public)
    path('<int:product_id>/', views.product_public_detail_view, name='product_detail'),
    
    # Product CRUD (seller only)
    path('create/', views.product_create_view, name='product_create'),
    path('<int:product_id>/edit/', views.product_edit_view, name='product_edit'),
    path('<int:product_id>/delete/', views.product_delete_view, name='product_delete'),
    path('<int:product_id>/seller/', views.product_detail_view, name='product_seller_detail'),
    
    # Images
    path('<int:product_id>/images/', views.product_images_view, name='product_images'),
    path('image/<int:image_id>/delete/', views.product_image_delete_view, name='product_image_delete'),
    path('<int:product_id>/images/reorder/', views.product_image_reorder_view, name='product_image_reorder'),
    
    # Publish/Unpublish
    path('<int:product_id>/publish/', views.product_publish_view, name='product_publish'),
    path('<int:product_id>/unpublish/', views.product_unpublish_view, name='product_unpublish'),
]
