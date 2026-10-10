"""
Forms for the coming-soon waitlist.
"""

import time

from django import forms
from django.core import signing
from django.core.signing import BadSignature, SignatureExpired

from .email_checks import validate_waitlist_email

TIMESTAMP_SALT = "core.waitlist.timestamp"
MIN_FILL_SECONDS = 3
MAX_FORM_AGE_SECONDS = 60 * 30


class WaitlistSubscribeForm(forms.Form):
    """
    Collects an email address, plus two invisible-to-humans bot checks:
    a honeypot field bots tend to fill in, and a signed render timestamp
    that catches submissions completed faster than a human could.
    """

    # The coming-soon template writes these inputs as plain HTML (faster than
    # widget rendering), so field names here must match it.
    email = forms.EmailField()
    website = forms.CharField(required=False)
    timestamp = forms.CharField(required=False)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        validate_waitlist_email(email)
        return email

    def is_bot(self):
        """
        True if the honeypot or timing check suggests an automated submission.
        Reads the raw POST data so it can run before is_valid(), letting bots be
        dropped before the costlier email checks (DNS lookups) run.
        """
        if self.data.get("website"):
            return True

        raw_timestamp = self.data.get("timestamp") or ""
        try:
            rendered_at = signing.loads(
                raw_timestamp, salt=TIMESTAMP_SALT, max_age=MAX_FORM_AGE_SECONDS
            )
        except (BadSignature, SignatureExpired, ValueError):
            return True

        return (time.time() - rendered_at) < MIN_FILL_SECONDS

    @staticmethod
    def generate_timestamp():
        return signing.dumps(time.time(), salt=TIMESTAMP_SALT)
