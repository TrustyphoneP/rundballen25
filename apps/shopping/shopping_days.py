"""
shopping_days.py – Einkaufstag-Berechnung

Drei Einkaufstage pro Freizeit:
  Tag 1: Einen Tag vor Freizeit-Beginn
          -> Alle trockenen Zutaten (gesamte Freizeit)
          -> Frische Zutaten fuer Tag 1 + Tag 2

  Tag 2: Dritter Tag der Freizeit (index 2, also start + 2)
          -> Frische Zutaten fuer Tag 3, 4, 5

  Tag 3: Sechster Tag der Freizeit (index 5, also start + 5)
          -> Frische Zutaten fuer Tag 6 bis Ende

Faellt ein Einkaufstag auf einen Sonntag (weekday() == 6),
wird er um einen Tag vorgezogen (Samstag).
"""
from datetime import timedelta
from dataclasses import dataclass, field
from typing import List


def _no_sunday(d):
    """Zieht einen Tag vor wenn Sonntag."""
    if d.weekday() == 6:  # Sunday
        return d - timedelta(days=1)
    return d


@dataclass
class ShoppingDay:
    label:       str
    date:        object   # date
    description: str
    day_indices: List[int]  # welche Freizeit-Tage (0-basiert) deckt dieser Einkauf ab
    include_dry: bool = False


def get_shopping_days(camp):
    """
    Gibt drei ShoppingDay-Objekte fuer ein Camp zurueck.
    day_indices sind 0-basiert (0 = erster Freizeit-Tag).
    """
    start = camp.start_date
    duration = camp.duration_days  # Anzahl Tage

    # Einkaufstag 1: Tag vor der Freizeit
    day1_date = _no_sunday(start - timedelta(days=1))

    # Einkaufstag 2: 3. Tag der Freizeit (Index 2 = start + 2)
    # Nur relevant wenn Freizeit laenger als 2 Tage
    day2_raw  = start + timedelta(days=2)
    day2_date = _no_sunday(day2_raw)

    # Einkaufstag 3: 6. Tag der Freizeit (Index 5 = start + 5)
    # Nur relevant wenn Freizeit laenger als 5 Tage
    day3_raw  = start + timedelta(days=5)
    day3_date = _no_sunday(day3_raw)

    days = [
        ShoppingDay(
            label="Einkauf 1",
            date=day1_date,
            description="Alle trockenen Zutaten + Frisches fuer Tag 1–2",
            day_indices=list(range(min(2, duration))),
            include_dry=True,
        ),
    ]

    if duration > 2:
        days.append(ShoppingDay(
            label="Einkauf 2",
            date=day2_date,
            description="Frische Zutaten fuer Tag 3–5",
            day_indices=list(range(2, min(5, duration))),
            include_dry=False,
        ))

    if duration > 5:
        days.append(ShoppingDay(
            label="Einkauf 3",
            date=day3_date,
            description=f"Frische Zutaten fuer Tag 6–{duration}",
            day_indices=list(range(5, duration)),
            include_dry=False,
        ))

    return days


def build_shopping_day_items(camp, shopping_day, all_day_meals):
    """
    Aggregiert Zutaten fuer einen Einkaufstag.

    all_day_meals: geordnete Liste von DayMeal-Objekten (nach Datum),
                   Index 0 = erster Freizeit-Tag.

    Gibt dict: {(ingredient_id, unit) -> {ingredient, unit, amount, is_fresh}}
    """
    from decimal import Decimal

    aggregated = {}

    for idx in shopping_day.day_indices:
        if idx >= len(all_day_meals):
            continue
        meal = all_day_meals[idx]
        if meal is None:
            continue
        for item in meal.get_all_scaled_ingredients():
            ing    = item["ingredient"]
            is_fresh = ing.is_fresh

            if shopping_day.include_dry and not is_fresh:
                continue 

            # Trockene Zutaten nur bei Einkauf 1
            if not is_fresh and not shopping_day.include_dry:
                continue

            key = (ing.id, item["unit"])
            if key not in aggregated:
                aggregated[key] = {
                    "ingredient": ing,
                    "unit":       item["unit"],
                    "amount":     Decimal("0"),
                    "is_fresh":   is_fresh,
                }
            aggregated[key]["amount"] += Decimal(str(item["amount"]))

    # Trockene Zutaten bei Einkauf 1: alle Tage der ganzen Freizeit
    if shopping_day.include_dry:
        for meal in all_day_meals:
            if meal is None:
                continue
            for item in meal.get_all_scaled_ingredients():
                ing = item["ingredient"]
                if ing.is_fresh:
                    continue  # Frische bereits oben per day_indices erfasst
                key = (ing.id, item["unit"])
                if key not in aggregated:
                    aggregated[key] = {
                        "ingredient": ing,
                        "unit":       item["unit"],
                        "amount":     Decimal("0"),
                        "is_fresh":   False,
                    }
                aggregated[key]["amount"] += Decimal(str(item["amount"]))

    return aggregated
