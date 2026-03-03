from django import forms
from weather.models import LawnAssessment, LawnProfile


class LawnProfileForm(forms.ModelForm):
    class Meta:
        model = LawnProfile
        fields = [
            "grass_type",
            "lawn_state",
            "usage",
            "sun_exposure",
            "soil_type",
            "goal",
            "has_irrigation",
            "mowing_frequency",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mowing_frequency"].widget = forms.NumberInput(
            attrs={"min": 0, "max": 7, "class": "input input-bordered w-20"}
        )


class LawnAssessmentForm(forms.ModelForm):
    issues = forms.MultipleChoiceField(
        choices=LawnAssessment.ISSUE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Problèmes observés",
    )

    class Meta:
        model = LawnAssessment
        fields = ["overall_rating", "issues", "notes"]

    def clean_issues(self):
        issues = self.cleaned_data.get("issues", [])
        if "none" in issues and len(issues) > 1:
            issues = ["none"]
        return issues
