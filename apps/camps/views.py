import csv
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, HttpResponseBadRequest
from django.db.models import Count, Q, Prefetch
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.recipes.models import Allergen
from .models import Camp, Participant, CampDay
from .forms import ParticipantForm, ParticipantFilterForm, CsvImportForm, CampForm


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    camps = Camp.objects.filter(is_active=True)
    active_camp = camps.first()

    ctx = {"camps": camps, "active_camp": active_camp}

    if active_camp:
        participants = list(active_camp.participants.prefetch_related("intolerances"))
        total        = len(participants)
        with_intol   = sum(
            1 for p in participants
            if p.is_vegan or p.is_vegetarian or p.is_halal or p.is_kosher
            or p.intolerances.exists()
        )

        # Allergen-Haeufigkeiten für Dashboard
        allergen_counts = (
            Allergen.objects
            .filter(participants__camp=active_camp)
            .annotate(cnt=Count("participants"))
            .filter(cnt__gt=0)
            .order_by("-cnt")[:8]
        )

        ctx.update({
            "total":          total,
            "with_intol":     with_intol,
            "allergen_counts": allergen_counts,
        })

    ctx["stats"] = {
        "mit_intol": ctx.get("with_intol", 0),
        "teilnehmer": sum(1 for p in participants if p.person_type == "participant") if active_camp else 0,
        "betreuer": sum(1 for p in participants if p.person_type == "supervisor") if active_camp else 0,
    }
    return render(request, "camps/dashboard.html", ctx)


# ---------------------------------------------------------------------------
# Teilnehmer – Liste
# ---------------------------------------------------------------------------

@login_required
def participant_list(request, camp_pk):
    camp    = get_object_or_404(Camp, pk=camp_pk)
    form    = ParticipantFilterForm(request.GET or None)
    qs      = camp.participants.prefetch_related("intolerances")

    # Filter anwenden
    if form.is_valid():
        q = form.cleaned_data.get("q")
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q)
            )
        ptype = form.cleaned_data.get("person_type")
        if ptype:
            qs = qs.filter(person_type=ptype)

        intol = form.cleaned_data.get("intolerance")
        if intol:
            qs = qs.filter(intolerances=intol)

        diet = form.cleaned_data.get("diet")
        if diet == "vegan":        qs = qs.filter(is_vegan=True)
        elif diet == "vegetarian": qs = qs.filter(is_vegetarian=True)
        elif diet == "halal":      qs = qs.filter(is_halal=True)
        elif diet == "kosher":     qs = qs.filter(is_kosher=True)
        elif diet == "any_restrict":
            qs = qs.filter(
                Q(is_vegan=True) | Q(is_vegetarian=True) |
                Q(is_halal=True) | Q(is_kosher=True) |
                Q(intolerances__isnull=False)
            ).distinct()

    # Statistiken für den Header
    all_participants = list(camp.participants.prefetch_related("intolerances"))
    stats = {
        "total":       len(all_participants),
        "teilnehmer":  sum(1 for p in all_participants if p.person_type == "participant"),
        "betreuer":    sum(1 for p in all_participants if p.person_type == "supervisor"),
        "mit_intol":   sum(1 for p in all_participants if p.is_vegan or p.is_vegetarian or p.is_halal or p.is_kosher or p.intolerances.exists()),
        "vegan":       sum(1 for p in all_participants if p.is_vegan),
    }

    stats_display = [
        ("Gesamt",              stats["total"],      ""),
        ("Teilnehmer",          stats["teilnehmer"], ""),
        ("Betreuer",            stats["betreuer"],   ""),
        ("Mit Unverträglichkeit", stats["mit_intol"], "text-warn"),
        ("Vegan",               stats["vegan"],      "text-ok"),
    ]
    # Custom sort: SKF/Allergie first, then "Kain" first name, then alphabetical
    participants = list(qs.prefetch_related("intolerances"))

    def sort_key(p):
        has_restriction = (
            p.is_vegan or p.is_vegetarian or p.is_halal or p.is_kosher
            or p.intolerances.exists()
        )
        is_kain = p.first_name.lower() == "kain"
        return (
            0 if has_restriction else (1 if is_kain else 2),
            p.last_name.lower(),
            p.first_name.lower(),
        )

    participants.sort(key=sort_key)

    return render(request, "camps/participant_list.html", {
        "camp":          camp,
        "participants":  participants,
        "filter_form":   form,
        "stats":         stats,
        "stats_display": stats_display,
    })


# ---------------------------------------------------------------------------
# Teilnehmer – Detail
# ---------------------------------------------------------------------------

@login_required
def participant_detail(request, pk):
    from apps.meals.models import DayMeal
    from apps.recipes.models import RecipeIngredient

    p = get_object_or_404(
        Participant.objects.prefetch_related("intolerances", "absent_dates"),
        pk=pk
    )

    # Per-day meal conflict summary
    person_allergen_ids = set(p.intolerances.values_list("pk", flat=True))
    day_conflicts = []

    day_meals = (
        DayMeal.objects
        .filter(day__camp=p.camp)
        .select_related("day", "main_course", "dessert", "salad")
        .order_by("day__date")
    )

    for dm in day_meals:
        conflicts = []
        slots = [
            ("Hauptgericht", dm.main_course),
            ("Dessert",      dm.dessert),
            ("Salat",        dm.salad),
        ]
        for slot_name, recipe in slots:
            if not recipe:
                continue
            issues = []

            # Allergen conflicts
            ingredient_ids = RecipeIngredient.objects.filter(recipe=recipe).values_list("ingredient_id", flat=True)
            recipe_allergen_ids = set(
                recipe.allergens.values_list("pk", flat=True)
            ) | set(
                type(p.intolerances.first()).objects.filter(
                    ingredients__in=ingredient_ids
                ).values_list("pk", flat=True)
                if p.intolerances.exists() else []
            )
            matching_allergens = person_allergen_ids & recipe_allergen_ids
            for allergen in p.intolerances.all():
                if allergen.pk in matching_allergens:
                    issues.append(f"enthält {allergen.name}")

            # SKF conflicts
            diet_types = set(
                RecipeIngredient.objects
                .filter(recipe=recipe)
                .values_list("ingredient__diet_type", flat=True)
            )
            if p.is_vegan and "meat" in diet_types:
                issues.append("enthält Fleisch (Teili ist Vegan)")
            elif p.is_vegan and "vegetarian" in diet_types:
                issues.append("enthält nicht-vegane Zutaten")
            elif p.is_vegetarian and "meat" in diet_types:
                issues.append("enthält Fleisch (Teili ist Vegetarisch)")

            if issues:
                conflicts.append({
                    "slot": slot_name,
                    "recipe": recipe.name,
                    "issues": issues,
                })

        if conflicts:
            day_conflicts.append({
                "date": dm.day.date,
                "conflicts": conflicts,
            })

    return render(request, "camps/participant_detail.html", {
        "person":        p,
        "day_conflicts": day_conflicts,
    })


# ---------------------------------------------------------------------------
# Teilnehmer – Erstellen / Bearbeiten
# ---------------------------------------------------------------------------

@login_required
def participant_create(request, camp_pk):
    camp = get_object_or_404(Camp, pk=camp_pk)
    form = ParticipantForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        person = form.save(commit=False)
        person.camp = camp
        person.save()
        form.save_m2m()
        messages.success(request, f"{person.full_name()} wurde hinzugefuegt.")
        if request.headers.get("HX-Request"):
            # HTMX: Tabellenzeile zurückgeben
            return render(request, "camps/partials/participant_row.html", {"person": person})
        return redirect("camps:participant_list", camp_pk=camp.pk)

    return render(request, "camps/participant_form.html", {
        "form": form, "camp": camp, "action": "Hinzufügen"
    })


@login_required
def participant_edit(request, pk):
    person = get_object_or_404(Participant, pk=pk)
    form   = ParticipantForm(request.POST or None, instance=person)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{person.full_name()} wurde aktualisiert.")
        return redirect("camps:participant_list", camp_pk=person.camp.pk)

    return render(request, "camps/participant_form.html", {
        "form": form, "camp": person.camp, "person": person, "action": "Bearbeiten"
    })


# ---------------------------------------------------------------------------
# Teilnehmer – Löschen
# ---------------------------------------------------------------------------

@login_required
@require_POST
def participant_delete(request, pk):
    person = get_object_or_404(Participant, pk=pk)
    camp_pk = person.camp.pk
    name    = person.full_name()
    person.delete()
    messages.success(request, f"{name} wurde entfernt.")
    if request.headers.get("HX-Request"):
        return HttpResponse("")  # Zeile aus DOM entfernen via HTMX
    return redirect("camps:participant_list", camp_pk=camp_pk)


# ---------------------------------------------------------------------------
# CSV-Export
# ---------------------------------------------------------------------------

@login_required
def participant_csv_export(request, camp_pk):
    camp = get_object_or_404(Camp, pk=camp_pk)
    qs   = camp.participants.prefetch_related("intolerances").all()

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="teilnehmer_{slugify(camp.name)}.csv"'
    )
    response.write("\ufeff")  # BOM für Excel

    writer = csv.writer(response, delimiter=";")
    writer.writerow([
        "Vorname", "Nachname", "Typ",
        "Vegan", "Vegetarisch", "Halal", "Koscher",
        "Allergien", "Zusatzhinweise", "Notizen"
    ])
    for p in qs:
        writer.writerow([
            p.first_name, p.last_name, p.get_person_type_display(),
            "Ja" if p.is_vegan      else "Nein",
            "Ja" if p.is_vegetarian else "Nein",
            "Ja" if p.is_halal      else "Nein",
            "Ja" if p.is_kosher     else "Nein",
            "|".join(a.name for a in p.intolerances.all()),
            p.intolerance_notes,
            p.notes,
        ])
    return response


# ---------------------------------------------------------------------------
# CSV-Import
# ---------------------------------------------------------------------------

@login_required
def participant_csv_import(request, camp_pk):
    camp = get_object_or_404(Camp, pk=camp_pk)
    form = CsvImportForm(request.POST or None, request.FILES or None,
                         initial={"camp": camp})

    if request.method == "POST" and form.is_valid():
        rows, parse_errors = form.parse_rows()

        created = 0
        for row_data in rows:
            allergens = row_data.pop("intolerances", [])
            p = Participant(**row_data)
            p.save()
            p.intolerances.set(allergens)
            created += 1

        if parse_errors:
            for e in parse_errors:
                messages.warning(request, e)
        messages.success(
            request,
            f"{created} Teilnehmer importiert."
        )
        return redirect("camps:participant_list", camp_pk=camp.pk)

    return render(request, "camps/csv_import.html", {"form": form, "camp": camp})


# ---------------------------------------------------------------------------
# CSV-Vorlage
# ---------------------------------------------------------------------------

@login_required
def csv_template(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="teilnehmer_vorlage.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow([
        "Vorname", "Nachname", "Typ",
        "Vegan", "Vegetarisch", "Halal", "Koscher",
        "Allergien", "Zusatzhinweise", "Notizen"
    ])
    writer.writerow([
        "Anna", "Beispiel", "Teilnehmer",
        "Nein", "Ja", "Nein", "Nein",
        "Milch/Laktose|Gluten", "Bitte glutenfreies Brot", ""
    ])
    return response


# ---------------------------------------------------------------------------
# Allergen-Übersicht (HTMX-Panel)
# ---------------------------------------------------------------------------

@login_required
def allergen_overview(request, camp_pk):
    camp = get_object_or_404(Camp, pk=camp_pk)
    allergen_counts = (
        Allergen.objects
        .filter(participants__camp=camp)
        .annotate(cnt=Count("participants"))
        .filter(cnt__gt=0)
        .order_by("-cnt")
    )
    return render(request, "camps/allergen_overview.html", {
        "camp": camp,
        "allergen_counts": allergen_counts,
    })




@login_required
def skf_list(request, camp_pk):
    """Liste aller Teilnehmer mit SKF-Einschränkungen."""
    camp = get_object_or_404(Camp, pk=camp_pk)
    participants = list(
        camp.participants
        .prefetch_related("intolerances")
        .order_by("last_name", "first_name")
    )
    skf_participants = [
        p for p in participants
        if p.is_vegan or p.is_vegetarian or p.is_halal or p.is_kosher
        or p.intolerances.exists()
    ]
    return render(request, "camps/skf_list.html", {
        "camp": camp,
        "participants": skf_participants,
    })


@login_required
def skf_briefing_days(request, camp_pk):
    """Übersicht aller Tage mit SKF-Konflikten."""
    from apps.meals.models import DayMeal
    from apps.recipes.models import RecipeIngredient

    camp = get_object_or_404(Camp, pk=camp_pk)

    # All SKF participants
    skf_participants = list(
        camp.participants
        .prefetch_related("intolerances")
        .filter(
            Q(is_vegan=True) | Q(is_vegetarian=True) |
            Q(is_halal=True) | Q(is_kosher=True) |
            Q(intolerances__isnull=False)
        )
        .distinct()
    )
    skf_allergen_ids = set()
    for p in skf_participants:
        for a in p.intolerances.all():
            skf_allergen_ids.add(a.pk)

    day_meals = (
        DayMeal.objects
        .filter(day__camp=camp)
        .select_related("day", "main_course", "dessert", "salad")
        .order_by("day__date")
    )

    days = []
    for dm in day_meals:
        conflict_count = 0
        for recipe in [dm.main_course, dm.dessert, dm.salad]:
            if not recipe:
                continue
            ingredient_ids = RecipeIngredient.objects.filter(recipe=recipe).values_list("ingredient_id", flat=True)
            recipe_allergen_ids = set(
                type(skf_participants[0].intolerances.first()).objects
                .filter(ingredients__in=ingredient_ids)
                .values_list("pk", flat=True)
            ) if skf_participants and skf_participants[0].intolerances.exists() else set()
            recipe_allergen_ids |= set(recipe.allergens.values_list("pk", flat=True))

            diet_types = set(
                RecipeIngredient.objects
                .filter(recipe=recipe)
                .values_list("ingredient__diet_type", flat=True)
            )
            has_meat = "meat" in diet_types
            has_allergen = bool(skf_allergen_ids & recipe_allergen_ids)
            if has_meat or has_allergen:
                conflict_count += 1

        days.append({
            "day":            dm.day,
            "dm":             dm,
            "conflict_count": conflict_count,
        })

    return render(request, "camps/skf_briefing_days.html", {
        "camp":              camp,
        "days":              days,
        "skf_count":         len(skf_participants),
    })


@login_required
def skf_briefing_day(request, camp_pk, day_pk):
    """SKF-Briefing für einen einzelnen Tag."""
    from apps.meals.models import DayMeal
    from apps.recipes.models import RecipeIngredient, Allergen
    from apps.camps.models import CampDay

    camp    = get_object_or_404(Camp, pk=camp_pk)
    day     = get_object_or_404(CampDay, pk=day_pk, camp=camp)
    dm      = getattr(day, "day_meal", None)

    skf_participants = list(
        camp.participants
        .prefetch_related("intolerances")
        .filter(
            Q(is_vegan=True) | Q(is_vegetarian=True) |
            Q(is_halal=True) | Q(is_kosher=True) |
            Q(intolerances__isnull=False)
        )
        .distinct()
        .order_by("last_name", "first_name")
    )

    briefing = []

    for p in skf_participants:
        person_allergen_ids = set(p.intolerances.values_list("pk", flat=True))
        issues = []

        if dm:
            slots = [
                ("Hauptgericht", dm.main_course),
                ("Dessert",      dm.dessert),
                ("Salat",        dm.salad),
            ]
            for slot_name, recipe in slots:
                if not recipe:
                    continue

                ingredient_ids = list(
                    RecipeIngredient.objects
                    .filter(recipe=recipe)
                    .values_list("ingredient_id", flat=True)
                )
                recipe_allergen_ids = set(
                    Allergen.objects
                    .filter(ingredients__in=ingredient_ids)
                    .values_list("pk", flat=True)
                ) | set(recipe.allergens.values_list("pk", flat=True))

                diet_types = set(
                    RecipeIngredient.objects
                    .filter(recipe=recipe)
                    .values_list("ingredient__diet_type", flat=True)
                )

                slot_issues = []

                # Allergen conflicts
                for allergen in p.intolerances.all():
                    if allergen.pk in recipe_allergen_ids:
                        # Find the specific ingredients causing the issue
                        bad_ingredients = list(
                            RecipeIngredient.objects
                            .filter(recipe=recipe, ingredient__allergens=allergen)
                            .select_related("ingredient")
                            .values_list("ingredient__name", flat=True)
                        )
                        slot_issues.append({
                            "type":        "allergen",
                            "allergen":    allergen.name,
                            "ingredients": bad_ingredients,
                            "action":      f"Ersetze {', '.join(bad_ingredients)} durch {allergen.name}-freie Alternative",
                        })

                # SKF conflicts
                if p.is_vegan and "meat" in diet_types:
                    bad = list(RecipeIngredient.objects.filter(
                        recipe=recipe, ingredient__diet_type="meat"
                    ).values_list("ingredient__name", flat=True))
                    slot_issues.append({
                        "type":        "skf",
                        "allergen":    "Fleisch",
                        "ingredients": bad,
                        "action":      f"Vegane Alternative für {', '.join(bad)}",
                    })
                elif p.is_vegan and "vegetarian" in diet_types:
                    bad = list(RecipeIngredient.objects.filter(
                        recipe=recipe, ingredient__diet_type="vegetarian"
                    ).values_list("ingredient__name", flat=True))
                    slot_issues.append({
                        "type":        "skf",
                        "allergen":    "Nicht vegan",
                        "ingredients": bad,
                        "action":      f"Vegane Alternative für {', '.join(bad)}",
                    })
                elif p.is_vegetarian and "meat" in diet_types:
                    bad = list(RecipeIngredient.objects.filter(
                        recipe=recipe, ingredient__diet_type="meat"
                    ).values_list("ingredient__name", flat=True))
                    slot_issues.append({
                        "type":        "skf",
                        "allergen":    "Fleisch",
                        "ingredients": bad,
                        "action":      f"Vegetarische Alternative für {', '.join(bad)}",
                    })

                if slot_issues:
                    issues.append({
                        "slot":   slot_name,
                        "recipe": recipe.name,
                        "issues": slot_issues,
                    })

        if issues:
            briefing.append({
                "person": p,
                "issues": issues,
            })

    return render(request, "camps/skf_briefing_day.html", {
        "camp":     camp,
        "day":      day,
        "dm":       dm,
        "briefing": briefing,
    })
