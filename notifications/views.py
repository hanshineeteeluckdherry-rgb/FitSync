from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required

from .forms import NoticeForm
from .models import Notice, Notification


@login_required
def notification_list(request):
    # Show only the notifications that belong to the signed-in member.
    notifications = Notification.objects.filter(recipient=request.user)
    return render(
        request,
        "notifications/notification_list.html",
        {"notifications": notifications},
    )


@login_required
def notification_detail(request, notification_id):
    # Members can only open their own notifications (anything else gives a 404).
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        recipient=request.user,
    )
    # Opening a notification marks it as read.
    if not notification.is_read:
        notification.is_read = True
        # Only update the is_read column instead of saving the whole row.
        notification.save(update_fields=["is_read"])
    return render(
        request,
        "notifications/notification_detail.html",
        {"notification": notification},
    )


@login_required
@require_POST
def mark_as_read(request, notification_id):
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        recipient=request.user,
    )
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    if notification.link:
        return redirect(notification.link)
    return redirect("notifications:list")


@login_required
@require_POST
def mark_all_as_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return redirect("notifications:list")


@admin_required
def notice_list(request):
    return render(
        request,
        "notifications/admin/notice_list.html",
        {"notices": Notice.objects.all(), "active_sidebar": "notices"},
    )


@admin_required
def notice_create(request):
    # The form is empty on a normal visit and filled with data on a POST.
    form = NoticeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        notice = form.save(commit=False)
        notice.created_by = request.user
        notice.save()
        return redirect("notifications:notice_list")
    return render(
        request,
        "notifications/admin/notice_form.html",
        {"form": form, "title": "Add Gym Notice", "active_sidebar": "notices"},
    )


@admin_required
def notice_edit(request, notice_id):
    notice = get_object_or_404(Notice, pk=notice_id)
    form = NoticeForm(request.POST or None, instance=notice)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("notifications:notice_list")
    return render(
        request,
        "notifications/admin/notice_form.html",
        {"form": form, "title": "Edit Gym Notice", "active_sidebar": "notices"},
    )


@admin_required
def notice_delete(request, notice_id):
    notice = get_object_or_404(Notice, pk=notice_id)
    # Only delete after the admin confirms by submitting the confirmation form.
    if request.method == "POST":
        notice.delete()
        return redirect("notifications:notice_list")
    return render(
        request,
        "notifications/admin/notice_confirm_delete.html",
        {"notice": notice, "active_sidebar": "notices"},
    )
