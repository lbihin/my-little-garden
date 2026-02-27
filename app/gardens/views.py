from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView
from gardens.forms import AddressForm, GardenForm
from gardens.models import Garden


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["address"] = self.object.address
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
