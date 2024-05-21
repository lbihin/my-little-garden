from django import forms

from activities.models import FertilizationTask, Activity


class FertilizationForm(forms.ModelForm):
    class Meta:
        model = FertilizationTask
        fields = ['fertilizer', 'quantity_as_float', 'unit']


class ActivityForm(forms.ModelForm):

    class Meta:
        model = Activity
        fields = ('comment', )