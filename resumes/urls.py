from django.urls import path, re_path

from . import views

app_name = "resumes"

# Public resume ids look like "r_ab12cd34" or an external id: letters, digits, '-' and '_' only.
RESUME_ID_PATTERN = r"[A-Za-z0-9_-]{1,64}"

urlpatterns = [
    path("ping/", views.ping, name="ping"),  # placeholder - replace with real endpoints
    # A malformed id never matches this pattern, so it is a plain 404 before any lookup happens.
    re_path(rf"^(?P<resume_id>{RESUME_ID_PATTERN})/pdf/$", views.ResumePdfView.as_view(), name="pdf"),
]
