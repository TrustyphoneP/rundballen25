from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("meals", "0005_alter_fruehstueckconfig_id"),
        ("camps", "0005_alter_participant_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="BrotConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("camp", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="brot_config", to="camps.camp")),
                ("doppelweck_per_person", models.FloatField(default=1.0, verbose_name="Doppelweck pro Person")),
                ("scheiben_per_person",   models.FloatField(default=2.0, verbose_name="Scheiben Brot pro Person")),
                ("scheiben_per_laib",     models.FloatField(default=25.0, verbose_name="Scheiben pro Laib")),
                ("updated_at",            models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Brot Konfiguration"},
        ),
    ]
