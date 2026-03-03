from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from weather.services import WeatherData, fetch_weather

# -- Service tests -----------------------------------------------------------


def _fake_weather_data() -> WeatherData:
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    t0 = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00")
    t1 = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:00")

    return WeatherData(
        times=[t0, t1],
        air_temperature=[8.5, 9.0],
        humidity=[72.0, 68.0],
        precipitation=[0.0, 0.2],
        precipitation_probability=[10.0, 30.0],
        wind_speed=[5.0, 8.0],
        uv_index=[2.0, 3.0],
        evapotranspiration=[0.15, 0.20],
        soil_temp_0cm=[6.0, 6.2],
        soil_temp_6cm=[5.5, 5.6],
        soil_temp_18cm=[4.8, 4.8],
        soil_temp_54cm=[4.0, 4.0],
        soil_moisture_surface=[0.32, 0.31],
        soil_moisture_deep=[0.35, 0.35],
        latitude=48.85,
        longitude=2.35,
        timezone="Europe/Paris",
    )


class TestWeatherData:
    def test_ok_when_data_present(self):
        wd = _fake_weather_data()
        assert wd.ok is True

    def test_not_ok_when_error(self):
        wd = WeatherData(error="fail")
        assert wd.ok is False

    def test_not_ok_when_empty(self):
        wd = WeatherData()
        assert wd.ok is False

    def test_current_snapshot(self):
        wd = _fake_weather_data()
        snap = wd.current_snapshot()
        assert snap["air_temp"] in [8.5, 9.0]
        assert "soil_0cm" in snap
        assert "precipitation" in snap
        assert "wind_speed" in snap

    def test_current_snapshot_empty(self):
        wd = WeatherData()
        assert wd.current_snapshot() == {}

    def test_recent_precipitation(self):
        wd = _fake_weather_data()
        total = wd.recent_precipitation_mm(24)
        # Index 0 is current (future timestamps), so only precip[0]=0.0
        assert total == pytest.approx(0.0, abs=0.01)

    def test_recent_et0(self):
        wd = _fake_weather_data()
        total = wd.recent_et0_mm(24)
        # Index 0 is current (future timestamps), so only et0[0]=0.15
        assert total == pytest.approx(0.15, abs=0.01)

    def test_upcoming_precipitation(self):
        wd = _fake_weather_data()
        # Index 0 is "current" since both are in the future relative to test
        total = wd.upcoming_precipitation_mm(24)
        assert total >= 0


class TestFetchWeather:
    def setup_method(self):
        cache.clear()

    @patch("weather.services.httpx.get")
    def test_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = {
            "latitude": 48.85,
            "longitude": 2.35,
            "timezone": "Europe/Paris",
            "hourly": {
                "time": ["2026-02-27T12:00"],
                "temperature_2m": [8.5],
                "relative_humidity_2m": [72.0],
                "precipitation": [0.0],
                "precipitation_probability": [10.0],
                "wind_speed_10m": [5.0],
                "uv_index": [2.0],
                "et0_fao_evapotranspiration": [0.15],
                "soil_temperature_0cm": [6.0],
                "soil_temperature_6cm": [5.5],
                "soil_temperature_18cm": [4.8],
                "soil_temperature_54cm": [4.0],
                "soil_moisture_0_to_1cm": [0.32],
                "soil_moisture_1_to_3cm": [0.35],
            },
        }
        result = fetch_weather(48.85, 2.35)
        assert result.ok
        assert result.air_temperature == [8.5]
        assert result.soil_temp_0cm == [6.0]
        assert result.precipitation == [0.0]
        assert result.wind_speed == [5.0]

    @patch("weather.services.httpx.get")
    def test_http_error(self, mock_get):
        import httpx

        resp = httpx.Response(500)
        mock_get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "err", request=httpx.Request("GET", ""), response=resp
        )
        result = fetch_weather(48.85, 2.35)
        assert not result.ok
        assert "500" in result.error

    @patch("weather.services.httpx.get")
    def test_network_error(self, mock_get):
        import httpx

        mock_get.side_effect = httpx.ConnectError("timeout")
        result = fetch_weather(48.85, 2.35)
        assert not result.ok
        assert "Impossible" in result.error


# -- View tests ---------------------------------------------------------------


@pytest.fixture
def auth_client(user):
    client = Client()
    client.force_login(user)
    return client


class TestWeatherDashboardView:
    @patch("weather.views.fetch_weather")
    def test_dashboard_loads(self, mock_fetch, auth_client, garden):
        mock_fetch.return_value = _fake_weather_data()
        url = reverse(
            "gardens:weather:dashboard",
            kwargs={"garden_slug": garden.slug},
        )
        resp = auth_client.get(url)
        assert resp.status_code == 200
        assert "Conditions du jardin" in resp.content.decode()

    @patch("weather.views.fetch_weather")
    def test_dashboard_with_days_param(self, mock_fetch, auth_client, garden):
        mock_fetch.return_value = _fake_weather_data()
        url = reverse(
            "gardens:weather:dashboard",
            kwargs={"garden_slug": garden.slug},
        )
        resp = auth_client.get(url + "?days=7")
        assert resp.status_code == 200
        mock_fetch.assert_called_once()
        _, kwargs = mock_fetch.call_args
        assert kwargs["forecast_days"] == 7

    @patch("weather.views.fetch_weather")
    def test_dashboard_error(self, mock_fetch, auth_client, garden):
        mock_fetch.return_value = WeatherData(error="API down")
        url = reverse(
            "gardens:weather:dashboard",
            kwargs={"garden_slug": garden.slug},
        )
        resp = auth_client.get(url)
        assert resp.status_code == 200
        assert "API down" in resp.content.decode()

    def test_dashboard_requires_login(self, client, garden):
        url = reverse(
            "gardens:weather:dashboard",
            kwargs={"garden_slug": garden.slug},
        )
        resp = client.get(url)
        assert resp.status_code == 302
