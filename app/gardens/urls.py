from django.urls import include, path
from gardens import views

app_name = "gardens"

urlpatterns = [
    path("", views.GardenListView.as_view(), name="list"),
    path("create/", views.GardenFormView.as_view(), name="create"),
    # HTMX partials (before slug catch-all)
    path("name_length/", views.garden_name_length_view, name="length-name"),
    path("search/", views.search_garden_view, name="search"),
    # Slug-based routes
    path("<slug:slug>/", views.GardenDetailView.as_view(), name="detail"),
    path("<slug:slug>/edit/", views.GardenUpdateView.as_view(), name="edit"),
    path("<slug:slug>/delete/", views.garden_delete_view, name="delete"),
    path("<slug:garden_slug>/activities/", include("activities.urls")),
    path("<slug:garden_slug>/weather/", include("weather.urls")),
]
