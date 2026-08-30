import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser


class HealthCheckView(APIView):
    """Minimal public endpoint used to verify that the API is reachable."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok", "service": "cmu-elect-api"})

from .models import Profile, Election, Position, Candidate, Vote, AuditLog, PasswordResetRequest
from .permissions import IsAuthenticatedAndPasswordChanged, IsAdministrator
from .serializers import (
    LoginSerializer, AdminLoginSerializer, ElectionSerializer, AdminElectionSerializer, BallotSubmissionSerializer,
    ChangePasswordSerializer, VoterSerializer, VoterCreateSerializer,
    VoterPasswordResetSerializer, AdminPositionSerializer, AdminCandidateSerializer, AuditLogSerializer,
)


def hash_value(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()




def create_audit_log(*, actor=None, action, target_model="", target_object_id="", description=""):
    return AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target_model=target_model,
        target_object_id=str(target_object_id) if target_object_id else "",
        description=description,
    )


def create_reset_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def send_reset_code(email, code):
    send_mail(
        subject="CMU-ELECT password reset verification code",
        message=(
            "Your CMU-ELECT verification code is " + code +
            ". It expires in 10 minutes. If you did not request a password reset, "
            "you can ignore this message."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "cmu-elect@localhost"),
        recipient_list=[email],
        fail_silently=False,
    )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            create_audit_log(actor=None, action="security_login_failure", target_model="Authentication", description="A voter login attempt failed.")
            raise
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        create_audit_log(actor=user, action="voter_login", target_model="User", target_object_id=user.id, description="Voter successfully logged in.")
        return Response({
            "token": token.key,
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.profile.role,
                "email": user.profile.cmu_email,
                "must_change_password": user.profile.must_change_password,
            },
        })


class AdminLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            create_audit_log(actor=None, action="security_admin_login_failure", target_model="Authentication", description="An administrator login attempt failed.")
            raise
        user = serializer.validated_data["user"]
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)
        create_audit_log(actor=user, action="admin_login", target_model="User", target_object_id=user.id, description="Administrator successfully logged in.")
        return Response({
            "token": token.key,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_admin": True,
            },
        })


class AdminDashboardView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        return Response({
            "detail": "Administrator access granted.",
            "user": {
                "id": request.user.id,
                "username": request.user.username,
                "email": request.user.email,
                "is_admin": True,
            },
            "modules": [
                {"key": "users", "name": "User Management", "path": "/admin/users"},
                {"key": "elections", "name": "Election Management", "path": "/admin/elections"},
                {"key": "positions", "name": "Position Management", "path": "/admin/positions"},
                {"key": "candidates", "name": "Candidate Management", "path": "/admin/candidates"},
                {"key": "results", "name": "Results", "path": "/admin/results"},
                {"key": "analytics", "name": "Analytics", "path": "/admin/analytics"},
                {"key": "audit-logs", "name": "Audit Logs", "path": "/admin/audit-logs"},
            ],
        })


class AdminVoterListCreateView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        queryset = Profile.objects.select_related("user").all().order_by("full_name", "id")

        search = str(request.query_params.get("search", "")).strip()
        category = str(request.query_params.get("category", "")).strip().lower()
        account_status = str(request.query_params.get("status", "")).strip().lower()

        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(cmu_email__icontains=search)
                | Q(user__username__icontains=search)
            )
        if category:
            queryset = queryset.filter(role=category)
        if account_status:
            queryset = queryset.filter(account_status=account_status)

        return Response(VoterSerializer(queryset, many=True).data)

    @transaction.atomic
    def post(self, request):
        serializer = VoterCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        voter = serializer.save()
        create_audit_log(actor=request.user, action="account_created", target_model="Profile", target_object_id=voter.id, description="Voter account was created.")
        return Response(VoterSerializer(voter).data, status=status.HTTP_201_CREATED)


class AdminVoterDetailView(APIView):
    permission_classes = [IsAdministrator]

    def get_voter(self, voter_id):
        return Profile.objects.select_related("user").get(pk=voter_id)

    def get(self, request, voter_id):
        try:
            voter = self.get_voter(voter_id)
        except Profile.DoesNotExist:
            return Response({"detail": "Voter account not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(VoterSerializer(voter).data)

    @transaction.atomic
    def patch(self, request, voter_id):
        try:
            voter = self.get_voter(voter_id)
        except Profile.DoesNotExist:
            return Response({"detail": "Voter account not found."}, status=status.HTTP_404_NOT_FOUND)

        previous_status = voter.account_status
        serializer = VoterSerializer(voter, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        action = "account_deactivated" if previous_status != voter.account_status and voter.account_status == "inactive" else "account_modified"
        description = "Voter account was deactivated." if action == "account_deactivated" else "Voter account was modified."
        create_audit_log(actor=request.user, action=action, target_model="Profile", target_object_id=voter.id, description=description)
        return Response(VoterSerializer(voter).data)


class AdminElectionListCreateView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        elections = Election.objects.all().order_by("start_datetime", "id")
        return Response(AdminElectionSerializer(elections, many=True).data)

    @transaction.atomic
    def post(self, request):
        serializer = AdminElectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        election = serializer.save(status=Election.STATUS_ACTIVE)
        create_audit_log(actor=request.user, action="election_created", target_model="Election", target_object_id=election.id, description="Election was created.")
        return Response(AdminElectionSerializer(election).data, status=status.HTTP_201_CREATED)


class AdminElectionDetailView(APIView):
    permission_classes = [IsAdministrator]

    def get_election(self, election_id):
        return Election.objects.get(pk=election_id)

    def get(self, request, election_id):
        try:
            election = self.get_election(election_id)
        except Election.DoesNotExist:
            return Response({"detail": "Election not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AdminElectionSerializer(election).data)

    @transaction.atomic
    def patch(self, request, election_id):
        try:
            election = self.get_election(election_id)
        except Election.DoesNotExist:
            return Response({"detail": "Election not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminElectionSerializer(election, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        create_audit_log(actor=request.user, action="election_modified", target_model="Election", target_object_id=election.id, description="Election was modified.")
        return Response(AdminElectionSerializer(election).data)

    @transaction.atomic
    def delete(self, request, election_id):
        try:
            election = self.get_election(election_id)
        except Election.DoesNotExist:
            return Response({"detail": "Election not found."}, status=status.HTTP_404_NOT_FOUND)

        if election.effective_status == Election.STATUS_ACTIVE:
            return Response(
                {"detail": "Active elections cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        election_id_value = election.id
        election.delete()
        create_audit_log(actor=request.user, action="election_deleted", target_model="Election", target_object_id=election_id_value, description="Election was deleted.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminPositionListCreateView(APIView):
    permission_classes = [IsAdministrator]

    def get_election(self, election_id):
        return Election.objects.get(pk=election_id)

    def get(self, request, election_id):
        try:
            election = self.get_election(election_id)
        except Election.DoesNotExist:
            return Response({"detail": "Election not found."}, status=status.HTTP_404_NOT_FOUND)

        positions = election.positions.all().order_by("order", "id")
        return Response(AdminPositionSerializer(positions, many=True).data)

    @transaction.atomic
    def post(self, request, election_id):
        try:
            election = self.get_election(election_id)
        except Election.DoesNotExist:
            return Response({"detail": "Election not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminPositionSerializer(
            data=request.data, context={"request": request, "election": election}
        )
        serializer.is_valid(raise_exception=True)
        position = serializer.save(election=election)
        create_audit_log(actor=request.user, action="position_created", target_model="Position", target_object_id=position.id, description="Position was created.")
        return Response(AdminPositionSerializer(position).data, status=status.HTTP_201_CREATED)


class AdminPositionDetailView(APIView):
    permission_classes = [IsAdministrator]

    def get_position(self, position_id):
        return Position.objects.select_related("election").get(pk=position_id)

    def get(self, request, position_id):
        try:
            position = self.get_position(position_id)
        except Position.DoesNotExist:
            return Response({"detail": "Position not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AdminPositionSerializer(position).data)

    @transaction.atomic
    def patch(self, request, position_id):
        try:
            position = self.get_position(position_id)
        except Position.DoesNotExist:
            return Response({"detail": "Position not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminPositionSerializer(
            position, data=request.data, partial=True,
            context={"request": request, "election": position.election}
        )
        serializer.is_valid(raise_exception=True)
        position = serializer.save()
        create_audit_log(actor=request.user, action="position_modified", target_model="Position", target_object_id=position.id, description="Position was modified.")
        return Response(AdminPositionSerializer(position).data)

    @transaction.atomic
    def delete(self, request, position_id):
        try:
            position = self.get_position(position_id)
        except Position.DoesNotExist:
            return Response({"detail": "Position not found."}, status=status.HTTP_404_NOT_FOUND)

        position_id_value = position.id
        position.delete()
        create_audit_log(actor=request.user, action="position_deleted", target_model="Position", target_object_id=position_id_value, description="Position was deleted.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCandidateListCreateView(APIView):
    permission_classes = [IsAdministrator]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_context(self, election_id, position_id):
        try:
            election = Election.objects.get(pk=election_id)
        except Election.DoesNotExist:
            return None, None, Response(
                {"detail": "Election not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            position = Position.objects.get(pk=position_id)
        except Position.DoesNotExist:
            return None, None, Response(
                {"detail": "Position not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if position.election_id != election.id:
            return None, None, Response(
                {"detail": "Position does not belong to this election."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return election, position, None

    def get(self, request, election_id, position_id):
        _, position, error = self.get_context(election_id, position_id)
        if error:
            return error
        candidates = position.candidates.all().order_by("id")
        return Response(AdminCandidateSerializer(candidates, many=True).data)

    @transaction.atomic
    def post(self, request, election_id, position_id):
        _, position, error = self.get_context(election_id, position_id)
        if error:
            return error
        serializer = AdminCandidateSerializer(
            data=request.data, context={"request": request, "position": position}
        )
        serializer.is_valid(raise_exception=True)
        candidate = serializer.save(position=position)
        create_audit_log(actor=request.user, action="candidate_created", target_model="Candidate", target_object_id=candidate.id, description="Candidate was created.")
        return Response(
            AdminCandidateSerializer(candidate).data,
            status=status.HTTP_201_CREATED,
        )


class AdminCandidateDetailView(APIView):
    permission_classes = [IsAdministrator]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_candidate(self, candidate_id):
        return Candidate.objects.select_related("position", "position__election").get(pk=candidate_id)

    def get(self, request, candidate_id):
        try:
            candidate = self.get_candidate(candidate_id)
        except Candidate.DoesNotExist:
            return Response({"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AdminCandidateSerializer(candidate).data)

    @transaction.atomic
    def patch(self, request, candidate_id):
        try:
            candidate = self.get_candidate(candidate_id)
        except Candidate.DoesNotExist:
            return Response({"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminCandidateSerializer(
            candidate, data=request.data, partial=True,
            context={"request": request, "position": candidate.position}
        )
        serializer.is_valid(raise_exception=True)
        candidate = serializer.save()
        create_audit_log(actor=request.user, action="candidate_modified", target_model="Candidate", target_object_id=candidate.id, description="Candidate was modified.")
        return Response(AdminCandidateSerializer(candidate).data)

    @transaction.atomic
    def delete(self, request, candidate_id):
        try:
            candidate = self.get_candidate(candidate_id)
        except Candidate.DoesNotExist:
            return Response({"detail": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND)
        candidate_id_value = candidate.id
        candidate.delete()
        create_audit_log(actor=request.user, action="candidate_deleted", target_model="Candidate", target_object_id=candidate_id_value, description="Candidate was deleted.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminVoterPasswordResetView(APIView):
    permission_classes = [IsAdministrator]

    @transaction.atomic
    def post(self, request, voter_id):
        try:
            voter = Profile.objects.select_related("user").get(pk=voter_id)
        except Profile.DoesNotExist:
            return Response({"detail": "Voter account not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = VoterPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = voter.user
        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])
        voter.must_change_password = True
        voter.save(update_fields=["must_change_password", "updated_at"])
        Token.objects.filter(user=user).delete()
        create_audit_log(actor=request.user, action="password_reset", target_model="Profile", target_object_id=voter.id, description="Administrator reset a voter account password.")

        return Response({"detail": "Voter password reset successfully. The voter must change it on first login."})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        is_admin = bool(request.user.is_staff)
        create_audit_log(actor=request.user, action="admin_logout" if is_admin else "voter_logout", target_model="User", target_object_id=request.user.id, description="Administrator logged out." if is_admin else "Voter logged out.")
        Token.objects.filter(user=request.user).delete()
        return Response({"detail": "Logged out."})


class MeView(APIView):
    def get(self, request):
        profile = request.user.profile
        if profile.account_status != "active" or not request.user.is_active:
            return Response({"detail": "This account is inactive. Please contact the administrator."}, status=status.HTTP_403_FORBIDDEN)
        return Response({
            "id": request.user.id,
            "username": request.user.username,
            "role": profile.role,
            "email": profile.cmu_email,
            "must_change_password": profile.must_change_password,
        })


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = request.user.profile
        if profile.account_status != "active" or not request.user.is_active:
            return Response({"detail": "This account is inactive. Please contact the administrator."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        profile.must_change_password = False
        profile.save(update_fields=["must_change_password", "updated_at"])
        create_audit_log(actor=request.user, action="password_changed", target_model="User", target_object_id=request.user.id, description="User changed their password.")

        # Rotate the DRF token after a password change so the old token cannot
        # be reused while keeping the voter signed in on this device.
        Token.objects.filter(user=request.user).delete()
        new_token = Token.objects.create(user=request.user)

        return Response({
            "detail": "Password changed successfully.",
            "token": new_token.key,
            "must_change_password": False,
        })


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        if not email:
            return Response({"detail": "Please enter your CMU email."}, status=400)

        # Use a generic success message so the API does not reveal whether an account exists.
        response = {"detail": "If that CMU email exists, a verification code has been sent."}
        try:
            profile = Profile.objects.select_related("user").get(cmu_email__iexact=email)
        except Profile.DoesNotExist:
            return Response(response)

        if profile.account_status != "active" or not profile.user.is_active:
            return Response(response)

        PasswordResetRequest.objects.filter(
            email__iexact=email, used_at__isnull=True
        ).update(used_at=timezone.now())

        code = create_reset_code()
        PasswordResetRequest.objects.create(
            email=profile.cmu_email,
            code_hash=hash_value(code),
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        send_reset_code(profile.cmu_email, code)


        return Response(response)


class VerifyResetCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        code = str(request.data.get("code", "")).strip()
        if not email or not code:
            return Response({"detail": "Email and verification code are required."}, status=400)

        reset = PasswordResetRequest.objects.filter(
            email__iexact=email,
            used_at__isnull=True,
            verified_at__isnull=True,
        ).order_by("-created_at").first()
        if not reset or reset.expires_at < timezone.now():
            return Response({"detail": "That code has expired. Please request a new one."}, status=400)
        if reset.attempts >= 5:
            return Response({"detail": "Too many attempts. Please request a new code."}, status=400)

        if not secrets.compare_digest(hash_value(code), reset.code_hash):
            reset.attempts += 1
            reset.save(update_fields=["attempts"])
            return Response({"detail": "Invalid verification code."}, status=400)

        token = secrets.token_urlsafe(32)
        reset.verified_at = timezone.now()
        reset.reset_token_hash = hash_value(token)
        reset.save(update_fields=["verified_at", "reset_token_hash"])
        return Response({"detail": "Code verified.", "reset_token": token})


class ResendResetCodeView(ForgotPasswordView):
    pass


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        reset_token = str(request.data.get("reset_token", "")).strip()
        password = str(request.data.get("password", ""))
        confirm_password = str(request.data.get("confirm_password", ""))

        if not all([email, reset_token, password, confirm_password]):
            return Response({"detail": "All fields are required."}, status=400)
        if password != confirm_password:
            return Response({"detail": "Passwords do not match."}, status=400)
        if len(password) < 8:
            return Response({"detail": "Password must be at least 8 characters."}, status=400)

        reset = PasswordResetRequest.objects.filter(
            email__iexact=email,
            verified_at__isnull=False,
            used_at__isnull=True,
        ).order_by("-created_at").first()
        if not reset or reset.expires_at < timezone.now():
            return Response({"detail": "Your reset session has expired. Please start again."}, status=400)
        if not secrets.compare_digest(hash_value(reset_token), reset.reset_token_hash):
            return Response({"detail": "Invalid reset session."}, status=400)

        try:
            profile = Profile.objects.select_related("user").get(cmu_email__iexact=email)
        except Profile.DoesNotExist:
            return Response({"detail": "Account not found."}, status=400)

        if profile.account_status != "active" or not profile.user.is_active:
            return Response({"detail": "Password reset is unavailable for this account."}, status=400)

        user = profile.user
        user.set_password(password)
        user.save(update_fields=["password"])
        Token.objects.filter(user=user).delete()
        reset.used_at = timezone.now()
        reset.save(update_fields=["used_at"])
        create_audit_log(actor=None, action="password_reset", target_model="User", target_object_id=user.id, description="Password reset was completed through the password recovery flow.")
        return Response({"detail": "Password changed successfully."})


class ElectionListView(APIView):
    permission_classes = [IsAuthenticatedAndPasswordChanged]

    def get(self, request):
        profile = getattr(request.user, "profile", None)
        if not profile or profile.account_status != "active" or not request.user.is_active:
            return Response(
                {"detail": "This account is inactive. Please contact the administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

        elections = (
            Election.objects
            .filter(eligible_voter_category=profile.role)
            .prefetch_related("positions__candidates")
            .order_by("start_datetime", "id")
        )
        return Response(ElectionSerializer(elections, many=True).data)


class ElectionDetailView(APIView):
    """Return one election only when it is eligible for the authenticated voter."""

    permission_classes = [IsAuthenticatedAndPasswordChanged]

    def get(self, request, election_id):
        profile = getattr(request.user, "profile", None)
        if not profile or profile.account_status != "active" or not request.user.is_active:
            return Response(
                {"detail": "This account is inactive. Please contact the administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            election = (
                Election.objects
                .prefetch_related("positions__candidates")
                .get(pk=election_id, eligible_voter_category=profile.role)
            )
        except Election.DoesNotExist:
            return Response(
                {"detail": "Election not found or you are not eligible to access it."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(ElectionSerializer(election).data)


class VoteView(APIView):
    """Submit a ballot atomically; request.user is always the voter."""

    permission_classes = [IsAuthenticatedAndPasswordChanged]

    @transaction.atomic
    def post(self, request):
        serializer = BallotSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = getattr(request.user, "profile", None)
        if not profile or profile.account_status != "active" or not request.user.is_active:
            return Response(
                {"detail": "This account is inactive. Please contact the administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            election = (
                Election.objects
                .select_for_update()
                .prefetch_related("positions__candidates")
                .get(pk=serializer.validated_data["election_id"])
            )
        except Election.DoesNotExist:
            return Response({"detail": "Election not found."}, status=status.HTTP_404_NOT_FOUND)

        if election.schedule_status == "not_started":
            return Response(
                {"detail": "Voting for this election has not started."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not election.is_open:
            return Response(
                {"detail": "Voting for this election has ended."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if profile.role != election.eligible_voter_category:
            return Response(
                {"detail": "You are not eligible to vote in this election."},
                status=status.HTTP_403_FORBIDDEN,
            )

        position_map = {position.id: position for position in election.positions.all()}
        validated_choices = []

        for item in serializer.validated_data["votes"]:
            position = position_map.get(item["position_id"])
            if position is None:
                return Response({"detail": "Invalid position."}, status=status.HTTP_400_BAD_REQUEST)

            candidate = next(
                (candidate for candidate in position.candidates.all()
                 if candidate.id == item["candidate_id"]),
                None,
            )
            if candidate is None:
                return Response(
                    {"detail": "Invalid candidate selection."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            validated_choices.append((position, candidate))

        position_ids = [position.id for position, _ in validated_choices]
        if Vote.objects.filter(
            voter=request.user,
            election=election,
            position_id__in=position_ids,
        ).exists():
            create_audit_log(actor=request.user, action="security_duplicate_vote_attempt", target_model="Election", target_object_id=election.id, description="A duplicate voting attempt was blocked.")
            return Response(
                {"detail": "You have already voted in this election."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_votes = [
            Vote.objects.create(
                voter=request.user,
                election=election,
                position=position,
                candidate=candidate,
            )
            for position, candidate in validated_choices
        ]

        submitted_at = max(vote.created_at for vote in created_votes)
        create_audit_log(actor=request.user, action="vote_submitted", target_model="Election", target_object_id=election.id, description=f"Voter submitted a ballot containing {len(created_votes)} position vote(s). Candidate choices are not stored in the audit description.")
        return Response(
            {
                "detail": "Vote successfully submitted.",
                "election": {"id": election.id, "name": election.name},
                "submitted_at": submitted_at,
                "votes_created": len(created_votes),
            },
            status=status.HTTP_201_CREATED,
        )


def build_analytics_data(election):
    """Build non-candidate aggregate analytics from current database records."""
    eligible_voters = Profile.objects.filter(
        role=election.eligible_voter_category,
        account_status="active",
        user__is_active=True,
    ).count()
    vote_queryset = Vote.objects.filter(election=election)
    total_votes = vote_queryset.count()
    participants = vote_queryset.values("voter_id").distinct().count()
    turnout_percentage = round((participants / eligible_voters) * 100, 2) if eligible_voters else 0.0

    return {
        "updated_at": timezone.now(),
        "election": {
            "id": election.id, "name": election.name, "status": election.effective_status,
            "schedule_status": election.schedule_status,
            "eligible_voter_category": election.eligible_voter_category,
            "start_datetime": election.start_datetime, "end_datetime": election.end_datetime,
        },
        "metrics": {
            "total_eligible_voters": eligible_voters, "total_votes": total_votes,
            "participants": participants, "turnout_percentage": turnout_percentage,
            "position_count": election.positions.count(),
            "candidate_count": Candidate.objects.filter(position__election=election).count(),
        },
    }


class AdminAuditLogListView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        queryset = AuditLog.objects.select_related("actor").all()
        search = str(request.query_params.get("search", "")).strip()
        action = str(request.query_params.get("action", "")).strip()
        target_model = str(request.query_params.get("target_model", "")).strip()
        sort = str(request.query_params.get("sort", "desc")).strip().lower()
        if search:
            queryset = queryset.filter(Q(action__icontains=search) | Q(description__icontains=search) | Q(target_model__icontains=search) | Q(target_object_id__icontains=search) | Q(actor__username__icontains=search))
        if action: queryset = queryset.filter(action=action)
        if target_model: queryset = queryset.filter(target_model=target_model)
        queryset = queryset.order_by("timestamp", "id") if sort == "asc" else queryset.order_by("-timestamp", "-id")
        return Response({
            "logs": AuditLogSerializer(queryset[:500], many=True).data,
            "actions": list(AuditLog.objects.order_by("action").values_list("action", flat=True).distinct()),
            "target_models": list(AuditLog.objects.exclude(target_model="").order_by("target_model").values_list("target_model", flat=True).distinct()),
        })


class AnalyticsView(APIView):
    """Return live database-backed analytics for an administrator."""
    permission_classes = [IsAdministrator]

    def get(self, request, election_id):
        try:
            election = Election.objects.get(pk=election_id)
        except Election.DoesNotExist:
            return Response({"detail": "Election not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(build_analytics_data(election))


class VoterAnalyticsView(APIView):
    """Return aggregate live analytics to an eligible authenticated voter."""
    permission_classes = [IsAuthenticated]

    def get(self, request, election_id):
        try:
            election = Election.objects.get(pk=election_id)
        except Election.DoesNotExist:
            return Response({"detail": "Election not found."}, status=status.HTTP_404_NOT_FOUND)

        profile = getattr(request.user, "profile", None)
        if (
            not request.user.is_active
            or not profile
            or profile.account_status != "active"
        ):
            return Response({"detail": "Active voter access is required."}, status=status.HTTP_403_FORBIDDEN)
        if profile.must_change_password:
            return Response({"detail": "You must change your password before viewing analytics."}, status=status.HTTP_403_FORBIDDEN)
        if profile.role != election.eligible_voter_category:
            return Response({"detail": "You are not eligible to view this election's analytics."}, status=status.HTTP_403_FORBIDDEN)

        return Response(build_analytics_data(election))


class ResultsView(APIView):
    """Return final database-backed election results after an election ends."""
    permission_classes = [IsAuthenticated]

    def get(self, request, election_id):
        try:
            election = Election.objects.get(pk=election_id)
        except Election.DoesNotExist:
            return Response({"detail": "Election not found."}, status=status.HTTP_404_NOT_FOUND)

        if election.effective_status != Election.STATUS_ENDED:
            return Response(
                {"detail": "Election results are not available until the election has ended."},
                status=status.HTTP_403_FORBIDDEN,
            )

        is_admin = bool(request.user.is_staff and request.user.is_active)
        if not is_admin:
            profile = getattr(request.user, "profile", None)
            if not profile or profile.account_status != "active" or not request.user.is_active:
                return Response({"detail": "Active voter access is required."}, status=status.HTTP_403_FORBIDDEN)
            if profile.must_change_password:
                return Response({"detail": "You must change your password before viewing results."}, status=status.HTTP_403_FORBIDDEN)
            if profile.role != election.eligible_voter_category:
                return Response({"detail": "You are not eligible to view this election's results."}, status=status.HTTP_403_FORBIDDEN)

        total_votes = Vote.objects.filter(election=election).count()
        positions = election.positions.annotate(
            position_total=Count("votes", filter=Q(votes__election=election))
        ).prefetch_related("candidates")

        results = []
        for position in positions:
            candidates = list(
                position.candidates.annotate(
                    vote_count=Count("votes", filter=Q(votes__election=election))
                ).order_by("name", "id")
            )
            position_total = position.position_total
            max_votes = max((candidate.vote_count for candidate in candidates), default=0)
            winners = [
                {
                    "id": candidate.id,
                    "candidate": candidate.name,
                    "percentage": round((candidate.vote_count / position_total) * 100, 2) if position_total else 0.0,
                }
                for candidate in candidates
                if max_votes > 0 and candidate.vote_count == max_votes
            ]

            results.append({
                "position_id": position.id,
                "position": position.name,
                "total_votes": position_total,
                "winners": winners,
                "candidates": [
                    {
                        "id": candidate.id,
                        "candidate": candidate.name,
                        "percentage": round((candidate.vote_count / position_total) * 100, 2) if position_total else 0.0,
                    }
                    for candidate in candidates
                ],
            })

        return Response({
            "election": {
                "id": election.id, "name": election.name, "status": election.effective_status,
            },
            "total_votes": total_votes,
            "results": results,
        })
