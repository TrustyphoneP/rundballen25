"""
Datenmodelle fuer das Rundballen-Raetsel.

Spielablauf:
  Phase 1 bis 4, je bestehend aus:
    - Bild-Raetsel auf /riddle          (Loesung = Jahreszahl)
    - Text-Raetsel auf /<jahreszahl>    (Loesung durch Spielleiter freigeschaltet)

RiddleStage: ein Bild + zugehoeriges Textfeld, plus die Loesung (Jahreszahl)
RiddleState: singleton, haelt den aktuellen Spielstand
PlayerBan:   IP-basierte Sperre nach falscher Eingabe
"""

import random
from django.db import models
from django.utils import timezone
from datetime import timedelta


class RiddleStage(models.Model):
    """
    Ein Raetsel-Schritt: Bild + Jahreszahl-Loesung + Textinhalt der naechsten Seite.
    order=1..4
    """

    order = models.PositiveSmallIntegerField(
        unique=True,
        verbose_name="Reihenfolge (1-4)",
    )
    # --- Bild-Raetsel ---
    image = models.ImageField(
        upload_to="riddle/stages/",
        verbose_name="Raetsel-Bild",
        help_text="Wird auf /riddle angezeigt.",
    )
    solution_year = models.PositiveIntegerField(
        verbose_name="Loesung (Jahreszahl)",
        help_text="z.B. 2014 -- URL /2014 fuehrt zum Textinhalt.",
    )
    hint = models.TextField(
        blank=True,
        default="",
        verbose_name="Hinweis (optional)",
        help_text="Wird unterhalb des Bildes eingeblendet, wenn gesetzt.",
    )
    # --- Text-Raetsel auf /<jahreszahl> ---
    text_content = models.TextField(
        verbose_name="Textinhalt der Jahreszahl-Seite",
        help_text="HTML erlaubt. Wird auf /<solution_year> angezeigt.",
    )
    text_solution = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="Loesung des Textraetsels",
        help_text="Antwort, die Spieler unter dem Textraetsel eingeben muessen. "
        "Vergleich ist unabhaengig von Gross-/Kleinschreibung.",
    )
    text_response = models.TextField(
        blank=True,
        default="",
        verbose_name="Antwortstring bei korrekter Loesung",
        help_text="Wird angezeigt, wenn die Loesung des Textraetsels korrekt eingegeben wurde.",
    )

    class Meta:
        ordering = ["order"]
        verbose_name = "Raetsel-Stufe"
        verbose_name_plural = "Raetsel-Stufen"

    def __str__(self):
        return f"Stufe {self.order} (Loesung: {self.solution_year})"

    def check_text_solution(self, entered: str) -> bool:
        """
        Vergleicht die eingegebene Textantwort mit der hinterlegten Loesung.
        Unabhaengig von Gross-/Kleinschreibung, fuehrende/folgende Leerzeichen
        und mehrfachen Leerzeichen dazwischen.
        """
        if not self.text_solution:
            return False
        normalize = lambda s: " ".join(s.strip().casefold().split())
        return normalize(entered) == normalize(self.text_solution)


class RiddleState(models.Model):
    """
    Singleton: Spielstand des Raetsels.
    current_stage=0  -> Spiel noch nicht gestartet (Anleitung sichtbar)
    current_stage=1  -> Erstes Bild aktiv
    current_stage=5  -> Spiel beendet
    """

    current_stage = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Aktuelle Stufe (0=nicht gestartet, 1-4=aktiv, 5=Ende)",
    )
    started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Spielstand"
        verbose_name_plural = "Spielstand"

    def __str__(self):
        return f"Spielstand: Stufe {self.current_stage}"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def current_riddle(self):
        """Gibt das aktive RiddleStage-Objekt zurueck oder None."""
        if self.current_stage == 0 or self.current_stage > 4:
            return None
        return RiddleStage.objects.filter(order=self.current_stage).first()

    def is_active(self):
        return 1 <= self.current_stage <= 4

    def is_finished(self):
        return self.current_stage == 5


class PlayerBan(models.Model):
    """
    IP-Sperre nach falscher Jahreszahl.
    Dauer: zufaellig 4-8 Stunden.
    """

    ip_address = models.GenericIPAddressField(verbose_name="IP-Adresse")
    banned_until = models.DateTimeField(verbose_name="Gesperrt bis")
    wrong_year = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Eingegebene Jahreszahl"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sperre"
        verbose_name_plural = "Sperren"
        indexes = [models.Index(fields=["ip_address", "banned_until"])]

    def __str__(self):
        return f"{self.ip_address} gesperrt bis {self.banned_until:%d.%m.%Y %H:%M}"

    @classmethod
    def is_banned(cls, ip):
        return cls.objects.filter(
            ip_address=ip, banned_until__gt=timezone.now()
        ).exists()

    @classmethod
    def get_ban(cls, ip):
        return (
            cls.objects.filter(ip_address=ip, banned_until__gt=timezone.now())
            .order_by("-banned_until")
            .first()
        )

    @classmethod
    def create_ban(cls, ip, wrong_year=None):
        hours = random.uniform(4, 8)
        banned_until = timezone.now() + timedelta(hours=hours)
        # Vorhandene Sperre verlaengern wenn bereits gesperrt
        existing = cls.get_ban(ip)
        if existing:
            existing.banned_until = max(existing.banned_until, banned_until)
            existing.save(update_fields=["banned_until"])
            return existing
        return cls.objects.create(
            ip_address=ip, banned_until=banned_until, wrong_year=wrong_year
        )
