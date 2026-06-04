from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ("recipes", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Camp",
            fields=[
                ("id",                models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name",              models.CharField(max_length=200, verbose_name="Bezeichnung")),
                ("description",       models.TextField(blank=True)),
                ("start_date",        models.DateField(verbose_name="Beginn")),
                ("end_date",          models.DateField(verbose_name="Ende")),
                ("location",          models.CharField(blank=True, max_length=200, verbose_name="Ort")),
                ("participant_count", models.PositiveIntegerField(default=100, verbose_name="Teilnehmeranzahl (geplant)")),
                ("supervisor_count",  models.PositiveIntegerField(default=30, verbose_name="Betreueranzahl")),
                ("created_at",        models.DateTimeField(auto_now_add=True)),
                ("is_active",         models.BooleanField(default=True)),
                ("created_by",        models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="camps_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-start_date"], "verbose_name": "Freizeit", "verbose_name_plural": "Freizeiten"},
        ),
        migrations.CreateModel(
            name="CampDay",
            fields=[
                ("id",                   models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("date",                 models.DateField(verbose_name="Datum")),
                ("note",                 models.CharField(blank=True, max_length=300)),
                ("participants_present", models.PositiveIntegerField(blank=True, null=True, verbose_name="Anwesende TN")),
                ("supervisors_present",  models.PositiveIntegerField(blank=True, null=True, verbose_name="Anwesende Betreuer")),
                ("camp",                 models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="days", to="camps.camp")),
            ],
            options={"ordering": ["date"], "verbose_name": "Freizeit-Tag", "verbose_name_plural": "Freizeit-Tage"},
        ),
        migrations.AlterUniqueTogether(
            name="campday",
            unique_together={("camp", "date")},
        ),
        migrations.CreateModel(
            name="Participant",
            fields=[
                ("id",                models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("first_name",        models.CharField(max_length=100, verbose_name="Vorname")),
                ("last_name",         models.CharField(max_length=100, verbose_name="Nachname")),
                ("person_type",       models.CharField(choices=[("participant","Teilnehmer"),("supervisor","Betreuer")], default="participant", max_length=20, verbose_name="Typ")),
                ("age",               models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Alter")),
                ("notes",             models.TextField(blank=True, verbose_name="Sonstige Hinweise")),
                ("is_vegan",          models.BooleanField(default=False, verbose_name="Vegan")),
                ("is_vegetarian",     models.BooleanField(default=False, verbose_name="Vegetarisch")),
                ("is_halal",          models.BooleanField(default=False, verbose_name="Halal")),
                ("is_kosher",         models.BooleanField(default=False, verbose_name="Koscher")),
                ("intolerance_notes", models.TextField(blank=True, verbose_name="Zusatzhinweise Unverträglichkeiten")),
                ("created_at",        models.DateTimeField(auto_now_add=True)),
                ("camp",         models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="participants", to="camps.camp")),
                ("absent_dates", models.ManyToManyField(blank=True, related_name="absences", to="camps.campday", verbose_name="Abwesend an folgenden Tagen")),
                ("intolerances", models.ManyToManyField(blank=True, related_name="participants", to="recipes.allergen", verbose_name="Allergien / Unverträglichkeiten")),
            ],
            options={"ordering": ["last_name", "first_name"], "verbose_name": "Teilnehmer / Betreuer", "verbose_name_plural": "Teilnehmer / Betreuer"},
        ),
    ]
