from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import member_required

from .forms import OutdoorActivityForm
from .models import OutdoorActivity


@member_required
def activity_list(request):
    activities = OutdoorActivity.objects.filter(member=request.user)
    return render(
        request,
        "activities/activity_list.html",
        {"activities": activities, "active_sidebar": "activities"},
    )


@member_required
def add_activity(request):
    form = OutdoorActivityForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        activity = form.save(commit=False)
        activity.member = request.user
        activity.save()
        messages.success(request, "Outdoor activity saved.")
        return redirect("activities:activity_detail", pk=activity.pk)

    return render(
        request,
        "activities/activity_form.html",
        {"form": form, "active_sidebar": "activities"},
    )


@member_required
def activity_detail(request, pk):
    activity = get_object_or_404(OutdoorActivity, pk=pk, member=request.user)
    pace = None
    if activity.distance_km and activity.duration_minutes:
        pace = round(activity.duration_minutes / float(activity.distance_km), 2)

    return render(
        request,
        "activities/activity_detail.html",
        {
            "activity": activity,
            "pace": pace,
            "active_sidebar": "activities",
        },
    )


@member_required
def delete_activity(request, pk):
    activity = get_object_or_404(OutdoorActivity, pk=pk, member=request.user)
    if request.method == "POST":
        activity.delete()
        messages.success(request, "Outdoor activity deleted.")
        return redirect("activities:activity_list")

    return render(
        request,
        "activities/delete_activity.html",
        {"activity": activity, "active_sidebar": "activities"},
    )
