from typing import Any


def register_client(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Stub for the client onboarding workflow.
    Replace this with real persistence + validation.
    """
    return {"status": "registered", "client": payload}
