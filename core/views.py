import datetime

from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import WaitlistSubscribeForm
from .models import WaitlistSubscriber

RATE_LIMIT_WINDOW = datetime.timedelta(hours=24)
RATE_LIMIT_MAX_PER_IP = 5


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@require_POST
def waitlist_subscribe(request):
    """Add an email to the launch mailing list from the coming-soon page."""
    form = WaitlistSubscribeForm(request.POST)

    if not form.is_valid():
        messages.error(request, "Unesite ispravnu email adresu.")
        return redirect("home")

    if form.is_bot():
        # Pretend success so automated submissions don't learn the check failed.
        messages.success(request, "Hvala! Javićemo vam se čim krenemo sa radom.")
        return redirect("home")

    ip_address = _client_ip(request)
    if ip_address:
        recent_count = WaitlistSubscriber.objects.filter(
            ip_address=ip_address, created_at__gte=timezone.now() - RATE_LIMIT_WINDOW
        ).count()
        if recent_count >= RATE_LIMIT_MAX_PER_IP:
            messages.error(request, "Previše pokušaja. Pokušajte ponovo kasnije.")
            return redirect("home")

    email = form.cleaned_data["email"].strip().lower()
    _, created = WaitlistSubscriber.objects.get_or_create(
        email=email, defaults={"ip_address": ip_address}
    )
    if created:
        messages.success(request, "Hvala! Javićemo vam se čim krenemo sa radom.")
    else:
        messages.info(request, "Već ste na listi — javićemo vam se!")

    return redirect("home")
