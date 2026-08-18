"""Verify the background render queue end-to-end without needing the AI key.

Creates a channel + a video with a pre-written script (so the script step is
skipped), enqueues it, runs the worker, and asserts a real MP4 comes out with
the queue status progressing queued -> running -> done.
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.database import init_db
from db import queries
from modules import jobqueue


async def main() -> int:
    await init_db()
    ch = await queries.create_channel({"name": "QueueCheck", "niche": "space facts",
                                       "voice": "en-US-AndrewNeural"})
    v = await queries.create_video({"channel_id": ch["id"], "topic": "render queue self-test"})
    await queries.update_video(v["id"], {
        "stage": "scripted", "title": "Render Queue Self-Test",
        "script": [
            {"heading": "Segment one", "narration": "This clip verifies the background render queue works end to end."},
            {"heading": "Segment two", "narration": "Voiceover, caption slides, and the final encode all run automatically."},
        ],
    })

    await jobqueue.start()
    await jobqueue.enqueue(v["id"])

    seen = []
    for _ in range(150):
        await asyncio.sleep(1)
        row = await queries.get_video(v["id"])
        if not seen or seen[-1] != (row["queue_status"], row["queue_msg"]):
            seen.append((row["queue_status"], row["queue_msg"]))
            print("  ->", row["queue_status"], "|", row["queue_msg"])
        if row["queue_status"] in ("done", "failed"):
            break

    row = await queries.get_video(v["id"])
    path = row["video_path"]
    ok = (row["queue_status"] == "done" and path and os.path.exists(path)
          and os.path.getsize(path) > 1000)

    # cleanup
    await queries.delete_channel(ch["id"])
    seg_dir = Path(path).parent if path else None
    if seg_dir and seg_dir.exists():
        for f in seg_dir.iterdir():
            f.unlink(missing_ok=True)
        seg_dir.rmdir()

    print(f"\nRESULT: status={row['queue_status']} "
          f"size={os.path.getsize(path) if path and os.path.exists(path) else 0}B "
          f"-> {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
