from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from confluence.client import ConfluenceClient
from confluence.embeddings import LocalEmbeddingService
from confluence.models import Chunk


class Command(BaseCommand):
    help = (
        "Проверка здоровья интеграции: подключение к Confluence; "
        "опционально — локальная генерация embeddings."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--space-key",
            default="",
            help="Ключ пространства Confluence. Если не указан, используется CONFLUENCE_SPACE_KEY.",
        )
        parser.add_argument(
            "--embeddings",
            action="store_true",
            help="Дополнительно проверить локальную модель embeddings (без записи в БД).",
        )
        parser.add_argument(
            "--text",
            default="",
            help="С --embeddings: текст для проверки. Иначе берутся чанки из БД.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=1,
            help="С --embeddings и без --text: сколько чанков векторизовать.",
        )

    def handle(self, *args, **options):
        try:
            cf = ConfluenceClient()
        except ImproperlyConfigured as exc:
            raise CommandError(str(exc)) from exc

        client = cf.api
        space_key = options["space_key"] or settings.CONFLUENCE_SPACE_KEY

        try:
            if space_key:
                space = client.get_space(space_key)
                space_name = space.get("name", space_key)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Подключение работает. Доступно пространство {space_key}: {space_name}."
                    )
                )
            else:
                spaces = client.get_all_spaces(start=0, limit=5)
                results = spaces.get("results", []) if isinstance(spaces, dict) else spaces
                keys = ", ".join(space.get("key", "?") for space in results)
                suffix = f" Найдены пространства: {keys}." if keys else ""
                self.stdout.write(self.style.SUCCESS(f"Подключение работает.{suffix}"))
        except Exception as exc:
            raise CommandError(f"Не удалось подключиться к Confluence: {exc}") from exc

        if options["embeddings"]:
            self._check_local_embeddings(
                text=options["text"],
                limit=options["limit"],
            )

    def _check_local_embeddings(self, *, text: str, limit: int) -> None:
        if limit < 1:
            raise CommandError("--limit должен быть больше 0.")

        if text:
            texts = [text]
        else:
            texts = list(
                Chunk.objects.order_by("id").values_list("text", flat=True)[:limit]
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
