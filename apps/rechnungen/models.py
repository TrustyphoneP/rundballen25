"""
rechnungen – Rechnungsführung

Belege (Kassenbons und A4-Rechnungen) werden als Handyfoto hochgeladen,
automatisch analysiert und in Positionen mit Grundpreisen zerlegt.
Die Grundpreise können in die Zutaten-Stammdaten (Ingredient.price)
übernommen werden und speisen so die Kostenkalkulation für Rezepte,
Lieferungen und ganze Freizeiten.

Jeder Beleg gehört zu einer Kostenkategorie (Abendessen, SKF-Alternativen,
Betreueressen usw.), sodass sich die Ist-Ausgaben je Kategorie auswerten
lassen. Kategorien sind Stammdaten und können erweitert werden.

Die Preishistorie hält fest, welcher Preis wann von welchem Beleg kam,
damit Preisentwicklungen nachvollziehbar bleiben.
"""
from decimal import Decimal

from django.db import models

from apps.recipes.models import Ingredient


class Kostenkategorie(models.Model):
    """
    Kostenpunkt für die Zuordnung von Belegen (z.B. Abendessen,
    Frühstück/Mittagessen, SKF-Alternativen, Betreueressen, Allgemein).
    Über die Kategoriekosten-Seite erweiterbar.
    """

    name = models.CharField(max_length=100, unique=True, verbose_name="Name")
    sortierung = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sortierung", "name"]
        verbose_name = "Kostenkategorie"
        verbose_name_plural = "Kostenkategorien"

    def __str__(self):
        return self.name


class Beleg(models.Model):
    """Ein hochgeladener Kassenbon oder eine A4-Rechnung als Foto."""

    class Status(models.TextChoices):
        NEU        = "neu",        "Neu"
        ANALYSIERT = "analysiert", "Analysiert"
        GEPRUEFT   = "geprueft",   "Geprüft"
        FEHLER     = "fehler",     "Fehler bei Analyse"

    camp = models.ForeignKey(
        "camps.Camp", on_delete=models.CASCADE,
        related_name="belege", verbose_name="Freizeit",
    )
    kategorie = models.ForeignKey(
        Kostenkategorie, on_delete=models.PROTECT,
        null=True, blank=True, related_name="belege",
        verbose_name="Kostenkategorie",
    )
    nur_preiserfassung = models.BooleanField(
        default=False,
        verbose_name="Nicht für aktuelle Freizeit",
        help_text="Nur zur Preiserfassung (z.B. alte Belege) -- zählt "
                  "nicht zu den Ist-Kosten der Freizeit.",
    )
    image = models.ImageField(
        upload_to="belege/%Y/%m/",
        verbose_name="Belegfoto",
        help_text="Handyfoto des Kassenbons oder der A4-Rechnung",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEU,
    )

    # Ergebnis der Analyse (Kopf des Belegs)
    haendler = models.CharField(
        max_length=200, blank=True, verbose_name="Händler / Laden",
    )
    kaufdatum = models.DateField(
        null=True, blank=True, verbose_name="Kaufdatum",
    )
    gesamtbetrag = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Gesamtbetrag (€)",
    )

    # Rohdaten & Fehlerdiagnose -- bewusst gespeichert, damit
    # Analyse-Probleme nachträglich untersucht werden können, statt
    # sie stillschweigend zu verschlucken.
    analyse_rohdaten = models.JSONField(
        null=True, blank=True, verbose_name="Analyse-Rohdaten (JSON)",
    )
    analyse_fehler = models.TextField(
        blank=True, verbose_name="Fehlermeldung der Analyse",
    )
    analysiert_am = models.DateTimeField(null=True, blank=True)

    hochgeladen_von = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="belege_hochgeladen",
    )
    hochgeladen_am = models.DateTimeField(auto_now_add=True)
    notiz = models.CharField(max_length=300, blank=True, verbose_name="Notiz")

    class Meta:
        ordering = ["-hochgeladen_am"]
        verbose_name = "Beleg"
        verbose_name_plural = "Belege"

    @property
    def positionen_summe(self):
        """Summe aller Positions-Gesamtpreise (zum Abgleich mit gesamtbetrag)."""
        total = Decimal("0")
        for pos in self.positionen.all():
            if pos.gesamtpreis is not None:
                total += pos.gesamtpreis
        return total

    def __str__(self):
        teile = [self.haendler or "Beleg"]
        if self.kaufdatum:
            teile.append(self.kaufdatum.strftime("%d.%m.%Y"))
        if self.gesamtbetrag is not None:
            teile.append(f"{self.gesamtbetrag} €")
        return " – ".join(teile)


class BelegPosition(models.Model):
    """
    Eine Zeile eines Belegs: Artikel, Menge, Gesamtpreis und der daraus
    ermittelte Grundpreis (z.B. €/kg). Kann einer Zutat zugeordnet und
    deren Preis-Stammdatum übernommen werden.
    """

    class GrundpreisEinheit(models.TextChoices):
        KG    = "kg",  "kg"
        L     = "l",   "l"
        STK   = "Stk", "Stk"
        PCK   = "Pck", "Pck"

    beleg = models.ForeignKey(
        Beleg, on_delete=models.CASCADE, related_name="positionen",
    )
    sortierung = models.PositiveIntegerField(default=0)

    text_original = models.CharField(
        max_length=300, blank=True,
        verbose_name="Bontext (wie gedruckt)",
    )
    artikel_name = models.CharField(
        max_length=200, verbose_name="Artikel",
    )

    # Gesamtmenge der Zeile (z.B. 2 Packungen à 400 g -> 800 g)
    menge = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name="Menge",
    )
    einheit = models.CharField(
        max_length=10, choices=Ingredient.Unit.choices, blank=True,
        verbose_name="Einheit",
    )

    gesamtpreis = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Zeilensumme (€)",
    )
    grundpreis = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        verbose_name="Grundpreis (€)",
        help_text="Preis je Grundpreis-Einheit, z.B. 8,73 für 8,73 €/kg",
    )
    grundpreis_einheit = models.CharField(
        max_length=10, choices=GrundpreisEinheit.choices, blank=True,
        verbose_name="Grundpreis-Einheit",
    )

    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="beleg_positionen",
        verbose_name="Zutat",
    )

    hinweis = models.CharField(
        max_length=200, blank=True, verbose_name="Hinweis",
        help_text="z.B. Pfand, Rabatt, unsichere Erkennung",
    )

    ist_uebernommen = models.BooleanField(
        default=False, verbose_name="Preis übernommen",
    )
    uebernommen_am = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["beleg", "sortierung", "pk"]
        verbose_name = "Beleg-Position"
        verbose_name_plural = "Beleg-Positionen"

    def __str__(self):
        return f"{self.artikel_name} ({self.gesamtpreis} €)"


class Preishistorie(models.Model):
    """
    Historisierter Zutatenpreis: jede Preisübernahme aus einem Beleg
    (und jede manuelle Erfassung) legt hier einen Eintrag an. So bleibt
    nachvollziehbar, woher Ingredient.price stammt und wie sich Preise
    über Läden und Jahre entwickeln.
    """

    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.CASCADE, related_name="preishistorie",
        verbose_name="Zutat",
    )
    preis = models.DecimalField(
        max_digits=10, decimal_places=4, verbose_name="Preis (€)",
    )
    einheit = models.CharField(
        max_length=10, choices=Ingredient.Unit.choices,
        verbose_name="Preis-Einheit",
    )
    haendler = models.CharField(max_length=200, blank=True, verbose_name="Händler")
    kaufdatum = models.DateField(null=True, blank=True, verbose_name="Kaufdatum")
    beleg = models.ForeignKey(
        Beleg, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="preiseintraege",
    )
    erfasst_von = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
    )
    erfasst_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-erfasst_am"]
        verbose_name = "Preishistorie-Eintrag"
        verbose_name_plural = "Preishistorie"

    def __str__(self):
        return f"{self.ingredient.name}: {self.preis} €/{self.einheit}"
