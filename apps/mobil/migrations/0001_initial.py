from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("camps", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FreizeitMitglied",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("beigetreten_am", models.DateTimeField(auto_now_add=True)),
                ("camp", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mobil_mitglieder", to="camps.camp")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="freizeit_mitgliedschaften", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Freizeit-Mitgliedschaft",
                "verbose_name_plural": "Freizeit-Mitgliedschaften",
                "ordering": ["-beigetreten_am"],
                "unique_together": {("user", "camp")},
            },
        ),
    ]
