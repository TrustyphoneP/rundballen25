"""
voting – Betreuer-Abstimmung (1x jährlich)

Ablauf:
  1. Admin legt eine Poll an und wählt das Camp
  2. Rezepte aus der DB werden automatisch als VoteRecipe importiert
     (können auch manuell hinzugefügt / ausgeblendet werden)
  3. Admin generiert VoteTokens (einen pro Betreuer) und verteilt die Links
  4. Betreuer öffnen ihren Link und wählen 0–6 Gerichte
  5. Admin sieht Ergebnisse in Echtzeit

Duplikat-Prävention: jeder Token kann nur einmal verwendet werden.
Die Identität des Wählers ist nicht rekonstruierbar (kein User-FK an Vote).
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

    def token_count(self):
        return self.tokens.count()

    def used_token_count(self):
        return self.tokens.filter(used=True).count()

    def results(self):
        """Gibt VoteRecipes sortiert nach Stimmenanzahl zurück."""
        return self.vote_recipes.annotate(
            vote_count=models.Count("votes")
        ).order_by("-vote_count")

    def __str__(self):
        return f"{self.title} [{self.get_status_display()}]"


class VoteRecipe(models.Model):
    """
    Eigene Tabelle für abstimmbare Gerichte.
    Wird beim Poll-Erstellen automatisch aus recipes.Recipe befüllt,
    kann aber auch manuell gepflegt werden (z.B. Rezepte ohne DB-Eintrag).
    """
    poll        = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="vote_recipes")
    # Optionale Verknüpfung zur Rezept-DB — kann None sein für manuelle Einträge
    recipe      = models.ForeignKey(
        "recipes.Recipe", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="vote_entries",
        verbose_name="Rezept (DB)",
    )
    name        = models.CharField(max_length=200, verbose_name="Gerichtsname")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    is_vegan    = models.BooleanField(default=False, verbose_name="Vegan")
    is_active   = models.BooleanField(default=True, verbose_name="Zur Abstimmung freigegeben")
    sort_order  = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Abstimm-Gericht"
        verbose_name_plural = "Abstimm-Gerichte"

    def vote_count(self):
        return self.votes.count()

    def __str__(self):
        return f"{self.name} ({self.poll})"


class VoteToken(models.Model):
    """Ein Einmal-Link pro Betreuer. Token = URL-safe-String."""
    poll       = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="tokens")
    token      = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
    label      = models.CharField(max_length=100, blank=True,
                                  help_text="Nur intern sichtbar, z.B. Name des Betreuers")
    used       = models.BooleanField(default=False)
    used_at    = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["label", "created_at"]
        verbose_name = "Abstimmungstoken"
        verbose_name_plural = "Abstimmungstokens"

    def vote_url(self, request=None):
        from django.urls import reverse
        path = reverse("voting:vote", kwargs={"token": self.token})
        if request:
            return request.build_absolute_uri(path)
        return path

    def __str__(self):
        status = "benutzt" if self.used else "offen"
        label  = f" ({self.label})" if self.label else ""
        return f"Token {self.token[:8]}…{label} – {status}"


class Vote(models.Model):
    """
    Eine Stimmabgabe: ein Token wählt 0–6 Gerichte.
    Jedes gewählte Gericht = ein Vote-Eintrag.
    token ist unique → verhindert doppeltes Abstimmen.
    """
    token      = models.ForeignKey(
        VoteToken, on_delete=models.CASCADE, related_name="votes"
    )
    vote_recipe = models.ForeignKey(
        VoteRecipe, on_delete=models.CASCADE, related_name="votes"
    )
    voted_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ein Token kann jedes Gericht nur einmal wählen
        unique_together = [["token", "vote_recipe"]]
        verbose_name = "Stimme"
        verbose_name_plural = "Stimmen"

    def __str__(self):
        return f"{self.token} → {self.vote_recipe.name}"
