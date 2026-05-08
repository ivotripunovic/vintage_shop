import json
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, OuterRef, Subquery
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from sellers.models import Seller
from products.models import Product
from .models import Conversation, Message
from .forms import MessageForm


def _assert_participant(conversation, user):
    """Return True if user is buyer or seller's user, else False."""
    return user == conversation.buyer or user == conversation.seller.user


@login_required
def chat_inbox(request):
    conversations = (
        Conversation.objects.filter(
            Q(buyer=request.user) | Q(seller__user=request.user)
        )
        .select_related("buyer", "seller", "product")
        .order_by("-updated_at")
    )
    # Annotate unread count per conversation for current user
    conv_list = []
    for conv in conversations:
        unread = conv.messages.filter(is_read=False).exclude(sender=request.user).count()
        last_msg = conv.messages.order_by("-created_at").first()
        conv_list.append((conv, unread, last_msg))

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
    conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    messages_qs = list(
        conversation.messages.select_related("sender").order_by("created_at")[:100]
    )
    form = MessageForm()
    return render(request, "chat/detail.html", {
        "conversation": conversation,
        "messages": messages_qs,
        "form": form,
        "last_id": messages_qs[-1].id if messages_qs else 0,
    })


@login_required
@require_POST
def chat_send(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk)
    if not _assert_participant(conversation, request.user):
        return JsonResponse({"ok": False, "error": "Forbidden"}, status=403)

    form = MessageForm(request.POST)
    if not form.is_valid():
        errors = {f: e.get_json_data() for f, e in form.errors.items()}
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    msg = form.save(commit=False)
    msg.conversation = conversation
    msg.sender = request.user
    msg.save()

    # Touch conversation.updated_at
    Conversation.objects.filter(pk=pk).update(updated_at=msg.created_at)

    return JsonResponse({
        "ok": True,
        "message": {
            "id": msg.id,
            "body": msg.body,
            "created_at": msg.created_at.isoformat(),
            "is_mine": True,
        },
    })


@login_required
def chat_poll(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk)
    if not _assert_participant(conversation, request.user):
        return JsonResponse({"error": "Forbidden"}, status=403)

    try:
        after = int(request.GET.get("after", 0))
    except (TypeError, ValueError):
        after = 0

    new_messages = (
        conversation.messages
        .filter(id__gt=after)
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
            "sender": m.sender.email,
        }
        for m in new_messages
    ]

    unread_total = (
        Message.objects
        .filter(conversation__in=Conversation.objects.filter(
            Q(buyer=request.user) | Q(seller__user=request.user)
        ))
        .filter(is_read=False)
        .exclude(sender=request.user)
        .count()
    )

    return JsonResponse({"messages": payload, "unread_total": unread_total})


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

    conversation, _ = Conversation.objects.get_or_create(
        buyer=request.user,
        seller=seller,
        product=product,
    )
    return redirect("chat_detail", pk=conversation.pk)


@login_required
def chat_unread(request):
    count = (
        Message.objects
        .filter(conversation__in=Conversation.objects.filter(
            Q(buyer=request.user) | Q(seller__user=request.user)
        ))
        .filter(is_read=False)
        .exclude(sender=request.user)
        .count()
    )
    return JsonResponse({"count": count})
