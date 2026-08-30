from django.contrib import admin
from .models import Profile, Election, Position, Candidate, Vote, AuditLog, PasswordResetRequest

admin.site.register(Profile)
admin.site.register(Election)
admin.site.register(Position)
admin.site.register(Candidate)
admin.site.register(Vote)
admin.site.register(AuditLog)
admin.site.register(PasswordResetRequest)
