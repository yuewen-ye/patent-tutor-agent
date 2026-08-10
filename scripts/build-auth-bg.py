#!/usr/bin/env python3
"""Build the login-page background video from a sequence of frame images.

Usage:
    python scripts/build-auth-bg.py frames/frame_*.png --output frontend/public/auth-bg.mp4 --fps 12

Requires:
    pip install imageio imageio-ffmpeg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

try:
    import imageio
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "imageio is required. Install it with: pip install imageio imageio-ffmpeg"
    ) from exc


def collect_frames(patterns: Sequence[str]) -> list[Path]:
    frames: set[Path] = set()
    for pattern in patterns:
        matched = sorted(Path(".").glob(pattern))
        if not matched:
            raise SystemExit(f"No files matched pattern: {pattern}")
        frames.update(matched)
    return sorted(frames)


def build_video(frames: Sequence[Path], output: Path, fps: int, quality: int = 8) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(
        str(output),
        fps=fps,
        quality=quality,
        pixelformat="yuv420p",
        codec="libx264",
    )
    for frame in frames:
        image = imageio.imread(str(frame))
        writer.append_data(image)
    writer.close()
    print(f"Wrote {len(frames)} frames to {output} at {fps} fps")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build auth background video from frames")
    parser.add_argument("frames", nargs="+", help="Glob patterns for frame images")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("frontend/public/auth-bg.mp4"),
        help="Output video path (default: frontend/public/auth-bg.mp4)",
    )
    parser.add_argument("--fps", type=int, default=12, help="Frames per second (default: 12)")
    parser.add_argument("--quality", type=int, default=8, help="Video quality 0-10 (default: 8)")
    args = parser.parse_args(argv)

    frames = collect_frames(args.frames)
    build_video(frames, args.output, args.fps, args.quality)
    return 0


if __name__ == "__main__":
    sys.exit(main())
