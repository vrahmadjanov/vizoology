from django.core.management.base import BaseCommand, CommandError

from ai.validators import validate_top_k
from confluence.utils import search_confluence_chunks, search_result_excerpt


class Command(BaseCommand):
    help = "Ищет релевантные Confluence-чанки по текстовому запросу."

    def add_arguments(self, parser):
        parser.add_argument("query", help="Текст поискового запроса.")
        parser.add_argument(
            "--top-k",
            type=int,
            default=5,
            help="Сколько ближайших чанков вернуть.",
        )

    def handle(self, *args, **options):
        top_k = options["top_k"]
        try:
            validate_top_k(top_k)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        results = search_confluence_chunks(options["query"], top_k=top_k)
        if not results:
            self.stdout.write(self.style.WARNING("Ничего не найдено."))
            return

        for index, result in enumerate(results, start=1):
            chunk = result.chunk
            self.stdout.write(
                self.style.SUCCESS(
                    f"{index}. score={result.score:.4f} distance={result.distance:.4f}"
                )
            )
            self.stdout.write(f"   page: {result.page_title}")
            if result.page_url:
                self.stdout.write(f"   url: {result.page_url}")
            self.stdout.write(f"   chunk: #{chunk.position}, id={chunk.id}")
            self.stdout.write(f"   text: {search_result_excerpt(chunk.text)}")
