from django.urls import path
from . import views

app_name = "shopping"

urlpatterns = [
    path("",                                      views.index,               name="index"),
    path("aus-wochenplan/",                       views.create_from_plan,    name="create_from_plan"),
    path("aus-rezepten/",                         views.create_from_recipes, name="create_from_recipes"),
    path("freizeit/<int:camp_pk>/",               views.plan_overview,       name="plan_overview"),
    path("freizeit/<int:camp_pk>/export/",        views.export_csv_combined, name="export_csv_combined"),
    path("<int:pk>/",                             views.detail,              name="detail"),
    path("<int:pk>/export/",                      views.export_csv,          name="export_csv"),
    path("<int:pk>/regenerieren/",                views.regenerate,          name="regenerate"),
    path("<int:pk>/zurücksetzen/",               views.reset_list,          name="reset_list"),
    path("<int:pk>/löschen/",                    views.delete_list,         name="delete_list"),
    path("item/<int:pk>/toggle/",                 views.toggle_item,         name="toggle_item"),
]
