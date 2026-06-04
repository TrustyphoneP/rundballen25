from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("camps", "0003_alter_participant_intolerance_notes"),
    ]

    operations = [
        migrations.AddField(
            model_name="participant",
            name="date_of_birth",
            field=models.DateField(null=True, blank=True, verbose_name="Geburtsdatum"),
        ),
        migrations.RemoveField(
            model_name="participant",
            name="age",
        ),
    ]
