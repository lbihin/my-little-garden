import pytest
from activities.models import FertilizationTask, Fertilizer
from activities.validators import validate_unit_measurement
from django.core.exceptions import ValidationError


class TestFertilizer:
    def test_str(self, fertilizer):
        assert str(fertilizer) == "TestCo NPK Universel (N=10.0%, P=10.0%, K=10.0%)"

    def test_get_element_base_composition(self, fertilizer):
        assert fertilizer.get_element_base_composition() == {
            "N": 10.0,
            "P": 10.0,
            "K": 10.0,
        }

    def test_str_partial_rates(self, db):
        fert = Fertilizer(name="Azote", company="Co", n_rate=15.0)
        assert "N=15.0%" in str(fert)


class TestFertilizationTask:
    def test_str_with_quantity(self, fertilization_task):
        assert str(fertilization_task) == "5.0 kg"

    def test_str_without_quantity(self, db):
        task = FertilizationTask()
        assert str(task) == "—"

    def test_get_quantity_display(self, fertilization_task):
        display = fertilization_task.get_quantity_display()
        assert "5" in display
        assert "kg" in display

    def test_get_quantity_display_none(self, db):
        task = FertilizationTask()
        assert task.get_quantity_display() == "—"

    def test_get_base_component_quantity(self, fertilization_task):
        result = fertilization_task.get_base_component_quantity()
        assert "N" in result
        assert "P" in result
        assert "K" in result
        # 5.0 * 10% = 0.5
        assert "0.5" in result["N"]

    def test_get_base_component_quantity_no_fertilizer(self, db):
        task = FertilizationTask(quantity_as_float=5.0, unit="kg")
        assert task.get_base_component_quantity() == {}


class TestActivity:
    def test_str(self, activity):
        assert "Activity" in str(activity)
        assert activity.garden.name in str(activity)

    def test_get_absolute_url(self, activity):
        url = activity.get_absolute_url()
        assert str(activity.pk) in url
        assert activity.garden.slug in url

    def test_get_quantity_delegates(self, activity):
        assert "kg" in activity.get_quantity()

    def test_get_quantity_no_task(self, garden):
        from activities.models import Activity
        from django.utils import timezone

        act = Activity.objects.create(creation=timezone.now(), garden=garden)
        assert act.get_quantity() == "—"


class TestUnitValidator:
    @pytest.mark.parametrize("unit", ["kg", "g", "l", "ml", "lb", "oz"])
    def test_valid_units(self, unit):
        validate_unit_measurement(unit)  # should not raise

    def test_invalid_unit(self):
        with pytest.raises(ValidationError):
            validate_unit_measurement("gallon")
