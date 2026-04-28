from django.core.management.base import BaseCommand, CommandError

from confluence.embeddings import LocalEmbeddingService
from confluence.models import ConfluencePageChunk


class Command(BaseCommand):
    help = "Проверяет генерацию embeddings локальной моделью без сохранения в БД."

    def add_arguments(self, parser):
        parser.add_argument(
            "--text",
            default="",
            help="Текст для проверки. Если не указан, берется первый Confluence-чанк.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=1,
            help="Сколько чанков векторизовать для проверки, если --text не указан.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit < 1:
            raise CommandError("--limit должен быть больше 0.")

        if options["text"]:
            texts = [options["text"]]
        else:
            texts = list(
                ConfluencePageChunk.objects.order_by("id").values_list("text", flat=True)[:limit]
            )

        if not texts:
            raise CommandError("Нет текста для проверки. Сначала соберите чанки.")

        service = LocalEmbeddingService()
        self.stdout.write(f"Загружаю локальную модель: {service.model_name}")
        results = service.embed_passages(texts)

        dimensions = results[0].dimensions if results else 0
        self.stdout.write(
            self.style.SUCCESS(
                f"Embeddings сгенерированы. Текстов: {len(results)}, размерность: {dimensions}."
            )
        )
