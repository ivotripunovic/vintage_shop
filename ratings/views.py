"""
Rate a sale, reply to a rating, and report a rating.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from orders.models import Sale

from .forms import RatingForm, ReplyForm, ReportForm
from .models import Rating, RatingReport
from .services import can_rate, rating_direction


def _redirect_back(request):
    """Go back to the page the form was on, or to the account ratings section."""
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect("account-settings")


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def rate_sale_view(request, sale_id):
    """Rate the other side of a sale, once, while the window is open."""
    sale = get_object_or_404(Sale.objects.select_related("seller", "buyer"), pk=sale_id)
    direction = rating_direction(sale, request.user)
    if direction is None:
        return HttpResponseForbidden()
    if not can_rate(sale, request.user):
        messages.error(request, "Ovu prodaju više ne možete oceniti.")
        return redirect("account-settings")

    is_buyer = direction == Rating.BUYER_TO_SELLER
    form = RatingForm(request.POST or None, direction=direction)
    if request.method == "POST" and form.is_valid():
        rating = form.save(commit=False)
        rating.sale = sale
        rating.direction = direction
        rating.author = request.user
        rating.subject = sale.seller.user if is_buyer else sale.buyer
        try:
            with transaction.atomic():
                # Lock the sale so two sides rating at once see each other's
                # rating and the second one releases both
                Sale.objects.select_for_update().get(pk=sale.pk)
                rating.save()
                # Both sides have rated: release both now
                if sale.ratings.count() == 2:
                    sale.ratings.update(released_at=timezone.now())
        except IntegrityError:
            messages.error(request, "Ovu prodaju ste već ocenili.")
            return redirect("account-settings")
        messages.success(
            request,
            "Hvala na oceni. Biće objavljena kada i druga strana oceni prodaju "
            "ili najkasnije 14 dana od prodaje.",
        )
        return redirect("account-settings")

    context = {
        "page_title": "Ocenite prodaju",
        "sale": sale,
        "form": form,
        "other_name": sale.seller.shop_name if is_buyer else sale.buyer.email,
    }
    return render(request, "ratings/rate_sale.html", context)


def _own_visible_rating(request, rating_id):
    """The released rating of which the user is the subject, or None."""
    rating = get_object_or_404(
        Rating.objects.visible().select_related("sale"), pk=rating_id
    )
    return rating if rating.subject_id == request.user.pk else None


@login_required(login_url="login")
@require_POST
def rating_reply_view(request, rating_id):
    """The rated person posts one short public reply."""
    rating = _own_visible_rating(request, rating_id)
    if rating is None:
        return HttpResponseForbidden()
    form = ReplyForm(request.POST)
    if rating.reply:
        messages.error(request, "Na ovu ocenu ste već odgovorili.")
    elif form.is_valid():
        rating.reply = form.cleaned_data["reply"]
        rating.replied_at = timezone.now()
        rating.save(update_fields=["reply", "replied_at", "updated_at"])
        messages.success(request, "Vaš odgovor je objavljen.")
    else:
        messages.error(request, "Odgovor može imati najviše 500 znakova.")
    return _redirect_back(request)


@login_required(login_url="login")
@require_POST
def rating_report_view(request, rating_id):
    """The rated person reports the rating to staff."""
    rating = _own_visible_rating(request, rating_id)
    if rating is None:
        return HttpResponseForbidden()
    form = ReportForm(request.POST)
    if form.is_valid():
        _, created = RatingReport.objects.get_or_create(
            rating=rating,
            reporter=request.user,
            defaults={"reason": form.cleaned_data["reason"]},
        )
        if created:
            messages.success(request, "Prijava je poslata. Pregledaće je naš tim.")
        else:
            messages.info(request, "Ovu ocenu ste već prijavili.")
    else:
        messages.error(request, "Navedite razlog prijave (do 500 znakova).")
    return _redirect_back(request)
