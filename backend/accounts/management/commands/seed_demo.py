import os
from datetime import date
from students.models import (
    AcademicYear,
    ClassGroup,
    Division,
    Subject,
    TeacherAssignment,
    Student,
    ParentStudentLink,
)
from medical.models import StudentMedical
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from accounts.models import User, Membership
from institutions.models import Institution
from institutions.type_config import TYPE_CONFIG


class Command(BaseCommand):
    help = "Seed institutions, roles, classes, students, parents and medical cards for development."

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.getenv("DEMO_PASSWORD")
        if not password or len(password) < 12:
            raise CommandError(
                "Set DEMO_PASSWORD to a local-only password of at least 12 characters."
            )
        for kind, config in TYPE_CONFIG.items():
            institution, _ = Institution.objects.get_or_create(
                name=f"Development {kind.title()}", type=kind
            )
            for role in config["roles"]:
                email = f"{role.lower()}@{kind.lower()}.example.test"
                user = User.objects.filter(email=email).first()
                if not user:
                    user = User.objects.create_user(
                        email, password, name=config["roles"][role]
                    )
                Membership.objects.get_or_create(
                    user=user, institution=institution, role=role
                )
                self.stdout.write(f"{kind} {role}: {email}")
            teacher = User.objects.get(email=f"teacher@{kind.lower()}.example.test")
            Membership.objects.get_or_create(
                user=teacher, institution=institution, role="PARENT"
            )
            year, _ = AcademicYear.objects.get_or_create(
                institution=institution,
                name="2026–27",
                defaults={
                    "starts_on": date(2026, 6, 1),
                    "ends_on": date(2027, 3, 31),
                    "is_current": not AcademicYear.objects.filter(
                        institution=institution, is_current=True
                    ).exists(),
                },
            )
            group, _ = ClassGroup.objects.get_or_create(
                institution=institution,
                academic_year=year,
                name="8" if kind != "TUITION" else "Evening Mathematics",
            )
            other_group, _ = ClassGroup.objects.get_or_create(
                institution=institution,
                academic_year=year,
                name="9" if kind != "TUITION" else "Weekend Science",
            )
            division, _ = Division.objects.get_or_create(
                institution=institution,
                class_group=group,
                name="A" if kind != "MADRASA" else "Level 1",
            )
            subject, _ = Subject.objects.get_or_create(
                institution=institution,
                code="MATH" if kind != "MADRASA" else "ISLAM",
                defaults={
                    "name": "Mathematics" if kind != "MADRASA" else "Islamic studies"
                },
            )
            TeacherAssignment.objects.get_or_create(
                institution=institution,
                teacher=teacher,
                class_group=group,
                division=None if kind == "TUITION" else division,
                subject=None,
                is_class_teacher=True,
            )
            for prefix in ["subject", "relief"]:
                email = f"{prefix}@{kind.lower()}.example.test"
                person = User.objects.filter(email=email).first()
                if not person:
                    person = User.objects.create_user(
                        email,
                        password,
                        name="Subject Teacher"
                        if prefix == "subject"
                        else "Relief Teacher",
                    )
                Membership.objects.get_or_create(
                    institution=institution, user=person, role="TEACHER"
                )
                if prefix == "subject":
                    TeacherAssignment.objects.get_or_create(
                        institution=institution,
                        teacher=person,
                        class_group=group,
                        division=division,
                        subject=subject,
                        is_class_teacher=False,
                    )
                self.stdout.write(f"{kind} TEACHER: {email}")
            parent = User.objects.get(email=f"parent@{kind.lower()}.example.test")
            for index, name in enumerate(
                ["Amina Rahman", "Bilal Rahman", "Fathima Noor"], start=1
            ):
                student, _ = Student.objects.get_or_create(
                    institution=institution,
                    admission_number=f"{kind[:2]}-2026-{index:03}",
                    defaults={
                        "name": name,
                        "class_group": group if index != 2 else other_group,
                        "division": division if index != 2 else None,
                        "date_of_birth": date(2012 + index, 2, 10),
                        "joined_on": date(2026, 6, 1),
                        "user": User.objects.get(email="student@school.example.test")
                        if kind == "SCHOOL" and index == 1
                        else None,
                    },
                )
                ParentStudentLink.objects.get_or_create(
                    institution=institution,
                    parent=parent,
                    student=student,
                    defaults={"phone": "+910000000000", "relationship": "Guardian"},
                )
                if index == 1:
                    ParentStudentLink.objects.get_or_create(
                        institution=institution,
                        parent=teacher,
                        student=student,
                        defaults={"relationship": "Guardian"},
                    )
                StudentMedical.objects.get_or_create(
                    institution=institution,
                    student=student,
                    defaults={
                        "blood_group": "O+",
                        "allergies": "Penicillin" if index == 1 else "",
                        "conditions": "Asthma" if index == 1 else "",
                        "doctor": "Development clinic (sample)",
                        "emergency_contacts": [
                            {
                                "name": "Sample guardian — test number",
                                "relationship": "Guardian",
                                "phone": "+910000000000",
                            }
                        ],
                    },
                )
            from django.utils import timezone
            from datetime import timedelta
            from attendance.models import Attendance
            from exams.models import Exam, ExamSubject, Mark
            from events.models import Event, EventEligibility, EventParticipation
            from notices.models import Notice
            from madrasa.models import HifzProgress, TimetableEntry
            from tuition.models import FeeInstallment, TestSeries, TestResult

            roster = Student.objects.filter(
                institution=institution, class_group=group, deleted_at=None
            )
            for pupil in roster:
                for offset in range(7):
                    Attendance.objects.get_or_create(
                        institution=institution,
                        student=pupil,
                        date=timezone.localdate() - timedelta(days=offset),
                        session="DAY",
                        defaults={
                            "status": "ABSENT" if offset in [2, 4] else "PRESENT",
                            "marked_by": teacher,
                        },
                    )
            admin_user = User.objects.get(email=f"admin@{kind.lower()}.example.test")
            for number in [1, 2]:
                exam, _ = Exam.objects.get_or_create(
                    institution=institution,
                    class_group=group,
                    name=f"Term {number}",
                    defaults={"date": date(2026, 9 + number, 1), "published": True},
                )
                exam_subject, _ = ExamSubject.objects.get_or_create(
                    institution=institution,
                    exam=exam,
                    subject=subject,
                    defaults={"max_marks": 100},
                )
                for pupil in roster:
                    Mark.objects.get_or_create(
                        institution=institution,
                        student=pupil,
                        exam_subject=exam_subject,
                        defaults={
                            "score": 90 if number == 1 else 65,
                            "entered_by": teacher,
                        },
                    )
            event, _ = Event.objects.get_or_create(
                institution=institution,
                name="Annual learning exhibition",
                academic_year=year,
                defaults={
                    "starts_on": date(2026, 12, 1),
                    "description": "Students share their learning with families.",
                },
            )
            EventEligibility.objects.get_or_create(
                institution=institution, event=event, class_group=group
            )
            first = roster.first()
            if first:
                EventParticipation.objects.get_or_create(
                    institution=institution,
                    event=event,
                    student=first,
                    defaults={"status": "PARTICIPATED"},
                )
            Notice.objects.get_or_create(
                institution=institution,
                title="Office hours",
                defaults={
                    "body": "The institution office is open from 9am to 4pm on working days.",
                    "audience": "ALL",
                    "created_by": admin_user,
                },
            )
            if kind == "MADRASA":
                for pupil in roster:
                    HifzProgress.objects.get_or_create(
                        institution=institution,
                        student=pupil,
                        date=timezone.localdate(),
                        surah=1,
                        juz=1,
                        defaults={
                            "lines": 7,
                            "revision_status": "SECURE",
                            "recorded_by": teacher,
                        },
                    )
                for lesson_kind, start, end in [
                    ("SCHOOL", "09:00", "10:00"),
                    ("MADRASA", "17:00", "18:00"),
                ]:
                    TimetableEntry.objects.get_or_create(
                        institution=institution,
                        class_group=group,
                        kind=lesson_kind,
                        weekday=0,
                        starts_at=start,
                        defaults={"ends_at": end, "label": "Learning session"},
                    )
            if kind == "TUITION":
                series, _ = TestSeries.objects.get_or_create(
                    institution=institution,
                    class_group=group,
                    name="Weekly practice 1",
                    defaults={
                        "subject": subject,
                        "date": timezone.localdate(),
                        "max_marks": 100,
                        "published": True,
                    },
                )
                for index, pupil in enumerate(roster):
                    FeeInstallment.objects.get_or_create(
                        institution=institution,
                        student=pupil,
                        label="October tuition",
                        defaults={"amount": 1000, "due_date": date(2026, 10, 15)},
                    )
                    TestResult.objects.get_or_create(
                        institution=institution,
                        series=series,
                        student=pupil,
                        defaults={
                            "score": max(0, 95 - index * 5),
                            "recorded_by": teacher,
                        },
                    )
        self.stdout.write(
            self.style.SUCCESS(
                "All phase records prepared; existing passwords and records were preserved."
            )
        )
