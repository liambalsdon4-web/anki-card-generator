"""Weighted scoring for micro-SaaS ideas.

Mirrors the weighted-vote pattern in crypto_hype_finder/core/hype_scorer.py.
competition and build_effort are inverted (lower is better).
"""
from __future__ import annotations

WEIGHTS = {
    "demand": 0.28,
    "willingness_to_pay": 0.24,
    "competition": 0.18,      # inverted
    "build_effort": 0.15,     # inverted
    "founder_fit": 0.15,
}


def score_idea(idea: dict) -> float:
    def g(k):
        try:
            return max(0.0, min(100.0, float(idea.get(k, 0) or 0)))
        except (TypeError, ValueError):
            return 0.0
    parts = {
        "demand": g("demand"),
        "willingness_to_pay": g("willingness_to_pay"),
        "competition": 100.0 - g("competition"),
        "build_effort": 100.0 - g("build_effort"),
        "founder_fit": g("founder_fit"),
    }
    return round(sum(parts[k] * w for k, w in WEIGHTS.items()), 1)


DEFAULT_CHECKLIST = [
    "10+ people describe this exact pain unprompted (Reddit/forums/X)",
    "Found 3+ competitors charging money (validates willingness to pay)",
    "Can reach the buyer somewhere specific (subreddit, Slack, directory)",
    "MVP scope fits in <3 weeks of solo build",
    "One clear paid trigger (the 'I'd pay for this' moment)",
    "Landing page + waitlist gets 20 signups before building",
]


def default_validation() -> list[dict]:
    return [{"item": item, "done": False} for item in DEFAULT_CHECKLIST]
