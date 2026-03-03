# Create your views here.
from activities.forms import ActivityForm
from activities.models import Activity
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
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

        # Include greenkeeping report so we can show lawn advice details
        try:
            from weather.greenkeeping import analyse
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
        except Exception:
            import logging

            logging.getLogger(__name__).exception("Greenkeeping analysis failed")
            context["report"] = None

        return context

    def get_queryset(self):
        garden = get_object_or_404(Garden, slug=self.kwargs["garden_slug"])
        return self.model.objects.filter(garden=garden)


class ActivityDescriptionView(LoginRequiredMixin, DetailView):
    template_name = "activities/partials/descriptions.html"
    model = Activity
    context_object_name = "activity"


class ActivityFormView(LoginRequiredMixin, CreateView):
    template_name = "activities/create-update.html"
    form_class = ActivityForm

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
        return data
