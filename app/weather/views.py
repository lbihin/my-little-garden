import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from gardens.models import Garden
from weather.services import fetch_weather

# Default coordinates (Paris) if garden has no address
DEFAULT_LAT = 48.8566
DEFAULT_LON = 2.3522


class WeatherDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard showing weather and soil data for a garden."""

    template_name = "weather/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        garden = get_object_or_404(Garden, slug=self.kwargs["garden_slug"])
        context["garden"] = garden

        # Resolve coordinates
        if garden.address and garden.address.latitude and garden.address.longitude:
            lat = float(garden.address.latitude)
            lon = float(garden.address.longitude)
            context["location_source"] = garden.address.city or garden.address.name
        else:
            lat, lon = DEFAULT_LAT, DEFAULT_LON
            context["location_source"] = "Paris (par défaut)"

        days = int(self.request.GET.get("days", 3))
        weather = fetch_weather(lat, lon, days=days)
        context["weather"] = weather
        context["days"] = days

        if weather.ok:
            context["current"] = weather.current_snapshot()
            # Serialize for Chart.js
            context["chart_labels"] = json.dumps(weather.times)
            context["chart_air_temp"] = json.dumps(weather.air_temperature)
            context["chart_humidity"] = json.dumps(weather.humidity)
            context["chart_precipitation"] = json.dumps(weather.precipitation)
            context["chart_wind_speed"] = json.dumps(weather.wind_speed)
            context["chart_uv_index"] = json.dumps(weather.uv_index)
            context["chart_soil_0"] = json.dumps(weather.soil_temp_0cm)
            context["chart_soil_6"] = json.dumps(weather.soil_temp_6cm)
            context["chart_soil_18"] = json.dumps(weather.soil_temp_18cm)
            context["chart_soil_54"] = json.dumps(weather.soil_temp_54cm)
            context["chart_moisture_surface"] = json.dumps(
                weather.soil_moisture_surface
            )
            context["chart_moisture_deep"] = json.dumps(weather.soil_moisture_deep)

        return context
