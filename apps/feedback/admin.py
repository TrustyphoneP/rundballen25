from django.contrib import admin
from .models import FeedbackSubmission, MealRating


class MealRatingInline(admin.TabularInline):
    model = MealRating
    extra = 0
    readonly_fields = ("day", "recipe", "recipe_name", "rating", "comment")


@admin.register(FeedbackSubmission)
class FeedbackSubmissionAdmin(admin.ModelAdmin):
    list_display = ("submitted_at", "camp", "general_comment")
    list_filter = ("camp",)
    inlines = [MealRatingInline]


@admin.register(MealRating)
class MealRatingAdmin(admin.ModelAdmin):
    list_display = ("recipe_name", "rating", "day", "submission")
    list_filter = ("day__camp", "rating")
