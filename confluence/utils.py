from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup


def html_to_plain_text(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def page_body_to_plain_text(page: dict[str, Any]) -> str:
    body = page.get("body") or {}
    for key in ("view", "storage"):
        block = body.get(key) or {}
        raw_html = block.get("value")
        if raw_html:
            return html_to_plain_text(raw_html)
    return ""
