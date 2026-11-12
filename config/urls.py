from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from matching.views import SessionHistoryView

urlpatterns = [
    path("", RedirectView.as_view(url="/api/v1/screening/ping/"), name="home"),
    path("admin/", admin.site.urls),
    path("api/sessions", SessionHistoryView.as_view(), name="session-history-compat"),
    path("api/v1/", include("common.urls")),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/screening/", include("screening.urls")),
    path("api/v1/matching/", include("matching.urls")),
    path("api/v1/vectorsearch/", include("vectorsearch.urls")),
    path("api/v1/resumes/", include("resumes.urls")),
    path("api/v1/interview/", include("interview.urls")),
]
