from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from .models import Camp, CampDay, Participant


class CampDayInline(admin.TabularInline):
    model   = CampDay
    extra   = 0
    fields  = ["date", "note", "participants_present", "supervisors_present"]
    ordering = ["date"]


@admin.register(Camp)
class CampAdmin(admin.ModelAdmin):
    list_display  = ["name", "start_date", "end_date", "location",
                     "participant_count", "supervisor_count", "is_active"]
    list_filter   = ["is_active"]
    search_fields = ["name", "location"]
    inlines       = [CampDayInline]
    readonly_fields = ["created_at", "created_by"]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class IntoleranceFilter(admin.SimpleListFilter):
    title        = "Unverträglichkeit"
    parameter_name = "intol"

    def lookups(self, request, model_admin):
        from apps.recipes.models import Allergen
        return [(a.pk, a.name) for a in Allergen.objects.all()]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(intolerances__pk=self.value())
        return queryset


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display  = ["full_name", "camp", "person_type", "diet_summary_display",
                     "intolerances_display", "created_at"]
    list_filter   = ["camp", "person_type", "is_vegan", "is_vegetarian",
                     "is_halal", "is_kosher", IntoleranceFilter]
    search_fields = ["first_name", "last_name"]
    filter_horizontal = ["intolerances", "absent_dates"]
    readonly_fields   = ["created_at"]

    fieldsets = [
        ("Person", {"fields": [
            ("first_name", "last_name"),
            ("camp", "person_type", "date_of_birth"),
        ]}),
        ("Diaet", {"fields": [
            ("is_vegan", "is_vegetarian", "is_halal", "is_kosher"),
        ]}),
        ("Unverträglichkeiten", {"fields": [
            "intolerances", "intolerance_notes",
        ]}),
        ("Abwesenheiten", {"fields": ["absent_dates"], "classes": ["collapse"]}),
        ("Sonstiges", {"fields": ["notes", "created_at"], "classes": ["collapse"]}),
    ]

    @admin.display(description="Diaet")
    def diet_summary_display(self, obj):
        flags = obj.diet_flags()
        if not flags:
            return "–"
        return ", ".join(flags)

    @admin.display(description="Allergene")
    def intolerances_display(self, obj):
        names = [a.name for a in obj.intolerances.all()[:4]]
        if not names:
            return "–"
        return format_html(
            '<span style="color:#e07b54">{}</span>',
            ", ".join(names)
        )
