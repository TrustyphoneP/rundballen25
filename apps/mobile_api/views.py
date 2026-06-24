from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from .models import MobileUserProfile, Wochenplan, Aktion
from .serializers import (
    LoginSerializer, ChangePasswordSerializer, UserSerializer,
    BetreuerlSerializer, WochenplanListSerializer, WochenplanDetailSerializer,
    AktionSerializer,
)


def get_or_create_profile(user):
    profile, _ = MobileUserProfile.objects.get_or_create(user=user)
    return profile


# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = authenticate(
        username=serializer.validated_data["username"],
        password=serializer.validated_data["password"],
    )

    if user is None:
        return Response(
            {"detail": "Benutzername oder Passwort falsch."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        return Response(
            {"detail": "Dieser Account ist deaktiviert."},
            status=status.HTTP_403_FORBIDDEN,
        )

    profile = get_or_create_profile(user)
    refresh = RefreshToken.for_user(user)

    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "force_password_reset": profile.force_password_reset,
        "user": UserSerializer(user).data,
    })


@api_view(["POST"])
def change_password_view(request):
    serializer = ChangePasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = request.user
    user.set_password(serializer.validated_data["new_password"])
    user.save()

    profile = get_or_create_profile(user)
    profile.force_password_reset = False
    profile.save()

    refresh = RefreshToken.for_user(user)
    return Response({
        "detail": "Passwort erfolgreich geaendert.",
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    })


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def token_refresh_view(request):
    from rest_framework_simplejwt.serializers import TokenRefreshSerializer
    serializer = TokenRefreshSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(serializer.validated_data)


@api_view(["GET"])
def me_view(request):
    return Response(UserSerializer(request.user).data)


# ---------------------------------------------------------------------------
# CAMPS (liest aus bestehendem Camp-Model)
# ---------------------------------------------------------------------------

@api_view(["GET"])
def camps_view(request):
    """
    Gibt alle Camps zurueck. Liest aus dem bestehenden Camp-Model.
    ANPASSEN: Import-Pfad und Feldnamen auf dein tatsaechliches Camp-Model.
    """
    try:
        # Anpassen an deinen tatsaechlichen Import-Pfad:
        from apps.camps.models import Camp  # <-- ggf. anpassen
        camps = Camp.objects.all().order_by("-start_date")
        data = [
            {
                "id": c.id,
                "name": c.name,
                "start_date": str(c.start_date),
                "end_date": str(c.end_date),
            }
            for c in camps
        ]
        return Response(data)
    except ImportError:
        # Fallback falls Camp-Model noch nicht gefunden --
        # gibt das aktive Camp hart kodiert zurueck
        return Response([
            {
                "id": 1,
                "name": "Rheinstrasse 2026",
                "start_date": "2026-07-22",
                "end_date": "2026-07-28",
            }
        ])


# ---------------------------------------------------------------------------
# BETREUER
# ---------------------------------------------------------------------------

@api_view(["GET"])
def betreuer_list_view(request):
    """
    Alle aktiven Betreuer (Staff-User oder nach Gruppe filtern).
    ANPASSEN: Filter auf deine tatsaechliche Betreuer-Logik.
    """
    # Variante 1: Alle Staff-User
    betreuer = User.objects.filter(is_active=True, is_staff=True).order_by("last_name", "first_name")

    # Variante 2: Falls Betreuer eine eigene Gruppe haben:
    # betreuer = User.objects.filter(groups__name="Betreuer", is_active=True)

    return Response(BetreuerlSerializer(betreuer, many=True).data)


# ---------------------------------------------------------------------------
# WOCHENPLAENE
# ---------------------------------------------------------------------------

class WochenplanListCreateView(generics.ListCreateAPIView):
    def get_serializer_class(self):
        return WochenplanListSerializer if self.request.method == "GET" else WochenplanDetailSerializer

    def get_queryset(self):
        camp_id = self.kwargs.get("camp_id")
        qs = Wochenplan.objects.prefetch_related("aktionen")
        if camp_id:
            qs = qs.filter(camp_id=camp_id)
        return qs

    def perform_create(self, serializer):
        camp_id = self.kwargs.get("camp_id")
        serializer.save(camp_id=camp_id)


class WochenplanDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WochenplanDetailSerializer
    queryset = Wochenplan.objects.prefetch_related("aktionen__verantwortlich")


# ---------------------------------------------------------------------------
# AKTIONEN
# ---------------------------------------------------------------------------

class AktionListCreateView(generics.ListCreateAPIView):
    serializer_class = AktionSerializer

    def get_queryset(self):
        return Aktion.objects.filter(
            wochenplan_id=self.kwargs["wochenplan_id"]
        ).prefetch_related("verantwortlich")

    def perform_create(self, serializer):
        serializer.save(wochenplan_id=self.kwargs["wochenplan_id"])


class AktionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AktionSerializer
    queryset = Aktion.objects.prefetch_related("verantwortlich")


# ---------------------------------------------------------------------------
# TAGESPLAN (personalisiert)
# ---------------------------------------------------------------------------

@api_view(["GET"])
def mein_tagesplan(request, camp_id, wochentag):
    """
    Gibt den personalisierten Tagesplan für den eingeloggten Betreuer zurück:
    - Alle Aktionen ohne Verantwortlichen (= für alle)
    - Plus Aktionen, bei denen dieser Betreuer explizit eingetragen ist
    """
    # Aktionen ohne zugeordneten Betreuer (Pflichtprogramm für alle)
    alle = Aktion.objects.filter(
        wochenplan__camp_id=camp_id,
        wochentag=wochentag,
        verantwortlich__isnull=True,
    )

    # Aktionen explizit für diesen Betreuer
    meine = Aktion.objects.filter(
        wochenplan__camp_id=camp_id,
        wochentag=wochentag,
        verantwortlich=request.user,
    )

    aktionen = (alle | meine).distinct().order_by("beginn_stunde", "beginn_minute")
    return Response(AktionSerializer(aktionen, many=True).data)
