from datetime import datetime

from django import forms
from django.utils import timezone

from accounts.models import User

from .models import Service, Session


class ServiceForm(forms.ModelForm):
    """Validate service information entered by staff or administrators."""
    class Meta:
        model = Service
        fields = ["name", "service_type", "description", "price", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "price": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"


class SessionForm(forms.ModelForm):
    """Staff assign instructors; coaches schedule their own classes."""
    class Meta:
        model = Session
        fields = [
            "service",
            "instructor",
            "date",
            "start_time",
            "end_time",
            "capacity",
            "status",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "capacity": forms.NumberInput(attrs={"min": 1}),
        }

    def __init__(self, *args, **kwargs):
        self.coach = kwargs.pop("coach", None)
        super().__init__(*args, **kwargs)
        # Only active services and active coaches can be assigned to a session.
        self.fields["service"].queryset = Service.objects.filter(is_active=True)
        self.fields["instructor"].queryset = User.objects.filter(
            role=User.Role.COACH,
            is_active=True,
        )
        if self.coach:
            # Ignore any instructor/status values submitted by the browser.
            self.fields.pop("instructor")
            self.fields.pop("status")
            self.instance.instructor = self.coach
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned = super().clean()
        if not self.coach:
            return cleaned
        day = cleaned.get("date")
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if self.instance.pk and (
            self.instance.status != Session.Status.SCHEDULED
            or timezone.make_aware(datetime.combine(self.instance.date, self.instance.start_time)) <= timezone.now()
        ):
            raise forms.ValidationError("Only upcoming scheduled classes can be edited.")
        if day and start:
            if timezone.make_aware(datetime.combine(day, start)) <= timezone.now():
                self.add_error("date", "Choose a future date and time.")
            if end and Session.objects.filter(
                instructor=self.coach, date=day, status=Session.Status.SCHEDULED,
                start_time__lt=end, end_time__gt=start,
            ).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("You already teach another class during this time.")
        if self.instance.pk and cleaned.get("capacity") is not None:
            if cleaned["capacity"] < self.instance.confirmed_booking_count:
                self.add_error("capacity", "Capacity cannot be below the number of confirmed bookings.")
        return cleaned
