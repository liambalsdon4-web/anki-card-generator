# 💰 Income Hub

A local dashboard for managing multiple income streams, with two working modules for actually *creating* new ones:

- **Overview** — track every income stream (type, status, MRR, cost), a revenue trend chart, and net profit across everything.
- **🚀 Micro-SaaS Launchpad** — generate niche SaaS ideas with AI, auto-scored on demand · willingness-to-pay · competition · build-effort · founder-fit. Work a validation checklist, then promote the winner into a tracked income stream.
- **🎬 Faceless YouTube** — a full pipeline: AI writes the script/title/description/tags/thumbnail prompt → **edge-tts** voices it → **Pillow** caption slides → **ffmpeg** renders an MP4 → optional **YouTube** upload. Videos move across a kanban board (idea → scripted → voiced → rendered → uploaded → published).

Stack: FastAPI + aiosqlite + vanilla-JS SPA, pywebview desktop. Port **8007**.

## Run

```bash
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt   # Windows
python main.py            # desktop window
python main.py --web      # browser
python main.py --server   # headless at http://127.0.0.1:8007
```

No system installs needed — **ffmpeg is bundled** via `imageio-ffmpeg`, and **edge-tts** voiceover is free with no key.

## AI setup (required for idea + script generation)

Uses **Google Gemini** (free tier). Get a key at <https://aistudio.google.com> → *Get API key*, then either:
- set a `GEMINI_API_KEY` environment variable, or
- paste it in **Settings** (takes precedence, stored in `data/config.json`).

> ⚠️ The `GEMINI_API_KEY` currently on this PC is **invalid/expired** (Google returns `Unauthenticated`). Add a fresh key in Settings before using the Micro-SaaS or script generators. Everything else (income tracking, voiceover, slides, video render) works without a key.

## YouTube auto-upload (optional)

The render pipeline works without this. To enable one-click upload:
1. In Google Cloud, enable the **YouTube Data API v3**.
2. Create an **OAuth client ID** of type **Desktop app**, download the JSON.
3. Save it as `data/client_secret.json`. The first upload opens a browser consent once (token cached to `data/token.json`).

## How the video pipeline works

```
Gemini  →  script + title + description + tags + thumbnail prompt
edge-tts →  one mp3 per segment (free, no key)
Pillow   →  one caption slide per segment (gradient bg + heading + text)
ffmpeg   →  loop each slide for its audio length, concat → final.mp4   (bundled binary)
YouTube  →  optional upload via Data API (your OAuth)
```

Renders land in `data/renders/video_<id>/final.mp4` and are viewable/downloadable in the app.

## Structure

```
config/settings.py     port 8007, Gemini key/model, TTS voice, resolution
core/ai.py             Gemini client (ideas + scripts + topics)
core/scoring.py        micro-SaaS idea scoring
core/tts.py            edge-tts voiceover        core/slides.py   Pillow slides
core/render.py         ffmpeg assembly           core/youtube_upload.py  Data API (staged)
modules/saas.py        idea gen → score → promote
modules/youtube.py     script → voice → render → upload orchestration
db/…  api/…  static/…  main.py
```

Verify the render pipeline any time (no key needed): `python scripts/check_render.py`

## Honest note

These are *asset-building* income methods (compounding, no gatekeeper who can ban you) — the opposite of arbitrage. None are instant: micro-SaaS realistically takes months to meaningful MRR; faceless YouTube has a low success rate and a long monetization ramp. The hub is the cockpit; the work is still real.
