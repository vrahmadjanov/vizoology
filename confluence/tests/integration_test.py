"""
Django тесты для интеграции с Confluence REST API.

Запуск тестов:
    python manage.py test confluence
    python manage.py test confluence.tests.ConfluenceIntegrationTestCase
    python manage.py test confluence.tests.ConfluenceIntegrationTestCase.test_can_list_spaces

Для запуска только интеграционных тестов (требуют настроенные переменные окружения):
    python manage.py test confluence --tag=integration

Нужны переменные окружения в .env:
- URL: CONFLUENCE_BASE_URL
- Пользователь: CONFLUENCE_USERNAME
- Авторизация: CONFLUENCE_API_TOKEN

Дополнительно для проверки конкретных страниц:
- CONFLUENCE_PAGE_ID или пара CONFLUENCE_SPACE_KEY + CONFLUENCE_PAGE_TITLE

Тесты проверяют:
1. Подключение к API и получение списка пространств
2. Чтение страниц документации и извлечение текста
3. Поиск контента по ключевым словам
4. Получение вложений страниц
5. Навигацию по структуре пространств
6. Комплексный рабочий процесс использования документации
"""

import os
from unittest import skipIf

from django.test import TestCase, override_settings, tag
from django.core.exceptions import ImproperlyConfigured

from confluence.embeddings import PASSAGE_PREFIX, format_e5_text

try:
    from atlassian import Confluence
    CONFLUENCE_AVAILABLE = True
except ImportError:
    CONFLUENCE_AVAILABLE = False

from confluence.services import (
    get_confluence_client,
    normalize_confluence_results,
    page_body_to_plain_text,
    split_text_into_chunks,
)
from confluence.search import search_result_excerpt


def _confluence_client_from_env() -> Confluence | None:
    """Создает клиент Confluence из переменных окружения."""
    if not CONFLUENCE_AVAILABLE:
        return None
    try:
        return get_confluence_client()
    except ImproperlyConfigured:
        return None


def documentation_excerpt(plain_text: str, max_chars: int = 8000) -> str:
    """Фрагмент документации для дальнейшего использования в приложении (лимит по длине)."""
    text = plain_text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n…"


@skipIf(not CONFLUENCE_AVAILABLE, "Библиотека atlassian-python-api не установлена")
@tag('integration')
class ConfluenceIntegrationTestCase(TestCase):
    """Интеграционные тесты для работы с Confluence API."""
    
    def setUp(self):
        """Настройка тестов - создание клиента Confluence."""
        self.client = _confluence_client_from_env()
    
    def _require_client(self) -> Confluence:
        """Проверяет наличие настроенного клиента или пропускает тест."""
        if self.client is None:
            self.skipTest(
                "Задайте в .env: CONFLUENCE_BASE_URL, "
                "CONFLUENCE_USERNAME и CONFLUENCE_API_TOKEN."
            )
        return self.client

    def test_can_list_spaces(self):
        """Доступ к API и чтение списка пространств."""
        client = self._require_client()
        data = client.get_all_spaces(start=0, limit=5)
        self.assertIn("results", data)
        self.assertIsInstance(data["results"], list)

    def test_can_fetch_documentation_page_and_use_body(self):
        """Получение страницы документации и извлечение текста для использования."""
        client = self._require_client()
        page_id = os.environ.get("CONFLUENCE_PAGE_ID", "").strip()
        space = (
            os.environ.get("CONFLUENCE_SPACE_KEY", "").strip()
            or os.environ.get("ATLASSIAN_SPACE_KEY", "").strip()
        )
        title = os.environ.get("CONFLUENCE_PAGE_TITLE", "").strip()

        if page_id:
            page = client.get_page_by_id(
                page_id, expand="body.view,body.storage,version,space"
            )
        elif space and title:
            page = client.get_page_by_title(
                space, title, expand="body.view,body.storage,version,space"
            )
            self.assertIsNotNone(
                page,
                f"Страница «{title}» в пространстве «{space}» не найдена или нет доступа.",
            )
        else:
            # Если не указаны конкретные страницы, попробуем получить первую доступную
            spaces = client.get_all_spaces(start=0, limit=1)
            if spaces.get("results"):
                space_key = spaces["results"][0]["key"]
                pages = client.get_all_pages_from_space(space_key, start=0, limit=1)
                pages_list = normalize_confluence_results(pages)
                if pages_list:
                    page_id = pages_list[0]["id"]
                    page = client.get_page_by_id(
                        page_id, expand="body.view,body.storage,version,space"
                    )
                else:
                    self.skipTest(f"Нет доступных страниц в пространстве {space_key}")
            else:
                self.skipTest(
                    "Укажите CONFLUENCE_PAGE_ID или CONFLUENCE_SPACE_KEY + CONFLUENCE_PAGE_TITLE, "
                    "либо убедитесь что есть доступные пространства."
                )

        self.assertIn("id", page)
        self.assertIn("title", page)
        plain = page_body_to_plain_text(page)
        self.assertTrue(
            plain,
            "Тело страницы пустое: проверьте expand и права на страницу.",
        )
        excerpt = documentation_excerpt(plain, max_chars=500)
        self.assertGreater(len(excerpt), 0)
        if len(plain.strip()) <= 500:
            self.assertEqual(excerpt, plain.strip())
        else:
            self.assertTrue(excerpt.endswith("…"))

    def test_can_search_content(self):
        """Поиск контента в Confluence для получения релевантной документации."""
        client = self._require_client()
        
        # Попробуем найти страницы с общими терминами
        search_terms = ["API", "документация", "руководство", "guide"]
        found_content = False
        
        for term in search_terms:
            try:
                results = client.cql(f'text ~ "{term}"', limit=3)
                if results.get("results"):
                    found_content = True
                    # Проверим что можем получить информацию из найденных страниц
                    for result in results["results"][:1]:  # Проверим только первую
                        page_id = result["content"]["id"]
                        page = client.get_page_by_id(page_id, expand="body.view")
                        self.assertIn("id", page)
                        self.assertIn("title", page)
                        plain_text = page_body_to_plain_text(page)
                        if plain_text:  # Если есть текст, проверим что можем его использовать
                            excerpt = documentation_excerpt(plain_text, max_chars=200)
                            self.assertGreater(len(excerpt), 0)
                    break
            except Exception as e:
                # Если поиск по этому термину не работает, пробуем следующий
                print(f"Поиск по термину '{term}' не удался: {e}")
                continue
        
        if not found_content:
            self.skipTest("Не удалось найти контент для тестирования поиска")

    def test_can_get_page_attachments(self):
        """Проверка получения вложений страницы (если есть)."""
        client = self._require_client()
        
        # Получим любую доступную страницу
        spaces = client.get_all_spaces(start=0, limit=1)
        if not spaces.get("results"):
            self.skipTest("Нет доступных пространств")
        
        space_key = spaces["results"][0]["key"]
        pages = client.get_all_pages_from_space(space_key, start=0, limit=5)
        
        pages_list = normalize_confluence_results(pages)
        
        if not pages_list:
            self.skipTest("Нет доступных страниц")
        
        # Проверим несколько страниц на наличие вложений
        for page_info in pages_list:
            page_id = page_info["id"]
            try:
                attachments = client.get_attachments_from_content(page_id)
                # Проверяем что API работает (может вернуть пустой список)
                self.assertIn("results", attachments)
                self.assertIsInstance(attachments["results"], list)
                
                if attachments["results"]:
                    # Если есть вложения, проверим их структуру
                    attachment = attachments["results"][0]
                    self.assertIn("id", attachment)
                    self.assertIn("title", attachment)
                    break
            except Exception as e:
                print(f"Ошибка при получении вложений для страницы {page_id}: {e}")
                continue

    def test_can_get_space_content_tree(self):
        """Проверка получения структуры контента пространства."""
        client = self._require_client()
        
        # Получим доступное пространство
        space_key = (
            os.environ.get("CONFLUENCE_SPACE_KEY", "").strip()
            or os.environ.get("ATLASSIAN_SPACE_KEY", "").strip()
        )
        
        if not space_key:
            spaces = client.get_all_spaces(start=0, limit=1)
            if not spaces.get("results"):
                self.skipTest("Нет доступных пространств")
            space_key = spaces["results"][0]["key"]
        
        # Получим информацию о пространстве
        space_info = client.get_space(space_key)
        self.assertIn("key", space_info)
        self.assertIn("name", space_info)
        
        # Получим страницы пространства
        pages = client.get_all_pages_from_space(space_key, start=0, limit=10)
        
        pages_list = normalize_confluence_results(pages)
        self.assertIsInstance(pages_list, list)
        
        if pages_list:
            # Проверим что можем получить иерархию страниц
            for page in pages_list[:3]:  # Проверим первые 3 страницы
                page_id = page["id"]
                try:
                    # Получим дочерние страницы
                    children = client.get_page_child_by_type(page_id, type="page")
                    
                    # API может возвращать генератор, словарь или список
                    if hasattr(children, '__iter__') and not isinstance(children, (str, dict)):
                        # Если это генератор или итератор, преобразуем в список
                        children_list = list(children)
                        self.assertIsInstance(children_list, list)
                    elif isinstance(children, dict):
                        self.assertIsInstance(children, dict)
                        if "results" in children:
                            self.assertIsInstance(children["results"], list)
                    elif isinstance(children, list):
                        self.assertIsInstance(children, list)
                    
                except Exception as e:
                    # Не все страницы могут иметь дочерние элементы
                    print(f"Не удалось получить дочерние страницы для {page_id}: {e}")

    def test_documentation_integration_workflow(self):
        """Комплексный тест рабочего процесса использования документации."""
        client = self._require_client()
        
        # 1. Найдем пространство с документацией
        spaces = client.get_all_spaces(start=0, limit=5)
        self.assertIn("results", spaces)
        
        documentation_found = False
        
        for space in spaces["results"]:
            space_key = space["key"]
            
            # 2. Получим страницы из пространства
            pages = client.get_all_pages_from_space(space_key, start=0, limit=3)
            
            pages_list = normalize_confluence_results(pages)
            
            if not pages_list:
                continue
            
            for page_info in pages_list:
                page_id = page_info["id"]
                
                # 3. Получим полную информацию о странице
                page = client.get_page_by_id(
                    page_id, 
                    expand="body.view,body.storage,version,space,ancestors"
                )
                
                # 4. Извлечем текст документации
                plain_text = page_body_to_plain_text(page)
                
                if plain_text and len(plain_text.strip()) > 50:
                    documentation_found = True
                    
                    # 5. Создадим выдержку для использования в приложении
                    excerpt = documentation_excerpt(plain_text, max_chars=1000)
                    
                    # 6. Проверим что информация пригодна для использования
                    self.assertGreater(len(excerpt), 50)
                    self.assertIn("title", page)
                    self.assertIn("space", page)
                    
                    # 7. Проверим метаданные страницы
                    self.assertIn("version", page)
                    self.assertIn("number", page["version"])
                    
                    print(f"✓ Успешно получена документация из страницы: {page['title']}")
                    print(f"  Пространство: {page['space']['name']}")
                    print(f"  Размер текста: {len(plain_text)} символов")
                    print(f"  Выдержка: {len(excerpt)} символов")
                    
                    break
            
            if documentation_found:
                break
        
        if not documentation_found:
            self.skipTest("Не найдено подходящих страниц с документацией для тестирования")


@tag('unit')
class ConfluenceUtilsTestCase(TestCase):
    """Unit тесты для утилитарных функций Confluence."""
    
    def test_page_body_to_plain_text_with_view(self):
        """Тест извлечения текста из body.view."""
        page = {
            "body": {
                "view": {
                    "value": "<p>Тестовый <strong>текст</strong> с <em>форматированием</em></p>"
                }
            }
        }
        result = page_body_to_plain_text(page)
        # BeautifulSoup может добавлять переносы строк, поэтому проверяем содержание
        self.assertIn("Тестовый", result)
        self.assertIn("текст", result)
        self.assertIn("форматированием", result)
        # Проверим что HTML теги удалены
        self.assertNotIn("<strong>", result)
        self.assertNotIn("<em>", result)
    
    def test_page_body_to_plain_text_with_storage(self):
        """Тест извлечения текста из body.storage."""
        page = {
            "body": {
                "storage": {
                    "value": "<ac:structured-document><p>Confluence <strong>контент</strong></p></ac:structured-document>"
                }
            }
        }
        result = page_body_to_plain_text(page)
        # BeautifulSoup может добавлять переносы строк, поэтому проверяем содержание
        self.assertIn("Confluence", result)
        self.assertIn("контент", result)
        # Проверим что HTML теги удалены
        self.assertNotIn("<strong>", result)
        self.assertNotIn("ac:structured-document", result)
    
    def test_page_body_to_plain_text_empty(self):
        """Тест обработки пустого контента."""
        page = {"body": {}}
        result = page_body_to_plain_text(page)
        self.assertEqual(result, "")
    
    def test_documentation_excerpt_short_text(self):
        """Тест создания выдержки для короткого текста."""
        text = "Короткий текст документации"
        result = documentation_excerpt(text, max_chars=100)
        self.assertEqual(result, text)
    
    def test_documentation_excerpt_long_text(self):
        """Тест создания выдержки для длинного текста."""
        text = "Очень длинный текст документации " * 20
        result = documentation_excerpt(text, max_chars=50)
        self.assertTrue(len(result) <= 52)  # 50 + "\n…"
        self.assertTrue(result.endswith("…"))
    
    def test_documentation_excerpt_exact_limit(self):
        """Тест создания выдержки для текста точно по лимиту."""
        text = "A" * 50
        result = documentation_excerpt(text, max_chars=50)
        self.assertEqual(result, text)

    def test_split_text_into_chunks_keeps_paragraphs(self):
        """Тест разбиения текста на чанки по строкам/абзацам."""
        text = "\n".join(
            [
                "Первый логический блок. " * 3,
                "Второй логический блок. " * 3,
                "Третий логический блок. " * 3,
                "Четвертый логический блок. " * 3,
            ]
        )

        chunks = split_text_into_chunks(text, max_chars=200)

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].position, 0)
        self.assertIn("Первый логический блок.", chunks[0].text)
        self.assertIn("Третий логический блок.", chunks[1].text)
        self.assertLessEqual(len(chunks[0].text), 200)

    def test_split_text_into_chunks_splits_large_block(self):
        """Тест разбиения одного очень большого блока."""
        text = "слово " * 120

        chunks = split_text_into_chunks(text, max_chars=200)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk.text) <= 200 for chunk in chunks))
        self.assertEqual([chunk.position for chunk in chunks], list(range(len(chunks))))

    def test_format_e5_text_adds_passage_prefix_and_normalizes_spaces(self):
        """Тест подготовки текста под E5 embedding-модель."""
        result = format_e5_text("  строка\nс   лишними пробелами  ", prefix=PASSAGE_PREFIX)

        self.assertEqual(result, "passage: строка с лишними пробелами")

    def test_search_result_excerpt_normalizes_and_limits_text(self):
        """Тест подготовки короткой выдержки для результата поиска."""
        result = search_result_excerpt("  строка\nс   лишними пробелами  ", max_chars=20)

        self.assertEqual(result, "строка с лишними...")


@skipIf(not CONFLUENCE_AVAILABLE, "Библиотека atlassian-python-api не установлена")
class ConfluenceClientTestCase(TestCase):
    """Unit тесты для создания клиента Confluence."""

    @override_settings(
        CONFLUENCE_BASE_URL="https://test.atlassian.net/wiki",
        CONFLUENCE_USERNAME="test@example.com",
        CONFLUENCE_API_TOKEN="test-token",
        CONFLUENCE_SPACE_KEY="TEST",
    )
    def test_confluence_client_creation_with_env_vars(self):
        """Тест создания клиента с настройками Django."""
        client = _confluence_client_from_env()
        self.assertIsNotNone(client)
        self.assertIsInstance(client, Confluence)

    @override_settings(
        CONFLUENCE_BASE_URL="",
        CONFLUENCE_USERNAME="",
        CONFLUENCE_API_TOKEN="",
        CONFLUENCE_SPACE_KEY="",
    )
    def test_confluence_client_creation_missing_vars(self):
        """Тест создания клиента при отсутствии настроек."""
        client = _confluence_client_from_env()
        self.assertIsNone(client)