"""TTS service: narration text -> audio asset.

Providers are pluggable behind a small Protocol so course generation logic never
depends on a concrete vendor. Default resolution order:

1. ``TTS_PROVIDER`` env var (``edge`` | ``mock``).
2. If unset: use Edge TTS when the ``edge_tts`` package is importable (free,
   no API key), otherwise fall back to the mock provider that writes a real
   silent WAV so the full pipeline stays testable offline.
"""

from __future__ import annotations

import logging
import os
import struct
import uuid
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

_LOGGER = logging.getLogger(__name__)

# 中文讲稿大致语速：每秒约 4 字（留 0.5s 页间静音余量）
_CHARS_PER_SECOND = 4.0
_PAGE_PADDING_SEC = 0.5

TTS_PROVIDER_ENV = "TTS_PROVIDER"
TTS_VOICE_ENV = "TTS_VOICE"
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


@dataclass(frozen=True)
class AudioAsset:
    """Result of one narration synthesis."""

    storage_key: str          # relative path under the course audio dir, e.g. slide_001.wav
    duration_sec: float
    provider: str
    voice: str
    local_path: Path | None = None


@runtime_checkable
class TTSService(Protocol):
    def synthesize(self, text: str, *, voice: str = DEFAULT_VOICE) -> AudioAsset:
        """Synthesize narration text into an audio asset."""
        ...


def _estimated_duration(text: str, chars_per_second: float = _CHARS_PER_SECOND) -> float:
    """Estimate narration duration from Chinese text length."""
    if not text:
        return _PAGE_PADDING_SEC
    return round(len(text) / chars_per_second + _PAGE_PADDING_SEC, 1)


class MockTTSService:
    """Zero-dependency provider: writes a real silent WAV (duration ~ narration length).

    Keeps the full pipeline (slides -> narration -> audio_url) working offline and
    testable; swap in a real provider when a free one is available.
    """

    provider = "mock"

    def __init__(self, voice: str = DEFAULT_VOICE, sample_rate: int = 16000) -> None:
        self.voice = voice
        self.sample_rate = sample_rate

    def synthesize(self, text: str, *, voice: str = DEFAULT_VOICE) -> AudioAsset:
        duration = _estimated_duration(text)
        n_frames = max(1, int(duration * self.sample_rate))
        storage_key = f"{uuid.uuid4().hex[:12]}.wav"
        local_path = _write_silent_wav(storage_key, n_frames, self.sample_rate)
        return AudioAsset(
            storage_key=storage_key,
            duration_sec=duration,
            provider=self.provider,
            voice=voice,
            local_path=local_path,
        )


class EdgeTTSService:
    """Free provider backed by Microsoft Edge TTS (edge-tts package, no API key).

    Requires ``edge-tts`` to be installed; the factory degrades to Mock when the
    import fails (e.g. offline container), so synthesis never blocks the course.
    """

    provider = "edge"

    def __init__(self, voice: str = DEFAULT_VOICE) -> None:
        self.voice = voice

    def synthesize(self, text: str, *, voice: str = DEFAULT_VOICE) -> AudioAsset:
        import edge_tts  # imported lazily; factory checks availability first

        communicate = edge_tts.Communicate(text, voice or self.voice)
        storage_key = f"{uuid.uuid4().hex[:12]}.mp3"
        local_path = _local_audio_path(storage_key)
        _LOGGER.info("edge-tts synthesizing %s (%d chars)", storage_key, len(text))
        import asyncio

        asyncio.run(communicate.save(str(local_path)))
        duration = _estimated_duration(text)
        return AudioAsset(
            storage_key=storage_key,
            duration_sec=duration,
            provider=self.provider,
            voice=voice or self.voice,
            local_path=local_path,
        )


def _local_audio_path(storage_key: str) -> Path:
    # The node stage owns the real course dir; TTS only returns storage_key + local
    # scratch path. The caller moves the file into artifacts and rewrites audio_url.
    scratch = Path(os.environ.get("TTS_SCRATCH_DIR", "")) if os.environ.get("TTS_SCRATCH_DIR") else Path.cwd()
    return scratch / storage_key


def _write_silent_wav(storage_key: str, n_frames: int, sample_rate: int) -> Path:
    """Write a real silent WAV and return its local path."""
    path = _local_audio_path(storage_key)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(struct.pack("<h", 0) * n_frames)
    return path


def _edge_tts_available() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return False


def get_tts_service() -> TTSService:
    """Resolve the TTS provider: env override -> edge (if available) -> mock."""
    provider = os.getenv(TTS_PROVIDER_ENV, "").strip().lower()
    voice = os.getenv(TTS_VOICE_ENV, DEFAULT_VOICE)
    if provider == "edge":
        if not _edge_tts_available():
            _LOGGER.warning("TTS_PROVIDER=edge 但未安装 edge-tts，降级为 mock")
            return MockTTSService(voice=voice)
        return EdgeTTSService(voice=voice)
    if provider == "mock":
        return MockTTSService(voice=voice)
    # auto: free first, fallback mock
    if _edge_tts_available():
        return EdgeTTSService(voice=voice)
    _LOGGER.info("未检测到免费 TTS 库（edge-tts），使用 mock 占位（生成静音音频）")
    return MockTTSService(voice=voice)
