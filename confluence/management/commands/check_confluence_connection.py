from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from confluence.services import get_confluence_client, get_confluence_settings


class Command(BaseCommand):
    help = "Проверяет подключение к Confluence и доступ к пространству."

    def add_arguments(self, parser):
        parser.add_argument(
            "--space-key",
            default="",
            help="Ключ пространства Confluence. Если не указан, используется CONFLUENCE_SPACE_KEY.",
        )

    def handle(self, *args, **options):
        try:
            connection_settings = get_confluence_settings()
            client = get_confluence_client()
        except ImproperlyConfigured as exc:
            raise CommandError(str(exc)) from exc

        space_key = options["space_key"] or connection_settings.space_key

        try:
            if space_key:
                space = client.get_space(space_key)
                space_name = space.get("name", space_key)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Подключение работает. Доступно пространство {space_key}: {space_name}."
                    )
                )
                return

            spaces = client.get_all_spaces(start=0, limit=5)
            results = spaces.get("results", []) if isinstance(spaces, dict) else spaces
            keys = ", ".join(space.get("key", "?") for space in results)
            suffix = f" Найдены пространства: {keys}." if keys else ""
            self.stdout.write(self.style.SUCCESS(f"Подключение работает.{suffix}"))
        except Exception as exc:
            raise CommandError(f"Не удалось подключиться к Confluence: {exc}") from exc
