from django.shortcuts import render


def admin_dashboard_view(request):
    """
    Dashboard entry point – dedicated KPI canvas.
    """
    return render(
        request,
        "admin/dashboard.html",
        {
            "active_nav": "dashboard",
        },
    )


def admin_company_view(request):
    """
    Company data entry screen without the dashboard summary wrapper.
    """
    return render(
        request,
        "admin/company_form.html",
        {
            "show_dashboard": False,
            "active_nav": "company",
        },
    )
