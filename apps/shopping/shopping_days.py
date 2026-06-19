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
from datetime import timedelta
from dataclasses import dataclass, field
from typing import List


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
            dinner_indices=list(range(min(2, duration))),      # day 1-2 dinner
            breakfast_indices=list(range(min(2, duration))),   # day 1-2 breakfast
            include_dry=True,
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
        ))

    if duration > 5:
        days.append(ShoppingDay(
            label="Lieferung 3",
            date=day3_date,
            description=f"Frisches für Abendessen Tag 6–{duration} + Frühstück Tag 6–Ende",
            dinner_indices=list(range(5, duration)),
            breakfast_indices=list(range(5, duration)),
            include_dry=False,
        ))

    return days


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

    def add(ing, unit, amount, is_fresh, source="Abendessen"):
        key = (ing.id, unit)
        if key not in aggregated:
            aggregated[key] = {
                "ingredient": ing,
                "unit":       unit,
                "amount":     Decimal("0"),
                "is_fresh":   is_fresh,
                "source":     source,
            }
        aggregated[key]["amount"] += Decimal(str(amount))

    # --- Abendessen (dinner) ---
    for idx in shopping_day.dinner_indices:
        if idx >= len(all_day_meals):
            continue
        meal = all_day_meals[idx]
        if meal is None:
            continue
        for item in meal.get_all_scaled_ingredients():
            ing      = item["ingredient"]
            is_fresh = ing.is_fresh
            if not is_fresh and not shopping_day.include_dry:
                continue
            add(ing, item["unit"], item["amount"], is_fresh, "Abendessen")

    # --- Alle trockenen Zutaten (nur Lieferung 1) ---
    if shopping_day.include_dry:
        for meal in all_day_meals:
            if meal is None:
                continue
            for item in meal.get_all_scaled_ingredients():
                ing = item["ingredient"]
                if ing.is_fresh:
                    continue  # already handled above per day
                add(ing, item["unit"], item["amount"], False, "Trocken")

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
                return aggregated, fruehstueck_extras

            total_loaves = loaves_per_day * bread_days_this_delivery
            total_slices = total_loaves * SLICES_PER_LOAF

            # Fresh Aufschnitt -- split by delivery, use DB ingredient
            topping_defs = [
                ("loaves_cheese",       "weight_cheese",       "spb_cheese",       "Käseaufschnitt"),
                ("loaves_salami",       "weight_salami",       "spb_salami",       "Salamiaufschnitt"),
                ("loaves_fleischkaese", "weight_fleischkaese", "spb_fleischkaese", "Fleischkäseaufschnitt"),
                ("loaves_fleischwurst", "weight_fleischwurst", "spb_fleischwurst", "Fleischwurstaufschnitt"),
            ]

            for loaves_key, weight_key, spb_key, ing_name in topping_defs:
                loaves_total_camp = getattr(cfg, loaves_key, 0)
                if loaves_total_camp == 0:
                    continue
                loaves_these_days = loaves_total_camp * bread_days_this_delivery / total_bread_days
                weight_per_slice  = getattr(cfg, weight_key, 0)
                spb               = getattr(cfg, spb_key, 1)
                weight_g          = round(loaves_these_days * SLICES_PER_LOAF * spb * weight_per_slice)
                if weight_g > 0:
                    try:
                        ing = Ingredient.objects.get(name=ing_name)
                        add(ing, "g", weight_g, True, "Frühstück")
                    except Ingredient.DoesNotExist:
                        fruehstueck_extras.append({"name": ing_name, "amount": weight_g, "unit": "g"})

            # --- Obst aus FruitConfig -- proportional über alle Liefertage,
            #     analog zum Aufschnitt anhand der Brot-Tage in dieser Lieferung ---
            try:
                from apps.meals.models import FruitConfig

                fruit_cfg = FruitConfig.objects.get(camp=camp)
                fruit_defs = [
                    ("amount_apfel",     "weight_apfel",     "Äpfel"),
                    ("amount_banane",    "weight_banane",    "Bananen"),
                    ("amount_birne",     "weight_birne",     "Birnen"),
                    ("amount_nektarine", "weight_nektarine", "Nektarinen"),
                ]
                for amount_key, weight_key, fruit_name in fruit_defs:
                    total_amount_camp = getattr(fruit_cfg, amount_key, None)
                    total_weight_camp = getattr(fruit_cfg, weight_key, None)

                    if total_amount_camp:
                        amount_these_days = round(total_amount_camp * bread_days_this_delivery / total_bread_days)
                        if amount_these_days > 0:
                            try:
                                ing = Ingredient.objects.get(name=fruit_name)
                                add(ing, "Stk", amount_these_days, True, "Obst")
                            except Ingredient.DoesNotExist:
                                fruehstueck_extras.append({"name": fruit_name, "amount": amount_these_days, "unit": "Stk"})

                    if total_weight_camp:
                        weight_these_days = round(total_weight_camp * bread_days_this_delivery / total_bread_days, 2)
                        if weight_these_days > 0:
                            try:
                                ing = Ingredient.objects.get(name=fruit_name)
                                add(ing, "kg", weight_these_days, True, "Obst")
                            except Ingredient.DoesNotExist:
                                fruehstueck_extras.append({"name": f"{fruit_name} (Gewicht)", "amount": weight_these_days, "unit": "kg"})
            except Exception:
                pass

            # Dry items -- only on first delivery (include_dry)
            if shopping_day.include_dry:
                # Total over all bread days
                all_bread_days  = total_bread_days
                all_loaves     = loaves_per_day * all_bread_days
                all_slices     = all_loaves * SLICES_PER_LOAF
                all_teilis_days = teilis * all_bread_days

                fruehstueck_extras.append({"name": "H-Milch",               "amount": all_bread_days * 15,              "unit": "l"})
                fruehstueck_extras.append({"name": "G&G Choco Drink",        "amount": all_bread_days,                   "unit": "Pck"})
                fruehstueck_extras.append({"name": "G&G Pflanzenmargarine",  "amount": round(all_slices * 2.5),          "unit": "g"})
                fruehstueck_extras.append({"name": "G&G Müsliriegel",        "amount": math.ceil(all_teilis_days * 1.5), "unit": "Stk"})

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

    return aggregated, fruehstueck_extras
