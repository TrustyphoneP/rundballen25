from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0004_alter_allergen_options_alter_recipe_base_servings_and_more"),
    ]

    operations = [
        # Step 1: add new field with default vegan
        migrations.AddField(
            model_name="ingredient",
            name="diet_type",
            field=models.CharField(
                max_length=20,
                choices=[("vegan", "Vegan"), ("vegetarian", "Vegetarisch"), ("meat", "Fleisch")],
                default="vegan",
                verbose_name="SKF",
            ),
        ),
        # Step 2: migrate existing is_vegan=False rows to vegetarian
        migrations.RunSQL(
            "UPDATE recipes_ingredient SET diet_type = 'vegetarian' WHERE is_vegan = false;",
            reverse_sql="UPDATE recipes_ingredient SET is_vegan = false WHERE diet_type != 'vegan';",
        ),
        # Step 3: remove old is_vegan field
        migrations.RemoveField(
            model_name="ingredient",
            name="is_vegan",
        ),
    ]
