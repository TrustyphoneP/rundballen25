from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_user_date_joined_alter_user_email_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="must_change_password",
            field=models.BooleanField(
                default=False,
                verbose_name="Muss Passwort ändern",
                help_text="Benutzer wird nach dem Login zur Passwortänderung aufgefordert.",
            ),
        ),
    ]
