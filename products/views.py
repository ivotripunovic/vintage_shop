"""
Views for product management (CRUD operations).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Count, Q
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from sellers.models import Seller

from .forms import (
    MAX_IMAGE_MB,
    MAX_UPLOAD_MB,
    BulkProductImageForm,
    ProductForm,
    ProductImageForm,
)
from .models import Product, ProductImage
from .popularity import recent_viewer_count, record_view

# Statuses a seller can move to published / archived from the edit form
PUBLISHABLE_STATUSES = ("draft", "expired", "archived")
ARCHIVABLE_STATUSES = ("draft", "published", "expired")


def publish_error(seller, product):
    """Why the product can't be published right now, or None if it can."""
    if not product.images.exists():
        return "Dodajte bar jednu fotografiju pre objavljivanja."
    if not seller.can_publish(product):
        return seller.listing_limit_message()
    return None


def _get_seller_or_403(request):
    """Helper to get seller profile or return 403."""
    if not request.user.is_authenticated or not request.user.is_seller:
        return None

    try:
        return request.user.seller_profile
    except Seller.DoesNotExist:
        return None


def _last_used_defaults(seller):
    """Category and condition of the seller's latest listing, as form initial."""
    last = (
        seller.products.filter(is_deleted=False)
        .order_by("-created_at")
        .values("category", "condition")
        .first()
    )
    return {k: v for k, v in (last or {}).items() if v is not None}


@login_required
@require_http_methods(["GET", "POST"])
def product_create_view(request):
    """
    Create a new product.
    """
    seller = _get_seller_or_403(request)
    if not seller:
        messages.error(request, "Morate biti prodavac da biste dodavali proizvode.")
        return redirect("seller_register")

    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = seller
            product.status = "draft"
            product.save()

            messages.success(
                request, "Nacrt je sačuvan. Dodajte fotografije da biste ga objavili."
            )
            return redirect("product_images", product_id=product.id)
    else:
        form = ProductForm(initial=_last_used_defaults(seller))

    context = {
        "form": form,
        "page_title": "Dodaj proizvod",
        "autosave_key": f"product-form:{seller.id}:new",
    }

    return render(request, "products/product_form.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def product_edit_view(request, product_id):
    """
    Edit an existing product.
    """
    seller = _get_seller_or_403(request)
    if not seller:
        return HttpResponseForbidden("You are not authorized to access this resource.")

    product = get_object_or_404(Product, id=product_id, seller=seller)

    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save()
            action = request.POST.get("action")

            if action == "publish" and product.status in PUBLISHABLE_STATUSES:
                error = publish_error(seller, product)
                if error:
                    messages.error(request, f"Izmene su sačuvane, ali: {error}")
                    if not product.images.exists():
                        return redirect("product_images", product_id=product.id)
                    return redirect("product_seller_detail", product_id=product.id)
                product.publish()
                messages.success(request, f'"{product.title}" je objavljen.')
            elif action == "archive" and product.status in ARCHIVABLE_STATUSES:
                product.status = "archived"
                product.save()
                messages.success(request, f'"{product.title}" je arhiviran.')
            else:
                messages.success(request, "Proizvod je uspešno ažuriran.")
            return redirect("product_seller_detail", product_id=product.id)
    else:
        form = ProductForm(instance=product)

    context = {
        "form": form,
        "product": product,
        "page_title": f"Izmeni: {product.title}",
        "autosave_key": f"product-form:{seller.id}:{product.id}",
        "can_publish_action": product.status in PUBLISHABLE_STATUSES,
        "can_archive_action": product.status in ARCHIVABLE_STATUSES,
    }

    return render(request, "products/product_form.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def product_delete_view(request, product_id):
    """
    Delete a product (soft delete).
    """
    seller = _get_seller_or_403(request)
    if not seller:
        return HttpResponseForbidden("You are not authorized to access this resource.")

    product = get_object_or_404(Product, id=product_id, seller=seller)

    if request.method == "POST":
        product.delete()  # Uses soft delete from SoftDeleteModel
        messages.success(request, f'Proizvod "{product.title}" je obrisan.')
        return redirect("seller_products_list")

    context = {
        "product": product,
    }

    return render(request, "products/product_confirm_delete.html", context)


@login_required
@require_http_methods(["GET"])
def product_detail_view(request, product_id):
    """
    View product details (seller view with edit option).
    """
    seller = _get_seller_or_403(request)
    if not seller:
        messages.error(request, "Morate biti prodavac da biste videli ovu stranicu.")
        return redirect("seller_register")

    product = get_object_or_404(Product, id=product_id, seller=seller)
    images = product.images.all()

    context = {
        "product": product,
        "images": images,
        "is_owner": product.seller == seller,
        "publish_error": publish_error(seller, product),
        "uses_listing_slot": product.needs_new_listing_period,
        "listings_left": seller.listings_left_this_month(),
    }

    return render(request, "products/product_detail.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def product_images_view(request, product_id):
    """
    Manage product images.
    """
    seller = _get_seller_or_403(request)
    if not seller:
        return HttpResponseForbidden("You are not authorized to access this resource.")

    product = get_object_or_404(Product, id=product_id, seller=seller)

    if request.method == "POST":
        form = BulkProductImageForm(request.POST, request.FILES)
        if form.is_valid():
            images = form.cleaned_data["images"]

            with transaction.atomic():
                # Get current max order
                max_order = (
                    product.images.aggregate(max=models.Max("order")).get("max") or 0
                )

                for idx, image_file in enumerate(images):
                    ProductImage.objects.create(
                        product=product,
                        image=image_file,
                        order=max_order + idx + 1,
                        alt_text=f"{product.title} – fotografija {max_order + idx + 1}",
                    )

            messages.success(request, f"Otpremljeno fotografija: {len(images)}.")
            return redirect("product_seller_detail", product_id=product.id)
    else:
        form = BulkProductImageForm()

    # Get existing images
    images = product.images.all()

    context = {
        "form": form,
        "product": product,
        "images": images,
        "max_image_mb": MAX_IMAGE_MB,
        "max_upload_mb": MAX_UPLOAD_MB,
    }

    return render(request, "products/product_images.html", context)


@login_required
@require_http_methods(["POST"])
def product_image_delete_view(request, image_id):
    """
    Delete a specific product image.
    """
    seller = _get_seller_or_403(request)
    if not seller:
        return HttpResponseForbidden("You are not authorized to access this resource.")

    image = get_object_or_404(ProductImage, id=image_id, product__seller=seller)
    product = image.product

    image.delete()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {"status": "success", "message": "Image deleted successfully."}
        )

    messages.success(request, "Fotografija je obrisana.")
    return redirect("product_images", product_id=product.id)


@login_required
@require_http_methods(["POST"])
def product_image_move_view(request, image_id):
    """
    Move a photo to the front (cover), or one place up or down.

    Plain POST so it works without JavaScript; orders are renumbered 0..n-1.
    """
    seller = _get_seller_or_403(request)
    if not seller:
        return HttpResponseForbidden("You are not authorized to access this resource.")

    image = get_object_or_404(ProductImage, id=image_id, product__seller=seller)
    product = image.product
    direction = request.POST.get("to")

    with transaction.atomic():
        images = list(product.images.select_for_update())
        index = images.index(image)
        if direction == "first":
            new_index = 0
        elif direction == "up":
            new_index = max(index - 1, 0)
        elif direction == "down":
            new_index = min(index + 1, len(images) - 1)
        else:
            return HttpResponseBadRequest("Unknown direction.")

        images.insert(new_index, images.pop(index))
        for order, item in enumerate(images):
            if item.order != order:
                item.order = order
                item.save(update_fields=["order"])

    if direction == "first" and index != 0:
        messages.success(request, "Naslovna fotografija je promenjena.")
    url = reverse("product_images", args=[product.id])
    return redirect(f"{url}#image-{image.id}")


@login_required
@require_http_methods(["POST"])
def product_image_reorder_view(request, product_id):
    """
    Reorder product images (AJAX).
    """
    seller = _get_seller_or_403(request)
    if not seller:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=403)

    product = get_object_or_404(Product, id=product_id, seller=seller)

    # Expect JSON data with image order
    import json

    try:
        data = json.loads(request.body)
        image_ids = data.get("image_ids", [])

        with transaction.atomic():
            for order, image_id in enumerate(image_ids):
                ProductImage.objects.filter(id=image_id, product=product).update(
                    order=order
                )

        return JsonResponse(
            {"status": "success", "message": "Images reordered successfully."}
        )
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def product_publish_view(request, product_id):
    """
    Publish a product (draft to published).
    """
    seller = _get_seller_or_403(request)
    if not seller:
        return HttpResponseForbidden("You are not authorized to access this resource.")

    product = get_object_or_404(Product, id=product_id, seller=seller)

    error = publish_error(seller, product)
    if error:
        messages.error(request, error)
        if not product.images.exists():
            return redirect("product_images", product_id=product.id)
        return redirect("seller_products_list")

    product.publish()
    messages.success(request, f'"{product.title}" je objavljen i vidljiv kupcima.')

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": "success", "message": "Product published."})

    return redirect("seller_products_list")


@login_required
@require_http_methods(["POST"])
def product_unpublish_view(request, product_id):
    """
    Unpublish a product (published to draft).
    """
    seller = _get_seller_or_403(request)
    if not seller:
        return HttpResponseForbidden("You are not authorized to access this resource.")

    product = get_object_or_404(Product, id=product_id, seller=seller)
    product.unpublish()

    messages.success(request, f'"{product.title}" je sada nacrt i skriven od kupaca.')

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"status": "success", "message": "Product unpublished."})

    return redirect("seller_products_list")


@require_http_methods(["GET"])
def product_public_detail_view(request, product_id):
    """
    Public product detail page (for buyers).
    Shows product images, description, price, seller info, and related products.
    """
    product = get_object_or_404(
        Product.objects.select_related("seller").annotate(
            wishlist_count=Count("wishlisted_by")
        ),
        id=product_id,
        status="published",
        is_deleted=False,
        seller__status="active",
    )

    # Get product images
    images = product.images.all().order_by("order")

    # Get related products (same seller, published, excluding current product)
    related_products = (
        product.seller.products.filter(status="published")
        .exclude(id=product.id)
        .order_by("-created_at")[:6]
    )

    is_owner = (
        request.user.is_authenticated and product.seller.user_id == request.user.id
    )
    in_wishlist = (
        request.user.is_authenticated
        and product.wishlisted_by.filter(user=request.user).exists()
    )
    vid = None if is_owner else record_view(request, product)

    context = {
        "product": product,
        "images": images,
        "related_products": related_products,
        "page_title": product.title,
        "is_owner": is_owner,
        "in_wishlist": in_wishlist,
        "recent_viewers": recent_viewer_count(product.pk, exclude=vid),
    }

    return render(request, "products/product_public_detail.html", context)


@require_http_methods(["GET"])
def category_products_view(request, category_id):
    """
    Browse products in a specific category (public view).
    """
    from .models import ProductCategory

    category = get_object_or_404(ProductCategory, id=category_id)

    # Get search and filter parameters
    search_query = request.GET.get("q", "")
    condition_filter = request.GET.get("condition")
    premijum_only = request.GET.get("premijum") == "1"
    sort_by = request.GET.get("sort", "-created_at")

    # Include products from this category and all its subcategories
    products = (
        Product.objects.filter(
            status="published", category_id__in=category.get_all_ids()
        )
        .select_related("condition", "seller")
        .prefetch_related("images")
    )

    # Apply search
    if search_query:
        products = products.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    # Apply condition filter
    if condition_filter:
        products = products.filter(condition_id=condition_filter)

    # Only products from Premijum sellers
    if premijum_only:
        products = products.filter(seller__tier="premijum")

    # Apply sorting
    if sort_by in ["-created_at", "created_at", "-price", "price", "title"]:
        products = products.order_by(sort_by)
    else:
        products = products.order_by("-created_at")

    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Get conditions for filter
    from .models import ProductCondition

    conditions = ProductCondition.objects.all()

    context = {
        "category": category,
        "page_obj": page_obj,
        "products": page_obj.object_list,
        "search_query": search_query,
        "conditions": conditions,
        "selected_condition": condition_filter,
        "premijum_only": premijum_only,
        "sort_by": sort_by,
        "page_title": f"{category.name} Products",
    }

    return render(request, "products/category.html", context)


@require_http_methods(["GET"])
def products_browse_view(request):
    """
    Browse all published products (public view).
    """
    # Get search and filter parameters
    search_query = request.GET.get("q", "")
    category_filter = request.GET.get("category")
    condition_filter = request.GET.get("condition")
    premijum_only = request.GET.get("premijum") == "1"
    sort_by = request.GET.get("sort", "-created_at")

    # Start with published products
    products = (
        Product.objects.filter(status="published")
        .select_related("category", "seller")
        .prefetch_related("images")
    )

    # Apply search
    if search_query:
        products = products.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    # Apply category filter
    if category_filter:
        products = products.filter(category_id=category_filter)

    # Apply condition filter
    if condition_filter:
        products = products.filter(condition_id=condition_filter)

    # Only products from Premijum sellers
    if premijum_only:
        products = products.filter(seller__tier="premijum")

    # Apply sorting
    if sort_by in ["-created_at", "created_at", "-price", "price", "title"]:
        products = products.order_by(sort_by)
    else:
        products = products.order_by("-created_at")

    # Pagination
    paginator = Paginator(products, 12)  # 12 products per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Get unique categories and conditions for filters
    from .models import ProductCategory, ProductCondition

    categories = ProductCategory.objects.filter(parent=None).prefetch_related(
        "children"
    )
    conditions = ProductCondition.objects.all()

    context = {
        "page_obj": page_obj,
        "products": page_obj.object_list,
        "search_query": search_query,
        "categories": categories,
        "conditions": conditions,
        "selected_category": category_filter,
        "selected_condition": condition_filter,
        "premijum_only": premijum_only,
        "sort_by": sort_by,
        "page_title": "Browse Products",
    }

    return render(request, "products/browse.html", context)
