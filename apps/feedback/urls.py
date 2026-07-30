from django.urls import path
from . import views

app_name = "feedback"

urlpatterns = [
    path("",                    views.feedback_home,  name="home"),
    path("danke/",               views.feedback_danke, name="danke"),
    path("tag/<int:day_pk>/",   views.feedback_day,   name="day"),
    path("auswertung/",         views.feedback_admin, name="admin_overview"),
]
