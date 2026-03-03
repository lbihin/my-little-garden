"""
Professional lawn-care programme knowledge base.

Encodes month-by-month best practices from major European turfgrass science
sources:
  - STRI (Sports Turf Research Institute)
  - R&A Greenkeeping guidelines
  - Progazon France (interprofession gazon)
  - European Turfgrass Society recommendations

Each "programme" is a calendar of tasks keyed by month (1–12), grass season,
and the user's intensity level (low / medium / high).

The public function ``get_monthly_plan()`` generates a personalised action list
for a given LawnProfile + current month + weather context.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ProgramTask:
    """A single actionable task in the user's monthly plan."""

    icon: str
    title: str
    detail: str
    category: str  # mowing, fertilisation, watering, scarification, etc.
    priority: int = 2  # 1 = high, 2 = normal, 3 = nice-to-have
    done: bool = False

    @property
    def priority_label(self) -> str:
        return {1: "Important", 2: "Normal", 3: "Optionnel"}[self.priority]


@dataclass
class MonthlyPlan:
    """The full plan for the current month."""

    month: int
    month_name: str
    season: str
    headline: str  # short motivational intro
    tasks: list[ProgramTask] = field(default_factory=list)
    tips: list[str] = field(default_factory=list)  # bonus seasonal tips


# ---------------------------------------------------------------------------
# Month names (French) and season mapping
# ---------------------------------------------------------------------------

MONTH_NAMES = {
    1: "Janvier",
    2: "Février",
    3: "Mars",
    4: "Avril",
    5: "Mai",
    6: "Juin",
    7: "Juillet",
    8: "Août",
    9: "Septembre",
    10: "Octobre",
    11: "Novembre",
    12: "Décembre",
}

MONTH_SEASON = {
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


# ---------------------------------------------------------------------------
# Knowledge base — month-by-month rules
#
# Each month contains a dict of tasks keyed by category.
# Tasks are conditional on: grass_type, intensity, soil_type, issues, etc.
# ---------------------------------------------------------------------------


def _mowing_tasks(month: int, profile) -> list[ProgramTask]:
    """Generate mowing advice for the month based on the profile."""
    tasks: list[ProgramTask] = []
    growing = month in range(3, 11)  # Mar–Oct for cool-season
    warm_growing = month in range(5, 10)  # May–Sep for warm-season

    is_warm = profile.grass_type == "warm_season"
    active = warm_growing if is_warm else growing

    if not active:
        if month in (11, 12):
            tasks.append(
                ProgramTask(
                    icon="🍂",
                    title="Dernière tonte haute",
                    detail="Si la pelouse pousse encore, effectuez une dernière tonte "
                    "à 5–6 cm. Ramassez les feuilles mortes pour éviter l'étouffement.",
                    category="mowing",
                    priority=2,
                )
            )
        return tasks

    # Height recommendations by month, intensity, and usage
    if profile.goal == "perfect":
        target_height = {
            3: "3–4 cm",
            4: "2.5–3.5 cm",
            5: "2.5–3 cm",
            6: "3–3.5 cm",
            7: "3.5–4 cm",
            8: "3.5–4 cm",
            9: "3–3.5 cm",
            10: "3.5–4 cm",
        }.get(month, "3–4 cm")
        freq = "2–3 fois" if month in (4, 5, 6, 9) else "1–2 fois"
    elif profile.goal == "nice":
        target_height = {
            3: "4–5 cm",
            4: "3.5–4.5 cm",
            5: "3.5–4 cm",
            6: "4–5 cm",
            7: "5–6 cm",
            8: "5–6 cm",
            9: "4–5 cm",
            10: "4–5 cm",
        }.get(month, "4–5 cm")
        freq = "1–2 fois" if month in (4, 5, 6, 9) else "1 fois"
    else:
        target_height = "5–7 cm"
        freq = "1 fois"

    # Shade adjustment
    shade_note = ""
    if profile.sun_exposure == "shade":
        shade_note = " En zone ombragée, montez de 1 cm supplémentaire."
    elif profile.sun_exposure == "partial":
        shade_note = " En mi-ombre, ajoutez 0.5 cm."

    # Summer stress
    if month in (7, 8):
        tasks.append(
            ProgramTask(
                icon="🌡️",
                title="Tonte en période de chaleur",
                detail=f"Hauteur recommandée : {target_height} — "
                f"tondez le matin ou en fin de journée. "
                f"Fréquence : {freq} par semaine.{shade_note}"
                " Ne coupez jamais plus d'un tiers de la hauteur (règle du tiers).",
                category="mowing",
                priority=1,
            )
        )
    else:
        tasks.append(
            ProgramTask(
                icon="✂️",
                title="Tonte régulière",
                detail=f"Hauteur recommandée : {target_height}. "
                f"Fréquence : {freq} par semaine.{shade_note}"
                " Respectez la règle du tiers : ne coupez jamais plus "
                "d'un tiers de la hauteur en une seule fois.",
                category="mowing",
                priority=1,
            )
        )

    # Mulching advice for high-intensity users
    if profile.goal == "perfect" and month in (4, 5, 6, 9):
        tasks.append(
            ProgramTask(
                icon="♻️",
                title="Mulching recommandé",
                detail="Utilisez la fonction mulching de votre tondeuse : "
                "les brins finement coupés nourrissent le sol. "
                "À éviter si le gazon est humide ou trop haut.",
                category="mowing",
                priority=3,
            )
        )

    return tasks


def _fertilisation_tasks(month: int, profile) -> list[ProgramTask]:
    """Generate fertilisation advice based on profile and season."""
    tasks: list[ProgramTask] = []

    # NPK schedules per intensity level
    if profile.goal == "perfect":
        schedule = {
            3: (
                "Engrais de démarrage",
                "NPK 20-5-8 ou similaire, 25–30 g/m². "
                "Stimule la reprise après l'hiver. Appliquer sur gazon sec.",
            ),
            5: (
                "Fertilisation de croissance",
                "NPK 15-5-15, 30 g/m². " "Renforce l'enracinement et la densité.",
            ),
            6: (
                "Entretien estival",
                "NPK 12-0-24 riche en potasse, 25 g/m². "
                "La potasse renforce la résistance à la sécheresse et aux maladies.",
            ),
            9: (
                "Fertilisation d'automne",
                "NPK 5-5-20 ou engrais automnal, 30 g/m². "
                "Prépare le gazon pour l'hiver avec un bon stock de potasse.",
            ),
            11: (
                "Dernière fertilisation",
                "Engrais organique ou compost fin, 20 g/m². "
                "Nourrit lentement le sol pendant l'hiver.",
            ),
        }
    elif profile.goal == "nice":
        schedule = {
            4: (
                "Engrais de printemps",
                "NPK équilibré (type 15-5-15), 25 g/m². "
                "Commence la saison avec un apport complet.",
            ),
            6: (
                "Fertilisation été",
                "NPK 12-0-18, 20 g/m². " "Privilégiez un engrais à libération lente.",
            ),
            9: (
                "Fertilisation d'automne",
                "NPK automnal riche en potasse, 25 g/m². "
                "Prépare les racines pour l'hiver.",
            ),
        }
    else:
        schedule = {
            4: (
                "Engrais de printemps",
                "Un seul apport printanier suffit : "
                "NPK équilibré 20 g/m² ou compost fin en surface.",
            ),
        }

    if month in schedule:
        title, detail = schedule[month]
        # Soil type adjustment
        if profile.soil_type == "sandy":
            detail += (
                " Sol sableux : fractionnez en 2 passages pour limiter le lessivage."
            )
        elif profile.soil_type == "clay":
            detail += (
                " Sol argileux : aérez au préalable pour une meilleure absorption."
            )

        tasks.append(
            ProgramTask(
                icon="🧪",
                title=title,
                detail=detail,
                category="fertilisation",
                priority=1 if profile.goal == "perfect" else 2,
            )
        )

    return tasks


def _scarification_tasks(month: int, profile) -> list[ProgramTask]:
    """Scarification / aeration schedule."""
    tasks: list[ProgramTask] = []

    if profile.goal == "basic":
        # One scarification per year in spring
        if month == 4:
            tasks.append(
                ProgramTask(
                    icon="🪥",
                    title="Scarification annuelle",
                    detail="Passez le scarificateur une fois au printemps pour "
                    "retirer feutre et mousse. Profondeur : 2–3 mm.",
                    category="scarification",
                    priority=2,
                )
            )
    elif profile.goal == "nice":
        if month in (4, 9):
            label = "de printemps" if month == 4 else "d'automne"
            tasks.append(
                ProgramTask(
                    icon="🪥",
                    title=f"Scarification {label}",
                    detail=f"Scarifiez en croisant les passages. "
                    f"{'Idéal avant le sursemis.' if month == 9 else 'Retirer feutre et mousse accumulés.'}",
                    category="scarification",
                    priority=2,
                )
            )
    else:  # perfect
        if month == 3:
            tasks.append(
                ProgramTask(
                    icon="🪥",
                    title="Pré-scarification légère",
                    detail="Passage léger pour ouvrir le feutre avant la "
                    "reprise de végétation.",
                    category="scarification",
                    priority=2,
                )
            )
        if month == 4:
            tasks.append(
                ProgramTask(
                    icon="🪥",
                    title="Scarification principale",
                    detail="Scarification croisée (2 passages perpendiculaires) "
                    "à 3 mm de profondeur. Ramassez bien les déchets.",
                    category="scarification",
                    priority=1,
                )
            )
        if month == 9:
            tasks.append(
                ProgramTask(
                    icon="🪥",
                    title="Scarification d'automne",
                    detail="Préparez le terrain pour le sursemis. "
                    "2 passages croisés puis ratissage soigneux.",
                    category="scarification",
                    priority=1,
                )
            )

    # Aeration for compacted / high-use lawns
    if profile.usage in ("sport", "family") and month in (4, 9):
        tasks.append(
            ProgramTask(
                icon="🕳️",
                title="Aération du sol",
                detail="Utilisez un aérateur à lames ou carotteur. "
                "Indispensable sur sol compacté ou très piétiné. "
                "Épandre du sable de rivière après carottage.",
                category="aeration",
                priority=1 if profile.usage == "sport" else 2,
            )
        )

    return tasks


def _overseeding_tasks(month: int, profile) -> list[ProgramTask]:
    """Overseeding (sursemis) schedule."""
    tasks: list[ProgramTask] = []

    # Degraded lawns get overseeding advice
    optimal_months = (4, 9) if profile.grass_type != "warm_season" else (5, 6)

    if month not in optimal_months:
        return tasks

    if profile.lawn_state == "degraded" or profile.goal == "perfect":
        is_autumn = month >= 9
        tasks.append(
            ProgramTask(
                icon="🌱",
                title="Sursemis" + (" d'automne" if is_autumn else " de printemps"),
                detail="Semez 20–30 g/m² de gazon de regarnissage sur les zones "
                "dégarnies. Griffez légèrement, roulez et arrosez finement "
                "pendant 2–3 semaines (sol humide en permanence)."
                + (
                    " L'automne est la meilleure période : sol chaud, "
                    "pluies régulières, moins de concurrence des adventices."
                    if is_autumn
                    else ""
                ),
                category="overseeding",
                priority=1 if profile.lawn_state == "degraded" else 2,
            )
        )

    if profile.lawn_state == "new" and month in (4, 5, 9):
        tasks.append(
            ProgramTask(
                icon="🌱",
                title="Entretien du jeune semis",
                detail="Arrosage quotidien léger (5–10 min) pendant les 3 "
                "premières semaines. Première tonte quand le gazon atteint 8–10 cm, "
                "en coupant à 5–6 cm. Évitez le piétinement.",
                category="overseeding",
                priority=1,
            )
        )

    return tasks


def _watering_tasks(month: int, profile) -> list[ProgramTask]:
    """Watering calendar rules (complement to the live weather advice)."""
    tasks: list[ProgramTask] = []

    summer = month in (6, 7, 8)
    shoulder = month in (5, 9)

    if not (summer or shoulder):
        return tasks

    if profile.has_irrigation:
        if summer:
            tasks.append(
                ProgramTask(
                    icon="💧",
                    title="Programmation arrosage été",
                    detail="Arrosez le matin tôt (avant 8h) ou en soirée. "
                    "Privilégiez des arrosages profonds et espacés "
                    "(15–20 mm, 2–3 fois/semaine) plutôt que quotidiens et légers.",
                    category="watering",
                    priority=1,
                )
            )
    else:
        if summer and profile.goal != "basic":
            tasks.append(
                ProgramTask(
                    icon="💧",
                    title="Arrosage manuel en été",
                    detail="Sans irrigation automatique, arrosez le matin tôt. "
                    "Comptez 10–15 L/m²/semaine en cas de sécheresse."
                    " Un bon arrosage copieux vaut mieux que plusieurs légers.",
                    category="watering",
                    priority=2,
                )
            )

    if profile.goal == "basic" and summer:
        tasks.append(
            ProgramTask(
                icon="🏜️",
                title="Accepter la dormance estivale",
                detail="Votre gazon peut jaunir en été sans arrosage : c'est normal ! "
                "Il repartira aux premières pluies d'automne. "
                "Ne tondez pas pendant les périodes de sécheresse.",
                category="watering",
                priority=3,
            )
        )

    return tasks


def _weed_moss_tasks(month: int, profile) -> list[ProgramTask]:
    """Weed and moss control tasks."""
    tasks: list[ProgramTask] = []

    if profile.goal == "basic":
        if month == 4:
            tasks.append(
                ProgramTask(
                    icon="🌿",
                    title="Désherbage sélectif si nécessaire",
                    detail="Arrachez manuellement les principales adventices "
                    "(pissenlits, plantains). Un gazon dense et bien tondu "
                    "est le meilleur anti-mauvaises herbes.",
                    category="weeding",
                    priority=3,
                )
            )
        return tasks

    # Spring moss treatment
    if month in (2, 3) and profile.sun_exposure in ("shade", "partial"):
        tasks.append(
            ProgramTask(
                icon="🌫️",
                title="Traitement anti-mousse",
                detail="Épandez du sulfate de fer (30 g/m²) ou un produit "
                "anti-mousse homologué. Attendez 2 semaines puis scarifiez "
                "pour retirer la mousse morte.",
                category="moss",
                priority=2,
            )
        )

    # Selective weed control
    if month in (4, 5, 9, 10) and profile.goal in ("nice", "perfect"):
        tasks.append(
            ProgramTask(
                icon="🌿",
                title="Désherbage sélectif",
                detail="Appliquez un herbicide sélectif gazon par temps doux "
                "(15–25 °C) et sans vent. Respectez les doses et les délais "
                "avant tonte. Alternative : arrachage manuel ciblé.",
                category="weeding",
                priority=2 if profile.goal == "nice" else 1,
            )
        )

    return tasks


def _disease_prevention_tasks(month: int, profile) -> list[ProgramTask]:
    """Disease and pest prevention."""
    tasks: list[ProgramTask] = []

    if profile.goal == "basic":
        return tasks

    # Fusarium risk in autumn/winter
    if month in (10, 11) and profile.goal == "perfect":
        tasks.append(
            ProgramTask(
                icon="🔬",
                title="Prévention fusariose",
                detail="Réduisez la fertilisation azotée. Évitez de tondre "
                "sur gazon mouillé. Assurez une bonne aération. "
                "Surveillez les taches brunes circulaires.",
                category="disease",
                priority=2,
            )
        )

    # Dollar spot / summer diseases
    if month in (6, 7, 8) and profile.goal == "perfect":
        tasks.append(
            ProgramTask(
                icon="🔬",
                title="Surveillance maladies estivales",
                detail="Dollar spot, fil rouge : vérifiez que la fertilisation "
                "est suffisante et l'arrosage regroupé le matin. "
                "Un gazon bien nourri résiste mieux.",
                category="disease",
                priority=3,
            )
        )

    return tasks


def _seasonal_tips(month: int, profile) -> list[str]:
    """Return a short list of bonus tips for the month."""
    tips: list[str] = []

    if month == 1:
        tips.append("Profitez de l'hiver pour entretenir et affûter vos outils.")
        tips.append("Évitez de marcher sur un gazon gelé (casse les brins).")
    elif month == 2:
        tips.append("C'est le moment de planifier vos achats : semences, engrais.")
        if profile.goal == "perfect":
            tips.append("Faites analyser votre sol pour ajuster la fertilisation.")
    elif month == 3:
        tips.append("La reprise de végétation approche dès que le sol dépasse 8 °C.")
        tips.append("Ramassez les derniers débris ou feuilles sur la pelouse.")
    elif month == 4:
        tips.append(
            "Avril est le mois clé : scarification, fertilisation, première tonte."
        )
    elif month == 5:
        tips.append("Surveillez les premières adventices et traitez tôt.")
    elif month == 6:
        tips.append("Montez progressivement la hauteur de coupe pour l'été.")
    elif month == 7:
        tips.append("En cas de forte chaleur, la pelouse ralentit naturellement.")
        tips.append(
            "Roulez le gazon tôt le matin pour refermer les fissures de sécheresse."
        )
    elif month == 8:
        tips.append("Préparez la saison d'automne : commandez semences et engrais.")
    elif month == 9:
        tips.append("Septembre est le meilleur mois pour sursemer et rénover.")
    elif month == 10:
        tips.append(
            "Ramassez les feuilles régulièrement pour ne pas étouffer le gazon."
        )
    elif month == 11:
        tips.append("Dernière tonte de la saison : hauteur 5–6 cm.")
        tips.append("Hivernez la tondeuse : vidange, affûtage de lame, nettoyage.")
    elif month == 12:
        tips.append("Le gazon est en repos. Laissez-le tranquille.")

    return tips


def _headline(month: int, profile) -> str:
    """Motivational headline for the month."""
    headlines = {
        1: "L'hiver est calme — préparez la saison à venir 🧤",
        2: "La reprise approche — planification et patience ⏳",
        3: "Le printemps s'éveille — réveillez votre gazon ! 🌱",
        4: "Mois clé — c'est LE moment d'agir ! 💪",
        5: "Croissance maximale — votre gazon explose ! 🚀",
        6: "Le gazon est magnifique — entretenez le rythme ☀️",
        7: "Attention canicule — protégez votre pelouse 🌡️",
        8: "Résistance estivale — tenez bon ! 🏖️",
        9: "Renouveau automnal — la saison idéale pour rénover 🍂",
        10: "Avant l'hiver — derniers soins importants 🍁",
        11: "Transition — préparez le gazon pour le repos hivernal ❄️",
        12: "Repos bien mérité — votre gazon hiberne 🛌",
    }
    return headlines.get(month, "")


# ---------------------------------------------------------------------------
# Issue-based corrective tasks
# ---------------------------------------------------------------------------


def _issue_tasks(profile, latest_issues: list[str]) -> list[ProgramTask]:
    """
    Generate corrective tasks based on the user's latest assessment issues.
    """
    tasks: list[ProgramTask] = []

    if not latest_issues or "none" in latest_issues:
        return tasks

    issue_handlers = {
        "weeds": ProgramTask(
            icon="🌿",
            title="Traitement mauvaises herbes",
            detail="Arrachez manuellement ou appliquez un herbicide sélectif. "
            "Resemez les zones dégarnies après traitement.",
            category="corrective",
            priority=1,
        ),
        "moss": ProgramTask(
            icon="🌫️",
            title="Traitement mousse",
            detail="Appliquez du sulfate de fer (30 g/m²), attendez 2 semaines "
            "puis scarifiez. Améliorez le drainage et la luminosité.",
            category="corrective",
            priority=1,
        ),
        "bare_patches": ProgramTask(
            icon="🌱",
            title="Regarnissage zones dégarnies",
            detail="Griffez le sol, semez 30 g/m² de gazon de regarnissage, "
            "tassez et arrosez quotidiennement pendant 3 semaines.",
            category="corrective",
            priority=1,
        ),
        "yellow": ProgramTask(
            icon="💛",
            title="Gazon jauni — diagnostic",
            detail="Causes possibles : manque d'eau, carence en azote, "
            "brûlure d'engrais ou maladie. Vérifiez l'arrosage "
            "et apportez un engrais léger si nécessaire.",
            category="corrective",
            priority=1,
        ),
        "disease": ProgramTask(
            icon="🔬",
            title="Traitement maladie",
            detail="Identifiez la maladie (fusariose, fil rouge, dollar spot…). "
            "Améliorez l'aération, réduisez l'azote, "
            "et consultez un professionnel si persistant.",
            category="corrective",
            priority=1,
        ),
        "pests": ProgramTask(
            icon="🐛",
            title="Traitement parasites",
            detail="Vérifiez la présence de vers blancs (tipules, hannetons) "
            "en soulevant le gazon. Traitez avec des nématodes "
            "auxiliaires en septembre–octobre.",
            category="corrective",
            priority=1,
        ),
        "compaction": ProgramTask(
            icon="🕳️",
            title="Décompactage urgent",
            detail="Passez l'aérateur ou le carotteur. Épandre du sable "
            "de rivière (2–3 L/m²) dans les trous. "
            "Répétez au printemps et à l'automne.",
            category="corrective",
            priority=1,
        ),
    }

    for issue in latest_issues:
        if issue in issue_handlers:
            tasks.append(issue_handlers[issue])

    return tasks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_monthly_plan(
    profile,
    month: int,
    latest_issues: list[str] | None = None,
) -> MonthlyPlan:
    """
    Build a personalised monthly plan for the given lawn profile.

    Parameters
    ----------
    profile : LawnProfile
        The user's lawn profile (model instance or equivalent).
    month : int
        Month number (1–12).
    latest_issues : list[str] | None
        Issue keys from the latest LawnAssessment, if any.

    Returns
    -------
    MonthlyPlan
    """
    tasks: list[ProgramTask] = []

    # Collect tasks from each category
    tasks.extend(_mowing_tasks(month, profile))
    tasks.extend(_fertilisation_tasks(month, profile))
    tasks.extend(_scarification_tasks(month, profile))
    tasks.extend(_overseeding_tasks(month, profile))
    tasks.extend(_watering_tasks(month, profile))
    tasks.extend(_weed_moss_tasks(month, profile))
    tasks.extend(_disease_prevention_tasks(month, profile))

    # Corrective tasks from latest assessment
    if latest_issues:
        tasks.extend(_issue_tasks(profile, latest_issues))

    # Sort: priority 1 first, then 2, then 3
    tasks.sort(key=lambda t: t.priority)

    return MonthlyPlan(
        month=month,
        month_name=MONTH_NAMES[month],
        season=MONTH_SEASON[month],
        headline=_headline(month, profile),
        tasks=tasks,
        tips=_seasonal_tips(month, profile),
    )
