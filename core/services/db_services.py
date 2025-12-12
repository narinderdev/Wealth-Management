from __future__ import annotations

from typing import Any, Optional, Type

from django.contrib.auth import get_user_model
from django.db.models import Model

User = get_user_model()


def create_object(model: Type[Model], **fields: Any) -> Model:
    """Create a new model instance using the provided fields."""
    return model.objects.create(**fields)


def get_object(model: Type[Model], **filters: Any) -> Optional[Model]:
    """Return the first instance of the given model matching the filters."""
    if not filters:
        return None
    return model.objects.filter(**filters).first()
