from django.contrib import admin
from .models import FreizeitMitglied


@admin.register(FreizeitMitglied)
class FreizeitMitgliedAdmin(admin.ModelAdmin):
    list_display = ("user", "camp", "beigetreten_am")
    list_filter = ("camp",)
    search_fields = ("user__username", "user__first_name", "user__last_name")
    autocomplete_fields = ("user",)
