from django import forms
from .models import Message


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Napišite poruku...",
                "class": (
                    "w-full border border-neutral-300 px-3 py-2 text-sm "
                    "focus:outline-none focus:border-stone-900 resize-none"
                ),
                "maxlength": 2000,
            })
        }
        labels = {"body": ""}
