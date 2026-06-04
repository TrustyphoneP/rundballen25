from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ("camps", "0001_initial"),
        ("accounts", "0001_initial"),
        ("recipes", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Poll",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=200, verbose_name="Titel")),
                ("description", models.TextField(blank=True, verbose_name="Beschreibung")),
                ("status", models.CharField(max_length=10, choices=[("draft","Entwurf"),("open","Offen"),("closed","Abgeschlossen")], default="draft")),
                ("min_votes", models.PositiveSmallIntegerField(default=0, verbose_name="Mindestauswahl")),
                ("max_votes", models.PositiveSmallIntegerField(default=6, verbose_name="Maximalauswahl")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("closed_at", models.DateTimeField(null=True, blank=True)),
                ("camp", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="polls", to="camps.camp")),
                ("created_by", models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, to="accounts.user")),
            ],
            options={"verbose_name": "Abstimmung", "verbose_name_plural": "Abstimmungen", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="VoteRecipe",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("is_vegan", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("poll", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vote_recipes", to="voting.poll")),
                ("recipe", models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vote_entries", to="recipes.recipe")),
            ],
            options={"verbose_name": "Abstimm-Gericht", "verbose_name_plural": "Abstimm-Gerichte", "ordering": ["sort_order", "name"]},
        ),
        migrations.CreateModel(
            name="Vote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("session_key", models.CharField(max_length=40, verbose_name="Session")),
                ("voted_at", models.DateTimeField(auto_now_add=True)),
                ("vote_recipe", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="votes", to="voting.voterecipe")),
            ],
            options={"verbose_name": "Stimme", "verbose_name_plural": "Stimmen"},
        ),
        migrations.AlterUniqueTogether(
            name="vote",
            unique_together={("vote_recipe", "session_key")},
        ),
    ]