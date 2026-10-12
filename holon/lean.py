"""`holon lean`: the Lean 4 second kernel for M0 (I9; whitepaper §8.8, §8.9; closes D-d for M0).

  python -m holon lean --milestone M0 [--json] [--jobs N]

For each M0 law, regenerate gen/M0/lean/<law_id>.lean (holon.gen.lean_proofs: model, statement with the
IR statement hash, and a proof re-checking the Bend verdict recorded in results/M0/<law_id>.json: the
law for PROVED, the counter-law at the recorded witness for REFUTED), check it in a fresh temporary lake
project (Lean 4.34.0, no Mathlib, no dependencies, nothing reused from an earlier build), and audit it:

  * Lean G3: the file, comments removed, holds none of FORBIDDEN;
  * `#print axioms` for every theorem the file declares (appended by the runner, whatever the file says)
    lists only ALLOWED_AXIOMS;
  * the theorem carrying the verdict is among them; each file checks within lean.budget_s_per_file.

The committed report gen/M0/lean/report.json binds each result to the sha256 of the exact text checked. It
holds no timings, so a re-run over the same records rewrites gen/M0/lean byte for byte; timings are in the
printed report and, from the gate, in results/M0/gate_timing.json (G7_lean). The M0 pipeline reads it
(`kernel_entry`): a record lists lean4 as checked only when the text it would emit now, from the law, the
facts and the run's own verdict and witness, has the checked sha256; independence_class is I2 only then.
G7 re-checks every such file from scratch.

Order of a full regeneration: `holon run` (Bend verdicts and witnesses), `holon lean` (re-checks them from
the records), `holon run` again (records pick up the Lean result). The Lean files depend only on each
record's status and witness, so once those are stable the second run changes nothing else.

check_text(src, tmpdir) and flip_canary(src) are the building blocks (and the I9-P4 canary).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEAN_VERSION = "4.34.0"
TOOLCHAIN = f"leanprover/lean4:v{LEAN_VERSION}"
ALLOWED_AXIOMS = frozenset({"propext", "Quot.sound"})
FORBIDDEN = re.compile(r"\b(sorry|admit|native_decide|bv_decide|decide\s*\+\s*native|axiom|unsafe|implemented_by|"
                       r"extern|ofReduceBool|ofReduceNat|opaque|partial|macro|macro_rules|syntax|elab|notation|"
                       r"infix|infixl|infixr|prefix|postfix|import|run_cmd|run_tac|run_elab|initialize|"
                       r"builtin_initialize|debug\.skipKernelTC|Lean\.Elab|Lean\.Meta)\b")
# commands that run code or cut elaboration short (#eval runs IO during the lake build; #exit stops checking the rest
# of the file): forbidden like the tactics above (audit F-M2-32)
FORBIDDEN_CMD = re.compile(r"(?m)^[ \t]*#(eval|exit)\b")
# A canary counts as rejected only for a semantic reason (audit F-M2-32): the kernel decided the flipped claim false,
# or found the two sides not definitionally equal. A parse, name or goal-shape error rejects it vacuously, and
# "unsolved goals" alone is not enough (a syntax error can surface first as an empty tactic block's unsolved goal).
SEMANTIC_REJECTION = re.compile(r"Tactic `decide` proved that the proposition|is not definitionally equal|"
                                r"Tactic `rfl` failed: The left-hand side|type mismatch")
NON_SEMANTIC = re.compile(r"unexpected token|unexpected identifier|unknown identifier|unknown constant|unknown tactic|"
                          r"expected term|unterminated|invalid syntax|Expected the goal to be a binary relation")
CLAIM_MARK = "-- holon:claim"
REPORT = "report.json"
SUBDIR = "lean"
MODULE = "HolonCheck"
RESULTS = ("checked", "rejected", "forbidden", "bad_axioms", "missing_theorem", "timeout", "unavailable",
           "unsupported", "not_run")


# ------------------------------------------------------------------ configuration and toolchain
def config(root: Path | str = ROOT) -> dict:
    p = Path(root) / "config" / "holon.json"
    cfg = json.loads(p.read_text()) if p.exists() else {}
    lean = {"toolchain": TOOLCHAIN, "pinned_version": LEAN_VERSION, "budget_s_per_file": 120, "timeout_s": 300}
    lean.update(cfg.get("lean", {}))
    return lean


class LeanUnavailable(RuntimeError):
    pass


def toolchain_bin(cfg: dict | None = None) -> Path:
    """The bin directory of the pinned toolchain under ~/.elan (absolute; never a PATH lookup)."""
    cfg = cfg or config()
    tc = cfg["toolchain"]
    d = Path.home() / ".elan" / "toolchains" / tc.replace("/", "--").replace(":", "---") / "bin"
    if not (d / "lean").is_file() or not (d / "lake").is_file():
        raise LeanUnavailable(f"Lean toolchain {tc} not installed (no lean/lake in {d})")
    return d


def _env(bin_dir: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("LEAN", "LAKE", "ELAN"))}
    env["PATH"] = os.pathsep.join([str(bin_dir), env.get("PATH", "")])  # prepended: the pinned lean wins
    return env


def lean_version(cfg: dict | None = None) -> str:
    b = toolchain_bin(cfg)
    p = subprocess.run([str(b / "lean"), "--version"], capture_output=True, text=True, timeout=60, env=_env(b))
    out = p.stdout.strip()
    m = re.match(r"Lean \(version (\d+\.\d+\.\d+)", out)
    if p.returncode != 0 or not m:
        raise LeanUnavailable(f"cannot run lean --version: {out or p.stderr.strip()}")
    return out


# What the fingerprint hashes, relative to the toolchain directory: the executables and the shared libraries
# that hold the elaborator, the kernel and Lake. The Init/Std .olean files (2.4 GB) are not hashed.
FINGERPRINT_FILES = ("bin/lean", "bin/lake", "lib/lean/libleanshared.so", "lib/lean/libLake_shared.so")


def _file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


_FP_CACHE: dict[str, dict] = {}


def fingerprint(cfg: dict | None = None) -> dict:
    """sha256 over FINGERPRINT_FILES of the pinned toolchain (resolved through links), as in bend.fingerprint."""
    home = Path(os.path.realpath(toolchain_bin(cfg))).parent
    if str(home) not in _FP_CACHE:
        files, h = {}, hashlib.sha256()
        for rel in FINGERPRINT_FILES:
            p = home / rel
            if not p.is_file():
                raise LeanUnavailable(f"Lean toolchain file {p} is missing")
            files[rel] = _file_sha256(p)
            h.update(rel.encode() + b"\0" + files[rel].encode() + b"\n")
        _FP_CACHE[str(home)] = {"toolchain_dir": str(home), "files": files, "fingerprint": "sha256:" + h.hexdigest()}
    return _FP_CACHE[str(home)]


def toolchain_ok(cfg: dict | None = None) -> tuple[bool, str]:
    """(ok, detail): `lean --version` is the pinned version and, when lean.pinned_fingerprint is set, the
    toolchain's fingerprint equals it."""
    cfg = cfg or config()
    try:
        v = lean_version(cfg)
        fp = fingerprint(cfg)
    except LeanUnavailable as e:
        return False, str(e)
    got = re.match(r"Lean \(version (\d+\.\d+\.\d+)", v).group(1)
    if got != cfg["pinned_version"]:
        return False, f"{v} is not the pinned {cfg['pinned_version']}"
    pin = cfg.get("pinned_fingerprint")
    if pin and fp["fingerprint"] != pin:
        return False, f"Lean toolchain fingerprint {fp['fingerprint']} ({fp['toolchain_dir']}) is not the pinned {pin}"
    return True, f"{v}; fingerprint {fp['fingerprint']}" + (" pinned" if pin else " (no pin configured)")


def pinned_version_ok(cfg: dict | None = None) -> tuple[bool, str]:
    return toolchain_ok(cfg)


# ------------------------------------------------------------------ source audit
_LIT = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)\'', re.S)


def strip_comments(src: str) -> str:
    """Lean source without comments (line comments, and block comments, which nest in Lean). String and char
    literals are kept whole, so a `--` or `/-` inside one never hides the code after it."""
    out, i, depth, n = [], 0, 0, len(src)
    while i < n:
        m = _LIT.match(src, i) if depth == 0 and src[i] in "\"'" else None
        if m:
            out.append(m.group(0))
            i = m.end()
        elif depth == 0 and src.startswith("--", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif src.startswith("/-", i):
            depth += 1
            i += 2
        elif depth and src.startswith("-/", i):
            depth -= 1
            i += 2
        elif depth:
            i += 1
        else:
            out.append(src[i])
            i += 1
    return "".join(out)


def forbidden(src: str) -> list[str]:
    code = strip_comments(src)
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)
    return sorted(set(m.group(0) for m in FORBIDDEN.finditer(code))
                  | {"#" + m.group(1) for m in FORBIDDEN_CMD.finditer(code)})


def first_error_block(out: str) -> str:
    """The text of Lean's first error, up to the next error or warning."""
    lines = out.splitlines()
    i = next((k for k, line in enumerate(lines) if re.search(r"(^|: )error:", line)), None)
    if i is None:
        return ""
    j = next((k for k in range(i + 1, len(lines)) if re.search(r"(^|: )(error|warning):", lines[k])), len(lines))
    return "\n".join(lines[i:j])


def semantic_rejection(out: str) -> bool:
    """Was a canary rejected for a semantic reason (SEMANTIC_REJECTION in its first error, and no parse, name or
    goal-shape error anywhere)? A canary rejected for any other reason proves nothing about the kernel."""
    return bool(SEMANTIC_REJECTION.search(first_error_block(out))) and not NON_SEMANTIC.search(out)


def theorems(src: str) -> list[str]:
    return re.findall(r"^theorem\s+([A-Za-z_][A-Za-z0-9_.]*)", strip_comments(src), re.M)


_AX = re.compile(r"'([^']+)' (does not depend on any axioms|depends on axioms: \[([^\]]*)\])", re.S)


def parse_axioms(out: str) -> dict[str, list[str]]:
    res: dict[str, list[str]] = {}
    for m in _AX.finditer(out):
        res[m.group(1)] = sorted(a.strip() for a in (m.group(3) or "").replace("\n", " ").split(",") if a.strip())
    return res


# ------------------------------------------------------------------ checking one text
def _project(d: Path, src: str, names: list[str], cfg: dict) -> None:
    d.mkdir(parents=True)
    (d / "lean-toolchain").write_text(cfg["toolchain"] + "\n")
    (d / "lakefile.toml").write_text(f'name = "holoncheck"\ndefaultTargets = ["{MODULE}"]\n\n'
                                     f'[[lean_lib]]\nname = "{MODULE}"\n')
    audit = "".join(f"\n#print axioms {t}" for t in names)
    (d / f"{MODULE}.lean").write_text(src.rstrip("\n") + "\n\n-- appended by holon.lean (axiom audit)" + audit + "\n")


def check_text(src: str, tmpdir, expect: list[str] | None = None, cfg: dict | None = None,
               timeout: float | None = None) -> dict:
    """Check one Lean source in a fresh lake project under tmpdir.

    result: checked (Lean accepts it, every declared theorem is audited, axioms within ALLOWED_AXIOMS and
    every `expect`ed theorem present) | rejected | forbidden | bad_axioms | missing_theorem | timeout |
    unavailable. Also returns axioms (union over the theorems), per-theorem axioms, seconds and out."""
    cfg = cfg or config()
    names = theorems(src)
    base = {"result": "rejected", "axioms": [], "theorems": {}, "seconds": 0.0, "out": ""}
    bad = forbidden(src)
    if bad:
        return {**base, "result": "forbidden", "out": f"forbidden in the source: {bad}"}
    try:
        b = toolchain_bin(cfg)
    except LeanUnavailable as e:
        return {**base, "result": "unavailable", "out": str(e)}
    d = Path(tmpdir) / f"proj-{hashlib.sha256(src.encode()).hexdigest()[:12]}"
    if d.exists():
        shutil.rmtree(d)  # never reuse a build
    _project(d, src, names, cfg)
    t0 = time.monotonic()
    try:
        p = subprocess.run([str(b / "lake"), "build", "--no-cache", "--log-level=info"], cwd=d, env=_env(b),
                           capture_output=True, text=True, timeout=timeout or cfg["timeout_s"])
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        return {**base, "result": "timeout", "seconds": round(time.monotonic() - t0, 3),
                "out": f"timeout after {timeout or cfg['timeout_s']} s\n{out[-4000:]}"}
    secs = round(time.monotonic() - t0, 3)
    out = p.stdout + p.stderr
    ax = parse_axioms(out)
    union = sorted({a for t in names for a in ax.get(t, [])})
    res = {**base, "axioms": union, "theorems": {t: ax.get(t) for t in names}, "seconds": secs, "out": out}
    if p.returncode != 0 or re.search(r"(^|\n)error:|: error:", out):
        return {**res, "result": "rejected"}
    if not names or any(ax.get(t) is None for t in names) or any(t not in names for t in (expect or [])):
        return {**res, "result": "missing_theorem"}
    if not set(union) <= ALLOWED_AXIOMS:
        return {**res, "result": "bad_axioms"}
    return {**res, "result": "checked"}


def flip_canary(src: str) -> str:
    """The source with its main claim's relation flipped (= to ≠, or ≠ to =), proof unchanged: Lean must
    reject it. The main claim is the one line carrying CLAIM_MARK (holon.gen.lean_laws)."""
    lines = src.split("\n")
    idx = [i for i, l in enumerate(lines) if l.rstrip().endswith(CLAIM_MARK)]
    if len(idx) != 1:
        raise ValueError(f"expected exactly one line marked {CLAIM_MARK!r}, found {len(idx)}")
    i = idx[0]
    code = lines[i][: lines[i].rindex(CLAIM_MARK)]
    if code.count(" ≠ ") == 1 and code.count(" = ") == 0:
        code = code.replace(" ≠ ", " = ")
    elif code.count(" = ") == 1 and code.count(" ≠ ") == 0:
        code = code.replace(" = ", " ≠ ")
    else:
        raise ValueError(f"the marked claim has no single top-level relation: {code.strip()[:200]}")
    lines[i] = code + CLAIM_MARK + " (flipped canary)"
    return "\n".join(lines)


# ------------------------------------------------------------------ emission for a milestone
def facts_path(milestone: str, root: Path) -> Path:
    reg = json.loads((root / "laws" / milestone / "REGISTRY.json").read_text())
    return root / reg.get("facts", "facts/morph_header.json")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def emit_for(law: dict, facts: dict, facts_sha256: str, verdict: str, witness: dict | None) -> tuple[str, dict]:
    """(Lean text, info) for a law and the verdict to re-check; raises LeanUnsupported."""
    from . import ir
    from .gen import lean_laws, lean_proofs
    ll = lean_laws.emit(law, facts, ir.statement_hash(law))
    return lean_proofs.emit_file(law, facts, facts_sha256, ll, verdict, ir.render_statement(law), witness)


def lean_dir(milestone: str, root: Path | str = ROOT) -> Path:
    return Path(root) / "gen" / milestone / SUBDIR


def applicable(milestone: str, root: Path | str = ROOT) -> bool:
    from . import ir
    return ir.ir_version_of(milestone, root) == "holon-ir/0.1"


def plan(milestone: str, root: Path) -> tuple[list[dict], dict, str]:
    """[(law, verdict, witness, text | None, info | error)] from the laws and the committed records."""
    from . import ir
    from .gen.lean_model import LeanUnsupported, load_facts
    fp = facts_path(milestone, root)
    facts, fsha = load_facts(fp), hashlib.sha256(fp.read_bytes()).hexdigest()
    out = []
    for law in ir.load_laws(milestone, root):
        lid = law["law_id"]
        rp = root / "results" / milestone / f"{lid}.json"
        rec = json.loads(rp.read_text()) if rp.exists() else {}
        verdict = rec.get("status", "UNKNOWN")
        item = {"law": law, "law_id": lid, "verdict": verdict, "witness": rec.get("witness"), "text": None}
        if verdict not in ("PROVED", "REFUTED"):
            item["error"] = f"no Bend verdict to re-check (status {verdict})"
        else:
            try:
                item["text"], item["info"] = emit_for(law, facts, fsha, verdict, rec.get("witness"))
            except LeanUnsupported as e:
                item["error"] = f"unsupported: {e}"
        out.append(item)
    return out, facts, fsha


def run(milestone: str = "M0", root: Path | str = ROOT, jobs: int = 1, log=print) -> dict:
    root = Path(root).resolve()
    cfg = config(root)
    if not applicable(milestone, root):
        raise SystemExit(f"holon lean: {milestone} is not a holon-ir/0.1 milestone (Lean emitters cover M0's IR)")
    items, _, fsha = plan(milestone, root)
    ok, version = toolchain_ok(cfg)
    d = lean_dir(milestone, root)
    tmp = Path(tempfile.mkdtemp(prefix="holon-lean-"))

    def one(it):
        if it["text"] is None:
            return {"result": "unsupported" if it["error"].startswith("unsupported") else "not_run",
                    "axioms": [], "theorems": {}, "seconds": 0.0, "out": it["error"]}
        if not ok:
            return {"result": "unavailable", "axioms": [], "theorems": {}, "seconds": 0.0,
                    "out": f"Lean is not the pinned toolchain: {version}"}
        r = check_text(it["text"], tmp / it["law_id"], expect=[it["info"]["main"]], cfg=cfg)
        if r["result"] == "checked" and r["seconds"] > cfg["budget_s_per_file"]:
            r = {**r, "result": "timeout", "out": f"over the budget of {cfg['budget_s_per_file']} s\n" + r["out"]}
        return r

    try:
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
            results = list(ex.map(one, items))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    report = {"milestone": milestone, "kernel": "lean4", "lean_version": cfg["pinned_version"],
              "toolchain": cfg["toolchain"], "lean": lean_version(cfg) if ok else None,
              "fingerprint": fingerprint(cfg)["fingerprint"] if ok else None, "facts_sha256": fsha,
              "allowed_axioms": sorted(ALLOWED_AXIOMS), "laws": {}}
    cli = {"laws": {}}
    for it, r in zip(items, results):
        lid = it["law_id"]
        entry = {"result": r["result"], "axioms": r["axioms"], "verdict": it["verdict"],
                 "statement_hash": _hash(it["law"]),
                 "source": f"gen/{milestone}/{SUBDIR}/{lid}.lean" if it["text"] is not None else None,
                 "source_sha256": sha256_text(it["text"]) if it["text"] is not None else None,
                 "theorems": r["theorems"], "main": (it.get("info") or {}).get("main"),
                 "generator": (it.get("info") or {}).get("generator")}
        if r["result"] != "checked":
            entry["error"] = _first_error(r["out"])
        report["laws"][lid] = entry
        cli["laws"][lid] ={"result": r["result"], "axioms": r["axioms"], "seconds": r["seconds"],
                            "verdict": it["verdict"], **({"error": entry["error"]} if "error" in entry else {})}
        log(f"{lid:16s} {it['verdict']:8s} lean4 {r['result']:10s} {r['seconds']:7.2f} s  axioms {r['axioms']}")
    # written only now, after every check, so an interrupted run never leaves files without their report
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    for it in items:
        if it["text"] is not None:
            (d / f"{it['law_id']}.lean").write_text(it["text"], encoding="utf-8")
    (d / REPORT).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return cli


def _hash(law: dict) -> str:
    from . import ir
    return ir.statement_hash(law)


def _first_error(out: str, n: int = 12) -> str:
    lines = [l for l in out.splitlines() if "error" in l.lower()] or out.strip().splitlines()
    return "\n".join(lines[:n])[:2000]


# ------------------------------------------------------------------ what records may claim
def load_report(milestone: str, root: Path | str = ROOT) -> dict | None:
    p = lean_dir(milestone, root) / REPORT
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def kernel_entry(law: dict, facts: dict, facts_sha256: str, status: str, witness: dict | None,
                 report: dict | None, milestone: str = "M0") -> dict | None:
    """The lean4 entry of a record's kernels[] (None for a milestone the Lean emitters do not cover).

    checked only when the committed report checked exactly the text emitted now for this law, these facts,
    this status and this witness, with allowed axioms; failed when it checked that text and Lean did not
    accept it; otherwise not_run, with the reason."""
    entry = {"name": "lean4", "version": LEAN_VERSION, "role": "second-independent"}
    if status not in ("PROVED", "REFUTED"):
        return {**entry, "result": "not_run", "note": "no verdict to re-check"}
    try:
        text, info = emit_for(law, facts, facts_sha256, status, witness)
    except Exception as e:  # noqa: BLE001  (any facts the Lean emitters cannot express: not run, never a crash)
        return {**entry, "result": "not_run", "note": f"the Lean emitters cannot express this law: "
                                                      f"{type(e).__name__}: {e}"}
    sha = sha256_text(text)
    r = (report or {}).get("laws", {}).get(law["law_id"])
    entry.update({"source": f"gen/{milestone}/{SUBDIR}/{law['law_id']}.lean", "source_sha256": sha,
                  "theorem": info["main"]})
    if not report or report.get("lean_version") != LEAN_VERSION or r is None:
        return {**entry, "result": "not_run", "note": "no Lean report for this law (run `holon lean`)"}
    if r.get("source_sha256") != sha or r.get("verdict") != status or r.get("statement_hash") != _hash(law):
        return {**entry, "result": "not_run",
                "note": "the Lean report is stale: it checked another text (re-run `holon lean`)"}
    if r.get("result") == "checked" and set(r.get("axioms", [])) <= ALLOWED_AXIOMS and r.get("main") == info["main"]:
        return {**entry, "result": "checked", "axioms": sorted(r.get("axioms", []))}
    return {**entry, "result": "failed", "note": f"Lean result {r.get('result')}"}


# ------------------------------------------------------------------ CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon lean")
    ap.add_argument("--milestone", default="M0")
    ap.add_argument("--root")
    ap.add_argument("--json", action="store_true", help="print the report as JSON on stdout")
    ap.add_argument("--jobs", type=int, default=1, help="files checked in parallel (default 1: honest timings)")
    a = ap.parse_args(argv)
    root = Path(a.root or ROOT).resolve()
    log = (lambda s: print(s, file=sys.stderr)) if a.json else print
    rep = run(a.milestone, root, a.jobs, log)
    if a.json:
        print(json.dumps(rep, indent=2, sort_keys=True))
    return 0 if rep["laws"] and all(r["result"] == "checked" for r in rep["laws"].values()) else 1
