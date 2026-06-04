"""
context_processors.py

Stellt active_camp und stats auf jeder Seite bereit
damit die Sidebar immer korrekt gerendert wird.
"""
from django.db.models import Q


def active_camp(request):
    """
    Gibt active_camp und stats für die Sidebar zurück.
    Laeuft bei jedem Request — deshalb minimal und gecacht.
    """
    if not request.user.is_authenticated:
        return {}

    from apps.camps.models import Camp

    camp = Camp.objects.filter(is_active=True).order_by("-start_date").first()
    if not camp:
        return {"active_camp": None, "stats": {}}

    # Erst alle TN holen, dann in Python filtern – vermeidet JOIN-Duplikate
    participants = camp.participants.prefetch_related("intolerances").all()

    mit_intol = sum(
        1 for p in participants
        if p.is_vegan or p.is_vegetarian or p.is_halal or p.is_kosher
        or p.intolerances.exists()
    )

    return {
        "active_camp": camp,
        "stats": {
            "mit_intol": mit_intol,
        },
    }