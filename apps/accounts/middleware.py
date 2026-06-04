from django.shortcuts import redirect
from django.urls import reverse

EXEMPT_URLS = (
    "/accounts/login/",
    "/accounts/logout/",
    "/accounts/passwort-aendern/",
    "/admin/",
)


class ForcePasswordChangeMiddleware:
    """
    Leitet Benutzer mit must_change_password=True zur Passwortänderung um.
    Alle anderen URLs sind gesperrt bis das Passwort geändert wurde.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and getattr(request.user, "must_change_password", False)
            and not any(request.path.startswith(url) for url in EXEMPT_URLS)
        ):
            return redirect("accounts:force_password_change")
        return self.get_response(request)
