from django.urls import path
from . import views

app_name = "mobil"

urlpatterns = [
    # Auth
    path("",                    views.login_view,        name="login"),
    path("logout/",             views.logout_view,       name="logout"),
    path("passwort/",           views.passwort_view,     name="passwort"),

    # Freizeiten
    path("freizeiten/",                     views.freizeiten_view,    name="freizeiten"),
    path("freizeiten/<int:camp_pk>/beitreten/", views.freizeit_beitreten, name="beitreten"),
    path("freizeiten/<int:camp_pk>/waehlen/",   views.freizeit_waehlen,   name="waehlen"),

    # Plaene
    path("heute/",              views.heute_view,        name="heute"),
    path("woche/",              views.woche_view,        name="woche"),
    path("plan/neu/",           views.plan_anlegen,      name="plan_neu"),
    path("aktion/neu/",         views.aktion_anlegen,    name="aktion_neu"),
    path("aktion/<int:pk>/",    views.aktion_bearbeiten, name="aktion_bearbeiten"),

    # Profil
    path("profil/",             views.profil_view,       name="profil"),
]
