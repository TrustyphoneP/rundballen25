from django.db import migrations, models
import django.db.models.deletion
import django.db.models.functions
import secrets


class Migration(migrations.Migration):

    dependencies = [
        ("voting",   "0001_initial"),
        ("camps",    "0001_initial"),
        ("recipes",  "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        # Drop old tables
        migrations.DeleteModel("Vote"),
        migrations.DeleteModel("VoteToken"),
        migrations.DeleteModel("PollOption"),
        migrations.DeleteModel("Poll"),

        # Rebuild Poll
        migrations.CreateModel(
            name="Poll",
            fields=[
                ("id",          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("title",       models.CharField(max_length=200, verbose_name="Titel")),
                ("description", models.TextField(blank=True, verbose_name="Beschreibung")),
                ("status",      models.CharField(choices=[("draft","Entwurf"),("open","Offen"),("closed","Abgeschlossen")], default="draft", max_length=10)),
                ("min_votes",   models.PositiveSmallIntegerField(default=0, verbose_name="Mindestauswahl")),
                ("max_votes",   models.PositiveSmallIntegerField(default=6, verbose_name="Maximalauswahl")),
                ("created_at",  models.DateTimeField(auto_now_add=True)),
                ("closed_at",   models.DateTimeField(blank=True, null=True)),
                ("camp",        models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="polls", to="camps.camp")),
                ("created_by",  models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="accounts.user")),
            ],
            options={"ordering": ["-created_at"], "verbose_name": "Abstimmung", "verbose_name_plural": "Abstimmungen"},
        ),

        # VoteRecipe
        migrations.CreateModel(
            name="VoteRecipe",
            fields=[
                ("id",          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name",        models.CharField(max_length=200, verbose_name="Gerichtsname")),
                ("description", models.TextField(blank=True, verbose_name="Beschreibung")),
                ("is_vegan",    models.BooleanField(default=False, verbose_name="Vegan")),
                ("is_active",   models.BooleanField(default=True, verbose_name="Zur Abstimmung freigegeben")),
                ("sort_order",  models.PositiveSmallIntegerField(default=0)),
                ("poll",   models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vote_recipes", to="voting.poll")),
                ("recipe", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vote_entries", to="recipes.recipe", verbose_name="Rezept (DB)")),
            ],
            options={"ordering": ["sort_order", "name"], "verbose_name": "Abstimm-Gericht", "verbose_name_plural": "Abstimm-Gerichte"},
        ),

        # VoteToken
        migrations.CreateModel(
            name="VoteToken",
            fields=[
                ("id",         models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("token",      models.CharField(default=secrets.token_urlsafe, max_length=64, unique=True)),
                ("label",      models.CharField(blank=True, help_text="Nur intern sichtbar, z.B. Name des Betreuers", max_length=100)),
                ("used",       models.BooleanField(default=False)),
                ("used_at",    models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("poll",       models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tokens", to="voting.poll")),
            ],
            options={"ordering": ["label", "created_at"], "verbose_name": "Abstimmungstoken", "verbose_name_plural": "Abstimmungstokens"},
        ),

        # Vote
        migrations.CreateModel(
            name="Vote",
            fields=[
                ("id",       models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("voted_at", models.DateTimeField(auto_now_add=True)),
                ("token",       models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="votes", to="voting.votetoken")),
                ("vote_recipe", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="votes", to="voting.voterecipe")),
            ],
            options={"verbose_name": "Stimme", "verbose_name_plural": "Stimmen"},
        ),
        migrations.AlterUniqueTogether(
            name="vote",
            unique_together={("token", "vote_recipe")},
        ),
    ]
