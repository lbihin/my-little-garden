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
    # Atmosphere
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "precipitation_probability",
    "wind_speed_10m",
    "uv_index",
    "et0_fao_evapotranspiration",
    # Soil temperature at 4 depths
    "soil_temperature_0cm",
    "soil_temperature_6cm",
    "soil_temperature_18cm",
    "soil_temperature_54cm",
    # Soil moisture
    "soil_moisture_0_to_1cm",
    "soil_moisture_1_to_3cm",
]

TIMEOUT = 10  # seconds


@dataclass
class WeatherData:
    """Structured weather data returned by the service."""

    times: list[str] = field(default_factory=list)
    # Atmosphere
    air_temperature: list[float | None] = field(default_factory=list)
    humidity: list[float | None] = field(default_factory=list)
    precipitation: list[float | None] = field(default_factory=list)
    precipitation_probability: list[float | None] = field(default_factory=list)
    wind_speed: list[float | None] = field(default_factory=list)
    uv_index: list[float | None] = field(default_factory=list)
    evapotranspiration: list[float | None] = field(default_factory=list)
    # Soil
    soil_temp_0cm: list[float | None] = field(default_factory=list)
    soil_temp_6cm: list[float | None] = field(default_factory=list)
    soil_temp_18cm: list[float | None] = field(default_factory=list)
    soil_temp_54cm: list[float | None] = field(default_factory=list)
    soil_moisture_surface: list[float | None] = field(default_factory=list)
    soil_moisture_deep: list[float | None] = field(default_factory=list)
    # Meta
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and len(self.times) > 0

    def _current_index(self) -> int:
        """Index of the most recent past hourly slot."""
        now = datetime.now().strftime("%Y-%m-%dT%H:00")
        idx = 0
        for i, t in enumerate(self.times):
            if t <= now:
                idx = i
        return idx

    def current_snapshot(self) -> dict:
        """Return the most recent data point as a simple dict."""
        if not self.times:
            return {}
        idx = self._current_index()
        return {
            "time": self.times[idx],
            "air_temp": self.air_temperature[idx],
            "humidity": self.humidity[idx],
            "precipitation": self.precipitation[idx] if self.precipitation else 0,
            "precip_prob": (
                self.precipitation_probability[idx]
                if self.precipitation_probability
                else 0
            ),
            "wind_speed": self.wind_speed[idx] if self.wind_speed else 0,
            "uv_index": self.uv_index[idx] if self.uv_index else 0,
            "et0": self.evapotranspiration[idx] if self.evapotranspiration else 0,
            "soil_0cm": self.soil_temp_0cm[idx],
            "soil_6cm": self.soil_temp_6cm[idx],
            "soil_18cm": self.soil_temp_18cm[idx],
            "soil_54cm": self.soil_temp_54cm[idx],
            "moisture_surface": self.soil_moisture_surface[idx],
            "moisture_deep": self.soil_moisture_deep[idx],
        }

    def recent_precipitation_mm(self, hours: int = 24) -> float:
        """Sum of precipitation over the last *hours* from the current index."""
        if not self.precipitation:
            return 0.0
        idx = self._current_index()
        start = max(0, idx - hours + 1)
        return sum(v or 0 for v in self.precipitation[start : idx + 1])

    def upcoming_precipitation_mm(self, hours: int = 24) -> float:
        """Sum of precipitation over the next *hours* from the current index."""
        if not self.precipitation:
            return 0.0
        idx = self._current_index()
        end = min(len(self.precipitation), idx + hours + 1)
        return sum(v or 0 for v in self.precipitation[idx + 1 : end])

    def recent_et0_mm(self, hours: int = 24) -> float:
        """Sum of reference evapotranspiration over the last *hours*."""
        if not self.evapotranspiration:
            return 0.0
        idx = self._current_index()
        start = max(0, idx - hours + 1)
        return sum(v or 0 for v in self.evapotranspiration[start : idx + 1])

    def upcoming_et0_mm(self, hours: int = 24) -> float:
        """Sum of reference evapotranspiration over the next *hours*."""
        if not self.evapotranspiration:
            return 0.0
        idx = self._current_index()
        end = min(len(self.evapotranspiration), idx + hours + 1)
        return sum(v or 0 for v in self.evapotranspiration[idx + 1 : end])


def fetch_weather(
    latitude: float,
    longitude: float,
    forecast_days: int = 7,
    past_days: int = 7,
) -> WeatherData:
    """
    Fetch weather data from Open-Meteo (past measured + forecast).

    Args:
        latitude: Garden latitude.
        longitude: Garden longitude.
        forecast_days: Number of forecast days (1-16, default 7).
        past_days: Number of past days with measured data (0-92, default 7).

    Returns:
        WeatherData with all the time series, or an error message.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": "auto",
        "forecast_days": min(forecast_days, 16),
        "past_days": min(past_days, 92),
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
        precipitation=hourly.get("precipitation", []),
        precipitation_probability=hourly.get("precipitation_probability", []),
        wind_speed=hourly.get("wind_speed_10m", []),
        uv_index=hourly.get("uv_index", []),
        evapotranspiration=hourly.get("et0_fao_evapotranspiration", []),
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
