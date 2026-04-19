from pathlib import Path

from daily_podcast.cli import _compose_audio_prompt, _create_notebook_for_manifest
from daily_podcast.config import load_config
from daily_podcast.models import RunManifest


def test_create_notebook_passes_audio_prompt_and_sources(monkeypatch, tmp_path: Path) -> None:
    cfg = load_config(project_root=tmp_path)
    cfg.notebooklm_interests = "hep-ph, detector systematics"
    run_date = "2026-04-18"
    ids = ["2604.14282", "2604.14284"]

    papers_dir = tmp_path / "runs" / run_date / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)

    pdf_paths: list[Path] = []
    for idx, arxiv_id in enumerate(ids, start=1):
        pdf_path = papers_dir / f"{idx:02d}_{arxiv_id}.pdf"
        pdf_path.write_bytes(b"%PDF-test")
        pdf_paths.append(pdf_path)

    cfg.notebook_note_template_file.write_text(
        "Focus on {interests} for {date}. IDs: {arxiv_ids}.",
        encoding="utf-8",
    )

    manifest = RunManifest(
        run_date=run_date,
        selected_ids=ids,
        downloaded_files=[str(path) for path in pdf_paths],
    )

    captured: dict[str, object] = {}

    def fake_create_notebook_and_audio_overview(
        _cfg,
        source_paths: list[Path],
        audio_prompt: str = "",
    ) -> tuple[str, str]:
        captured["cfg"] = _cfg
        captured["source_paths"] = source_paths
        captured["audio_prompt"] = audio_prompt
        return "https://notebooklm.google.com/notebook/abc123", "abc123"

    monkeypatch.setattr(
        "daily_podcast.cli.create_notebook_and_audio_overview",
        fake_create_notebook_and_audio_overview,
    )

    _create_notebook_for_manifest(cfg, manifest)

    assert captured["cfg"] is cfg
    source_paths = captured["source_paths"]
    assert isinstance(source_paths, list)
    assert source_paths[0].name == "00_instructions.txt"
    assert source_paths[1:] == pdf_paths

    audio_prompt = captured["audio_prompt"]
    assert isinstance(audio_prompt, str)
    assert "hep-ph, detector systematics" in audio_prompt
    assert "2604.14282, 2604.14284" in audio_prompt
    assert source_paths[0].read_text(encoding="utf-8") == audio_prompt

    assert manifest.notebook_url == "https://notebooklm.google.com/notebook/abc123"
    assert manifest.notebook_id == "abc123"
    assert manifest.notebook_status == "created"


def test_compose_audio_prompt_enforces_rapidfire_breadth(tmp_path: Path) -> None:
    cfg = load_config(project_root=tmp_path)
    cfg.notebooklm_interests = "hep-ph"
    run_date = "2026-04-18"
    ids = [
        "2604.14282",
        "2604.14284",
        "2604.14290",
        "2604.14301",
        "2604.14308",
        "2604.14311",
        "2604.14320",
        "2604.14324",
        "2604.14339",
        "2604.14351",
    ]
    pdf_paths = [tmp_path / f"{idx:02d}_{arxiv_id}.pdf" for idx, arxiv_id in enumerate(ids, start=1)]

    manifest = RunManifest(run_date=run_date, selected_ids=ids)
    prompt = _compose_audio_prompt(
        cfg,
        manifest,
        pdf_paths,
        note_template=(
            "Date {date}. Interests: {interests}. Total: {paper_count}. "
            "Min coverage: {min_coverage}.\n{paper_lines}\n"
        ),
    )

    assert "Total: 10" in prompt
    assert "Min coverage: 8" in prompt
    assert "Cover at least 8 of the 10 papers" in prompt
    assert "Do not frame everything as a major breakthrough" in prompt
    assert "Paper checklist:" in prompt
    assert "- 1. 2604.14282 (01_2604.14282.pdf)" in prompt
    assert "- 10. 2604.14351 (10_2604.14351.pdf)" in prompt
