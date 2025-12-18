from management.views.admin_portal import admin_component_view


def admin_borrower_view(request):
    return admin_component_view(request, component_slug="borrowers")
