"""Voiceover via edge-tts (free, no API key). Produces one mp3 per segment."""
from __future__ import annotations

from pathlib import Path


async def synthesize(text: str, out_path: Path, voice: str) -> Path:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))
    return out_path


async def synthesize_segments(segments: list[str], out_dir: Path, voice: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, text in enumerate(segments):
        p = out_dir / f"seg_{i:02d}.mp3"
        await synthesize(text, p, voice)
        paths.append(p)
    return paths


async def list_voices(prefix: str = "en-") -> list[dict]:
    import edge_tts

    voices = await edge_tts.list_voices()
    return [
        {"name": v["ShortName"], "gender": v["Gender"], "locale": v["Locale"]}
        for v in voices if v["ShortName"].startswith(prefix)
    ]
