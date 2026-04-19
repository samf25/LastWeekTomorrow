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
        "Generate an Audio Overview for {date} focused on: {interests}.\n"
        "Audience: expert HEP/QFT researcher (ATLAS plus muon collider context).\n"
        "Use ALL uploaded papers as source material.\n"
        "There are {paper_count} papers in this run. Cover at least {min_coverage}.\n"
        "Assume fluency with QFT, EFT, collider phenomenology, detector effects, and statistics.\n"
        "Do not provide intro-level explanations.\n"
        "Primary goal: a rapidfire daily digest of granular updates, not a cohesive narrative.\n"
        "Most items are incremental; do not present every paper as a major development.\n"
        "For each covered paper, mention arXiv ID and give: what changed technically, how meaningful it is, and immediate relevance (or irrelevance) to ATLAS/muon-collider work.\n"
        "Only after rapidfire per-paper coverage, provide short cross-paper synthesis.\n"
        "\nPaper checklist for this run:\n{paper_lines}\n"
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
