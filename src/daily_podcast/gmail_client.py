from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Config
from .email_parser import extract_html_from_eml_bytes, extract_ranked_papers_from_html, select_top_ids
from .models import RunManifest

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def fetch_latest_iarxiv_email_raw(cfg: Config) -> tuple[str, bytes]:
    service = _gmail_service(cfg)
    result = (
        service.users()
        .messages()
        .list(userId="me", q=cfg.gmail_query, maxResults=1)
        .execute()
    )
    messages = result.get("messages", [])
    if not messages:
        raise RuntimeError(f"No emails matched query: {cfg.gmail_query!r}")

    message_id = messages[0]["id"]
    payload = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="raw")
        .execute()
    )
    raw_data = payload.get("raw")
    if not raw_data:
        raise RuntimeError(f"Gmail returned no raw payload for message id={message_id}")

    eml_bytes = base64.urlsafe_b64decode(raw_data.encode("utf-8"))
    return message_id, eml_bytes


def build_manifest_from_latest_email(cfg: Config, run_date: str) -> RunManifest:
    message_id, eml_bytes = fetch_latest_iarxiv_email_raw(cfg)
    return build_manifest_from_eml_bytes(
        cfg=cfg,
        run_date=run_date,
        eml_bytes=eml_bytes,
        source_message_id=message_id,
    )


def build_manifest_from_eml_file(cfg: Config, run_date: str, eml_file: Path) -> RunManifest:
    if not eml_file.exists():
        raise FileNotFoundError(f"EML file not found: {eml_file}")
    return build_manifest_from_eml_bytes(
        cfg=cfg,
        run_date=run_date,
        eml_bytes=eml_file.read_bytes(),
        source_message_id=f"local-eml:{eml_file.name}",
    )


def build_manifest_from_eml_bytes(
    cfg: Config,
    run_date: str,
    eml_bytes: bytes,
    source_message_id: str,
) -> RunManifest:
    html = extract_html_from_eml_bytes(eml_bytes)
    papers = extract_ranked_papers_from_html(html)
    selected_ids = select_top_ids(papers, cfg.top_n)

    return RunManifest(
        run_date=run_date,
        source_message_id=source_message_id,
        extracted_at_utc=datetime.now(timezone.utc).isoformat(),
        papers=papers,
        selected_ids=selected_ids,
    )


def _gmail_service(cfg: Config) -> Any:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Missing Gmail dependencies. Install with `pip install -e .` "
            "or `pip install google-api-python-client google-auth-oauthlib google-auth-httplib2`."
        ) from exc

    creds = None
    if cfg.gmail_token_file.exists():
        creds = Credentials.from_authorized_user_file(str(cfg.gmail_token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not cfg.gmail_credentials_file.exists():
                raise FileNotFoundError(
                    f"Gmail credentials file not found: {cfg.gmail_credentials_file}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(cfg.gmail_credentials_file), SCOPES
            )
            creds = flow.run_local_server(port=0)
        cfg.gmail_token_file.parent.mkdir(parents=True, exist_ok=True)
        cfg.gmail_token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)
