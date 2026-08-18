from typing import Optional

from pydantic import BaseModel


class StreamIn(BaseModel):
    name: str
    kind: str = "other"
    status: str = "idea"
    monthly_revenue: float = 0
    monthly_cost: float = 0
    url: str = ""
    notes: str = ""


class StreamPatch(BaseModel):
    name: Optional[str] = None
    kind: Optional[str] = None
    status: Optional[str] = None
    monthly_revenue: Optional[float] = None
    monthly_cost: Optional[float] = None
    url: Optional[str] = None
    notes: Optional[str] = None


class GenerateIdeasIn(BaseModel):
    n: int = 6
    focus: str = ""


class IdeaPatch(BaseModel):
    status: Optional[str] = None
    validation: Optional[list] = None
    stage: Optional[str] = None
    tasks: Optional[list] = None
    mrr: Optional[float] = None


class SignupIn(BaseModel):
    email: str


class ChannelIn(BaseModel):
    name: str
    niche: str = ""
    style: str = "top-10 list"
    voice: str = "en-US-AndrewNeural"
    target_length_words: int = 220
    cadence: str = "weekly"
    notes: str = ""


class VideoIn(BaseModel):
    channel_id: int
    topic: str


class BatchIn(BaseModel):
    channel_id: int
    count: int = 0
    topics: list[str] = []
    focus: str = ""
    do_upload: bool = False
    auto_run: bool = True


class EnqueueIn(BaseModel):
    do_upload: bool = False


class BookmakerIn(BaseModel):
    name: str
    balance: float = 0
    status: str = "active"
    notes: str = ""


class BookmakerPatch(BaseModel):
    name: Optional[str] = None
    balance: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class ArbLegIn(BaseModel):
    bookmaker_id: Optional[int] = None
    selection: str = ""
    odds: float = 0
    stake: float = 0


class ArbIn(BaseModel):
    event: str
    sport: str = ""
    stake_total: float = 0
    profit_pct: float = 0
    guaranteed_profit: float = 0
    notes: str = ""
    legs: list[ArbLegIn] = []


class BetIn(BaseModel):
    bookmaker_id: Optional[int] = None
    arb_id: Optional[int] = None
    event: str = ""
    selection: str = ""
    odds: float = 0
    stake: float = 0
    status: str = "pending"


class BetPatch(BaseModel):
    status: Optional[str] = None
    stake: Optional[float] = None
    odds: Optional[float] = None
    selection: Optional[str] = None


class ScanIn(BaseModel):
    sports: list[str] = []
    regions: str = "au"
    min_profit: float = 0


class SettingsPatch(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = None
    tts_voice: Optional[str] = None
    video_resolution: Optional[str] = None
    upload_privacy: Optional[str] = None
    odds_api_key: Optional[str] = None


class ClientIn(BaseModel):
    name: str
    contact: str = ""
    email: str = ""
    url: str = ""
    notes: str = ""


class ClientPatch(BaseModel):
    name: Optional[str] = None
    contact: Optional[str] = None
    email: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None


class ProjectIn(BaseModel):
    client_id: Optional[int] = None
    name: str
    status: str = "lead"
    rate_type: str = "fixed"
    rate: float = 0
    hours_logged: float = 0
    due_date: str = ""
    notes: str = ""


class ProjectPatch(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    rate_type: Optional[str] = None
    rate: Optional[float] = None
    hours_logged: Optional[float] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None


class InvoiceIn(BaseModel):
    project_id: Optional[int] = None
    amount: float = 0
    status: str = "draft"
    due_date: str = ""
    notes: str = ""


class InvoicePatch(BaseModel):
    amount: Optional[float] = None
    status: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None


class GoalIn(BaseModel):
    period: str
    target_revenue: float = 0
    target_net: float = 0


class SharedCostIn(BaseModel):
    name: str
    amount: float = 0
    category: str = "other"
    url: str = ""
    notes: str = ""


class SharedCostPatch(BaseModel):
    name: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None
    active: Optional[int] = None
