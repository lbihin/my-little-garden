import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView

from gardens.models import Garden
from plants.forms import PlantForm, PlantTaskForm
from plants.models import Plant, PlantTask

logger = logging.getLogger(__name__)


class PlantListView(LoginRequiredMixin, ListView):
    template_name = "plants/list.html"
    context_object_name = "plants"

    def get_queryset(self):
        self.garden = get_object_or_404(
            Garden, slug=self.kwargs["garden_slug"], created_by=self.request.user
        )
        return Plant.objects.filter(garden=self.garden)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["garden"] = self.garden
        return context


class PlantCreateView(LoginRequiredMixin, ListView):
    template_name = "plants/create-update.html"

    def get(self, request, garden_slug):
        garden = get_object_or_404(Garden, slug=garden_slug, created_by=request.user)
        context = {"garden": garden, "form": PlantForm()}
        return render(request, self.template_name, context)

    def post(self, request, garden_slug):
        garden = get_object_or_404(Garden, slug=garden_slug, created_by=request.user)
        form = PlantForm(request.POST)
        if form.is_valid():
            plant = form.save(commit=False)
            plant.garden = garden
            plant.save()
            return redirect("gardens:plants:detail", garden_slug=garden.slug, slug=plant.slug)
        context = {"garden": garden, "form": form}
        return render(request, self.template_name, context)


class PlantDetailView(LoginRequiredMixin, DetailView):
    template_name = "plants/detail.html"
    model = Plant
    context_object_name = "plant"

    def get_queryset(self):
        return Plant.objects.filter(
            garden__slug=self.kwargs["garden_slug"],
            garden__created_by=self.request.user,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["garden"] = self.object.garden
        context["tasks"] = self.object.tasks.all()
        context["pending_count"] = self.object.tasks.filter(done=False).count()
        context["task_form"] = PlantTaskForm()
        return context


class PlantUpdateView(LoginRequiredMixin, DetailView):
    model = Plant
    template_name = "plants/create-update.html"

    def get_queryset(self):
        return Plant.objects.filter(
            garden__slug=self.kwargs["garden_slug"],
            garden__created_by=self.request.user,
        )

    def get(self, request, *args, **kwargs):
        plant = self.get_object()
        context = {
            "garden": plant.garden,
            "plant": plant,
            "form": PlantForm(instance=plant),
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        plant = self.get_object()
        form = PlantForm(request.POST, instance=plant)
        if form.is_valid():
            form.save()
            return redirect(plant.get_absolute_url())
        context = {"garden": plant.garden, "plant": plant, "form": form}
        return render(request, self.template_name, context)


@login_required
def plant_delete_view(request, garden_slug, slug):
    plant = get_object_or_404(
        Plant, slug=slug, garden__slug=garden_slug, garden__created_by=request.user
    )
    if request.method == "POST":
        garden = plant.garden
        plant.delete()
        return redirect("gardens:plants:list", garden_slug=garden.slug)
    return render(request, "plants/delete.html", {"garden": plant.garden, "plant": plant})


# ---------- Tasks (HTMX-powered) ----------


@login_required
def task_create_view(request, garden_slug, slug):
    plant = get_object_or_404(
        Plant, slug=slug, garden__slug=garden_slug, garden__created_by=request.user
    )
    if request.method == "POST":
        form = PlantTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.plant = plant
            task.save()
    tasks = plant.tasks.all()
    return render(request, "plants/partials/task-list.html", {"plant": plant, "tasks": tasks, "task_form": PlantTaskForm()})


@login_required
def task_toggle_view(request, garden_slug, pk):
    task = get_object_or_404(
        PlantTask, pk=pk, plant__garden__slug=garden_slug, plant__garden__created_by=request.user
    )
    if request.method == "POST":
        task.done = not task.done
        task.completed_at = timezone.now() if task.done else None
        task.save()
    tasks = task.plant.tasks.all()
    return render(request, "plants/partials/task-list.html", {"plant": task.plant, "tasks": tasks, "task_form": PlantTaskForm()})


@login_required
def task_delete_view(request, garden_slug, pk):
    task = get_object_or_404(
        PlantTask, pk=pk, plant__garden__slug=garden_slug, plant__garden__created_by=request.user
    )
    plant = task.plant
    if request.method == "POST":
        task.delete()
    tasks = plant.tasks.all()
    return render(request, "plants/partials/task-list.html", {"plant": plant, "tasks": tasks, "task_form": PlantTaskForm()})


@login_required
def plant_identify_view(request, garden_slug):
    """PlantNet identification — accepts an image URL and returns suggestions."""
    import os
    from plants.services import identify_plant

    garden = get_object_or_404(Garden, slug=garden_slug, created_by=request.user)
    context = {"garden": garden}

    if request.method == "POST":
        image_url = request.POST.get("image_url", "").strip()
        api_key = os.environ.get("PLANTNET_API_KEY", "")

        if not image_url:
            context["error"] = "Veuillez fournir une URL d'image."
        elif not api_key:
            context["error"] = "Clé API PlantNet non configurée (PLANTNET_API_KEY)."
        else:
            result = identify_plant(image_url, api_key)
            context["result"] = result
            if result.get("success"):
                context["form"] = PlantForm(
                    initial={
                        "common_name": result["common_name"],
                        "scientific_name": result["scientific_name"],
                    }
                )

    return render(request, "plants/identify.html", context)
