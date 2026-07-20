"""
shopping_days.py – Einkaufstag-Berechnung

Drei Liefertage pro Freizeit:
  Lieferung 1: Camp-Tag 1 (Anreisetag)
               -> Alle trockenen Zutaten (gesamte Freizeit)
               -> Frische Zutaten für Abendessen Tag 1 + Abendessen Tag 2
               -> Frühstück/Belag für Tag 1 + Tag 2

  Lieferung 2: Camp-Tag 3 (→ Tag 4 wenn Sonntag)
               -> Frische Zutaten für Abendessen Tag 3, 4, 5
               -> Frühstück/Belag für Tag 3, 4, 5

  Lieferung 3: Camp-Tag 6 (→ Tag 5 wenn Sonntag)
               -> Frische Zutaten für Abendessen Tag 6 bis Ende
               -> Frühstück/Belag für Tag 6 bis Ende

Lieferung erfolgt mittags → reicht für Abendessen desselben Tages,
aber NICHT für Frühstück/Mittagessen desselben Tages.
Daher: Belag/Frühstück wird der Lieferung VOR dem jeweiligen Tag zugeordnet.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


def _sunday_adjust_forward(d):
    """Tag 3: wenn Sonntag -> Tag 4."""
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def _sunday_adjust_backward(d):
    """Tag 6: wenn Sonntag -> Tag 5."""
    if d.weekday() == 6:
        return d - timedelta(days=1)
    return d


@dataclass
class ShoppingDay:
    label:            str
    date:             object   # date
    description:      str
    dinner_indices:   List[int]  # 0-based camp day indices for dinner
    breakfast_indices: List[int]  # 0-based camp day indices for breakfast/belag
    include_dry:      bool = False
    index:            int  = 0   # 0-based delivery index (0=Lieferung 1, 1=Lieferung 2, 2=Lieferung 3)


def get_shopping_days(camp):
    """
    Gibt drei ShoppingDay-Objekte für ein Camp zurück.
    Indices sind 0-basiert (0 = erster Freizeit-Tag).
    """
    start    = camp.start_date
    duration = camp.duration_days

    # Delivery 1: Camp day 1 (index 0)
    day1_date = start

    # Delivery 2: Camp day 3 (index 2), forward if Sunday
    day2_date = _sunday_adjust_forward(start + timedelta(days=2))

    # Delivery 3: Camp day 6 (index 5), backward if Sunday
    day3_date = _sunday_adjust_backward(start + timedelta(days=5))

    # Dinner: delivery covers same day (noon delivery ok for evening)
    # Breakfast: delivery covers NEXT day onwards (noon too late for breakfast)
    # So breakfast_indices for delivery N = dinner_indices shifted +1

    days = [
        ShoppingDay(
            label="Lieferung 1",
            date=day1_date,
            description=f"Alles trockene + Frisches für Abendessen {start.strftime('%d.%m.')}–{(start + timedelta(days=1)).strftime('%d.%m.')} + Frühstück Tag 1–2",
            dinner_indices=list(range(min(2, duration))),
            breakfast_indices=list(range(min(2, duration))),
            include_dry=True,
            index=0,
        ),
    ]

    if duration > 2:
        days.append(ShoppingDay(
            label="Lieferung 2",
            date=day2_date,
            description="Frisches für Abendessen Tag 3–5 + Frühstück Tag 3–5",
            dinner_indices=list(range(2, min(5, duration))),
            breakfast_indices=list(range(2, min(5, duration))),
            include_dry=False,
            index=1,
        ))

    if duration > 5:
        days.append(ShoppingDay(
            label="Lieferung 3",
            date=day3_date,
            description=f"Frisches für Abendessen Tag 6–{duration} + Frühstück Tag 6–Ende",
            dinner_indices=list(range(5, duration)),
            breakfast_indices=list(range(5, duration)),
            include_dry=False,
            index=2,
        ))

    return days


# Belag-Namen als EINZIGE Quelle fuer Mittag- (loaves_*) und Fruehstueck-
# Block (halbweck_*). Verhindert, dass die beiden Bloecke durch Tippfehler
# oder Encoding-Abweichungen unterschiedliche Namen verwenden.
_TOPPING_DEFS = [
    # (feld_suffix, ingredient_name)
    ("cheese",       "Käseaufschnitt"),
    ("salami",       "Salamiaufschnitt"),
    ("fleischkaese", "Fleischkäseaufschnitt"),
    ("fleischwurst", "Fleischwurstaufschnitt"),
]


def _lookup_ingredient(name):
    """Findet ein Ingredient unabhaengig von Unicode-Normalisierung.

    'ä' kann als ein Codepoint (NFC) oder als 'a' + Kombinationszeichen (NFD)
    vorliegen; beide sehen identisch aus, sind fuer die DB aber verschiedene
    Strings. Ein exact-match get() schlaegt dann fehl, obwohl die Zutat
    sichtbar existiert. Diese Funktion sucht beide Formen und gibt None
    zurueck, wenn wirklich nichts existiert. Duplikate werden geloggt statt
    eine Exception zu werfen.
    """
    import unicodedata
    from apps.recipes.models import Ingredient

    forms = {unicodedata.normalize("NFC", name), unicodedata.normalize("NFD", name)}
    qs = Ingredient.objects.filter(name__in=list(forms))
    count = qs.count()
    if count > 1:
        logger.warning(
            "Mehrere Ingredient-Eintraege fuer '%s' gefunden (%d Stueck) -- "
            "verwende den ersten. Duplikate in der DB bereinigen.",
            name, count,
        )
    return qs.first()


def _lookup_or_create_ingredient(name, diet_type="vegan", is_fresh=False):
    """Wie _lookup_ingredient, legt die Zutat aber automatisch an, wenn sie
    noch nicht existiert (Name NFC-normalisiert). Damit bilden alle festen
    Fruehstueck/Mittag-Posten garantiert eine echte Einkaufslisten-Position
    statt in den Text-Extras-Fallback zu rutschen."""
    import unicodedata
    from apps.recipes.models import Ingredient

    ing = _lookup_ingredient(name)
    if ing is not None:
        return ing
    ing = Ingredient.objects.create(
        name=unicodedata.normalize("NFC", name),
        diet_type=diet_type,
        is_fresh=is_fresh,
    )
    logger.info("Ingredient '%s' automatisch angelegt (Fruehstueck/Mittag-Posten).", name)
    return ing


# Namen der frischen Aufschnitt-Sorten, aus _TOPPING_DEFS abgeleitet. Diese
# Zutaten werden beim Metzger/Frischeteller in runden Mengen bestellt, nicht
# grammgenau. Andere g-Zutaten (Gewuerze etc.) bleiben unverrundet, da dort
# 70 g auf 100 g aufzurunden das Rezept verfaelschen wuerde.
_AUFSCHNITT_NAMES = {name for _, name in _TOPPING_DEFS}


def _round_to_100g(aggregated):
    """Rundet die aggregierte Menge der vier Aufschnitt-Sorten auf die
    naechsten 100 g, kaufmaennisch gerundet (0,5 aufwaerts). Wird als
    letzter Schritt vor der Rueckgabe angewendet, damit Mittag- und
    Halbweck-Anteil bereits vollstaendig summiert sind, bevor gerundet
    wird (Runden vor dem Summieren wuerde den Fehler vervielfachen)."""
    for entry in aggregated.values():
        if entry["unit"] == "g" and entry["ingredient"].name in _AUFSCHNITT_NAMES:
            entry["amount"] = (Decimal(entry["amount"]) / 100).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            ) * 100
    return aggregated


def _merge_extras(extras):
    """Fuehrt Fallback-Extras nach (Name, Einheit) zusammen: wenn mehrere
    Bloecke fuer dieselbe Zutat in den Fallback laufen (z.B. Mittag- und
    Halbweck-Anteil bei fehlendem Ingredient-Stammdatensatz), erscheint
    EINE Zeile mit der Summe statt mehrerer Einzelzeilen."""
    merged = {}
    for e in extras:
        key = (e["name"], e["unit"])
        merged[key] = merged.get(key, 0) + e["amount"]
    return [{"name": n, "amount": a, "unit": u} for (n, u), a in merged.items()]


def build_shopping_day_items(camp, shopping_day, all_day_meals):
    """
    Aggregiert Zutaten für einen Liefertag.

    all_day_meals: geordnete Liste von DayMeal-Objekten (nach Datum),
                   Index 0 = erster Freizeit-Tag.

    Gibt dict: {(ingredient_id, unit) -> {ingredient, unit, amount, is_fresh, source}}
    """
    from decimal import Decimal
    import math

    aggregated = {}

    # Einheiten, die sich gegenseitig umrechnen lassen, werden auf eine
    # gemeinsame Basis normalisiert, bevor sie aggregiert werden. Sonst
    # werden z.B. "130 g" aus einem Rezept und "1,2 kg" aus einem anderen
    # Rezept für dieselbe Zutat NICHT zusammengeführt, weil (ingredient_id, unit)
    # zwei unterschiedliche Schlüssel wären ("g" vs "kg").
    _WEIGHT_TO_G = {"g": Decimal("1"), "kg": Decimal("1000")}
    _VOLUME_TO_ML = {"ml": Decimal("1"), "l": Decimal("1000")}

    def _normalize_unit(unit, amount):
        """Gibt (normalisierte_einheit, normalisierte_menge) zurück.
        Gewicht -> g, Volumen -> ml, alles andere (Stk/Pck/EL/TL/Bd) bleibt."""
        amount = Decimal(str(amount))
        if unit in _WEIGHT_TO_G:
            return "g", amount * _WEIGHT_TO_G[unit]
        if unit in _VOLUME_TO_ML:
            return "ml", amount * _VOLUME_TO_ML[unit]
        return unit, amount

    def add(ing, unit, amount, is_fresh, source="Abendessen"):
        norm_unit, norm_amount = _normalize_unit(unit, amount)
        key = (ing.id, norm_unit)
        if key not in aggregated:
            aggregated[key] = {
                "ingredient": ing,
                "unit":       norm_unit,
                "amount":     Decimal("0"),
                "is_fresh":   is_fresh,
                "source":     source,
            }
        aggregated[key]["amount"] += norm_amount

    # --- Abendessen (dinner): NUR frische Zutaten ---
    # Trockene Zutaten werden separat unten für die GESAMTE Freizeit
    # aggregiert (nicht nur für die Tage dieser Lieferung), sonst würden
    # sie hier UND im "Alle trockenen Zutaten"-Block doppelt gezählt.
    for idx in shopping_day.dinner_indices:
        if idx >= len(all_day_meals):
            continue
        meal = all_day_meals[idx]
        if meal is None:
            continue
        for item in meal.get_all_scaled_ingredients():
            ing      = item["ingredient"]
            is_fresh = ing.is_fresh
            if not is_fresh:
                continue
            add(ing, item["unit"], item["amount"], is_fresh, "Abendessen")

    # --- Alle trockenen Zutaten (nur Lieferung 1) ---
    # Kategorie bleibt "Abendessen" (Herkunft: Hauptgericht/Dessert/Salat),
    # NICHT "Trocken" -- "Trocken" ist kein Kategorie-Wert mehr, sondern wird
    # ausschließlich über das is_fresh-Flag (Spalte "Trocken/Frisch") sichtbar.
    if shopping_day.include_dry:
        for meal in all_day_meals:
            if meal is None:
                continue
            for item in meal.get_all_scaled_ingredients():
                ing = item["ingredient"]
                if ing.is_fresh:
                    continue  # already handled above per day
                add(ing, item["unit"], item["amount"], False, "Abendessen")

    # --- Frühstück/Belag aus FruehstueckConfig ---
    # Dry items (Milch, Choco, Margarine, Müsliriegel): only on Lieferung 1
    # Fresh Aufschnitt: split across deliveries by day count
    fruehstueck_extras = []

    try:
        from apps.meals.models import FruehstueckConfig
        from apps.recipes.models import Ingredient

        cfg = FruehstueckConfig.objects.get(camp=camp)
        num_days = len(shopping_day.breakfast_indices)

        if num_days > 0:
            SLICES_PER_LOAF   = 25
            SLICES_PER_PERSON = 2
            persons = camp.participants.count() or camp.participant_count + camp.supervisor_count
            teilis  = camp.participants.filter(person_type="participant").count() or camp.participant_count

            loaves_per_day   = math.ceil(persons * SLICES_PER_PERSON / SLICES_PER_LOAF)
            total_bread_days = max(camp.duration_days - 1, 1)  # skip first day

            # Bread days in this delivery (exclude day 0 = first camp day, no bread)
            bread_days_this_delivery = sum(1 for i in shopping_day.breakfast_indices if i > 0)
            if bread_days_this_delivery == 0 and not shopping_day.include_dry:
                return _round_to_100g(aggregated), _merge_extras(fruehstueck_extras)

            total_loaves = loaves_per_day * bread_days_this_delivery
            total_slices = total_loaves * SLICES_PER_LOAF

            # Fresh Aufschnitt -- split by delivery, use DB ingredient.
            # Namen kommen aus _TOPPING_DEFS (gemeinsame Quelle mit dem
            # Halbweck-Block), Lookup ist normalisierungs-tolerant.
            for suffix, ing_name in _TOPPING_DEFS:
                loaves_total_camp = getattr(cfg, f"loaves_{suffix}", 0)
                if loaves_total_camp == 0:
                    continue
                loaves_these_days = loaves_total_camp * bread_days_this_delivery / total_bread_days
                weight_per_slice  = getattr(cfg, f"weight_{suffix}", 0)
                spb               = getattr(cfg, f"spb_{suffix}", 1)
                weight_g          = round(loaves_these_days * SLICES_PER_LOAF * spb * weight_per_slice)
                if weight_g > 0:
                    ing = _lookup_or_create_ingredient(
                        ing_name,
                        diet_type="vegetarian" if suffix == "cheese" else "meat",
                        is_fresh=True,
                    )
                    add(ing, "g", weight_g, True, "Frühstück/Mittag")

    except Exception:
        pass

    # --- Frühstück Aufschnitt (Halbweck) -- eigener Block, damit Fehler
    #     nicht vom äußeren try/except verschluckt werden ---
    # WICHTIG: Kein pauschales "except Exception: pass" mehr. Ein Fehler bei
    # EINER Belag-Sorte (z.B. Ingredient.MultipleObjectsReturned, falsches
    # Feld, o.ä.) darf nicht dazu führen, dass die komplette Halbweck-Menge
    # (inkl. aller anderen Beläge) stillschweigend verschwindet. Deshalb wird
    # jede Belag-Sorte einzeln abgesichert und jeder Fehler geloggt.
    try:
        from apps.meals.models import FruehstueckConfig
        from apps.recipes.models import Ingredient

        cfg = FruehstueckConfig.objects.get(camp=camp)
        total_bread_days = max(camp.duration_days - 1, 1)
        bread_days_this_delivery = sum(1 for i in shopping_day.breakfast_indices if i > 0)

        # Tag nach der Freizeit: gehoert zur LETZTEN Lieferung (deckt den
        # letzten Camp-Tag ab). Formel identisch zur Anzeige in
        # apps.meals.views (extra_day_notes):
        #   Gesamtgewicht / num_bread_days * 0.6
        is_last_delivery = (camp.duration_days - 1) in shopping_day.breakfast_indices

        for suffix, ing_name in _TOPPING_DEFS:
            try:
                hw_total_camp = getattr(cfg, f"halbweck_{suffix}", 0)
                if hw_total_camp == 0:
                    continue
                hw_these_days    = hw_total_camp * bread_days_this_delivery / total_bread_days
                weight_per_slice = getattr(cfg, f"weight_{suffix}", 0)
                spb              = getattr(cfg, f"spb_{suffix}", 1)
                weight_g         = round(hw_these_days * spb * weight_per_slice)

                # Tag nach Freizeit (nur letzte Lieferung), gleiche Formel
                # wie extra_day_notes in der Fruehstueck-Ansicht
                if is_last_delivery:
                    total_g_camp = hw_total_camp * spb * weight_per_slice
                    weight_g += round(total_g_camp / total_bread_days * 0.6)

                if weight_g <= 0:
                    continue
                ing = _lookup_or_create_ingredient(
                    ing_name,
                    diet_type="vegetarian" if suffix == "cheese" else "meat",
                    is_fresh=True,
                )
                add(ing, "g", weight_g, True, "Frühstück/Mittag")
            except Exception:
                logger.exception(
                    "Halbweck-Belag '%s' konnte nicht berechnet werden (camp=%s, "
                    "shopping_day=%s) -- übersprungen, andere Beläge laufen weiter.",
                    ing_name, camp.pk, shopping_day.label,
                )
    except Exception:
        logger.exception(
            "Halbweck-Block komplett fehlgeschlagen (camp=%s, shopping_day=%s) -- "
            "FruehstueckConfig fehlt vermutlich oder Import-Fehler.",
            camp.pk, shopping_day.label,
        )

    # --- Obst aus FruitConfig -- feste Aufteilung nach Liefertag:
    #     Lieferung 1: 1/6, Lieferung 2: 3/6, Lieferung 3: 2/6
    try:
        from apps.meals.models import FruitConfig
        from apps.recipes.models import Ingredient
        from fractions import Fraction

        FRUIT_FRACTIONS = {0: Fraction(1, 6), 1: Fraction(3, 6), 2: Fraction(2, 6)}
        fraction = FRUIT_FRACTIONS.get(shopping_day.index)
        if fraction is None:
            raise ValueError(f"Unbekannter Lieferindex: {shopping_day.index}")

        fruit_cfg = FruitConfig.objects.get(camp=camp)
        fruit_defs = [
            ("amount_apfel",     "weight_apfel",     "Äpfel"),
            ("amount_banane",    "weight_banane",    "Bananen"),
            ("amount_birne",     "weight_birne",     "Wassermelone"),
            ("amount_nektarine", "weight_nektarine", "Nektarinen"),
        ]
        for amount_key, weight_key, fruit_name in fruit_defs:
            total_amount_camp = getattr(fruit_cfg, amount_key, None)
            total_weight_camp = getattr(fruit_cfg, weight_key, None)

            if total_amount_camp:
                amount_this_delivery = round(total_amount_camp * fraction)
                if amount_this_delivery > 0:
                    ing = _lookup_or_create_ingredient(fruit_name, diet_type="vegan", is_fresh=True)
                    add(ing, "Stk", amount_this_delivery, True, "Frühstück/Mittag")

            if total_weight_camp:
                weight_this_delivery = round(total_weight_camp * float(fraction), 2)
                if weight_this_delivery > 0:
                    ing = _lookup_or_create_ingredient(fruit_name, diet_type="vegan", is_fresh=True)
                    add(ing, "kg", weight_this_delivery, True, "Frühstück/Mittag")
    except Exception:
        logger.exception("Obst-Block fehlgeschlagen (camp=%s, shopping_day=%s)", camp.pk, shopping_day.label)

    # --- Dry items: H-Milch, Choco Drink, Margarine, Müsliriegel, Nuss-Nougat ---
    if shopping_day.include_dry:
        try:
            from apps.meals.models import FruehstueckConfig, NussNougatConfig, BrotConfig
            from apps.recipes.models import Ingredient as _Ing
            from datetime import timedelta as _td

            _cfg = FruehstueckConfig.objects.get(camp=camp)
            _teilis = camp.participants.filter(person_type="participant").count() or camp.participant_count
            _total_bread = max(camp.duration_days - 1, 1)
            _loaves_per_day = math.ceil(
                (camp.participants.count() or camp.participant_count + camp.supervisor_count)
                * 2 / 25
            )
            _all_slices     = _loaves_per_day * _total_bread * 25
            _all_teilis_days = _teilis * _total_bread

            # Feste Frühstücksposten als ECHTE Zutaten (nicht mehr als
            # Sonder-Extras): get_or_create legt fehlende Zutaten selbst an,
            # add() macht daraus normale Einkaufslisten-Positionen, die wie
            # alles andere aggregiert, angezeigt und exportiert werden.
            _dry_defs = [
                ("H-Milch",               _total_bread * 15,                 "l",   "vegetarian"),
                ("G&G Choco Drink",       _total_bread,                      "Pck", "vegetarian"),
                ("G&G Pflanzenmargarine", round(_all_slices * 2.5),          "g",   "vegan"),
                ("G&G Müsliriegel",       math.ceil(_all_teilis_days * 1.5), "Stk", "vegetarian"),
            ]
            for _name, _amount, _unit, _diet in _dry_defs:
                if _amount and _amount > 0:
                    ing, _ = _Ing.objects.get_or_create(
                        name=_name, defaults={"diet_type": _diet, "is_fresh": False}
                    )
                    add(ing, _unit, _amount, False, "Frühstück/Mittag")

            # Nuss-Nougat-Creme
            nn_cfg   = NussNougatConfig.objects.get(camp=camp)
            brot_cfg = BrotConfig.objects.get(camp=camp)
            if nn_cfg.g_per_halbweck:
                camp_days_ordered = list(camp.days.order_by("date"))
                if len(camp_days_ordered) >= 2:
                    dw_bread_dates = [d.date for d in camp_days_ordered[1:]]
                    dw_extra_date  = camp_days_ordered[-1].date + _td(days=1)
                    dw_all_dates   = dw_bread_dates + [dw_extra_date]
                    total_doppelweck = 0
                    for dw_date in dw_all_dates:
                        factor = 0.6 if dw_date == dw_extra_date else 1.0
                        total_doppelweck += math.ceil(_teilis * brot_cfg.doppelweck_per_person * factor)
                    nn_total_g = round(nn_cfg.g_per_halbweck * 2 * total_doppelweck * 0.6)
                    if nn_total_g > 0:
                        ing, _ = _Ing.objects.get_or_create(
                            name="G&G Nuss-Nougat-Creme",
                            defaults={"diet_type": "vegetarian", "is_fresh": False},
                        )
                        add(ing, "g", nn_total_g, False, "Frühstück/Mittag")
        except Exception:
            pass

    # --- Allgemeine Zutaten (freizeitweit, nur Lieferung 1) ---
    if shopping_day.include_dry:
        try:
            from apps.meals.models import GeneralIngredient
            for gi in GeneralIngredient.objects.filter(
                camp=camp, category=GeneralIngredient.Category.ALLGEMEIN
            ).select_related("ingredient"):
                add(gi.ingredient, gi.unit, gi.amount, gi.ingredient.is_fresh, "Allgemein")
        except Exception:
            pass

    # --- Betreueressen-Zutaten: gebunden an den Tag des Bezugsrezepts,
    #     landen im Liefertag, der diesen Tag in dinner_indices abdeckt
    #     (gleiche Logik wie Abendessen: Lieferung kommt am selben Tag) ---
    try:
        from apps.meals.models import GeneralIngredient

        # Camp-Tage in Datums-Reihenfolge, um den 0-basierten Index eines
        # CampDay zu bestimmen (entspricht der Reihenfolge von all_day_meals)
        camp_days_ordered = list(camp.days.order_by("date"))
        day_to_index = {d.pk: i for i, d in enumerate(camp_days_ordered)}

        be_items = GeneralIngredient.objects.filter(
            camp=camp, category=GeneralIngredient.Category.BETREUERESSEN,
            day__isnull=False,
        ).select_related("ingredient", "day")

        for gi in be_items:
            day_index = day_to_index.get(gi.day_id)
            if day_index is None:
                continue
            if day_index in shopping_day.dinner_indices:
                add(gi.ingredient, gi.unit, gi.amount, gi.ingredient.is_fresh, "Betreueressen")
    except Exception:
        pass

    # --- Alternative-Zutaten (SKF-Alternativen): identisch zu Betreueressen
    #     aufgebaut -- gebunden an den Tag des Bezugsrezepts, landen im
    #     Liefertag, der diesen Tag in dinner_indices abdeckt. Mengen werden
    #     NICHT skaliert, sie kommen als feste Eingabe direkt aus dem Formular. ---
    try:
        from apps.meals.models import GeneralIngredient

        camp_days_ordered = list(camp.days.order_by("date"))
        day_to_index = {d.pk: i for i, d in enumerate(camp_days_ordered)}

        alt_items = GeneralIngredient.objects.filter(
            camp=camp, category=GeneralIngredient.Category.ALTERNATIVE,
            day__isnull=False,
        ).select_related("ingredient", "day")

        for gi in alt_items:
            day_index = day_to_index.get(gi.day_id)
            if day_index is None:
                continue
            if day_index in shopping_day.dinner_indices:
                add(gi.ingredient, gi.unit, gi.amount, gi.ingredient.is_fresh, "Alternative")
    except Exception:
        pass

    return _round_to_100g(aggregated), _merge_extras(fruehstueck_extras)
