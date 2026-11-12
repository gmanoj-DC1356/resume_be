from django.conf import settings
from django.db import models


class SearchSession(models.Model):
    """One job-description search run by a user (SEARCH_SESSIONS table)."""

    class Status(models.TextChoices):
        PENDING = "PENDING"
        RUNNING = "RUNNING"
        COMPLETED = "COMPLETED"
        FAILED = "FAILED"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="search_sessions")
    job_title = models.CharField(max_length=200)
    skills_json = models.JSONField(default=list)  # list of skill strings extracted/entered for the search
    jd_text = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    result_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"], name="session_user_created_idx")]

    def __str__(self) -> str:
        return f"{self.job_title} ({self.status})"


class SearchResult(models.Model):
    """One ranked candidate for a session (SEARCH_RESULTS table)."""

    session = models.ForeignKey(SearchSession, on_delete=models.CASCADE, related_name="results")
    candidate = models.ForeignKey(
        "resumes.Resume",
        on_delete=models.PROTECT,  # keep result history; a resume with results cannot be deleted silently
        related_name="search_results",
        db_column="candidate_ref",
    )
    score = models.FloatField()  # normalised match score, 0..1
    rank_position = models.PositiveIntegerField()  # 1 = best
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["session", "rank_position"]
        constraints = [
            models.UniqueConstraint(fields=["session", "candidate"], name="result_unique_candidate_per_session"),
            models.UniqueConstraint(fields=["session", "rank_position"], name="result_unique_rank_per_session"),
            models.CheckConstraint(condition=models.Q(score__gte=0, score__lte=1), name="result_score_0_1"),
            models.CheckConstraint(condition=models.Q(rank_position__gte=1), name="result_rank_gte_1"),
        ]

    def __str__(self) -> str:
        return f"#{self.rank_position} {self.candidate_id} ({self.score:.3f})"
