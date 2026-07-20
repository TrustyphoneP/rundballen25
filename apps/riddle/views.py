"""
Views fuer das Rundballen-Raetsel.

/riddle               -- riddle_home   (Anleitung ODER aktuelles Bild)
/<year>/              -- year_page     (Textinhalt wenn Jahreszahl korrekt & aktiv,
                                        sonst Sperre. Kein Formular: Spieler tippen
                                        die Jahreszahl selbst in die Adressleiste.)
/riddle/admin/        -- riddle_admin  (Spielleiter-Dashboard, staff only)
/riddle/admin/action/ -- admin_action  (POST fuer Admin-Aktionen)
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib import messages

from .models import RiddleStage, RiddleState, PlayerBan


def _get_client_ip(request):
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _is_staff(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


# ---------------------------------------------------------------------------
# /riddle -- Startseite / aktuelles Bild
# ---------------------------------------------------------------------------
def riddle_home(request):
    state = RiddleState.get()
    ip = _get_client_ip(request)
    ban = PlayerBan.get_ban(ip)

    ctx = {
        "state": state,
        "ban": ban,
        "stage": state.current_riddle(),
    }
    return render(request, "riddle/home.html", ctx)


# ---------------------------------------------------------------------------
# /<year>/ -- Textinhalt (kein "riddle" in der URL)
#
# GET:  Spieler tippen die Jahreszahl selbst in die Adressleiste. Jede
#       Jahreszahl, die nicht exakt der aktuellen Loesung entspricht,
#       fuehrt zur Sperre.
# POST: Antwort auf das Textraetsel. Korrekt -> Antwortstring wird angezeigt.
#       Falsch -> Fehlermeldung, KEINE Sperre (Sperren gelten nur fuer
#       Jahreszahlen).
# ---------------------------------------------------------------------------
def year_page(request, year: int):
    ip = _get_client_ip(request)

    ban = PlayerBan.get_ban(ip)
    if ban:
        return render(request, "riddle/banned.html", {"ban": ban})

    state = RiddleState.get()
    if not state.is_active():
        return redirect("riddle:home")

    stage = state.current_riddle()

    if not stage or stage.solution_year != year:
        ban = PlayerBan.create_ban(ip, wrong_year=year)
        return render(request, "riddle/banned.html", {"ban": ban})

    ctx = {
        "stage": stage,
        "state": state,
        "answer_correct": False,
        "answer_wrong": False,
        "entered_answer": "",
    }

    if request.method == "POST":
        entered = request.POST.get("antwort", "")
        ctx["entered_answer"] = entered
        if stage.check_text_solution(entered):
            ctx["answer_correct"] = True
        else:
            ctx["answer_wrong"] = True

    return render(request, "riddle/year_page.html", ctx)


# ---------------------------------------------------------------------------
# /riddle/admin/ -- Spielleiter-Dashboard
# ---------------------------------------------------------------------------
@login_required
@user_passes_test(_is_staff, login_url="/accounts/login/")
def riddle_admin(request):
    state = RiddleState.get()
    stages = RiddleStage.objects.all()
    active_bans = PlayerBan.objects.filter(banned_until__gt=timezone.now()).count()
    ctx = {
        "state": state,
        "stages": stages,
        "current_stage": state.current_riddle(),
        "can_advance": 1 <= state.current_stage <= 3,
        "can_start": state.current_stage == 0,
        "is_finished": state.is_finished(),
        "active_bans": active_bans,
    }
    return render(request, "riddle/admin.html", ctx)


# ---------------------------------------------------------------------------
# /riddle/admin/action/ -- POST-Handler fuer Admin-Aktionen
# ---------------------------------------------------------------------------
@require_POST
@login_required
@user_passes_test(_is_staff, login_url="/accounts/login/")
def admin_action(request):
    state = RiddleState.get()
    action = request.POST.get("action")

    if action == "start" and state.current_stage == 0:
        state.current_stage = 1
        state.started_at = timezone.now()
        state.save()
        messages.success(request, "Spiel gestartet. Stufe 1 ist aktiv.")

    elif action == "advance" and 1 <= state.current_stage <= 3:
        state.current_stage += 1
        state.save()
        messages.success(
            request, f"Naechste Stufe freigeschaltet: Stufe {state.current_stage}."
        )

    elif action == "finish" and state.current_stage == 4:
        state.current_stage = 5
        state.save()
        messages.success(request, "Spiel beendet.")

    elif action == "reset":
        state.current_stage = 0
        state.started_at = None
        state.save()
        messages.warning(request, "Spiel zurueckgesetzt.")

    elif action == "save_stage":
        stage_order = int(request.POST.get("stage_order", 0))
        try:
            stage = RiddleStage.objects.get(order=stage_order)
            stage.hint = request.POST.get("hint", "").strip()
            stage.text_solution = request.POST.get("text_solution", "").strip()
            stage.text_response = request.POST.get("text_response", "").strip()
            stage.save(update_fields=["hint", "text_solution", "text_response"])
            messages.success(request, f"Stufe {stage_order} gespeichert.")
        except RiddleStage.DoesNotExist:
            messages.error(request, "Stufe nicht gefunden.")

    elif action == "clear_bans":
        PlayerBan.objects.all().delete()
        messages.success(request, "Alle Sperren aufgehoben.")

    return redirect("riddle:admin")
