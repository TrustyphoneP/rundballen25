from django.urls import path
from . import views

app_name = "camps"

urlpatterns = [
    # Dashboard
    path("",                                     views.dashboard,              name="dashboard"),

    # Teilnehmer
    path("freizeit/<int:camp_pk>/teilnehmer/",         views.participant_list,   name="participant_list"),
    path("freizeit/<int:camp_pk>/teilnehmer/neu/",     views.participant_create, name="participant_create"),
    path("freizeit/<int:camp_pk>/import/",             views.participant_csv_import, name="csv_import"),
    path("freizeit/<int:camp_pk>/export/",             views.participant_csv_export, name="csv_export"),
    path("freizeit/<int:camp_pk>/allergene/",          views.allergen_overview,  name="allergen_overview"),
    path("teilnehmer/<int:pk>/",                       views.participant_detail, name="participant_detail"),
    path("teilnehmer/<int:pk>/bearbeiten/",            views.participant_edit,   name="participant_edit"),
    path("teilnehmer/<int:pk>/löschen/",              views.participant_delete, name="participant_delete"),

    # Hilfsmittel
    path("csv-vorlage/",                               views.csv_template,       name="csv_template"),
]
