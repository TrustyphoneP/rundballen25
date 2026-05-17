"""
Migration: Vote-Modell auf Session-basiert umstellen.
- VoteToken-Tabelle entfernen
- Vote: token FK entfernen, session_key CharField hinzufügen
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("voting", "0004_alter_poll_id_alter_vote_id_alter_voterecipe_id_and_more"),
    ]

    operations = [
        # 1. Alte Votes löschen (inkompatibles Schema)
        migrations.DeleteModel("Vote"),

        # 2. VoteToken-Tabelle entfernen
        migrations.DeleteModel("VoteToken"),

        # 3. Neues Vote-Modell mit session_key
        migrations.CreateModel(
            name="Vote",
            fields=[
                ("id",          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("session_key", models.CharField(max_length=40, verbose_name="Session")),
                ("voted_at",    models.DateTimeField(auto_now_add=True)),
                ("vote_recipe", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="votes",
                    to="voting.voterecipe",
                )),
            ],
            options={
                "verbose_name": "Stimme",
                "verbose_name_plural": "Stimmen",
            },
        ),
        migrations.AlterUniqueTogether(
            name="vote",
            unique_together={("vote_recipe", "session_key")},
        ),
    ]
