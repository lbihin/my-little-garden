"""
Models for the "Follow the Pro" lawn care program.

Stores:
- LawnProfile: the user's lawn characteristics from the questionnaire
- LawnAssessment: periodic reviews (photos + self-evaluation)
"""

from django.db import models
from django.urls import reverse
from gardens.models import Garden


class LawnProfile(models.Model):
    """User's lawn profile — filled via the onboarding questionnaire."""

    # ── Grass type ──
    GRASS_TYPE_CHOICES = [
        ("cool_season", "Saison froide (ray-grass, fétuque, pâturin)"),
        ("warm_season", "Saison chaude (bermuda, zoysia, kikuyu)"),
        ("mixed", "Mélange / Je ne sais pas"),
    ]

    # ── Current state ──
    LAWN_STATE_CHOICES = [
        ("new", "Nouveau semis (< 6 mois)"),
        ("young", "Jeune gazon (6–18 mois)"),
        ("established", "Gazon établi (> 18 mois)"),
        ("degraded", "Dégradé / à rénover"),
    ]

    # ── Usage ──
    USAGE_CHOICES = [
        ("decorative", "Décoratif — peu piétiné"),
        ("family", "Familial — enfants, animaux"),
        ("sport", "Sportif — terrain de jeux"),
    ]

    # ── Sun exposure ──
    SUN_CHOICES = [
        ("full_sun", "Plein soleil (> 6h/jour)"),
        ("partial", "Mi-ombre (3–6h/jour)"),
        ("shade", "Ombre (< 3h/jour)"),
    ]

    # ── Soil type ──
    SOIL_CHOICES = [
        ("clay", "Argileux (lourd, collant)"),
        ("loam", "Limoneux (équilibré)"),
        ("sandy", "Sableux (drainant)"),
        ("unknown", "Je ne sais pas"),
    ]

    # ── Goal / ambition ──
    GOAL_CHOICES = [
        ("basic", "Propre et vert — sans se prendre la tête"),
        ("nice", "Beau gazon — effort modéré"),
        ("perfect", "Gazon de rêve — je suis motivé !"),
    ]

    garden = models.OneToOneField(
        Garden,
        on_delete=models.CASCADE,
        related_name="lawn_profile",
    )
    grass_type = models.CharField(
        max_length=20, choices=GRASS_TYPE_CHOICES, default="mixed"
    )
    lawn_state = models.CharField(
        max_length=20, choices=LAWN_STATE_CHOICES, default="established"
    )
    usage = models.CharField(max_length=20, choices=USAGE_CHOICES, default="family")
    sun_exposure = models.CharField(
        max_length=20, choices=SUN_CHOICES, default="full_sun"
    )
    soil_type = models.CharField(max_length=20, choices=SOIL_CHOICES, default="unknown")
    goal = models.CharField(max_length=20, choices=GOAL_CHOICES, default="nice")
    has_irrigation = models.BooleanField(
        default=False,
        verbose_name="Système d'arrosage automatique",
    )
    mowing_frequency = models.PositiveSmallIntegerField(
        default=1,
        help_text="Nombre de tontes par semaine en saison de pousse",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profil gazon — {self.garden.name}"

    def get_absolute_url(self):
        return reverse(
            "gardens:weather:program",
            kwargs={"garden_slug": self.garden.slug},
        )

    @property
    def intensity(self) -> str:
        """Map the user's goal to an intensity level used by the program engine."""
        return {"basic": "low", "nice": "medium", "perfect": "high"}[self.goal]


class LawnAssessment(models.Model):
    """Periodic review of the lawn's condition by the user."""

    RATING_CHOICES = [
        (1, "😞 Très mauvais"),
        (2, "😕 Pas top"),
        (3, "🙂 Correct"),
        (4, "😊 Bien"),
        (5, "🤩 Excellent"),
    ]

    ISSUE_CHOICES = [
        ("weeds", "Mauvaises herbes"),
        ("moss", "Mousse"),
        ("bare_patches", "Zones dégarnies"),
        ("yellow", "Jaunissement"),
        ("disease", "Maladie / champignons"),
        ("pests", "Insectes / vers blancs"),
        ("compaction", "Sol compacté"),
        ("none", "Rien à signaler ✓"),
    ]

    lawn_profile = models.ForeignKey(
        LawnProfile,
        on_delete=models.CASCADE,
        related_name="assessments",
    )
    date = models.DateField(auto_now_add=True)
    overall_rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, default=3)
    issues = models.JSONField(
        default=list,
        blank=True,
        help_text="List of issue keys from ISSUE_CHOICES",
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Évaluation {self.date} — {self.get_overall_rating_display()}"

    def get_issue_labels(self) -> list[str]:
        """Return human-readable issue labels."""
        issue_map = dict(self.ISSUE_CHOICES)
        return [issue_map.get(i, i) for i in (self.issues or [])]
