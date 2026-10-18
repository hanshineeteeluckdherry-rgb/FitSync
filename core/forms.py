from django import forms


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
