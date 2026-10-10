"""
Email confirmed waitlist subscribers that the site is live.

Each subscriber is marked notified right after their email is sent, so the
command can be re-run safely after a failure without double-sending.
"""

from django.core.mail import get_connection
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.emails import build_launch_message
from core.models import WaitlistSubscriber


class Command(BaseCommand):
    help = "Send the launch announcement to confirmed, not-yet-notified subscribers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List who would be emailed without sending anything.",
        )
        parser.add_argument(
            "--limit", type=int, default=None, help="Send at most this many emails."
        )

    def handle(self, *args, **options):
        pending = WaitlistSubscriber.objects.filter(
            confirmed_at__isnull=False, notified_at__isnull=True
        ).order_by("created_at")
        if options["limit"]:
            pending = pending[: options["limit"]]
        emails = list(pending.values_list("email", flat=True))

        if options["dry_run"]:
            for email in emails:
                self.stdout.write(email)
            self.stdout.write(f"Dry run: {len(emails)} subscriber(s) would be emailed.")
            return

        sent = failed = 0
        with get_connection(fail_silently=False) as connection:
            for email in emails:
                try:
                    build_launch_message(email, connection=connection).send()
                except Exception as exc:
                    failed += 1
                    self.stderr.write(f"Failed {email}: {exc}")
                    continue
                WaitlistSubscriber.objects.filter(email=email).update(
                    notified_at=timezone.now()
                )
                sent += 1

        self.stdout.write(self.style.SUCCESS(f"Sent {sent}, failed {failed}."))
