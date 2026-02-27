import random

from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify


class PlantQuerySet(models.QuerySet):
    def search(self, query):
        if not query:
            return self.none()
        lookups = (
            Q(common_name__icontains=query)
            | Q(scientific_name__icontains=query)
            | Q(notes__icontains=query)
        )
        return self.filter(lookups)


class PlantManager(models.Manager):
    def get_queryset(self):
        return PlantQuerySet(self.model, using=self._db)

    def search(self, query):
        return self.get_queryset().search(query=query)


class Plant(models.Model):
    """A plant in the user's garden, optionally identified via PlantNet."""

    garden = models.ForeignKey(
        "gardens.Garden",
        on_delete=models.CASCADE,
        related_name="plants",
    )
    common_name = models.CharField(max_length=150)
    scientific_name = models.CharField(max_length=200, blank=True, default="")
    slug = models.SlugField(unique=True, blank=True, null=True)
    photo_url = models.URLField(
        blank=True,
        default="",
        help_text="URL of the plant photo (e.g. from PlantNet identification)",
    )
    identification_score = models.FloatField(
        blank=True,
        null=True,
        help_text="PlantNet confidence score (0-1)",
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlantManager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        if self.scientific_name:
            return f"{self.common_name} ({self.scientific_name})"
        return self.common_name

    def get_absolute_url(self):
        return reverse(
            "gardens:plants:detail",
            kwargs={
                "garden_slug": self.garden.slug,
                "slug": self.slug,
            },
        )

    def pending_tasks_count(self):
        return self.tasks.filter(done=False).count()


def _slugify_plant(instance, save=False, new_slug=None):
    if new_slug is not None:
        slug = new_slug
    else:
        slug = slugify(instance.common_name)
    qs = Plant.objects.filter(slug=slug).exclude(id=instance.id)
    if qs.exists():
        rand_int = random.randint(300_000, 500_000)
        slug = f"{slug}-{rand_int}"
        return _slugify_plant(instance, save=save, new_slug=slug)
    instance.slug = slug
    if save:
        instance.save()
    return instance


@receiver(pre_save, sender=Plant)
def plant_pre_save(sender, instance, *args, **kwargs):
    _slugify_plant(instance, save=False)


@receiver(post_save, sender=Plant)
def plant_post_save(sender, instance, created, *args, **kwargs):
    if created:
        _slugify_plant(instance, save=True)


class PlantTask(models.Model):
    """A to-do item for a specific plant."""

    PRIORITY_CHOICES = [
        (1, "Basse"),
        (2, "Moyenne"),
        (3, "Haute"),
    ]

    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True, default="")
    priority = models.PositiveSmallIntegerField(
        choices=PRIORITY_CHOICES,
        default=2,
    )
    done = models.BooleanField(default=False)
    due_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["done", "-priority", "due_date"]

    def __str__(self):
        return self.title
