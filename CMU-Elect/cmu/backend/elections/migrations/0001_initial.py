# Generated for the CMU-ELECT starter. It is equivalent to running makemigrations.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Election",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("audience", models.CharField(choices=[("student", "Student"), ("alumni", "Alumni"), ("faculty", "Faculty")], max_length=20)),
                ("is_open", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="PasswordResetRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("code_hash", models.CharField(max_length=64)),
                ("reset_token_hash", models.CharField(blank=True, max_length=64)),
                ("expires_at", models.DateTimeField()),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Profile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("student", "Student"), ("alumni", "Alumni"), ("faculty", "Faculty")], max_length=20)),
                ("cmu_email", models.EmailField(max_length=254, unique=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Position",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("order", models.PositiveIntegerField(default=0)),
                ("election", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="positions", to="elections.election")),
            ],
            options={"ordering": ["order", "id"]},
        ),
        migrations.CreateModel(
            name="Candidate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("department", models.CharField(blank=True, max_length=120)),
                ("platform", models.TextField(blank=True)),
                ("gwa", models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ("party_list", models.CharField(blank=True, max_length=120)),
                ("photo", models.ImageField(blank=True, null=True, upload_to="candidates/")),
                ("position", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="candidates", to="elections.position")),
            ],
        ),
        migrations.CreateModel(
            name="Vote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("candidate", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="elections.candidate")),
                ("election", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="elections.election")),
                ("position", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="elections.position")),
                ("voter", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="votes", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="vote",
            constraint=models.UniqueConstraint(fields=("voter", "election", "position"), name="one_vote_per_voter_position"),
        ),
    ]
