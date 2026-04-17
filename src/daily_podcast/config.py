from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - handled at runtime in minimal environments.
    def load_dotenv(*_args, **_kwargs):  # type: ignore[no-redef]
        return False


@dataclass(slots=True)
class Config:
    project_root: Path
    runs_dir: Path
    state_file: Path
    gmail_credentials_file: Path
    gmail_token_file: Path
    gmail_query: str
    top_n: int
    arxiv_pdf_base_url: str
    download_timeout_seconds: int
    download_retries: int
    min_pdf_bytes: int
    notebooklm_url: str
    notebooklm_headless: bool
    notebooklm_login_wait_seconds: int
    notebooklm_credentials_file: Path
    notebooklm_login_email: str
    notebooklm_login_password: str
    notebook_note_template_file: Path
    notebooklm_interests: str
    playwright_storage_state: Path

    def ensure_directories(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.gmail_token_file.parent.mkdir(parents=True, exist_ok=True)


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config(project_root: Path | None = None) -> Config:
    root = project_root or Path.cwd()
    load_dotenv(root / ".env")

    runs_dir = root / os.getenv("RUNS_DIR", "runs")
    state_file = root / os.getenv("STATE_FILE", "state/latest_run.json")
    gmail_credentials_file = root / os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
    gmail_token_file = root / os.getenv("GMAIL_TOKEN_FILE", "tokens/token.json")
    note_template_file = root / os.getenv("NOTEBOOKLM_NOTE_TEMPLATE_FILE", "notebook_note.txt")
    playwright_storage_state = root / os.getenv("PLAYWRIGHT_STORAGE_STATE", "playwright-state.json")
    notebooklm_credentials_file = root / os.getenv(
        "NOTEBOOKLM_CREDENTIALS_FILE",
        "harvardkey_credentials.json",
    )

    return Config(
        project_root=root,
        runs_dir=runs_dir,
        state_file=state_file,
        gmail_credentials_file=gmail_credentials_file,
        gmail_token_file=gmail_token_file,
        gmail_query=os.getenv(
            "GMAIL_QUERY",
            'from:noreply@iarxiv.org subject:"IArxiv.org - Daily papers"',
        ),
        top_n=int(os.getenv("TOP_N", "10")),
        arxiv_pdf_base_url=os.getenv("ARXIV_PDF_BASE_URL", "https://arxiv.org/pdf"),
        download_timeout_seconds=int(os.getenv("DOWNLOAD_TIMEOUT_SECONDS", "60")),
        download_retries=int(os.getenv("DOWNLOAD_RETRIES", "3")),
        min_pdf_bytes=int(os.getenv("MIN_PDF_BYTES", "10000")),
        notebooklm_url=os.getenv("NOTEBOOKLM_URL", "https://notebooklm.google.com/"),
        notebooklm_headless=_to_bool(os.getenv("NOTEBOOKLM_HEADLESS"), default=False),
        notebooklm_login_wait_seconds=int(os.getenv("NOTEBOOKLM_LOGIN_WAIT_SECONDS", "240")),
        notebooklm_credentials_file=notebooklm_credentials_file,
        notebooklm_login_email=os.getenv("NOTEBOOKLM_LOGIN_EMAIL", ""),
        notebooklm_login_password=os.getenv("NOTEBOOKLM_LOGIN_PASSWORD", ""),
        notebook_note_template_file=note_template_file,
        notebooklm_interests=os.getenv("NOTEBOOKLM_INTERESTS", "X, Y, Z"),
        playwright_storage_state=playwright_storage_state,
    )
