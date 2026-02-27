from django import forms

from activities.models import Activity


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ("comment",)
