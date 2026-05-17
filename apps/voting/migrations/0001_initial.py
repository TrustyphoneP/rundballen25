from django.db import migrations, models
import django.db.models.deletion
import secrets


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ("camps",    "0001_initial"),
        ("recipes",  "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Poll",
            fields=[
                ("id",          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("title",       models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("status",      models.CharField(choices=[("draft","Entwurf"),("open","Offen"),("closed","Abgeschlossen")], default="draft", max_length=10)),
                ("created_at",  models.DateTimeField(auto_now_add=True)),
                ("closed_at",   models.DateTimeField(blank=True, null=True)),
                ("camp",       models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="polls", to="camps.camp")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to="accounts.user")),
            ],
            options={"verbose_name": "Abstimmung", "verbose_name_plural": "Abstimmungen"},
        ),
        migrations.CreateModel(
            name="PollOption",
            fields=[
                ("id",          models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("description", models.CharField(blank=True, max_length=300)),
                ("poll",   models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="options", to="voting.poll")),
                ("recipe", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="recipes.recipe")),
            ],
            options={"verbose_name": "Abstimmungsoption"},
        ),
        migrations.AlterUniqueTogether(name="polloption", unique_together={("poll", "recipe")}),
        migrations.CreateModel(
            name="VoteToken",
            fields=[
                ("id",         models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("token",      models.CharField(default=secrets.token_urlsafe, max_length=64, unique=True)),
                ("label",      models.CharField(blank=True, max_length=100)),
                ("used",       models.BooleanField(default=False)),
                ("used_at",    models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("poll", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tokens", to="voting.poll")),
            ],
            options={"verbose_name": "Abstimmungstoken"},
        ),
        migrations.CreateModel(
            name="Vote",
            fields=[
                ("id",       models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("voted_at", models.DateTimeField(auto_now_add=True)),
                ("option", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="votes", to="voting.polloption")),
                ("token",  models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="vote", to="voting.votetoken")),
            ],
            options={"verbose_name": "Stimme", "verbose_name_plural": "Stimmen"},
        ),
    ]
