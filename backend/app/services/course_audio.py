"""Course slide audio synthesis: narration text -> audio assets in the session artifact dir.

This is a workflow-side-effect concern: nodes never write files directly. The graph
side-effect wrapper calls ``synthesize_slide_audio`` after ``slide_deck`` produces
``course_slides``; audio files land under ``artifacts/sessions/{sid}/audio/`` and each
slide's ``narration`` gets ``audio_url`` / ``duration_sec`` backfilled.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from backend.app.core.tts import get_tts_service

_LOGGER = logging.getLogger(__name__)

AUDIO_SUBDIR = "audio"


def _artifacts_root_abs(artifact_root: Path) -> Path:
    return artifact_root if artifact_root.is_absolute() else artifact_root.resolve()


def _course_audio_dir(artifact_root: Path, session_id: str) -> Path:
    from backend.app.runtime_outputs.artifacts import sanitize_session_id

    return _artifacts_root_abs(artifact_root) / "sessions" / sanitize_session_id(session_id) / AUDIO_SUBDIR


def _audio_public_path(session_id: str, storage_key: str) -> str:
    """URL-visible path served by GET /sessions/{id}/artifacts/{path}.

    The artifacts API resolves paths relative to the session artifact directory
    (``artifacts/sessions/{sid}/``), so the public path is just ``audio/<key>``.
    """
    return f"{AUDIO_SUBDIR}/{storage_key}"


def synthesize_slide_audio(
    *,
    artifact_root: Path,
    session_id: str,
    course_slides: dict[str, Any],
) -> dict[str, Any]:
    """Synthesize per-slide narration audio and return a copy of ``course_slides``
    with ``narration.audio_url`` / ``narration.duration_sec`` backfilled.

    Returns the updated slides dict. If TTS fails for a slide, the narration keeps
    its text and audio_url stays None (non-blocking).
    """
    slides = course_slides.get("slides") or []
    if not isinstance(slides, list) or not slides:
        return course_slides

    audio_dir = _course_audio_dir(artifact_root, session_id)
    audio_dir.mkdir(parents=True, exist_ok=True)
    tts = get_tts_service()

    updated_slides: list[dict[str, Any]] = []
    for slide in slides:
        if not isinstance(slide, dict):
            updated_slides.append(slide)
            continue
        narration = slide.get("narration") or {}
        text = narration.get("text") if isinstance(narration, dict) else None
        if not text:
            updated_slides.append(slide)
            continue
        try:
            asset = tts.synthesize(str(text))
        except Exception as exc:  # noqa: BLE001 - TTS failure must not block the course
            _LOGGER.warning("TTS synthesis failed for slide %s: %s", slide.get("id"), exc)
            updated_slides.append(slide)
            continue
        if asset.local_path is not None and asset.local_path.exists():
            target = audio_dir / asset.storage_key
            shutil.move(str(asset.local_path), str(target))
        narration = dict(narration)
        narration["audio_url"] = _audio_public_path(session_id, asset.storage_key)
        narration["duration_sec"] = asset.duration_sec
        updated_slide = dict(slide)
        updated_slide["narration"] = narration
        updated_slides.append(updated_slide)

    # Persist an audio manifest next to the files for auditability.
    manifest_path = audio_dir / "audio_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "session_id": session_id,
                "provider": tts.provider,
                "slides": [
                    {
                        "slide_id": s.get("id"),
                        "audio_url": (s.get("narration") or {}).get("audio_url"),
                        "duration_sec": (s.get("narration") or {}).get("duration_sec"),
                    }
                    for s in updated_slides
                    if isinstance(s, dict)
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = dict(course_slides)
    result["slides"] = updated_slides
    return result
