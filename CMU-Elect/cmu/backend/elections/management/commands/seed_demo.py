from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from elections.models import Profile, Election, Position, Candidate

class Command(BaseCommand):
    help = "Create demo CMU-ELECT users, elections, positions, and candidates."

    def handle(self, *args, **kwargs):
        demo = [
            ("student_demo", "student", "student@cmu.edu"),
            ("alumni_demo", "alumni", "alumni@cmu.edu"),
            ("faculty_demo", "faculty", "faculty@cmu.edu"),
        ]
        for username, role, email in demo:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password("DemoPass123!")
                user.save()
            Profile.objects.update_or_create(
                user=user,
                defaults={
                    "role": role,
                    "cmu_email": email,
                    "account_status": "active",
                    "must_change_password": True,
                },
            )

        for role, name in [
            ("student", "STUDENT ELECTION"),
            ("alumni", "ALUMNI ELECTION"),
            ("faculty", "FACULTY ELECTION"),
        ]:
            election, _ = Election.objects.get_or_create(
                audience=role, defaults={"name": name, "is_open": True}
            )
            for i, position_name in enumerate(
                ["President", "Vice President", "Secretary", "Treasurer", "Peace Officer"], 1
            ):
                position, _ = Position.objects.get_or_create(
                    election=election, name=position_name, defaults={"order": i}
                )
                if not position.candidates.exists():
                    Candidate.objects.create(
                        position=position, name="Juan Dela Cruz",
                        department="College of Computer Studies",
                        platform="Transparency, Improvements, Unity",
                        gwa=1.25, party_list="Party List"
                    )
                    Candidate.objects.create(
                        position=position, name="Maria Santos",
                        department="College of Computer Studies",
                        platform="Service, Accountability, Student Voice",
                        gwa=1.50, party_list="Independent"
                    )
        self.stdout.write(self.style.SUCCESS(
            "Demo data ready. Password for all demo users: DemoPass123!"
        ))
