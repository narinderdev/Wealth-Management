import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .view_services import user_view

User = get_user_model()


def _authenticate_by_email_or_username(request, identifier, password):
    """
    Try to authenticate by matching the provided identifier to a user email first,
    then fall back to using it as a username. This allows the login form to ask
    for an email even if the username is the actual credential.
    """
    if not identifier or not password:
        return None

    account = User.objects.filter(email__iexact=identifier).first()
    if account:
        user = authenticate(request, username=account.get_username(), password=password)
        if user:
            return user

    return authenticate(request, username=identifier, password=password)


_static_user_cache = None


def _ensure_static_user():
    global _static_user_cache
    if _static_user_cache:
        return _static_user_cache

    username = getattr(settings, "STATIC_LOGIN_USERNAME", None)
    email = getattr(settings, "STATIC_LOGIN_EMAIL", username)
    password = getattr(settings, "STATIC_LOGIN_PASSWORD", None)

    if not username or not password:
        return None

    user, created = User.objects.get_or_create(username=username, defaults={"email": email or ""})
    if created or not user.check_password(password):
        user.set_password(password)
        if email and user.email != email:
            user.email = email
        user.save()

    _static_user_cache = user
    return user


def login_view(request):
    _ensure_static_user()
    if request.user.is_authenticated:
        return redirect("dashboard")

    error_message = None
    static_identity = getattr(settings, "STATIC_LOGIN_EMAIL", getattr(settings, "STATIC_LOGIN_USERNAME", None))
    static_password = getattr(settings, "STATIC_LOGIN_PASSWORD", None)
    if request.method == "POST":
        identifier = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user = _authenticate_by_email_or_username(request, identifier, password)
        if user:
            login(request, user)
            return redirect("dashboard")

        error_message = "Invalid email or password."

    context = {
        "error_message": error_message,
        "static_login_identity": static_identity,
        "static_login_password": static_password,
    }
    return render(request, "login.html", context)


@login_required(login_url="login")
def dashboard_view(request):
    return render(request, "dashboard.html", {"user": request.user})


def logout_view(request):
    logout(request)
    messages.success(request, "You have been signed out.")
    return redirect("login")


def home(request):
    """Return a minimal response to prove the app is configured."""
    return HttpResponse("Wealth Management app is running.")


def clients_list(request):
    """Return a canned, service-backed client list payload."""
    return JsonResponse(user_view.list_clients())


@require_POST
def onboard_client(request):
    """Accept client data and send it to the onboarding view service."""
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Provided body is not valid JSON")

    return JsonResponse(user_view.onboard_client(payload))
