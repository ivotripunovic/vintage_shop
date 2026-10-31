import logging
import threading
import time
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.mail import BadHeaderError, send_mail
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from orders.models import Sale, can_be_sold
from products.models import Product
from ratings.services import buyer_averages, can_rate
from sellers.models import Seller

from .forms import MessageForm
from .models import Conversation, Message

logger = logging.getLogger(__name__)

# Don't email a recipient about new messages more than once per this window,
# so an active back-and-forth conversation doesn't spam their inbox.
EMAIL_NOTIFY_COOLDOWN = timedelta(minutes=10)

# Per-user caps against spam: (max actions, window in seconds)
SEND_RATE_LIMIT = (20, 60)
START_RATE_LIMIT = (20, 60 * 60)


def _rate_limited(user, action, limit):
    """Count one action by the user; True once they are over the limit.

    Fixed time windows keyed by bucket, so it works on caches whose incr()
    resets the expiry (the file cache used in production).
    """
    max_count, window = limit
    bucket = int(time.time() // window)
    key = f"chat-rl:{action}:{user.pk}:{bucket}"
    cache.add(key, 0, window * 2)
    try:
        count = cache.incr(key)
    except ValueError:  # expired between add() and incr()
        cache.set(key, 1, window * 2)
        count = 1
    return count > max_count


def _user_conversations(user):
    """Conversations the user takes part in, as buyer or as seller."""
    return Conversation.objects.filter(Q(buyer=user) | Q(seller__user=user))


def _unread_total(user):
    """Unread messages addressed to the user across all their conversations."""
    return (
        Message.objects.filter(conversation__in=_user_conversations(user))
        .filter(is_read=False)
        .exclude(sender=user)
        .count()
    )


def _assert_participant(conversation, user):
    """Return True if user is buyer or seller's user, else False."""
    return user == conversation.buyer or user == conversation.seller.user


def _notify_recipient_by_email(conversation, sender, message):
    """Email the other participant about a new message, if not on cooldown.

    The cooldown is tracked per recipient, so a reply is still emailed to
    someone who was just the sender.
    """
    now = timezone.now()
    cooldown_field = (
        "seller_emailed_at" if sender == conversation.buyer else "buyer_emailed_at"
    )
    # Claim the cooldown slot in one UPDATE, so two quick messages can't both
    # trigger an email
    claimed = (
        Conversation.objects.filter(pk=conversation.pk)
        .filter(
            Q(**{f"{cooldown_field}__isnull": True})
            | Q(**{f"{cooldown_field}__lte": now - EMAIL_NOTIFY_COOLDOWN})
        )
        .update(**{cooldown_field: now})
    )
    if not claimed:
        return

    recipient = conversation.other_participant(sender)
    chat_url = f"{settings.SITE_DOMAIN}{reverse('chat_detail', args=[conversation.pk])}"
    site_name = settings.SITE_NAME
    name = recipient.first_name or recipient.email
    sender_name = conversation.label_for(sender)
    subject = f"Nova poruka na {site_name}"
    body = f"""Zdravo {name},

Imate novu poruku od {sender_name}:

"{message.body[:200]}"

Pogledajte i odgovorite ovde:
{chat_url}

Srdačan pozdrav,
Tim {site_name}
"""

    args = (subject, body, recipient.email, conversation.pk)
    if getattr(settings, "CHAT_EMAIL_ASYNC", True):
        # After commit, in a thread: the sender never waits on the mail server
        transaction.on_commit(
            lambda: threading.Thread(
                target=_send_notification, args=args, daemon=True
            ).start()
        )
    else:
        _send_notification(*args)


def _send_notification(subject, body, to_email, conversation_pk):
    logger.info(
        "Sending new-message email to %s via %s", to_email, settings.EMAIL_BACKEND
    )
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [to_email],
            fail_silently=False,
        )
    except BadHeaderError:
        logger.error(
            "Invalid header in new-message email for conversation %s", conversation_pk
        )
    except Exception:
        logger.exception(
            "Failed to send new-message email for conversation %s", conversation_pk
        )


@login_required
def chat_inbox(request):
    last_message = Message.objects.filter(conversation=OuterRef("pk")).order_by(
        "-created_at", "-id"
    )
    conversations = (
        _user_conversations(request.user)
        .select_related("buyer", "seller", "product")
        .annotate(
            unread=Count(
                "messages",
                filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user),
            ),
            last_body=Subquery(last_message.values("body")[:1]),
            last_created_at=Subquery(last_message.values("created_at")[:1]),
        )
        .order_by("-updated_at")
    )
    conv_list = [
        (
            conv,
            conv.unread,
            (
                {"body": conv.last_body, "created_at": conv.last_created_at}
                if conv.last_created_at
                else None
            ),
        )
        for conv in conversations
    ]

    return render(request, "chat/inbox.html", {"conv_list": conv_list})


@login_required
def chat_detail(request, pk):
    conversation = get_object_or_404(
        Conversation.objects.select_related("buyer", "seller__user", "product"),
        pk=pk,
    )
    if not _assert_participant(conversation, request.user):
        return HttpResponseForbidden()

    # Mark incoming messages as read
    conversation.messages.filter(is_read=False).exclude(sender=request.user).update(
        is_read=True
    )

    # Latest 100, shown oldest first; older ones aren't paged in
    messages_qs = list(
        conversation.messages.select_related("sender").order_by("-created_at", "-id")[
            :100
        ]
    )[::-1]
    form = MessageForm()

    # Sellers see the buyer's rating and can record the sale; either side gets
    # a prompt to rate a recorded sale
    is_seller_side = (
        request.user == conversation.seller.user and not conversation.is_team
    )
    buyer_rating = None
    if is_seller_side:
        average, count = buyer_averages([conversation.buyer]).get(
            conversation.buyer.pk, (None, 0)
        )
        buyer_rating = {"average": average, "count": count}
    sale = None
    if conversation.product_id:
        sale = (
            Sale.objects.select_related("seller")
            .filter(product_id=conversation.product_id, buyer=conversation.buyer)
            .first()
        )
    sale_to_rate = sale if sale and can_rate(sale, request.user) else None
    can_mark_sold = (
        is_seller_side
        and sale is None
        and conversation.product is not None
        and can_be_sold(conversation.product)
    )

    return render(
        request,
        "chat/detail.html",
        {
            "conversation": conversation,
            # Not "messages": base.html renders that name as flash messages
            "chat_messages": messages_qs,
            "form": form,
            "last_id": messages_qs[-1].id if messages_qs else 0,
            "buyer_rating": buyer_rating,
            "sale_to_rate": sale_to_rate,
            "can_mark_sold": can_mark_sold,
        },
    )


@login_required
@require_POST
def chat_send(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk)
    if not _assert_participant(conversation, request.user):
        return JsonResponse(
            {"ok": False, "error": "Nemate pristup ovom razgovoru."}, status=403
        )

    form = MessageForm(request.POST)
    if not form.is_valid():
        errors = {f: e.get_json_data() for f, e in form.errors.items()}
        error = next(
            (e["message"] for field in errors.values() for e in field),
            "Poruka nije ispravna.",
        )
        return JsonResponse({"ok": False, "error": error, "errors": errors}, status=400)

    if _rate_limited(request.user, "send", SEND_RATE_LIMIT):
        return JsonResponse(
            {"ok": False, "error": "Šaljete poruke prebrzo. Sačekajte malo."},
            status=429,
        )

    msg = form.save(commit=False)
    msg.conversation = conversation
    msg.sender = request.user
    msg.save()

    # Touch conversation.updated_at
    Conversation.objects.filter(pk=pk).update(updated_at=msg.created_at)

    _notify_recipient_by_email(conversation, request.user, msg)

    return JsonResponse(
        {
            "ok": True,
            "message": {
                "id": msg.id,
                "body": msg.body,
                "created_at": msg.created_at.isoformat(),
                "is_mine": True,
            },
        }
    )


@login_required
def chat_poll(request, pk):
    conversation = get_object_or_404(
        Conversation.objects.select_related("seller"), pk=pk
    )
    if not _assert_participant(conversation, request.user):
        return JsonResponse({"error": "Forbidden"}, status=403)

    try:
        after = int(request.GET.get("after", 0))
    except (TypeError, ValueError):
        after = 0

    new_messages = (
        conversation.messages.filter(id__gt=after)
        .select_related("sender")
        .order_by("created_at")
    )

    # Mark fetched messages from the other participant as read
    new_messages.exclude(sender=request.user).update(is_read=True)

    payload = [
        {
            "id": m.id,
            "body": m.body,
            "created_at": m.created_at.isoformat(),
            "is_mine": m.sender_id == request.user.id,
            "sender": conversation.label_for(m.sender),
        }
        for m in new_messages
    ]

    return JsonResponse(
        {"messages": payload, "unread_total": _unread_total(request.user)}
    )


@login_required
@require_POST
def chat_start(request):
    try:
        seller_id = int(request.POST.get("seller_id", 0))
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Neispravan prodavac.")

    seller = get_object_or_404(Seller, pk=seller_id)

    if seller.user == request.user:
        return HttpResponseBadRequest("Ne možete slati poruke sebi.")

    product = None
    product_id = request.POST.get("product_id")
    if product_id:
        try:
            product = Product.objects.get(pk=int(product_id), seller=seller)
        except (Product.DoesNotExist, ValueError):
            pass

    lookup = {"buyer": request.user, "seller": seller, "product": product}
    conversation = Conversation.objects.filter(**lookup).first()
    if conversation is None:
        # Only new conversations count; reopening an existing one is free
        if _rate_limited(request.user, "start", START_RATE_LIMIT):
            messages.error(
                request,
                "Pokrenuli ste previše novih razgovora. Pokušajte ponovo kasnije.",
            )
            back = request.META.get("HTTP_REFERER", "")
            if not url_has_allowed_host_and_scheme(
                back, allowed_hosts={request.get_host()}
            ):
                back = reverse("chat_inbox")
            return redirect(back)
        conversation, _ = Conversation.objects.get_or_create(**lookup)
    return redirect("chat_detail", pk=conversation.pk)


@login_required
def chat_unread(request):
    return JsonResponse({"count": _unread_total(request.user)})
