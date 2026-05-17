from django.urls import path
from . import views

app_name = "voting"

urlpatterns = [
    # Admin
    path("",                                           views.admin_index,         name="index"),
    path("neu/",                                       views.admin_create,        name="create"),
    path("<int:pk>/",                                  views.admin_detail,        name="admin_detail"),
    path("<int:pk>/status/",                           views.admin_set_status,    name="set_status"),
    path("<int:pk>/gericht/hinzufuegen/",              views.admin_add_recipe,    name="add_recipe"),
    path("<int:pk>/gericht/<int:recipe_pk>/toggle/",   views.admin_toggle_recipe, name="toggle_recipe"),
    path("<int:pk>/gericht/<int:recipe_pk>/loeschen/", views.admin_delete_recipe, name="delete_recipe"),
    path("<int:pk>/stimmen/reset/",                    views.admin_reset_votes,   name="reset_votes"),
    path("<int:pk>/ergebnisse.json",                   views.results_json,        name="results_json"),

    # Öffentlich — ein Link für alle
    path("abstimmen/<int:poll_id>/",                   views.vote,                name="vote"),
    path("abstimmen/<int:poll_id>/danke/",             views.thank_you,           name="thank_you"),
]
