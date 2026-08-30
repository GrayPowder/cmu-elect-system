from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


VOTER_CATEGORY_CHOICES = [
    ("student", "Student"),
    ("alumni", "Alumni"),
    ("faculty", "Faculty"),
]


class Profile(models.Model):
    """CMU voter profile attached to Django's built-in User model.

    Django User remains the authentication source of truth. Profile stores
    CMU-specific voter information and account workflow fields.
    """

    ROLE_CHOICES = VOTER_CATEGORY_CHOICES
    ACCOUNT_STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        db_index=True,
        help_text="Voter category: Student, Alumni, or Faculty.",
    )
    cmu_email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    account_status = models.CharField(
        max_length=10,
        choices=ACCOUNT_STATUS_CHOICES,
        default="active",
        db_index=True,
    )
    must_change_password = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def login_identifier(self):
        return self.cmu_email

    @property
    def voter_category(self):
        return self.role

    def clean(self):
        self.cmu_email = self.cmu_email.strip().lower()
        if self.account_status == "active" and not self.user.is_active:
            raise ValidationError("An active voter profile requires an active Django user account.")

    def __str__(self):
        return f"{self.full_name or self.user.get_username()} - {self.get_role_display()}"


class Election(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_ENDED = "ended"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_ENDED, "Ended"),
    ]

    # Backward-compatible alias for existing serializers/code.
    ROLE_CHOICES = VOTER_CATEGORY_CHOICES

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    eligible_voter_category = models.CharField(
        max_length=20,
        choices=VOTER_CATEGORY_CHOICES,
        db_index=True,
    )
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start_datetime__lt=models.F("end_datetime")),
                name="election_start_before_end",
            )
        ]

    @property
    def audience(self):
        """Backward-compatible name used by the existing Phase 1 API."""
        return self.eligible_voter_category

    @property
    def effective_status(self):
        """Current status used by the application, derived from status and schedule."""
        if self.status == self.STATUS_ENDED or timezone.now() > self.end_datetime:
            return self.STATUS_ENDED
        return self.STATUS_ACTIVE

    @property
    def schedule_status(self):
        """Current voter-facing schedule state without changing the stored status field."""
        now = timezone.now()
        if self.status == self.STATUS_ENDED or now > self.end_datetime:
            return self.STATUS_ENDED
        if now < self.start_datetime:
            return "not_started"
        return self.STATUS_ACTIVE

    @property
    def is_open(self):
        """Voting is allowed only while the election is active and inside its schedule."""
        now = timezone.now()
        return (
            self.status == self.STATUS_ACTIVE
            and self.start_datetime <= now <= self.end_datetime
        )

    def clean(self):
        if self.start_datetime >= self.end_datetime:
            raise ValidationError("Election start date/time must be before the end date/time.")

    def __str__(self):
        return self.name


class Position(models.Model):
    election = models.ForeignKey(
        Election,
        on_delete=models.CASCADE,
        related_name="positions",
    )
    name = models.CharField(max_length=80)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["election", "name"],
                name="unique_position_name_per_election",
            )
        ]

    def clean(self):
        if self.election_id is None:
            return
        if not self.name.strip():
            raise ValidationError("Position name cannot be empty.")

    def __str__(self):
        return self.name


class Candidate(models.Model):
    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name="candidates",
    )
    name = models.CharField(max_length=120)
    department = models.CharField(max_length=120, blank=True)
    platform = models.TextField(blank=True)
    gwa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    party_list = models.CharField(max_length=120, blank=True)
    photo = models.ImageField(upload_to="candidates/", null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["position", "name"],
                name="unique_candidate_name_per_position",
            )
        ]

    @property
    def election(self):
        """Logical election relationship through Position."""
        return self.position.election

    def clean(self):
        if self.position_id is None:
            return
        if not self.name.strip():
            raise ValidationError("Candidate name cannot be empty.")

    def __str__(self):
        return self.name


class Vote(models.Model):
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="votes")
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name="votes")
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name="votes")
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="votes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["voter", "election", "position"],
                name="one_vote_per_voter_position",
            )
        ]

    def clean(self):
        errors = {}

        if self.position_id and self.election_id:
            if self.position.election_id != self.election_id:
                errors["position"] = "The position does not belong to the selected election."

        if self.candidate_id and self.position_id:
            if self.candidate.position_id != self.position_id:
                errors["candidate"] = "The candidate does not belong to the selected position."

        if self.candidate_id and self.election_id:
            if self.candidate.position.election_id != self.election_id:
                errors["candidate"] = "The candidate does not belong to the selected election."

        if self.voter_id and self.election_id:
            try:
                voter_role = self.voter.profile.role
            except Profile.DoesNotExist:
                voter_role = None
            if voter_role and voter_role != self.election.eligible_voter_category:
                errors["voter"] = "The voter is not eligible for this election."

        if errors:
            raise ValidationError(errors)


class AuditLog(models.Model):
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    target_model = models.CharField(max_length=100, blank=True)
    target_object_id = models.CharField(max_length=64, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-timestamp", "-id"]

    def __str__(self):
        actor = self.actor.get_username() if self.actor else "System"
        return f"{actor} - {self.action}"


class PasswordResetRequest(models.Model):
    """Short-lived password-reset challenge used by the React reset flow."""

    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=64)
    reset_token_hash = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Password reset for {self.email}"
