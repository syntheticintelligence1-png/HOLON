"""I40 instrument, fixed at the I40 prereg (tests_m3/test_refute.py is the contract). Everything here is computed from
committed artifacts, independently of holon/: it never imports holon.

  record_files(root)         every result record of the milestones I40 recomputes, keyed "<dir>/<law_id>" with dir one
                             of RECORD_DIRS (results/M2/extracted_m1 holds I20's differential re-runs of M1 laws)
  law_of(root, key)          the law IR a record decides (an extracted_m1 record decides the M1 law of its id)
  skeleton(w)                a witness's shape: per key the op names of a trace, the op of one step, or its value kind
  witness_classes(root)      the REFUTED witness classes (one per REFUTED record, one per checked entry point of a
                             per-entry record) with their law, model, keys, skeleton and signature (codec: the byte
                             positions where the two sides differ; domain: version byte, length and the two verdicts)
  codec_laws(root)           every law over a codec document (M0 and the M3 PAR laws) with its status and the solver
                             verdict its status implies (sat iff REFUTED)
  unknown_records(root)      every UNKNOWN record, with its law's facts document
  replay_sides(root)         the I4 replay sides of every record that has a replay entry (replay/<M>/report.json)
  concretization_kind(...)   rule K1-K4 of the contract: direct, commit_class, bmc or go_only
  expected_final_bin(...)    the final filter rule F1-F4 of the contract, written out a second time
  unfalsified_reaches(root)  the guard reaches I20's step refinement left unfalsified (results/M2/refinement/extracted.json)
  sidecar_doc(root)          the computed fields of spec/M3/lib/refute.json (the rest is transcription, checked by tests)
  toy_run(variant, traces)   witness steps on the REAL planted ToyLock (tests_m3/fixtures/refute/<variant>/src) through
                             the byte copy of the I20 step harness (HolonStepBase) and the toy's concrete harness, with the
                             pinned forge and solc: per trace {"outcomes": ["ok" | "rev <key>", ..]}
  toy_chain(...), revert_request_paths(), initializer_paths(), zero_blob_commit()
                             the hand-built traces of the instrument checks (TestInstruments), run at the prereg

The toolchain is pinned (config/holon.json replay: forge, solc, the dependency tree; I15's check): a missing or different
tool is a failure, never a skip.
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
from tests_m2._keccak import keccak256
from tests_m3 import _i26 as I26
from tests_m3._m3 import ROOT, load_json

RECORD_DIRS = ("M0", "M1", "M2", "M2/extracted_m1", "M3")
SIDECAR_REL = "spec/M3/lib/refute.json"
FIX_REL = "tests_m3/fixtures/refute"
HARNESS_DIR = ROOT / FIX_REL / "harness"
# HolonStepBase.sol: a byte copy of replay/M2/solidity/HolonStepBase.sol at this prereg (the bytes I26's, I27's, I30's
# and I31's fixtures copied); HolonToyLockStep.t.sol: the toy's concrete harness, written at this prereg
HARNESS = {"HolonStepBase.sol": "d6b490fad4b5da0ae4438c32be6dab6a3e301eff1a06b7b111b470a6874f6334",
           "HolonToyLockStep.t.sol": "f9ec7a3196aaa74c0a54d3feec4e1c9a7309218288a577c247cfbe2976358089"}
BLOCKING = ("internal_harness", "emulated_storage")
CODEC_FACTS = ("facts/morph_header.json",)
PANIC_SELECTOR = bytes.fromhex("4e487b71")
ERROR_SELECTOR = bytes.fromhex("08c379a0")
TOY_CALLER = "0x0000000000000000000000000000000000001001"


# ------------------------------------------------------------------ JSON
def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ------------------------------------------------------------------ records and laws
def record_files(root: Path = ROOT) -> dict[str, dict]:
    out = {}
    for d in RECORD_DIRS:
        for p in sorted((root / "results" / d).glob("L*.json")):
            out[f"{d}/{p.stem}"] = load_json(p)
    return out


def split_key(key: str) -> tuple[str, str]:
    d, _, lid = key.rpartition("/")
    return d, lid


def law_of(root: Path, key: str) -> dict:
    d, lid = split_key(key)
    m = "M1" if d == "M2/extracted_m1" else d
    return load_json(root / "laws" / m / f"{lid}.json")


def _order(key: str) -> tuple:
    d, lid = split_key(key)
    return RECORD_DIRS.index(d), lid


def _op(x):
    if isinstance(x, dict):
        return x.get("op") or x.get("action")
    return None


def skeleton(w: dict) -> dict:
    def kind(v):
        if isinstance(v, list):
            return [_op(x) for x in v]
        if isinstance(v, dict):
            if "op" in v or "action" in v:
                return _op(v)
            if "run" in v:
                return {"run": [_op(x) for x in v["run"]]}
            if "instance" in v:
                return "oracle"
            return "record"
        if isinstance(v, str) and v.startswith("0x"):
            return "bytes"
        return "scalar"
    return {k: kind(v) for k, v in sorted(w.items())}


def _hexb(s: str) -> bytes:
    return bytes.fromhex(s[2:] if s.startswith("0x") else s)


def signature(rec: dict, w: dict) -> tuple[str, dict]:
    """(kind, signature) of a witness: codec (the byte positions where the two sides' encodings differ), domain (the
    version byte, the length and the two definedness verdicts) or trace (its skeleton)."""
    diff = rec.get("difference")
    if isinstance(diff, dict) and isinstance(diff.get("lhs"), str) and isinstance(diff.get("rhs"), str):
        a, b = _hexb(diff["lhs"]), _hexb(diff["rhs"])
        pos = [i for i in range(max(len(a), len(b))) if i >= len(a) or i >= len(b) or a[i] != b[i]]
        return "codec", {"diff_positions": pos, "lengths": [len(a), len(b)]}
    if (isinstance(diff, dict) and isinstance(diff.get("lhs"), bool) and isinstance(diff.get("rhs"), bool)
            and isinstance(w.get("b"), str)):
        b = _hexb(w["b"])
        return "domain", {"version_byte": b[0] if b else None, "length": len(b), "lhs": diff["lhs"], "rhs": diff["rhs"]}
    return "trace", {"skeleton": skeleton(w)}


def witness_classes(root: Path = ROOT) -> list[dict]:
    out = []
    recs = record_files(root)
    for key in sorted(recs, key=_order):
        r = recs[key]
        if r.get("status") != "REFUTED":
            continue
        law = law_of(root, key)
        per_entry = r.get("witnesses") or {}
        entries = sorted(e for e, x in per_entry.items() if (x or {}).get("status") == "REFUTED") or [None]
        for e in entries:
            w = per_entry[e]["witness"] if e is not None else r["witness"]
            kind, sig = signature(r, w)
            out.append({"record": key, "law_id": r["law_id"], "milestone": split_key(key)[0], "entry": e,
                        "rule": r.get("rule") or law.get("rule"), "subform": r.get("subform") or law.get("subform"),
                        "facts": law["facts"], "model": (r.get("artifacts") or {}).get("model"),
                        "statement_hash": r["statement_hash"], "witness_sha256": sha256_json(w), "keys": sorted(w),
                        "kind": kind, "signature": sig})
    for i, c in enumerate(out):
        c["id"] = f"C{i + 1:02d}"
    return out


def codec_laws(root: Path = ROOT) -> list[dict]:
    """Every law over a codec document: the M0 laws (facts/morph_header.json) and the M3 PAR laws (the linked codec
    model). The solver's verdict on a law's negation that its status implies: sat iff REFUTED."""
    out = []
    for key, r in sorted(record_files(root).items(), key=lambda kv: _order(kv[0])):
        d, _ = split_key(key)
        law = law_of(root, key)
        if (d == "M0" and law["facts"] in CODEC_FACTS) or (d == "M3" and (r.get("rule") or law.get("rule")) == "PAR"):
            out.append({"record": key, "law_id": r["law_id"], "status": r["status"],
                        "solver": "sat" if r["status"] == "REFUTED" else "unsat"})
    return out


def unknown_records(root: Path = ROOT) -> list[dict]:
    out = []
    for key, r in sorted(record_files(root).items(), key=lambda kv: _order(kv[0])):
        if r.get("status") == "UNKNOWN":
            law = law_of(root, key)
            out.append({"record": key, "law_id": r["law_id"], "rule": r.get("rule") or law.get("rule"),
                        "subform": r.get("subform") or law.get("subform"), "facts": law["facts"],
                        "statement_hash": r.get("statement_hash")})
    return out


def replay_sides(root: Path = ROOT) -> dict[str, dict]:
    """The I4 sides (tests_m2/_i4.py: M0 entries hold sides directly, later ones under "sides") of every record with a
    replay entry in replay/<M>/report.json."""
    out = {}
    for m in ("M0", "M1", "M2"):
        rep = load_json(root / "replay" / m / "report.json")
        for lid, entry in (rep.get("laws") or {}).items():
            ss = dict(entry) if m == "M0" else dict(entry.get("sides") or {})
            out[f"{m}/{lid}"] = {k: v for k, v in ss.items() if isinstance(v, dict)}
    return out


def _has_key(obj, k: str) -> bool:
    if isinstance(obj, dict):
        return k in obj or any(_has_key(v, k) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_key(v, k) for v in obj)
    return False


def concretization_kind(key: str, rec: dict, law: dict, sides: dict) -> str:
    """Rules K1-K4 of the contract.
    K1 bmc: the witness rests on a construction no public call makes: a side ran on an internal harness or emulated
       storage, or the law's statement applies a migration (a "mig" term), or a codec law's claim is definedness (a
       domain witness) and not every side is a Go library call;
    K2 go_only: every side of the witness is a Go library call (no EVM side), tested before K1's definedness clause
       (amended at the I67 prereg, spec/M3/amendments.jsonl: a Go-op law's definedness witness has no EVM side);
    K3 commit_class: a codec law whose claim compares an EVM encoder with another encoder (the Solidity side is a commit
       of the witness's version from the deployment, observing the cells where the encoders differ);
    K4 direct: otherwise (the witness is a schedule of public calls on the machine from its initial state)."""
    w = rec.get("witness") if isinstance(rec.get("witness"), dict) else {}
    kind = signature(rec, w)[0] if w else "trace"
    provs = [s.get("provenance") for s in sides.values()]
    if any(p in BLOCKING for p in provs) or _has_key(law.get("statement"), "mig"):
        return "bmc"
    if provs and all(p == "library_api" for p in provs):
        return "go_only"
    if kind == "domain":
        return "bmc"
    if kind == "codec":
        return "commit_class"
    return "direct"


def expected_final_bin(sides: dict, conc: dict) -> str:
    """The final filter rule F1-F4 of the contract (holon/filter.py final must agree on every input):
    F1 model_defect: some side failed;
    F2 known_limitation: the record's kind is bmc and BMC found no public path within the bound (result no_path);
    F3 finding: the kind is not go_only, its concretization found a path (direct and commit_class: by construction),
       some public_schedule side passed and observed the obstruction, every side that is not internal_harness or
       emulated_storage passed and observed it, and a blocking side is present only when the kind is bmc (a public
       path supersedes the construction);
    F4 pending: anything else."""
    ss = [s for s in sides.values() if isinstance(s, dict)]
    if any(s.get("status") == "failed" for s in ss):
        return "model_defect"
    kind, result = conc.get("kind"), conc.get("result")
    if kind == "bmc" and result == "no_path":
        return "known_limitation"

    def ok(s):
        return s.get("status") == "passed" and s.get("obstruction_observed") is True
    pub = [s for s in ss if s.get("provenance") == "public_schedule"]
    nonblock = [s for s in ss if s.get("provenance") not in BLOCKING]
    block = [s for s in ss if s.get("provenance") in BLOCKING]
    if (kind != "go_only" and result == "path" and any(ok(s) for s in pub) and all(ok(s) for s in nonblock)
            and (not block or kind == "bmc")):
        return "finding"
    return "pending"


def concretization_kinds(root: Path = ROOT) -> dict[str, dict]:
    """Per REFUTED record: its kind (K1-K4), its I4 sides' provenance, and its filter_bin at the prereg."""
    sides = replay_sides(root)
    out = {}
    for key, r in sorted(record_files(root).items(), key=lambda kv: _order(kv[0])):
        if r.get("status") != "REFUTED":
            continue
        law = law_of(root, key)
        ss = sides.get(key, {})
        if not ss and split_key(key)[0] == "M2/extracted_m1":
            ss = sides.get("M1/" + r["law_id"], {})   # the same law and witness as M1's: its sides' provenance
        out[key] = {"kind": concretization_kind(key, r, law, ss), "filter_bin": r.get("filter_bin"),
                    "provenance": {k: s.get("provenance") for k, s in sorted(ss.items())}}
    return out


def unfalsified_reaches(root: Path = ROOT) -> list[str]:
    r = load_json(root / "results" / "M2" / "refinement" / "extracted.json")
    return [u["id"] for u in r["guard_coverage"]["unfalsified"]]


# ------------------------------------------------------------------ the sidecar's computed fields
def sidecar_inputs(root: Path = ROOT) -> list[str]:
    paths = sorted({f"results/{d}/{p.name}" for d in RECORD_DIRS for p in (root / "results" / d).glob("L*.json")}
                   | {f"laws/{m}/{p.name}" for m in ("M0", "M1", "M2", "M3") for p in (root / "laws" / m).glob("L*.json")}
                   | {"replay/M0/report.json", "replay/M1/report.json", "replay/M2/report.json",
                      "results/M2/refinement/extracted.json"})
    return paths


def sidecar_doc(root: Path = ROOT) -> dict:
    """The computed fields of spec/M3/lib/refute.json: classes, codec_laws, unknowns, records and unfalsified_reaches,
    with the sha256 of every input they were computed from."""
    classes = witness_classes(root)
    kinds = concretization_kinds(root)
    return {
        "classes": classes,
        "codec_laws": codec_laws(root),
        "unknowns": unknown_records(root),
        "records": kinds,
        "unfalsified_reaches": unfalsified_reaches(root),
        "inputs": [{"path": p, "sha256": sha256_file(root / p)} for p in sidecar_inputs(root)],
    }


# ------------------------------------------------------------------ the real ToyLock, through the step harness
def _toy_project(variant: str, cfg: dict) -> Path:
    proj = Path(tempfile.mkdtemp(prefix="holon-i40-toy-"))
    (proj / "src").mkdir()
    (proj / "test").mkdir()
    shutil.copy(ROOT / FIX_REL / variant / "src" / "ToyLock.sol", proj / "src" / "ToyLock.sol")
    for name in HARNESS:
        shutil.copy(HARNESS_DIR / f"{name}.txt", proj / "test" / name)
    shutil.copytree(Path(cfg["sol_deps"]) / "node_modules", proj / "node_modules", symlinks=False,
                    ignore=shutil.ignore_patterns(".git"))
    (proj / "foundry.toml").write_text(
        "[profile.default]\nsrc = 'src'\ntest = 'test'\nout = 'out'\nlibs = ['node_modules']\n"
        "evm_version = 'cancun'\noptimizer = false\nfs_permissions = [{ access = 'read-write', path = './' }]\n")
    (proj / "remappings.txt").write_text("forge-std/=node_modules/forge-std/src/\nds-test/=node_modules/ds-test/src/\n")
    return proj


def revert_key(ret: bytes) -> str:
    if ret[:4] == PANIC_SELECTOR and len(ret) == 36:
        return f"panic:0x{int.from_bytes(ret[4:], 'big'):02x}"
    if ret[:4] == ERROR_SELECTOR and len(ret) >= 68:
        n = int.from_bytes(ret[36:68], "big")
        return ret[68:68 + n].decode("utf-8", "replace")
    return "0x" + ret.hex()


def toy_run(variant: str, traces: list[list[dict]]) -> list[dict]:
    if not traces:
        raise AssertionError("no trace to replay")
    cfg = I15._check_toolchain()
    for name, pin in HARNESS.items():
        if sha256_file(HARNESS_DIR / f"{name}.txt") != pin:
            raise AssertionError(f"{FIX_REL}/harness/{name}.txt is not the harness fixed at the I40 prereg")
    proj = _toy_project(variant, cfg)
    try:
        fin, fout = proj / "holon_i40_steps.json", proj / "holon_i40_steps.out"
        fin.write_text(json.dumps({"lens": [len(tr) for tr in traces],
                                   "steps": [I26.call_step(s) for tr in traces for s in tr], "slots": [], "init": []}))
        env = {**os.environ, "HOLON_STEPS_IN": str(fin), "HOLON_STEPS_OUT": str(fout), "HOLON_LO": "0",
               "HOLON_HI": str(len(traces))}
        p = subprocess.run([cfg["forge"], "test", "--offline", "--use", cfg["solc"], "--match-contract",
                            "^HolonToyLockStepTest$", "--match-test", r"^test_steps\(\)$"], cwd=proj, env=env,
                           capture_output=True, text=True, timeout=1800)
        if p.returncode != 0 or not fout.exists():
            raise AssertionError(f"the I40 toy instrument failed (exit {p.returncode}): {(p.stdout + p.stderr)[-2000:]}")
        outcomes: dict = {}
        for line in fout.read_text().splitlines():
            f = line.split(" ")
            if f[0] == "S" and len(f) == 14 and f[3] == "call" and f[2].isdigit():
                outcomes[(int(f[1]), int(f[2]))] = "ok" if f[5] == "1" else "rev " + revert_key(_hexb(f[-1]))
        return [{"outcomes": [outcomes.get((t, i), "missing") for i in range(len(tr))]} for t, tr in enumerate(traces)]
    finally:
        shutil.rmtree(proj, ignore_errors=True)


def toy_step(action: str, ts: int, args: list | None = None, types: list | None = None,
             caller: str = TOY_CALLER) -> dict:
    sig = f"{action}({','.join(types or [])})"
    return I26.step(action, sig, list(types or []), list(args or []), caller, ts)


def toy_chain(t0: int = 1_700_000_000, late: int = 1) -> list[dict]:
    """The seven-step chain of the planted fixture: arm at t0, s1..s5, then fire `late` seconds after arm (W = 0)."""
    return ([toy_step("arm", t0)] + [toy_step(f"s{i}", t0) for i in range(1, 6)] + [toy_step("fire", t0 + late)])


# ------------------------------------------------------------------ hand-built rollup traces (instrument checks)
TARGETS_132 = ("challengeState", "commitBatch", "commitBatchWithProof", "commitState", "finalizeBatch", "proveState")


def _revert_request_prefix() -> tuple[list[dict], dict]:
    """S1 commits batch 1 (version 1, one blob), the challenger challenges it, S2 proves it after the proof window:
    the timeout branch sets revertReqIndex = 1 and slashes S1 (Rollup.sol:612-614, :803-805)."""
    F, W, D, t0, r0 = I26.deployment_init()
    blob = (1 << 248) | 0x42
    inp, h = I26._batch1(r0, blob, 110, 1)
    s1, s2 = I26.STANDIN_SUBMITTERS
    T = I26.EPOCH + t0
    hb = keccak256(h)
    pre = [I26.commit_step("commitBatch", inp, s1, T + 1, [I26.word_hex(blob)]),
           I26.step("challengeState", "challengeState(uint64,bytes32)", ["uint64", "bytes32"], [1, hb], I26.CHALLENGER,
                    T + 2, 1),
           I26.step("proveState", "proveState(bytes,bytes)", ["bytes", "bytes"], [h, b"\x01"], s2, T + 2 + W)]
    return pre, {"T": T, "W": W, "r0": r0, "h": h, "hb": hb, "s2": s2, "inp": inp}


def revert_request_paths() -> dict[str, list[dict]]:
    """For each action whose nonReqRevert reach (Rollup.sol:132) I20 left unfalsified: the three-step prefix, then that
    action, called by a caller that passes every earlier check, so it reverts at :132 with "pending revert request"."""
    pre, x = _revert_request_prefix()
    T, W, h, hb, s2, r0 = x["T"], x["W"], x["h"], x["hb"], x["s2"], x["r0"]
    t = T + 3 + W
    blob = (1 << 248) | 0x43
    inp2 = [1, h, 2, 0, I26._word(110), I26._word(120), I26._word(0)]
    last = {
        "challengeState": I26.step("challengeState", "challengeState(uint64,bytes32)", ["uint64", "bytes32"], [1, hb],
                                   I26.CHALLENGER, t, 1),
        "commitBatch": I26.commit_step("commitBatch", inp2, s2, t, [I26.word_hex(blob)]),
        "commitBatchWithProof": I26.step(
            "commitBatchWithProof", f"commitBatchWithProof({I26.INPUT},bytes,bytes)", [I26.INPUT, "bytes", "bytes"],
            [inp2, h, b"\x01"], "0x0000000000000000000000000000000000001005", t),
        "commitState": I26.commit_step("commitState", inp2, s2, t, []),
        "finalizeBatch": I26.step("finalizeBatch", "finalizeBatch(bytes)", ["bytes"], [h],
                                  "0x0000000000000000000000000000000000001005", t),
        "proveState": I26.step("proveState", "proveState(bytes,bytes)", ["bytes", "bytes"], [h, b"\x01"], s2, t),
    }
    return {a: pre + [last[a]] for a in TARGETS_132}


def initializer_paths() -> dict[str, list[dict]]:
    """initialize2 (resp. initialize3) called twice by an unprivileged caller: the first call passes the reinitializer
    check (_initialized is 1 after the binding's deployment), the second reverts at Initializable.sol:120."""
    F, W, D, t0, r0 = I26.deployment_init()
    T = I26.EPOCH + t0
    anyone = "0x0000000000000000000000000000000000001005"
    i2 = I26.step("initialize2", "initialize2(bytes32)", ["bytes32"], [I26._word(7)], anyone, T + 1)
    i3 = I26.step("initialize3", "initialize3(uint256)", ["uint256"], [5], anyone, T + 1)
    return {"initialize2": [i2, dict(i2, env=dict(i2["env"], **{"block.timestamp": T + 2}))],
            "initialize3": [i3, dict(i3, env=dict(i3["env"], **{"block.timestamp": T + 2}))]}


def zero_blob_commit() -> list[dict]:
    """I21-T2's EVM half: one commitBatch of batch 1 at version 1 carrying no blob, which stores ZERO_VERSIONED_HASH."""
    F, W, D, t0, r0 = I26.deployment_init()
    inp, h = I26._batch1(r0, int(I26.ZVH, 16), 110, 1)
    return [I26.commit_step("commitBatch", inp, I26.STANDIN_SUBMITTERS[0], I26.EPOCH + t0 + 1, [])]
