"""Module 3 - Resume matching engine & knowledge base.

Owner: Vinay (Phase 1)
Pattern to follow: serializer -> view -> permission check -> url -> test.

The search endpoint lives in the screening app (`POST /api/v1/screening/search/`) and calls
`matching.search_service.run_search`.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.paginator import EmptyPage, Paginator
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.serializers import CharField, ChoiceField, DateTimeField, IntegerField, Serializer
from rest_framework.views import APIView

from matching.models import SearchSession
from matching.presenters import candidate_payload, split_skills
from matching.skills import normalize_skill


@api_view(["GET"])
def ping(request):
    # IsAuthenticated is the project default. Add object-level checks for real endpoints.
    return Response({"app": "matching", "status": "ok"})


class SessionHistoryFilters(Serializer):
    type = ChoiceField(choices=("match", "questions"), required=False)
    query = CharField(max_length=100, required=False, allow_blank=True, trim_whitespace=True)
    from_timestamp = DateTimeField(required=False)
    to_timestamp = DateTimeField(required=False)
    page = IntegerField(min_value=1, required=False, default=1)

    def to_internal_value(self, data):
        mapped = data.copy()
        if "from" in mapped:
            mapped["from_timestamp"] = mapped.get("from")
        if "to" in mapped:
            mapped["to_timestamp"] = mapped.get("to")
        return super().to_internal_value(mapped)


class SessionHistoryView(APIView):
    """List the current user's search history for the UI sidebar."""

    page_size = 20

    def get_permissions(self):
        if settings.DEBUG:
            return [AllowAny()]
        return super().get_permissions()

    def get(self, request):
        filters = SessionHistoryFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data

        user = request.user
        if not user.is_authenticated:
            user = get_user_model().objects.filter(username="local_dev").first()
            if user is None:
                return Response([])

        sessions = SearchSession.objects.filter(user=user)
        if values.get("type") == "questions":
            sessions = sessions.none()
        if query := values.get("query"):
            sessions = sessions.filter(job_title__icontains=query)
        if from_timestamp := values.get("from_timestamp"):
            sessions = sessions.filter(created_at__gte=from_timestamp)
        if to_timestamp := values.get("to_timestamp"):
            sessions = sessions.filter(created_at__lte=to_timestamp)

        page = Paginator(sessions.order_by("-created_at"), self.page_size)
        try:
            entries = page.page(values["page"])
        except EmptyPage:
            return Response([])

        return Response(
            [
                {
                    "id": str(session.pk),
                    "title": session.job_title,
                    "type": "match",
                    "createdAt": session.created_at.isoformat(),
                }
                for session in entries
            ]
        )


class SessionTitleSerializer(Serializer):
    """Allowlist validation for renaming a history entry."""

    title = CharField(max_length=200, trim_whitespace=True)


class SessionDetailView(APIView):
    """GET: the saved results of one history entry. PATCH: rename it. DELETE: remove it.

    Auth: IsAuthenticated (project default, deliberately not relaxed in DEBUG). The lookup is scoped
    to request.user, so another user's id returns 404 rather than revealing that it exists.
    """

    def get_session(self, request, pk):
        return get_object_or_404(SearchSession, pk=pk, user=request.user)

    def get(self, request, pk):
        session = self.get_session(request, pk)
        requested = session.skills_json
        rows = session.results.select_related("candidate").order_by("rank_position")
        candidates = []
        for row in rows:
            matched, missing = split_skills(requested, row.candidate.skills_json, normalize_skill)
            candidates.append(candidate_payload(row.candidate, row.score, matched, missing))
        return Response(
            {
                "id": str(session.pk),
                "title": session.job_title,
                "skills": requested,
                "jobDescription": session.jd_text,
                "candidates": candidates,
            }
        )

    def patch(self, request, pk):
        session = self.get_session(request, pk)
        serializer = SessionTitleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session.job_title = serializer.validated_data["title"]
        session.save(update_fields=["job_title"])
        return Response(
            {
                "id": str(session.pk),
                "title": session.job_title,
                "type": "match",
                "createdAt": session.created_at.isoformat(),
            }
        )

    def delete(self, request, pk):
        self.get_session(request, pk).delete()
        return Response(status=204)
