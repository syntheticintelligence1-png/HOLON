"""HTTP for the historical fetch: per-host pacing, retries with backoff, JSON-RPC (single and batch).

Nothing here enters an output: retries, timing and the pacing state only decide when a request is sent. A
source is identified in every output by its host name only (`host`), never by a URL, so a key carried in
ETH_RPC_URL (path or query) or in ETHERSCAN_API_KEY never reaches a file. Error messages are scrubbed of
every secret value before they are raised (`scrub`).
"""
from __future__ import annotations

import http.client
import json
import os
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

SECRET_ENV = ("ETH_RPC_URL", "ETHERSCAN_API_KEY")
USER_AGENT = "holon-historical/1"
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 524, 525}


class SourceError(RuntimeError):
    """A source answered, but not with the data: a refusal (archive token, range limit), a null result or a
    malformed body. The caller tries the next source; retrying the same one would not help."""


class TransientError(RuntimeError):
    """The request failed in a way that retrying may cure (rate limit, 5xx, timeout) and the retries ran out."""


def secrets() -> list[str]:
    out = []
    for k in SECRET_ENV:
        v = os.environ.get(k)
        if v:
            out.append(v)
            if k == "ETH_RPC_URL":
                p = urllib.parse.urlsplit(v)
                parts = [p.path.strip("/"), p.query, p.username or "", p.password or ""]
                parts += p.path.split("/") + [x.split("=", 1)[-1] for x in p.query.split("&")]
                out += [s for s in parts if len(s) >= 8]
    return sorted(set(out), key=len, reverse=True)


def scrub(text: str) -> str:
    for s in secrets():
        text = text.replace(s, "<secret>")
    return text


def host(url: str) -> str:
    """The host name of a URL: what outputs record as the source."""
    return (urllib.parse.urlsplit(url).hostname or "?").lower()


class Pacer:
    """Per-host spacing between requests. The interval grows on a rate limit and shrinks slowly on success."""

    def __init__(self, interval: float = 0.05, floor: float = 0.02, ceiling: float = 2.0, pause_on_limit: float = 10.0):
        self.lock = threading.Lock()
        self.interval, self.floor, self.ceiling = interval, floor, ceiling
        self.pause_on_limit = pause_on_limit
        self.next_at = 0.0
        self.pause_until = 0.0

    def wait(self) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                start = max(self.next_at, self.pause_until)
                if now >= start:
                    self.next_at = now + self.interval
                    return
                delay = start - now
            time.sleep(min(delay, 1.0))

    def ok(self) -> None:
        with self.lock:
            self.interval = max(self.floor, self.interval * 0.85)

    def limited(self, retry_after: float | None = None) -> None:
        with self.lock:
            self.interval = min(self.ceiling, self.interval * 1.5 + 0.02)
            pause = min(60.0, retry_after) if retry_after else min(self.pause_on_limit, max(1.0, self.interval * 5))
            self.pause_until = max(self.pause_until, time.monotonic() + pause)


class Http:
    """A small client: one Pacer per host, bounded retries with exponential backoff and jitter."""

    def __init__(self, retries: int = 7, timeout: float = 90.0, floors: dict | None = None):
        self.retries, self.timeout = retries, timeout
        self.pacers: dict[str, Pacer] = {}
        self.floors = floors or {}
        self.lock = threading.Lock()
        self.calls: dict[str, int] = {}

    def pacer(self, h: str) -> Pacer:
        with self.lock:
            if h not in self.pacers:
                f = self.floors.get(h)
                self.pacers[h] = Pacer(f, f, max(2.0, 20 * f), pause_on_limit=60.0) if f else Pacer()
            return self.pacers[h]

    def request(self, url: str, body: bytes | None = None, headers: dict | None = None) -> tuple[int, bytes]:
        """(status, body) of the first non-retryable answer; raises TransientError when retries run out."""
        h = host(url)
        pacer = self.pacer(h)
        hdrs = {"user-agent": USER_AGENT, "accept": "application/json", **(headers or {})}
        last = ""
        for attempt in range(self.retries + 1):
            pacer.wait()
            with self.lock:
                self.calls[h] = self.calls.get(h, 0) + 1
            req = urllib.request.Request(url, data=body, headers=hdrs, method="POST" if body is not None else "GET")
            retry_after = None
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = r.read()
                pacer.ok()
                return r.status, data
            except urllib.error.HTTPError as e:
                try:
                    data = e.read()
                except Exception:  # noqa: BLE001 - a body that cannot be read is an empty body
                    data = b""
                if e.code not in RETRY_STATUS:
                    pacer.ok()
                    return e.code, data
                ra = e.headers.get("retry-after") if e.headers else None
                retry_after = float(ra) if ra and ra.isdigit() else None
                last = f"HTTP {e.code}: {data[:200]!r}"
                pacer.limited(retry_after)
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, http.client.HTTPException) as e:
                # HTTPException covers a body cut off mid-read (IncompleteRead) or a garbled status line
                last = f"{type(e).__name__}: {e}"
                pacer.limited()
            if attempt < self.retries:
                time.sleep(min(30.0, (2 ** attempt) * 0.5 * (1 + random.random())))
        raise TransientError(scrub(f"{h}: retries exhausted ({last})"))

    def get_json(self, url: str):
        status, data = self.request(url)
        if status != 200:
            raise SourceError(scrub(f"{host(url)}: HTTP {status}: {data[:300]!r}"))
        try:
            return json.loads(data)
        except ValueError as e:
            raise SourceError(f"{host(url)}: malformed JSON ({e})") from None


class Rpc:
    """A JSON-RPC endpoint. `call` returns the result; `batch` returns one (result | SourceError) per call."""

    def __init__(self, http: Http, url: str):
        self.http, self.url, self.host = http, url, host(url)

    def _post(self, payload):
        status, data = self.http.request(self.url, json.dumps(payload).encode(), {"content-type": "application/json"})
        try:
            doc = json.loads(data)
        except ValueError:
            raise SourceError(scrub(f"{self.host}: HTTP {status}: {data[:300]!r}")) from None
        if status != 200 and not isinstance(doc, (dict, list)):
            raise SourceError(scrub(f"{self.host}: HTTP {status}"))
        return status, doc

    def call(self, method: str, params: list):
        status, doc = self._post({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        if not isinstance(doc, dict):
            raise SourceError(f"{self.host}: {method}: not a JSON-RPC response (HTTP {status})")
        if doc.get("error") is not None:
            raise SourceError(scrub(f"{self.host}: {method}: {json.dumps(doc['error'])[:300]}"))
        if status != 200:
            raise SourceError(f"{self.host}: {method}: HTTP {status}")
        return doc.get("result")

    def batch(self, calls: list[tuple[str, list]]) -> list:
        if not calls:
            return []
        status, doc = self._post([{"jsonrpc": "2.0", "id": i, "method": m, "params": p} for i, (m, p) in enumerate(calls)])
        if isinstance(doc, dict):  # a batch refused as a whole (rate limit, size): one error for every call
            err = doc.get("error") or {"http": status}
            raise SourceError(scrub(f"{self.host}: batch refused: {json.dumps(err)[:300]}"))
        by_id = {r.get("id"): r for r in doc if isinstance(r, dict)}
        out = []
        for i, (m, _) in enumerate(calls):
            r = by_id.get(i)
            if r is None:
                out.append(SourceError(f"{self.host}: {m}: no answer in the batch"))
            elif r.get("error") is not None:
                out.append(SourceError(scrub(f"{self.host}: {m}: {json.dumps(r['error'])[:300]}")))
            else:
                out.append(r.get("result"))
        return out


def is_rate_limit(err: Exception) -> bool:
    s = str(err).lower()
    return "rate limit" in s or "too many requests" in s or "-32005" in s or "429" in s
