"""Uses synthetic text only; never put real resumes in tests."""
from django.test import SimpleTestCase

from matching.ingestion.chunker import chunk_text, split_sections

SYNTHETIC = """Summary
Backend engineer with a focus on data platforms.
Experience
Built synthetic pipelines at Example Corp.
Skills
Python, SQL, Docker
Education
BSc Example University
"""


class ChunkerTests(SimpleTestCase):
    def test_sections_detected(self):
        names = [name for name, _ in split_sections(SYNTHETIC)]
        self.assertEqual(names, ["summary", "experience", "skills", "education"])

    def test_long_section_splits_with_overlap(self):
        body = "Experience\n" + " ".join(f"w{i}" for i in range(700))
        chunks = chunk_text(body, max_words=300, overlap_words=40)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0].text.split()[-40:], chunks[1].text.split()[:40])
        self.assertEqual([c.chunk_idx for c in chunks], [0, 1, 2])

    def test_bad_overlap_rejected(self):
        with self.assertRaises(ValueError):
            chunk_text("a b c", max_words=10, overlap_words=10)
