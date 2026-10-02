from django.shortcuts import render


def home(request):
    return render(request, "core/home.html")


def features(request):
    """Display FitSync's public platform features."""
    return render(request, "core/features.html")


# Create your views here.
