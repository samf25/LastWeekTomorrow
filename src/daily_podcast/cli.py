from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from .config import Config, load_config
from .downloader import download_papers
from .gmail_client import build_manifest_from_eml_file, build_manifest_from_latest_email
from .models import RunManifest
from .notebooklm import create_notebook_and_audio_overview, delete_notebook
from .state import (
    default_run_date,
    load_manifest,
    manifest_path,
    resolve_manifest,
    run_directory,
    save_manifest,
    save_note_template_if_missing,
)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    cfg = load_config()
    cfg.ensure_directories()
    save_note_template_if_missing(cfg)

    try:
        return args.func(args, cfg)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="daily_podcast")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_p = subparsers.add_parser("run", help="Run full pipeline for a date.")
    run_p.add_argument("--date", default=default_run_date(), help="Run date YYYY-MM-DD")
    run_p.add_argument(
        "--eml-file",
        help="Optional local .eml file to use instead of Gmail API (useful for testing).",
    )
    run_p.set_defaults(func=cmd_run)

    fetch_p = subparsers.add_parser("fetch-email", help="Fetch latest iArxiv email and create manifest.")
    fetch_p.add_argument("--date", default=default_run_date(), help="Run date YYYY-MM-DD")
    fetch_p.add_argument(
        "--eml-file",
        help="Optional local .eml file to use instead of Gmail API (useful for testing).",
    )
    fetch_p.set_defaults(func=cmd_fetch_email)

    dl_p = subparsers.add_parser("download-pdfs", help="Download arXiv PDFs for selected IDs.")
    _add_date_or_latest(dl_p)
    dl_p.set_defaults(func=cmd_download_pdfs)

    nb_p = subparsers.add_parser(
        "create-notebook", help="Create NotebookLM notebook and trigger audio overview."
    )
    _add_date_or_latest(nb_p)
    nb_p.set_defaults(func=cmd_create_notebook)

    cf_p = subparsers.add_parser("cleanup-files", help="Delete downloaded local files for a run.")
    _add_date_or_latest(cf_p)
    cf_p.set_defaults(func=cmd_cleanup_files)

    cn_p = subparsers.add_parser("cleanup-notebook", help="Delete the NotebookLM notebook for a run.")
    _add_date_or_latest(cn_p)
    cn_p.set_defaults(func=cmd_cleanup_notebook)

    return parser


def _add_date_or_latest(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--date", help="Run date YYYY-MM-DD")
    parser.add_argument("--latest", action="store_true", help="Use latest recorded run.")


def cmd_run(args: argparse.Namespace, cfg: Config) -> int:
    run_date = args.date
    manifest = _fetch_manifest_for_date(cfg, run_date, args.eml_file)
    _download_for_manifest(cfg, manifest)
    _create_notebook_for_manifest(cfg, manifest)
    print(f"Pipeline completed for {run_date}")
    print(f"Manifest: {manifest_path(cfg, run_date)}")
    print(f"Notebook URL: {manifest.notebook_url or 'unknown'}")
    return 0


def cmd_fetch_email(args: argparse.Namespace, cfg: Config) -> int:
    run_date = args.date
    manifest = _fetch_manifest_for_date(cfg, run_date, args.eml_file)
    print(f"Saved manifest: {manifest_path(cfg, run_date)}")
    print(f"Selected top {len(manifest.selected_ids)} arXiv IDs: {', '.join(manifest.selected_ids)}")
    return 0


def cmd_download_pdfs(args: argparse.Namespace, cfg: Config) -> int:
    manifest = resolve_manifest(cfg, args.date, args.latest)
    _download_for_manifest(cfg, manifest)
    print(f"Downloaded {len(manifest.downloaded_files)} PDFs for run {manifest.run_date}")
    return 0


def cmd_create_notebook(args: argparse.Namespace, cfg: Config) -> int:
    manifest = resolve_manifest(cfg, args.date, args.latest)
    _create_notebook_for_manifest(cfg, manifest)
    print(f"Notebook created for run {manifest.run_date}")
    print(f"Notebook URL: {manifest.notebook_url}")
    return 0


def cmd_cleanup_files(args: argparse.Namespace, cfg: Config) -> int:
    manifest = resolve_manifest(cfg, args.date, args.latest)
    papers_dir = run_directory(cfg, manifest.run_date) / "papers"
    if papers_dir.exists():
        _assert_under_runs_dir(cfg, papers_dir)
        shutil.rmtree(papers_dir)
    manifest.downloaded_files = []
    save_manifest(cfg, manifest)
    print(f"Deleted local papers for run {manifest.run_date}")
    return 0


def cmd_cleanup_notebook(args: argparse.Namespace, cfg: Config) -> int:
    manifest = resolve_manifest(cfg, args.date, args.latest)
    if not manifest.notebook_url:
        raise RuntimeError("Manifest has no notebook_url to delete.")
    delete_notebook(cfg, manifest.notebook_url)
    manifest.notebook_status = "deleted"
    save_manifest(cfg, manifest)
    print(f"Deleted NotebookLM notebook for run {manifest.run_date}")
    return 0


def _fetch_manifest_for_date(cfg: Config, run_date: str, eml_file: str | None = None) -> RunManifest:
    if eml_file:
        manifest = build_manifest_from_eml_file(cfg, run_date, Path(eml_file))
    else:
        manifest = build_manifest_from_latest_email(cfg, run_date)
    manifest = _merge_with_existing_manifest(cfg, manifest)
    save_manifest(cfg, manifest)
    return manifest


def _download_for_manifest(cfg: Config, manifest: RunManifest) -> None:
    if len(manifest.selected_ids) < cfg.top_n:
        raise RuntimeError(
            f"Manifest has {len(manifest.selected_ids)} selected IDs; expected at least {cfg.top_n}."
        )
    papers_dir = run_directory(cfg, manifest.run_date) / "papers"
    paths = download_papers(manifest.selected_ids, papers_dir, cfg)
    manifest.downloaded_files = [str(path) for path in paths]
    save_manifest(cfg, manifest)


def _create_notebook_for_manifest(cfg: Config, manifest: RunManifest) -> None:
    resolved_paths, missing = _resolve_manifest_file_paths(cfg, manifest.downloaded_files)
    if not resolved_paths:
        raise RuntimeError(
            "No downloaded files found in manifest. Run `daily_podcast download-pdfs` first."
        )
    if missing:
        raise RuntimeError(f"Missing downloaded files:\n" + "\n".join(missing))
    pdf_paths = resolved_paths
    manifest.downloaded_files = [str(path) for path in pdf_paths]

    note_template = cfg.notebook_note_template_file.read_text(encoding="utf-8")
    note_text = note_template.format(
        interests=cfg.notebooklm_interests,
        date=manifest.run_date,
        arxiv_ids=", ".join(manifest.selected_ids),
    )
    instructions_file = run_directory(cfg, manifest.run_date) / "00_instructions.txt"
    instructions_file.write_text(note_text, encoding="utf-8")

    source_paths = [instructions_file, *pdf_paths]
    notebook_url, notebook_id = create_notebook_and_audio_overview(cfg, source_paths)
    manifest.notebook_url = notebook_url
    manifest.notebook_id = notebook_id
    manifest.notebook_status = "created"
    save_manifest(cfg, manifest)


def _assert_under_runs_dir(cfg: Config, path: Path) -> None:
    runs_root = cfg.runs_dir.resolve()
    target = path.resolve()
    if runs_root == target:
        raise RuntimeError("Refusing to delete entire runs directory.")
    if runs_root not in target.parents:
        raise RuntimeError(f"Refusing to delete path outside runs dir: {path}")


def _merge_with_existing_manifest(cfg: Config, new_manifest: RunManifest) -> RunManifest:
    existing: RunManifest | None = None
    try:
        existing = load_manifest(cfg, new_manifest.run_date)
    except Exception:  # noqa: BLE001
        existing = None

    recovered_files = _discover_downloaded_files(cfg, new_manifest.run_date, new_manifest.selected_ids)

    if not existing:
        new_manifest.downloaded_files = recovered_files
        return new_manifest

    if existing.selected_ids == new_manifest.selected_ids:
        existing_paths, _ = _resolve_manifest_file_paths(cfg, existing.downloaded_files)
        new_manifest.downloaded_files = [str(path) for path in existing_paths] or recovered_files
        new_manifest.notebook_url = existing.notebook_url
        new_manifest.notebook_id = existing.notebook_id
        new_manifest.notebook_status = existing.notebook_status
    else:
        new_manifest.downloaded_files = recovered_files

    return new_manifest


def _discover_downloaded_files(cfg: Config, run_date: str, selected_ids: list[str]) -> list[str]:
    papers_dir = run_directory(cfg, run_date) / "papers"
    discovered: list[str] = []
    if not papers_dir.exists():
        return discovered
    for index, arxiv_id in enumerate(selected_ids, start=1):
        candidate = papers_dir / f"{index:02d}_{arxiv_id}.pdf"
        if candidate.exists():
            discovered.append(str(candidate))
    return discovered


def _resolve_manifest_file_paths(cfg: Config, file_entries: list[str]) -> tuple[list[Path], list[str]]:
    resolved: list[Path] = []
    missing: list[str] = []
    for raw in file_entries:
        path = _resolve_existing_path(cfg, raw)
        if path is None:
            missing.append(raw)
            continue
        resolved.append(path)
    return resolved, missing


def _resolve_existing_path(cfg: Config, raw_path: str) -> Path | None:
    for candidate in _candidate_paths(cfg, raw_path):
        if candidate.exists():
            return candidate
    return None


def _candidate_paths(cfg: Config, raw_path: str) -> list[Path]:
    raw = raw_path.strip()
    candidates: list[Path] = []

    direct = Path(raw)
    candidates.append(direct)
    if not direct.is_absolute():
        candidates.append(cfg.project_root / direct)

    # Handle backslash-prefixed WSL paths that appear in PowerShell, e.g. \mnt\c\...
    slash_norm = raw.replace("\\", "/")
    m_wsl = re.match(r"^/?mnt/([a-zA-Z])/(.+)$", slash_norm)
    if m_wsl:
        drive = m_wsl.group(1).lower()
        rest_posix = m_wsl.group(2)
        candidates.append(Path(f"/mnt/{drive}/{rest_posix}"))
        rest_windows = rest_posix.replace("/", "\\")
        candidates.append(Path(f"{drive.upper()}:\\{rest_windows}"))

    # Handle Windows drive paths, e.g. C:\Users\...
    m_win = re.match(r"^([a-zA-Z]):[\\/](.+)$", raw)
    if m_win:
        drive = m_win.group(1).lower()
        rest = m_win.group(2).replace("\\", "/")
        candidates.append(Path(f"/mnt/{drive}/{rest}"))

    # De-duplicate while preserving order.
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique
