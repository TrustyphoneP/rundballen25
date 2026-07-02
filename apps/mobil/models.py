from django.conf import settings
from django.db import models


class FreizeitMitglied(models.Model):
    """
    Verbindet einen Nutzer (Betreuer) mit einer Freizeit (Camp).
    Wochenplaene und Aktionen leben weiterhin in apps.mobile_api,
    damit Webapp und React-Native-App dieselben Daten nutzen.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="freizeit_mitgliedschaften",
    )
    camp = models.ForeignKey(
        "camps.Camp",
        on_delete=models.CASCADE,
        related_name="mobil_mitglieder",
    )
    beigetreten_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["user", "camp"]]
        verbose_name = "Freizeit-Mitgliedschaft"
        verbose_name_plural = "Freizeit-Mitgliedschaften"
        ordering = ["-beigetreten_am"]

    def __str__(self):
        return f"{self.user.username} → {self.camp}"
