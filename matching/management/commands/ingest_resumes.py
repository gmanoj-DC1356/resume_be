"""Usage: python manage.py ingest_resumes --input-dir data/resumes [--reset]"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from matching.conf import get_matching_settings
from matching.ingestion.pipeline import ingest_folder


class Command(BaseCommand):
    help = "Ingest a folder of resume PDFs (chunk, embed, store) into the local Milvus collection"

    def add_arguments(self, parser):
        parser.add_argument("--input-dir", required=True, type=Path)
        parser.add_argument("--reset", action="store_true", help="Drop and rebuild the collection")

    def handle(self, *args, input_dir, reset, **options):
        try:
            report = ingest_folder(input_dir, get_matching_settings(), reset=reset)
        except (NotADirectoryError, RuntimeError) as exc:
            raise CommandError(str(exc))
        self.stdout.write(
            f"Ingested {report.ingested} resumes ({report.chunks} chunks), "
            f"skipped {report.skipped_existing} unchanged, failed {len(report.failed)}"
        )
        for name in report.failed:
            self.stderr.write(f"  FAILED: {name}")
