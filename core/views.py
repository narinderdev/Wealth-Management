from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from .view_services import user_view


def home(request):
    """Return a minimal response to prove the app is configured."""
    return HttpResponse("Wealth Management app is running.")


def login_view(request):
    return user_view.login(request)


@login_required(login_url="login")
def dashboard_view(request):
    return user_view.dashboard(request)


def logout_view(request):
    return user_view.logout(request)




