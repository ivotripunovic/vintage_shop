"""
Sales: the seller marks a product as sold to a buyer from chat.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from products.models import Product
from ratings.services import buyer_averages
from users.models import User

from .models import Sale, can_be_sold


def sale_candidates(product):
    """Buyers who messaged the seller about the product and haven't bought it."""
    return (
        User.objects.filter(
            chat_conversations_as_buyer__product=product,
            chat_conversations_as_buyer__is_team=False,
        )
        .exclude(purchases__product=product)
        .distinct()
        .order_by("email")
    )


def _record_sale(product_id, buyer):
    """Record the sale under a row lock; None if the product can't be sold now."""
    with transaction.atomic():
        product = Product.objects.select_for_update().get(pk=product_id)
        # Checked again under the lock, so double submits can't oversell
        if not can_be_sold(product):
            return None
        sale = Sale.objects.create(
            product=product,
            product_title=product.title,
            seller=product.seller,
            buyer=buyer,
        )
        if product.stock == 1:
            product.stock = 0
            product.mark_sold()
        else:
            # Not save(): that would restart an expired listing's period
            Product.objects.filter(pk=product.pk).update(
                stock=F("stock") - 1, updated_at=timezone.now()
            )
    return sale


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def product_mark_sold_view(request, product_id):
    """Pick the buyer from chat and record the sale."""
    product = get_object_or_404(
        Product.objects.select_related("seller"), pk=product_id, is_deleted=False
    )
    if product.seller.user_id != request.user.id:
        return HttpResponseForbidden()
    if not can_be_sold(product):
        messages.error(request, "Ovaj artikal se ne može označiti kao prodat.")
        return redirect("seller_products_list")

    candidates = sale_candidates(product)

    if request.method == "POST":
        buyer_id = request.POST.get("buyer", "")
        buyer = (
            candidates.filter(pk=int(buyer_id)).first() if buyer_id.isdigit() else None
        )
        if buyer is None:
            messages.error(request, "Izaberite kupca sa kojim ste se dogovorili.")
        else:
            try:
                sale = _record_sale(product.pk, buyer)
            except IntegrityError:
                # A parallel submit recorded the same buyer first
                sale = None
            if sale is None:
                messages.error(request, "Prodaja nije zabeležena. Proverite artikal.")
            else:
                messages.success(
                    request,
                    f"„{product.title}“ je označen kao prodat kupcu {buyer.email}.",
                )
            return redirect("seller_products_list")

    # Show each buyer's rating from other sellers next to their name
    candidates = list(candidates)
    averages = buyer_averages(candidates)
    for buyer in candidates:
        buyer.rating_average, buyer.rating_count = averages.get(buyer.pk, (None, 0))

    context = {
        "page_title": "Označi kao prodato",
        "product": product,
        "candidates": candidates,
        "selected": request.POST.get("buyer") or request.GET.get("buyer"),
    }
    return render(request, "orders/mark_sold.html", context)
