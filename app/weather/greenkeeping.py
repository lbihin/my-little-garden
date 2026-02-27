"""
Greenkeeping intelligence module.

Analyses weather + soil data from Open-Meteo and returns
actionable recommendations for lawn/garden care.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from weather.services import WeatherData


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class Status(str, Enum):
    """Visual severity used by the UI (maps to DaisyUI badge colours)."""

    OK = "ok"  # badge-success
    INFO = "info"  # badge-info
    WARN = "warn"  # badge-warning
    DANGER = "danger"  # badge-error


@dataclass
class Advice:
    """One piece of greenkeeping advice."""

    icon: str  # emoji
    title: str
    detail: str
    status: Status = Status.INFO


@dataclass
class GreenkeepingReport:
    """Full analysis report returned to the view."""

    generated_at: str = ""
    advices: list[Advice] = field(default_factory=list)
    # Summary numbers
    grass_growing: bool = False
    soil_temp_surface: float = 0.0
    air_temp: float = 0.0
    moisture_surface: float = 0.0
    precip_last_24h: float = 0.0
    precip_next_24h: float = 0.0
    et0_last_24h: float = 0.0
    water_balance: float = 0.0  # precip - ET₀ (positive = surplus)
    wind_speed: float = 0.0
    uv_index: float = 0.0
    season: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEASONS = {
    1: "hiver",
    2: "hiver",
    3: "printemps",
    4: "printemps",
    5: "printemps",
    6: "été",
    7: "été",
    8: "été",
    9: "automne",
    10: "automne",
    11: "automne",
    12: "hiver",
}


def _current_season() -> str:
    return SEASONS[datetime.now().month]


def _current_month() -> int:
    return datetime.now().month


# ---------------------------------------------------------------------------
# Analysis functions – each appends Advice items
# ---------------------------------------------------------------------------


def _analyse_grass_growth(snap: dict, report: GreenkeepingReport) -> None:
    """Assess whether grass is actively growing."""
    soil = snap.get("soil_0cm") or 0
    air = snap.get("air_temp") or 0
    report.grass_growing = soil > 8 and air > 5

    if soil < 5:
        report.advices.append(
            Advice(
                "❄️",
                "Sol trop froid — gazon dormant",
                f"Température du sol à {soil:.1f} °C. La croissance reprend au-dessus de 8 °C.",
                Status.INFO,
            )
        )
    elif soil < 8:
        report.advices.append(
            Advice(
                "🌱",
                "Sol en train de se réchauffer",
                f"Sol à {soil:.1f} °C — la pousse va redémarrer bientôt (seuil : 8 °C).",
                Status.INFO,
            )
        )
    elif soil < 12:
        report.advices.append(
            Advice(
                "🌿",
                "Le gazon pousse lentement",
                f"Sol à {soil:.1f} °C, air à {air:.0f} °C. Croissance modérée.",
                Status.OK,
            )
        )
    elif soil <= 25:
        report.advices.append(
            Advice(
                "🌿",
                "Le gazon pousse activement",
                f"Sol à {soil:.1f} °C, air à {air:.0f} °C. Conditions optimales de croissance.",
                Status.OK,
            )
        )
    else:
        report.advices.append(
            Advice(
                "🔥",
                "Stress thermique",
                f"Sol à {soil:.1f} °C — le gazon peut jaunir. Arrosez tôt le matin.",
                Status.WARN,
            )
        )


def _analyse_mowing(snap: dict, report: GreenkeepingReport) -> None:
    """Should the user mow?"""
    if not report.grass_growing:
        return  # no point mowing if not growing

    moisture = snap.get("moisture_surface") or 0
    rain_prob = snap.get("precip_prob") or 0
    air = snap.get("air_temp") or 0

    if moisture > 0.45:
        report.advices.append(
            Advice(
                "🚫",
                "Sol trop humide pour tondre",
                "Le sol est gorgé d'eau — attendez qu'il sèche pour éviter d'arracher le gazon.",
                Status.WARN,
            )
        )
    elif rain_prob > 60:
        report.advices.append(
            Advice(
                "🌧️",
                "Pluie prévue — reportez la tonte",
                f"Probabilité de pluie : {rain_prob:.0f} %. Tondre sur herbe sèche donne un meilleur résultat.",
                Status.INFO,
            )
        )
    elif air < 3:
        report.advices.append(
            Advice(
                "🥶",
                "Trop froid pour tondre",
                f"Air à {air:.0f} °C. Évitez de tondre par gel ou quasi-gel.",
                Status.WARN,
            )
        )
    else:
        report.advices.append(
            Advice(
                "✂️",
                "Conditions favorables à la tonte",
                "Sol ressuyé, pas de pluie imminente — c'est le bon moment pour tondre.",
                Status.OK,
            )
        )


def _analyse_trampling(snap: dict, report: GreenkeepingReport) -> None:
    """Warn if foot traffic could damage the lawn."""
    soil = snap.get("soil_0cm") or 0
    moisture = snap.get("moisture_surface") or 0

    if soil < 0:
        report.advices.append(
            Advice(
                "🚷",
                "Sol gelé — évitez de marcher",
                "Piétiner un gazon gelé casse les brins. Attendez le dégel.",
                Status.DANGER,
            )
        )
    elif moisture > 0.50:
        report.advices.append(
            Advice(
                "🚷",
                "Sol détrempé — limitez le passage",
                "Le sol saturé se compacte facilement sous les pas.",
                Status.WARN,
            )
        )


def _analyse_scarification(snap: dict, report: GreenkeepingReport) -> None:
    """Is it a good time to scarify?"""
    month = _current_month()
    soil = snap.get("soil_0cm") or 0
    moisture = snap.get("moisture_surface") or 0

    good_months = month in (3, 4, 9, 10)

    if good_months and soil >= 10 and moisture < 0.45:
        report.advices.append(
            Advice(
                "🪮",
                "Bonne période pour scarifier",
                "Sol chaud (≥ 10 °C), pas trop humide. Le gazon récupérera bien.",
                Status.OK,
            )
        )
    elif good_months and soil < 10:
        report.advices.append(
            Advice(
                "🪮",
                "Scarification : sol encore un peu froid",
                f"Sol à {soil:.1f} °C — attendez qu'il dépasse 10 °C pour scarifier.",
                Status.INFO,
            )
        )
    elif not good_months and month in (5, 6, 7, 8):
        report.advices.append(
            Advice(
                "🪮",
                "Hors saison de scarification",
                "La scarification se fait au printemps (mars-avril) ou à l'automne (sept.-oct.).",
                Status.INFO,
            )
        )


def _analyse_fertiliser(report: GreenkeepingReport) -> None:
    """Suggest fertiliser type by season."""
    season = report.season
    if season == "printemps":
        report.advices.append(
            Advice(
                "🧪",
                "Engrais printemps : riche en azote",
                "Apportez un NPK type 20-5-10 pour relancer la pousse après l'hiver.",
                Status.OK,
            )
        )
    elif season == "été":
        report.advices.append(
            Advice(
                "🧪",
                "Engrais été : potassium pour la résistance",
                "Privilégiez un engrais riche en potassium (K) pour résister à la sécheresse.",
                Status.INFO,
            )
        )
    elif season == "automne":
        report.advices.append(
            Advice(
                "🧪",
                "Engrais automne : phosphore & potassium",
                "Un NPK type 5-5-15 renforce les racines avant l'hiver.",
                Status.OK,
            )
        )
    else:  # hiver
        report.advices.append(
            Advice(
                "🧪",
                "Pas d'engrais en hiver",
                "Le gazon est en dormance — toute fertilisation serait gaspillée.",
                Status.INFO,
            )
        )


def _analyse_watering(snap: dict, report: GreenkeepingReport) -> None:
    """Water balance: precipitation vs evapotranspiration."""
    balance = report.water_balance

    if not report.grass_growing:
        return  # watering dormant grass is wasteful

    if balance < -3:
        report.advices.append(
            Advice(
                "💧",
                "Arrosage recommandé",
                f"Déficit hydrique de {abs(balance):.1f} mm sur 24 h. "
                "Arrosez tôt le matin (5-8 h) pour limiter l'évaporation.",
                Status.WARN,
            )
        )
    elif balance < 0:
        report.advices.append(
            Advice(
                "💧",
                "Gazon légèrement en déficit",
                f"Bilan hydrique : {balance:+.1f} mm. Surveillez l'humidité du sol.",
                Status.INFO,
            )
        )
    else:
        report.advices.append(
            Advice(
                "💧",
                "Pas besoin d'arroser",
                f"Bilan hydrique : {balance:+.1f} mm — les précipitations suffisent.",
                Status.OK,
            )
        )


def _analyse_treatment_window(snap: dict, report: GreenkeepingReport) -> None:
    """Can the user apply treatments (herbicide, anti-mousse)?"""
    wind = snap.get("wind_speed") or 0
    rain_prob = snap.get("precip_prob") or 0
    uv = snap.get("uv_index") or 0

    problems = []
    if wind > 15:
        problems.append(f"vent fort ({wind:.0f} km/h)")
    if rain_prob > 40:
        problems.append(f"risque de pluie ({rain_prob:.0f} %)")
    if uv > 8:
        problems.append(f"UV élevé ({uv:.0f})")

    if problems:
        report.advices.append(
            Advice(
                "⚗️",
                "Traitement déconseillé",
                "Conditions défavorables : " + ", ".join(problems) + ".",
                Status.WARN,
            )
        )
    else:
        report.advices.append(
            Advice(
                "⚗️",
                "Fenêtre favorable pour traiter",
                f"Vent faible ({wind:.0f} km/h), peu de pluie annoncée, UV modéré.",
                Status.OK,
            )
        )


def _analyse_overseeding(snap: dict, report: GreenkeepingReport) -> None:
    """Conditions for overseeding / re-seeding."""
    soil = snap.get("soil_0cm") or 0
    moisture = snap.get("moisture_surface") or 0
    month = _current_month()

    good_months = month in (3, 4, 5, 9, 10)
    good_soil = 10 <= soil <= 25
    good_moisture = 0.20 <= moisture <= 0.45

    if good_months and good_soil and good_moisture:
        report.advices.append(
            Advice(
                "🌾",
                "Conditions idéales pour sursemer",
                f"Sol à {soil:.1f} °C, humidité adéquate. Le semis lèvera bien.",
                Status.OK,
            )
        )
    elif good_months and not good_soil:
        report.advices.append(
            Advice(
                "🌾",
                "Sursemis : sol pas encore prêt",
                f"Sol à {soil:.1f} °C — il faut entre 10 et 25 °C pour une bonne germination.",
                Status.INFO,
            )
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyse(weather: WeatherData) -> GreenkeepingReport:
    """
    Run all greenkeeping analyses on the given weather data.

    Returns a GreenkeepingReport with individual Advice items.
    """
    report = GreenkeepingReport(
        generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
        season=_current_season(),
    )

    if not weather.ok:
        report.advices.append(
            Advice(
                "⚠️",
                "Données météo indisponibles",
                weather.error or "Impossible d'analyser sans données.",
                Status.DANGER,
            )
        )
        return report

    snap = weather.current_snapshot()

    # Populate summary numbers
    report.soil_temp_surface = snap.get("soil_0cm") or 0
    report.air_temp = snap.get("air_temp") or 0
    report.moisture_surface = snap.get("moisture_surface") or 0
    report.wind_speed = snap.get("wind_speed") or 0
    report.uv_index = snap.get("uv_index") or 0
    report.precip_last_24h = weather.recent_precipitation_mm(24)
    report.precip_next_24h = weather.upcoming_precipitation_mm(24)
    report.et0_last_24h = weather.recent_et0_mm(24)
    report.water_balance = report.precip_last_24h - report.et0_last_24h

    # Run each analysis
    _analyse_grass_growth(snap, report)
    _analyse_mowing(snap, report)
    _analyse_trampling(snap, report)
    _analyse_scarification(snap, report)
    _analyse_fertiliser(report)
    _analyse_watering(snap, report)
    _analyse_treatment_window(snap, report)
    _analyse_overseeding(snap, report)

    return report
