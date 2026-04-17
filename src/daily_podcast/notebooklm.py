from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import Config


@dataclass(slots=True)
class LoginCredentials:
    email: str = ""
    password: str = ""


def create_notebook_and_audio_overview(
    cfg: Config,
    source_paths: list[Path],
) -> tuple[str, str | None]:
    playwright = _import_playwright()
    credentials = _load_login_credentials(cfg)

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg.notebooklm_headless)
        context_kwargs: dict[str, object] = {}
        if cfg.playwright_storage_state.exists():
            context_kwargs["storage_state"] = str(cfg.playwright_storage_state)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        page.goto(cfg.notebooklm_url, wait_until="domcontentloaded")

        page = _wait_for_ready_area(
            page,
            cfg=cfg,
            credentials=credentials,
            ready_selectors=_workspace_ready_selectors(),
        )
        _click_if_present(page, _new_notebook_selectors(), timeout_ms=15_000)
        _upload_files(page, source_paths)
        _trigger_audio_overview(page)

        notebook_url = page.url
        notebook_id = _extract_notebook_id(notebook_url)

        context.storage_state(path=str(cfg.playwright_storage_state))
        context.close()
        browser.close()
        return notebook_url, notebook_id


def delete_notebook(cfg: Config, notebook_url: str) -> None:
    playwright = _import_playwright()
    credentials = _load_login_credentials(cfg)

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg.notebooklm_headless)
        context_kwargs: dict[str, object] = {}
        if cfg.playwright_storage_state.exists():
            context_kwargs["storage_state"] = str(cfg.playwright_storage_state)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        page.goto(notebook_url, wait_until="domcontentloaded")

        page = _wait_for_ready_area(
            page,
            cfg=cfg,
            credentials=credentials,
            ready_selectors=_delete_menu_open_selectors(),
        )
        _click_first(page, _delete_menu_open_selectors())
        _click_first(page, _delete_notebook_selectors())
        _click_first(page, _delete_confirm_selectors())

        context.storage_state(path=str(cfg.playwright_storage_state))
        context.close()
        browser.close()


def _import_playwright():
    try:
        from playwright import sync_api
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is required for NotebookLM automation. Install dependencies and run "
            "`playwright install chromium`."
        ) from exc
    return sync_api


def _load_login_credentials(cfg: Config) -> LoginCredentials:
    email = cfg.notebooklm_login_email.strip()
    password = cfg.notebooklm_login_password

    if cfg.notebooklm_credentials_file.exists():
        try:
            data = json.loads(cfg.notebooklm_credentials_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Could not parse NotebookLM credentials JSON: {cfg.notebooklm_credentials_file}"
            ) from exc
        email = email or str(
            data.get("google_email") or data.get("harvard_email") or data.get("email") or ""
        ).strip()
        password = password or str(
            data.get("harvard_password") or data.get("password") or ""
        )

    return LoginCredentials(email=email, password=password)


def _wait_for_ready_area(page, cfg: Config, credentials: LoginCredentials, ready_selectors: list[str]):
    deadline = time.time() + cfg.notebooklm_login_wait_seconds
    prompted_2fa = False
    printed_cred_hint = False
    okta_push_clicked = False
    in_two_factor_mode = False

    if credentials.email:
        print(f"NotebookLM login email loaded: {credentials.email}")
    else:
        print(
            "NotebookLM login email not configured. Set NOTEBOOKLM_LOGIN_EMAIL "
            "or harvardkey_credentials.json to enable auto-fill."
        )

    while time.time() < deadline:
        pages = _candidate_pages(page)

        for candidate in pages:
            if _has_any(candidate, ready_selectors, timeout_ms=300):
                return candidate

        for candidate in pages:
            _handle_post_auth_prompts(candidate)

        two_factor_page = _find_first_page_with_any(pages, _two_factor_selectors())
        if two_factor_page is not None:
            in_two_factor_mode = True
            if not prompted_2fa:
                print("NotebookLM login awaiting 2FA approval. Complete 2FA and keep this window open.")
                prompted_2fa = True
            if not okta_push_clicked and _click_if_present(
                two_factor_page, _okta_verify_push_selectors(), timeout_ms=600
            ):
                print("Clicked Okta Verify push button.")
                okta_push_clicked = True
            # Important: once 2FA is visible, stop interacting with login fields/buttons.
            page.wait_for_timeout(1_000)
            continue

        if in_two_factor_mode:
            # Sticky 2FA mode: do not restart login while user is approving or waiting for redirect.
            page.wait_for_timeout(1_000)
            continue

        for candidate in pages:
            _attempt_login_step(candidate, credentials)

        if credentials.email and not printed_cred_hint and _has_any(
            page, _google_email_input_selectors(), timeout_ms=300
        ):
            print("Attempting automatic Google email entry.")
            printed_cred_hint = True

        page.wait_for_timeout(500)

    raise RuntimeError(
        "NotebookLM page did not reach a ready state in time. "
        "If login/2FA was pending, complete it and rerun `daily_podcast create-notebook --latest`."
    )


def _attempt_login_step(page, credentials: LoginCredentials) -> None:
    _click_if_present(page, _use_another_account_selectors(), timeout_ms=600)
    _click_if_present(page, _sign_in_selectors(), timeout_ms=600)
    if credentials.email:
        _click_account_for_email_if_present(page, credentials.email, timeout_ms=500)
        if _fill_if_present(page, _google_email_input_selectors(), credentials.email, timeout_ms=800):
            if not _click_if_present(page, _google_next_selectors(), timeout_ms=800):
                _press_enter_on_first(page, _google_email_input_selectors(), timeout_ms=500)
        _fill_if_present(page, _harvard_email_input_selectors(), credentials.email, timeout_ms=800)
    if credentials.password:
        if _fill_if_present(
            page, _harvard_password_input_selectors(), credentials.password, timeout_ms=800
        ):
            _click_if_present(page, _harvard_submit_selectors(), timeout_ms=800)


def _click_first(page, selectors: Iterable[str], timeout_ms: int = 10_000) -> None:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            locator.click()
            return
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError(f"Unable to find any matching selector in {list(selectors)}")


def _click_if_present(page, selectors: Iterable[str], timeout_ms: int = 1_500) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            locator.click()
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _fill_if_present(page, selectors: Iterable[str], text: str, timeout_ms: int = 1_500) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            locator.fill(text)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _press_enter_on_first(page, selectors: Iterable[str], timeout_ms: int = 1_500) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            locator.press("Enter")
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _click_account_for_email_if_present(page, email: str, timeout_ms: int = 1_000) -> bool:
    selectors = [
        f'text="{email}"',
        f'[data-identifier="{email}"]',
        f'li:has-text("{email}")',
        f'div:has-text("{email}")',
    ]
    return _click_if_present(page, selectors, timeout_ms=timeout_ms)


def _candidate_pages(page) -> list:
    pages = [page]
    for candidate in page.context.pages:
        if candidate in pages:
            continue
        pages.append(candidate)
    return [p for p in pages if not p.is_closed()]


def _find_first_page_with_any(pages: list, selectors: Iterable[str]):
    for page in pages:
        if _has_any(page, selectors, timeout_ms=200):
            return page
    return None


def _handle_post_auth_prompts(page) -> None:
    # HarvardKey "Keep me signed in" screen shown after MFA.
    if _click_if_present(page, _device_trust_yes_selectors(), timeout_ms=300):
        print('Handled HarvardKey "Keep me signed in" prompt.')
        return
    _click_if_present(page, _device_trust_no_selectors(), timeout_ms=300)


def _has_any(page, selectors: Iterable[str], timeout_ms: int = 1_000) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _upload_files(page, source_paths: list[Path]) -> None:
    file_paths = [str(path.resolve()) for path in source_paths]
    if not file_paths:
        raise ValueError("No source files provided for upload.")

    _click_if_present(page, _upload_button_selectors(), timeout_ms=20_000)
    if not _set_input_files(page, file_paths):
        _click_if_present(page, _upload_button_selectors(), timeout_ms=8_000)
        if not _set_input_files(page, file_paths):
            raise RuntimeError("Could not find working file upload input in NotebookLM.")
    page.wait_for_timeout(2_500)


def _set_input_files(page, file_paths: list[str]) -> bool:
    try:
        inputs = page.locator('input[type="file"]')
        count = inputs.count()
        for index in range(count - 1, -1, -1):
            try:
                input_node = inputs.nth(index)
                input_node.wait_for(state="attached", timeout=2_000)
                input_node.set_input_files(file_paths)
                return True
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        return False
    return False


def _trigger_audio_overview(page) -> None:
    _click_if_present(page, _studio_tab_selectors(), timeout_ms=8_000)
    _click_first(page, _audio_overview_selectors(), timeout_ms=45_000)
    if not _click_if_present(page, _audio_generate_selectors(), timeout_ms=10_000):
        page.wait_for_timeout(2_000)
        _click_if_present(page, _audio_generate_selectors(), timeout_ms=8_000)


def _extract_notebook_id(url: str) -> str | None:
    match = re.search(r"/notebook/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    return None


def _workspace_ready_selectors() -> list[str]:
    return [
        'button:has-text("Create new")',
        'button:has-text("New notebook")',
        'button:has-text("Upload")',
        'button:has-text("Upload files")',
        '[role="button"]:has-text("Create new")',
        '[role="button"]:has-text("New notebook")',
        '[role="button"]:has-text("Upload files")',
    ]


def _new_notebook_selectors() -> list[str]:
    return [
        'button:has-text("Create new")',
        'button:has-text("New notebook")',
        '[role="button"]:has-text("Create new")',
        '[role="button"]:has-text("New notebook")',
        "text=Create new",
        "text=New notebook",
    ]


def _upload_button_selectors() -> list[str]:
    return [
        'button:has-text("Upload files")',
        '[role="button"]:has-text("Upload files")',
        'button:has-text("Upload")',
        '[role="button"]:has-text("Upload")',
        "text=Upload files",
        "text=Upload",
    ]


def _studio_tab_selectors() -> list[str]:
    return [
        '[role="tab"]:has-text("Studio")',
        'button:has-text("Studio")',
        '[role="button"]:has-text("Studio")',
    ]


def _audio_overview_selectors() -> list[str]:
    return [
        'button:has-text("Audio Overview")',
        '[role="button"]:has-text("Audio Overview")',
        "text=Audio Overview",
    ]


def _audio_generate_selectors() -> list[str]:
    return [
        'button:has-text("Generate")',
        'button:has-text("Create")',
        '[role="button"]:has-text("Generate")',
        '[role="button"]:has-text("Create")',
    ]


def _delete_menu_open_selectors() -> list[str]:
    return [
        '[aria-label*="More"]',
        'button:has-text("More")',
        '[role="button"]:has-text("More")',
    ]


def _delete_notebook_selectors() -> list[str]:
    return [
        'button:has-text("Delete notebook")',
        '[role="menuitem"]:has-text("Delete notebook")',
        "text=Delete notebook",
    ]


def _delete_confirm_selectors() -> list[str]:
    return [
        'button:has-text("Delete")',
        '[role="button"]:has-text("Delete")',
    ]


def _sign_in_selectors() -> list[str]:
    return [
        'button:has-text("Sign in")',
        'a:has-text("Sign in")',
        'button:has-text("Continue with Google")',
        '[role="button"]:has-text("Continue with Google")',
    ]


def _use_another_account_selectors() -> list[str]:
    return [
        "text=Use another account",
        'div:has-text("Use another account")',
        'button:has-text("Use another account")',
        'a:has-text("Use another account")',
    ]


def _google_email_input_selectors() -> list[str]:
    return [
        '#identifierId',
        'input[name="identifier"]',
        'input[autocomplete="username"]',
        'input[aria-label*="Email"]',
        'input[type="email"]',
    ]


def _google_next_selectors() -> list[str]:
    return [
        '#identifierNext button',
        'button:has-text("Next")',
        '[role="button"]:has-text("Next")',
    ]


def _harvard_email_input_selectors() -> list[str]:
    return [
        'input[name="username"]',
        'input[name="email"]',
        'input[type="email"]',
        'input[name="j_username"]',
    ]


def _harvard_password_input_selectors() -> list[str]:
    return [
        'input[type="password"]',
        'input[name="password"]',
        'input[name="j_password"]',
    ]


def _harvard_submit_selectors() -> list[str]:
    return [
        'button[type="submit"]',
        'input[type="submit"]',
        'button:has-text("Sign in")',
        'button:has-text("Log in")',
    ]


def _two_factor_selectors() -> list[str]:
    return [
        "text=2-Step Verification",
        "text=Verify it's you",
        "text=Approve sign in",
        "text=Duo",
        "text=Okta Verify",
        "text=Two-factor",
    ]


def _okta_verify_push_selectors() -> list[str]:
    return [
        'button:has-text("Send Push")',
        '[role="button"]:has-text("Send Push")',
        'button:has-text("Send push")',
        '[role="button"]:has-text("Send push")',
        'button:has-text("Verify with Push")',
        '[role="button"]:has-text("Verify with Push")',
        'button:has-text("Push")',
        '[role="button"]:has-text("Push")',
    ]


def _device_trust_yes_selectors() -> list[str]:
    return [
        'button:has-text("Yes, this is my device")',
        '[role="button"]:has-text("Yes, this is my device")',
        'text=Yes, this is my device',
        'input[type="submit"][value*="Yes"]',
    ]


def _device_trust_no_selectors() -> list[str]:
    return [
        'button:has-text("No, other people may use this device")',
        '[role="button"]:has-text("No, other people may use this device")',
        'text=No, other people may use this device',
        'input[type="submit"][value*="No"]',
    ]
