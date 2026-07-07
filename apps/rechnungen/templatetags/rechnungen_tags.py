from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from django import template

register = template.Library()


@register.filter
def euro(wert):
    """
    Formatiert einen Betrag deutsch: 1234.5 -> '1.234,50 €'.
    None oder nicht interpretierbare Werte ergeben '–'.
    """
    if wert is None or wert == "":
        return "–"
    try:
        betrag = Decimal(str(wert)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return "–"
    text = f"{betrag:,.2f}"  # 1,234.50
    return text.replace(",", "\u00a0").replace(".", ",").replace("\u00a0", ".") + " €"


@register.filter
def dezimal_de(wert):
    """
    Zahl mit deutschem Komma, überflüssige Nachkommastellen entfernt
    (für Mengen- und Grundpreis-Eingabefelder).
    """
    if wert is None or wert == "":
        return ""
    try:
        d = Decimal(str(wert)).normalize()
    except (InvalidOperation, ValueError):
        return str(wert)
    text = format(d, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


@register.filter
def menge(amount, unit):
    """
    Menge + Einheit mit den Rundungsregeln der Einkaufsliste formatieren.
    Delegiert an apps.shopping.templatetags.shopping_tags.format_amount,
    das dort nur als Python-Funktion existiert, nicht als Filter.
    """
    from apps.shopping.templatetags.shopping_tags import format_amount
    return format_amount(amount, unit)
