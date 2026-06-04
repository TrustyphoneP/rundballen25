from django.urls import path
from . import views

app_name = "recipes"

urlpatterns = [
    path("",                          views.recipe_list,            name="list"),
    path("neu/",                      views.recipe_create,          name="create"),
    path("<int:pk>/",                 views.recipe_detail,          name="detail"),
    path("<int:pk>/bearbeiten/",      views.recipe_edit,            name="edit"),
    path("<int:pk>/löschen/",        views.recipe_delete,          name="delete"),

    path("zutaten/",                  views.ingredient_list,        name="ingredient_list"),
    path("zutaten/neu/",              views.ingredient_create,      name="ingredient_create"),
    path("zutaten/<int:pk>/",         views.ingredient_edit,        name="ingredient_edit"),

    path("api/zutaten/",              views.ingredient_autocomplete, name="ingredient_autocomplete"),
]
