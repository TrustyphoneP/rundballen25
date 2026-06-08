import csv
from decimal import Decimal
from datetime import date

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.camps.models import Camp
from apps.recipes.models import Recipe
from .models import ShoppingList, ShoppingItem
from .forms import ShoppingListFromPlanForm, ShoppingListFromRecipesForm
from .shopping_days import get_shopping_days, build_shopping_day_items


# ---------------------------------------------------------------------------
# Uebersicht
# ---------------------------------------------------------------------------

@login_required
def index(request):
    lists = ShoppingList.objects.select_related("camp", "generated_by").all()
    return render(request, "shopping/index.html", {"lists": lists})


# ---------------------------------------------------------------------------
# Aus Wochenplan generieren
# ---------------------------------------------------------------------------

@login_required
def create_from_plan(request):
    active_camp = Camp.objects.filter(is_active=True).first()

    # Always generate for active camp on GET or POST
    if active_camp:
        return _generate_from_plan(request, active_camp)

    # No active camp: show selection form
    form = ShoppingListFromPlanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        camp = form.cleaned_data["camp"]
        return _generate_from_plan(request, camp)

    return render(request, "shopping/create_from_plan.html", {"form": form})


def _generate_from_plan(request, camp):
    """Generiert drei Einkaufs-ShoppingLists für das Camp."""
    from apps.meals.models import DayMeal
    from apps.camps.models import CampDay

    # Alle Tage geordnet laden
    camp_days = list(
        CampDay.objects.filter(camp=camp).order_by("date")
    )

    # DayMeal pro Tag (None wenn kein Plan)
    day_meal_map = {
        dm.day_id: dm
        for dm in DayMeal.objects.filter(
            day__camp=camp
        ).prefetch_related(
            "main_course__recipe_ingredients__ingredient__allergens",
            "dessert__recipe_ingredients__ingredient__allergens",
            "salad__recipe_ingredients__ingredient__allergens",
        )
    }
    all_day_meals = [day_meal_map.get(cd.id) for cd in camp_days]

    shopping_days = get_shopping_days(camp)

    # Alte Listen für dieses Camp löschen und neu generieren
    ShoppingList.objects.filter(camp=camp).delete()

    created = []
    for sd in shopping_days:
        items, fruehstueck_extras = build_shopping_day_items(camp, sd, all_day_meals)

        sl = ShoppingList.objects.create(
            camp=camp,
            from_date=sd.date,
            to_date=sd.date,
            generated_by=request.user,
            notes=f"{sd.label}: {sd.description}",
        )
        ShoppingItem.objects.bulk_create([
            ShoppingItem(
                shopping_list=sl,
                ingredient=v["ingredient"],
                amount=v["amount"],
                unit=v["unit"],
                notes=v.get("source", "frisch" if v["is_fresh"] else "trocken"),
            )
            for v in items.values()
        ])
        # Store Frühstück extras in list notes for display
        if fruehstueck_extras:
            sl.notes += "\n__fruehstueck__:" + "|".join(
                f"{e['name']}:{e['amount']}:{e['unit']}" for e in fruehstueck_extras
            )
            sl.save(update_fields=["notes"])
        created.append((sd, sl))

    if not any(sl.items.count() > 0 for _, sl in created):
        messages.warning(
            request,
            "Keine Rezepte im Wochenplan gefunden. "
            "Bitte zuerst den Wochenplan befuellen."
        )
    else:
        total_items = sum(sl.items.count() for _, sl in created)
        messages.success(
            request,
            f"{len(created)} Einkaufslisten generiert ({total_items} Positionen gesamt)."
        )

    return redirect("shopping:plan_overview", camp_pk=camp.pk)


# ---------------------------------------------------------------------------
# Einkaufsplan-Uebersicht (alle 3 Listen eines Camps)
# ---------------------------------------------------------------------------

@login_required
def plan_overview(request, camp_pk):
    camp  = get_object_or_404(Camp, pk=camp_pk)
    lists = ShoppingList.objects.filter(camp=camp).order_by("from_date").prefetch_related("items__ingredient")
    shopping_days = get_shopping_days(camp)

    # Listen und Einkaufstage zusammenfuehren
    paired = list(zip(shopping_days, lists)) if lists else []

    # Parse fruehstueck extras from notes for display
    paired_with_extras = []
    for sd, sl in paired:
        extras = []
        if "__fruehstueck__:" in sl.notes:
            raw = sl.notes.split("__fruehstueck__:")[1]
            for entry in raw.split("|"):
                parts = entry.split(":")
                if len(parts) == 3:
                    try:
                        extras.append({"name": parts[0], "amount": float(parts[1]), "unit": parts[2]})
                    except ValueError:
                        pass
        paired_with_extras.append((sd, sl, extras))

    return render(request, "shopping/plan_overview.html", {
        "camp":               camp,
        "lists":              lists,
        "shopping_days":      shopping_days,
        "paired":             paired,
        "paired_with_extras": paired_with_extras,
    })


# ---------------------------------------------------------------------------
# Aus Rezepten generieren (manuell)
# ---------------------------------------------------------------------------

@login_required
def create_from_recipes(request):
    form = ShoppingListFromRecipesForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        camp    = form.cleaned_data["camp"]
        recipes = form.cleaned_data["recipes"]
        persons = form.cleaned_data["persons"]
        notes   = form.cleaned_data.get("notes", "")

        aggregated = {}
        for recipe in recipes:
            for item in recipe.get_scaled_ingredients(persons):
                key = (item["ingredient"].id, item["unit"])
                if key not in aggregated:
                    aggregated[key] = {
                        "ingredient": item["ingredient"],
                        "unit":       item["unit"],
                        "amount":     Decimal("0"),
                    }
                aggregated[key]["amount"] += Decimal(str(item["amount"]))

        sl = ShoppingList.objects.create(
            camp=camp,
            from_date=date.today(),
            to_date=date.today(),
            generated_by=request.user,
            notes=f"{persons} Personen | {', '.join(r.name for r in recipes)}"
                  + (f" | {notes}" if notes else ""),
        )
        ShoppingItem.objects.bulk_create([
            ShoppingItem(
                shopping_list=sl,
                ingredient=v["ingredient"],
                amount=v["amount"],
                unit=v["unit"],
            )
            for v in aggregated.values()
        ])

        messages.success(request, f"Einkaufsliste: {sl.items.count()} Zutaten für {persons} Personen.")
        return redirect("shopping:detail", pk=sl.pk)

    return render(request, "shopping/create_from_recipes.html", {"form": form})


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

@login_required
def detail(request, pk):
    sl    = get_object_or_404(ShoppingList.objects.select_related("camp"), pk=pk)
    items = sl.items.select_related("ingredient").order_by("ingredient__is_fresh", "ingredient__name")
    fresh = items.filter(ingredient__is_fresh=True)
    dry   = items.filter(ingredient__is_fresh=False)
    total   = items.count()
    bought  = items.filter(is_bought=True).count()

    # Build recipe-day info for this delivery
    from apps.meals.models import DayMeal
    from apps.camps.models import CampDay
    from .shopping_days import get_shopping_days

    recipe_days = []  # list of {date, recipes}
    try:
        shopping_days = get_shopping_days(sl.camp)
        # Find which delivery this is by matching date
        matching_sd = next((sd for sd in shopping_days if sd.date == sl.from_date), None)
        if matching_sd:
            for idx in matching_sd.dinner_indices:
                try:
                    day = CampDay.objects.filter(camp=sl.camp).order_by("date")[idx]
                    dm  = DayMeal.objects.filter(day=day).first()
                    if dm:
                        recipes = [r.name for r in [dm.main_course, dm.dessert, dm.salad] if r]
                        if recipes:
                            recipe_days.append({
                                "date":    day.date,
                                "recipes": ", ".join(recipes),
                            })
                except (IndexError, Exception):
                    pass
    except Exception:
        pass

    return render(request, "shopping/detail.html", {
        "sl":          sl,
        "items":       items,
        "fresh":       fresh,
        "dry":         dry,
        "total":       total,
        "bought":      bought,
        "open":        total - bought,
        "recipe_days": recipe_days,
    })


# ---------------------------------------------------------------------------
# Item abhaken (HTMX)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def toggle_item(request, pk):
    item           = get_object_or_404(ShoppingItem, pk=pk)
    item.is_bought = not item.is_bought
    item.save(update_fields=["is_bought"])
    if request.headers.get("HX-Request"):
        return render(request, "shopping/partials/item_row.html", {"item": item})
    return redirect("shopping:detail", pk=item.shopping_list.pk)


# ---------------------------------------------------------------------------
# Alle zurücksetzen
# ---------------------------------------------------------------------------

@login_required
@require_POST
def reset_list(request, pk):
    sl = get_object_or_404(ShoppingList, pk=pk)
    sl.items.update(is_bought=False)
    messages.success(request, "Alle Positionen zurückgesetzt.")
    return redirect("shopping:detail", pk=sl.pk)


# ---------------------------------------------------------------------------
# Neu berechnen
# ---------------------------------------------------------------------------

@login_required
@require_POST
def regenerate(request, pk):
    sl = get_object_or_404(ShoppingList, pk=pk)
    sl.regenerate()
    messages.success(request, f"Neu berechnet: {sl.items.count()} Zutaten.")
    return redirect("shopping:detail", pk=sl.pk)


# ---------------------------------------------------------------------------
# CSV-Export (eine Liste)
# ---------------------------------------------------------------------------

@login_required
def export_csv(request, pk):
    from apps.meals.models import DayMeal
    from apps.camps.models import CampDay
    from apps.recipes.models import RecipeIngredient

    sl = get_object_or_404(ShoppingList, pk=pk)

    # Build ingredient -> {day_numbers, recipe_names} map
    ing_info = {}  # ingredient_id -> {"days": set, "recipes": set}
    camp_days = list(CampDay.objects.filter(camp=sl.camp).order_by("date"))
    day_meals = DayMeal.objects.filter(day__camp=sl.camp).select_related(
        "day", "main_course", "dessert", "salad"
    )
    for dm in day_meals:
        try:
            day_num = next(i+1 for i, d in enumerate(camp_days) if d.pk == dm.day.pk)
        except StopIteration:
            continue
        for recipe in [dm.main_course, dm.dessert, dm.salad]:
            if not recipe:
                continue
            for ri in RecipeIngredient.objects.filter(recipe=recipe).values_list("ingredient_id", flat=True):
                if ri not in ing_info:
                    ing_info[ri] = {"days": set(), "recipes": set()}
                ing_info[ri]["days"].add(day_num)
                ing_info[ri]["recipes"].add(recipe.name)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="einkauf_{slugify(sl.camp.name)}_{sl.from_date}.csv"'
    )
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["Zutat", "Menge", "Einheit", "Typ", "Kategorie", "Zutaten-Notiz", "Tag", "Rezept"])
    for item in sl.items.select_related("ingredient").order_by("ingredient__is_fresh", "ingredient__name"):
        info = ing_info.get(item.ingredient.pk, {})
        days_str    = ", ".join(str(d) for d in sorted(info.get("days", [])))
        recipes_str = ", ".join(sorted(info.get("recipes", [])))
        writer.writerow([
            item.ingredient.name,
            str(item.amount).replace(".", ","),
            item.unit,
            "frisch" if item.ingredient.is_fresh else "trocken",
            item.notes,
            item.ingredient.notes,
            days_str,
            recipes_str,
        ])
    return response


# ---------------------------------------------------------------------------
# Löschen
# ---------------------------------------------------------------------------

@login_required
@require_POST
def delete_list(request, pk):
    sl = get_object_or_404(ShoppingList, pk=pk)
    camp_pk = sl.camp.pk
    sl.delete()
    messages.success(request, "Einkaufsliste geloescht.")
    return redirect("shopping:plan_overview", camp_pk=camp_pk)


# ---------------------------------------------------------------------------
# Kombinierter CSV-Export (alle Listen eines Camps)
# ---------------------------------------------------------------------------

@login_required
def export_csv_combined(request, camp_pk):
    from apps.meals.models import DayMeal
    from apps.camps.models import CampDay
    from apps.recipes.models import RecipeIngredient

    camp  = get_object_or_404(Camp, pk=camp_pk)
    lists = ShoppingList.objects.filter(camp=camp).order_by("from_date").prefetch_related("items__ingredient")

    # Build ingredient -> {day_numbers, recipe_names} map
    ing_info = {}
    camp_days = list(CampDay.objects.filter(camp=camp).order_by("date"))
    day_meals = DayMeal.objects.filter(day__camp=camp).select_related("day", "main_course", "dessert", "salad")
    for dm in day_meals:
        try:
            day_num = next(i+1 for i, d in enumerate(camp_days) if d.pk == dm.day.pk)
        except StopIteration:
            continue
        for recipe in [dm.main_course, dm.dessert, dm.salad]:
            if not recipe:
                continue
            for ri in RecipeIngredient.objects.filter(recipe=recipe).values_list("ingredient_id", flat=True):
                if ri not in ing_info:
                    ing_info[ri] = {"days": set(), "recipes": set()}
                ing_info[ri]["days"].add(day_num)
                ing_info[ri]["recipes"].add(recipe.name)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="einkauf_{slugify(camp.name)}_gesamt.csv"'
    )
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["Lieferung", "Datum", "Kategorie", "Artikel", "Menge", "Einheit", "Typ", "Zutaten-Notiz", "Tag", "Rezept"])

    shopping_days = get_shopping_days(camp)

    for i, sl in enumerate(lists):
        sd = shopping_days[i] if i < len(shopping_days) else None
        label = sd.label if sd else f"Lieferung {i+1}"
        datum = sl.from_date.strftime("%d.%m.%Y")

        for item in sl.items.select_related("ingredient").order_by("notes", "ingredient__name"):
            info = ing_info.get(item.ingredient.pk, {})
            days_str    = ", ".join(str(d) for d in sorted(info.get("days", [])))
            recipes_str = ", ".join(sorted(info.get("recipes", [])))
            writer.writerow([
                label,
                datum,
                item.notes,
                item.ingredient.name,
                str(item.amount).replace(".", ","),
                item.unit,
                "frisch" if item.ingredient.is_fresh else "trocken",
                item.ingredient.notes,
                days_str,
                recipes_str,
            ])

        # Frühstück extras from notes
        if "__fruehstueck__:" in sl.notes:
            raw = sl.notes.split("__fruehstueck__:")[1]
            for entry in raw.split("|"):
                parts = entry.split(":")
                if len(parts) == 3:
                    try:
                        writer.writerow([
                            label, datum, "Frühstück",
                            parts[0],
                            str(float(parts[1])).replace(".", ","),
                            parts[2], "trocken", "", "", "",
                        ])
                    except ValueError:
                        pass

    return response
