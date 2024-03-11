# Create your models here.
import pint
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
    unit = models.CharField(max_length=50, validators=[validate_unit_measurement], blank=True, null=True)
    fertilizer = models.ForeignKey(Fertilizer, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"{self.quantity_as_float}{self.unit}"

    def convert_to_system(self, quantity, system="mks"):
        if quantity is None:
            return None
        ureg = pint.UnitRegistry(system=system)
        return quantity * ureg[self.unit.lower()]

    def as_mks(self, quantity):
        # meter, kilogram, second
        measurement = self.convert_to_system(quantity, system='mks').to_base_units()
        number = measurement.magnitude
        unit = measurement.units
        formatted_number = "{:,.2f}".format(number).rstrip('0').rstrip('.').replace(",", ".")
        return "{} {:~}".format(formatted_number, unit)

    def get_quantity(self, system="mks"):
        return self.compute_quantity(self.quantity_as_float, system=system)

    def compute_quantity(self, quantity, system="mks"):
        if system == "mks":
            return self.as_mks(quantity)
        elif system == "imperial":
            return self.as_imperial(quantity)

    def as_imperial(self, quantity):
        # miles, pounds, seconds
        measurement = self.convert_to_system(quantity, system='imperial')
        number = measurement.magnitude
        unit = measurement.units
        formatted_number = "{:,.2f}".format(number).rstrip('0').rstrip('.').replace(",", ".")
        return "{} {:~}".format(formatted_number, unit)

    def get_nitrogen_quantity(self, system='mks'):
        quantity = self.quantity_as_float * self.fertilizer.n_rate / 100
        return self.compute_quantity(quantity, system=system)

    def get_base_component_quantity(self, system='mks'):
        composition = {}
        for element, rate in self.fertilizer.get_element_base_composition().items():
            quantity = self.quantity_as_float * rate/100
            composition[element] = self.compute_quantity(quantity, system=system)
        return composition


class Activity(models.Model):
    creation = models.DateTimeField()
    updated = models.DateTimeField(auto_now=True)
    comment = models.TextField()
    garden = models.ForeignKey(Garden, on_delete=models.CASCADE, related_name='activities', null=True, blank=True)
    fertilization = models.OneToOneField(FertilizationTask, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ('creation',)

    def get_absolute_url(self):
        return reverse('gardens:activities:description', kwargs={'garden_slug': self.garden.slug, 'pk':self.pk})

    def get_creation_date(self):
        return self.creation.strftime('%d.%m.%y')

    def get_updated_date(self):
        return self.updated.strftime('%d.%m.%y')

    def since_update(self):
        return compute_time_difference(self.updated)

    def get_children_fertilization(self):
        if self.fertilization:
            return self.fertilization

    def get_quantity(self):
        if obj := self.get_children_fertilization():
            return obj.get_quantity()
        return '-'

    def get_base_element_quantity(self):
        if obj := self.get_children_fertilization():
            return obj.get_base_component_quantity()
        return '-'
