from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("meals", "0003_alter_warmmeal_options_alter_breadplan_bread_type_and_more"),
        ("camps", "0004_participant_date_of_birth"),
    ]

    operations = [
        migrations.CreateModel(
            name="FruehstueckConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("camp", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="fruehstueck_config", to="camps.camp")),
                ("loaves_cheese",       models.PositiveIntegerField(default=0)),
                ("loaves_salami",       models.PositiveIntegerField(default=0)),
                ("loaves_fleischkaese", models.PositiveIntegerField(default=0)),
                ("loaves_fleischwurst", models.PositiveIntegerField(default=0)),
                ("weight_cheese",       models.FloatField(default=23.0)),
                ("weight_salami",       models.FloatField(default=15.0)),
                ("weight_fleischkaese", models.FloatField(default=20.0)),
                ("weight_fleischwurst", models.FloatField(default=15.0)),
                ("spb_cheese",          models.FloatField(default=1.0)),
                ("spb_salami",          models.FloatField(default=1.5)),
                ("spb_fleischkaese",    models.FloatField(default=1.0)),
                ("spb_fleischwurst",    models.FloatField(default=2.0)),
                ("updated_at",          models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Frühstück Konfiguration"},
        ),
    ]
