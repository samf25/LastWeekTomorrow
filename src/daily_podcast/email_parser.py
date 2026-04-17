from __future__ import annotations

import re
from email import policy
from email.parser import BytesParser

from .models import RankedPaper

ARXIV_ID_PATTERN = r"\d{4}\.\d{4,5}(?:v\d+)?"
RANKED_ROW_PATTERN = re.compile(
    rf"\[(?P<rank>\d+)\]\s*<a[^>]*>\s*(?P<arxiv_id>{ARXIV_ID_PATTERN})\s*</a>\s*"
    r"\((?P<category>[^)]+)\)\s*\[score:\s*(?P<score>[0-9.]+)\]",
    re.IGNORECASE | re.DOTALL,
)


def extract_html_from_eml_bytes(eml_bytes: bytes) -> str:
    msg = BytesParser(policy=policy.default).parsebytes(eml_bytes)
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                content = part.get_content()
                if isinstance(content, str):
                    return content
    if msg.get_content_type() == "text/html":
        content = msg.get_content()
        if isinstance(content, str):
            return content
    raise ValueError("No HTML body found in email payload.")


def extract_ranked_papers_from_html(html: str) -> list[RankedPaper]:
    seen_ids: set[str] = set()
    papers: list[RankedPaper] = []

    for match in RANKED_ROW_PATTERN.finditer(html):
        arxiv_id = match.group("arxiv_id").strip()
        if arxiv_id in seen_ids:
            continue
        seen_ids.add(arxiv_id)
        papers.append(
            RankedPaper(
                rank=int(match.group("rank")),
                arxiv_id=arxiv_id,
                category=match.group("category").strip(),
                score=float(match.group("score")),
            )
        )
    papers.sort(key=lambda p: p.rank)
    return papers


def select_top_ids(papers: list[RankedPaper], top_n: int) -> list[str]:
    if len(papers) < top_n:
        raise ValueError(f"Expected at least {top_n} ranked papers, found {len(papers)}")
    selected = papers[:top_n]
    return [p.arxiv_id for p in selected]
