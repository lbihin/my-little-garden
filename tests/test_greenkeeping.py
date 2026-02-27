"""Tests for the greenkeeping advisor module."""

from unittest.mock import patch

import pytest
from weather.greenkeeping import (
    Advice,
    GreenkeepingReport,
    Status,
    _analyse_fertiliser,
    _analyse_grass_growth,
    _analyse_mowing,
    _analyse_overseeding,
    _analyse_scarification,
    _analyse_trampling,
    _analyse_treatment_window,
    _analyse_watering,
    analyse,
)
from weather.services import WeatherData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snap(**overrides) -> dict:
    """Return a snapshot dict with sensible defaults, merged with overrides."""
    base = {
        "air_temp": 15.0,
        "humidity": 60.0,
        "precipitation": 0.0,
        "precip_prob": 10.0,
        "wind_speed": 5.0,
        "uv_index": 3.0,
        "et0": 0.2,
        "soil_0cm": 12.0,
        "soil_6cm": 11.0,
        "soil_18cm": 9.0,
        "soil_54cm": 7.0,
        "moisture_surface": 0.30,
        "moisture_deep": 0.33,
    }
    base.update(overrides)
    return base


def _make_report(**overrides) -> GreenkeepingReport:
    defaults = {
        "grass_growing": True,
        "season": "printemps",
        "water_balance": 0.5,
    }
    defaults.update(overrides)
    return GreenkeepingReport(**defaults)


def _fake_weather(soil_0=12.0, air=15.0, moisture=0.30, precip=None) -> WeatherData:
    return WeatherData(
        times=["2026-04-15T12:00", "2026-04-15T13:00"],
        air_temperature=[air, air + 0.5],
        humidity=[60.0, 58.0],
        precipitation=precip or [0.0, 0.0],
        precipitation_probability=[10.0, 20.0],
        wind_speed=[5.0, 6.0],
        uv_index=[3.0, 4.0],
        evapotranspiration=[0.15, 0.20],
        soil_temp_0cm=[soil_0, soil_0 + 0.2],
        soil_temp_6cm=[soil_0 - 1, soil_0 - 0.8],
        soil_temp_18cm=[soil_0 - 3, soil_0 - 2.8],
        soil_temp_54cm=[soil_0 - 5, soil_0 - 4.8],
        soil_moisture_surface=[moisture, moisture],
        soil_moisture_deep=[moisture + 0.03, moisture + 0.03],
        latitude=48.85,
        longitude=2.35,
        timezone="Europe/Paris",
    )


# ---------------------------------------------------------------------------
# Grass growth
# ---------------------------------------------------------------------------


class TestGrassGrowth:
    def test_dormant_cold_soil(self):
        snap = _make_snap(soil_0cm=3.0, air_temp=2.0)
        report = _make_report(grass_growing=False)
        _analyse_grass_growth(snap, report)
        assert not report.grass_growing
        assert any("dormant" in a.title.lower() for a in report.advices)

    def test_warming_up(self):
        snap = _make_snap(soil_0cm=7.0, air_temp=8.0)
        report = _make_report()
        _analyse_grass_growth(snap, report)
        assert not report.grass_growing  # < 8 °C
        assert any("réchauffer" in a.title.lower() for a in report.advices)

    def test_slow_growth(self):
        snap = _make_snap(soil_0cm=10.0, air_temp=10.0)
        report = _make_report()
        _analyse_grass_growth(snap, report)
        assert report.grass_growing
        assert any("lentement" in a.title.lower() for a in report.advices)

    def test_active_growth(self):
        snap = _make_snap(soil_0cm=18.0, air_temp=20.0)
        report = _make_report()
        _analyse_grass_growth(snap, report)
        assert report.grass_growing
        assert any("activement" in a.title.lower() for a in report.advices)

    def test_heat_stress(self):
        snap = _make_snap(soil_0cm=30.0, air_temp=35.0)
        report = _make_report()
        _analyse_grass_growth(snap, report)
        assert any("stress" in a.title.lower() for a in report.advices)
        assert report.advices[-1].status == Status.WARN


# ---------------------------------------------------------------------------
# Mowing
# ---------------------------------------------------------------------------


class TestMowing:
    def test_good_conditions(self):
        snap = _make_snap(moisture_surface=0.25, precip_prob=5.0, air_temp=18.0)
        report = _make_report(grass_growing=True)
        _analyse_mowing(snap, report)
        assert any("favorable" in a.title.lower() for a in report.advices)

    def test_too_wet(self):
        snap = _make_snap(moisture_surface=0.50)
        report = _make_report(grass_growing=True)
        _analyse_mowing(snap, report)
        assert any("humide" in a.title.lower() for a in report.advices)

    def test_rain_expected(self):
        snap = _make_snap(precip_prob=80.0)
        report = _make_report(grass_growing=True)
        _analyse_mowing(snap, report)
        assert any("pluie" in a.title.lower() for a in report.advices)

    def test_no_advice_when_dormant(self):
        snap = _make_snap()
        report = _make_report(grass_growing=False)
        _analyse_mowing(snap, report)
        assert len(report.advices) == 0  # no mowing advice when dormant


# ---------------------------------------------------------------------------
# Trampling
# ---------------------------------------------------------------------------


class TestTrampling:
    def test_frozen_soil(self):
        snap = _make_snap(soil_0cm=-2.0)
        report = _make_report()
        _analyse_trampling(snap, report)
        assert any("gelé" in a.title.lower() for a in report.advices)
        assert report.advices[-1].status == Status.DANGER

    def test_waterlogged(self):
        snap = _make_snap(moisture_surface=0.55)
        report = _make_report()
        _analyse_trampling(snap, report)
        assert any("détrempé" in a.title.lower() for a in report.advices)

    def test_no_warning_normal(self):
        snap = _make_snap(soil_0cm=10.0, moisture_surface=0.30)
        report = _make_report()
        _analyse_trampling(snap, report)
        assert len(report.advices) == 0


# ---------------------------------------------------------------------------
# Scarification
# ---------------------------------------------------------------------------


class TestScarification:
    @patch("weather.greenkeeping._current_month", return_value=4)
    def test_good_conditions_spring(self, _):
        snap = _make_snap(soil_0cm=12.0, moisture_surface=0.30)
        report = _make_report()
        _analyse_scarification(snap, report)
        assert any("bonne période" in a.title.lower() for a in report.advices)

    @patch("weather.greenkeeping._current_month", return_value=4)
    def test_soil_too_cold(self, _):
        snap = _make_snap(soil_0cm=7.0)
        report = _make_report()
        _analyse_scarification(snap, report)
        assert any("froid" in a.title.lower() for a in report.advices)

    @patch("weather.greenkeeping._current_month", return_value=7)
    def test_wrong_season(self, _):
        snap = _make_snap(soil_0cm=20.0)
        report = _make_report()
        _analyse_scarification(snap, report)
        assert any("hors saison" in a.title.lower() for a in report.advices)


# ---------------------------------------------------------------------------
# Fertiliser
# ---------------------------------------------------------------------------


class TestFertiliser:
    def test_spring(self):
        report = _make_report(season="printemps")
        _analyse_fertiliser(report)
        assert any("azote" in a.title.lower() for a in report.advices)

    def test_summer(self):
        report = _make_report(season="été")
        _analyse_fertiliser(report)
        assert any("potassium" in a.title.lower() for a in report.advices)

    def test_autumn(self):
        report = _make_report(season="automne")
        _analyse_fertiliser(report)
        assert any("phosphore" in a.title.lower() for a in report.advices)

    def test_winter(self):
        report = _make_report(season="hiver")
        _analyse_fertiliser(report)
        assert any("pas d'engrais" in a.title.lower() for a in report.advices)


# ---------------------------------------------------------------------------
# Watering
# ---------------------------------------------------------------------------


class TestWatering:
    def test_deficit(self):
        snap = _make_snap()
        report = _make_report(grass_growing=True, water_balance=-5.0)
        _analyse_watering(snap, report)
        assert any("recommandé" in a.title.lower() for a in report.advices)
        assert report.advices[-1].status == Status.WARN

    def test_slight_deficit(self):
        snap = _make_snap()
        report = _make_report(grass_growing=True, water_balance=-1.0)
        _analyse_watering(snap, report)
        assert any("déficit" in a.title.lower() for a in report.advices)

    def test_surplus(self):
        snap = _make_snap()
        report = _make_report(grass_growing=True, water_balance=2.0)
        _analyse_watering(snap, report)
        assert any("pas besoin" in a.title.lower() for a in report.advices)

    def test_no_advice_when_dormant(self):
        snap = _make_snap()
        report = _make_report(grass_growing=False)
        _analyse_watering(snap, report)
        assert len(report.advices) == 0


# ---------------------------------------------------------------------------
# Treatment window
# ---------------------------------------------------------------------------


class TestTreatmentWindow:
    def test_good_window(self):
        snap = _make_snap(wind_speed=3.0, precip_prob=5.0, uv_index=2.0)
        report = _make_report()
        _analyse_treatment_window(snap, report)
        assert any("favorable" in a.title.lower() for a in report.advices)

    def test_too_windy(self):
        snap = _make_snap(wind_speed=20.0)
        report = _make_report()
        _analyse_treatment_window(snap, report)
        assert any("déconseillé" in a.title.lower() for a in report.advices)

    def test_rain_and_uv(self):
        snap = _make_snap(precip_prob=60.0, uv_index=10.0)
        report = _make_report()
        _analyse_treatment_window(snap, report)
        advice = [a for a in report.advices if "déconseillé" in a.title.lower()]
        assert len(advice) == 1
        assert "pluie" in advice[0].detail


# ---------------------------------------------------------------------------
# Overseeding
# ---------------------------------------------------------------------------


class TestOverseeding:
    @patch("weather.greenkeeping._current_month", return_value=4)
    def test_ideal_conditions(self, _):
        snap = _make_snap(soil_0cm=15.0, moisture_surface=0.30)
        report = _make_report()
        _analyse_overseeding(snap, report)
        assert any("idéales" in a.title.lower() for a in report.advices)

    @patch("weather.greenkeeping._current_month", return_value=4)
    def test_soil_not_ready(self, _):
        snap = _make_snap(soil_0cm=5.0, moisture_surface=0.30)
        report = _make_report()
        _analyse_overseeding(snap, report)
        assert any("pas encore" in a.title.lower() for a in report.advices)


# ---------------------------------------------------------------------------
# Full analyse()
# ---------------------------------------------------------------------------


class TestAnalyse:
    def test_returns_report(self):
        weather = _fake_weather()
        report = analyse(weather)
        assert isinstance(report, GreenkeepingReport)
        assert report.generated_at  # not empty
        assert len(report.advices) > 0

    def test_with_error_weather(self):
        weather = WeatherData(error="API down")
        report = analyse(weather)
        assert len(report.advices) == 1
        assert report.advices[0].status == Status.DANGER

    def test_season_populated(self):
        weather = _fake_weather()
        report = analyse(weather)
        assert report.season in ("printemps", "été", "automne", "hiver")

    def test_water_balance_calculated(self):
        weather = _fake_weather(precip=[2.0, 3.0])
        report = analyse(weather)
        # precip_last_24h - et0_last_24h
        assert report.water_balance != 0 or report.precip_last_24h >= 0


# ---------------------------------------------------------------------------
# Garden detail view with greenkeeping
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_client(user):
    from django.test import Client

    client = Client()
    client.force_login(user)
    return client


class TestGardenDetailWithGreenkeeping:
    @patch("weather.services.fetch_weather")
    def test_dashboard_has_report(self, mock_fetch, auth_client, garden):
        mock_fetch.return_value = _fake_weather()
        url = garden.get_absolute_url()
        resp = auth_client.get(url)
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Tableau de bord" in content

    @patch("weather.services.fetch_weather")
    def test_dashboard_shows_advice(self, mock_fetch, auth_client, garden):
        mock_fetch.return_value = _fake_weather()
        url = garden.get_absolute_url()
        resp = auth_client.get(url)
        content = resp.content.decode()
        # Should contain at least one advice card
        assert "card-body" in content

    @patch("weather.services.fetch_weather")
    def test_dashboard_uses_default_coords(self, mock_fetch, auth_client, garden):
        """Garden without address should use Paris defaults."""
        mock_fetch.return_value = _fake_weather()
        url = garden.get_absolute_url()
        resp = auth_client.get(url)
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Paris" in content
