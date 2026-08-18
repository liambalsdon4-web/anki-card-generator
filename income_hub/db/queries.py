"""Thin async data-access helpers over aiosqlite."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import aiosqlite

from config.settings import DB_PATH


def _now_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def _conn():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db


# ── income streams ───────────────────────────────────────────────────────────

async def list_streams() -> list[dict]:
    db = await _conn()
    try:
        rows = await db.execute_fetchall("SELECT * FROM income_streams ORDER BY updated_at DESC")
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def create_stream(data: dict) -> dict:
    db = await _conn()
    try:
        cur = await db.execute(
            """INSERT INTO income_streams (name, kind, status, monthly_revenue, monthly_cost, url, notes, ref_type, ref_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (data["name"], data.get("kind", "other"), data.get("status", "idea"),
             data.get("monthly_revenue", 0), data.get("monthly_cost", 0),
             data.get("url", ""), data.get("notes", ""),
             data.get("ref_type", ""), data.get("ref_id")),
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM income_streams WHERE id=?", (cur.lastrowid,))
        return dict(rows[0])
    finally:
        await db.close()


async def update_stream(sid: int, data: dict) -> dict | None:
    fields = ["name", "kind", "status", "monthly_revenue", "monthly_cost", "url", "notes"]
    sets, vals = [], []
    for f in fields:
        if f in data and data[f] is not None:
            sets.append(f"{f}=?")
            vals.append(data[f])
    if not sets:
        return None
    sets.append("updated_at=datetime('now')")
    vals.append(sid)
    db = await _conn()
    try:
        await db.execute(f"UPDATE income_streams SET {', '.join(sets)} WHERE id=?", vals)
        # Mirror monthly figures into this month's revenue_log row.
        if "monthly_revenue" in data or "monthly_cost" in data:
            await db.execute(
                """INSERT INTO revenue_log (stream_id, period, revenue, cost)
                   VALUES (?,?,?,?)
                   ON CONFLICT(stream_id, period) DO UPDATE SET
                     revenue=excluded.revenue, cost=excluded.cost""",
                (sid, _now_period(), data.get("monthly_revenue", 0), data.get("monthly_cost", 0)),
            )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM income_streams WHERE id=?", (sid,))
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


async def delete_stream(sid: int) -> None:
    db = await _conn()
    try:
        await db.execute("DELETE FROM income_streams WHERE id=?", (sid,))
        await db.commit()
    finally:
        await db.close()


async def revenue_trend(months: int = 6) -> dict:
    db = await _conn()
    try:
        rows = await db.execute_fetchall(
            """SELECT period, SUM(revenue) AS revenue, SUM(cost) AS cost
               FROM revenue_log GROUP BY period ORDER BY period DESC LIMIT ?""",
            (months,),
        )
        rows = list(reversed([dict(r) for r in rows]))
        return {
            "labels": [r["period"] for r in rows],
            "revenue": [round(r["revenue"] or 0, 2) for r in rows],
            "cost": [round(r["cost"] or 0, 2) for r in rows],
        }
    finally:
        await db.close()


# ── saas ideas ────────────────────────────────────────────────────────────────

async def insert_ideas(ideas: list[dict]) -> None:
    db = await _conn()
    try:
        for i in ideas:
            await db.execute(
                """INSERT INTO saas_ideas
                   (name, problem, target_user, solution, monetization, demand, competition,
                    willingness_to_pay, build_effort, founder_fit, score, est_mrr_range, tags,
                    validation_json, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (i["name"], i.get("problem", ""), i.get("target_user", ""), i.get("solution", ""),
                 i.get("monetization", ""), i.get("demand", 0), i.get("competition", 0),
                 i.get("willingness_to_pay", 0), i.get("build_effort", 0), i.get("founder_fit", 0),
                 i.get("score", 0), i.get("est_mrr_range", ""), i.get("tags", ""),
                 json.dumps(i.get("validation", [])), i.get("status", "new")),
            )
        await db.commit()
    finally:
        await db.close()


_IDEA_JSON = {"validation": "validation_json", "tasks": "tasks_json",
              "build_kit": "build_kit_json", "research": "research_json"}


def _idea_row(d: dict, signups: int = 0) -> dict:
    d["validation"] = json.loads(d.pop("validation_json") or "[]")
    d["tasks"] = json.loads(d.pop("tasks_json") or "[]")
    d["build_kit"] = json.loads(d.pop("build_kit_json") or "null")
    d["research"] = json.loads(d.pop("research_json") or "null")
    d["has_landing"] = bool(d.get("landing_html"))
    d.pop("landing_html", None)
    d["signups"] = signups
    return d


async def list_ideas() -> list[dict]:
    db = await _conn()
    try:
        rows = await db.execute_fetchall("SELECT * FROM saas_ideas ORDER BY score DESC, id DESC")
        crows = await db.execute_fetchall("SELECT idea_id, COUNT(*) c FROM saas_signups GROUP BY idea_id")
        counts = {r["idea_id"]: r["c"] for r in crows}
        return [_idea_row(dict(r), counts.get(r["id"], 0)) for r in rows]
    finally:
        await db.close()


async def get_idea(iid: int) -> dict | None:
    db = await _conn()
    try:
        rows = await db.execute_fetchall("SELECT * FROM saas_ideas WHERE id=?", (iid,))
        if not rows:
            return None
        crows = await db.execute_fetchall("SELECT COUNT(*) c FROM saas_signups WHERE idea_id=?", (iid,))
        return _idea_row(dict(rows[0]), crows[0]["c"])
    finally:
        await db.close()


async def get_idea_landing(iid: int) -> str | None:
    db = await _conn()
    try:
        rows = await db.execute_fetchall("SELECT landing_html FROM saas_ideas WHERE id=?", (iid,))
        return rows[0]["landing_html"] if rows else None
    finally:
        await db.close()


async def update_idea(iid: int, data: dict) -> dict | None:
    scalar = {"status", "stage", "mrr", "landing_html"}
    sets, vals = [], []
    for k, v in data.items():
        if k in _IDEA_JSON:
            sets.append(f"{_IDEA_JSON[k]}=?")
            vals.append(json.dumps(v))
        elif k in scalar:
            sets.append(f"{k}=?")
            vals.append(v)
    if not sets:
        return await get_idea(iid)
    vals.append(iid)
    db = await _conn()
    try:
        await db.execute(f"UPDATE saas_ideas SET {', '.join(sets)} WHERE id=?", vals)
        await db.commit()
    finally:
        await db.close()
    return await get_idea(iid)


async def delete_idea(iid: int) -> None:
    db = await _conn()
    try:
        await db.execute("DELETE FROM saas_ideas WHERE id=?", (iid,))
        await db.commit()
    finally:
        await db.close()


async def add_signup(idea_id: int, email: str) -> int:
    db = await _conn()
    try:
        await db.execute("INSERT INTO saas_signups (idea_id, email) VALUES (?,?)", (idea_id, email))
        await db.commit()
        rows = await db.execute_fetchall("SELECT COUNT(*) c FROM saas_signups WHERE idea_id=?", (idea_id,))
        return rows[0]["c"]
    finally:
        await db.close()


# ── youtube ──────────────────────────────────────────────────────────────────

async def create_channel(data: dict) -> dict:
    db = await _conn()
    try:
        cur = await db.execute(
            """INSERT INTO yt_channels (name, niche, style, voice, target_length_words, cadence, notes)
               VALUES (?,?,?,?,?,?,?)""",
            (data["name"], data.get("niche", ""), data.get("style", "top-10 list"),
             data.get("voice", "en-US-AndrewNeural"), data.get("target_length_words", 220),
             data.get("cadence", "weekly"), data.get("notes", "")),
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM yt_channels WHERE id=?", (cur.lastrowid,))
        return dict(rows[0])
    finally:
        await db.close()


async def list_channels() -> list[dict]:
    db = await _conn()
    try:
        rows = await db.execute_fetchall("SELECT * FROM yt_channels ORDER BY id DESC")
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def delete_channel(cid: int) -> None:
    db = await _conn()
    try:
        await db.execute("DELETE FROM yt_channels WHERE id=?", (cid,))
        await db.commit()
    finally:
        await db.close()


async def create_video(data: dict) -> dict:
    db = await _conn()
    try:
        cur = await db.execute(
            "INSERT INTO yt_videos (channel_id, topic, stage) VALUES (?,?,?)",
            (data["channel_id"], data["topic"], "idea"),
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM yt_videos WHERE id=?", (cur.lastrowid,))
        return _video_row(rows[0])
    finally:
        await db.close()


async def list_videos(channel_id: int | None = None) -> list[dict]:
    db = await _conn()
    try:
        if channel_id:
            rows = await db.execute_fetchall(
                "SELECT * FROM yt_videos WHERE channel_id=? ORDER BY id DESC", (channel_id,))
        else:
            rows = await db.execute_fetchall("SELECT * FROM yt_videos ORDER BY id DESC")
        return [_video_row(r) for r in rows]
    finally:
        await db.close()


async def get_video(vid: int) -> dict | None:
    db = await _conn()
    try:
        rows = await db.execute_fetchall("SELECT * FROM yt_videos WHERE id=?", (vid,))
        return _video_row(rows[0]) if rows else None
    finally:
        await db.close()


async def update_video(vid: int, data: dict) -> dict | None:
    cols = {"stage", "title", "description", "tags", "thumbnail_prompt",
            "audio_path", "video_path", "youtube_id", "views", "error", "queue_upload"}
    sets, vals = [], []
    for k, v in data.items():
        if k == "script":
            sets.append("script_json=?")
            vals.append(json.dumps(v))
        elif k in cols:
            sets.append(f"{k}=?")
            vals.append(v)
    if not sets:
        return await get_video(vid)
    sets.append("updated_at=datetime('now')")
    vals.append(vid)
    db = await _conn()
    try:
        await db.execute(f"UPDATE yt_videos SET {', '.join(sets)} WHERE id=?", vals)
        await db.commit()
    finally:
        await db.close()
    return await get_video(vid)


async def set_queue(vid: int, status: str, msg: str = "") -> None:
    db = await _conn()
    try:
        await db.execute(
            "UPDATE yt_videos SET queue_status=?, queue_msg=?, updated_at=datetime('now') WHERE id=?",
            (status, msg, vid),
        )
        await db.commit()
    finally:
        await db.close()


async def videos_in_queue() -> list[dict]:
    """Videos that were queued or mid-run — used to resume the worker on startup."""
    db = await _conn()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM yt_videos WHERE queue_status IN ('queued','running') ORDER BY id")
        return [_video_row(r) for r in rows]
    finally:
        await db.close()


async def queue_items(channel_id: int | None = None) -> list[dict]:
    """Active/failed queue rows for the queue panel."""
    db = await _conn()
    try:
        sql = "SELECT * FROM yt_videos WHERE queue_status IN ('queued','running','failed')"
        args: tuple = ()
        if channel_id:
            sql += " AND channel_id=?"
            args = (channel_id,)
        sql += " ORDER BY CASE queue_status WHEN 'running' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END, id"
        rows = await db.execute_fetchall(sql, args)
        return [_video_row(r) for r in rows]
    finally:
        await db.close()


def _video_row(r) -> dict:
    d = dict(r)
    d["script"] = json.loads(d.pop("script_json") or "[]")
    return d


# ── Sports betting ─────────────────────────────────────────────────────────────

def bet_profit(status: str, odds: float, stake: float) -> float:
    if status == "won":
        return round(stake * (odds - 1), 2)
    if status == "lost":
        return round(-stake, 2)
    return 0.0  # pending / void


async def list_bookmakers() -> list[dict]:
    db = await _conn()
    try:
        rows = await db.execute_fetchall("SELECT * FROM bookmakers ORDER BY name COLLATE NOCASE")
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def create_bookmaker(data: dict) -> dict:
    db = await _conn()
    try:
        cur = await db.execute(
            "INSERT INTO bookmakers (name, balance, status, notes) VALUES (?,?,?,?)",
            (data["name"], data.get("balance", 0), data.get("status", "active"), data.get("notes", "")),
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM bookmakers WHERE id=?", (cur.lastrowid,))
        return dict(rows[0])
    finally:
        await db.close()


async def update_bookmaker(bid: int, data: dict) -> dict | None:
    sets, vals = [], []
    for f in ("name", "balance", "status", "notes"):
        if f in data and data[f] is not None:
            sets.append(f"{f}=?")
            vals.append(data[f])
    if not sets:
        return None
    sets.append("updated_at=datetime('now')")
    vals.append(bid)
    db = await _conn()
    try:
        await db.execute(f"UPDATE bookmakers SET {', '.join(sets)} WHERE id=?", vals)
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM bookmakers WHERE id=?", (bid,))
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


async def delete_bookmaker(bid: int) -> None:
    db = await _conn()
    try:
        await db.execute("DELETE FROM bookmakers WHERE id=?", (bid,))
        await db.commit()
    finally:
        await db.close()


async def create_arb(data: dict) -> dict:
    db = await _conn()
    try:
        cur = await db.execute(
            """INSERT INTO arbs (event, sport, stake_total, profit_pct, guaranteed_profit, notes)
               VALUES (?,?,?,?,?,?)""",
            (data["event"], data.get("sport", ""), data.get("stake_total", 0),
             data.get("profit_pct", 0), data.get("guaranteed_profit", 0), data.get("notes", "")),
        )
        arb_id = cur.lastrowid
        for leg in data.get("legs", []):
            await db.execute(
                """INSERT INTO bets (arb_id, bookmaker_id, event, selection, odds, stake, status)
                   VALUES (?,?,?,?,?,?, 'pending')""",
                (arb_id, leg.get("bookmaker_id"), data["event"], leg.get("selection", ""),
                 leg.get("odds", 0), leg.get("stake", 0)),
            )
        await db.commit()
        return await _get_arb(db, arb_id)
    finally:
        await db.close()


async def _get_arb(db, arb_id: int) -> dict | None:
    rows = await db.execute_fetchall("SELECT * FROM arbs WHERE id=?", (arb_id,))
    if not rows:
        return None
    arb = dict(rows[0])
    legs = await db.execute_fetchall("SELECT * FROM bets WHERE arb_id=? ORDER BY id", (arb_id,))
    arb["legs"] = [dict(l) for l in legs]
    return arb


async def list_arbs() -> list[dict]:
    db = await _conn()
    try:
        arows = await db.execute_fetchall("SELECT * FROM arbs ORDER BY id DESC")
        brows = await db.execute_fetchall("SELECT * FROM bets WHERE arb_id IS NOT NULL ORDER BY id")
        legs_by_arb: dict[int, list] = {}
        for b in brows:
            legs_by_arb.setdefault(b["arb_id"], []).append(dict(b))
        out = []
        for a in arows:
            d = dict(a)
            d["legs"] = legs_by_arb.get(a["id"], [])
            out.append(d)
        return out
    finally:
        await db.close()


async def delete_arb(arb_id: int) -> None:
    db = await _conn()
    try:
        await db.execute("DELETE FROM arbs WHERE id=?", (arb_id,))
        await db.commit()
    finally:
        await db.close()


async def list_single_bets() -> list[dict]:
    db = await _conn()
    try:
        rows = await db.execute_fetchall("SELECT * FROM bets WHERE arb_id IS NULL ORDER BY id DESC")
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def create_bet(data: dict) -> dict:
    status = data.get("status", "pending")
    profit = bet_profit(status, data.get("odds", 0), data.get("stake", 0))
    db = await _conn()
    try:
        cur = await db.execute(
            """INSERT INTO bets (arb_id, bookmaker_id, event, selection, odds, stake, status, profit, settled_at)
               VALUES (?,?,?,?,?,?,?,?, CASE WHEN ?='pending' THEN NULL ELSE datetime('now') END)""",
            (data.get("arb_id"), data.get("bookmaker_id"), data.get("event", ""), data.get("selection", ""),
             data.get("odds", 0), data.get("stake", 0), status, profit, status),
        )
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM bets WHERE id=?", (cur.lastrowid,))
        return dict(rows[0])
    finally:
        await db.close()


async def update_bet(bet_id: int, data: dict) -> dict | None:
    db = await _conn()
    try:
        rows = await db.execute_fetchall("SELECT * FROM bets WHERE id=?", (bet_id,))
        if not rows:
            return None
        cur = dict(rows[0])
        odds = data.get("odds", cur["odds"])
        stake = data.get("stake", cur["stake"])
        status = data.get("status", cur["status"])
        sets = {"odds": odds, "stake": stake, "status": status,
                "selection": data.get("selection", cur["selection"]),
                "profit": bet_profit(status, odds, stake)}
        cols = ", ".join(f"{k}=?" for k in sets)
        vals = list(sets.values())
        settled = "settled_at=CASE WHEN ?='pending' THEN NULL ELSE COALESCE(settled_at, datetime('now')) END"
        await db.execute(f"UPDATE bets SET {cols}, {settled} WHERE id=?", (*vals, status, bet_id))
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM bets WHERE id=?", (bet_id,))
        return dict(rows[0])
    finally:
        await db.close()


async def delete_bet(bet_id: int) -> None:
    db = await _conn()
    try:
        await db.execute("DELETE FROM bets WHERE id=?", (bet_id,))
        await db.commit()
    finally:
        await db.close()


async def betting_summary() -> dict:
    db = await _conn()
    try:
        (bankroll,) = list(await db.execute_fetchall("SELECT COALESCE(SUM(balance),0) FROM bookmakers"))[0]
        (books,) = list(await db.execute_fetchall("SELECT COUNT(*) FROM bookmakers"))[0]
        rows = await db.execute_fetchall("SELECT status, stake, profit, settled_at FROM bets")
        realized = sum(r["profit"] for r in rows if r["status"] in ("won", "lost", "void"))
        pending_stake = sum(r["stake"] for r in rows if r["status"] == "pending")
        turnover = sum(r["stake"] for r in rows if r["status"] in ("won", "lost", "void"))
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        month_profit = sum(r["profit"] for r in rows
                           if r["status"] in ("won", "lost", "void") and (r["settled_at"] or "").startswith(month))
        return {
            "bankroll": round(bankroll or 0, 2),
            "book_count": books,
            "realized_profit": round(realized, 2),
            "pending_stake": round(pending_stake, 2),
            "turnover": round(turnover, 2),
            "roi": round(realized / turnover * 100, 2) if turnover else 0.0,
            "month_profit": round(month_profit, 2),
            "open_bets": sum(1 for r in rows if r["status"] == "pending"),
        }
    finally:
        await db.close()


async def list_signups(idea_id: int) -> list[dict]:
    db = await _conn()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM saas_signups WHERE idea_id=? ORDER BY created_at DESC", (idea_id,))
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def bet_daily_history() -> dict:
    db = await _conn()
    try:
        rows = await db.execute_fetchall(
            """SELECT date(settled_at) AS day, SUM(profit) AS profit
               FROM bets WHERE status IN ('won','lost','void') AND settled_at IS NOT NULL
               GROUP BY day ORDER BY day""")
        rows = [dict(r) for r in rows]
        cumulative, running = [], 0.0
        for r in rows:
            running = round(running + (r["profit"] or 0), 2)
            cumulative.append({"day": r["day"], "profit": running})
        return {
            "labels": [r["day"] for r in cumulative],
            "values": [r["profit"] for r in cumulative],
        }
    finally:
        await db.close()


async def get_goal(period: str) -> dict | None:
    db = await _conn()
    try:
        rows = await db.execute_fetchall("SELECT * FROM income_goals WHERE period=?", (period,))
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


async def upsert_goal(period: str, target_revenue: float, target_net: float) -> dict:
    db = await _conn()
    try:
        await db.execute(
            """INSERT INTO income_goals (period, target_revenue, target_net) VALUES (?,?,?)
               ON CONFLICT(period) DO UPDATE SET
                 target_revenue=excluded.target_revenue, target_net=excluded.target_net,
                 updated_at=datetime('now')""",
            (period, target_revenue, target_net))
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM income_goals WHERE period=?", (period,))
        return dict(rows[0])
    finally:
        await db.close()


async def list_shared_costs() -> list[dict]:
    db = await _conn()
    try:
        rows = await db.execute_fetchall("SELECT * FROM shared_costs ORDER BY name COLLATE NOCASE")
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def create_shared_cost(data: dict) -> dict:
    db = await _conn()
    try:
        cur = await db.execute(
            "INSERT INTO shared_costs (name, amount, category, url, notes, active) VALUES (?,?,?,?,?,1)",
            (data["name"], data.get("amount", 0), data.get("category", "other"),
             data.get("url", ""), data.get("notes", "")))
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM shared_costs WHERE id=?", (cur.lastrowid,))
        return dict(rows[0])
    finally:
        await db.close()


async def update_shared_cost(cid: int, data: dict) -> dict | None:
    sets, vals = [], []
    for f in ("name", "amount", "category", "url", "notes", "active"):
        if f in data and data[f] is not None:
            sets.append(f"{f}=?")
            vals.append(data[f])
    if not sets:
        return None
    sets.append("updated_at=datetime('now')")
    vals.append(cid)
    db = await _conn()
    try:
        await db.execute(f"UPDATE shared_costs SET {', '.join(sets)} WHERE id=?", vals)
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM shared_costs WHERE id=?", (cid,))
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


async def delete_shared_cost(cid: int) -> None:
    db = await _conn()
    try:
        await db.execute("DELETE FROM shared_costs WHERE id=?", (cid,))
        await db.commit()
    finally:
        await db.close()


# ── Freelance ──────────────────────────────────────────────────────────────────

async def list_clients() -> list[dict]:
    db = await _conn()
    try:
        rows = await db.execute_fetchall("SELECT * FROM fl_clients ORDER BY name COLLATE NOCASE")
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def create_client(data: dict) -> dict:
    db = await _conn()
    try:
        cur = await db.execute(
            "INSERT INTO fl_clients (name, contact, email, url, notes) VALUES (?,?,?,?,?)",
            (data["name"], data.get("contact", ""), data.get("email", ""),
             data.get("url", ""), data.get("notes", "")))
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM fl_clients WHERE id=?", (cur.lastrowid,))
        return dict(rows[0])
    finally:
        await db.close()


async def update_client(cid: int, data: dict) -> dict | None:
    sets, vals = [], []
    for f in ("name", "contact", "email", "url", "notes"):
        if f in data and data[f] is not None:
            sets.append(f"{f}=?")
            vals.append(data[f])
    if not sets:
        return None
    vals.append(cid)
    db = await _conn()
    try:
        await db.execute(f"UPDATE fl_clients SET {', '.join(sets)} WHERE id=?", vals)
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM fl_clients WHERE id=?", (cid,))
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


async def delete_client(cid: int) -> None:
    db = await _conn()
    try:
        await db.execute("DELETE FROM fl_clients WHERE id=?", (cid,))
        await db.commit()
    finally:
        await db.close()


async def list_projects(client_id: int | None = None) -> list[dict]:
    db = await _conn()
    try:
        if client_id:
            rows = await db.execute_fetchall(
                "SELECT * FROM fl_projects WHERE client_id=? ORDER BY updated_at DESC", (client_id,))
        else:
            rows = await db.execute_fetchall("SELECT * FROM fl_projects ORDER BY updated_at DESC")
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def create_project(data: dict) -> dict:
    db = await _conn()
    try:
        cur = await db.execute(
            """INSERT INTO fl_projects (client_id, name, status, rate_type, rate, hours_logged, due_date, notes)
               VALUES (?,?,?,?,?,?,?,?)""",
            (data.get("client_id"), data["name"], data.get("status", "lead"),
             data.get("rate_type", "fixed"), data.get("rate", 0),
             data.get("hours_logged", 0), data.get("due_date", ""), data.get("notes", "")))
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM fl_projects WHERE id=?", (cur.lastrowid,))
        return dict(rows[0])
    finally:
        await db.close()


async def update_project(pid: int, data: dict) -> dict | None:
    sets, vals = [], []
    for f in ("name", "status", "rate_type", "rate", "hours_logged", "due_date", "notes"):
        if f in data and data[f] is not None:
            sets.append(f"{f}=?")
            vals.append(data[f])
    if not sets:
        return None
    sets.append("updated_at=datetime('now')")
    vals.append(pid)
    db = await _conn()
    try:
        await db.execute(f"UPDATE fl_projects SET {', '.join(sets)} WHERE id=?", vals)
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM fl_projects WHERE id=?", (pid,))
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


async def delete_project(pid: int) -> None:
    db = await _conn()
    try:
        await db.execute("DELETE FROM fl_projects WHERE id=?", (pid,))
        await db.commit()
    finally:
        await db.close()


async def list_invoices(project_id: int | None = None) -> list[dict]:
    db = await _conn()
    try:
        if project_id:
            rows = await db.execute_fetchall(
                "SELECT * FROM fl_invoices WHERE project_id=? ORDER BY created_at DESC", (project_id,))
        else:
            rows = await db.execute_fetchall("SELECT * FROM fl_invoices ORDER BY created_at DESC")
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def create_invoice(data: dict) -> dict:
    db = await _conn()
    try:
        paid_at = None
        if data.get("status") == "paid":
            paid_at = datetime.now(timezone.utc).isoformat()
        cur = await db.execute(
            "INSERT INTO fl_invoices (project_id, amount, status, due_date, paid_at, notes) VALUES (?,?,?,?,?,?)",
            (data.get("project_id"), data.get("amount", 0), data.get("status", "draft"),
             data.get("due_date", ""), paid_at, data.get("notes", "")))
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM fl_invoices WHERE id=?", (cur.lastrowid,))
        return dict(rows[0])
    finally:
        await db.close()


async def update_invoice(iid: int, data: dict) -> dict | None:
    db = await _conn()
    try:
        rows = await db.execute_fetchall("SELECT * FROM fl_invoices WHERE id=?", (iid,))
        if not rows:
            return None
        cur = dict(rows[0])
        status = data.get("status", cur["status"])
        paid_at = cur["paid_at"]
        if status == "paid" and not paid_at:
            paid_at = datetime.now(timezone.utc).isoformat()
        amount = data.get("amount", cur["amount"])
        due_date = data.get("due_date", cur["due_date"])
        notes = data.get("notes", cur["notes"])
        await db.execute(
            "UPDATE fl_invoices SET status=?, paid_at=?, amount=?, due_date=?, notes=? WHERE id=?",
            (status, paid_at, amount, due_date, notes, iid))
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM fl_invoices WHERE id=?", (iid,))
        return dict(rows[0])
    finally:
        await db.close()


async def delete_invoice(iid: int) -> None:
    db = await _conn()
    try:
        await db.execute("DELETE FROM fl_invoices WHERE id=?", (iid,))
        await db.commit()
    finally:
        await db.close()


async def freelance_summary() -> dict:
    db = await _conn()
    try:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        irows = await db.execute_fetchall("SELECT amount, status, paid_at FROM fl_invoices")
        total_earned = sum(r["amount"] for r in irows if r["status"] == "paid")
        pending = sum(r["amount"] for r in irows if r["status"] in ("draft", "sent"))
        month_earned = sum(r["amount"] for r in irows
                           if r["status"] == "paid" and (r["paid_at"] or "").startswith(month))
        (client_count,) = list(await db.execute_fetchall("SELECT COUNT(*) FROM fl_clients"))[0]
        (active_projects,) = list(await db.execute_fetchall(
            "SELECT COUNT(*) FROM fl_projects WHERE status='active'"))[0]
        return {
            "total_earned": round(total_earned, 2),
            "pending": round(pending, 2),
            "month_earned": round(month_earned, 2),
            "client_count": int(client_count),
            "active_projects": int(active_projects),
        }
    finally:
        await db.close()


async def sync_freelance_stream(month_earned: float) -> dict:
    db = await _conn()
    try:
        rows = await db.execute_fetchall(
            "SELECT id FROM income_streams WHERE kind='freelance' AND name='Freelance / Web Dev' LIMIT 1")
        rev = round(max(0.0, month_earned), 2)
        if rows:
            await db.execute(
                "UPDATE income_streams SET monthly_revenue=?, status='earning', updated_at=datetime('now') WHERE id=?",
                (rev, rows[0]["id"]))
            sid = rows[0]["id"]
        else:
            cur = await db.execute(
                """INSERT INTO income_streams (name, kind, status, monthly_revenue, notes)
                   VALUES ('Freelance / Web Dev', 'freelance', 'earning', ?,
                   'Auto-synced from the Freelance tab')""", (rev,))
            sid = cur.lastrowid
        await db.execute(
            """INSERT INTO revenue_log (stream_id, period, revenue, cost) VALUES (?,?,?,0)
               ON CONFLICT(stream_id, period) DO UPDATE SET revenue=excluded.revenue""",
            (sid, _now_period(), rev))
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM income_streams WHERE id=?", (sid,))
        return dict(rows[0])
    finally:
        await db.close()


async def upsert_betting_stream(monthly_revenue: float) -> dict:
    """Mirror this-month betting profit into an income_streams row so it shows on the Overview."""
    db = await _conn()
    try:
        rows = await db.execute_fetchall(
            "SELECT id FROM income_streams WHERE kind='betting' AND name='Sports betting' LIMIT 1")
        rev = round(max(0.0, monthly_revenue), 2)
        if rows:
            await db.execute(
                "UPDATE income_streams SET monthly_revenue=?, status='earning', updated_at=datetime('now') WHERE id=?",
                (rev, rows[0]["id"]))
            sid = rows[0]["id"]
        else:
            cur = await db.execute(
                """INSERT INTO income_streams (name, kind, status, monthly_revenue, notes)
                   VALUES ('Sports betting', 'betting', 'earning', ?, 'Auto-synced from the Betting tab')""",
                (rev,))
            sid = cur.lastrowid
        await db.execute(
            """INSERT INTO revenue_log (stream_id, period, revenue, cost) VALUES (?,?,?,0)
               ON CONFLICT(stream_id, period) DO UPDATE SET revenue=excluded.revenue""",
            (sid, _now_period(), rev))
        await db.commit()
        rows = await db.execute_fetchall("SELECT * FROM income_streams WHERE id=?", (sid,))
        return dict(rows[0])
    finally:
        await db.close()
