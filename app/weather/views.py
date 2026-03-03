import json
from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView
from gardens.models import Garden
from weather.forms import LawnAssessmentForm, LawnProfileForm
from weather.greenkeeping import WATERING_PROFILES, analyse
from weather.models import LawnProfile
from weather.programs import get_monthly_plan
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


# ---------------------------------------------------------------------------
# Follow the Pro — lawn programme views
# ---------------------------------------------------------------------------


class LawnProgramView(LoginRequiredMixin, TemplateView):
    """
    Main programme page.

    If the garden has a LawnProfile → show the monthly plan.
    Otherwise → redirect to the questionnaire.
    """

    template_name = "weather/program.html"

    def get(self, request, *args, **kwargs):
        garden = get_object_or_404(Garden, slug=self.kwargs["garden_slug"])
        try:
            lawn_profile = garden.lawn_profile
        except LawnProfile.DoesNotExist:
            return redirect(
                "gardens:weather:questionnaire",
                garden_slug=garden.slug,
            )

        # Requested month (default = today)
        month = int(request.GET.get("month", date.today().month))
        month = max(1, min(12, month))

        # Latest issues from most recent assessment
        latest = lawn_profile.assessments.first()
        latest_issues = latest.issues if latest else []

        plan = get_monthly_plan(lawn_profile, month, latest_issues=latest_issues)

        context = {
            "garden": garden,
            "lawn_profile": lawn_profile,
            "plan": plan,
            "current_month": date.today().month,
            "selected_month": month,
            "months": list(range(1, 13)),
            "latest_assessment": latest,
        }
        return self.render_to_response(context)


class LawnQuestionnaireView(LoginRequiredMixin, View):
    """Questionnaire to create or update the lawn profile."""

    template_name = "weather/questionnaire.html"

    def get(self, request, garden_slug):
        garden = get_object_or_404(Garden, slug=garden_slug)
        try:
            form = LawnProfileForm(instance=garden.lawn_profile)
            is_update = True
        except LawnProfile.DoesNotExist:
            form = LawnProfileForm()
            is_update = False

        return render(
            request,
            self.template_name,
            {"garden": garden, "form": form, "is_update": is_update},
        )

    def post(self, request, garden_slug):
        garden = get_object_or_404(Garden, slug=garden_slug)
        try:
            instance = garden.lawn_profile
            is_update = True
        except LawnProfile.DoesNotExist:
            instance = None
            is_update = False

        form = LawnProfileForm(request.POST, instance=instance)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.garden = garden
            profile.save()
            return redirect("gardens:weather:program", garden_slug=garden.slug)

        return render(
            request,
            self.template_name,
            {"garden": garden, "form": form, "is_update": is_update},
        )


class LawnAssessmentView(LoginRequiredMixin, View):
    """Create a new assessment (periodic review)."""

    template_name = "weather/assessment.html"

    def get(self, request, garden_slug):
        garden = get_object_or_404(Garden, slug=garden_slug)
        try:
            lawn_profile = garden.lawn_profile
        except LawnProfile.DoesNotExist:
            return redirect(
                "gardens:weather:questionnaire",
                garden_slug=garden.slug,
            )

        form = LawnAssessmentForm()
        return render(
            request,
            self.template_name,
            {
                "garden": garden,
                "lawn_profile": lawn_profile,
                "form": form,
            },
        )

    def post(self, request, garden_slug):
        garden = get_object_or_404(Garden, slug=garden_slug)
        try:
            lawn_profile = garden.lawn_profile
        except LawnProfile.DoesNotExist:
            return redirect(
                "gardens:weather:questionnaire",
                garden_slug=garden.slug,
            )

        form = LawnAssessmentForm(request.POST)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.lawn_profile = lawn_profile
            assessment.save()
            return redirect("gardens:weather:program", garden_slug=garden.slug)

        return render(
            request,
            self.template_name,
            {
                "garden": garden,
                "lawn_profile": lawn_profile,
                "form": form,
            },
        )
