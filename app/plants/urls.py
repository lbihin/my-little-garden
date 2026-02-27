from django.urls import path
from plants import views

app_name = "plants"

urlpatterns = [
    path("", views.PlantListView.as_view(), name="list"),
    path("add/", views.PlantCreateView.as_view(), name="create"),
    # Identification (before slug catch-all)
    path("identify/", views.plant_identify_view, name="identify"),
    path("identify/search/", views.plant_search_htmx_view, name="identify-search"),
    path("identify/add/", views.plant_add_from_identify_view, name="identify-add"),
    # Tasks (non-slug)
    path("tasks/<int:pk>/toggle/", views.task_toggle_view, name="task-toggle"),
    path("tasks/<int:pk>/delete/", views.task_delete_view, name="task-delete"),
    # Slug-based routes
    path("<slug:slug>/", views.PlantDetailView.as_view(), name="detail"),
    path("<slug:slug>/edit/", views.PlantUpdateView.as_view(), name="edit"),
    path("<slug:slug>/delete/", views.plant_delete_view, name="delete"),
    path("<slug:slug>/tasks/add/", views.task_create_view, name="task-create"),
]
