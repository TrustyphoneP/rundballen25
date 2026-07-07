from django.contrib import admin

from .models import Beleg, BelegPosition, Preishistorie


class BelegPositionInline(admin.TabularInline):
    model = BelegPosition
    extra = 0
    fields = [
        "sortierung", "artikel_name", "menge", "einheit",
        "gesamtpreis", "grundpreis", "grundpreis_einheit",
        "ingredient", "hinweis", "ist_uebernommen",
    ]
    autocomplete_fields = ["ingredient"]


@admin.register(Beleg)
class BelegAdmin(admin.ModelAdmin):
    list_display = [
        "pk", "camp", "haendler", "kaufdatum", "gesamtbetrag",
        "status", "hochgeladen_von", "hochgeladen_am",
    ]
    list_filter = ["status", "camp"]
    search_fields = ["haendler", "notiz"]
    readonly_fields = ["analyse_rohdaten", "analyse_fehler", "analysiert_am", "hochgeladen_am"]
    inlines = [BelegPositionInline]


@admin.register(Preishistorie)
class PreishistorieAdmin(admin.ModelAdmin):
    list_display = [
        "ingredient", "preis", "einheit", "haendler",
        "kaufdatum", "beleg", "erfasst_von", "erfasst_am",
    ]
    list_filter = ["einheit", "haendler"]
    search_fields = ["ingredient__name", "haendler"]
    autocomplete_fields = ["ingredient"]
