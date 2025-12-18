"""
Views for seller onboarding, dashboard, and account management.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db import transaction, models
from django.core.paginator import Paginator
from django.db.models import Q, Count
from datetime import date, timedelta
from django.utils.timezone import now

from users.models import User
from .models import Seller, SellerSubscription
from .forms import (
    SellerRegistrationForm,
    ShopSetupForm,
    BankDetailsForm,
    SellerAccountSettingsForm
)
from products.models import Product, ProductCondition


@require_http_methods(["GET", "POST"])
def seller_register_view(request):
    """
    Step 1: Seller registration.
    Creates user account and redirects to shop setup.
    """
    if request.method == "POST":
        form = SellerRegistrationForm(request.POST)
        if form.is_valid():
            # Create user
            user = User.objects.create_user(
                email=form.cleaned_data['email'],
                username=form.cleaned_data['email'],
                password=form.cleaned_data['password1'],
                is_seller=True,
                is_buyer=False,
            )
            
            # Authenticate and log in
            user = authenticate(username=form.cleaned_data['email'], password=form.cleaned_data['password1'])
            login(request, user)
            
            # Redirect to shop setup
            messages.success(request, 'Account created! Now set up your shop.')
            return redirect('seller_shop_setup')
    else:
        form = SellerRegistrationForm()
    
    return render(request, 'sellers/register.html', {'form': form})


@login_required
@require_http_methods(["GET", "POST"])
def seller_shop_setup_view(request):
    """
    Step 2: Seller shop setup.
    Collects shop name, description, location, image.
    """
    if not request.user.is_seller:
        messages.error(request, 'You must be a seller to access this page.')
        return redirect('seller_register')
    
    if request.method == "POST":
        form = ShopSetupForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                seller, created = Seller.objects.get_or_create(user=request.user)
                form_instance = form.save(commit=False)
                form_instance.user = request.user
                form_instance.id = seller.id if seller.id else None
                form_instance.save()
                
                messages.success(request, 'Shop setup complete! Now add your bank details.')
                return redirect('seller_bank_details')
    else:
        # Pre-fill if seller already exists
        try:
            seller = request.user.seller_profile
            form = ShopSetupForm(instance=seller)
        except Seller.DoesNotExist:
            form = ShopSetupForm()
    
    return render(request, 'sellers/shop_setup.html', {'form': form})


@require_http_methods(["GET", "POST"])
def seller_bank_details_view(request):
    """
    Step 3: Seller bank details.
    Collects bank account information for payments.
    """
    if not request.user.is_authenticated or not request.user.is_seller:
        messages.error(request, 'You must be a seller to access this page.')
        return redirect('login')
    
    try:
        seller = request.user.seller_profile
    except Seller.DoesNotExist:
        messages.error(request, 'Please complete shop setup first.')
        return redirect('seller_shop_setup')
    
    if request.method == "POST":
        form = BankDetailsForm(request.POST, instance=seller)
        if form.is_valid():
            with transaction.atomic():
                seller = form.save()
                
                # Create initial subscription if doesn't exist
                if not seller.active_subscription:
                    start_date = now().date()
                    renewal_date = start_date + timedelta(days=30)
                    SellerSubscription.objects.create(
                        seller=seller,
                        plan_type='monthly',
                        start_date=start_date,
                        renewal_date=renewal_date,
                        status='active',
                        amount=9.99
                    )
                
                messages.success(request, 'Bank details saved! Your seller account is ready.')
                return redirect('seller_dashboard')
    else:
        form = BankDetailsForm(instance=seller)
    
    return render(request, 'sellers/bank_details.html', {'form': form, 'seller': seller})


@login_required
@require_http_methods(["GET"])
def seller_dashboard_view(request):
    """
    Seller dashboard showing overview and key metrics.
    """
    if not request.user.is_seller:
        messages.error(request, 'You are not authorized to access this page.')
        return redirect('home')
    
    # Get or create seller profile (should exist via signal, but handle just in case)
    seller, created = Seller.objects.get_or_create(
        user=request.user,
        defaults={
            'shop_name': request.user.email.split('@')[0],
            'shop_slug': request.user.email.split('@')[0].replace('.', '-'),
        }
    )
    
    # If newly created, also create subscription
    if created and not seller.active_subscription:
        start_date = now().date()
        renewal_date = start_date + timedelta(days=30)
        SellerSubscription.objects.create(
            seller=seller,
            plan_type='monthly',
            start_date=start_date,
            renewal_date=renewal_date,
            status='active',
            amount=9.99
        )
    
    # Get seller statistics
    total_products = seller.products.count()
    published_products = seller.products.filter(status='published').count()
    draft_products = seller.products.filter(status='draft').count()
    
    # Get active subscription
    subscription = seller.active_subscription
    
    # Get recent products
    recent_products = seller.products.all()[:5]
    
    context = {
        'seller': seller,
        'total_products': total_products,
        'published_products': published_products,
        'draft_products': draft_products,
        'subscription': subscription,
        'recent_products': recent_products,
    }
    
    return render(request, 'sellers/dashboard.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def seller_settings_view(request):
    """
    Seller account settings page.
    Allows editing of shop details and email.
    """
    if not request.user.is_seller:
        messages.error(request, 'You are not authorized to access this page.')
        return redirect('home')
    
    # Get or create seller profile
    seller, created = Seller.objects.get_or_create(
        user=request.user,
        defaults={
            'shop_name': request.user.email.split('@')[0],
            'shop_slug': request.user.email.split('@')[0].replace('.', '-'),
        }
    )
    
    if request.method == "POST":
        form = SellerAccountSettingsForm(request.POST, request.FILES, instance=seller, user=request.user)
        if form.is_valid():
            seller = form.save()
            messages.success(request, 'Account settings updated successfully.')
            return redirect('seller_settings')
    else:
        form = SellerAccountSettingsForm(instance=seller, user=request.user)
    
    # Get subscription info for display
    subscription = seller.active_subscription
    
    context = {
        'form': form,
        'seller': seller,
        'subscription': subscription,
    }
    
    return render(request, 'sellers/settings.html', context)


@login_required
@require_http_methods(["GET"])
def seller_products_list_view(request):
    """
    List all products for the logged-in seller.
    """
    if not request.user.is_seller:
        messages.error(request, 'You are not authorized to access this page.')
        return redirect('home')
    
    # Get or create seller profile
    seller, created = Seller.objects.get_or_create(
        user=request.user,
        defaults={
            'shop_name': request.user.email.split('@')[0],
            'shop_slug': request.user.email.split('@')[0].replace('.', '-'),
        }
    )
    
    # Get filter parameters
    status_filter = request.GET.get('status')
    
    products = seller.products.all()
    
    if status_filter and status_filter in ['draft', 'published', 'sold', 'archived']:
        products = products.filter(status=status_filter)
    
    # Count by status
    status_counts = {
        'all': seller.products.count(),
        'published': seller.products.filter(status='published').count(),
        'draft': seller.products.filter(status='draft').count(),
        'sold': seller.products.filter(status='sold').count(),
        'archived': seller.products.filter(status='archived').count(),
    }
    
    context = {
        'products': products,
        'status_counts': status_counts,
        'current_status': status_filter or 'all',
    }
    
    return render(request, 'sellers/products_list.html', context)


@require_http_methods(["GET"])
def shops_browse_view(request):
    """
    Browse all active shops with published products (public view).
    """
    # Get search parameter
    search_query = request.GET.get('q', '')
    sort_by = request.GET.get('sort', '-created_at')
    
    # Get sellers with at least one published product
    sellers = Seller.objects.filter(
        status='active',
        products__status='published'
    ).distinct().annotate(
        published_count=Count('products', filter=models.Q(products__status='published'))
    )
    
    # Apply search
    if search_query:
        sellers = sellers.filter(
            Q(shop_name__icontains=search_query) | 
            Q(shop_description__icontains=search_query) |
            Q(location__icontains=search_query)
        )
    
    # Apply sorting
    if sort_by == 'name':
        sellers = sellers.order_by('shop_name')
    elif sort_by == '-products':
        sellers = sellers.order_by('-published_count')
    else:
        sellers = sellers.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(sellers, 12)  # 12 shops per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'sellers': page_obj.object_list,
        'search_query': search_query,
        'sort_by': sort_by,
        'page_title': 'Browse Shops',
    }
    
    return render(request, 'sellers/browse.html', context)


@require_http_methods(["GET"])
def shop_detail_view(request, shop_slug):
    """
    View a specific shop with all its published products.
    """
    seller = get_object_or_404(
        Seller.objects.annotate(
            published_count=Count('products', filter=models.Q(products__status='published'))
        ),
        shop_slug=shop_slug,
        status='active'
    )
    
    # Get published products for this shop
    products = seller.products.filter(status='published').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(products, 12)  # 12 products per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'seller': seller,
        'page_obj': page_obj,
        'products': page_obj.object_list,
        'page_title': seller.shop_name,
    }
    
    return render(request, 'sellers/shop_detail.html', context)
