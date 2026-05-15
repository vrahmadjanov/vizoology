from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from django.db import DatabaseError
from openpyxl import load_workbook

from ai.validators import validate_min_score, validate_top_k
from parser.services.excel_batch import AskExcelStats, fill_workbook_rag


def validate_excel_workbook_cli_path(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"Файл не найден: {path}")
    if path.suffix.lower() != ".xlsx":
        raise ValueError("Ожидается файл с расширением .xlsx")


def ask_excel_workbook_inplace(
    path: Path,
    *,
    sheet_name: str | None,
    questions_col: str | None,
    answers_start_col: str | None,
    top_k: int,
    min_score: float,
    save_history: bool,
    warn_row: Callable[[str], None] | None = None,
    info_row: Callable[[str], None] | None = None,
) -> AskExcelStats:
    validate_top_k(top_k)
    validate_min_score(min_score)
    validate_excel_workbook_cli_path(path)

    try:
        wb = load_workbook(path)
    except Exception as exc:
        raise ValueError(f"Не удалось открыть книгу: {exc}") from exc

    stats = fill_workbook_rag(
        wb,
        sheet_name=sheet_name,
        questions_col=questions_col,
        answers_start_col=answers_start_col,
        top_k=top_k,
        min_score=min_score,
        save_history=save_history,
        warn_row=warn_row,
        info_row=info_row,
    )

    try:
        wb.save(path)
    except Exception as exc:
        raise ValueError(f"Не удалось сохранить книгу: {exc}") from exc

    return stats
