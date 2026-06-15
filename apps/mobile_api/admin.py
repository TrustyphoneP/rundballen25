from django.contrib import admin
from .models import MobileUserProfile, Wochenplan, Aktion


@admin.register(MobileUserProfile)
class MobileUserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "force_password_reset"]
    list_filter = ["force_password_reset"]
    search_fields = ["user__username", "user__first_name", "user__last_name"]
    actions = ["reset_password_flag"]

    @admin.action(description="Passwort-Reset erzwingen (force_password_reset = True)")
    def reset_password_flag(self, request, queryset):
        queryset.update(force_password_reset=True)
        self.message_user(request, f"{queryset.count()} Profile aktualisiert.")


class AktionInline(admin.TabularInline):
    model = Aktion
    extra = 0
    fields = [
        "wochentag", "beginn_stunde", "beginn_minute",
        "ende_stunde", "ende_minute", "titel", "kategorie", "ort",
    ]


@admin.register(Wochenplan)
class WochenplanAdmin(admin.ModelAdmin):
    list_display = ["titel", "camp_id", "erstellt_am"]
    list_filter = ["camp_id"]
    search_fields = ["titel"]
    inlines = [AktionInline]


@admin.register(Aktion)
class AktionAdmin(admin.ModelAdmin):
    list_display = [
        "titel", "wochentag", "beginn_stunde", "beginn_minute",
        "ende_stunde", "ende_minute", "kategorie", "ort",
    ]
    list_filter = ["wochentag", "kategorie", "wochenplan__camp_id"]
    search_fields = ["titel", "beschreibung"]
    filter_horizontal = ["verantwortlich"]
