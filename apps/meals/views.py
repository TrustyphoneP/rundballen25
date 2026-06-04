"""
meals/views.py – Wochenplan

Zeigt alle Tage der aktiven Freizeit als Kalender-Grid.
Pro Tag: Hauptgericht, Dessert, Salat einzeln zuweisbar per HTMX-Modal.
CampDays werden beim ersten Aufruf automatisch angelegt falls nötig.
"""
from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_POST

from apps.camps.models import Camp, CampDay
from apps.recipes.models import Recipe, RecipeCategory
from .models import DayMeal


SLOTS = [
    ("main_course", "Hauptgericht"),
    ("dessert",     "Dessert"),
    ("salad",       "Salat"),
]


def _ensure_camp_days(camp):
    """Legt CampDay-Objekte für jeden Tag der Freizeit an falls nicht vorhanden."""
    current = camp.start_date
    while current <= camp.end_date:
        CampDay.objects.get_or_create(camp=camp, date=current)
        current += timedelta(days=1)


def _ensure_day_meal(camp_day):
    """Legt DayMeal für einen CampDay an falls nicht vorhanden."""
    obj, _ = DayMeal.objects.get_or_create(day=camp_day)
    return obj


# ---------------------------------------------------------------------------
# Wochenplan – Hauptansicht
# ---------------------------------------------------------------------------

@login_required
def week_plan(request, camp_pk=None):
    if camp_pk:
        camp = get_object_or_404(Camp, pk=camp_pk)
    else:
        camp = Camp.objects.filter(is_active=True).first()
        if not camp:
            messages.warning(request, "Keine aktive Freizeit gefunden.")
            return redirect("camps:dashboard")

    _ensure_camp_days(camp)

    days = (
        CampDay.objects
        .filter(camp=camp)
        .prefetch_related(
            "day_meal__main_course__allergens",
            "day_meal__dessert__allergens",
            "day_meal__salad__allergens",
        )
        .order_by("date")
    )

    # DayMeal für jeden Tag sicherstellen
    for day in days:
        if not hasattr(day, "day_meal") or day.day_meal is None:
            _ensure_day_meal(day)

    # Rezepte nach Kategorie-Name gruppieren für die Auswahl-Dropdowns
    categories = {
        "main_course": Recipe.objects.filter(
            category__name__iexact="Hauptgericht"
        ).order_by("name"),
        "dessert": Recipe.objects.filter(
            category__name__iexact="Dessert"
        ).order_by("name"),
        "salad": Recipe.objects.filter(
            category__name__iexact="Salat"
        ).order_by("name"),
    }

    # Allergen-Warnung: betroffene Teilnehmer pro Allergen
    # (vereinfacht: Anzahl aus Participant-Tabelle)
    from apps.recipes.models import Allergen
    allergen_counts = {}
    for a in Allergen.objects.filter(participants__camp=camp).distinct():
        allergen_counts[a.pk] = a.participants.filter(camp=camp).count()

    return render(request, "meals/week_plan.html", {
        "camp":           camp,
        "days":           days,
        "slots":          SLOTS,
        "categories":     categories,
        "allergen_counts": allergen_counts,
    })


# ---------------------------------------------------------------------------
# Rezept einem Slot zuweisen (HTMX-POST)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def assign_recipe(request, day_pk, slot):
    """Weist einem Slot (main_course / dessert / salad) ein Rezept zu."""
    if slot not in [s[0] for s in SLOTS]:
        return HttpResponse("Ungueltiger Slot", status=400)

    camp_day = get_object_or_404(CampDay, pk=day_pk)
    day_meal = _ensure_day_meal(camp_day)

    recipe_pk = request.POST.get("recipe_id", "").strip()
    if recipe_pk:
        recipe = get_object_or_404(Recipe, pk=recipe_pk)
        setattr(day_meal, slot, recipe)
    else:
        setattr(day_meal, slot, None)

    day_meal.save(update_fields=[slot])

    # Frische Instanz mit Prefetch für das Partial
    day_meal = DayMeal.objects.prefetch_related(
        "main_course__allergens",
        "dessert__allergens",
        "salad__allergens",
    ).get(pk=day_meal.pk)

    from apps.recipes.models import Allergen
    allergen_counts = {}
    camp = camp_day.camp
    for a in Allergen.objects.filter(participants__camp=camp).distinct():
        allergen_counts[a.pk] = a.participants.filter(camp=camp).count()

    categories = {
        "main_course": Recipe.objects.filter(category__name__iexact="Hauptgericht").order_by("name"),
        "dessert":     Recipe.objects.filter(category__name__iexact="Dessert").order_by("name"),
        "salad":       Recipe.objects.filter(category__name__iexact="Salat").order_by("name"),
    }

    return render(request, "meals/partials/day_card.html", {
        "day":            camp_day,
        "day_meal":       day_meal,
        "slots":          SLOTS,
        "categories":     categories,
        "allergen_counts": allergen_counts,
    })


# ---------------------------------------------------------------------------
# Notiz speichern
# ---------------------------------------------------------------------------

@login_required
@require_POST
def save_note(request, day_pk):
    camp_day = get_object_or_404(CampDay, pk=day_pk)
    day_meal = _ensure_day_meal(camp_day)
    day_meal.notes = request.POST.get("notes", "")
    day_meal.save(update_fields=["notes"])
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect("meals:week_plan")


# ---------------------------------------------------------------------------
# Slot leeren
# ---------------------------------------------------------------------------

@login_required
@require_POST
def clear_slot(request, day_pk, slot):
    if slot not in [s[0] for s in SLOTS]:
        return HttpResponse("Ungueltiger Slot", status=400)
    camp_day = get_object_or_404(CampDay, pk=day_pk)
    day_meal = _ensure_day_meal(camp_day)
    setattr(day_meal, slot, None)
    day_meal.save(update_fields=[slot])

    day_meal = DayMeal.objects.prefetch_related(
        "main_course__allergens", "dessert__allergens", "salad__allergens",
    ).get(pk=day_meal.pk)

    from apps.recipes.models import Allergen
    allergen_counts = {}
    camp = camp_day.camp
    for a in Allergen.objects.filter(participants__camp=camp).distinct():
        allergen_counts[a.pk] = a.participants.filter(camp=camp).count()

    categories = {
        "main_course": Recipe.objects.filter(category__name__iexact="Hauptgericht").order_by("name"),
        "dessert":     Recipe.objects.filter(category__name__iexact="Dessert").order_by("name"),
        "salad":       Recipe.objects.filter(category__name__iexact="Salat").order_by("name"),
    }

    return render(request, "meals/partials/day_card.html", {
        "day":            camp_day,
        "day_meal":       day_meal,
        "slots":          SLOTS,
        "categories":     categories,
        "allergen_counts": allergen_counts,
    })
