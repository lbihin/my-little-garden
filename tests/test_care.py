"""Tests for the plant care suggestion engine."""

from unittest.mock import MagicMock

import pytest
from plants.care import (
    CareSuggestion,
    _check_genus_weather,
    _check_weather_rule,
    _extract_genus,
    _guess_genus,
    suggest_care_tasks,
)
from plants.models import Plant, PlantTask

# ── Helper tests ──────────────────────────────────────────────


class TestExtractGenus:
    def test_standard_binomial(self):
        assert _extract_genus("Lavandula angustifolia") == "Lavandula"

    def test_single_word(self):
        assert _extract_genus("Rosa") == "Rosa"

    def test_empty_string(self):
        assert _extract_genus("") == ""

    def test_none_string(self):
        assert _extract_genus("") == ""

    def test_with_extra_spaces(self):
        assert _extract_genus("  Hydrangea  macrophylla ") == "Hydrangea"


class TestGuessGenus:
    def test_french_rose(self):
        assert _guess_genus("Rosier grimpant") == "Rosa"

    def test_french_lavender(self):
        assert _guess_genus("Lavande vraie") == "Lavandula"

    def test_french_tomato(self):
        assert _guess_genus("Tomate cerise") == "Solanum"

    def test_french_olive(self):
        assert _guess_genus("Olivier") == "Olea"

    def test_unknown(self):
        assert _guess_genus("Plante mystérieuse") == ""

    def test_empty(self):
        assert _guess_genus("") == ""


class TestCheckWeatherRule:
    def test_frost_triggered(self):
        rule = {"condition": "frost"}
        assert _check_weather_rule(rule, air_temp=-5, recent_rain_mm=10) is True

    def test_frost_not_triggered(self):
        rule = {"condition": "frost"}
        assert _check_weather_rule(rule, air_temp=5, recent_rain_mm=10) is False

    def test_heat_triggered(self):
        rule = {"condition": "heat"}
        assert _check_weather_rule(rule, air_temp=35, recent_rain_mm=10) is True

    def test_heat_not_triggered(self):
        rule = {"condition": "heat"}
        assert _check_weather_rule(rule, air_temp=25, recent_rain_mm=10) is False

    def test_drought_triggered(self):
        rule = {"condition": "drought"}
        assert _check_weather_rule(rule, air_temp=25, recent_rain_mm=0.5) is True

    def test_drought_not_triggered(self):
        rule = {"condition": "drought"}
        assert _check_weather_rule(rule, air_temp=25, recent_rain_mm=15) is False

    def test_no_weather_data(self):
        rule = {"condition": "frost"}
        assert _check_weather_rule(rule, air_temp=None, recent_rain_mm=None) is False


class TestCheckGenusWeather:
    def test_passes_without_filters(self):
        rule = {"months": [3]}
        assert _check_genus_weather(rule, air_temp=15, soil_temp=8) is True

    def test_min_soil_temp_pass(self):
        rule = {"min_soil_temp": 5}
        assert _check_genus_weather(rule, air_temp=15, soil_temp=8) is True

    def test_min_soil_temp_fail(self):
        rule = {"min_soil_temp": 5}
        assert _check_genus_weather(rule, air_temp=15, soil_temp=3) is False

    def test_no_weather_data_passes(self):
        """Without weather data, weather filter is skipped."""
        rule = {"min_soil_temp": 5}
        assert _check_genus_weather(rule, air_temp=None, soil_temp=None) is True


# ── Suggestion engine tests ──────────────────────────────────


def _mock_plant(
    pk=1,
    common_name="Lavande",
    scientific_name="Lavandula angustifolia",
    slug="lavande",
):
    """Create a mock Plant object."""
    plant = MagicMock(spec=Plant)
    plant.pk = pk
    plant.common_name = common_name
    plant.scientific_name = scientific_name
    plant.slug = slug
    return plant


class TestSuggestCareTasks:
    def test_returns_list(self):
        plant = _mock_plant()
        result = suggest_care_tasks([plant], month=7)
        assert isinstance(result, list)
        assert all(isinstance(s, CareSuggestion) for s in result)

    def test_lavender_harvest_in_july(self):
        plant = _mock_plant()
        result = suggest_care_tasks([plant], month=7)
        titles = [s.title for s in result]
        assert "Récolte de la lavande" in titles

    def test_lavender_no_harvest_in_january(self):
        plant = _mock_plant()
        result = suggest_care_tasks([plant], month=1)
        titles = [s.title for s in result]
        assert "Récolte de la lavande" not in titles

    def test_rose_pruning_in_march(self):
        plant = _mock_plant(
            pk=2, common_name="Rosier", scientific_name="Rosa gallica", slug="rosier"
        )
        result = suggest_care_tasks([plant], month=3, soil_temp=8)
        titles = [s.title for s in result]
        assert "Taille des rosiers" in titles

    def test_rose_pruning_skipped_cold_soil(self):
        plant = _mock_plant(
            pk=2, common_name="Rosier", scientific_name="Rosa gallica", slug="rosier"
        )
        result = suggest_care_tasks([plant], month=3, soil_temp=2)
        titles = [s.title for s in result]
        assert "Taille des rosiers" not in titles

    def test_universal_rules_always_present(self):
        plant = _mock_plant()
        result = suggest_care_tasks([plant], month=4)
        titles = [s.title for s in result]
        assert "Paillage de printemps" in titles

    def test_frost_warning(self):
        plant = _mock_plant()
        result = suggest_care_tasks([plant], month=1, air_temp=-5)
        titles = [s.title for s in result]
        assert "Protection contre le gel" in titles

    def test_heat_warning(self):
        plant = _mock_plant()
        result = suggest_care_tasks([plant], month=7, air_temp=35)
        titles = [s.title for s in result]
        assert "Arrosage renforcé (canicule)" in titles

    def test_no_heat_warning_at_normal_temp(self):
        plant = _mock_plant()
        result = suggest_care_tasks([plant], month=7, air_temp=25)
        titles = [s.title for s in result]
        assert "Arrosage renforcé (canicule)" not in titles

    def test_drought_warning(self):
        plant = _mock_plant()
        result = suggest_care_tasks([plant], month=8, air_temp=28, recent_rain_mm=0)
        titles = [s.title for s in result]
        assert "Attention sécheresse" in titles

    def test_excludes_existing_tasks(self):
        plant = _mock_plant()
        result = suggest_care_tasks(
            [plant],
            month=7,
            existing_task_titles={"Récolte de la lavande"},
        )
        titles = [s.title for s in result]
        assert "Récolte de la lavande" not in titles

    def test_excludes_existing_tasks_case_insensitive(self):
        plant = _mock_plant()
        result = suggest_care_tasks(
            [plant],
            month=7,
            existing_task_titles={"récolte de la lavande"},
        )
        titles = [s.title for s in result]
        assert "Récolte de la lavande" not in titles

    def test_sorted_by_priority_desc(self):
        plant = _mock_plant()
        result = suggest_care_tasks([plant], month=7, air_temp=35)
        priorities = [s.priority for s in result]
        assert priorities == sorted(priorities, reverse=True)

    def test_multiple_plants(self):
        lavande = _mock_plant(pk=1, slug="lavande")
        rose = _mock_plant(
            pk=2, common_name="Rosier", scientific_name="Rosa gallica", slug="rosier"
        )
        result = suggest_care_tasks([lavande, rose], month=7)
        plant_names = {s.plant_name for s in result}
        assert "Lavande" in plant_names
        assert "Rosier" in plant_names

    def test_genus_guessed_from_common_name(self):
        plant = _mock_plant(
            pk=3,
            common_name="Tomate cerise",
            scientific_name="",
            slug="tomate-cerise",
        )
        result = suggest_care_tasks([plant], month=7)
        titles = [s.title for s in result]
        assert "Taille des gourmands" in titles

    def test_suggestion_has_plant_slug(self):
        plant = _mock_plant(slug="lavande-vraie")
        result = suggest_care_tasks([plant], month=7)
        assert any(s.plant_slug == "lavande-vraie" for s in result)

    def test_empty_plant_list(self):
        result = suggest_care_tasks([], month=5)
        assert result == []


# ── Integration tests (Django DB) ────────────────────────────


@pytest.mark.django_db
class TestSuggestCareTasksIntegration:
    def test_with_real_plant(self, garden):
        plant = Plant.objects.create(
            garden=garden,
            common_name="Lavande",
            scientific_name="Lavandula angustifolia",
        )
        result = suggest_care_tasks([plant], month=7)
        assert len(result) > 0
        titles = [s.title for s in result]
        assert "Récolte de la lavande" in titles

    def test_existing_tasks_excluded(self, garden):
        plant = Plant.objects.create(
            garden=garden,
            common_name="Lavande",
            scientific_name="Lavandula angustifolia",
        )
        PlantTask.objects.create(plant=plant, title="Récolte de la lavande", priority=2)
        existing = set(plant.tasks.filter(done=False).values_list("title", flat=True))
        result = suggest_care_tasks([plant], month=7, existing_task_titles=existing)
        titles = [s.title for s in result]
        assert "Récolte de la lavande" not in titles

    def test_done_tasks_not_excluded(self, garden):
        plant = Plant.objects.create(
            garden=garden,
            common_name="Lavande",
            scientific_name="Lavandula angustifolia",
        )
        PlantTask.objects.create(
            plant=plant, title="Récolte de la lavande", priority=2, done=True
        )
        # Only exclude pending (not done) tasks
        existing = set(plant.tasks.filter(done=False).values_list("title", flat=True))
        result = suggest_care_tasks([plant], month=7, existing_task_titles=existing)
        titles = [s.title for s in result]
        assert "Récolte de la lavande" in titles
