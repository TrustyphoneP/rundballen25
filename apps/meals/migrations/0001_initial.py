from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ("camps",   "0001_initial"),
        ("recipes", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="WarmMeal",
            fields=[
                ("id",              models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("person_override", models.PositiveIntegerField(blank=True, null=True, verbose_name="Personenzahl (manuell)")),
                ("notes",           models.TextField(blank=True, verbose_name="Notizen")),
                ("day",    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="warm_meal", to="camps.campday")),
                ("recipe", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="warm_meals", to="recipes.recipe", verbose_name="Rezept")),
            ],
            options={"ordering": ["day__date"], "verbose_name": "Warmes Abendessen", "verbose_name_plural": "Warme Abendessen"},
        ),
        migrations.CreateModel(
            name="BreadPlan",
            fields=[
                ("id",               models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("breakfast_loaves", models.DecimalField(decimal_places=1, default=0, max_digits=6, verbose_name="Laibe Fruehstueck")),
                ("evening_loaves",   models.DecimalField(decimal_places=1, default=0, max_digits=6, verbose_name="Laibe Abend")),
                ("bread_type",       models.CharField(blank=True, default="Mischbrot", max_length=100, verbose_name="Brotsorte")),
                ("use_rolls",        models.BooleanField(default=False, verbose_name="Broetchen statt Brot")),
                ("rolls_count",      models.PositiveIntegerField(blank=True, null=True, verbose_name="Anzahl Broetchen")),
                ("topping_notes",    models.TextField(blank=True, verbose_name="Belaege / Aufschnitt")),
                ("notes",            models.TextField(blank=True, verbose_name="Sonstige Notizen")),
                ("day", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="bread_plan", to="camps.campday")),
            ],
            options={"verbose_name": "Brotplanung", "verbose_name_plural": "Brotplanung"},
        ),
    ]
