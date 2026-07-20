from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RiddleStage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "order",
                    models.PositiveSmallIntegerField(
                        unique=True,
                        verbose_name="Reihenfolge (1-4)",
                    ),
                ),
                (
                    "image",
                    models.ImageField(
                        upload_to="riddle/stages/",
                        verbose_name="Raetsel-Bild",
                        help_text="Wird auf /riddle angezeigt.",
                    ),
                ),
                (
                    "solution_year",
                    models.PositiveIntegerField(
                        verbose_name="Loesung (Jahreszahl)",
                        help_text="z.B. 2014 -- URL /2014 fuehrt zum Textinhalt.",
                    ),
                ),
                (
                    "hint",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="Hinweis (optional)",
                    ),
                ),
                (
                    "text_content",
                    models.TextField(
                        verbose_name="Textinhalt der Jahreszahl-Seite",
                        help_text="HTML erlaubt. Wird auf /<solution_year> angezeigt.",
                    ),
                ),
            ],
            options={
                "verbose_name": "Raetsel-Stufe",
                "verbose_name_plural": "Raetsel-Stufen",
                "ordering": ["order"],
            },
        ),
        migrations.CreateModel(
            name="RiddleState",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "current_stage",
                    models.PositiveSmallIntegerField(
                        default=0,
                        verbose_name="Aktuelle Stufe (0=nicht gestartet, 1-4=aktiv, 5=Ende)",
                    ),
                ),
                (
                    "started_at",
                    models.DateTimeField(null=True, blank=True),
                ),
            ],
            options={
                "verbose_name": "Spielstand",
                "verbose_name_plural": "Spielstand",
            },
        ),
        migrations.CreateModel(
            name="PlayerBan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(verbose_name="IP-Adresse"),
                ),
                (
                    "banned_until",
                    models.DateTimeField(verbose_name="Gesperrt bis"),
                ),
                (
                    "wrong_year",
                    models.PositiveIntegerField(
                        null=True, blank=True, verbose_name="Eingegebene Jahreszahl"
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
            ],
            options={
                "verbose_name": "Sperre",
                "verbose_name_plural": "Sperren",
            },
        ),
        migrations.AddIndex(
            model_name="playerban",
            index=models.Index(
                fields=["ip_address", "banned_until"],
                name="riddle_playerban_ip_until_idx",
            ),
        ),
    ]
