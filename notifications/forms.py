from django import forms

from .models import Notice


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
        if publish_date and expires_on and expires_on < publish_date:
            self.add_error("expires_on", "The expiry date must be on or after the publish date.")
        return cleaned_data
