import csv
import io
from django import forms
from django.core.exceptions import ValidationError
from .models import Camp, Participant
from apps.recipes.models import Allergen


class CampForm(forms.ModelForm):
    class Meta:
        model = Camp
        fields = ["name", "description", "start_date", "end_date",
                  "location", "participant_count", "supervisor_count"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date":   forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end   = cleaned.get("end_date")
        if start and end and end <= start:
            raise ValidationError("Enddatum muss nach dem Startdatum liegen.")
        return cleaned


class ParticipantForm(forms.ModelForm):
    """Formular fuer einzelnen Teilnehmer / Betreuer."""

    intolerances = forms.ModelMultipleChoiceField(
        queryset=Allergen.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Allergien / Unvertraeglichkeiten",
    )

    class Meta:
        model = Participant
        fields = [
            "first_name", "last_name", "person_type", "age",
            "is_vegan", "is_vegetarian", "is_halal", "is_kosher",
            "intolerances", "intolerance_notes", "notes",
        ]
        widgets = {
            "intolerance_notes": forms.Textarea(attrs={"rows": 2}),
            "notes":             forms.Textarea(attrs={"rows": 2}),
        }


class ParticipantFilterForm(forms.Form):
    """Filter fuer die Teilnehmerliste."""

    q = forms.CharField(
        required=False,
        label="Suche",
        widget=forms.TextInput(attrs={"placeholder": "Name suchen..."}),
    )
    person_type = forms.ChoiceField(
        required=False,
        label="Typ",
        choices=[
            ("", "Alle"),
            ("participant", "Teilnehmer"),
            ("supervisor",  "Betreuer"),
        ],
    )
    intolerance = forms.ModelChoiceField(
        queryset=Allergen.objects.all(),
        required=False,
        empty_label="Alle Unvertraeglichkeiten",
        label="Unvertraeglichkeit",
    )
    diet = forms.ChoiceField(
        required=False,
        label="Diaet",
        choices=[
            ("",             "Alle"),
            ("vegan",        "Vegan"),
            ("vegetarian",   "Vegetarisch"),
            ("halal",        "Halal"),
            ("kosher",       "Koscher"),
            ("any_restrict", "Mit Einschraenkungen"),
        ],
    )


class CsvImportForm(forms.Form):
    """
    CSV-Import fuer Teilnehmer.

    Erwartetes Format (Semikolon-getrennt, erste Zeile = Header):
      Vorname;Nachname;Typ;Vegan;Vegetarisch;Halal;Koscher;Allergien;Hinweise
      Anna;Müller;Teilnehmer;Nein;Nein;Nein;Nein;Gluten|Milch;Glutenfreies Brot bitte

    Typ: Teilnehmer | Betreuer
    Boolesche Felder: Ja | Nein (oder 1 | 0)
    Allergien: Pipe-getrennte Allergen-Namen (muessen in DB vorhanden sein)
    """

    csv_file = forms.FileField(
        label="CSV-Datei",
        help_text="UTF-8, Semikolon-getrennt. Vorlage herunterladen.",
    )
    camp = forms.ModelChoiceField(
        queryset=Camp.objects.filter(is_active=True),
        label="Freizeit",
    )
    skip_header = forms.BooleanField(
        initial=True, required=False,
        label="Erste Zeile ueberspringen (Header)",
    )

    def clean_csv_file(self):
        f = self.cleaned_data["csv_file"]
        if not f.name.endswith(".csv"):
            raise ValidationError("Nur CSV-Dateien erlaubt.")
        if f.size > 1_000_000:
            raise ValidationError("Datei zu gross (max. 1 MB).")
        return f

    def parse_rows(self):
        """
        Liest CSV und gibt Liste von dicts zurueck.
        Wirft ValidationError bei Formatproblemen.
        """
        f = self.cleaned_data["csv_file"]
        skip = self.cleaned_data.get("skip_header", True)
        camp = self.cleaned_data["camp"]

        allergen_map = {a.name.lower(): a for a in Allergen.objects.all()}

        content = f.read().decode("utf-8-sig")  # BOM-tolerant
        reader  = csv.reader(io.StringIO(content), delimiter=";")
        rows    = list(reader)

        if skip and rows:
            rows = rows[1:]

        results = []
        errors  = []

        for i, row in enumerate(rows, start=2 if skip else 1):
            if not any(row):
                continue  # Leerzeilen ueberspringen
            if len(row) < 2:
                errors.append(f"Zeile {i}: Zu wenig Spalten.")
                continue

            def cell(idx, default=""):
                return row[idx].strip() if idx < len(row) else default

            def to_bool(val):
                return val.strip().lower() in ("ja", "yes", "1", "true", "x")

            # Allergene parsen
            raw_allergens = cell(7)
            allergen_objs = []
            if raw_allergens:
                for name in raw_allergens.split("|"):
                    name = name.strip().lower()
                    if name in allergen_map:
                        allergen_objs.append(allergen_map[name])
                    else:
                        errors.append(
                            f"Zeile {i}: Unbekanntes Allergen '{name}' (wird ignoriert)."
                        )

            ptype_raw = cell(2, "Teilnehmer").lower()
            ptype = (Participant.PersonType.SUPERVISOR
                     if "betreuer" in ptype_raw
                     else Participant.PersonType.PARTICIPANT)

            results.append({
                "camp":              camp,
                "first_name":        cell(0),
                "last_name":         cell(1),
                "person_type":       ptype,
                "is_vegan":          to_bool(cell(3)),
                "is_vegetarian":     to_bool(cell(4)),
                "is_halal":          to_bool(cell(5)),
                "is_kosher":         to_bool(cell(6)),
                "intolerances":      allergen_objs,
                "intolerance_notes": cell(8),
                "notes":             cell(9),
            })

        return results, errors
