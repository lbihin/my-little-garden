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
