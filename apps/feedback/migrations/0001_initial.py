from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ("camps", "0001_initial"),
        ("meals", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeedbackForm",
            fields=[
                ("id",         models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("title",      models.CharField(max_length=200)),
                ("is_active",  models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("camp", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="feedback_forms", to="camps.camp")),
                ("day",  models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="camps.campday")),
            ],
            options={"verbose_name": "Feedbackformular", "verbose_name_plural": "Feedbackformulare"},
        ),
        migrations.CreateModel(
            name="FeedbackEntry",
            fields=[
                ("id",           models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("rating",       models.PositiveSmallIntegerField(blank=True, choices=[(1,"Sehr schlecht"),(2,"Schlecht"),(3,"Okay"),(4,"Gut"),(5,"Sehr gut")], null=True)),
                ("comment",      models.TextField(blank=True, verbose_name="Kommentar (anonym)")),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("session_hash", models.CharField(blank=True, max_length=64)),
                ("form",      models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entries", to="feedback.feedbackform")),
                ("warm_meal", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="meals.warmmeal")),
            ],
            options={"verbose_name": "Feedbackeintrag", "verbose_name_plural": "Feedbackeintraege"},
        ),
    ]
