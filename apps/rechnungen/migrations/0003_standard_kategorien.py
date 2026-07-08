"""
Standard-Kostenkategorien anlegen, passend zu den Bereichen der
Essensplanung. Weitere Kostenpunkte können jederzeit über die
Kategoriekosten-Seite ergänzt werden.
"""
from django.db import migrations

STANDARD_KATEGORIEN = [
    (10, "Abendessen"),
    (20, "Frühstück/Mittagessen"),
    (30, "Brot"),
    (40, "Allgemein"),
    (50, "SKF-Alternativen"),
    (60, "Betreueressen"),
    (70, "Sonstiges"),
]


def kategorien_anlegen(apps, schema_editor):
    Kostenkategorie = apps.get_model("rechnungen", "Kostenkategorie")
    for sortierung, name in STANDARD_KATEGORIEN:
        Kostenkategorie.objects.get_or_create(
            name=name, defaults={"sortierung": sortierung}
        )


def kategorien_entfernen(apps, schema_editor):
    Kostenkategorie = apps.get_model("rechnungen", "Kostenkategorie")
    namen = [name for _, name in STANDARD_KATEGORIEN]
    Kostenkategorie.objects.filter(name__in=namen, belege__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("rechnungen", "0002_kostenkategorie_beleg_kategorie"),
    ]

    operations = [
        migrations.RunPython(kategorien_anlegen, kategorien_entfernen),
    ]
