"""One HTTP GET. Callers log the endpoint, never the query string that carries a key."""

import urllib.error
import urllib.parse
import urllib.request

TIMEOUT_SECONDS = 20
KEY_HELP = r"Add {name} to your key file in C:\Users\msell\secrets."


class SourceFailure(RuntimeError):
    """One source failed. The search still returns the other sources."""

    def __init__(self, source: str, kind: str):
        self.source = source
        self.kind = kind
        super().__init__(plain_message(source, kind))

    @property
    def text(self) -> str:
        return plain_message(self.source, self.kind)


def plain_message(source: str, kind: str) -> str:
    from leadgen.sources.records import SOURCE_LABELS

    label = SOURCE_LABELS.get(source, source)
    if kind == "rate":
        return f"{label} is rate limited."
    if kind == "timeout":
        return f"{label} timed out."
    if kind == "sam_key":
        return f"{label} is not set up. {KEY_HELP.format(name='SAM_API_KEY')}"
    if kind == "edgar_agent":
        return f"{label} is not set up. {KEY_HELP.format(name='LEADGEN_EDGAR_USER_AGENT')}"
    return f"{label} did not respond."


def fetch(
    url: str,
    params: list[tuple[str, str]],
    headers: dict[str, str],
    timeout: float = TIMEOUT_SECONDS,
) -> tuple[int, str]:
    """Return the status and body. Timeouts propagate as TimeoutError."""
    query = urllib.parse.urlencode(params)
    target = url if not query else f"{url}?{query}"
    request = urllib.request.Request(target, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status = getattr(response, "status", 200)
            return int(status), raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read() if exc.fp is not None else b""
        return int(exc.code), raw.decode("utf-8", errors="replace")
