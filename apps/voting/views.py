from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.views.decorators.http import require_POST

from apps.recipes.models import Recipe
from .models import Poll, VoteRecipe, Vote
from .forms import PollForm


# ---------------------------------------------------------------------------
# Admin – Übersicht
# ---------------------------------------------------------------------------

@login_required
def admin_index(request):
    polls = Poll.objects.select_related("camp").annotate(
        voter_count=Count("vote_recipes__votes__session_key", distinct=True),
    )
    return render(request, "voting/admin_index.html", {"polls": polls})


# ---------------------------------------------------------------------------
# Admin – Poll anlegen
# ---------------------------------------------------------------------------

@login_required
def admin_create(request):
    form = PollForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        poll = form.save(commit=False)
        poll.created_by = request.user
        poll.save()
        imported = 0
        for recipe in Recipe.objects.all():
            VoteRecipe.objects.create(
                poll=poll,
                recipe=recipe,
                name=recipe.name,
                description=recipe.description[:200] if recipe.description else "",
                is_vegan=recipe.is_vegan,
                is_active=True,
            )
            imported += 1
        messages.success(request, f"Abstimmung erstellt. {imported} Rezepte importiert.")
        return redirect("voting:admin_detail", pk=poll.pk)
    return render(request, "voting/admin_create.html", {"form": form})


# ---------------------------------------------------------------------------
# Admin – Detail: Ergebnisse + Gerichte verwalten
# ---------------------------------------------------------------------------

@login_required
def admin_detail(request, pk):
    poll = get_object_or_404(
        Poll.objects.prefetch_related("vote_recipes__votes"),
        pk=pk,
    )
    results = (
        poll.vote_recipes
        .annotate(cnt=Count("votes"))
        .order_by("-cnt", "name")
    )
    # Eindeutige Abstimmende = distinct session_keys
    total_voters = Vote.objects.filter(
        vote_recipe__poll=poll
    ).values("session_key").distinct().count()

    # Abstimmungs-URL
    vote_url = request.build_absolute_uri(
        f"/voting/abstimmen/{poll.pk}/"
    )

    return render(request, "voting/admin_detail.html", {
        "poll":         poll,
        "results":      results,
        "total_voters": total_voters,
        "vote_url":     vote_url,
    })


# ---------------------------------------------------------------------------
# Admin – Status setzen
# ---------------------------------------------------------------------------

@login_required
@require_POST
def admin_set_status(request, pk):
    poll   = get_object_or_404(Poll, pk=pk)
    action = request.POST.get("action")
    if action == "open":
        poll.status    = Poll.Status.OPEN
        poll.closed_at = None
        messages.success(request, "Abstimmung geöffnet.")
    elif action == "close":
        poll.status    = Poll.Status.CLOSED
        poll.closed_at = timezone.now()
        messages.success(request, "Abstimmung geschlossen.")
    elif action == "draft":
        poll.status = Poll.Status.DRAFT
    poll.save()
    return redirect("voting:admin_detail", pk=pk)


# ---------------------------------------------------------------------------
# Admin – Gericht hinzufügen
# ---------------------------------------------------------------------------

@login_required
@require_POST
def admin_add_recipe(request, pk):
    poll = get_object_or_404(Poll, pk=pk)
    name = request.POST.get("name", "").strip()
    if name:
        VoteRecipe.objects.create(
            poll=poll, name=name,
            description=request.POST.get("description", ""),
            is_vegan=request.POST.get("is_vegan") == "on",
            is_active=True,
        )
        messages.success(request, f"'{name}' hinzugefügt.")
    return redirect("voting:admin_detail", pk=pk)


# ---------------------------------------------------------------------------
# Admin – Gericht aktivieren/deaktivieren
# ---------------------------------------------------------------------------

@login_required
@require_POST
def admin_toggle_recipe(request, pk, recipe_pk):
    vr = get_object_or_404(VoteRecipe, pk=recipe_pk, poll__pk=pk)
    vr.is_active = not vr.is_active
    vr.save(update_fields=["is_active"])
    return redirect("voting:admin_detail", pk=pk)


# ---------------------------------------------------------------------------
# Admin – Gericht löschen
# ---------------------------------------------------------------------------

@login_required
@require_POST
def admin_delete_recipe(request, pk, recipe_pk):
    vr = get_object_or_404(VoteRecipe, pk=recipe_pk, poll__pk=pk)
    vr.delete()
    messages.success(request, "Gericht entfernt.")
    return redirect("voting:admin_detail", pk=pk)


# ---------------------------------------------------------------------------
# Admin – Stimmen zurücksetzen (für Tests)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def admin_reset_votes(request, pk):
    poll = get_object_or_404(Poll, pk=pk)
    Vote.objects.filter(vote_recipe__poll=poll).delete()
    messages.success(request, "Alle Stimmen zurückgesetzt.")
    return redirect("voting:admin_detail", pk=pk)


# ---------------------------------------------------------------------------
# Abstimmungs-Screen (öffentlich, Session-basiert)
# ---------------------------------------------------------------------------

def vote(request, poll_id):
    poll    = get_object_or_404(Poll, pk=poll_id)
    session_key = request.session.session_key

    # Session sicherstellen
    if not session_key:
        request.session.create()
        session_key = request.session.session_key

    if poll.status != Poll.Status.OPEN:
        return render(request, "voting/poll_closed.html", {"poll": poll})

    # Bereits abgestimmt?
    session_voted_key = f"voted_poll_{poll_id}"
    already_voted = request.session.get(session_voted_key, False)
    if already_voted:
        my_votes = Vote.objects.filter(
            vote_recipe__poll=poll,
            session_key=session_key,
        ).select_related("vote_recipe")
        return render(request, "voting/already_voted.html", {
            "poll": poll, "my_votes": my_votes,
        })

    recipes = poll.vote_recipes.filter(is_active=True).order_by("sort_order", "name")

    if request.method == "POST":
        selected_ids = request.POST.getlist("recipes")

        if len(selected_ids) > poll.max_votes:
            messages.error(request, f"Maximal {poll.max_votes} Gerichte wählbar.")
            return render(request, "voting/vote.html", {
                "poll": poll, "recipes": recipes,
                "selected_ids": [int(x) for x in selected_ids],
            })

        for rid in selected_ids:
            try:
                vr = poll.vote_recipes.get(pk=rid, is_active=True)
                Vote.objects.get_or_create(vote_recipe=vr, session_key=session_key)
            except VoteRecipe.DoesNotExist:
                pass

        # Session markieren
        request.session[session_voted_key] = True
        request.session.modified = True

        return redirect("voting:thank_you", poll_id=poll_id)

    return render(request, "voting/vote.html", {
        "poll":         poll,
        "recipes":      recipes,
        "selected_ids": [],
    })


# ---------------------------------------------------------------------------
# Danke-Seite
# ---------------------------------------------------------------------------

def thank_you(request, poll_id):
    poll        = get_object_or_404(Poll, pk=poll_id)
    session_key = request.session.session_key
    my_votes    = Vote.objects.filter(
        vote_recipe__poll=poll,
        session_key=session_key,
    ).select_related("vote_recipe")
    return render(request, "voting/thank_you.html", {
        "poll":     poll,
        "my_votes": my_votes,
    })


# ---------------------------------------------------------------------------
# Ergebnisse JSON (Live-Refresh im Admin)
# ---------------------------------------------------------------------------

@login_required
def results_json(request, pk):
    poll    = get_object_or_404(Poll, pk=pk)
    results = (
        poll.vote_recipes.filter(is_active=True)
        .annotate(cnt=Count("votes"))
        .order_by("-cnt")
        .values("name", "cnt", "is_vegan")
    )
    total = Vote.objects.filter(
        vote_recipe__poll=poll
    ).values("session_key").distinct().count()
    return JsonResponse({"results": list(results), "total_voters": total})
