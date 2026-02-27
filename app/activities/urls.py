from django.urls import path

from activities import views
from app import utils

app_name = 'activities'

urlpatterns = [
    path('', views.ActivityListView.as_view(), name='index'),
    path('create/', views.ActivityFormView.as_view(), name='create_activity')
]

htmx_urlpatterns = [
    path('description/<int:pk>/', views.ActivityDescriptionView.as_view(), name='description')
]

urlpatterns = utils.arrange_urlpatterns(urlpatterns + htmx_urlpatterns)