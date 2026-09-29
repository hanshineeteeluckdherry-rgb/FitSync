from django import forms

from .models import Exercise, WeightRecord, WorkoutPlan


class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        fields = [
            "name",
            "category",
            "secondary_muscles",
            "equipment",
            "difficulty",
            "intensity",
            "description",
            "instructions",
            "image",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "instructions": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"


class WorkoutPlanForm(forms.ModelForm):
    GOAL_CHOICES = [
        ("", "Select a fitness goal"),
        ("Build Strength", "Build Strength"),
        ("Muscle Gain", "Muscle Gain"),
        ("Fat Loss", "Fat Loss"),
        ("Endurance", "Endurance"),
        ("General Fitness", "General Fitness"),
        ("Mobility", "Mobility"),
    ]

    DAYS = [
        ("Mon", "Mon"),
        ("Tue", "Tue"),
        ("Wed", "Wed"),
        ("Thu", "Thu"),
        ("Fri", "Fri"),
        ("Sat", "Sat"),
        ("Sun", "Sun"),
    ]

    goal = forms.ChoiceField(choices=GOAL_CHOICES, required=False)

    workout_days = forms.MultipleChoiceField(
        choices=DAYS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = WorkoutPlan
        fields = ["name", "goal", "description", "workout_days"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Upper Body Strength"}),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Describe the purpose or focus of this plan...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.workout_days:
            self.initial["workout_days"] = self.instance.workout_days.split(",")
        for name in ["name", "description"]:
            self.fields[name].widget.attrs["class"] = "form-control"
        self.fields["goal"].widget.attrs["class"] = "form-select"

    def save(self, commit=True):
        plan = super().save(commit=False)
        plan.workout_days = ",".join(self.cleaned_data.get("workout_days", []))
        if commit:
            plan.save()
        return plan


class WeightRecordForm(forms.ModelForm):
    class Meta:
        model = WeightRecord
        fields = ["weight_kg", "recorded_date", "note", "progress_photo"]
        widgets = {
            "recorded_date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
