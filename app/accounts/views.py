from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.views.generic import CreateView


class UserLoginView(LoginView):
    template_name = 'accounts/login.html'
    # Redirect in settings.


class UserRegistrationView(CreateView):
    form_class = UserCreationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        form.save()  # save the user
        return super(UserRegistrationView, self).form_valid(form)


class UserLogoutView(LogoutView):
    template_name = 'accounts/logout.html'
    # Redirect in settings.
