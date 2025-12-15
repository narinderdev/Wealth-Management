from django.shortcuts import render


def admin_borrower_view(request):
    """
    Render static borrower admin form shell.
    """
    return render(
        request,
        "admin/borrower_form.html",
        {
            "active_nav": "borrower",
        },
    )
