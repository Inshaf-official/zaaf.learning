from django.db.models import Exists, OuterRef, Q
from rest_framework.permissions import BasePermission, SAFE_METHODS
from accounts.permissions import membership_for
from .models import TeacherAssignment, Student


def assignments(request, class_teacher=False):
    member = membership_for(request)
    query = TeacherAssignment.objects.filter(
        institution=member.institution,
        teacher=request.user,
        teacher__is_active=True,
        teacher__memberships__institution=member.institution,
        teacher__memberships__role="TEACHER",
        teacher__memberships__is_active=True,
    )
    return query.filter(is_class_teacher=True) if class_teacher else query


def annotated_students(request):
    member = membership_for(request)
    scope = Q(division__isnull=True) | Q(division_id=OuterRef("division_id"))
    return (
        Student.objects.filter(institution=member.institution)
        .select_related("class_group__academic_year", "division", "user")
        .annotate(
            assigned=Exists(
                assignments(request)
                .filter(class_group_id=OuterRef("class_group_id"))
                .filter(scope)
            ),
            class_teacher=Exists(
                assignments(request, True)
                .filter(class_group_id=OuterRef("class_group_id"))
                .filter(scope)
            ),
            linked_parent=Exists(
                request.user.children_links.filter(
                    institution=member.institution, student_id=OuterRef("pk")
                )
            ),
        )
    )


def can_manage(request, student):
    member = membership_for(request)
    return member.role == "ADMIN" or (
        member.role == "TEACHER" and student.class_teacher
    )


def can_read(request, student):
    role = membership_for(request).role
    return (
        role == "ADMIN"
        or (role == "TEACHER" and student.assigned)
        or (role == "PARENT" and student.linked_parent)
        or (role == "STUDENT" and student.user_id == request.user.id)
    )


def visible_students(request):
    query = annotated_students(request).filter(deleted_at=None)
    role = membership_for(request).role
    if role == "ADMIN":
        return query
    if role == "TEACHER":
        return query.filter(assigned=True)
    if role == "PARENT":
        return query.filter(linked_parent=True)
    return query.filter(user=request.user) if role == "STUDENT" else query.none()


class StudentAccess(BasePermission):
    def has_permission(self, request, view):
        member = membership_for(request)
        if view.action == "create":
            return member.role == "ADMIN" or (
                member.role == "TEACHER" and assignments(request, True).exists()
            )
        return True

    def has_object_permission(self, request, view, obj):
        return (
            can_read(request, obj)
            if request.method in SAFE_METHODS
            else can_manage(request, obj)
        )


class AcademicAccess(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or membership_for(request).role == "ADMIN"
