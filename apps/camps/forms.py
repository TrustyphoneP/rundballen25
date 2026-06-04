import csv
import io
from datetime import datetime
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
    """Formular für einzelnen Teilnehmer / Betreuer."""

    intolerances = forms.ModelMultipleChoiceField(
        queryset=Allergen.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Allergien / Unverträglichkeiten",
    )

    class Meta:
        model = Participant
        fields = [
            "first_name", "last_name", "person_type", "date_of_birth",
            "is_vegan", "is_vegetarian", "is_halal", "is_kosher",
            "intolerances", "intolerance_notes", "notes",
        ]
        widgets = {
            "date_of_birth": forms.TextInput(attrs={"placeholder": "TT.MM.JJJJ"}),
            "intolerance_notes": forms.Textarea(attrs={"rows": 2}),
            "notes":             forms.Textarea(attrs={"rows": 2}),
        }


class ParticipantFilterForm(forms.Form):
    """Filter für die Teilnehmerliste."""

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
        empty_label="Alle Unverträglichkeiten",
        label="Unverträglichkeit",
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
            ("any_restrict", "Mit Einschränkungen"),
        ],
    )


class CsvImportForm(forms.Form):
    """
    CSV-Import für Teilnehmer.

    Unterstützte Spalten (Semikolon-getrennt, erste Zeile = Header):
      Vorname;Nachname;Geburtsdatum;Typ;Vegan;Vegetarisch;Halal;Koscher;Allergien;Zusatzhinweise;Notizen

    Geburtsdatum: TT.MM.JJJJ
    Typ: Teilnehmer | Betreuer
    Boolesche Felder: Ja | Nein (oder 1 | 0)
    Allergien: Komma- oder Pipe-getrennte Allergen-Namen
    Halal, Koscher, Notizen: optional
    """

    csv_file = forms.FileField(
        label="CSV-Datei",
        help_text="Semikolon-getrennt, Geburtsdatum als TT.MM.JJJJ. Vorlage herunterladen.",
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
        Liest CSV und gibt Liste von dicts zurück.
        Erkennt Spalten automatisch anhand des Headers.
        """
        f    = self.cleaned_data["csv_file"]
        skip = self.cleaned_data.get("skip_header", True)
        camp = self.cleaned_data["camp"]

        allergen_map = {a.name.lower(): a for a in Allergen.objects.all()}

        raw = f.read()
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                content = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValidationError("CSV-Datei konnte nicht gelesen werden. Bitte als UTF-8 speichern.")

        reader = csv.reader(io.StringIO(content), delimiter=";")
        rows   = list(reader)

        if not rows:
            return [], ["CSV-Datei ist leer."]

        # Header-Mapping: Spaltennamen -> Index (case-insensitive)
        header = [h.strip().lower() for h in rows[0]]
        col = {
            "vorname":         next((i for i, h in enumerate(header) if "vorname"       in h), 0),
            "nachname":        next((i for i, h in enumerate(header) if "nachname"      in h), 1),
            "geburtsdatum":    next((i for i, h in enumerate(header) if "geburt"        in h), None),
            "typ":             next((i for i, h in enumerate(header) if "typ"           in h), None),
            "vegan":           next((i for i, h in enumerate(header) if "vegan"         in h), None),
            "vegetarisch":     next((i for i, h in enumerate(header) if "vegetar"       in h), None),
            "halal":           next((i for i, h in enumerate(header) if "halal"         in h), None),
            "koscher":         next((i for i, h in enumerate(header) if "koscher"       in h), None),
            "allergien":       next((i for i, h in enumerate(header) if "allergi"       in h), None),
            "zusatzhinweise":  next((i for i, h in enumerate(header) if "zusatz"        in h), None),
            "notizen":         next((i for i, h in enumerate(header) if "notiz"         in h), None),
        }

        data_rows = rows[1:] if skip else rows

        results = []
        errors  = []

        def cell(row, key, default=""):
            idx = col.get(key)
            if idx is None or idx >= len(row):
                return default
            return row[idx].strip()

        def to_bool(val):
            return val.strip().lower() in ("ja", "yes", "1", "true", "x")

        def parse_date(val):
            if not val:
                return None
            for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(val.strip(), fmt).date()
                except ValueError:
                    continue
            return None

        def parse_allergens(raw_str, row_num):
            objs = []
            if not raw_str:
                return objs
            # Unterstütze sowohl Komma als auch Pipe als Trenner
            sep = "," if "," in raw_str else "|"
            for name in raw_str.split(sep):
                name = name.strip().lower()
                if not name:
                    continue
                if name in allergen_map:
                    objs.append(allergen_map[name])
                else:
                    errors.append(
                        f"Zeile {row_num}: Unbekanntes Allergen '{name}' (wird ignoriert)."
                    )
            return objs

        for i, row in enumerate(data_rows, start=2 if skip else 1):
            if not any(row):
                continue
            if len(row) < 2:
                errors.append(f"Zeile {i}: Zu wenig Spalten.")
                continue

            ptype_raw = cell(row, "typ", "Teilnehmer").lower()
            ptype = (Participant.PersonType.SUPERVISOR
                     if "betreuer" in ptype_raw
                     else Participant.PersonType.PARTICIPANT)

            dob = parse_date(cell(row, "geburtsdatum"))
            if cell(row, "geburtsdatum") and dob is None:
                errors.append(
                    f"Zeile {i}: Ungültiges Geburtsdatum '{cell(row, 'geburtsdatum')}' (wird ignoriert)."
                )

            results.append({
                "camp":               camp,
                "first_name":         cell(row, "vorname"),
                "last_name":          cell(row, "nachname"),
                "person_type":        ptype,
                "date_of_birth":      dob,
                "is_vegan":           to_bool(cell(row, "vegan")),
                "is_vegetarian":      to_bool(cell(row, "vegetarisch")),
                "is_halal":           to_bool(cell(row, "halal")),
                "is_kosher":          to_bool(cell(row, "koscher")),
                "intolerances":       parse_allergens(cell(row, "allergien"), i),
                "intolerance_notes":  cell(row, "zusatzhinweise"),
                "notes":              cell(row, "notizen"),
            })

        return results, errors
