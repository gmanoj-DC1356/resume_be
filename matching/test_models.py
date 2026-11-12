"""Synthetic data only."""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from matching.models import SearchResult, SearchSession
from resumes.models import Resume


class SearchModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tester", password="x-unused-test-pw-1")
        self.session = SearchSession.objects.create(
            user=self.user, job_title="Frontend Engineer", skills_json=["React", "TypeScript"]
        )
        self.resume_a = Resume.objects.create(candidate_ref="aaaaaaaaaaaaaaaa", resume_uri="file://synthetic/a.pdf")
        self.resume_b = Resume.objects.create(candidate_ref="bbbbbbbbbbbbbbbb", resume_uri="file://synthetic/b.pdf")

    def _result(self, resume, score, rank):
        return SearchResult.objects.create(session=self.session, candidate=resume, score=score, rank_position=rank)

    def test_relations_and_ordering(self):
        self._result(self.resume_b, 0.7, 2)
        self._result(self.resume_a, 0.9, 1)
        self.assertEqual([r.candidate_id for r in self.session.results.all()], ["aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"])
        self.assertEqual(self.user.search_sessions.count(), 1)
        self.assertEqual(self.resume_a.search_results.count(), 1)

    def test_duplicate_candidate_or_rank_rejected(self):
        self._result(self.resume_a, 0.9, 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._result(self.resume_a, 0.8, 2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._result(self.resume_b, 0.8, 1)

    def test_score_range_enforced(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._result(self.resume_a, 1.5, 1)

    def test_resume_with_results_is_protected(self):
        from django.db.models import ProtectedError

        self._result(self.resume_a, 0.9, 1)
        with self.assertRaises(ProtectedError):
            self.resume_a.delete()
