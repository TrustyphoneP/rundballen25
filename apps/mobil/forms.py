from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from apps.mobile_api.models import Wochenplan, Aktion, WOCHENTAG_CHOICES
from .models import Gruppe, FreizeitZugang, Checkliste

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
    gruppen = forms.ModelMultipleChoiceField(
        queryset=Gruppe.objects.none(),
        required=False,
        label="Teilnehmende Gruppen",
        help_text="Leer lassen = keine Gruppeneinschränkung.",
        widget=forms.CheckboxSelectMultiple,
    )
    verantwortlich = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Verantwortliche Betreuer",
        help_text="Leer lassen = Aktion gilt für alle Betreuer.",
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
        if camp is not None:
            self.fields["gruppen"].queryset = Gruppe.objects.filter(camp=camp)
        if self.instance.pk:
            self.fields["gruppen"].initial = self.instance.gruppen.all()
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


class GruppeForm(forms.ModelForm):
    class Meta:
        model = Gruppe
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "z. B. Igel"}),
        }


class RegistrierungForm(forms.Form):
    code = forms.CharField(
        label="Zugangscode",
        widget=forms.TextInput(attrs={
            "placeholder": "Code von der Freizeitleitung",
            "autocapitalize": "characters",
            "autocomplete": "one-time-code",
        }),
    )
    name = forms.CharField(
        label="Dein Name",
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "z. B. Mia", "autocomplete": "name"}),
    )
    username = forms.CharField(
        label="Benutzername",
        max_length=150,
        widget=forms.TextInput(attrs={
            "placeholder": "für die Anmeldung",
            "autocapitalize": "none",
            "autocomplete": "username",
        }),
    )
    password1 = forms.CharField(
        label="Passwort",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Passwort wiederholen",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        zugang = (
            FreizeitZugang.objects
            .filter(code__iexact=code, aktiv=True, camp__is_active=True)
            .select_related("camp")
            .first()
        )
        if zugang is None:
            raise forms.ValidationError("Dieser Zugangscode ist nicht gültig.")
        self.zugang = zugang
        return code

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Dieser Benutzername ist schon vergeben.")
        return username

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Die Passwörter stimmen nicht überein.")
            else:
                validate_password(p1)
        return cleaned


class ChecklisteForm(forms.ModelForm):
    class Meta:
        model = Checkliste
        fields = ["titel", "beschreibung", "sichtbar_fuer"]
        widgets = {
            "titel": forms.TextInput(attrs={"placeholder": "z. B. Packliste Ausflug"}),
            "beschreibung": forms.Textarea(attrs={"rows": 2}),
        }
