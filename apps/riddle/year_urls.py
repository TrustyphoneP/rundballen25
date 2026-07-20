"""
Bindet /<year>/ direkt ein, OHNE riddle/ Praefix.

In config/urls.py:
    path("<int:year>/", include("apps.riddle.year_urls")),
"""

from django.urls import path
from . import views

# Kein app_name hier, da diese URLs im riddle-Namespace ueber year_page erreichbar sind
urlpatterns = [
    path("", views.year_page, name="riddle_year_page"),
]
