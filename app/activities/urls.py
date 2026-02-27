from django.urls import path

from activities import views

app_name = 'activities'

urlpatterns = [
    path('', views.ActivityListView.as_view(), name='index'),
    path('create/', views.ActivityFormView.as_view(), name='create_activity'),
    # HTMX partials
    path('description/<int:pk>/', views.ActivityDescriptionView.as_view(), name='description'),
]