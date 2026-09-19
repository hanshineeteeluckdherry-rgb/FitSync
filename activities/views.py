# Create your views here.
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from .models import OutdoorActivity


@login_required
def activity_list(request):
    activities = OutdoorActivity.objects.filter(member=request.user)
    return render(request, "activities/activity_list.html", {"activities": activities})


@login_required
def add_activity(request):
    if request.method == "POST":
        activity_type = request.POST.get("activity_type")
        date = request.POST.get("date")
        distance_km = request.POST.get("distance_km")
        duration_minutes = request.POST.get("duration_minutes")

        if not all([activity_type, date, distance_km, duration_minutes]):
            messages.error(request, "Please fill in all fields.")
            return redirect("activities:add_activity")

        try:
            distance_km = float(distance_km)
            duration_minutes = int(duration_minutes)
        except ValueError:
            messages.error(request, "Distance and duration must be valid numbers.")
            return redirect("activities:add_activity")

        if distance_km <= 0 or duration_minutes <= 0:
            messages.error(request, "Distance and duration must be greater than zero.")
            return redirect("activities:add_activity")

        OutdoorActivity.objects.create(
            member=request.user,
            activity_type=activity_type,
            date=date,
            distance_km=distance_km,
            duration_minutes=duration_minutes,
        )
        messages.success(request, "Activity added successfully.")
        return redirect("activities:activity_list")

    return render(request, "activities/add_activity.html", {
        "activity_choices": OutdoorActivity.ACTIVITY_CHOICES
    })


@login_required
def activity_detail(request, pk):
    activity = get_object_or_404(OutdoorActivity, pk=pk, member=request.user)
    pace = None
    if activity.distance_km and activity.duration_minutes:
        pace = round(activity.duration_minutes / float(activity.distance_km), 2)
    return render(request, "activities/activity_detail.html", {
        "activity": activity,
        "pace": pace,
    })


@login_required
def delete_activity(request, pk):
    activity = get_object_or_404(OutdoorActivity, pk=pk, member=request.user)
    if request.method == "POST":
        activity.delete()
        messages.success(request, "Activity deleted.")
        return redirect("activities:activity_list")
    return render(request, "activities/delete_activity.html", {"activity": activity})