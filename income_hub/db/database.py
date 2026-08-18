import aiosqlite

from config.settings import DB_PATH

SCHEMA = """
-- ── Hub: income streams ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS income_streams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'other',   -- micro_saas | youtube | trading | betting | affiliate | other
    status TEXT NOT NULL DEFAULT 'idea',  -- idea | building | launched | earning | paused
    monthly_revenue REAL DEFAULT 0,
    monthly_cost REAL DEFAULT 0,
    url TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    ref_type TEXT DEFAULT '',             -- links to a module record, e.g. 'saas_idea'
    ref_id INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS revenue_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stream_id INTEGER REFERENCES income_streams(id) ON DELETE CASCADE,
    period TEXT NOT NULL,                 -- 'YYYY-MM'
    revenue REAL DEFAULT 0,
    cost REAL DEFAULT 0,
    note TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(stream_id, period)
);

-- ── Micro-SaaS launchpad ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saas_ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    problem TEXT DEFAULT '',
    target_user TEXT DEFAULT '',
    solution TEXT DEFAULT '',
    monetization TEXT DEFAULT '',
    demand INTEGER DEFAULT 0,             -- 0-100 sub-scores from AI
    competition INTEGER DEFAULT 0,
    willingness_to_pay INTEGER DEFAULT 0,
    build_effort INTEGER DEFAULT 0,
    founder_fit INTEGER DEFAULT 0,
    score REAL DEFAULT 0,                 -- computed weighted score
    est_mrr_range TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    validation_json TEXT DEFAULT '[]',    -- checklist [{item, done}]
    status TEXT DEFAULT 'new',            -- new | shortlisted | building | dropped
    stage TEXT DEFAULT 'idea',            -- idea | validating | building | launched | earning
    build_kit_json TEXT DEFAULT '',       -- AI MVP plan
    research_json TEXT DEFAULT '',         -- AI market research
    landing_html TEXT DEFAULT '',          -- generated landing page
    tasks_json TEXT DEFAULT '[]',          -- build tasks [{text, done}]
    mrr REAL DEFAULT 0,                    -- tracked MRR once earning
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS saas_signups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idea_id INTEGER REFERENCES saas_ideas(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- ── Faceless YouTube ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS yt_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    niche TEXT DEFAULT '',
    style TEXT DEFAULT 'top-10 list',
    voice TEXT DEFAULT 'en-US-AndrewNeural',
    target_length_words INTEGER DEFAULT 220,
    cadence TEXT DEFAULT 'weekly',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS yt_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER REFERENCES yt_channels(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'idea',   -- idea | scripted | voiced | rendered | uploaded | published
    title TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    thumbnail_prompt TEXT DEFAULT '',
    script_json TEXT DEFAULT '[]',        -- [{heading, narration}]
    audio_path TEXT DEFAULT '',
    video_path TEXT DEFAULT '',
    youtube_id TEXT DEFAULT '',
    views INTEGER DEFAULT 0,
    error TEXT DEFAULT '',
    queue_status TEXT DEFAULT '',          -- '' | queued | running | done | failed
    queue_msg TEXT DEFAULT '',             -- current pipeline step / result note
    queue_upload INTEGER DEFAULT 0,        -- 1 = also upload to YouTube when the queue reaches it
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- ── Freelance / web-dev tracker ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS fl_clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact TEXT DEFAULT '',
    email TEXT DEFAULT '',
    url TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fl_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES fl_clients(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'lead',   -- lead | active | done | cancelled
    rate_type TEXT NOT NULL DEFAULT 'fixed', -- fixed | hourly
    rate REAL DEFAULT 0,                    -- fixed price OR hourly rate
    hours_logged REAL DEFAULT 0,
    due_date TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fl_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES fl_projects(id) ON DELETE CASCADE,
    amount REAL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft',  -- draft | sent | paid | overdue
    due_date TEXT DEFAULT '',
    paid_at TEXT,
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

-- ── Income goals ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS income_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT NOT NULL UNIQUE,           -- 'YYYY-MM'
    target_revenue REAL DEFAULT 0,
    target_net REAL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- ── Shared / recurring costs ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shared_costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    amount REAL DEFAULT 0,                 -- per month
    category TEXT DEFAULT 'other',         -- hosting | domain | api | tools | other
    url TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- ── Sports betting (arbitrage) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS bookmakers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    balance REAL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',   -- active | limited | gubbed | banned | closed
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS arbs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event TEXT NOT NULL,
    sport TEXT DEFAULT '',
    stake_total REAL DEFAULT 0,
    profit_pct REAL DEFAULT 0,               -- expected ROI at placement
    guaranteed_profit REAL DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arb_id INTEGER REFERENCES arbs(id) ON DELETE CASCADE,          -- NULL = standalone bet
    bookmaker_id INTEGER REFERENCES bookmakers(id) ON DELETE SET NULL,
    event TEXT DEFAULT '',
    selection TEXT DEFAULT '',
    odds REAL DEFAULT 0,
    stake REAL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | won | lost | void
    profit REAL DEFAULT 0,                    -- realised profit once settled
    created_at TEXT DEFAULT (datetime('now')),
    settled_at TEXT
);
"""

# Columns added after the initial release — applied to existing DBs on startup.
_MIGRATIONS = [
    ("yt_videos", "queue_status", "TEXT DEFAULT ''"),
    ("yt_videos", "queue_msg", "TEXT DEFAULT ''"),
    ("yt_videos", "queue_upload", "INTEGER DEFAULT 0"),
    ("saas_ideas", "stage", "TEXT DEFAULT 'idea'"),
    ("saas_ideas", "build_kit_json", "TEXT DEFAULT ''"),
    ("saas_ideas", "research_json", "TEXT DEFAULT ''"),
    ("saas_ideas", "landing_html", "TEXT DEFAULT ''"),
    ("saas_ideas", "tasks_json", "TEXT DEFAULT '[]'"),
    ("saas_ideas", "mrr", "REAL DEFAULT 0"),
]


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        for table, col, ddl in _MIGRATIONS:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
            except Exception:
                pass  # column already exists
        await db.commit()
