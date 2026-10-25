from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import (
    Case,
    Count,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import TruncDate
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from gym.forms import (
    AdminRoleForm,
    AdminUserCreationForm,
    AttendanceCorrectionForm,
    CoachAssignmentForm,
    ContactForm,
    ContactMessageManagementForm,
    EmailLoginForm,
    ExerciseForm,
    GymConfigurationForm,
    GymSettingsForm,
    MemberProfileForm,
    MembershipPackageForm,
    MembershipRecordForm,
    NoticeForm,
    OutdoorActivityForm,
    PaymentRecordForm,
    RegistrationForm,
    ServiceForm,
    SessionForm,
    SimulatedPaymentForm,
    StyledPasswordChangeForm,
    TeamMemberForm,
    UserProfileForm,
    WaterIntakeForm,
    WeightRecordForm,
    WorkoutPlanForm,
    WorkoutSetForm,
)
from gym.models import (
    AttendanceRecord,
    Booking,
    CoachAssignment,
    CoachProfile,
    ContactMessage,
    Exercise,
    GymConfiguration,
    GymSettings,
    MemberProfile,
    MemberQRCode,
    Membership,
    MembershipPackage,
    Notice,
    Notification,
    OutdoorActivity,
    Payment,
    Service,
    Session,
    TeamMember,
    User,
    WaterIntake,
    WeightRecord,
    WorkoutExerciseRecord,
    WorkoutPlan,
    WorkoutPlanExercise,
    WorkoutSession,
)
from gym.permissions import (
    admin_required,
    coach_required,
    member_required,
    role_required,
    staff_required,
)
from smtplib import SMTPException
import base64
import io
import qrcode
import uuid

# Notifications — Anjie


def create_notification(
    recipient, notification_type, title, message, link="", reference_key=""
):
    if reference_key:
        notification, created = Notification.objects.get_or_create(
            recipient=recipient,
            notification_type=notification_type,
            reference_key=reference_key,
            defaults={"title": title, "message": message, "link": link},
        )
        return (notification, created)
    notification = Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        link=link,
    )
    return (notification, True)


# Accounts and profiles — Rheva

# 2.3 Fitness information and goals


# 1.4 Register a member
def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome to FitSync. Your account has been created.")
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}
        ):
            return redirect(next_url)
        return redirect("accounts:member_dashboard")
    fitness_fields = {"age", "height_cm", "current_weight_kg", "fitness_goal"}
    start_step = 2 if any((name in form.errors for name in fitness_fields)) else 1
    return render(
        request,
        "authentication/register.html",
        {"form": form, "start_step": start_step},
    )


# 1.5 and 2.1 Sign in
def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    form = EmailLoginForm(request=request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        if not form.cleaned_data.get("remember_me"):
            request.session.set_expiry(0)
        messages.success(request, f"Welcome back, {user.first_name or 'member'}.")
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}
        ):
            return redirect(next_url)
        return redirect("accounts:dashboard")
    return render(request, "authentication/login.html", {"form": form})


# 2.1 Sign out
@login_required
def logout_view(request):
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
    completed_items = sum((1 for value in profile_fields if value))
    profile_percent = round(completed_items / len(profile_fields) * 100)
    personal_plan_count = WorkoutPlan.objects.filter(
        member=request.user, plan_type="PERSONAL", is_active=True
    ).count()
    coach_plan_count = WorkoutPlan.objects.filter(
        member=request.user, plan_type="COACH_ASSIGNED", is_active=True
    ).count()
    completed_workouts = WorkoutSession.objects.filter(
        member=request.user, completed_at__isnull=False
    )
    completed_workout_count = completed_workouts.count()
    latest_weight = WeightRecord.objects.filter(member=request.user).first()
    water_record = WaterIntake.objects.filter(
        member=request.user, recorded_date=today
    ).first()
    month_start = today.replace(day=1)
    previous_month_end = month_start - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)
    workouts_this_month = completed_workouts.filter(
        completed_at__date__gte=month_start
    ).count()
    workouts_last_month = completed_workouts.filter(
        completed_at__date__gte=previous_month_start,
        completed_at__date__lte=previous_month_end,
    ).count()
    coach_assignment = (
        CoachAssignment.objects.filter(member=request.user, active=True)
        .select_related("coach")
        .first()
    )
    upcoming_booking = (
        Booking.objects.filter(
            member=request.user,
            status=Booking.Status.CONFIRMED,
            session__status=Session.Status.SCHEDULED,
        )
        .filter(
            Q(session__date__gt=today)
            | Q(
                session__date=today,
                session__start_time__gte=timezone.localtime().time(),
            )
        )
        .select_related("session__service", "session__instructor")
        .order_by("session__date", "session__start_time")
        .first()
    )
    current_occupancy = AttendanceRecord.objects.filter(
        check_out_time__isnull=True
    ).count()
    max_capacity = GymConfiguration.get_capacity()
    if max_capacity:
        occupancy_percent = min(round(current_occupancy / max_capacity * 100), 100)
    else:
        occupancy_percent = 0
    if occupancy_percent < 45:
        occupancy_status = "Quiet"
    elif occupancy_percent < 75:
        occupancy_status = "Moderate"
    else:
        occupancy_status = "Busy"
    active_membership = (
        Membership.objects.filter(
            member=request.user,
            status=Membership.Status.ACTIVE,
            start_date__lte=today,
            end_date__gte=today,
        )
        .select_related("package")
        .first()
    )
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
        exercise_count = (
            workout.exercise_records.values("exercise_id").distinct().count()
        )
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
        weight_time = timezone.make_aware(
            datetime.combine(weight.recorded_date, time.min)
        )
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
    return render(request, "member/dashboard.html", context)


@role_required(User.Role.STAFF)
def staff_dashboard(request):
    context = {
        "member_count": User.objects.filter(
            role=User.Role.MEMBER, is_active=True
        ).count(),
        "active_sidebar": "dashboard",
    }
    return render(request, "staff/dashboard.html", context)


@coach_required
def coach_dashboard(request):
    assignments = CoachAssignment.objects.filter(
        coach=request.user, active=True, member__is_active=True
    ).select_related("member")
    assigned_member_ids = assignments.values_list("member_id", flat=True)
    coach_plan_count = WorkoutPlan.objects.filter(
        coach=request.user, plan_type="COACH_ASSIGNED", is_active=True
    ).count()
    completed_workout_count = WorkoutSession.objects.filter(
        member_id__in=assigned_member_ids, completed_at__isnull=False
    ).count()
    context = {
        "assignments": assignments,
        "assignment_count": assignments.count(),
        "coach_plan_count": coach_plan_count,
        "completed_workout_count": completed_workout_count,
        "active_sidebar": "dashboard",
    }
    return render(request, "coach/dashboard.html", context)


@admin_required
def admin_dashboard(request):
    today = date.today()
    scheduled_sessions = Session.objects.filter(
        date__gte=today, status=Session.Status.SCHEDULED
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
            status=Membership.Status.ACTIVE, start_date__lte=today, end_date__gte=today
        ).count(),
        "today_attendance_count": AttendanceRecord.objects.filter(
            check_in_time__date=today
        ).count(),
        "current_occupancy": AttendanceRecord.objects.filter(
            check_out_time__isnull=True
        ).count(),
        "upcoming_session_count": scheduled_sessions.count(),
        "upcoming_sessions": scheduled_sessions[:5],
        "confirmed_booking_count": Booking.objects.filter(
            status=Booking.Status.CONFIRMED
        ).count(),
        "successful_payment_count": successful_payments.count(),
        "total_revenue": successful_payments.aggregate(total=Sum("amount"))["total"]
        or 0,
        "recent_activity": recent_activity[:6],
        "active_sidebar": "dashboard",
    }
    return render(request, "admin_dashboard/dashboard.html", context)


@login_required
def profile(request):
    member_profile = None
    if request.user.role == User.Role.MEMBER:
        member_profile, _ = MemberProfile.objects.get_or_create(user=request.user)
    return render(
        request,
        "shared/profile.html",
        {"member_profile": member_profile, "active_sidebar": "profile"},
    )


# 2.2–2.3 Update profile and fitness information
@login_required
def profile_edit(request):
    user_form = UserProfileForm(request.POST or None, instance=request.user)
    member_form = None
    if request.user.role == User.Role.MEMBER:
        member_profile, _ = MemberProfile.objects.get_or_create(user=request.user)
        member_form = MemberProfileForm(
            request.POST or None, request.FILES or None, instance=member_profile
        )
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
    return render(request, "shared/profile_edit.html", context)


@login_required
def password_change(request):
    form = StyledPasswordChangeForm(user=request.user, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Your password has been changed.")
        return redirect("accounts:password_change_done")
    return render(request, "authentication/password_change_form.html", {"form": form})


@login_required
def password_change_done(request):
    return render(request, "authentication/password_change_done.html")


# 4.2 Manage accounts
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
    return render(request, "admin_dashboard/user_list.html", context)


@admin_required
def admin_user_create(request):
    form = AdminUserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        new_user = form.save()
        messages.success(request, "User account created successfully.")
        return redirect("accounts:admin_user_detail", user_id=new_user.id)
    return render(
        request,
        "admin_dashboard/user_form.html",
        {"form": form, "active_sidebar": "users"},
    )


@admin_required
def admin_user_detail(request, user_id):
    selected_user = get_object_or_404(User, pk=user_id)
    return render(
        request,
        "admin_dashboard/user_detail.html",
        {"selected_user": selected_user, "active_sidebar": "users"},
    )


# 4.3 Assign roles
@admin_required
def admin_user_role(request, user_id):
    selected_user = get_object_or_404(User, pk=user_id)
    form = AdminRoleForm(request.POST or None, instance=selected_user)
    if request.method == "POST" and form.is_valid():
        if selected_user.is_superuser:
            messages.error(
                request, "The role of a Django superuser cannot be changed here."
            )
        else:
            updated_user = form.save()
            if updated_user.role == User.Role.MEMBER:
                MemberProfile.objects.get_or_create(user=updated_user)
            elif updated_user.role == User.Role.COACH:
                CoachProfile.objects.get_or_create(user=updated_user)
            messages.success(request, "User role updated successfully.")
        return redirect("accounts:admin_user_detail", user_id=selected_user.id)
    return render(
        request,
        "admin_dashboard/user_role_form.html",
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
        "admin_dashboard/user_status_confirm.html",
        {"selected_user": selected_user, "active_sidebar": "users"},
    )


# 4.12 Assign members to coaches
@admin_required
def coach_assignment_list(request):
    assignments = CoachAssignment.objects.select_related("coach", "member")
    return render(
        request,
        "admin_dashboard/coach_assignment_list.html",
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
        "admin_dashboard/coach_assignment_form.html",
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
        "admin_dashboard/coach_assignment_confirm_delete.html",
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
        "staff/member_list.html",
        {"members": members, "query": query, "active_sidebar": "members"},
    )


@staff_required
def staff_member_detail(request, user_id):
    member = get_object_or_404(User, pk=user_id, role=User.Role.MEMBER)
    member_profile, _ = MemberProfile.objects.get_or_create(user=member)
    return render(
        request,
        "staff/member_detail.html",
        {
            "member": member,
            "member_profile": member_profile,
            "active_sidebar": "members",
        },
    )


# Memberships and payments — Noorie


def _active_packages():
    return (
        MembershipPackage.objects.filter(is_active=True)
        .annotate(
            plan_order=Case(
                When(slug="starter", then=Value(1)),
                When(slug="premium", then=Value(2)),
                When(slug="elite", then=Value(3)),
                When(slug="student", then=Value(4)),
                default=Value(99),
                output_field=IntegerField(),
            )
        )
        .order_by("plan_order", "name")
    )


def _current_for(user):
    membership = (
        Membership.objects.filter(member=user, status=Membership.Status.ACTIVE)
        .select_related("package")
        .order_by("-end_date")
        .first()
    )
    if membership and membership.end_date < date.today():
        membership.status = Membership.Status.EXPIRED
        membership.save(update_fields=["status"])
        create_notification(
            recipient=user,
            notification_type=Notification.Type.MEMBERSHIP,
            title="Membership Expired",
            message=f"Your {membership.package.name} membership has expired.",
            link=reverse("memberships:member_packages"),
            reference_key=f"membership-expired-{membership.id}",
        )
        return None
    if membership:
        days_remaining = (membership.end_date - date.today()).days
        if days_remaining <= 7:
            create_notification(
                recipient=user,
                notification_type=Notification.Type.MEMBERSHIP,
                title="Membership Expiry Reminder",
                message=f"Your {membership.package.name} membership expires in {days_remaining} day(s).",
                link=reverse("memberships:current_membership"),
                reference_key=f"membership-reminder-{membership.id}",
            )
    return membership


def _report_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


# 1.2 Compare membership packages
def public_packages(request):
    return render(request, "public/memberships.html", {"packages": _active_packages()})


def public_package_detail(request, slug):
    package = get_object_or_404(MembershipPackage, slug=slug, is_active=True)
    return render(request, "public/membership_detail.html", {"package": package})


def auth_required(request, package_id):
    package = get_object_or_404(MembershipPackage, pk=package_id, is_active=True)
    if request.user.is_authenticated:
        return redirect("memberships:checkout", package_id=package.pk)
    next_url = f"/memberships/member/checkout/{package.pk}/"
    return render(
        request,
        "authentication/membership_login.html",
        {"package": package, "next_url": next_url},
    )


@member_required
def member_packages(request):
    return render(
        request,
        "member/membership_packages.html",
        {
            "packages": _active_packages(),
            "current_membership": _current_for(request.user),
            "active_sidebar": "membership",
            "membership_tab": "plans",
        },
    )


# 2.6 Membership information
@member_required
def current_membership(request):
    membership = _current_for(request.user)
    return render(
        request,
        "member/current_membership.html",
        {
            "membership": membership,
            "active_sidebar": "membership",
            "membership_tab": "current",
        },
    )


@member_required
def membership_history(request):
    memberships = Membership.objects.filter(member=request.user).select_related(
        "package"
    )
    return render(
        request,
        "member/membership_history.html",
        {
            "memberships": memberships,
            "active_sidebar": "membership",
            "membership_tab": "history",
        },
    )


# 2.6 Payment history
@member_required
def payment_history(request):
    payments = Payment.objects.filter(member=request.user).select_related(
        "package", "membership"
    )
    return render(
        request,
        "member/payment_history.html",
        {"payments": payments, "active_sidebar": "payments"},
    )


# 2.4–2.5 Select and pay for membership
@member_required
@transaction.atomic
def checkout(request, package_id):
    package = get_object_or_404(MembershipPackage, pk=package_id, is_active=True)
    form = SimulatedPaymentForm(
        request.POST or None, initial={"payer_name": request.user.get_full_name()}
    )
    renewal_id = request.POST.get("renewal_id") or request.GET.get("renew")
    renewal_membership = None
    if renewal_id:
        renewal_membership = get_object_or_404(
            Membership, pk=renewal_id, member=request.user, package=package
        )
    if request.method == "POST" and form.is_valid():
        failed = form.cleaned_data["simulate_failure"]
        payment = Payment.objects.create(
            member=request.user,
            package=package,
            amount=package.price,
            payment_method=form.cleaned_data["payment_method"],
            status=Payment.Status.FAILED if failed else Payment.Status.SUCCESS,
        )
        if failed:
            messages.error(
                request, "The simulated payment failed. No membership was activated."
            )
            return redirect("memberships:payment_failed", payment_id=payment.pk)
        if renewal_membership:
            extension_date = max(date.today(), renewal_membership.end_date)
            renewal_membership.end_date = extension_date + timedelta(
                days=30 * package.duration_months
            )
            renewal_membership.status = Membership.Status.ACTIVE
            renewal_membership.save(update_fields=["end_date", "status"])
            membership = renewal_membership
        else:
            old_membership = _current_for(request.user)
            if old_membership:
                old_membership.status = Membership.Status.CANCELLED
                old_membership.save(update_fields=["status"])
            start_date = date.today()
            membership = Membership.objects.create(
                member=request.user,
                package=package,
                start_date=start_date,
                end_date=start_date + timedelta(days=30 * package.duration_months),
                status=Membership.Status.ACTIVE,
            )
        payment.membership = membership
        payment.save(update_fields=["membership"])
        messages.success(request, "Payment successful. Your membership is now active.")
        return redirect("memberships:payment_success", payment_id=payment.pk)
    return render(
        request,
        "member/checkout.html",
        {
            "package": package,
            "form": form,
            "renewal_membership": renewal_membership,
            "active_sidebar": "membership",
        },
    )


@member_required
def renew_membership(request, membership_id):
    membership = get_object_or_404(Membership, pk=membership_id, member=request.user)
    if request.method != "POST":
        return redirect("memberships:current_membership")
    checkout_url = reverse("memberships:checkout", args=[membership.package_id])
    return redirect(f"{checkout_url}?renew={membership.pk}")


@member_required
def payment_success(request, payment_id):
    payment = get_object_or_404(
        Payment.objects.select_related("package", "membership"),
        pk=payment_id,
        member=request.user,
        status=Payment.Status.SUCCESS,
    )
    return render(
        request,
        "member/payment_success.html",
        {"payment": payment, "active_sidebar": "membership"},
    )


@member_required
def payment_failed(request, payment_id):
    payment = get_object_or_404(
        Payment.objects.select_related("package"),
        pk=payment_id,
        member=request.user,
        status=Payment.Status.FAILED,
    )
    return render(
        request,
        "member/payment_failed.html",
        {"payment": payment, "active_sidebar": "membership"},
    )


@member_required
def receipt(request, payment_id):
    payment = get_object_or_404(
        Payment.objects.select_related("package", "membership"),
        pk=payment_id,
        member=request.user,
        status=Payment.Status.SUCCESS,
    )
    return render(request, "member/receipt.html", {"payment": payment})


@member_required
def receipt_download(request, payment_id):
    payment = get_object_or_404(
        Payment.objects.select_related("package", "membership", "member"),
        pk=payment_id,
        member=request.user,
        status=Payment.Status.SUCCESS,
    )
    member_name = payment.member.get_full_name() or payment.member.email
    receipt_text = "\n".join(
        [
            "FitSync Payment Receipt",
            f"Receipt Number: {payment.receipt_number}",
            f"Member: {member_name}",
            f"Membership Plan: {payment.package.name}",
            f"Payment Method: {payment.get_payment_method_display()}",
            f"Payment Date: {payment.created_at:%d %b %Y, %H:%M}",
            f"Status: {payment.get_status_display()}",
            f"Total: Rs {payment.amount:.2f}",
            "",
            "This receipt records a simulated FitSync coursework payment.",
        ]
    )
    response = HttpResponse(receipt_text, content_type="text/plain")
    filename = f"receipt-{payment.receipt_number}.txt"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@admin_required
def admin_package_list(request):
    packages = MembershipPackage.objects.all()
    return render(
        request,
        "admin_dashboard/package_list.html",
        {"packages": packages, "active_sidebar": "memberships"},
    )


@admin_required
def admin_package_create(request):
    form = MembershipPackageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Membership package created.")
        return redirect("memberships:admin_package_list")
    return render(
        request,
        "admin_dashboard/package_form.html",
        {"form": form, "page_name": "Create Package", "active_sidebar": "memberships"},
    )


@admin_required
def admin_package_edit(request, package_id):
    package = get_object_or_404(MembershipPackage, pk=package_id)
    form = MembershipPackageForm(request.POST or None, instance=package)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Membership package updated.")
        return redirect("memberships:admin_package_list")
    return render(
        request,
        "admin_dashboard/package_form.html",
        {"form": form, "page_name": "Edit Package", "active_sidebar": "memberships"},
    )


@admin_required
def admin_package_toggle(request, package_id):
    package = get_object_or_404(MembershipPackage, pk=package_id)
    if request.method == "POST":
        package.is_active = not package.is_active
        package.save(update_fields=["is_active"])
        messages.success(request, "Package availability updated.")
    return redirect("memberships:admin_package_list")


@admin_required
def admin_membership_list(request):
    memberships = Membership.objects.select_related("member", "package")
    status = request.GET.get("status", "")
    if status:
        memberships = memberships.filter(status=status)
    query = request.GET.get("q", "").strip()
    if query:
        memberships = memberships.filter(
            Q(member__first_name__icontains=query)
            | Q(member__last_name__icontains=query)
            | Q(member__email__icontains=query)
        )
    return render(
        request,
        "admin_dashboard/membership_list.html",
        {
            "memberships": memberships,
            "status_filter": status,
            "query": query,
            "status_choices": Membership.Status.choices,
            "active_sidebar": "memberships",
        },
    )


@admin_required
def admin_membership_edit(request, membership_id):
    membership = get_object_or_404(
        Membership.objects.select_related("member", "package"), pk=membership_id
    )
    form = MembershipRecordForm(request.POST or None, instance=membership)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Membership record updated.")
        return redirect("memberships:admin_membership_list")
    return render(
        request,
        "admin_dashboard/membership_record_form.html",
        {
            "form": form,
            "page_name": "Edit Membership",
            "record_name": membership.member.get_full_name() or membership.member.email,
            "cancel_url": "memberships:admin_membership_list",
            "active_sidebar": "memberships",
        },
    )


@admin_required
def admin_payment_list(request):
    payments = Payment.objects.select_related("member", "package")
    status = request.GET.get("status", "")
    if status:
        payments = payments.filter(status=status)
    query = request.GET.get("q", "").strip()
    if query:
        payments = payments.filter(
            Q(member__first_name__icontains=query)
            | Q(member__last_name__icontains=query)
            | Q(member__email__icontains=query)
            | Q(receipt_number__icontains=query)
        )
    date_from = request.GET.get("date_from", "")
    if date_from:
        try:
            payments = payments.filter(
                created_at__date__gte=date.fromisoformat(date_from)
            )
        except ValueError:
            date_from = ""
    date_to = request.GET.get("date_to", "")
    if date_to:
        try:
            payments = payments.filter(
                created_at__date__lte=date.fromisoformat(date_to)
            )
        except ValueError:
            date_to = ""
    return render(
        request,
        "admin_dashboard/payment_list.html",
        {
            "payments": payments,
            "status_filter": status,
            "query": query,
            "date_from": date_from,
            "date_to": date_to,
            "status_choices": Payment.Status.choices,
            "active_sidebar": "payments",
        },
    )


@admin_required
def admin_payment_detail(request, payment_id):
    payment = get_object_or_404(
        Payment.objects.select_related("member", "package", "membership"), pk=payment_id
    )
    return render(
        request,
        "admin_dashboard/payment_detail.html",
        {"payment": payment, "active_sidebar": "payments"},
    )


@admin_required
def admin_payment_edit(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id)
    form = PaymentRecordForm(request.POST or None, instance=payment)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Payment record updated.")
        return redirect("memberships:admin_payment_detail", payment_id=payment.pk)
    return render(
        request,
        "admin_dashboard/membership_record_form.html",
        {
            "form": form,
            "page_name": "Edit Payment",
            "record_name": payment.receipt_number,
            "cancel_url": "memberships:admin_payment_detail",
            "cancel_id": payment.pk,
            "active_sidebar": "payments",
        },
    )


@admin_required
def admin_membership_report(request):
    date_from = _report_date(request.GET.get("date_from", ""))
    date_to = _report_date(request.GET.get("date_to", ""))
    memberships = Membership.objects.all()
    payments = Payment.objects.all()
    if date_from:
        memberships = memberships.filter(created_at__date__gte=date_from)
        payments = payments.filter(created_at__date__gte=date_from)
    if date_to:
        memberships = memberships.filter(created_at__date__lte=date_to)
        payments = payments.filter(created_at__date__lte=date_to)
    active_count = memberships.filter(status=Membership.Status.ACTIVE).count()
    expired_count = memberships.filter(status=Membership.Status.EXPIRED).count()
    cancelled_count = memberships.filter(status=Membership.Status.CANCELLED).count()
    successful = payments.filter(status=Payment.Status.SUCCESS)
    package_counts = (
        memberships.values("package__name")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    context = {
        "active_count": active_count,
        "expired_count": expired_count,
        "cancelled_count": cancelled_count,
        "successful_payments": successful.count(),
        "payment_total": successful.aggregate(total=Sum("amount"))["total"] or 0,
        "package_counts": package_counts,
        "date_from": date_from,
        "date_to": date_to,
        "active_sidebar": "reports",
    }
    return render(request, "admin_dashboard/membership_report.html", context)


# Services, sessions and bookings — Mehnaz

# 3.6 Manage scheduled sessions


def session_start(session):
    """Combine the session date and start time into one timezone-aware value."""
    start = datetime.combine(session.date, session.start_time)
    return timezone.make_aware(start, timezone.get_current_timezone())


def session_has_started(session):
    """Check whether the session has already started."""
    return session_start(session) <= timezone.now()


def bookings_valid_date(value):
    """Convert a valid date string into a date object for filtering."""
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def management_layout(user):
    """Select the correct dashboard layout for an administrator or staff member."""
    if user.is_superuser or user.role == User.Role.ADMIN:
        return "layouts/admin_base.html"
    if user.role == User.Role.COACH:
        return "layouts/coach_base.html"
    return "layouts/staff_base.html"


def managed_sessions(user):
    """Coaches may manage only the sessions they teach."""
    sessions = Session.objects.select_related("service", "instructor")
    if user.role == User.Role.COACH and (not user.is_superuser):
        sessions = sessions.filter(instructor=user)
    return sessions


def session_coach(user):
    return user if user.role == User.Role.COACH and (not user.is_superuser) else None


def upcoming_sessions():
    """Return scheduled sessions that have not yet started."""
    now = timezone.localtime()
    return Session.objects.filter(
        service__is_active=True, status=Session.Status.SCHEDULED
    ).filter(Q(date__gt=now.date()) | Q(date=now.date(), start_time__gt=now.time()))


# 1.3 and 2.8 Browse scheduled sessions
def schedule(request):
    """Display future sessions and apply the selected schedule filters."""
    search_query = request.GET.get("search", "").strip()
    selected_type = request.GET.get("type", "").strip()
    selected_status = request.GET.get("status", "").strip()
    selected_date = bookings_valid_date(request.GET.get("date", ""))
    selected_instructor = request.GET.get("instructor", "").strip()
    sessions = (
        upcoming_sessions()
        .select_related("service", "instructor")
        .annotate(
            confirmed_count=Count(
                "bookings", filter=Q(bookings__status=Booking.Status.CONFIRMED)
            )
        )
    )
    if search_query:
        sessions = sessions.filter(
            Q(service__name__icontains=search_query)
            | Q(service__description__icontains=search_query)
            | Q(instructor__first_name__icontains=search_query)
            | Q(instructor__last_name__icontains=search_query)
        )
    if selected_type:
        sessions = sessions.filter(service__service_type=selected_type)
    if selected_date:
        sessions = sessions.filter(date=selected_date)
    if selected_instructor.isdigit():
        sessions = sessions.filter(instructor_id=selected_instructor)
    if selected_status == "AVAILABLE":
        sessions = sessions.filter(confirmed_count__lt=F("capacity"))
    elif selected_status == "FULL":
        sessions = sessions.filter(confirmed_count__gte=F("capacity"))
    booked_session_ids = []
    if request.user.is_authenticated:
        booked_session_ids = list(
            Booking.objects.filter(
                member=request.user, status=Booking.Status.CONFIRMED
            ).values_list("session_id", flat=True)
        )
    context = {
        "sessions": sessions,
        "service_types": Service.Type.choices,
        "instructors": User.objects.filter(role=User.Role.COACH, is_active=True),
        "search_query": search_query,
        "selected_type": selected_type,
        "selected_status": selected_status,
        "selected_date": request.GET.get("date", ""),
        "selected_instructor": selected_instructor,
        "booked_session_ids": booked_session_ids,
    }
    return render(request, "public/schedule.html", context)


def session_detail(request, session_id):
    """Display the details and current availability of one session."""
    session = get_object_or_404(
        Session.objects.select_related("service", "instructor"), pk=session_id
    )
    confirmed_count = session.bookings.filter(status=Booking.Status.CONFIRMED).count()
    already_booked = False
    if request.user.is_authenticated:
        already_booked = session.bookings.filter(
            member=request.user, status=Booking.Status.CONFIRMED
        ).exists()
    return render(
        request,
        "public/session_detail.html",
        {
            "session": session,
            "confirmed_count": confirmed_count,
            "remaining_spaces": max(session.capacity - confirmed_count, 0),
            "already_booked": already_booked,
            "has_started": session_has_started(session),
        },
    )


# 2.9–2.10 Validate and confirm booking
@login_required
@require_POST
def book_session(request, session_id):
    """Validate the member and create a confirmed session booking."""
    if request.user.role != User.Role.MEMBER:
        messages.error(request, "Only member accounts can book a session.")
        return redirect("bookings:schedule")
    today = timezone.localdate()
    active_membership = (
        Membership.objects.select_related("package")
        .filter(
            member=request.user,
            status=Membership.Status.ACTIVE,
            start_date__lte=today,
            end_date__gte=today,
        )
        .order_by("-end_date")
        .first()
    )
    if not active_membership:
        messages.error(request, "You need an active membership to book a session.")
        return redirect("bookings:schedule")
    with transaction.atomic():
        session = get_object_or_404(
            Session.objects.select_for_update().select_related("service"), pk=session_id
        )
        if not active_membership.package.allows_service(session.service.service_type):
            messages.error(
                request, "Your membership plan does not include this service."
            )
            return redirect("bookings:schedule")
        if session.status != Session.Status.SCHEDULED:
            messages.error(request, "This session is no longer available for booking.")
            return redirect("bookings:schedule")
        if session_has_started(session):
            messages.error(
                request, "You cannot book a session that has already started."
            )
            return redirect("bookings:schedule")
        if Booking.objects.filter(
            member=request.user, session=session, status=Booking.Status.CONFIRMED
        ).exists():
            messages.warning(request, "You have already booked this session.")
            return redirect("bookings:schedule")
        if Booking.objects.filter(
            member=request.user,
            status=Booking.Status.CONFIRMED,
            session__status=Session.Status.SCHEDULED,
            session__date=session.date,
            session__start_time__lt=session.end_time,
            session__end_time__gt=session.start_time,
        ).exists():
            messages.error(request, "You already have another booking at this time.")
            return redirect("bookings:schedule")
        confirmed_count = Booking.objects.filter(
            session=session, status=Booking.Status.CONFIRMED
        ).count()
        if confirmed_count >= session.capacity:
            messages.error(request, "Sorry, this session is now full.")
            return redirect("bookings:schedule")
        booking = Booking.objects.create(
            member=request.user, session=session, status=Booking.Status.CONFIRMED
        )
        create_notification(
            recipient=request.user,
            notification_type=Notification.Type.BOOKING,
            title="Booking Confirmed",
            message=f"Your booking for {session.service.name} on {session.date:%d %B %Y} is confirmed.",
            link=reverse("bookings:booking_detail", args=[booking.id]),
            reference_key=f"booking-confirmed-{booking.id}",
        )
    messages.success(
        request, f"Your booking for {session.service.name} was successful."
    )
    return redirect("bookings:schedule")


# 2.11 Upcoming and past bookings
@login_required
def my_bookings(request):
    """Group the member's bookings into upcoming, previous and cancelled sections."""
    if request.user.role != User.Role.MEMBER:
        messages.error(request, "Only member accounts can view personal bookings.")
        return redirect("bookings:schedule")
    bookings = Booking.objects.filter(member=request.user).select_related(
        "session", "session__service", "session__instructor"
    )
    upcoming = []
    previous = []
    cancelled = []
    for booking in bookings.order_by("session__date", "session__start_time"):
        if booking.status == Booking.Status.CANCELLED:
            cancelled.append(booking)
        elif session_has_started(booking.session):
            previous.append(booking)
        else:
            upcoming.append(booking)
    return render(
        request,
        "member/bookings.html",
        {
            "upcoming_bookings": upcoming,
            "previous_bookings": list(reversed(previous)),
            "cancelled_bookings": list(reversed(cancelled)),
        },
    )


@login_required
def booking_detail(request, booking_id):
    """Display the details of one booking belonging to the logged-in member."""
    booking = get_object_or_404(
        Booking.objects.select_related(
            "session", "session__service", "session__instructor"
        ),
        pk=booking_id,
        member=request.user,
    )
    can_cancel = booking.status == Booking.Status.CONFIRMED and (
        not session_has_started(booking.session)
    )
    return render(
        request,
        "shared/booking_detail.html",
        {"booking": booking, "can_cancel": can_cancel},
    )


# 2.12 Cancel booking
@login_required
def cancel_booking(request, booking_id):
    """Cancel the member's booking only if its session has not started."""
    booking = get_object_or_404(
        Booking.objects.select_related("session", "session__service"),
        pk=booking_id,
        member=request.user,
    )
    if booking.status != Booking.Status.CONFIRMED:
        messages.warning(request, "This booking is no longer active.")
        return redirect("bookings:my_bookings")
    if session_has_started(booking.session):
        messages.error(
            request, "A booking cannot be cancelled after the session has started."
        )
        return redirect("bookings:my_bookings")
    if request.method == "POST":
        booking.status = Booking.Status.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.save(update_fields=["status", "cancelled_at"])
        create_notification(
            recipient=request.user,
            notification_type=Notification.Type.BOOKING,
            title="Booking Cancelled",
            message=f"Your booking for {booking.session.service.name} on {booking.session.date:%d %B %Y} was cancelled.",
            link=reverse("bookings:my_bookings"),
            reference_key=f"booking-cancelled-{booking.id}",
        )
        messages.success(
            request, f"Your booking for {booking.session.service.name} was cancelled."
        )
        return redirect("bookings:my_bookings")
    return render(request, "shared/booking_confirm_cancel.html", {"booking": booking})


@staff_required
def service_list(request):
    """Display all services for staff and administrator management."""
    services = Service.objects.all()
    query = request.GET.get("q", "").strip()
    if query:
        services = services.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )
    return render(
        request,
        "admin_dashboard/service_list.html",
        {
            "services": services,
            "query": query,
            "layout_template": management_layout(request.user),
            "active_sidebar": "sessions",
        },
    )


@staff_required
def service_create(request):
    """Allow staff or administrators to create a bookable service."""
    form = ServiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Service created successfully.")
        return redirect("bookings:service_list")
    return render(
        request,
        "shared/session_service_form.html",
        {
            "form": form,
            "title": "Add Service",
            "layout_template": management_layout(request.user),
            "active_sidebar": "sessions",
        },
    )


@staff_required
def service_edit(request, service_id):
    """Allow staff or administrators to update an existing service."""
    service = get_object_or_404(Service, pk=service_id)
    form = ServiceForm(request.POST or None, instance=service)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Service updated successfully.")
        return redirect("bookings:service_list")
    return render(
        request,
        "shared/session_service_form.html",
        {
            "form": form,
            "title": "Edit Service",
            "layout_template": management_layout(request.user),
            "active_sidebar": "sessions",
        },
    )


@staff_required
def service_delete(request, service_id):
    """Allow staff or administrators to delete a service safely."""
    service = get_object_or_404(Service, pk=service_id)
    if request.method == "POST":
        if service.sessions.exists():
            service.is_active = False
            service.save(update_fields=["is_active"])
            messages.success(
                request, "Service deactivated because it has session records."
            )
        else:
            service.delete()
            messages.success(request, "Service deleted successfully.")
        return redirect("bookings:service_list")
    return render(
        request,
        "admin_dashboard/service_confirm_delete.html",
        {
            "service": service,
            "layout_template": management_layout(request.user),
            "active_sidebar": "sessions",
        },
    )


@role_required(User.Role.STAFF, User.Role.ADMIN, User.Role.COACH)
def session_list(request):
    """Display sessions for staff and administrator management."""
    sessions = managed_sessions(request.user).annotate(
        booking_total=Count(
            "bookings", filter=Q(bookings__status=Booking.Status.CONFIRMED)
        )
    )
    status = request.GET.get("status", "")
    selected_date = bookings_valid_date(request.GET.get("date", ""))
    if status:
        sessions = sessions.filter(status=status)
    if selected_date:
        sessions = sessions.filter(date=selected_date)
    return render(
        request,
        "shared/session_list.html",
        {
            "sessions": sessions,
            "status_choices": Session.Status.choices,
            "selected_status": status,
            "selected_date": request.GET.get("date", ""),
            "layout_template": management_layout(request.user),
            "active_sidebar": "sessions",
        },
    )


# 3.6 Create a teaching session
@role_required(User.Role.STAFF, User.Role.ADMIN, User.Role.COACH)
def session_create(request):
    """Allow staff or administrators to schedule a new session."""
    form = SessionForm(request.POST or None, coach=session_coach(request.user))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Session created successfully.")
        return redirect("bookings:session_list")
    return render(
        request,
        "shared/session_service_form.html",
        {
            "form": form,
            "title": "Add Session",
            "layout_template": management_layout(request.user),
            "active_sidebar": "sessions",
        },
    )


@role_required(User.Role.STAFF, User.Role.ADMIN, User.Role.COACH)
def session_edit(request, session_id):
    """Allow staff or administrators to update a scheduled session."""
    session = get_object_or_404(managed_sessions(request.user), pk=session_id)
    form = SessionForm(
        request.POST or None, instance=session, coach=session_coach(request.user)
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Session updated successfully.")
        return redirect("bookings:session_list")
    return render(
        request,
        "shared/session_service_form.html",
        {
            "form": form,
            "title": "Edit Session",
            "layout_template": management_layout(request.user),
            "active_sidebar": "sessions",
        },
    )


@role_required(User.Role.STAFF, User.Role.ADMIN, User.Role.COACH)
def session_cancel(request, session_id):
    """Cancel a session and its confirmed member bookings."""
    session = get_object_or_404(managed_sessions(request.user), pk=session_id)
    if request.method == "POST":
        affected_members = list(
            session.bookings.filter(status=Booking.Status.CONFIRMED).select_related(
                "member"
            )
        )
        session.status = Session.Status.CANCELLED
        session.save(update_fields=["status"])
        session.bookings.filter(status=Booking.Status.CONFIRMED).update(
            status=Booking.Status.CANCELLED, cancelled_at=timezone.now()
        )
        for booking in affected_members:
            create_notification(
                recipient=booking.member,
                notification_type=Notification.Type.BOOKING,
                title="Session Cancelled",
                message=f"The {session.service.name} session on {session.date:%d %B %Y} was cancelled.",
                link=reverse("bookings:my_bookings"),
                reference_key=f"session-cancelled-{session.id}",
            )
        messages.success(request, "Session and its active bookings were cancelled.")
        return redirect("bookings:session_list")
    return render(
        request,
        "shared/session_confirm_cancel.html",
        {
            "session": session,
            "layout_template": management_layout(request.user),
            "active_sidebar": "sessions",
        },
    )


# 3.7 Session attendees
@role_required(User.Role.STAFF, User.Role.ADMIN, User.Role.COACH)
def session_roster(request, session_id):
    """Display the members with confirmed bookings for a session."""
    session = get_object_or_404(managed_sessions(request.user), pk=session_id)
    bookings = session.bookings.filter(status=Booking.Status.CONFIRMED).select_related(
        "member"
    )
    return render(
        request,
        "shared/session_roster.html",
        {
            "session": session,
            "bookings": bookings,
            "layout_template": management_layout(request.user),
            "active_sidebar": "sessions",
        },
    )


@staff_required
def booking_report(request):
    """Generate filtered booking statistics and service popularity summaries."""
    bookings = Booking.objects.select_related("member", "session", "session__service")
    date_from = bookings_valid_date(request.GET.get("date_from", ""))
    date_to = bookings_valid_date(request.GET.get("date_to", ""))
    status = request.GET.get("status", "")
    if date_from:
        bookings = bookings.filter(session__date__gte=date_from)
    if date_to:
        bookings = bookings.filter(session__date__lte=date_to)
    if status:
        bookings = bookings.filter(status=status)
    popular_services = (
        bookings.values("session__service__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )
    daily_totals = (
        bookings.annotate(day=TruncDate("booked_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("-day")
    )
    context = {
        "bookings": bookings.order_by("-session__date", "-session__start_time"),
        "total_bookings": bookings.count(),
        "confirmed_total": bookings.filter(status=Booking.Status.CONFIRMED).count(),
        "cancelled_total": bookings.filter(status=Booking.Status.CANCELLED).count(),
        "popular_services": popular_services,
        "daily_totals": daily_totals,
        "status_choices": Booking.Status.choices,
        "selected_status": status,
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
        "layout_template": management_layout(request.user),
        "active_sidebar": "bookings",
    }
    return render(request, "shared/booking_report.html", context)


# Workouts, progress and water intake — Hanshinee

# 2.14 Personal workout plans; 2.18 Progress; 2.22 Workout recording; 2.23 History; 2.25 Water intake; 4.11 Exercise library


def is_member(user):
    return user.is_authenticated and user.role == "MEMBER"


# 2.25 Daily water total
@login_required
def water_intake(request):
    if not is_member(request.user):
        return HttpResponseForbidden("This page is for members.")
    today = timezone.localdate()
    records = WaterIntake.objects.filter(member=request.user)
    today_record = records.filter(recorded_date=today).first()
    form = WaterIntakeForm(
        request.POST or None,
        initial={
            "recorded_date": today,
            "litres": today_record.litres if today_record else 0,
        },
    )
    if request.method == "POST" and form.is_valid():
        WaterIntake.objects.update_or_create(
            member=request.user,
            recorded_date=form.cleaned_data["recorded_date"],
            defaults={"litres": form.cleaned_data["litres"]},
        )
        messages.success(request, "Your water intake has been saved.")
        return redirect("workouts:water_intake")
    return render(
        request,
        "member/water_intake.html",
        {
            "form": form,
            "records": records[:30],
            "today_litres": today_record.litres if today_record else 0,
            "active_sidebar": "water",
        },
    )


def is_coach(user):
    return user.is_authenticated and user.role == "COACH"


def can_manage_exercises(user):
    return user.is_authenticated and (
        user.is_superuser or user.role in ["STAFF", "ADMIN"]
    )


def coach_is_assigned(coach, member):
    return CoachAssignment.objects.filter(
        coach=coach, member=member, active=True
    ).exists()


def can_view_plan(user, plan):
    if user == plan.member:
        return True
    if is_coach(user) and plan.coach == user and coach_is_assigned(user, plan.member):
        return True
    return False


def can_edit_plan(user, plan):
    if plan.plan_type == "PERSONAL":
        return user == plan.member
    return (
        is_coach(user) and plan.coach == user and coach_is_assigned(user, plan.member)
    )


def positive_int(value, default=0):
    try:
        number = int(value)
        return max(number, 0)
    except (TypeError, ValueError):
        return default


def decimal_or_none(value):
    if value in [None, ""]:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None


@login_required
def workout_plans(request):
    if not is_member(request.user):
        return HttpResponseForbidden("This page is for members.")
    personal_plans = WorkoutPlan.objects.filter(
        member=request.user, plan_type="PERSONAL", is_active=True
    )
    coach_plans = WorkoutPlan.objects.filter(
        member=request.user, plan_type="COACH_ASSIGNED", is_active=True
    )
    return render(
        request,
        "member/workout_plans.html",
        {
            "personal_plans": personal_plans,
            "coach_plans": coach_plans,
            "active_sidebar": "plans",
        },
    )


# 2.14 and 4.11 Shared exercise library
@login_required
def exercise_library(request):
    exercises = Exercise.objects.filter(is_active=True)
    search = request.GET.get("search", "").strip()
    muscle = request.GET.get("muscle", "")
    equipment = request.GET.get("equipment", "")
    plan_id = request.GET.get("plan")
    if search:
        exercises = exercises.filter(
            Q(name__icontains=search)
            | Q(category__icontains=search)
            | Q(secondary_muscles__icontains=search)
        )
    if muscle:
        exercises = exercises.filter(category=muscle)
    if equipment:
        exercises = exercises.filter(equipment=equipment)
    plan = None
    if plan_id:
        plan = get_object_or_404(WorkoutPlan, id=plan_id)
        if not can_edit_plan(request.user, plan):
            return HttpResponseForbidden("You cannot edit this workout plan.")
    return render(
        request,
        "shared/exercise_library.html",
        {
            "exercises": exercises,
            "search": search,
            "selected_muscle": muscle,
            "selected_equipment": equipment,
            "muscle_choices": Exercise.MUSCLE_CHOICES,
            "equipment_choices": Exercise.EQUIPMENT_CHOICES,
            "plan": plan,
            "active_sidebar": "plans",
            "layout_template": (
                "layouts/coach_base.html"
                if is_coach(request.user)
                else "layouts/member_base.html"
            ),
        },
    )


@login_required
def exercise_detail(request, exercise_id):
    exercise = get_object_or_404(Exercise, id=exercise_id, is_active=True)
    return render(
        request,
        "shared/exercise_detail.html",
        {
            "exercise": exercise,
            "active_sidebar": "plans",
            "layout_template": (
                "layouts/coach_base.html"
                if is_coach(request.user)
                else "layouts/member_base.html"
            ),
        },
    )


# 4.11 Manage exercise library
@login_required
def exercise_manage(request):
    if not can_manage_exercises(request.user):
        return HttpResponseForbidden("You do not have permission to manage exercises.")
    exercises = Exercise.objects.all()
    search = request.GET.get("search", "").strip()
    if search:
        exercises = exercises.filter(
            Q(name__icontains=search) | Q(category__icontains=search)
        )
    layout_template = (
        "layouts/admin_base.html"
        if request.user.is_superuser or request.user.role == "ADMIN"
        else "layouts/staff_base.html"
    )
    return render(
        request,
        "admin_dashboard/exercise_list.html",
        {
            "exercises": exercises,
            "search": search,
            "layout_template": layout_template,
            "active_sidebar": "exercises",
        },
    )


@login_required
def exercise_create(request):
    if not can_manage_exercises(request.user):
        return HttpResponseForbidden("You do not have permission to manage exercises.")
    form = ExerciseForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Exercise added successfully.")
        return redirect("workouts:exercise_manage")
    return render(
        request,
        "admin_dashboard/exercise_form.html",
        {"form": form, "title": "Add Exercise"},
    )


@login_required
def exercise_edit(request, exercise_id):
    if not can_manage_exercises(request.user):
        return HttpResponseForbidden("You do not have permission to manage exercises.")
    exercise = get_object_or_404(Exercise, id=exercise_id)
    form = ExerciseForm(request.POST or None, request.FILES or None, instance=exercise)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Exercise updated successfully.")
        return redirect("workouts:exercise_manage")
    return render(
        request,
        "admin_dashboard/exercise_form.html",
        {"form": form, "title": "Edit Exercise"},
    )


@login_required
def exercise_toggle(request, exercise_id):
    if request.method != "POST" or not can_manage_exercises(request.user):
        return HttpResponseForbidden("You do not have permission to manage exercises.")
    exercise = get_object_or_404(Exercise, id=exercise_id)
    exercise.is_active = not exercise.is_active
    exercise.save(update_fields=["is_active"])
    messages.success(request, "Exercise status updated.")
    return redirect("workouts:exercise_manage")


# 2.14 Create a personal plan
@login_required
def plan_create(request):
    if not is_member(request.user):
        return HttpResponseForbidden("Only members can create personal workout plans.")
    exercises = Exercise.objects.filter(is_active=True).order_by("category", "name")
    form = WorkoutPlanForm(request.POST or None)
    if request.method == "POST":
        selected_ids = request.POST.getlist("exercise_ids")
        if form.is_valid() and selected_ids:
            plan = form.save(commit=False)
            plan.member = request.user
            plan.plan_type = "PERSONAL"
            plan.save()
            selected_exercises = Exercise.objects.filter(
                id__in=selected_ids, is_active=True
            )
            for order, exercise in enumerate(selected_exercises, start=1):
                WorkoutPlanExercise.objects.create(
                    workout_plan=plan, exercise=exercise, sets=3, reps=10, order=order
                )
            messages.success(
                request,
                "Workout plan created. You can now adjust sets, reps, weight and duration.",
            )
            return redirect("workouts:plan_detail", plan_id=plan.id)
        if not selected_ids:
            messages.error(
                request, "Choose at least one exercise from the Exercise Library."
            )
    return render(
        request,
        "shared/plan_builder.html",
        {
            "form": form,
            "exercises": exercises,
            "muscle_choices": Exercise.MUSCLE_CHOICES,
            "equipment_choices": Exercise.EQUIPMENT_CHOICES,
            "active_sidebar": "plans",
        },
    )


@login_required
def plan_detail(request, plan_id):
    plan = get_object_or_404(WorkoutPlan, id=plan_id)
    if not can_view_plan(request.user, plan):
        return HttpResponseForbidden("You cannot view this workout plan.")
    entries = plan.plan_exercises.select_related("exercise")
    if request.method == "POST" and can_edit_plan(request.user, plan):
        for entry in entries:
            entry.sets = (
                positive_int(request.POST.get(f"sets_{entry.id}"), entry.sets) or 1
            )
            entry.reps = (
                positive_int(request.POST.get(f"reps_{entry.id}"), entry.reps) or 1
            )
            entry.weight_kg = decimal_or_none(request.POST.get(f"weight_{entry.id}"))
            duration = positive_int(request.POST.get(f"duration_{entry.id}"), 0)
            entry.duration_minutes = duration or None
            entry.day_number = (
                positive_int(request.POST.get(f"day_{entry.id}"), entry.day_number) or 1
            )
            entry.order = (
                positive_int(request.POST.get(f"order_{entry.id}"), entry.order) or 1
            )
            entry.save()
        messages.success(request, "Exercise targets updated.")
        return redirect("workouts:plan_detail", plan_id=plan.id)
    return render(
        request,
        "shared/plan_detail.html",
        {
            "plan": plan,
            "entries": entries,
            "can_edit": can_edit_plan(request.user, plan),
            "active_sidebar": "plans",
            "layout_template": (
                "layouts/coach_base.html"
                if is_coach(request.user)
                else "layouts/member_base.html"
            ),
        },
    )


# 2.15 Edit a personal plan
@login_required
def plan_edit(request, plan_id):
    plan = get_object_or_404(WorkoutPlan, id=plan_id)
    if not can_edit_plan(request.user, plan):
        messages.error(request, "You cannot edit this workout plan.")
        return redirect("workouts:plan_detail", plan_id=plan.id)
    form = WorkoutPlanForm(request.POST or None, instance=plan)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Workout plan updated.")
        return redirect("workouts:plan_detail", plan_id=plan.id)
    return render(
        request,
        "shared/plan_form.html",
        {
            "form": form,
            "title": "Edit Workout Plan",
            "plan": plan,
            "active_sidebar": "plans",
            "layout_template": (
                "layouts/coach_base.html"
                if is_coach(request.user)
                else "layouts/member_base.html"
            ),
        },
    )


# 2.15 Delete a personal plan
@login_required
def plan_delete(request, plan_id):
    plan = get_object_or_404(WorkoutPlan, id=plan_id)
    if not can_edit_plan(request.user, plan):
        return HttpResponseForbidden("You cannot delete this workout plan.")
    if request.method == "POST":
        plan.delete()
        messages.success(request, "Workout plan deleted.")
        if is_coach(request.user):
            return redirect("workouts:coach_plans")
        return redirect("workouts:plans")
    return render(
        request,
        "shared/plan_confirm_delete.html",
        {
            "plan": plan,
            "active_sidebar": "plans",
            "layout_template": (
                "layouts/coach_base.html"
                if is_coach(request.user)
                else "layouts/member_base.html"
            ),
        },
    )


@login_required
def plan_add_exercises(request, plan_id):
    plan = get_object_or_404(WorkoutPlan, id=plan_id)
    if not can_edit_plan(request.user, plan):
        return HttpResponseForbidden("You cannot edit this workout plan.")
    if request.method == "POST":
        selected_ids = request.POST.getlist("exercise_ids")
        if not selected_ids:
            messages.error(request, "Select at least one exercise.")
            return redirect("workouts:plan_add_exercises", plan_id=plan.id)
        existing_ids = set(plan.plan_exercises.values_list("exercise_id", flat=True))
        next_order = plan.plan_exercises.count() + 1
        added = 0
        for exercise in Exercise.objects.filter(id__in=selected_ids, is_active=True):
            if exercise.id in existing_ids:
                continue
            WorkoutPlanExercise.objects.create(
                workout_plan=plan, exercise=exercise, sets=3, reps=10, order=next_order
            )
            next_order += 1
            added += 1
        messages.success(request, f"{added} exercise(s) added to the plan.")
        return redirect("workouts:plan_detail", plan_id=plan.id)
    exercises = Exercise.objects.filter(is_active=True)
    search = request.GET.get("search", "").strip()
    muscle = request.GET.get("muscle", "")
    equipment = request.GET.get("equipment", "")
    if search:
        exercises = exercises.filter(
            Q(name__icontains=search)
            | Q(category__icontains=search)
            | Q(secondary_muscles__icontains=search)
        )
    if muscle:
        exercises = exercises.filter(category=muscle)
    if equipment:
        exercises = exercises.filter(equipment=equipment)
    existing_ids = list(plan.plan_exercises.values_list("exercise_id", flat=True))
    return render(
        request,
        "shared/plan_add_exercises.html",
        {
            "plan": plan,
            "exercises": exercises,
            "existing_ids": existing_ids,
            "search": search,
            "selected_muscle": muscle,
            "selected_equipment": equipment,
            "muscle_choices": Exercise.MUSCLE_CHOICES,
            "equipment_choices": Exercise.EQUIPMENT_CHOICES,
            "active_sidebar": "plans",
            "layout_template": (
                "layouts/coach_base.html"
                if is_coach(request.user)
                else "layouts/member_base.html"
            ),
        },
    )


@login_required
def plan_remove_exercise(request, plan_id, entry_id):
    plan = get_object_or_404(WorkoutPlan, id=plan_id)
    if request.method != "POST" or not can_edit_plan(request.user, plan):
        return HttpResponseForbidden("You cannot edit this workout plan.")
    entry = get_object_or_404(WorkoutPlanExercise, id=entry_id, workout_plan=plan)
    entry.delete()
    messages.success(request, "Exercise removed from the plan.")
    return redirect("workouts:plan_detail", plan_id=plan.id)


# 2.22 Start workout timing
@login_required
def start_workout(request, plan_id):
    plan = get_object_or_404(
        WorkoutPlan, id=plan_id, member=request.user, is_active=True
    )
    if not is_member(request.user):
        return HttpResponseForbidden("Only members can start workouts.")
    if not plan.plan_exercises.exists():
        messages.error(
            request, "Add at least one exercise before starting this workout."
        )
        return redirect("workouts:plan_detail", plan_id=plan.id)
    session = WorkoutSession.objects.create(member=request.user, workout_plan=plan)
    return redirect("workouts:active_workout", session_id=session.id)


def workout_set_entries(session, data=None):
    if not session.workout_plan:
        return []
    entries = list(session.workout_plan.plan_exercises.select_related("exercise"))
    for entry in entries:
        selected = (
            data.getlist(f"completed_sets_{entry.id}") if data is not None else []
        )
        entry.set_rows = []
        for number in range(1, entry.sets + 1):
            form = WorkoutSetForm(
                data,
                prefix=f"set_{entry.id}_{number}",
                initial={"reps": entry.reps, "weight_kg": entry.weight_kg},
            )
            entry.set_rows.append(
                {"number": number, "form": form, "completed": str(number) in selected}
            )
    return entries


@login_required
def active_workout(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, member=request.user)
    if session.completed_at:
        return redirect("workouts:history_detail", session_id=session.id)
    entries = workout_set_entries(session)
    return render(
        request,
        "member/active_workout.html",
        {"session": session, "entries": entries, "active_sidebar": "plans"},
    )


# 2.22 Save completed sets and automatic elapsed duration
@login_required
@transaction.atomic
def finish_workout(request, session_id):
    session = get_object_or_404(
        WorkoutSession.objects.select_for_update(), id=session_id, member=request.user
    )
    if request.method != "POST":
        return redirect("workouts:active_workout", session_id=session.id)
    if session.completed_at:
        return redirect("workouts:history_detail", session_id=session.id)
    entries = workout_set_entries(session, request.POST)
    completed_sets = []
    valid = True
    for entry in entries:
        for row in entry.set_rows:
            if row["completed"]:
                completed_sets.append((entry, row))
                if not row["form"].is_valid():
                    valid = False
    if not completed_sets:
        messages.error(
            request, "Mark at least one set complete before finishing the workout."
        )
    elif not valid:
        messages.error(request, "Check the reps and weight for your completed sets.")
    if not completed_sets or not valid:
        return render(
            request,
            "member/active_workout.html",
            {
                "session": session,
                "entries": entries,
                "active_sidebar": "plans",
                "notes": request.POST.get("notes", ""),
            },
        )
    for entry, row in completed_sets:
        WorkoutExerciseRecord.objects.create(
            workout_session=session,
            exercise=entry.exercise,
            set_number=row["number"],
            sets=1,
            reps=row["form"].cleaned_data["reps"],
            weight_kg=row["form"].cleaned_data["weight_kg"],
        )
    session.completed_at = timezone.now()
    # 2.22 Elapsed time includes rests; posted duration values are ignored.
    elapsed_seconds = max(
        0, (session.completed_at - session.started_at).total_seconds()
    )
    session.duration_minutes = round(elapsed_seconds / 60)
    session.notes = request.POST.get("notes", "").strip()
    session.save()
    messages.success(request, "Workout completed. Great work!")
    return redirect("workouts:history_detail", session_id=session.id)


# 2.23 Review completed workouts
@login_required
def workout_history(request):
    if not is_member(request.user):
        return HttpResponseForbidden("This page is for members.")
    sessions = (
        WorkoutSession.objects.filter(member=request.user, completed_at__isnull=False)
        .select_related("workout_plan")
        .annotate(exercise_count=Count("exercise_records__exercise", distinct=True))
    )
    return render(
        request,
        "member/workout_history.html",
        {"sessions": sessions, "active_sidebar": "history"},
    )


@login_required
def workout_history_detail(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id)
    if request.user != session.member:
        if not (
            is_coach(request.user) and coach_is_assigned(request.user, session.member)
        ):
            return HttpResponseForbidden("You cannot view this workout history.")
    records = session.exercise_records.select_related("exercise").order_by(
        "exercise_id", "set_number", "id"
    )
    return render(
        request,
        "member/workout_history_detail.html",
        {
            "session": session,
            "records": records,
            "active_sidebar": "progress" if is_coach(request.user) else "history",
            "layout_template": (
                "layouts/coach_base.html"
                if is_coach(request.user)
                else "layouts/member_base.html"
            ),
        },
    )


# 2.18 View recorded fitness progress
@login_required
def progress(request):
    if not is_member(request.user):
        return HttpResponseForbidden("This page is for members.")
    today = timezone.localdate()
    period = request.GET.get("period", "weekly")
    if period not in ["weekly", "monthly", "all"]:
        period = "weekly"
    start_date = None
    if period == "weekly":
        start_date = today - timedelta(days=6)
    elif period == "monthly":
        start_date = today - timedelta(days=29)
    all_records = WeightRecord.objects.filter(
        member=request.user, recorded_date__lte=today
    )
    records = all_records
    sessions = WorkoutSession.objects.filter(
        member=request.user, completed_at__isnull=False, completed_at__date__lte=today
    ).select_related("workout_plan")
    if start_date:
        records = records.filter(recorded_date__gte=start_date)
        sessions = sessions.filter(completed_at__date__gte=start_date)
    profile = getattr(request.user, "member_profile", None)
    target_weight = profile.target_weight_kg if profile else None
    latest = all_records.first()
    first = all_records.order_by("recorded_date", "id").first()
    current_weight = (
        latest.weight_kg if latest else profile.current_weight_kg if profile else None
    )
    initial_weight = first.weight_kg if first else current_weight
    goal_percent = 0
    remaining_weight = None
    if current_weight is not None and target_weight is not None:
        if initial_weight >= target_weight:
            remaining_weight = max(0, current_weight - target_weight)
        else:
            remaining_weight = max(0, target_weight - current_weight)
        goal_distance = initial_weight - target_weight
        if goal_distance:
            goal_percent = max(
                0,
                min(
                    100,
                    round(
                        float((initial_weight - current_weight) / goal_distance) * 100
                    ),
                ),
            )
        elif current_weight == target_weight:
            goal_percent = 100
    chart_records = list(records.order_by("recorded_date", "id"))
    weight_change = None
    if len(chart_records) >= 2:
        weight_change = chart_records[-1].weight_kg - chart_records[0].weight_kg
    session_list = list(sessions)
    durations = [
        item.duration_minutes
        for item in session_list
        if item.duration_minutes is not None
    ]
    average_minutes = round(sum(durations) / len(durations)) if durations else None
    estimated_calories = sum(durations) * 7 if durations else None
    breakdown_counts = {"Strength": 0, "Cardio": 0, "HIIT": 0, "Other": 0}
    for item in session_list:
        description = (
            f"{item.workout_plan.goal} {item.workout_plan.name}".lower()
            if item.workout_plan
            else ""
        )
        if "hiit" in description:
            category = "HIIT"
        elif "cardio" in description or "endurance" in description:
            category = "Cardio"
        elif "strength" in description or "muscle" in description:
            category = "Strength"
        else:
            category = "Other"
        breakdown_counts[category] += 1
    breakdown = [
        {
            "name": name,
            "count": count,
            "percent": round(count / len(session_list) * 100) if session_list else 0,
            "colour": colour,
        }
        for (name, count), colour in zip(
            breakdown_counts.items(), ["teal", "blue", "amber", "purple"]
        )
    ]
    personal_records = []
    seen_exercises = set()
    exercise_records = (
        WorkoutExerciseRecord.objects.filter(
            workout_session__in=sessions, weight_kg__isnull=False
        )
        .select_related("exercise", "workout_session")
        .order_by("-weight_kg", "-workout_session__completed_at")
    )
    for record in exercise_records:
        if record.exercise_id not in seen_exercises:
            personal_records.append(record)
            seen_exercises.add(record.exercise_id)
        if len(personal_records) == 4:
            break
    calorie_days = []
    recent_sessions = WorkoutSession.objects.filter(
        member=request.user,
        completed_at__date__gte=today - timedelta(days=6),
        completed_at__date__lte=today,
    )
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        minutes = sum(
            (
                item.duration_minutes or 0
                for item in recent_sessions
                if timezone.localdate(item.completed_at) == day
            )
        )
        calorie_days.append({"label": day.strftime("%a"), "value": minutes * 7})
    return render(
        request,
        "member/progress.html",
        {
            "records": records,
            "chart_records": chart_records,
            "target_weight": target_weight,
            "period": period,
            "current_weight": current_weight,
            "initial_weight": initial_weight,
            "remaining_weight": remaining_weight,
            "goal_percent": goal_percent,
            "weight_change": weight_change,
            "workout_count": len(session_list),
            "average_minutes": average_minutes,
            "estimated_calories": estimated_calories,
            "breakdown": breakdown,
            "personal_records": personal_records,
            "photos": records.exclude(progress_photo="").exclude(
                progress_photo__isnull=True
            )[:10],
            "weight_chart": [
                {
                    "label": item.recorded_date.strftime("%d %b"),
                    "value": float(item.weight_kg),
                }
                for item in chart_records
            ],
            "calorie_chart": calorie_days,
            "active_sidebar": "progress",
        },
    )


# 2.17 Record a dated weight
@login_required
def weight_add(request):
    if not is_member(request.user):
        return HttpResponseForbidden("This page is for members.")
    form = WeightRecordForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.member = request.user
        record.save()
        messages.success(request, "Weight record added.")
        return redirect("workouts:progress")
    return render(
        request,
        "member/weight_form.html",
        {"form": form, "title": "Add Weight Record", "active_sidebar": "progress"},
    )


@login_required
def weight_edit(request, record_id):
    record = get_object_or_404(WeightRecord, id=record_id, member=request.user)
    form = WeightRecordForm(
        request.POST or None, request.FILES or None, instance=record
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Weight record updated.")
        return redirect("workouts:progress")
    return render(
        request,
        "member/weight_form.html",
        {"form": form, "title": "Edit Weight Record", "active_sidebar": "progress"},
    )


@login_required
def weight_delete(request, record_id):
    record = get_object_or_404(WeightRecord, id=record_id, member=request.user)
    if request.method == "POST":
        record.delete()
        messages.success(request, "Weight record deleted.")
        return redirect("workouts:progress")
    return render(
        request,
        "member/weight_confirm_delete.html",
        {"record": record, "active_sidebar": "progress"},
    )


# 3.8 Assigned members
@login_required
def coach_members(request):
    if not is_coach(request.user):
        return HttpResponseForbidden("This page is for coaches.")
    assignments = CoachAssignment.objects.filter(
        coach=request.user, active=True, member__is_active=True
    ).select_related("member", "member__member_profile")
    return render(
        request,
        "coach/assigned_members.html",
        {"assignments": assignments, "active_sidebar": "members"},
    )


@login_required
def coach_plans(request):
    if not is_coach(request.user):
        return HttpResponseForbidden("This page is for coaches.")
    members = User.objects.filter(
        role="MEMBER",
        is_active=True,
        coach_links__coach=request.user,
        coach_links__active=True,
    ).order_by("first_name", "last_name")
    plans = (
        WorkoutPlan.objects.filter(
            coach=request.user, member__in=members, plan_type="COACH_ASSIGNED"
        )
        .select_related("member")
        .annotate(exercise_count=Count("plan_exercises"))
        .order_by(
            "member__first_name", "member__last_name", "member_id", "-updated_at", "-pk"
        )
    )
    selected_member = request.GET.get("member", "")
    if selected_member:
        member = get_object_or_404(
            members, pk=selected_member if selected_member.isdigit() else 0
        )
        plans = plans.filter(member=member)
    page = Paginator(plans, 15).get_page(request.GET.get("page"))
    return render(
        request,
        "coach/workout_plans.html",
        {
            "plans": page.object_list,
            "page_obj": page,
            "plan_count": page.paginator.count,
            "members": members,
            "selected_member": selected_member,
            "active_sidebar": "plans",
        },
    )


@login_required
def coach_progress(request):
    if not is_coach(request.user):
        return HttpResponseForbidden("This page is for coaches.")
    weights = WeightRecord.objects.filter(member=OuterRef("pk")).order_by(
        "-recorded_date", "-pk"
    )
    completed = WorkoutSession.objects.filter(
        member=OuterRef("pk"), completed_at__isnull=False
    ).order_by("-completed_at")
    members = (
        User.objects.filter(
            role="MEMBER",
            is_active=True,
            coach_links__coach=request.user,
            coach_links__active=True,
        )
        .select_related("member_profile")
        .annotate(
            latest_weight=Subquery(weights.values("weight_kg")[:1]),
            latest_weight_date=Subquery(weights.values("recorded_date")[:1]),
            last_workout=Subquery(completed.values("completed_at")[:1]),
            completed_count=Count(
                "workout_sessions",
                filter=Q(workout_sessions__completed_at__isnull=False),
                distinct=True,
            ),
            weekly_count=Count(
                "workout_sessions",
                filter=Q(
                    workout_sessions__completed_at__date__gte=timezone.localdate()
                    - timedelta(days=6),
                    workout_sessions__completed_at__isnull=False,
                ),
                distinct=True,
            ),
        )
        .order_by("first_name", "last_name")
    )
    return render(
        request,
        "coach/progress.html",
        {"members": members, "active_sidebar": "progress"},
    )


# 3.9 Create a member plan
@login_required
def coach_plan_create(request, member_id):
    if not is_coach(request.user):
        return HttpResponseForbidden("This page is for coaches.")
    member = get_object_or_404(User, id=member_id, role="MEMBER")
    if not coach_is_assigned(request.user, member):
        return HttpResponseForbidden("This member is not assigned to you.")
    form = WorkoutPlanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        plan = form.save(commit=False)
        plan.member = member
        plan.coach = request.user
        plan.plan_type = "COACH_ASSIGNED"
        plan.save()
        messages.success(request, "Coach-assigned plan created. Add exercises next.")
        return redirect("workouts:plan_add_exercises", plan_id=plan.id)
    return render(
        request,
        "shared/plan_form.html",
        {
            "form": form,
            "title": f"Create Plan for {member.get_full_name() or member.username}",
            "coach_mode": True,
            "active_sidebar": "plans",
            "layout_template": "layouts/coach_base.html",
        },
    )


# 3.10 Review assigned member progress
@login_required
def coach_member_progress(request, member_id):
    if not is_coach(request.user):
        return HttpResponseForbidden("This page is for coaches.")
    member = get_object_or_404(User, id=member_id, role="MEMBER")
    if not coach_is_assigned(request.user, member):
        return HttpResponseForbidden("This member is not assigned to you.")
    weight_records = WeightRecord.objects.filter(member=member)
    workout_sessions = WorkoutSession.objects.filter(
        member=member, completed_at__isnull=False
    ).select_related("workout_plan")
    return render(
        request,
        "coach/member_progress.html",
        {
            "member": member,
            "weight_records": weight_records,
            "workout_sessions": workout_sessions,
            "active_sidebar": "progress",
        },
    )


# Attendance — Bhavshika

# 4.8 Attendance corrections


def has_active_membership(member):
    today = timezone.localdate()
    return Membership.objects.filter(
        member=member,
        status=Membership.Status.ACTIVE,
        start_date__lte=today,
        end_date__gte=today,
    ).exists()


def dashboard_base(user):
    if user.is_superuser or user.role == User.Role.ADMIN:
        return "layouts/admin_base.html"
    return "layouts/staff_base.html"


def attendance_sidebar(user):
    if user.is_superuser or user.role == User.Role.ADMIN:
        return "attendance"
    return "attendance-history"


def attendance_valid_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


# 2.7 Digital membership QR code
@member_required
def my_qr_code(request):
    qr_code, _ = MemberQRCode.objects.get_or_create(member=request.user)
    qr_active = qr_code.is_active and has_active_membership(request.user)
    qr_image = None
    if qr_active:
        image = qrcode.make(str(qr_code.qr_token))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        qr_image = base64.b64encode(buffer.getvalue()).decode()
    return render(
        request,
        "member/qr_code.html",
        {
            "qr_code": qr_code,
            "qr_image": qr_image,
            "qr_active": qr_active,
            "active_sidebar": "qr",
        },
    )


# 2.13 and 3.5 Gym occupancy
@member_required
def occupancy(request):
    current_occupancy = AttendanceRecord.objects.filter(
        check_out_time__isnull=True
    ).count()
    max_capacity = GymConfiguration.get_capacity()
    occupancy_percent = min(round(current_occupancy / max_capacity * 100), 100)
    return render(
        request,
        "shared/occupancy.html",
        {
            "current_occupancy": current_occupancy,
            "max_capacity": max_capacity,
            "available_spaces": max(max_capacity - current_occupancy, 0),
            "occupancy_percent": occupancy_percent,
            "active_sidebar": "occupancy",
        },
    )


# 3.3–3.4 Check-in and check-out
@staff_required
def staff_attendance(request):
    if request.method == "POST":
        identifier = request.POST.get("member_identifier", "").strip()
        action = request.POST.get("action")
        member = None
        try:
            qr_token = uuid.UUID(identifier)
            qr_code = (
                MemberQRCode.objects.select_related("member")
                .filter(qr_token=qr_token, is_active=True)
                .first()
            )
            if qr_code:
                member = qr_code.member
        except (ValueError, AttributeError):
            pass
        if member is None:
            member = (
                get_user_model()
                .objects.filter(
                    email__iexact=identifier, role=User.Role.MEMBER, is_active=True
                )
                .first()
            )
        if member is None:
            messages.error(request, "No member was found with that QR code or email.")
            return redirect("attendance:staff_attendance")
        active_record = AttendanceRecord.objects.filter(
            member=member, check_out_time__isnull=True
        ).first()
        if action == "check_in":
            if not has_active_membership(member):
                messages.error(request, f"{member} does not have an active membership.")
            elif active_record:
                messages.error(request, f"{member} is already checked in.")
            elif (
                AttendanceRecord.objects.filter(check_out_time__isnull=True).count()
                >= GymConfiguration.get_capacity()
            ):
                messages.error(request, "Gym is at maximum capacity. Check-in denied.")
            else:
                AttendanceRecord.objects.create(member=member)
                messages.success(request, f"{member} checked in successfully.")
        elif action == "check_out":
            if active_record is None:
                messages.error(request, f"{member} has no active check-in.")
            else:
                active_record.check_out_time = timezone.now()
                active_record.save(update_fields=["check_out_time"])
                messages.success(request, f"{member} checked out successfully.")
        else:
            messages.error(request, "Select check-in or check-out.")
        return redirect("attendance:staff_attendance")
    today_records = AttendanceRecord.objects.filter(
        check_in_time__date=timezone.localdate()
    ).select_related("member")
    current_occupancy = AttendanceRecord.objects.filter(
        check_out_time__isnull=True
    ).count()
    return render(
        request,
        "staff/attendance.html",
        {
            "today_records": today_records,
            "current_occupancy": current_occupancy,
            "max_capacity": GymConfiguration.get_capacity(),
            "base_template": dashboard_base(request.user),
            "active_sidebar": "attendance",
        },
    )


@staff_required
def attendance_history(request):
    records = AttendanceRecord.objects.select_related("member", "corrected_by")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    date_from = attendance_valid_date(request.GET.get("date_from", ""))
    date_to = attendance_valid_date(request.GET.get("date_to", ""))
    if query:
        records = records.filter(
            Q(member__first_name__icontains=query)
            | Q(member__last_name__icontains=query)
            | Q(member__email__icontains=query)
        )
    if status == "INSIDE":
        records = records.filter(check_out_time__isnull=True)
    elif status == "COMPLETED":
        records = records.filter(check_out_time__isnull=False)
    if date_from:
        records = records.filter(check_in_time__date__gte=date_from)
    if date_to:
        records = records.filter(check_in_time__date__lte=date_to)
    return render(
        request,
        "shared/attendance_history.html",
        {
            "records": records,
            "query": query,
            "status_filter": status,
            "date_from": date_from,
            "date_to": date_to,
            "base_template": dashboard_base(request.user),
            "active_sidebar": attendance_sidebar(request.user),
        },
    )


# 4.8 Correct attendance with an audit note
@staff_required
def correct_attendance(request, pk):
    record = get_object_or_404(AttendanceRecord, pk=pk)
    initial = {
        "check_in_time": timezone.localtime(record.check_in_time),
        "check_out_time": (
            timezone.localtime(record.check_out_time) if record.check_out_time else None
        ),
        "correction_note": record.correction_note,
    }
    form = AttendanceCorrectionForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        record.check_in_time = form.cleaned_data["check_in_time"]
        record.check_out_time = form.cleaned_data["check_out_time"]
        record.correction_note = form.cleaned_data["correction_note"]
        record.corrected_by = request.user
        record.save()
        messages.success(request, "Attendance record corrected successfully.")
        return redirect("attendance:attendance_history")
    return render(
        request,
        "shared/form.html",
        {
            "title": "Correct Attendance Record",
            "subtitle": str(record.member),
            "cancel_url": reverse("attendance:attendance_history"),
            "record": record,
            "form": form,
            "base_template": dashboard_base(request.user),
            "active_sidebar": attendance_sidebar(request.user),
        },
    )


@staff_required
def attendance_report(request):
    records = AttendanceRecord.objects.all()
    date_from = attendance_valid_date(request.GET.get("date_from", ""))
    date_to = attendance_valid_date(request.GET.get("date_to", ""))
    if date_from:
        records = records.filter(check_in_time__date__gte=date_from)
    if date_to:
        records = records.filter(check_in_time__date__lte=date_to)
    daily_counts = (
        records.annotate(day=TruncDate("check_in_time"))
        .values("day")
        .annotate(total_check_ins=Count("id"))
        .order_by("-day")
    )
    return render(
        request,
        "shared/attendance_report.html",
        {
            "daily_counts": daily_counts,
            "total_check_ins": records.count(),
            "current_occupancy": AttendanceRecord.objects.filter(
                check_out_time__isnull=True
            ).count(),
            "date_from": date_from,
            "date_to": date_to,
            "base_template": dashboard_base(request.user),
            "active_sidebar": "reports",
        },
    )


# 4.7 Gym capacity
@admin_required
def capacity_settings(request):
    configuration, _ = GymConfiguration.objects.get_or_create(pk=1)
    form = GymConfigurationForm(request.POST or None, instance=configuration)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Gym capacity updated.")
        return redirect("attendance:capacity_settings")
    return render(
        request,
        "admin_dashboard/capacity_settings.html",
        {
            "form": form,
            "current_occupancy": AttendanceRecord.objects.filter(
                check_out_time__isnull=True
            ).count(),
            "active_sidebar": "capacity",
        },
    )


# Outdoor activities — Bhavshika

# 2.19 GPS activity (mobile phase); 2.20 Activity history


@member_required
def activity_list(request):
    activities = OutdoorActivity.objects.filter(member=request.user)
    return render(
        request,
        "member/outdoor_activities.html",
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
        "member/outdoor_activity_form.html",
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
        "member/outdoor_activity_detail.html",
        {"activity": activity, "pace": pace, "active_sidebar": "activities"},
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
        "member/outdoor_activity_confirm_delete.html",
        {"activity": activity, "active_sidebar": "activities"},
    )


# Notifications and notices — Anjie


# 2.24 Member notifications
@login_required
def notification_list(request):
    notifications = Notification.objects.filter(recipient=request.user)
    return render(
        request,
        "shared/notification_list.html",
        {"notifications": notifications},
    )


@login_required
def notification_detail(request, notification_id):
    notification = get_object_or_404(
        Notification, pk=notification_id, recipient=request.user
    )
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])
    return render(
        request,
        "shared/notification_detail.html",
        {"notification": notification},
    )


@login_required
@require_POST
def mark_as_read(request, notification_id):
    notification = get_object_or_404(
        Notification, pk=notification_id, recipient=request.user
    )
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    if notification.link:
        return redirect(notification.link)
    return redirect("notifications:list")


@login_required
@require_POST
def mark_all_as_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True
    )
    return redirect("notifications:list")


# 4.10 Gym notices
@admin_required
def notice_list(request):
    return render(
        request,
        "admin_dashboard/notice_list.html",
        {"notices": Notice.objects.all(), "active_sidebar": "notices"},
    )


@admin_required
def notice_create(request):
    form = NoticeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        notice = form.save(commit=False)
        notice.created_by = request.user
        notice.save()
        return redirect("notifications:notice_list")
    return render(
        request,
        "admin_dashboard/notice_form.html",
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
        "admin_dashboard/notice_form.html",
        {"form": form, "title": "Edit Gym Notice", "active_sidebar": "notices"},
    )


@admin_required
def notice_delete(request, notice_id):
    notice = get_object_or_404(Notice, pk=notice_id)
    if request.method == "POST":
        notice.delete()
        return redirect("notifications:notice_list")
    return render(
        request,
        "admin_dashboard/notice_confirm_delete.html",
        {"notice": notice, "active_sidebar": "notices"},
    )


# Public pages and dashboard summaries — Shared

# 1.7 Contact enquiries; 4.14 Public contact details; 4.15 Enquiry management


def home(request):
    now = timezone.localtime()
    completed_workouts = WorkoutSession.objects.filter(completed_at__date=now.date())
    workout_minutes = sum(
        (session.duration_minutes or 0 for session in completed_workouts)
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
    return render(request, "public/home.html", {"live_stats": live_stats})


def features(request):
    """Display FitSync's public platform features."""
    return render(request, "public/features.html")


# 1.7 Store a contact enquiry
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
        message_body = f"From: {form.cleaned_data['full_name']}\nEmail: {form.cleaned_data['email']}\nTopic: {topic}\n\n{form.cleaned_data['message']}"
        enquiry = ContactMessage.objects.create(
            full_name=form.cleaned_data["full_name"],
            email=form.cleaned_data["email"],
            topic=topic,
            message=form.cleaned_data["message"],
        )
        recipient = (
            getattr(settings, "CONTACT_RECIPIENT_EMAIL", "")
            or GymSettings.load().public_email
        )
        # Always store first. Console/dummy backends do not deliver email.
        local_only = settings.EMAIL_BACKEND in {
            "django.core.mail.backends.console.EmailBackend",
            "django.core.mail.backends.dummy.EmailBackend",
            "django.core.mail.backends.filebased.EmailBackend",
        }
        if recipient and not local_only:
            try:
                sent = send_mail(
                    subject=f"FitSync contact: {topic}",
                    message=message_body,
                    from_email=None,
                    recipient_list=[recipient],
                )
            except (SMTPException, OSError, ValueError):
                sent = 0
            if sent:
                enquiry.email_notification_sent = True
                enquiry.save(update_fields=["email_notification_sent"])
        messages.success(request, "Thank you. Your message has been received.")
        return redirect("core:contact")
    return render(
        request, "public/contact.html", {"form": form, "gym": GymSettings.load()}
    )


# About page — Rheva


def aboutus(request):
    return render(request, "public/about.html")


# Team profiles — Rheva

# 4.13 Public team profiles


def ourteam(request):
    members = TeamMember.objects.filter(is_active=True)
    return render(
        request,
        "public/team.html",
        {
            "team_members": members,
            "featured_member": members.filter(is_featured=True).first(),
            "departments": TeamMember.Department.choices,
            "gym": GymSettings.load(),
        },
    )


# Public team and contact content — Shared


@admin_required
def public_content_settings(request):
    form = GymSettingsForm(
        request.POST or None, request.FILES or None, instance=GymSettings.load()
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Public contact details saved.")
        return redirect("core:manage_settings")
    return render(
        request,
        "admin_dashboard/public_content_form.html",
        {
            "form": form,
            "title": "Contact Details",
            "active_sidebar": "public_settings",
            "cancel_url": reverse("accounts:admin_dashboard"),
        },
    )


@admin_required
def public_team_list(request):
    people = TeamMember.objects.select_related("user").all()
    query = request.GET.get("q", "").strip()
    if query:
        people = people.filter(
            Q(display_name__icontains=query) | Q(job_title__icontains=query)
        )
    page = Paginator(people, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "admin_dashboard/team_list.html",
        {"people": page, "query": query, "active_sidebar": "public_team"},
    )


@admin_required
def public_team_edit(request, person_id=None):
    person = (
        get_object_or_404(TeamMember, pk=person_id) if person_id is not None else None
    )
    form = TeamMemberForm(request.POST or None, request.FILES or None, instance=person)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            person = form.save()
            if person.is_featured:
                TeamMember.objects.exclude(pk=person.pk).update(is_featured=False)
        messages.success(
            request, "Team profile saved. No login account was created or changed."
        )
        return redirect("core:manage_team")
    return render(
        request,
        "admin_dashboard/public_content_form.html",
        {
            "form": form,
            "title": "Edit Team Profile" if person else "Add Team Profile",
            "active_sidebar": "public_team",
            "cancel_url": reverse("core:manage_team"),
        },
    )


@admin_required
@require_POST
def public_team_toggle(request, person_id):
    person = get_object_or_404(TeamMember, pk=person_id)
    person.is_active = not person.is_active
    person.save(update_fields=["is_active"])
    messages.success(request, "Team profile visibility updated.")
    return redirect("core:manage_team")


@admin_required
def contact_inbox(request):
    enquiries = ContactMessage.objects.all()
    status = request.GET.get("status", "")
    if status in ContactMessage.Status.values:
        enquiries = enquiries.filter(status=status)
    query = request.GET.get("q", "").strip()
    if query:
        enquiries = enquiries.filter(
            Q(full_name__icontains=query)
            | Q(email__icontains=query)
            | Q(message__icontains=query)
        )
    return render(
        request,
        "admin_dashboard/enquiry_inbox.html",
        {
            "enquiries": Paginator(enquiries, 20).get_page(request.GET.get("page")),
            "status_choices": ContactMessage.Status.choices,
            "selected_status": status,
            "query": query,
            "active_sidebar": "contact_inbox",
        },
    )


@admin_required
def contact_enquiry_detail(request, enquiry_id):
    enquiry = get_object_or_404(ContactMessage, pk=enquiry_id)
    form = ContactMessageManagementForm(request.POST or None, instance=enquiry)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Enquiry status and internal notes saved.")
        return redirect("core:manage_enquiry", enquiry_id=enquiry.pk)
    return render(
        request,
        "admin_dashboard/enquiry_detail.html",
        {"enquiry": enquiry, "form": form, "active_sidebar": "contact_inbox"},
    )
