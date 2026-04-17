from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .config import Config
from .models import RunManifest


def run_directory(cfg: Config, run_date: str) -> Path:
    return cfg.runs_dir / run_date


def manifest_path(cfg: Config, run_date: str) -> Path:
    return run_directory(cfg, run_date) / "manifest.json"


def default_run_date() -> str:
    return date.today().isoformat()


def save_manifest(cfg: Config, manifest: RunManifest) -> Path:
    cfg.ensure_directories()
    path = manifest_path(cfg, manifest.run_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
    _save_latest_state(cfg, manifest)
    return path


def load_manifest(cfg: Config, run_date: str) -> RunManifest:
    path = manifest_path(cfg, run_date)
    if not path.exists():
        raise FileNotFoundError(f"No manifest found for run date {run_date}: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return RunManifest.from_dict(data)


def load_latest_manifest(cfg: Config) -> RunManifest:
    if not cfg.state_file.exists():
        raise FileNotFoundError(
            f"No latest state file found at {cfg.state_file}. Run fetch-email first."
        )
    state = json.loads(cfg.state_file.read_text(encoding="utf-8"))
    run_date = state.get("latest_run_date")
    if not run_date:
        raise ValueError(f"Invalid state file, missing latest_run_date: {cfg.state_file}")
    return load_manifest(cfg, run_date)


def resolve_manifest(cfg: Config, run_date: str | None, latest: bool) -> RunManifest:
    if run_date and latest:
        raise ValueError("Use only one of --date or --latest.")
    if run_date:
        return load_manifest(cfg, run_date)
    if latest:
        return load_latest_manifest(cfg)
    return load_manifest(cfg, default_run_date())


def save_note_template_if_missing(cfg: Config) -> None:
    if cfg.notebook_note_template_file.exists():
        return
    template = (
        "Create a concise daily summary of the last day's developments in my focus areas: "
        "{interests}.\nUse the uploaded papers as the source of truth.\n"
        "Highlight key advances, disagreements, methods, and likely near-term research directions.\n"
        "Mention the most practically relevant insights first.\n"
    )
    cfg.notebook_note_template_file.write_text(template, encoding="utf-8")


def _save_latest_state(cfg: Config, manifest: RunManifest) -> None:
    cfg.state_file.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "latest_run_date": manifest.run_date,
        "manifest_path": str(manifest_path(cfg, manifest.run_date)),
        "notebook_url": manifest.notebook_url,
        "notebook_id": manifest.notebook_id,
    }
    cfg.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
