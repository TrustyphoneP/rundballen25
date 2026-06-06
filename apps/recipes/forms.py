from django import forms
from django.forms import inlineformset_factory
from .models import Recipe, RecipeIngredient, Ingredient, RecipeCategory


class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = [
            "name", "category", "description",
            "base_servings", "prep_time_min", "cook_time_min",
            "is_vegan", "is_vegetarian",
            "allergens", "notes",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "notes":       forms.Textarea(attrs={"rows": 2}),
            "allergens":   forms.CheckboxSelectMultiple,
        }


class RecipeIngredientForm(forms.ModelForm):
    # Zutat: Autocomplete-faehiges Textfeld + verstecktes ID-Feld
    ingredient_name = forms.CharField(
        label="Zutat",
        widget=forms.TextInput(attrs={
            "placeholder": "Zutat eingeben...",
            "class": "ingredient-autocomplete",
            "autocomplete": "off",
        }),
    )

    class Meta:
        model  = RecipeIngredient
        fields = ["ingredient", "amount", "unit", "note"]
        widgets = {
            "ingredient": forms.HiddenInput,
            "amount":     forms.NumberInput(attrs={"placeholder": "Menge", "step": "0.001", "min": "0"}),
            "note":       forms.TextInput(attrs={"placeholder": "Hinweis (optional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ingredient-Feld ist hidden, Name kommt aus ingredient_name
        self.fields["ingredient"].required = False
        if self.instance and self.instance.pk and self.instance.ingredient_id:
            self.fields["ingredient_name"].initial = self.instance.ingredient.name

    def clean(self):
        cleaned = super().clean()
        name = cleaned.get("ingredient_name", "").strip()
        ingredient = cleaned.get("ingredient")

        if name and not ingredient:
            # Neü Zutat on-the-fly anlegen
            obj, _ = Ingredient.objects.get_or_create(name=name)
            cleaned["ingredient"] = obj

        return cleaned


# Inline-Formset: mehrere Zutaten auf einmal bearbeiten
RecipeIngredientFormSet = inlineformset_factory(
    Recipe,
    RecipeIngredient,
    form=RecipeIngredientForm,
    extra=5,
    can_delete=True,
    fields=["ingredient", "amount", "unit", "note"],
)


class IngredientForm(forms.ModelForm):
    class Meta:
        model  = Ingredient
        fields = ["name", "allergens", "diet_type", "is_fresh", "notes"]
        widgets = {
            "allergens": forms.CheckboxSelectMultiple,
            "notes":     forms.TextInput(attrs={"placeholder": "Optionale Notiz"}),
        }
