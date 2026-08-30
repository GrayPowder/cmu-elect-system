from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from .models import AuditLog, Candidate, Election, Position, Profile, Vote


class Phase2ModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="student-001",
            password="test-password-123",
            first_name="Test",
            last_name="Student",
            email="student@cmu.edu",
        )
        self.profile = Profile.objects.create(
            user=self.user,
            role="student",
            cmu_email="student@cmu.edu",
            full_name="Test Student",
        )
        now = timezone.now()
        self.election = Election.objects.create(
            name="Student Election",
            description="Phase 2 test election",
            eligible_voter_category="student",
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=1),
            status=Election.STATUS_ACTIVE,
        )
        self.position = Position.objects.create(
            election=self.election,
            name="President",
            order=1,
        )
        self.candidate = Candidate.objects.create(
            position=self.position,
            name="Candidate A",
        )

    def test_profile_supports_required_voter_fields(self):
        self.assertEqual(self.profile.login_identifier, "student@cmu.edu")
        self.assertEqual(self.profile.voter_category, "student")
        self.assertEqual(self.profile.account_status, "active")
        self.assertFalse(self.profile.must_change_password)
        self.assertTrue(self.user.has_usable_password())

    def test_election_position_candidate_relationship(self):
        self.assertEqual(self.position.election, self.election)
        self.assertEqual(self.candidate.position, self.position)
        self.assertEqual(self.candidate.election, self.election)

    def test_election_rejects_invalid_schedule(self):
        self.election.start_datetime = self.election.end_datetime
        with self.assertRaises(ValidationError):
            self.election.full_clean()

    def test_vote_requires_matching_election_position_and_candidate(self):
        vote = Vote(
            voter=self.user,
            election=self.election,
            position=self.position,
            candidate=self.candidate,
        )
        vote.full_clean()
        vote.save()
        self.assertEqual(Vote.objects.count(), 1)

    def test_duplicate_vote_is_blocked_by_database_constraint(self):
        Vote.objects.create(
            voter=self.user,
            election=self.election,
            position=self.position,
            candidate=self.candidate,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Vote.objects.create(
                    voter=self.user,
                    election=self.election,
                    position=self.position,
                    candidate=self.candidate,
                )

    def test_vote_rejects_candidate_from_different_position(self):
        other_position = Position.objects.create(
            election=self.election,
            name="Vice President",
            order=2,
        )
        other_candidate = Candidate.objects.create(
            position=other_position,
            name="Candidate B",
        )
        vote = Vote(
            voter=self.user,
            election=self.election,
            position=self.position,
            candidate=other_candidate,
        )
        with self.assertRaises(ValidationError):
            vote.full_clean()

    def test_audit_log_can_reference_existing_actor_without_sensitive_data(self):
        log = AuditLog.objects.create(
            actor=self.user,
            action="TEST_ACTION",
            target_model="Election",
            target_object_id=str(self.election.pk),
            description="Phase 2 model test",
        )
        self.assertEqual(log.actor, self.user)
        self.assertEqual(log.target_model, "Election")
        self.assertNotIn("password", log.description.lower())


class Phase3AuthenticationTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.user = User.objects.create_user(
            username="auth-student-001",
            password="InitialPass123!",
            email="auth.student@cmu.edu",
        )
        self.profile = Profile.objects.create(
            user=self.user,
            role="student",
            cmu_email="auth.student@cmu.edu",
            full_name="Auth Student",
            account_status="active",
            must_change_password=False,
        )

    def login(self, password="InitialPass123!", role="student"):
        return self.client.post(
            "/api/auth/login/",
            {"email": self.profile.cmu_email, "password": password, "role": role},
            format="json",
        )

    def authenticate(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")

    def test_valid_login_returns_token_and_user_state(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["token"])
        self.assertFalse(response.data["user"]["must_change_password"])

    def test_invalid_login_is_rejected(self):
        response = self.login(password="WrongPassword123!")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid CMU email or password", str(response.data))

    def test_inactive_account_cannot_login(self):
        self.profile.account_status = "inactive"
        self.profile.save(update_fields=["account_status"])
        response = self.login()
        self.assertEqual(response.status_code, 400)
        self.assertIn("inactive", str(response.data).lower())

    def test_first_login_requires_password_change(self):
        self.profile.must_change_password = True
        self.profile.save(update_fields=["must_change_password"])

        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["user"]["must_change_password"])

        self.authenticate(response.data["token"])
        protected = self.client.get("/api/elections/")
        self.assertEqual(protected.status_code, 403)

    def test_password_change_clears_first_login_flag_and_rotates_token(self):
        self.profile.must_change_password = True
        self.profile.save(update_fields=["must_change_password"])
        login_response = self.login()
        old_token = login_response.data["token"]
        self.authenticate(old_token)

        response = self.client.post(
            "/api/auth/change-password/",
            {
                "current_password": "InitialPass123!",
                "new_password": "NewSecurePass123!",
                "confirm_password": "NewSecurePass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["must_change_password"])
        self.assertNotEqual(old_token, response.data["token"])
        self.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertFalse(self.profile.must_change_password)
        self.assertTrue(self.user.check_password("NewSecurePass123!"))

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")
        protected = self.client.get("/api/elections/")
        self.assertEqual(protected.status_code, 200)

    def test_password_change_rejects_wrong_current_password(self):
        login_response = self.login()
        self.authenticate(login_response.data["token"])
        response = self.client.post(
            "/api/auth/change-password/",
            {
                "current_password": "WrongPassword123!",
                "new_password": "NewSecurePass123!",
                "confirm_password": "NewSecurePass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("InitialPass123!"))

    def test_forgot_password_does_not_reveal_unknown_account(self):
        response = self.client.post(
            "/api/auth/forgot-password/",
            {"email": "does-not-exist@cmu.edu"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("dev_code", response.data)
        self.assertIn("If that CMU email exists", response.data["detail"])

    def test_forgot_password_verify_and_reset(self):
        from unittest.mock import patch

        sent = {}

        def capture_code(email, code):
            sent["email"] = email
            sent["code"] = code

        with patch("elections.views.send_reset_code", side_effect=capture_code):
            request = self.client.post(
                "/api/auth/forgot-password/",
                {"email": self.profile.cmu_email},
                format="json",
            )

        self.assertEqual(request.status_code, 200)
        self.assertEqual(sent["email"], self.profile.cmu_email)
        self.assertNotIn("dev_code", request.data)

        verify = self.client.post(
            "/api/auth/verify-code/",
            {"email": self.profile.cmu_email, "code": sent["code"]},
            format="json",
        )
        self.assertEqual(verify.status_code, 200)
        reset_token = verify.data["reset_token"]

        reset = self.client.post(
            "/api/auth/reset-password/",
            {
                "email": self.profile.cmu_email,
                "reset_token": reset_token,
                "password": "ResetSecurePass123!",
                "confirm_password": "ResetSecurePass123!",
            },
            format="json",
        )
        self.assertEqual(reset.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ResetSecurePass123!"))

        login = self.login(password="ResetSecurePass123!")
        self.assertEqual(login.status_code, 200)

    def test_logout_invalidates_token_and_protected_endpoint(self):
        login_response = self.login()
        token = login_response.data["token"]
        self.authenticate(token)
        logout = self.client.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(logout.status_code, 200)

        protected = self.client.get("/api/elections/")
        self.assertEqual(protected.status_code, 401)

    def test_protected_endpoint_requires_authentication(self):
        response = self.client.get("/api/elections/")
        self.assertEqual(response.status_code, 401)

class Phase4AdministratorAuthenticationTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@cmu.edu",
            password="AdminPass123!",
        )
        self.voter = User.objects.create_user(
            username="voter-001",
            email="voter@cmu.edu",
            password="VoterPass123!",
        )
        Profile.objects.create(
            user=self.voter,
            role="student",
            cmu_email="voter@cmu.edu",
            full_name="Test Voter",
        )

    def test_admin_can_login_and_access_dashboard(self):
        response = self.client.post(
            "/api/auth/admin/login/",
            {"email": "admin@cmu.edu", "password": "AdminPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["user"]["is_admin"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")
        dashboard = self.client.get("/api/admin/dashboard/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(len(dashboard.data["modules"]), 7)

    def test_voter_cannot_login_as_admin(self):
        response = self.client.post(
            "/api/auth/admin/login/",
            {"email": "voter@cmu.edu", "password": "VoterPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_voter_cannot_access_admin_api(self):
        from rest_framework.authtoken.models import Token

        token = Token.objects.create(user=self.voter)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_access_admin_api(self):
        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, 401)

    def test_admin_logout_invalidates_token(self):
        from rest_framework.authtoken.models import Token

        token = Token.objects.create(user=self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        logout = self.client.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(logout.status_code, 200)

        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, 401)


class Phase5VoterAccountManagementTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework.authtoken.models import Token

        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="phase5-admin", email="phase5-admin@cmu.edu", password="AdminPass123!"
        )
        self.voter = User.objects.create_user(
            username="20230001", email="voter1@cmu.edu", password="VoterPass123!"
        )
        self.profile = Profile.objects.create(
            user=self.voter, role="student", cmu_email="voter1@cmu.edu",
            full_name="Juan Student", account_status="active", must_change_password=False,
        )
        self.admin_token = Token.objects.create(user=self.admin)
        self.voter_token = Token.objects.create(user=self.voter)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

    def test_voter_can_login_with_login_identifier(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": self.voter.username, "password": "VoterPass123!", "role": "student"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["username"], self.voter.username)

    def test_admin_can_list_voters_without_passwords(self):
        response = self.client.get("/api/admin/voters/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Juan Student")
        self.assertEqual(response.data[0]["id"], self.profile.pk)
        self.assertEqual(response.data[0]["identifier"], "20230001")
        self.assertEqual(response.data[0]["category"], "student")
        self.assertEqual(response.data[0]["status"], "active")
        self.assertNotIn("password", response.data[0])

    def test_admin_can_create_voter_for_each_supported_category(self):
        for index, category in enumerate(["student", "alumni", "faculty"], start=2):
            response = self.client.post(
                "/api/admin/voters/",
                {
                    "name": f"Test {category.title()}",
                    "identifier": f"2023{index:04d}",
                    "email": f"{category}{index}@cmu.edu",
                    "category": category,
                    "password": "SecurePass123!",
                    "status": "active",
                },
                format="json",
            )
            self.assertEqual(response.status_code, 201)
            self.assertNotIn("password", response.data)
            created = Profile.objects.get(user__username=f"2023{index:04d}")
            self.assertEqual(created.role, category)
            self.assertTrue(created.must_change_password)
            self.assertTrue(created.user.check_password("SecurePass123!"))

    def test_create_inactive_voter_disables_django_account(self):
        response = self.client.post(
            "/api/admin/voters/",
            {
                "name": "Inactive Voter",
                "identifier": "20239999",
                "email": "inactive@cmu.edu",
                "category": "faculty",
                "password": "SecurePass123!",
                "status": "inactive",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        profile = Profile.objects.get(user__username="20239999")
        self.assertEqual(profile.account_status, "inactive")
        self.assertFalse(profile.user.is_active)

    def test_admin_can_search_and_filter_voters(self):
        Profile.objects.create(
            user=User.objects.create_user(username="alumni-001", email="alumni@cmu.edu", password="SecurePass123!"),
            role="alumni", cmu_email="alumni@cmu.edu", full_name="Maria Alumni", account_status="inactive"
        )
        search = self.client.get("/api/admin/voters/?search=Maria")
        self.assertEqual(search.status_code, 200)
        self.assertEqual([row["identifier"] for row in search.data], ["alumni-001"])

        category = self.client.get("/api/admin/voters/?category=student")
        self.assertEqual(category.status_code, 200)
        self.assertTrue(all(row["category"] == "student" for row in category.data))

        inactive = self.client.get("/api/admin/voters/?status=inactive")
        self.assertEqual(inactive.status_code, 200)
        self.assertEqual([row["identifier"] for row in inactive.data], ["alumni-001"])

    def test_voter_management_uses_profile_id_not_user_id(self):
        # The admin User and voter User have different primary keys from the Profile.
        # The API resource id must therefore be the Profile id used by detail endpoints.
        self.assertNotEqual(self.voter.pk, self.profile.pk)
        response = self.client.patch(
            f"/api/admin/voters/{self.profile.pk}/",
            {"status": "inactive"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.profile.pk)
        self.profile.refresh_from_db(); self.voter.refresh_from_db()
        self.assertEqual(self.profile.account_status, "inactive")
        self.assertFalse(self.voter.is_active)

    def test_admin_can_edit_voter(self):
        response = self.client.patch(
            f"/api/admin/voters/{self.profile.pk}/",
            {
                "name": "Juan Updated",
                "identifier": "20230001-UPD",
                "email": "juan.updated@cmu.edu",
                "category": "faculty",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.voter.refresh_from_db()
        self.assertEqual(self.profile.full_name, "Juan Updated")
        self.assertEqual(self.profile.role, "faculty")
        self.assertEqual(self.profile.cmu_email, "juan.updated@cmu.edu")
        self.assertEqual(self.voter.username, "20230001-UPD")
        self.assertEqual(self.voter.email, "juan.updated@cmu.edu")

    def test_admin_can_activate_and_deactivate_voter(self):
        response = self.client.patch(
            f"/api/admin/voters/{self.profile.pk}/",
            {"status": "inactive"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db(); self.voter.refresh_from_db()
        self.assertEqual(self.profile.account_status, "inactive")
        self.assertFalse(self.voter.is_active)

        response = self.client.patch(
            f"/api/admin/voters/{self.profile.pk}/",
            {"status": "active"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db(); self.voter.refresh_from_db()
        self.assertEqual(self.profile.account_status, "active")
        self.assertTrue(self.voter.is_active)

    def test_admin_can_reset_password_without_password_in_response(self):
        old_token = self.voter_token.key
        response = self.client.post(
            f"/api/admin/voters/{self.profile.pk}/reset-password/",
            {"password": "NewSecurePass123!", "confirm_password": "NewSecurePass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("password", response.data)
        self.profile.refresh_from_db(); self.voter.refresh_from_db()
        self.assertTrue(self.voter.check_password("NewSecurePass123!"))
        self.assertTrue(self.profile.must_change_password)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {old_token}")
        self.assertEqual(self.client.get("/api/elections/").status_code, 401)

    def test_voter_cannot_use_voter_management_endpoints(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.voter_token.key}")
        self.assertEqual(self.client.get("/api/admin/voters/").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/admin/voters/",
                {
                    "name": "Blocked", "identifier": "blocked", "email": "blocked@cmu.edu",
                    "category": "student", "password": "SecurePass123!", "status": "active"
                }, format="json"
            ).status_code,
            403,
        )
        self.assertEqual(self.client.patch(f"/api/admin/voters/{self.profile.pk}/", {"name": "Blocked"}, format="json").status_code, 403)
        self.assertEqual(self.client.post(f"/api/admin/voters/{self.profile.pk}/reset-password/", {"password": "SecurePass123!", "confirm_password": "SecurePass123!"}, format="json").status_code, 403)

    def test_unauthenticated_user_cannot_use_voter_management_endpoints(self):
        self.client.credentials()
        self.assertEqual(self.client.get("/api/admin/voters/").status_code, 401)
        self.assertEqual(self.client.post("/api/admin/voters/", {}, format="json").status_code, 401)

    def test_duplicate_identifier_and_email_are_rejected(self):
        duplicate_identifier = self.client.post(
            "/api/admin/voters/",
            {"name": "Duplicate", "identifier": "20230001", "email": "new@cmu.edu", "category": "student", "password": "SecurePass123!", "status": "active"},
            format="json",
        )
        self.assertEqual(duplicate_identifier.status_code, 400)

        duplicate_email = self.client.post(
            "/api/admin/voters/",
            {"name": "Duplicate", "identifier": "new-unique", "email": "voter1@cmu.edu", "category": "student", "password": "SecurePass123!", "status": "active"},
            format="json",
        )
        self.assertEqual(duplicate_email.status_code, 400)


class Phase6ElectionManagementTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework.authtoken.models import Token

        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="phase6-admin", email="phase6-admin@cmu.edu", password="AdminPass123!"
        )
        self.voter = User.objects.create_user(
            username="phase6-voter", email="phase6-voter@cmu.edu", password="VoterPass123!"
        )
        Profile.objects.create(
            user=self.voter, role="student", cmu_email="phase6-voter@cmu.edu",
            full_name="Phase 6 Voter", account_status="active", must_change_password=False,
        )
        self.admin_token = Token.objects.create(user=self.admin)
        self.voter_token = Token.objects.create(user=self.voter)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        self.now = timezone.now()

    def election_payload(self, start=None, end=None, category="student"):
        start = start or (self.now + timedelta(hours=1))
        end = end or (self.now + timedelta(hours=3))
        return {
            "name": "CMU Student Election",
            "description": "Phase 6 test election",
            "start_datetime": start.isoformat(),
            "end_datetime": end.isoformat(),
            "eligible_voter_category": category,
        }

    def test_election_name_cannot_be_empty_or_spaces(self):
        for invalid_name in ["", "   ", "\t", "\n"]:
            response = self.client.post(
                "/api/admin/elections/",
                {**self.election_payload(), "name": invalid_name},
                format="json",
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("name", response.data)

    def test_election_name_is_trimmed(self):
        response = self.client.post(
            "/api/admin/elections/",
            {**self.election_payload(), "name": "  CMU Election  "},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "CMU Election")

    def test_1_admin_can_create_election(self):
        response = self.client.post("/api/admin/elections/", self.election_payload(), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "CMU Student Election")
        self.assertEqual(response.data["eligible_voter_category"], "student")
        self.assertEqual(response.data["status"], "active")
        self.assertFalse(response.data["is_open"])
        self.assertTrue(Election.objects.filter(name="CMU Student Election").exists())

    def test_2_admin_can_edit_election(self):
        election = Election.objects.create(
            name="Original Election", description="Original",
            eligible_voter_category="student",
            start_datetime=self.now + timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=3),
            status=Election.STATUS_ACTIVE,
        )
        response = self.client.patch(
            f"/api/admin/elections/{election.pk}/",
            {"name": "Updated Election", "description": "Updated description", "eligible_voter_category": "faculty"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        election.refresh_from_db()
        self.assertEqual(election.name, "Updated Election")
        self.assertEqual(election.description, "Updated description")
        self.assertEqual(election.eligible_voter_category, "faculty")

    def test_3_admin_can_view_election(self):
        election = Election.objects.create(
            name="View Election", description="View me",
            eligible_voter_category="alumni",
            start_datetime=self.now + timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=3),
            status=Election.STATUS_ACTIVE,
        )
        response = self.client.get(f"/api/admin/elections/{election.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], election.pk)
        self.assertEqual(response.data["eligible_voter_category"], "alumni")

    def test_4_active_election_is_active_and_voting_allowed_inside_schedule(self):
        election = Election.objects.create(
            name="Active Election", description="Open now",
            eligible_voter_category="student",
            start_datetime=self.now - timedelta(minutes=5),
            end_datetime=self.now + timedelta(minutes=5),
            status=Election.STATUS_ACTIVE,
        )
        response = self.client.get(f"/api/admin/elections/{election.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "active")
        self.assertTrue(response.data["is_open"])
        self.assertEqual(election.effective_status, Election.STATUS_ACTIVE)
        self.assertTrue(election.is_open)

    def test_5_ended_election_is_ended_when_schedule_has_passed(self):
        election = Election.objects.create(
            name="Ended Election", description="Already ended",
            eligible_voter_category="student",
            start_datetime=self.now - timedelta(hours=3),
            end_datetime=self.now - timedelta(hours=1),
            status=Election.STATUS_ACTIVE,
        )
        response = self.client.get(f"/api/admin/elections/{election.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ended")
        self.assertFalse(response.data["is_open"])
        self.assertEqual(election.effective_status, Election.STATUS_ENDED)
        self.assertFalse(election.is_open)

    def test_6_active_election_cannot_be_deleted(self):
        election = Election.objects.create(
            name="Protected Active Election", description="Do not delete",
            eligible_voter_category="student",
            start_datetime=self.now - timedelta(minutes=5),
            end_datetime=self.now + timedelta(hours=1),
            status=Election.STATUS_ACTIVE,
        )
        response = self.client.delete(f"/api/admin/elections/{election.pk}/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Election.objects.filter(pk=election.pk).exists())

    def test_7_ended_election_can_be_deleted(self):
        election = Election.objects.create(
            name="Deletable Ended Election", description="Delete me",
            eligible_voter_category="student",
            start_datetime=self.now - timedelta(hours=3),
            end_datetime=self.now - timedelta(hours=1),
            status=Election.STATUS_ACTIVE,
        )
        response = self.client.delete(f"/api/admin/elections/{election.pk}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Election.objects.filter(pk=election.pk).exists())

    def test_8_invalid_dates_are_rejected(self):
        response = self.client.post(
            "/api/admin/elections/",
            self.election_payload(
                start=self.now + timedelta(hours=3),
                end=self.now + timedelta(hours=1),
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("end_datetime", response.data)

    def test_9_supported_voter_categories(self):
        for index, category in enumerate(["student", "alumni", "faculty"], start=1):
            payload = self.election_payload(category=category)
            payload["name"] = f"Category Election {index}"
            response = self.client.post("/api/admin/elections/", payload, format="json")
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.data["eligible_voter_category"], category)

    def test_voter_cannot_access_election_management_api(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.voter_token.key}")
        response = self.client.get("/api/admin/elections/")
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_access_election_management_api(self):
        self.client.credentials()
        response = self.client.get("/api/admin/elections/")
        self.assertEqual(response.status_code, 401)

class Phase7PositionManagementTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="phase7-admin",
            email="phase7-admin@cmu.edu",
            password="AdminPass123!",
            is_staff=True,
        )
        self.voter = User.objects.create_user(
            username="phase7-voter",
            email="phase7-voter@cmu.edu",
            password="VoterPass123!",
        )
        Profile.objects.create(
            user=self.voter,
            role="student",
            cmu_email="phase7-voter@cmu.edu",
            full_name="Phase 7 Voter",
        )
        now = timezone.now()
        self.election = Election.objects.create(
            name="Phase 7 Election",
            description="Position management test election",
            eligible_voter_category="student",
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=1),
            status=Election.STATUS_ACTIVE,
        )

    def authenticate_admin(self):
        self.client.force_authenticate(user=self.admin)

    def test_admin_can_create_and_read_position(self):
        self.authenticate_admin()

        response = self.client.post(
            f"/api/admin/elections/{self.election.id}/positions/",
            {"name": "President", "order": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "President")
        self.assertEqual(response.data["election_id"], self.election.id)

        position_id = response.data["id"]
        list_response = self.client.get(
            f"/api/admin/elections/{self.election.id}/positions/"
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 1)

        detail_response = self.client.get(f"/api/admin/positions/{position_id}/")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data["name"], "President")

    def test_admin_can_update_position(self):
        self.authenticate_admin()
        position = Position.objects.create(election=self.election, name="President", order=1)

        response = self.client.patch(
            f"/api/admin/positions/{position.id}/",
            {"name": "Chairperson", "order": 2},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        position.refresh_from_db()
        self.assertEqual(position.name, "Chairperson")
        self.assertEqual(position.order, 2)

    def test_admin_can_delete_position(self):
        self.authenticate_admin()
        position = Position.objects.create(election=self.election, name="Treasurer", order=4)

        response = self.client.delete(f"/api/admin/positions/{position.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Position.objects.filter(id=position.id).exists())

    def test_position_name_cannot_be_empty(self):
        self.authenticate_admin()
        response = self.client.post(
            f"/api/admin/elections/{self.election.id}/positions/",
            {"name": "   ", "order": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.data)

    def test_duplicate_position_name_is_rejected_within_same_election(self):
        self.authenticate_admin()
        Position.objects.create(election=self.election, name="President", order=1)

        response = self.client.post(
            f"/api/admin/elections/{self.election.id}/positions/",
            {"name": " president ", "order": 2},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", str(response.data).lower())

    def test_invalid_election_id_is_rejected(self):
        self.authenticate_admin()
        response = self.client.post(
            "/api/admin/elections/999999/positions/",
            {"name": "President", "order": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_position_id_is_rejected(self):
        self.authenticate_admin()
        response = self.client.get("/api/admin/positions/999999/")
        self.assertEqual(response.status_code, 404)

    def test_non_admin_cannot_manage_positions(self):
        self.client.force_authenticate(user=self.voter)
        response = self.client.get(f"/api/admin/elections/{self.election.id}/positions/")
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_manage_positions(self):
        response = self.client.get(f"/api/admin/elections/{self.election.id}/positions/")
        self.assertEqual(response.status_code, 401)


class Phase8CandidateManagementTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()
        self.admin = User.objects.create_user(username="phase8-admin", email="phase8-admin@cmu.edu", password="AdminPass123!", is_staff=True)
        self.voter = User.objects.create_user(username="phase8-voter", email="phase8-voter@cmu.edu", password="VoterPass123!")
        Profile.objects.create(user=self.voter, role="student", cmu_email="phase8-voter@cmu.edu", full_name="Phase 8 Voter")
        now = timezone.now()
        self.election = Election.objects.create(name="Phase 8 Election", eligible_voter_category="student", start_datetime=now-timedelta(hours=1), end_datetime=now+timedelta(hours=1), status=Election.STATUS_ACTIVE)
        self.other_election = Election.objects.create(name="Other Election", eligible_voter_category="student", start_datetime=now-timedelta(hours=1), end_datetime=now+timedelta(hours=1), status=Election.STATUS_ACTIVE)
        self.position = Position.objects.create(election=self.election, name="President", order=1)
        self.other_position = Position.objects.create(election=self.other_election, name="President", order=1)

    def authenticate_admin(self):
        self.client.force_authenticate(user=self.admin)

    def test_admin_can_create_and_read_candidate(self):
        self.authenticate_admin()
        response = self.client.post(f"/api/admin/elections/{self.election.id}/positions/{self.position.id}/candidates/", {"name":"Juan Dela Cruz","platform":"Better student representation."}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["position_id"], self.position.id)
        self.assertEqual(response.data["election_id"], self.election.id)
        list_response = self.client.get(f"/api/admin/elections/{self.election.id}/positions/{self.position.id}/candidates/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 1)

    def test_admin_can_edit_and_delete_candidate(self):
        self.authenticate_admin()
        candidate = Candidate.objects.create(position=self.position, name="Juan Dela Cruz", platform="Old")
        response = self.client.patch(f"/api/admin/candidates/{candidate.id}/", {"name":"Maria Santos","platform":"New"}, format="json")
        self.assertEqual(response.status_code, 200)
        candidate.refresh_from_db()
        self.assertEqual(candidate.name, "Maria Santos")
        delete_response = self.client.delete(f"/api/admin/candidates/{candidate.id}/")
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(Candidate.objects.filter(pk=candidate.id).exists())

    def test_invalid_position_is_rejected(self):
        self.authenticate_admin()
        response = self.client.post(f"/api/admin/elections/{self.election.id}/positions/999999/candidates/", {"name":"Test Candidate"}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_position_from_different_election_is_rejected(self):
        self.authenticate_admin()
        response = self.client.post(f"/api/admin/elections/{self.election.id}/positions/{self.other_position.id}/candidates/", {"name":"Test Candidate"}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_candidate_name_cannot_be_blank_or_spaces(self):
        self.authenticate_admin()
        response = self.client.post(f"/api/admin/elections/{self.election.id}/positions/{self.position.id}/candidates/", {"name":"   "}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.data)

    def test_candidate_party_list_is_saved_and_returned(self):
        self.authenticate_admin()
        response = self.client.post(
            f"/api/admin/elections/{self.election.id}/positions/{self.position.id}/candidates/",
            {"name": "Juan Dela Cruz", "party_list": "Student Unity Party", "platform": "Better student representation."},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["party_list"], "Student Unity Party")
        candidate = Candidate.objects.get(pk=response.data["id"])
        self.assertEqual(candidate.party_list, "Student Unity Party")

    def test_candidate_name_cannot_be_blank_or_spaces_on_create_and_edit(self):
        self.authenticate_admin()
        response = self.client.post(
            f"/api/admin/elections/{self.election.id}/positions/{self.position.id}/candidates/",
            {"name": "   "},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        candidate = Candidate.objects.create(position=self.position, name="Valid Candidate")
        response = self.client.patch(
            f"/api/admin/candidates/{candidate.id}/",
            {"name": "   "},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        candidate.refresh_from_db()
        self.assertEqual(candidate.name, "Valid Candidate")

    def test_unauthorized_user_cannot_manage_candidates(self):
        self.client.force_authenticate(user=self.voter)
        response = self.client.get(f"/api/admin/elections/{self.election.id}/positions/{self.position.id}/candidates/")
        self.assertEqual(response.status_code, 403)
        self.client.force_authenticate(user=None)
        response = self.client.get(f"/api/admin/elections/{self.election.id}/positions/{self.position.id}/candidates/")
        self.assertEqual(response.status_code, 401)


class Phase11ElectionResultsTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        now = timezone.now()
        self.admin = User.objects.create_user(
            username="phase11-admin",
            email="phase11-admin@cmu.edu",
            password="AdminPass123!",
            is_staff=True,
        )
        self.voter_one = User.objects.create_user(
            username="phase11-voter-one",
            email="phase11-one@cmu.edu",
            password="VoterPass123!",
        )
        self.voter_two = User.objects.create_user(
            username="phase11-voter-two",
            email="phase11-two@cmu.edu",
            password="VoterPass123!",
        )
        self.voter_three = User.objects.create_user(
            username="phase11-voter-three",
            email="phase11-three@cmu.edu",
            password="VoterPass123!",
        )
        self.ineligible_voter = User.objects.create_user(
            username="phase11-voter-faculty",
            email="phase11-faculty@cmu.edu",
            password="VoterPass123!",
        )
        for user, role, email in [
            (self.voter_one, "student", "phase11-one@cmu.edu"),
            (self.voter_two, "student", "phase11-two@cmu.edu"),
            (self.voter_three, "student", "phase11-three@cmu.edu"),
            (self.ineligible_voter, "faculty", "phase11-faculty@cmu.edu"),
        ]:
            Profile.objects.create(
                user=user,
                role=role,
                cmu_email=email,
                full_name=user.username,
                must_change_password=False,
            )

        self.election = Election.objects.create(
            name="Phase 11 Election",
            eligible_voter_category="student",
            start_datetime=now - timedelta(days=2),
            end_datetime=now - timedelta(days=1),
            status=Election.STATUS_ENDED,
        )
        self.president = Position.objects.create(election=self.election, name="President", order=1)
        self.vice_president = Position.objects.create(election=self.election, name="Vice President", order=2)
        self.president_a = Candidate.objects.create(position=self.president, name="Candidate A")
        self.president_b = Candidate.objects.create(position=self.president, name="Candidate B")
        self.vice_a = Candidate.objects.create(position=self.vice_president, name="Candidate C")

        # Controlled votes:
        # President A = 2
        # President B = 1
        # Vice President C = 1

        Vote.objects.create(
            voter=self.voter_one,
            election=self.election,
            position=self.president,
            candidate=self.president_a,
        )

        Vote.objects.create(
            voter=self.voter_two,
            election=self.election,
            position=self.president,
            candidate=self.president_a,
        )

        Vote.objects.create(
            voter=self.voter_three,
            election=self.election,
            position=self.president,
            candidate=self.president_b,
        )

        Vote.objects.create(
            voter=self.voter_one,
            election=self.election,
            position=self.vice_president,
            candidate=self.vice_a,
        )
        
    def test_admin_receives_accurate_candidate_position_total_and_winner_results(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(f"/api/elections/{self.election.id}/results/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_votes"], 4)
        self.assertEqual(response.data["election"]["status"], "ended")

        president = response.data["results"][0]
        self.assertEqual(president["position"], "President")
        self.assertEqual(president["total_votes"], 3)
        self.assertEqual(
            {row["candidate"]: row["percentage"] for row in president["candidates"]},
            {"Candidate A": 66.67, "Candidate B": 33.33},
        )
        self.assertEqual(president["winners"], [{"id": self.president_a.id, "candidate": "Candidate A", "percentage": 66.67}])

        vice_president = response.data["results"][1]
        self.assertEqual(vice_president["total_votes"], 1)
        self.assertEqual(vice_president["winners"], [{"id": self.vice_a.id, "candidate": "Candidate C", "percentage": 100.0}])

    def test_eligible_voter_can_view_results_after_election_ends(self):
        self.client.force_authenticate(user=self.voter_one)

        response = self.client.get(f"/api/elections/{self.election.id}/results/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_votes"], 4)

    def test_admin_cannot_view_results_before_election_ends(self):
        self.election.status = Election.STATUS_ACTIVE
        self.election.start_datetime = timezone.now() - timedelta(hours=1)
        self.election.end_datetime = timezone.now() + timedelta(hours=1)
        self.election.save(update_fields=["status", "start_datetime", "end_datetime"])
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(f"/api/elections/{self.election.id}/results/")

        self.assertEqual(response.status_code, 403)
        self.assertIn("not available", response.data["detail"].lower())

    def test_voter_cannot_view_results_before_election_ends(self):
        self.election.status = Election.STATUS_ACTIVE
        self.election.start_datetime = timezone.now() - timedelta(hours=1)
        self.election.end_datetime = timezone.now() + timedelta(hours=1)
        self.election.save(update_fields=["status", "start_datetime", "end_datetime"])
        self.client.force_authenticate(user=self.voter_one)

        response = self.client.get(f"/api/elections/{self.election.id}/results/")

        self.assertEqual(response.status_code, 403)
        self.assertIn("not available", response.data["detail"].lower())

    def test_admin_can_view_results_before_election_ends(self):
        self.election.status = Election.STATUS_ACTIVE
        self.election.start_datetime = timezone.now() - timedelta(hours=1)
        self.election.end_datetime = timezone.now() + timedelta(hours=1)
        self.election.save(update_fields=["status", "start_datetime", "end_datetime"])
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(f"/api/elections/{self.election.id}/results/")

        self.assertEqual(response.status_code, 200)

    def test_ineligible_voter_cannot_view_results(self):
        self.client.force_authenticate(user=self.ineligible_voter)

        response = self.client.get(f"/api/elections/{self.election.id}/results/")

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_view_results(self):
        response = self.client.get(f"/api/elections/{self.election.id}/results/")

        self.assertEqual(response.status_code, 401)

    def test_phase10_submission_data_is_consumed_by_phase11_results(self):
        from rest_framework.test import APIClient

        active = Election.objects.create(
            name="Phase 10 to 11 Integration",
            eligible_voter_category="student",
            start_datetime=timezone.now() - timedelta(hours=1),
            end_datetime=timezone.now() + timedelta(hours=1),
            status=Election.STATUS_ACTIVE,
        )
        president = Position.objects.create(election=active, name="President", order=1)
        candidate_a = Candidate.objects.create(position=president, name="Candidate A")
        candidate_b = Candidate.objects.create(position=president, name="Candidate B")

        self.client.force_authenticate(user=self.voter_one)
        submit_one = self.client.post(
            "/api/votes/",
            {
                "election_id": active.id,
                "votes": [{"position_id": president.id, "candidate_id": candidate_a.id}],
            },
            format="json",
        )
        self.assertEqual(submit_one.status_code, 201)

        self.client.force_authenticate(user=self.voter_two)
        submit_two = self.client.post(
            "/api/votes/",
            {
                "election_id": active.id,
                "votes": [{"position_id": president.id, "candidate_id": candidate_b.id}],
            },
            format="json",
        )
        self.assertEqual(submit_two.status_code, 201)

        active.end_datetime = timezone.now() - timedelta(minutes=1)
        active.status = Election.STATUS_ENDED
        active.save(update_fields=["end_datetime", "status"])

        self.client.force_authenticate(user=self.admin)
        results = self.client.get(f"/api/elections/{active.id}/results/")
        self.assertEqual(results.status_code, 200)
        self.assertEqual(results.data["total_votes"], 2)
        rows = {row["candidate"]: row["percentage"] for row in results.data["results"][0]["candidates"]}
        self.assertEqual(rows, {"Candidate A": 50.0, "Candidate B": 50.0})
        self.assertEqual(len(results.data["results"][0]["winners"]), 2)


class Phase9VoterDashboardTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.now = timezone.now()

        self.student = User.objects.create_user(
            username="phase9-student",
            email="phase9-student@cmu.edu",
            password="StudentPass123!",
        )
        self.alumni = User.objects.create_user(
            username="phase9-alumni",
            email="phase9-alumni@cmu.edu",
            password="AlumniPass123!",
        )
        self.faculty = User.objects.create_user(
            username="phase9-faculty",
            email="phase9-faculty@cmu.edu",
            password="FacultyPass123!",
        )

        Profile.objects.create(
            user=self.student, role="student", cmu_email="phase9-student@cmu.edu",
            full_name="Phase 9 Student", must_change_password=False,
        )
        Profile.objects.create(
            user=self.alumni, role="alumni", cmu_email="phase9-alumni@cmu.edu",
            full_name="Phase 9 Alumni", must_change_password=False,
        )
        Profile.objects.create(
            user=self.faculty, role="faculty", cmu_email="phase9-faculty@cmu.edu",
            full_name="Phase 9 Faculty", must_change_password=False,
        )

        self.student_election = Election.objects.create(
            name="Student Election",
            description="Student election",
            eligible_voter_category="student",
            start_datetime=self.now - timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=1),
            status=Election.STATUS_ACTIVE,
        )
        self.alumni_election = Election.objects.create(
            name="Alumni Election",
            description="Alumni election",
            eligible_voter_category="alumni",
            start_datetime=self.now - timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=1),
            status=Election.STATUS_ACTIVE,
        )
        self.faculty_election = Election.objects.create(
            name="Faculty Election",
            description="Faculty election",
            eligible_voter_category="faculty",
            start_datetime=self.now - timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=1),
            status=Election.STATUS_ACTIVE,
        )
        self.position = Position.objects.create(
            election=self.student_election, name="President", order=1
        )
        Candidate.objects.create(position=self.position, name="Student Candidate")

    def test_student_sees_only_student_elections(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get("/api/elections/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({e["name"] for e in response.data}, {"Student Election"})

    def test_alumni_sees_only_alumni_elections(self):
        self.client.force_authenticate(user=self.alumni)
        response = self.client.get("/api/elections/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({e["name"] for e in response.data}, {"Alumni Election"})

    def test_faculty_sees_only_faculty_elections(self):
        self.client.force_authenticate(user=self.faculty)
        response = self.client.get("/api/elections/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({e["name"] for e in response.data}, {"Faculty Election"})

    def test_ineligible_election_details_are_not_exposed(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get(f"/api/elections/{self.alumni_election.id}/")
        self.assertEqual(response.status_code, 404)

    def test_eligible_election_details_include_positions_and_candidates(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get(f"/api/elections/{self.student_election.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "active")
        self.assertTrue(response.data["is_open"])
        self.assertEqual(response.data["positions"][0]["name"], "President")
        self.assertEqual(response.data["positions"][0]["candidates"][0]["name"], "Student Candidate")

    def test_not_started_status_is_reported_without_changing_stored_status(self):
        election = Election.objects.create(
            name="Future Student Election",
            eligible_voter_category="student",
            start_datetime=self.now + timedelta(hours=1),
            end_datetime=self.now + timedelta(hours=2),
            status=Election.STATUS_ACTIVE,
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get(f"/api/elections/{election.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "not_started")
        self.assertFalse(response.data["is_open"])
        self.assertEqual(election.status, Election.STATUS_ACTIVE)

    def test_ended_status_is_reported(self):
        election = Election.objects.create(
            name="Past Student Election",
            eligible_voter_category="student",
            start_datetime=self.now - timedelta(hours=2),
            end_datetime=self.now - timedelta(hours=1),
            status=Election.STATUS_ACTIVE,
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get(f"/api/elections/{election.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ended")
        self.assertFalse(response.data["is_open"])

    def test_unauthenticated_dashboard_and_details_are_rejected(self):
        self.assertEqual(self.client.get("/api/elections/").status_code, 401)
        self.assertEqual(
            self.client.get(f"/api/elections/{self.student_election.id}/").status_code, 401
        )


class Phase10VotingSystemTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        now = timezone.now()

        self.voter_one = User.objects.create_user(
            username="phase10-one", email="phase10-one@cmu.edu", password="VoterPass123!"
        )
        self.voter_two = User.objects.create_user(
            username="phase10-two", email="phase10-two@cmu.edu", password="VoterPass123!"
        )
        self.faculty = User.objects.create_user(
            username="phase10-faculty", email="phase10-faculty@cmu.edu", password="VoterPass123!"
        )
        Profile.objects.create(
            user=self.voter_one, role="student", cmu_email="phase10-one@cmu.edu",
            full_name="Voter One", must_change_password=False,
        )
        Profile.objects.create(
            user=self.voter_two, role="student", cmu_email="phase10-two@cmu.edu",
            full_name="Voter Two", must_change_password=False,
        )
        Profile.objects.create(
            user=self.faculty, role="faculty", cmu_email="phase10-faculty@cmu.edu",
            full_name="Faculty", must_change_password=False,
        )

        self.election = Election.objects.create(
            name="Phase 10 Student Election",
            eligible_voter_category="student",
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=1),
            status=Election.STATUS_ACTIVE,
        )
        self.other_election = Election.objects.create(
            name="Other Student Election",
            eligible_voter_category="student",
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=1),
            status=Election.STATUS_ACTIVE,
        )
        self.ended = Election.objects.create(
            name="Ended Election",
            eligible_voter_category="student",
            start_datetime=now - timedelta(hours=2),
            end_datetime=now - timedelta(hours=1),
            status=Election.STATUS_ACTIVE,
        )
        self.future = Election.objects.create(
            name="Future Election",
            eligible_voter_category="student",
            start_datetime=now + timedelta(hours=1),
            end_datetime=now + timedelta(hours=2),
            status=Election.STATUS_ACTIVE,
        )

        self.president = Position.objects.create(
            election=self.election, name="President", order=1
        )
        self.vice = Position.objects.create(
            election=self.election, name="Vice President", order=2
        )
        self.other_position = Position.objects.create(
            election=self.other_election, name="President", order=1
        )

        self.candidate_a = Candidate.objects.create(position=self.president, name="Candidate A")
        self.candidate_b = Candidate.objects.create(position=self.president, name="Candidate B")
        self.candidate_c = Candidate.objects.create(position=self.vice, name="Candidate C")
        self.other_candidate = Candidate.objects.create(
            position=self.other_position, name="Other Candidate"
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def ballot(self, election_id=None, votes=None, **extra):
        payload = {
            "election_id": election_id or self.election.id,
            "votes": votes if votes is not None else [
                {"position_id": self.president.id, "candidate_id": self.candidate_a.id},
                {"position_id": self.vice.id, "candidate_id": self.candidate_c.id},
            ],
        }
        payload.update(extra)
        return self.client.post("/api/votes/", payload, format="json")

    def test_valid_ballot_creates_all_votes(self):
        self.authenticate(self.voter_one)
        response = self.ballot()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["votes_created"], 2)
        self.assertEqual(
            Vote.objects.filter(voter=self.voter_one, election=self.election).count(), 2
        )

    def test_duplicate_position_vote_is_rejected(self):
        self.authenticate(self.voter_one)
        self.assertEqual(self.ballot().status_code, 201)
        response = self.client.post(
            "/api/votes/",
            {
                "election_id": self.election.id,
                "votes": [{"position_id": self.president.id, "candidate_id": self.candidate_b.id}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            Vote.objects.filter(voter=self.voter_one, election=self.election).count(), 2
        )

    def test_same_voter_can_vote_for_different_positions_when_allowed(self):
        self.authenticate(self.voter_one)
        response = self.ballot(
            votes=[{"position_id": self.president.id, "candidate_id": self.candidate_a.id}]
        )
        self.assertEqual(response.status_code, 201)
        response = self.ballot(
            votes=[{"position_id": self.vice.id, "candidate_id": self.candidate_c.id}]
        )
        self.assertEqual(response.status_code, 201)

    def test_two_voters_can_vote_for_same_candidate(self):
        self.authenticate(self.voter_one)
        self.assertEqual(
            self.ballot(votes=[{"position_id": self.president.id, "candidate_id": self.candidate_a.id}]).status_code,
            201,
        )
        self.authenticate(self.voter_two)
        self.assertEqual(
            self.ballot(votes=[{"position_id": self.president.id, "candidate_id": self.candidate_a.id}]).status_code,
            201,
        )
        self.assertEqual(Vote.objects.filter(candidate=self.candidate_a).count(), 2)

    def test_ended_election_is_rejected(self):
        self.authenticate(self.voter_one)
        response = self.ballot(election_id=self.ended.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Vote.objects.filter(voter=self.voter_one).count(), 0)

    def test_not_started_election_is_rejected(self):
        self.authenticate(self.voter_one)
        response = self.ballot(election_id=self.future.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("not started", response.data["detail"].lower())
        self.assertEqual(Vote.objects.filter(voter=self.voter_one).count(), 0)

    def test_ineligible_voter_is_rejected(self):
        self.authenticate(self.faculty)
        response = self.ballot()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Vote.objects.filter(voter=self.faculty).count(), 0)

    def test_cross_election_position_is_rejected(self):
        self.authenticate(self.voter_one)
        response = self.ballot(
            votes=[{"position_id": self.other_position.id, "candidate_id": self.other_candidate.id}]
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("position", response.data["detail"].lower())
        self.assertEqual(Vote.objects.filter(voter=self.voter_one).count(), 0)

    def test_cross_election_candidate_is_rejected(self):
        self.authenticate(self.voter_one)
        response = self.ballot(
            votes=[{"position_id": self.president.id, "candidate_id": self.other_candidate.id}]
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Vote.objects.filter(voter=self.voter_one).count(), 0)

    def test_cross_position_candidate_is_rejected(self):
        self.authenticate(self.voter_one)
        response = self.ballot(
            votes=[{"position_id": self.vice.id, "candidate_id": self.candidate_a.id}]
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Vote.objects.filter(voter=self.voter_one).count(), 0)

    def test_tampered_voter_id_does_not_change_authenticated_voter(self):
        self.authenticate(self.voter_one)
        response = self.ballot(voter_id=self.voter_two.id)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Vote.objects.filter(voter=self.voter_one).count(), 2)
        self.assertEqual(Vote.objects.filter(voter=self.voter_two).count(), 0)

    def test_unauthenticated_request_is_rejected(self):
        response = self.ballot()
        self.assertEqual(response.status_code, 401)

    def test_duplicate_position_in_one_ballot_is_rejected(self):
        self.authenticate(self.voter_one)
        response = self.ballot(
            votes=[
                {"position_id": self.president.id, "candidate_id": self.candidate_a.id},
                {"position_id": self.president.id, "candidate_id": self.candidate_b.id},
            ]
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Vote.objects.filter(voter=self.voter_one).count(), 0)

    def test_transaction_rolls_back_partial_ballot(self):
        from unittest.mock import patch

        self.authenticate(self.voter_one)
        original_create = Vote.objects.create
        calls = {"count": 0}

        def fail_on_second(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("forced failure")
            return original_create(*args, **kwargs)

        with patch("elections.views.Vote.objects.create", side_effect=fail_on_second):
            with self.assertRaises(RuntimeError):
                self.ballot()

        self.assertEqual(Vote.objects.filter(voter=self.voter_one).count(), 0)

    def test_account_inactive_is_rejected(self):
        self.voter_one.profile.account_status = "inactive"
        self.voter_one.profile.save(update_fields=["account_status"])
        self.voter_one.is_active = False
        self.voter_one.save(update_fields=["is_active"])
        self.authenticate(self.voter_one)
        response = self.ballot()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Vote.objects.filter(voter=self.voter_one).count(), 0)


class Phase12RealTimeAnalyticsTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        now = timezone.now()
        self.admin = User.objects.create_user(
            username="phase12-admin", email="phase12-admin@cmu.edu",
            password="AdminPass123!", is_staff=True,
        )
        self.voter_one = User.objects.create_user(
            username="phase12-voter-one", email="phase12-one@cmu.edu", password="VoterPass123!",
        )
        self.voter_two = User.objects.create_user(
            username="phase12-voter-two", email="phase12-two@cmu.edu", password="VoterPass123!",
        )
        self.voter_three = User.objects.create_user(
            username="phase12-voter-three", email="phase12-three@cmu.edu", password="VoterPass123!",
        )
        for user in [self.voter_one, self.voter_two, self.voter_three]:
            Profile.objects.create(
                user=user, role="student", cmu_email=user.email,
                full_name=user.username, must_change_password=False,
            )

        self.election = Election.objects.create(
            name="Phase 12 Analytics Election",
            eligible_voter_category="student",
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=1),
            status=Election.STATUS_ACTIVE,
        )
        self.president = Position.objects.create(election=self.election, name="President", order=1)
        self.vice = Position.objects.create(election=self.election, name="Vice President", order=2)
        self.president_a = Candidate.objects.create(position=self.president, name="Candidate A")
        self.president_b = Candidate.objects.create(position=self.president, name="Candidate B")
        self.vice_a = Candidate.objects.create(position=self.vice, name="Candidate C")

    def authenticate_admin(self):
        self.client.force_authenticate(user=self.admin)

    def analytics_url(self):
        return f"/api/admin/elections/{self.election.id}/analytics/"

    def test_analytics_returns_database_backed_metrics_and_breakdowns(self):
        Vote.objects.create(voter=self.voter_one, election=self.election, position=self.president, candidate=self.president_a)
        Vote.objects.create(voter=self.voter_two, election=self.election, position=self.president, candidate=self.president_b)
        Vote.objects.create(voter=self.voter_one, election=self.election, position=self.vice, candidate=self.vice_a)

        self.authenticate_admin()
        response = self.client.get(self.analytics_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["metrics"]["total_eligible_voters"], 3)
        self.assertEqual(response.data["metrics"]["total_votes"], 3)
        self.assertEqual(response.data["metrics"]["participants"], 2)
        self.assertEqual(response.data["metrics"]["turnout_percentage"], 66.67)
        self.assertEqual(response.data["metrics"]["position_count"], 2)
        self.assertEqual(response.data["metrics"]["candidate_count"], 3)
        self.assertNotIn("votes_per_position", response.data)
        self.assertNotIn("votes_per_candidate", response.data)
        self.assertIn("updated_at", response.data)

    def test_analytics_changes_when_vote_data_changes_without_page_refresh(self):
        self.authenticate_admin()

        first = self.client.get(self.analytics_url())
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["metrics"]["total_votes"], 0)
        self.assertEqual(first.data["metrics"]["participants"], 0)
        self.assertEqual(first.data["metrics"]["turnout_percentage"], 0.0)

        Vote.objects.create(
            voter=self.voter_one, election=self.election,
            position=self.president, candidate=self.president_a,
        )

        second = self.client.get(self.analytics_url())
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["metrics"]["total_votes"], 1)
        self.assertEqual(second.data["metrics"]["participants"], 1)
        self.assertEqual(second.data["metrics"]["turnout_percentage"], 33.33)
        self.assertNotIn("votes_per_position", second.data)
        self.assertNotIn("votes_per_candidate", second.data)

    def test_analytics_only_allows_administrators(self):
        self.client.force_authenticate(user=self.voter_one)
        response = self.client.get(self.analytics_url())
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(user=None)
        response = self.client.get(self.analytics_url())
        self.assertEqual(response.status_code, 401)

    def voter_analytics_url(self):
        return f"/api/elections/{self.election.id}/analytics/"

    def test_eligible_voter_can_view_live_aggregate_analytics(self):
        self.client.force_authenticate(user=self.voter_one)
        response = self.client.get(self.voter_analytics_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["metrics"]["total_eligible_voters"], 3)
        self.assertEqual(response.data["metrics"]["total_votes"], 0)
        self.assertEqual(response.data["metrics"]["participants"], 0)
        self.assertEqual(response.data["metrics"]["turnout_percentage"], 0.0)
        self.assertNotIn("votes_per_position", response.data)
        self.assertNotIn("votes_per_candidate", response.data)

    def test_voter_analytics_updates_when_vote_data_changes(self):
        self.client.force_authenticate(user=self.voter_one)
        first = self.client.get(self.voter_analytics_url())
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["metrics"]["total_votes"], 0)

        Vote.objects.create(
            voter=self.voter_two, election=self.election,
            position=self.president, candidate=self.president_a,
        )

        second = self.client.get(self.voter_analytics_url())
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["metrics"]["total_votes"], 1)
        self.assertEqual(second.data["metrics"]["participants"], 1)
        self.assertEqual(second.data["metrics"]["turnout_percentage"], 33.33)

    def test_voter_analytics_rejects_ineligible_voter(self):
        faculty_user = User.objects.create_user(
            username="phase12-faculty", email="phase12-faculty@cmu.edu", password="VoterPass123!",
        )
        Profile.objects.create(
            user=faculty_user, role="faculty", cmu_email=faculty_user.email,
            full_name="Phase 12 Faculty", must_change_password=False,
        )
        self.client.force_authenticate(user=faculty_user)
        response = self.client.get(self.voter_analytics_url())
        self.assertEqual(response.status_code, 403)

    def test_voter_analytics_rejects_password_change_required_voter(self):
        self.voter_one.profile.must_change_password = True
        self.voter_one.profile.save(update_fields=["must_change_password"])
        self.client.force_authenticate(user=self.voter_one)
        response = self.client.get(self.voter_analytics_url())
        self.assertEqual(response.status_code, 403)

    def test_analytics_handles_zero_eligible_voters_without_division_error(self):
        self.election.eligible_voter_category = "faculty"
        self.election.save(update_fields=["eligible_voter_category"])
        self.authenticate_admin()

        response = self.client.get(self.analytics_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["metrics"]["total_eligible_voters"], 0)
        self.assertEqual(response.data["metrics"]["turnout_percentage"], 0.0)


class Phase13AuditLoggingTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()
        now = timezone.now()
        self.admin = User.objects.create_user(username="phase13-admin", email="phase13-admin@cmu.edu", password="AdminPass123!", is_staff=True)
        self.voter = User.objects.create_user(username="phase13-voter", email="phase13-voter@cmu.edu", password="VoterPass123!")
        Profile.objects.create(user=self.voter, role="student", cmu_email=self.voter.email, full_name="Phase 13 Voter", must_change_password=False)
        self.election = Election.objects.create(name="Phase 13 Election", eligible_voter_category="student", start_datetime=now-timedelta(hours=1), end_datetime=now+timedelta(hours=1), status=Election.STATUS_ACTIVE)
        self.position = Position.objects.create(election=self.election, name="President", order=1)
        self.candidate = Candidate.objects.create(position=self.position, name="Candidate A")

    def admin_auth(self): self.client.force_authenticate(user=self.admin)

    def test_authentication_events_are_logged_without_credentials(self):
        self.assertEqual(self.client.post("/api/auth/admin/login/", {"email": self.admin.email, "password": "AdminPass123!"}, format="json").status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action="admin_login", actor=self.admin).exists())
        self.client.post("/api/auth/login/", {"email": self.voter.email, "password": "VoterPass123!", "role": "student"}, format="json")
        self.assertTrue(AuditLog.objects.filter(action="voter_login", actor=self.voter).exists())
        self.client.post("/api/auth/login/", {"email": self.voter.email, "password": "WrongPassword!", "role": "student"}, format="json")
        log=AuditLog.objects.filter(action="security_login_failure").latest("id")
        self.assertIsNone(log.actor); self.assertNotIn("WrongPassword", log.description); self.assertNotIn(self.voter.email, log.description)

    def test_account_events_are_logged(self):
        self.admin_auth()
        r=self.client.post("/api/admin/voters/", {"name":"New Voter","identifier":"phase13-new","email":"phase13-new@cmu.edu","category":"student","password":"NewVoterPass123!","status":"active"}, format="json")
        self.assertEqual(r.status_code,201); vid=r.data["id"]
        self.assertTrue(AuditLog.objects.filter(action="account_created",target_object_id=str(vid)).exists())
        self.assertEqual(self.client.patch(f"/api/admin/voters/{vid}/", {"name":"Updated Voter"}, format="json").status_code,200)
        self.assertTrue(AuditLog.objects.filter(action="account_modified",target_object_id=str(vid)).exists())
        self.assertEqual(self.client.patch(f"/api/admin/voters/{vid}/", {"status":"inactive"}, format="json").status_code,200)
        self.assertTrue(AuditLog.objects.filter(action="account_deactivated",target_object_id=str(vid)).exists())
        self.assertEqual(self.client.post(f"/api/admin/voters/{vid}/reset-password/", {"password":"ResetPass123!","confirm_password":"ResetPass123!"}, format="json").status_code,200)
        self.assertTrue(AuditLog.objects.filter(action="password_reset",target_object_id=str(vid)).exists())
        self.assertFalse(AuditLog.objects.filter(target_object_id=str(vid),description__icontains="password").filter(description__icontains="ResetPass123!").exists())

    def test_election_position_candidate_and_voting_events_are_logged(self):
        self.admin_auth()
        r=self.client.post("/api/admin/elections/", {"name":"Logged Election","description":"Audit test","eligible_voter_category":"student","start_datetime":(self.election.start_datetime).isoformat(),"end_datetime":(self.election.end_datetime).isoformat()}, format="json")
        self.assertEqual(r.status_code,201); eid=r.data["id"]
        self.assertTrue(AuditLog.objects.filter(action="election_created",target_object_id=str(eid)).exists())
        self.assertEqual(self.client.patch(f"/api/admin/elections/{eid}/", {"description":"Updated"}, format="json").status_code,200)
        self.assertTrue(AuditLog.objects.filter(action="election_modified",target_object_id=str(eid)).exists())
        r=self.client.post(f"/api/admin/elections/{eid}/positions/", {"name":"Vice President","order":2}, format="json")
        self.assertEqual(r.status_code,201); pid=r.data["id"]
        self.assertTrue(AuditLog.objects.filter(action="position_created",target_object_id=str(pid)).exists())
        self.assertEqual(self.client.patch(f"/api/admin/positions/{pid}/", {"name":"VP Updated"}, format="json").status_code,200)
        self.assertTrue(AuditLog.objects.filter(action="position_modified",target_object_id=str(pid)).exists())
        r=self.client.post(f"/api/admin/elections/{eid}/positions/{pid}/candidates/", {"name":"Logged Candidate"}, format="json")
        self.assertEqual(r.status_code,201); cid=r.data["id"]
        self.assertTrue(AuditLog.objects.filter(action="candidate_created",target_object_id=str(cid)).exists())
        self.assertEqual(self.client.patch(f"/api/admin/candidates/{cid}/", {"name":"Candidate Updated"}, format="json").status_code,200)
        self.assertTrue(AuditLog.objects.filter(action="candidate_modified",target_object_id=str(cid)).exists())
        self.assertEqual(self.client.delete(f"/api/admin/candidates/{cid}/").status_code,204)
        self.assertTrue(AuditLog.objects.filter(action="candidate_deleted",target_object_id=str(cid)).exists())
        self.assertEqual(self.client.delete(f"/api/admin/positions/{pid}/").status_code,204)
        self.assertTrue(AuditLog.objects.filter(action="position_deleted",target_object_id=str(pid)).exists())
        e=Election.objects.get(pk=eid); e.status=Election.STATUS_ENDED; e.end_datetime=timezone.now()-timedelta(minutes=1); e.save(update_fields=["status","end_datetime"])
        self.assertEqual(self.client.delete(f"/api/admin/elections/{eid}/").status_code,204)
        self.assertTrue(AuditLog.objects.filter(action="election_deleted",target_object_id=str(eid)).exists())

        self.client.force_authenticate(user=self.voter)
        r=self.client.post("/api/votes/", {"election_id":self.election.id,"votes":[{"position_id":self.position.id,"candidate_id":self.candidate.id}]}, format="json")
        self.assertEqual(r.status_code,201)
        log=AuditLog.objects.filter(action="vote_submitted",actor=self.voter).latest("id")
        self.assertNotIn("Candidate A", log.description)
        self.assertEqual(self.client.post("/api/votes/", {"election_id":self.election.id,"votes":[{"position_id":self.position.id,"candidate_id":self.candidate.id}]}, format="json").status_code,400)
        self.assertTrue(AuditLog.objects.filter(action="security_duplicate_vote_attempt",actor=self.voter).exists())

    def test_admin_audit_endpoint_supports_search_filter_sort_and_is_protected(self):
        AuditLog.objects.create(actor=self.admin,action="TEST_EVENT",target_model="Election",target_object_id=str(self.election.id),description="Unique audit search text")
        self.admin_auth()
        r=self.client.get("/api/admin/audit-logs/?search=Unique%20audit%20search%20text&sort=asc")
        self.assertEqual(r.status_code,200); self.assertEqual(len(r.data["logs"]),1); self.assertEqual(r.data["logs"][0]["action"],"TEST_EVENT")
        self.client.force_authenticate(user=self.voter); self.assertEqual(self.client.get("/api/admin/audit-logs/").status_code,403)
        self.client.force_authenticate(user=None); self.assertEqual(self.client.get("/api/admin/audit-logs/").status_code,401)

    def test_logout_events_are_logged(self):
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action="admin_logout", actor=self.admin).exists())
        self.client.force_authenticate(user=self.voter)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action="voter_logout", actor=self.voter).exists())
