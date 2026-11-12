from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from matching.models import SearchResult, SearchSession


class MatchingPingTests(TestCase):
    def test_ping_requires_authentication(self):
        res = APIClient().get("/api/v1/matching/ping/")
        self.assertIn(res.status_code, (401, 403))

    def test_ping_ok_when_authenticated(self):
        user = get_user_model().objects.create_user("tester", password="x-unused-test-pw-1")
        client = APIClient()
        client.force_authenticate(user)
        self.assertEqual(client.get("/api/v1/matching/ping/").status_code, 200)


class SessionHistoryApiTests(TestCase):
    url = "/api/v1/matching/sessions/"

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="tester")
        self.other_user = user_model.objects.create_user(username="other")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.session = SearchSession.objects.create(
            user=self.user,
            job_title="Data Engineer",
            skills_json=["Python", "SQL"],
            result_count=4,
        )
        SearchSession.objects.create(user=self.other_user, job_title="Private search")

    def test_lists_only_caller_searches_in_ui_shape(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            [
                {
                    "id": str(self.session.pk),
                    "title": "Data Engineer",
                    "type": "match",
                    "createdAt": self.session.created_at.isoformat(),
                }
            ],
        )

    def test_supports_unversioned_ui_history_url(self):
        response = self.client.get("/api/sessions")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], str(self.session.pk))

    def test_applies_query_and_type_filters(self):
        self.assertEqual(len(self.client.get(self.url, {"query": "engineer"}).data), 1)
        self.assertEqual(self.client.get(self.url, {"query": "unknown"}).data, [])
        self.assertEqual(self.client.get(self.url, {"type": "questions"}).data, [])

    def test_rejects_invalid_filters(self):
        self.assertEqual(self.client.get(self.url, {"type": "unsupported"}).status_code, 400)
        self.assertEqual(self.client.get(self.url, {"page": 0}).status_code, 400)

    @override_settings(DEBUG=True)
    def test_anonymous_debug_request_lists_local_dev_history(self):
        local_dev = get_user_model().objects.create_user(username="local_dev", is_active=False)
        session = SearchSession.objects.create(user=local_dev, job_title="Local search")

        response = APIClient().get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([entry["id"] for entry in response.data], [str(session.pk)])

    @override_settings(DEBUG=False)
    def test_requires_authentication_outside_debug(self):
        response = APIClient().get(self.url)

        self.assertIn(response.status_code, (401, 403))


class SessionDetailApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="tester")
        self.other_user = user_model.objects.create_user(username="other")
        self.session = SearchSession.objects.create(user=self.user, job_title="Data Engineer")
        self.foreign = SearchSession.objects.create(user=self.other_user, job_title="Private search")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def url(self, session):
        return f"/api/v1/matching/sessions/{session.pk}/"

    def test_rename_own_session(self):
        response = self.client.patch(self.url(self.session), {"title": " Senior Data Engineer "}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Senior Data Engineer")
        self.session.refresh_from_db()
        self.assertEqual(self.session.job_title, "Senior Data Engineer")

    def test_rename_rejects_blank_and_overlong_titles(self):
        for title in ("   ", "x" * 201):
            response = self.client.patch(self.url(self.session), {"title": title}, format="json")
            self.assertEqual(response.status_code, 400)

    def test_delete_own_session(self):
        self.assertEqual(self.client.delete(self.url(self.session)).status_code, 204)
        self.assertFalse(SearchSession.objects.filter(pk=self.session.pk).exists())

    def test_cannot_touch_another_users_session(self):
        self.assertEqual(self.client.patch(self.url(self.foreign), {"title": "x"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(self.url(self.foreign)).status_code, 404)
        self.assertTrue(SearchSession.objects.filter(pk=self.foreign.pk).exists())

    @override_settings(DEBUG=True)
    def test_anonymous_is_denied_even_in_debug(self):
        anonymous = APIClient()
        self.assertIn(anonymous.delete(self.url(self.session)).status_code, (401, 403))
        self.assertTrue(SearchSession.objects.filter(pk=self.session.pk).exists())

    def test_get_returns_saved_results_for_own_session(self):
        from resumes.models import Resume

        resume = Resume.objects.create(
            candidate_ref="d" * 16, resume_uri="file://synthetic/d.pdf", display_name="Candidate D",
            role="Data Engineer", years_experience=5, skills_json=["Python", "SQL"], summary="Synthetic.",
        )
        self.session.skills_json = ["Python", "Spark"]
        self.session.jd_text = "Synthetic description."
        self.session.save()
        SearchResult.objects.create(session=self.session, candidate=resume, score=0.9, rank_position=1)

        body = self.client.get(self.url(self.session)).json()

        self.assertEqual(body["title"], "Data Engineer")
        self.assertEqual(body["skills"], ["Python", "Spark"])
        self.assertEqual(len(body["candidates"]), 1)
        self.assertEqual(body["candidates"][0]["score"], 90)
        self.assertEqual(body["candidates"][0]["matchedSkills"], ["Python"])
        self.assertEqual(body["candidates"][0]["missingSkills"], ["Spark"])

    def test_cannot_read_another_users_results(self):
        self.assertEqual(self.client.get(self.url(self.foreign)).status_code, 404)
