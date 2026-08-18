"""Unit-test the arbitrage detection against a synthetic Odds-API payload
(no API key / network needed)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import odds

# One real arb (2.10 + 2.05 -> 96.4% book margin) and one non-arb (1.80 + 1.90).
events = [
    {"sport_title": "AFL", "home_team": "Cats", "away_team": "Pies",
     "commence_time": "2026-08-20T09:00:00Z", "bookmakers": [
        {"title": "Sportsbet", "markets": [{"key": "h2h", "outcomes": [
            {"name": "Cats", "price": 2.10}, {"name": "Pies", "price": 1.75}]}]},
        {"title": "Betfair", "markets": [{"key": "h2h", "outcomes": [
            {"name": "Cats", "price": 1.95}, {"name": "Pies", "price": 2.05}]}]},
     ]},
    {"sport_title": "NRL", "home_team": "Storm", "away_team": "Broncos",
     "commence_time": "2026-08-21T09:00:00Z", "bookmakers": [
        {"title": "TAB", "markets": [{"key": "h2h", "outcomes": [
            {"name": "Storm", "price": 1.80}, {"name": "Broncos", "price": 1.90}]}]},
     ]},
]

arbs = odds._arbs_from_events(events, min_profit=0.0)
print(f"found {len(arbs)} arb(s):")
for a in arbs:
    print(f"  {a['event']}  +{a['profit_pct']}%  (book {a['book_pct']}%)")
    for l in a["legs"]:
        print(f"    {l['selection']}: @{l['odds']} on {l['bookmaker']}")

ok = (len(arbs) == 1 and arbs[0]["event"] == "Cats vs Pies"
      and abs(arbs[0]["profit_pct"] - 3.73) < 0.1
      and {l["bookmaker"] for l in arbs[0]["legs"]} == {"Sportsbet", "Betfair"})
print("\nRESULT:", "PASS" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
