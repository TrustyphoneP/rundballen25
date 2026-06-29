from django.contrib import admin
from django.utils.html import format_html
from .models import Allergen, Recipe, Ingredient, RecipeCategory, RecipeIngredient

@admin.register(Allergen)
class AllergenAdmin(admin.ModelAdmin):
    list_display = ["name", "short_code", "sort_order"]
    ordering     = ["sort_order"]

@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display  = ["name", "category", "is_vegan", "is_vegetarian", "base_servings"]
    filter_horizontal = ["allergens"]
    list_filter   = ["is_vegan", "is_vegetarian", "category"]


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ["name", "price", "price_unit_display"]
    search_fields = ["name"]
    # price_unit wird automatisch aus den Rezept-Verwendungen abgeleitet
    # (Ingredient.save()) -- kein eigenes Eingabefeld im Formular, stattdessen
    # eine read-only Anzeige mit roter Warnung bei uneinheitlicher Verwendung.
    readonly_fields = ["price_unit_display"]
    fields = [
        "name", "allergens", "diet_type", "is_fresh", "notes",
        "price", "price_unit_display",
    ]

    @admin.display(description="Preis-Einheit")
    def price_unit_display(self, obj):
        if not obj.pk:
            return "– (erst nach dem ersten Speichern verfügbar)"
        unit, inconsistent = obj.derive_price_unit()
        if inconsistent:
            used_units = ", ".join(obj.all_units_used())
            return format_html(
                '<span style="color:#c0392b; font-weight:bold;">⚠ Uneinheitlich verwendet ({})'
                ' — Preis kann nicht eindeutig zugeordnet werden.</span>',
                used_units,
            )
        if unit:
            return format_html('<span>{}</span>', unit)
        return "– (noch in keinem Rezept verwendet)"


admin.site.register(RecipeCategory)
admin.site.register(RecipeIngredient)
