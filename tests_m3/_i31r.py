"""I31 replay instrument, fixed at the I31 prereg: runs DISCH witnesses on the REAL Rollup at the pinned commit,
independently of holon's replay, and evaluates a law's blocked condition and check on the real storage.

  real_run(traces, slots)     each trace (a witness's steps: {"action", "calldata", "env": {"caller", "msg.value",
                              "block.timestamp", "blobhash", ..}}) from a fresh deployment of the I20 binding, through
                              the byte copy of the I20 step harness taken at this prereg (tests_m3/fixtures/disch/
                              harness/); per trace {"outcomes": ["ok" | "rev <key>", ..], "calls": [[{"to", "data",
                              "ok", "ret"}] per step], "slots": [{slot: word} per step]} where "slots" holds vm.load
                              of every requested slot after each step (the harness's D lines)
  Layout(doc)                 the storage layout of a transitions document (storage and inherited_storage)
  Layout.slots_for(term, keys)  every slot a term may read when each mapping key is one of `keys`
  Layout.value(term, words, t)  the value of a DISCH term (the atoms of a blocked condition, a check's expr) on
                              real storage words, block.timestamp t; a read of a slot not in words is an error

The toolchain is pinned (config/holon.json replay: forge, solc, the dependency tree; I15's check): a missing or
different tool is a failure, never a skip. Nothing here imports holon/.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from tests_m2 import _i15 as I15
from tests_m2._i16 import morph_checkout
from tests_m2._keccak import keccak256
from tests_m3._m3 import ROOT, load_json

HARNESS_DIR = ROOT / "tests_m3" / "fixtures" / "disch" / "harness"
# byte copies of replay/M2/solidity/HolonStepBase.sol, replay/M1/solidity/HolonTraceReplay.t.sol and
# replay/M2/solidity/HolonExtractedStep.t.sol at the I31 prereg (the same bytes I30's fixture copied)
HARNESS = {"HolonStepBase.sol": "d6b490fad4b5da0ae4438c32be6dab6a3e301eff1a06b7b111b470a6874f6334",
           "HolonTraceReplay.t.sol": "3e651a254861603f30c9614ee85ccaa85b6b012d3c2bf88e2aa8813b26959853",
           "HolonExtractedStep.t.sol": "8a4e31d7cc0cfd7b86db08c71e7ad27c618ec75808b67afa1fc8eecfbfa8a5da"}
PANIC_SELECTOR = bytes.fromhex("4e487b71")
ERROR_SELECTOR = bytes.fromhex("08c379a0")
W256 = 1 << 256


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def num(v) -> int:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    return int(str(v), 0)


def _w(v: int) -> bytes:
    return (v % W256).to_bytes(32, "big")


def _dyn(b: bytes) -> bytes:
    return _w(len(b)) + b + b"\0" * ((-len(b)) % 32)


def _hexbytes(s) -> bytes:
    s = str(s)
    return bytes.fromhex(s[2:] if s.startswith("0x") else s)


def call_step(step: dict) -> str:
    """The step harness's call step: abi.encode(uint8 2, bool false, bytes payload), payload = abi.encode(address
    caller, uint256 value, uint256 timestamp, bytes32[] blobhashes, address to (0: the target), bytes data)."""
    env = step.get("env") or {}
    blobs = [_hexbytes(b).rjust(32, b"\0") for b in env.get("blobhash") or []]
    data = _hexbytes(step["calldata"])
    head_words = 6
    arr = _w(len(blobs)) + b"".join(blobs)
    off_arr = 32 * head_words
    off_data = off_arr + len(arr)
    payload = (_w(num(env["caller"])) + _w(num(env.get("msg.value", 0))) + _w(num(env.get("block.timestamp", 0)))
               + _w(off_arr) + _w(0) + _w(off_data) + arr + _dyn(data))
    outer = _w(2) + _w(0) + _w(96) + _dyn(payload)
    return "0x" + outer.hex()


def revert_key(ret: bytes) -> str:
    if len(ret) >= 68 and ret[:4] == ERROR_SELECTOR:
        n = int.from_bytes(ret[36:68], "big")
        return ret[68:68 + n].decode("utf-8", "replace")
    if len(ret) == 36 and ret[:4] == PANIC_SELECTOR:
        return "panic:0x%x" % int.from_bytes(ret[4:], "big")
    return "0x" + ret[:4].hex()


def deployment_init() -> list[int]:
    """The binding's deployment parameters, as holon fragments passes them (replay/M2/fragments.json "init")."""
    binding = load_json(ROOT / "replay" / "M2" / "fragments.json")
    initial = load_json(ROOT / binding["init"]["facts"])["initial"]
    out = []
    for k in binding["init"]["keys"]:
        name, _, idx = k.partition(".")
        out.append(int(initial[name][int(idx)] if idx else initial[name]))
    return out


def real_run(traces: list[list[dict]], slots: list[int]) -> list[dict]:
    if not traces:
        raise AssertionError("no trace to replay")
    cfg = I15._check_toolchain()
    for name, pin in HARNESS.items():
        if _sha(HARNESS_DIR / f"{name}.txt") != pin:
            raise AssertionError(f"tests_m3/fixtures/disch/harness/{name}.txt is not the harness copied at the prereg")
    morph = morph_checkout()
    proj = Path(tempfile.mkdtemp(prefix="holon-i31-sol-"))
    try:
        shutil.copytree(morph / "contracts" / "contracts", proj / "contracts")
        for d in ("mock", "test"):
            shutil.rmtree(proj / "contracts" / d, ignore_errors=True)
        for f in ("foundry.toml", "remappings.txt"):
            shutil.copy(morph / "contracts" / f, proj / f)
        shutil.copytree(Path(cfg["sol_deps"]) / "node_modules", proj / "node_modules", symlinks=False,
                        ignore=shutil.ignore_patterns(".git"))
        (proj / "test").mkdir()
        for name in HARNESS:
            shutil.copy(HARNESS_DIR / f"{name}.txt", proj / "test" / name)
        init = deployment_init()
        sl = ["0x" + _w(s).hex() for s in slots]
        base = [cfg["forge"], "test", "--offline", "--use", cfg["solc"]]
        out = []
        for k, tr in enumerate(traces):
            fin, fout = proj / f"holon_i31_steps_{k}.json", proj / f"holon_i31_steps_{k}.out"
            fin.write_text(json.dumps({"lens": [len(tr)], "steps": [call_step(s) for s in tr], "slots": sl,
                                       "init": init}))
            env = {**os.environ, "HOLON_STEPS_IN": str(fin), "HOLON_STEPS_OUT": str(fout), "HOLON_LO": "0",
                   "HOLON_HI": "1"}
            p = subprocess.run(base + ["--match-contract", "^HolonExtractedStepTest$", "--match-test",
                                       r"^test_steps\(\)$"], cwd=proj, env=env, capture_output=True, text=True,
                               timeout=3000)
            if p.returncode != 0 or not fout.exists():
                raise AssertionError(f"the I31 replay instrument failed on trace {k} (exit {p.returncode}): "
                                     f"{(p.stdout + p.stderr)[-2000:]}")
            outcomes, calls, words = {}, {}, {}
            for line in fout.read_text().splitlines():
                f = line.split(" ")
                if f[0] == "S" and len(f) > 5 and f[3] == "call" and f[2].isdigit():
                    ret = bytes.fromhex(f[-1][2:])
                    outcomes[int(f[2])] = "ok" if f[5] == "1" else "rev " + revert_key(ret)
                elif f[0] == "C" and len(f) > 6 and f[2].isdigit():
                    calls.setdefault(int(f[2]), []).append({"to": f[3], "data": f[4], "ok": f[5] == "1",
                                                            "ret": f[6]})
                elif f[0] == "D" and len(f) > 3 and f[2].isdigit():
                    vals = [] if f[3] == "-" else f[3].split(",")
                    words[int(f[2])] = {s: num(v) for s, v in zip(slots, vals)}
            out.append({"outcomes": [outcomes.get(i, "missing") for i in range(len(tr))],
                        "calls": [calls.get(i, []) for i in range(len(tr))],
                        "slots": [words.get(i, {}) for i in range(len(tr))]})
        return out
    finally:
        shutil.rmtree(proj, ignore_errors=True)


# ------------------------------------------------------------------ the layout and term values on real storage
class Layout:
    def __init__(self, doc: dict):
        self.fam = {}
        for s in list(doc.get("storage") or []) + list(doc.get("inherited_storage") or []):
            if s["name"] == "__gap":
                continue
            self.fam[s["name"]] = s

    def _base(self, t):
        """(family entry, [keys], member) of a read term, or None."""
        if not isinstance(t, list) or not t:
            return None
        if t[0] == "storage":
            return self.fam[t[1]], [], None
        if t[0] == "map":
            b = self._base(t[1])
            return (b[0], b[1] + [t[2]], b[2]) if b else None
        if t[0] == "member":
            b = self._base(t[1])
            return (b[0], b[1], t[2]) if b else None
        return None

    def _slot(self, fam: dict, keys: list[int], member):
        slot = fam["slot"]
        for k in keys:
            slot = int.from_bytes(keccak256(_w(k) + _w(slot)), "big")
        off, width = fam.get("offset", 0), fam.get("width") or 256
        if member is not None:
            f = next(x for x in fam["fields"] if x["name"] == member)
            slot, off, width = slot + f["slot"], f.get("offset", 0), f.get("width") or 256
        return slot, off, width

    def slots_for(self, t, keys: list[int], acc=None) -> set:
        """Every slot term t may read, each mapping key ranging over `keys` (constants: themselves)."""
        if acc is None:
            acc = set()
        b = self._base(t)
        if b is not None:
            fam, ks, member = b
            choices = [[]]
            for k in ks:
                kk = [k] if isinstance(k, int) and not isinstance(k, bool) else list(keys)
                choices = [c + [x] for c in choices for x in kk]
                if not (isinstance(k, int) and not isinstance(k, bool)):
                    self.slots_for(k, keys, acc)
            for c in choices:
                acc.add(self._slot(fam, c, member)[0])
            return acc
        if isinstance(t, list):
            for x in t[1:]:
                self.slots_for(x, keys, acc)
        return acc

    def value(self, t, words: dict, now: int):
        if isinstance(t, bool):
            return int(t)
        if isinstance(t, int):
            return t % W256
        b = self._base(t)
        if b is not None:
            fam, ks, member = b
            keys = [self.value(k, words, now) for k in ks]
            slot, off, width = self._slot(fam, keys, member)
            if slot not in words:
                raise AssertionError(f"the replay did not read slot {hex(slot)} ({json.dumps(t)})")
            return (words[slot] >> (8 * off)) & ((1 << width) - 1)
        h = t[0]
        if t == ["env", "block.timestamp"]:
            return now
        if h == "!":
            return int(self.value(t[1], words, now) == 0)
        if h == "&&":
            return int(all(self.value(x, words, now) != 0 for x in t[1:]))
        if h == "||":
            return int(any(self.value(x, words, now) != 0 for x in t[1:]))
        a = self.value(t[1], words, now) if len(t) > 1 and h not in ("fits",) else None
        if h in ("==", "!=", "<", "<=", ">", ">="):
            c = self.value(t[2], words, now)
            return int({"==": a == c, "!=": a != c, "<": a < c, "<=": a <= c, ">": a > c, ">=": a >= c}[h])
        if h in ("+", "-", "*"):
            c = self.value(t[2], words, now)
            return {"+": a + c, "-": a - c, "*": a * c}[h] % W256
        if h == "?":
            return self.value(t[2], words, now) if a != 0 else self.value(t[3], words, now)
        if h == "fits":
            n, e = t[1], t[2]
            x, y = self.value(e[1], words, now), self.value(e[2], words, now)
            r = {"+": x + y, "-": x - y, "*": x * y}[e[0]]
            return int(0 <= r < (1 << n))
        raise AssertionError(f"the replay instrument cannot evaluate {json.dumps(t)[:120]}")
