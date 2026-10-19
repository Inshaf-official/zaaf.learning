from rest_framework import serializers
from .models import Institution


class SettingsSerializer(serializers.ModelSerializer):
    has_logo = serializers.SerializerMethodField()

    class Meta:
        model = Institution
        fields = [
            "id",
            "name",
            "type",
            "address",
            "language",
            "attendance_rules",
            "grading_scale",
            "has_logo",
        ]
        read_only_fields = ["id", "type", "has_logo"]

    def get_has_logo(self, obj) -> bool:
        return bool(obj.logo)

    def validate_attendance_rules(self, value):
        if not isinstance(value, dict) or set(value) - {
            "low_threshold",
            "late_edit_policy",
            "sessions",
            "marks_drop_threshold",
        }:
            raise serializers.ValidationError("Unrecognized attendance setting.")
        for key in ["low_threshold", "marks_drop_threshold"]:
            if key in value and (
                isinstance(value[key], bool)
                or not isinstance(value[key], (int, float))
                or not 0 <= value[key] <= 100
            ):
                raise serializers.ValidationError(f"{key} must be between 0 and 100.")
        if value.get("late_edit_policy", "ADMIN_ONLY") not in ["ADMIN_ONLY", "BLOCK"]:
            raise serializers.ValidationError("Choose ADMIN_ONLY or BLOCK.")
        sessions = value.get("sessions", ["DAY"])
        import re

        if (
            not isinstance(sessions, list)
            or not sessions
            or len(sessions) > 10
            or any(
                not isinstance(x, str) or not re.fullmatch(r"[A-Z0-9_-]{1,40}", x)
                for x in sessions
            )
        ):
            raise serializers.ValidationError("Choose 1–10 valid session codes.")
        return {**self.instance.attendance_rules, **value}

    def validate_grading_scale(self, value):
        if not isinstance(value, list) or not 1 <= len(value) <= 20:
            raise serializers.ValidationError("Provide 1–20 grade thresholds.")
        cleaned = []
        for row in value:
            if (
                not isinstance(row, dict)
                or set(row) != {"min", "grade"}
                or not isinstance(row["min"], (int, float))
                or isinstance(row["min"], bool)
                or not 0 <= row["min"] <= 100
                or not isinstance(row["grade"], str)
                or not 1 <= len(row["grade"]) <= 10
            ):
                raise serializers.ValidationError(
                    "Each threshold needs min (0–100) and grade (1–10 characters)."
                )
            cleaned.append(row)
        if (
            len({r["min"] for r in cleaned}) != len(cleaned)
            or min(r["min"] for r in cleaned) != 0
        ):
            raise serializers.ValidationError(
                "Thresholds must be unique and include zero."
            )
        return sorted(cleaned, key=lambda r: r["min"], reverse=True)
