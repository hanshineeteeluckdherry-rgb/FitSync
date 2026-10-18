from decimal import Decimal, InvalidOperation
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, OuterRef, Subquery
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import CoachAssignment, User

from .forms import ExerciseForm, WaterIntakeForm, WeightRecordForm, WorkoutPlanForm, WorkoutSetForm
from .models import (
    Exercise,
    WaterIntake,
    WeightRecord,
    WorkoutExerciseRecord,
    WorkoutPlan,
    WorkoutPlanExercise,
    WorkoutSession,
)


def is_member(user):
    return user.is_authenticated and user.role == "MEMBER"


@login_required
def water_intake(request):
    if not is_member(request.user):
        return HttpResponseForbidden("This page is for members.")

    today = timezone.localdate()
    records = WaterIntake.objects.filter(member=request.user)
    today_record = records.filter(recorded_date=today).first()
    form = WaterIntakeForm(
        request.POST or None,
        initial={"recorded_date": today, "litres": today_record.litres if today_record else 0},
    )
    if request.method == "POST" and form.is_valid():
        WaterIntake.objects.update_or_create(
            member=request.user,
            recorded_date=form.cleaned_data["recorded_date"],
            defaults={"litres": form.cleaned_data["litres"]},
        )
        messages.success(request, "Your water intake has been saved.")
        return redirect("workouts:water_intake")

    return render(request, "workouts/water_intake.html", {
        "form": form,
        "records": records[:30],
        "today_litres": today_record.litres if today_record else 0,
        "active_sidebar": "water",
    })


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
            "layout_template": "layouts/coach_base.html" if is_coach(request.user) else "layouts/member_base.html",
        },
    )


@login_required
def exercise_detail(request, exercise_id):
    exercise = get_object_or_404(Exercise, id=exercise_id, is_active=True)
    return render(
        request,
        "workouts/exercise_detail.html",
        {"exercise": exercise, "active_sidebar": "plans", "layout_template": "layouts/coach_base.html" if is_coach(request.user) else "layouts/member_base.html"},
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
            return redirect("workouts:coach_plans")
        return redirect("workouts:plans")

    return render(
        request,
        "workouts/plan_confirm_delete.html",
        {"plan": plan, "active_sidebar": "plans", "layout_template": "layouts/coach_base.html" if is_coach(request.user) else "layouts/member_base.html"},
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


def workout_set_entries(session, data=None):
    if not session.workout_plan:
        return []
    entries = list(session.workout_plan.plan_exercises.select_related("exercise"))
    for entry in entries:
        selected = data.getlist(f"completed_sets_{entry.id}") if data is not None else []
        entry.set_rows = []
        for number in range(1, entry.sets + 1):
            form = WorkoutSetForm(
                data,
                prefix=f"set_{entry.id}_{number}",
                initial={"reps": entry.reps, "weight_kg": entry.weight_kg},
            )
            entry.set_rows.append({"number": number, "form": form, "completed": str(number) in selected})
    return entries


@login_required
def active_workout(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, member=request.user)
    if session.completed_at:
        return redirect("workouts:history_detail", session_id=session.id)

    entries = workout_set_entries(session)
    return render(
        request,
        "workouts/active_workout.html",
        {"session": session, "entries": entries, "active_sidebar": "plans"},
    )


@login_required
@transaction.atomic
def finish_workout(request, session_id):
    session = get_object_or_404(WorkoutSession.objects.select_for_update(), id=session_id, member=request.user)
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
        messages.error(request, "Mark at least one set complete before finishing the workout.")
    elif not valid:
        messages.error(request, "Check the reps and weight for your completed sets.")
    if not completed_sets or not valid:
        return render(request, "workouts/active_workout.html", {
            "session": session, "entries": entries, "active_sidebar": "plans",
            "notes": request.POST.get("notes", ""),
        })

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
    session.duration_minutes = None
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
    ).select_related("workout_plan").annotate(exercise_count=Count("exercise_records__exercise", distinct=True))
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

    records = session.exercise_records.select_related("exercise").order_by("exercise_id", "set_number", "id")
    return render(
        request,
        "workouts/workout_history_detail.html",
        {"session": session, "records": records, "active_sidebar": "progress" if is_coach(request.user) else "history", "layout_template": "layouts/coach_base.html" if is_coach(request.user) else "layouts/member_base.html"},
    )


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

    all_records = WeightRecord.objects.filter(member=request.user, recorded_date__lte=today)
    records = all_records
    sessions = WorkoutSession.objects.filter(member=request.user, completed_at__isnull=False, completed_at__date__lte=today).select_related("workout_plan")
    if start_date:
        records = records.filter(recorded_date__gte=start_date)
        sessions = sessions.filter(completed_at__date__gte=start_date)

    profile = getattr(request.user, "member_profile", None)
    target_weight = profile.target_weight_kg if profile else None
    latest = all_records.first()
    first = all_records.order_by("recorded_date", "id").first()
    current_weight = latest.weight_kg if latest else (profile.current_weight_kg if profile else None)
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
            goal_percent = max(0, min(100, round(float((initial_weight - current_weight) / goal_distance) * 100)))
        elif current_weight == target_weight:
            goal_percent = 100

    chart_records = list(records.order_by("recorded_date", "id"))
    weight_change = None
    if len(chart_records) >= 2:
        weight_change = chart_records[-1].weight_kg - chart_records[0].weight_kg
    session_list = list(sessions)
    durations = [item.duration_minutes for item in session_list if item.duration_minutes is not None]
    average_minutes = round(sum(durations) / len(durations)) if durations else None
    estimated_calories = sum(durations) * 7 if durations else None

    breakdown_counts = {"Strength": 0, "Cardio": 0, "HIIT": 0, "Other": 0}
    for item in session_list:
        description = f"{item.workout_plan.goal} {item.workout_plan.name}".lower() if item.workout_plan else ""
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
        {"name": name, "count": count, "percent": round(count / len(session_list) * 100) if session_list else 0, "colour": colour}
        for (name, count), colour in zip(breakdown_counts.items(), ["teal", "blue", "amber", "purple"])
    ]

    personal_records = []
    seen_exercises = set()
    exercise_records = WorkoutExerciseRecord.objects.filter(workout_session__in=sessions, weight_kg__isnull=False).select_related("exercise", "workout_session").order_by("-weight_kg", "-workout_session__completed_at")
    for record in exercise_records:
        if record.exercise_id not in seen_exercises:
            personal_records.append(record)
            seen_exercises.add(record.exercise_id)
        if len(personal_records) == 4:
            break

    calorie_days = []
    recent_sessions = WorkoutSession.objects.filter(member=request.user, completed_at__date__gte=today - timedelta(days=6), completed_at__date__lte=today)
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        minutes = sum(item.duration_minutes or 0 for item in recent_sessions if timezone.localdate(item.completed_at) == day)
        calorie_days.append({"label": day.strftime("%a"), "value": minutes * 7})

    return render(
        request,
        "workouts/progress.html",
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
            "photos": records.exclude(progress_photo="").exclude(progress_photo__isnull=True)[:10],
            "weight_chart": [{"label": item.recorded_date.strftime("%d %b"), "value": float(item.weight_kg)} for item in chart_records],
            "calorie_chart": calorie_days,
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
        member__is_active=True,
    ).select_related("member", "member__member_profile")
    return render(
        request,
        "workouts/coach_members.html",
        {"assignments": assignments, "active_sidebar": "members"},
    )


@login_required
def coach_plans(request):
    if not is_coach(request.user):
        return HttpResponseForbidden("This page is for coaches.")
    members = User.objects.filter(
        role="MEMBER", is_active=True,
        coach_links__coach=request.user, coach_links__active=True,
    ).order_by("first_name", "last_name")
    plans = WorkoutPlan.objects.filter(
        coach=request.user, member__in=members, plan_type="COACH_ASSIGNED",
    ).select_related("member").annotate(exercise_count=Count("plan_exercises")).order_by(
        "member__first_name", "member__last_name", "member_id", "-updated_at", "-pk"
    )
    selected_member = request.GET.get("member", "")
    if selected_member:
        # Reject unassigned IDs rather than exposing their names or plans.
        member = get_object_or_404(members, pk=selected_member if selected_member.isdigit() else 0)
        plans = plans.filter(member=member)
    page = Paginator(plans, 15).get_page(request.GET.get("page"))
    return render(request, "workouts/coach_plans.html", {
        "plans": page.object_list, "page_obj": page, "plan_count": page.paginator.count,
        "members": members, "selected_member": selected_member,
        "active_sidebar": "plans",
    })


@login_required
def coach_progress(request):
    if not is_coach(request.user):
        return HttpResponseForbidden("This page is for coaches.")
    weights = WeightRecord.objects.filter(member=OuterRef("pk")).order_by("-recorded_date", "-pk")
    completed = WorkoutSession.objects.filter(member=OuterRef("pk"), completed_at__isnull=False).order_by("-completed_at")
    members = User.objects.filter(
        role="MEMBER", is_active=True, coach_links__coach=request.user, coach_links__active=True,
    ).select_related("member_profile").annotate(
        latest_weight=Subquery(weights.values("weight_kg")[:1]),
        latest_weight_date=Subquery(weights.values("recorded_date")[:1]),
        last_workout=Subquery(completed.values("completed_at")[:1]),
        completed_count=Count("workout_sessions", filter=Q(workout_sessions__completed_at__isnull=False), distinct=True),
        weekly_count=Count("workout_sessions", filter=Q(workout_sessions__completed_at__date__gte=timezone.localdate() - timedelta(days=6), workout_sessions__completed_at__isnull=False), distinct=True),
    ).order_by("first_name", "last_name")
    return render(request, "workouts/coach_progress.html", {
        "members": members, "active_sidebar": "progress",
    })


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
            "title": f"Create Plan for {member.get_full_name() or member.username}",
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
