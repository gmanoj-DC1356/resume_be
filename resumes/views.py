"""Module 5 - Resume viewer: secure resume file serving.

Owner: Manoj (Phase 1)
Pattern to follow: serializer -> view -> permission check -> url -> test.
"""
import logging

from django.http import FileResponse
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import CanViewResume
from .services import ResumeFileUnavailable, find_resume, open_resume_pdf

logger = logging.getLogger(__name__)

PDF_CONTENT_TYPE = "application/pdf"
# One message for every "cannot serve this" case, so callers cannot tell a missing resume from a damaged one.
NOT_AVAILABLE = "Resume not available."


@api_view(["GET"])
def ping(request):
    # IsAuthenticated is the project default. Add object-level checks for real endpoints.
    return Response({"app": "resumes", "status": "ok"})


class ResumePdfView(APIView):
    """GET /api/v1/resumes/<resume_id>/pdf/ - streams the resume for in-app reading.

    `resume_id` is the id search results return as `resumeId`. The stored file location is never
    sent to the client; the file is served only after the access check.
    """

    permission_classes = [CanViewResume]

    def perform_content_negotiation(self, request, force=False):
        # The reader asks for Accept: application/pdf, which the JSON-only API renderer cannot satisfy.
        # Forcing negotiation keeps the file response and still renders errors as JSON instead of a 406.
        return super().perform_content_negotiation(request, force=True)

    def get(self, request, resume_id: str):
        resume = find_resume(resume_id)
        if resume is None:
            raise NotFound(NOT_AVAILABLE)
        self.check_object_permissions(request, resume)
        try:
            stored = open_resume_pdf(resume)
        except ResumeFileUnavailable as error:
            logger.warning("Resume file unavailable for %s: %s", resume.candidate_ref, error)
            raise NotFound(NOT_AVAILABLE) from None

        response = FileResponse(
            stored,
            content_type=PDF_CONTENT_TYPE,
            as_attachment=False,
            # Named after the public id, never the candidate, so no personal data reaches the headers.
            filename=f"{resume_id}.pdf",
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
