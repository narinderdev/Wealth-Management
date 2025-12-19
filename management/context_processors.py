from django.conf import settings

from management.models import Company


def company_context(request):
    company_id = request.session.get("company_id")
    company_name = None
    company_contact = None
    if company_id:
        company = Company.objects.filter(pk=company_id).first()
        if company:
            company_name = company.company or f"Company {company.company_id}"
            company_contact = company.email or "Contact"
    return {
        "company_name": company_name,
        "company_contact": company_contact,
    }
