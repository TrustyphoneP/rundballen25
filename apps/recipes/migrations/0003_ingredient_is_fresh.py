from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("recipes", "0002_seed_allergens")]
    operations = [
        migrations.AddField(
            model_name="ingredient",
            name="is_fresh",
            field=models.BooleanField(
                default=False,
                verbose_name="Frische Zutat",
                help_text="Frisch (z.B. Gemuese, Fleisch) oder trocken (z.B. Nudeln, Dosenware)"
            ),
        ),
    ]
