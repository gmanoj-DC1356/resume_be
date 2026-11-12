import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import Resume
from .sample_pdf import PDF_MAGIC, build_sample_pdf

NOT_AVAILABLE = "Resume not available."


class ResumesPingTests(TestCase):
    def test_ping_requires_authentication(self):
        res = APIClient().get("/api/v1/resumes/ping/")
        self.assertIn(res.status_code, (401, 403))

    def test_ping_ok_when_authenticated(self):
        user = get_user_model().objects.create_user("tester", password="x-unused-test-pw-1")
        client = APIClient()
        client.force_authenticate(user)
        self.assertEqual(client.get("/api/v1/resumes/ping/").status_code, 200)


class ResumePdfEndpointTests(TestCase):
    """Synthetic PDFs written to throwaway folders; no real resume is ever used."""

    def setUp(self):
        root = tempfile.TemporaryDirectory()
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.addCleanup(outside.cleanup)
        self.root, self.outside = Path(root.name), Path(outside.name)
        override = override_settings(RESUME_FILES_ROOT=self.root)
        override.enable()
        self.addCleanup(override.disable)

        self.client = APIClient()
        self.client.force_authenticate(get_user_model().objects.create_user("recruiter", password="x-unused-test-pw-1"))
        self.pdf = build_sample_pdf(["Synthetic Candidate", "Skills: Python"])
        self.resume = self._resume("abc123", self._write(self.root / "a.pdf", self.pdf))

    @staticmethod
    def _write(path: Path, content: bytes) -> Path:
        path.write_bytes(content)
        return path

    @staticmethod
    def _resume(ref: str, location: Path | str, **extra) -> Resume:
        uri = location.as_uri() if isinstance(location, Path) else location
        return Resume.objects.create(candidate_ref=ref, resume_uri=uri, display_name="Synthetic Person", **extra)

    def _get(self, resume_id: str):
        return self.client.get(f"/api/v1/resumes/{resume_id}/pdf/", HTTP_ACCEPT="application/pdf")

    def _assert_not_available(self, res):
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res["Content-Type"], "application/json")
        self.assertEqual(res.json()["error"]["detail"]["detail"], NOT_AVAILABLE)

    def test_sample_pdf_is_a_pdf(self):
        self.assertTrue(self.pdf.startswith(PDF_MAGIC))

    def test_requires_authentication(self):
        self.assertIn(APIClient().get("/api/v1/resumes/r_abc123/pdf/").status_code, (401, 403))

    def test_serves_pdf_by_derived_id(self):
        res = self._get("r_abc123")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")
        self.assertEqual(b"".join(res.streaming_content), self.pdf)
        self.assertTrue(res["Content-Disposition"].startswith("inline"))
        self.assertEqual(res["Cache-Control"], "private, no-store")
        self.assertEqual(res["X-Content-Type-Options"], "nosniff")

    def test_serves_pdf_by_external_id(self):
        self._resume("ref2", self._write(self.root / "b.pdf", self.pdf), external_id="r_104")
        self.assertEqual(self._get("r_104").status_code, 200)

    def test_derived_id_not_accepted_when_external_id_is_set(self):
        self._resume("ref3", self._write(self.root / "c.pdf", self.pdf), external_id="r_900")
        self._assert_not_available(self._get("r_ref3"))

    def test_filename_uses_public_id_not_candidate_name(self):
        res = self._get("r_abc123")
        self.assertIn("r_abc123.pdf", res["Content-Disposition"])
        self.assertNotIn("Synthetic", res["Content-Disposition"])

    def test_unknown_resume_is_404_json(self):
        self._assert_not_available(self._get("r_nope"))

    def test_malformed_id_is_404(self):
        for bad in ("..%2Fsecret", "a.b", "a%20b"):
            with self.subTest(bad=bad):
                self.assertEqual(self.client.get(f"/api/v1/resumes/{bad}/pdf/").status_code, 404)

    def test_file_outside_resume_folder_is_not_served(self):
        self._resume("out1", self._write(self.outside / "x.pdf", self.pdf))
        self._assert_not_available(self._get("r_out1"))

    def test_symlink_escaping_the_folder_is_not_served(self):
        target = self._write(self.outside / "secret.pdf", self.pdf)
        link = self.root / "link.pdf"
        link.symlink_to(target)
        self._resume("lnk1", link)
        self._assert_not_available(self._get("r_lnk1"))

    def test_non_pdf_content_is_not_served(self):
        self._resume("html1", self._write(self.root / "h.pdf", b"<html><script>alert(1)</script></html>"))
        self._assert_not_available(self._get("r_html1"))

    def test_non_pdf_extension_is_not_served(self):
        self._resume("txt1", self._write(self.root / "t.txt", self.pdf))
        self._assert_not_available(self._get("r_txt1"))

    def test_missing_file_is_not_served(self):
        self._resume("gone1", self.root / "gone.pdf")
        self._assert_not_available(self._get("r_gone1"))

    def test_non_file_location_is_not_served(self):
        self._resume("web1", "http://example.com/resume.pdf")
        self._assert_not_available(self._get("r_web1"))

    def test_sample_candidate_not_served_outside_debug(self):
        self._resume("smp1", "sample://smp1")
        self._assert_not_available(self._get("r_smp1"))

    @override_settings(DEBUG=True)
    def test_sample_candidate_gets_a_synthetic_pdf_in_debug(self):
        self._resume("smp2", "sample://smp2", role="Data Engineer", years_experience=6, skills_json=["Python", "SQL"])
        res = self._get("r_smp2")
        body = b"".join(res.streaming_content)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(body.startswith(PDF_MAGIC))
        self.assertIn(b"synthetic sample", body)

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post("/api/v1/resumes/r_abc123/pdf/").status_code, 405)
