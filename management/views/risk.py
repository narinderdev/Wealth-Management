from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from management.views.summary import _build_borrower_summary


def _borrower_context(request):
    borrower_profile = getattr(request.user, "borrower_profile", None)
    borrower = borrower_profile.borrower if borrower_profile else None
    return {"borrower_summary": _build_borrower_summary(borrower)}


@login_required(login_url="login")
def risk_view(request):
    return render(request, "risk/risk.html", _borrower_context(request))
