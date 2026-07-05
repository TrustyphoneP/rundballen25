from django.conf import settings
from django.db import models


class FreizeitMitglied(models.Model):
    """
    Verbindet einen Nutzer (Betreuer) mit einer Freizeit (Camp).
    Wochenpläne und Aktionen leben weiterhin in apps.mobile_api,
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
    Aktionen können Gruppen zugeordnet werden. Die M2M-Beziehung liegt
    bewusst auf dieser Seite, damit apps.mobile_api unverändert bleibt.
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


class FreizeitZugang(models.Model):
    """
    Zugangscode pro Freizeit. Wer den Code kennt, kann sich selbst
    registrieren (Name und Passwort selbst wählen) und wird automatisch
    mit der Freizeit verbunden.
    """
    camp = models.OneToOneField(
        "camps.Camp",
        on_delete=models.CASCADE,
        related_name="mobil_zugang",
    )
    code = models.CharField(
        max_length=32,
        unique=True,
        verbose_name="Zugangscode",
    )
    aktiv = models.BooleanField(default=True, verbose_name="Registrierung offen")
    erstellt_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Freizeit-Zugangscode"
        verbose_name_plural = "Freizeit-Zugangscodes"

    def __str__(self):
        return f"{self.camp}: {self.code}"


class Checkliste(models.Model):
    """
    Checkliste einer Freizeit. Wird von Leitung/Admin angelegt,
    Betreuer haken die Punkte persönlich ab.
    """
    SICHTBARKEIT_CHOICES = [
        ("alle", "Alle"),
        ("supervisor", "Nur Betreuer"),
        ("kitchen", "Nur Küche"),
        ("leitung", "Nur Leitung"),
    ]

    camp = models.ForeignKey(
        "camps.Camp",
        on_delete=models.CASCADE,
        related_name="mobil_checklisten",
    )
    titel = models.CharField(max_length=200, verbose_name="Titel")
    beschreibung = models.TextField(blank=True, verbose_name="Beschreibung")
    sichtbar_fuer = models.CharField(
        max_length=20,
        choices=SICHTBARKEIT_CHOICES,
        default="alle",
        verbose_name="Sichtbar für",
    )
    erstellt_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["titel"]
        verbose_name = "Checkliste"
        verbose_name_plural = "Checklisten"

    def __str__(self):
        return f"{self.titel} ({self.camp})"

    def sichtbar_fuer_user(self, user):
        if user.is_leitung():
            return True
        if self.sichtbar_fuer == "alle":
            return True
        return user.role == self.sichtbar_fuer


class ChecklistenPunkt(models.Model):
    checkliste = models.ForeignKey(
        Checkliste,
        on_delete=models.CASCADE,
        related_name="punkte",
    )
    text = models.CharField(max_length=300, verbose_name="Punkt")
    reihenfolge = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["reihenfolge", "pk"]
        verbose_name = "Checklisten-Punkt"
        verbose_name_plural = "Checklisten-Punkte"

    def __str__(self):
        return self.text


class PunktErledigt(models.Model):
    """Persönlicher Haken eines Nutzers an einem Checklisten-Punkt."""
    punkt = models.ForeignKey(
        ChecklistenPunkt,
        on_delete=models.CASCADE,
        related_name="erledigungen",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="checklisten_haken",
    )
    erledigt_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["punkt", "user"]]
        verbose_name = "Erledigter Punkt"
        verbose_name_plural = "Erledigte Punkte"
