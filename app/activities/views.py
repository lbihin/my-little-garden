# Create your views here.
from activities.forms import ActivityForm
from activities.models import Activity
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView
from gardens.models import Garden


class ActivityListView(LoginRequiredMixin, ListView):
    template_name = "activities/activities.html"
    model = Activity
    context_object_name = "activities"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        garden = get_object_or_404(Garden, slug=self.kwargs["garden_slug"])
        context["garden"] = garden
        context["address"] = garden.address

        context["actionable_weekly_deficit"] = 0.0
        context["actionable_total_litres"] = 0.0
        context["profile_strategy_note"] = ""
        context["priority_advice"] = None
        context["lawn_tasks"] = []
        context["action_tasks"] = []
        context["info_tasks"] = []

        # Include greenkeeping report so we can show lawn advice details
        try:
            from weather.greenkeeping import WATERING_PROFILES, analyse
            from weather.services import fetch_weather

            if garden.address and garden.address.latitude and garden.address.longitude:
                lat = float(garden.address.latitude)
                lon = float(garden.address.longitude)
                context["location_source"] = garden.address.city or garden.address.name
            else:
                lat, lon = 48.8566, 2.3522
                context["location_source"] = "Paris (par défaut)"

            weather = fetch_weather(lat, lon)
            report = analyse(
                weather,
                profile=garden.watering_profile,
                surface=garden.surface or 0,
            )
            context["report"] = report

            if report and report.watering:
                watering = report.watering
                profile_meta = WATERING_PROFILES.get(
                    watering.profile, WATERING_PROFILES["standard"]
                )
                raw_deficit = float(watering.weekly_deficit)
                if watering.profile == "pro":
                    ignore_threshold = 0.0
                    context["profile_strategy_note"] = (
                        "Mode pro: tout déficit est traité immédiatement."
                    )
                elif watering.profile == "laissez_faire":
                    ignore_threshold = raw_deficit
                    context["profile_strategy_note"] = (
                        "Mode laisser-faire: priorité à l'observation et aux pluies naturelles."
                    )
                else:
                    ignore_threshold = float(profile_meta["ignore_threshold"])
                    context["profile_strategy_note"] = (
                        f"{profile_meta['description']} (tolérance {ignore_threshold:.0f} mm)."
                    )

                actionable = max(0.0, raw_deficit - ignore_threshold)
                context["actionable_weekly_deficit"] = round(actionable, 1)
                if watering.surface > 0:
                    context["actionable_total_litres"] = round(
                        actionable * watering.surface, 0
                    )

            if report and report.advices:
                priority_map = {"danger": 3, "warn": 3, "info": 2, "ok": 1}
                badge_map = {
                    "danger": ("badge-error", "Urgent"),
                    "warn": ("badge-warning", "Action"),
                    "info": ("badge-info", "À faire"),
                    "ok": ("badge-success", "OK"),
                }
                action_tasks, info_tasks = [], []
                for advice in report.advices:
                    st = advice.status.value
                    badge_class, badge_label = badge_map.get(st, ("badge-ghost", "Info"))
                    task = {
                        "title": advice.title,
                        "detail": advice.detail,
                        "icon": advice.icon,
                        "status": st,
                        "actionable": advice.actionable,
                        "priority": priority_map.get(st, 1),
                        "badge_class": badge_class,
                        "badge_label": badge_label,
                        "prefill": advice.title,
                    }
                    if advice.actionable:
                        action_tasks.append(task)
                    else:
                        info_tasks.append(task)

                action_tasks.sort(key=lambda t: (-t["priority"], t["title"]))
                # Priority alert: first actionable danger/warn
                urgent = [t for t in action_tasks if t["status"] in ("danger", "warn")]
                context["priority_advice"] = urgent[0] if urgent else None
                context["action_tasks"] = action_tasks
                context["info_tasks"] = info_tasks
                # Keep lawn_tasks for backward compatibility
                context["lawn_tasks"] = action_tasks
        except Exception:
            import logging

            logging.getLogger(__name__).exception("Greenkeeping analysis failed")
            context["report"] = None

        return context

    def get_queryset(self):
        garden = get_object_or_404(Garden, slug=self.kwargs["garden_slug"])
        return self.model.objects.filter(garden=garden)


class QuickLogActivity(LoginRequiredMixin, View):
    """HTMX endpoint: record a task as done without leaving the page."""

    def post(self, request, garden_slug):
        garden = get_object_or_404(Garden, slug=garden_slug)
        task_title = request.POST.get("task_title", "").strip()
        note = request.POST.get("note", "").strip()
        comment = task_title
        if note:
            comment = f"{task_title}\n\n{note}"
        if not comment:
            comment = "Intervention manuelle"
        Activity.objects.create(
            garden=garden,
            comment=comment,
            creation=timezone.now(),
        )
        activities = Activity.objects.filter(garden=garden)
        return render(
            request,
            "activities/partials/quick_log_success.html",
            {
                "activities": activities,
                "task_title": task_title or "Intervention",
                "garden": garden,
            },
        )


class ActivityDeleteView(LoginRequiredMixin, View):
    """HTMX endpoint: delete an activity and return the refreshed table."""

    def post(self, request, garden_slug, pk):
        garden = get_object_or_404(Garden, slug=garden_slug)
        activity = get_object_or_404(Activity, pk=pk, garden=garden)
        activity.delete()
        activities = Activity.objects.filter(garden=garden)
        return render(
            request,
            "activities/partials/table.html",
            {"activities": activities, "garden": garden},
        )


class ActivityDescriptionView(LoginRequiredMixin, DetailView):
    template_name = "activities/partials/descriptions.html"
    model = Activity
    context_object_name = "activity"


class ActivityFormView(LoginRequiredMixin, CreateView):
    template_name = "activities/create-update.html"
    form_class = ActivityForm

    def get_initial(self):
        initial = super().get_initial()
        prefill = self.request.GET.get("prefill", "").strip()
        if prefill:
            initial["comment"] = prefill
        return initial

    def get_success_url(self):
        return reverse(
            "gardens:activities:index",
            kwargs={"garden_slug": self.object.garden.slug},
        )

    def form_valid(self, form):
        form.instance.garden = get_object_or_404(
            Garden, slug=self.kwargs["garden_slug"]
        )
        form.instance.creation = timezone.now()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data["garden"] = get_object_or_404(Garden, slug=self.kwargs["garden_slug"])
        data["prefill"] = self.request.GET.get("prefill", "").strip()
        return data
