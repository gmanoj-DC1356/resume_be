"""Synthetic resume text only."""
from datetime import date

from django.test import SimpleTestCase

from matching.ingestion.resume_parser import parse_resume

SAMPLE = """Candidate A - Senior React Developer
Summary
Frontend engineer with 7 years of experience building single page applications with React and TypeScript.
Focus on performance and testing.
Experience
Senior Frontend Engineer, Example Retail Co, 2021 - Present
Built a component library.
Skills
React, TypeScript, Jest, Cypress, Storybook, Internal Tool X
Education
BSc Example University
"""


class ParserTests(SimpleTestCase):
    def test_fields_extracted(self):
        parsed = parse_resume(SAMPLE, today=date(2026, 1, 1))
        self.assertEqual(parsed.name, "Candidate A")
        self.assertEqual(parsed.role, "Senior React Developer")
        self.assertEqual(parsed.years_experience, 7)
        self.assertTrue(parsed.summary.startswith("Frontend engineer with 7 years"))
        self.assertIn("React", parsed.skills)
        self.assertIn("Internal Tool X", parsed.skills)  # unknown skills from the Skills section are kept

    def test_years_from_overlapping_ranges_when_not_stated(self):
        text = "Candidate B\nExperience\nDev, A, 2018 - 2021\nDev, B, 2020 - 2024\n"
        self.assertEqual(parse_resume(text, today=date(2026, 1, 1)).years_experience, 6)

    def test_role_falls_back_to_first_experience_title(self):
        text = "Candidate C\nExperience\nData Engineer, Example Co, 2022 - Present\n"
        self.assertEqual(parse_resume(text).role, "Data Engineer")
