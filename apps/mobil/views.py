import secrets
from datetime import date

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.camps.models import Camp
from apps.mobile_api.models import Wochenplan, Aktion, WOCHENTAG_CHOICES

from .forms import WochenplanForm, AktionForm, GruppeForm, RegistrierungForm, ChecklisteForm
from .models import FreizeitMitglied, Gruppe, FreizeitZugang, Checkliste, ChecklistenPunkt, PunktErledigt

SESSION_CAMP_KEY = "mobil_camp_id"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def kann_bearbeiten(user):
    """Leitung, Admin (root) und Staff dürfen verwalten."""
    return user.is_authenticated and (user.is_leitung() or user.is_staff)


def aktive_freizeit(request):
    """Aktuell in der Session gewählte Freizeit, sonst einzige Mitgliedschaft."""
    camp_id = request.session.get(SESSION_CAMP_KEY)
    qs = Camp.objects.filter(is_active=True)
    if camp_id:
        camp = qs.filter(pk=camp_id).first()
        if camp:
            return camp
    mitgliedschaften = FreizeitMitglied.objects.filter(
        user=request.user, camp__is_active=True
    ).select_related("camp")
    if mitgliedschaften.count() == 1:
        camp = mitgliedschaften.first().camp
        request.session[SESSION_CAMP_KEY] = camp.pk
        return camp
    return None


def zeitspanne(a):
    return f"{a.beginn_stunde:02d}:{a.beginn_minute:02d}–{a.ende_stunde:02d}:{a.ende_minute:02d}"


def aktionen_fuer_tag(camp, user, wochentag):
    """
    Individualisierter Tagesplan:
    - Aktionen ohne Verantwortliche UND ohne Gruppen gelten für alle
    - plus Aktionen, bei denen der Nutzer verantwortlich ist
    - plus Aktionen, an denen die Gruppe des Nutzers teilnimmt
    """
    basis = Aktion.objects.filter(
        wochenplan__camp_id=camp.pk, wochentag=wochentag
    )
    alle = basis.filter(verantwortlich__isnull=True, gruppen__isnull=True)
    meine = basis.filter(verantwortlich=user)

    mitglied = FreizeitMitglied.objects.filter(user=user, camp=camp).first()
    if mitglied and mitglied.gruppe_id:
        gruppe = basis.filter(gruppen=mitglied.gruppe_id)
    else:
        gruppe = basis.none()

    return (
        (alle | meine | gruppe)
        .distinct()
        .prefetch_related("verantwortlich", "gruppen")
        .order_by("beginn_stunde", "beginn_minute")
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login_view(request):
    if request.user.is_authenticated:
        return redirect("mobil:heute")
    error = None
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", "").strip(),
            password=request.POST.get("password", ""),
        )
        if user is None:
            error = "Benutzername oder Passwort falsch."
        elif not user.is_active:
            error = "Dieser Account ist deaktiviert."
        else:
            login(request, user)
            if getattr(user, "must_change_password", False):
                return redirect("mobil:passwort")
            return redirect("mobil:heute")
    return render(request, "mobil/login.html", {"error": error})


def registrieren_view(request):
    """Selbstregistrierung mit Freizeit-Zugangscode."""
    if request.user.is_authenticated:
        return redirect("mobil:heute")

    if request.method == "POST":
        form = RegistrierungForm(request.POST)
        if form.is_valid():
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password1"],
                first_name=form.cleaned_data["name"],
                role="supervisor",
            )
            camp = form.zugang.camp
            FreizeitMitglied.objects.create(user=user, camp=camp)
            login(request, user)
            request.session[SESSION_CAMP_KEY] = camp.pk
            messages.success(
                request,
                f"Willkommen, {user.first_name}! Du bist mit „{camp.name}“ verbunden.",
            )
            return redirect("mobil:heute")
    else:
        form = RegistrierungForm()
    return render(request, "mobil/registrieren.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("mobil:login")


@login_required
def passwort_view(request):
    """
    Passwort setzen. Wird beim ersten Login erzwungen
    (must_change_password) und kann jederzeit freiwillig genutzt werden.
    """
    erzwungen = getattr(request.user, "must_change_password", False)
    if request.method == "POST":
        form = SetPasswordForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            user.must_change_password = False
            user.save(update_fields=["must_change_password"])
            update_session_auth_hash(request, user)
            messages.success(request, "Passwort gespeichert.")
            return redirect("mobil:heute")
    else:
        form = SetPasswordForm(request.user)
    return render(request, "mobil/passwort.html", {"form": form, "erzwungen": erzwungen})


# ---------------------------------------------------------------------------
# Freizeiten
# ---------------------------------------------------------------------------

@login_required
def freizeiten_view(request):
    camps = Camp.objects.filter(is_active=True)
    meine_ids = set(
        FreizeitMitglied.objects.filter(user=request.user).values_list("camp_id", flat=True)
    )
    aktive_id = request.session.get(SESSION_CAMP_KEY)
    return render(request, "mobil/freizeiten.html", {
        "camps": camps,
        "meine_ids": meine_ids,
        "aktive_id": aktive_id,
    })


@login_required
def freizeit_beitreten(request, camp_pk):
    camp = get_object_or_404(Camp, pk=camp_pk, is_active=True)
    if request.method == "POST":
        FreizeitMitglied.objects.get_or_create(user=request.user, camp=camp)
        request.session[SESSION_CAMP_KEY] = camp.pk
        messages.success(request, f"Du bist jetzt mit „{camp.name}“ verbunden.")
    return redirect("mobil:freizeiten")


@login_required
def freizeit_waehlen(request, camp_pk):
    camp = get_object_or_404(Camp, pk=camp_pk, is_active=True)
    request.session[SESSION_CAMP_KEY] = camp.pk
    return redirect("mobil:heute")


# ---------------------------------------------------------------------------
# Tagesplan / Wochenplan (Ansicht)
# ---------------------------------------------------------------------------

@login_required
def heute_view(request):
    camp = aktive_freizeit(request)
    if camp is None:
        return redirect("mobil:freizeiten")

    try:
        wochentag = int(request.GET.get("tag", date.today().weekday()))
    except (TypeError, ValueError):
        wochentag = date.today().weekday()
    wochentag = max(0, min(6, wochentag))

    aktionen = aktionen_fuer_tag(camp, request.user, wochentag)
    return render(request, "mobil/heute.html", {
        "camp": camp,
        "aktionen": [(a, zeitspanne(a)) for a in aktionen],
        "wochentag": wochentag,
        "wochentage": WOCHENTAG_CHOICES,
        "ist_heute": wochentag == date.today().weekday(),
        "kann_bearbeiten": kann_bearbeiten(request.user),
    })


@login_required
def woche_view(request):
    camp = aktive_freizeit(request)
    if camp is None:
        return redirect("mobil:freizeiten")

    plaene = Wochenplan.objects.filter(camp_id=camp.pk).prefetch_related(
        "aktionen__verantwortlich"
    )
    tage = []
    for nr, name in WOCHENTAG_CHOICES:
        aktionen = (
            Aktion.objects.filter(wochenplan__camp_id=camp.pk, wochentag=nr)
            .prefetch_related("verantwortlich", "gruppen")
            .order_by("beginn_stunde", "beginn_minute")
        )
        tage.append((nr, name, [(a, zeitspanne(a)) for a in aktionen]))

    return render(request, "mobil/woche.html", {
        "camp": camp,
        "plaene": plaene,
        "tage": tage,
        "heute_nr": date.today().weekday(),
        "kann_bearbeiten": kann_bearbeiten(request.user),
    })


# ---------------------------------------------------------------------------
# Wochenplan / Aktionen (Bearbeitung)
# ---------------------------------------------------------------------------

@login_required
def plan_anlegen(request):
    camp = aktive_freizeit(request)
    if camp is None:
        return redirect("mobil:freizeiten")
    if not kann_bearbeiten(request.user):
        messages.error(request, "Keine Berechtigung zum Bearbeiten.")
        return redirect("mobil:woche")

    if request.method == "POST":
        form = WochenplanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.camp_id = camp.pk
            plan.save()
            messages.success(request, f"Wochenplan „{plan.titel}“ angelegt.")
            return redirect("mobil:woche")
    else:
        form = WochenplanForm()
    return render(request, "mobil/plan_form.html", {"form": form, "camp": camp})


@login_required
def aktion_anlegen(request):
    camp = aktive_freizeit(request)
    if camp is None:
        return redirect("mobil:freizeiten")
    if not kann_bearbeiten(request.user):
        messages.error(request, "Keine Berechtigung zum Bearbeiten.")
        return redirect("mobil:woche")

    plan = Wochenplan.objects.filter(camp_id=camp.pk).first()
    if plan is None:
        plan = Wochenplan.objects.create(camp_id=camp.pk, titel="Wochenplan")

    initial = {}
    try:
        initial["wochentag"] = int(request.GET.get("tag", ""))
    except (TypeError, ValueError):
        pass

    if request.method == "POST":
        form = AktionForm(request.POST, camp=camp)
        if form.is_valid():
            aktion = form.save(commit=False)
            aktion.wochenplan = plan
            aktion.save()
            form.save_m2m()
            aktion.gruppen.set(form.cleaned_data["gruppen"])
            messages.success(request, f"Aktion „{aktion.titel}“ gespeichert.")
            return redirect(f"/mobil/heute/?tag={aktion.wochentag}")
    else:
        form = AktionForm(camp=camp, initial=initial)
    return render(request, "mobil/aktion_form.html", {
        "form": form, "camp": camp, "aktion": None,
    })


@login_required
def aktion_bearbeiten(request, pk):
    camp = aktive_freizeit(request)
    if camp is None:
        return redirect("mobil:freizeiten")
    if not kann_bearbeiten(request.user):
        messages.error(request, "Keine Berechtigung zum Bearbeiten.")
        return redirect("mobil:woche")

    aktion = get_object_or_404(Aktion, pk=pk, wochenplan__camp_id=camp.pk)

    if request.method == "POST":
        if request.POST.get("loeschen") == "1":
            tag = aktion.wochentag
            aktion.delete()
            messages.success(request, "Aktion gelöscht.")
            return redirect(f"/mobil/heute/?tag={tag}")
        form = AktionForm(request.POST, instance=aktion, camp=camp)
        if form.is_valid():
            aktion = form.save()
            aktion.gruppen.set(form.cleaned_data["gruppen"])
            messages.success(request, f"Aktion „{aktion.titel}“ aktualisiert.")
            return redirect(f"/mobil/heute/?tag={aktion.wochentag}")
    else:
        form = AktionForm(instance=aktion, camp=camp)
    return render(request, "mobil/aktion_form.html", {
        "form": form, "camp": camp, "aktion": aktion,
    })


# ---------------------------------------------------------------------------
# Profil
# ---------------------------------------------------------------------------

@login_required
def profil_view(request):
    mitgliedschaften = FreizeitMitglied.objects.filter(
        user=request.user
    ).select_related("camp")
    return render(request, "mobil/profil.html", {
        "mitgliedschaften": mitgliedschaften,
    })


# ---------------------------------------------------------------------------
# Gruppen (zentrale Verwaltung)
# ---------------------------------------------------------------------------

@login_required
def gruppen_view(request):
    camp = aktive_freizeit(request)
    if camp is None:
        return redirect("mobil:freizeiten")
    if not kann_bearbeiten(request.user):
        messages.error(request, "Keine Berechtigung für die Gruppenverwaltung.")
        return redirect("mobil:heute")

    form = GruppeForm()

    if request.method == "POST":
        aktion = request.POST.get("aktion")

        if aktion == "anlegen":
            form = GruppeForm(request.POST)
            if form.is_valid():
                gruppe = form.save(commit=False)
                gruppe.camp = camp
                try:
                    gruppe.save()
                    messages.success(request, f"Gruppe „{gruppe.name}“ angelegt.")
                    return redirect("mobil:gruppen")
                except Exception:
                    form.add_error("name", "Diese Gruppe gibt es bereits.")

        elif aktion == "loeschen":
            gruppe = get_object_or_404(Gruppe, pk=request.POST.get("gruppe_id"), camp=camp)
            name = gruppe.name
            gruppe.delete()
            messages.success(request, f"Gruppe „{name}“ gelöscht.")
            return redirect("mobil:gruppen")

        elif aktion == "code_setzen":
            code = request.POST.get("code", "").strip()
            if code:
                if FreizeitZugang.objects.filter(code__iexact=code).exclude(camp=camp).exists():
                    messages.error(request, "Dieser Code wird schon von einer anderen Freizeit genutzt.")
                else:
                    FreizeitZugang.objects.update_or_create(
                        camp=camp, defaults={"code": code, "aktiv": True}
                    )
                    messages.success(request, f"Zugangscode „{code}“ gespeichert.")
            return redirect("mobil:gruppen")

        elif aktion == "code_generieren":
            code = secrets.token_hex(3).upper()
            while FreizeitZugang.objects.filter(code__iexact=code).exists():
                code = secrets.token_hex(3).upper()
            FreizeitZugang.objects.update_or_create(
                camp=camp, defaults={"code": code, "aktiv": True}
            )
            messages.success(request, f"Neuer Zugangscode: {code}")
            return redirect("mobil:gruppen")

        elif aktion == "code_toggle":
            zugang = FreizeitZugang.objects.filter(camp=camp).first()
            if zugang:
                zugang.aktiv = not zugang.aktiv
                zugang.save(update_fields=["aktiv"])
                status = "offen" if zugang.aktiv else "geschlossen"
                messages.success(request, f"Registrierung ist jetzt {status}.")
            return redirect("mobil:gruppen")

        elif aktion == "rolle_setzen":
            mitglied = get_object_or_404(
                FreizeitMitglied, pk=request.POST.get("mitglied_id"), camp=camp
            )
            neue_rolle = request.POST.get("rolle")
            erlaubte = ["supervisor", "kitchen", "leitung"]
            if request.user.is_admin():
                erlaubte.append("admin")
            ziel = mitglied.user
            if ziel.is_admin() and not request.user.is_admin():
                messages.error(request, "Nur Admin (root) kann Admin-Rollen ändern.")
            elif neue_rolle in erlaubte:
                ziel.role = neue_rolle
                ziel.save(update_fields=["role"])
                messages.success(
                    request,
                    f"{ziel.first_name or ziel.username} ist jetzt {ziel.get_role_display()}.",
                )
            else:
                messages.error(request, "Diese Rolle darfst du nicht vergeben.")
            return redirect("mobil:gruppen")

        elif aktion == "zuordnen":
            mitglied = get_object_or_404(
                FreizeitMitglied, pk=request.POST.get("mitglied_id"), camp=camp
            )
            gruppe_id = request.POST.get("gruppe_id") or None
            if gruppe_id:
                mitglied.gruppe = get_object_or_404(Gruppe, pk=gruppe_id, camp=camp)
            else:
                mitglied.gruppe = None
            mitglied.save(update_fields=["gruppe"])
            messages.success(request, "Zuordnung gespeichert.")
            return redirect("mobil:gruppen")

    gruppen = Gruppe.objects.filter(camp=camp).prefetch_related("mitglieder__user")
    mitglieder = (
        FreizeitMitglied.objects.filter(camp=camp)
        .select_related("user", "gruppe")
        .order_by("user__first_name", "user__username")
    )
    return render(request, "mobil/gruppen.html", {
        "camp": camp,
        "form": form,
        "gruppen": gruppen,
        "mitglieder": mitglieder,
        "zugang": FreizeitZugang.objects.filter(camp=camp).first(),
        "rollen": (
            [("supervisor", "Betreuer"), ("kitchen", "Küche"), ("leitung", "Leitung")]
            + ([("admin", "Admin (root)")] if request.user.is_admin() else [])
        ),
    })


# ---------------------------------------------------------------------------
# Checklisten
# ---------------------------------------------------------------------------

def _sichtbare_checklisten(camp, user):
    qs = Checkliste.objects.filter(camp=camp).prefetch_related("punkte")
    return [c for c in qs if c.sichtbar_fuer_user(user)]


@login_required
def checklisten_view(request):
    camp = aktive_freizeit(request)
    if camp is None:
        return redirect("mobil:freizeiten")

    listen = _sichtbare_checklisten(camp, request.user)
    erledigt_ids = set(
        PunktErledigt.objects.filter(
            user=request.user, punkt__checkliste__camp=camp
        ).values_list("punkt_id", flat=True)
    )
    daten = []
    for liste in listen:
        punkte = list(liste.punkte.all())
        fertig = sum(1 for p in punkte if p.pk in erledigt_ids)
        daten.append((liste, fertig, len(punkte)))

    return render(request, "mobil/checklisten.html", {
        "camp": camp,
        "daten": daten,
        "kann_bearbeiten": kann_bearbeiten(request.user),
    })


@login_required
def checkliste_detail(request, pk):
    camp = aktive_freizeit(request)
    if camp is None:
        return redirect("mobil:freizeiten")
    liste = get_object_or_404(Checkliste, pk=pk, camp=camp)
    if not liste.sichtbar_fuer_user(request.user):
        messages.error(request, "Diese Checkliste ist für dich nicht sichtbar.")
        return redirect("mobil:checklisten")

    if request.method == "POST":
        punkt = get_object_or_404(ChecklistenPunkt, pk=request.POST.get("punkt_id"), checkliste=liste)
        haken = PunktErledigt.objects.filter(punkt=punkt, user=request.user)
        if haken.exists():
            haken.delete()
        else:
            PunktErledigt.objects.create(punkt=punkt, user=request.user)
        return redirect("mobil:checkliste", pk=liste.pk)

    erledigt_ids = set(
        PunktErledigt.objects.filter(
            user=request.user, punkt__checkliste=liste
        ).values_list("punkt_id", flat=True)
    )
    punkte = [(p, p.pk in erledigt_ids) for p in liste.punkte.all()]
    return render(request, "mobil/checkliste_detail.html", {
        "camp": camp,
        "liste": liste,
        "punkte": punkte,
        "fertig": sum(1 for _, e in punkte if e),
        "kann_bearbeiten": kann_bearbeiten(request.user),
    })


@login_required
def checkliste_verwalten(request, pk=None):
    """Anlegen und Bearbeiten einer Checkliste inkl. Punkte (Leitung/Admin)."""
    camp = aktive_freizeit(request)
    if camp is None:
        return redirect("mobil:freizeiten")
    if not kann_bearbeiten(request.user):
        messages.error(request, "Keine Berechtigung für Checklisten-Verwaltung.")
        return redirect("mobil:checklisten")

    liste = get_object_or_404(Checkliste, pk=pk, camp=camp) if pk else None

    if request.method == "POST":
        aktion = request.POST.get("aktion")

        if aktion == "speichern":
            form = ChecklisteForm(request.POST, instance=liste)
            if form.is_valid():
                neu = liste is None
                liste = form.save(commit=False)
                liste.camp = camp
                liste.save()
                messages.success(
                    request,
                    f"Checkliste „{liste.titel}“ {'angelegt' if neu else 'gespeichert'}.",
                )
                return redirect("mobil:checkliste_verwalten", pk=liste.pk)

        elif aktion == "loeschen" and liste:
            titel = liste.titel
            liste.delete()
            messages.success(request, f"Checkliste „{titel}“ gelöscht.")
            return redirect("mobil:checklisten")

        elif aktion == "punkt_hinzufuegen" and liste:
            text = request.POST.get("text", "").strip()
            if text:
                max_rf = liste.punkte.count()
                ChecklistenPunkt.objects.create(
                    checkliste=liste, text=text, reihenfolge=max_rf + 1
                )
            return redirect("mobil:checkliste_verwalten", pk=liste.pk)

        elif aktion == "punkt_loeschen" and liste:
            get_object_or_404(
                ChecklistenPunkt, pk=request.POST.get("punkt_id"), checkliste=liste
            ).delete()
            return redirect("mobil:checkliste_verwalten", pk=liste.pk)

    form = ChecklisteForm(instance=liste)
    return render(request, "mobil/checkliste_verwalten.html", {
        "camp": camp,
        "liste": liste,
        "form": form,
    })


# ---------------------------------------------------------------------------
# Wochenplan CSV-Import
# ---------------------------------------------------------------------------

@login_required
def plan_import(request):
    """Wochenplan per CSV hochladen (Leitung/Admin)."""
    from .csv_import import csv_parsen, csv_importieren

    camp = aktive_freizeit(request)
    if camp is None:
        return redirect("mobil:freizeiten")
    if not kann_bearbeiten(request.user):
        messages.error(request, "Keine Berechtigung für den Import.")
        return redirect("mobil:woche")

    fehler = []
    if request.method == "POST":
        datei = request.FILES.get("datei")
        ersetzen = request.POST.get("ersetzen") == "1"
        if datei is None:
            fehler = ["Bitte eine CSV-Datei auswählen."]
        elif datei.size > 1024 * 1024:
            fehler = ["Die Datei ist größer als 1 MB."]
        else:
            aktionen, fehler = csv_parsen(datei.read(), camp)
            if not fehler:
                anzahl = csv_importieren(aktionen, camp, ersetzen=ersetzen)
                if ersetzen:
                    messages.success(
                        request,
                        f"Wochenplan ersetzt: {anzahl} Aktionen importiert.",
                    )
                else:
                    messages.success(request, f"{anzahl} Aktionen importiert.")
                return redirect("mobil:woche")

    anzahl_aktionen = Aktion.objects.filter(wochenplan__camp_id=camp.pk).count()
    return render(request, "mobil/plan_import.html", {
        "camp": camp,
        "fehler": fehler,
        "anzahl_aktionen": anzahl_aktionen,
    })


@login_required
def plan_import_vorlage(request):
    """CSV-Vorlage zum Herunterladen."""
    from .csv_import import VORLAGE
    antwort = HttpResponse(
        VORLAGE.encode("utf-8-sig"),  # BOM, damit Excel Umlaute korrekt zeigt
        content_type="text/csv; charset=utf-8",
    )
    antwort["Content-Disposition"] = 'attachment; filename="wochenplan_vorlage.csv"'
    return antwort
