from django import forms

from .models import GymConfiguration


class AttendanceCorrectionForm(forms.Form):
    check_in_time = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"},
            format="%Y-%m-%dT%H:%M",
        )
    )
    check_out_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"},
            format="%Y-%m-%dT%H:%M",
        ),
    )
    correction_note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"})
    )

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get("check_in_time")
        check_out = cleaned_data.get("check_out_time")
        if check_in and check_out and check_out <= check_in:
            self.add_error("check_out_time", "Check-out must be after check-in.")
        return cleaned_data


class GymConfigurationForm(forms.ModelForm):
    class Meta:
        model = GymConfiguration
        fields = ["max_capacity"]
        widgets = {
            "max_capacity": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            )
        }

    def clean_max_capacity(self):
        capacity = self.cleaned_data["max_capacity"]
        if capacity < 1:
            raise forms.ValidationError("Capacity must be at least 1.")
        return capacity
