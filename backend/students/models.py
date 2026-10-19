from django.conf import settings
from django.db import models
from django.db.models import Q


class TenantRecord(models.Model):
    institution = models.ForeignKey(
        "institutions.Institution", on_delete=models.CASCADE
    )

    class Meta:
        abstract = True


class AcademicYear(TenantRecord):
    name = models.CharField(max_length=50)
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ["-starts_on", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "name"], name="unique_academic_year"
            ),
            models.UniqueConstraint(
                fields=["institution"],
                condition=Q(is_current=True),
                name="one_current_year",
            ),
            models.CheckConstraint(
                condition=Q(ends_on__gte=models.F("starts_on")),
                name="academic_year_order",
            ),
        ]


class ClassGroup(TenantRecord):
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="class_groups"
    )
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "academic_year", "name"],
                name="unique_class_group",
            )
        ]
        indexes = [models.Index(fields=["institution", "academic_year"])]


class Division(TenantRecord):
    class_group = models.ForeignKey(
        ClassGroup, on_delete=models.PROTECT, related_name="divisions"
    )
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "class_group", "name"], name="unique_division"
            )
        ]


class Subject(TenantRecord):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "code"], name="unique_subject_code"
            )
        ]


class TeacherAssignment(TenantRecord):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="teaching_assignments",
    )
    class_group = models.ForeignKey(
        ClassGroup, on_delete=models.PROTECT, related_name="teacher_assignments"
    )
    division = models.ForeignKey(
        Division, null=True, blank=True, on_delete=models.PROTECT
    )
    subject = models.ForeignKey(
        Subject, null=True, blank=True, on_delete=models.PROTECT
    )
    is_class_teacher = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(is_class_teacher=True) | Q(subject__isnull=False),
                name="assignment_has_duty",
            ),
            models.UniqueConstraint(
                fields=[
                    "institution",
                    "teacher",
                    "class_group",
                    "division",
                    "subject",
                    "is_class_teacher",
                ],
                nulls_distinct=False,
                name="unique_teacher_assignment",
            ),
        ]
        indexes = [models.Index(fields=["institution", "teacher", "class_group"])]


class Student(TenantRecord):
    interest_tags = models.JSONField(default=list)
    admission_number = models.CharField(max_length=100)
    name = models.CharField(max_length=150, db_index=True)
    date_of_birth = models.DateField(null=True, blank=True)
    class_group = models.ForeignKey(
        ClassGroup, on_delete=models.PROTECT, related_name="students"
    )
    division = models.ForeignKey(
        Division,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="students",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="student_records",
    )
    joined_on = models.DateField()
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def has_login(self):
        return self.user_id is not None

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "admission_number"], name="unique_admission"
            ),
            models.UniqueConstraint(
                fields=["institution", "user"],
                condition=Q(user__isnull=False),
                name="unique_student_account",
            ),
        ]
        indexes = [
            models.Index(fields=["institution", "class_group", "division"]),
            models.Index(fields=["institution", "deleted_at", "name"]),
        ]


class ParentStudentLink(TenantRecord):
    parent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="children_links",
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="parent_links"
    )
    relationship = models.CharField(max_length=50, default="Guardian")
    phone = models.CharField(max_length=25, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "parent", "student"], name="unique_parent_child"
            )
        ]
        indexes = [
            models.Index(fields=["institution", "student"]),
            models.Index(fields=["institution", "parent"]),
        ]
