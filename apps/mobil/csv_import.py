"""
CSV-Import für Wochenpläne.

Erwartete Struktur (Semikolon oder Komma als Trennzeichen):

    wochentag;beginn;ende;titel;kategorie;ort;beschreibung;gruppen;verantwortliche
    Montag;12:00;14:00;Töpfer-Workshop;programm;Scheune;Ton mitbringen;Igel,Füchse;mia,tom

- wochentag: Montag..Sonntag, Mo..So oder 0..6
- beginn/ende: HH:MM, Minuten 00 oder 30
- kategorie: Wert oder Anzeigename aus KATEGORIE_CHOICES, leer = programm
- gruppen: Gruppennamen der Freizeit, mit Komma getrennt, leer = keine Einschränkung
- verantwortliche: Benutzernamen, mit Komma getrennt, leer = alle Betreuer

Der Import ist atomar: entweder alle Zeilen oder keine.
"""
import csv
import io
import unicodedata

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.mobile_api.models import Aktion, Wochenplan, WOCHENTAG_CHOICES, KATEGORIE_CHOICES

from .models import Gruppe

SPALTEN = [
    "wochentag", "beginn", "ende", "titel",
    "kategorie", "ort", "beschreibung", "gruppen", "verantwortliche",
]
PFLICHT = ["wochentag", "beginn", "ende", "titel"]

_WOCHENTAGE = {}
for _nr, _name in WOCHENTAG_CHOICES:
    _WOCHENTAGE[_name.lower()] = _nr
    _WOCHENTAGE[_name[:2].lower()] = _nr
    _WOCHENTAGE[str(_nr)] = _nr

_KATEGORIEN = {}
for _wert, _anzeige in KATEGORIE_CHOICES:
    _KATEGORIEN[_wert.lower()] = _wert
    _KATEGORIEN[_anzeige.lower()] = _wert


def _nfc(text):
    return unicodedata.normalize("NFC", text or "").strip()


def _dekodieren(rohdaten):
    """Bytes dekodieren: UTF-8 (mit/ohne BOM), sonst Windows-1252."""
    try:
        return rohdaten.decode("utf-8-sig")
    except UnicodeDecodeError:
        return rohdaten.decode("cp1252")


def _zeit(wert, feld, fehler, zeile):
    try:
        stunde_s, minute_s = wert.split(":")
        stunde, minute = int(stunde_s), int(minute_s)
    except (ValueError, AttributeError):
        fehler.append(f"Zeile {zeile}: {feld} „{wert}“ hat nicht das Format HH:MM.")
        return None
    if not 0 <= stunde <= 23:
        fehler.append(f"Zeile {zeile}: {feld} „{wert}“ hat eine ungültige Stunde.")
        return None
    if minute not in (0, 30):
        fehler.append(f"Zeile {zeile}: {feld} „{wert}“ muss auf :00 oder :30 enden.")
        return None
    return stunde, minute


def csv_parsen(rohdaten, camp):
    """
    Parst die CSV-Datei und validiert alle Zeilen gegen die Freizeit.
    Rückgabe: (aktionen, fehler)
    aktionen: Liste von Dicts mit fertig aufgelösten Werten
    fehler:   Liste von Fehlermeldungen mit Zeilennummern
    """
    fehler = []
    try:
        text = _dekodieren(rohdaten)
    except UnicodeDecodeError:
        return [], ["Die Datei konnte nicht gelesen werden (weder UTF-8 noch Windows-1252)."]

    text = unicodedata.normalize("NFC", text)
    erste_zeile = text.splitlines()[0] if text.splitlines() else ""
    trenner = ";" if erste_zeile.count(";") >= erste_zeile.count(",") else ","

    leser = csv.DictReader(io.StringIO(text), delimiter=trenner)
    if leser.fieldnames is None:
        return [], ["Die Datei ist leer."]

    kopf = [_nfc(f).lower() for f in leser.fieldnames]
    leser.fieldnames = kopf
    unbekannt = [f for f in kopf if f and f not in SPALTEN]
    if unbekannt:
        fehler.append(
            f"Unbekannte Spalten: {', '.join(unbekannt)}. "
            f"Erlaubt sind: {', '.join(SPALTEN)}."
        )
    for pflicht in PFLICHT:
        if pflicht not in kopf:
            fehler.append(f"Pflichtspalte „{pflicht}“ fehlt in der Kopfzeile.")
    if fehler:
        return [], fehler

    # Nachschlagetabellen der Freizeit (case-insensitiv, NFC-normalisiert)
    gruppen_map = {
        _nfc(g.name).lower(): g for g in Gruppe.objects.filter(camp=camp)
    }
    User = get_user_model()
    from .models import FreizeitMitglied
    nutzer_map = {
        m.user.username.lower(): m.user
        for m in FreizeitMitglied.objects.filter(camp=camp).select_related("user")
    }

    aktionen = []
    for nr, zeile in enumerate(leser, start=2):
        werte = {k: _nfc(v) for k, v in zeile.items() if k}
        if not any(werte.values()):
            continue  # Leerzeile

        # Wochentag
        tag = _WOCHENTAGE.get(werte.get("wochentag", "").lower())
        if tag is None:
            fehler.append(
                f"Zeile {nr}: Wochentag „{werte.get('wochentag', '')}“ unbekannt "
                f"(Montag..Sonntag, Mo..So oder 0..6)."
            )

        # Zeiten
        beginn = _zeit(werte.get("beginn", ""), "Beginn", fehler, nr)
        ende = _zeit(werte.get("ende", ""), "Ende", fehler, nr)
        if beginn and ende:
            if ende[0] * 60 + ende[1] <= beginn[0] * 60 + beginn[1]:
                fehler.append(f"Zeile {nr}: Das Ende muss nach dem Beginn liegen.")

        # Titel
        titel = werte.get("titel", "")
        if not titel:
            fehler.append(f"Zeile {nr}: Titel fehlt.")

        # Kategorie
        kategorie_roh = werte.get("kategorie", "")
        kategorie = _KATEGORIEN.get(kategorie_roh.lower(), None) if kategorie_roh else "programm"
        if kategorie is None:
            gueltige = ", ".join(w for w, _ in KATEGORIE_CHOICES)
            fehler.append(
                f"Zeile {nr}: Kategorie „{kategorie_roh}“ unbekannt (erlaubt: {gueltige})."
            )

        # Gruppen
        gruppen = []
        for name in filter(None, (t.strip() for t in werte.get("gruppen", "").split(","))):
            g = gruppen_map.get(_nfc(name).lower())
            if g is None:
                vorhandene = ", ".join(sorted(g.name for g in gruppen_map.values())) or "keine"
                fehler.append(
                    f"Zeile {nr}: Gruppe „{name}“ gibt es in dieser Freizeit nicht "
                    f"(vorhanden: {vorhandene})."
                )
            else:
                gruppen.append(g)

        # Verantwortliche
        verantwortliche = []
        for name in filter(None, (t.strip() for t in werte.get("verantwortliche", "").split(","))):
            u = nutzer_map.get(name.lower())
            if u is None:
                fehler.append(
                    f"Zeile {nr}: Benutzer „{name}“ ist nicht mit dieser Freizeit verbunden."
                )
            else:
                verantwortliche.append(u)

        if beginn and ende and tag is not None and titel and kategorie:
            aktionen.append({
                "wochentag": tag,
                "beginn": beginn,
                "ende": ende,
                "titel": titel,
                "kategorie": kategorie,
                "ort": werte.get("ort", ""),
                "beschreibung": werte.get("beschreibung", ""),
                "gruppen": gruppen,
                "verantwortliche": verantwortliche,
            })

    if not aktionen and not fehler:
        fehler.append("Die Datei enthält keine Aktionszeilen.")
    return aktionen, fehler


@transaction.atomic
def csv_importieren(aktionen, camp, ersetzen=False):
    """Legt die geparsten Aktionen an. Atomar. Rückgabe: Anzahl."""
    plan = Wochenplan.objects.filter(camp_id=camp.pk).first()
    if plan is None:
        plan = Wochenplan.objects.create(camp_id=camp.pk, titel="Wochenplan")
    if ersetzen:
        Aktion.objects.filter(wochenplan__camp_id=camp.pk).delete()

    for daten in aktionen:
        aktion = Aktion.objects.create(
            wochenplan=plan,
            wochentag=daten["wochentag"],
            titel=daten["titel"],
            kategorie=daten["kategorie"],
            beginn_stunde=daten["beginn"][0],
            beginn_minute=daten["beginn"][1],
            ende_stunde=daten["ende"][0],
            ende_minute=daten["ende"][1],
            ort=daten["ort"],
            beschreibung=daten["beschreibung"],
        )
        if daten["verantwortliche"]:
            aktion.verantwortlich.set(daten["verantwortliche"])
        if daten["gruppen"]:
            aktion.gruppen.set(daten["gruppen"])
    return len(aktionen)


VORLAGE = (
    "wochentag;beginn;ende;titel;kategorie;ort;beschreibung;gruppen;verantwortliche\r\n"
    "Montag;12:00;14:00;Töpfer-Workshop;programm;Scheune;Ton mitbringen;;\r\n"
    "Montag;20:00;22:00;Kino;programm;Saal;;;\r\n"
    "Dienstag;08:00;08:30;Frühstück;mahlzeit;Speisesaal;;;\r\n"
)
