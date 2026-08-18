"""Gemini client — mirrors study_app/core/ai.py (lazy SDK import, JSON mode).

Two generators used by the modules:
  - generate_saas_ideas : niche micro-SaaS ideas with scoring sub-metrics
  - generate_video_script : faceless-YouTube script + title/description/tags/thumbnail
"""
from __future__ import annotations

import json

from config.settings import get_api_key, get_model

genai = None
gexc = None


class AIError(RuntimeError):
    pass


def _ensure_sdk() -> None:
    global genai, gexc
    if genai is not None:
        return
    try:
        import google.generativeai as _genai
    except ImportError:
        raise AIError("google-generativeai not installed. Run: pip install google-generativeai")
    genai = _genai
    try:
        from google.api_core import exceptions as _gexc
        gexc = _gexc
    except ImportError:
        gexc = None


def _configure() -> None:
    _ensure_sdk()
    key = get_api_key()
    if not key:
        raise AIError("No Gemini API key set. Add one in Settings (free at https://aistudio.google.com).")
    genai.configure(api_key=key)


def _call(model, contents):
    try:
        return model.generate_content(contents)
    except Exception as e:
        if gexc is not None and isinstance(e, gexc.ResourceExhausted):
            raise AIError("Gemini quota/rate limit reached. Wait a moment and retry (free tier is limited).")
        if gexc is not None and isinstance(e, (gexc.PermissionDenied, gexc.Unauthenticated)):
            raise AIError("Gemini rejected the API key. Check it in Settings.")
        raise AIError(f"AI request failed: {e}")


def _json_call(system: str, prompt: str):
    _configure()
    model = genai.GenerativeModel(
        get_model(), system_instruction=system,
        generation_config={"response_mime_type": "application/json"},
    )
    resp = _call(model, prompt)
    raw = (resp.text or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = min((i for i in (raw.find("["), raw.find("{")) if i != -1), default=-1)
        end = max(raw.rfind("]"), raw.rfind("}"))
        if start != -1 and end != -1:
            return json.loads(raw[start:end + 1])
        raise AIError("Gemini returned unparseable output.")


# ── Micro-SaaS idea generation ────────────────────────────────────────────────

_SAAS_SYSTEM = (
    "You are a pragmatic indie-hacker advisor. You generate realistic micro-SaaS ideas "
    "a solo technical founder could build in weeks and charge for. Favour B2B, vertical "
    "workflow tools, dev tools, and AI-workflow niches with clear willingness to pay. "
    "Be honest about competition. Output strict JSON only."
)

_SAAS_PROMPT = """Generate {n} distinct micro-SaaS ideas{focus_clause}.

The founder is a solo developer comfortable with Python/FastAPI, JS, scrapers, and AI APIs.
They want recurring revenue, low churn, and something buildable solo.

Return a JSON array. Each item:
{{
  "name": "short product name",
  "problem": "the painful problem, one sentence",
  "target_user": "specific buyer persona",
  "solution": "what the tool does, one or two sentences",
  "monetization": "pricing model, e.g. $29/mo per seat",
  "est_mrr_range": "realistic 12-month MRR band, e.g. $2k-8k",
  "tags": "comma,separated,keywords",
  "demand": 0-100,               // strength of real, searchable demand
  "competition": 0-100,          // how crowded (higher = MORE competition)
  "willingness_to_pay": 0-100,   // how readily this buyer pays for tools
  "build_effort": 0-100,         // effort to an MVP (higher = MORE effort)
  "founder_fit": 0-100           // fit for a solo Python/JS + AI dev
}}
Only output the JSON array."""


def generate_saas_ideas(n: int = 6, focus: str = "") -> list[dict]:
    focus_clause = f" focused on: {focus}" if focus.strip() else ""
    data = _json_call(_SAAS_SYSTEM, _SAAS_PROMPT.format(n=n, focus_clause=focus_clause))
    if isinstance(data, dict):
        data = data.get("ideas") or data.get("items") or [data]
    return [d for d in data if isinstance(d, dict) and d.get("name")]


# ── Faceless YouTube script generation ────────────────────────────────────────

_SCRIPT_SYSTEM = (
    "You write tight, retention-optimised scripts for faceless YouTube videos "
    "(voiceover over simple visuals). Hook hard in the first line, keep sentences "
    "short and speakable, no stage directions or emojis in narration. Output strict JSON."
)

_SCRIPT_PROMPT = """Write a faceless YouTube video for the channel "{channel}" (niche: {niche}, style: {style}).
Topic: "{topic}"
Target narration length: about {words} words total, split into 5-9 segments.

Return JSON:
{{
  "title": "clickable, <70 chars, no clickbait lies",
  "description": "2-3 sentence description with a call to subscribe",
  "tags": "comma,separated,youtube,tags",
  "thumbnail_prompt": "a vivid text-to-image prompt for the thumbnail",
  "segments": [
    {{"heading": "on-screen caption, <8 words", "narration": "spoken lines for this segment"}}
  ]
}}
Only output the JSON object."""


def generate_video_script(channel: str, niche: str, style: str, topic: str, words: int = 220) -> dict:
    data = _json_call(
        _SCRIPT_SYSTEM,
        _SCRIPT_PROMPT.format(channel=channel, niche=niche, style=style, topic=topic, words=words),
    )
    if not isinstance(data, dict) or not data.get("segments"):
        raise AIError("Gemini did not return a valid script.")
    return data


# ── Micro-SaaS build-out generators ───────────────────────────────────────────

def _idea_brief(idea: dict) -> str:
    return (f'Product: {idea.get("name","")}\nProblem: {idea.get("problem","")}\n'
            f'Target user: {idea.get("target_user","")}\nSolution: {idea.get("solution","")}\n'
            f'Monetization: {idea.get("monetization","")}')


def generate_build_kit(idea: dict) -> dict:
    system = ("You are a senior technical co-founder who ships lean MVPs solo. "
              "Be concrete and buildable for a Python/FastAPI + JS developer. Output strict JSON.")
    prompt = f"""Produce an MVP build kit for this micro-SaaS.
{_idea_brief(idea)}

Return JSON:
{{
  "mvp_scope": "one tight paragraph: the smallest version worth charging for",
  "stack": ["concrete tools/libraries"],
  "features": [{{"name":"feature","detail":"what it does, one line"}}],
  "data_model": [{{"entity":"Table","fields":"comma-separated columns"}}],
  "pricing": [{{"tier":"name","price":"$X/mo","features":"what's included"}}],
  "roadmap": [{{"week":"Week 1","goal":"milestone","tasks":["task","task"]}}]
}}
5-7 features, 3-5 tables, 2-3 pricing tiers, a 3-4 week roadmap. Only the JSON object."""
    data = _json_call(system, prompt)
    if not isinstance(data, dict) or not data.get("features"):
        raise AIError("Gemini did not return a valid build kit.")
    return data


def generate_research(idea: dict) -> dict:
    system = ("You are a pragmatic market analyst for indie SaaS. Be honest and specific, "
              "name real competitor types and realistic pricing. Output strict JSON.")
    prompt = f"""Do a fast market-validation research pass for this micro-SaaS.
{_idea_brief(idea)}

Return JSON:
{{
  "verdict": "one-line go / caution / no-go call with the key reason",
  "competitors": [{{"name":"real or category","angle":"how they position","pricing":"approx"}}],
  "demand_signals": ["specific places/behaviours showing this demand"],
  "keywords": ["buyer-intent search phrases"],
  "pricing_benchmark": "what comparable tools charge and the sweet spot",
  "risks": ["the honest risks / why it might fail"],
  "differentiation": "the sharpest wedge to win a beachhead"
}}
3-5 competitors, 4-6 demand signals, 5-8 keywords, 3-4 risks. Only the JSON object."""
    data = _json_call(system, prompt)
    if not isinstance(data, dict) or not data.get("verdict"):
        raise AIError("Gemini did not return valid research.")
    return data


def generate_landing_copy(idea: dict) -> dict:
    system = ("You write high-converting landing-page copy for developer/B2B SaaS. "
              "Punchy, concrete, benefit-led, no fluff or emojis. Output strict JSON.")
    prompt = f"""Write landing-page copy for a waitlist page for this micro-SaaS.
{_idea_brief(idea)}

Return JSON:
{{
  "headline": "big promise, <9 words",
  "subhead": "one sentence expanding the promise",
  "cta": "waitlist button text, 2-4 words",
  "features": [{{"title":"benefit","body":"one concrete sentence"}}],
  "pricing": [{{"tier":"name","price":"$X/mo","features":["line","line"],"highlight":true}}],
  "faq": [{{"q":"question","a":"answer"}}],
  "footer_note": "one reassuring line (e.g. no spam, early-bird pricing)"
}}
3-4 features, 2-3 pricing tiers (mark one highlight:true), 3-4 FAQ. Only the JSON object."""
    data = _json_call(system, prompt)
    if not isinstance(data, dict) or not data.get("headline"):
        raise AIError("Gemini did not return valid landing copy.")
    return data


def generate_topics(channel: str, niche: str, style: str, n: int = 8) -> list[str]:
    system = "You are a YouTube growth strategist. Output strict JSON array of strings."
    prompt = (f'Give {n} high-CTR video topics for a faceless "{niche}" channel '
              f'named "{channel}" in the "{style}" format. Return a JSON array of title-style strings only.')
    data = _json_call(system, prompt)
    if isinstance(data, dict):
        data = data.get("topics") or data.get("items") or []
    return [str(t) for t in data if str(t).strip()][:n]
