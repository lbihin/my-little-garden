"""
Seasonal plant care knowledge base and task suggestion engine.

Generates care suggestions based on:
- Plant genus (extracted from scientific_name)
- Current month / season
- Weather conditions (air temperature, soil temperature, recent rain)

Sources:
- Royal Horticultural Society (RHS) seasonal gardening guides
- Calendrier des travaux du jardin (Rustica, Truffaut, Vilmorin)
- Standard European (zone 7-8) horticultural best practices
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)


# ─── Data structures ─────────────────────────────────────────────────


@dataclass
class CareSuggestion:
    """A suggested care task for a plant."""

    plant_id: int
    plant_name: str
    plant_slug: str
    title: str
    detail: str
    priority: int  # 1=Basse, 2=Moyenne, 3=Haute
    icon: str
    category: str  # pruning, watering, fertilizing, protection, treatment, harvest


# ─── Genus-specific care rules ───────────────────────────────────────
#
# Each rule:
#   genera  — list of genus names (first word of scientific_name)
#   months  — list of month numbers when rule applies
#   title   — short task title
#   detail  — explanation / how-to
#   priority — 1-3
#   icon    — emoji
#   category — task category
#   Optional weather filters (applied when weather data available):
#   min_air_temp / max_air_temp — air temperature thresholds
#   min_soil_temp / max_soil_temp — soil temperature thresholds

GENUS_RULES: list[dict] = [
    # ─── Rosa (Roses) ────────────────────────────────────────────
    {
        "genera": ["Rosa"],
        "months": [2, 3],
        "title": "Taille des rosiers",
        "detail": (
            "Taillez vos rosiers à 3-5 yeux au-dessus du point de greffe. "
            "Supprimez le bois mort et les branches qui se croisent. "
            "Coupez en biais à 5 mm au-dessus d'un œil tourné vers l'extérieur."
        ),
        "priority": 3,
        "icon": "✂️",
        "category": "pruning",
        "min_soil_temp": 5,
    },
    {
        "genera": ["Rosa"],
        "months": [3, 4],
        "title": "Fertilisation de printemps",
        "detail": (
            "Apportez un engrais spécial rosiers (riche en potasse) "
            "au pied de chaque rosier après la taille. Griffez légèrement le sol."
        ),
        "priority": 2,
        "icon": "🧪",
        "category": "fertilizing",
    },
    {
        "genera": ["Rosa"],
        "months": [6, 7, 8, 9],
        "title": "Suppression des fleurs fanées",
        "detail": (
            "Coupez les fleurs fanées au-dessus de la première feuille à 5 folioles "
            "pour stimuler une nouvelle floraison."
        ),
        "priority": 1,
        "icon": "🌹",
        "category": "pruning",
    },
    {
        "genera": ["Rosa"],
        "months": [6],
        "title": "Fertilisation d'été",
        "detail": (
            "Après la première vague de floraison, apportez un engrais "
            "pour soutenir la remontée."
        ),
        "priority": 2,
        "icon": "🧪",
        "category": "fertilizing",
    },
    {
        "genera": ["Rosa"],
        "months": [5, 6, 7],
        "title": "Surveillez les pucerons",
        "detail": (
            "Inspectez les jeunes pousses et boutons floraux. "
            "En cas d'attaque : jet d'eau puissant ou savon noir (30 g/L)."
        ),
        "priority": 2,
        "icon": "🐛",
        "category": "treatment",
    },
    {
        "genera": ["Rosa"],
        "months": [11, 12],
        "title": "Protection hivernale des rosiers",
        "detail": (
            "Buttez la base des rosiers avec 15-20 cm de terre ou compost. "
            "Protège le point de greffe du gel."
        ),
        "priority": 2,
        "icon": "🧣",
        "category": "protection",
    },
    {
        "genera": ["Rosa"],
        "months": [12, 1, 2],
        "title": "Traitement d'hiver (bouillie bordelaise)",
        "detail": (
            "Pulvérisez de la bouillie bordelaise sur les branches nues — "
            "prévient les maladies cryptogamiques (taches noires, rouille, oïdium). "
            "Traitez par temps sec et hors gel."
        ),
        "priority": 2,
        "icon": "💧",
        "category": "treatment",
    },
    # ─── Hydrangea (Hortensias) ──────────────────────────────────
    {
        "genera": ["Hydrangea"],
        "months": [3, 4],
        "title": "Taille des hortensias",
        "detail": (
            "Supprimez uniquement les inflorescences sèches en coupant juste "
            "au-dessus de la première paire de gros bourgeons. "
            "Ne taillez pas le vieux bois — il porte les boutons floraux."
        ),
        "priority": 3,
        "icon": "✂️",
        "category": "pruning",
    },
    {
        "genera": ["Hydrangea"],
        "months": [4, 5],
        "title": "Fertilisation des hortensias",
        "detail": (
            "Apportez un engrais pour plantes de terre de bruyère. "
            "Pour garder des fleurs bleues, ajoutez du sulfate d'aluminium "
            "(30 g pour 10 L d'eau d'arrosage)."
        ),
        "priority": 2,
        "icon": "🧪",
        "category": "fertilizing",
    },
    {
        "genera": ["Hydrangea"],
        "months": [6, 7, 8],
        "title": "Arrosage régulier des hortensias",
        "detail": (
            "Les hortensias sont de gros buveurs — arrosez copieusement "
            "2 à 3 fois par semaine en été, de préférence le soir. "
            "Paillez le pied pour conserver l'humidité."
        ),
        "priority": 3,
        "icon": "💧",
        "category": "watering",
    },
    {
        "genera": ["Hydrangea"],
        "months": [11],
        "title": "Paillage hivernal des hortensias",
        "detail": (
            "Paillez généreusement le pied (feuilles mortes, BRF) "
            "pour protéger les racines superficielles du gel."
        ),
        "priority": 2,
        "icon": "🍂",
        "category": "protection",
    },
    # ─── Lavandula (Lavandes) ────────────────────────────────────
    {
        "genera": ["Lavandula"],
        "months": [3, 4],
        "title": "Taille de nettoyage de la lavande",
        "detail": (
            "Taillez d'un tiers en boule arrondie pour supprimer "
            "le bois mort et rajeunir la touffe. "
            "Attention : ne jamais couper dans le vieux bois sans feuilles."
        ),
        "priority": 2,
        "icon": "✂️",
        "category": "pruning",
    },
    {
        "genera": ["Lavandula"],
        "months": [7, 8],
        "title": "Récolte de la lavande",
        "detail": (
            "Récoltez les épis floraux quand les fleurs du bas commencent à faner. "
            "Coupez les tiges à mi-longueur. Faites sécher en bouquets suspendus "
            "dans un endroit aéré et sombre."
        ),
        "priority": 2,
        "icon": "💐",
        "category": "harvest",
    },
    {
        "genera": ["Lavandula"],
        "months": [9],
        "title": "Taille de mise en forme",
        "detail": (
            "Après la floraison, donnez une forme compacte et arrondie "
            "à la touffe pour éviter qu'elle ne se dégarnisse du centre."
        ),
        "priority": 1,
        "icon": "✂️",
        "category": "pruning",
    },
    # ─── Prunus (Cerisiers, Pruniers, Abricotiers) ──────────────
    {
        "genera": ["Prunus"],
        "months": [2, 3],
        "title": "Taille de formation des arbres fruitiers",
        "detail": (
            "Taillez avant le débourrement (gonflement des bourgeons). "
            "Supprimez bois mort, branches concurrentes et gourmands. "
            "Appliquez un mastic cicatrisant sur les grosses coupes."
        ),
        "priority": 3,
        "icon": "✂️",
        "category": "pruning",
    },
    {
        "genera": ["Prunus"],
        "months": [11, 12],
        "title": "Traitement hivernal des fruitiers",
        "detail": (
            "Pulvérisez de la bouillie bordelaise à la chute des feuilles "
            "et en fin d'hiver pour prévenir la cloque, la moniliose "
            "et les chancres. Ramassez les fruits momifiés."
        ),
        "priority": 2,
        "icon": "💧",
        "category": "treatment",
    },
    {
        "genera": ["Prunus"],
        "months": [6, 7],
        "title": "Récolte et taille d'été",
        "detail": (
            "Récoltez les cerises bien mûres. Après récolte, pratiquez "
            "une taille d'éclaircie pour aérer le houppier."
        ),
        "priority": 2,
        "icon": "🍒",
        "category": "harvest",
    },
    # ─── Malus & Pyrus (Pommiers, Poiriers) ─────────────────────
    {
        "genera": ["Malus", "Pyrus"],
        "months": [2, 3],
        "title": "Taille de fructification",
        "detail": (
            "Éclaircissez le centre de l'arbre pour laisser passer la lumière. "
            "Raccourcissez les rameaux à fruits à 3-5 yeux. "
            "Supprimez les gourmands verticaux."
        ),
        "priority": 3,
        "icon": "✂️",
        "category": "pruning",
    },
    {
        "genera": ["Malus", "Pyrus"],
        "months": [6],
        "title": "Éclaircissage des fruits",
        "detail": (
            "Supprimez les fruits en excès pour ne garder que 1-2 fruits "
            "par bouquet. Les fruits restants seront plus gros et savoureux."
        ),
        "priority": 2,
        "icon": "🍎",
        "category": "pruning",
    },
    {
        "genera": ["Malus"],
        "months": [8, 9, 10],
        "title": "Récolte des pommes",
        "detail": (
            "Récoltez quand le fruit se détache facilement en le tournant "
            "légèrement. Stockez dans un endroit frais, sombre et aéré."
        ),
        "priority": 2,
        "icon": "🍎",
        "category": "harvest",
    },
    {
        "genera": ["Malus", "Pyrus"],
        "months": [3],
        "title": "Traitement préventif (carpocapse)",
        "detail": (
            "Installez des pièges à phéromones pour lutter contre le ver "
            "de la pomme (carpocapse). Pulvérisez de la bouillie bordelaise."
        ),
        "priority": 2,
        "icon": "🐛",
        "category": "treatment",
    },
    # ─── Herbs: Rosmarinus, Thymus, Salvia, Mentha ──────────────
    {
        "genera": ["Rosmarinus", "Salvia", "Thymus", "Mentha", "Origanum", "Ocimum"],
        "months": [3, 4],
        "title": "Taille de nettoyage des aromatiques",
        "detail": (
            "Supprimez les tiges sèches et abîmées par l'hiver. "
            "Raccourcissez légèrement pour favoriser la ramification."
        ),
        "priority": 2,
        "icon": "✂️",
        "category": "pruning",
    },
    {
        "genera": ["Rosmarinus", "Salvia", "Thymus", "Mentha", "Origanum", "Ocimum"],
        "months": [5, 6],
        "title": "Pincement des aromatiques",
        "detail": (
            "Pincez les extrémités des tiges pour stimuler la ramification "
            "et obtenir des plantes plus touffues et productives."
        ),
        "priority": 1,
        "icon": "🌿",
        "category": "pruning",
    },
    {
        "genera": ["Rosmarinus", "Salvia", "Thymus", "Mentha", "Origanum", "Ocimum"],
        "months": [6, 7, 8, 9],
        "title": "Récolte des aromatiques",
        "detail": (
            "Récoltez régulièrement les feuilles et tiges — "
            "cela stimule la croissance. Récoltez le matin après "
            "l'évaporation de la rosée, avant les fortes chaleurs."
        ),
        "priority": 1,
        "icon": "🌿",
        "category": "harvest",
    },
    # ─── Olea (Oliviers) ────────────────────────────────────────
    {
        "genera": ["Olea"],
        "months": [3, 4],
        "title": "Taille d'entretien de l'olivier",
        "detail": (
            "Aérez le centre de l'arbre et supprimez les rejets au pied. "
            "Raccourcissez les branches ayant fructifié l'année précédente."
        ),
        "priority": 2,
        "icon": "✂️",
        "category": "pruning",
    },
    {
        "genera": ["Olea"],
        "months": [10, 11],
        "title": "Récolte des olives",
        "detail": (
            "Récoltez les olives vertes en octobre ou noires en novembre, "
            "selon l'usage (table ou huile). Utilisez un peigne ou récoltez à la main."
        ),
        "priority": 2,
        "icon": "🫒",
        "category": "harvest",
    },
    # ─── Rhododendron, Azalea, Camellia (Ericacées) ─────────────
    {
        "genera": ["Rhododendron", "Azalea", "Camellia"],
        "months": [4, 5, 6],
        "title": "Suppression des fleurs fanées",
        "detail": (
            "Cassez délicatement les inflorescences fanées à la main "
            "(pas au sécateur) juste en dessous de la fleur. "
            "Cela concentre l'énergie vers les boutons floraux de l'an prochain."
        ),
        "priority": 2,
        "icon": "🌺",
        "category": "pruning",
    },
    {
        "genera": ["Rhododendron", "Azalea", "Camellia"],
        "months": [4, 5],
        "title": "Fertilisation acide",
        "detail": (
            "Apportez un engrais spécial terre de bruyère. "
            "Paillez avec de l'écorce de pin pour maintenir un sol acide."
        ),
        "priority": 2,
        "icon": "🧪",
        "category": "fertilizing",
    },
    # ─── Vitis (Vigne) ──────────────────────────────────────────
    {
        "genera": ["Vitis"],
        "months": [2, 3],
        "title": "Taille de la vigne",
        "detail": (
            "Taillez les sarments de l'année précédente à 2-3 yeux. "
            "Forme en gobelet ou en cordon selon le palissage."
        ),
        "priority": 3,
        "icon": "✂️",
        "category": "pruning",
    },
    {
        "genera": ["Vitis"],
        "months": [5, 6],
        "title": "Ébourgeonnage et palissage",
        "detail": (
            "Supprimez les bourgeons en surnombre et attachez les pousses "
            "au palissage. Supprimez les entre-cœurs pour aérer."
        ),
        "priority": 2,
        "icon": "🌿",
        "category": "pruning",
    },
    {
        "genera": ["Vitis"],
        "months": [8, 9],
        "title": "Récolte du raisin",
        "detail": (
            "Récoltez lorsque les baies sont bien colorées et sucrées. "
            "Le raisin ne mûrit plus une fois coupé — testez avant !"
        ),
        "priority": 2,
        "icon": "🍇",
        "category": "harvest",
    },
    # ─── Wisteria (Glycine) ─────────────────────────────────────
    {
        "genera": ["Wisteria"],
        "months": [7, 8],
        "title": "Taille d'été de la glycine",
        "detail": (
            "Raccourcissez toutes les pousses de l'année à 5-6 bourgeons "
            "(environ 20 cm). Cela favorise la formation des boutons floraux."
        ),
        "priority": 2,
        "icon": "✂️",
        "category": "pruning",
    },
    {
        "genera": ["Wisteria"],
        "months": [2],
        "title": "Taille d'hiver de la glycine",
        "detail": (
            "Raccourcissez les pousses taillées en été à 2-3 bourgeons. "
            "Supprimez le bois mort et les branches mal placées."
        ),
        "priority": 3,
        "icon": "✂️",
        "category": "pruning",
    },
    # ─── Buxus (Buis) ───────────────────────────────────────────
    {
        "genera": ["Buxus"],
        "months": [5, 6],
        "title": "Première taille du buis",
        "detail": (
            "Taillez en forme (boule, cône, haie) après les dernières gelées. "
            "Travaillez par temps couvert pour éviter les brûlures."
        ),
        "priority": 2,
        "icon": "✂️",
        "category": "pruning",
    },
    {
        "genera": ["Buxus"],
        "months": [9],
        "title": "Seconde taille du buis",
        "detail": (
            "Retouchez la forme avant l'automne. Dernière taille de l'année "
            "pour que les nouvelles pousses aient le temps de durcir."
        ),
        "priority": 1,
        "icon": "✂️",
        "category": "pruning",
    },
    {
        "genera": ["Buxus"],
        "months": [5, 6, 7, 8],
        "title": "Surveillez la pyrale du buis",
        "detail": (
            "Inspectez régulièrement les feuilles intérieures — "
            "cherchez de petites chenilles vertes et des fils de soie. "
            "Traitez au Bacillus thuringiensis (Bt) dès l'apparition."
        ),
        "priority": 3,
        "icon": "🐛",
        "category": "treatment",
    },
    # ─── Solanum (Tomates) ──────────────────────────────────────
    {
        "genera": ["Solanum"],
        "months": [5],
        "title": "Plantation des tomates",
        "detail": (
            "Après les Saints de Glace (15 mai), plantez les pieds en pleine terre. "
            "Enterrez profondément la tige — elle produira de nouvelles racines."
        ),
        "priority": 3,
        "icon": "🌱",
        "category": "planting",
        "min_air_temp": 10,
    },
    {
        "genera": ["Solanum"],
        "months": [6, 7, 8],
        "title": "Taille des gourmands",
        "detail": (
            "Supprimez les gourmands (pousses à l'aisselle des feuilles) "
            "pour concentrer l'énergie vers les fruits. "
            "Tuteurez solidement les pieds."
        ),
        "priority": 2,
        "icon": "🍅",
        "category": "pruning",
    },
    {
        "genera": ["Solanum"],
        "months": [6, 7, 8, 9],
        "title": "Arrosage régulier des tomates",
        "detail": (
            "Arrosez au pied (jamais le feuillage !) 2-3 fois par semaine. "
            "Paillez pour conserver l'humidité et prévenir le mildiou."
        ),
        "priority": 3,
        "icon": "💧",
        "category": "watering",
    },
    # ─── Fragaria (Fraisiers) ───────────────────────────────────
    {
        "genera": ["Fragaria"],
        "months": [3, 4],
        "title": "Nettoyage des fraisiers",
        "detail": (
            "Supprimez les feuilles sèches ou malades. "
            "Griffez le sol entre les rangs et apportez du compost."
        ),
        "priority": 2,
        "icon": "🍓",
        "category": "pruning",
    },
    {
        "genera": ["Fragaria"],
        "months": [8, 9],
        "title": "Suppression des stolons",
        "detail": (
            "Coupez les stolons pour concentrer l'énergie sur le pied-mère — "
            "sauf si vous voulez multiplier vos fraisiers. "
            "Dans ce cas, plantez les stolons enracinés."
        ),
        "priority": 1,
        "icon": "✂️",
        "category": "pruning",
    },
]

# ─── Universal seasonal rules (apply to all plants) ─────────────────

SEASONAL_RULES: list[dict] = [
    # Spring
    {
        "months": [3, 4],
        "title": "Désherbage de printemps",
        "detail": (
            "Désherbez autour du pied pour éviter la concurrence en eau "
            "et en nutriments au démarrage de la végétation."
        ),
        "priority": 1,
        "icon": "🌱",
        "category": "maintenance",
    },
    {
        "months": [3, 4, 5],
        "title": "Paillage de printemps",
        "detail": (
            "Mettez en place un paillage (5-10 cm) au pied — "
            "écorce, BRF, paille ou feuilles mortes. "
            "Réduit le désherbage, conserve l'humidité et protège le sol."
        ),
        "priority": 2,
        "icon": "🍂",
        "category": "maintenance",
    },
    {
        "months": [4, 5],
        "title": "Fertilisation de printemps",
        "detail": (
            "Reprise de végétation : apportez un engrais organique complet "
            "(compost mûr, fumier décomposé) au pied."
        ),
        "priority": 2,
        "icon": "🧪",
        "category": "fertilizing",
    },
    # Summer
    {
        "months": [7, 8],
        "title": "Vérification de l'arrosage",
        "detail": (
            "Vérifiez l'humidité du sol en enfonçant un doigt à 5 cm. "
            "Si sec, arrosez copieusement le soir de préférence."
        ),
        "priority": 2,
        "icon": "💧",
        "category": "watering",
    },
    # Autumn
    {
        "months": [10, 11],
        "title": "Paillage hivernal",
        "detail": (
            "Installez un paillage épais (10-15 cm de feuilles mortes ou BRF) "
            "au pied pour protéger les racines du gel."
        ),
        "priority": 2,
        "icon": "🍂",
        "category": "protection",
    },
    {
        "months": [10, 11],
        "title": "Nettoyage d'automne",
        "detail": (
            "Ramassez les feuilles mortes et les débris végétaux pour prévenir "
            "les maladies fongiques qui hivernent dans les débris."
        ),
        "priority": 1,
        "icon": "🍁",
        "category": "maintenance",
    },
]

# ─── Weather-based rules (apply when conditions are met) ─────────────

WEATHER_RULES: list[dict] = [
    {
        "condition": "frost",
        "title": "Protection contre le gel",
        "detail": (
            "Températures en dessous de -3°C — protégez les plantes sensibles "
            "avec un voile d'hivernage ou rentrez les pots à l'abri."
        ),
        "priority": 3,
        "icon": "🥶",
        "category": "protection",
    },
    {
        "condition": "heat",
        "title": "Arrosage renforcé (canicule)",
        "detail": (
            "Températures supérieures à 30°C — arrosez copieusement le soir. "
            "Ombrez les plantes les plus fragiles si possible."
        ),
        "priority": 3,
        "icon": "🌡️",
        "category": "watering",
    },
    {
        "condition": "drought",
        "title": "Attention sécheresse",
        "detail": (
            "Peu ou pas de pluie récente — vérifiez l'humidité du sol "
            "et arrosez si nécessaire. Paillez pour réduire l'évaporation."
        ),
        "priority": 2,
        "icon": "☀️",
        "category": "watering",
    },
]

# ─── Common name → genus fallback mapping ────────────────────────────

_COMMON_HINTS: dict[str, str] = {
    "rose": "Rosa",
    "rosier": "Rosa",
    "lavande": "Lavandula",
    "hortensia": "Hydrangea",
    "cerisier": "Prunus",
    "prunier": "Prunus",
    "abricotier": "Prunus",
    "pêcher": "Prunus",
    "pommier": "Malus",
    "poirier": "Pyrus",
    "tomate": "Solanum",
    "romarin": "Rosmarinus",
    "thym": "Thymus",
    "sauge": "Salvia",
    "menthe": "Mentha",
    "basilic": "Ocimum",
    "origan": "Origanum",
    "olivier": "Olea",
    "glycine": "Wisteria",
    "buis": "Buxus",
    "vigne": "Vitis",
    "fraisier": "Fragaria",
    "fraise": "Fragaria",
    "rhododendron": "Rhododendron",
    "azalée": "Azalea",
    "camélia": "Camellia",
}


# ─── Suggestion engine ───────────────────────────────────────────────


def _extract_genus(scientific_name: str) -> str:
    """Extract genus (first word) from a scientific name like 'Lavandula angustifolia'."""
    if not scientific_name:
        return ""
    return scientific_name.strip().split()[0]


def _guess_genus(common_name: str) -> str:
    """Try to guess genus from the French common name."""
    if not common_name:
        return ""
    lower = common_name.strip().lower()
    for hint, genus in _COMMON_HINTS.items():
        if hint in lower:
            return genus
    return ""


def _check_weather_rule(
    rule: dict,
    air_temp: float | None,
    recent_rain_mm: float | None,
) -> bool:
    """Check if a weather-based rule's condition is met."""
    condition = rule["condition"]
    if condition == "frost" and air_temp is not None:
        return air_temp < -3
    if condition == "heat" and air_temp is not None:
        return air_temp > 30
    if condition == "drought" and recent_rain_mm is not None:
        return recent_rain_mm < 2  # Less than 2mm in the last 48h
    return False


def _check_genus_weather(
    rule: dict,
    air_temp: float | None,
    soil_temp: float | None,
) -> bool:
    """Check optional weather filters on a genus rule."""
    if "min_air_temp" in rule and air_temp is not None:
        if air_temp < rule["min_air_temp"]:
            return False
    if "max_air_temp" in rule and air_temp is not None:
        if air_temp > rule["max_air_temp"]:
            return False
    if "min_soil_temp" in rule and soil_temp is not None:
        if soil_temp < rule["min_soil_temp"]:
            return False
    if "max_soil_temp" in rule and soil_temp is not None:
        if soil_temp > rule["max_soil_temp"]:
            return False
    return True


def suggest_care_tasks(
    plants: list,
    month: int | None = None,
    air_temp: float | None = None,
    soil_temp: float | None = None,
    recent_rain_mm: float | None = None,
    existing_task_titles: set[str] | None = None,
) -> list[CareSuggestion]:
    """
    Generate care suggestions for a list of plants.

    Args:
        plants: List of Plant model instances.
        month: Current month (1-12). Defaults to today's month.
        air_temp: Current air temperature (°C).
        soil_temp: Current soil temperature at 6cm (°C).
        recent_rain_mm: Total precipitation in last 48h (mm).
        existing_task_titles: Set of existing task titles (to avoid duplicates).

    Returns:
        List of CareSuggestion objects, sorted by priority (highest first).
    """
    if month is None:
        month = date.today().month

    if existing_task_titles is None:
        existing_task_titles = set()

    # Normalize existing titles for comparison
    existing_normalized = {t.lower().strip() for t in existing_task_titles}

    suggestions: list[CareSuggestion] = []
    seen_keys: set[str] = set()  # Avoid duplicate suggestions

    for plant in plants:
        plant_id = plant.pk
        plant_name = plant.common_name or plant.scientific_name or "Plante"
        plant_slug = plant.slug

        # Determine genus
        genus = _extract_genus(plant.scientific_name)
        if not genus:
            genus = _guess_genus(plant.common_name)

        # 1) Genus-specific rules
        if genus:
            for rule in GENUS_RULES:
                if genus not in rule["genera"]:
                    continue
                if month not in rule["months"]:
                    continue
                if not _check_genus_weather(rule, air_temp, soil_temp):
                    continue

                # Deduplicate
                key = f"{plant_id}:{rule['title']}"
                if key in seen_keys:
                    continue
                if rule["title"].lower().strip() in existing_normalized:
                    continue
                seen_keys.add(key)

                suggestions.append(
                    CareSuggestion(
                        plant_id=plant_id,
                        plant_name=plant_name,
                        plant_slug=plant_slug,
                        title=rule["title"],
                        detail=rule["detail"],
                        priority=rule["priority"],
                        icon=rule["icon"],
                        category=rule["category"],
                    )
                )

        # 2) Universal seasonal rules
        for rule in SEASONAL_RULES:
            if month not in rule["months"]:
                continue

            key = f"{plant_id}:{rule['title']}"
            if key in seen_keys:
                continue
            if rule["title"].lower().strip() in existing_normalized:
                continue
            seen_keys.add(key)

            suggestions.append(
                CareSuggestion(
                    plant_id=plant_id,
                    plant_name=plant_name,
                    plant_slug=plant_slug,
                    title=rule["title"],
                    detail=rule["detail"],
                    priority=rule["priority"],
                    icon=rule["icon"],
                    category=rule["category"],
                )
            )

        # 3) Weather-based rules
        for rule in WEATHER_RULES:
            if not _check_weather_rule(rule, air_temp, recent_rain_mm):
                continue

            key = f"{plant_id}:{rule['title']}"
            if key in seen_keys:
                continue
            if rule["title"].lower().strip() in existing_normalized:
                continue
            seen_keys.add(key)

            suggestions.append(
                CareSuggestion(
                    plant_id=plant_id,
                    plant_name=plant_name,
                    plant_slug=plant_slug,
                    title=rule["title"],
                    detail=rule["detail"],
                    priority=rule["priority"],
                    icon=rule["icon"],
                    category=rule["category"],
                )
            )

    # Sort by priority (high first), then by plant name
    suggestions.sort(key=lambda s: (-s.priority, s.plant_name))

    return suggestions
