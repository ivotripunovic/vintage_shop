"""
Sales: the seller marks a product as sold to a buyer from chat.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from products.models import Product
from ratings.services import buyer_averages
from users.models import User

from .models import Sale


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


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def product_mark_sold_view(request, product_id):
    """Pick the buyer from chat and record the sale."""
    product = get_object_or_404(
        Product.objects.select_related("seller"), pk=product_id, is_deleted=False
    )
    if product.seller.user_id != request.user.id:
        return HttpResponseForbidden()
    if product.status == "sold" or product.stock < 1:
        messages.error(request, "Ovaj artikal je već prodat.")
        return redirect("seller_products_list")

    candidates = sale_candidates(product)

    if request.method == "POST":
        buyer = candidates.filter(pk=request.POST.get("buyer") or None).first()
        if buyer is None:
            messages.error(request, "Izaberite kupca sa kojim ste se dogovorili.")
        else:
            with transaction.atomic():
                product = Product.objects.select_for_update().get(pk=product.pk)
                Sale.objects.create(
                    product=product,
                    product_title=product.title,
                    seller=product.seller,
                    buyer=buyer,
                )
                product.stock -= 1
                if product.stock == 0:
                    product.status = "sold"
                product.save(update_fields=["stock", "status", "updated_at"])
            messages.success(
                request, f"„{product.title}“ je označen kao prodat kupcu {buyer.email}."
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
