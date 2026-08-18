"""The Odds API v4 client + arbitrage detection (free key from the-odds-api.com).

We only request the h2h market in the chosen region (1 API credit per sport per
scan). For each event we take the best price for every outcome across all
bookmakers; if the implied probabilities sum to under 100%, it's an arb.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from config.settings import get_odds_api_key

API = "https://api.the-odds-api.com/v4"


class OddsError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(get_odds_api_key())


def _get(path: str, params: dict) -> tuple:
    key = get_odds_api_key()
    if not key:
        raise OddsError("No Odds API key set. Add one in Settings (free at the-odds-api.com).")
    url = f"{API}{path}?{urllib.parse.urlencode({**params, 'apiKey': key})}"
    req = urllib.request.Request(url, headers={"User-Agent": "IncomeHub/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
            quota = {"remaining": r.headers.get("x-requests-remaining"),
                     "used": r.headers.get("x-requests-used")}
            return data, quota
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        if e.code == 401:
            raise OddsError("Odds API rejected the key. Check it in Settings.")
        if e.code == 429:
            raise OddsError("Odds API monthly quota exhausted for this key.")
        raise OddsError(f"Odds API error {e.code}: {body[:160]}")
    except urllib.error.URLError as e:
        raise OddsError(f"Could not reach the Odds API: {e.reason}")


def list_sports() -> list[dict]:
    data, _ = _get("/sports", {"all": "false"})
    return [{"key": s["key"], "title": s["title"], "group": s.get("group", "")}
            for s in data if s.get("active")]


def _arbs_from_events(events: list[dict], min_profit: float) -> list[dict]:
    out = []
    for ev in events:
        best: dict[str, tuple] = {}  # outcome name -> (price, bookmaker title)
        for bk in ev.get("bookmakers", []):
            for mk in bk.get("markets", []):
                if mk.get("key") != "h2h":
                    continue
                for oc in mk.get("outcomes", []):
                    name, price = oc.get("name"), oc.get("price")
                    if name and price and (name not in best or price > best[name][0]):
                        best[name] = (price, bk.get("title", "?"))
        if len(best) < 2:
            continue
        s = sum(1 / p for p, _ in best.values())
        if s <= 0 or s >= 1:
            continue
        profit_pct = (1 / s - 1) * 100
        if profit_pct < min_profit:
            continue
        home, away = ev.get("home_team"), ev.get("away_team")
        name = f"{home} vs {away}" if home and away else ev.get("sport_title", "Event")
        out.append({
            "event": name,
            "sport": ev.get("sport_title") or ev.get("sport_key", ""),
            "commence_time": ev.get("commence_time"),
            "profit_pct": round(profit_pct, 2),
            "book_pct": round(s * 100, 2),
            "legs": [{"selection": nm, "bookmaker": book, "odds": round(price, 2)}
                     for nm, (price, book) in best.items()],
        })
    return out


def scan(sports: list[str], regions: str = "au", min_profit: float = 0.0) -> dict:
    all_arbs: list[dict] = []
    quota: dict = {}
    for sk in sports:
        data, q = _get(f"/sports/{sk}/odds",
                       {"regions": regions, "markets": "h2h", "oddsFormat": "decimal"})
        quota = q or quota
        all_arbs.extend(_arbs_from_events(data, min_profit))
    all_arbs.sort(key=lambda a: a["profit_pct"], reverse=True)
    return {"arbs": all_arbs, "quota": quota}
