# Daily arXiv Podcast Pipeline

This project creates a daily paper-to-audio workflow:

1. Fetch latest iArxiv daily email from Gmail.
2. Extract top-N ranked arXiv IDs from visible ranked rows.
3. Download PDFs directly from `https://arxiv.org/pdf/<id>.pdf` (tracking-safe, no iArxiv link usage).
4. Automate NotebookLM to upload an `instructions.txt` source plus papers, then trigger audio overview.
5. Provide cleanup commands for local files and notebook deletion.

## Quick start

1. Create env and install:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -e .[dev]`
   - `playwright install chromium`
2. Copy `.env.example` to `.env` and adjust paths/settings.
3. Place Gmail OAuth client secret file at `GMAIL_CREDENTIALS_FILE`.
4. For NotebookLM login prefill, copy `harvardkey_credentials.example.json` to
   `harvardkey_credentials.json` and set your credentials there (2FA still manual).
5. Run:
   - `daily_podcast run`
   - Test with sample email: `daily_podcast run --eml-file EXAMPLE_IARXIV.eml`

## Commands

- `daily_podcast run [--date YYYY-MM-DD] [--eml-file path/to/file.eml]`
- `daily_podcast fetch-email [--date YYYY-MM-DD] [--eml-file path/to/file.eml]`
- `daily_podcast download-pdfs [--date YYYY-MM-DD | --latest]`
- `daily_podcast create-notebook [--date YYYY-MM-DD | --latest]`
- `daily_podcast cleanup-files [--date YYYY-MM-DD | --latest]`
- `daily_podcast cleanup-notebook [--date YYYY-MM-DD | --latest]`

For local testing without Gmail credentials, use:

- `daily_podcast fetch-email --eml-file EXAMPLE_IARXIV.eml`

## Handoff Guide

- Full setup handoff doc (LLM-friendly): `LLM_SETUP_HANDOFF.md`
