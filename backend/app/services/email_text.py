import html as html_lib
import re
from html.parser import HTMLParser

_BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "div",
    "dl",
    "dt",
    "dd",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}
_SKIP_TAGS = {"head", "noscript", "script", "style", "title"}

_PAREN_URL_RE = re.compile(r"\(\s*https?://[^)\s]*\s*\)", re.IGNORECASE)
_ANGLE_URL_RE = re.compile(r"<\s*https?://[^>\s]*\s*>", re.IGNORECASE)
_BARE_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_HSPACE_RE = re.compile(r"[ \t\f\v]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_EMPTY_LINE_JUNK_RE = re.compile(r"^[\s,.;:!?|•·*#\-_=]+$")


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def html_to_text(markup: str) -> str:
    """Convert HTML email markup into readable plain text."""
    if not markup:
        return ""
    parser = _HTMLTextExtractor()
    try:
        parser.feed(markup)
        parser.close()
    except Exception:
        return markup
    return parser.get_text()


def clean_email_body(text: str, limit: int = 20000) -> str:
    """Strip tracking URLs and layout noise from an email body.

    Works on both plain-text and HTML-derived bodies, so it is safe to apply
    to text that was already cleaned.
    """
    if not text:
        return ""

    value = html_lib.unescape(text.replace("\r\n", "\n").replace("\r", "\n"))
    value = _PAREN_URL_RE.sub(" ", value)
    value = _ANGLE_URL_RE.sub(" ", value)
    value = _BARE_URL_RE.sub(" ", value)

    lines: list[str] = []
    for raw_line in value.split("\n"):
        line = _HSPACE_RE.sub(" ", raw_line).strip()
        if line and _EMPTY_LINE_JUNK_RE.match(line):
            continue
        lines.append(line)

    cleaned = "\n".join(lines)
    cleaned = _MULTI_NEWLINE_RE.sub("\n\n", cleaned).strip()
    if limit and len(cleaned) > limit:
        cleaned = cleaned[:limit].rstrip() + "\n…"
    return cleaned
