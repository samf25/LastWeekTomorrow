from pathlib import Path

import pytest

from daily_podcast.cli import _resolve_existing_path
from daily_podcast.config import load_config


def test_resolves_backslash_wsl_style_paths_when_available() -> None:
    this_file = Path(__file__).resolve()
    this_str = str(this_file)
    if not this_str.startswith("/mnt/"):
        pytest.skip("WSL-style /mnt path not present in this environment.")

    cfg = load_config(project_root=Path(__file__).resolve().parents[1])
    backslash_form = "\\" + this_str.lstrip("/").replace("/", "\\")
    resolved = _resolve_existing_path(cfg, backslash_form)

    assert resolved is not None
    assert resolved.exists()
