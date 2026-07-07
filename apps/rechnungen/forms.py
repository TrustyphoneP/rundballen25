from django import forms

from .models import Beleg


class MultipleFileInput(forms.ClearableFileInput):
    """FileInput mit multiple-Attribut (Django erlaubt das nicht direkt)."""
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """
    FileField, das mehrere Dateien in einem Rutsch akzeptiert -- fürs
    Hochladen mehrerer Belegfotos direkt von der Handykamera.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={
            "accept": "image/*",
            "capture": "environment",
            "multiple": True,
        }))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(d, initial) for d in data]
        return [single_clean(data, initial)]


class BelegUploadForm(forms.Form):
    bilder = MultipleFileField(
        label="Belegfotos",
        help_text="Handyfotos von Kassenbons oder A4-Rechnungen (JPG/PNG/HEIC-als-JPG). "
                  "Mehrere Dateien gleichzeitig möglich.",
    )
    sofort_analysieren = forms.BooleanField(
        required=False, initial=True,
        label="Direkt per Claude analysieren",
        help_text="Dauert wenige Sekunden pro Beleg. Kann auch später "
                  "einzeln angestoßen werden.",
    )
    notiz = forms.CharField(
        required=False, max_length=300, label="Notiz",
        widget=forms.TextInput(attrs={"placeholder": "z.B. Großeinkauf Lieferung 1"}),
    )


class BelegNotizForm(forms.ModelForm):
    class Meta:
        model = Beleg
        fields = ["notiz"]
