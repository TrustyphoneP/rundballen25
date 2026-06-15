from django import template
from decimal import Decimal
import math

register = template.Library()


@register.filter
def smart_amount(amount, unit):
    """
    Formats amount+unit with smart rounding and unit conversion:
    - g >= 1000 → kg (1 decimal)
    - ml >= 1000 → l (1 decimal)
    - g/ml < 1000 → rounded to nearest integer
    - Stk/Pck/EL/TL etc. → rounded up to next integer
    - kg/l → 1 decimal place
    """
    try:
        val = float(amount)
    except (TypeError, ValueError):
        return f"{amount} {unit}"

    unit = (unit or "").strip()

    if unit == "g":
        if val >= 1000:
            kg = val / 1000
            return f"{kg:.1f} kg".replace(".", ",")
        return f"{round(val)} g"

    if unit == "ml":
        if val >= 1000:
            l = val / 1000
            return f"{l:.1f} l".replace(".", ",")
        return f"{round(val)} ml"

    if unit == "kg":
        return f"{val:.1f} kg".replace(".", ",")

    if unit == "l":
        return f"{val:.1f} l".replace(".", ",")

    # Count units: always round up
    if unit in ("Stk", "Pck", "Bd", "EL", "TL"):
        return f"{math.ceil(val)} {unit}"

    # Default: round to integer
    return f"{round(val)} {unit}"


def format_amount(amount, unit):
    """Standalone version of smart_amount for use in Python code (e.g. CSV export)."""
    return smart_amount(amount, unit)
