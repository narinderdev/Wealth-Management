import json
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_POST
from .view_services import user_view


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
