from django import forms

from activities.models import FertilizationTask, Activity


class FertilizationForm(forms.ModelForm):
    class Meta:
        model = FertilizationTask
        fields = ['fertilizer', 'quantity_as_float', 'unit']


class ActivityForm(forms.ModelForm):

    parent_garden = forms.CharField(initial='', disabled=True)

    class Meta:
        model = Activity
        fields = ('comment', 'task')
