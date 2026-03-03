from django.urls import path

from accounts.views import UserLoginView, UserRegistrationView, UserLogoutView

app_name = 'accounts'

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('register/', UserRegistrationView.as_view(), name='register')
]
