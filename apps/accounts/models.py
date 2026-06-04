from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Erweiterter Nutzer: Admin, Betreuer, Küche"""

    class Role(models.TextChoices):
        ADMIN      = "admin",      "Leitung / Admin"
        SUPERVISOR = "supervisor", "Betreuer"
        KITCHEN    = "kitchen",    "Küche"
        STAFF      = "staff",      "Mitarbeiter"

    role                 = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)
    phone                = models.CharField(max_length=30, blank=True)
    bio                  = models.TextField(blank=True)
    must_change_password = models.BooleanField(
        default=False,
        verbose_name="Muss Passwort ändern",
        help_text="Benutzer wird nach dem Login zur Passwortänderung aufgefordert.",
    )

    class Meta:
        verbose_name = "Benutzer"
        verbose_name_plural = "Benutzer"

    def is_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"