"""YouTube upload via the Data API v3 — staged/optional.

Requires the user to enable the YouTube Data API, download an OAuth client
secret to data/client_secret.json, and authorise once (token cached to
data/token.json). Until then this raises a clear, actionable error. No secrets
are bundled and nothing uploads automatically.
"""
from __future__ import annotations

from pathlib import Path

from config.settings import DATA_DIR

CLIENT_SECRET = DATA_DIR / "client_secret.json"
TOKEN_PATH = DATA_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def is_configured() -> bool:
    return CLIENT_SECRET.exists()


def _get_service():
    if not CLIENT_SECRET.exists():
        raise RuntimeError(
            "YouTube upload not configured. Enable the YouTube Data API v3, create an "
            "OAuth desktop client, and save it to data/client_secret.json. See README."
        )
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as e:
        raise RuntimeError("Install google-api-python-client and google-auth-oauthlib.") from e

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def upload(video_path: str, title: str, description: str, tags: list[str],
           privacy: str = "private") -> str:
    """Upload a video and return its YouTube video ID. Runs a blocking OAuth flow
    the first time — call from a thread."""
    from googleapiclient.http import MediaFileUpload

    service = _get_service()
    body = {
        "snippet": {"title": title[:100], "description": description,
                    "tags": tags[:30], "categoryId": "22"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    return response["id"]
