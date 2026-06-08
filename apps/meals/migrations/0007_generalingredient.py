from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("meals", "0006_brotconfig"),
        ("camps", "0005_alter_participant_options_and_more"),
        ("recipes", "0006_alter_recipeingredient_unit"),
    ]

    operations = [
        migrations.CreateModel(
            name="GeneralIngredient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("camp", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="general_ingredients", to="camps.camp")),
                ("ingredient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="general_uses", to="recipes.ingredient")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("unit", models.CharField(max_length=20)),
                ("notes", models.CharField(blank=True, max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"verbose_name": "Allgemeine Zutat", "verbose_name_plural": "Allgemeine Zutaten", "ordering": ["ingredient__name"]},
        ),
    ]
