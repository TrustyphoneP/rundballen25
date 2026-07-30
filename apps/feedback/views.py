"""
feedback/views.py

Zwei oeffentliche, mobil-optimierte Views fuer Teilis (ohne Login):
  - feedback_home: Liste der Hauptgerichte aus dem Wochenplan
                   + allgemeines Feedback + finales Speichern
  - feedback_day:  Bewertungsseite mit Schieberegler 1-10 und Freitext,
                   Zwischenspeicherung clientseitig in sessionStorage

Eine geschuetzte Auswertung fuer Betreuer:
  - feedback_admin: Durchschnitt, Anzahl und Kommentare pro Gericht
                    sowie alle allgemeinen Rueckmeldungen
"""
import hashlib
import json
import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from apps.camps.models import Camp, CampDay
from .models import RATING_TEXTS, FeedbackSubmission, MealRating

logger = logging.getLogger(__name__)


def _active_camp():
    return Camp.objects.filter(is_active=True).order_by("-start_date").first()


def _days_with_main_course(camp):
    """Alle Tage der Freizeit, die im Wochenplan ein Hauptgericht haben."""
    days = (
        CampDay.objects
        .filter(camp=camp, day_meal__main_course__isnull=False)
        .select_related("day_meal__main_course")
        .order_by("date")
    )
    return list(days)


def _session_hash(request):
    if not request.session.session_key:
        request.session.save()
    return hashlib.sha256(request.session.session_key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Oeffentlich: Hauptliste + finales Speichern
# ---------------------------------------------------------------------------

def feedback_home(request):
    camp = _active_camp()
    if not camp:
        return render(request, "feedback/keine_freizeit.html")

    days = _days_with_main_course(camp)

    if request.method == "POST":
        return _save_submission(request, camp, days)

    return render(request, "feedback/home.html", {
        "camp": camp,
        "days": days,
    })


def _save_submission(request, camp, days):
    """Verarbeitet das finale Speichern aus der Hauptliste."""
    general_comment = (request.POST.get("general_comment") or "").strip()
    raw = request.POST.get("ratings_json") or "{}"

    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("ratings_json ist kein Objekt")
    except (ValueError, TypeError):
        logger.warning("Feedback: ungültiges ratings_json verworfen")
        return HttpResponseBadRequest("Ungültige Bewertungsdaten.")

    valid_days = {str(d.pk): d for d in days}
    ratings = []
    for day_pk, entry in data.items():
        day = valid_days.get(str(day_pk))
        if not day or not isinstance(entry, dict):
            continue
        try:
            rating = int(entry.get("rating"))
        except (TypeError, ValueError):
            continue
        if not 1 <= rating <= 10:
            continue
        comment = str(entry.get("comment") or "").strip()[:2000]
        main = day.day_meal.main_course
        ratings.append(MealRating(
            day=day,
            recipe=main,
            recipe_name=main.name if main else "",
            rating=rating,
            comment=comment,
        ))

    if not ratings and not general_comment:
        return redirect("feedback:home")

    with transaction.atomic():
        submission = FeedbackSubmission.objects.create(
            camp=camp,
            general_comment=general_comment[:4000],
            session_hash=_session_hash(request),
        )
        for r in ratings:
            r.submission = submission
        MealRating.objects.bulk_create(ratings)

    return redirect("feedback:danke")


def feedback_danke(request):
    return render(request, "feedback/danke.html")


# ---------------------------------------------------------------------------
# Oeffentlich: Bewertungsseite fuer einen Tag
# ---------------------------------------------------------------------------

def feedback_day(request, day_pk):
    camp = _active_camp()
    if not camp:
        return render(request, "feedback/keine_freizeit.html")

    day = get_object_or_404(
        CampDay.objects.select_related("day_meal__main_course"),
        pk=day_pk, camp=camp,
    )
    main = getattr(getattr(day, "day_meal", None), "main_course", None)
    if not main:
        return redirect("feedback:home")

    return render(request, "feedback/day.html", {
        "camp": camp,
        "day": day,
        "main": main,
        "rating_texts": RATING_TEXTS,
    })


# ---------------------------------------------------------------------------
# Geschuetzt: Auswertung fuer Betreuer
# ---------------------------------------------------------------------------

@login_required
def feedback_admin(request):
    camp = _active_camp()
    if not camp:
        return render(request, "feedback/admin.html", {"camp": None})

    days = _days_with_main_course(camp)
    submissions = FeedbackSubmission.objects.filter(camp=camp)

    stats = (
        MealRating.objects
        .filter(day__camp=camp)
        .values("day_id")
        .annotate(avg=Avg("rating"), anzahl=Count("id"))
    )
    stats_by_day = {s["day_id"]: s for s in stats}

    day_rows = []
    for day in days:
        s = stats_by_day.get(day.pk, {})
        comments = (
            MealRating.objects
            .filter(day=day)
            .exclude(comment="")
            .order_by("-submission__submitted_at")
        )
        day_rows.append({
            "day": day,
            "main": day.day_meal.main_course,
            "avg": s.get("avg"),
            "anzahl": s.get("anzahl", 0),
            "comments": comments,
        })

    general_comments = (
        submissions.exclude(general_comment="").order_by("-submitted_at")
    )

    return render(request, "feedback/admin.html", {
        "camp": camp,
        "day_rows": day_rows,
        "general_comments": general_comments,
        "total_submissions": submissions.count(),
        "rating_texts": RATING_TEXTS,
    })
