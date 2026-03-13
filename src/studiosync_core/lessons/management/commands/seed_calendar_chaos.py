from datetime import date, datetime, timedelta
from decimal import Decimal
import random

from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker

from studiosync_core.core.models import Band, Student, Studio, Teacher
from studiosync_core.inventory.models import PracticeRoom
from studiosync_core.lessons.models import Lesson, LessonNote

fake = Faker()

class Command(BaseCommand):
    help = "Generate random calendar events (chaos) to make the schedule look busy."

    def add_arguments(self, parser):
        parser.add_argument(
            "--back",
            type=int,
            default=30,
            help="Number of days back to seed events (default: 30)",
        )
        parser.add_argument(
            "--forward",
            type=int,
            default=60,
            help="Number of days forward to seed events (default: 60)",
        )
        parser.add_argument(
            "--density",
            type=float,
            default=0.7,
            help="Probability density of events (0.0 to 1.0, default: 0.7)",
        )

    def handle(self, *args, **options):
        days_back = options["back"]
        days_forward = options["forward"]
        density = options["density"]

        self.stdout.write(f"🎲 Generating calendar chaos for the next {days_forward} days and past {days_back} days...")

        # 1. Get existing data
        studio = Studio.objects.first()
        if not studio:
            self.stdout.write(self.style.ERROR("❌ Error: No studio found. Please run seed_data.py first."))
            return

        teachers = list(Teacher.objects.filter(studio=studio))
        students = list(Student.objects.filter(studio=studio))
        bands = list(Band.objects.filter(studio=studio))
        rooms = list(PracticeRoom.objects.all())

        if not teachers or not students:
            self.stdout.write(self.style.ERROR("❌ Error: No teachers or students found. Please run seed_data.py first."))
            return

        # 2. Define event types and their characteristics
        EVENT_TYPES = [
            {"type": "workshop", "name": "Masterclass", "duration": 120, "prob": 0.05},
            {"type": "recital", "name": "Studio Recital", "duration": 180, "prob": 0.02},
            {"type": "group", "name": "Group Theory Class", "duration": 60, "prob": 0.1},
            {"type": "makeup", "name": "Makeup Lesson", "duration": 45, "prob": 0.15},
            {"type": "private", "name": "Ad-hoc Private Session", "duration": 60, "prob": 0.2},
        ]

        total_events = 0
        start_date = timezone.now().date() - timedelta(days=days_back)
        end_date = timezone.now().date() + timedelta(days=days_forward)
        
        current_date = start_date
        while current_date <= end_date:
            num_events_today = random.randint(0, 5) if random.random() < density else 0
            
            for _ in range(num_events_today):
                event_config = random.choices(
                    EVENT_TYPES, 
                    weights=[e["prob"] for e in EVENT_TYPES], 
                    k=1
                )[0]
                
                teacher = random.choice(teachers)
                student = None
                band = None
                
                if event_config["type"] == "private" or event_config["type"] == "makeup":
                    student = random.choice(students)
                elif event_config["type"] == "group" or event_config["type"] == "workshop":
                    student = random.choice(students)
                
                if bands and random.random() < 0.2:
                    band = random.choice(bands)
                    student = None
                
                room = random.choice(rooms) if rooms else None
                hour = random.randint(9, 19)
                minute = random.choice([0, 15, 30, 45])
                
                scheduled_start = timezone.make_aware(
                    datetime.combine(current_date, datetime.min.time().replace(hour=hour, minute=minute))
                )
                scheduled_end = scheduled_start + timedelta(minutes=event_config["duration"])
                
                # Check for overlaps
                if Lesson.objects.filter(
                    teacher=teacher,
                    scheduled_start__lt=scheduled_end,
                    scheduled_end__gt=scheduled_start
                ).exists():
                    continue

                status = "scheduled"
                if current_date < timezone.now().date():
                    status = random.choice(["completed", "no_show", "cancelled"])
                elif current_date == timezone.now().date():
                    if scheduled_start < timezone.now():
                        status = "completed"
                    else:
                        status = "scheduled"

                lesson, created = Lesson.objects.get_or_create(
                    studio=studio,
                    teacher=teacher,
                    scheduled_start=scheduled_start,
                    defaults={
                        "student": student,
                        "band": band,
                        "room": room,
                        "scheduled_end": scheduled_end,
                        "lesson_type": event_config["type"],
                        "status": status,
                        "rate": teacher.hourly_rate or Decimal("50.00"),
                        "summary": f"{event_config['name']} for {student.user.get_full_name() if student else (band.name if band else 'General')}",
                        "location": room.name if room else "Main Hall",
                    }
                )
                
                if created:
                    total_events += 1
                    # Enhance lesson note with realistic musical data
                    MUSICAL_PIECES = ["Für Elise", "Moonlight Sonata", "Clair de Lune", "Canon in D", "Autumn Leaves", "Imagine"]
                    TECHNIQUES = ["Major Scales", "Arpeggios", "Vibrato", "Sight Reading", "Ear Training"]
                    
                    if status == "completed":
                        pieces = random.sample(MUSICAL_PIECES, random.randint(1, 2))
                        LessonNote.objects.create(
                            lesson=lesson,
                            teacher=teacher,
                            content=f"Today we focused on {', '.join(pieces)}. {fake.paragraph(nb_sentences=2)}",
                            pieces_practiced=pieces,
                            practice_assignments=f"Focus on {random.choice(TECHNIQUES)} and the first 16 bars of {pieces[0]}.",
                            strengths=f"Good {random.choice(TECHNIQUES)} control.",
                            progress_rating=random.randint(3, 5)
                        )

            current_date += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f"✅ Successfully added {total_events} random events to the calendar."))
        self.stdout.write(self.style.SUCCESS("🎉 Chaos seeding complete!"))
