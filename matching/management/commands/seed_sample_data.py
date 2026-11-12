"""Usage: python manage.py seed_sample_data   (idempotent; synthetic data only)"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from matching.models import SearchResult, SearchSession
from matching.sample_data import SAMPLE_CANDIDATES, SAMPLE_JOB_SKILLS, SAMPLE_JOB_TITLE, SEED_USERNAME
from resumes.models import Resume


class Command(BaseCommand):
    help = "Load the synthetic sample candidates and their sample ranking into the database"

    @transaction.atomic
    def handle(self, *args, **options):
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(username=SEED_USERNAME, defaults={"is_active": False})
        if created:
            user.set_unusable_password()  # system owner of the shared sample search; cannot log in
            user.save()

        session, _ = SearchSession.objects.update_or_create(
            user=user,
            job_title=SAMPLE_JOB_TITLE,
            defaults={
                "skills_json": SAMPLE_JOB_SKILLS,
                "jd_text": "Synthetic sample job.",
                "status": SearchSession.Status.COMPLETED,
                "result_count": len(SAMPLE_CANDIDATES),
            },
        )
        session.results.all().delete()
        for rank, item in enumerate(sorted(SAMPLE_CANDIDATES, key=lambda c: -c["score"]), start=1):
            resume, _ = Resume.objects.update_or_create(
                candidate_ref=item["candidate_ref"],
                defaults={
                    "external_id": item["external_id"],
                    "resume_uri": f"sample://{item['candidate_ref']}",
                    "display_name": item["name"],
                    "role": item["role"],
                    "years_experience": item["years"],
                    "skills_json": item["skills"],
                    "summary": item["summary"],
                },
            )
            SearchResult.objects.create(
                session=session, candidate=resume, score=item["score"] / 100, rank_position=rank
            )
        self.stdout.write(f"Seeded {len(SAMPLE_CANDIDATES)} sample candidates and one sample search.")
