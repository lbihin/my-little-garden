import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
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
            return redirect(
                "gardens:plants:detail", garden_slug=garden.slug, slug=plant.slug
            )
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
        garden = self.object.garden
        context["garden"] = garden
        context["tasks"] = self.object.tasks.all()
        context["pending_count"] = self.object.tasks.filter(done=False).count()
        context["task_form"] = PlantTaskForm()

        # Care suggestions for this specific plant
        try:
            from plants.care import suggest_care_tasks
            from weather.services import fetch_weather

            if garden.address and garden.address.latitude and garden.address.longitude:
                lat = float(garden.address.latitude)
                lon = float(garden.address.longitude)
            else:
                lat, lon = 48.8566, 2.3522  # Paris default

            weather = fetch_weather(lat, lon)
            current = weather.current_snapshot() if weather.ok else {}
            existing = set(
                self.object.tasks.filter(done=False).values_list("title", flat=True)
            )
            context["care_suggestions"] = suggest_care_tasks(
                plants=[self.object],
                air_temp=current.get("air_temp"),
                soil_temp=current.get("soil_temp_6cm"),
                recent_rain_mm=(
                    weather.recent_precipitation_mm(48) if weather.ok else None
                ),
                existing_task_titles=existing,
            )
        except Exception:
            logger.exception("Care suggestions failed")
            context["care_suggestions"] = []

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
    return render(
        request, "plants/delete.html", {"garden": plant.garden, "plant": plant}
    )


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
    return render(
        request,
        "plants/partials/task-list.html",
        {"plant": plant, "tasks": tasks, "task_form": PlantTaskForm()},
    )


@login_required
def task_toggle_view(request, garden_slug, pk):
    task = get_object_or_404(
        PlantTask,
        pk=pk,
        plant__garden__slug=garden_slug,
        plant__garden__created_by=request.user,
    )
    if request.method == "POST":
        task.done = not task.done
        task.completed_at = timezone.now() if task.done else None
        task.save()
    tasks = task.plant.tasks.all()
    return render(
        request,
        "plants/partials/task-list.html",
        {"plant": task.plant, "tasks": tasks, "task_form": PlantTaskForm()},
    )


@login_required
def task_delete_view(request, garden_slug, pk):
    task = get_object_or_404(
        PlantTask,
        pk=pk,
        plant__garden__slug=garden_slug,
        plant__garden__created_by=request.user,
    )
    plant = task.plant
    if request.method == "POST":
        task.delete()
    tasks = plant.tasks.all()
    return render(
        request,
        "plants/partials/task-list.html",
        {"plant": plant, "tasks": tasks, "task_form": PlantTaskForm()},
    )


@login_required
def suggestion_accept_view(request, garden_slug, slug):
    """Accept a care suggestion — creates a PlantTask and refreshes the task list."""
    plant = get_object_or_404(
        Plant, slug=slug, garden__slug=garden_slug, garden__created_by=request.user
    )
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        notes = request.POST.get("notes", "").strip()
        priority = int(request.POST.get("priority", 2))

        if title:
            PlantTask.objects.create(
                plant=plant,
                title=title,
                notes=notes,
                priority=min(max(priority, 1), 3),
            )

    tasks = plant.tasks.all()
    return render(
        request,
        "plants/partials/task-list.html",
        {"plant": plant, "tasks": tasks, "task_form": PlantTaskForm()},
    )


@login_required
def plant_identify_view(request, garden_slug):
    """Main identification page — supports both name search and photo recognition."""
    import os

    from plants.services import identify_plant, identify_plant_from_file

    garden = get_object_or_404(Garden, slug=garden_slug, created_by=request.user)
    context = {"garden": garden, "mode": request.GET.get("mode", "search")}

    # Photo-based identification (PlantNet)
    if request.method == "POST":
        api_key = os.environ.get("PLANTNET_API_KEY", "")
        has_photo = "photo" in request.FILES
        has_url = "image_url" in request.POST and request.POST["image_url"].strip()

        if not has_photo and not has_url:
            context["photo_error"] = "Veuillez sélectionner une photo."
        elif not api_key:
            context["photo_error"] = (
                "Clé API PlantNet non configurée (PLANTNET_API_KEY)."
            )
        elif has_photo:
            # File upload mode
            photo = request.FILES["photo"]
            result = identify_plant_from_file(photo, api_key)
            context["photo_result"] = result
            if not result.get("success"):
                context["photo_error"] = result.get("error", "Erreur inconnue.")
        else:
            # URL fallback mode
            image_url = request.POST.get("image_url", "").strip()
            result = identify_plant(image_url, api_key)
            context["photo_result"] = result
            if not result.get("success"):
                context["photo_error"] = result.get("error", "Erreur inconnue.")

        context["mode"] = "photo"

    return render(request, "plants/identify.html", context)


@login_required
def plant_search_htmx_view(request, garden_slug):
    """HTMX endpoint — live species search by name via iNaturalist."""
    from plants.services import search_species

    garden = get_object_or_404(Garden, slug=garden_slug, created_by=request.user)
    query = request.GET.get("q", "").strip()

    result = search_species(query)
    return render(
        request,
        "plants/partials/search-results.html",
        {"garden": garden, "result": result, "query": query},
    )


@login_required
def plant_add_from_identify_view(request, garden_slug):
    """Quick-add a plant from identification results (name or photo)."""
    garden = get_object_or_404(Garden, slug=garden_slug, created_by=request.user)

    if request.method == "POST":
        common_name = request.POST.get("common_name", "").strip()
        scientific_name = request.POST.get("scientific_name", "").strip()
        photo_url = request.POST.get("photo_url", "").strip()
        score = request.POST.get("score", "")

        if not common_name and not scientific_name:
            return redirect("gardens:plants:identify", garden_slug=garden.slug)

        plant = Plant.objects.create(
            garden=garden,
            common_name=common_name or scientific_name,
            scientific_name=scientific_name,
            photo_url=photo_url,
            identification_score=float(score) if score else None,
        )
        return redirect(plant.get_absolute_url())

    return redirect("gardens:plants:identify", garden_slug=garden.slug)
