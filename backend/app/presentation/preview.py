"""Generate per-slide PNG previews from a rendered PPTX package.

LibreOffice is used to convert the PPTX to PDF (the only reliable headless path
for multi-slide PPTX rendering). PyMuPDF then renders each PDF page to PNG.
If LibreOffice is not available on the host, the PPTX is still generated and the
result reports that previews are unavailable.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pymupdf

PREVIEW_DPI = 150


def _find_soffice() -> str | None:
    """Return the path to a usable LibreOffice binary, or None.

    In addition to PATH we check common platform installation directories so
    that Windows hosts work out of the box after a standard LibreOffice install.
    """
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path

    common_paths = [
        # Windows
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
        Path.home()
        / "AppData"
        / "Local"
        / "Programs"
        / "LibreOffice"
        / "program"
        / "soffice.exe",
        # Linux
        Path("/usr/bin/soffice"),
        Path("/usr/lib/libreoffice/program/soffice"),
        Path("/opt/libreoffice/program/soffice"),
        # macOS
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
    ]
    for candidate in common_paths:
        if candidate.exists():
            return str(candidate)
    return None


def _render_pdf_pages_to_png(
    pdf_path: Path, output_dir: Path, *, dpi: int = PREVIEW_DPI
) -> list[Path]:
    """Render every page of ``pdf_path`` to a PNG file in ``output_dir``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    zoom = dpi / 72.0
    matrix = pymupdf.Matrix(zoom, zoom)
    with pymupdf.open(str(pdf_path)) as doc:
        for page_number in range(len(doc)):
            page = doc.load_page(page_number)
            pix = page.get_pixmap(matrix=matrix)
            dest = output_dir / f"slide_{page_number + 1:03d}.png"
            pix.save(str(dest))
            rendered.append(dest)
    return rendered


def generate_slide_previews(
    pptx_path: Path,
    output_dir: Path,
    *,
    artifact_root: Path | None = None,
    dpi: int = PREVIEW_DPI,
) -> dict[str, Any]:
    """Convert ``pptx_path`` to per-slide PNGs inside ``output_dir``.

    Returns a result dict describing the generated previews. The dict has the
    same fields as ``PresentationResult.preview_images`` so callers can embed
    it directly in the service result.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    soffice = _find_soffice()
    if soffice is None:
        return {
            "enabled": False,
            "reason": "LibreOffice (soffice) not available on host",
            "count": 0,
            "slides": [],
        }

    with tempfile.TemporaryDirectory(prefix="pptx-preview-") as tmpdir:
        tmp_path = Path(tmpdir)
        # Step 1: PPTX -> PDF. LibreOffice headless PNG export only emits a
        # single image; PDF is the reliable multi-slide intermediate format.
        cmd = [
            soffice,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(tmp_path),
            str(pptx_path),
        ]
        env = os.environ.copy()
        env["HOME"] = str(tmp_path)
        try:
            subprocess.run(
                cmd,
                env=env,
                check=True,
                capture_output=True,
                timeout=120,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            return {
                "enabled": False,
                "reason": f"LibreOffice PDF conversion failed: {exc}",
                "count": 0,
                "slides": [],
            }

        pdf_files = list(tmp_path.glob("*.pdf"))
        if not pdf_files:
            return {
                "enabled": False,
                "reason": "LibreOffice produced no PDF file",
                "count": 0,
                "slides": [],
            }
        pdf_path = pdf_files[0]

        # Step 2: PDF -> per-page PNGs.
        try:
            generated = _render_pdf_pages_to_png(pdf_path, output_dir, dpi=dpi)
        except Exception as exc:  # noqa: BLE001 - preview must not fail PPTX
            return {
                "enabled": False,
                "reason": f"PDF to PNG rendering failed: {exc}",
                "count": 0,
                "slides": [],
            }

        slides: list[dict[str, Any]] = []
        for index, dest in enumerate(generated, start=1):
            artifact_path = str(dest)
            if artifact_root is not None:
                try:
                    artifact_path = dest.relative_to(artifact_root).as_posix()
                except ValueError:
                    artifact_path = str(dest)
            slides.append(
                {
                    "page": index,
                    "filename": dest.name,
                    "path": artifact_path,
                    "size_bytes": dest.stat().st_size,
                }
            )

    return {
        "enabled": True,
        "dpi": dpi,
        "count": len(slides),
        "slides": slides,
    }
