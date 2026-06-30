from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()


class MobileUserProfile(models.Model):
    """
    Erweiterung des bestehenden Django-Users um den force_password_reset-Flag.
    Wird per OneToOne an den Standard-User gehaengt, damit kein bestehender Code
    angepasst werden muss.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="mobile_profile"
    )
    force_password_reset = models.BooleanField(
        default=True,
        help_text="Wenn True, muss der Nutzer beim naechsten Login ein neues Passwort setzen.",
    )

    class Meta:
        verbose_name = "Mobile Nutzerprofil"
        verbose_name_plural = "Mobile Nutzerprofile"

    def __str__(self):
        return f"Profil für {self.user.username}"


class Wochenplan(models.Model):
    """
    Wochenplan für eine Freizeit (Camp).
    Verknüpft sich mit dem bestehenden Camp-Model über camp_id.
    """
    camp_id = models.IntegerField(
        verbose_name="Camp-ID",
        help_text="ID des Camps aus der bestehenden Camp-Tabelle",
    )
    titel = models.CharField(max_length=200, verbose_name="Titel")
    erstellt_am = models.DateTimeField(auto_now_add=True)
    geaendert_am = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wochenplan"
        verbose_name_plural = "Wochenplaene"
        ordering = ["camp_id", "titel"]

    def __str__(self):
        return f"{self.titel} (Camp {self.camp_id})"


WOCHENTAG_CHOICES = [
    (0, "Montag"),
    (1, "Dienstag"),
    (2, "Mittwoch"),
    (3, "Donnerstag"),
    (4, "Freitag"),
    (5, "Samstag"),
    (6, "Sonntag"),
]

KATEGORIE_CHOICES = [
    ("programm", "Programm"),
    ("mahlzeit", "Mahlzeit"),
    ("schlaf", "Schlafen/Ruhe"),
    ("hygiene", "Hygiene"),
    ("transport", "Transport"),
    ("frei", "Freie Zeit"),
    ("sonstiges", "Sonstiges"),
]


class Aktion(models.Model):
    """
    Einzelner Zeitblock im Wochenplan.
    Beispiel: Montag 12:00-14:00 Workshop
    """
    wochenplan = models.ForeignKey(
        Wochenplan, on_delete=models.CASCADE, related_name="aktionen"
    )
    wochentag = models.IntegerField(choices=WOCHENTAG_CHOICES)
    titel = models.CharField(max_length=200)
    beschreibung = models.TextField(blank=True)
    kategorie = models.CharField(
        max_length=20, choices=KATEGORIE_CHOICES, default="programm"
    )
    beginn_stunde = models.IntegerField(help_text="0-23")
    beginn_minute = models.IntegerField(default=0, help_text="0 oder 30")
    ende_stunde = models.IntegerField(help_text="0-23")
    ende_minute = models.IntegerField(default=0, help_text="0 oder 30")
    ort = models.CharField(max_length=200, blank=True)
    # Verantwortliche Betreuer (User-IDs, kommasepariert als einfache Loesung)
    verantwortlich = models.ManyToManyField(
        User, blank=True, related_name="zugeordnete_aktionen"
    )

    class Meta:
        verbose_name = "Aktion"
        verbose_name_plural = "Aktionen"
        ordering = ["wochentag", "beginn_stunde", "beginn_minute"]

    def __str__(self):
        tag = dict(WOCHENTAG_CHOICES).get(self.wochentag, "?")
        return f"{tag} {self.beginn_stunde:02d}:{self.beginn_minute:02d} {self.titel}"
