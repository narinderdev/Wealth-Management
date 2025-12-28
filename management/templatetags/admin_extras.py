from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def _to_decimal(value):
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(value)
    except (TypeError, ValueError, InvalidOperation):
        try:
            return Decimal(str(value))
        except Exception:
            return None


@register.filter
def attr(obj, attr_name):
    if not obj or not attr_name:
        return None
    return getattr(obj, attr_name, None)


@register.filter
def weeks_of_supply(row):
    if not row:
        return None
    finished = _to_decimal(getattr(row, "finished_goods", None)) or Decimal("0")
    sales = _to_decimal(getattr(row, "net_sales", None))
    if not sales:
        return None
    return (finished / sales) * Decimal("52")


@register.filter
def currency_display(value):
    amount = _to_decimal(value)
    if amount is None:
        return None
    return f"${amount:,.2f}"
