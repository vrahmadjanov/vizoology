from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from django.conf import settings
from django.db import close_old_connections
from openpyxl import Workbook

from ai.rag import RAGAnswer, answer_question
from ai.validators import validate_min_score, validate_top_k
from ai.services.history import (
    save_question_answer_history,
    sources_for_answer,
    unique_sources,
)
from parser.services.parser import (
    apply_answer_block_column_widths,
    ensure_answer_block_headers,
    iter_nonempty_questions_in_column,
    resolve_first_answer_column_index,
    write_three_column_answer_block,
)


@dataclass(frozen=True)
class AskExcelStats:
    processed: int
    errors: int


@dataclass(frozen=True)
class _RowFillResult:
    orig_row: int
    answer_text: str
    reasoning_text: str
    sources: list[tuple[int, str, str | None]]
    rag_answer: RAGAnswer | None = None


def _excel_ask_max_workers(
    question_count: int,
    *,
    max_workers: int | None,
) -> int:
    if question_count <= 1:
        return 1
    configured = (
        settings.EXCEL_ASK_MAX_WORKERS
        if max_workers is None
        else max(1, max_workers)
    )
    return min(configured, question_count)


def _process_question_row(
    row: int,
    question: str,
    *,
    top_k: int,
    min_score: float,
    warn_row: Callable[[str], None] | None,
) -> _RowFillResult:
    close_old_connections()
    try:
        rag_answer = answer_question(
            question, top_k=top_k, min_score=min_score
        )
        return _RowFillResult(
            orig_row=row,
            answer_text=rag_answer.structured_answer.short_answer,
            reasoning_text=rag_answer.structured_answer.reasoning_summary,
            sources=rag_sources_for_column(rag_answer),
            rag_answer=rag_answer,
        )
    except Exception as exc:
        msg = f"Ошибка RAG: {exc}"
        if warn_row:
            warn_row(f"Строка {row}: {msg}")
        return _RowFillResult(
            orig_row=row,
            answer_text=msg,
            reasoning_text="",
            sources=[],
        )
    finally:
        close_old_connections()


def _collect_row_results(
    question_rows: list[tuple[int, str]],
    *,
    top_k: int,
    min_score: float,
    save_history: bool,
    warn_row: Callable[[str], None] | None,
    info_row: Callable[[str], None] | None,
    max_workers: int | None,
) -> tuple[list[_RowFillResult], int, int]:
    workers = _excel_ask_max_workers(
        len(question_rows), max_workers=max_workers
    )

    if workers <= 1:
        row_results = [
            _process_question_row(
                row,
                question,
                top_k=top_k,
                min_score=min_score,
                warn_row=warn_row,
            )
            for row, question in question_rows
        ]
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            row_results = list(
                executor.map(
                    lambda item: _process_question_row(
                        item[0],
                        item[1],
                        top_k=top_k,
                        min_score=min_score,
                        warn_row=warn_row,
                    ),
                    question_rows,
                )
            )

    processed = 0
    errors = 0
    for result in row_results:
        if result.rag_answer is None:
            errors += 1
            continue
        processed += 1
        if save_history:
            save_question_answer_history(
                result.rag_answer, top_k=top_k, min_score=min_score
            )
        if info_row:
            info_row(f"Строка {result.orig_row}: готово")

    return row_results, processed, errors


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
    max_workers: int | None = None,
) -> AskExcelStats:
    """
    Заполняет три колонки ответа для каждой непустой ячейки вопроса на выбранном листе.
    Книга изменяется на месте.
    """
    min_score = settings.RAG_MIN_SCORE if min_score is None else min_score
    validate_top_k(top_k)
    validate_min_score(min_score)

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
    ensure_answer_block_headers(ws, first_ans_col)
    apply_answer_block_column_widths(ws, first_ans_col)

    question_rows = list(
        iter_nonempty_questions_in_column(ws, questions_col or None)
    )
    row_results, processed, errors = _collect_row_results(
        question_rows,
        top_k=top_k,
        min_score=min_score,
        save_history=save_history,
        warn_row=warn_row,
        info_row=info_row,
        max_workers=max_workers,
    )

    for result in row_results:
        write_three_column_answer_block(
            ws,
            result.orig_row,
            first_answer_column_index=first_ans_col,
            answer_text=result.answer_text,
            sources=result.sources,
            reasoning_text=result.reasoning_text,
        )

    return AskExcelStats(processed=processed, errors=errors)


def rag_sources_for_column(
    rag_answer: RAGAnswer,
) -> list[tuple[int, str, str | None]]:
    """(номер, заголовок, url) для колонки источников — по одной Excel-строке на источник."""
    sources_list = sources_for_answer(rag_answer)
    if not sources_list and rag_answer.sources:
        sources_list = unique_sources(rag_answer.sources)
    rows: list[tuple[int, str, str | None]] = []
    for source in sources_list:
        url = (source.url or "").strip() or None
        rows.append((source.number, source.title, url))
    return rows
