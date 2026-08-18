"""Faceless YouTube pipeline orchestration.

Stages: idea -> scripted -> voiced -> rendered -> uploaded -> published.
Each step is idempotent-ish and records progress/errors on the video row.
Heavy work (TTS, ffmpeg, upload) runs in worker threads via asyncio.to_thread
where the underlying lib is blocking.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from config.settings import RENDER_DIR, get_resolution, get_voice
from core import ai, tts, slides, render, youtube_upload
from db import queries


async def create_batch(channel_id: int, count: int = 0, topics: list[str] | None = None,
                       focus: str = "") -> list[dict]:
    """Create several video rows at once — from an explicit topic list, or by
    asking the AI for `count` topics for the channel. Returns the created rows.
    """
    channels = {c["id"]: c for c in await queries.list_channels()}
    ch = channels.get(channel_id)
    if not ch:
        raise ValueError("channel not found")

    picked = [t.strip() for t in (topics or []) if t.strip()]
    if not picked and count > 0:
        picked = ai.generate_topics(ch["name"], ch["niche"], ch["style"], n=count)
    if not picked:
        raise ValueError("no topics to create")

    created = []
    for topic in picked[: count or len(picked)]:
        created.append(await queries.create_video({"channel_id": channel_id, "topic": topic}))
    return created


async def write_script(video_id: int) -> dict:
    video = await queries.get_video(video_id)
    if not video:
        raise ValueError("video not found")
    channels = {c["id"]: c for c in await queries.list_channels()}
    ch = channels.get(video["channel_id"], {})

    data = ai.generate_video_script(
        channel=ch.get("name", "Channel"), niche=ch.get("niche", ""),
        style=ch.get("style", "top-10 list"), topic=video["topic"],
        words=ch.get("target_length_words", 220),
    )
    segments = [{"heading": s.get("heading", ""), "narration": s.get("narration", "")}
                for s in data.get("segments", []) if s.get("narration")]
    return await queries.update_video(video_id, {
        "stage": "scripted",
        "title": data.get("title", video["topic"]),
        "description": data.get("description", ""),
        "tags": data.get("tags", ""),
        "thumbnail_prompt": data.get("thumbnail_prompt", ""),
        "script": segments,
        "error": "",
    })


async def make_voiceover(video_id: int) -> dict:
    video = await queries.get_video(video_id)
    if not video or not video["script"]:
        raise ValueError("script required before voiceover")
    channels = {c["id"]: c for c in await queries.list_channels()}
    voice = channels.get(video["channel_id"], {}).get("voice") or get_voice()

    seg_dir = RENDER_DIR / f"video_{video_id}"
    narrations = [s["narration"] for s in video["script"]]
    await tts.synthesize_segments(narrations, seg_dir, voice)
    return await queries.update_video(video_id, {"stage": "voiced", "audio_path": str(seg_dir), "error": ""})


async def render_final(video_id: int) -> dict:
    video = await queries.get_video(video_id)
    if not video or not video["audio_path"]:
        raise ValueError("voiceover required before render")
    channels = {c["id"]: c for c in await queries.list_channels()}
    ch = channels.get(video["channel_id"], {})

    seg_dir = Path(video["audio_path"])
    size = get_resolution()

    def _build() -> str:
        slide_paths, audio_paths = [], []
        for i, seg in enumerate(video["script"]):
            audio = seg_dir / f"seg_{i:02d}.mp3"
            if not audio.exists():
                continue
            slide = seg_dir / f"slide_{i:02d}.png"
            slides.make_slide(i, seg.get("heading", ""), seg.get("narration", ""),
                              ch.get("name", ""), size, slide)
            slide_paths.append(slide)
            audio_paths.append(audio)
        out = seg_dir / "final.mp4"
        render.render_video(slide_paths, audio_paths, out, size)
        return str(out)

    out_path = await asyncio.to_thread(_build)
    return await queries.update_video(video_id, {"stage": "rendered", "video_path": out_path, "error": ""})


async def upload(video_id: int, privacy: str | None = None) -> dict:
    from config.settings import get_upload_privacy
    privacy = privacy or get_upload_privacy()
    video = await queries.get_video(video_id)
    if not video or not video["video_path"]:
        raise ValueError("render required before upload")
    tags = [t.strip() for t in (video["tags"] or "").split(",") if t.strip()]

    def _do():
        return youtube_upload.upload(video["video_path"], video["title"] or video["topic"],
                                     video["description"], tags, privacy)

    yid = await asyncio.to_thread(_do)
    return await queries.update_video(video_id, {
        "stage": "uploaded", "youtube_id": yid, "error": "",
    })


async def run_full_pipeline(video_id: int, do_upload: bool = False) -> dict:
    """script -> voice -> render (-> upload). Records the error and stops on failure."""
    try:
        await write_script(video_id)
        await make_voiceover(video_id)
        result = await render_final(video_id)
        if do_upload and youtube_upload.is_configured():
            result = await upload(video_id)
        return result
    except Exception as e:
        await queries.update_video(video_id, {"error": str(e)})
        raise
