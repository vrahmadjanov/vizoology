from django.test import SimpleTestCase

from ai.services.history import sources_for_answer, unique_sources
from ai.rag import (
    RAGAnswer,
    SourceSnippet,
    StructuredAnswer,
    build_answer_prompt,
    has_sufficient_relevance,
    parse_structured_answer,
)


class RAGPromptTestCase(SimpleTestCase):
    def test_build_answer_prompt_contains_question_sources_and_rules(self):
        prompt = build_answer_prompt(
            "Как подключить источник данных?",
            [
                SourceSnippet(
                    number=1,
                    title="Подключение источников",
                    url="https://example.test/page",
                    chunk_id=10,
                    chunk_position=2,
                    score=0.91,
                    text="Откройте раздел Источники данных и создайте подключение.",
                )
            ],
        )

        self.assertIn("Как подключить источник данных?", prompt)
        self.assertIn("Источник 1: Подключение источников", prompt)
        self.assertIn("Ссылка: https://example.test/page", prompt)
        self.assertIn("Отвечай только на основании фрагментов", prompt)
        self.assertIn('"short_answer"', prompt)
        self.assertIn('"reasoning_summary"', prompt)
        self.assertIn('"source_numbers"', prompt)

    def test_build_answer_prompt_rejects_empty_question(self):
        with self.assertRaises(ValueError):
            build_answer_prompt(
                "",
                [
                    SourceSnippet(
                        number=1,
                        title="Title",
                        url="",
                        chunk_id=1,
                        chunk_position=0,
                        score=1,
                        text="Text",
                    )
                ],
            )

    def test_unique_sources_keeps_first_source_for_each_url(self):
        sources = [
            SourceSnippet(
                number=1,
                title="Page",
                url="https://example.test/page",
                chunk_id=1,
                chunk_position=0,
                score=0.9,
                text="First",
            ),
            SourceSnippet(
                number=2,
                title="Page",
                url="https://example.test/page",
                chunk_id=2,
                chunk_position=1,
                score=0.8,
                text="Second",
            ),
        ]

        unique = unique_sources(sources)

        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0].chunk_id, 1)

    def test_has_sufficient_relevance_uses_best_score(self):
        sources = [
            SourceSnippet(
                number=1,
                title="Weak",
                url="",
                chunk_id=1,
                chunk_position=0,
                score=0.3,
                text="Weak text",
            ),
            SourceSnippet(
                number=2,
                title="Strong",
                url="",
                chunk_id=2,
                chunk_position=0,
                score=0.7,
                text="Strong text",
            ),
        ]

        self.assertTrue(has_sufficient_relevance(sources, min_score=0.7))
        self.assertFalse(has_sufficient_relevance(sources, min_score=0.71))

    def test_parse_structured_answer_accepts_json_markdown(self):
        answer = parse_structured_answer(
            """```json
            {
              "short_answer": "Ответ по документации.",
              "reasoning_summary": "Это следует из источника.",
              "source_numbers": [1, 2]
            }
            ```"""
        )

        self.assertEqual(answer.short_answer, "Ответ по документации.")
        self.assertEqual(answer.reasoning_summary, "Это следует из источника.")
        self.assertEqual(answer.source_numbers, [1, 2])

    def test_sources_for_answer_uses_structured_source_numbers(self):
        first = SourceSnippet(
            number=1,
            title="First",
            url="https://example.test/first",
            chunk_id=1,
            chunk_position=0,
            score=0.9,
            text="First text",
        )
        second = SourceSnippet(
            number=2,
            title="Second",
            url="https://example.test/second",
            chunk_id=2,
            chunk_position=0,
            score=0.8,
            text="Second text",
        )
        rag_answer = RAGAnswer(
            question="Question",
            structured_answer=StructuredAnswer(
                short_answer="Answer",
                reasoning_summary="Reason",
                source_numbers=[2],
            ),
            sources=[first, second],
            model="test-model",
        )

        sources = sources_for_answer(rag_answer)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].title, "Second")

    def test_sources_for_answer_returns_empty_without_source_numbers(self):
        rag_answer = RAGAnswer(
            question="Question",
            structured_answer=StructuredAnswer(
                short_answer="Не найдено достаточно данных.",
                reasoning_summary="Score ниже порога.",
                source_numbers=[],
            ),
            sources=[
                SourceSnippet(
                    number=1,
                    title="Weak",
                    url="https://example.test/weak",
                    chunk_id=1,
                    chunk_position=0,
                    score=0.1,
                    text="Weak text",
                )
            ],
            model="",
        )

        self.assertEqual(sources_for_answer(rag_answer), [])

    def test_rag_answer_sources_payload_excludes_chunk_text(self):
        rag_answer = RAGAnswer(
            question="Question",
            structured_answer=StructuredAnswer(
                short_answer="Answer",
                reasoning_summary="Reason",
                source_numbers=[1],
            ),
            sources=[
                SourceSnippet(
                    number=1,
                    title="Page",
                    url="https://example.test/page",
                    chunk_id=1,
                    chunk_position=0,
                    score=0.9,
                    text="Full chunk text",
                )
            ],
            model="test-model",
        )

        payload = rag_answer.sources_payload()

        self.assertEqual(payload[0]["url"], "https://example.test/page")
        self.assertNotIn("text", payload[0])
