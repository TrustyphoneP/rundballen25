from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import render, redirect
from django.contrib import messages


@login_required
def force_password_change(request):
    """Erzwingt Passwortänderung beim ersten Login."""
    if not request.user.must_change_password:
        return redirect("camps:dashboard")

    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            user.must_change_password = False
            user.save(update_fields=["must_change_password"])
            update_session_auth_hash(request, user)
            messages.success(request, "Passwort erfolgreich geändert.")
            return redirect("camps:dashboard")
    else:
        form = PasswordChangeForm(request.user)

    return render(request, "accounts/force_password_change.html", {"form": form})
