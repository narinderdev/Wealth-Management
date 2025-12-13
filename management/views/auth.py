from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.shortcuts import redirect, render

from management.models import Borrower, BorrowerUser

User = get_user_model()


def _authenticate_by_email_or_username(request, identifier, password):
    if not identifier or not password:
        return None

    account = User.objects.filter(email__iexact=identifier).first()
    if account:
        user = authenticate(
            request, username=account.get_username(), password=password
        )
        if user:
            return user

    return authenticate(request, username=identifier, password=password)


def _find_borrower_by_identifier(identifier):
    if not identifier:
        return None

    identifier = identifier.strip()
    borrower = None
    if identifier.isdigit():
        borrower = Borrower.objects.filter(pk=int(identifier)).first()
    if not borrower:
        borrower = Borrower.objects.filter(
            primary_contact_email__iexact=identifier
        ).first()
    if not borrower:
        borrower = Borrower.objects.filter(company__company__iexact=identifier).first()
    return borrower


def _authenticate_by_borrower(identifier, password):
    borrower = _find_borrower_by_identifier(identifier)
    if borrower and borrower.check_password(password):
        return borrower
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


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    error_message = None
    if request.method == "POST":
        identifier = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user = _authenticate_by_email_or_username(request, identifier, password)
        if user:
            login(request, user)
            return redirect("dashboard")

        borrower = _authenticate_by_borrower(identifier, password)
        if borrower:
            user = _ensure_user_for_borrower(borrower)
            login(request, user)
            return redirect("dashboard")

        error_message = "Invalid email or password."

    context = {"error_message": error_message}
    return render(request, "login.html", context)


def logout_view(request):
    logout(request)
    messages.success(request, "You have been signed out.")
    return redirect("login")
