from django import forms
from django.utils import timezone

from .models import OutdoorActivity


class OutdoorActivityForm(forms.ModelForm):
    class Meta:
        model = OutdoorActivity
        fields = ["activity_type", "date", "distance_km", "duration_minutes"]
        widgets = {
            "activity_type": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "distance_km": forms.NumberInput(
                attrs={"class": "form-control", "min": "0.01", "step": "0.01"}
            ),
            "duration_minutes": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
        }

    def clean_date(self):
        activity_date = self.cleaned_data["date"]
        if activity_date > timezone.localdate():
            raise forms.ValidationError("Activity date cannot be in the future.")
        return activity_date

    def clean_distance_km(self):
        distance = self.cleaned_data["distance_km"]
        if distance <= 0:
            raise forms.ValidationError("Distance must be greater than zero.")
        return distance

    def clean_duration_minutes(self):
        duration = self.cleaned_data["duration_minutes"]
        if duration <= 0:
            raise forms.ValidationError("Duration must be greater than zero.")
        return duration
