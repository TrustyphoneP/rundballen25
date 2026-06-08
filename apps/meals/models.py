"""
meals – Mahlzeitenplanung

Pro Tag gibt es ein warmes Abendessen mit drei Komponenten:
  - Hauptgericht  (Rezeptkategorie: Hauptgericht)
  - Dessert       (Rezeptkategorie: Dessert)
  - Salat         (Rezeptkategorie: Salat)

Fruehstueck und Abendbrot laufen ueber BreadPlan.
"""
from decimal import Decimal
from django.db import models
from django.conf import settings


class DayMeal(models.Model):
    """
    Tagesplanung Abendessen: ein CampDay hat genau eine DayMeal-Instanz
    mit je einem optionalen Rezept für Hauptgericht, Dessert und Salat.
    Ersetzt WarmMeal (war nur ein Rezept pro Tag).
    """
    day = models.OneToOneField(
        "camps.CampDay", on_delete=models.CASCADE, related_name="day_meal"
    )
    main_course = models.ForeignKey(
        "recipes.Recipe", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="as_main_course",
        verbose_name="Hauptgericht",
    )
    dessert = models.ForeignKey(
        "recipes.Recipe", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="as_dessert",
        verbose_name="Dessert",
    )
    salad = models.ForeignKey(
        "recipes.Recipe", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="as_salad",
        verbose_name="Salat",
    )
    person_override = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Personenzahl (manuell)",
        help_text="Leer = alle anwesenden Personen des Tages",
    )
    notes = models.TextField(blank=True, verbose_name="Notizen zum Tag")

    class Meta:
        ordering = ["day__date"]
        verbose_name = "Tagesplanung Abendessen"
        verbose_name_plural = "Tagesplanung Abendessen"

    @property
    def persons(self):
        return self.person_override or self.day.persons_present

    def recipes(self):
        """Alle zugewiesenen Rezepte als Liste (ohne None)."""
        return [r for r in [self.main_course, self.dessert, self.salad] if r]

    def get_all_scaled_ingredients(self):
        """
        Aggregiert Zutaten aus allen drei Komponenten skaliert auf Personenzahl.
        Gibt Liste von dicts: {ingredient, amount, unit, note, source}
        """
        from decimal import Decimal
        aggregated = {}
        slots = [
            ("Hauptgericht", self.main_course),
            ("Dessert",      self.dessert),
            ("Salat",        self.salad),
        ]
        for label, recipe in slots:
            if not recipe:
                continue
            for item in recipe.get_scaled_ingredients(self.persons):
                key = (item["ingredient"].id, item["unit"])
                if key not in aggregated:
                    aggregated[key] = {
                        "ingredient": item["ingredient"],
                        "unit":       item["unit"],
                        "amount":     Decimal("0"),
                        "note":       item["note"],
                        "source":     label,
                    }
                aggregated[key]["amount"] += Decimal(str(item["amount"]))
        return list(aggregated.values())

    def allergen_warning(self):
        """Gibt alle Allergene aller Rezepte des Tages zurück."""
        allergens = set()
        for recipe in self.recipes():
            for a in recipe.allergens.all():
                allergens.add(a)
        return allergens

    def is_complete(self):
        return bool(self.main_course)

    def __str__(self):
        parts = []
        if self.main_course: parts.append(self.main_course.name)
        if self.dessert:      parts.append(self.dessert.name)
        if self.salad:        parts.append(self.salad.name)
        return f"{self.day.date}: {' | '.join(parts) or 'kein Rezept'}"


# ---------------------------------------------------------------------------
# Rueckwaertskompatibilitaet: WarmMeal als Alias für alte Referenzen
# ---------------------------------------------------------------------------
class WarmMeal(models.Model):
    """
    Legacy-Modell – bleibt in der DB für bestehende Datensaetze.
    Neü Logik laeuft ueber DayMeal.
    """
    day    = models.OneToOneField(
        "camps.CampDay", on_delete=models.CASCADE, related_name="warm_meal"
    )
    recipe = models.ForeignKey(
        "recipes.Recipe", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="warm_meals",
        verbose_name="Rezept"
    )
    person_override = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["day__date"]
        verbose_name = "Abendessen (alt)"
        verbose_name_plural = "Abendessen (alt)"

    @property
    def persons(self):
        return self.person_override or self.day.persons_present

    def get_scaled_ingredients(self):
        if not self.recipe:
            return []
        return self.recipe.get_scaled_ingredients(self.persons)

    def __str__(self):
        return f"{self.day.date}: {self.recipe.name if self.recipe else 'kein Rezept'}"


class BreadPlan(models.Model):
    day               = models.OneToOneField(
        "camps.CampDay", on_delete=models.CASCADE, related_name="bread_plan"
    )
    breakfast_loaves  = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    evening_loaves    = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    bread_type        = models.CharField(max_length=100, default="Mischbrot", blank=True)
    use_rolls         = models.BooleanField(default=False)
    rolls_count       = models.PositiveIntegerField(null=True, blank=True)
    topping_notes     = models.TextField(blank=True)
    notes             = models.TextField(blank=True)

    class Meta:
        verbose_name = "Brotplanung"
        verbose_name_plural = "Brotplanung"

    @classmethod
    def calculate(cls, camp_day, slices_per_loaf=17):
        cfg     = settings.RUNDBALLEN.get("BREAD_PORTIONS_PER_PERSON", {})
        persons = camp_day.persons_present
        return {
            "breakfast_loaves": round(persons * cfg.get("breakfast", 3) / slices_per_loaf, 1),
            "evening_loaves":   round(persons * cfg.get("evening",   2) / slices_per_loaf, 1),
        }

    @classmethod
    def calculate_and_save(cls, camp_day, slices_per_loaf=17):
        obj, _ = cls.objects.update_or_create(
            day=camp_day, defaults=cls.calculate(camp_day, slices_per_loaf)
        )
        return obj

    @property
    def total_loaves(self):
        return self.breakfast_loaves + self.evening_loaves

    def __str__(self):
        return f"Brot {self.day.date}: {self.breakfast_loaves}+{self.evening_loaves} Laibe"


class FruehstueckConfig(models.Model):
    """Gespeicherte Konfiguration für Frühstück/Mittagessen pro Freizeit."""
    camp = models.OneToOneField(
        "camps.Camp", on_delete=models.CASCADE,
        related_name="fruehstueck_config"
    )
    loaves_cheese       = models.PositiveIntegerField(default=0)
    loaves_salami       = models.PositiveIntegerField(default=0)
    loaves_fleischkaese = models.PositiveIntegerField(default=0)
    loaves_fleischwurst = models.PositiveIntegerField(default=0)

    weight_cheese       = models.FloatField(default=23.0)
    weight_salami       = models.FloatField(default=15.0)
    weight_fleischkaese = models.FloatField(default=20.0)
    weight_fleischwurst = models.FloatField(default=15.0)

    spb_cheese       = models.FloatField(default=1.0)
    spb_salami       = models.FloatField(default=1.5)
    spb_fleischkaese = models.FloatField(default=1.0)
    spb_fleischwurst = models.FloatField(default=2.0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Frühstück Konfiguration"

    def __str__(self):
        return f"Frühstück Konfig: {self.camp}"


class BrotConfig(models.Model):
    """Gespeicherte Konfiguration für Brotplanung pro Freizeit."""
    camp = models.OneToOneField(
        "camps.Camp", on_delete=models.CASCADE,
        related_name="brot_config"
    )
    doppelweck_per_person  = models.FloatField(default=1.0, verbose_name="Doppelweck pro Person")
    scheiben_per_person    = models.FloatField(default=2.0, verbose_name="Scheiben Brot pro Person")
    scheiben_per_laib      = models.FloatField(default=25.0, verbose_name="Scheiben pro Laib")
    updated_at             = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Brot Konfiguration"

    def __str__(self):
        return f"Brot Konfig: {self.camp}"


class GeneralIngredient(models.Model):
    """Allgemeine Zutaten die keinem Rezept zugehören (z.B. Gewürze, Putzmittel)."""
    camp       = models.ForeignKey("camps.Camp", on_delete=models.CASCADE, related_name="general_ingredients")
    ingredient = models.ForeignKey("recipes.Ingredient", on_delete=models.CASCADE, related_name="general_uses")
    amount     = models.DecimalField(max_digits=10, decimal_places=2)
    unit       = models.CharField(max_length=20)
    notes      = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ingredient__name"]
        verbose_name = "Allgemeine Zutat"
        verbose_name_plural = "Allgemeine Zutaten"

    def __str__(self):
        return f"{self.ingredient.name} ({self.amount} {self.unit})"
