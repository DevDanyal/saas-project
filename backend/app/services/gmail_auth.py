import base64
import hashlib
import hmac
import json
import secrets
import time

from google_auth_oauthlib.flow import Flow as GoogleFlow
from google.oauth2.credentials import Credentials

from app.core.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
]

READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"

STATE_MAX_AGE = 600  # 10 minutes


def _state_secret() -> bytes:
    secret = settings.session_secret or settings.encryption_key
    if not secret:
        raise RuntimeError("SESSION_SECRET (or ENCRYPTION_KEY) must be configured")
    return secret.encode()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_oauth_state() -> str:
    """Stateless, signed OAuth state token (works across restarts/replicas)."""
    payload = {
        "nonce": secrets.token_urlsafe(16),
        "exp": int(time.time()) + STATE_MAX_AGE,
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(_state_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_oauth_state(state: str | None) -> bool:
    if not state or "." not in state:
        return False
    try:
        body, sig = state.rsplit(".", 1)
        expected = hmac.new(
            _state_secret(), body.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        payload = json.loads(_b64decode(body))
        return int(payload.get("exp", 0)) >= int(time.time())
    except (ValueError, TypeError, KeyError):
        return False


def scope_allows(scope: str | None, needle: str) -> bool:
    """Whether a comma/space separated granted-scope string includes `needle`."""
    if not scope:
        return False
    parts = {p.strip() for p in scope.replace(" ", ",").split(",") if p.strip()}
    return needle in parts or "https://mail.google.com/" in parts


def build_flow(state: str | None = None) -> GoogleFlow:
    flow = GoogleFlow.from_client_config(
        {
            "installed": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_redirect_uri],
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = settings.google_redirect_uri
    flow.autogenerate_code_verifier = False
    if state is not None:
        flow.state = state
    return flow


def build_authorization_url(state: str) -> str:
    flow = build_flow(state=state)
    return flow.authorization_url(
        state=state,
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )[0]


def begin_authorization() -> tuple[str, str]:
    state = create_oauth_state()
    flow = build_flow(state=state)
    url = flow.authorization_url(
        state=state,
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )[0]
    return state, url


def exchange_code(code: str, state: str) -> Credentials:
    if not verify_oauth_state(state):
        raise ValueError("Invalid or expired OAuth state")
    flow = build_flow()
    flow.fetch_token(code=code)
    return flow.credentials


def build_gmail_service(credentials: Credentials):
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def build_calendar_service(credentials: Credentials):
    from googleapiclient.discovery import build

    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def get_profile_email(credentials: Credentials) -> str | None:
    """Resolve the connected account's email via the Gmail profile endpoint.

    Avoids relying on an id_token (we only request gmail.readonly, so no
    openid/email scopes are granted).
    """
    try:
        service = build_gmail_service(credentials)
        profile = service.users().getProfile(userId="me").execute()
        return profile.get("emailAddress")
    except Exception:
        return None