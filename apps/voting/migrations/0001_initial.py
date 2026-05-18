from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("camps",   "0001_initial"),
        ("recipes", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Poll",
            fields=[
                ("id",          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("title",       models.CharField(max_length=200, verbose_name="Titel")),
                ("description", models.TextField(blank=True, verbose_name="Beschreibung")),
                ("status",      models.CharField(
                    choices=[("draft","Entwurf"),("open","Offen"),("closed","Abgeschlossen")],
                    default="draft", max_length=10)),
                ("min_votes",   models.PositiveSmallIntegerField(default=0, verbose_name="Mindestauswahl")),
                ("max_votes",   models.PositiveSmallIntegerField(default=6, verbose_name="Maximalauswahl")),
                ("created_at",  models.DateTimeField(auto_now_add=True)),
                ("closed_at",   models.DateTimeField(blank=True, null=True)),
                ("camp",        models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="polls", to="camps.camp")),
                ("created_by",  models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"], "verbose_name": "Abstimmung", "verbose_name_plural": "Abstimmungen"},
        ),
        migrations.CreateModel(
            name="VoteRecipe",
            fields=[
                ("id",          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name",        models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("is_vegan",    models.BooleanField(default=False)),
                ("is_active",   models.BooleanField(default=True)),
                ("sort_order",  models.PositiveSmallIntegerField(default=0)),
                ("poll",        models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vote_recipes", to="voting.poll")),
                ("recipe",      models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vote_entries", to="recipes.recipe")),
            ],
            options={"ordering": ["sort_order", "name"], "verbose_name": "Abstimm-Gericht", "verbose_name_plural": "Abstimm-Gerichte"},
        ),
        migrations.CreateModel(
            name="Vote",
            fields=[
                ("id",          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("session_key", models.CharField(max_length=40, verbose_name="Session")),
                ("voted_at",    models.DateTimeField(auto_now_add=True)),
                ("vote_recipe", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="votes", to="voting.voterecipe")),
            ],
            options={"verbose_name": "Stimme", "verbose_name_plural": "Stimmen"},
        ),
        migrations.AlterUniqueTogether(
            name="vote",
            unique_together={("vote_recipe", "session_key")},
        ),
    ]
