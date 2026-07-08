"""
apps/rechnungen/views.py – Rechnungsführung

Belege hochladen, automatisch analysieren, Positionen prüfen und
Grundpreise in die Zutaten-Stammdaten übernehmen. Darauf aufbauend:
Preisliste, Rezeptkosten, Freizeitkosten und Preistreiber.
"""
import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.camps.models import Camp
from apps.recipes.models import Ingredient

from . import services
from .forms import BelegUploadForm, KostenkategorieForm
from .models import Beleg, BelegPosition, Kostenkategorie, Preishistorie

logger = logging.getLogger(__name__)


def _aktive_freizeit():
    return Camp.objects.filter(is_active=True).order_by("-start_date").first()


# ---------------------------------------------------------------------------
# Belegübersicht
# ---------------------------------------------------------------------------

@login_required
def index(request):
    camp = _aktive_freizeit()
    belege = []
    ist_summe = None
    if camp:
        belege = (
            Beleg.objects.filter(camp=camp)
            .select_related("hochgeladen_von", "kategorie")
            .annotate(anzahl_positionen=Count("positionen"))
        )
        ist_summe = belege.aggregate(s=Sum("gesamtbetrag"))["s"]

    return render(request, "rechnungen/index.html", {
        "camp":      camp,
        "belege":    belege,
        "ist_summe": ist_summe,
    })


# ---------------------------------------------------------------------------
# Beleg hochladen
# ---------------------------------------------------------------------------

@login_required
def upload(request):
    camp = _aktive_freizeit()
    if not camp:
        messages.warning(request, "Keine aktive Freizeit vorhanden -- bitte zuerst eine Freizeit aktivieren.")
        return redirect("rechnungen:index")

    form = BelegUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        bilder = request.FILES.getlist("bilder")
        kategorie = form.cleaned_data["kategorie"]
        sofort = form.cleaned_data["sofort_analysieren"]
        notiz = form.cleaned_data["notiz"]

        neue_belege = []
        for bild in bilder:
            beleg = Beleg.objects.create(
                camp=camp,
                kategorie=kategorie,
                image=bild,
                notiz=notiz,
                hochgeladen_von=request.user,
            )
            neue_belege.append(beleg)

        if sofort:
            fehler = 0
            for beleg in neue_belege:
                erfolg, meldung = services.analysiere_beleg(beleg, user=request.user)
                if not erfolg:
                    fehler += 1
                    messages.error(request, f"Beleg {beleg.pk}: {meldung}")
            ok = len(neue_belege) - fehler
            if ok:
                messages.success(request, f"{ok} Beleg(e) hochgeladen und analysiert.")
        else:
            messages.success(request, f"{len(neue_belege)} Beleg(e) hochgeladen. Analyse kann pro Beleg gestartet werden.")

        if len(neue_belege) == 1:
            return redirect("rechnungen:detail", pk=neue_belege[0].pk)
        return redirect("rechnungen:index")

    return render(request, "rechnungen/upload.html", {"form": form, "camp": camp})


# ---------------------------------------------------------------------------
# Beleg-Detail: Bild, Positionen, Zuordnung, Preisübernahme
# ---------------------------------------------------------------------------

@login_required
def detail(request, pk):
    beleg = get_object_or_404(
        Beleg.objects.select_related("camp").prefetch_related("positionen__ingredient"),
        pk=pk,
    )
    zutaten_namen = list(Ingredient.objects.order_by("name").values_list("name", flat=True))
    positionen = beleg.positionen.all()
    differenz = None
    if beleg.gesamtbetrag is not None:
        differenz = beleg.gesamtbetrag - beleg.positionen_summe

    return render(request, "rechnungen/detail.html", {
        "beleg":         beleg,
        "positionen":    positionen,
        "zutaten_namen": zutaten_namen,
        "differenz":     differenz,
        "einheiten":     Ingredient.Unit.choices,
        "grundpreis_einheiten": BelegPosition.GrundpreisEinheit.choices,
        "kategorien":    Kostenkategorie.objects.all(),
    })


@login_required
@require_POST
def beleg_kategorie(request, pk):
    """Ändert die Kostenkategorie eines Belegs."""
    beleg = get_object_or_404(Beleg, pk=pk)
    kategorie_id = request.POST.get("kategorie")
    if kategorie_id:
        kategorie = get_object_or_404(Kostenkategorie, pk=kategorie_id)
        beleg.kategorie = kategorie
        beleg.save(update_fields=["kategorie"])
        messages.success(request, f"Kategorie auf '{kategorie.name}' gesetzt.")
    else:
        beleg.kategorie = None
        beleg.save(update_fields=["kategorie"])
        messages.success(request, "Kategorie entfernt.")
    return redirect("rechnungen:detail", pk=beleg.pk)


@login_required
@require_POST
def analysieren(request, pk):
    beleg = get_object_or_404(Beleg, pk=pk)
    erfolg, meldung = services.analysiere_beleg(beleg, user=request.user)
    if erfolg:
        messages.success(request, meldung)
    else:
        messages.error(request, meldung)
    return redirect("rechnungen:detail", pk=beleg.pk)


@login_required
@require_POST
def loeschen(request, pk):
    beleg = get_object_or_404(Beleg, pk=pk)
    beleg.image.delete(save=False)
    beleg.delete()
    messages.success(request, "Beleg gelöscht.")
    return redirect("rechnungen:index")


def _parse_decimal_de(wert, nachkommastellen="0.0001"):
    """Formulareingabe (deutsches Komma erlaubt) -> Decimal oder None."""
    wert = (wert or "").strip().replace(",", ".")
    if not wert:
        return None
    try:
        return Decimal(wert).quantize(Decimal(nachkommastellen))
    except InvalidOperation:
        return None


@login_required
@require_POST
def position_aktualisieren(request, pk):
    """
    Speichert die manuell geprüften Felder einer Position. Bei
    action=uebernehmen wird zusätzlich der Grundpreis in die
    Zutaten-Stammdaten übertragen.
    """
    position = get_object_or_404(
        BelegPosition.objects.select_related("beleg", "ingredient"), pk=pk
    )

    position.artikel_name = (request.POST.get("artikel_name") or position.artikel_name)[:200]
    position.menge = _parse_decimal_de(request.POST.get("menge"), "0.001")

    einheit = request.POST.get("einheit") or ""
    gueltige_einheiten = {code for code, _ in Ingredient.Unit.choices}
    position.einheit = einheit if einheit in gueltige_einheiten else ""

    position.gesamtpreis = _parse_decimal_de(request.POST.get("gesamtpreis"), "0.01")
    position.grundpreis = _parse_decimal_de(request.POST.get("grundpreis"))

    gp_einheit = request.POST.get("grundpreis_einheit") or ""
    gueltige_gp = {code for code, _ in BelegPosition.GrundpreisEinheit.choices}
    position.grundpreis_einheit = gp_einheit if gp_einheit in gueltige_gp else ""

    # Grundpreis ggf. aus Menge + Zeilensumme nachrechnen
    if position.grundpreis is None or not position.grundpreis_einheit:
        gp, gpe = services.ermittle_grundpreis(
            position.menge, position.einheit, position.gesamtpreis
        )
        if gp is not None:
            position.grundpreis, position.grundpreis_einheit = gp, gpe

    # Zutat per Name auflösen (Datalist-Eingabe), leer = keine Zuordnung
    zutat_name = (request.POST.get("zutat") or "").strip()
    if zutat_name:
        ing = services.lookup_ingredient(zutat_name)
        if ing is None:
            messages.warning(
                request,
                f"Zutat '{zutat_name}' nicht in den Stammdaten gefunden -- "
                "Zuordnung unverändert gelassen.",
            )
        else:
            if ing != position.ingredient:
                position.ist_uebernommen = False
                position.uebernommen_am = None
            position.ingredient = ing
    else:
        position.ingredient = None
        position.ist_uebernommen = False
        position.uebernommen_am = None

    position.save()

    if request.POST.get("action") == "uebernehmen":
        erfolg, meldung = services.uebernehme_position(position, user=request.user)
        if erfolg:
            messages.success(request, meldung)
        else:
            messages.error(request, meldung)
    else:
        messages.success(request, f"Position '{position.artikel_name}' gespeichert.")

    return redirect("rechnungen:detail", pk=position.beleg.pk)


@login_required
@require_POST
def position_loeschen(request, pk):
    position = get_object_or_404(BelegPosition.objects.select_related("beleg"), pk=pk)
    beleg_pk = position.beleg.pk
    position.delete()
    messages.success(request, "Position gelöscht.")
    return redirect("rechnungen:detail", pk=beleg_pk)


@login_required
@require_POST
def alle_uebernehmen(request, pk):
    """Überträgt alle zugeordneten, noch nicht übernommenen Grundpreise."""
    beleg = get_object_or_404(Beleg, pk=pk)
    kandidaten = beleg.positionen.filter(
        ingredient__isnull=False, ist_uebernommen=False,
        grundpreis__isnull=False,
    ).exclude(grundpreis_einheit="")

    ok, fehler = 0, 0
    for position in kandidaten:
        erfolg, meldung = services.uebernehme_position(position, user=request.user)
        if erfolg:
            ok += 1
        else:
            fehler += 1
            messages.error(request, meldung)

    if ok:
        messages.success(request, f"{ok} Preis(e) in die Zutaten-Stammdaten übernommen.")
    if not ok and not fehler:
        messages.info(request, "Keine offenen, zugeordneten Positionen mit Grundpreis vorhanden.")
    return redirect("rechnungen:detail", pk=beleg.pk)


# ---------------------------------------------------------------------------
# Kategoriekosten: Ist-Ausgaben je Kostenkategorie, Kategorien verwalten
# ---------------------------------------------------------------------------

@login_required
def kategorien(request):
    """
    Ist-Kosten der aktiven Freizeit je Kostenkategorie (Summe der
    Beleg-Gesamtbeträge) plus Verwaltung: neue Kostenpunkte anlegen,
    unbenutzte löschen.
    """
    camp = _aktive_freizeit()

    form = KostenkategorieForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        kategorie = form.save(commit=False)
        max_sort = Kostenkategorie.objects.order_by("-sortierung").first()
        kategorie.sortierung = (max_sort.sortierung + 10) if max_sort else 10
        kategorie.save()
        messages.success(request, f"Kostenkategorie '{kategorie.name}' angelegt.")
        return redirect("rechnungen:kategorien")

    eintraege = []
    gesamt = Decimal("0")
    for kategorie in Kostenkategorie.objects.all():
        belege = kategorie.belege.filter(camp=camp) if camp else kategorie.belege.none()
        summe = belege.aggregate(s=Sum("gesamtbetrag"))["s"] or Decimal("0")
        anzahl = belege.count()
        gesamt += summe
        eintraege.append({
            "kategorie": kategorie,
            "summe":     summe,
            "anzahl":    anzahl,
            "loeschbar": not kategorie.belege.exists(),
        })

    ohne = Beleg.objects.filter(camp=camp, kategorie__isnull=True) if camp else Beleg.objects.none()
    ohne_summe = ohne.aggregate(s=Sum("gesamtbetrag"))["s"] or Decimal("0")
    gesamt += ohne_summe

    return render(request, "rechnungen/kategorien.html", {
        "camp":        camp,
        "eintraege":   eintraege,
        "ohne_anzahl": ohne.count(),
        "ohne_summe":  ohne_summe,
        "gesamt":      gesamt,
        "form":        form,
    })


@login_required
@require_POST
def kategorie_loeschen(request, pk):
    kategorie = get_object_or_404(Kostenkategorie, pk=pk)
    if kategorie.belege.exists():
        messages.error(
            request,
            f"'{kategorie.name}' hat zugeordnete Belege und kann nicht gelöscht werden.",
        )
    else:
        name = kategorie.name
        kategorie.delete()
        messages.success(request, f"Kostenkategorie '{name}' gelöscht.")
    return redirect("rechnungen:kategorien")


# ---------------------------------------------------------------------------
# Preisliste
# ---------------------------------------------------------------------------

@login_required
def preisliste(request):
    q = request.GET.get("q", "").strip()
    nur_ohne = request.GET.get("ohne") == "1"

    zutaten = Ingredient.objects.all().prefetch_related("preishistorie")
    if q:
        zutaten = zutaten.filter(name__icontains=q)
    if nur_ohne:
        zutaten = zutaten.filter(price__isnull=True)

    eintraege = []
    mit_preis = 0
    for ing in zutaten:
        # Prefetch nutzen statt zu slicen -- .all()[:1] würde pro Zutat
        # eine neue Query auslösen. Historie ist per Meta absteigend sortiert.
        historie = list(ing.preishistorie.all())
        letzter = historie[0] if historie else None
        if ing.price is not None:
            mit_preis += 1
        eintraege.append({
            "ingredient": ing,
            "letzter":    letzter,
            "anzahl":     len(historie),
        })

    return render(request, "rechnungen/preisliste.html", {
        "eintraege": eintraege,
        "q":         q,
        "nur_ohne":  nur_ohne,
        "mit_preis": mit_preis,
        "gesamt":    len(eintraege),
    })


# ---------------------------------------------------------------------------
# Rezeptkosten
# ---------------------------------------------------------------------------

@login_required
def rezeptkosten(request):
    ergebnisse = services.berechne_rezeptkosten()
    return render(request, "rechnungen/rezeptkosten.html", {
        "ergebnisse": ergebnisse,
    })


# ---------------------------------------------------------------------------
# Freizeitkosten
# ---------------------------------------------------------------------------

@login_required
def freizeitkosten(request):
    camp = _aktive_freizeit()
    if not camp:
        messages.warning(request, "Keine aktive Freizeit vorhanden.")
        return redirect("rechnungen:index")

    kosten = services.berechne_freizeitkosten(camp)

    personen = camp.participants.count() or camp.total_persons
    pro_person = kosten["summe"] / personen if personen else None
    tage = camp.duration_days
    pro_person_tag = pro_person / tage if pro_person is not None and tage else None

    ist_summe = Beleg.objects.filter(camp=camp).aggregate(s=Sum("gesamtbetrag"))["s"]

    return render(request, "rechnungen/freizeitkosten.html", {
        "camp":           camp,
        "kosten":         kosten,
        "personen":       personen,
        "tage":           tage,
        "pro_person":     pro_person,
        "pro_person_tag": pro_person_tag,
        "ist_summe":      ist_summe,
    })


# ---------------------------------------------------------------------------
# Preistreiber
# ---------------------------------------------------------------------------

@login_required
def preistreiber(request):
    treiber = services.berechne_preistreiber()

    camp = _aktive_freizeit()
    top_positionen = []
    if camp:
        top_positionen = services.berechne_freizeitkosten(camp)["top_positionen"]

    return render(request, "rechnungen/preistreiber.html", {
        "treiber":        treiber,
        "camp":           camp,
        "top_positionen": top_positionen,
    })
