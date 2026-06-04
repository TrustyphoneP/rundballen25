from django.db import models
from django.conf import settings
from django.urls import reverse
from datetime import date


class Camp(models.Model):
    name              = models.CharField(max_length=200, verbose_name="Bezeichnung")
    description       = models.TextField(blank=True)
    start_date        = models.DateField(verbose_name="Beginn")
    end_date          = models.DateField(verbose_name="Ende")
    location          = models.CharField(max_length=200, blank=True, verbose_name="Ort")
    participant_count = models.PositiveIntegerField(default=100, verbose_name="Teilnehmeranzahl (geplant)")
    supervisor_count  = models.PositiveIntegerField(default=30,  verbose_name="Betreueranzahl")
    created_by        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="camps_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active  = models.BooleanField(default=True)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Freizeit"
        verbose_name_plural = "Freizeiten"

    @property
    def total_persons(self):
        return self.participant_count + self.supervisor_count

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1

    def get_absolute_url(self):
        return reverse("camps:detail", kwargs={"pk": self.pk})

    def __str__(self):
        return f"{self.name} ({self.start_date.year})"


class CampDay(models.Model):
    camp                 = models.ForeignKey(Camp, on_delete=models.CASCADE, related_name="days")
    date                 = models.DateField(verbose_name="Datum")
    note                 = models.CharField(max_length=300, blank=True)
    participants_present = models.PositiveIntegerField(null=True, blank=True, verbose_name="Anwesende TN")
    supervisors_present  = models.PositiveIntegerField(null=True, blank=True, verbose_name="Anwesende Betreuer")

    class Meta:
        ordering = ["date"]
        unique_together = [["camp", "date"]]
        verbose_name = "Freizeit-Tag"
        verbose_name_plural = "Freizeit-Tage"

    @property
    def persons_present(self):
        p = self.participants_present if self.participants_present is not None else self.camp.participant_count
        s = self.supervisors_present  if self.supervisors_present  is not None else self.camp.supervisor_count
        return p + s

    def __str__(self):
        return f"{self.camp} – {self.date}"


class Participant(models.Model):
    """
    Teilnehmer oder Betreuer einer Freizeit.
    Unverträglichkeiten werden zentral erfasst und
    fliessen in Mahlzeiten- und Einkaufsplanung ein.
    """

    class PersonType(models.TextChoices):
        PARTICIPANT = "participant", "Teilnehmer"
        SUPERVISOR  = "supervisor",  "Betreuer"

    camp          = models.ForeignKey(Camp, on_delete=models.CASCADE, related_name="participants")
    first_name    = models.CharField(max_length=100, verbose_name="Vorname")
    last_name     = models.CharField(max_length=100, verbose_name="Nachname")
    person_type   = models.CharField(
        max_length=20, choices=PersonType.choices,
        default=PersonType.PARTICIPANT, verbose_name="Typ"
    )
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Geburtsdatum")
    notes         = models.TextField(blank=True, verbose_name="Sonstige Hinweise")

    # Diaet-Flags
    is_vegan      = models.BooleanField(default=False, verbose_name="Vegan")
    is_vegetarian = models.BooleanField(default=False, verbose_name="Vegetarisch")
    is_halal      = models.BooleanField(default=False, verbose_name="Halal")
    is_kosher     = models.BooleanField(default=False, verbose_name="Koscher")

    intolerances = models.ManyToManyField(
        "recipes.Allergen",
        blank=True,
        related_name="participants",
        verbose_name="Allergien / Unverträglichkeiten",
    )
    intolerance_notes = models.TextField(
        blank=True,
        verbose_name="Zusatzhinweise Unverträglichkeiten",
        help_text="Für alles, was nicht in die Checkboxen passt",
    )

    absent_dates = models.ManyToManyField(
        CampDay, blank=True, related_name="absences",
        verbose_name="Abwesend an folgenden Tagen"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = "Teilnehmer / Betreuer"
        verbose_name_plural = "Teilnehmer / Betreuer"

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def age_at_camp(self):
        """Alter zum Zeitpunkt des Freizeit-Starts."""
        if not self.date_of_birth:
            return None
        ref = self.camp.start_date
        years = ref.year - self.date_of_birth.year
        # Noch kein Geburtstag in diesem Jahr?
        if (ref.month, ref.day) < (self.date_of_birth.month, self.date_of_birth.day):
            years -= 1
        return years

    def age_today(self):
        """Aktuelles Alter (heute)."""
        if not self.date_of_birth:
            return None
        today = date.today()
        years = today.year - self.date_of_birth.year
        if (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day):
            years -= 1
        return years

    def diet_flags(self):
        flags = []
        if self.is_vegan:      flags.append("Vegan")
        if self.is_vegetarian: flags.append("Vegetarisch")
        if self.is_halal:      flags.append("Halal")
        if self.is_kosher:     flags.append("Koscher")
        return flags

    def has_restrictions(self):
        return (self.is_vegan or self.is_vegetarian or self.is_halal
                or self.is_kosher or self.intolerances.exists())

    def get_absolute_url(self):
        return reverse("camps:participant_detail", kwargs={"pk": self.pk})

    def __str__(self):
        age = self.age_at_camp()
        age_str = f", {age} J." if age is not None else ""
        return f"{self.full_name()} ({self.get_person_type_display()}{age_str}, {self.camp})"
