from django import forms
from apps.camps.models import Camp
from apps.recipes.models import Recipe
from .models import ShoppingList, ShoppingItem


class ShoppingListFromPlanForm(forms.Form):
    """
    Einkaufsliste aus dem Wochenplan generieren.
    Liest alle WarmMeals im Zeitraum und aggregiert die Zutaten.
    """
    camp      = forms.ModelChoiceField(
        queryset=Camp.objects.filter(is_active=True),
        label="Freizeit",
    )
    from_date = forms.DateField(
        label="Von",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    to_date   = forms.DateField(
        label="Bis",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    notes = forms.CharField(
        required=False,
        label="Notizen",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Optionale Notizen..."}),
    )

    def clean(self):
        cleaned = super().clean()
        f = cleaned.get("from_date")
        t = cleaned.get("to_date")
        if f and t and t < f:
            raise forms.ValidationError("Enddatum muss nach dem Startdatum liegen.")
        return cleaned


class ShoppingListFromRecipesForm(forms.Form):
    """
    Einkaufsliste aus manuell gewaehlten Rezepten + Personenzahl generieren.
    Kein Wochenplan noetig — gut fuer einmalige Aktionen.
    """
    camp      = forms.ModelChoiceField(
        queryset=Camp.objects.filter(is_active=True),
        label="Freizeit (fuer Zuordnung)",
    )
    recipes   = forms.ModelMultipleChoiceField(
        queryset=Recipe.objects.prefetch_related("recipe_ingredients"),
        label="Rezepte",
        widget=forms.CheckboxSelectMultiple,
    )
    persons   = forms.IntegerField(
        label="Personenzahl",
        min_value=1,
        max_value=500,
        initial=130,
        help_text="Fuer wie viele Personen soll berechnet werden?",
    )
    notes = forms.CharField(
        required=False,
        label="Notizen",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Optionale Notizen..."}),
    )


class ShoppingItemNoteForm(forms.ModelForm):
    class Meta:
        model  = ShoppingItem
        fields = ["notes", "is_bought"]
