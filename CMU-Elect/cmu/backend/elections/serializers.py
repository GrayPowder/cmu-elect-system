from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import Profile, Election, Position, Candidate, Vote, AuditLog, VOTER_CATEGORY_CHOICES


class VoterSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(source="full_name")
    identifier = serializers.CharField(source="user.username")
    email = serializers.EmailField(source="cmu_email")
    category = serializers.ChoiceField(source="role", choices=VOTER_CATEGORY_CHOICES)
    status = serializers.ChoiceField(source="account_status", choices=Profile.ACCOUNT_STATUS_CHOICES)
    created_date = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Profile
        fields = ["id", "name", "identifier", "email", "category", "status", "created_date"]
        read_only_fields = ["id", "created_date"]

    def validate_identifier(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Login identifier is required.")
        queryset = User.objects.filter(username__iexact=value)
        current_user = getattr(self.instance, "user", None)
        if current_user:
            queryset = queryset.exclude(pk=current_user.pk)
        if queryset.exists():
            raise serializers.ValidationError("That login identifier is already in use.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        queryset = Profile.objects.filter(cmu_email__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        user_queryset = User.objects.filter(email__iexact=value)
        current_user = getattr(self.instance, "user", None)
        if current_user:
            user_queryset = user_queryset.exclude(pk=current_user.pk)
        if queryset.exists() or user_queryset.exists():
            raise serializers.ValidationError("That email address is already assigned to another account.")
        return value

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        return value

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        new_identifier = user_data.get("username")
        if new_identifier is not None:
            instance.user.username = new_identifier.strip()

        new_email = validated_data.get("cmu_email")
        if new_email is not None:
            instance.user.email = new_email.strip().lower()

        if "account_status" in validated_data:
            new_status = validated_data["account_status"]
            instance.user.is_active = new_status == "active"

        instance.user.save(update_fields=["username", "email", "is_active"])
        return super().update(instance, validated_data)


class VoterCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    identifier = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    category = serializers.ChoiceField(choices=VOTER_CATEGORY_CHOICES)
    password = serializers.CharField(write_only=True, min_length=8)
    status = serializers.ChoiceField(choices=Profile.ACCOUNT_STATUS_CHOICES, default="active")

    def validate_identifier(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Login identifier is required.")
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That login identifier is already in use.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if Profile.objects.filter(cmu_email__iexact=value).exists() or User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("That email address is already assigned to another account.")
        return value

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        identifier = validated_data.pop("identifier")
        email = validated_data.pop("email")
        status_value = validated_data.pop("status")

        user = User.objects.create_user(
            username=identifier,
            email=email,
            password=password,
            is_active=status_value == "active",
        )
        return Profile.objects.create(
            user=user,
            full_name=validated_data["name"],
            cmu_email=email,
            role=validated_data["category"],
            account_status=status_value,
            must_change_password=True,
        )


class VoterPasswordResetSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        validate_password(attrs["password"])
        return attrs


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=Profile.ROLE_CHOICES)

    def validate(self, attrs):
        identifier = attrs["email"].strip()
        try:
            profile = Profile.objects.select_related("user").get(cmu_email__iexact=identifier)
        except Profile.DoesNotExist:
            try:
                profile = Profile.objects.select_related("user").get(user__username__iexact=identifier)
            except Profile.DoesNotExist:
                raise serializers.ValidationError("Invalid CMU email or password.")

        if profile.account_status != "active" or not profile.user.is_active:
            raise serializers.ValidationError("This account is inactive. Please contact the administrator.")

        user = authenticate(username=profile.user.username, password=attrs["password"])
        if not user:
            raise serializers.ValidationError("Invalid CMU email or password.")
        if profile.role != attrs["role"]:
            raise serializers.ValidationError("The selected account type does not match this account.")
        attrs["user"] = user
        return attrs


class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.is_active or not user.is_staff:
            raise serializers.ValidationError("Invalid administrator email or password.")

        authenticated_user = authenticate(username=user.username, password=attrs["password"])
        if not authenticated_user or not authenticated_user.is_staff:
            raise serializers.ValidationError("Invalid administrator email or password.")

        attrs["user"] = authenticated_user
        return attrs


class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = ["id", "name", "department", "platform", "gwa", "party_list", "photo"]


class PositionSerializer(serializers.ModelSerializer):
    candidates = CandidateSerializer(many=True, read_only=True)

    class Meta:
        model = Position
        fields = ["id", "name", "order", "candidates"]


class AdminCandidateSerializer(serializers.ModelSerializer):
    election_id = serializers.IntegerField(
        source="position.election.id",
        read_only=True
    )

    position_id = serializers.IntegerField(
        source="position.id",
        read_only=True
    )

    remove_photo = serializers.BooleanField(
        required=False,
        default=False,
        write_only=True
    )

    class Meta:
        model = Candidate
        fields = [
            "id",
            "election_id",
            "position_id",
            "name",
            "party_list",
            "platform",
            "photo",
            "remove_photo",
        ]
        read_only_fields = [
            "id",
            "election_id",
            "position_id",
        ]

    def create(self, validated_data):
        validated_data.pop("remove_photo", None)

        return Candidate.objects.create(**validated_data)

    def update(self, instance, validated_data):
        remove_photo = validated_data.pop("remove_photo", False)

        if remove_photo:
            if instance.photo:
                instance.photo.delete(save=False)
            instance.photo = None

        return super().update(instance, validated_data)

class AdminPositionSerializer(serializers.ModelSerializer):
    election_id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(
        max_length=80,
        required=True,
        allow_blank=False,
        trim_whitespace=True,
    )

    class Meta:
        model = Position
        fields = ["id", "election_id", "name", "order"]
        read_only_fields = ["id", "election_id"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                "Position name cannot be empty or contain only spaces."
            )
        return value

    def validate_order(self, value):
        if value < 0:
            raise serializers.ValidationError("Position order cannot be negative.")
        return value

    def validate(self, attrs):
        election = self.context.get("election")
        name = attrs.get("name", getattr(self.instance, "name", "")).strip()
        if not name:
            raise serializers.ValidationError({
                "name": "Position name cannot be empty or contain only spaces."
            })
        if election and Position.objects.filter(
            election=election, name__iexact=name
        ).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError({
                "name": "A position with this name already exists in this election."
            })
        return attrs


class ElectionSerializer(serializers.ModelSerializer):
    """Voter-facing election representation used by the dashboard and details page.

    The original Phase 1 fields are preserved, while Phase 9 adds the schedule
    and voter-facing status/availability information needed by the UI.
    """
    audience = serializers.CharField(source="eligible_voter_category", read_only=True)
    is_open = serializers.BooleanField(read_only=True)
    status = serializers.CharField(source="schedule_status", read_only=True)
    voting_availability = serializers.SerializerMethodField()
    positions = PositionSerializer(many=True, read_only=True)

    class Meta:
        model = Election
        fields = [
            "id",
            "name",
            "description",
            "audience",
            "start_datetime",
            "end_datetime",
            "status",
            "is_open",
            "voting_availability",
            "positions",
        ]

    def get_voting_availability(self, obj):
        if obj.schedule_status == "not_started":
            return "not_started"
        if obj.schedule_status == Election.STATUS_ENDED:
            return "ended"
        if obj.is_open:
            return "available"
        return "unavailable"


class BallotItemSerializer(serializers.Serializer):
    position_id = serializers.IntegerField(min_value=1)
    candidate_id = serializers.IntegerField(min_value=1)


class BallotSubmissionSerializer(serializers.Serializer):
    election_id = serializers.IntegerField(min_value=1)
    votes = BallotItemSerializer(many=True, allow_empty=False)

    def validate_votes(self, value):
        position_ids = [item["position_id"] for item in value]
        if len(position_ids) != len(set(position_ids)):
            raise serializers.ValidationError("Only one candidate may be selected for each position.")
        return value


class AdminElectionSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        max_length=120,
        required=True,
        allow_blank=False,
        trim_whitespace=True,
    )
    eligible_voter_category = serializers.ChoiceField(choices=VOTER_CATEGORY_CHOICES)
    status = serializers.SerializerMethodField()
    is_open = serializers.BooleanField(read_only=True)
    created_date = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Election
        fields = [
            "id",
            "name",
            "description",
            "start_datetime",
            "end_datetime",
            "eligible_voter_category",
            "status",
            "is_open",
            "created_date",
        ]
        read_only_fields = ["id", "status", "is_open", "created_date"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                "Election name cannot be empty or contain only spaces."
            )
        return value

    def validate(self, attrs):
        start = attrs.get("start_datetime", getattr(self.instance, "start_datetime", None))
        end = attrs.get("end_datetime", getattr(self.instance, "end_datetime", None))
        if start and end and start >= end:
            raise serializers.ValidationError({
                "end_datetime": "Election end date/time must be after the start date/time."
            })
        return attrs

    def get_status(self, obj):
        return obj.effective_status


class VoteSerializer(serializers.Serializer):
    position_id = serializers.IntegerField()
    candidate_id = serializers.IntegerField()


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context["request"].user

        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": "Current password is incorrect."})

        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        if attrs["current_password"] == attrs["new_password"]:
            raise serializers.ValidationError({"new_password": "New password must be different from your current password."})

        validate_password(attrs["new_password"], user=user)
        return attrs


class AuditLogSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ["id", "actor", "action", "timestamp", "target_model", "target_object_id", "description"]

    def get_actor(self, obj):
        return obj.actor.get_username() if obj.actor else "System"
