import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView
from gardens.forms import AddressForm, GardenForm
from gardens.models import Garden

logger = logging.getLogger(__name__)


class GardenFormView(LoginRequiredMixin, ListView):
    """Handles both GET (show form) and POST (create garden + optional address)."""

    template_name = "gardens/create-update.html"

    def get(self, request):
        context = {
            "form": GardenForm(),
            "address_form": AddressForm(prefix="addr"),
        }
        return render(request, self.template_name, context)

    def post(self, request):
        form = GardenForm(request.POST)
        address_form = AddressForm(request.POST, prefix="addr")

        if form.is_valid() and address_form.is_valid():
            garden = form.save(commit=False)
            garden.created_by = request.user

            if address_form.has_data():
                address = address_form.save(commit=False)
                address.name = garden.name
                address.save()
                garden.address = address

            garden.save()
            return redirect("gardens:list")

        context = {"form": form, "address_form": address_form}
        return render(request, self.template_name, context)


class GardenListView(LoginRequiredMixin, ListView):
    template_name = "gardens/gardens.html"
    model = Garden
    context_object_name = "gardens"

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return user.gardens.all()
        else:
            return Garden.objects.none()


class GardenDetailView(LoginRequiredMixin, DetailView):
    template_name = "gardens/details.html"
    model = Garden
    context_object_name = "garden"

    # Default coordinates (Paris) if garden has no address
    DEFAULT_LAT = 48.8566
    DEFAULT_LON = 2.3522

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["address"] = self.object.address

        # Fetch weather + greenkeeping analysis for the dashboard
        try:
            from weather.greenkeeping import analyse
            from weather.services import fetch_weather

            garden = self.object
            if garden.address and garden.address.latitude and garden.address.longitude:
                lat = float(garden.address.latitude)
                lon = float(garden.address.longitude)
                context["location_source"] = garden.address.city or garden.address.name
            else:
                lat, lon = self.DEFAULT_LAT, self.DEFAULT_LON
                context["location_source"] = "Paris (par défaut)"

            weather = fetch_weather(lat, lon)
            report = analyse(
                weather,
                profile=garden.watering_profile,
                surface=garden.surface or 0,
            )
            context["report"] = report
            context["weather"] = weather
            if weather.ok:
                context["current"] = weather.current_snapshot()
        except Exception:
            logger.exception("Greenkeeping analysis failed")
            context["report"] = None

        # Plant tasks for the dashboard "On fait quoi aujourd'hui?" section
        try:
            from plants.models import PlantTask

            garden = self.object
            context["plant_count"] = garden.plants.count()
            context["plant_tasks_pending"] = (
                PlantTask.objects.filter(plant__garden=garden, done=False)
                .select_related("plant")
                .order_by("-priority", "due_date")[:5]
            )
            context["plant_tasks_pending_total"] = PlantTask.objects.filter(
                plant__garden=garden, done=False
            ).count()
        except Exception:
            logger.exception("Plant tasks fetch failed")
            context["plant_count"] = 0
            context["plant_tasks_pending"] = []
            context["plant_tasks_pending_total"] = 0

        # Care suggestions based on plant genus + weather + season
        try:
            from plants.care import suggest_care_tasks
            from plants.models import PlantTask

            garden = self.object
            plants = list(garden.plants.all())
            if plants:
                existing = set(
                    PlantTask.objects.filter(
                        plant__garden=garden, done=False
                    ).values_list("title", flat=True)
                )
                weather = context.get("weather")
                current = context.get("current", {})
                report = context.get("report")
                watering = report.watering if report else None
                context["care_suggestions"] = suggest_care_tasks(
                    plants=plants,
                    air_temp=current.get("air_temp"),
                    soil_temp=current.get("soil_temp_6cm"),
                    recent_rain_mm=(
                        weather.recent_precipitation_mm(48)
                        if weather and weather.ok
                        else None
                    ),
                    existing_task_titles=existing,
                    weekly_deficit=(watering.weekly_deficit if watering else None),
                )
        except Exception:
            logger.exception("Care suggestions failed")
            context["care_suggestions"] = []

        return context


@login_required
def garden_delete_view(request, slug: str):
    if not request.htmx:
        raise Http404("Delete Garden is not HTMX requested. Invalid request")
    garden = get_object_or_404(Garden, slug=slug, created_by=request.user)
    if request.method == "POST":
        garden.delete()
        # Get all gardens after delete
        gardens = Garden.objects.filter(created_by=request.user)
        context = {"gardens": gardens}
        return render(request, "gardens/partials/cards.html", context)
    return render(request, "gardens/delete.html", {"garden": garden})


class GardenUpdateView(LoginRequiredMixin, DetailView):
    """Handles GET (show pre-filled form) and POST (update garden + address)."""

    model = Garden
    template_name = "gardens/create-update.html"

    def get(self, request, *args, **kwargs):
        garden = self.get_object()
        context = {
            "garden": garden,
            "form": GardenForm(instance=garden),
            "address_form": AddressForm(instance=garden.address, prefix="addr"),
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        garden = self.get_object()
        form = GardenForm(request.POST, instance=garden)
        address_form = AddressForm(request.POST, instance=garden.address, prefix="addr")

        if form.is_valid() and address_form.is_valid():
            garden = form.save(commit=False)

            if address_form.has_data():
                address = address_form.save(commit=False)
                if not address.name:
                    address.name = garden.name
                # Reset lat/lon so geocoding is re-triggered on save
                address.latitude = None
                address.longitude = None
                address.save()
                garden.address = address

            garden.save()
            return redirect("gardens:detail", slug=garden.slug)

        context = {
            "garden": garden,
            "form": form,
            "address_form": address_form,
        }
        return render(request, self.template_name, context)


def garden_name_length_view(request):
    text = request.POST.get("name", "")
    count = len(text)
    return HttpResponse(
        f"{count} / {Garden._meta.get_field('name').max_length} caractères."
    )


@login_required
def search_garden_view(request):
    card_search = request.GET.get("garden-search", None)
    if card_search:  # Search functionality
        context = {"is_search": True}
        gardens = Garden.objects.search(card_search)
    else:  # Clear functionality
        context = {"is_search": False}
        gardens = Garden.objects.all()
    context["gardens"] = gardens
    return render(request, "gardens/partials/cards.html", context=context)
