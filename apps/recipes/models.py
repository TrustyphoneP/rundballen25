"""
recipes – Herzstück der Unverträglichkeitsverwaltung

Alle 14 EU-Pflichtallergene sind vorinstalliert.
Jedes Rezept kann beliebige Allergene und Diäteigenschaften tragen.
Die Mengenberechnung erfolgt pro Person und skaliert automatisch.
"""
from django.db import models

from decimal import Decimal


class Allergen(models.Model):
    """
    EU-Pflichtallergene (Anhang II VO 1169/2011) + Erweiterungen.
    Wird beim ersten Migrate per Data Migration befüllt.
    """
    name        = models.CharField(max_length=100, unique=True)
    short_code  = models.CharField(max_length=10, unique=True, help_text="z.B. GL, MI, NU")
    description = models.TextField(blank=True)
    icon        = models.CharField(max_length=10, blank=True, help_text="Emoji")
    sort_order  = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Allergen / Unverträglichkeit"
        verbose_name_plural = "Allergene / Unverträglichkeiten"

    def __str__(self):
        return self.name


class RecipeCategory(models.Model):
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=10, blank=True)

    class Meta:
        verbose_name = "Rezeptkategorie"
        verbose_name_plural = "Rezeptkategorien"

    def __str__(self):
        return self.name


class Recipe(models.Model):
    """Ein Rezept mit Zutaten, Diätangaben und Mengenberechnung"""

    name        = models.CharField(max_length=200, verbose_name="Rezeptname")
    description = models.TextField(blank=True)
    category    = models.ForeignKey(
        RecipeCategory, on_delete=models.SET_NULL, null=True, blank=True
    )
    image       = models.ImageField(upload_to="recipes/", blank=True, null=True)

    # Diät-Flags
    is_vegan       = models.BooleanField(default=False, verbose_name="Vegan")
    is_vegetarian  = models.BooleanField(default=False, verbose_name="Vegetarisch")

    # Allergene: welche enthält das Rezept?
    allergens = models.ManyToManyField(
        Allergen, blank=True,
        related_name="recipes",
        verbose_name="Enthaltene Allergene"
    )

    # Basis für Mengenberechnung
    base_servings = models.PositiveIntegerField(
        default=10,
        verbose_name="Basis-Portionen",
        help_text="Für wie viele Personen sind die Zutatenmengen angegeben?"
    )
    prep_time_min  = models.PositiveIntegerField(null=True, blank=True, verbose_name="Zubereitung (Min)")
    cook_time_min  = models.PositiveIntegerField(null=True, blank=True, verbose_name="Kochzeit (Min)")

    notes          = models.TextField(blank=True, verbose_name="Notizen / Hinweise")
    created_by     = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="recipes_created"
    )
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Rezept"
        verbose_name_plural = "Rezepte"

    def get_scaled_ingredients(self, num_persons: int):
        """Gibt Zutaten skaliert auf num_persons zurück."""
        factor = Decimal(num_persons) / Decimal(self.base_servings)
        result = []
        for ri in self.recipe_ingredients.select_related("ingredient"):
            result.append({
                "ingredient": ri.ingredient,
                "amount": ri.amount * factor,
                "unit": ri.unit,
                "note": ri.note,
            })
        return result

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    """Zutat (Stammdaten)"""

    class Unit(models.TextChoices):
        GRAM  = "g",   "Gramm"
        KG    = "kg",  "Kilogramm"
        ML    = "ml",  "Milliliter"
        L     = "l",   "Liter"
        PIECE = "Stk", "Stück"
        TBL   = "EL",  "Esslöffel"
        TSP   = "TL",  "Teelöffel"
        PACK  = "Pck", "Packung"
        BUNCH = "Bd",  "Bund"

    name     = models.CharField(max_length=200, unique=True)
    allergens = models.ManyToManyField(Allergen, blank=True, related_name="ingredients")
    is_vegan  = models.BooleanField(default=True)
    is_fresh  = models.BooleanField(default=False, verbose_name="Frische Zutat", help_text="Frisch (z.B. Gemuese, Fleisch) oder trocken (z.B. Nudeln, Dosenware)")
    notes     = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Zutat"
        verbose_name_plural = "Zutaten"

    def __str__(self):
        return self.name


class RecipeIngredient(models.Model):
    """Menge einer Zutat in einem Rezept (für base_servings)"""

    recipe     = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="recipe_ingredients")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT)
    amount     = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="Menge")
    unit       = models.CharField(max_length=10, choices=Ingredient.Unit.choices, default=Ingredient.Unit.GRAM)
    note       = models.CharField(max_length=200, blank=True, verbose_name="Hinweis")

    class Meta:
        unique_together = [["recipe", "ingredient"]]
        verbose_name = "Rezept-Zutat"
        verbose_name_plural = "Rezept-Zutaten"

    def __str__(self):
        return f"{self.amount} {self.unit} {self.ingredient}"
