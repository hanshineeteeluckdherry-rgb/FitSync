from django.contrib import admin

from .models import (
    Exercise,
    WeightRecord,
    WorkoutExerciseRecord,
    WorkoutPlan,
    WorkoutPlanExercise,
    WorkoutSession,
)


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "equipment", "difficulty", "is_active")
    list_filter = ("category", "equipment", "difficulty", "is_active")
    search_fields = ("name", "secondary_muscles")


class WorkoutPlanExerciseInline(admin.TabularInline):
    model = WorkoutPlanExercise
    extra = 0


@admin.register(WorkoutPlan)
class WorkoutPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "member", "plan_type", "coach", "is_active")
    list_filter = ("plan_type", "is_active")
    inlines = [WorkoutPlanExerciseInline]


admin.site.register(WorkoutSession)
admin.site.register(WorkoutExerciseRecord)
admin.site.register(WeightRecord)
