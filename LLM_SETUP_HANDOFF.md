# LLM Setup Handoff: Daily arXiv Podcast

Use this document to guide another person through setup end-to-end.

## 1) What This Project Does

- Pulls the latest iArxiv daily email from Gmail.
- Extracts top ranked arXiv IDs from visible email text (no iArxiv tracking links used for downloads).
- Downloads PDFs from `https://arxiv.org/pdf/<id>.pdf`.
- Opens NotebookLM, uploads `00_instructions.txt` + papers, injects a custom Audio Overview prompt in Studio, and starts Audio Overview.

## 2) Prerequisites

- Python 3.10+ with `venv` and `pip`.
- Chromium installable by Playwright.
- A Google account that receives iArxiv emails.
- NotebookLM access in that same browser session.

## 3) Clone + Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
playwright install chromium
```

## 4) Google Cloud + Gmail API Credentials

1. Go to Google Cloud Console and create/select a project.
2. Enable **Gmail API** for the project.
3. Configure OAuth consent in **Google Auth Platform**.
4. Create OAuth Client:
   - App type: **Desktop app**
5. Download OAuth client JSON and save it at repo root as:
   - `credentials.json`

Notes:
- First Gmail API run opens a browser consent flow.
- Token is written to `tokens/token.json` automatically.

## 5) Local Secret Files

Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Create HarvardKey credential file:

```bash
cp harvardkey_credentials.example.json harvardkey_credentials.json
```

Set values in `harvardkey_credentials.json`:
- `google_email`
- `harvard_email`
- `harvard_password`

2FA is still manual by design.

## 6) Run Commands

Full live flow (recommended daily command):

```bash
daily_podcast run
```

Behavior note:
- `daily_podcast run` automatically cleans up local downloaded paper files after notebook creation.
- It does **not** delete the NotebookLM notebook.

Full test flow from sample `.eml`:

```bash
daily_podcast run --eml-file EXAMPLE_IARXIV.eml
```

Step-by-step mode:

```bash
daily_podcast fetch-email
daily_podcast download-pdfs --latest
daily_podcast create-notebook --latest
```

## 7) Expected Login Behavior

- Script autofills Google/Harvard credentials when possible.
- Script clicks Okta Verify push when selector matches.
- Script pauses in 2FA mode and waits for user approval.
- Script handles HarvardKey “Keep me signed in” page automatically.

## 8) Cleanup Commands

```bash
daily_podcast cleanup-files --latest
daily_podcast cleanup-notebook --latest
```

## 9) Secrets Safety (Do Not Commit)

These are ignored by git:
- `.env` and `.env.*`
- `tokens/`
- `playwright-state.json`
- `harvardkey_credentials.json`
- `credentials.json`
- `client_secret*.json`

Before push:

```bash
git status
```

Ensure no secret files are staged.
