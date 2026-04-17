from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urlparse

from .config import Config

ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(?:v\d+)?$")


def make_pdf_url(arxiv_id: str, base_url: str) -> str:
    if not ARXIV_ID_RE.match(arxiv_id):
        raise ValueError(f"Invalid arXiv id format: {arxiv_id}")
    return f"{base_url.rstrip('/')}/{arxiv_id}.pdf"


def ensure_allowed_download_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Only https downloads are allowed: {url}")
    if parsed.netloc != "arxiv.org":
        raise ValueError(
            f"Download host must be arxiv.org; refusing non-compliant URL: {url}"
        )


def download_papers(
    arxiv_ids: list[str],
    out_dir: Path,
    cfg: Config,
) -> list[Path]:
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError(
            "requests is required for PDF downloading. Install dependencies with `pip install -e .`."
        ) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    session = requests.Session()
    headers = {"User-Agent": "daily-podcast/0.1.0 (+tracking-safe)"}

    for index, arxiv_id in enumerate(arxiv_ids, start=1):
        url = make_pdf_url(arxiv_id, cfg.arxiv_pdf_base_url)
        ensure_allowed_download_url(url)

        filename = f"{index:02d}_{arxiv_id}.pdf"
        output_path = out_dir / filename
        _download_with_retries(
            session=session,
            url=url,
            output_path=output_path,
            timeout=cfg.download_timeout_seconds,
            retries=cfg.download_retries,
            headers=headers,
        )
        _validate_pdf(output_path, cfg.min_pdf_bytes)
        paths.append(output_path)

    return paths


def _download_with_retries(
    session,
    url: str,
    output_path: Path,
    timeout: int,
    retries: int,
    headers: dict[str, str],
) -> None:
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=timeout, headers=headers, stream=True)
            response.raise_for_status()
            with output_path.open("wb") as fp:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        fp.write(chunk)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(2**attempt)

    raise RuntimeError(f"Failed to download {url} after {retries} attempts: {last_error}")


def _validate_pdf(path: Path, min_pdf_bytes: int) -> None:
    if not path.exists():
        raise RuntimeError(f"Missing downloaded file: {path}")
    size = path.stat().st_size
    if size < min_pdf_bytes:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded file too small ({size} bytes): {path}")
    with path.open("rb") as fp:
        header = fp.read(5)
    if header != b"%PDF-":
        path.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded file is not a valid PDF: {path}")
