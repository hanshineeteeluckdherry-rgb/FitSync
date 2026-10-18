from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import User
from attendance.models import AttendanceRecord
from bookings.models import Session
from workouts.models import WorkoutSession

from .forms import ContactForm


def home(request):
    now = timezone.localtime()
    completed_workouts = WorkoutSession.objects.filter(
        completed_at__date=now.date()
    )
    workout_minutes = sum(
        session.duration_minutes or 0 for session in completed_workouts
    )
    live_stats = {
        "members_in_gym": AttendanceRecord.objects.filter(
            check_out_time__isnull=True
        ).count(),
        "workouts_today": completed_workouts.count(),
        "calories_today": workout_minutes * 7,
        "classes_running": Session.objects.filter(
            date=now.date(),
            start_time__lte=now.time(),
            end_time__gt=now.time(),
            status=Session.Status.SCHEDULED,
        ).count(),
        "active_members": User.objects.filter(
            role=User.Role.MEMBER, is_active=True
        ).count(),
        "coach_count": User.objects.filter(
            role=User.Role.COACH, is_active=True
        ).count(),
    }
    return render(request, "core/home.html", {"live_stats": live_stats})


def features(request):
    """Display FitSync's public platform features."""
    return render(request, "core/features.html")


def contact(request):
    initial = {}
    if request.user.is_authenticated:
        initial = {
            "full_name": request.user.get_full_name(),
            "email": request.user.email,
        }

    form = ContactForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        topic = form.cleaned_data["topic"] or "GENERAL"
        message_body = (
            f"From: {form.cleaned_data['full_name']}\n"
            f"Email: {form.cleaned_data['email']}\n"
            f"Topic: {topic}\n\n"
            f"{form.cleaned_data['message']}"
        )
        send_mail(
            subject=f"FitSync contact: {topic}",
            message=message_body,
            from_email=None,
            recipient_list=["hello@fitsync.com"],
        )
        messages.success(request, "Thank you. Your message has been sent.")
        return redirect("core:contact")

    return render(request, "core/contact.html", {"form": form})


# Create your views here.
