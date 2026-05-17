from django.contrib import admin
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

admin.site.register(RecipeCategory)
admin.site.register(Ingredient)
admin.site.register(RecipeIngredient)
