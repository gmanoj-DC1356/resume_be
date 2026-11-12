"""Module 2 - Home/Dashboard: JD input, screening results, session history.

Owner: Veeran (Phase 1)
Pattern to follow: serializer -> view -> permission check -> url -> test.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from matching.conf import search_mode
from matching.sample_service import run_sample_search
from matching.search_service import SearchUnavailable, run_search

from .serializers import SearchRequestSerializer


@api_view(["GET"])
def ping(request):
    # IsAuthenticated is the project default. Add object-level checks for real endpoints.
    return Response({"app": "screening", "status": "ok"})


class SearchUnavailableError(APIException):
    status_code = 503
    default_detail = "Search is temporarily unavailable."
    default_code = "search_unavailable"


class SearchView(APIView):
    """POST: rank resumes for a job title, skills and job description.

    Ranking is done by the matching engine: `run_sample_search` (seeded DB rows, default for now) or
    `run_search` (Milvus), chosen by MATCHING_SEARCH_MODE.
    In DEBUG, unauthenticated local UI requests use a non-login dev account. Production remains
    protected by the project default (IsAuthenticated).
    """

    def get_permissions(self):
        if settings.DEBUG:
            return [AllowAny()]
        return super().get_permissions()

    def post(self, request):
        serializer = SearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        search = run_sample_search if search_mode() == "sample" else run_search
        user = request.user
        if not user.is_authenticated:
            user, _ = get_user_model().objects.get_or_create(
                username="local_dev",
                defaults={"is_active": False},
            )
        try:
            results = search(
                user=user,
                job_title=data["jobTitle"],
                skills=data["skills"],
                jd_text=data["jobDescription"],
                top_n=data["topN"],
            )
        except SearchUnavailable:
            raise SearchUnavailableError()
        return Response(results)
