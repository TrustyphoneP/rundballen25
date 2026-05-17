from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("meals",   "0001_initial"),
        ("camps",   "0001_initial"),
        ("recipes", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DayMeal",
            fields=[
                ("id",              models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("person_override", models.PositiveIntegerField(blank=True, null=True, verbose_name="Personenzahl (manuell)")),
                ("notes",           models.TextField(blank=True, verbose_name="Notizen zum Tag")),
                ("day",         models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="day_meal",  to="camps.campday")),
                ("main_course", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="as_main_course", to="recipes.recipe", verbose_name="Hauptgericht")),
                ("dessert",     models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="as_dessert",     to="recipes.recipe", verbose_name="Dessert")),
                ("salad",       models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="as_salad",        to="recipes.recipe", verbose_name="Salat")),
            ],
            options={"ordering": ["day__date"], "verbose_name": "Tagesplanung Abendessen", "verbose_name_plural": "Tagesplanung Abendessen"},
        ),
    ]
