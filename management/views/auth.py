from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.shortcuts import redirect, render

from management.models import Company

User = get_user_model()



def _find_company_by_identifier(identifier):
    if not identifier:
        return None

    identifier = identifier.strip()
    company = None
    if identifier.isdigit():
        company = Company.objects.filter(company_id=int(identifier)).first()
    if not company:
        company = Company.objects.filter(email__iexact=identifier).first()
    if not company:
        company = Company.objects.filter(company__iexact=identifier).first()
    return company


def _authenticate_by_company(identifier, password):
    company = _find_company_by_identifier(identifier)
    if company and company.check_password(password):
        return company
    return None


def _ensure_user_for_borrower(borrower):
    borrower_user = getattr(borrower, "login_user", None)
    if borrower_user:
        return borrower_user.user

    email = borrower.primary_contact_email
    user = User.objects.filter(email__iexact=email).first() if email else None

    if not user:
        username_base = f"borrower_{borrower.id}"
        username = username_base
        suffix = 0
        while User.objects.filter(username=username).exists():
            suffix += 1
            username = f"{username_base}_{suffix}"
        user = User.objects.create(username=username, email=email or "")
        user.set_unusable_password()
        user.save(update_fields=["password"])

    borrower_user, created = BorrowerUser.objects.get_or_create(
        user=user,
        defaults={"borrower": borrower, "is_active": True},
    )
    if not created and borrower_user.borrower != borrower:
        borrower_user.borrower = borrower
        borrower_user.save(update_fields=["borrower"])

    return user


def _ensure_user_for_company(company):
    if not company:
        return None

    username = f"company_{company.company_id}"
    user, created = User.objects.get_or_create(
        username=username,
        defaults={"email": company.email or ""},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])

    return user


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    error_message = None
    if request.method == "POST":
        identifier = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        company = _authenticate_by_company(identifier, password)
        if company:
            user = _ensure_user_for_company(company)
            login(request, user)
            request.session["company_id"] = company.id
            request.session.pop("selected_borrower_id", None)
            request.session.modified = True
            return redirect("borrower_portfolio")

        error_message = "Invalid email or password."

    context = {"error_message": error_message}
    return render(request, "login.html", context)


def logout_view(request):
    logout(request)
    messages.success(request, "You have been signed out.")
    request.session.pop("company_id", None)
    request.session.pop("selected_borrower_id", None)
    return redirect("login")
