"""Sample mode: the seeded DB rows are returned through the ORM. Synthetic data only."""
import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from matching.models import SearchSession

URL = "/api/v1/screening/search/"

EXPECTED = [
    {"resumeId": "r_104", "candidateRef": "CAND-0104", "name": "Candidate A", "role": "Data Engineer",
     "yearsExperience": 8, "score": 91, "matchedSkills": ["Python", "SQL", "Spark", "Azure"], "missingSkills": [],
     "summary": "Built Spark batch and streaming pipelines on Azure Databricks for commercial analytics."},
    {"resumeId": "r_087", "candidateRef": "CAND-0087", "name": "Candidate B", "role": "Analytics Engineer",
     "yearsExperience": 6, "score": 84, "matchedSkills": ["Python", "Azure", "SQL"], "missingSkills": ["Spark"],
     "summary": "Designed ELT models and orchestration on Azure Data Factory."},
    {"resumeId": "r_142", "candidateRef": "CAND-0142", "name": "Candidate C", "role": "Software Engineer",
     "yearsExperience": 5, "score": 73, "matchedSkills": ["Python", "SQL"], "missingSkills": ["Spark", "Azure"],
     "summary": "Backend services and reporting APIs in Python with SQL warehouses."},
    {"resumeId": "r_019", "candidateRef": "CAND-0019", "name": "Candidate D", "role": "Data Analyst",
     "yearsExperience": 4, "score": 58, "matchedSkills": ["SQL", "Azure"], "missingSkills": ["Python", "Spark"],
     "summary": "Dashboards and ad-hoc analysis; started moving jobs to cloud."},
]
BODY = {"jobTitle": "Data Engineer", "skills": ["Python", "SQL", "Spark", "Azure"], "jobDescription": "x" * 60}


class SampleSearchTests(TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"MATCHING_SEARCH_MODE": "sample"})
        patcher.start()
        self.addCleanup(patcher.stop)
        call_command("seed_sample_data", verbosity=0)
        self.user = get_user_model().objects.create_user("tester", password="x-unused-test-pw-1")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_returns_seeded_sample_exactly(self):
        res = self.client.post(URL, BODY, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, EXPECTED)

    def test_seed_is_idempotent(self):
        call_command("seed_sample_data", verbosity=0)
        self.assertEqual(len(self.client.post(URL, BODY, format="json").data), 4)

    def test_missing_skills_follow_requested_skills(self):
        res = self.client.post(URL, {"jobTitle": "Dev", "skills": ["Spark"]}, format="json")
        self.assertEqual(res.data[0]["matchedSkills"], ["Spark"])
        self.assertEqual(res.data[3]["missingSkills"], ["Spark"])

    def test_top_n_and_caller_history(self):
        res = self.client.post(URL, {**BODY, "topN": 2}, format="json")
        self.assertEqual([c["resumeId"] for c in res.data], ["r_104", "r_087"])
        session = SearchSession.objects.get(user=self.user)
        self.assertEqual(session.result_count, 2)

    def test_empty_when_not_seeded(self):
        from resumes.models import Resume

        SearchSession.objects.all().delete()
        Resume.objects.all().delete()
        self.assertEqual(self.client.post(URL, BODY, format="json").data, [])

    @override_settings(DEBUG=True)
    def test_anonymous_local_search_uses_non_login_dev_user(self):
        response = APIClient().post(URL, BODY, format="json")

        self.assertEqual(response.status_code, 200)
        session = SearchSession.objects.get(user__username="local_dev")
        self.assertEqual(session.user.username, "local_dev")
        self.assertFalse(session.user.is_active)

    def test_seed_user_cannot_log_in(self):
        seed = get_user_model().objects.get(username="sample_seed")
        self.assertFalse(seed.is_active)
        self.assertFalse(seed.has_usable_password())
