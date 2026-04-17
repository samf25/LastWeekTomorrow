from pathlib import Path

from daily_podcast.config import load_config
from daily_podcast.gmail_client import build_manifest_from_eml_file


def test_build_manifest_from_local_eml_file() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cfg = load_config(project_root=repo_root)
    manifest = build_manifest_from_eml_file(
        cfg=cfg,
        run_date="2026-04-17",
        eml_file=repo_root / "EXAMPLE_IARXIV.eml",
    )
    assert manifest.source_message_id == "local-eml:EXAMPLE_IARXIV.eml"
    assert len(manifest.selected_ids) == 10
    assert manifest.selected_ids[0] == "2604.14282"
