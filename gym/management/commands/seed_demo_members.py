"""Create an isolated, repeatable set of fictional members for local testing."""
from datetime import datetime, time, timedelta
from decimal import Decimal
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from gym.models import CoachAssignment, MemberProfile, User
from gym.models import Booking, Service, Session
from gym.models import Membership, MembershipPackage
from gym.models import (
    Exercise,
    WaterIntake,
    WeightRecord,
    WorkoutExerciseRecord,
    WorkoutPlan,
    WorkoutPlanExercise,
    WorkoutSession,
)

MEMBERS = [
    ("Rachel", "Green"),
    ("Monica", "Geller"),
    ("Phoebe", "Buffay"),
    ("Joey", "Tribbiani"),
    ("Chandler", "Bing"),
    ("Ross", "Geller"),
    ("Gunther", ""),
    ("Janice", "Hosenstein"),
    ("Mike", "Hannigan"),
    ("Carol", "Willick"),
]


def get_demo_member(index, password=None, create=True):
    first, last = MEMBERS[index - 1]
    handle = "_".join((part.lower() for part in (first, last) if part)) + "_m"
    email = f"{handle}@fitsync.com"
    legacy_email = f"demo.member{index:02d}@fitsync.local"
    legacy = User.objects.filter(
        email=legacy_email, username=f"demo_member_{index:02d}"
    ).first()
    old_friends = User.objects.filter(
        email=f"{handle}@fitsync.local", username=handle
    ).first()
    current = User.objects.filter(email=email).first()
    matches = {user.pk: user for user in (legacy, old_friends, current) if user}
    if len(matches) > 1:
        raise CommandError(
            f"{email} already belongs to another account. No accounts were merged."
        )
    user = legacy or old_friends or current
    if user and user.role != User.Role.MEMBER:
        raise CommandError(f"{user.email} is not a member account.")
    if (
        User.objects.filter(username=handle)
        .exclude(pk=user.pk if user else None)
        .exists()
    ):
        raise CommandError(f"Username {handle} is already in use.")
    if legacy or old_friends:
        user.username = handle
        user.email = email
        user.first_name = first
        user.last_name = last
        user.save(update_fields=["username", "email", "first_name", "last_name"])
    elif user is None:
        if not create:
            raise CommandError(
                f"Demo member {index:02d} was not found. Run seed_demo_members first."
            )
        user = User.objects.create_user(
            username=handle,
            email=email,
            password=password,
            first_name=first,
            last_name=last,
            role=User.Role.MEMBER,
        )
    return user


COACH_EMAILS = [
    "chris.bumstead@fitsync.com",
    "sarah.safforti@fitsync.com",
    "chris.heria@fitsync.com",
    "emily.watson@fitsync.com",
    "sam.sulek@fitsync.com",
    "chloe.ting@fitsync.com",
]
EXERCISES = [
    ("Barbell Bench Press", "CHEST", "BARBELL"),
    ("Dumbbell Shoulder Press", "SHOULDERS", "DUMBBELL"),
    ("Triceps Pushdown", "TRICEPS", "CABLE"),
    ("Lat Pulldown", "BACK", "CABLE"),
    ("Dumbbell Row", "BACK", "DUMBBELL"),
    ("Hammer Curl", "BICEPS", "DUMBBELL"),
    ("Goblet Squat", "LEGS", "DUMBBELL"),
    ("Leg Press", "LEGS", "MACHINE"),
    ("Romanian Deadlift", "LEGS", "BARBELL"),
]


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("seed_bookings", services_only=True, stdout=self.stdout)
        coaches = list(User.objects.filter(email__in=COACH_EMAILS))
        if len(coaches) != len(COACH_EMAILS):
            raise CommandError(
                "Set up the existing Our Team coach accounts first (seed_team for a fresh demo database). No coaches were created."
            )
        coaches = sorted(coaches, key=lambda coach: COACH_EMAILS.index(coach.email))
        if any(
            (coach.role != User.Role.COACH or not coach.is_active for coach in coaches)
        ):
            raise CommandError(
                "The Our Team coaches must be active coach accounts before seeding members."
            )
        members = []
        for index in range(1, len(MEMBERS) + 1):
            members.append(get_demo_member(index, password=options["password"]))
        anchor = timezone.localdate(members[0].date_joined)
        package = MembershipPackage.objects.get(slug="premium")
        exercises = []
        for name, category, equipment in EXERCISES:
            exercise, _ = Exercise.objects.get_or_create(
                name=name,
                category=category,
                defaults={
                    "equipment": equipment,
                    "description": "Resistance-training exercise.",
                },
            )
            exercises.append(exercise)
        classes = []
        service_names = [
            "Strength Training",
            "HIIT Training",
            "Boxing Fundamentals",
            "Pilates",
            "Indoor Cycling",
            "Power Yoga",
        ]
        for index, (coach, name) in enumerate(zip(coaches, service_names)):
            service = Service.objects.get(name=name)
            if not service.is_active:
                raise CommandError(f"Activate {name} before creating demo bookings.")
            session, _ = Session.objects.get_or_create(
                service=service,
                instructor=coach,
                date=anchor + timedelta(days=index + 2),
                start_time=time(10),
                defaults={"end_time": time(11), "capacity": 12},
            )
            if session.status != Session.Status.SCHEDULED:
                raise CommandError(
                    "A demo class was cancelled/completed. Existing classes will not be reopened."
                )
            if (
                Session.objects.filter(
                    instructor=coach,
                    date=session.date,
                    status=Session.Status.SCHEDULED,
                    start_time__lt=session.end_time,
                    end_time__gt=session.start_time,
                )
                .exclude(pk=session.pk)
                .exists()
            ):
                raise CommandError(
                    f"{coach} already teaches during a demo class time. No data was changed."
                )
            classes.append(session)
        for index, member in enumerate(members):
            coach = coaches[index % len(coaches)]
            gaining = index % 3 == 0
            start_weight = Decimal(65 + index * 2)
            direction = Decimal("1") if gaining else Decimal("-1")
            latest_weight = start_weight + direction * Decimal("1.8")
            goal = "Build Strength" if gaining else "Improve Fitness"
            MemberProfile.objects.get_or_create(
                user=member,
                defaults={
                    "age": 22 + index,
                    "height_cm": 160 + index * 2,
                    "current_weight_kg": latest_weight,
                    "target_weight_kg": start_weight + direction * Decimal("5"),
                    "fitness_goal": goal,
                },
            )
            CoachAssignment.objects.get_or_create(coach=coach, member=member)
            Membership.objects.get_or_create(
                member=member,
                package=package,
                defaults={
                    "start_date": anchor - timedelta(days=28),
                    "end_date": anchor + timedelta(days=32),
                    "status": Membership.Status.ACTIVE,
                },
            )
            group = index % 3
            plan, _ = WorkoutPlan.objects.get_or_create(
                member=member,
                name=f"Demo {('Push' if group == 0 else 'Pull' if group == 1 else 'Leg')} Day",
                plan_type="COACH_ASSIGNED",
                defaults={
                    "coach": coach,
                    "goal": goal,
                    "description": "Fictional demonstration plan.",
                    "workout_days": "Mon, Wed, Fri",
                },
            )
            personal, _ = WorkoutPlan.objects.get_or_create(
                member=member,
                name="Demo Full Body",
                plan_type="PERSONAL",
                defaults={
                    "goal": "General Fitness",
                    "description": "Fictional personal workout plan.",
                    "workout_days": "Sat",
                },
            )
            plan_exercises = exercises[group * 3 : group * 3 + 3]
            for workout_plan, chosen in [
                (plan, plan_exercises),
                (personal, [exercises[0], exercises[3], exercises[6]]),
            ]:
                for order, exercise in enumerate(chosen, start=1):
                    WorkoutPlanExercise.objects.get_or_create(
                        workout_plan=workout_plan,
                        exercise=exercise,
                        defaults={
                            "sets": 3,
                            "reps": 10,
                            "weight_kg": 10 + index + order * 5,
                            "order": order,
                        },
                    )
            for week, days_ago in enumerate([42, 28, 14, 7, 4, 2, 0]):
                WeightRecord.objects.get_or_create(
                    member=member,
                    recorded_date=anchor - timedelta(days=days_ago),
                    defaults={
                        "weight_kg": start_weight + direction * Decimal("0.3") * week,
                        "note": "Fictional demo progress record.",
                    },
                )
            for day in range(7):
                WaterIntake.objects.get_or_create(
                    member=member,
                    recorded_date=anchor - timedelta(days=day),
                    defaults={
                        "litres": Decimal("1.5") + Decimal("0.25") * ((index + day) % 5)
                    },
                )
            for number, days_ago in enumerate([17, 12, 8, 5, 3, 1]):
                started = timezone.make_aware(
                    datetime.combine(anchor - timedelta(days=days_ago), time(17))
                )
                workout, _ = WorkoutSession.objects.get_or_create(
                    member=member,
                    workout_plan=plan,
                    started_at=started,
                    defaults={
                        "completed_at": started + timedelta(minutes=40),
                        "notes": "Fictional demo workout. Duration/calories are not measured.",
                    },
                )
                for exercise in plan_exercises:
                    for set_number in range(1, 4):
                        WorkoutExerciseRecord.objects.get_or_create(
                            workout_session=workout,
                            exercise=exercise,
                            set_number=set_number,
                            defaults={
                                "sets": 1,
                                "reps": 10 if set_number < 3 else 8,
                                "weight_kg": Decimal(
                                    15 + index + number * 2 + set_number
                                ),
                            },
                        )
            for class_index in [index % 6, (index + 1) % 6]:
                session = classes[class_index]
                if not Booking.objects.filter(member=member, session=session).exists():
                    if session.is_full:
                        raise CommandError("A demo class is full; no data was changed.")
                    Booking.objects.create(member=member, session=session)
            self.stdout.write(f"Ready: {member.email} -> {coach.get_full_name()}")
        self.stdout.write(
            self.style.SUCCESS(
                "10 fictional members ready: 20 plans, 60 completed workouts, 70 weight records, 70 water records and 20 class bookings. Existing demo records and passwords were preserved."
            )
        )
