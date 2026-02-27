from activities.models import Activity
from django import forms


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ("comment",)
