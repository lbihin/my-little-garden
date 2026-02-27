# Create your models here.
from django.db import models
from django.urls import reverse

from activities.validators import validate_unit_measurement
from app.utils import compute_time_difference
from gardens.models import Garden


class Fertilizer(models.Model):
    name = models.CharField(max_length=50, null=True, blank=True)
    company = models.CharField(max_length=50, null=True, blank=True)
    organic = models.BooleanField(default=False)
    n_rate = models.FloatField(null=True, blank=True)
    p_rate = models.FloatField(null=True, blank=True)
    k_rate = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.company} {self.name} (N={self.n_rate}%, P={self.p_rate}%, K={self.k_rate}%)"

    def get_element_base_composition(self):
        return {'N': self.n_rate, 'P': self.p_rate, 'K': self.k_rate}


class FertilizationTask(models.Model):
    quantity_as_float = models.FloatField(null=True, blank=True)
    unit = models.CharField(
        max_length=50,
        validators=[validate_unit_measurement],
        blank=True,
        null=True,
    )
    fertilizer = models.ForeignKey(Fertilizer, on_delete=models.CASCADE, null=True)

    def __str__(self):
        if self.quantity_as_float and self.unit:
            return f"{self.quantity_as_float} {self.unit}"
        return "—"

    def get_quantity_display(self):
        """Return a formatted quantity string."""
        if self.quantity_as_float is None:
            return "—"
        formatted = f"{self.quantity_as_float:,.2f}".rstrip("0").rstrip(".")
        return f"{formatted} {self.unit or ''}"

    def get_base_component_quantity(self):
        """Return NPK quantities based on fertilizer composition."""
        if not self.fertilizer or not self.quantity_as_float:
            return {}
        composition = {}
        for element, rate in self.fertilizer.get_element_base_composition().items():
            if rate:
                qty = self.quantity_as_float * rate / 100
                formatted = f"{qty:,.2f}".rstrip("0").rstrip(".")
                composition[element] = f"{formatted} {self.unit or ''}"
        return composition


class Activity(models.Model):
    creation = models.DateTimeField()
    updated = models.DateTimeField(auto_now=True)
    comment = models.TextField(blank=True, default="")
    garden = models.ForeignKey(
        Garden, on_delete=models.CASCADE, related_name="activities", null=True, blank=True
    )
    task = models.OneToOneField(
        FertilizationTask, on_delete=models.CASCADE, null=True, blank=True
    )

    class Meta:
        ordering = ("-creation",)
        verbose_name_plural = "activities"

    def __str__(self):
        return f"Activity {self.pk} — {self.garden} ({self.get_creation_date()})"

    def get_absolute_url(self):
        return reverse(
            "gardens:activities:description",
            kwargs={"garden_slug": self.garden.slug, "pk": self.pk},
        )

    def get_creation_date(self):
        return self.creation.strftime("%d.%m.%y")

    def get_updated_date(self):
        return self.updated.strftime("%d.%m.%y")

    def since_update(self):
        return compute_time_difference(self.updated)

    def get_quantity(self):
        if self.task:
            return self.task.get_quantity_display()
        return "—"

    def get_base_element_quantity(self):
        if self.task:
            return self.task.get_base_component_quantity()
        return {}

