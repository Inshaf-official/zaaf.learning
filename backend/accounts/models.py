from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        user = self.model(
            email=self.normalize_email(email).lower() if email else None, **extra
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True)
        return self.create_user(email, password, **extra)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True, null=True, blank=True)
    login_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    name = models.CharField(max_length=150)
    must_change_password = models.BooleanField(default=False)
    auth_version = models.PositiveIntegerField(default=0)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]
    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("email"), name="unique_email_case_insensitive"
            ),
            models.CheckConstraint(
                condition=models.Q(email__isnull=False)
                | models.Q(login_id__isnull=False),
                name="user_has_identity",
            ),
        ]


class Membership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        TEACHER = "TEACHER", "Teacher"
        PARENT = "PARENT", "Parent"
        STUDENT = "STUDENT", "Student"

    institution = models.ForeignKey(
        "institutions.Institution", on_delete=models.CASCADE
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    invited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "user", "role"], name="unique_membership"
            )
        ]
        indexes = [models.Index(fields=["institution", "role", "is_active"])]


class LoginAttempt(models.Model):
    # Global authentication security metadata cannot have a tenant before identity is resolved.
    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True)
    updated_at = models.DateTimeField(auto_now=True)


class PasswordGrant(models.Model):
    institution = models.ForeignKey(
        "institutions.Institution", on_delete=models.CASCADE
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True)


class AuditLog(models.Model):
    institution = models.ForeignKey(
        "institutions.Institution", on_delete=models.CASCADE
    )
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80)
    object = models.CharField(max_length=200)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True)

    class Meta:
        indexes = [models.Index(fields=["institution", "timestamp"])]
