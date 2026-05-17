from django.contrib import admin
from .models import DayMeal, WarmMeal, BreadPlan

@admin.register(DayMeal)
class DayMealAdmin(admin.ModelAdmin):
    list_display  = ["day", "main_course", "dessert", "salad"]
    list_filter   = ["day__camp"]
    raw_id_fields = ["day", "main_course", "dessert", "salad"]

@admin.register(WarmMeal)
class WarmMealAdmin(admin.ModelAdmin):
    list_display = ["day", "recipe"]
    list_filter  = ["day__camp"]

@admin.register(BreadPlan)
class BreadPlanAdmin(admin.ModelAdmin):
    list_display = ["day", "breakfast_loaves", "evening_loaves"]
    list_filter  = ["day__camp"]
