from datetime import date

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.shortcuts import get_object_or_404, redirect, render

from apps.camps.models import Camp
from apps.mobile_api.models import Wochenplan, Aktion, WOCHENTAG_CHOICES

from .forms import WochenplanForm, AktionForm, GruppeForm
from .models import FreizeitMitglied, Gruppe

SESSION_CAMP_KEY = "mobil_camp_id"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def kann_bearbeiten(user):
    """Leitung/Admin und Staff duerfen Plaene bearbeiten."""
    return user.is_authenticated and (user.is_admin() or user.is_staff)


def aktive_freizeit(request):
    """Aktuell in der Session gewaehlte Freizeit, sonst einzige Mitgliedschaft."""
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
    - Aktionen ohne Verantwortliche UND ohne Gruppen gelten fuer alle
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
            messages.success(request, "Aktion geloescht.")
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
        messages.error(request, "Keine Berechtigung fuer die Gruppenverwaltung.")
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
            messages.success(request, f"Gruppe „{name}“ geloescht.")
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
    })
