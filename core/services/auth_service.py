from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import AbstractBaseUser

from .db_services import create_object, get_object

User = get_user_model()


def _create_or_update_user(username: str, email: str, password: str) -> tuple[AbstractBaseUser, bool]:
    """Provision or refresh the static user account stored in settings."""
    user = get_object(User, username=username)
    created = False
    if not user:
        user = create_object(User, username=username, email=email or "")
        created = True

    if created or not user.check_password(password):
        user.set_password(password)
        if email and user.email != email:
            user.email = email
        user.save()

    return user, created


def ensure_static_user() -> Optional[AbstractBaseUser]:
    """
    Ensure the configured static login account exists and is kept in sync with settings.
    """
    username = getattr(settings, "STATIC_LOGIN_USERNAME", None)
    password = getattr(settings, "STATIC_LOGIN_PASSWORD", None)
    if not username or not password:
        return None

    email = getattr(settings, "STATIC_LOGIN_EMAIL", username)
    user, _created = _create_or_update_user(username=username, email=email or "", password=password)
    return user


def authenticate_by_identifier(request, identifier: str, password: str):
    """Try to authenticate using an email identifier first, then fall back to username."""
    if not identifier or not password:
        return None

    account = get_object(User, email__iexact=identifier)
    if account:
        user = authenticate(request, username=account.get_username(), password=password)
        if user:
            return user

    return authenticate(request, username=identifier, password=password)
