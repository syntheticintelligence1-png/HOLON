"""The pinned ABI of the Rollup's functions, and the names of every selector in the pinned checkout's history.

Decoding uses the pinned ABI only: the ABI JSON the pinned solc (config replay.solc, sha256-checked against
replay.solc_sha256) emits for contracts/contracts/l1/rollup/IRollup.sol at the facts' commit of the pinned
morph checkout (config replay.morph, checked by holon.replay.check_checkout). A transaction "decodes under the
pinned ABI" iff its selector is one of those functions' and its calldata decodes strictly (below).

Naming uses more: every revision of IRollup.sol in the pinned checkout's own git history (each compiled with
the same solc; a revision that does not compile is listed in `history_errors`), plus the external/public
functions of Rollup.sol's revisions whose parameters are all elementary types (importGenesisBatch(bytes),
finalizeBatch(bytes), ...), read from the declaration text. A historical selector names a function (so an
older commitBatch is still a commit) and can decode a legacy call for the supplementary statistics, but it
never makes a transaction "decoded".

Strict decoding (the Solidity ABI decoder's own checks on calldata): every head word and every offset and
length lies inside the calldata; uintN values fit N bits; address and bool words are clean; bytesN words have
zero low-order padding. Trailing bytes after the encoding are allowed (Solidity ignores them).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

from ..keccak import keccak256

ELEMENTARY = re.compile(r"^(u?int\d*|bytes\d*|address|bool|string)(\[\d*\])*$")


class AbiError(ValueError):
    pass


def canonical_type(p: dict) -> str:
    t = p["type"]
    if t.startswith("tuple"):
        return "(" + ",".join(canonical_type(c) for c in p["components"]) + ")" + t[len("tuple"):]
    return t


def signature(fn: dict) -> str:
    return f"{fn['name']}(" + ",".join(canonical_type(p) for p in fn["inputs"]) + ")"


def selector(sig: str) -> str:
    return "0x" + keccak256(sig.encode())[:4].hex()


# ---------------------------------------------------------------- decoding
def _is_dynamic(p: dict) -> bool:
    t = p["type"]
    if t in ("bytes", "string") or t.endswith("[]"):
        return True
    m = re.fullmatch(r"(.*)\[(\d+)\]", t)
    if m:
        return _is_dynamic({**p, "type": m.group(1)})
    if t == "tuple":
        return any(_is_dynamic(c) for c in p["components"])
    return False


def _static_size(p: dict) -> int:
    t = p["type"]
    m = re.fullmatch(r"(.*)\[(\d+)\]", t)
    if m:
        return int(m.group(2)) * _static_size({**p, "type": m.group(1)})
    if t == "tuple":
        return sum(_static_size(c) for c in p["components"])
    return 32


def _word(data: bytes, pos: int) -> bytes:
    if pos < 0 or pos + 32 > len(data):
        raise AbiError(f"word at {pos} past the end ({len(data)} bytes)")
    return data[pos:pos + 32]


def _uint(data: bytes, pos: int) -> int:
    return int.from_bytes(_word(data, pos), "big")


def _static(p: dict, data: bytes, pos: int):
    t = p["type"]
    m = re.fullmatch(r"(.*)\[(\d+)\]", t)
    if m:
        inner = {**p, "type": m.group(1)}
        size = _static_size(inner)
        return [_static(inner, data, pos + i * size) for i in range(int(m.group(2)))]
    if t == "tuple":
        return _params(p["components"], data, pos)
    w = _word(data, pos)
    v = int.from_bytes(w, "big")
    m = re.fullmatch(r"uint(\d*)", t)
    if m:
        if v >> int(m.group(1) or 256):
            raise AbiError(f"{t} value out of range")
        return v
    if t == "address":
        if v >> 160:
            raise AbiError("dirty address")
        return "0x" + w[12:].hex()
    if t == "bool":
        if v > 1:
            raise AbiError("dirty bool")
        return v == 1
    m = re.fullmatch(r"bytes(\d+)", t)
    if m:
        n = int(m.group(1))
        if any(w[n:]):
            raise AbiError(f"dirty {t}")
        return "0x" + w[:n].hex()
    raise AbiError(f"unsupported type {t}")


def _dynamic(p: dict, data: bytes, pos: int):
    t = p["type"]
    if t in ("bytes", "string"):
        n = _uint(data, pos)
        if pos + 32 + n > len(data):
            raise AbiError(f"{t} of {n} bytes past the end")
        b = data[pos + 32:pos + 32 + n]
        return b if t == "bytes" else b.decode("utf-8", "replace")
    if t.endswith("[]"):
        n = _uint(data, pos)
        if n > len(data):
            raise AbiError("array length past the end")
        return _params([{**p, "type": t[:-2]}] * n, data, pos + 32)
    m = re.fullmatch(r"(.*)\[(\d+)\]", t)
    if m:
        return _params([{**p, "type": m.group(1)}] * int(m.group(2)), data, pos)
    if t == "tuple":
        return _params(p["components"], data, pos)
    raise AbiError(f"unsupported dynamic type {t}")


def _params(params: list[dict], data: bytes, base: int) -> list:
    out, off = [], 0
    for p in params:
        if _is_dynamic(p):
            rel = _uint(data, base + off)
            if rel > len(data):
                raise AbiError("offset past the end")
            out.append(_dynamic(p, data, base + rel))
            off += 32
        else:
            out.append(_static(p, data, base + off))
            off += _static_size(p)
    return out


def named(params: list[dict], values: list):
    """Decoded values with tuple components by name (structs as dicts)."""
    out = {}
    for p, v in zip(params, values):
        if p["type"] == "tuple":
            v = named(p["components"], v)
        out[p.get("name") or f"_{len(out)}"] = v
    return out


def decode(fn: dict, calldata: bytes) -> dict:
    if len(calldata) < 4 or "0x" + calldata[:4].hex() != selector(signature(fn)):
        raise AbiError("selector mismatch")
    return named(fn["inputs"], _params(fn["inputs"], calldata[4:], 0))


# ---------------------------------------------------------------- the ABI from the pinned checkout
def _git(checkout: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(checkout), *args], capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise AbiError(f"git {' '.join(args)}: {p.stderr.strip()[:300]}")
    return p.stdout


def _solc_abi(solc: str, source: str, contract: str) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="holon-abi-") as d:
        f = Path(d) / f"{contract}.sol"
        f.write_text(source)
        p = subprocess.run([solc, "--combined-json", "abi", f.name], cwd=d, capture_output=True, text=True, timeout=300)
        if p.returncode != 0:
            raise AbiError(p.stderr.strip()[:300])
        doc = json.loads(p.stdout)
    abi = []
    for name, c in sorted(doc["contracts"].items()):
        if name.endswith(":" + contract):
            abi = c["abi"] if isinstance(c["abi"], list) else json.loads(c["abi"])
    if not abi:
        raise AbiError(f"no {contract} in the solc output")
    return [x for x in abi if x.get("type") == "function"]


def _elementary_functions(source: str) -> list[str]:
    src = re.sub(r"//[^\n]*", "", source)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    out = []
    for m in re.finditer(r"function\s+(\w+)\s*\(([^)]*)\)([^{;]*)", src):
        name, params, rest = m.group(1), m.group(2), m.group(3)
        if not re.search(r"\b(external|public)\b", rest):
            continue
        types = []
        for prm in [x.strip() for x in params.split(",") if x.strip()]:
            t = prm.split()[0]
            t = {"uint": "uint256", "int": "int256"}.get(t, t)
            if not ELEMENTARY.match(t):
                types = None
                break
            types.append(t)
        if types is not None:
            out.append(f"{name}(" + ",".join(types) + ")")
    return out


class PinnedAbi:
    def __init__(self, checkout: Path, commit: str, solc: str, target: dict):
        self.checkout, self.commit, self.solc = Path(checkout), commit, solc
        self.commit_functions = tuple(target["commit_functions"])
        iface, impl, cname = target["abi"]["interface"], target["abi"]["implementation"], target["abi"]["interface_contract"]
        self.interface = iface
        self.pinned = {}                     # selector -> function ABI (the interface at the pinned commit)
        for fn in _solc_abi(solc, (self.checkout / iface).read_text(), cname):
            self.pinned[selector(signature(fn))] = fn
        self.names: dict[str, dict] = {}     # selector -> {"name", "signature", "origin"}
        self.legacy: dict[str, dict] = {}    # selector -> (function ABI, origin) for historical interface functions
        self.history_errors: list[str] = []
        for sel, fn in self.pinned.items():
            self.names[sel] = {"name": fn["name"], "signature": signature(fn), "origin": "pinned"}
        for sig in _elementary_functions((self.checkout / impl).read_text()):
            self.names.setdefault(selector(sig), {"name": sig.split("(")[0], "signature": sig, "origin": "pinned"})
        for path in (iface, impl):
            for rev in _git(self.checkout, "log", "--format=%H", commit, "--", path).split():
                try:
                    src = _git(self.checkout, "show", f"{rev}:{path}")
                except AbiError as e:
                    self.history_errors.append(f"{rev[:12]} {path}: {e}")
                    continue
                if path == iface:
                    try:
                        fns = _solc_abi(solc, src, cname)
                    except AbiError as e:
                        self.history_errors.append(f"{rev[:12]} {path}: {str(e)[:120]}")
                        fns = []
                    for fn in fns:
                        sel = selector(signature(fn))
                        self.names.setdefault(sel, {"name": fn["name"], "signature": signature(fn), "origin": rev})
                        if sel not in self.pinned:
                            self.legacy.setdefault(sel, (fn, rev))
                else:
                    for sig in _elementary_functions(src):
                        self.names.setdefault(selector(sig), {"name": sig.split("(")[0], "signature": sig, "origin": rev})

    def commit_selectors(self) -> dict[str, str]:
        return {s: signature(f) for s, f in sorted(self.pinned.items()) if f["name"] in self.commit_functions}

    def describe(self) -> dict:
        return {"source": f"{self.interface} at {self.commit} (pinned solc)",
                "commit_selectors": self.commit_selectors(),
                "history_signatures": {s: v["signature"] for s, v in sorted(self.names.items())
                                       if v["origin"] != "pinned" and v["name"] in self.commit_functions},
                "history_errors": self.history_errors}


def solc_sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
