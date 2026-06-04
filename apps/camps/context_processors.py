"""
context_processors.py

Stellt active_camp und stats auf jeder Seite bereit
damit die Sidebar immer korrekt gerendert wird.
"""
from django.db.models import Count, Q


def active_camp(request):
    """
    Gibt active_camp und stats für die Sidebar zurück.
    Laeuft bei jedem Request — deshalb minimal und gecacht.
    """
    if not request.user.is_authenticated:
        return {}

    # Import hier um zirkulaere Imports zu vermeiden
    from apps.camps.models import Camp

    camp = Camp.objects.filter(is_active=True).order_by("-start_date").first()
    if not camp:
        return {"active_camp": None, "stats": {}}

    # Statistiken für Sidebar-Badge (Unverträglichkeiten)
    from apps.recipes.models import Allergen
    mit_intol = (
        camp.participants
        .filter(
            Q(intolerances__isnull=False) |
            Q(is_vegan=True) | Q(is_vegetarian=True) |
            Q(is_halal=True) | Q(is_kosher=True)
        )
        .distinct()
        .count()
    )

    return {
        "active_camp": camp,
        "stats": {
            "mit_intol": mit_intol,
        },
    }
