from django.db import models


class Resume(models.Model):
    """Resume catalogue entry (RESUMES table). Files live in storage; only URIs are kept here."""

    # Same value as the Milvus `resume_id` (content-hash prefix), so both stores join on it.
    candidate_ref = models.CharField(max_length=64, primary_key=True)
    resume_uri = models.CharField(max_length=1024)  # location of the original PDF; never returned raw to clients
    summary_uri = models.CharField(max_length=1024, blank=True)  # parsed/summary artifact, filled after parsing
    external_id = models.CharField(max_length=64, blank=True)  # public id shown to the UI (e.g. "r_104"); blank => derived
    # Parsed at ingest (matching.ingestion.resume_parser); used to build search responses.
    display_name = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=200, blank=True)
    years_experience = models.PositiveSmallIntegerField(default=0)
    skills_json = models.JSONField(default=list)  # list of skill strings
    summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.candidate_ref
