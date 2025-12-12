from __future__ import annotations

import json
from typing import Any, Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render

from ..services.auth_service import authenticate_by_identifier, ensure_static_user
from ..services.user_service import register_client


def _static_login_identity() -> Optional[str]:
    """Expose the configured static login identifier for the UI."""
    return getattr(settings, "STATIC_LOGIN_EMAIL", getattr(settings, "STATIC_LOGIN_USERNAME", None))


def _static_login_password() -> Optional[str]:
    """Expose the configured static login password for the UI."""
    return getattr(settings, "STATIC_LOGIN_PASSWORD", None)


def login(request):
    """Render or process the login form."""
    ensure_static_user()
    if request.user.is_authenticated:
        return redirect("dashboard")

    error_message = None
    if request.method == "POST":
        identifier = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user = authenticate_by_identifier(request, identifier, password)
        if user:
            auth_login(request, user)
            return redirect("dashboard")

        error_message = "Invalid email or password."

    context = {
        "error_message": error_message,
        "static_login_identity": _static_login_identity(),
        "static_login_password": _static_login_password(),
    }
    return render(request, "login.html", context)


def dashboard(request):
    """Render the dashboard page for authenticated users."""
    return render(request, "dashboard.html", {"user": request.user})


def logout(request):
    """Log the user out and flash a success message."""
    auth_logout(request)
    messages.success(request, "You have been signed out.")
    return redirect("login")
