from rest_framework import serializers
from django.contrib.auth import get_user_model`nUser = get_user_model()
from .models import MobileUserProfile, Wochenplan, Aktion


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, data):
        if data["new_password"] != data["new_password_confirm"]:
            raise serializers.ValidationError("Passwoerter stimmen nicht ueberein.")
        return data


class UserSerializer(serializers.ModelSerializer):
    force_password_reset = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "force_password_reset"]

    def get_force_password_reset(self, obj):
        profile = getattr(obj, "mobile_profile", None)
        if profile is None:
            # Profil noch nicht angelegt -> erstmalig -> True
            return True
        return profile.force_password_reset


# ---------------------------------------------------------------------------
# Camp (liest aus bestehendem Camp-Model)
# ---------------------------------------------------------------------------

class CampSerializer(serializers.Serializer):
    """
    Liest aus dem bestehenden Camp-Model (apps.camps.models.Camp oder aehnlich).
    Felder werden dynamisch gemappt -- anpassen falls das Model anders heisst.
    """
    id = serializers.IntegerField()
    name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()


# ---------------------------------------------------------------------------
# Betreuer / Teilis (aus bestehendem User-Model)
# ---------------------------------------------------------------------------

class BetreuerlSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]


# ---------------------------------------------------------------------------
# Wochenplan + Aktion
# ---------------------------------------------------------------------------

class AktionSerializer(serializers.ModelSerializer):
    verantwortlich = BetreuerlSerializer(many=True, read_only=True)
    verantwortlich_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        many=True,
        write_only=True,
        source="verantwortlich",
        required=False,
    )
    wochentag_name = serializers.CharField(source="get_wochentag_display", read_only=True)
    kategorie_name = serializers.CharField(source="get_kategorie_display", read_only=True)

    class Meta:
        model = Aktion
        fields = [
            "id", "wochenplan", "wochentag", "wochentag_name",
            "titel", "beschreibung", "kategorie", "kategorie_name",
            "beginn_stunde", "beginn_minute", "ende_stunde", "ende_minute",
            "ort", "verantwortlich", "verantwortlich_ids",
        ]
        read_only_fields = ["id"]


class WochenplanListSerializer(serializers.ModelSerializer):
    aktionen_count = serializers.SerializerMethodField()

    class Meta:
        model = Wochenplan
        fields = ["id", "camp_id", "titel", "erstellt_am", "aktionen_count"]

    def get_aktionen_count(self, obj):
        return obj.aktionen.count()


class WochenplanDetailSerializer(serializers.ModelSerializer):
    aktionen = AktionSerializer(many=True, read_only=True)

    class Meta:
        model = Wochenplan
        fields = ["id", "camp_id", "titel", "erstellt_am", "geaendert_am", "aktionen"]
        read_only_fields = ["id", "erstellt_am", "geaendert_am"]
