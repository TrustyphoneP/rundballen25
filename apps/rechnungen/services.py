"""
apps/rechnungen/services.py – automatische Beleg-Analyse & Kostenrechnung

Ablauf der Analyse:
1. Belegfoto vorverarbeiten (EXIF-Drehung, Skalierung; sehr lange Kassenbons
   werden in überlappende Segmente geschnitten, damit die kleine Bonschrift
   für das Modell lesbar bleibt).
2. Die Analyse-API (Vision) extrahiert Händler, Datum, Gesamtbetrag und alle
   Positionen als striktes JSON, inklusive Grundpreis (€/kg, €/l, €/Stk)
   und Vorschlag für die passende Zutat aus den Stammdaten.
3. Antwort wird serverseitig validiert, fehlende Grundpreise werden aus
   Menge + Zeilensumme nachgerechnet, Zutaten-Vorschläge werden
   Unicode-normalisierungstolerant aufgelöst.

Alle Fehler werden geloggt und am Beleg gespeichert (status=fehler),
nichts wird stillschweigend verschluckt.
"""
import base64
import io
import json
import logging
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Einheiten-Umrechnung
# ---------------------------------------------------------------------------

_WEIGHT_TO_G  = {"g": Decimal("1"), "kg": Decimal("1000")}
_VOLUME_TO_ML = {"ml": Decimal("1"), "l": Decimal("1000")}


def konvertiere_preis(preis, von_einheit, nach_einheit):
    """
    Rechnet einen Preis von einer Einheit in eine andere um
    (z.B. 8,73 €/kg -> 0,00873 €/g). Gibt None zurück, wenn die
    Einheiten nicht derselben Dimension angehören (z.B. kg vs. Stk).
    """
    if preis is None or not von_einheit or not nach_einheit:
        return None
    preis = Decimal(str(preis))
    if von_einheit == nach_einheit:
        return preis
    if von_einheit in _WEIGHT_TO_G and nach_einheit in _WEIGHT_TO_G:
        # Preis je von_einheit -> Preis je Gramm -> Preis je nach_einheit
        return preis / _WEIGHT_TO_G[von_einheit] * _WEIGHT_TO_G[nach_einheit]
    if von_einheit in _VOLUME_TO_ML and nach_einheit in _VOLUME_TO_ML:
        return preis / _VOLUME_TO_ML[von_einheit] * _VOLUME_TO_ML[nach_einheit]
    return None


def ermittle_grundpreis(menge, einheit, gesamtpreis):
    """
    Berechnet den Grundpreis aus Gesamtmenge und Zeilensumme, falls das
    Modell keinen auf dem Bon gedruckten Grundpreis gefunden hat.
    Gewicht wird auf €/kg normiert, Volumen auf €/l, Zählbares auf
    €/Stk bzw. €/Pck. Gibt (grundpreis, einheit) oder (None, "") zurück.
    """
    if menge is None or gesamtpreis is None or not einheit:
        return None, ""
    try:
        menge = Decimal(str(menge))
        gesamtpreis = Decimal(str(gesamtpreis))
    except (InvalidOperation, ValueError):
        return None, ""
    if menge <= 0:
        return None, ""

    if einheit in _WEIGHT_TO_G:
        menge_kg = menge * _WEIGHT_TO_G[einheit] / Decimal("1000")
        if menge_kg <= 0:
            return None, ""
        return (gesamtpreis / menge_kg).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "kg"
    if einheit in _VOLUME_TO_ML:
        menge_l = menge * _VOLUME_TO_ML[einheit] / Decimal("1000")
        if menge_l <= 0:
            return None, ""
        return (gesamtpreis / menge_l).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "l"
    if einheit in ("Stk", "Pck"):
        return (gesamtpreis / menge).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), einheit
    return None, ""


def lookup_ingredient(name):
    """
    Findet eine Zutat unabhängig von Unicode-Normalisierung (NFC/NFD)
    und Groß-/Kleinschreibung. Gibt None zurück, wenn nichts passt.
    Gleiche Motivation wie apps.shopping.shopping_days._lookup_ingredient:
    'ä' kann als ein Codepoint oder als 'a' + Kombinationszeichen vorliegen.
    """
    from apps.recipes.models import Ingredient

    if not name:
        return None
    name = name.strip()
    forms = {unicodedata.normalize("NFC", name), unicodedata.normalize("NFD", name)}
    qs = Ingredient.objects.filter(name__in=list(forms))
    ing = qs.first()
    if ing:
        if qs.count() > 1:
            logger.warning(
                "Mehrere Ingredient-Einträge für '%s' gefunden -- verwende den ersten.",
                name,
            )
        return ing
    # Fallback: case-insensitive auf NFC-Form
    return Ingredient.objects.filter(
        name__iexact=unicodedata.normalize("NFC", name)
    ).first()


# ---------------------------------------------------------------------------
# Bildvorverarbeitung
# ---------------------------------------------------------------------------

# Zielbreite nach Skalierung. Bonschrift ist klein -- 1100 px Breite reichen
# für gestochen scharfe Ziffern, ohne die API-Limits zu reizen.
_MAX_BREITE = 1100
# Maximale Segmenthöhe. Lange Kassenbons (Seitenverhältnis > ~2,4) werden in
# überlappende Segmente geschnitten, damit keine Zeile an einer Schnittkante
# verloren geht und die Auflösung pro Segment hoch bleibt.
_MAX_HOEHE = 2200
_UEBERLAPPUNG = 180


def bereite_bilder_vor(beleg):
    """
    Öffnet das Belegfoto, korrigiert die EXIF-Drehung, skaliert es und
    zerschneidet sehr lange Bons in Segmente. Gibt eine Liste von
    Base64-kodierten JPEG-Strings zurück.
    """
    from PIL import Image, ImageOps

    with beleg.image.open("rb") as f:
        img = Image.open(f)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")

    if img.width > _MAX_BREITE:
        neue_hoehe = round(img.height * _MAX_BREITE / img.width)
        img = img.resize((_MAX_BREITE, neue_hoehe), Image.LANCZOS)

    segmente = []
    if img.height <= _MAX_HOEHE + _UEBERLAPPUNG:
        segmente.append(img)
    else:
        schritt = _MAX_HOEHE - _UEBERLAPPUNG
        y = 0
        while y < img.height:
            unten = min(y + _MAX_HOEHE, img.height)
            segmente.append(img.crop((0, y, img.width, unten)))
            if unten >= img.height:
                break
            y += schritt

    kodiert = []
    for seg in segmente:
        buf = io.BytesIO()
        seg.save(buf, format="JPEG", quality=85)
        kodiert.append(base64.standard_b64encode(buf.getvalue()).decode("ascii"))
    return kodiert


# ---------------------------------------------------------------------------
# Analyse-API
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "Du bist ein präzises Belegerfassungssystem für die Küchenverwaltung "
    "von Kinderferienfreizeiten. Du bekommst Fotos von deutschen Kassenbons "
    "oder A4-Rechnungen (bei langen Bons ggf. in überlappenden Segmenten "
    "desselben Belegs) und extrahierst alle Positionen als striktes JSON. "
    "Antworte ausschließlich mit einem JSON-Objekt, ohne Markdown, ohne "
    "Erklärtext, ohne Codeblock-Zäune."
)


def _baue_prompt(zutaten_namen):
    zutaten_liste = "\n".join(f"- {n}" for n in zutaten_namen) if zutaten_namen else "(keine)"
    return f"""Extrahiere alle Daten dieses Belegs als JSON mit exakt diesem Schema:

{{
  "haendler": "Name des Ladens oder null",
  "datum": "Kaufdatum als YYYY-MM-DD oder null",
  "gesamtbetrag": Zahl (Endsumme in Euro) oder null,
  "positionen": [
    {{
      "text_original": "Zeile wie auf dem Bon gedruckt",
      "artikel_name": "bereinigter, gut lesbarer Artikelname",
      "menge": Zahl (GESAMTmenge der Zeile) oder null,
      "einheit": "g" | "kg" | "ml" | "l" | "Stk" | "Pck" | null,
      "gesamtpreis": Zahl (Zeilensumme in Euro),
      "grundpreis": Zahl (Preis je Grundpreis-Einheit) oder null,
      "grundpreis_einheit": "kg" | "l" | "Stk" | "Pck" | null,
      "zutat": "exakter Name aus der Zutatenliste unten oder null",
      "hinweis": "z.B. Pfand, Rabatt, unsicher -- sonst null"
    }}
  ]
}}

Regeln:
- Zahlen mit Punkt als Dezimaltrenner (deutsche Bons drucken Komma: umrechnen).
- Mehrfachzeilen wie "2 x 1,99" ergeben menge/gesamtpreis der GESAMTEN Zeile.
- Packungsgrößen im Artikelnamen (z.B. "Gouda 400g") in menge/einheit übernehmen;
  bei mehreren Packungen die Gesamtmenge (2 x 400g -> menge 800, einheit "g").
- Wenn der Bon einen Grundpreis druckt (z.B. "1 kg = 8,73"), diesen übernehmen.
  Sonst grundpreis selbst berechnen (gesamtpreis geteilt durch Menge in kg/l/Stk),
  auf 4 Nachkommastellen.
- Pfand-Zeilen: hinweis "Pfand", zutat null. Rabatt-/TA-Zeilen: negativer
  gesamtpreis, hinweis "Rabatt", zutat null.
- "zutat" NUR setzen, wenn der Artikel eindeutig einer Zutat aus der Liste
  entspricht (z.B. "Gouda jung 48%" -> "Käseaufschnitt" nur wenn sicher).
  Im Zweifel null.
- Segmente überlappen sich: doppelt sichtbare Zeilen nur EINMAL ausgeben.
- Unleserliche Werte: null und hinweis "unsicher".

Bekannte Zutaten der Stammdaten:
{zutaten_liste}"""


def _rufe_analyse_api(bilder_b64, prompt):
    """
    Ruft die Analyse-API mit den Belegbildern auf und gibt den
    Antworttext zurück. In Tests wird diese Funktion gemockt.
    """
    import anthropic

    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY ist nicht gesetzt. Bitte in der .env "
            "hinterlegen und den Container neu starten."
        )

    client = anthropic.Anthropic(api_key=api_key)
    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": b64,
            },
        }
        for b64 in bilder_b64
    ]
    content.append({"type": "text", "text": prompt})

    response = client.messages.create(
        model=getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=8000,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    return "".join(
        block.text for block in response.content if block.type == "text"
    )


def _parse_json_antwort(text):
    """
    Parst die Modellantwort robust: entfernt eventuelle Codeblock-Zäune
    und schneidet auf das äußerste JSON-Objekt zu.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    ende = text.rfind("}")
    if start == -1 or ende == -1 or ende <= start:
        raise ValueError(f"Keine JSON-Struktur in der Antwort gefunden: {text[:200]!r}")
    return json.loads(text[start:ende + 1])


def _zu_decimal(wert, nachkommastellen="0.0001"):
    """Wandelt Modell-Ausgaben (Zahl oder String, ggf. mit Komma) in Decimal."""
    if wert is None or wert == "":
        return None
    try:
        return Decimal(str(wert).replace(",", ".")).quantize(
            Decimal(nachkommastellen), rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, ValueError):
        logger.warning("Nicht als Zahl interpretierbarer Wert vom Modell: %r", wert)
        return None


_GUELTIGE_EINHEITEN = {"g", "kg", "ml", "l", "Stk", "Pck", "EL", "TL", "Bd"}
_GUELTIGE_GRUNDPREIS_EINHEITEN = {"kg", "l", "Stk", "Pck"}


def analysiere_beleg(beleg, user=None):
    """
    Führt die komplette Analyse eines Belegs durch und speichert das
    Ergebnis. Gibt (erfolg: bool, meldung: str) zurück. Bestehende
    Positionen werden bei erneuter Analyse ersetzt.
    """
    from django.db import transaction
    from apps.recipes.models import Ingredient
    from .models import Beleg, BelegPosition

    import datetime as _dt

    try:
        bilder = bereite_bilder_vor(beleg)
        zutaten_namen = list(
            Ingredient.objects.order_by("name").values_list("name", flat=True)
        )
        antwort_text = _rufe_analyse_api(bilder, _baue_prompt(zutaten_namen))
        daten = _parse_json_antwort(antwort_text)
    except Exception as exc:
        logger.exception("Beleg-Analyse fehlgeschlagen (Beleg %s)", beleg.pk)
        beleg.status = Beleg.Status.FEHLER
        beleg.analyse_fehler = str(exc)
        beleg.save(update_fields=["status", "analyse_fehler"])
        return False, f"Analyse fehlgeschlagen: {exc}"

    positionen = daten.get("positionen") or []

    with transaction.atomic():
        beleg.haendler = (daten.get("haendler") or "")[:200]
        kaufdatum = None
        if daten.get("datum"):
            try:
                kaufdatum = _dt.date.fromisoformat(str(daten["datum"]))
            except ValueError:
                logger.warning(
                    "Ungültiges Kaufdatum vom Modell für Beleg %s: %r",
                    beleg.pk, daten["datum"],
                )
        beleg.kaufdatum = kaufdatum
        beleg.gesamtbetrag = _zu_decimal(daten.get("gesamtbetrag"), "0.01")
        beleg.analyse_rohdaten = daten
        beleg.analyse_fehler = ""
        beleg.status = Beleg.Status.ANALYSIERT
        beleg.analysiert_am = timezone.now()
        beleg.save()

        beleg.positionen.all().delete()
        neue = []
        for idx, pos in enumerate(positionen):
            if not isinstance(pos, dict):
                logger.warning("Position %d von Beleg %s ist kein Objekt: %r", idx, beleg.pk, pos)
                continue

            einheit = pos.get("einheit") or ""
            if einheit and einheit not in _GUELTIGE_EINHEITEN:
                logger.warning("Unbekannte Einheit %r bei Beleg %s ignoriert.", einheit, beleg.pk)
                einheit = ""

            menge = _zu_decimal(pos.get("menge"), "0.001")
            gesamtpreis = _zu_decimal(pos.get("gesamtpreis"), "0.01")
            grundpreis = _zu_decimal(pos.get("grundpreis"))
            grundpreis_einheit = pos.get("grundpreis_einheit") or ""
            if grundpreis_einheit not in _GUELTIGE_GRUNDPREIS_EINHEITEN:
                grundpreis_einheit = ""
            if grundpreis is None or not grundpreis_einheit:
                grundpreis, grundpreis_einheit = ermittle_grundpreis(
                    menge, einheit, gesamtpreis
                )
                grundpreis_einheit = grundpreis_einheit or ""

            ingredient = lookup_ingredient(pos.get("zutat"))

            neue.append(BelegPosition(
                beleg=beleg,
                sortierung=idx,
                text_original=(pos.get("text_original") or "")[:300],
                artikel_name=(pos.get("artikel_name") or pos.get("text_original") or "?")[:200],
                menge=menge,
                einheit=einheit,
                gesamtpreis=gesamtpreis,
                grundpreis=grundpreis,
                grundpreis_einheit=grundpreis_einheit,
                ingredient=ingredient,
                hinweis=(pos.get("hinweis") or "")[:200],
            ))
        BelegPosition.objects.bulk_create(neue)

    return True, f"{len(neue)} Positionen erkannt."


# ---------------------------------------------------------------------------
# Preisübernahme in die Zutaten-Stammdaten
# ---------------------------------------------------------------------------

def preis_fuer_uebernahme(position):
    """
    Ermittelt, welcher Preis in welcher Einheit bei einer Übernahme in
    Ingredient.price geschrieben würde, ohne etwas zu speichern.
    Gibt (preis, einheit, fehler) zurück:
    - (Decimal, "kg", None) bei Erfolg
    - (None, "", "Meldung") wenn die Übernahme nicht möglich wäre.
    Wird von uebernehme_position UND von der Detail-Ansicht (Vergleich
    alter/neuer Preis für die Überschreiben-Rückfrage) genutzt, damit
    beide exakt dieselbe Umrechnung verwenden.
    """
    ing = position.ingredient
    if ing is None:
        return None, "", "Position ist keiner Zutat zugeordnet."
    if position.grundpreis is None or not position.grundpreis_einheit:
        return None, "", "Position hat keinen Grundpreis."

    ziel_einheit, inkonsistent = ing.derive_price_unit()
    if inkonsistent:
        return None, "", (
            f"'{ing.name}' wird mit inkompatiblen Einheiten verwendet -- "
            "Preis kann nicht eindeutig zugeordnet werden."
        )
    if not ziel_einheit:
        # Zutat wird noch nirgends verwendet: Grundpreis-Einheit direkt nutzen.
        ziel_einheit = position.grundpreis_einheit

    preis = konvertiere_preis(
        position.grundpreis, position.grundpreis_einheit, ziel_einheit
    )
    if preis is None:
        return None, "", (
            f"Grundpreis-Einheit '{position.grundpreis_einheit}' ist nicht in "
            f"die Preis-Einheit '{ziel_einheit}' von '{ing.name}' umrechenbar."
        )
    return preis.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), ziel_einheit, None


def aktueller_preis_in(ingredient, einheit):
    """
    Der aktuell hinterlegte Zutatenpreis, umgerechnet in die angegebene
    Einheit -- für den Vergleich alt/neu vor einer Überschreibung.
    None, wenn kein Preis hinterlegt oder nicht umrechenbar.
    """
    if ingredient.price is None or not ingredient.price_unit:
        return None
    preis = konvertiere_preis(ingredient.price, ingredient.price_unit, einheit)
    if preis is None:
        return None
    return preis.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def uebernehme_position(position, user=None):
    """
    Überträgt den Grundpreis einer Beleg-Position in Ingredient.price,
    umgerechnet auf die automatisch abgeleitete Preis-Einheit der Zutat
    (derive_price_unit). Legt einen Preishistorie-Eintrag an.
    Gibt (erfolg: bool, meldung: str) zurück.
    """
    from .models import Preishistorie

    ing = position.ingredient
    preis, ziel_einheit, fehler = preis_fuer_uebernahme(position)
    if fehler:
        return False, fehler

    # Hinweis: Ingredient.price hat 4 Nachkommastellen. Wird eine Zutat nur
    # in g/ml verwendet, leitet derive_price_unit "g"/"ml" ab und der Preis
    # wird je Gramm gespeichert -- Auflösung damit 0,1 €/kg. Für die
    # Budgetierung unkritisch; die Preishistorie unten hält den exakten
    # Grundpreis in seiner Original-Einheit fest, es geht nichts verloren.
    ing.price = preis
    ing.save()  # save() leitet price_unit automatisch ab

    Preishistorie.objects.create(
        ingredient=ing,
        preis=position.grundpreis,
        einheit=position.grundpreis_einheit,
        haendler=position.beleg.haendler,
        kaufdatum=position.beleg.kaufdatum,
        beleg=position.beleg,
        erfasst_von=user,
    )

    position.ist_uebernommen = True
    position.uebernommen_am = timezone.now()
    position.save(update_fields=["ist_uebernommen", "uebernommen_am"])

    return True, f"{ing.name}: {preis} €/{ing.price_unit or ziel_einheit} übernommen."


# ---------------------------------------------------------------------------
# Kostenrechnung: Freizeit
# ---------------------------------------------------------------------------

def berechne_freizeitkosten(camp):
    """
    Berechnet die geplanten Kosten einer Freizeit auf Basis der drei
    Lieferungen (build_shopping_day_items deckt Abendessen, Frühstück,
    Brot, Allgemein, Betreueressen und SKF-Alternativen ab) und der
    hinterlegten Zutatenpreise.

    Gibt ein dict zurück mit:
    - lieferungen: Liste je Lieferung (label, datum, positionen, summe,
      ohne_preis)
    - quellen: Zwischensummen je Quelle (Abendessen, Frühstück, ...)
    - summe: Gesamtsumme aller bepreisbaren Positionen
    - ohne_preis: Namen der Zutaten ohne verwendbaren Preis
    - top_positionen: die teuersten Einzelpositionen über alle Lieferungen
    """
    from apps.camps.models import CampDay
    from apps.meals.models import DayMeal
    from apps.shopping.shopping_days import get_shopping_days, build_shopping_day_items

    camp_days = list(CampDay.objects.filter(camp=camp).order_by("date"))
    day_meal_map = {
        dm.day_id: dm
        for dm in DayMeal.objects.filter(day__camp=camp).prefetch_related(
            "main_course__recipe_ingredients__ingredient",
            "dessert__recipe_ingredients__ingredient",
            "salad__recipe_ingredients__ingredient",
        )
    }
    all_day_meals = [day_meal_map.get(cd.id) for cd in camp_days]
    shopping_days = get_shopping_days(camp)

    lieferungen = []
    quellen = {}
    summe = Decimal("0")
    ohne_preis = set()
    alle_positionen = []

    for sd in shopping_days:
        items, fruehstueck_extras = build_shopping_day_items(camp, sd, all_day_meals)
        positionen = []
        lieferung_summe = Decimal("0")
        lieferung_ohne_preis = []

        for v in items.values():
            ing = v["ingredient"]
            kosten = ing.price_for(v["amount"], v["unit"])
            eintrag = {
                "name":   ing.name,
                "amount": v["amount"],
                "unit":   v["unit"],
                "source": v.get("source", ""),
                "kosten": kosten,
            }
            positionen.append(eintrag)
            if kosten is None:
                ohne_preis.add(ing.name)
                lieferung_ohne_preis.append(ing.name)
            else:
                lieferung_summe += kosten
                quelle = v.get("source", "Sonstiges")
                quellen[quelle] = quellen.get(quelle, Decimal("0")) + kosten

        for extra in fruehstueck_extras or []:
            ing = lookup_ingredient(extra.get("name"))
            kosten = None
            if ing is not None:
                kosten = ing.price_for(extra["amount"], extra["unit"])
            eintrag = {
                "name":   extra.get("name", "?"),
                "amount": extra["amount"],
                "unit":   extra["unit"],
                "source": "Frühstück/Mittag",
                "kosten": kosten,
            }
            positionen.append(eintrag)
            if kosten is None:
                ohne_preis.add(extra.get("name", "?"))
                lieferung_ohne_preis.append(extra.get("name", "?"))
            else:
                lieferung_summe += kosten
                quellen["Frühstück/Mittag"] = quellen.get("Frühstück/Mittag", Decimal("0")) + kosten

        positionen.sort(key=lambda p: (p["kosten"] is None, -(p["kosten"] or 0)))
        summe += lieferung_summe
        alle_positionen.extend(positionen)
        lieferungen.append({
            "label":       sd.label,
            "datum":       sd.date,
            "beschreibung": sd.description,
            "positionen":  positionen,
            "summe":       lieferung_summe,
            "ohne_preis":  sorted(set(lieferung_ohne_preis)),
        })

    bepreist = [p for p in alle_positionen if p["kosten"] is not None]
    bepreist.sort(key=lambda p: p["kosten"], reverse=True)

    return {
        "lieferungen":    lieferungen,
        "quellen":        sorted(quellen.items(), key=lambda kv: kv[1], reverse=True),
        "summe":          summe,
        "ohne_preis":     sorted(ohne_preis),
        "top_positionen": bepreist[:25],
    }


# ---------------------------------------------------------------------------
# Kostenrechnung: Rezepte
# ---------------------------------------------------------------------------

def berechne_rezeptkosten():
    """
    Berechnet für jedes Rezept die Kosten der Basis-Portionen und pro
    Person. Zutaten ohne verwendbaren Preis werden gezählt statt geraten.
    Gibt eine Liste von dicts zurück, absteigend nach Kosten pro Person.
    """
    from apps.recipes.models import Recipe

    ergebnisse = []
    recipes = Recipe.objects.prefetch_related(
        "recipe_ingredients__ingredient"
    ).all()

    for recipe in recipes:
        summe = Decimal("0")
        fehlend = []
        anzahl = 0
        for ri in recipe.recipe_ingredients.all():
            anzahl += 1
            kosten = ri.ingredient.price_for(ri.amount, ri.unit)
            if kosten is None:
                fehlend.append(ri.ingredient.name)
            else:
                summe += kosten

        pro_person = (
            summe / Decimal(str(recipe.base_servings))
            if recipe.base_servings else None
        )
        ergebnisse.append({
            "recipe":        recipe,
            "summe":         summe,
            "pro_person":    pro_person,
            "zutaten":       anzahl,
            "ohne_preis":    fehlend,
            "vollstaendig":  not fehlend and anzahl > 0,
        })

    ergebnisse.sort(
        key=lambda e: e["pro_person"] if e["pro_person"] is not None else Decimal("-1"),
        reverse=True,
    )
    return ergebnisse


# ---------------------------------------------------------------------------
# Kostenrechnung: Kategorien (Plan aus Einkaufsliste, Ist aus Belegen)
# ---------------------------------------------------------------------------

# Zuordnung Einkaufslisten-Quelle -> Name der Kostenkategorie. Die Quellen
# sind die source-Labels aus build_shopping_day_items; die Kategorienamen
# entsprechen den per Datenmigration angelegten Standard-Kategorien.
QUELLE_ZU_KATEGORIE = {
    "Abendessen":       "Abendessen",
    "Frühstück/Mittag": "Frühstück/Mittagessen",
    "Allgemein":        "Allgemein",
    "Betreueressen":    "Betreueressen",
    "Alternative":      "SKF-Alternativen",
}


def berechne_kategoriekosten(camp):
    """
    Stellt je Kostenkategorie zwei GETRENNTE Werte gegenüber:

    - plan: vorkalkulierte Kosten aus der Einkaufsliste -- Mengen je Quelle
      (Abendessen, Frühstück/Mittag, Allgemein, Betreueressen, Alternative)
      multipliziert mit den hinterlegten Zutatenpreisen. Reine Übersicht.
    - ist: tatsächliche Ausgaben -- Summe der Gesamtbeträge aller Belege,
      die dieser Kategorie zugeordnet wurden. Das ist der maßgebliche Wert.

    Es findet KEINE Verrechnung statt; Plan und Ist stehen nebeneinander.
    Gibt ein dict mit eintraege, ohne_kategorie, plan_nicht_zugeordnet
    und den Summen zurück.
    """
    from django.db.models import Sum
    from .models import Beleg, Kostenkategorie

    plan_je_kategorie = {}
    plan_nicht_zugeordnet = []
    if camp is not None:
        for quelle, betrag in berechne_freizeitkosten(camp)["quellen"]:
            kategorie_name = QUELLE_ZU_KATEGORIE.get(quelle)
            if kategorie_name is None:
                plan_nicht_zugeordnet.append((quelle, betrag))
            else:
                plan_je_kategorie[kategorie_name] = (
                    plan_je_kategorie.get(kategorie_name, Decimal("0")) + betrag
                )

    eintraege = []
    ist_gesamt = Decimal("0")
    plan_gesamt = sum(plan_je_kategorie.values(), Decimal("0")) + sum(
        (betrag for _, betrag in plan_nicht_zugeordnet), Decimal("0")
    )

    for kategorie in Kostenkategorie.objects.all():
        belege = kategorie.belege.filter(camp=camp) if camp else kategorie.belege.none()
        ist = belege.aggregate(s=Sum("gesamtbetrag"))["s"] or Decimal("0")
        ist_gesamt += ist
        eintraege.append({
            "kategorie": kategorie,
            "ist":       ist,
            "plan":      plan_je_kategorie.get(kategorie.name),
            "anzahl":    belege.count(),
            "loeschbar": not kategorie.belege.exists(),
        })

    ohne = (
        Beleg.objects.filter(camp=camp, kategorie__isnull=True)
        if camp else Beleg.objects.none()
    )
    ohne_summe = ohne.aggregate(s=Sum("gesamtbetrag"))["s"] or Decimal("0")
    ist_gesamt += ohne_summe

    return {
        "eintraege":             eintraege,
        "ohne_anzahl":           ohne.count(),
        "ohne_summe":            ohne_summe,
        "plan_nicht_zugeordnet": plan_nicht_zugeordnet,
        "ist_gesamt":            ist_gesamt,
        "plan_gesamt":           plan_gesamt,
    }


# ---------------------------------------------------------------------------
# Preistreiber: teure Zutaten je Gewicht/Volumen
# ---------------------------------------------------------------------------

def berechne_preistreiber():
    """
    Normiert alle hinterlegten Zutatenpreise auf €/kg bzw. €/l und
    liefert sie absteigend sortiert, gruppiert nach Dimension. So lassen
    sich sehr teure Artikel je Gewicht sofort isolieren.
    """
    from apps.recipes.models import Ingredient

    gewicht, volumen, stueck = [], [], []
    for ing in Ingredient.objects.exclude(price__isnull=True).exclude(price_unit=""):
        if ing.price_unit in _WEIGHT_TO_G:
            preis_kg = konvertiere_preis(ing.price, ing.price_unit, "kg")
            gewicht.append({"ingredient": ing, "preis": preis_kg, "einheit": "kg"})
        elif ing.price_unit in _VOLUME_TO_ML:
            preis_l = konvertiere_preis(ing.price, ing.price_unit, "l")
            volumen.append({"ingredient": ing, "preis": preis_l, "einheit": "l"})
        else:
            stueck.append({"ingredient": ing, "preis": ing.price, "einheit": ing.price_unit})

    for liste in (gewicht, volumen, stueck):
        liste.sort(key=lambda e: e["preis"], reverse=True)

    return {"gewicht": gewicht, "volumen": volumen, "stueck": stueck}
