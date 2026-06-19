from django.urls import path
from . import views

app_name = "meals"

urlpatterns = [
    path("",                                    views.week_plan,      name="index"),
    path("freizeit/<int:camp_pk>/",             views.week_plan,      name="week_plan"),
    path("tag/<int:day_pk>/slot/<str:slot>/",   views.assign_recipe,  name="assign_recipe"),
    path("tag/<int:day_pk>/slot/<str:slot>/leeren/", views.clear_slot, name="clear_slot"),
    path("tag/<int:day_pk>/notiz/",             views.save_note,      name="save_note"),
    path("freizeit/<int:camp_pk>/brot/",        views.bread_plan,     name="bread_plan"),
    path("brot/",                               views.bread_plan,     name="bread_plan_default"),
    path("freizeit/<int:camp_pk>/fruehstueck/", views.fruehstueck,    name="fruehstueck"),
    path("fruehstueck/",                        views.fruehstueck,    name="fruehstueck_default"),
    path("freizeit/<int:camp_pk>/allgemein/",   views.allgemein,      name="allgemein"),
    path("allgemein/",                          views.allgemein,      name="allgemein_default"),

    # Betreueressen: Resteverwertung pro Tag
    path("freizeit/<int:camp_pk>/betreueressen/",                 views.betreueressen, name="betreueressen"),
    path("freizeit/<int:camp_pk>/betreueressen/tag/<int:day_pk>/", views.betreueressen, name="betreueressen_day"),
    path("betreueressen/",                                        views.betreueressen, name="betreueressen_default"),
]
