"""
Greenkeeping intelligence module.

Analyses weather + soil data from Open-Meteo and returns
actionable recommendations for lawn/garden care.

Watering strategy reference (cool-season turfgrass, Europe):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 1 mm of rain = 1 L/m²
• Weekly ET₀ in temperate Europe:
  - Spring (Mar–May):  ~15–20 mm/week
  - Summer (Jun–Aug):  ~25–40 mm/week
  - Autumn (Sep–Nov):  ~10–15 mm/week
  - Winter (Dec–Feb):  ~2–5 mm/week (grass dormant)
• Cool-season grasses require ~60–80 % of ET₀ to stay green
• Deficit irrigation: intentionally replacing only a fraction
  of ET₀ to save water while accepting some quality loss

Profiles:
  standard     – 70 % ET₀ replacement, balanced approach
  eco          – 60 % ET₀, minimise waste, still attractive
  resilient    – 30 % ET₀, accepts summer dormancy, regrows
  laissez_faire– 0 %  ET₀, rainfall only, nature decides
  pro          – 100% ET₀, golf-green quality, zero tolerance
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
    # True  → user can log "Fait" (something TO DO)
    # False → purely informational / preventive (state, don't-do-X)
    actionable: bool = True


@dataclass
class WateringRecommendation:
    """Quantified watering recommendation."""

    weekly_et0: float = 0.0  # mm – raw ET₀ over the analysis window
    et0_replacement_pct: int = 70  # profile replacement ratio (0-100 %)
    weekly_need: float = 0.0  # mm – ET₀ × replacement ratio
    weekly_precip: float = 0.0  # mm – natural rainfall
    weekly_deficit: float = 0.0  # mm – need − precip (positive = must water)
    litres_per_m2: float = 0.0  # L/m² to apply (= deficit in mm)
    total_litres: float = 0.0  # L for the whole garden surface
    profile: str = "standard"
    profile_label: str = ""
    surface: int = 0  # m²


@dataclass
class GreenkeepingReport:
    """Full analysis report returned to the view."""

    generated_at: str = ""
    advices: list[Advice] = field(default_factory=list)
    # Summary numbers
    grass_growing: bool = False
    soil_temp_surface: float = 0.0
    soil_temp_roots: float = 0.0  # ~6 cm — lawn root zone
    air_temp: float = 0.0
    moisture_surface: float = 0.0
    precip_last_24h: float = 0.0
    precip_next_24h: float = 0.0
    et0_last_24h: float = 0.0
    water_balance: float = 0.0  # precip - ET₀ (positive = surplus)
    wind_speed: float = 0.0
    uv_index: float = 0.0
    season: str = ""
    # Watering details
    watering: WateringRecommendation | None = None


# ---------------------------------------------------------------------------
# Watering profiles
# ---------------------------------------------------------------------------

WATERING_PROFILES: dict[str, dict] = {
    "standard": {
        "label": "🌿 Standard",
        "et0_pct": 0.70,
        "description": "Beau jardin, arrosage équilibré",
        # Weekly deficit (mm) below which we don't recommend watering
        "ignore_threshold": 5.0,
        # Weekly deficit (mm) above which we alert
        "warn_threshold": 15.0,
    },
    "eco": {
        "label": "💧 Éco-responsable",
        "et0_pct": 0.60,
        "description": "Économe en eau, gazon soigné",
        "ignore_threshold": 8.0,
        "warn_threshold": 20.0,
    },
    "resilient": {
        "label": "🌾 Résilient",
        "et0_pct": 0.30,
        "description": "Accepte la dormance estivale, le gazon revient après",
        "ignore_threshold": 15.0,
        "warn_threshold": 30.0,
    },
    "laissez_faire": {
        "label": "🍃 Laisser-faire",
        "et0_pct": 0.0,
        "description": "Pas d'arrosage, la nature décide",
        "ignore_threshold": 999.0,
        "warn_threshold": 999.0,
    },
    "pro": {
        "label": "⛳ Greenkeeper pro",
        "et0_pct": 1.0,
        "description": "Gazon de golf, tolérance zéro",
        "ignore_threshold": 2.0,
        "warn_threshold": 8.0,
    },
}


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


# Cool-season turf monthly crop coefficients (Kc) for temperate Europe.
# Used to convert reference ET₀ to lawn ETc before applying profile ratio.
COOL_SEASON_KC_BY_MONTH: dict[int, float] = {
    1: 0.55,
    2: 0.60,
    3: 0.70,
    4: 0.80,
    5: 0.90,
    6: 0.95,
    7: 0.95,
    8: 0.90,
    9: 0.85,
    10: 0.75,
    11: 0.65,
    12: 0.55,
}


def _weather_month(weather: WeatherData) -> int:
    """Best-effort month from weather timeline, fallback to current month."""
    if weather.times:
        try:
            idx = weather._current_index()
            return datetime.fromisoformat(weather.times[idx]).month
        except (ValueError, IndexError):
            return _current_month()
    return _current_month()


def _soil_temperature_stress_coeff(soil_temp_c: float | None) -> float:
    """FAO-style stress coefficient proxy based on root-zone soil temperature.

    - <= 5 °C: dormant, no effective transpiration demand
    - >= 10 °C: active growth, no temperature-related stress
    - Linear ramp between 5 and 10 °C
    """
    if soil_temp_c is None:
        return 1.0
    if soil_temp_c <= 5:
        return 0.0
    if soil_temp_c >= 10:
        return 1.0
    return (soil_temp_c - 5.0) / 5.0


# ---------------------------------------------------------------------------
# Analysis functions – each appends Advice items
# ---------------------------------------------------------------------------


def _analyse_grass_growth(snap: dict, report: GreenkeepingReport) -> None:
    """Assess whether grass is actively growing.

    Uses soil temperature at root depth (~6 cm) as the primary indicator.
    Cool-season grass roots start growing when root-zone soil reaches ~6 °C,
    shoot growth kicks in around 8 °C, and optimum is 10-18 °C.
    """
    soil_roots = snap.get("soil_6cm") or snap.get("soil_0cm") or 0
    soil_surface = snap.get("soil_0cm") or 0
    air = snap.get("air_temp") or 0
    report.grass_growing = soil_roots > 8 and air > 5

    if soil_roots < 5:
        report.advices.append(
            Advice(
                "❄️",
                "Sol trop froid — gazon dormant",
                f"Sol à {soil_roots:.1f} °C à 6 cm de profondeur (racines). "
                f"La croissance reprend au-dessus de 8 °C.",
                Status.INFO,
                actionable=False,
            )
        )
    elif soil_roots < 8:
        report.advices.append(
            Advice(
                "🌱",
                "Sol en train de se réchauffer",
                f"Sol à {soil_roots:.1f} °C aux racines (6 cm) — "
                f"la pousse va redémarrer bientôt (seuil : 8 °C). "
                f"Surface : {soil_surface:.1f} °C.",
                Status.INFO,
                actionable=False,
            )
        )
    elif soil_roots < 12:
        report.advices.append(
            Advice(
                "🌿",
                "Le gazon pousse lentement",
                f"Sol à {soil_roots:.1f} °C aux racines, air à {air:.0f} °C. Croissance modérée.",
                Status.OK,
                actionable=False,
            )
        )
    elif soil_roots <= 25:
        report.advices.append(
            Advice(
                "🌿",
                "Le gazon pousse activement",
                f"Sol à {soil_roots:.1f} °C aux racines, air à {air:.0f} °C. "
                f"Conditions optimales de croissance.",
                Status.OK,
                actionable=False,
            )
        )
    else:
        report.advices.append(
            Advice(
                "🔥",
                "Stress thermique",
                f"Sol à {soil_roots:.1f} °C aux racines — le gazon peut jaunir. "
                f"Arrosez tôt le matin.",
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
                actionable=False,
            )
        )
    elif rain_prob > 60:
        report.advices.append(
            Advice(
                "🌧️",
                "Pluie prévue — reportez la tonte",
                f"Probabilité de pluie : {rain_prob:.0f} %. Tondre sur herbe sèche donne un meilleur résultat.",
                Status.INFO,
                actionable=False,
            )
        )
    elif air < 3:
        report.advices.append(
            Advice(
                "🥶",
                "Trop froid pour tondre",
                f"Air à {air:.0f} °C. Évitez de tondre par gel ou quasi-gel.",
                Status.WARN,
                actionable=False,
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
                actionable=False,
            )
        )
    elif moisture > 0.50:
        report.advices.append(
            Advice(
                "🚷",
                "Sol détrempé — limitez le passage",
                "Le sol saturé se compacte facilement sous les pas.",
                Status.WARN,
                actionable=False,
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
                actionable=False,
            )
        )
    elif not good_months and month in (5, 6, 7, 8):
        report.advices.append(
            Advice(
                "🪴",
                "Hors saison de scarification",
                "La scarification se fait au printemps (mars-avril) ou à l'automne (sept.-oct.).",
                Status.INFO,
                actionable=False,
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
                actionable=False,
            )
        )


def _analyse_watering(
    weather: WeatherData,
    report: GreenkeepingReport,
    profile_key: str = "standard",
    surface: int = 0,
) -> None:
    """
    Analyse watering needs based on the selected profile.

     Uses the 7-day water budget approach:
     1. Estimate weekly ET₀ from available data (extrapolated from the
         forecast window).
     2. Convert ET₀ to ETc with seasonal Kc and soil-temperature Ks.
     3. Apply profile replacement ratio.
     4. Subtract natural precipitation → net irrigation need.
     5. Convert to L/m² (1 mm = 1 L/m²) and total litres for the garden.
    """
    profile = WATERING_PROFILES.get(profile_key, WATERING_PROFILES["standard"])

    # --- Compute 7-day water budget ---
    available_hours = len(weather.times)
    if available_hours == 0:
        return

    # Total precipitation and ET₀ over all available data
    total_precip = (
        sum(v or 0 for v in weather.precipitation) if weather.precipitation else 0
    )
    total_et0 = (
        sum(v or 0 for v in weather.evapotranspiration)
        if weather.evapotranspiration
        else 0
    )

    # Scale to exactly 7 days (168 hours)
    scale = 168.0 / available_hours if available_hours > 0 else 1.0
    weekly_precip = total_precip * scale
    weekly_et0 = total_et0 * scale

    month = _weather_month(weather)
    kc = COOL_SEASON_KC_BY_MONTH.get(month, 0.8)
    snap = weather.current_snapshot()
    soil_temp = snap.get("soil_6cm")
    if soil_temp is None:
        soil_temp = report.soil_temp_roots if report.soil_temp_roots > 0 else None
    ks = _soil_temperature_stress_coeff(soil_temp)

    # ETc then profile-adjusted need
    et0_pct = profile["et0_pct"]
    weekly_etc = weekly_et0 * kc * ks
    weekly_need = weekly_etc * et0_pct
    weekly_deficit = max(0, weekly_need - weekly_precip)

    # Litres
    litres_per_m2 = weekly_deficit  # 1 mm = 1 L/m²
    total_litres = litres_per_m2 * surface if surface > 0 else 0

    rec = WateringRecommendation(
        weekly_et0=round(weekly_et0, 1),
        et0_replacement_pct=round(et0_pct * 100),
        weekly_need=round(weekly_need, 1),
        weekly_precip=round(weekly_precip, 1),
        weekly_deficit=round(weekly_deficit, 1),
        litres_per_m2=round(litres_per_m2, 1),
        total_litres=round(total_litres, 0),
        profile=profile_key,
        profile_label=profile["label"],
        surface=surface,
    )
    report.watering = rec

    ignore = profile["ignore_threshold"]
    warn = profile["warn_threshold"]

    # --- Laissez-faire: never recommend watering ---
    if profile_key == "laissez_faire":
        if weekly_deficit > 25:
            report.advices.append(
                Advice(
                    "🍃",
                    "Le gazon entre en dormance",
                    f"Déficit de {weekly_deficit:.0f} mm/sem. En mode "
                    "laisser-faire, le gazon jaunira mais repartira "
                    "naturellement avec le retour des pluies.",
                    Status.INFO,
                    actionable=False,
                )
            )
        else:
            report.advices.append(
                Advice(
                    "🍃",
                    "Pas d'arrosage — mode laisser-faire",
                    "Les précipitations naturelles suffisent pour le moment.",
                    Status.OK,
                    actionable=False,
                )
            )
        return

    # --- Dormant grass: skip watering in most profiles ---
    if not report.grass_growing and profile_key != "pro":
        report.advices.append(
            Advice(
                "💧",
                "Gazon dormant — arrosage inutile",
                "Le sol est trop froid pour une croissance active. "
                "Économisez l'eau jusqu'au redémarrage.",
                Status.INFO,
                actionable=False,
            )
        )
        return

    # --- Generate advice based on deficit vs thresholds ---
    if weekly_deficit <= ignore:
        detail = (
            f"Besoin estimé : {weekly_need:.0f} mm/sem "
            f"({et0_pct:.0%} de l'ETc; Kc={kc:.2f}, Ks={ks:.2f}). "
            f"Pluies prévues : {weekly_precip:.0f} mm. "
            f"Aucun arrosage nécessaire."
        )
        report.advices.append(Advice("💧", "Pas besoin d'arroser", detail, Status.OK, actionable=False))
    elif weekly_deficit <= warn:
        detail = (
            f"Besoin : {weekly_need:.0f} mm/sem − pluies {weekly_precip:.0f} mm "
            f"= déficit de {weekly_deficit:.0f} mm ({litres_per_m2:.0f} L/m²). "
        )
        if total_litres > 0:
            detail += (
                f"Pour vos {surface} m² : ~{total_litres:.0f} L "
                "à répartir sur la semaine. "
            )
        detail += (
            "Arrosez en profondeur 1 à 2 fois par semaine, " "tôt le matin (5-8 h)."
        )
        report.advices.append(Advice("💧", "Arrosage conseillé", detail, Status.INFO))
    else:
        detail = (
            f"Déficit important : {weekly_deficit:.0f} mm/sem "
            f"({litres_per_m2:.0f} L/m²). "
        )
        if total_litres > 0:
            detail += f"Pour vos {surface} m² : ~{total_litres:.0f} L. "
        detail += (
            "Arrosez en profondeur (15-20 min par zone) 2 à 3 fois par semaine, "
            "tôt le matin. Évitez les arrosages légers et fréquents qui "
            "favorisent un enracinement superficiel."
        )
        report.advices.append(Advice("💧", "Arrosage recommandé", detail, Status.WARN))

    # --- Profile-specific bonus tips ---
    if profile_key == "eco" and weekly_deficit > ignore:
        report.advices.append(
            Advice(
                "♻️",
                "Astuce éco : récupérez l'eau de pluie",
                "Un récupérateur de 300 L couvre ~1 arrosage pour 30 m². "
                "Tondez haut (6-8 cm) pour réduire l'évaporation du sol.",
                Status.INFO,
                actionable=False,
            )
        )
    elif profile_key == "resilient" and weekly_deficit > ignore:
        report.advices.append(
            Advice(
                "🌾",
                "Astuce résilient : laisser jaunir n'est pas fatal",
                "Le gazon entre en dormance au-dessus de ~25 mm/sem de "
                "déficit. Il reverdit naturellement en 2-4 semaines "
                "après le retour des pluies.",
                Status.INFO,
                actionable=False,
            )
        )
    elif profile_key == "pro":
        report.advices.append(
            Advice(
                "⛳",
                f"Profil pro : remplacement de {et0_pct:.0%} de l'ET₀",
                f"ET₀ estimée : {weekly_et0:.0f} mm/sem. Objectif : "
                "maintenir l'humidité du sol entre 0,25 et 0,35 m³/m³. "
                "Programmez l'arrosage en fonction du tensiomètre.",
                Status.INFO,
                actionable=False,
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
                actionable=False,
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
                actionable=False,
            )
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyse(
    weather: WeatherData,
    profile: str = "standard",
    surface: int = 0,
) -> GreenkeepingReport:
    """
    Run all greenkeeping analyses on the given weather data.

    Args:
        weather: WeatherData from the Open-Meteo service.
        profile: Watering profile key (standard, eco, resilient,
                 laissez_faire, pro).
        surface: Garden surface in m² (used for total litres).

    Returns:
        GreenkeepingReport with individual Advice items.
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
    report.soil_temp_roots = snap.get("soil_6cm") or 0
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
    _analyse_watering(weather, report, profile_key=profile, surface=surface)
    _analyse_treatment_window(snap, report)
    _analyse_overseeding(snap, report)

    return report
