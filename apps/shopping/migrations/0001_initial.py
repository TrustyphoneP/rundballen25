from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ("camps",    "0001_initial"),
        ("recipes",  "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShoppingList",
            fields=[
                ("id",           models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("from_date",    models.DateField(verbose_name="Von Datum")),
                ("to_date",      models.DateField(verbose_name="Bis Datum")),
                ("generated_at", models.DateTimeField(auto_now_add=True)),
                ("notes",        models.TextField(blank=True)),
                ("camp",         models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shopping_lists", to="camps.camp")),
                ("generated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="accounts.user")),
            ],
            options={"ordering": ["-generated_at"], "verbose_name": "Einkaufsliste", "verbose_name_plural": "Einkaufslisten"},
        ),
        migrations.CreateModel(
            name="ShoppingItem",
            fields=[
                ("id",        models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("amount",    models.DecimalField(decimal_places=3, max_digits=12)),
                ("unit",      models.CharField(max_length=10)),
                ("is_bought", models.BooleanField(default=False, verbose_name="Gekauft")),
                ("notes",     models.CharField(blank=True, max_length=300)),
                ("ingredient",     models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="recipes.ingredient")),
                ("shopping_list",  models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="shopping.shoppinglist")),
            ],
            options={"ordering": ["ingredient__name"], "verbose_name": "Einkaufsposten", "verbose_name_plural": "Einkaufsposten"},
        ),
    ]
