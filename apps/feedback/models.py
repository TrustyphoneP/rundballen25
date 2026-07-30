"""
feedback – Anonymes Teilnehmer-Feedback

Teilis bewerten die Hauptgerichte aus dem Wochenplan anonym mit 1-10
und koennen pro Gericht sowie allgemein Freitext-Feedback geben.
Die Bewertungen werden clientseitig zwischengespeichert und in einem
Rutsch als FeedbackSubmission mit zugehoerigen MealRatings gespeichert.
"""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


# Einzige Quelle fuer die Erlaeuterungstexte des Schiebereglers.
# Wird in der Bewertungsseite (live unter dem Regler) und in der
# Auswertung verwendet.
RATING_TEXTS = {
    1:  "\"Würde ich dem Kettensägentypen nicht in den Garten werfen\"",
    2:  "\"Sonst noch jemand was vom Kurt?\"",
    3:  "\"Probier doch wenigstens mal\"",
    4:  "\"Es gibt Abends kein Nutella!\"",
    5:  "\"André, war total lecker! Was ist heute Betreueressen?\"",
    6:  "\"Sind alle satt geworden\"",
    7:  "\"Teili XYZ isst das sonst gar nicht!\"",
    8:  "\"Nehme extra zwei Laktase\"",
    9:  "\"Absoluter Freizeitklassiker\"",
    10: "\"Mache nur wieder mit, wenn es dieses Gericht gibt.\"",
}


class FeedbackSubmission(models.Model):
    """Eine anonyme Feedbackabgabe (allgemeines Feedback + Gerichtbewertungen)"""

    camp = models.ForeignKey(
        "camps.Camp", on_delete=models.CASCADE,
        related_name="feedback_submissions", verbose_name="Freizeit",
    )
    general_comment = models.TextField(
        blank=True, verbose_name="Allgemeines Feedback",
    )
    # Kein User-FK, vollstaendig anonym. Der Session-Hash dient nur dazu,
    # Mehrfachabgaben grob erkennen zu koennen.
    session_hash = models.CharField(max_length=64, blank=True, editable=False)
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="Abgegeben am")

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = "Feedbackabgabe"
        verbose_name_plural = "Feedbackabgaben"

    def __str__(self):
        return f"Feedback {self.submitted_at:%d.%m.%Y %H:%M} ({self.camp})"


class MealRating(models.Model):
    """Bewertung eines Hauptgerichts (1-10) innerhalb einer Feedbackabgabe"""

    submission = models.ForeignKey(
        FeedbackSubmission, on_delete=models.CASCADE,
        related_name="ratings", verbose_name="Feedbackabgabe",
    )
    day = models.ForeignKey(
        "camps.CampDay", on_delete=models.CASCADE,
        related_name="meal_ratings", verbose_name="Tag",
    )
    recipe = models.ForeignKey(
        "recipes.Recipe", on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Hauptgericht",
    )
    # Snapshot des Gerichtnamens zum Zeitpunkt der Bewertung,
    # falls das Rezept spaeter geloescht oder umbenannt wird.
    recipe_name = models.CharField(max_length=200, blank=True, verbose_name="Gericht")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name="Bewertung (1-10)",
    )
    comment = models.TextField(blank=True, verbose_name="Feedback zum Gericht")

    class Meta:
        ordering = ["day__date"]
        verbose_name = "Gerichtbewertung"
        verbose_name_plural = "Gerichtbewertungen"

    @property
    def rating_text(self):
        return RATING_TEXTS.get(self.rating, "")

    def __str__(self):
        return f"{self.recipe_name}: {self.rating}/10"
