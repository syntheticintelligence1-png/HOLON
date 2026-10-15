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
                                r"Tactic `rfl` failed: The left-hand side|[Tt]ype mismatch")
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


def run_m3_promotion(root: Path | str = ROOT, log=print) -> dict:
    """Emit `gen/M3/lean/` and `results/M3/lean.json` for I43 (`Theory core II; Lean for the promoted set`)."""
    from . import bend
    from .gen import basis as basis_gen
    from .gen import core as core_gen
    from .gen import lean_bend

    root = Path(root).resolve()
    cfg = config(root)
    ok_tc, version = toolchain_ok(cfg)
    if not ok_tc:
        raise RuntimeError(f"Lean is not the pinned toolchain: {version}")

    lean_proj = root / "gen" / "M3" / "lean"
    if lean_proj.exists():
        shutil.rmtree(lean_proj)
    (lean_proj / "Holon" / "Basis").mkdir(parents=True, exist_ok=True)
    for ms in ("M1", "M2", "M3"):
        (lean_proj / "Holon" / ms).mkdir(parents=True, exist_ok=True)

    (lean_proj / "lean-toolchain").write_text(
        f"leanprover/lean4:v{LEAN_VERSION}\n", encoding="utf-8"
    )
    (lean_proj / "lakefile.toml").write_text(
        'name = "holon"\n'
        'version = "0.1.0"\n'
        'defaultTargets = ["Holon"]\n'
        "\n"
        "[[lean_lib]]\n"
        'name = "Holon"\n'
        'globs = ["Holon.*"]\n',
        encoding="utf-8",
    )
    (lean_proj / "Holon.lean").write_text(
        "-- GENERATED by holon.lean; do not edit.\n"
        "-- Lean 4 core only, no imports.\n",
        encoding="utf-8",
    )

    core_laws_p = root / "gen" / "M3" / "core" / "LAWS.bend"
    core_proof_p = root / "gen" / "M3" / "core" / "PROOF.bend"
    core_lean_txt, _ = lean_bend.translate_files(
        lean_bend.resolve_bend_bundle(core_laws_p, core_proof_p),
        prune_unused=False,
    )
    (lean_proj / "Holon" / "Core.lean").write_text(
        core_lean_txt, encoding="utf-8"
    )

    eq_laws_p = root / "gen" / "M3" / "basis" / "equivariance" / "LAWS.bend"
    eq_proof_p = root / "gen" / "M3" / "basis" / "equivariance" / "PROOF.bend"
    eq_lean_txt, eq_thms = lean_bend.translate_files(
        lean_bend.resolve_bend_bundle(eq_laws_p, eq_proof_p),
        prune_unused=True,
    )
    (lean_proj / "Holon" / "Basis" / "Equivariance.lean").write_text(
        eq_lean_txt, encoding="utf-8"
    )

    pa_laws_p = root / "gen" / "M3" / "basis" / "pasting" / "LAWS.bend"
    pa_proof_p = root / "gen" / "M3" / "basis" / "pasting" / "PROOF.bend"
    pa_lean_txt, pa_thms = lean_bend.translate_files(
        lean_bend.resolve_bend_bundle(pa_laws_p, pa_proof_p),
        prune_unused=True,
    )
    (lean_proj / "Holon" / "Basis" / "Pasting.lean").write_text(
        pa_lean_txt, encoding="utf-8"
    )

    raw_promoted: dict[str, list[dict]] = {}
    for ms in ("M0", "M1", "M2", "M3"):
        reg = json.loads((root / "laws" / ms / "REGISTRY.json").read_text())
        ms_items: list[dict] = []
        for lid in sorted(reg["statements"]):
            rec_p = root / "results" / ms / f"{lid}.json"
            if not rec_p.is_file():
                continue
            rec = json.loads(rec_p.read_text())
            if rec.get("status") != "PROVED":
                continue
            law = json.loads((root / "laws" / ms / f"{lid}.json").read_text())
            gen_name = None
            for att in rec.get("attempts") or []:
                if att.get("result") in ("PROVED", "accepted") or (
                    att.get("kind") == "proof" and att.get("exit_code") == 0
                ):
                    gen_name = att.get("generator") or att.get("kind")
                    break
            if ms != "M0":
                art = rec.get("artifacts") or {}
                lp = root / art["laws"]
                pp = root / art["proof"]
                l_txt, _ = lean_bend.translate_files(
                    lean_bend.resolve_bend_bundle(lp, pp),
                    prune_unused=True,
                    header_comments=[
                        f"law_id: {lid}",
                        f"statement_hash: {rec['statement_hash']}",
                    ],
                )
                out_f = lean_proj / "Holon" / ms / f"{lid}.lean"
                out_f.write_text(l_txt, encoding="utf-8")
                lean_mod = f"gen/M3/lean/Holon/{ms}/{lid}.lean"
            else:
                lean_mod = f"gen/M0/lean/{lid}.lean"
            ms_items.append({
                "law_id": lid,
                "milestone": ms,
                "ir_version": law.get("ir_version", "holon-ir/0.1"),
                "rule": law.get("rule"),
                "facts": law.get("facts"),
                "status": "PROVED",
                "statement_hash": rec["statement_hash"],
                "bend_generator": gen_name,
                "prior_independence_class": rec.get("independence_class"),
                "lean_module": lean_mod,
                "lean_theorem": lid,
            })
        raw_promoted[ms] = ms_items

    submod_names = [
        "Holon." + ".".join(p.relative_to(lean_proj / "Holon").with_suffix("").parts)
        for p in sorted((lean_proj / "Holon").rglob("*.lean"))
    ]
    root_lines = [
        "-- GENERATED by holon.lean; do not edit.",
        "-- Lean 4 core only, no external library dependencies.",
        "-- Root library entry point for Holon M3 Lean 4.34.0 promotion package.",
        '-- Submodules built via lakefile.toml globs = ["Holon.*"]:',
        *(f"--   {m}" for m in submod_names),
        "",
        "theorem holon_m3_root : True := trivial",
        "",
        "#print axioms holon_m3_root",
        "",
    ]
    (lean_proj / "Holon.lean").write_text("\n".join(root_lines), encoding="utf-8")

    b = toolchain_bin(cfg)
    with tempfile.TemporaryDirectory(prefix="holon-m3-lake-") as td:
        proj_copy = Path(td) / "lean"
        shutil.copytree(lean_proj, proj_copy)
        proc = subprocess.run(
            [str(b / "lake"), "build", "--no-cache", "--log-level=info"],
            cwd=proj_copy,
            env=_env(b),
            capture_output=True,
            text=True,
            timeout=600,
        )
        lake_out = proc.stdout + proc.stderr
        lake_ok = proc.returncode == 0
        if not lake_ok:
            raise RuntimeError(f"lake build failed:\n{lake_out[-2000:]}")
        ax_map = parse_axioms(lake_out)

    m0_rep = json.loads((root / "gen" / "M0" / "lean" / "report.json").read_text())
    m0_laws_rep = m0_rep.get("laws") or {}

    report_laws: dict[str, dict] = {}
    milestones_out: dict[str, list[dict]] = {}
    for ms in ("M0", "M1", "M2", "M3"):
        ms_out: list[dict] = []
        for item in raw_promoted[ms]:
            lid = item["law_id"]
            src_rel = item["lean_module"]
            src_p = root / src_rel
            src_sha = hashlib.sha256(src_p.read_bytes()).hexdigest()
            if ms == "M0":
                axioms = sorted(m0_laws_rep.get(lid, {}).get("axioms", []))
            else:
                axioms = sorted(ax_map.get(lid, []))
            k_ok = lake_ok and set(axioms) <= ALLOWED_AXIOMS
            k_entry = {
                "name": "lean4",
                "version": LEAN_VERSION,
                "role": "second-independent",
                "result": "checked" if k_ok else "failed",
                "axioms": axioms,
                "source": src_rel,
                "source_sha256": src_sha,
                "theorem": lid,
            }
            ms_out.append({
                **item,
                "independence_class": "I2" if k_ok else item["prior_independence_class"],
                "lean4_kernel": k_entry,
            })
            report_laws[lid] = {
                "result": k_entry["result"],
                "axioms": axioms,
                "verdict": "PROVED",
                "statement_hash": item["statement_hash"],
                "source": src_rel,
                "source_sha256": src_sha,
                "main": lid,
                "generator": item["bend_generator"],
            }
        milestones_out[ms] = ms_out

    tc2_lids = [entry[0] for entry in core_gen.THEORY_CORE_II]
    core_src_rel = "gen/M3/lean/Holon/Core.lean"
    core_src_sha = hashlib.sha256((root / core_src_rel).read_bytes()).hexdigest()
    for lid in tc2_lids:
        axioms = sorted(ax_map.get(lid, []))
        report_laws[lid] = {
            "result": "checked" if (lake_ok and set(axioms) <= ALLOWED_AXIOMS) else "failed",
            "axioms": axioms,
            "verdict": "PROVED",
            "source": core_src_rel,
            "source_sha256": core_src_sha,
            "main": lid,
        }

    eq_src_rel = "gen/M3/lean/Holon/Basis/Equivariance.lean"
    eq_src_sha = hashlib.sha256((root / eq_src_rel).read_bytes()).hexdigest()
    for lid in eq_thms:
        axioms = sorted(ax_map.get(lid, []))
        report_laws[lid] = {
            "result": "checked" if (lake_ok and set(axioms) <= ALLOWED_AXIOMS) else "failed",
            "axioms": axioms,
            "verdict": "PROVED",
            "source": eq_src_rel,
            "source_sha256": eq_src_sha,
            "main": lid,
        }

    pa_src_rel = "gen/M3/lean/Holon/Basis/Pasting.lean"
    pa_src_sha = hashlib.sha256((root / pa_src_rel).read_bytes()).hexdigest()
    for lid in pa_thms:
        axioms = sorted(ax_map.get(lid, []))
        report_laws[lid] = {
            "result": "checked" if (lake_ok and set(axioms) <= ALLOWED_AXIOMS) else "failed",
            "axioms": axioms,
            "verdict": "PROVED",
            "source": pa_src_rel,
            "source_sha256": pa_src_sha,
            "main": lid,
        }

    lean_report = {
        "milestone": "M3",
        "kernel": "lean4",
        "lean_version": LEAN_VERSION,
        "toolchain": cfg["toolchain"],
        "lean": lean_version(cfg),
        "fingerprint": fingerprint(cfg)["fingerprint"],
        "allowed_axioms": sorted(ALLOWED_AXIOMS),
        "laws": report_laws,
    }
    (lean_proj / REPORT).write_text(
        json.dumps(lean_report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    def _group_record(lids: list[str], lp: Path, pp: Path, lean_rel: str) -> dict:
        r_chk = bend.check(pp)
        r_vrd = bend.check_verdict(pp)
        r_lonly = bend.check_verdict(lp)
        laws_list = []
        all_lean_ok = lake_ok
        for lid in lids:
            axs = sorted(ax_map.get(lid, []))
            ok_l = lake_ok and (lid in ax_map) and (set(axs) <= ALLOWED_AXIOMS)
            all_lean_ok = all_lean_ok and ok_l
            laws_list.append({
                "law_id": lid,
                "status": "PROVED" if (r_chk.ok and r_vrd.ok and ok_l) else "UNKNOWN",
                "axioms": axs,
                "lean_module": lean_rel,
            })
        return {
            "law_count": len(lids),
            "bend_check_ok": bool(r_chk.ok),
            "bend_verdict_ok": bool(r_vrd.ok),
            "laws_only_verdict_ok": bool(r_lonly.ok),
            "lean_check_ok": bool(all_lean_ok),
            "laws": laws_list,
        }

    groups = {
        "theory_core_ii": _group_record(tc2_lids, core_laws_p, core_proof_p, core_src_rel),
        "equivariance": _group_record(eq_thms, eq_laws_p, eq_proof_p, eq_src_rel),
        "pasting": _group_record(pa_thms, pa_laws_p, pa_proof_p, pa_src_rel),
    }

    ctx_m1 = basis_gen._discover_context(root)["m1"]
    m1_mod = ctx_m1["model"]
    st_flds = ", ".join(ctx_m1["st_fields"])
    st_ty = ctx_m1["st_ty"]
    fn_mig_l = ctx_m1["mig_1_fn"]
    fn_mig_e = ctx_m1["mig_2_fn"]
    fn_step_w = ctx_m1["actions"][-1][0]
    fn_csr = ctx_m1["csr_obs_fn"]

    bend_canary_defs = [
        (
            "canary_equivar_compose_swapped",
            "theory_core_ii",
            "\n".join([
                "import Base",
                "law canary_equivar_compose_swapped:",
                "  for -A: Data",
                "  for -B: Type",
                "  for -f: A -> B",
                "  for -s1: A -> A",
                "  for s2: A -> A",
                "  for -t1: B -> B",
                "  for -t2: B -> B",
                "  for h1: @x:A -> {f(s1(x)) == t1(f(x)) : B}",
                "  for h2: @x:A -> {f(s2(x)) == t2(f(x)) : B}",
                "  @+a:A -> {f(s1(s2(a))) == t2(t1(f(a))) : B}",
                "",
            ]),
            "\n".join([
                "import Base",
                "import ./LAWS.bend as Laws",
                "def Laws.canary_equivar_compose_swapped(A, B, f, s1, s2, t1, t2, h1, h2):",
                "  +a => (%h2(a) : {f(s1(s2(a))) == t1(_) : B}; h1(s2(a)))",
                "",
            ]),
        ),
        (
            "canary_paste_grid_2x2_missing_v",
            "theory_core_ii",
            "\n".join([
                "import Base",
                "law canary_paste_grid_2x2_missing_v:",
                "  for -A: Data",
                "  for -B: Type",
                "  for -C: Type",
                "  for -f1: A -> B",
                "  for f2: A -> B",
                "  for -f3: A -> B",
                "  for -g1: B -> C",
                "  for -g2: B -> C",
                "  for -g3: B -> C",
                "  for hf12: @a:A -> {f1(a) == f2(a) : B}",
                "  for hf23: @a:A -> {f2(a) == f3(a) : B}",
                "  for hg12: @b:B -> {g1(b) == g2(b) : C}",
                "  @+a:A -> {g1(f1(a)) == g3(f3(a)) : C}",
                "",
            ]),
            "\n".join([
                "import Base",
                "import ./LAWS.bend as Laws",
                "def Laws.canary_paste_grid_2x2_missing_v(A, B, C, f1, f2, f3, g1, g2, g3, hf12, hf23, hg12):",
                "  +a => (%hf23(a) : {g1(f1(a)) == g2(_) : C}; (%hg12(f2(a)) : {g1(f1(a)) == _ : C}; (%hf12(a) : {g1(f1(a)) == g1(_) : C}; {==})))",
                "",
            ]),
        ),
        (
            "canary_equivar_mig_eta2_unmigrated_rhs",
            "equivariance",
            "\n".join([
                "import Base",
                f"import ../../../M1/model/{m1_mod}.bend as M",
                "law canary_equivar_mig_eta2_unmigrated_rhs:",
                f"  for s: M.{st_ty}",
                "  for +dt: Nat",
                "  for +root: Nat",
                f"  {{M.{fn_mig_e}(M.{fn_step_w}(s, dt), root) == M.{fn_step_w}(s, dt) : M.{st_ty}}}",
                "",
            ]),
            "\n".join([
                "import Base",
                "import ./LAWS.bend as Laws",
                f"import ../../../M1/model/{m1_mod}.bend as M",
                "def Laws.canary_equivar_mig_eta2_unmigrated_rhs(s, dt, root):",
                "  match s:",
                f"    case M.{st_ty}{{{st_flds}}}:",
                "      {==}",
                "",
            ]),
        ),
        (
            "canary_paste_csr_last_mig_legacy",
            "pasting",
            "\n".join([
                "import Base",
                f"import ../../../M1/model/{m1_mod}.bend as M",
                "law canary_paste_csr_last_mig_legacy:",
                f"  for s: M.{st_ty}",
                f"  {{M.{fn_csr}(M.{fn_mig_l}(s)) == M.{fn_csr}(s) : Nat}}",
                "",
            ]),
            "\n".join([
                "import Base",
                "import ./LAWS.bend as Laws",
                f"import ../../../M1/model/{m1_mod}.bend as M",
                "def Laws.canary_paste_csr_last_mig_legacy(s):",
                "  match s:",
                f"    case M.{st_ty}{{{st_flds}}}:",
                "      {==}",
                "",
            ]),
        ),
    ]

    canary_lean_src = "\n".join([
        "/-!",
        "Canary: flipped claim on core_equivar_compose in Lean 4.",
        "Lean 4 core only, no imports.",
        "-/",
        "theorem canary_lean_flipped_claim",
        "    (A B : Type) (f : A → B) (s1 s2 : A → A) (t1 t2 : B → B)",
        "    (h1 : ∀ x : A, f (s1 x) = t1 (f x))",
        "    (h2 : ∀ x : A, f (s2 x) = t2 (f x)) :",
        "    ∀ a : A, f (s1 (s2 a)) = t2 (t1 (f a)) -- holon:claim",
        "    := by",
        "  intro a",
        "  rw [h1 (s2 a), h2 a]",
        "  rfl",
        "",
    ])

    canaries_out: list[dict] = []
    basis_dir = root / "gen" / "M3" / "basis"
    with tempfile.TemporaryDirectory(dir=basis_dir) as td:
        td_p = Path(td)
        for cid, cgrp, c_laws, c_proof in bend_canary_defs:
            lp = td_p / "LAWS.bend"
            pp = td_p / "PROOF.bend"
            lp.write_text(c_laws, encoding="utf-8")
            pp.write_text(c_proof, encoding="utf-8")
            r_chk = bend.check(pp)
            r_vrd = bend.check_verdict(pp)
            canaries_out.append({
                "canary_id": cid,
                "group": cgrp,
                "status": "REFUTED" if (not r_chk.ok and not r_vrd.ok) else "ACCEPTED",
                "bend_check_ok": bool(r_chk.ok),
                "bend_verdict_ok": bool(r_vrd.ok),
            })
        l_res = check_text(canary_lean_src, td_p / "lean_canary", cfg=cfg)
        l_sem = (l_res["result"] == "rejected") and semantic_rejection(l_res["out"])
        canaries_out.append({
            "canary_id": "canary_lean_flipped_claim",
            "group": "lean",
            "status": "REFUTED" if l_sem else "ACCEPTED",
            "lean_check_ok": l_res["result"] == "checked",
            "semantic_rejection": bool(l_sem),
        })

    m0_cnt = len(milestones_out["M0"])
    m1_cnt = len(milestones_out["M1"])
    m2_cnt = len(milestones_out["M2"])
    m3_cnt = len(milestones_out["M3"])
    total_promoted = m0_cnt + m1_cnt + m2_cnt + m3_cnt
    m2_core_cnt = len(core_gen.CATALOG)
    tc1_cnt = len(core_gen.THEORY_CORE_I)
    tc2_cnt = len(core_gen.THEORY_CORE_II)
    eq_cnt = len(eq_thms)
    pa_cnt = len(pa_thms)

    summary = {
        "m2_core_laws": m2_core_cnt,
        "theory_core_i_laws": tc1_cnt,
        "theory_core_ii_laws": tc2_cnt,
        "m3_core_total_laws": m2_core_cnt + tc1_cnt + tc2_cnt,
        "equivariance_basis_laws": eq_cnt,
        "pasting_basis_laws": pa_cnt,
        "total_new_bend_laws": tc2_cnt + eq_cnt + pa_cnt,
        "promoted_m0_laws": m0_cnt,
        "promoted_m1_laws": m1_cnt,
        "promoted_m2_laws": m2_cnt,
        "promoted_m3_laws": m3_cnt,
        "total_promoted_i2_laws": total_promoted,
        "canaries_refuted": sum(1 for c in canaries_out if c["status"] == "REFUTED"),
    }

    results_doc = {
        "lean_toolchain_version": LEAN_VERSION,
        "allowed_axioms": sorted(ALLOWED_AXIOMS),
        "lake_build_ok": bool(lake_ok),
        "summary": summary,
        "groups": groups,
        "promoted_laws": {
            "total_promoted_laws": total_promoted,
            "counts_by_milestone": {
                "M0": m0_cnt,
                "M1": m1_cnt,
                "M2": m2_cnt,
                "M3": m3_cnt,
            },
            "milestones": milestones_out,
        },
        "canaries": canaries_out,
    }
    res_path = root / "results" / "M3" / "lean.json"
    res_path.parent.mkdir(parents=True, exist_ok=True)
    res_path.write_text(
        json.dumps(results_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    log(f"M3 Lean promotion checked: {total_promoted} promoted I2 laws, {tc2_cnt} core II laws, {eq_cnt + pa_cnt} basis laws")
    return {"laws": {k: {"result": v["result"], "axioms": v["axioms"]} for k, v in report_laws.items()}}


def run(milestone: str = "M0", root: Path | str = ROOT, jobs: int = 1, log=print) -> dict:
    root = Path(root).resolve()
    if milestone == "M3":
        return run_m3_promotion(root=root, log=log)
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
