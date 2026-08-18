"""In-process background queue that runs the faceless-YouTube pipeline hands-off.

One worker drains an asyncio.Queue and runs each video through the remaining
pipeline steps (script -> voice -> render -> optional upload). Heavy work is
serialised deliberately — ffmpeg/TTS are CPU-bound, so one video at a time keeps
the machine responsive. Steps that are already done are skipped, so a video can
resume from wherever it stopped (and pre-scripted videos don't need the AI key).

Queue state is mirrored onto the video row (queue_status/queue_msg) so it
survives a restart: pending/interrupted videos are re-enqueued on startup.
"""
from __future__ import annotations

import asyncio

from config import settings as cfg
from core import youtube_upload
from db import queries
from modules import youtube as yt

_queue: asyncio.Queue[int] | None = None
_task: asyncio.Task | None = None
_current: int | None = None


def _q() -> asyncio.Queue[int]:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


async def start() -> None:
    """Start the worker and re-enqueue anything left over from a previous run."""
    global _task
    for v in await queries.videos_in_queue():
        await queries.set_queue(v["id"], "queued", "waiting")
        _q().put_nowait(v["id"])
    if _task is None or _task.done():
        _task = asyncio.create_task(_worker())


async def enqueue(video_id: int, do_upload: bool = False) -> None:
    await queries.update_video(video_id, {"queue_upload": 1 if do_upload else 0})
    await queries.set_queue(video_id, "queued", "waiting")
    _q().put_nowait(video_id)


async def enqueue_many(video_ids: list[int], do_upload: bool = False) -> int:
    for vid in video_ids:
        await enqueue(vid, do_upload)
    return len(video_ids)


async def clear_pending() -> int:
    """Drop everything still queued (a running video is left to finish)."""
    q = _q()
    ids: list[int] = []
    while not q.empty():
        try:
            ids.append(q.get_nowait())
            q.task_done()
        except asyncio.QueueEmpty:
            break
    cleared = 0
    for vid in ids:
        v = await queries.get_video(vid)
        if v and v.get("queue_status") == "queued":
            await queries.set_queue(vid, "", "")
            cleared += 1
    return cleared


async def snapshot(channel_id: int | None = None) -> dict:
    return {"running": _current, "items": await queries.queue_items(channel_id)}


async def _worker() -> None:
    global _current
    while True:
        vid = await _q().get()
        try:
            v = await queries.get_video(vid)
            if not v or v.get("queue_status") != "queued":
                continue  # cleared/deleted before we got to it
            _current = vid
            try:
                await _run_one(vid)
                await queries.set_queue(vid, "done", "complete")
            except Exception as e:  # noqa: BLE001 — surface any failure to the UI
                msg = str(e) or e.__class__.__name__
                await queries.set_queue(vid, "failed", msg[:200])
                await queries.update_video(vid, {"error": msg})
            finally:
                _current = None
        finally:
            _q().task_done()


async def _run_one(vid: int) -> None:
    """Run only the steps this video still needs, reporting progress as we go."""
    v = await queries.get_video(vid)
    if not v["script"]:
        await queries.set_queue(vid, "running", "writing script")
        await yt.write_script(vid)

    v = await queries.get_video(vid)
    if not v["audio_path"]:
        await queries.set_queue(vid, "running", "recording voiceover")
        await yt.make_voiceover(vid)

    v = await queries.get_video(vid)
    if not v["video_path"]:
        await queries.set_queue(vid, "running", "rendering video")
        await yt.render_final(vid)

    v = await queries.get_video(vid)
    if v.get("queue_upload") and not v["youtube_id"]:
        if not youtube_upload.is_configured():
            raise RuntimeError("Auto-upload is on but YouTube isn't configured "
                               "(add data/client_secret.json in Settings).")
        await queries.set_queue(vid, "running", "uploading to YouTube")
        await yt.upload(vid, privacy=cfg.get_upload_privacy())
