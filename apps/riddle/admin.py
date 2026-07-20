from django.contrib import admin
from .models import RiddleStage, RiddleState, PlayerBan


@admin.register(RiddleStage)
class RiddleStageAdmin(admin.ModelAdmin):
    list_display = ("order", "solution_year", "text_solution", "hint_preview", "has_image")
    list_editable = ("solution_year",)
    ordering = ("order",)
    fieldsets = (
        ("Bild-Raetsel", {"fields": ("order", "image", "solution_year", "hint")}),
        (
            "Text-Raetsel (auf /<jahreszahl>)",
            {"fields": ("text_content", "text_solution", "text_response")},
        ),
    )

    def hint_preview(self, obj):
        return obj.hint[:40] if obj.hint else "-"
    hint_preview.short_description = "Hinweis (Vorschau)"

    def has_image(self, obj):
        return bool(obj.image)
    has_image.boolean = True
    has_image.short_description = "Bild?"


@admin.register(RiddleState)
class RiddleStateAdmin(admin.ModelAdmin):
    list_display = ("current_stage", "started_at")

    def has_add_permission(self, request):
        # Nur ein Singleton erlaubt
        return not RiddleState.objects.exists()


@admin.register(PlayerBan)
class PlayerBanAdmin(admin.ModelAdmin):
    list_display = ("ip_address", "banned_until", "wrong_year", "created_at")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)
    ordering = ("-banned_until",)
