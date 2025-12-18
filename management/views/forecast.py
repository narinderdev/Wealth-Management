
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from management.views.summary import _build_borrower_summary, get_preferred_borrower


def _borrower_context(request):
    borrower = get_preferred_borrower(request)
    return {"borrower_summary": _build_borrower_summary(borrower)}


@login_required(login_url="login")
def forecast_view(request):
    context = _borrower_context(request)
    context["active_tab"] = "forecast"
    return render(request, "forecast/forecast.html", context)
