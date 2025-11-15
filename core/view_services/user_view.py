from __future__ import annotations
from typing import Any
from ..services.user_service import register_client


def list_clients() -> dict[str, Any]:
    """
    Return a simple list of clients as a skeleton for a GET endpoint.
    """
    clients = [
        {"id": 1, "name": "Ava Park", "status": "active"},
        {"id": 2, "name": "Leo Martinez", "status": "pending"},
    ]
    return {
        "clients": clients,
        "count": len(clients),
    }


def onboard_client(payload: dict[str, Any]) -> dict[str, Any]:
    """Wrap the user_service onboarding helper for a POST endpoint."""
    return register_client(payload)

