from django.conf import settings
from django.db import models

class PermissionAudit(models.Model):
    class Action(models.TextChoices):
        ASSIGNED = "ASSIGNED", "Assigned"
        REVOKED = "REVOKED", "Revoked"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="permission_actions"
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="permission_changes"
    )
    function = models.ForeignKey(
        "permissions.Function", on_delete=models.PROTECT
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["target_user", "-created_at"], name="idx_audit_target_date")
        ]
