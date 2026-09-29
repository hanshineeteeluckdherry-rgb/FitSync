from django.core.management.base import BaseCommand
from workouts.models import Exercise

EXERCISES = {
    "CHEST": ["Barbell Bench Press", "Incline Barbell Bench Press", "Decline Barbell Bench Press", "Dumbbell Bench Press", "Incline Dumbbell Press", "Decline Dumbbell Press", "Machine Chest Press", "Smith Machine Bench Press", "Push-Up", "Wide-Grip Push-Up", "Incline Push-Up", "Decline Push-Up", "Cable Fly", "Low Cable Fly", "High Cable Fly", "Dumbbell Fly", "Incline Dumbbell Fly", "Pec Deck", "Chest Dip", "Svend Press"],
    "BACK": ["Deadlift", "Lat Pulldown", "Pull-Up", "Chin-Up", "Barbell Row", "Dumbbell Row", "Seated Cable Row", "T-Bar Row", "Chest-Supported Row", "Machine Row", "Straight-Arm Pulldown", "Single-Arm Cable Row", "Inverted Row", "Rack Pull", "Good Morning", "Back Extension", "Close-Grip Pulldown", "Wide-Grip Pulldown", "Meadows Row", "Kettlebell Row"],
    "SHOULDERS": ["Overhead Press", "Dumbbell Shoulder Press", "Arnold Press", "Machine Shoulder Press", "Lateral Raise", "Cable Lateral Raise", "Front Raise", "Plate Front Raise", "Rear Delt Fly", "Reverse Pec Deck", "Face Pull", "Upright Row", "Landmine Press", "Pike Push-Up", "Handstand Push-Up", "Dumbbell Y Raise", "Cable Y Raise", "Bus Driver", "Shrug", "Dumbbell Shrug"],
    "BICEPS": ["Barbell Curl", "Dumbbell Curl", "Hammer Curl", "Incline Dumbbell Curl", "Preacher Curl", "Cable Curl", "EZ-Bar Curl", "Concentration Curl", "Spider Curl", "Reverse Curl", "Zottman Curl", "Bayesian Cable Curl", "Machine Biceps Curl", "Cross-Body Hammer Curl", "Drag Curl", "Wide-Grip Barbell Curl", "Close-Grip Barbell Curl", "Alternating Dumbbell Curl", "Resistance Band Curl", "Chin-Up Biceps Focus"],
    "TRICEPS": ["Triceps Pushdown", "Rope Pushdown", "Overhead Cable Extension", "Dumbbell Overhead Extension", "Skull Crusher", "Close-Grip Bench Press", "Bench Dip", "Parallel Bar Dip", "Diamond Push-Up", "Cable Kickback", "Dumbbell Kickback", "Single-Arm Pushdown", "Reverse-Grip Pushdown", "EZ-Bar Overhead Extension", "JM Press", "Machine Triceps Extension", "Resistance Band Pushdown", "Lying Dumbbell Extension", "Cross-Body Cable Extension", "Tate Press"],
    "LEGS": ["Barbell Squat", "Front Squat", "Goblet Squat", "Leg Press", "Hack Squat", "Walking Lunge", "Reverse Lunge", "Bulgarian Split Squat", "Leg Extension", "Leg Curl", "Romanian Deadlift", "Sumo Deadlift", "Step-Up", "Box Squat", "Sissy Squat", "Wall Sit", "Single-Leg Press", "Nordic Hamstring Curl", "Standing Calf Raise", "Seated Calf Raise"],
    "GLUTES": ["Hip Thrust", "Barbell Glute Bridge", "Glute Bridge", "Cable Kickback Glute Focus", "Donkey Kick", "Fire Hydrant", "Sumo Squat", "Curtsy Lunge", "Step-Up Glute Focus", "Bulgarian Split Squat Glute Focus", "Cable Pull-Through", "Kettlebell Swing", "Single-Leg Hip Thrust", "Frog Pump", "Banded Lateral Walk", "Clamshell", "Reverse Hyperextension", "Romanian Deadlift Glute Focus", "Smith Machine Hip Thrust", "Abduction Machine"],
    "CORE": ["Plank", "Side Plank", "Crunch", "Bicycle Crunch", "Reverse Crunch", "Hanging Knee Raise", "Hanging Leg Raise", "Russian Twist", "Mountain Climber", "Dead Bug", "Bird Dog", "Ab Wheel Rollout", "Cable Crunch", "Pallof Press", "V-Up", "Toe Touch", "Flutter Kick", "Leg Raise", "Hollow Body Hold", "Farmer Carry"],
}

DIFFICULTIES = ["BEGINNER", "INTERMEDIATE", "INTERMEDIATE", "ADVANCED", "BEGINNER"]
INTENSITIES = ["MODERATE", "HIGH", "HIGH", "VERY_HIGH", "LOW"]
SECONDARY = {
    "CHEST": "Triceps, Shoulders", "BACK": "Biceps, Rear Delts", "SHOULDERS": "Triceps, Upper Back",
    "BICEPS": "Forearms", "TRICEPS": "Shoulders, Chest", "LEGS": "Glutes, Hamstrings, Calves",
    "GLUTES": "Hamstrings, Legs", "CORE": "Obliques, Lower Back",
}

class Command(BaseCommand):
    help = "Add 160 FitSync exercises (20 per muscle group)."

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0
        for category, names in EXERCISES.items():
            for index, name in enumerate(names):
                exercise, created = Exercise.objects.update_or_create(
                    name=name,
                    category=category,
                    defaults={
                        "secondary_muscles": SECONDARY[category],
                        "equipment": self.get_equipment(name, index),
                        "difficulty": DIFFICULTIES[index % len(DIFFICULTIES)],
                        "intensity": INTENSITIES[index % len(INTENSITIES)],
                        "description": self.get_description(name, category),
                        "instructions": self.get_instructions(name, category),
                        "is_active": True,
                    },
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
        self.stdout.write(self.style.SUCCESS(f"Exercise library ready: {created_count} created, {updated_count} updated. Total active: {Exercise.objects.filter(is_active=True).count()}."))


    def get_description(self, name, category):
        focus = {
            "CHEST": "chest strength and pressing control",
            "BACK": "back strength, posture and pulling control",
            "SHOULDERS": "shoulder strength and upper-body stability",
            "BICEPS": "biceps strength and elbow-flexion control",
            "TRICEPS": "triceps strength and pressing support",
            "LEGS": "lower-body strength and leg development",
            "GLUTES": "glute strength and hip extension",
            "CORE": "core stability, control and trunk strength",
        }
        return f"{name} is used to develop {focus[category]}. Add it to a plan and adjust sets, repetitions, weight or duration to suit your goal."

    def get_instructions(self, name, category):
        return (
            f"Set up safely for {name}. Keep a controlled tempo and stable posture, "
            "complete the planned repetitions with good form, and stop if the movement causes pain."
        )

    def get_equipment(self, name, index):
        text = name.lower()
        if "dumbbell" in text or "arnold" in text:
            return "DUMBBELL"
        if "cable" in text or "pushdown" in text or "pulldown" in text or "face pull" in text:
            return "CABLE"
        if "machine" in text or "pec deck" in text or "leg press" in text or "leg extension" in text or "leg curl" in text:
            return "MACHINE"
        if "kettlebell" in text:
            return "KETTLEBELL"
        if "band" in text:
            return "BAND"
        if any(word in text for word in ["push-up", "pull-up", "chin-up", "plank", "crunch", "dip", "wall sit", "bird dog", "dead bug"]):
            return "BODYWEIGHT"
        if any(word in text for word in ["barbell", "deadlift", "squat", "good morning"]):
            return "BARBELL"
        return ["BARBELL", "DUMBBELL", "BODYWEIGHT", "CABLE", "MACHINE"][index % 5]
