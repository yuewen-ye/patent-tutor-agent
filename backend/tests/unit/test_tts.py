"""TTS scratch location and failure-cleanup behavior."""

from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path

import pytest

from backend.app.core.tts import EdgeTTSService, MockTTSService, _local_audio_path

pytestmark = pytest.mark.unit


def test_scratch_defaults_to_system_temp_not_cwd(monkeypatch) -> None:
    monkeypatch.delenv("TTS_SCRATCH_DIR", raising=False)
    monkeypatch.chdir(tempfile.gettempdir())  # cwd == tempdir would mask a cwd fallback

    path = _local_audio_path("abc123.mp3")

    assert path == Path(tempfile.gettempdir()) / "patent-tutor-tts" / "abc123.mp3"


def test_scratch_honors_env_override(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TTS_SCRATCH_DIR", str(tmp_path / "custom"))

    path = _local_audio_path("abc123.wav")

    assert path == tmp_path / "custom" / "abc123.wav"
    assert path.parent.is_dir()


def test_mock_tts_writes_into_scratch_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TTS_SCRATCH_DIR", str(tmp_path))

    asset = MockTTSService().synthesize("这是一段讲稿")

    assert asset.local_path is not None
    assert asset.local_path.parent == tmp_path
    assert asset.local_path.exists()
    asset.local_path.unlink()


def test_edge_tts_failure_removes_partial_scratch_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TTS_SCRATCH_DIR", str(tmp_path))

    class _FailingCommunicate:
        def __init__(self, text: str, voice: str) -> None:
            pass

        async def save(self, path: str) -> None:
            Path(path).write_bytes(b"")  # partial file, then the network dies
            raise RuntimeError("boom")

    fake_module = types.SimpleNamespace(Communicate=_FailingCommunicate)
    monkeypatch.setitem(sys.modules, "edge_tts", fake_module)

    with pytest.raises(RuntimeError, match="boom"):
        EdgeTTSService().synthesize("这是一段讲稿")

    assert list(tmp_path.iterdir()) == []
