"""
recipes – Herzstück der Unverträglichkeitsverwaltung

Alle 14 EU-Pflichtallergene sind vorinstalliert.
Jedes Rezept kann beliebige Allergene und Diäteigenschaften tragen.
Die Mengenberechnung erfolgt pro Person und skaliert automatisch.
"""
from django.db import models


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
        from decimal import Decimal
        factor = Decimal(str(num_persons)) / Decimal(str(self.base_servings))
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
        GRAM  = "g",   "g"
        KG    = "kg",  "kg"
        ML    = "ml",  "ml"
        L     = "l",   "l"
        PIECE = "Stk", "Stk"
        TBL   = "EL",  "EL"
        TSP   = "TL",  "TL"
        PACK  = "Pck", "Pck"
        BUNCH = "Bd",  "Bd"

    name     = models.CharField(max_length=200, unique=True)
    allergens = models.ManyToManyField(Allergen, blank=True, related_name="ingredients")
    class DietType(models.TextChoices):
        VEGAN       = "vegan",       "Vegan"
        VEGETARIAN  = "vegetarian",  "Vegetarisch"
        MEAT        = "meat",        "Fleisch"

    diet_type = models.CharField(
        max_length=20,
        choices=DietType.choices,
        default=DietType.VEGAN,
        verbose_name="SKF",
    )
    is_fresh  = models.BooleanField(default=False, verbose_name="Frische Zutat", help_text="Frisch (z.B. Gemuese, Fleisch) oder trocken (z.B. Nudeln, Dosenware)")
    notes     = models.CharField(max_length=300, blank=True)

    # Kostenkalkulation
    price = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True,
        verbose_name="Preis (€)",
        help_text="Preis pro 'Preis-Einheit' unten, z.B. 5,36 für 5,36€ pro kg",
    )
    price_unit = models.CharField(
        max_length=10, choices=Unit.choices, blank=True,
        verbose_name="Preis-Einheit",
        help_text="Auf welche Einheit sich der Preis bezieht (z.B. 'kg' bei 5,36€/kg)",
    )

    @property
    def has_price(self):
        return self.price is not None and self.price_unit

    def derive_price_unit(self):
        """
        Ermittelt die Einheit für den Preis direkt aus den tatsächlichen
        Rezept-Verwendungen dieser Zutat (RecipeIngredient.unit), statt sie
        manuell auswählen zu lassen.

        Gibt (einheit, ist_uneinheitlich) zurück:
        - einheit: die Einheit, falls eindeutig ermittelbar, sonst "" (z.B.
          keine Verwendung, oder mehrere unterschiedliche Einheiten)
        - ist_uneinheitlich: True, wenn die Zutat in mehreren Rezepten mit
          unterschiedlichen Einheiten verwendet wird (z.B. einmal "g",
          einmal "kg") -- dann sollte eine Warnung angezeigt werden, da der
          Preis sich nicht eindeutig zuordnen lässt.
        """
        units = list(
            self.recipe_uses_for_pricing()
            .values_list("unit", flat=True)
            .distinct()
        )
        if len(units) == 1:
            return units[0], False
        if len(units) > 1:
            return "", True
        return "", False

    def recipe_uses_for_pricing(self):
        """RecipeIngredient-Zeilen, die diese Zutat verwenden (für
        derive_price_unit und die Admin-Anzeige)."""
        return RecipeIngredient.objects.filter(ingredient=self)

    def save(self, *args, **kwargs):
        # price_unit wird nicht manuell gepflegt, sondern automatisch aus den
        # Rezept-Verwendungen abgeleitet, sobald eindeutig ermittelbar. Bei
        # uneinheitlicher Verwendung (mehrere unterschiedliche Einheiten)
        # bleibt das Feld leer -- price_for() liefert dann bewusst keinen
        # Wert, statt einen falschen zu erraten.
        if self.pk:  # nur möglich, wenn die Zutat schon existiert (FK braucht pk)
            unit, _ = self.derive_price_unit()
            self.price_unit = unit
        super().save(*args, **kwargs)

    def price_for(self, amount, unit):
        """
        Berechnet die Kosten für eine gegebene Menge in einer beliebigen Einheit,
        unter automatischer Umrechnung auf die hinterlegte Preis-Einheit
        (z.B. Rezept nutzt 'g', Preis ist je 'kg' hinterlegt).
        Gibt None zurück, wenn kein Preis hinterlegt ist oder die Einheiten
        nicht zueinander umrechenbar sind (z.B. 'kg' vs 'Stk').
        """
        from decimal import Decimal

        if not self.has_price:
            return None

        _WEIGHT_TO_G = {"g": Decimal("1"), "kg": Decimal("1000")}
        _VOLUME_TO_ML = {"ml": Decimal("1"), "l": Decimal("1000")}

        amount = Decimal(str(amount))

        # Gleiche Einheit: direkt multiplizieren, keine Umrechnung nötig
        if unit == self.price_unit:
            return self.price * amount

        # Gewicht <-> Gewicht (g/kg)
        if unit in _WEIGHT_TO_G and self.price_unit in _WEIGHT_TO_G:
            amount_in_g = amount * _WEIGHT_TO_G[unit]
            price_per_g = self.price / _WEIGHT_TO_G[self.price_unit]
            return amount_in_g * price_per_g

        # Volumen <-> Volumen (ml/l)
        if unit in _VOLUME_TO_ML and self.price_unit in _VOLUME_TO_ML:
            amount_in_ml = amount * _VOLUME_TO_ML[unit]
            price_per_ml = self.price / _VOLUME_TO_ML[self.price_unit]
            return amount_in_ml * price_per_ml

        # Nicht umrechenbar (z.B. 'kg' Rezeptmenge gegen 'Stk' Preiseinheit)
        return None

    @property
    def is_vegan(self):
        return self.diet_type == self.DietType.VEGAN

    @property
    def is_vegetarian(self):
        return self.diet_type in (self.DietType.VEGAN, self.DietType.VEGETARIAN)

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
