from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.urls import reverse
from geopy import Nominatim

from app.utils import compute_time_difference
from gardens import utils


class Address(models.Model):
    name = models.CharField(max_length=60)
    street = models.CharField(max_length=60, default="")
    city = models.CharField(max_length=60, default="")
    state = models.CharField(max_length=60, blank=True, null=True)
    postal_code = models.CharField(max_length=10, default="")
    country = models.CharField(max_length=30, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)

    class Meta:
        verbose_name_plural = "addresses"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.latitude or not self.longitude:
            self.get_lat_lon()
        super().save(*args, **kwargs)

    def get_lat_lon(self):
        address_components = list(
            filter(None, [self.street, self.city, self.state, self.postal_code])
        )
        address_string = ", ".join(address_components)
        geolocator = Nominatim(user_agent="myLittleGardenApp")
        location = geolocator.geocode(address_string)
        if location:
            self.latitude = location.latitude
            self.longitude = location.longitude

    def get_not_empty_fields(self):
        """Returns a list of (field_name, value) tuples for non-empty address fields."""
        field_list = ["street", "state", "postal_code", "city", "country"]
        return [
            (field.name, field.value_to_string(self))
            for field in Address._meta.fields
            if field.name in field_list and getattr(self, field.name)
        ]


class GardenQuerySet(models.QuerySet):
    def search(self, query):
        if not query:
            return self.none()
        lookups = Q(name__icontains=query) | Q(description__icontains=query)
        return self.filter(lookups)


class GardenManager(models.Manager):
    def get_queryset(self):
        return GardenQuerySet(self.model, using=self._db)

    def search(self, query):
        return self.get_queryset().search(query=query)


class Garden(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        related_name="gardens",
    )
    name = models.CharField(max_length=128)
    slug = models.SlugField(unique=True, blank=True, null=True)
    description = models.TextField(blank=True, default="")
    creation = models.DateField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    address = models.ForeignKey(
        Address, on_delete=models.SET_NULL, related_name="gardens", null=True, blank=True
    )
    surface = models.PositiveIntegerField(default=0)

    objects = GardenManager()

    def __str__(self):
        return self.name

    def has_address(self):
        return self.address is not None

    def get_last_update(self):
        return compute_time_difference(self.updated)

    def get_absolute_url(self):
        return reverse("gardens:detail", kwargs={"slug": self.slug})

    def get_edit_url(self):
        return reverse("gardens:edit", kwargs={"slug": self.slug})

    def get_delete_url(self):
        return reverse("gardens:delete", kwargs={"slug": self.slug})


@receiver(pre_save, sender=Garden)
def garden_pre_save(sender, instance, *args, **kwargs):
    utils.slugify_instance_name(instance, save=False)


@receiver(post_save, sender=Garden)
def garden_post_save(sender, instance, created, *args, **kwargs):
    if created:
        utils.slugify_instance_name(instance, save=True)


