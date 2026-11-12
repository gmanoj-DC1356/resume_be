"""Search API tests. Embedder and Milvus are faked; data is synthetic."""
import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from matching.models import SearchResult, SearchSession
from resumes.models import Resume

URL = "/api/v1/screening/search/"


class FakeEmbedder:
    def embed_query(self, query):
        return [0.0] * 4


def make_resume(ref, name, role, years, skills, summary="Synthetic summary."):
    return Resume.objects.create(
        candidate_ref=ref, resume_uri=f"file://synthetic/{ref}.pdf", display_name=name, role=role,
        years_experience=years, skills_json=skills, summary=summary,
    )


def hit(resume_id, sim):
    return {"id": f"{resume_id}:0", "distance": sim, "entity": {"resume_id": resume_id, "section": "skills"}}


class SearchApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tester", password="x-unused-test-pw-1")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        make_resume("a" * 16, "Candidate A", "Data Engineer", 8, ["Python", "SQL", "Spark", "Azure"])
        make_resume("b" * 16, "Candidate B", "Analytics Engineer", 6, ["Python", "Azure", "SQL"])
        self.hits = [hit("a" * 16, 0.9), hit("b" * 16, 0.85), hit("c" * 16, 0.8)]  # "c" has no catalogue row
        patches = [
            mock.patch.dict(os.environ, {"MATCHING_SEARCH_MODE": "vector"}),
            mock.patch("matching.search_service.get_embedder", return_value=FakeEmbedder()),
            mock.patch("matching.search_service.get_shared_client", return_value=object()),
            mock.patch("matching.search_service.search_chunks", side_effect=lambda *a, **k: self.hits),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def post(self, body):
        return self.client.post(URL, body, format="json")

    def test_requires_authentication(self):
        res = APIClient().post(URL, {"jobTitle": "x", "skills": ["Python"]}, format="json")
        self.assertIn(res.status_code, (401, 403))

    def test_response_shape_and_ranking(self):
        res = self.post({"jobTitle": "Data Engineer", "skills": ["Python", "SQL", "Spark", "Azure"]})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)  # unknown resume skipped
        first, second = res.data
        self.assertEqual(
            set(first),
            {"resumeId", "candidateRef", "name", "role", "yearsExperience", "score", "matchedSkills", "missingSkills", "summary"},
        )
        self.assertEqual(first["name"], "Candidate A")
        self.assertEqual(first["matchedSkills"], ["Python", "SQL", "Spark", "Azure"])
        self.assertEqual(first["missingSkills"], [])
        self.assertEqual(second["missingSkills"], ["Spark"])
        self.assertGreater(first["score"], second["score"])
        self.assertTrue(first["resumeId"].startswith("r_"))
        self.assertTrue(first["candidateRef"].startswith("CAND-"))

    def test_skill_aliases_match_and_casing_preserved(self):
        res = self.post({"jobTitle": "Data Engineer", "skills": ["pyspark", "SQL"]})
        self.assertEqual(res.data[0]["matchedSkills"], ["SQL", "pyspark"])  # alias of Spark; user's spelling kept

    def test_skills_extracted_from_job_description_when_omitted(self):
        res = self.post({"jobTitle": "Data Engineer", "jobDescription": "We need Python and Spark experience."})
        self.assertEqual(res.data[0]["matchedSkills"], ["Python", "Spark"])

    def test_session_and_results_persisted_for_caller(self):
        self.post({"jobTitle": "Data Engineer", "skills": ["Python"], "jobDescription": "jd"})
        session = SearchSession.objects.get()
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.status, SearchSession.Status.COMPLETED)
        self.assertEqual(session.result_count, 2)
        self.assertEqual(SearchResult.objects.filter(session=session).count(), 2)

    def test_top_n_limits_results(self):
        self.assertEqual(len(self.post({"jobTitle": "x", "skills": ["Python"], "topN": 1}).data), 1)

    def test_validation_rejects_bad_input(self):
        self.assertEqual(self.post({"skills": ["Python"]}).status_code, 400)  # no job title
        self.assertEqual(self.post({"jobTitle": "x"}).status_code, 400)  # no skills or JD
        self.assertEqual(self.post({"jobTitle": "x", "skills": ["a"] * 51}).status_code, 400)
        self.assertEqual(self.post({"jobTitle": "x", "skills": ["a"], "topN": 500}).status_code, 400)

    def test_backend_failure_returns_503_and_marks_session_failed(self):
        with mock.patch("matching.search_service.search_chunks", side_effect=RuntimeError("down")):
            res = self.post({"jobTitle": "x", "skills": ["Python"]})
        self.assertEqual(res.status_code, 503)
        self.assertNotIn("down", str(res.data))  # no internals leaked
        self.assertEqual(SearchSession.objects.get().status, SearchSession.Status.FAILED)
