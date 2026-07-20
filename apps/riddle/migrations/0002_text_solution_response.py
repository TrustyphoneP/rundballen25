from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("riddle", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="riddlestage",
            name="text_solution",
            field=models.CharField(
                max_length=200,
                blank=True,
                default="",
                verbose_name="Loesung des Textraetsels",
                help_text="Antwort, die Spieler unter dem Textraetsel eingeben muessen. "
                "Vergleich ist unabhaengig von Gross-/Kleinschreibung.",
            ),
        ),
        migrations.AddField(
            model_name="riddlestage",
            name="text_response",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Antwortstring bei korrekter Loesung",
                help_text="Wird angezeigt, wenn die Loesung des Textraetsels korrekt "
                "eingegeben wurde.",
            ),
        ),
    ]
