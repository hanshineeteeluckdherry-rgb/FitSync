from django import forms

from django.utils import timezone

from .models import Exercise, WaterIntake, WeightRecord, WorkoutPlan


class WaterIntakeForm(forms.ModelForm):
    class Meta:
        model = WaterIntake
        fields = ["recorded_date", "litres"]
        labels = {"recorded_date": "Date", "litres": "Total water for this day (litres)"}
        widgets = {
            "recorded_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "litres": forms.NumberInput(attrs={"min": "0", "step": "0.05", "class": "form-control"}),
        }

    def clean_recorded_date(self):
        recorded_date = self.cleaned_data["recorded_date"]
        if recorded_date > timezone.localdate():
            raise forms.ValidationError("Choose today or an earlier date.")
        return recorded_date


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


class WorkoutSetForm(forms.Form):
    reps = forms.IntegerField(
        min_value=1,
        max_value=1000,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
    )
    weight_kg = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=6,
        decimal_places=2,
        label="Weight (kg)",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "0.01"}),
    )


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
