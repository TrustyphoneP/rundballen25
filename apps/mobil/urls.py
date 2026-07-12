from django.urls import path
from . import views

app_name = "mobil"

urlpatterns = [
    # Auth
    path("",                    views.login_view,        name="login"),
    path("registrieren/",       views.registrieren_view, name="registrieren"),
    path("logout/",             views.logout_view,       name="logout"),
    path("passwort/",           views.passwort_view,     name="passwort"),

    # Freizeiten
    path("freizeiten/",                     views.freizeiten_view,    name="freizeiten"),
    path("freizeiten/<int:camp_pk>/beitreten/", views.freizeit_beitreten, name="beitreten"),
    path("freizeiten/<int:camp_pk>/waehlen/",   views.freizeit_waehlen,   name="waehlen"),

    # Pläne
    path("heute/",              views.heute_view,        name="heute"),
    path("woche/",              views.woche_view,        name="woche"),
    path("plan/neu/",           views.plan_anlegen,      name="plan_neu"),
    path("plan/import/",        views.plan_import,       name="plan_import"),
    path("plan/import/vorlage/", views.plan_import_vorlage, name="plan_import_vorlage"),
    path("aktion/neu/",         views.aktion_anlegen,    name="aktion_neu"),
    path("aktion/<int:pk>/",    views.aktion_bearbeiten, name="aktion_bearbeiten"),

    # Checklisten
    path("checklisten/",                 views.checklisten_view,     name="checklisten"),
    path("checklisten/neu/",             views.checkliste_verwalten, name="checkliste_neu"),
    path("checklisten/<int:pk>/",        views.checkliste_detail,    name="checkliste"),
    path("checklisten/<int:pk>/bearbeiten/", views.checkliste_verwalten, name="checkliste_verwalten"),

    # Gruppen (zentrale Verwaltung)
    path("gruppen/",            views.gruppen_view,      name="gruppen"),

    # Profil
    path("profil/",             views.profil_view,       name="profil"),
]
