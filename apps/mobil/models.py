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
    gruppe = models.ForeignKey(
        "mobil.Gruppe",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mitglieder",
        verbose_name="Gruppe",
    )
    beigetreten_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["user", "camp"]]
        verbose_name = "Freizeit-Mitgliedschaft"
        verbose_name_plural = "Freizeit-Mitgliedschaften"
        ordering = ["-beigetreten_am"]

    def __str__(self):
        return f"{self.user.username} → {self.camp}"


class Gruppe(models.Model):
    """
    Betreuergruppe innerhalb einer Freizeit.
    Aktionen koennen Gruppen zugeordnet werden. Die M2M-Beziehung liegt
    bewusst auf dieser Seite, damit apps.mobile_api unveraendert bleibt.
    """
    camp = models.ForeignKey(
        "camps.Camp",
        on_delete=models.CASCADE,
        related_name="mobil_gruppen",
    )
    name = models.CharField(max_length=100, verbose_name="Gruppenname")
    aktionen = models.ManyToManyField(
        "mobile_api.Aktion",
        blank=True,
        related_name="gruppen",
        verbose_name="Aktionen",
    )
    erstellt_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["camp", "name"]]
        ordering = ["name"]
        verbose_name = "Gruppe"
        verbose_name_plural = "Gruppen"

    def __str__(self):
        return f"{self.name} ({self.camp})"
