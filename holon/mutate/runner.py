"""M2 A1 mutation-adequacy runner. See spec/M2/mutants.json for the contract."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from .. import mpipeline, pipeline
from ..assemble.header import (M1_HEADER_FACTS, M1_HEADER_LAWS, assemble,
                               facts_sha256, write_docs)
from ..frontends.solidity import layout_extract

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK = Path.home() / "work" / "holon-mut"


class CompileError(RuntimeError):
    """A compile failure of the mutated target — the ONLY route to `invalid`."""


ROLLUP_FACTS = "spec/M1/facts/morph_rollup.json"

# Laws whose extracted-baseline status diverges from results/M1 because their
# counter-models need requires the AST cannot justify (S1 PR #16).
BASELINE_MISMATCH_REASONS = {
    "L_disch_delay_wait": "extracted baseline lacks requires the AST cannot justify (S1 PR #16)",
    "L_nat_eta2": "extracted baseline lacks requires the AST cannot justify (S1 PR #16)",
    "L_sort_remaining": "extracted baseline lacks requires the AST cannot justify (S1 PR #16)",
    "L_sym_omega": "extracted baseline lacks requires the AST cannot justify (S1 PR #16)",
}


def _s1():
    """S1's Solidity transition extractor; ImportError => pending_extractor."""
    from ..frontends.solidity import astload, extract as s1extract
    return astload, s1extract


def _s1_available() -> bool:
    try:
        _s1()
        return True
    except ImportError:
        return False


def _rollup_law_ids() -> set:
    """M1 laws bound to the rollup facts file (derived, not hard-coded)."""
    from .. import ir
    return {l["law_id"] for l in ir.load_laws_any("M1", ROOT)
            if l["facts"] == ROLLUP_FACTS}


def _solc(arg: Path | None) -> Path:
    if arg:
        return Path(arg)
    if layout_extract.SOLC.exists():
        return layout_extract.SOLC
    svm = sorted(Path.home().glob(".local/share/svm/0.8.24/solc-*"))
    if svm:
        return svm[0]
    raise RuntimeError("no solc 0.8.24 found (pass --solc)")


def _git(morph: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(morph), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr[:400]}")
    return r.stdout.strip()


def _file_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _worktree(morph: Path, commit: str, dest: Path) -> None:
    _git(morph, "worktree", "add", "--detach", str(dest), commit)


def _rm_worktree(morph: Path, dest: Path) -> None:
    subprocess.run(["git", "-C", str(morph), "worktree", "remove", "--force", str(dest)],
                   capture_output=True, text=True)


def _node_modules(wt: Path, morph: Path) -> None:
    """solc remaps resolve node_modules/ under the contracts dir; worktrees
    don't carry it (gitignored), so link one in if the source lacks it."""
    target = wt / "contracts" / "node_modules"
    if target.exists():
        return
    for cand in (morph / "contracts" / "node_modules", morph / "node_modules",
                 Path.home() / "ext" / "replay_sol" / "node_modules",
                 Path(os.environ.get("HOLON_NODE_MODULES", "/nonexistent"))):
        if (cand / "@openzeppelin").is_dir():
            target.symlink_to(cand)
            return
    raise RuntimeError("no node_modules with @openzeppelin for solc remaps "
                       "(set HOLON_NODE_MODULES)")


def _verify_shas(wt: Path, shas: dict) -> None:
    for rel, want in shas.items():
        got = _file_sha(wt / rel)
        if got != want:
            raise RuntimeError(f"{rel}: sha256 {got} != spec {want}")


def _apply(wt: Path, m: dict) -> None:
    """spec `apply`: replace line `line` of `file` (stripped text must equal
    `original`) with original leading whitespace + `replacement`; empty
    replacement leaves a blank line."""
    p = wt / m["file"]
    lines = p.read_text().splitlines(keepends=True)
    i = m["line"] - 1
    if lines[i].strip() != m["original"].strip():
        raise RuntimeError(f"{m['id']}: {m['file']}:{m['line']} is "
                           f"{lines[i].strip()!r}, expected {m['original'].strip()!r}")
    indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
    nl = "\n" if lines[i].endswith("\n") else ""
    lines[i] = indent + m["replacement"] + nl
    p.write_text("".join(lines))


def _go_build(wt: Path) -> tuple[bool, str]:
    """Validity for Go mutants: build the module that contains common/batch."""
    mod = wt / "common"
    r = subprocess.run(["go", "build", "./batch"], cwd=mod,
                       capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or r.stdout)[-500:]


def _detected_via(changed: list[dict]) -> str | None:
    """`flip` when some PROVED<->REFUTED transition fired, `unknown_only` when
    every change is to/from UNKNOWN."""
    if not changed:
        return None
    flips = {"PROVED", "REFUTED"}
    if any({c["baseline"], c["mutant"]} <= flips and c["baseline"] != c["mutant"]
           for c in changed):
        return "flip"
    return "unknown_only"


def _extract_and_run(wt: Path, solc: Path, scratch: Path) -> dict:
    """assemble facts + run the pipelines; returns statuses {law: status}
    plus facts sha/bytes for the miss-label comparison. Assembly and solc
    compile failures raise; pipeline-stage failures (facts.load, generator,
    emitter) are caught by the caller."""
    try:
        doc, cov = assemble(wt, solc, out_dir=scratch / "extracted")
    except RuntimeError as e:
        if str(e).startswith("solc"):
            raise CompileError(str(e)) from e
        raise
    facts_p = scratch / "facts.json"
    write_docs(doc, cov, facts_p)
    return {"doc": doc, "coverage": cov, "facts_p": facts_p,
            "facts_sha": _file_sha(facts_p), "facts_bytes": facts_p.read_bytes(),
            "link_fallbacks": sorted({d["element"] for d in cov["debt"]
                                      if d["kind"] == "offset_link_ordinal"})}


def _s1_extract(wt: Path, solc: Path, scratch: Path) -> dict:
    """S1 extraction on `wt`: solc --ast-compact-json + translate -> facts.
    solc's own compile failure is a CompileError; anything else raises."""
    astload, s1extract = _s1()
    spec = s1extract.load_spec()
    try:
        world = astload.run_solc(spec, str(wt), solc=str(solc))
    except RuntimeError as e:
        if str(e).startswith("solc failed"):
            raise CompileError(str(e)) from e
        raise
    facts_p = scratch / "rollup_facts.json"
    facts_p.parent.mkdir(parents=True, exist_ok=True)
    doc, cov = s1extract.extract(world, spec, facts_p,
                                 scratch / "rollup_coverage.json")
    return {"facts_p": facts_p, "facts_sha": _file_sha(facts_p),
            "facts_bytes": facts_p.read_bytes(), "doc": doc, "cov": cov,
            "link_fallbacks": []}


def _run_rollup_pipeline(facts_p: Path, scratch: Path) -> dict:
    """The M1 laws bound to the rollup facts file, on extracted facts."""
    return mpipeline.run_m1("M1", None, str(scratch / "results_m1"),
                            str(scratch / "gen_m1"), no_registry=True,
                            log=lambda *a: None, law_ids=_rollup_law_ids(),
                            facts_overrides={ROLLUP_FACTS: facts_p})


def _run_pipelines(facts_p: Path, scratch: Path) -> dict:
    """M0 pipeline on the assembled facts + the M1 laws bound to the header
    facts file (morph_rollup/morph_batchdata stay the committed M1 facts —
    these mutants don't touch them)."""
    statuses = dict(pipeline.run("M0", str(facts_p), str(scratch / "results"),
                                 str(scratch / "gen"), no_registry=True,
                                 log=lambda *a: None))
    statuses.update(mpipeline.run_m1(
        "M1", None, str(scratch / "results_m1"), str(scratch / "gen_m1"),
        no_registry=True, log=lambda *a: None, law_ids=set(M1_HEADER_LAWS),
        facts_overrides={M1_HEADER_FACTS: facts_p}))
    return statuses


def run_mutants(spec_path: Path, morph: Path, only: list[str] | None,
                work: Path | None, solc: Path | None, out: Path) -> int:
    t_start = time.time()
    spec = json.loads(Path(spec_path).read_text())
    solc_p = _solc(solc)
    work = work or DEFAULT_WORK
    commit = spec["target"]["commit"]
    if _git(morph, "rev-parse", "HEAD") != commit:
        raise RuntimeError(f"morph at {_git(morph, 'rev-parse', 'HEAD')}, spec pins {commit}")
    mutants = [m for m in spec["mutants"] if only is None or m["id"] in only]
    work.mkdir(parents=True, exist_ok=True)
    baseline_cache: dict[str, dict] = {}

    def baseline() -> dict:
        if commit not in baseline_cache:
            wt = work / "wt-baseline"
            _worktree(morph, commit, wt)
            try:
                _node_modules(wt, morph)
                _verify_shas(wt, spec["target"]["file_sha256"])
                scratch = work / "out" / "baseline"
                run = _extract_and_run(wt, solc_p, scratch)
                run["statuses"] = _run_pipelines(run["facts_p"], scratch)
                baseline_cache[commit] = run
            finally:
                _rm_worktree(morph, wt)
        return baseline_cache[commit]

    s1_ok = _s1_available()
    rollup_base: dict | None = None

    def rollup_baseline() -> dict:
        nonlocal rollup_base
        if rollup_base is None:
            wt = work / "wt-rollup-baseline"
            _worktree(morph, commit, wt)
            try:
                _node_modules(wt, morph)
                _verify_shas(wt, spec["target"]["file_sha256"])
                scratch = work / "out" / "rollup-baseline"
                run = _s1_extract(wt, solc_p, scratch)
                try:
                    run["statuses"] = _run_rollup_pipeline(run["facts_p"], scratch)
                except Exception as e:
                    # a baseline failure aborts the run, never gets scored
                    first = (str(e).splitlines() or [repr(e)])[0]
                    raise RuntimeError(
                        f"rollup baseline pipeline failed on extracted facts: "
                        f"{first}") from e
                rollup_base = run
            finally:
                _rm_worktree(morph, wt)
        return rollup_base

    results = []
    for m in mutants:
        t0 = time.time()
        rec = {"id": m["id"], "file": m["file"], "line": m["line"],
               "operator": m.get("operator"), "equivalent": bool(m.get("equivalent"))}
        if m["id"].startswith("R"):
            if not s1_ok:
                rec.update({"valid": None, "detected": False,
                            "label": "pending_extractor", "changed": [],
                            "seconds": round(time.time() - t0, 3)})
                results.append(rec)
                continue
            wt = work / f"wt-{m['id']}"
            scratch = work / "out" / m["id"]
            _worktree(morph, commit, wt)
            try:
                _node_modules(wt, morph)
                _verify_shas(wt, spec["target"]["file_sha256"])
                _apply(wt, m)
                try:
                    run = _s1_extract(wt, solc_p, scratch)
                except CompileError as e:
                    rec.update({"valid": False, "detected": False,
                                "label": "invalid", "changed": [],
                                "build_error": str(e)[:500],
                                "seconds": round(time.time() - t0, 3)})
                    results.append(rec)
                    continue
                except Exception as e:
                    first = (str(e).splitlines() or [repr(e)])[0]
                    rec.update({"valid": True, "detected": False,
                                "label": "extraction_gap", "changed": [],
                                "pipeline_error": f"assemble: {first}"[:500],
                                "link_fallbacks": [],
                                "seconds": round(time.time() - t0, 3)})
                    results.append(rec)
                    continue
                base = rollup_baseline()
                try:
                    statuses = _run_rollup_pipeline(run["facts_p"], scratch)
                except Exception as e:
                    first = (str(e).splitlines() or [repr(e)])[0]
                    label = ("extraction_gap" if run["facts_bytes"] == base["facts_bytes"]
                             else "rule_gap")
                    rec.update({"valid": True, "detected": False, "label": label,
                                "facts_sha256": run["facts_sha"], "changed": [],
                                "pipeline_error": f"pipeline: {first}"[:500],
                                "link_fallbacks": run["link_fallbacks"],
                                "seconds": round(time.time() - t0, 3)})
                    results.append(rec)
                    continue
                changed = [{"law": lid, "baseline": base["statuses"][lid],
                            "mutant": st}
                           for lid, st in statuses.items()
                           if st != base["statuses"][lid]]
                detected = bool(changed)
                label = (None if detected
                         else "extraction_gap" if run["facts_bytes"] == base["facts_bytes"]
                         else "rule_gap")
                rec.update({"valid": True, "detected": detected, "label": label,
                            "detected_via": _detected_via(changed),
                            "facts_sha256": run["facts_sha"], "changed": changed,
                            "link_fallbacks": run["link_fallbacks"],
                            "seconds": round(time.time() - t0, 3)})
                results.append(rec)
            finally:
                _rm_worktree(morph, wt)
            continue
        wt = work / f"wt-{m['id']}"
        scratch = work / "out" / m["id"]
        _worktree(morph, commit, wt)
        try:
            _node_modules(wt, morph)
            _verify_shas(wt, spec["target"]["file_sha256"])
            _apply(wt, m)
            if m["file"].endswith(".go"):
                ok, why = _go_build(wt)
                if not ok:
                    rec.update({"valid": False, "detected": False, "label": "invalid",
                                "changed": [], "build_error": why,
                                "seconds": round(time.time() - t0, 3)})
                    results.append(rec)
                    continue
            try:
                run = _extract_and_run(wt, solc_p, scratch)
            except CompileError as e:
                # a failed compile of the mutated target is invalid,
                # never detected — the only route to `invalid`
                rec.update({"valid": False, "detected": False, "label": "invalid",
                            "changed": [], "build_error": str(e)[:500],
                            "seconds": round(time.time() - t0, 3)})
                results.append(rec)
                continue
            except Exception as e:
                # any other extraction/assemble failure on a mutant that
                # compiled: stays valid, not detected, extraction_gap
                first = (str(e).splitlines() or [repr(e)])[0]
                rec.update({"valid": True, "detected": False,
                            "label": "extraction_gap", "changed": [],
                            "pipeline_error": f"assemble: {first}"[:500],
                            "link_fallbacks": [],
                            "seconds": round(time.time() - t0, 3)})
                results.append(rec)
                continue
            base = baseline()
            try:
                statuses = _run_pipelines(run["facts_p"], scratch)
            except Exception as e:
                # the pipeline rejected the assembled facts: the mutant stays
                # valid (it compiled) and counts as not detected; labelled by
                # the frozen definitions on the facts comparison
                label = ("extraction_gap" if run["facts_bytes"] == base["facts_bytes"]
                         else "rule_gap")
                first = (str(e).splitlines() or [repr(e)])[0]
                rec.update({"valid": True, "detected": False, "label": label,
                            "facts_sha256": run["facts_sha"], "changed": [],
                            "pipeline_error": f"pipeline: {first}"[:500],
                            "link_fallbacks": run["link_fallbacks"],
                            "seconds": round(time.time() - t0, 3)})
                results.append(rec)
                continue
            changed = [{"law": lid, "baseline": base["statuses"][lid], "mutant": st}
                       for lid, st in statuses.items() if st != base["statuses"][lid]]
            detected = bool(changed)
            label = (None if detected
                     else "extraction_gap" if run["facts_bytes"] == base["facts_bytes"]
                     else "rule_gap")
            rec.update({"valid": True, "detected": detected, "label": label,
                        "detected_via": _detected_via(changed),
                        "facts_sha256": run["facts_sha"], "changed": changed,
                        "link_fallbacks": run["link_fallbacks"],
                        "seconds": round(time.time() - t0, 3)})
            results.append(rec)
        finally:
            _rm_worktree(morph, wt)

    live = [r for r in results if r["label"] != "pending_extractor"]
    valid = [r for r in live if r["valid"] and not r["equivalent"]]
    detected = [r for r in valid if r["detected"]]
    score = len(detected) / len(valid) if valid else None
    pending = [r for r in results if r["label"] == "pending_extractor"]
    rb = rollup_base or {}
    results_m1 = {}
    try:
        results_m1 = json.loads((ROOT / "results" / "M1" / "summary.json").read_text())
    except OSError:
        pass
    rvs = {lid: {"baseline": st, "results_M1": results_m1.get(lid),
                 "match": st == results_m1.get(lid),
                 **({"reason": BASELINE_MISMATCH_REASONS[lid]}
                    if st != results_m1.get(lid) else {})}
           for lid, st in (rb.get("statuses") or {}).items()} if rb else {}
    for lid, v in rvs.items():
        if not v["match"]:
            v.setdefault("reason", None)
    report = {
        "schema": "holon-mutation-report/0.1",
        "spec": str(spec_path), "target_commit": commit,
        "baseline_facts_sha256": baseline_cache.get(commit, {}).get("facts_sha"),
        "rollup_baseline_facts_sha256": rb.get("facts_sha"),
        "rollup_baseline_vs_results_M1": rvs,
        "rollup_baseline_mismatches": sum(1 for v in rvs.values() if not v["match"]),
        "m1_rollup_facts": (json.dumps(rb["doc"]["extraction"], sort_keys=True)
                            if rb and rb["doc"].get("extraction") is not None
                            else "spec/M1/facts (hand; S1 extraction pending)"),
        **({"provenance": rb["doc"]["provenance"]} if rb and "provenance" in rb["doc"] else {}),
        "m1_header_laws": list(M1_HEADER_LAWS),
        "detected_via_counts": {
            "flip": sum(1 for r in detected if r.get("detected_via") == "flip"),
            "unknown_only": sum(1 for r in detected if r.get("detected_via") == "unknown_only"),
        },
        "mutants": results,
        "final": not pending,          # never final while any mutant is pending
        "pending": [r["id"] for r in pending],
        "provisional_header_score": score,
        "score_definition": spec["score"],
        "threshold": spec["threshold"],
        "equivalence_reclassifications": [],
        "total_seconds": round(time.time() - t_start, 3),
    }
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n")
    print(f"score {score} ({len(detected)}/{len(valid)} valid), "
          f"{len(pending)} pending -> {out}")
    return 0
