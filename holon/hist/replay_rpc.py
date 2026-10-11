"""L1 JSON-RPC client + minimal ABI for the S6 historical replay (stdlib only).

Oracle-side only: everything fetched here is compared against the COMPILED
model's answers. No model logic lives in this file.
"""
from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from typing import Any

from .replay_keccak import keccak256, selector

_UA = {"User-Agent": "holon-hist-replay/1.0", "Content-Type": "application/json"}


class RpcError(RuntimeError):
    pass


@dataclass
class Rpc:
    urls: Any
    timeout: int = 30
    _next_id: int = 0
    _ui: int = 0
    n_calls: int = 0

    def __post_init__(self):
        if isinstance(self.urls, str):
            self.urls = [self.urls]
        else:
            self.urls = list(self.urls)

    @property
    def url(self) -> str:
        return self.urls[self._ui]

    def _rotate(self) -> bool:
        if len(self.urls) < 2:
            return False
        self._ui = (self._ui + 1) % len(self.urls)
        return True

    def _payload(self, method: str, params: list) -> dict:
        self._next_id += 1
        return {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}

    def _post(self, body: Any, attempts: int = 4) -> Any:
        data = json.dumps(body).encode()
        last: Exception | None = None
        for i in range(attempts):
            try:
                req = urllib.request.Request(self.url, data=data, headers=_UA)
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    self.n_calls += len(body) if isinstance(body, list) else 1
                    return json.loads(r.read())
            except Exception as e:  # noqa: BLE001 - retried uniformly
                last = e
                if not self._rotate():
                    time.sleep(min(2 ** i, 8))
        raise RpcError(f"RPC {self.url} failed after {attempts} tries: {last}")

    def call(self, method: str, params: list) -> Any:
        err = None
        for _ in range(max(1, len(self.urls))):
            resp = self._post(self._payload(method, params))
            if "error" in resp:
                err = f"{method}: {resp['error']}"
                if not self._rotate():
                    break
                continue
            return resp.get("result")
        raise RpcError(err or f"{method}: no endpoints")

    def batch(self, calls: list[tuple[str, list]]) -> list[Any]:
        """One HTTP round-trip for many RPC calls; falls back to sequential
        calls when the endpoint rejects batch arrays (publicnode does)."""
        body = []
        for m, p in calls:
            self._next_id += 1
            body.append({"jsonrpc": "2.0", "id": self._next_id, "method": m, "params": p})
        try:
            resp = self._post(body, attempts=3)
        except RpcError:
            resp = None
        if isinstance(resp, list):
            by_id = {r.get("id"): r for r in resp}
            out = []
            ok = True
            for i, _ in enumerate(body):
                r = by_id.get(body[i]["id"])
                if r is None or "error" in r:
                    ok = False
                    break
                out.append(r.get("result"))
            if ok:
                return out
        # sequential fallback
        return [self.call(m, p) for m, p in calls]

    # ---- eth helpers ----
    def block_number(self) -> int:
        return int(self.call("eth_blockNumber", []), 16)

    def get_tx(self, h: str) -> dict:
        return self.call("eth_getTransactionByHash", [h])

    def get_receipt(self, h: str) -> dict:
        return self.call("eth_getTransactionReceipt", [h])

    def get_block(self, n: int | str) -> dict:
        tag = hex(n) if isinstance(n, int) else n
        return self.call("eth_getBlockByNumber", [tag, False])

    def get_logs(self, address: str, topic0: str, from_block: int, to_block: int,
                 topics_extra: list | None = None) -> list[dict]:
        topics = [topic0] + (topics_extra or [])
        try:
            return self.call("eth_getLogs", [{
                "address": address, "topics": topics,
                "fromBlock": hex(from_block), "toBlock": hex(to_block)}]) or []
        except RpcError:
            if to_block - from_block <= 40:
                raise
            mid = (from_block + to_block) // 2
            return (self.get_logs(address, topic0, from_block, mid,
                                  topics_extra) +
                    self.get_logs(address, topic0, mid + 1, to_block,
                                  topics_extra))

    def eth_call(self, to: str, data: str, block: int | str) -> str:
        tag = hex(block) if isinstance(block, int) else block
        return self.call("eth_call", [{"to": to, "data": data}, tag])


# ---------- minimal ABI ----------
def pad32(v: int) -> bytes:
    return v.to_bytes(32, "big")


def enc_uint(v: int) -> bytes:
    return pad32(v)


def enc_addr(a: str) -> bytes:
    return pad32(int(a, 16))


def enc_bytes32(h: str) -> bytes:
    return bytes.fromhex(h[2:] if h.startswith("0x") else h)


def call_data(sig: str, *enc_args: bytes) -> str:
    return "0x" + (selector(sig) + b"".join(enc_args)).hex()


def decode_uints(ret: str, n: int) -> list[int]:
    raw = bytes.fromhex(ret[2:] if ret.startswith("0x") else ret)
    if len(raw) < 32 * n:
        raise RpcError(f"short eth_call result: {len(raw)} < {32 * n}")
    return [int.from_bytes(raw[32 * i:32 * i + 32], "big") for i in range(n)]


def u8(h: str) -> int:
    return int(h, 16)


ZERO32 = "0x" + "00" * 32
ZERO_VERSIONED_HASH = "0x01" + "00" * 31
