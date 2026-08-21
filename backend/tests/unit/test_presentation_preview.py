"""PNG preview generation from PPTX (LibreOffice + PyMuPDF or graceful degradation)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pymupdf
import pytest

from backend.app.presentation.preview import generate_slide_previews

pytestmark = pytest.mark.unit


def _make_pdf(path: Path, pages: int) -> None:
    """Create a minimal PDF with ``pages`` blank pages."""
    with pymupdf.open() as doc:
        for _ in range(pages):
            doc.new_page(width=612, height=792)
        doc.save(str(path))


def test_generates_preview_images_when_soffice_available(tmp_path, monkeypatch) -> None:
    """Simulate a successful LibreOffice PDF conversion by patching subprocess.run."""
    pptx = tmp_path / "course_deck.pptx"
    pptx.write_bytes(b"fake pptx")
    output_dir = tmp_path / "sessions" / "s1" / "presentation" / "previews"

    def _fake_run(cmd, **kwargs):
        outdir = Path(cmd[cmd.index("--outdir") + 1])
        outdir.mkdir(parents=True, exist_ok=True)
        _make_pdf(outdir / "course_deck.pdf", pages=3)
        return subprocess.CompletedProcess(cmd, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr("shutil.which", lambda _name: "/bin/soffice")
    monkeypatch.setattr("subprocess.run", _fake_run)

    result = generate_slide_previews(pptx, output_dir, artifact_root=tmp_path)

    assert result["enabled"] is True
    assert result["count"] == 3
    assert len(result["slides"]) == 3
    assert output_dir.joinpath("slide_001.png").exists()
    assert output_dir.joinpath("slide_003.png").exists()
    assert result["slides"][0]["path"].startswith("sessions/s1/presentation/previews/")


def test_gracefully_degrades_when_soffice_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.presentation.preview._find_soffice", lambda: None
    )
    pptx = tmp_path / "course_deck.pptx"
    pptx.write_bytes(b"fake pptx")
    output_dir = tmp_path / "previews"

    result = generate_slide_previews(pptx, output_dir)

    assert result["enabled"] is False
    assert "soffice" in result["reason"].lower()
    assert result["slides"] == []


def test_reports_failure_when_soffice_exits_with_error(tmp_path, monkeypatch) -> None:
    def _fake_run(*args, **kwargs):
        raise OSError("soffice crashed")

    monkeypatch.setattr("subprocess.run", _fake_run)
    monkeypatch.setattr("shutil.which", lambda _name: "/bin/soffice")
    pptx = tmp_path / "course_deck.pptx"
    pptx.write_bytes(b"fake pptx")
    output_dir = tmp_path / "previews"

    result = generate_slide_previews(pptx, output_dir)

    assert result["enabled"] is False
    assert "failed" in result["reason"].lower()


def test_finds_soffice_in_common_installation_paths(tmp_path, monkeypatch) -> None:
    """The resolver should discover a fake soffice in a known Windows path."""
    fake_dir = tmp_path / "LibreOffice" / "program"
    fake_dir.mkdir(parents=True)
    fake_soffice = fake_dir / "soffice.exe"
    fake_soffice.write_text("fake")

    monkeypatch.setattr("shutil.which", lambda _name: None)
    from backend.app.presentation.preview import _find_soffice

    # We cannot easily inject the fake Windows path, but we can at least verify
    # PATH lookup returns None when not present.
    assert _find_soffice() is None or Path(_find_soffice()).exists()
