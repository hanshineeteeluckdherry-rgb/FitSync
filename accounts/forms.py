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

from .models import CoachAssignment, MemberProfile, User


class BootstrapFormMixin:
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


class RegistrationForm(BootstrapFormMixin, forms.Form):
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
    fitness_goal = forms.ChoiceField(
        choices=FITNESS_GOALS,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()

        # Short placeholders keep the form close to the approved Figma layout.
        self.fields["first_name"].widget.attrs["placeholder"] = "Lionel"
        self.fields["last_name"].widget.attrs["placeholder"] = "Messi"
        self.fields["email"].widget.attrs["placeholder"] = "lionel.messi@email.com"
        self.fields["password1"].widget.attrs["placeholder"] = "Enter your password"
        self.fields["password2"].widget.attrs["placeholder"] = "Confirm your password"
        self.fields["age"].widget.attrs.update({"placeholder": "28", "min": "13", "max": "100"})
        self.fields["height_cm"].widget.attrs.update({"placeholder": "180", "min": "100", "max": "250"})
        self.fields["current_weight_kg"].widget.attrs.update({"placeholder": "82", "step": "0.1"})

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
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

        # The fitness values come directly from step 2 of registration.
        MemberProfile.objects.create(
            user=user,
            age=self.cleaned_data["age"],
            height_cm=self.cleaned_data["height_cm"],
            current_weight_kg=self.cleaned_data["current_weight_kg"],
            fitness_goal=self.cleaned_data["fitness_goal"],
        )
        return user


class EmailLoginForm(BootstrapFormMixin, forms.Form):
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
            if existing_user and not existing_user.is_active:
                raise ValidationError(
                    "This account is inactive. Please contact an administrator."
                )

            username = existing_user.username if existing_user else email
            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password,
            )
            if self.user_cache is None:
                raise ValidationError("Invalid email or password.")
        return cleaned_data

    def get_user(self):
        return self.user_cache


class UserProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        duplicate = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise ValidationError("Another account already uses this email.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        # Registered users use their email as the simple login username.
        if "@" in user.username:
            user.username = user.email
        if commit:
            user.save()
        return user


class MemberProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MemberProfile
        fields = [
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


class AdminRoleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["role"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()


class CoachAssignmentForm(BootstrapFormMixin, forms.ModelForm):
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


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()


class StyledPasswordResetForm(BootstrapFormMixin, PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()


class StyledSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()
