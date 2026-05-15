from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from django.conf import settings
from openpyxl import Workbook

from ai.management.commands.ask import (
    _save_history,
    _sources_for_answer,
    _unique_sources,
)
from ai.rag import RAGAnswer, answer_question
from parser.services.parser import (
    iter_nonempty_questions_in_column,
    resolve_first_answer_column_index,
    write_three_column_answer_block,
)


@dataclass(frozen=True)
class AskExcelStats:
    processed: int
    errors: int


def fill_workbook_rag(
    workbook: Workbook,
    *,
    sheet_name: str | None = None,
    questions_col: str | None = None,
    answers_start_col: str | None = None,
    top_k: int = 5,
    min_score: float | None = None,
    save_history: bool = True,
    warn_row: Callable[[str], None] | None = None,
    info_row: Callable[[str], None] | None = None,
) -> AskExcelStats:
    """
    Заполняет три колонки ответа для каждой непустой ячейки вопроса на выбранном листе.
    Книга изменяется на месте.
    """
    min_score = settings.RAG_MIN_SCORE if min_score is None else min_score
    if top_k < 1:
        raise ValueError("top_k должен быть больше 0.")
    if not 0 <= min_score <= 1:
        raise ValueError("min_score должен быть от 0 до 1.")

    if sheet_name:
        if sheet_name not in workbook.sheetnames:
            raise ValueError(
                f"Лист «{sheet_name}» не найден. Доступны: {', '.join(workbook.sheetnames)}"
            )
        ws = workbook[sheet_name]
    else:
        ws = workbook.active
    if ws is None:
        raise ValueError("В книге нет активного листа.")

    first_ans_col = resolve_first_answer_column_index(
        question_column_letter=questions_col,
        answer_block_start_column_letter=answers_start_col,
    )

    processed = 0
    errors = 0
    for row, question in iter_nonempty_questions_in_column(
        ws, questions_col or None
    ):
        try:
            rag_answer = answer_question(
                question, top_k=top_k, min_score=min_score
            )
        except Exception as exc:
            errors += 1
            msg = f"Ошибка RAG: {exc}"
            if warn_row:
                warn_row(f"Строка {row}: {msg}")
            write_three_column_answer_block(
                ws,
                row,
                first_answer_column_index=first_ans_col,
                answer_text=msg,
                sources_text="",
                reasoning_text="",
            )
            continue

        sources_cell = rag_sources_to_cell(rag_answer)
        write_three_column_answer_block(
            ws,
            row,
            first_answer_column_index=first_ans_col,
            answer_text=rag_answer.structured_answer.short_answer,
            sources_text=sources_cell,
            reasoning_text=rag_answer.structured_answer.reasoning_summary,
        )
        processed += 1
        if save_history:
            _save_history(rag_answer, top_k=top_k, min_score=min_score)
        if info_row:
            info_row(f"Строка {row}: готово")

    return AskExcelStats(processed=processed, errors=errors)


def rag_sources_to_cell(rag_answer: RAGAnswer) -> str:
    sources_list = _sources_for_answer(rag_answer)
    if not sources_list and rag_answer.sources:
        sources_list = _unique_sources(rag_answer.sources)
    lines: list[str] = []
    for source in sources_list:
        url = source.url or "без ссылки"
        lines.append(
            f"- {source.title}: {url} (chunk_id={source.chunk_id}, score={source.score:.4f})"
        )
    return "\n".join(lines)
