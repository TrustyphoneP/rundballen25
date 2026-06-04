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
        participants = active_camp.participants.prefetch_related("intolerances")
        total        = participants.count()
        with_intol   = participants.filter(
            Q(intolerances__isnull=False) |
            Q(is_vegan=True) | Q(is_vegetarian=True) |
            Q(is_halal=True) | Q(is_kosher=True)
        ).distinct().count()

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

    # active_camp already in ctx; also expose stats for sidebar badge
    ctx["stats"] = {"mit_intol": ctx.get("with_intol", 0)}
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
    all_participants = camp.participants.prefetch_related("intolerances")
    stats = {
        "total":       all_participants.count(),
        "teilnehmer":  all_participants.filter(person_type="participant").count(),
        "betreuer":    all_participants.filter(person_type="supervisor").count(),
        "mit_intol":   all_participants.filter(intolerances__isnull=False).distinct().count(),
        "vegan":       all_participants.filter(is_vegan=True).count(),
    }

    stats_display = [
        ("Gesamt",              stats["total"],      ""),
        ("Teilnehmer",          stats["teilnehmer"], ""),
        ("Betreuer",            stats["betreuer"],   ""),
        ("Mit Unverträglichkeit", stats["mit_intol"], "text-warn"),
        ("Vegan",               stats["vegan"],      "text-ok"),
    ]
    return render(request, "camps/participant_list.html", {
        "camp":          camp,
        "participants":  qs,
        "filter_form":   form,
        "stats":         stats,
        "stats_display": stats_display,
    })


# ---------------------------------------------------------------------------
# Teilnehmer – Detail
# ---------------------------------------------------------------------------

@login_required
def participant_detail(request, pk):
    p = get_object_or_404(
        Participant.objects.prefetch_related("intolerances", "absent_dates"),
        pk=pk
    )
    return render(request, "camps/participant_detail.html", {"person": p})


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
# Allergen-Uebersicht (HTMX-Panel)
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


