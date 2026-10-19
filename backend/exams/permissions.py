from rest_framework.permissions import BasePermission
from accounts.permissions import membership_for
from students.permissions import assignments, can_manage


class EnterMarks(BasePermission):
    def has_object_permission(self, request, view, obj):
        student, exam_subject = obj
        if can_manage(request, student):
            return True
        if membership_for(request).role != "TEACHER":
            return False
        if not hasattr(request, "mark_assignments"):
            request.mark_assignments = list(
                assignments(request).values(
                    "class_group_id", "subject_id", "division_id"
                )
            )
        return any(
            row["class_group_id"] == student.class_group_id
            and row["subject_id"] == exam_subject.subject_id
            and (
                row["division_id"] is None or row["division_id"] == student.division_id
            )
            for row in request.mark_assignments
        )
