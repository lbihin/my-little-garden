from django import forms

from gardens.models import Garden


class GardenForm(forms.ModelForm):
    class Meta:
        model = Garden
        fields = ["name", "description"]

    def clean_name(self):
        name = self.cleaned_data.get("name")
        qs = Garden.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                f"'{name}' est déjà utilisé. Veuillez choisir un autre nom de jardin."
            )
        return name
