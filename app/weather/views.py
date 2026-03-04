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

    @staticmethod
    def _slice_chart_window(weather, days: int):
        """Return chart arrays limited to the selected horizon (24h/3j/7j)."""
        if not weather.ok:
            return None

        start = weather._current_index()
        horizon = max(1, days) * 24
        end = min(len(weather.times), start + horizon)

        # Fallback if slicing yields nothing (edge cases around timestamps)
        if start >= end:
            start = 0
            end = len(weather.times)

        return {
            "labels": weather.times[start:end],
            "precip": weather.precipitation[start:end],
            "wind": weather.wind_speed[start:end],
            "et0": weather.evapotranspiration[start:end],
            "soil_0": weather.soil_temp_0cm[start:end],
            "soil_6": weather.soil_temp_6cm[start:end],
            "soil_18": weather.soil_temp_18cm[start:end],
            "soil_54": weather.soil_temp_54cm[start:end],
        }

    @staticmethod
    def _build_focus_card(report):
        """Return a concise next-action summary for the dashboard."""
        if not report:
            return {
                "level": "info",
                "title": "Pas de recommandation disponible",
                "detail": "Les données météo sont incomplètes pour le moment.",
            }

        watering = report.watering
        if watering:
            profile_meta = WATERING_PROFILES.get(watering.profile, WATERING_PROFILES["standard"])
            ignore = profile_meta["ignore_threshold"]
            warn = profile_meta["warn_threshold"]

            if watering.profile == "pro":
                if watering.weekly_deficit <= 0:
                    return {
                        "level": "ok",
                        "title": "Objectif qualité tenu",
                        "detail": "Aucun déficit détecté pour le niveau Greenkeeper pro.",
                    }
                if watering.weekly_deficit <= warn:
                    return {
                        "level": "info",
                        "title": "Rattrapage fin conseillé",
                        "detail": f"Déficit détecté: {watering.weekly_deficit:.0f} mm cette semaine (mode pro).",
                    }
                return {
                    "level": "warn",
                    "title": "Arrosage prioritaire",
                    "detail": f"Déficit important: {watering.weekly_deficit:.0f} mm cette semaine (mode pro).",
                }

            if watering.profile == "laissez_faire":
                return {
                    "level": "info",
                    "title": "Mode laisser-faire actif",
                    "detail": "La stratégie accepte la variabilité hydrique et limite l'arrosage.",
                }

            if watering.weekly_deficit <= ignore:
                return {
                    "level": "ok",
                    "title": "Aucune action urgente",
                    "detail": "Le déficit est dans la zone de tolérance de votre stratégie.",
                }
            if watering.weekly_deficit <= warn:
                return {
                    "level": "info",
                    "title": "Arrosage léger conseillé",
                    "detail": f"Déficit estimé: {watering.weekly_deficit:.0f} mm cette semaine.",
                }
            return {
                "level": "warn",
                "title": "Arrosage prioritaire",
                "detail": f"Déficit important: {watering.weekly_deficit:.0f} mm cette semaine.",
            }

        return {
            "level": "info",
            "title": "Surveillance recommandée",
            "detail": "Consultez les activités pour les actions détaillées.",
        }

    @staticmethod
    def _build_weekly_goal(report):
        """Return one actionable weekly objective sentence for the user."""
        if not report or not report.watering:
            return "Surveillez l'humidité du sol et consultez les activités détaillées."

        watering = report.watering
        profile_meta = WATERING_PROFILES.get(watering.profile, WATERING_PROFILES["standard"])
        ignore = profile_meta["ignore_threshold"]
        warn = profile_meta["warn_threshold"]

        if watering.profile == "pro":
            if watering.weekly_deficit <= 0:
                return "Ne pas arroser: aucun déficit détecté en mode pro."
            if watering.surface > 0 and watering.total_litres > 0:
                sessions = 1 if watering.weekly_deficit <= warn else 2
                litres_per_session = watering.total_litres / sessions
                return (
                    f"Arroser {watering.total_litres:.0f} L au total "
                    f"en {sessions} passage(s) (~{litres_per_session:.0f} L/passage) pour tenir l'objectif pro."
                )
            sessions = 1 if watering.weekly_deficit <= warn else 2
            return (
                f"Apporter {watering.weekly_deficit:.0f} mm d'arrosage "
                f"en {sessions} passage(s) pour tenir l'objectif pro."
            )

        if watering.profile == "laissez_faire":
            return "Ne pas arroser: la stratégie laissez-faire privilégie les pluies naturelles."

        if watering.weekly_deficit <= ignore:
            return "Ne pas arroser, les besoins sont couverts."

        sessions = 1 if watering.weekly_deficit <= warn else 2
        if watering.surface > 0 and watering.total_litres > 0:
            litres_per_session = watering.total_litres / sessions
            return (
                f"{watering.total_litres:.0f} L au total "
                f"en {sessions} passage(s) (~{litres_per_session:.0f} L/passage)."
            )

        return (
            f"{watering.weekly_deficit:.0f} mm d'arrosage "
            f"en {sessions} passage(s)."
        )

    @staticmethod
    def _watering_actionability(report):
        """Return raw/actionable deficit values based on profile thresholds."""
        if not report or not report.watering:
            return {
                "raw_weekly_deficit": 0.0,
                "actionable_weekly_deficit": 0.0,
                "deficit_ignore_threshold": 0.0,
                "actionable_total_litres": 0.0,
                "is_strict_profile": False,
                "profile_strategy_note": "",
            }

        watering = report.watering
        profile_meta = WATERING_PROFILES.get(
            watering.profile, WATERING_PROFILES["standard"]
        )
        raw_ignore_threshold = float(profile_meta["ignore_threshold"])
        # In pro mode, every deficit is actionable.
        ignore_threshold = 0.0 if watering.profile == "pro" else raw_ignore_threshold
        raw_deficit = float(watering.weekly_deficit)
        actionable_deficit = max(0.0, raw_deficit - ignore_threshold)
        actionable_total_litres = (
            actionable_deficit * watering.surface if watering.surface > 0 else 0.0
        )

        strategy_note = ""
        if watering.profile == "pro":
            strategy_note = "Mode pro: aucun seuil de tolérance, tout déficit est traité."
        elif watering.profile == "laissez_faire":
            strategy_note = "Mode laisser-faire: tolérance maximale au déficit."
        elif watering.profile == "resilient":
            strategy_note = "Mode résilient: légère tolérance avant action."
        elif watering.profile == "eco":
            strategy_note = "Mode éco: tolérance modérée pour économiser l'eau."
        else:
            strategy_note = "Mode standard: équilibre confort gazon / consommation d'eau."

        return {
            "raw_weekly_deficit": round(raw_deficit, 1),
            "actionable_weekly_deficit": round(actionable_deficit, 1),
            "deficit_ignore_threshold": round(ignore_threshold, 1),
            "actionable_total_litres": round(actionable_total_litres, 0),
            "is_strict_profile": watering.profile == "pro",
            "profile_strategy_note": strategy_note,
        }

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
        days = 1 if days == 1 else 3 if days == 3 else 7
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
            context["focus"] = self._build_focus_card(report)
            context["weekly_goal"] = self._build_weekly_goal(report)
            context.update(self._watering_actionability(report))

            # Profiles dict for inline selector
            context["profiles"] = WATERING_PROFILES

            window = self._slice_chart_window(weather, days)

            # Serialize for Chart.js (selected range only)
            context["chart_labels"] = json.dumps(window["labels"])
            context["chart_precipitation"] = json.dumps(window["precip"])
            context["chart_wind_speed"] = json.dumps(window["wind"])
            context["chart_et0"] = json.dumps(window["et0"])
            context["chart_soil_0"] = json.dumps(window["soil_0"])
            context["chart_soil_6"] = json.dumps(window["soil_6"])
            context["chart_soil_18"] = json.dumps(window["soil_18"])
            context["chart_soil_54"] = json.dumps(window["soil_54"])

            precip_total = sum(v or 0 for v in window["precip"])
            et0_total = sum(v or 0 for v in window["et0"])
            soil6 = [v for v in window["soil_6"] if v is not None]
            soil_delta = 0.0
            if len(soil6) >= 2:
                soil_delta = soil6[-1] - soil6[0]

            context["trend_precip_total"] = round(precip_total, 1)
            context["trend_et0_total"] = round(et0_total, 1)
            context["trend_soil6_delta"] = round(soil_delta, 1)

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
        context.update(WeatherDashboardView._watering_actionability(report))
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
