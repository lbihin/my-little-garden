import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import TemplateView
from gardens.models import Garden
from weather.greenkeeping import WATERING_PROFILES, analyse
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
        force_refresh = self.request.GET.get("refresh") == "1"
        weather = fetch_weather(
            lat, lon, forecast_days=days, force_refresh=force_refresh
        )
        context["weather"] = weather
        context["days"] = days

        if weather.ok:
            context["current"] = weather.current_snapshot()

            # Greenkeeping report (watering, advices, water balance…)
            report = analyse(
                weather,
                profile=garden.watering_profile,
                surface=garden.surface or 0,
            )
            context["report"] = report

            # Profiles dict for inline selector
            context["profiles"] = WATERING_PROFILES

            # Serialize for Chart.js (only charts we display)
            context["chart_labels"] = json.dumps(weather.times)
            context["chart_precipitation"] = json.dumps(weather.precipitation)
            context["chart_wind_speed"] = json.dumps(weather.wind_speed)
            context["chart_et0"] = json.dumps(weather.evapotranspiration)
            context["chart_soil_0"] = json.dumps(weather.soil_temp_0cm)
            context["chart_soil_6"] = json.dumps(weather.soil_temp_6cm)
            context["chart_soil_18"] = json.dumps(weather.soil_temp_18cm)
            context["chart_soil_54"] = json.dumps(weather.soil_temp_54cm)

        return context


class ChangeWateringProfileView(LoginRequiredMixin, View):
    """HTMX endpoint to change watering profile inline."""

    def post(self, request, garden_slug):
        garden = get_object_or_404(Garden, slug=garden_slug)
        profile = request.POST.get("watering_profile", "standard")
        if profile in WATERING_PROFILES:
            garden.watering_profile = profile
            garden.save(update_fields=["watering_profile"])

        # Fetch weather so we can re-render the watering partial
        if garden.address and garden.address.latitude and garden.address.longitude:
            lat = float(garden.address.latitude)
            lon = float(garden.address.longitude)
        else:
            lat, lon = DEFAULT_LAT, DEFAULT_LON

        weather = fetch_weather(lat, lon)
        report = analyse(
            weather, profile=garden.watering_profile, surface=garden.surface or 0
        )

        context = {
            "garden": garden,
            "report": report,
            "profiles": WATERING_PROFILES,
        }
        return render(request, "weather/partials/watering.html", context)
