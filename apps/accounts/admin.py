from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django import forms
from .models import User


class CustomUserCreationForm(UserCreationForm):
    """Erweitertes Formular: Rolle + Passwort-Änderungspflicht direkt beim Anlegen."""
    must_change_password = forms.BooleanField(
        required=False,
        initial=True,
        label="Muss Passwort ändern",
        help_text="Benutzer wird nach erstem Login zur Passwortänderung aufgefordert.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "role")


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display  = ("username", "get_full_name", "email", "role", "must_change_password", "is_active", "is_superuser")
    list_filter   = ("role", "is_active", "is_staff", "is_superuser", "must_change_password")
    search_fields = ("username", "first_name", "last_name", "email")
    ordering      = ("username",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Persönliche Daten", {"fields": ("first_name", "last_name", "email", "phone", "bio")}),
        ("Rolle & Zugang", {"fields": ("role", "must_change_password", "is_active", "is_staff", "is_superuser")}),
        ("Gruppen & Rechte", {"classes": ("collapse",), "fields": ("groups", "user_permissions")}),
        ("Aktivität", {"classes": ("collapse",), "fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "first_name", "last_name", "role",
                       "password1", "password2", "must_change_password"),
        }),
    )
