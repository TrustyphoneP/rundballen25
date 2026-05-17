"""
voting – Betreuer-Abstimmung (1x jährlich)

Duplikat-Prävention via Session-Cookie.
Kein Token-Verteilen nötig — jeder öffnet denselben Link.
"""
import secrets
from django.db import models
from django.utils import timezone


class Poll(models.Model):
    class Status(models.TextChoices):
        DRAFT  = "draft",  "Entwurf"
        OPEN   = "open",   "Offen"
        CLOSED = "closed", "Abgeschlossen"

    camp        = models.ForeignKey("camps.Camp", on_delete=models.CASCADE, related_name="polls")
    title       = models.CharField(max_length=200, verbose_name="Titel")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    status      = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    min_votes   = models.PositiveSmallIntegerField(default=0, verbose_name="Mindestauswahl")
    max_votes   = models.PositiveSmallIntegerField(default=6, verbose_name="Maximalauswahl")
    created_by  = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    closed_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Abstimmung"
        verbose_name_plural = "Abstimmungen"

    def __str__(self):
        return f"{self.title} [{self.get_status_display()}]"


class VoteRecipe(models.Model):
    """Abstimmbares Gericht — eigene Tabelle, optional mit Rezept-DB verknüpft."""
    poll        = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="vote_recipes")
    recipe      = models.ForeignKey(
        "recipes.Recipe", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="vote_entries",
    )
    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_vegan    = models.BooleanField(default=False)
    is_active   = models.BooleanField(default=True)
    sort_order  = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Abstimm-Gericht"
        verbose_name_plural = "Abstimm-Gerichte"

    def vote_count(self):
        return self.votes.count()

    def __str__(self):
        return f"{self.name} ({self.poll})"


class Vote(models.Model):
    """
    Eine Stimmabgabe — identifiziert via Session-Key.
    Kein Token nötig: jeder Browser kann einmal abstimmen.
    """
    vote_recipe = models.ForeignKey(VoteRecipe, on_delete=models.CASCADE, related_name="votes")
    session_key = models.CharField(max_length=40, verbose_name="Session")
    voted_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["vote_recipe", "session_key"]]
        verbose_name = "Stimme"
        verbose_name_plural = "Stimmen"

    def __str__(self):
        return f"{self.vote_recipe.name} – {self.session_key[:8]}…"
