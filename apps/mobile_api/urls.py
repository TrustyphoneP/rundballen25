from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path("auth/login/", views.login_view, name="mobile-login"),
    path("auth/change-password/", views.change_password_view, name="mobile-change-password"),
    path("auth/refresh/", views.token_refresh_view, name="mobile-token-refresh"),
    path("auth/me/", views.me_view, name="mobile-me"),

    # Camps (aus bestehendem Camp-Model)
    path("camps/", views.camps_view, name="mobile-camps"),

    # Betreuer
    path("betreuer/", views.betreuer_list_view, name="mobile-betreuer"),

    # Wochenplaene (nested unter Camp)
    path(
        "camps/<int:camp_id>/wochenplaene/",
        views.WochenplanListCreateView.as_view(),
        name="mobile-wochenplan-list",
    ),
    path(
        "wochenplaene/<int:pk>/",
        views.WochenplanDetailView.as_view(),
        name="mobile-wochenplan-detail",
    ),

    # Aktionen (nested unter Wochenplan)
    path(
        "wochenplaene/<int:wochenplan_id>/aktionen/",
        views.AktionListCreateView.as_view(),
        name="mobile-aktion-list",
    ),
    path(
        "aktionen/<int:pk>/",
        views.AktionDetailView.as_view(),
        name="mobile-aktion-detail",
    ),

    # Personalisierter Tagesplan
    path(
        "camps/<int:camp_id>/tagesplan/<int:wochentag>/",
        views.mein_tagesplan,
        name="mobile-tagesplan",
    ),
]
