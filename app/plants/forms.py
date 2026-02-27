from django import forms

from plants.models import Plant, PlantTask


class PlantForm(forms.ModelForm):
    class Meta:
        model = Plant
        fields = ["common_name", "scientific_name", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["common_name"].widget.attrs.update(
            {"class": "input input-bordered w-full", "placeholder": "ex. Lavande"}
        )
        self.fields["scientific_name"].widget.attrs.update(
            {
                "class": "input input-bordered w-full",
                "placeholder": "ex. Lavandula angustifolia",
            }
        )
        self.fields["scientific_name"].required = False
        self.fields["notes"].widget.attrs.update(
            {
                "class": "textarea textarea-bordered w-full h-24",
                "placeholder": "Notes, emplacement, particularités…",
            }
        )


class PlantTaskForm(forms.ModelForm):
    class Meta:
        model = PlantTask
        fields = ["title", "notes", "priority", "due_date"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].widget.attrs.update(
            {"class": "input input-bordered w-full", "placeholder": "ex. Tailler"}
        )
        self.fields["notes"].widget.attrs.update(
            {"class": "textarea textarea-bordered w-full h-16", "placeholder": "Détails…"}
        )
        self.fields["priority"].widget.attrs.update(
            {"class": "select select-bordered"}
        )
        self.fields["due_date"].widget = forms.DateInput(
            attrs={"type": "date", "class": "input input-bordered"}
        )
        self.fields["due_date"].required = False
