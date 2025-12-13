from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from management.views.summary import _build_borrower_summary


@login_required(login_url="login")
def collateral_dynamic_view(request):
    borrower_profile = getattr(request.user, "borrower_profile", None)
    borrower = borrower_profile.borrower if borrower_profile else None

    section = request.GET.get("section", "inventory")
    allowed_sections = {"overview", "accounts_receivable", "inventory"}
    if section not in allowed_sections:
        section = "inventory"

    inventory_tab = request.GET.get("inventory_tab", "summary")
    allowed_inventory_tabs = {
        "summary",
        "finished_goods",
        "raw_materials",
        "work_in_progress",
        "liquidation_model",
        "other_collateral",
    }
    if inventory_tab not in allowed_inventory_tabs:
        inventory_tab = "summary"

    context = {
        "borrower_summary": _build_borrower_summary(borrower),
        "active_section": section,
        "inventory_tab": inventory_tab,
        "active_tab": "collateral_dynamic",
    }
    return render(request, "collateral_dynamic/inventory_page.html", context)
