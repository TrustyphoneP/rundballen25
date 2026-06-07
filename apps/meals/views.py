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


@login_required
def bread_plan(request, camp_pk=None):
    """
    Brotplanung:
    - Kein Brot am ersten Tag
    - Brot an allen anderen Tagen + einem Tag nach dem letzten Abendessen
    - Doppelweck: 1 pro Person pro Tag
    - Brot: 2 Scheiben pro Person, 25 Scheiben pro Laib, aufrunden
    - Am letzten Tag 40% weniger
    """
    import math

    if camp_pk:
        camp = get_object_or_404(Camp, pk=camp_pk)
    else:
        camp = Camp.objects.filter(is_active=True).first()
        if not camp:
            return redirect("camps:dashboard")

    _ensure_camp_days(camp)

    days = list(CampDay.objects.filter(camp=camp).order_by("date"))
    if not days:
        return render(request, "meals/bread_plan.html", {"camp": camp, "rows": [], "totals": {}})

    # Real person count: actual participants + supervisors from DB
    teilis   = camp.participants.filter(person_type="participant").count()
    betreuer = camp.participants.filter(person_type="supervisor").count()
    persons  = teilis + betreuer or camp.participant_count + camp.supervisor_count

    SLICES_PER_LOAF   = 25
    SLICES_PER_PERSON = 2

    # Bread: skip first camp day only (include last)
    # Doppelweck: same days + one extra day after last camp day
    from datetime import timedelta
    bread_dates      = [d.date for d in days[1:]]
    extra_date       = days[-1].date + timedelta(days=1)
    doppelweck_dates = bread_dates + [extra_date]

    rows = []
    total_loaves     = 0
    total_doppelweck = 0

    for date in doppelweck_dates:
        has_bread  = date in bread_dates
        factor     = 0.6 if date == extra_date else 1.0
        loaves     = math.ceil(persons * SLICES_PER_PERSON / SLICES_PER_LOAF) if has_bread else 0
        doppelweck = math.ceil(persons * factor)

        total_loaves     += loaves
        total_doppelweck += doppelweck
        rows.append({
            "date":       date,
            "is_extra":   date == extra_date,
            "has_bread":  has_bread,
            "persons":    persons,
            "loaves":     loaves,
            "doppelweck": doppelweck,
        })

    totals = {
        "loaves":      total_loaves,
        "doppelweck":  total_doppelweck,
    }

    return render(request, "meals/bread_plan.html", {
        "camp":   camp,
        "rows":   rows,
        "totals": totals,
        "persons": persons,
    })


@login_required
def fruehstueck(request, camp_pk=None):
    """
    Frühstück/Mittagessen: Belagsberechnung.
    Pro Belag wird direkt die Anzahl Brote eingegeben.
    """
    import math
    from .models import FruehstueckConfig

    if camp_pk:
        camp = get_object_or_404(Camp, pk=camp_pk)
    else:
        camp = Camp.objects.filter(is_active=True).first()
        if not camp:
            return redirect("camps:dashboard")

    _ensure_camp_days(camp)
    days = list(CampDay.objects.filter(camp=camp).order_by("date"))

    teilis   = camp.participants.filter(person_type="participant").count()
    betreuer = camp.participants.filter(person_type="supervisor").count()
    persons  = teilis + betreuer or camp.participant_count + camp.supervisor_count

    SLICES_PER_LOAF   = 25
    SLICES_PER_PERSON = 2

    # Load saved config or create with defaults
    saved, _ = FruehstueckConfig.objects.get_or_create(camp=camp)

    # Bread days: skip first camp day only
    bread_dates = [d.date for d in days[1:]] if len(days) >= 2 else []

    # Per-day loaf rows
    total_loaves = 0
    rows = []
    for date in bread_dates:
        loaves = math.ceil(persons * SLICES_PER_PERSON / SLICES_PER_LOAF)
        total_loaves += loaves
        rows.append({"date": date, "loaves": loaves})

    def get_int(key, default):
        if request.method == "POST":
            try:
                return int(request.POST.get(key, default))
            except (ValueError, TypeError):
                return default
        return default

    def get_float(key, default):
        if request.method == "POST":
            try:
                return float(request.POST.get(key, default))
            except (ValueError, TypeError):
                return default
        return default

    # Read from POST or fall back to saved DB values
    t_cheese        = get_int("loaves_cheese",       saved.loaves_cheese)
    t_salami        = get_int("loaves_salami",       saved.loaves_salami)
    t_fleischkaese  = get_int("loaves_fleischkaese", saved.loaves_fleischkaese)
    t_fleischwurst  = get_int("loaves_fleischwurst", saved.loaves_fleischwurst)

    w_cheese        = get_float("weight_cheese",       saved.weight_cheese)
    w_salami        = get_float("weight_salami",       saved.weight_salami)
    w_fleischkaese  = get_float("weight_fleischkaese", saved.weight_fleischkaese)
    w_fleischwurst  = get_float("weight_fleischwurst", saved.weight_fleischwurst)

    spb_cheese       = get_float("spb_cheese",       saved.spb_cheese)
    spb_salami       = get_float("spb_salami",       saved.spb_salami)
    spb_fleischkaese = get_float("spb_fleischkaese", saved.spb_fleischkaese)
    spb_fleischwurst = get_float("spb_fleischwurst", saved.spb_fleischwurst)

    # Save if Speichern button clicked
    if request.method == "POST" and "save" in request.POST:
        saved.loaves_cheese       = t_cheese
        saved.loaves_salami       = t_salami
        saved.loaves_fleischkaese = t_fleischkaese
        saved.loaves_fleischwurst = t_fleischwurst
        saved.weight_cheese       = w_cheese
        saved.weight_salami       = w_salami
        saved.weight_fleischkaese = w_fleischkaese
        saved.weight_fleischwurst = w_fleischwurst
        saved.spb_cheese          = spb_cheese
        saved.spb_salami          = spb_salami
        saved.spb_fleischkaese    = spb_fleischkaese
        saved.spb_fleischwurst    = spb_fleischwurst
        saved.save()

    def calc(loaves, weight_per_slice, slices_per_bread):
        total_slices = loaves * SLICES_PER_LOAF * slices_per_bread
        weight_g     = round(total_slices * weight_per_slice)
        return {"loaves": loaves, "weight_g": weight_g, "weight_kg": round(weight_g / 1000, 2)}

    toppings = [
        {"name": "Käse",        "key": "cheese",       **calc(t_cheese,       w_cheese,       spb_cheese),       "weight_input": str(w_cheese),       "spb": str(spb_cheese)},
        {"name": "Salami",      "key": "salami",       **calc(t_salami,       w_salami,       spb_salami),       "weight_input": str(w_salami),       "spb": str(spb_salami)},
        {"name": "Fleischkäse", "key": "fleischkaese", **calc(t_fleischkaese, w_fleischkaese, spb_fleischkaese), "weight_input": str(w_fleischkaese), "spb": str(spb_fleischkaese)},
        {"name": "Fleischwurst","key": "fleischwurst", **calc(t_fleischwurst, w_fleischwurst, spb_fleischwurst), "weight_input": str(w_fleischwurst), "spb": str(spb_fleischwurst)},
    ]

    total_weight_g = sum(t["weight_g"] for t in toppings)

    # Fixed extras
    num_bread_days     = len(bread_dates)
    total_bread_slices = total_loaves * SLICES_PER_LOAF

    teilis_only = camp.participants.filter(person_type="participant").count() or camp.participant_count

    extras = [
        {
            "name":  "H-Milch",
            "per_day": "15 l",
            "total": f"{num_bread_days * 15} l",
            "note":  "15 l / Tag",
        },
        {
            "name":  "G&G Choco Drink",
            "per_day": "1 Pck",
            "total": f"{num_bread_days} Pck",
            "note":  "1 Pck / Tag",
        },
        {
            "name":  "G&G Pflanzenmargarine",
            "per_day": "—",
            "total": f"{round(total_bread_slices * 2.5)} g  ({round(total_bread_slices * 2.5 / 1000, 2)} kg)",
            "note":  "2,5 g / Brotscheibe",
        },
        {
            "name":  "G&G Müsliriegel",
            "per_day": f"{teilis_only} Stk",
            "total": f"{num_bread_days * teilis_only} Stk",
            "note":  "1,5 Stk / Teili / Tag (gerundet)",
        },
    ]

    # Correct Müsliriegel with 1.5 per teili
    muesli_total = math.ceil(num_bread_days * teilis_only * 1.5)
    muesli_per_day = math.ceil(teilis_only * 1.5)
    extras[3]["per_day"] = f"{muesli_per_day} Stk"
    extras[3]["total"]   = f"{muesli_total} Stk"

    return render(request, "meals/fruehstueck.html", {
        "camp":            camp,
        "persons":         persons,
        "total_loaves":    total_loaves,
        "rows":            rows,
        "toppings":        toppings,
        "total_weight_g":  total_weight_g,
        "total_weight_kg": round(total_weight_g / 1000, 2),
        "saved_at":        saved.updated_at,
        "extras":          extras,
        "num_bread_days":  num_bread_days,
    })
