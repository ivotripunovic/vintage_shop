"""
Views for product management (CRUD operations).
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db import transaction, models
from django.http import JsonResponse, HttpResponseForbidden
from django.core.paginator import Paginator
from django.db.models import Q

from .models import Product, ProductImage
from .forms import ProductForm, ProductImageForm, BulkProductImageForm
from sellers.models import Seller


def _get_seller_or_403(request):
    """Helper to get seller profile or return 403."""
    if not request.user.is_authenticated or not request.user.is_seller:
        return None
    
    try:
        return request.user.seller_profile
    except Seller.DoesNotExist:
        return None


@login_required
@require_http_methods(["GET", "POST"])
def product_create_view(request):
    """
    Create a new product.
    """
    seller = _get_seller_or_403(request)
    if not seller:
        messages.error(request, 'You must be a seller to create products.')
        return redirect('seller_register')
    
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = seller
            product.save()
            
            messages.success(request, 'Product created successfully. Now add images.')
            return redirect('product_images', product_id=product.id)
    else:
        form = ProductForm()
    
    context = {
        'form': form,
        'page_title': 'Create Product',
    }
    
    return render(request, 'products/product_form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def product_edit_view(request, product_id):
    """
    Edit an existing product.
    """
    seller = _get_seller_or_403(request)
    if not seller:
        return HttpResponseForbidden('You are not authorized to access this resource.')
    
    product = get_object_or_404(Product, id=product_id, seller=seller)
    
    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, 'Product updated successfully.')
            return redirect('product_detail', product_id=product.id)
    else:
        form = ProductForm(instance=product)
    
    context = {
        'form': form,
        'product': product,
        'page_title': f'Edit: {product.title}',
    }
    
    return render(request, 'products/product_form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def product_delete_view(request, product_id):
    """
    Delete a product (soft delete).
    """
    seller = _get_seller_or_403(request)
    if not seller:
        return HttpResponseForbidden('You are not authorized to access this resource.')
    
    product = get_object_or_404(Product, id=product_id, seller=seller)
    
    if request.method == "POST":
        product.delete()  # Uses soft delete from SoftDeleteModel
        messages.success(request, f'Product "{product.title}" deleted successfully.')
        return redirect('seller_products_list')
    
    context = {
        'product': product,
    }
    
    return render(request, 'products/product_confirm_delete.html', context)


@login_required
@require_http_methods(["GET"])
def product_detail_view(request, product_id):
    """
    View product details (seller view with edit option).
    """
    seller = _get_seller_or_403(request)
    if not seller:
        messages.error(request, 'You must be a seller to view product details.')
        return redirect('seller_register')
    
    product = get_object_or_404(Product, id=product_id, seller=seller)
    images = product.images.all()
    
    context = {
        'product': product,
        'images': images,
        'is_owner': product.seller == seller,
    }
    
    return render(request, 'products/product_detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def product_images_view(request, product_id):
    """
    Manage product images.
    """
    seller = _get_seller_or_403(request)
    if not seller:
        return HttpResponseForbidden('You are not authorized to access this resource.')
    
    product = get_object_or_404(Product, id=product_id, seller=seller)
    
    if request.method == "POST":
        form = BulkProductImageForm(request.POST, request.FILES)
        if form.is_valid():
            images = form.cleaned_data['images']
            
            with transaction.atomic():
                # Get current max order
                max_order = product.images.aggregate(max=models.Max('order')).get('max') or 0
                
                for idx, image_file in enumerate(images):
                    ProductImage.objects.create(
                        product=product,
                        image=image_file,
                        order=max_order + idx + 1,
                        alt_text=f'{product.title} - Image {max_order + idx + 2}'
                    )
            
            messages.success(request, f'{len(images)} image(s) uploaded successfully.')
            return redirect('seller_products_list')
    else:
        form = BulkProductImageForm()
    
    # Get existing images
    images = product.images.all()
    
    context = {
        'form': form,
        'product': product,
        'images': images,
    }
    
    return render(request, 'products/product_images.html', context)


@login_required
@require_http_methods(["POST"])
def product_image_delete_view(request, image_id):
    """
    Delete a specific product image.
    """
    seller = _get_seller_or_403(request)
    if not seller:
        return HttpResponseForbidden('You are not authorized to access this resource.')
    
    image = get_object_or_404(ProductImage, id=image_id, product__seller=seller)
    product = image.product
    
    image.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'message': 'Image deleted successfully.'})
    
    messages.success(request, 'Image deleted successfully.')
    return redirect('product_images', product_id=product.id)


@login_required
@require_http_methods(["POST"])
def product_image_reorder_view(request, product_id):
    """
    Reorder product images (AJAX).
    """
    seller = _get_seller_or_403(request)
    if not seller:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
    
    product = get_object_or_404(Product, id=product_id, seller=seller)
    
    # Expect JSON data with image order
    import json
    try:
        data = json.loads(request.body)
        image_ids = data.get('image_ids', [])
        
        with transaction.atomic():
            for order, image_id in enumerate(image_ids):
                ProductImage.objects.filter(
                    id=image_id,
                    product=product
                ).update(order=order)
        
        return JsonResponse({'status': 'success', 'message': 'Images reordered successfully.'})
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def product_publish_view(request, product_id):
    """
    Publish a product (draft to published).
    """
    seller = _get_seller_or_403(request)
    if not seller:
        return HttpResponseForbidden('You are not authorized to access this resource.')
    
    product = get_object_or_404(Product, id=product_id, seller=seller)
    
    # Check if product has at least one image
    if not product.images.exists():
        messages.error(request, 'Please add at least one image before publishing.')
        return redirect('product_images', product_id=product.id)
    
    product.publish()
    messages.success(request, f'"{product.title}" is now published and visible to buyers.')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'message': 'Product published.'})
    
    return redirect('seller_products_list')


@login_required
@require_http_methods(["POST"])
def product_unpublish_view(request, product_id):
    """
    Unpublish a product (published to draft).
    """
    seller = _get_seller_or_403(request)
    if not seller:
        return HttpResponseForbidden('You are not authorized to access this resource.')
    
    product = get_object_or_404(Product, id=product_id, seller=seller)
    product.unpublish()
    
    messages.success(request, f'"{product.title}" is now a draft and hidden from buyers.')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'message': 'Product unpublished.'})
    
    return redirect('seller_products_list')


@require_http_methods(["GET"])
def product_public_detail_view(request, product_id):
    """
    Public product detail page (for buyers).
    Shows product images, description, price, seller info, and related products.
    """
    product = get_object_or_404(Product, id=product_id, status='published')
    
    # Get product images
    images = product.images.all().order_by('order')
    
    # Get related products (same seller, published, excluding current product)
    related_products = (
        product.seller.products
        .filter(status='published')
        .exclude(id=product.id)
        .order_by('-created_at')[:6]
    )
    
    context = {
        'product': product,
        'images': images,
        'related_products': related_products,
        'page_title': product.title,
    }
    
    return render(request, 'products/product_public_detail.html', context)


@require_http_methods(["GET"])
def category_products_view(request, category_id):
    """
    Browse products in a specific category (public view).
    """
    from .models import ProductCategory
    
    category = get_object_or_404(ProductCategory, id=category_id)
    
    # Get search and filter parameters
    search_query = request.GET.get('q', '')
    condition_filter = request.GET.get('condition')
    sort_by = request.GET.get('sort', '-created_at')
    
    # Start with published products in this category
    products = Product.objects.filter(status='published', category=category)
    
    # Apply search
    if search_query:
        products = products.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Apply condition filter
    if condition_filter:
        products = products.filter(condition_id=condition_filter)
    
    # Apply sorting
    if sort_by in ['-created_at', 'created_at', '-price', 'price', 'title']:
        products = products.order_by(sort_by)
    else:
        products = products.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get conditions for filter
    from .models import ProductCondition
    conditions = ProductCondition.objects.all()
    
    context = {
        'category': category,
        'page_obj': page_obj,
        'products': page_obj.object_list,
        'search_query': search_query,
        'conditions': conditions,
        'selected_condition': condition_filter,
        'sort_by': sort_by,
        'page_title': f'{category.name} Products',
    }
    
    return render(request, 'products/category.html', context)


@require_http_methods(["GET"])
def products_browse_view(request):
    """
    Browse all published products (public view).
    """
    # Get search and filter parameters
    search_query = request.GET.get('q', '')
    category_filter = request.GET.get('category')
    condition_filter = request.GET.get('condition')
    sort_by = request.GET.get('sort', '-created_at')
    
    # Start with published products
    products = Product.objects.filter(status='published')
    
    # Apply search
    if search_query:
        products = products.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Apply category filter
    if category_filter:
        products = products.filter(category_id=category_filter)
    
    # Apply condition filter
    if condition_filter:
        products = products.filter(condition_id=condition_filter)
    
    # Apply sorting
    if sort_by in ['-created_at', 'created_at', '-price', 'price', 'title']:
        products = products.order_by(sort_by)
    else:
        products = products.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(products, 12)  # 12 products per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get unique categories and conditions for filters
    from .models import ProductCategory, ProductCondition
    categories = ProductCategory.objects.all()
    conditions = ProductCondition.objects.all()
    
    context = {
        'page_obj': page_obj,
        'products': page_obj.object_list,
        'search_query': search_query,
        'categories': categories,
        'conditions': conditions,
        'selected_category': category_filter,
        'selected_condition': condition_filter,
        'sort_by': sort_by,
        'page_title': 'Browse Products',
    }
    
    return render(request, 'products/browse.html', context)
