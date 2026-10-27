"""
Forms for rating, replying to and reporting ratings.
"""

from django import forms

from .models import Rating

SCORE_CHOICES = [(n, str(n)) for n in range(5, 0, -1)]
TEXTAREA_CLASS = (
    "w-full border border-neutral-300 px-3 py-2 text-sm focus:outline-none "
    "focus:border-stone-900"
)


class RatingForm(forms.ModelForm):
    """Overall score, the direction's optional aspects, and a short text."""

    class Meta:
        model = Rating
        fields = ["score", "text"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 4, "class": TEXTAREA_CLASS}),
        }
        labels = {"score": "Ukupna ocena", "text": "Opis"}

    def __init__(self, *args, direction, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["score"] = forms.TypedChoiceField(
            label="Ukupna ocena",
            choices=SCORE_CHOICES,
            coerce=int,
            widget=forms.RadioSelect,
        )
        self.aspect_names = []
        for field, label in Rating.ASPECTS[direction]:
            self.fields[field] = forms.TypedChoiceField(
                label=label,
                choices=[("", "—")] + SCORE_CHOICES,
                coerce=int,
                empty_value=None,
                required=False,
            )
            self.aspect_names.append(field)

    @property
    def aspect_fields(self):
        return [self[name] for name in self.aspect_names]

    def _post_clean(self):
        super()._post_clean()
        # ModelForm only copies Meta.fields to the instance; add the aspects
        for name in self.aspect_names:
            setattr(self.instance, name, self.cleaned_data.get(name))


class ReplyForm(forms.Form):
    reply = forms.CharField(max_length=500, widget=forms.Textarea)


class ReportForm(forms.Form):
    reason = forms.CharField(max_length=500, widget=forms.Textarea)
