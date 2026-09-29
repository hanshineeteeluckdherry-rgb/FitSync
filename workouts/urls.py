from django.urls import path

from . import views

app_name = "workouts"

urlpatterns = [
    path("", views.workout_plans, name="plans"),
    path("exercises/", views.exercise_library, name="exercise_library"),
    path("exercises/<int:exercise_id>/", views.exercise_detail, name="exercise_detail"),
    path("exercises/manage/", views.exercise_manage, name="exercise_manage"),
    path("exercises/manage/add/", views.exercise_create, name="exercise_create"),
    path("exercises/manage/<int:exercise_id>/edit/", views.exercise_edit, name="exercise_edit"),
    path("exercises/manage/<int:exercise_id>/toggle/", views.exercise_toggle, name="exercise_toggle"),
    path("plans/create/", views.plan_create, name="plan_create"),
    path("plans/<int:plan_id>/", views.plan_detail, name="plan_detail"),
    path("plans/<int:plan_id>/edit/", views.plan_edit, name="plan_edit"),
    path("plans/<int:plan_id>/delete/", views.plan_delete, name="plan_delete"),
    path("plans/<int:plan_id>/exercises/", views.plan_add_exercises, name="plan_add_exercises"),
    path("plans/<int:plan_id>/exercises/<int:entry_id>/remove/", views.plan_remove_exercise, name="plan_remove_exercise"),
    path("plans/<int:plan_id>/start/", views.start_workout, name="start_workout"),
    path("sessions/<int:session_id>/", views.active_workout, name="active_workout"),
    path("sessions/<int:session_id>/finish/", views.finish_workout, name="finish_workout"),
    path("history/", views.workout_history, name="history"),
    path("history/<int:session_id>/", views.workout_history_detail, name="history_detail"),
    path("progress/", views.progress, name="progress"),
    path("progress/add/", views.weight_add, name="weight_add"),
    path("progress/<int:record_id>/edit/", views.weight_edit, name="weight_edit"),
    path("progress/<int:record_id>/delete/", views.weight_delete, name="weight_delete"),
    path("coach/members/", views.coach_members, name="coach_members"),
    path("coach/members/<int:member_id>/plan/create/", views.coach_plan_create, name="coach_plan_create"),
    path("coach/members/<int:member_id>/progress/", views.coach_member_progress, name="coach_member_progress"),
]
