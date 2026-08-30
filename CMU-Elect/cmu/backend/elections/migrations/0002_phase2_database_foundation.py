from datetime import timedelta

from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


VOTER_CATEGORY_CHOICES = [
    ("student", "Student"),
    ("alumni", "Alumni"),
    ("faculty", "Faculty"),
]


STATUS_CHOICES = [
    ("active", "Active"),
    ("ended", "Ended"),
]


def populate_phase2_fields(apps, schema_editor):
    Profile = apps.get_model("elections", "Profile")
    Election = apps.get_model("elections", "Election")
    User = apps.get_model("auth", "User")

    for profile in Profile.objects.select_related("user").all():
        user = profile.user
        full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
        profile.full_name = full_name
        if not user.email:
            user.email = profile.cmu_email
            user.save(update_fields=["email"])
        profile.account_status = "active" if user.is_active else "inactive"
        profile.must_change_password = False
        profile.created_at = timezone.now()
        profile.updated_at = timezone.now()
        profile.save(update_fields=["full_name", "account_status", "must_change_password", "created_at", "updated_at"])

    now = timezone.now()
    for election in Election.objects.all():
        election.status = "active" if election.is_open else "ended"
        # Existing Phase 1 elections had no schedule. Preserve their creation
        # time as the starting point and provide a safe one-year migration window.
        election.start_datetime = election.created_at
        election.end_datetime = election.created_at + timedelta(days=365)
        if election.end_datetime <= now:
            election.end_datetime = now + timedelta(days=365)
        election.updated_at = timezone.now()
        election.save(update_fields=[
            "status",
            "start_datetime",
            "end_datetime",
            "updated_at",
        ])


def reverse_phase2_fields(apps, schema_editor):
    # The reverse migration restores the old election fields from the new ones.
    Election = apps.get_model("elections", "Election")
    for election in Election.objects.all():
        election.audience = election.eligible_voter_category
        election.is_open = election.status == "active"
        election.save(update_fields=["audience", "is_open"])


class Migration(migrations.Migration):
    dependencies = [
        ("elections", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="full_name",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="profile",
            name="account_status",
            field=models.CharField(
                choices=[("active", "Active"), ("inactive", "Inactive")],
                db_index=True,
                default="active",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="must_change_password",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="profile",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="profile",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AddField(
            model_name="election",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="election",
            name="start_datetime",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="election",
            name="end_datetime",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="election",
            name="status",
            field=models.CharField(
                choices=STATUS_CHOICES,
                db_index=True,
                default="active",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="election",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.RunPython(populate_phase2_fields, reverse_phase2_fields),
        migrations.AlterField(
            model_name="profile",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name="profile",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name="election",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name="election",
            name="start_datetime",
            field=models.DateTimeField(),
        ),
        migrations.AlterField(
            model_name="election",
            name="end_datetime",
            field=models.DateTimeField(),
        ),
        migrations.RenameField(
            model_name="election",
            old_name="audience",
            new_name="eligible_voter_category",
        ),
        migrations.AlterField(
            model_name="election",
            name="eligible_voter_category",
            field=models.CharField(
                choices=VOTER_CATEGORY_CHOICES,
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.RemoveField(
            model_name="election",
            name="is_open",
        ),
        migrations.AlterField(
            model_name="profile",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="profile",
                to="auth.user",
            ),
        ),
        migrations.AlterField(
            model_name="vote",
            name="election",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="votes",
                to="elections.election",
            ),
        ),
        migrations.AlterField(
            model_name="vote",
            name="position",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="votes",
                to="elections.position",
            ),
        ),
        migrations.AlterField(
            model_name="vote",
            name="candidate",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="votes",
                to="elections.candidate",
            ),
        ),
        migrations.AddConstraint(
            model_name="election",
            constraint=models.CheckConstraint(
                condition=models.Q(start_datetime__lt=models.F("end_datetime")),
                name="election_start_before_end",
            ),
        ),
        migrations.AddConstraint(
            model_name="position",
            constraint=models.UniqueConstraint(
                fields=("election", "name"),
                name="unique_position_name_per_election",
            ),
        ),
        migrations.AddConstraint(
            model_name="candidate",
            constraint=models.UniqueConstraint(
                fields=("position", "name"),
                name="unique_candidate_name_per_position",
            ),
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=100)),
                ("timestamp", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("target_model", models.CharField(blank=True, max_length=100)),
                ("target_object_id", models.CharField(blank=True, max_length=64)),
                ("description", models.TextField(blank=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to="auth.user",
                    ),
                ),
            ],
            options={"ordering": ["-timestamp", "-id"]},
        ),
    ]
