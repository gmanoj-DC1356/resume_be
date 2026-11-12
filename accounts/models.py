from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """Azure AD identity for a Django auth user (the USERS table in the RDM).

    The built-in user supplies id, email, last_login (= last_login_at) and date_joined (= created_at);
    this table adds the Azure AD object id and display name.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    aad_oid = models.UUIDField(unique=True)  # Azure AD object id (immutable per user)
    name = models.CharField(max_length=255, blank=True)

    def __str__(self) -> str:
        return f"{self.name or self.user_id} ({self.aad_oid})"
