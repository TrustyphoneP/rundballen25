from decimal import Decimal

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import models
from django.db.models import Q, Prefetch
from django.views.decorators.http import require_GET

from .models import Recipe, RecipeIngredient, Ingredient, RecipeCategory, Allergen
from .forms import RecipeForm, RecipeIngredientFormSet, IngredientForm


# ---------------------------------------------------------------------------
# Rezept-Liste
# ---------------------------------------------------------------------------

@login_required
def recipe_list(request):
    qs = Recipe.objects.prefetch_related("allergens", "recipe_ingredients").all()

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

    diet = request.GET.get("diet", "")
    if diet == "vegan":        qs = qs.filter(is_vegan=True)
    elif diet == "vegetarian": qs = qs.filter(is_vegetarian=True)

    allergen_id = request.GET.get("allergen", "")
    if allergen_id:
        qs = qs.exclude(allergens__pk=allergen_id)

    return render(request, "recipes/recipe_list.html", {
        "recipes":    qs,
        "allergens":  Allergen.objects.all(),
        "categories": RecipeCategory.objects.all(),
        "q":          q,
        "diet":       diet,
    })


# ---------------------------------------------------------------------------
# Rezept-Detail (mit skalierter Zutatenliste)
# ---------------------------------------------------------------------------

@login_required
def recipe_detail(request, pk):
    recipe = get_object_or_404(
        Recipe.objects.prefetch_related(
            "allergens",
            Prefetch("recipe_ingredients",
                     queryset=RecipeIngredient.objects.select_related("ingredient").prefetch_related("ingredient__allergens"))
        ),
        pk=pk,
    )

    try:
        persons = int(request.GET.get("persons", ""))
        if persons < 1:
            persons = recipe.base_servings
    except (ValueError, TypeError):
        persons = recipe.base_servings

    scaled = recipe.get_scaled_ingredients(persons)

    # Betroffene Teilnehmer aus aktiver Freizeit
    # Allergen-IDs aus Zutaten UND aus Rezept-Ebene zusammenführen
    from apps.camps.models import Camp, Participant
    affected = []
    active_camp = Camp.objects.filter(is_active=True).first()

    ingredient_ids = RecipeIngredient.objects.filter(recipe=recipe).values_list("ingredient_id", flat=True)
    ingredient_allergen_ids = set(
        Allergen.objects
        .filter(ingredients__in=ingredient_ids)
        .values_list("pk", flat=True)
    )
    recipe_allergen_ids = set(recipe.allergens.values_list("pk", flat=True))
    all_allergen_ids = ingredient_allergen_ids | recipe_allergen_ids

    if active_camp and all_allergen_ids:
        participants = (
            Participant.objects
            .filter(camp=active_camp, intolerances__in=all_allergen_ids)
            .prefetch_related("intolerances")
            .distinct()
            .order_by("last_name", "first_name")
        )
        for p in participants:
            matching = [a for a in p.intolerances.all() if a.pk in all_allergen_ids]
            affected.append({"person": p, "allergens": matching})

    all_allergens = Allergen.objects.filter(pk__in=all_allergen_ids).order_by("name")

    # SKF-Warnung: Fleisch/Vegetarisch-Konflikt
    from apps.camps.models import Participant
    diet_types = set(
        RecipeIngredient.objects
        .filter(recipe=recipe)
        .values_list("ingredient__diet_type", flat=True)
    )
    has_meat       = "meat" in diet_types
    has_vegetarian = "vegetarian" in diet_types
    is_fully_vegan = diet_types == {"vegan"} or diet_types == set()

    skf_affected = []
    if has_meat and active_camp:
        skf_affected = list(
            Participant.objects
            .filter(camp=active_camp)
            .filter(
                models.Q(is_vegan=True) | models.Q(is_vegetarian=True)
            )
            .order_by("last_name", "first_name")
        )

    return render(request, "recipes/recipe_detail.html", {
        "recipe":        recipe,
        "persons":       persons,
        "scaled":        scaled,
        "affected":      affected,
        "active_camp":   active_camp,
        "all_allergens": all_allergens,
        "has_meat":      has_meat,
        "has_vegetarian": has_vegetarian,
        "is_fully_vegan": is_fully_vegan,
        "skf_affected":  skf_affected,
    })


# ---------------------------------------------------------------------------
# Rezept anlegen
# ---------------------------------------------------------------------------

@login_required
def recipe_create(request):
    if request.method == "POST":
        form    = RecipeForm(request.POST, request.FILES)
        formset = RecipeIngredientFormSet(request.POST, prefix="ingredients")

        if form.is_valid() and formset.is_valid():
            recipe = form.save(commit=False)
            recipe.created_by = request.user
            recipe.save()
            form.save_m2m()
            formset.instance = recipe
            _save_formset(formset)
            messages.success(request, f"Rezept \"{recipe.name}\" gespeichert.")
            return redirect("recipes:detail", pk=recipe.pk)
    else:
        form    = RecipeForm()
        formset = RecipeIngredientFormSet(prefix="ingredients")

    return render(request, "recipes/recipe_form.html", {
        "form":    form,
        "formset": formset,
        "action":  "Neues Rezept",
    })


# ---------------------------------------------------------------------------
# Rezept bearbeiten
# ---------------------------------------------------------------------------

@login_required
def recipe_edit(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)

    if request.method == "POST":
        form    = RecipeForm(request.POST, request.FILES, instance=recipe)
        formset = RecipeIngredientFormSet(request.POST, instance=recipe, prefix="ingredients")

        if form.is_valid() and formset.is_valid():
            form.save()
            _save_formset(formset)
            messages.success(request, f"Rezept \"{recipe.name}\" aktualisiert.")
            return redirect("recipes:detail", pk=recipe.pk)
    else:
        form    = RecipeForm(instance=recipe)
        formset = RecipeIngredientFormSet(instance=recipe, prefix="ingredients")
        for subform in formset.forms:
            if subform.instance.pk and subform.instance.ingredient_id:
                subform.fields["ingredient_name"].initial = subform.instance.ingredient.name

    return render(request, "recipes/recipe_form.html", {
        "form":    form,
        "formset": formset,
        "recipe":  recipe,
        "action":  "Rezept bearbeiten",
    })


def _save_formset(formset):
    """Speichert Formset, loest ingredient_name -> ingredient auf."""
    instances = formset.save(commit=False)
    for obj in instances:
        name = obj.__dict__.get("_ingredient_name", "")
        if not obj.ingredient_id and name:
            obj.ingredient, _ = Ingredient.objects.get_or_create(name=name.strip())
        if obj.ingredient_id:
            obj.save()
    for obj in formset.deleted_objects:
        obj.delete()
    for form in formset.forms:
        if form.cleaned_data and not form.cleaned_data.get("DELETE"):
            name       = form.cleaned_data.get("ingredient_name", "").strip()
            ingredient = form.cleaned_data.get("ingredient")
            if name and not ingredient:
                ingredient, _ = Ingredient.objects.get_or_create(name=name)
            if ingredient:
                amount = form.cleaned_data.get("amount")
                unit   = form.cleaned_data.get("unit", "g")
                note   = form.cleaned_data.get("note", "")
                if amount:
                    RecipeIngredient.objects.update_or_create(
                        recipe=formset.instance,
                        ingredient=ingredient,
                        defaults={"amount": amount, "unit": unit, "note": note},
                    )


# ---------------------------------------------------------------------------
# Rezept löschen
# ---------------------------------------------------------------------------

@login_required
def recipe_delete(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    if request.method == "POST":
        name = recipe.name
        recipe.delete()
        messages.success(request, f"Rezept \"{name}\" geloescht.")
        return redirect("recipes:list")
    return render(request, "recipes/recipe_confirm_delete.html", {"recipe": recipe})


# ---------------------------------------------------------------------------
# Zutat-Autocomplete — gibt auch allergen_ids zurück für JS-Autohaken
# ---------------------------------------------------------------------------

@login_required
@require_GET
def ingredient_autocomplete(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    qs = (
        Ingredient.objects
        .filter(name__icontains=q)
        .prefetch_related("allergens")[:15]
    )
    results = [
        {
            "id":           ing.id,
            "name":         ing.name,
            "allergen_ids": [a.id for a in ing.allergens.all()],
        }
        for ing in qs
    ]
    return JsonResponse({"results": results})


# ---------------------------------------------------------------------------
# Zutat-Verwaltung
# ---------------------------------------------------------------------------

@login_required
def ingredient_list(request):
    qs = Ingredient.objects.prefetch_related("allergens").all()
    q  = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(name__icontains=q)
    return render(request, "recipes/ingredient_list.html", {
        "ingredients": qs, "q": q,
    })


@login_required
def ingredient_create(request):
    form = IngredientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Zutat gespeichert.")
        if request.headers.get("HX-Request"):
            return JsonResponse({"id": form.instance.pk, "name": form.instance.name})
        return redirect("recipes:ingredient_list")
    return render(request, "recipes/ingredient_form.html", {"form": form})


@login_required
def ingredient_edit(request, pk):
    ingredient = get_object_or_404(Ingredient, pk=pk)
    form = IngredientForm(request.POST or None, instance=ingredient)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"\"{ingredient.name}\" aktualisiert.")
        return redirect("recipes:ingredient_list")
    return render(request, "recipes/ingredient_form.html", {
        "form": form, "ingredient": ingredient,
    })
