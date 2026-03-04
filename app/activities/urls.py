from activities import views
from django.urls import path

app_name = "activities"

urlpatterns = [
    path("", views.ActivityListView.as_view(), name="index"),
    path("create/", views.ActivityFormView.as_view(), name="create_activity"),
    # HTMX: quick-log a task without leaving the page
    path("log/", views.QuickLogActivity.as_view(), name="quick_log"),
    # HTMX: delete an activity and refresh the table
    path("delete/<int:pk>/", views.ActivityDeleteView.as_view(), name="delete_activity"),
    # HTMX: activity detail partial
    path(
        "description/<int:pk>/",
        views.ActivityDescriptionView.as_view(),
        name="description",
    ),
]
