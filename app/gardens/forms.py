from django import forms
from gardens.models import Address, Garden


class GardenForm(forms.ModelForm):
    class Meta:
        model = Garden
        fields = ["name", "description", "surface", "watering_profile"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # surface and watering_profile are optional in the form;
        # model defaults kick in when not provided.
        self.fields["surface"].required = False
        self.fields["watering_profile"].required = False

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


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ["street", "city", "postal_code", "state", "country"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # All address fields are optional — user can skip entirely
        for field in self.fields.values():
            field.required = False

    def has_data(self) -> bool:
        """Return True if the user filled in at least one address field."""
        if not hasattr(self, "cleaned_data"):
            return False
        return any(
            self.cleaned_data.get(f)
            for f in ("street", "city", "postal_code", "country")
        )
