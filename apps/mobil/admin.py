from django.contrib import admin
from .models import FreizeitMitglied, Gruppe, FreizeitZugang, Checkliste, ChecklistenPunkt


@admin.register(FreizeitMitglied)
class FreizeitMitgliedAdmin(admin.ModelAdmin):
    list_display = ("user", "camp", "gruppe", "beigetreten_am")
    list_filter = ("camp", "gruppe")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    autocomplete_fields = ("user",)


@admin.register(Gruppe)
class GruppeAdmin(admin.ModelAdmin):
    list_display = ("name", "camp", "erstellt_am")
    list_filter = ("camp",)
    search_fields = ("name",)


@admin.register(FreizeitZugang)
class FreizeitZugangAdmin(admin.ModelAdmin):
    list_display = ("camp", "code", "aktiv", "erstellt_am")
    list_filter = ("aktiv",)


class ChecklistenPunktInline(admin.TabularInline):
    model = ChecklistenPunkt
    extra = 1

@admin.register(Checkliste)
class ChecklisteAdmin(admin.ModelAdmin):
    list_display = ("titel", "camp", "sichtbar_fuer", "erstellt_am")
    list_filter = ("camp", "sichtbar_fuer")
    inlines = [ChecklistenPunktInline]
