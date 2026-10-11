from django import forms

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
    """Validate session scheduling details entered by staff or administrators."""
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
        super().__init__(*args, **kwargs)
        # Only active services and active coaches can be assigned to a session.
        self.fields["service"].queryset = Service.objects.filter(is_active=True)
        self.fields["instructor"].queryset = User.objects.filter(
            role=User.Role.COACH,
            is_active=True,
        )
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"
