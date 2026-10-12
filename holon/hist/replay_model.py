"""replay_model.py — persistent access to the COMPILED generated models.

One `node holon/hist/replay_driver.mjs` subprocess serves the whole replay:
line-delimited JSON batches. All model evaluation happens inside the compiled
artifacts (morph_header.mjs, morph_rollup.mjs); this file only marshals.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

DRIVER = Path(__file__).with_name("replay_driver.mjs")


class ModelSession:
    def __init__(self, header_mjs: str | None = None, machine_mjs: str | None = None,
                 node: str = "node") -> None:
        self.header_mjs = header_mjs
        self.machine_mjs = machine_mjs
        self._sent_paths = False
        self.proc = subprocess.Popen(
            [node, str(DRIVER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, bufsize=1)

    def batch(self, jobs: list[dict]) -> list:
        req = {"jobs": jobs}
        if not self._sent_paths:
            req["header_module"] = self.header_mjs
            req["machine_module"] = self.machine_mjs
            self._sent_paths = True
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("replay_driver died")
        out = json.loads(line)
        if "error" in out:
            raise RuntimeError(out["error"])
        return out["results"]

    def keccak(self, data: bytes) -> str:
        return self.batch([{"kind": "keccak", "data": "0x" + data.hex()}])[0]

    def sha256(self, data: bytes) -> str:
        return self.batch([{"kind": "sha256", "data": "0x" + data.hex()}])[0]

    def hdr(self, fn: str, arg) -> object:
        job = {"kind": "hdr", "fn": fn}
        if isinstance(arg, (bytes, bytearray)):
            job["bytes"] = list(arg)
        else:
            job["hdr"] = arg
        return self.batch([job])[0]

    def mach(self, fn: str, *args) -> object:
        return self.batch([{"kind": "mach", "fn": fn, "args": list(args)}])[0]

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


# ---------- header record helpers ----------

# dec_go getter order (facts/morph_header.json): 12 fields; lastBlockNumber
# is present in the decoded list only for version >= 1 headers.
HDR_FIELDS = [
    ("version", 1), ("batchIndex", 8), ("l1MessagePopped", 8),
    ("totalL1MessagePopped", 8), ("dataHash", 32), ("blobVersionedHash", 32),
    ("prevStateHash", 32), ("postStateHash", 32), ("withdrawRootHash", 32),
    ("sequencerSetVerifyHash", 32), ("parentBatchHash", 32),
    ("lastBlockNumber", 8),
]


def hdr_cells(field_bytes: dict[str, list[int]]) -> dict:
    """field name -> byte list  ==>  {$hdr cells} for the header model."""
    cells = {}
    for name, width in HDR_FIELDS:
        bs = field_bytes.get(name, [0] * width)
        if len(bs) != width:
            raise ValueError(f"field {name}: want {width} bytes, got {len(bs)}")
        for i, b in enumerate(bs):
            cells[f"{name}_{i}"] = b
    return cells


def fields_named(dec_fields: list[list[int]]) -> dict[str, list[int]]:
    """dec_go result (list of byte lists) -> {field_name: bytes}."""
    if len(dec_fields) == 12:
        names = [n for n, _ in HDR_FIELDS]
    elif len(dec_fields) == 11:
        names = [n for n, _ in HDR_FIELDS[:-1]]
    else:
        raise ValueError(f"dec_go returned {len(dec_fields)} fields")
    return dict(zip(names, dec_fields))


def b2h(bs) -> str:
    return "0x" + bytes(bs).hex()


def h2b(h: str) -> bytes:
    h = h[2:] if h.startswith("0x") else h
    return bytes.fromhex(h)


def be_int(bs) -> int:
    return int.from_bytes(bytes(bs), "big")
