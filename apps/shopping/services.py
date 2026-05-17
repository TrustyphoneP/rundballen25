"""
apps/shopping/services.py – Automatische Einkaufsliste & CSV-Export
"""
import csv
import io
from collections import defaultdict
from decimal import Decimal
from typing import IO

from apps.camps.models import Camp
from apps.meals.models import MealSlot, Ingredient


def generate_shopping_list(camp: Camp) -> list[dict]:
    """
    Aggregiert alle Zutaten über alle Mahlzeit-Slots einer Freizeit.
    Gleiche Zutaten (gleicher Name + Einheit) werden summiert.
    Gibt eine Liste von Dicts zurück, sortiert nach Kategorie und Name.
    """
    aggregated: dict[tuple, dict] = defaultdict(lambda: {
        "name": "", "unit": "", "category": "", "amount": Decimal("0")
    })

    slots = (
        MealSlot.objects
        .filter(day_plan__camp=camp)
        .select_related("recipe", "day_plan__camp")
        .prefetch_related("recipe__ingredients")
    )

    for slot in slots:
        if slot.recipe is None:
            continue
        portions = slot.effective_portions()
        for ing in slot.recipe.ingredients.all():
            key = (ing.name.lower(), ing.unit)
            entry = aggregated[key]
            entry["name"] = ing.name
            entry["unit"] = ing.unit
            entry["category"] = ing.category or "Sonstiges"
            entry["amount"] += Decimal(str(ing.scaled_amount(portions)))

    result = list(aggregated.values())
    result.sort(key=lambda x: (x["category"], x["name"]))
    return result


def shopping_list_as_csv(camp: Camp, file: IO | None = None) -> str | None:
    """
    Schreibt Einkaufsliste als CSV.
    Ohne file-Argument: gibt CSV-String zurück.
    Mit file-Argument: schreibt in die geöffnete Datei.
    """
    items = generate_shopping_list(camp)
    fieldnames = ["Kategorie", "Zutat", "Menge", "Einheit"]

    if file is None:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow({
                "Kategorie": item["category"],
                "Zutat": item["name"],
                "Menge": f"{item['amount']:.2f}".replace(".", ","),
                "Einheit": item["unit"],
            })
        return buf.getvalue()

    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    for item in items:
        writer.writerow({
            "Kategorie": item["category"],
            "Zutat": item["name"],
            "Menge": f"{item['amount']:.2f}".replace(".", ","),
            "Einheit": item["unit"],
        })
    return None


def calculate_bread(camp: Camp) -> list[dict]:
    """
    Brotmengenberechnung: Je Frühstück und Brotzeit-Abend.
    Faustregel: 0.12 Laib pro Person pro Frühstück, 0.10 pro Abend.
    """
    from apps.meals.models import MealSlot
    results = []
    BREAKFAST_FACTOR = 0.12
    DINNER_FACTOR = 0.10

    slots = (
        MealSlot.objects
        .filter(day_plan__camp=camp)
        .select_related("day_plan")
        .order_by("day_plan__date")
    )
    for slot in slots:
        portions = slot.effective_portions()
        if slot.meal_type == MealSlot.MealType.BREAKFAST:
            results.append({
                "date": slot.day_plan.date,
                "meal": "Frühstück",
                "portions": portions,
                "loaves": round(portions * BREAKFAST_FACTOR, 1),
            })
        elif slot.meal_type == MealSlot.MealType.DINNER and (
            slot.recipe is None or "brot" in (slot.notes or "").lower()
        ):
            results.append({
                "date": slot.day_plan.date,
                "meal": "Brotzeit-Abend",
                "portions": portions,
                "loaves": round(portions * DINNER_FACTOR, 1),
            })
    return results
