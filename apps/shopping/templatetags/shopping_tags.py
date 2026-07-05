from django import template
from decimal import Decimal, ROUND_HALF_UP
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


def _round_by_magnitude(val):
    """Rundet nach Größenordnung, kaufmännisch (0,5 aufwärts), für g:
    3-stellig -> naechste Hundert, 2-stellig -> naechste Zehn,
    1-stellig -> naechste Eins. Z.B. '564 g' -> '600 g'."""
    d = Decimal(str(val))
    if d == 0:
        return 0
    digits = len(str(abs(int(d.to_integral_value(rounding=ROUND_HALF_UP)))))
    step = 10 ** (digits - 1) if digits >= 2 else 1
    step = Decimal(step)
    return int((d / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step)


def _round_stk(val):
    """Rundet Stk-Mengen, kaufmännisch (0,5 aufwaerts): ab zweistellig
    IMMER auf die naechste Zehn (deckelt bei 10, skaliert NICHT weiter
    auf Hundert bei dreistelligen Werten wie bei g). Einstellig bleibt
    unveraendert. Z.B. '177 Stk' -> '180 Stk', nicht '200 Stk'."""
    d = Decimal(str(val))
    if d == 0:
        return 0
    digits = len(str(abs(int(d.to_integral_value(rounding=ROUND_HALF_UP)))))
    step = Decimal(10) if digits >= 2 else Decimal(1)
    return int((d / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step)


def format_amount(amount, unit):
    """Formatiert Menge fuer den CSV-Export mit groessenordnungsabhaengiger
    Rundung:
    - kg/l: immer mathematisch auf 1 Nachkommastelle
    - g/ml >= 1000: zu kg/l konvertiert, dann wie kg/l gerundet
    - g/ml < 1000: nach Groessenordnung gerundet (3-stellig -> Hundert,
      2-stellig -> Zehn, 1-stellig -> Eins)
    - Stk: gedeckelt bei "naechste Zehn" ab zweistellig (nicht Hundert
      bei dreistellig, anders als g)
    - alles andere (Pck, Bd, EL, TL, ...): wie bisher ueber smart_amount
    """
    try:
        val = float(amount)
    except (TypeError, ValueError):
        return f"{amount} {unit}"

    unit = (unit or "").strip()

    if unit in ("kg", "l"):
        rounded = Decimal(str(val)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        return f"{rounded}".replace(".", ",") + f" {unit}"

    if unit in ("g", "ml"):
        if val >= 1000:
            converted = Decimal(str(val)) / 1000
            rounded = converted.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            target_unit = "kg" if unit == "g" else "l"
            return f"{rounded}".replace(".", ",") + f" {target_unit}"
        return f"{_round_by_magnitude(val)} {unit}"

    if unit == "Stk":
        return f"{_round_stk(val)} {unit}"

    return smart_amount(amount, unit)
