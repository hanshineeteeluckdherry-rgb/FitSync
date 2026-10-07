from django import forms

from .models import Membership, MembershipPackage, Payment


class BootstrapFormMixin:
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


class SimulatedPaymentForm(BootstrapFormMixin, forms.Form):
    payer_name = forms.CharField(max_length=120, label="Name on payment")
    payment_method = forms.ChoiceField(choices=Payment.Method.choices)
    demo_card_number = forms.CharField(
        label="Demo card number",
        initial="4242 4242 4242 4242",
        disabled=True,
        required=False,
    )
    demo_expiry = forms.CharField(label="Expiry", initial="12/30", disabled=True, required=False)
    demo_cvv = forms.CharField(label="CVV", initial="123", disabled=True, required=False)
    simulate_failure = forms.BooleanField(
        required=False,
        label="Simulate failed payment (demo only)",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()
        self.fields["payer_name"].widget.attrs["placeholder"] = "Lionel Messi"


class MembershipPackageForm(BootstrapFormMixin, forms.ModelForm):
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
            self.initial["allowed_service_types"] = self.instance.allowed_service_type_list

    def save(self, commit=True):
        package = super().save(commit=False)
        package.allowed_service_types = ",".join(
            self.cleaned_data.get("allowed_service_types", [])
        )
        if commit:
            package.save()
        return package


class MembershipRecordForm(BootstrapFormMixin, forms.ModelForm):
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
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date must be on or after the start date.")
        return cleaned_data


class PaymentRecordForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["payment_method", "status"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()
