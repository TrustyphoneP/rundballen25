from django.urls import path

from . import views

app_name = "rechnungen"

urlpatterns = [
    path("",                                    views.index,                  name="index"),
    path("hochladen/",                          views.upload,                 name="upload"),
    path("beleg/<int:pk>/",                     views.detail,                 name="detail"),
    path("beleg/<int:pk>/analysieren/",         views.analysieren,            name="analysieren"),
    path("beleg/<int:pk>/loeschen/",            views.loeschen,               name="loeschen"),
    path("beleg/<int:pk>/alle-uebernehmen/",    views.alle_uebernehmen,       name="alle_uebernehmen"),
    path("position/<int:pk>/aktualisieren/",    views.position_aktualisieren, name="position_aktualisieren"),
    path("position/<int:pk>/loeschen/",         views.position_loeschen,      name="position_loeschen"),
    path("beleg/<int:pk>/kategorie/",           views.beleg_kategorie,        name="beleg_kategorie"),

    path("kategorien/",                         views.kategorien,             name="kategorien"),
    path("kategorien/<int:pk>/loeschen/",       views.kategorie_loeschen,     name="kategorie_loeschen"),

    path("preisliste/",                         views.preisliste,             name="preisliste"),
    path("rezeptkosten/",                       views.rezeptkosten,           name="rezeptkosten"),
    path("freizeitkosten/",                     views.freizeitkosten,         name="freizeitkosten"),
    path("preistreiber/",                       views.preistreiber,           name="preistreiber"),
]
