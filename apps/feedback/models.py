"""
feedback – Anonymes Teilnehmer-Feedback

Teilnehmer können per QR-Code anonym Feedback zu Mahlzeiten und allgemeinen
Themen abgeben. Betreuer sehen aggregierte Ergebnisse im Dashboard.
"""
from django.db import models
import secrets


class FeedbackForm(models.Model):
    """Ein Feedbackformular für einen Camp-Tag oder die ganze Freizeit"""

    camp       = models.ForeignKey("camps.Camp", on_delete=models.CASCADE, related_name="feedback_forms")
    day        = models.ForeignKey("camps.CampDay", on_delete=models.SET_NULL, null=True, blank=True)
    title      = models.CharField(max_length=200)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Feedbackformular"
        verbose_name_plural = "Feedbackformulare"

    def __str__(self):
        return self.title


class FeedbackEntry(models.Model):
    """Eine einzelne anonyme Feedbackabgabe"""

    class Rating(models.IntegerChoices):
        VERY_BAD  = 1, "😞 Sehr schlecht"
        BAD       = 2, "😕 Schlecht"
        OKAY      = 3, "😐 Okay"
        GOOD      = 4, "🙂 Gut"
        VERY_GOOD = 5, "😄 Sehr gut"

    form      = models.ForeignKey(FeedbackForm, on_delete=models.CASCADE, related_name="entries")
    warm_meal = models.ForeignKey("meals.WarmMeal", on_delete=models.SET_NULL, null=True, blank=True)
    rating    = models.PositiveSmallIntegerField(choices=Rating.choices, null=True, blank=True)
    comment   = models.TextField(blank=True, verbose_name="Kommentar (anonym)")
    submitted_at = models.DateTimeField(auto_now_add=True)
    # Kein User-FK → vollständig anonym
    session_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        verbose_name = "Feedbackeintrag"
        verbose_name_plural = "Feedbackeinträge"
