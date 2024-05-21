# Create your views here.
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import DetailView, UpdateView
from django.views.generic import ListView

from activities.forms import ActivityForm
from activities.models import Activity
from gardens.models import Garden


class ActivityListView(LoginRequiredMixin, ListView):
    template_name = 'activities/activities.html'
    model = Activity
    context_object_name = 'activities'
    slug_url_kwarg = 'garden_slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        garden = get_object_or_404(Garden, slug=self.kwargs.get(self.slug_url_kwarg))
        context['garden'] = garden
        context['address'] = garden.address
        return context

    def get_queryset(self):
        garden = get_object_or_404(Garden, slug=self.kwargs.get(self.slug_url_kwarg))
        return self.model.objects.filter(garden=garden)


class ActivityDescriptionView(LoginRequiredMixin, DetailView):
    template_name = 'activities/partials/descriptions.html'
    model = Activity
    context_object_name = 'activity'


class ActivityUpdateView(LoginRequiredMixin, UpdateView):
    model = Activity
    form_class = ActivityForm
    template_name = 'activities/create-update.html'
    success_url = reverse_lazy('activities:index')
