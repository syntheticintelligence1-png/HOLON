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

I43 (Lean for the promoted set: every PROVED law of M1 onward, docs/HUMAN_ANSWERS.md Q8) adds the Lean directories
of the holon-ir/0.2 and 0.3 milestones, one per records directory (lean_dirs):

  python -m holon lean --milestone M1|M2|M3 [--root DIR] [--jobs N] [--json] [--check | --emit-only]

  M1   results/M1                gen/M1/lean                 each law's own facts document
  M2   results/M2                gen/M2/lean                 each law's own facts document
  M2/extracted_m1                gen/M2/extracted/m1/lean    the window view gen/M2/extracted/m1_view.json, over the
       results/M2/extracted_m1                               M1 laws (holon.differential's output layout)
  M3   results/M3                gen/M3/lean                 each law's own facts document

A dir's attempted laws (rule L0, items) are its PROVED records and its REFUTED records over a model kind the Lean
emitters cover (holon.gen.lean_common.model_kind: machine, machine_oracle, linked). Each is emitted (emit) by the
emitters of its kind: holon.gen.lean_machine (the model of a holon-facts/0.2 document), lean_mlaws (statements),
lean_mproofs (the machine proof classes), lean_sites (SORT sites: coercion_guard and the site counter-laws),
lean_linked (linked codec documents). A form an emitter cannot express raises lean_common.Unsupported: that law gets no
file, and its record says not_run with reason unsupported_form. The run writes <lean dir>/<law id>.lean,
<lean dir>/models/<stem>.lean (the model section every law file over it repeats verbatim) and <lean dir>/report.json,
after checking every file in a fresh lake project (check_law, check_model; classify reads the outcome). --check
re-emits in memory and compares with the committed .lean files (no Lean); --emit-only writes the .lean files and no
report. The pipelines read the report through kernel_entry_v2: a record's lean4 entry is checked only when the report
checked exactly the text emitted now, with the same verdict, statement hash and main theorem.

The emission reads documents only: the laws, the committed records (status, witness, witnesses, attempts), the facts,
the oracle sidecar spec/<M>/lib/oracles.json (modelled parameters), and through holon.gen.lean_sites.inputs the
SORT-site entries of <laws dir>/DERIVATION.json and the sort sites sidecar. It never imports a Bend emitter, holon.sorts, holon.mpipeline or the
facts helpers (rule L1, independence), and never reads a test, an instrument or a frozen sidecar of the contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from .gen import lean_common as LC

ROOT = Path(__file__).resolve().parents[1]
LEAN_VERSION = "4.34.0"
TOOLCHAIN = f"leanprover/lean4:v{LEAN_VERSION}"
ALLOWED_AXIOMS = frozenset({"propext", "Quot.sound"})
FORBIDDEN = re.compile(r"\b(sorry|admit|native_decide|bv_decide|decide\s*\+\s*native|axiom|unsafe|implemented_by|"
                       r"extern|ofReduceBool|ofReduceNat|opaque|partial|macro|macro_rules|syntax|elab|notation|"
                       r"infix|infixl|infixr|prefix|postfix|import|run_cmd|run_tac|run_elab|initialize|"
                       r"builtin_initialize|debug\.skipKernelTC|Lean\.Elab|Lean\.Meta)\b")
# commands that run code or cut elaboration short (#eval runs IO during the lake build; #exit stops checking the rest
# of the file): forbidden like the tactics above (audit F-M2-32). Every # command but #print axioms (which I9's M0
# files carry), anywhere in the code: Lean runs a command that follows a declaration on the same line, so a mid-line
# #eval could print forged audit lines and a mid-line #exit hide the rest of the file (I43 build review, M1)
FORBIDDEN_CMD = re.compile(r"#(?!print\s+axioms\b)([A-Za-z_][A-Za-z0-9_]*)")
# A canary counts as rejected only for a semantic reason (audit F-M2-32): the kernel decided the flipped claim false,
# or found the two sides not definitionally equal. A parse, name or goal-shape error rejects it vacuously, and
# "unsolved goals" alone is not enough (a syntax error can surface first as an empty tactic block's unsolved goal).
# Lean 4.34.0's wordings (I43, probed): "Tactic `decide` proved that the proposition ... is false" (decide), "Not a
# definitional equality: the left-hand side ... is not definitionally equal to the right-hand side" (rfl on a closed
# term), "Tactic `rfl` failed: The left-hand side ..." (the rfl tactic), "Type mismatch" (a term proof such as
# fun _ => rfl, exact rfl or Eq.refl); its name errors are capitalized ("Unknown identifier", "Unknown constant"),
# so both readings ignore case where Lean's wording varies.
SEMANTIC_REJECTION = re.compile(r"Tactic `decide` proved that the proposition|Not a definitional equality|"
                                r"is not definitionally equal|Tactic `rfl` failed: The left-hand side|"
                                r"(?i:type mismatch)")
NON_SEMANTIC = re.compile(r"(?i:unexpected token|unexpected identifier|unknown identifier|unknown constant|"
                          r"unknown tactic|expected term|unterminated|invalid syntax|"
                          r"Expected the goal to be a binary relation)")
# Lean's own messages for the resource limits a lean4 entry may report as not_run (I43 rule L8): over them Lean gave no
# verdict; any other rejection is a failed entry
RESOURCE_LIMITS = (("recursion_depth", re.compile(r"maximum recursion depth has been reached")),
                   ("heartbeats", re.compile(r"\(deterministic\) timeout at .*maximum number of heartbeats \(\d+\) "
                                             r"has been reached")))
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
    literals are kept whole, so a `--` or `/-` inside one never hides the code after it; so is an escaped identifier
    «...» outside a comment (I42 Question 5: `def «/-»` opens no comment, and the code after it stays visible)."""
    out, i, depth, n = [], 0, 0, len(src)
    while i < n:
        m = _LIT.match(src, i) if depth == 0 and src[i] in "\"'" else None
        if m:
            out.append(m.group(0))
            i = m.end()
        elif depth == 0 and src[i] == "«":
            j = src.find("»", i + 1)
            j = n if j < 0 else j + 1
            out.append(src[i:j])
            i = j
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


# A char literal opens with a quote that does not continue an identifier (x' is a name, '"' a char).
_CHAR_OPEN = re.compile(r"(?<![\w'!?])'")


def forbidden(src: str, strict: bool = False) -> list[str]:
    """The forbidden words and commands of a Lean source, comments removed, plus "string literal" or "char literal"
    for any literal outside a comment. No generated Lean file holds one, and Lean lexes literals in ways a comment
    stripper misreads (Q35's priority fix, after the escaped identifier of I42 Question 5): a raw string r"\\" ends
    at its second quote, an interpolated string s!"{..}" holds code in its braces, and a char literal '"' holds the
    quote a string blanker would open. Each could hide the code after it from this scan. strict (the I43 Lean
    directories, whose files carry no # at all): any # outside a comment is reported too."""
    code = strip_comments(src)
    lits = {"string literal"} if '"' in code else set()
    lits |= {"char literal"} if _CHAR_OPEN.search(code) else set()
    lits |= {"#"} if strict and "#" in code else set()
    code = re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)
    return sorted(set(m.group(0) for m in FORBIDDEN.finditer(code))
                  | {"#" + m.group(1) for m in FORBIDDEN_CMD.finditer(code)} | lits)


def first_error_block(out: str) -> str:
    """The text of Lean's first error, up to the next error or warning."""
    lines = out.splitlines()
    i = next((k for k, line in enumerate(lines) if re.search(r"(^|: )error(\(|:)", line)), None)
    if i is None:
        return ""
    j = next((k for k in range(i + 1, len(lines)) if re.search(r"(^|: )(error|warning)(\(|:)", lines[k])),
             len(lines))
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
SENTINEL_PREFIX = "holon_audit_sentinel_"


def _project(d: Path, src: str, names: list[str], cfg: dict, sentinel: str) -> None:
    d.mkdir(parents=True)
    (d / "lean-toolchain").write_text(cfg["toolchain"] + "\n")
    (d / "lakefile.toml").write_text(f'name = "holoncheck"\ndefaultTargets = ["{MODULE}"]\n\n'
                                     f'[[lean_lib]]\nname = "{MODULE}"\n')
    audit = "".join(f"\n#print axioms {t}" for t in [*names, sentinel])
    (d / f"{MODULE}.lean").write_text(src.rstrip("\n") + "\n\n-- appended by holon.lean (axiom audit)\n"
                                      f"theorem {sentinel} : True := trivial" + audit + "\n")


def check_text(src: str, tmpdir, expect: list[str] | None = None, cfg: dict | None = None,
               timeout: float | None = None, names: list[str] | None = None, strict: bool = False) -> dict:
    """Check one Lean source in a fresh lake project under tmpdir.

    result: checked (Lean accepts it, every declared theorem is audited, axioms within ALLOWED_AXIOMS and
    every `expect`ed theorem present) | rejected | forbidden | bad_axioms | missing_theorem | timeout |
    unavailable. Also returns axioms (union over the theorems), per-theorem axioms, seconds and out.
    names: the theorems to audit (default: every `theorem` the source declares, by its bare name). The runner appends
    a theorem with a fresh random name (the sentinel) after the file and audits it last: the output's audit lines must
    end with exactly the audited theorems and then the sentinel, in order, and only those lines count. So a file that
    stops early (#exit) or prints audit lines of its own cannot pass (I43 build review, M1). strict: forbidden(strict)."""
    cfg = cfg or config()
    names = theorems(src) if names is None else list(names)
    base = {"result": "rejected", "axioms": [], "theorems": {}, "seconds": 0.0, "out": ""}
    bad = forbidden(src, strict)
    if bad:
        return {**base, "result": "forbidden", "out": f"forbidden in the source: {bad}"}
    try:
        b = toolchain_bin(cfg)
    except LeanUnavailable as e:
        return {**base, "result": "unavailable", "out": str(e)}
    d = Path(tmpdir) / f"proj-{hashlib.sha256(src.encode()).hexdigest()[:12]}"
    if d.exists():
        shutil.rmtree(d)  # never reuse a build
    sentinel = SENTINEL_PREFIX + secrets.token_hex(8)
    _project(d, src, names, cfg, sentinel)
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
    lines = [(m.group(1), sorted(a.strip() for a in (m.group(3) or "").replace("\n", " ").split(",") if a.strip()))
             for m in _AX.finditer(out)]
    tail = lines[-(len(names) + 1):]
    ordered = [n for n, _ in tail] == [*names, sentinel]
    ax = dict(tail) if ordered else {}
    union = sorted({a for t in names for a in ax.get(t, [])})
    res = {**base, "axioms": union, "theorems": {t: ax.get(t) for t in names}, "seconds": secs, "out": out}
    if p.returncode != 0 or re.search(r"(^|\n)error:|: error:", out):
        return {**res, "result": "rejected"}
    if not ordered:
        return {**res, "result": "missing_theorem",
                "out": out + "\n[holon.lean] the axiom audit does not end with the audited theorems and the sentinel"}
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


# ================================================================== I43: the Lean directories of M1 onward
VIEW = "extracted_m1"          # holon.differential's layout: the M1 laws re-run on a milestone's window view
VIEW_LAWS = "laws/M1"
MODELS = "models"
_TARGET = re.compile(r"M\d+")   # a target milestone; anything else (T15, ...) is a test milestone (no Lean entries)


class LeanDirError(ValueError):
    """A Lean directory's inputs are inconsistent (a record without its law file, two models with one stem)."""


@dataclass(frozen=True)
class LeanDir:
    """One records directory and its Lean directory (rule L0). facts: the facts document of every law there (the
    view), or None for each law's own "facts"."""
    key: str
    milestone: str
    records: str
    laws: str
    lean: str
    facts: str | None


def _own_dir(m: str) -> LeanDir:
    return LeanDir(m, m, f"results/{m}", f"laws/{m}", f"gen/{m}/{SUBDIR}", None)


def _view_dir(m: str) -> LeanDir:
    return LeanDir(f"{m}/{VIEW}", m, f"results/{m}/{VIEW}", VIEW_LAWS, f"gen/{m}/extracted/m1/{SUBDIR}",
                   f"gen/{m}/extracted/m1_view.json")


_IRV: dict = {}


def _ir_version(milestone: str, root: Path) -> str | None:
    k = (milestone, str(Path(root).resolve()))
    if k not in _IRV:
        from . import ir
        try:
            _IRV[k] = ir.ir_version_of(milestone, root)
        except (ValueError, OSError):
            _IRV[k] = None
    return _IRV[k]


def lean_dirs(milestone: str, root: Path | str = ROOT) -> list[LeanDir]:
    """The Lean directories of a milestone: [] for M0 (holon-ir/0.1, I9's path), a test milestone or a milestone
    without laws; else the milestone's own and, when results/<M>/extracted_m1 exists, its window view's."""
    root = Path(root)
    if not _TARGET.fullmatch(milestone) or _ir_version(milestone, root) in (None, "holon-ir/0.1"):
        return []
    out = [_own_dir(milestone)]
    if (root / "results" / milestone / VIEW).is_dir():
        out.append(_view_dir(milestone))
    return out


def lean_dir_of(key: str) -> LeanDir:
    """The LeanDir of a dir key ("M<n>" or "M<n>/extracted_m1")."""
    m, _, rest = key.partition("/")
    if not _TARGET.fullmatch(m) or rest not in ("", VIEW):
        raise ValueError(f"{key!r} is not a Lean directory key")
    return _view_dir(m) if rest else _own_dir(m)


def dir_key_for(milestone: str, facts_path, root: Path | str = ROOT) -> str | None:
    """The key of the milestone's Lean directory whose facts document has facts_path's sha256 (matched by content, so
    a regeneration into a scratch directory keeps its key), else the milestone's own; None when no Lean directory
    covers the milestone."""
    root = Path(root)
    ds = lean_dirs(milestone, root)
    if not ds:
        return None
    p = Path(facts_path)
    sha = _file_sha256(p) if p.is_file() else None
    for d in ds:
        if d.facts and sha and (root / d.facts).is_file() and _file_sha256(root / d.facts) == sha:
            return d.key
    return ds[0].key


def main_theorem(law_id: str, status: str) -> str:
    """The theorem carrying a verdict: the law (PROVED) or its counter-law (REFUTED)."""
    return law_id if status == "PROVED" else f"{law_id}_counter"


def _attempted(status: str | None, kind: str) -> bool:
    return status == "PROVED" or (status == "REFUTED" and kind in LC.KINDS)


def _stem(facts_path: Path, facts: dict, kind: str) -> str:
    """The Bend model's stem: a linked document's role; else the facts file's stem, as holon names the model file."""
    if kind == "linked" and isinstance(facts.get("role"), str):
        return facts["role"]
    return re.sub(r"[^A-Za-z0-9_]", "_", Path(facts_path).stem) or "model"


def _load_json(p: Path, cache: dict | None = None):
    k = str(p)
    if cache is not None and k in cache:
        return cache[k]
    v = json.loads(Path(p).read_text(encoding="utf-8"))
    if cache is not None:
        cache[k] = v
    return v


@dataclass
class Item:
    """One law of a Lean directory (rule L0), from the committed record. law: for the view, rebound to the view's
    facts sha256 (as the view's run states it, gap LP-G8)."""
    d: LeanDir
    law_id: str
    law: dict
    record: dict
    status: str | None
    kind: str
    facts_path: Path
    facts: dict
    stem: str
    attempted: bool

    @property
    def main(self) -> str:
        return main_theorem(self.law_id, self.status)


def _registry_facts(laws_rel: str, root: Path) -> str | None:
    p = Path(root) / laws_rel / "REGISTRY.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("facts")
    except (OSError, ValueError):
        return None


def items(d: LeanDir, root: Path | str = ROOT) -> list[Item]:
    """Every record of the directory, in law-id order, read from the committed records under root."""
    from . import ir
    root = Path(root)
    cache: dict = {}
    reg_facts = _registry_facts(d.laws, root)
    out = []
    for p in ir.record_files(root / d.records):
        lid = p.stem
        rec = _load_json(p)
        lp = root / d.laws / f"{lid}.json"
        if not lp.is_file():
            raise LeanDirError(f"{d.records}/{p.name} has no law file {d.laws}/{lid}.json")
        law = _load_json(lp)
        rel = d.facts or law.get("facts") or reg_facts
        fp = root / rel
        facts = _load_json(fp, cache)
        if d.facts:
            law = ir.rebind_facts(law, _file_sha256(fp))
        kind = LC.model_kind(facts, law)
        status = rec.get("status")
        out.append(Item(d, lid, law, rec, status, kind, fp, facts, _stem(fp, facts, kind), _attempted(status, kind)))
    return out


def _statement_hash(it: Item, root: Path) -> str | None:
    """The statement identity a report binds a check to: the law's registry hash; for the view, the hash of the law
    rebound to the view's facts (LP-G8; a holon-ir/0.3 statement hash needs the Bend side's refs, so a 0.3 view law
    keeps its record's)."""
    from . import ir
    if it.d.facts:
        return ir.statement_hash(it.law) if it.law.get("ir_version") != "holon-ir/0.3" else \
            it.record.get("statement_hash")
    p = Path(root) / it.d.laws / "REGISTRY.json"
    try:
        reg = json.loads(p.read_text(encoding="utf-8")).get("statements") or {}
    except (OSError, ValueError):
        reg = {}
    return reg.get(it.law_id, it.record.get("statement_hash"))


# ------------------------------------------------------------------ the inputs an emitter reads besides the facts
def _oracle_params(milestone: str, facts_rel: str, root: Path) -> dict[str, str]:
    """{name: Fn type} of the modelled oracle parameters of a machine_oracle model, in sidecar order: the facts' own
    sidecar <facts dir>/../lib/oracles.json when there is one, else spec/<M>/lib/oracles.json when its "facts" list
    names the document (as the Bend side chooses it, holon.gen.oracles.Oracles.for_milestone)."""
    own = (Path(root) / facts_rel).parent.parent / "lib" / "oracles.json"
    doc = None
    if own.is_file():
        doc = _load_json(own)
    else:
        p = Path(root) / "spec" / milestone / "lib" / "oracles.json"
        if p.is_file():
            got = _load_json(p)
            if facts_rel in (got.get("facts") or []):
                doc = got
    if doc is None:
        return {}
    return {o["parameter"]["name"]: o["parameter"]["type"] for o in doc.get("oracles") or []
            if o.get("status") == "modelled" and isinstance(o.get("parameter"), dict)}


def _laws_over(d: LeanDir, facts_rel: str, root: Path) -> list[dict]:
    """Every law of the directory's laws, of any status, whose facts document is facts_rel (for the view: the laws
    over the registry's facts, which the view stands for)."""
    from . import ir
    reg_facts = _registry_facts(d.laws, root)
    out = []
    for law in ir.load_laws_any(Path(d.laws).name, root):
        own = law.get("facts") or reg_facts
        eff = d.facts if (d.facts and own == reg_facts) else own
        if eff == facts_rel:
            out.append(law)
    return out


# ------------------------------------------------------------------ emission
_MODELS: dict = {}


def _build_model(d: LeanDir, law: dict, facts_path: Path, facts: dict, kind: str, root: Path):
    """(Model, context, site entries) of a directory's model of one facts document. context: the machine Ctx, or the
    codec document for the linked kind; site entries: the SORT-site derivation entries over the document
    (holon.gen.lean_sites.inputs: <laws dir>/DERIVATION.json and the sort sites sidecar), machine_oracle only."""
    stem = _stem(facts_path, facts, kind)
    if kind == "linked":
        from .gen import lean_linked
        return lean_linked.model(facts, stem), facts, []
    if kind not in ("machine", "machine_oracle"):
        raise LC.Unsupported(f"no Lean emitter covers model kind {kind!r} (rule L1)")
    from .gen import lean_machine, lean_mlaws, lean_sites
    rel = d.facts or law.get("facts") or _registry_facts(d.laws, root)
    anchor = law.get("facts") or _registry_facts(d.laws, root)
    params = _oracle_params(d.milestone, rel, root) if kind == "machine_oracle" else {}
    ctx = lean_machine.Ctx(facts, kind, params, lean_machine.lib_twin(Path(root) / anchor, Path(root)), stem)
    views = sorted({v for x in _laws_over(d, rel, root) for v in lean_mlaws.views(x)})
    entries: list[dict] = []
    sites: list[str] = []
    if kind == "machine_oracle":   # the site declarations, and the oracle instances a site witness names
        entries, sidecar = lean_sites.inputs(Path(root), Path(d.laws).name, rel)
        sites = list(lean_sites.section(ctx, entries, sidecar))
    return lean_machine.model(ctx, views, sites), ctx, entries


def _model_of(d: LeanDir, law: dict, facts_path: Path, facts: dict, kind: str, root: Path):
    """_build_model, cached per process by (dir, facts sha256, kind, root, the law's facts); an Unsupported model is
    cached too and raised again for every law over it."""
    root = Path(root)
    k = (d.key, _file_sha256(facts_path), kind, str(root.resolve()), law.get("facts"))
    if k not in _MODELS:
        try:
            _MODELS[k] = _build_model(d, law, facts_path, facts, kind, root)
        except LC.Unsupported as e:
            _MODELS[k] = e
    got = _MODELS[k]
    if isinstance(got, LC.Unsupported):
        raise LC.Unsupported(str(got))
    return got


def _law_file(d: LeanDir, law: dict, record: dict, facts_path: Path, facts: dict, root: Path) -> LC.LawFile:
    """The law file of one attempted law, dispatched by its model kind and Lean class; raises Unsupported. A machine
    law with a site term (or of rule SORT, sub-form site) goes to holon.gen.lean_sites with its derivation entry,
    whatever its status; any other machine law to holon.gen.lean_mproofs; a linked law to holon.gen.lean_linked."""
    status = record.get("status")
    kind = LC.model_kind(facts, law)
    model, ctx, entries = _model_of(d, law, facts_path, facts, kind, root)
    cls = LC.lean_class(record)
    lid = law["law_id"]
    if kind == "linked":
        from .gen import lean_linked
        stmts = lean_linked.statements(law, status, ctx)
        thms = lean_linked.theorems(cls, law, status, record, ctx, stmts)
    else:
        from .gen import lean_mlaws, lean_mproofs, lean_sites
        stmts = lean_mlaws.statements(law, status, ctx)
        if lean_mlaws.site_ids(law) or (law.get("rule"), law.get("subform")) == ("SORT", "site"):
            thms = lean_sites.theorems(cls, law, status, record, ctx, stmts, lean_sites.site_entry(entries, lid))
        else:
            thms = lean_mproofs.theorems(cls, law, status, record, ctx, stmts)
    return LC.LawFile(lid, model, tuple(thms), main_theorem(lid, status), cls)


def emit_one(key: str, law: dict, facts_path, record: dict, root: Path | str = ROOT) -> LC.LawFile:
    """The law file of one law of Lean directory `key` over the facts document at facts_path, for the record's
    status, witness, witnesses and attempts; raises lean_common.Unsupported."""
    fp = Path(facts_path)
    return _law_file(lean_dir_of(key), law, record, fp, _load_json(fp), Path(root))


def emitter_context(key: str, law: dict, facts_path, root: Path | str = ROOT):
    """What the statement emitters take for a law of Lean directory `key`: the lean_machine Ctx (machine kinds) or
    the codec document (linked); raises lean_common.Unsupported (G7's flip canary renders statements with it)."""
    fp = Path(facts_path)
    facts = _load_json(fp)
    return _model_of(lean_dir_of(key), law, fp, facts, LC.model_kind(facts, law), Path(root))[1]


def item_statements(item: Item, law: dict | None = None, flip: bool = False,
                    root: Path | str = ROOT) -> list[tuple[str, str]]:
    """[(theorem name, statement text)] of an item, rendered with the Ctx (machine kinds) or codec document (linked)
    that emit uses for it; law, when given, replaces the item's IR (G7's perturb canary passes the perturbed copy);
    flip renders a REFUTED law's counter-law with its claim's relation flipped (G7's flip canary). Raises
    lean_common.Unsupported."""
    ctx = _model_of(item.d, item.law, item.facts_path, item.facts, item.kind, Path(root))[1]
    ir_ = item.law if law is None else law
    if item.kind == "linked":
        from .gen import lean_linked
        return lean_linked.statements(ir_, item.status, ctx, flip=flip)
    from .gen import lean_mlaws
    return lean_mlaws.statements(ir_, item.status, ctx, flip=flip)


def law_source(d: LeanDir, law_id: str) -> str:
    return f"{d.lean}/{law_id}.lean"


def model_source(d: LeanDir, stem: str) -> str:
    return f"{d.lean}/{MODELS}/{stem}.lean"


def _emission(d: LeanDir, root: Path, lenient: bool = False):
    """([(item, LawFile | None, why)], {stem: Model}) over the directory's attempted items. why: the Unsupported
    message. lenient (--emit-only): an emitter's crash is not raised but kept as that law's why ("emitter error: ..."),
    and its model is left out."""
    root = Path(root)
    laws, models = [], {}
    crash = Exception if lenient else ()
    for it in items(d, root):
        if not it.attempted:
            continue
        try:
            m = _model_of(d, it.law, it.facts_path, it.facts, it.kind, root)[0]
            if m.stem in models and models[m.stem] != m:
                raise LeanDirError(f"{d.key}: two different models named {m.stem}")
            models[m.stem] = m
        except LeanDirError:
            raise
        except LC.Unsupported:
            pass
        except crash:
            pass
        try:
            laws.append((it, _law_file(d, it.law, it.record, it.facts_path, it.facts, root), None))
        except LC.Unsupported as e:
            laws.append((it, None, str(e) or "unsupported"))
        except crash as e:
            laws.append((it, None, f"emitter error: {type(e).__name__}: {e}"))
    return laws, dict(sorted(models.items()))


def emit(d: LeanDir, root: Path | str = ROOT) -> tuple[dict, dict]:
    """(law id -> LawFile, or "unsupported_form: <why>"; stem -> Model) for a directory's attempted laws (documents
    only: no Lean, no report). The models are those of its attempted laws."""
    laws, models = _emission(d, Path(root))
    return {it.law_id: (lf if lf is not None else f"unsupported_form: {why}") for it, lf, why in laws}, models


def _texts(d: LeanDir, laws: list, models: dict) -> dict[str, str]:
    """Repo-relative path -> text of every file the emission writes into a Lean directory."""
    out = {law_source(d, it.law_id): lf.text() for it, lf, _ in laws if lf is not None}
    out.update({model_source(d, st): m.text() for st, m in models.items()})
    return out


# ------------------------------------------------------------------ checking and reading the outcome
_LEAN_ERROR_LINE = re.compile(r"^(?:error(?:\([^)]*\))?: \S+\.lean:(\d+):\d+: |"
                              r"\S+\.lean:(\d+):\d+: error(?:\([^)]*\))?: )")
_MESSAGE_START = re.compile(r"^(?:(?:error|warning|info|trace)(?:\([^)]*\))?: |\S+\.lean:\d+:\d+: |✖ |⚠ |✔ |"
                            r"Some required targets )")
DETAIL_MAX = 1000


def lean_error_blocks(out: str) -> list[tuple[int, str]]:
    """Lean's error messages in a check's output, each as (its line in the checked file, its text up to the next
    message)."""
    blocks, cur = [], None
    for ln in out.splitlines():
        if _MESSAGE_START.match(ln):
            if cur is not None:
                blocks.append(cur)
            cur = None
            m = _LEAN_ERROR_LINE.match(ln)
            if m:
                cur = (int(m.group(1) or m.group(2)), [ln])
        elif cur is not None:
            cur[1].append(ln)
    if cur is not None:
        blocks.append(cur)
    return [(n, "\n".join(b).strip()) for n, b in blocks]


def _short(s: str) -> str:
    s = (s or "").strip()
    return s if len(s) <= DETAIL_MAX else s[:DETAIL_MAX] + " [truncated]"


def _audit_from(text: str) -> int:
    """The first line of the axiom audit check_text appends (the checked file's own lines come before it)."""
    return len(text.rstrip("\n").split("\n")) + 1


def classify(r: dict) -> tuple[str, str | None, str | None]:
    """(result, reason, detail) of a lean4 entry from a check (rule L8): checked; not_run with reason timeout (over
    the budget, or no verdict in time), recursion_depth or heartbeats (every Lean error in the checked file is that
    limit's own message), unsupported_form (an emitter's Unsupported), toolchain_unavailable or no_report; failed for
    any other outcome (a Lean rejection, a forbidden word, bad axioms, a missing theorem), with the first error."""
    res, out = r.get("result"), r.get("out") or ""
    if res == "checked":
        return "checked", None, None
    if res == "unsupported":
        return "not_run", "unsupported_form", _short(r.get("detail") or out) or "an emitter cannot express this law"
    if res == "no_report":
        return "not_run", "no_report", _short(r.get("detail") or out) or "no Lean report checked this text"
    if res == "unavailable":
        return "not_run", "toolchain_unavailable", _short(out.splitlines()[0] if out else "") or \
            "the pinned Lean toolchain is not available"
    if res == "timeout":
        return "not_run", "timeout", _short(r.get("detail")) or "Lean gave no verdict within the budget"
    errs = lean_error_blocks(out)
    if res == "rejected":
        mine = [b for n, b in errs if n < r.get("audit_from", 1 << 30)]
        why = [next((k for k, rx in RESOURCE_LIMITS if rx.search(b)), None) for b in mine]
        if mine and all(why):
            return "not_run", why[0], _short(mine[0].splitlines()[0])
        return "failed", None, _short(errs[0][1] if errs else first_error_block(out) or _first_error(out, 6))
    if res == "missing_theorem":
        miss = sorted(t for t, a in (r.get("theorems") or {}).items() if a is None)
        main = r.get("main")
        detail = f"theorems without an axiom audit: {miss}" if miss else "the file declares no theorem"
        if main and main not in (r.get("theorems") or {}):
            detail = f"the verdict's theorem {main} is not declared"
        return "failed", None, detail
    if res == "bad_axioms":
        return "failed", None, f"axioms {r.get('axioms')} outside {sorted(ALLOWED_AXIOMS)}"
    return "failed", None, _short(out) or f"Lean result {res}"


def declared_theorems(src: str) -> list[str]:
    """Every theorem a Lean file declares, qualified by the namespace it is declared in (so the axiom audit, which
    runs after the file, names a theorem of the model section Model.<name>)."""
    names, ns = [], []
    for ln in strip_comments(src).split("\n"):
        m = re.match(r"namespace\s+([A-Za-z_][A-Za-z0-9_.]*)\s*$", ln)
        if m:
            ns.append(m.group(1))
            continue
        m = re.match(r"end\s+([A-Za-z_][A-Za-z0-9_.]*)\s*$", ln)
        if m and ns and ns[-1] == m.group(1):
            ns.pop()
            continue
        m = re.match(r"theorem\s+([A-Za-z_][A-Za-z0-9_.]*)", ln)
        if m:
            names.append(".".join(ns + [m.group(1)]))
    return names


def _within_budget(r: dict, cfg: dict) -> dict:
    budget = cfg["budget_s_per_file"]
    if r["result"] == "checked" and r["seconds"] > budget:
        return {**r, "result": "timeout", "detail": f"Lean needed more than the budget of {budget:g} s per file"}
    if r["result"] == "timeout":
        return {**r, "detail": f"Lean gave no verdict within {cfg['timeout_s']:g} s"}
    return r


def _checked(r: dict) -> dict:
    res, reason, detail = classify(r)
    out = {k: v for k, v in r.items() if k not in ("reason", "detail")}
    out["kernel_result"] = res
    if reason:
        out["reason"] = reason
    if detail:
        out["detail"] = detail
    return out


def check_law(text: str, tmpdir, main: str, cfg: dict | None = None) -> dict:
    """Check one law file (check_text in a fresh lake project, the verdict's theorem `main` expected), within the
    budget: check_text's result ("timeout" when over the budget), axioms, theorems, seconds and out, plus
    kernel_result, reason and detail as classify reads them."""
    cfg = cfg or config()
    r = check_text(text, tmpdir, expect=[main], cfg=cfg, names=declared_theorems(text), strict=True)
    r = _within_budget(r, cfg)
    return _checked({**r, "main": main, "audit_from": _audit_from(text)})


def check_model(text: str, tmpdir, cfg: dict | None = None) -> dict:
    """Check one model file: accepted when Lean elaborates it with no error, within the budget (a model needs no
    theorem; any it declares is audited)."""
    cfg = cfg or config()
    names = declared_theorems(text)
    r = check_text(text, tmpdir, cfg=cfg, names=names, strict=True)
    if r["result"] == "missing_theorem" and not names:
        r = {**r, "result": "checked"}
    r = _within_budget(r, cfg)
    return _checked({**r, "audit_from": _audit_from(text)})


def load_dir_report(d: LeanDir, root: Path | str = ROOT) -> dict | None:
    """<root>/<d.lean>/report.json (the committed report; never one under a --gen-dir)."""
    try:
        rep = json.loads((Path(root) / d.lean / REPORT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return rep if isinstance(rep, dict) else None


# ------------------------------------------------------------------ what records may claim (I43, rule L8)
def kernel_entry_v2(key: str | None, law: dict, facts_path, record: dict, root: Path | str = ROOT) -> dict | None:
    """The lean4 entry of a record's kernels[] for a law of Lean directory `key` (None: no Lean directory covers the
    run). None for a record that is not attempted (UNKNOWN; REFUTED over a model kind no emitter covers) and for a
    test milestone. checked only when the directory's committed report checked exactly the text emitted now, with
    the same verdict, statement hash and main theorem, and allowed axioms; not_run with the report's resource or
    toolchain reason, unsupported_form when an emitter cannot express the law, no_report when no report backs the
    text; failed for any other Lean outcome."""
    status = record.get("status")
    if key is None or status not in ("PROVED", "REFUTED"):
        return None
    d = lean_dir_of(key)
    if not _TARGET.fullmatch(d.milestone) or not _TARGET.fullmatch(str(law.get("milestone") or d.milestone)):
        return None
    fp = Path(facts_path)
    facts = _load_json(fp)
    kind = LC.model_kind(facts, law)
    if not _attempted(status, kind):
        return None
    lid = law["law_id"]
    entry = {"name": "lean4", "version": LEAN_VERSION, "role": "second-independent",
             "theorem": main_theorem(lid, status)}
    if kind in LC.READINGS:
        entry["reading"] = LC.READINGS[kind]
    try:
        lf = _law_file(d, law, record, fp, facts, Path(root))
    except LC.Unsupported as e:
        return {**entry, "result": "not_run", "reason": "unsupported_form",
                "detail": _short(str(e)) or "an emitter cannot express this law"}
    sha = sha256_text(lf.text())
    entry.update({"source": law_source(d, lid), "source_sha256": sha, "theorem": lf.main})
    rep = load_dir_report(d, root)
    r = ((rep or {}).get("laws") or {}).get(lid)
    if not rep or rep.get("lean_version") != LEAN_VERSION or rep.get("dir") != d.key or not isinstance(r, dict):
        return {**entry, "result": "not_run", "reason": "no_report",
                "detail": f"no Lean report for this law in {d.lean}/{REPORT} "
                          f"(run holon lean --milestone {d.milestone})"}
    if (r.get("source_sha256") != sha or r.get("verdict") != status
            or r.get("statement_hash") != record.get("statement_hash") or r.get("main") != lf.main):
        return {**entry, "result": "not_run", "reason": "no_report",
                "detail": f"the Lean report {d.lean}/{REPORT} is stale for this law: it checked another text, verdict, "
                          f"statement or theorem (run holon lean --milestone {d.milestone})"}
    if r.get("result") == "checked":
        ax = sorted(r.get("axioms") or [])
        if set(ax) <= ALLOWED_AXIOMS:
            return {**entry, "result": "checked", "axioms": ax}
        return {**entry, "result": "failed", "note": "Lean result bad_axioms",
                "detail": f"axioms {ax} outside {sorted(ALLOWED_AXIOMS)}"}
    if r.get("reason") in LC.ALLOWED_REASONS:
        return {**entry, "result": "not_run", "reason": r["reason"],
                "detail": _short(r.get("detail")) or f"Lean result {r.get('result')}"}
    return {**entry, "result": "failed", "note": f"Lean result {r.get('result')}",
            "detail": _short(r.get("detail")) or f"Lean result {r.get('result')}"}


# ------------------------------------------------------------------ the runner
def _write_dir(d: LeanDir, root: Path, texts: dict[str, str], report: dict | None) -> None:
    """Make the Lean directory hold exactly the emitted files (and the report): .lean files not emitted now are
    removed; without a report (--emit-only) an existing report.json stays."""
    base = root / d.lean
    if report is not None and base.exists():
        shutil.rmtree(base)
    elif base.exists():
        for p in sorted(base.rglob("*.lean")):
            if p.relative_to(root).as_posix() not in texts:
                p.unlink()
    for rel, text in sorted(texts.items()):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
    if report is not None:
        base.mkdir(parents=True, exist_ok=True)
        (base / REPORT).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _check_dir(d: LeanDir, root: Path, texts: dict[str, str]) -> list[str]:
    """--check: the problems of the committed .lean files against the re-emission."""
    have = {p.relative_to(root).as_posix(): p for p in sorted((root / d.lean).rglob("*.lean"))} \
        if (root / d.lean).is_dir() else {}
    bad = [f"{rel}: not emitted now" for rel in sorted(set(have) - set(texts))]
    bad += [f"{rel}: missing" for rel in sorted(set(texts) - set(have))]
    bad += [f"{rel}: differs from its re-emission" for rel in sorted(set(texts) & set(have))
            if have[rel].read_bytes() != texts[rel].encode("utf-8")]
    return bad


def run_dirs(milestone: str, root: Path | str = ROOT, jobs: int = 1, log=print, mode: str = "run",
             out: dict | None = None) -> int:
    """`holon lean --milestone <M>` for M1 onward. mode "run": emit, check every model and law file in Lean, then
    rewrite each Lean directory and its report (exit 0 iff every file is checked); "check": compare the committed
    .lean files with the re-emission (exit 0 iff equal, no Lean); "emit-only": write the .lean files, no report, no
    Lean (exit 0). out, when given, receives the printed report (with timings; never committed)."""
    root = Path(root).resolve()
    out = out if out is not None else {}
    out.update({"milestone": milestone, "mode": mode, "dirs": {}})
    plans = []
    for d in lean_dirs(milestone, root):
        laws, models = _emission(d, root, lenient=mode == "emit-only")
        plans.append((d, laws, models, _texts(d, laws, models)))
    if mode == "check":
        rc = 0
        for d, laws, models, texts in plans:
            bad = _check_dir(d, root, texts)
            out["dirs"][d.key] = {"files": len(texts), "problems": bad}
            for b in bad:
                log(f"{d.key}: {b}")
            log(f"{d.key}: {len(texts)} Lean files re-emitted under {d.lean}; "
                + ("the committed files are their re-emission" if not bad else f"{len(bad)} problems"))
            rc = rc or (1 if bad else 0)
        return rc
    if mode == "emit-only":
        for d, laws, models, texts in plans:
            for it, lf, why in laws:
                if lf is None:
                    log(f"warning: {d.key}: {it.law_id}: no Lean file ({why})")
            _write_dir(d, root, texts, None)
            out["dirs"][d.key] = {"written": sorted(texts),
                                  "unsupported": {it.law_id: why for it, lf, why in laws if lf is None}}
            log(f"{d.key}: wrote {len(texts)} Lean files under {d.lean} (no report)")
        return 0
    cfg = config(root)
    ok, version = toolchain_ok(cfg)
    fp = fingerprint(cfg)["fingerprint"] if ok else None
    tmp = Path(tempfile.mkdtemp(prefix="holon-lean-"))
    jobs_ = []
    for d, laws, models, texts in plans:
        for st, m in models.items():
            jobs_.append(("model", d, st, texts[model_source(d, st)], None))
        for it, lf, why in laws:
            if lf is not None:
                jobs_.append(("law", d, it.law_id, texts[law_source(d, it.law_id)], lf.main))

    def one(ix_job):
        ix, (what, d, name, text, main) = ix_job
        if not ok:
            return _checked({"result": "unavailable", "axioms": [], "theorems": {}, "seconds": 0.0,
                             "out": f"Lean is not the pinned toolchain: {version}"})
        t = tmp / f"{ix:05d}"
        return check_model(text, t, cfg) if what == "model" else check_law(text, t, main, cfg)

    try:
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
            results = list(ex.map(one, enumerate(jobs_)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    done = {(j[0], j[1].key, j[2]): r for j, r in zip(jobs_, results)}
    rc = 0
    for d, laws, models, texts in plans:
        report = {"dir": d.key, "milestone": d.milestone, "kernel": "lean4", "lean_version": cfg["pinned_version"],
                  "toolchain": cfg["toolchain"], "fingerprint": fp, "allowed_axioms": sorted(ALLOWED_AXIOMS),
                  "laws": {}, "models": {}}
        cli = {"laws": {}, "models": {}}
        for st, m in models.items():
            r = done[("model", d.key, st)]
            text = texts[model_source(d, st)]
            report["models"][st] = {"source": model_source(d, st), "source_sha256": sha256_text(text),
                                    "result": r["result"]}
            cli["models"][st] = {"result": r["result"], "seconds": r["seconds"],
                                 **({"detail": r["detail"]} if r.get("detail") else {})}
            rc = rc or (0 if r["result"] == "checked" else 1)
            log(f"{d.key:18s} model {st:40s} lean4 {r['result']:10s} {r['seconds']:7.2f} s")
        for it, lf, why in laws:
            try:
                gen_cls = LC.lean_class(it.record)
            except LC.Unsupported:
                gen_cls = None
            entry = {"verdict": it.status, "statement_hash": _statement_hash(it, root), "main": it.main,
                     "generator": gen_cls}
            if lf is None:
                r = _checked({"result": "unsupported", "axioms": [], "theorems": {}, "seconds": 0.0, "out": "",
                              "detail": why})
                entry.update({"result": "unsupported", "axioms": [], "theorems": {}, "source": None,
                              "source_sha256": None})
            else:
                r = done[("law", d.key, it.law_id)]
                text = texts[law_source(d, it.law_id)]
                entry.update({"result": r["result"], "axioms": r["axioms"], "theorems": r["theorems"],
                              "source": law_source(d, it.law_id), "source_sha256": sha256_text(text),
                              "main": lf.main, "generator": lf.generator})
            for k in ("reason", "detail"):
                if r.get(k):
                    entry[k] = r[k]
            report["laws"][it.law_id] = entry
            cli["laws"][it.law_id] = {"result": r["result"], "lean4": r["kernel_result"], "axioms": r["axioms"],
                                      "seconds": r["seconds"], "verdict": it.status,
                                      **{k: r[k] for k in ("reason", "detail") if r.get(k)}}
            rc = rc or (0 if r["kernel_result"] == "checked" else 1)
            log(f"{d.key:18s} {it.law_id:46s} {str(it.status):8s} lean4 {r['kernel_result']:8s} "
                f"{r.get('reason') or '':16s} {r['seconds']:7.2f} s  axioms {r['axioms']}")
        # written only now, after every check, so an interrupted run never leaves files without their report
        _write_dir(d, root, texts, report)
        out["dirs"][d.key] = cli
    return rc


# ------------------------------------------------------------------ CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon lean")
    ap.add_argument("--milestone", default="M0")
    ap.add_argument("--root")
    ap.add_argument("--json", action="store_true", help="print the report as JSON on stdout")
    ap.add_argument("--jobs", type=int, default=1, help="files checked in parallel (default 1: honest timings)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true",
                   help="M1 onward: re-emit in memory and compare with the committed .lean files (no Lean)")
    g.add_argument("--emit-only", action="store_true",
                   help="M1 onward: write the .lean files from the documents as they are (no Lean, no report)")
    a = ap.parse_args(argv)
    root = Path(a.root or ROOT).resolve()
    log = (lambda s: print(s, file=sys.stderr)) if a.json else print
    if _ir_version(a.milestone, root) == "holon-ir/0.1":   # I9's M0 path, unchanged
        if a.check or a.emit_only:
            print(f"holon lean: refused: --check and --emit-only cover the Lean directories of M1 onward, not "
                  f"{a.milestone}", file=sys.stderr)
            return 2
        rep = run(a.milestone, root, a.jobs, log)
        if a.json:
            print(json.dumps(rep, indent=2, sort_keys=True))
        return 0 if rep["laws"] and all(r["result"] == "checked" for r in rep["laws"].values()) else 1
    if not lean_dirs(a.milestone, root):
        print(f"holon lean: refused: no Lean directory covers {a.milestone} (a target milestone with holon-ir/0.2 or "
              f"0.3 laws)", file=sys.stderr)
        return 2
    mode = "check" if a.check else "emit-only" if a.emit_only else "run"
    rep: dict = {}
    try:
        rc = run_dirs(a.milestone, root, a.jobs, log, mode, rep)
    except LeanDirError as e:
        print(f"holon lean: refused: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(rep, indent=2, sort_keys=True))
    return rc
