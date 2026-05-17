from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.views.decorators.http import require_POST

from apps.camps.models import Camp
from apps.recipes.models import Recipe
from .models import Poll, VoteRecipe, VoteToken, Vote
from .forms import PollForm


@login_required
def admin_index(request):
    polls = Poll.objects.select_related("camp").annotate(
        token_count=Count("tokens", distinct=True),
        used_count=Count("tokens", filter=Q(tokens__used=True), distinct=True),
    )
    return render(request, "voting/admin_index.html", {"polls": polls})


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


@login_required
def admin_detail(request, pk):
    poll = get_object_or_404(
        Poll.objects.prefetch_related("vote_recipes__votes", "tokens"),
        pk=pk,
    )
    results = (
        poll.vote_recipes
        .annotate(cnt=Count("votes"))
        .order_by("-cnt", "name")
    )
    return render(request, "voting/admin_detail.html", {
        "poll":         poll,
        "results":      results,
        "total_voters": poll.tokens.filter(used=True).count(),
        "total_tokens": poll.tokens.count(),
    })


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


@login_required
@require_POST
def admin_toggle_recipe(request, pk, recipe_pk):
    vr = get_object_or_404(VoteRecipe, pk=recipe_pk, poll__pk=pk)
    vr.is_active = not vr.is_active
    vr.save(update_fields=["is_active"])
    return redirect("voting:admin_detail", pk=pk)


@login_required
@require_POST
def admin_delete_recipe(request, pk, recipe_pk):
    vr = get_object_or_404(VoteRecipe, pk=recipe_pk, poll__pk=pk)
    vr.delete()
    messages.success(request, "Gericht entfernt.")
    return redirect("voting:admin_detail", pk=pk)


@login_required
@require_POST
def admin_generate_tokens(request, pk):
    poll   = get_object_or_404(Poll, pk=pk)
    count  = max(1, min(int(request.POST.get("count", 1)), 100))
    prefix = request.POST.get("prefix", "").strip()
    for i in range(count):
        label = f"{prefix} {i+1}".strip() if prefix else ""
        VoteToken.objects.create(poll=poll, label=label)
    messages.success(request, f"{count} Token(s) generiert.")
    return redirect("voting:admin_detail", pk=pk)


@login_required
@require_POST
def admin_delete_token(request, pk, token_pk):
    token = get_object_or_404(VoteToken, pk=token_pk, poll__pk=pk)
    token.delete()
    return redirect("voting:admin_detail", pk=pk)


def vote(request, token):
    vtoken = get_object_or_404(VoteToken, token=token)
    poll   = vtoken.poll

    if vtoken.used:
        return render(request, "voting/already_voted.html", {"poll": poll})
    if poll.status != Poll.Status.OPEN:
        return render(request, "voting/poll_closed.html", {"poll": poll})

    recipes = poll.vote_recipes.filter(is_active=True).order_by("sort_order", "name")

    if request.method == "POST":
        selected_ids = request.POST.getlist("recipes")
        if len(selected_ids) > poll.max_votes:
            messages.error(request, f"Maximal {poll.max_votes} Gerichte waehlbar.")
            return render(request, "voting/vote.html", {
                "poll": poll, "recipes": recipes, "vtoken": vtoken,
                "selected_ids": [int(x) for x in selected_ids],
            })
        for rid in selected_ids:
            try:
                vr = poll.vote_recipes.get(pk=rid, is_active=True)
                Vote.objects.get_or_create(token=vtoken, vote_recipe=vr)
            except VoteRecipe.DoesNotExist:
                pass
        vtoken.used    = True
        vtoken.used_at = timezone.now()
        vtoken.save(update_fields=["used", "used_at"])
        return redirect("voting:thank_you", token=token)

    return render(request, "voting/vote.html", {
        "poll": poll, "recipes": recipes, "vtoken": vtoken, "selected_ids": [],
    })


def thank_you(request, token):
    vtoken = get_object_or_404(VoteToken, token=token)
    return render(request, "voting/thank_you.html", {
        "poll":  vtoken.poll,
        "votes": vtoken.votes.select_related("vote_recipe"),
    })


@login_required
def results_json(request, pk):
    poll    = get_object_or_404(Poll, pk=pk)
    results = (
        poll.vote_recipes.filter(is_active=True)
        .annotate(cnt=Count("votes"))
        .order_by("-cnt")
        .values("name", "cnt", "is_vegan")
    )
    return JsonResponse({
        "results":      list(results),
        "total_voters": poll.tokens.filter(used=True).count(),
    })
