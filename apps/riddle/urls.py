"""
URL-Konfiguration fuer apps.riddle.

In config/urls.py (bereits vorhanden):

    path("riddle/", include("apps.riddle.urls", namespace="riddle")),
    path("<int:year>/", include("apps.riddle.year_urls")),
"""

from django.urls import path
from . import views

app_name = "riddle"

urlpatterns = [
    # Startseite / aktuelles Bild (kein Eingabefeld, Spieler tippen die URL selbst)
    path("", views.riddle_home, name="home"),
    # Spielleiter-Admin
    path("admin/", views.riddle_admin, name="admin"),
    path("admin/action/", views.admin_action, name="admin_action"),
]
