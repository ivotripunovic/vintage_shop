"""
Forms for the coming-soon waitlist.
"""

import time

from django import forms
from django.core import signing
from django.core.signing import BadSignature, SignatureExpired

TIMESTAMP_SALT = "core.waitlist.timestamp"
MIN_FILL_SECONDS = 3
MAX_FORM_AGE_SECONDS = 60 * 30


class WaitlistSubscribeForm(forms.Form):
    """
    Collects an email address, plus two invisible-to-humans bot checks:
    a honeypot field bots tend to fill in, and a signed render timestamp
    that catches submissions completed faster than a human could.
    """

    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "w-full px-4 py-3 bg-transparent border border-stone-300 text-stone-900 "
                "placeholder-stone-400 text-sm focus:outline-none focus:border-stone-900 transition-colors",
                "placeholder": "vasa@email.com",
                "autocomplete": "email",
            }
        )
    )
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
    )
    timestamp = forms.CharField(required=False, widget=forms.HiddenInput())

    def is_bot(self):
        """True if the honeypot or timing check suggests an automated submission."""
        if self.cleaned_data.get("website"):
            return True

        raw_timestamp = self.cleaned_data.get("timestamp") or ""
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
