from pathlib import Path

from daily_podcast.cli import _merge_with_existing_manifest
from daily_podcast.config import load_config
from daily_podcast.models import RunManifest
from daily_podcast.state import save_manifest


def test_merge_recovers_downloaded_files_from_papers_dir(tmp_path: Path) -> None:
    cfg = load_config(project_root=tmp_path)
    run_date = "2026-04-17"
    papers_dir = tmp_path / "runs" / run_date / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)

    ids = ["2604.14282", "2604.14284"]
    for idx, arxiv_id in enumerate(ids, start=1):
        (papers_dir / f"{idx:02d}_{arxiv_id}.pdf").write_bytes(b"%PDF-test")

    merged = _merge_with_existing_manifest(
        cfg,
        RunManifest(run_date=run_date, selected_ids=ids),
    )
    assert len(merged.downloaded_files) == 2
    assert merged.downloaded_files[0].endswith("01_2604.14282.pdf")


def test_merge_preserves_existing_downstream_fields_when_ids_match(tmp_path: Path) -> None:
    cfg = load_config(project_root=tmp_path)
    run_date = "2026-04-17"
    ids = ["2604.14282", "2604.14284"]
    existing = RunManifest(
        run_date=run_date,
        selected_ids=ids,
        downloaded_files=[str(tmp_path / "runs" / run_date / "papers" / "01_2604.14282.pdf")],
        notebook_url="https://notebooklm.google.com/notebook/abc123",
        notebook_id="abc123",
        notebook_status="created",
    )
    Path(existing.downloaded_files[0]).parent.mkdir(parents=True, exist_ok=True)
    Path(existing.downloaded_files[0]).write_bytes(b"%PDF-test")
    save_manifest(cfg, existing)

    merged = _merge_with_existing_manifest(
        cfg,
        RunManifest(run_date=run_date, selected_ids=ids),
    )
    assert merged.downloaded_files == existing.downloaded_files
    assert merged.notebook_url == existing.notebook_url
    assert merged.notebook_id == existing.notebook_id
    assert merged.notebook_status == existing.notebook_status
