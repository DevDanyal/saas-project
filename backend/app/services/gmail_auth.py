import secrets

from google_auth_oauthlib.flow import Flow as GoogleFlow
from google.oauth2.credentials import Credentials

from app.core.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"

_flow_store: dict[str, GoogleFlow] = {}


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
    if state is not None:
        flow.state = state
    return flow


def build_authorization_url(state: str) -> str:
    flow = build_flow(state=state)
    return flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )[0]


def begin_authorization() -> tuple[str, str]:
    state = secrets.token_urlsafe(16)
    flow = build_flow(state=state)
    url = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )[0]
    _flow_store[state] = flow
    return state, url


def exchange_code(code: str, state: str) -> Credentials:
    flow = _flow_store.pop(state, None)
    if flow is None:
        flow = build_flow()
    flow.fetch_token(code=code)
    return flow.credentials


def build_gmail_service(credentials: Credentials):
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


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