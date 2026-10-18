import base64
import io
from datetime import date, datetime, time, timedelta

import qrcode

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .decorators import admin_required, coach_required, member_required, role_required, staff_required
from .forms import (
    AdminRoleForm,
    AdminUserCreationForm,
    CoachAssignmentForm,
    EmailLoginForm,
    MemberProfileForm,
    RegistrationForm,
    StyledPasswordChangeForm,
    UserProfileForm,
)
from .models import CoachAssignment, CoachProfile, MemberProfile, User
from attendance.models import AttendanceRecord, GymConfiguration, MemberQRCode
from bookings.models import Booking, Session
from workouts.models import WaterIntake, WeightRecord, WorkoutPlan, WorkoutSession
from memberships.models import Membership, Payment


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome to FitSync. Your account has been created.")
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect("accounts:member_dashboard")

    fitness_fields = {"age", "height_cm", "current_weight_kg", "fitness_goal"}
    start_step = 2 if any(name in form.errors for name in fitness_fields) else 1
    return render(
        request,
        "accounts/register.html",
        {"form": form, "start_step": start_step},
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    form = EmailLoginForm(request=request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        # Keep the browser session only when the member asks to be remembered.
        if not form.cleaned_data.get("remember_me"):
            request.session.set_expiry(0)
        messages.success(request, f"Welcome back, {user.first_name or 'member'}.")
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect("accounts:dashboard")

    return render(request, "accounts/login.html", {"form": form})


@login_required
def logout_view(request):
    # Logout is POST-only so a normal link cannot sign someone out by accident.
    if request.method == "POST":
        logout(request)
        messages.success(request, "You have been logged out.")
        return redirect("core:home")
    return redirect("accounts:dashboard")


@login_required
def dashboard_redirect(request):
    if not request.user.is_active:
        logout(request)
        messages.error(request, "Your account is inactive.")
        return redirect("accounts:login")

    if request.user.is_superuser or request.user.role == User.Role.ADMIN:
        return redirect("accounts:admin_dashboard")
    if request.user.role == User.Role.STAFF:
        return redirect("accounts:staff_dashboard")
    if request.user.role == User.Role.COACH:
        return redirect("accounts:coach_dashboard")
    return redirect("accounts:member_dashboard")


@member_required
def member_dashboard(request):
    today = timezone.localdate()
    profile, _ = MemberProfile.objects.get_or_create(user=request.user)
    profile_fields = [
        profile.phone,
        profile.date_of_birth or profile.age,
        profile.height_cm,
        profile.current_weight_kg,
        profile.target_weight_kg,
        profile.fitness_goal,
    ]
    completed_items = sum(1 for value in profile_fields if value)
    profile_percent = round((completed_items / len(profile_fields)) * 100)

    personal_plan_count = WorkoutPlan.objects.filter(
        member=request.user,
        plan_type="PERSONAL",
        is_active=True,
    ).count()
    coach_plan_count = WorkoutPlan.objects.filter(
        member=request.user,
        plan_type="COACH_ASSIGNED",
        is_active=True,
    ).count()
    completed_workouts = WorkoutSession.objects.filter(
        member=request.user,
        completed_at__isnull=False,
    )
    completed_workout_count = completed_workouts.count()
    latest_weight = WeightRecord.objects.filter(member=request.user).first()
    water_record = WaterIntake.objects.filter(member=request.user, recorded_date=today).first()

    month_start = today.replace(day=1)
    previous_month_end = month_start - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)
    workouts_this_month = completed_workouts.filter(
        completed_at__date__gte=month_start,
    ).count()
    workouts_last_month = completed_workouts.filter(
        completed_at__date__gte=previous_month_start,
        completed_at__date__lte=previous_month_end,
    ).count()

    coach_assignment = CoachAssignment.objects.filter(
        member=request.user,
        active=True,
    ).select_related("coach").first()

    upcoming_booking = Booking.objects.filter(
        member=request.user,
        status=Booking.Status.CONFIRMED,
        session__status=Session.Status.SCHEDULED,
        session__date__gte=today,
    ).select_related("session__service", "session__instructor").order_by(
        "session__date", "session__start_time"
    ).first()

    current_occupancy = AttendanceRecord.objects.filter(
        check_out_time__isnull=True,
    ).count()
    max_capacity = GymConfiguration.get_capacity()
    if max_capacity:
        occupancy_percent = min(round((current_occupancy / max_capacity) * 100), 100)
    else:
        occupancy_percent = 0
    if occupancy_percent < 45:
        occupancy_status = "Quiet"
    elif occupancy_percent < 75:
        occupancy_status = "Moderate"
    else:
        occupancy_status = "Busy"

    active_membership = Membership.objects.filter(
        member=request.user,
        status=Membership.Status.ACTIVE,
        start_date__lte=today,
        end_date__gte=today,
    ).select_related("package").first()

    qr_image = None
    if active_membership:
        qr_code, _ = MemberQRCode.objects.get_or_create(member=request.user)
        if qr_code.is_active:
            image = qrcode.make(str(qr_code.qr_token))
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            qr_image = base64.b64encode(buffer.getvalue()).decode()

    recent_activity = []
    for workout in completed_workouts[:4]:
        exercise_count = workout.exercise_records.values("exercise_id").distinct().count()
        plan_name = workout.workout_plan.name if workout.workout_plan else "Workout"
        recent_activity.append(
            {
                "time": workout.completed_at,
                "title": f"Completed {plan_name} — {exercise_count} exercises",
                "icon": "img/member-dashboard/activity-workout.svg",
                "colour": "teal",
            }
        )

    recent_bookings = Booking.objects.filter(member=request.user).select_related(
        "session__service"
    )[:3]
    for booking in recent_bookings:
        recent_activity.append(
            {
                "time": booking.booked_at,
                "title": f"Booked {booking.session.service.name}",
                "icon": "img/member-dashboard/activity-booking.svg",
                "colour": "blue",
            }
        )

    for weight in WeightRecord.objects.filter(member=request.user)[:3]:
        weight_time = timezone.make_aware(datetime.combine(weight.recorded_date, time.min))
        recent_activity.append(
            {
                "time": weight_time,
                "title": f"New weight recorded: {weight.weight_kg} kg",
                "icon": "img/member-dashboard/activity-weight.svg",
                "colour": "amber",
            }
        )

    recent_activity.sort(key=lambda item: item["time"], reverse=True)

    context = {
        "profile": profile,
        "profile_percent": profile_percent,
        "personal_plan_count": personal_plan_count,
        "coach_plan_count": coach_plan_count,
        "completed_workout_count": completed_workout_count,
        "workouts_this_month": workouts_this_month,
        "workout_change": workouts_this_month - workouts_last_month,
        "latest_weight": latest_weight,
        "today_water_litres": water_record.litres if water_record else 0,
        "coach_assignment": coach_assignment,
        "upcoming_booking": upcoming_booking,
        "current_occupancy": current_occupancy,
        "max_capacity": max_capacity,
        "occupancy_percent": occupancy_percent,
        "occupancy_status": occupancy_status,
        "active_membership": active_membership,
        "qr_image": qr_image,
        "recent_activity": recent_activity[:4],
        "today": today,
        "active_sidebar": "dashboard",
    }
    return render(request, "accounts/dashboards/member_dashboard.html", context)


@role_required(User.Role.STAFF)
def staff_dashboard(request):
    context = {
        "member_count": User.objects.filter(role=User.Role.MEMBER, is_active=True).count(),
        "active_sidebar": "dashboard",
    }
    return render(request, "accounts/dashboards/staff_dashboard.html", context)


@coach_required
def coach_dashboard(request):
    assignments = CoachAssignment.objects.filter(
        coach=request.user, active=True, member__is_active=True
    ).select_related("member")

    assigned_member_ids = assignments.values_list("member_id", flat=True)
    coach_plan_count = WorkoutPlan.objects.filter(
        coach=request.user,
        plan_type="COACH_ASSIGNED",
        is_active=True,
    ).count()
    completed_workout_count = WorkoutSession.objects.filter(
        member_id__in=assigned_member_ids,
        completed_at__isnull=False,
    ).count()

    context = {
        "assignments": assignments,
        "assignment_count": assignments.count(),
        "coach_plan_count": coach_plan_count,
        "completed_workout_count": completed_workout_count,
        "active_sidebar": "dashboard",
    }
    return render(request, "accounts/dashboards/coach_dashboard.html", context)


@admin_required
def admin_dashboard(request):
    today = date.today()
    scheduled_sessions = Session.objects.filter(
        date__gte=today,
        status=Session.Status.SCHEDULED,
    ).select_related("service", "instructor")
    successful_payments = Payment.objects.filter(status=Payment.Status.SUCCESS)

    recent_activity = []

    for payment in Payment.objects.select_related("member")[:4]:
        recent_activity.append(
            {
                "time": payment.created_at,
                "icon": "bi-wallet2",
                "title": "Payment recorded",
                "detail": f"{payment.member} - Rs {payment.amount}",
            }
        )

    for attendance in AttendanceRecord.objects.select_related("member")[:4]:
        recent_activity.append(
            {
                "time": attendance.check_in_time,
                "icon": "bi-qr-code-scan",
                "title": "Member checked in",
                "detail": str(attendance.member),
            }
        )

    for booking in Booking.objects.select_related("member", "session__service")[:4]:
        recent_activity.append(
            {
                "time": booking.booked_at,
                "icon": "bi-calendar-check",
                "title": "Booking created",
                "detail": f"{booking.member} - {booking.session.service.name}",
            }
        )

    for membership in Membership.objects.select_related("member", "package")[:4]:
        recent_activity.append(
            {
                "time": membership.created_at,
                "icon": "bi-card-checklist",
                "title": "Membership added",
                "detail": f"{membership.member} - {membership.package.name}",
            }
        )

    recent_activity.sort(key=lambda item: item["time"], reverse=True)

    context = {
        "total_users": User.objects.count(),
        "active_users": User.objects.filter(is_active=True).count(),
        "member_count": User.objects.filter(role=User.Role.MEMBER).count(),
        "staff_count": User.objects.filter(role=User.Role.STAFF).count(),
        "coach_count": User.objects.filter(role=User.Role.COACH).count(),
        "admin_count": User.objects.filter(role=User.Role.ADMIN).count(),
        "assignment_count": CoachAssignment.objects.filter(active=True).count(),
        "active_membership_count": Membership.objects.filter(
            status=Membership.Status.ACTIVE,
            start_date__lte=today,
            end_date__gte=today,
        ).count(),
        "today_attendance_count": AttendanceRecord.objects.filter(
            check_in_time__date=today,
        ).count(),
        "current_occupancy": AttendanceRecord.objects.filter(
            check_out_time__isnull=True,
        ).count(),
        "upcoming_session_count": scheduled_sessions.count(),
        "upcoming_sessions": scheduled_sessions[:5],
        "confirmed_booking_count": Booking.objects.filter(
            status=Booking.Status.CONFIRMED,
        ).count(),
        "successful_payment_count": successful_payments.count(),
        "total_revenue": successful_payments.aggregate(total=Sum("amount"))["total"] or 0,
        "recent_activity": recent_activity[:6],
        "active_sidebar": "dashboard",
    }
    return render(request, "accounts/dashboards/admin_dashboard.html", context)


@login_required
def profile(request):
    member_profile = None
    if request.user.role == User.Role.MEMBER:
        member_profile, _ = MemberProfile.objects.get_or_create(user=request.user)

    return render(
        request,
        "accounts/profile.html",
        {"member_profile": member_profile, "active_sidebar": "profile"},
    )


@login_required
def profile_edit(request):
    user_form = UserProfileForm(request.POST or None, instance=request.user)
    member_form = None

    if request.user.role == User.Role.MEMBER:
        member_profile, _ = MemberProfile.objects.get_or_create(user=request.user)
        member_form = MemberProfileForm(request.POST or None, 
                                        request.FILES or None,
                                        instance=member_profile)

    forms_are_valid = user_form.is_valid()
    if member_form is not None:
        forms_are_valid = member_form.is_valid() and forms_are_valid

    if request.method == "POST" and forms_are_valid:
        user_form.save()
        if member_form is not None:
            member_form.save()
        messages.success(request, "Your profile has been updated.")
        return redirect("accounts:profile")

    context = {
        "user_form": user_form,
        "member_form": member_form,
        "active_sidebar": "profile",
    }
    return render(request, "accounts/profile_edit.html", context)


@login_required
def password_change(request):
    form = StyledPasswordChangeForm(user=request.user, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        # Keep the current session valid after the password is changed.
        update_session_auth_hash(request, user)
        messages.success(request, "Your password has been changed.")
        return redirect("accounts:password_change_done")
    return render(request, "accounts/password_change_form.html", {"form": form})


@login_required
def password_change_done(request):
    return render(request, "accounts/password_change_done.html")


@admin_required
def admin_user_list(request):
    users = User.objects.all().order_by("first_name", "last_name", "email")
    query = request.GET.get("q", "").strip()
    role = request.GET.get("role", "").strip()
    status = request.GET.get("status", "").strip()

    if query:
        users = users.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    if role in User.Role.values:
        users = users.filter(role=role)
    if status == "active":
        users = users.filter(is_active=True)
    elif status == "inactive":
        users = users.filter(is_active=False)

    context = {
        "users": users,
        "query": query,
        "selected_role": role,
        "selected_status": status,
        "role_choices": User.Role.choices,
        "active_sidebar": "users",
    }
    return render(request, "accounts/admin/user_list.html", context)


@admin_required
def admin_user_create(request):
    form = AdminUserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        new_user = form.save()
        messages.success(request, "User account created successfully.")
        return redirect("accounts:admin_user_detail", user_id=new_user.id)

    return render(
        request,
        "accounts/admin/user_form.html",
        {"form": form, "active_sidebar": "users"},
    )


@admin_required
def admin_user_detail(request, user_id):
    selected_user = get_object_or_404(User, pk=user_id)
    return render(
        request,
        "accounts/admin/user_detail.html",
        {"selected_user": selected_user, "active_sidebar": "users"},
    )


@admin_required
def admin_user_role(request, user_id):
    selected_user = get_object_or_404(User, pk=user_id)
    form = AdminRoleForm(request.POST or None, instance=selected_user)

    if request.method == "POST" and form.is_valid():
        if selected_user.is_superuser:
            messages.error(request, "The role of a Django superuser cannot be changed here.")
        else:
            updated_user = form.save()
            # Make sure the matching role profile exists for later feature pages.
            if updated_user.role == User.Role.MEMBER:
                MemberProfile.objects.get_or_create(user=updated_user)
            elif updated_user.role == User.Role.COACH:
                CoachProfile.objects.get_or_create(user=updated_user)
            messages.success(request, "User role updated successfully.")
        return redirect("accounts:admin_user_detail", user_id=selected_user.id)

    return render(
        request,
        "accounts/admin/user_role_form.html",
        {"form": form, "selected_user": selected_user, "active_sidebar": "users"},
    )


@admin_required
def admin_user_status(request, user_id):
    selected_user = get_object_or_404(User, pk=user_id)

    if request.method == "POST":
        if selected_user == request.user:
            messages.error(request, "You cannot deactivate your own account.")
        elif selected_user.is_superuser:
            messages.error(request, "A superuser cannot be deactivated from this page.")
        else:
            selected_user.is_active = not selected_user.is_active
            selected_user.save(update_fields=["is_active"])
            state = "activated" if selected_user.is_active else "deactivated"
            messages.success(request, f"User account {state}.")
        return redirect("accounts:admin_user_detail", user_id=selected_user.id)

    return render(
        request,
        "accounts/admin/user_status_confirm.html",
        {"selected_user": selected_user, "active_sidebar": "users"},
    )


@admin_required
def coach_assignment_list(request):
    assignments = CoachAssignment.objects.select_related("coach", "member")
    return render(
        request,
        "accounts/admin/coach_assignment_list.html",
        {"assignments": assignments, "active_sidebar": "coaches"},
    )


@admin_required
def coach_assignment_create(request):
    form = CoachAssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Coach assignment created.")
        return redirect("accounts:coach_assignment_list")
    return render(
        request,
        "accounts/admin/coach_assignment_form.html",
        {"form": form, "active_sidebar": "coaches"},
    )


@admin_required
def coach_assignment_delete(request, assignment_id):
    assignment = get_object_or_404(CoachAssignment, pk=assignment_id)
    if request.method == "POST":
        assignment.delete()
        messages.success(request, "Coach assignment removed.")
        return redirect("accounts:coach_assignment_list")
    return render(
        request,
        "accounts/admin/coach_assignment_delete.html",
        {"assignment": assignment, "active_sidebar": "coaches"},
    )


@staff_required
def staff_member_list(request):
    members = User.objects.filter(role=User.Role.MEMBER).order_by(
        "first_name", "last_name", "email"
    )
    query = request.GET.get("q", "").strip()
    if query:
        members = members.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    return render(
        request,
        "accounts/staff/member_list.html",
        {"members": members, "query": query, "active_sidebar": "members"},
    )


@staff_required
def staff_member_detail(request, user_id):
    member = get_object_or_404(User, pk=user_id, role=User.Role.MEMBER)
    member_profile, _ = MemberProfile.objects.get_or_create(user=member)
    return render(
        request,
        "accounts/staff/member_detail.html",
        {
            "member": member,
            "member_profile": member_profile,
            "active_sidebar": "members",
        },
    )
