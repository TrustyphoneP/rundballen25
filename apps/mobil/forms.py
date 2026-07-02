from django import forms
from django.contrib.auth import get_user_model

from apps.mobile_api.models import Wochenplan, Aktion, WOCHENTAG_CHOICES

User = get_user_model()

STUNDEN = [(h, f"{h:02d}") for h in range(0, 24)]
MINUTEN = [(0, "00"), (30, "30")]


class WochenplanForm(forms.ModelForm):
    class Meta:
        model = Wochenplan
        fields = ["titel"]
        widgets = {
            "titel": forms.TextInput(attrs={"placeholder": "z. B. Woche 1"}),
        }


class AktionForm(forms.ModelForm):
    beginn_stunde = forms.TypedChoiceField(choices=STUNDEN, coerce=int, label="Beginn")
    beginn_minute = forms.TypedChoiceField(choices=MINUTEN, coerce=int, label="")
    ende_stunde = forms.TypedChoiceField(choices=STUNDEN, coerce=int, label="Ende")
    ende_minute = forms.TypedChoiceField(choices=MINUTEN, coerce=int, label="")
    verantwortlich = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Verantwortliche Betreuer",
        help_text="Leer lassen = Aktion gilt fuer alle Betreuer.",
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Aktion
        fields = [
            "wochentag", "titel", "kategorie",
            "beginn_stunde", "beginn_minute", "ende_stunde", "ende_minute",
            "ort", "beschreibung", "verantwortlich",
        ]
        widgets = {
            "titel": forms.TextInput(attrs={"placeholder": "z. B. Workshop"}),
            "ort": forms.TextInput(attrs={"placeholder": "z. B. Gruppenraum"}),
            "beschreibung": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, camp=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(is_active=True).order_by("first_name", "username")
        if camp is not None:
            mitglieder = camp.mobil_mitglieder.values_list("user_id", flat=True)
            if mitglieder:
                qs = qs.filter(pk__in=list(mitglieder))
        self.fields["verantwortlich"].queryset = qs

    def clean(self):
        cleaned = super().clean()
        bs, bm = cleaned.get("beginn_stunde"), cleaned.get("beginn_minute")
        es, em = cleaned.get("ende_stunde"), cleaned.get("ende_minute")
        if None not in (bs, bm, es, em) and (es * 60 + em) <= (bs * 60 + bm):
            raise forms.ValidationError("Das Ende muss nach dem Beginn liegen.")
        return cleaned
