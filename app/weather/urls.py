from django.urls import path
from weather import views

app_name = "weather"

urlpatterns = [
    path("", views.WeatherDashboardView.as_view(), name="dashboard"),
    path(
        "change-profile/",
        views.ChangeWateringProfileView.as_view(),
        name="change-profile",
    ),
]
