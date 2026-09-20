from django import forms

from .models import MembershipPackage, Payment


class BootstrapFormMixin:
    def add_bootstrap_classes(self):
        for field in self.fields.values():
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
