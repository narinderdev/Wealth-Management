from django.http import HttpResponse


def home(request):
    """Return a minimal response to prove the app is configured."""
    return HttpResponse("Wealth Management app is running.")
