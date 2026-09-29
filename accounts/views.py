from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .decorators import admin_required, coach_required, member_required, role_required, staff_required
from .forms import (
    AdminRoleForm,
    CoachAssignmentForm,
    EmailLoginForm,
    MemberProfileForm,
    RegistrationForm,
    StyledPasswordChangeForm,
    UserProfileForm,
)
from .models import CoachAssignment, CoachProfile, MemberProfile, User


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
    context = {
        "profile": profile,
        "profile_percent": profile_percent,
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
    context = {
        "assignments": assignments,
        "assignment_count": assignments.count(),
        "active_sidebar": "dashboard",
    }
    return render(request, "accounts/dashboards/coach_dashboard.html", context)


@admin_required
def admin_dashboard(request):
    context = {
        "total_users": User.objects.count(),
        "active_users": User.objects.filter(is_active=True).count(),
        "member_count": User.objects.filter(role=User.Role.MEMBER).count(),
        "staff_count": User.objects.filter(role=User.Role.STAFF).count(),
        "coach_count": User.objects.filter(role=User.Role.COACH).count(),
        "admin_count": User.objects.filter(role=User.Role.ADMIN).count(),
        "assignment_count": CoachAssignment.objects.filter(active=True).count(),
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

    if query:
        users = users.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    if role in User.Role.values:
        users = users.filter(role=role)

    context = {
        "users": users,
        "query": query,
        "selected_role": role,
        "role_choices": User.Role.choices,
        "active_sidebar": "users",
    }
    return render(request, "accounts/admin/user_list.html", context)


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
