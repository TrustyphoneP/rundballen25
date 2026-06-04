from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Allergen",
            fields=[
                ("id",          models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name",        models.CharField(max_length=100, unique=True)),
                ("short_code",  models.CharField(help_text="z.B. GL, MI, NU", max_length=10, unique=True)),
                ("description", models.TextField(blank=True)),
                ("icon",        models.CharField(blank=True, help_text="Emoji", max_length=10)),
                ("sort_order",  models.PositiveSmallIntegerField(default=0)),
            ],
            options={"ordering": ["sort_order", "name"], "verbose_name": "Allergen / Unverträglichkeit", "verbose_name_plural": "Allergene / Unverträglichkeiten"},
        ),
        migrations.CreateModel(
            name="RecipeCategory",
            fields=[
                ("id",   models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("icon", models.CharField(blank=True, max_length=10)),
            ],
            options={"verbose_name": "Rezeptkategorie", "verbose_name_plural": "Rezeptkategorien"},
        ),
        migrations.CreateModel(
            name="Ingredient",
            fields=[
                ("id",       models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name",     models.CharField(max_length=200, unique=True)),
                ("is_vegan", models.BooleanField(default=True)),
                ("notes",    models.CharField(blank=True, max_length=300)),
                ("allergens", models.ManyToManyField(blank=True, related_name="ingredients", to="recipes.allergen")),
            ],
            options={"ordering": ["name"], "verbose_name": "Zutat", "verbose_name_plural": "Zutaten"},
        ),
        migrations.CreateModel(
            name="Recipe",
            fields=[
                ("id",            models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name",          models.CharField(max_length=200, verbose_name="Rezeptname")),
                ("description",   models.TextField(blank=True)),
                ("image",         models.ImageField(blank=True, null=True, upload_to="recipes/")),
                ("is_vegan",      models.BooleanField(default=False, verbose_name="Vegan")),
                ("is_vegetarian", models.BooleanField(default=False, verbose_name="Vegetarisch")),
                ("base_servings", models.PositiveIntegerField(default=10, help_text="Für wie viele Personen sind die Zutatenmengen angegeben?", verbose_name="Basis-Portionen")),
                ("prep_time_min", models.PositiveIntegerField(blank=True, null=True, verbose_name="Zubereitung (Min)")),
                ("cook_time_min", models.PositiveIntegerField(blank=True, null=True, verbose_name="Kochzeit (Min)")),
                ("notes",         models.TextField(blank=True, verbose_name="Notizen / Hinweise")),
                ("created_at",    models.DateTimeField(auto_now_add=True)),
                ("updated_at",    models.DateTimeField(auto_now=True)),
                ("allergens",     models.ManyToManyField(blank=True, related_name="recipes", to="recipes.allergen", verbose_name="Enthaltene Allergene")),
                ("category",      models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="recipes.recipecategory")),
                ("created_by",    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recipes_created", to="accounts.user")),
            ],
            options={"ordering": ["name"], "verbose_name": "Rezept", "verbose_name_plural": "Rezepte"},
        ),
        migrations.CreateModel(
            name="RecipeIngredient",
            fields=[
                ("id",         models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount",     models.DecimalField(decimal_places=3, max_digits=10, verbose_name="Menge")),
                ("unit",       models.CharField(choices=[("g","Gramm"),("kg","Kilogramm"),("ml","Milliliter"),("l","Liter"),("Stk","Stueck"),("EL","Essloeffel"),("TL","Teeloeffe"),("Pck","Packung"),("Bd","Bund")], default="g", max_length=10)),
                ("note",       models.CharField(blank=True, max_length=200, verbose_name="Hinweis")),
                ("ingredient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="recipes.ingredient")),
                ("recipe",     models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recipe_ingredients", to="recipes.recipe")),
            ],
            options={"verbose_name": "Rezept-Zutat", "verbose_name_plural": "Rezept-Zutaten"},
        ),
        migrations.AlterUniqueTogether(
            name="recipeingredient",
            unique_together={("recipe", "ingredient")},
        ),
    ]
