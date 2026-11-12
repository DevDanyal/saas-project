import base64

from app.services import gmail_sync
from app.services.email_text import clean_email_body, html_to_text


def _part(mime: str, value: str) -> dict:
    data = base64.urlsafe_b64encode(value.encode()).decode()
    return {"mimeType": mime, "body": {"data": data}}


def test_clean_email_body_removes_tracking_urls():
    raw = (
        "Canva\n"
        "We have receipts\n\n"
        "See our offer ( https://click.engage.example/abc ) today.\n"
        "View online <https://click.engage.example/def>\n"
        "https://click.engage.example/ghi\n"
        "Unsubscribe\n"
    )
    cleaned = clean_email_body(raw)
    assert "https://" not in cleaned
    assert "Canva" in cleaned
    assert "We have receipts" in cleaned
    assert "Unsubscribe" in cleaned
    assert "\n\n\n" not in cleaned


def test_html_to_text_skips_scripts_and_styles():
    markup = (
        "<html><head><style>.a{color:red}</style></head>"
        "<body><p>Hello &amp; welcome</p><script>alert(1)</script>"
        "<p>Second line</p></body></html>"
    )
    text = html_to_text(markup)
    assert "Hello & welcome" in text
    assert "Second line" in text
    assert "alert" not in text
    assert "color:red" not in text


def test_extract_text_prefers_plain_over_html():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            _part("text/plain", "Plain body ( https://track.example/x )"),
            _part("text/html", "<p>HTML body</p>"),
        ],
    }
    text = gmail_sync._extract_text(payload)
    assert "Plain body" in text
    assert "https://" not in text


def test_extract_text_falls_back_to_html():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            _part(
                "text/html",
                "<html><body><p>Weekly offer</p><p>Shop now</p></body></html>",
            ),
        ],
    }
    text = gmail_sync._extract_text(payload)
    assert "Weekly offer" in text
    assert "Shop now" in text
