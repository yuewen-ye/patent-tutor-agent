from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).parents[3]


def test_studio_launchers_disable_hot_reload_to_keep_dev_store_single_writer() -> None:
    shell_script = (REPO_ROOT / "scripts/langgraph-dev.sh").read_text(encoding="utf-8")
    powershell_script = (REPO_ROOT / "scripts/langgraph-dev.ps1").read_text(encoding="utf-8")

    assert "langgraph dev --no-reload" in shell_script
    assert "langgraph dev --no-reload" in powershell_script
