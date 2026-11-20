"""
allauth forms with Serbian error messages (ACCOUNT_FORMS in settings).

USE_I18N is off, so allauth's and Django's form messages render in English.
Messages allauth raises through its adapter are translated in
AccountAdapter.error_messages; the rest (form-level checks, required
fields, Django's password validators) are mapped here. Turning on
site-wide translation is a separate decision, see
docs/features/auth-allauth-migration.md ("Language").
"""

import re

from allauth.account import forms as allauth_forms
from django import forms
from django.forms.utils import ErrorList

MESSAGES = {
    "This field is required.": "Ovo polje je obavezno.",
    "Enter a valid email address.": "Unesite ispravnu email adresu.",
    "You must type the same password each time.": "Lozinke se ne poklapaju.",
    "You must type the same email each time.": "Email adrese se ne poklapaju.",
    "This password is too common.": "Ova lozinka je previše česta.",
    "This password is entirely numeric.": "Lozinka ne sme da sadrži samo brojeve.",
}
PATTERNS = [
    (
        re.compile(r"This password is too short\. It must contain at least (\d+)"),
        r"Lozinka je prekratka. Mora imati najmanje \1 karaktera.",
    ),
    (
        re.compile(r"The password is too similar to the (.+)\.$"),
        "Lozinka je previše slična vašim ličnim podacima.",
    ),
]


def to_serbian(message):
    message = str(message)
    if message in MESSAGES:
        return MESSAGES[message]
    for pattern, replacement in PATTERNS:
        match = pattern.search(message)
        if match:
            return match.expand(replacement)
    return message


class SerbianErrorsMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # allauth's placeholders are English ("Email address", "Password")
        for field in self.fields.values():
            if "placeholder" in field.widget.attrs:
                is_email = getattr(field.widget, "input_type", "") == "email"
                field.widget.attrs["placeholder"] = "vas@email.com" if is_email else ""

    def full_clean(self):
        super().full_clean()
        for field, errors in list(self._errors.items()):
            self._errors[field] = ErrorList(
                [to_serbian(e) for e in errors], error_class=errors.error_class
            )


class LoginForm(SerbianErrorsMixin, allauth_forms.LoginForm):
    pass


class SignupForm(SerbianErrorsMixin, allauth_forms.SignupForm):
    # Optional; allauth's adapter copies them onto the user. Chat shows the
    # first name to sellers.
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=150, required=False)


class ResetPasswordForm(SerbianErrorsMixin, allauth_forms.ResetPasswordForm):
    pass


class ResetPasswordKeyForm(SerbianErrorsMixin, allauth_forms.ResetPasswordKeyForm):
    pass


class ChangePasswordForm(SerbianErrorsMixin, allauth_forms.ChangePasswordForm):
    pass


class SetPasswordForm(SerbianErrorsMixin, allauth_forms.SetPasswordForm):
    pass


class ChangeEmailForm(SerbianErrorsMixin, allauth_forms.ChangeEmailForm):
    pass
