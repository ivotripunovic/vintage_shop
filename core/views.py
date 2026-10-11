import datetime

from django.contrib import messages
from django.core.cache import cache
from django.core.signing import BadSignature
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .emails import (
    read_confirm_token,
    read_unsubscribe_token,
    send_waitlist_confirmation,
)
from .forms import WaitlistSubscribeForm
from .models import WaitlistSubscriber

RATE_LIMIT_WINDOW = datetime.timedelta(hours=24)
RATE_LIMIT_MAX_PER_IP = 5
# Every POST counts here, including invalid, duplicate and bot submissions
ATTEMPT_LIMIT_WINDOW_SECONDS = 60 * 60
ATTEMPT_LIMIT_MAX_PER_IP = 20
CONFIRMATION_RESEND_COOLDOWN = datetime.timedelta(minutes=10)

SUCCESS_MESSAGE = "Hvala! Proverite inbox i potvrdite email adresu."
TOO_MANY_MESSAGE = "Previše pokušaja. Pokušajte ponovo kasnije."


def _client_ip(request):
    """
    Nginx overwrites X-Real-IP with the connecting address. X-Forwarded-For is
    never trusted: nginx appends to it, so its first value is client-controlled.
    """
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR")


def _too_many_attempts(ip_address):
    """Count this attempt and return True if the IP is over its hourly limit."""
    key = f"waitlist:attempts:{ip_address}"
    cache.add(key, 0, ATTEMPT_LIMIT_WINDOW_SECONDS)
    try:
        attempts = cache.incr(key)
    except ValueError:
        # Key expired between add() and incr()
        cache.set(key, 1, ATTEMPT_LIMIT_WINDOW_SECONDS)
        attempts = 1
    return attempts > ATTEMPT_LIMIT_MAX_PER_IP


@require_POST
def waitlist_subscribe(request):
    """Add an email to the launch mailing list from the coming-soon page."""
    ip_address = _client_ip(request)
    if ip_address and _too_many_attempts(ip_address):
        messages.error(request, TOO_MANY_MESSAGE)
        return redirect("home")

    form = WaitlistSubscribeForm(request.POST)

    if form.is_bot():
        # Pretend success so automated submissions don't learn the check failed.
        messages.success(request, SUCCESS_MESSAGE)
        return redirect("home")

    if not form.is_valid():
        email_errors = form.errors.get("email")
        messages.error(
            request,
            email_errors[0] if email_errors else "Unesite ispravnu email adresu.",
        )
        return redirect("home")

    email = form.cleaned_data["email"]
    subscriber = WaitlistSubscriber.objects.filter(email=email).first()

    if subscriber is None:
        if ip_address:
            recent_count = WaitlistSubscriber.objects.filter(
                ip_address=ip_address,
                created_at__gte=timezone.now() - RATE_LIMIT_WINDOW,
            ).count()
            if recent_count >= RATE_LIMIT_MAX_PER_IP:
                messages.error(request, TOO_MANY_MESSAGE)
                return redirect("home")

        subscriber, created = WaitlistSubscriber.objects.get_or_create(
            email=email,
            defaults={"ip_address": ip_address, "confirmation_sent_at": timezone.now()},
        )
        if created:
            send_waitlist_confirmation(email)
        messages.success(request, SUCCESS_MESSAGE)
        return redirect("home")

    if subscriber.is_confirmed:
        messages.info(request, "Već ste na listi — javićemo vam se!")
        return redirect("home")

    # Unconfirmed: resend the link, but not more often than the cooldown
    now = timezone.now()
    if (
        subscriber.confirmation_sent_at is None
        or now - subscriber.confirmation_sent_at >= CONFIRMATION_RESEND_COOLDOWN
    ):
        subscriber.confirmation_sent_at = now
        subscriber.save(update_fields=["confirmation_sent_at", "updated_at"])
        send_waitlist_confirmation(email)
    messages.success(request, SUCCESS_MESSAGE)
    return redirect("home")


def waitlist_confirm(request, token):
    """Mark the subscriber confirmed via the link in the confirmation email."""
    try:
        email = read_confirm_token(token)
    except BadSignature:
        messages.error(request, "Link za potvrdu je neispravan ili je istekao.")
        return redirect("home")

    updated = WaitlistSubscriber.objects.filter(
        email=email, confirmed_at__isnull=True
    ).update(confirmed_at=timezone.now(), updated_at=timezone.now())
    if updated or WaitlistSubscriber.objects.filter(email=email).exists():
        messages.success(request, "Email potvrđen! Javićemo vam se čim krenemo.")
    else:
        messages.error(request, "Ova adresa više nije na listi. Prijavite se ponovo.")
    return redirect("home")


def waitlist_unsubscribe(request, token):
    """Remove the subscriber via the link in the launch email."""
    try:
        email = read_unsubscribe_token(token)
    except BadSignature:
        messages.error(request, "Link za odjavu je neispravan.")
        return redirect("home")

    WaitlistSubscriber.objects.filter(email=email).delete()
    messages.success(request, "Odjavljeni ste i nećete više dobijati poruke.")
    return redirect("home")


@never_cache
@require_GET
def health(request):
    """
    For uptime monitors: 200 "ok" when Django and PostgreSQL both answer,
    503 when the database doesn't (gunicorn being down shows up as a 502).
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return HttpResponse(
            "database unavailable", status=503, content_type="text/plain"
        )
    return HttpResponse("ok", content_type="text/plain")
