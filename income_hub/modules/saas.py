"""Micro-SaaS launchpad: generate ideas via Gemini, score them, persist, and
promote a chosen idea into a tracked hub income stream.
"""
from __future__ import annotations

import asyncio

from core import ai, scoring, landing
from db import queries


async def generate_and_store(n: int = 6, focus: str = "") -> list[dict]:
    raw = ai.generate_saas_ideas(n=n, focus=focus)   # sync SDK call
    for idea in raw:
        idea["score"] = scoring.score_idea(idea)
        idea["validation"] = scoring.default_validation()
        idea["status"] = "new"
    raw.sort(key=lambda i: i["score"], reverse=True)
    await queries.insert_ideas(raw)
    return await queries.list_ideas()


async def _idea_or_raise(idea_id: int) -> dict:
    idea = await queries.get_idea(idea_id)
    if not idea:
        raise ValueError("idea not found")
    return idea


async def build_kit(idea_id: int) -> dict:
    idea = await _idea_or_raise(idea_id)
    kit = await asyncio.to_thread(ai.generate_build_kit, idea)
    return await queries.update_idea(idea_id, {"build_kit": kit})


async def research(idea_id: int) -> dict:
    idea = await _idea_or_raise(idea_id)
    data = await asyncio.to_thread(ai.generate_research, idea)
    return await queries.update_idea(idea_id, {"research": data})


async def landing_page(idea_id: int) -> dict:
    idea = await _idea_or_raise(idea_id)
    copy = await asyncio.to_thread(ai.generate_landing_copy, idea)
    html = landing.render_landing(idea, copy, f"/api/saas/ideas/{idea_id}/signup")
    return await queries.update_idea(idea_id, {"landing_html": html})


async def promote_to_stream(idea_id: int) -> dict:
    idea = await queries.get_idea(idea_id)
    if not idea:
        raise ValueError("idea not found")
    await queries.update_idea(idea_id, {"status": "building"})
    return await queries.create_stream({
        "name": idea["name"],
        "kind": "micro_saas",
        "status": "building",
        "notes": f"{idea['problem']}\n\nTarget: {idea['target_user']}\nPricing: {idea['monetization']}",
        "ref_type": "saas_idea",
        "ref_id": idea_id,
    })
