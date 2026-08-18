"""Assemble a faceless video with ffmpeg (bundled via imageio-ffmpeg — no system
install). For each segment: loop its slide image for the length of its voiceover,
encode a clip, then concat all clips into one mp4.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(args: list[str]) -> None:
    proc = subprocess.run(
        [_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", *args],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr[-500:]}")


def _segment_clip(image: Path, audio: Path, out: Path, size: tuple[int, int]) -> None:
    w, h = size
    _run([
        "-loop", "1", "-i", str(image),
        "-i", str(audio),
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-vf", f"scale={w}:{h}",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(out),
    ])


def render_video(slides: list[Path], audios: list[Path], out_path: Path,
                 size: tuple[int, int]) -> Path:
    if not slides or len(slides) != len(audios):
        raise ValueError("slides and audios must be non-empty and equal length")

    work = out_path.parent
    clips = []
    for i, (img, aud) in enumerate(zip(slides, audios)):
        clip = work / f"clip_{i:02d}.mp4"
        _segment_clip(img, aud, clip, size)
        clips.append(clip)

    # concat via demuxer
    listfile = work / "clips.txt"
    listfile.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
    _run(["-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(out_path)])

    for c in clips:
        c.unlink(missing_ok=True)
    listfile.unlink(missing_ok=True)
    return out_path
