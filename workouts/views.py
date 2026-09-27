from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import CoachAssignment, User

from .forms import ExerciseForm, WeightRecordForm, WorkoutPlanForm
from .models import (
    Exercise,
    WeightRecord,
    WorkoutExerciseRecord,
    WorkoutPlan,
    WorkoutPlanExercise,
    WorkoutSession,
)


def is_member(user):
    return user.is_authenticated and user.role == "MEMBER"


def is_coach(user):
    return user.is_authenticated and user.role == "COACH"


def can_manage_exercises(user):
    return user.is_authenticated and (user.is_superuser or user.role in ["STAFF", "ADMIN"])


def coach_is_assigned(coach, member):
    return CoachAssignment.objects.filter(
        coach=coach,
        member=member,
        active=True,
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
    return is_coach(user) and plan.coach == user and coach_is_assigned(user, plan.member)


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
        member=request.user,
        plan_type="PERSONAL",
        is_active=True,
    )
    coach_plans = WorkoutPlan.objects.filter(
        member=request.user,
        plan_type="COACH_ASSIGNED",
        is_active=True,
    )

    return render(
        request,
        "workouts/workout_plans.html",
        {
            "personal_plans": personal_plans,
            "coach_plans": coach_plans,
            "active_sidebar": "plans",
        },
    )


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
        "workouts/exercise_library.html",
        {
            "exercises": exercises,
            "search": search,
            "selected_muscle": muscle,
            "selected_equipment": equipment,
            "muscle_choices": Exercise.MUSCLE_CHOICES,
            "equipment_choices": Exercise.EQUIPMENT_CHOICES,
            "plan": plan,
            "active_sidebar": "plans",
        },
    )


@login_required
def exercise_detail(request, exercise_id):
    exercise = get_object_or_404(Exercise, id=exercise_id, is_active=True)
    return render(
        request,
        "workouts/exercise_detail.html",
        {"exercise": exercise, "active_sidebar": "plans"},
    )


@login_required
def exercise_manage(request):
    if not can_manage_exercises(request.user):
        return HttpResponseForbidden("You do not have permission to manage exercises.")

    exercises = Exercise.objects.all()
    search = request.GET.get("search", "").strip()
    if search:
        exercises = exercises.filter(Q(name__icontains=search) | Q(category__icontains=search))

    layout_template = "layouts/admin_base.html" if request.user.is_superuser or request.user.role == "ADMIN" else "layouts/staff_base.html"
    return render(
        request,
        "workouts/exercise_manage.html",
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

    return render(request, "workouts/exercise_form.html", {"form": form, "title": "Add Exercise"})


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

    return render(request, "workouts/exercise_form.html", {"form": form, "title": "Edit Exercise"})


@login_required
def exercise_toggle(request, exercise_id):
    if request.method != "POST" or not can_manage_exercises(request.user):
        return HttpResponseForbidden("You do not have permission to manage exercises.")

    exercise = get_object_or_404(Exercise, id=exercise_id)
    exercise.is_active = not exercise.is_active
    exercise.save(update_fields=["is_active"])
    messages.success(request, "Exercise status updated.")
    return redirect("workouts:exercise_manage")


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
                id__in=selected_ids,
                is_active=True,
            )

            for order, exercise in enumerate(selected_exercises, start=1):
                WorkoutPlanExercise.objects.create(
                    workout_plan=plan,
                    exercise=exercise,
                    sets=3,
                    reps=10,
                    order=order,
                )

            messages.success(
                request,
                "Workout plan created. You can now adjust sets, reps, weight and duration.",
            )
            return redirect("workouts:plan_detail", plan_id=plan.id)

        if not selected_ids:
            messages.error(request, "Choose at least one exercise from the Exercise Library.")

    return render(
        request,
        "workouts/plan_builder.html",
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
            entry.sets = positive_int(request.POST.get(f"sets_{entry.id}"), entry.sets) or 1
            entry.reps = positive_int(request.POST.get(f"reps_{entry.id}"), entry.reps) or 1
            entry.weight_kg = decimal_or_none(request.POST.get(f"weight_{entry.id}"))
            duration = positive_int(request.POST.get(f"duration_{entry.id}"), 0)
            entry.duration_minutes = duration or None
            entry.day_number = positive_int(request.POST.get(f"day_{entry.id}"), entry.day_number) or 1
            entry.order = positive_int(request.POST.get(f"order_{entry.id}"), entry.order) or 1
            entry.save()
        messages.success(request, "Exercise targets updated.")
        return redirect("workouts:plan_detail", plan_id=plan.id)

    return render(
        request,
        "workouts/plan_detail.html",
        {
            "plan": plan,
            "entries": entries,
            "can_edit": can_edit_plan(request.user, plan),
            "active_sidebar": "plans",
            "layout_template": "layouts/coach_base.html" if is_coach(request.user) else "layouts/member_base.html",
        },
    )


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
        "workouts/plan_form.html",
        {"form": form, "title": "Edit Workout Plan", "plan": plan, "active_sidebar": "plans", "layout_template": "layouts/coach_base.html" if is_coach(request.user) else "layouts/member_base.html"},
    )


@login_required
def plan_delete(request, plan_id):
    plan = get_object_or_404(WorkoutPlan, id=plan_id)
    if not can_edit_plan(request.user, plan):
        return HttpResponseForbidden("You cannot delete this workout plan.")

    if request.method == "POST":
        plan.delete()
        messages.success(request, "Workout plan deleted.")
        if is_coach(request.user):
            return redirect("workouts:coach_members")
        return redirect("workouts:plans")

    return render(
        request,
        "workouts/plan_confirm_delete.html",
        {"plan": plan, "active_sidebar": "plans"},
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
                workout_plan=plan,
                exercise=exercise,
                sets=3,
                reps=10,
                order=next_order,
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
        "workouts/plan_add_exercises.html",
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
            "layout_template": "layouts/coach_base.html" if is_coach(request.user) else "layouts/member_base.html",
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


@login_required
def start_workout(request, plan_id):
    plan = get_object_or_404(WorkoutPlan, id=plan_id, member=request.user, is_active=True)
    if not is_member(request.user):
        return HttpResponseForbidden("Only members can start workouts.")
    if not plan.plan_exercises.exists():
        messages.error(request, "Add at least one exercise before starting this workout.")
        return redirect("workouts:plan_detail", plan_id=plan.id)

    session = WorkoutSession.objects.create(member=request.user, workout_plan=plan)
    return redirect("workouts:active_workout", session_id=session.id)


@login_required
def active_workout(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, member=request.user)
    if session.completed_at:
        return redirect("workouts:history_detail", session_id=session.id)

    entries = session.workout_plan.plan_exercises.select_related("exercise") if session.workout_plan else []
    return render(
        request,
        "workouts/active_workout.html",
        {"session": session, "entries": entries, "active_sidebar": "plans"},
    )


@login_required
def finish_workout(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, member=request.user)
    if request.method != "POST":
        return redirect("workouts:active_workout", session_id=session.id)
    if session.completed_at:
        return redirect("workouts:history_detail", session_id=session.id)

    entries = session.workout_plan.plan_exercises.select_related("exercise") if session.workout_plan else []
    total_duration = 0
    for entry in entries:
        sets = positive_int(request.POST.get(f"sets_{entry.id}"), entry.sets) or 1
        reps = positive_int(request.POST.get(f"reps_{entry.id}"), entry.reps) or 1
        weight = decimal_or_none(request.POST.get(f"weight_{entry.id}"))
        duration = positive_int(request.POST.get(f"duration_{entry.id}"), 0)
        total_duration += duration

        WorkoutExerciseRecord.objects.create(
            workout_session=session,
            exercise=entry.exercise,
            sets=sets,
            reps=reps,
            weight_kg=weight,
            duration_minutes=duration or None,
        )

    session.completed_at = timezone.now()
    session.duration_minutes = positive_int(request.POST.get("session_duration"), total_duration) or total_duration or None
    session.notes = request.POST.get("notes", "").strip()
    session.save()
    messages.success(request, "Workout completed. Great work!")
    return redirect("workouts:history_detail", session_id=session.id)


@login_required
def workout_history(request):
    if not is_member(request.user):
        return HttpResponseForbidden("This page is for members.")

    sessions = WorkoutSession.objects.filter(
        member=request.user,
        completed_at__isnull=False,
    ).select_related("workout_plan")
    return render(
        request,
        "workouts/workout_history.html",
        {"sessions": sessions, "active_sidebar": "history"},
    )


@login_required
def workout_history_detail(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id)
    if request.user != session.member:
        if not (is_coach(request.user) and coach_is_assigned(request.user, session.member)):
            return HttpResponseForbidden("You cannot view this workout history.")

    records = session.exercise_records.select_related("exercise")
    return render(
        request,
        "workouts/workout_history_detail.html",
        {"session": session, "records": records, "active_sidebar": "history", "layout_template": "layouts/coach_base.html" if is_coach(request.user) else "layouts/member_base.html"},
    )


@login_required
def progress(request):
    if not is_member(request.user):
        return HttpResponseForbidden("This page is for members.")

    records = WeightRecord.objects.filter(member=request.user)
    target_weight = None
    try:
        target_weight = request.user.member_profile.target_weight_kg
    except Exception:
        pass

    chart_records = list(records.order_by("recorded_date"))
    return render(
        request,
        "workouts/progress.html",
        {
            "records": records,
            "chart_records": chart_records,
            "target_weight": target_weight,
            "active_sidebar": "progress",
        },
    )


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
        "workouts/weight_form.html",
        {"form": form, "title": "Add Weight Record", "active_sidebar": "progress"},
    )


@login_required
def weight_edit(request, record_id):
    record = get_object_or_404(WeightRecord, id=record_id, member=request.user)
    form = WeightRecordForm(request.POST or None, request.FILES or None, instance=record)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Weight record updated.")
        return redirect("workouts:progress")

    return render(
        request,
        "workouts/weight_form.html",
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
        "workouts/weight_confirm_delete.html",
        {"record": record, "active_sidebar": "progress"},
    )


@login_required
def coach_members(request):
    if not is_coach(request.user):
        return HttpResponseForbidden("This page is for coaches.")

    assignments = CoachAssignment.objects.filter(
        coach=request.user,
        active=True,
    ).select_related("member")
    return render(
        request,
        "workouts/coach_members.html",
        {"assignments": assignments, "active_sidebar": "members"},
    )


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
        "workouts/plan_form.html",
        {
            "form": form,
            "title": f"Create Plan for {member.username}",
            "coach_mode": True,
            "active_sidebar": "plans",
            "layout_template": "layouts/coach_base.html",
        },
    )


@login_required
def coach_member_progress(request, member_id):
    if not is_coach(request.user):
        return HttpResponseForbidden("This page is for coaches.")

    member = get_object_or_404(User, id=member_id, role="MEMBER")
    if not coach_is_assigned(request.user, member):
        return HttpResponseForbidden("This member is not assigned to you.")

    weight_records = WeightRecord.objects.filter(member=member)
    workout_sessions = WorkoutSession.objects.filter(
        member=member,
        completed_at__isnull=False,
    ).select_related("workout_plan")

    return render(
        request,
        "workouts/coach_member_progress.html",
        {
            "member": member,
            "weight_records": weight_records,
            "workout_sessions": workout_sessions,
            "active_sidebar": "progress",
        },
    )
