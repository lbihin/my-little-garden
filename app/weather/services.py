"""
Service layer for fetching weather data from the Open-Meteo API.

Open-Meteo provides free weather data including soil temperature at
multiple depths — ideal for garden/greenkeeping applications.

API docs: https://open-meteo.com/en/docs
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# Hourly variables we request from Open-Meteo
HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "soil_temperature_0cm",
    "soil_temperature_6cm",
    "soil_temperature_18cm",
    "soil_temperature_54cm",
    "soil_moisture_0_to_1cm",
    "soil_moisture_1_to_3cm",
]

TIMEOUT = 10  # seconds


@dataclass
class WeatherData:
    """Structured weather data returned by the service."""

    times: list[str] = field(default_factory=list)
    air_temperature: list[float | None] = field(default_factory=list)
    humidity: list[float | None] = field(default_factory=list)
    soil_temp_0cm: list[float | None] = field(default_factory=list)
    soil_temp_6cm: list[float | None] = field(default_factory=list)
    soil_temp_18cm: list[float | None] = field(default_factory=list)
    soil_temp_54cm: list[float | None] = field(default_factory=list)
    soil_moisture_surface: list[float | None] = field(default_factory=list)
    soil_moisture_deep: list[float | None] = field(default_factory=list)
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and len(self.times) > 0

    def current_snapshot(self) -> dict:
        """Return the most recent data point as a simple dict."""
        if not self.times:
            return {}
        # Find the closest past timestamp
        now = datetime.now().strftime("%Y-%m-%dT%H:00")
        idx = 0
        for i, t in enumerate(self.times):
            if t <= now:
                idx = i
        return {
            "time": self.times[idx],
            "air_temp": self.air_temperature[idx],
            "humidity": self.humidity[idx],
            "soil_0cm": self.soil_temp_0cm[idx],
            "soil_6cm": self.soil_temp_6cm[idx],
            "soil_18cm": self.soil_temp_18cm[idx],
            "soil_54cm": self.soil_temp_54cm[idx],
            "moisture_surface": self.soil_moisture_surface[idx],
            "moisture_deep": self.soil_moisture_deep[idx],
        }


def fetch_weather(latitude: float, longitude: float, days: int = 3) -> WeatherData:
    """
    Fetch weather forecast data from Open-Meteo.

    Args:
        latitude: Garden latitude.
        longitude: Garden longitude.
        days: Number of forecast days (1-16, default 3).

    Returns:
        WeatherData with all the time series, or an error message.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": "auto",
        "forecast_days": min(days, 16),
    }

    try:
        response = httpx.get(OPEN_METEO_BASE_URL, params=params, timeout=TIMEOUT)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("Open-Meteo HTTP error: %s", exc)
        return WeatherData(error=f"Erreur API : {exc.response.status_code}")
    except httpx.RequestError as exc:
        logger.error("Open-Meteo request error: %s", exc)
        return WeatherData(error="Impossible de contacter Open-Meteo.")

    data = response.json()
    hourly = data.get("hourly", {})

    return WeatherData(
        times=hourly.get("time", []),
        air_temperature=hourly.get("temperature_2m", []),
        humidity=hourly.get("relative_humidity_2m", []),
        soil_temp_0cm=hourly.get("soil_temperature_0cm", []),
        soil_temp_6cm=hourly.get("soil_temperature_6cm", []),
        soil_temp_18cm=hourly.get("soil_temperature_18cm", []),
        soil_temp_54cm=hourly.get("soil_temperature_54cm", []),
        soil_moisture_surface=hourly.get("soil_moisture_0_to_1cm", []),
        soil_moisture_deep=hourly.get("soil_moisture_1_to_3cm", []),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        timezone=data.get("timezone", ""),
    )
