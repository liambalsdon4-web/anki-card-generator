"""Test the video pipeline WITHOUT Gemini: edge-tts -> Pillow slides -> ffmpeg.
Run: python scripts/check_render.py"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import RENDER_DIR
from core import tts, slides, render


async def main():
    voice = "en-US-AndrewNeural"
    size = (1280, 720)  # smaller = faster test
    segs = [
        {"heading": "Fact One", "narration": "Space is completely silent because there is no air to carry sound."},
        {"heading": "Fact Two", "narration": "A day on Venus is longer than its entire year."},
    ]
    work = RENDER_DIR / "test"
    work.mkdir(parents=True, exist_ok=True)

    print("1) edge-tts voiceover…")
    audios = await tts.synthesize_segments([s["narration"] for s in segs], work, voice)
    for a in audios:
        print(f"   {a.name}: {a.stat().st_size} bytes")

    print("2) Pillow slides…")
    slide_paths = []
    for i, s in enumerate(segs):
        p = work / f"slide_{i:02d}.png"
        slides.make_slide(i, s["heading"], s["narration"], "Test Channel", size, p)
        slide_paths.append(p)
        print(f"   {p.name}: {p.stat().st_size} bytes")

    print("3) ffmpeg render…")
    out = work / "final.mp4"
    render.render_video(slide_paths, audios, out, size)
    ok = out.exists() and out.stat().st_size > 5000
    print(f"   final.mp4: {out.stat().st_size} bytes  ->  {'OK' if ok else 'FAIL'}")
    print(f"\nRendered: {out}")
    sys.exit(0 if ok else 1)


asyncio.run(main())
