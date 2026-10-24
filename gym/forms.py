from datetime import datetime
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import (
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from gym.models import (
    CoachAssignment,
    CoachProfile,
    ContactMessage,
    Exercise,
    GymConfiguration,
    GymSettings,
    MemberProfile,
    Membership,
    MembershipPackage,
    Notice,
    OutdoorActivity,
    Payment,
    Service,
    Session,
    TeamMember,
    User,
    WaterIntake,
    WeightRecord,
    WorkoutPlan,
)

# Accounts and profiles — Rheva

# 2.3 Fitness information and goals


class AccountsBootstrapFormMixin:
    """Adds the Bootstrap classes already used by the shared FitSync UI."""

    def add_bootstrap_classes(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css_class = "form-check-input"
            elif isinstance(widget, forms.RadioSelect):
                css_class = "fitness-goal-radio"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css_class = "form-select"
            else:
                css_class = "form-control"
            old_class = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{old_class} {css_class}".strip()


class RegistrationForm(AccountsBootstrapFormMixin, forms.Form):
    FITNESS_GOALS = [
        ("Build Muscle", "Build Muscle"),
        ("Lose Weight", "Lose Weight"),
        ("Improve Endurance", "Improve Endurance"),
        ("Body Recomposition", "Body Recomposition"),
        ("Increase Strength", "Increase Strength"),
        ("General Wellness", "General Wellness"),
    ]
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)
    age = forms.IntegerField(min_value=13, max_value=100)
    height_cm = forms.IntegerField(min_value=100, max_value=250)
    current_weight_kg = forms.DecimalField(
        label="Weight (kg)", max_digits=5, decimal_places=2, min_value=30, max_value=350
    )
    fitness_goal = forms.ChoiceField(choices=FITNESS_GOALS, widget=forms.RadioSelect)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()
        self.fields["first_name"].widget.attrs["placeholder"] = "Lionel"
        self.fields["last_name"].widget.attrs["placeholder"] = "Messi"
        self.fields["email"].widget.attrs["placeholder"] = "lionel.messi@email.com"
        self.fields["password1"].widget.attrs["placeholder"] = "Enter your password"
        self.fields["password2"].widget.attrs["placeholder"] = "Confirm your password"
        self.fields["age"].widget.attrs.update(
            {"placeholder": "28", "min": "13", "max": "100"}
        )
        self.fields["height_cm"].widget.attrs.update(
            {"placeholder": "180", "min": "100", "max": "250"}
        )
        self.fields["current_weight_kg"].widget.attrs.update(
            {"placeholder": "82", "step": "0.1"}
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and (password1 != password2):
            self.add_error("password2", "The two passwords do not match.")
        if password1:
            temp_user = User(
                email=cleaned_data.get("email", ""),
                first_name=cleaned_data.get("first_name", ""),
                last_name=cleaned_data.get("last_name", ""),
            )
            try:
                validate_password(password1, user=temp_user)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data

    @transaction.atomic
    def save(self):
        email = self.cleaned_data["email"]
        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=self.cleaned_data["first_name"].strip(),
            last_name=self.cleaned_data["last_name"].strip(),
            password=self.cleaned_data["password1"],
            role=User.Role.MEMBER,
        )
        MemberProfile.objects.create(
            user=user,
            age=self.cleaned_data["age"],
            height_cm=self.cleaned_data["height_cm"],
            current_weight_kg=self.cleaned_data["current_weight_kg"],
            fitness_goal=self.cleaned_data["fitness_goal"],
        )
        return user


class EmailLoginForm(AccountsBootstrapFormMixin, forms.Form):
    email = forms.EmailField(label="Email address")
    password = forms.CharField(widget=forms.PasswordInput)
    remember_me = forms.BooleanField(required=False, label="Remember me")

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user_cache = None
        self.add_bootstrap_classes()
        self.fields["email"].widget.attrs["placeholder"] = "lionel.messi@email.com"
        self.fields["password"].widget.attrs["placeholder"] = "Enter your password"

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email", "").strip().lower()
        password = cleaned_data.get("password")
        if email and password:
            existing_user = User.objects.filter(email__iexact=email).first()
            if existing_user and (not existing_user.is_active):
                raise ValidationError(
                    "This account is inactive. Please contact an administrator."
                )
            username = existing_user.username if existing_user else email
            self.user_cache = authenticate(
                self.request, username=username, password=password
            )
            if self.user_cache is None:
                raise ValidationError("Invalid email or password.")
        return cleaned_data

    def get_user(self):
        return self.user_cache


class UserProfileForm(AccountsBootstrapFormMixin, forms.ModelForm):

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        duplicate = User.objects.filter(email__iexact=email).exclude(
            pk=self.instance.pk
        )
        if duplicate.exists():
            raise ValidationError("Another account already uses this email.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        if "@" in user.username:
            user.username = user.email
        if commit:
            user.save()
        return user


class MemberProfileForm(AccountsBootstrapFormMixin, forms.ModelForm):

    class Meta:
        model = MemberProfile
        fields = [
            "profile_picture",
            "phone",
            "date_of_birth",
            "emergency_contact",
            "age",
            "height_cm",
            "current_weight_kg",
            "target_weight_kg",
            "fitness_goal",
            "medical_notes",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "medical_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()


class AdminRoleForm(AccountsBootstrapFormMixin, forms.ModelForm):

    class Meta:
        model = User
        fields = ["role"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()


class AdminUserCreationForm(AccountsBootstrapFormMixin, forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    role = forms.ChoiceField(choices=User.Role.choices)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)
    is_active = forms.BooleanField(label="Active account", required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and (password1 != password2):
            self.add_error("password2", "The two passwords do not match.")
        if password1:
            temp_user = User(
                email=cleaned_data.get("email", ""),
                first_name=cleaned_data.get("first_name", ""),
                last_name=cleaned_data.get("last_name", ""),
            )
            try:
                validate_password(password1, user=temp_user)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data

    @transaction.atomic
    def save(self):
        email = self.cleaned_data["email"]
        role = self.cleaned_data["role"]
        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=self.cleaned_data["first_name"].strip(),
            last_name=self.cleaned_data["last_name"].strip(),
            password=self.cleaned_data["password1"],
            role=role,
            is_active=self.cleaned_data["is_active"],
        )
        if role == User.Role.MEMBER:
            MemberProfile.objects.create(user=user)
        elif role == User.Role.COACH:
            CoachProfile.objects.create(user=user)
        return user


class CoachAssignmentForm(AccountsBootstrapFormMixin, forms.ModelForm):

    class Meta:
        model = CoachAssignment
        fields = ["coach", "member", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["coach"].queryset = User.objects.filter(
            role=User.Role.COACH, is_active=True
        ).order_by("first_name", "last_name", "email")
        self.fields["member"].queryset = User.objects.filter(
            role=User.Role.MEMBER, is_active=True
        ).order_by("first_name", "last_name", "email")
        self.add_bootstrap_classes()


class StyledPasswordChangeForm(AccountsBootstrapFormMixin, PasswordChangeForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()


class StyledPasswordResetForm(AccountsBootstrapFormMixin, PasswordResetForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()


class StyledSetPasswordForm(AccountsBootstrapFormMixin, SetPasswordForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()


# Memberships and payments — Noorie


class MembershipsBootstrapFormMixin:

    def add_bootstrap_classes(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                continue
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"


class SimulatedPaymentForm(MembershipsBootstrapFormMixin, forms.Form):
    payer_name = forms.CharField(max_length=120, label="Name on payment")
    payment_method = forms.ChoiceField(choices=Payment.Method.choices)
    demo_card_number = forms.CharField(
        label="Demo card number",
        initial="4242 4242 4242 4242",
        disabled=True,
        required=False,
    )
    demo_expiry = forms.CharField(
        label="Expiry", initial="12/30", disabled=True, required=False
    )
    demo_cvv = forms.CharField(
        label="CVV", initial="123", disabled=True, required=False
    )
    simulate_failure = forms.BooleanField(
        required=False, label="Simulate failed payment (demo only)"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()
        self.fields["payer_name"].widget.attrs["placeholder"] = "Lionel Messi"


class MembershipPackageForm(MembershipsBootstrapFormMixin, forms.ModelForm):
    allowed_service_types = forms.MultipleChoiceField(
        choices=MembershipPackage.SERVICE_TYPE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select the services included in this plan. Leave all unchecked to allow every service.",
    )

    class Meta:
        model = MembershipPackage
        fields = [
            "name",
            "slug",
            "price",
            "duration_months",
            "description",
            "features",
            "audience",
            "allowed_service_types",
            "is_featured",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "features": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()
        if self.instance and self.instance.pk:
            self.initial["allowed_service_types"] = (
                self.instance.allowed_service_type_list
            )

    def save(self, commit=True):
        package = super().save(commit=False)
        package.allowed_service_types = ",".join(
            self.cleaned_data.get("allowed_service_types", [])
        )
        if commit:
            package.save()
        return package


class MembershipRecordForm(MembershipsBootstrapFormMixin, forms.ModelForm):

    class Meta:
        model = Membership
        fields = ["package", "start_date", "end_date", "status"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and (end_date < start_date):
            self.add_error("end_date", "End date must be on or after the start date.")
        return cleaned_data


class PaymentRecordForm(MembershipsBootstrapFormMixin, forms.ModelForm):

    class Meta:
        model = Payment
        fields = ["payment_method", "status"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()


# Services, sessions and bookings — Mehnaz

# 3.6 Manage scheduled sessions


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
        self.fields["service"].queryset = Service.objects.filter(is_active=True)
        self.fields["instructor"].queryset = User.objects.filter(
            role=User.Role.COACH, is_active=True
        )
        if self.coach:
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
            or timezone.make_aware(
                datetime.combine(self.instance.date, self.instance.start_time)
            )
            <= timezone.now()
        ):
            raise forms.ValidationError(
                "Only upcoming scheduled classes can be edited."
            )
        if day and start:
            if timezone.make_aware(datetime.combine(day, start)) <= timezone.now():
                self.add_error("date", "Choose a future date and time.")
            if (
                end
                and Session.objects.filter(
                    instructor=self.coach,
                    date=day,
                    status=Session.Status.SCHEDULED,
                    start_time__lt=end,
                    end_time__gt=start,
                )
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                raise forms.ValidationError(
                    "You already teach another class during this time."
                )
        if self.instance.pk and cleaned.get("capacity") is not None:
            if cleaned["capacity"] < self.instance.confirmed_booking_count:
                self.add_error(
                    "capacity",
                    "Capacity cannot be below the number of confirmed bookings.",
                )
        return cleaned


# Workouts, progress and water intake — Hanshinee

# 2.14 Personal workout plans; 2.18 Progress; 2.22 Workout recording; 2.23 History; 2.25 Water intake; 4.11 Exercise library


class WaterIntakeForm(forms.ModelForm):

    class Meta:
        model = WaterIntake
        fields = ["recorded_date", "litres"]
        labels = {
            "recorded_date": "Date",
            "litres": "Total water for this day (litres)",
        }
        widgets = {
            "recorded_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "litres": forms.NumberInput(
                attrs={"min": "0", "step": "0.05", "class": "form-control"}
            ),
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
        choices=DAYS, required=False, widget=forms.CheckboxSelectMultiple
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
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": "0", "step": "0.01"}
        ),
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


# Attendance — Bhavshika

# 4.8 Attendance corrections


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
        if check_in and check_out and (check_out <= check_in):
            self.add_error("check_out_time", "Check-out must be after check-in.")
        return cleaned_data


class GymConfigurationForm(forms.ModelForm):

    class Meta:
        model = GymConfiguration
        fields = ["max_capacity"]
        widgets = {
            "max_capacity": forms.NumberInput(attrs={"class": "form-control", "min": 1})
        }

    def clean_max_capacity(self):
        capacity = self.cleaned_data["max_capacity"]
        if capacity < 1:
            raise forms.ValidationError("Capacity must be at least 1.")
        return capacity


# Outdoor activities — Bhavshika

# 2.19 GPS activity (mobile phase); 2.20 Activity history


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


# Notifications and notices — Anjie


class NoticeForm(forms.ModelForm):

    class Meta:
        model = Notice
        fields = ["title", "message", "publish_date", "expires_on", "is_active"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 4}),
            "publish_date": forms.DateInput(attrs={"type": "date"}),
            "expires_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned_data = super().clean()
        publish_date = cleaned_data.get("publish_date")
        expires_on = cleaned_data.get("expires_on")
        if publish_date and expires_on and (expires_on < publish_date):
            self.add_error(
                "expires_on", "The expiry date must be on or after the publish date."
            )
        return cleaned_data


# Public pages and dashboard summaries — Shared

# 1.7 Contact enquiries; 4.14 Public contact details; 4.15 Enquiry management


class ContactForm(forms.Form):
    TOPIC_CHOICES = [
        ("", "Select a topic (optional)"),
        ("MEMBERSHIP", "Membership"),
        ("CLASSES", "Classes and bookings"),
        ("WORKOUTS", "Workouts and coaching"),
        ("PAYMENTS", "Payments"),
        ("OTHER", "Other"),
    ]
    full_name = forms.CharField(max_length=120)
    email = forms.EmailField()
    topic = forms.ChoiceField(choices=TOPIC_CHOICES, required=False)
    message = forms.CharField(max_length=1000, widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["full_name"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Your full name"}
        )
        self.fields["email"].widget.attrs.update(
            {"class": "form-control", "placeholder": "you@email.com"}
        )
        self.fields["topic"].widget.attrs["class"] = "form-select"
        self.fields["message"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Tell us how we can help...",
                "rows": 5,
                "data-contact-message": "",
            }
        )


# Team and contact management — Shared
# 4.13 Team profiles; 4.14 Contact details; 4.15 Enquiry management


class GymSettingsForm(forms.ModelForm):
    class Meta:
        model = GymSettings
        fields = [
            "address",
            "phone",
            "public_email",
            "careers_email",
            "opening_hours",
            "response_time",
            "instagram_url",
            "facebook_url",
            "social_handle",
            "map_image",
            "map_static_path",
        ]
        widgets = {"opening_hours": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class TeamMemberForm(forms.ModelForm):
    class Meta:
        model = TeamMember
        fields = [
            "display_name",
            "slug",
            "job_title",
            "department",
            "user",
            "bio",
            "featured_bio",
            "specialties",
            "experience",
            "photo",
            "static_photo",
            "is_featured",
            "is_active",
            "sort_order",
        ]
        widgets = {
            name: forms.Textarea(attrs={"rows": 3})
            for name in ("bio", "featured_bio", "specialties")
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = User.objects.filter(
            role__in=[User.Role.COACH, User.Role.STAFF, User.Role.ADMIN]
        )
        self.fields["is_featured"].help_text = (
            "Select this person for the large featured card; replaces the previous featured person."
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-check-input"
                if isinstance(field.widget, forms.CheckboxInput)
                else (
                    "form-select"
                    if isinstance(field.widget, forms.Select)
                    else "form-control"
                )
            )


class ContactMessageManagementForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["status", "staff_notes"]
        widgets = {
            "staff_notes": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }
