"""
Data Migration: Alle 14 EU-Pflichtallergene + häufige Unverträglichkeiten
automatisch beim ersten Migrate anlegen.
"""
from django.db import migrations

ALLERGENS = [
    # (name, short_code, icon, sort_order)
    ("Gluten (Weizen, Roggen, Gerste, Hafer)", "GL", "🌾", 1),
    ("Krebstiere und Krebstiererzeugnisse",    "KR", "🦐", 2),
    ("Eier und Eierzeugnisse",                 "EI", "🥚", 3),
    ("Fisch und Fischerzeugnisse",             "FI", "🐟", 4),
    ("Erdnüsse und Erdnusserzeugnisse",        "EN", "🥜", 5),
    ("Soja und Sojaerzeugnisse",               "SO", "🫘", 6),
    ("Milch / Laktose",                        "MI", "🥛", 7),
    ("Schalenfrüchte / Nüsse",                 "NU", "🌰", 8),
    ("Sellerie",                               "SE", "🥬", 9),
    ("Senf",                                   "SN", "🌿", 10),
    ("Sesam",                                  "SS", "🌱", 11),
    ("Schwefeldioxid / Sulfite",               "SU", "⚗️", 12),
    ("Lupinen",                                "LU", "🌼", 13),
    ("Weichtiere",                             "WE", "🦑", 14),
    ("Fruktose-Intoleranz",                    "FR", "🍎", 20),
    ("Histamin-Intoleranz",                    "HI", "🔴", 21),
    ("Sorbit-Intoleranz",                      "SB", "🍇", 22),
]

def seed_allergens(apps, schema_editor):
    Allergen = apps.get_model("recipes", "Allergen")
    for name, short_code, icon, sort_order in ALLERGENS:
        Allergen.objects.get_or_create(
            short_code=short_code,
            defaults={"name": name, "icon": icon, "sort_order": sort_order},
        )

def unseed_allergens(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [("recipes", "0001_initial")]
    operations = [migrations.RunPython(seed_allergens, unseed_allergens)]
