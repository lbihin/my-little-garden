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
    # Follow the Pro — lawn programme
    path("programme/", views.LawnProgramView.as_view(), name="program"),
    path(
        "programme/questionnaire/",
        views.LawnQuestionnaireView.as_view(),
        name="questionnaire",
    ),
    path(
        "programme/evaluation/",
        views.LawnAssessmentView.as_view(),
        name="assessment",
    ),
]
