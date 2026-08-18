import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import settings as cfg
from db.database import init_db
from db import queries
from modules import saas, youtube as yt, jobqueue
from core import ai, youtube_upload, odds
import csv
import io

from api.models import (
    StreamIn, StreamPatch, GenerateIdeasIn, IdeaPatch, ChannelIn, VideoIn, SettingsPatch,
    BatchIn, EnqueueIn, BookmakerIn, BookmakerPatch, ArbIn, BetIn, BetPatch, ScanIn, SignupIn,
    ClientIn, ClientPatch, ProjectIn, ProjectPatch, InvoiceIn, InvoicePatch,
    GoalIn, SharedCostIn, SharedCostPatch,
)
from fastapi.responses import HTMLResponse, StreamingResponse
from datetime import datetime, timezone

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await jobqueue.start()
    yield


app = FastAPI(lifespan=lifespan, title=cfg.APP_NAME)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
async def dashboard():
    streams = await queries.list_streams()
    mrr = sum(s["monthly_revenue"] or 0 for s in streams)
    cost = sum(s["monthly_cost"] or 0 for s in streams)
    by_kind: dict[str, float] = {}
    for s in streams:
        by_kind[s["kind"]] = by_kind.get(s["kind"], 0) + (s["monthly_revenue"] or 0)
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    shared_costs = await queries.list_shared_costs()
    shared_total = sum(c["amount"] for c in shared_costs if c["active"])
    goal = await queries.get_goal(period)
    return {
        "streams": streams,
        "totals": {"mrr": round(mrr, 2), "cost": round(cost, 2), "net": round(mrr - cost, 2),
                   "count": len(streams), "by_kind": by_kind},
        "trend": await queries.revenue_trend(6),
        "settings": cfg.get_settings(),
        "youtube_upload_ready": youtube_upload.is_configured(),
        "goal": goal,
        "shared_costs_total": round(shared_total, 2),
    }


# ── Income streams ────────────────────────────────────────────────────────────

@app.get("/api/streams")
async def list_streams():
    return await queries.list_streams()


@app.post("/api/streams", status_code=201)
async def create_stream(body: StreamIn):
    return await queries.create_stream(body.model_dump())


@app.put("/api/streams/{sid}")
async def update_stream(sid: int, body: StreamPatch):
    out = await queries.update_stream(sid, body.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(404)
    return out


@app.delete("/api/streams/{sid}", status_code=204)
async def delete_stream(sid: int):
    await queries.delete_stream(sid)


# ── Micro-SaaS launchpad ──────────────────────────────────────────────────────

@app.get("/api/saas/ideas")
async def list_ideas():
    return await queries.list_ideas()


@app.post("/api/saas/generate")
async def generate_ideas(body: GenerateIdeasIn):
    try:
        return await saas.generate_and_store(n=body.n, focus=body.focus)
    except ai.AIError as e:
        raise HTTPException(400, str(e))


@app.put("/api/saas/ideas/{iid}")
async def patch_idea(iid: int, body: IdeaPatch):
    out = await queries.update_idea(iid, body.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(404)
    return out


@app.delete("/api/saas/ideas/{iid}", status_code=204)
async def delete_idea(iid: int):
    await queries.delete_idea(iid)


@app.post("/api/saas/ideas/{iid}/promote")
async def promote_idea(iid: int):
    try:
        return await saas.promote_to_stream(iid)
    except ValueError as e:
        raise HTTPException(404, str(e))


def _saas_gen(fn):
    async def wrapper(iid: int):
        try:
            return await fn(iid)
        except ai.AIError as e:
            raise HTTPException(400, str(e))
        except ValueError as e:
            raise HTTPException(404, str(e))
    return wrapper


@app.post("/api/saas/ideas/{iid}/build-kit")
async def saas_build_kit(iid: int):
    return await _saas_gen(saas.build_kit)(iid)


@app.post("/api/saas/ideas/{iid}/research")
async def saas_research(iid: int):
    return await _saas_gen(saas.research)(iid)


@app.post("/api/saas/ideas/{iid}/landing")
async def saas_landing(iid: int):
    return await _saas_gen(saas.landing_page)(iid)


@app.get("/api/saas/ideas/{iid}/landing", response_class=HTMLResponse)
async def saas_landing_view(iid: int):
    html = await queries.get_idea_landing(iid)
    if not html:
        raise HTTPException(404, "no landing page generated")
    return HTMLResponse(html)


@app.post("/api/saas/ideas/{iid}/signup", status_code=201)
async def saas_signup(iid: int, body: SignupIn):
    return {"signups": await queries.add_signup(iid, body.email.strip())}


@app.get("/api/saas/ideas/{iid}/signups")
async def saas_list_signups(iid: int):
    return await queries.list_signups(iid)


@app.get("/api/saas/ideas/{iid}/signups/csv")
async def saas_signups_csv(iid: int):
    rows = await queries.list_signups(iid)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["email", "signed_up_at"])
    for r in rows:
        w.writerow([r["email"], r["created_at"]])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=signups_{iid}.csv"})


# ── Faceless YouTube ──────────────────────────────────────────────────────────

@app.get("/api/yt/channels")
async def list_channels():
    return await queries.list_channels()


@app.post("/api/yt/channels", status_code=201)
async def create_channel(body: ChannelIn):
    return await queries.create_channel(body.model_dump())


@app.delete("/api/yt/channels/{cid}", status_code=204)
async def delete_channel(cid: int):
    await queries.delete_channel(cid)


@app.get("/api/yt/videos")
async def list_videos(channel_id: int | None = None):
    return await queries.list_videos(channel_id)


@app.post("/api/yt/videos", status_code=201)
async def create_video(body: VideoIn):
    return await queries.create_video(body.model_dump())


@app.get("/api/yt/videos/{vid}")
async def get_video(vid: int):
    v = await queries.get_video(vid)
    if not v:
        raise HTTPException(404)
    return v


@app.post("/api/yt/topics/{channel_id}")
async def suggest_topics(channel_id: int):
    channels = {c["id"]: c for c in await queries.list_channels()}
    ch = channels.get(channel_id)
    if not ch:
        raise HTTPException(404)
    try:
        return {"topics": ai.generate_topics(ch["name"], ch["niche"], ch["style"])}
    except ai.AIError as e:
        raise HTTPException(400, str(e))


def _step(fn):
    async def wrapper(vid: int):
        try:
            return await fn(vid)
        except ai.AIError as e:
            raise HTTPException(400, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(500, str(e))
    return wrapper


@app.post("/api/yt/videos/{vid}/script")
async def video_script(vid: int):
    return await _step(yt.write_script)(vid)


@app.post("/api/yt/videos/{vid}/voice")
async def video_voice(vid: int):
    return await _step(yt.make_voiceover)(vid)


@app.post("/api/yt/videos/{vid}/render")
async def video_render(vid: int):
    return await _step(yt.render_final)(vid)


@app.post("/api/yt/videos/{vid}/upload")
async def video_upload(vid: int):
    return await _step(yt.upload)(vid)


@app.post("/api/yt/videos/{vid}/pipeline")
async def video_pipeline(vid: int):
    try:
        return await yt.run_full_pipeline(vid, do_upload=False)
    except Exception as e:
        raise HTTPException(400, str(e))


# ── Batch + background queue ───────────────────────────────────────────────────

@app.post("/api/yt/batch", status_code=201)
async def yt_batch(body: BatchIn):
    """Create a batch of videos (from topics or AI) and optionally queue them all."""
    try:
        videos = await yt.create_batch(body.channel_id, body.count, body.topics, body.focus)
    except ai.AIError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    if body.auto_run:
        await jobqueue.enqueue_many([v["id"] for v in videos], body.do_upload)
    return {"videos": videos, "queued": body.auto_run}


@app.post("/api/yt/videos/{vid}/enqueue")
async def yt_enqueue(vid: int, body: EnqueueIn):
    if not await queries.get_video(vid):
        raise HTTPException(404)
    await jobqueue.enqueue(vid, body.do_upload)
    return await jobqueue.snapshot()


@app.post("/api/yt/queue/enqueue_channel/{cid}")
async def yt_enqueue_channel(cid: int, body: EnqueueIn):
    vids = await queries.list_videos(cid)
    todo = [v["id"] for v in vids
            if v["queue_status"] not in ("queued", "running") and v["stage"] != "published"
            and not v["video_path"]]
    n = await jobqueue.enqueue_many(todo, body.do_upload)
    return {"queued": n, **(await jobqueue.snapshot(cid))}


@app.get("/api/yt/queue")
async def yt_queue(channel_id: int | None = None):
    return await jobqueue.snapshot(channel_id)


@app.post("/api/yt/queue/clear")
async def yt_queue_clear():
    return {"cleared": await jobqueue.clear_pending()}


@app.get("/api/yt/videos/{vid}/file")
async def video_file(vid: int):
    v = await queries.get_video(vid)
    if not v or not v["video_path"] or not Path(v["video_path"]).exists():
        raise HTTPException(404, "no rendered file")
    return FileResponse(v["video_path"], media_type="video/mp4",
                        filename=f"{(v['title'] or v['topic'])[:40]}.mp4")


# ── Sports betting ─────────────────────────────────────────────────────────────

@app.get("/api/bet/summary")
async def bet_summary():
    s = await queries.betting_summary()
    s["odds_ready"] = odds.is_configured()
    return s


@app.get("/api/bet/scan/sports")
async def bet_scan_sports():
    try:
        return await asyncio.to_thread(odds.list_sports)
    except odds.OddsError as e:
        raise HTTPException(400, str(e))


@app.post("/api/bet/scan")
async def bet_scan(body: ScanIn):
    if not body.sports:
        raise HTTPException(400, "Pick at least one sport to scan.")
    try:
        return await asyncio.to_thread(odds.scan, body.sports, body.regions, body.min_profit)
    except odds.OddsError as e:
        raise HTTPException(400, str(e))


@app.get("/api/bet/books")
async def bet_books():
    return await queries.list_bookmakers()


@app.post("/api/bet/books", status_code=201)
async def bet_book_create(body: BookmakerIn):
    return await queries.create_bookmaker(body.model_dump())


@app.put("/api/bet/books/{bid}")
async def bet_book_update(bid: int, body: BookmakerPatch):
    out = await queries.update_bookmaker(bid, body.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(404)
    return out


@app.delete("/api/bet/books/{bid}", status_code=204)
async def bet_book_delete(bid: int):
    await queries.delete_bookmaker(bid)


@app.get("/api/bet/arbs")
async def bet_arbs():
    return await queries.list_arbs()


@app.post("/api/bet/arbs", status_code=201)
async def bet_arb_create(body: ArbIn):
    return await queries.create_arb(body.model_dump())


@app.delete("/api/bet/arbs/{arb_id}", status_code=204)
async def bet_arb_delete(arb_id: int):
    await queries.delete_arb(arb_id)


@app.get("/api/bet/bets")
async def bet_singles():
    return await queries.list_single_bets()


@app.post("/api/bet/bets", status_code=201)
async def bet_create(body: BetIn):
    return await queries.create_bet(body.model_dump())


@app.put("/api/bet/bets/{bet_id}")
async def bet_update(bet_id: int, body: BetPatch):
    out = await queries.update_bet(bet_id, body.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(404)
    return out


@app.delete("/api/bet/bets/{bet_id}", status_code=204)
async def bet_delete(bet_id: int):
    await queries.delete_bet(bet_id)


@app.post("/api/bet/sync")
async def bet_sync():
    s = await queries.betting_summary()
    return await queries.upsert_betting_stream(s["month_profit"])


@app.get("/api/bet/history")
async def bet_history():
    return await queries.bet_daily_history()


# ── Goals ─────────────────────────────────────────────────────────────────────

@app.get("/api/goals/current")
async def get_current_goal():
    from datetime import datetime, timezone
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    return await queries.get_goal(period) or {"period": period, "target_revenue": 0, "target_net": 0}


@app.put("/api/goals/current")
async def set_current_goal(body: GoalIn):
    return await queries.upsert_goal(body.period, body.target_revenue, body.target_net)


# ── Shared / recurring costs ──────────────────────────────────────────────────

@app.get("/api/costs")
async def list_costs():
    return await queries.list_shared_costs()


@app.post("/api/costs", status_code=201)
async def create_cost(body: SharedCostIn):
    return await queries.create_shared_cost(body.model_dump())


@app.put("/api/costs/{cid}")
async def update_cost(cid: int, body: SharedCostPatch):
    out = await queries.update_shared_cost(cid, body.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(404)
    return out


@app.delete("/api/costs/{cid}", status_code=204)
async def delete_cost(cid: int):
    await queries.delete_shared_cost(cid)


# ── Freelance tracker ─────────────────────────────────────────────────────────

@app.get("/api/fl/summary")
async def fl_summary():
    return await queries.freelance_summary()


@app.get("/api/fl/clients")
async def fl_clients():
    return await queries.list_clients()


@app.post("/api/fl/clients", status_code=201)
async def fl_create_client(body: ClientIn):
    return await queries.create_client(body.model_dump())


@app.put("/api/fl/clients/{cid}")
async def fl_update_client(cid: int, body: ClientPatch):
    out = await queries.update_client(cid, body.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(404)
    return out


@app.delete("/api/fl/clients/{cid}", status_code=204)
async def fl_delete_client(cid: int):
    await queries.delete_client(cid)


@app.get("/api/fl/projects")
async def fl_projects(client_id: int | None = None):
    return await queries.list_projects(client_id)


@app.post("/api/fl/projects", status_code=201)
async def fl_create_project(body: ProjectIn):
    return await queries.create_project(body.model_dump())


@app.put("/api/fl/projects/{pid}")
async def fl_update_project(pid: int, body: ProjectPatch):
    out = await queries.update_project(pid, body.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(404)
    return out


@app.delete("/api/fl/projects/{pid}", status_code=204)
async def fl_delete_project(pid: int):
    await queries.delete_project(pid)


@app.get("/api/fl/invoices")
async def fl_invoices(project_id: int | None = None):
    return await queries.list_invoices(project_id)


@app.post("/api/fl/invoices", status_code=201)
async def fl_create_invoice(body: InvoiceIn):
    return await queries.create_invoice(body.model_dump())


@app.put("/api/fl/invoices/{iid}")
async def fl_update_invoice(iid: int, body: InvoicePatch):
    out = await queries.update_invoice(iid, body.model_dump(exclude_none=True))
    if not out:
        raise HTTPException(404)
    return out


@app.delete("/api/fl/invoices/{iid}", status_code=204)
async def fl_delete_invoice(iid: int):
    await queries.delete_invoice(iid)


@app.post("/api/fl/sync")
async def fl_sync():
    s = await queries.freelance_summary()
    return await queries.sync_freelance_stream(s["month_earned"])


# ── Settings ──────────────────────────────────────────────────────────────────

@app.post("/api/settings")
async def update_settings(body: SettingsPatch):
    cfg.save_settings(**body.model_dump(exclude_none=True))
    return cfg.get_settings()
