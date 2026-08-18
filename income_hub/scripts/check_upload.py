"""Verify the auto-upload plumbing without a real Google account.

- confirms enqueue records the per-video upload flag
- runs the queue on a video that's already 'rendered' (so voice/render are
  skipped) with auto-upload ON, and asserts it fails with the clear
  'not configured' message when no client_secret.json is present.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import youtube_upload
from db.database import init_db
from db import queries
from modules import jobqueue


async def main() -> int:
    await init_db()
    print("youtube_upload.is_configured():", youtube_upload.is_configured())

    ch = await queries.create_channel({"name": "UploadCheck", "niche": "x"})
    v = await queries.create_video({"channel_id": ch["id"], "topic": "upload plumbing test"})
    # Pretend it's already fully rendered so the worker jumps straight to upload.
    await queries.update_video(v["id"], {
        "stage": "rendered", "title": "Upload Test",
        "script": [{"heading": "h", "narration": "n"}],
        "audio_path": "x", "video_path": "x/final.mp4",
    })

    await jobqueue.enqueue(v["id"], do_upload=True)
    row = await queries.get_video(v["id"])
    flag_ok = row["queue_upload"] == 1
    print("queue_upload flag set:", flag_ok)

    await jobqueue.start()
    for _ in range(30):
        await asyncio.sleep(0.5)
        row = await queries.get_video(v["id"])
        if row["queue_status"] in ("done", "failed"):
            break

    row = await queries.get_video(v["id"])
    print("final queue_status:", row["queue_status"], "| msg:", row["queue_msg"])

    if youtube_upload.is_configured():
        expect_ok = row["queue_status"] in ("done", "running")  # would attempt real upload
    else:
        expect_ok = row["queue_status"] == "failed" and "configured" in (row["queue_msg"] or "")

    await queries.delete_channel(ch["id"])
    ok = flag_ok and expect_ok
    print(f"\nRESULT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
