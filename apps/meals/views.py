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
    import math
    from .models import BrotConfig

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

    teilis   = camp.participants.filter(person_type="participant").count()
    betreuer = camp.participants.filter(person_type="supervisor").count()
    persons  = teilis + betreuer or camp.participant_count + camp.supervisor_count

    # Load or create config
    cfg, _ = BrotConfig.objects.get_or_create(camp=camp)

    def get_float(key, default):
        if request.method == "POST":
            try:
                return float(request.POST.get(key, default))
            except (ValueError, TypeError):
                return default
        return default

    doppelweck_per_person = get_float("doppelweck_per_person", cfg.doppelweck_per_person)
    scheiben_per_person   = get_float("scheiben_per_person",   cfg.scheiben_per_person)
    scheiben_per_laib     = get_float("scheiben_per_laib",     cfg.scheiben_per_laib)

    # Save if Speichern clicked
    if request.method == "POST" and "save" in request.POST:
        cfg.doppelweck_per_person = doppelweck_per_person
        cfg.scheiben_per_person   = scheiben_per_person
        cfg.scheiben_per_laib     = scheiben_per_laib
        cfg.save()

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
        loaves     = math.ceil(persons * scheiben_per_person * factor / scheiben_per_laib) if has_bread else 0
        doppelweck = math.ceil(teilis * doppelweck_per_person * factor)

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
        "camp":                  camp,
        "rows":                  rows,
        "totals":                totals,
        "persons":               persons,
        "cfg":                   cfg,
        "doppelweck_per_person": str(doppelweck_per_person),
        "scheiben_per_person":   str(scheiben_per_person),
        "scheiben_per_laib":     str(scheiben_per_laib),
        "saved_at":              cfg.updated_at,
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

    # Read bread config
    from .models import BrotConfig
    brot_cfg, _ = BrotConfig.objects.get_or_create(camp=camp)
    SLICES_PER_LOAF   = int(brot_cfg.scheiben_per_laib)
    SLICES_PER_PERSON = brot_cfg.scheiben_per_person

    # Load saved config or create with defaults
    saved, _ = FruehstueckConfig.objects.get_or_create(camp=camp)

    from .models import FruitConfig, NussNougatConfig
    saved_fruit, _ = FruitConfig.objects.get_or_create(camp=camp)
    saved_nn, _    = NussNougatConfig.objects.get_or_create(camp=camp)

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

    def get_optional_int(key, default):
        """Wie get_int, aber leeres Feld -> None (Obst-Mengen sind optionale Schätzwerte)."""
        if request.method == "POST":
            raw = request.POST.get(key, "")
            if raw in ("", None):
                return None
            try:
                return int(raw)
            except (ValueError, TypeError):
                return default
        return default

    def get_optional_float(key, default):
        """Wie get_float, aber leeres Feld -> None (Obst-Gewichte sind optionale Schätzwerte)."""
        if request.method == "POST":
            raw = request.POST.get(key, "")
            if raw in ("", None):
                return None
            try:
                return float(raw)
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

    # Obst: Menge (Stück) und Gewicht (kg), beide optional, für die ganze Freizeit
    fruit_amount_apfel     = get_optional_int("amount_apfel",     saved_fruit.amount_apfel)
    fruit_weight_apfel     = get_optional_float("weight_apfel",   saved_fruit.weight_apfel)
    fruit_amount_banane    = get_optional_int("amount_banane",    saved_fruit.amount_banane)
    fruit_weight_banane    = get_optional_float("weight_banane",  saved_fruit.weight_banane)
    fruit_amount_birne     = get_optional_int("amount_birne",     saved_fruit.amount_birne)
    fruit_weight_birne     = get_optional_float("weight_birne",   saved_fruit.weight_birne)
    fruit_amount_nektarine = get_optional_int("amount_nektarine", saved_fruit.amount_nektarine)
    fruit_weight_nektarine = get_optional_float("weight_nektarine", saved_fruit.weight_nektarine)

    # Nuss-Nougat: g pro Halbweck, optional
    nn_g_per_halbweck = get_optional_float("nn_g_per_halbweck", saved_nn.g_per_halbweck)

    # Doppelweck-Gesamtzahl aus Brotplanung (Tag 2 bis Extra-Tag nach Freizeit),
    # identische Logik wie bread_plan() View:
    # - ab Tag 2 (bread_dates), plus Extra-Tag mit Faktor 0.6
    teilis_only = camp.participants.filter(person_type="participant").count() or camp.participant_count
    from datetime import timedelta as _td
    bread_dates_dw = [d.date for d in days[1:]] if len(days) >= 2 else []
    extra_date_dw  = days[-1].date + _td(days=1) if days else None
    doppelweck_dates_all = bread_dates_dw + ([extra_date_dw] if extra_date_dw else [])
    total_doppelweck = 0
    for dw_date in doppelweck_dates_all:
        factor = 0.6 if dw_date == extra_date_dw else 1.0
        total_doppelweck += math.ceil(teilis_only * brot_cfg.doppelweck_per_person * factor)

    # Nuss-Nougat Gesamtmenge: g/Halbweck × 2 Hälften × Anzahl Doppelweck
    nn_total_g = round(nn_g_per_halbweck * 2 * total_doppelweck) if nn_g_per_halbweck else None

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

        saved_fruit.amount_apfel       = fruit_amount_apfel
        saved_fruit.weight_apfel       = fruit_weight_apfel
        saved_fruit.amount_banane      = fruit_amount_banane
        saved_fruit.weight_banane      = fruit_weight_banane
        saved_fruit.amount_birne       = fruit_amount_birne
        saved_fruit.weight_birne       = fruit_weight_birne
        saved_fruit.amount_nektarine   = fruit_amount_nektarine
        saved_fruit.weight_nektarine   = fruit_weight_nektarine
        saved_fruit.save()

        saved_nn.g_per_halbweck = nn_g_per_halbweck
        saved_nn.save()

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

    # Nuss-Nougat als separater Belag unter dem Aufschnitt, mit Trennlinie
    nn_topping = {
        "name":             "Nuss-Nougat-Creme",
        "key":              "nn",
        "g_per_halbweck_input": str(nn_g_per_halbweck) if nn_g_per_halbweck is not None else "",
        "total_doppelweck": total_doppelweck,
        "total_g":          nn_total_g,
        "total_kg":         round(nn_total_g / 1000, 2) if nn_total_g else None,
    }

    total_weight_g = sum(t["weight_g"] for t in toppings)

    # Fixed extras
    num_bread_days     = len(bread_dates)
    total_bread_slices = total_loaves * SLICES_PER_LOAF

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

    def fmt_optional(value):
        """Wandelt None/Zahl in str um, ohne deutsche Komma-Lokalisierung
        (sonst zeigt <input type="number"> den Wert wegen value="5,0" nicht an)."""
        if value is None:
            return ""
        return str(value)

    fruits = [
        {"name": "Äpfel",      "key": "apfel",     "amount": fmt_optional(fruit_amount_apfel),     "weight": fmt_optional(fruit_weight_apfel)},
        {"name": "Bananen",    "key": "banane",    "amount": fmt_optional(fruit_amount_banane),    "weight": fmt_optional(fruit_weight_banane)},
        {"name": "Birnen",     "key": "birne",     "amount": fmt_optional(fruit_amount_birne),     "weight": fmt_optional(fruit_weight_birne)},
        {"name": "Nektarinen", "key": "nektarine", "amount": fmt_optional(fruit_amount_nektarine), "weight": fmt_optional(fruit_weight_nektarine)},
    ]

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
        "fruits":          fruits,
        "nn_topping":      nn_topping,
    })


@login_required
def allgemein(request, camp_pk=None):
    """Allgemeine Zutaten die keinem Rezept zugehören."""
    from .models import GeneralIngredient
    from apps.recipes.models import Ingredient

    if camp_pk:
        camp = get_object_or_404(Camp, pk=camp_pk)
    else:
        camp = Camp.objects.filter(is_active=True).first()
        if not camp:
            return redirect("camps:dashboard")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add":
            ing_name = request.POST.get("ingredient_name", "").strip()
            ing_id   = request.POST.get("ingredient_id", "").strip()
            amount   = request.POST.get("amount", "").strip()
            unit     = request.POST.get("unit", "g").strip()
            notes    = request.POST.get("notes", "").strip()

            if amount:
                try:
                    # Try by ID first, then exact name, else create new
                    if ing_id:
                        ing = Ingredient.objects.get(pk=ing_id)
                    elif ing_name:
                        ing = Ingredient.objects.filter(name__iexact=ing_name).first()
                        if not ing:
                            ing = Ingredient.objects.create(name=ing_name)
                            messages.success(request, f"Neue Zutat '{ing_name}' angelegt.")
                    else:
                        ing = None

                    if ing:
                        GeneralIngredient.objects.create(
                            camp=camp, ingredient=ing,
                            amount=amount, unit=unit, notes=notes,
                            category=GeneralIngredient.Category.ALLGEMEIN,
                        )
                        messages.success(request, f"{ing.name} hinzugefügt.")
                except (Ingredient.DoesNotExist, ValueError) as e:
                    messages.error(request, f"Fehler: {e}")
            else:
                messages.error(request, "Bitte Menge eingeben.")

        elif action == "delete":
            pk = request.POST.get("pk")
            GeneralIngredient.objects.filter(
                pk=pk, camp=camp, category=GeneralIngredient.Category.ALLGEMEIN,
            ).delete()

    items = GeneralIngredient.objects.filter(
        camp=camp, category=GeneralIngredient.Category.ALLGEMEIN,
    ).select_related("ingredient")

    # Autocomplete URL for ingredient search
    from django.urls import reverse
    autocomplete_url = reverse("recipes:ingredient_autocomplete")

    return render(request, "meals/allgemein.html", {
        "camp":             camp,
        "items":            items,
        "autocomplete_url": autocomplete_url,
    })


@login_required
def betreueressen(request, camp_pk=None, day_pk=None):
    """
    Betreueressen: Resteverwertung des Hauptgerichts eines Tages.
    Das Hauptgericht kommt direkt und ausschließlich aus dem Wochenplan
    (DayMeal.main_course) -- read-only, keine eigene Auswahl hier, damit es
    nie vom Wochenplan abweichen kann.

    Zusätzliche Zutaten (z.B. Eier für Eierreis aus Restreis) werden als
    GeneralIngredient(category="betreueressen", day=<dieser Tag>) gespeichert
    und landen im Liefertag, der diesen Tag abdeckt (gleiche Logik wie
    Abendessen-Zutaten).

    Allergen-Warnung bezieht sich NUR auf Personen mit person_type="supervisor",
    nicht auf alle Teilis (anders als im Wochenplan).
    """
    from .models import GeneralIngredient
    from apps.recipes.models import Ingredient

    if camp_pk:
        camp = get_object_or_404(Camp, pk=camp_pk)
    else:
        camp = Camp.objects.filter(is_active=True).first()
        if not camp:
            return redirect("camps:dashboard")

    _ensure_camp_days(camp)
    days = list(
        CampDay.objects.filter(camp=camp)
        .select_related("day_meal", "day_meal__main_course")
        .order_by("date")
    )

    if not days:
        return render(request, "meals/betreueressen.html", {"camp": camp, "days": []})

    # Aktiven Tag bestimmen: per URL-Param day_pk, sonst erster Tag
    if day_pk:
        current_day = get_object_or_404(
            CampDay.objects.select_related("day_meal", "day_meal__main_course"),
            pk=day_pk, camp=camp,
        )
    else:
        current_day = days[0]

    # Hauptgericht read-only aus dem Wochenplan
    main_course = None
    if hasattr(current_day, "day_meal") and current_day.day_meal:
        main_course = current_day.day_meal.main_course

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add":
            ing_name = request.POST.get("ingredient_name", "").strip()
            ing_id   = request.POST.get("ingredient_id", "").strip()
            amount   = request.POST.get("amount", "").strip()
            unit     = request.POST.get("unit", "g").strip()
            notes    = request.POST.get("notes", "").strip()

            if amount:
                try:
                    if ing_id:
                        ing = Ingredient.objects.get(pk=ing_id)
                    elif ing_name:
                        ing = Ingredient.objects.filter(name__iexact=ing_name).first()
                        if not ing:
                            ing = Ingredient.objects.create(name=ing_name)
                            messages.success(request, f"Neue Zutat '{ing_name}' angelegt.")
                    else:
                        ing = None

                    if ing:
                        GeneralIngredient.objects.create(
                            camp=camp, ingredient=ing,
                            amount=amount, unit=unit, notes=notes,
                            category=GeneralIngredient.Category.BETREUERESSEN,
                            day=current_day,
                        )
                        messages.success(request, f"{ing.name} hinzugefügt.")
                except (Ingredient.DoesNotExist, ValueError) as e:
                    messages.error(request, f"Fehler: {e}")
            else:
                messages.error(request, "Bitte Menge eingeben.")

        elif action == "delete":
            pk = request.POST.get("pk")
            GeneralIngredient.objects.filter(
                pk=pk, camp=camp, day=current_day,
                category=GeneralIngredient.Category.BETREUERESSEN,
            ).delete()

        # Redirect, damit der Tag in der URL bleibt (kein Re-POST bei Reload)
        return redirect("meals:betreueressen_day", camp_pk=camp.pk, day_pk=current_day.pk)

    # Original-Zutaten des Hauptgerichts: NUR Anzeige, keine Skalierung
    ref_ingredients = []
    if main_course:
        for ri in main_course.recipe_ingredients.select_related("ingredient").order_by("ingredient__name"):
            ref_ingredients.append({
                "ingredient": ri.ingredient,
                "amount":     ri.amount,
                "unit":       ri.unit,
                "note":       ri.note,
            })

    items = GeneralIngredient.objects.filter(
        camp=camp, day=current_day,
        category=GeneralIngredient.Category.BETREUERESSEN,
    ).select_related("ingredient")

    # Allergen-Warnung NUR für Betreuer (person_type="supervisor"),
    # nicht für alle Teilis wie im Wochenplan
    allergen_counts = {}
    if main_course:
        supervisors = camp.participants.filter(person_type="supervisor").prefetch_related("intolerances")
        for allergen in main_course.allergens.all():
            count = sum(1 for s in supervisors if allergen in s.intolerances.all())
            if count:
                allergen_counts[allergen.pk] = {"allergen": allergen, "count": count}

    from django.urls import reverse
    autocomplete_url = reverse("recipes:ingredient_autocomplete")

    return render(request, "meals/betreueressen.html", {
        "camp":              camp,
        "days":              days,
        "current_day":       current_day,
        "main_course":       main_course,
        "ref_ingredients":   ref_ingredients,
        "items":             items,
        "allergen_counts":   allergen_counts,
        "autocomplete_url":  autocomplete_url,
    })


@login_required
def skf_alternativen(request, camp_pk=None, day_pk=None):
    """
    SKF-Alternativen: Ersatzzutaten für ein Hauptgericht eines Tages, um
    Vegetariern/Teilis mit Unverträglichkeiten eine Alternative zu bieten
    (z.B. 200g Tofu statt Hühnerbrust). Technisch identisch zu
    "Betreueressen" aufgebaut, nur mit eigener Kategorie "alternative".

    Das Hauptgericht kommt direkt und ausschließlich aus dem Wochenplan
    (DayMeal.main_course) -- read-only, keine eigene Auswahl hier.

    WICHTIG: Mengen werden NICHT mit der Teilnehmerzahl skaliert -- die
    eingegebene Menge (z.B. "200g Tofu") geht 1:1 in die Einkaufsliste,
    Kategorie "Alternative".

    Allergen-Warnung bezieht sich NUR auf Personen mit person_type="supervisor",
    nicht auf alle Teilis (anders als im Wochenplan), genau wie Betreueressen.
    """
    from .models import GeneralIngredient
    from apps.recipes.models import Ingredient

    if camp_pk:
        camp = get_object_or_404(Camp, pk=camp_pk)
    else:
        camp = Camp.objects.filter(is_active=True).first()
        if not camp:
            return redirect("camps:dashboard")

    _ensure_camp_days(camp)
    days = list(
        CampDay.objects.filter(camp=camp)
        .select_related("day_meal", "day_meal__main_course")
        .order_by("date")
    )

    if not days:
        return render(request, "meals/skf_alternativen.html", {"camp": camp, "days": []})

    # Aktiven Tag bestimmen: per URL-Param day_pk, sonst erster Tag
    if day_pk:
        current_day = get_object_or_404(
            CampDay.objects.select_related("day_meal", "day_meal__main_course"),
            pk=day_pk, camp=camp,
        )
    else:
        current_day = days[0]

    # Hauptgericht read-only aus dem Wochenplan
    main_course = None
    if hasattr(current_day, "day_meal") and current_day.day_meal:
        main_course = current_day.day_meal.main_course

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add":
            ing_name = request.POST.get("ingredient_name", "").strip()
            ing_id   = request.POST.get("ingredient_id", "").strip()
            amount   = request.POST.get("amount", "").strip()
            unit     = request.POST.get("unit", "g").strip()
            notes    = request.POST.get("notes", "").strip()

            if amount:
                try:
                    if ing_id:
                        ing = Ingredient.objects.get(pk=ing_id)
                    elif ing_name:
                        ing = Ingredient.objects.filter(name__iexact=ing_name).first()
                        if not ing:
                            ing = Ingredient.objects.create(name=ing_name)
                            messages.success(request, f"Neue Zutat '{ing_name}' angelegt.")
                    else:
                        ing = None

                    if ing:
                        GeneralIngredient.objects.create(
                            camp=camp, ingredient=ing,
                            amount=amount, unit=unit, notes=notes,
                            category=GeneralIngredient.Category.ALTERNATIVE,
                            day=current_day,
                        )
                        messages.success(request, f"{ing.name} hinzugefügt.")
                except (Ingredient.DoesNotExist, ValueError) as e:
                    messages.error(request, f"Fehler: {e}")
            else:
                messages.error(request, "Bitte Menge eingeben.")

        elif action == "delete":
            pk = request.POST.get("pk")
            GeneralIngredient.objects.filter(
                pk=pk, camp=camp, day=current_day,
                category=GeneralIngredient.Category.ALTERNATIVE,
            ).delete()

        # Redirect, damit der Tag in der URL bleibt (kein Re-POST bei Reload)
        return redirect("meals:skf_alternativen_day", camp_pk=camp.pk, day_pk=current_day.pk)

    # Original-Zutaten des Hauptgerichts: NUR Anzeige, keine Skalierung
    ref_ingredients = []
    if main_course:
        for ri in main_course.recipe_ingredients.select_related("ingredient").order_by("ingredient__name"):
            ref_ingredients.append({
                "ingredient": ri.ingredient,
                "amount":     ri.amount,
                "unit":       ri.unit,
                "note":       ri.note,
            })

    items = GeneralIngredient.objects.filter(
        camp=camp, day=current_day,
        category=GeneralIngredient.Category.ALTERNATIVE,
    ).select_related("ingredient")

    # Allergen-Warnung NUR für Betreuer (person_type="supervisor"),
    # nicht für alle Teilis wie im Wochenplan
    allergen_counts = {}
    if main_course:
        supervisors = camp.participants.filter(person_type="supervisor").prefetch_related("intolerances")
        for allergen in main_course.allergens.all():
            count = sum(1 for s in supervisors if allergen in s.intolerances.all())
            if count:
                allergen_counts[allergen.pk] = {"allergen": allergen, "count": count}

    from django.urls import reverse
    autocomplete_url = reverse("recipes:ingredient_autocomplete")

    return render(request, "meals/skf_alternativen.html", {
        "camp":              camp,
        "days":              days,
        "current_day":       current_day,
        "main_course":       main_course,
        "ref_ingredients":   ref_ingredients,
        "items":             items,
        "allergen_counts":   allergen_counts,
        "autocomplete_url":  autocomplete_url,
    })
