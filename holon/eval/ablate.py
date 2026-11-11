"""`python -m holon eval ablate run|calibrate|metrics|report` (BUILD_PLAN I53, which closes the M4 exit; whitepaper §13
"Metrics" and "Ablations", L14, L15). The contract is the docstring of tests_m4/test_i53_ablations.py; the protocol
is spec/M4/lib/I53_protocol.json, read here and never written.

  run [--only A1,..] [--jobs N]   each ablation in its own scratch copy of the repository (outside it: HOLON_ABLATE_DIR,
                                  default ~/.holon/eval/ablate), the switch applied in a child process
                                  (holon.eval.ablate_child), the stages it feeds rerun there; writes
                                  results/eval/ablations/<id>.json and results/eval/ablations.json
  calibrate                       the I48 controls as test milestone T48 with the plan's budgets:
                                  results/eval/calibration.json and results/eval/calibration/<control>.json
  metrics                         results/eval/metrics.json, every §13 metric from its recorded source
  report [--check]                results/eval/ablations.json and docs/M4_EVAL.md from the committed outputs

Every system name, path and switch comes from the protocol; nothing here names a target. No generator closure imports
this module, and it imports no test module. Output is dumps(obj): sorted keys, no time, no absolute path; timings go
to results/eval/ablations_timing.json only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path("spec") / "M4" / "lib" / "I53_protocol.json"
MAP = Path("spec") / "M3" / "appendixA_map.json"
OUT = Path("results") / "eval"
SCHEMA = "holon-ablations/0.1"
BASES = ("hand", "code")
DECIDED = ("PROVED", "REFUTED", "checked", "failed")
FIELDS = ("status", "evidence_triage", "filter_bin")
IGNORE = shutil.ignore_patterns(".git", "__pycache__", "node_modules")


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ratio(n, d):
    return None if not d else n / d


def delta(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        d = a - b
        return round(d, 12) if isinstance(d, float) else d
    return None


def protocol(root: Path = ROOT) -> dict:
    return load(root / PROTOCOL)


def scratch_dir() -> Path:
    return Path(os.environ.get("HOLON_ABLATE_DIR") or Path.home() / ".holon" / "eval" / "ablate")


def scratch_copy(name: str, root: Path = ROOT) -> Path:
    dst = scratch_dir() / name / "repo"
    if dst.parent.exists():
        shutil.rmtree(dst.parent)
    dst.parent.mkdir(parents=True)
    shutil.copytree(root, dst, ignore=IGNORE, symlinks=True)
    return dst


def child(repo: Path, argv: list[str], patches=(), params=None, timeout: int = 4 * 3600, tag: str = "c") -> dict:
    """Run `holon <argv>` in the scratch copy repo, with the named patches applied in the child process."""
    d = repo / ".ablate"
    d.mkdir(exist_ok=True)
    n = len(list(d.glob("spec_*.json")))
    sp = d / f"spec_{n:03d}_{tag}.json"
    sp.write_text(json.dumps({"patches": list(patches), "argv": argv, "params": params or {}}), encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(repo), "BEND_NO_TELEMETRY": "1"}
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-m", "holon.eval.ablate_child", str(sp)], cwd=repo, env=env,
                           capture_output=True, text=True, timeout=timeout)
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        rc, out, err = "timeout", (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout"
    (d / f"log_{n:03d}_{tag}.txt").write_text(f"$ holon {' '.join(argv)}\nrc {rc}\n--- stdout\n{out}\n--- stderr\n{err}\n")
    return {"argv": "holon " + " ".join(argv), "rc": rc, "seconds": round(time.time() - t0, 3),
            "tail": (err or out)[-1500:]}


def first_line(text: str, pat: str) -> str | None:
    for ln in (text or "").splitlines():
        if re.search(pat, ln):
            return ln.strip()
    return None


# =========================================================================================== record sets and scores
def record_sets(root: Path) -> dict:
    """{set: {law: record}} for every set of the committed map (laws present in the set's laws dir, with a record)."""
    md = load(ROOT / MAP)
    out = {}
    for s in md["sets"]:
        res = root / s["results"]
        recs = {}
        if res.is_file():
            for h, v in sorted(load(res).items()):
                if isinstance(v, dict):
                    recs[h] = {"status": v.get("status")}
        elif res.is_dir():
            for lp in sorted((root / s["laws"]).glob("L*.json")):
                lid = load(lp)["law_id"]
                rp = res / f"{lid}.json"
                if rp.is_file():
                    recs[lid] = load(rp)
        out[s["name"]] = recs
    return out


def changes(full: dict, abl: dict) -> tuple[list, dict, dict]:
    """(removed [set, law], overrides {set: {law: {field: value}}}, added {set: {law: status}}) of abl against full."""
    removed, over, added = [], {}, {}
    for s in sorted(set(full) | set(abl)):
        f, a = full.get(s, {}), abl.get(s, {})
        for lid in sorted(set(f) - set(a)):
            removed.append([s, lid])
        for lid in sorted(set(a) - set(f)):
            added.setdefault(s, {})[lid] = a[lid].get("status")
        for lid in sorted(set(f) & set(a)):
            d = {k: a[lid].get(k) for k in FIELDS if a[lid].get(k) != f[lid].get(k)}
            if d:
                over.setdefault(s, {})[lid] = d
    return removed, over, added


def scores(root: Path, records: dict | None = None) -> dict:
    """The protocol's morph_metrics of the record sets at root, through holon.report."""
    from .. import report as R
    records = records if records is not None else record_sets(root)
    doc, sets = R.build_map(root, "M3")
    v = R.verdicts(doc, sets)
    items = doc["items"]
    obs = sorted(i for i in v if i.startswith("O"))
    rows = sorted(i for i in v if i.startswith("R"))
    rec = {}
    for i in obs:
        for f in items[i].get("families") or []:
            r = rec.setdefault(f, {"reproduced": 0, "total": 0})
            r["total"] += 1
            r["reproduced"] += v[i]["code"] == "reproduced"
    for r in rec.values():
        r["recall"] = ratio(r["reproduced"], r["total"])
    basis = {s["name"]: s["basis"] for s in sets}
    true_links = {(lk["set"], lk["law"]) for i in obs if v[i]["code"] == "reproduced"
                  for lk in items[i].get("links", []) if lk["counted"] and basis.get(lk["set"]) == "code"}
    c = {"true_defect": 0, "intended_asymmetry": 0, "model_defect": 0, "unadjudicated": 0}
    for s, laws in records.items():
        if basis.get(s) != "code":
            continue
        for lid, r in laws.items():
            if r.get("status") != "REFUTED":
                continue
            if r.get("filter_bin") == "model_defect":
                c["model_defect"] += 1
            elif r.get("evidence_triage") == "intent_question" or r.get("filter_bin") == "intended_bounded":
                c["intended_asymmetry"] += 1
            elif (s, lid) in true_links:
                c["true_defect"] += 1
            else:
                c["unadjudicated"] += 1
    c["precision"] = ratio(c["true_defect"], c["true_defect"] + c["intended_asymmetry"] + c["model_defect"])
    c["precision_all"] = ratio(c["true_defect"], sum(c[k] for k in ("true_defect", "intended_asymmetry",
                                                                   "model_defect", "unadjudicated")))
    out = {"findings": sum(1 for laws in records.values() for r in laws.values() if r.get("status") == "REFUTED"),
           "obstructions_reproduced": {b: sum(v[i][b] == "reproduced" for i in obs) for b in BASES},
           "rows_held": {b: sum(v[i][b] == "held" for i in rows) for b in BASES},
           "recall_per_rule": {f: rec[f] for f in sorted(rec)}, "precision": c}
    return out, {i: v[i] for i in obs + rows}


def score_delta(full: dict, abl: dict) -> dict:
    return {"findings": delta(abl["findings"], full["findings"]),
            "obstructions_reproduced": {b: delta(abl["obstructions_reproduced"][b], full["obstructions_reproduced"][b]) for b in BASES},
            "rows_held": {b: delta(abl["rows_held"][b], full["rows_held"][b]) for b in BASES},
            "precision": {k: delta(abl["precision"][k], full["precision"][k]) for k in sorted(full["precision"])},
            "recall_per_rule": {f: delta(abl["recall_per_rule"].get(f, {}).get("recall"), full["recall_per_rule"][f]["recall"])
                                for f in sorted(full["recall_per_rule"])}}


def morph_block(repo: Path, laws: dict, reran: list, extra: dict | None = None) -> dict:
    full_recs = record_sets(ROOT)
    abl_recs = record_sets(repo)
    full, vf = scores(ROOT, full_recs)
    abl, va = scores(repo, abl_recs)
    removed, over, added = changes(full_recs, abl_recs)
    return {"status": "run", "reran": reran, "laws": laws, "removed": removed, "overrides": over, "added": added,
            "full": full, "ablated": abl, "delta": score_delta(full, abl),
            "items_changed": {i: {"full": vf[i], "ablated": va[i]} for i in sorted(vf) if vf[i] != va.get(i)},
            "extra": extra or {}}


# =========================================================================================== derive and run
def derive_diff(repo: Path, m: str, patches=(), extra_args=(), tag="derive", params=None) -> tuple[dict, dict]:
    base = repo / ".ablate" / f"base_{m}"
    if not base.exists():
        (repo / ".ablate").mkdir(exist_ok=True)
        shutil.copytree(repo / "laws" / m, base)
    dp = repo / ".ablate" / f"diff_{m}_{tag}.json"
    r = child(repo, ["derive", "--milestone", m, "--against", str(base), "--diff", str(dp), *extra_args], patches,
              params, tag=f"{tag}_{m}")
    if r["rc"] != 0 or not dp.is_file():
        return r, {"derived": None, "lost": [], "gained": [], "changed": [], "error": r["tail"]}
    d = load(dp)
    ch = {"removed": [], "added": [], "statement": []}
    for e in d["laws"]:
        if e["change"] in ch:
            ch[e["change"]].append(e["law_id"])
    n = sum(1 for e in d["laws"] if e["change"] != "removed")
    return r, {"derived": n, "lost": sorted(ch["removed"]), "gained": sorted(ch["added"]),
               "changed": sorted(ch["statement"])}


def run_laws(repo: Path, m: str, ids: list[str], patches=(), tag="run", params=None) -> list[dict]:
    """Decide the changed or gained laws in the scratch copy under the switch: one run over all of them; if it fails,
    one run per law; a law no run decides is UNKNOWN with what was tried (protocol rerun_rule)."""
    if not ids:
        return []
    r = child(repo, ["run", "--milestone", m, "--laws", ",".join(sorted(ids))], patches, params, tag=f"{tag}_{m}")
    out = [r]
    if r["rc"] == 0:
        return out
    for lid in sorted(ids):
        q = child(repo, ["run", "--milestone", m, "--laws", lid], patches, params, tag=f"{tag}1_{lid[:40]}")
        out.append(q)
        if q["rc"] != 0:
            why = first_line(q["tail"], r"Error|error|refus") or q["tail"][-300:]
            rec = {"law_id": lid, "status": "UNKNOWN",
                   "attempts": [{"kind": "ablation_rerun", "bound": f"holon run under the switch exited {q['rc']}: {why}"}]}
            (repo / "results" / m / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")
    return out


def drop_records(repo: Path, m: str, ids: list[str]) -> None:
    """A lost law has no record: the derivation removed its law file; its old record goes too."""
    for lid in ids:
        p = repo / "results" / m / f"{lid}.json"
        if p.exists():
            p.unlink()


def derive_ablation(aid: str, patches: list, milestones: list[str], prep=None, params=None) -> dict:
    repo = scratch_copy(aid)
    if prep:
        prep(repo)
    reran, laws = [], {}
    for m in milestones:
        r, lw = derive_diff(repo, m, patches, params=params)
        reran.append(r)
        drop_records(repo, m, lw["lost"])
        reran += run_laws(repo, m, lw["gained"] + lw["changed"], patches, params=params)
        laws[m] = lw
    return {"repo": repo, "reran": reran, "laws": laws}


# =========================================================================================== the corpus row (c17 of I51)
def corpus_rerun(aid: str, how: str, patches: list) -> dict:
    """Rerun the derive-level stages of the one corpus entry that reached derive (named in the protocol's how text)
    from I51's committed document and sidecars (they name their own committed paths), as I51 ran them (holon.eval.
    holon_run._rules: sorts, types, model, disch, derive), under the switch: the laws derived (I51: none)."""
    ent = re.search(r"\b(c\d\d)\b", how).group(1)
    rel = f"{OUT.as_posix()}/holon/{ent}"
    corpus = load(ROOT / OUT / "holon" / "corpus.json")
    row = next(r for r in corpus["rows"] if ent in (r.get("id"), r.get("entry"), r.get("entry_id")))
    repo = scratch_copy(f"{aid}_{ent}")
    from . import holon_run as HR   # I51's own checkout of the entry (the manifest's URL, its pre-fix commit)
    entry = next(e for e in load(ROOT / "spec" / "eval" / "corpus.json")["entries"] if e["id"] == ent)
    ck = repo.parent / "checkout"
    clone, _tree = HR.checkout(entry, ck)
    cfgp = repo / "config" / "holon.json"
    cfg = load(cfgp)
    cfg["replay"]["sol_deps"] = None
    side = load(next((ROOT / rel / "sidecars").glob("extract_*.json")))
    cfg.setdefault("extract", {})["sources"] = {(side.get("target") or {}).get("repo"): str(ck)}
    cfgp.write_text(dumps(cfg), encoding="utf-8")
    M = re.search(r"milestone (T\d+)", json.dumps(protocol()["ablations"])).group(1)   # the scratch milestone
    ts, ds, us, fs = (f"{rel}/sidecars/{n}.json" for n in ("sort_types", "disch", "undo", "fact"))
    sorts = f"gen/{M}/sorts"
    steps = [("sorts", ["sorts", "--milestone", M, "--sidecar", ts, "--out", sorts]),
             ("types", ["types", "--milestone", M, "--sidecar", ts, "--out", sorts]),
             ("model", ["model", "--milestone", M, "--sidecar", ts, "--out", f"{sorts}/models"]),
             ("disch", ["disch", "--milestone", M, "--sidecar", ds, "--out", f"gen/{M}/disch"]),
             ("derive", ["derive", "--milestone", M, "--catalog", "holon-rules/1.15", "--sidecar", ts, "--disch", ds,
                         "--undo-sidecar", us, "--fact-sidecar", fs, "--out", f"laws/{M}",
                         "--obstructions", f"{sorts}/obstructions.json"])]
    reran, last = [], None
    for name, argv in steps:
        last = child(repo, argv, patches, tag=name)
        reran.append(last)
        if last["rc"] != 0:
            break
    nlaws = len(list((repo / "laws" / M).glob("L*.json"))) if (repo / "laws" / M).is_dir() else 0
    HR.drop_worktree(clone, ck)
    shutil.rmtree(repo.parent, ignore_errors=True)
    return {"status": "run", "reran": reran,
            "extra": {"entry": ent, "milestone": M, "laws": nlaws, "full_laws": len(row.get("laws") or []),
                      "completed": bool(last and last["rc"] == 0), "detected": False,
                      "full_detected": bool(row.get("detected"))}}


# =========================================================================================== the nine ablations
def a_derive(aid: str, P: dict, patches: list, milestones: list[str], prep=None, post=None, params=None) -> dict:
    res = derive_ablation(aid, patches, milestones, prep, params)
    if post:
        post(res["repo"])
    return morph_block(res["repo"], res["laws"], res["reran"])


def empty_evidence(repo: Path) -> None:
    for m in ("M2", "M3"):
        p = repo / "gen" / m / "evidence.json"
        if p.is_file():
            d = load(p)
            d["atoms"] = []
            p.write_text(dumps(d), encoding="utf-8")


def no_triage(repo: Path) -> None:
    """A3: every record's evidence triage read as no evidence: an intent question is a finding."""
    for p in sorted((repo / "results").rglob("L*.json")):
        d = load(p)
        if isinstance(d, dict) and d.get("evidence_triage") == "intent_question":
            d["evidence_triage"] = "finding"
            p.write_text(dumps(d), encoding="utf-8")


def a5(P: dict) -> dict:
    """Native-equivalence NAT laws: NAT laws outside the kept sub-forms, removed from every hand-built law set (each
    NAT law is decided on its own, so no other record changes)."""
    repo = scratch_copy("A5")
    kept = ("composition", "naturality", "slash")
    lost = {}
    for d in sorted((repo / "laws").iterdir()):
        if not d.is_dir() or d.name == "M3":
            continue
        for p in sorted(d.glob("L*.json")):
            law = load(p)
            if law.get("rule") == "NAT" and law.get("subform") not in kept:
                lost.setdefault(d.name, []).append(law["law_id"])
                p.unlink()
    laws = {m: {"derived": len(list((repo / "laws" / m).glob("L*.json"))), "lost": sorted(ids), "gained": [],
                "changed": []} for m, ids in sorted(lost.items())}
    return morph_block(repo, laws, [{"argv": "remove the native-equivalence laws from the law sets", "rc": 0}])


def a6_extra(repo: Path) -> dict:
    cl = repo / "gen" / "M3" / "disch" / "closure.json"
    dead = None
    if cl.is_file():
        d = load(cl)
        dead = sum(len((x.get("dead") or {})) for x in (d.get("models") or d.get("documents") or {}).values()) \
            if isinstance(d.get("models") or d.get("documents"), dict) else None
    full = load(ROOT / "gen" / "M3" / "disch" / "closure.json")
    fdead = sum(len((x.get("dead") or {})) for x in (full.get("models") or full.get("documents") or {}).values()) \
        if isinstance(full.get("models") or full.get("documents"), dict) else None
    return {"dead_full": fdead, "dead_after": dead}


def a6(P: dict) -> dict:
    repo = scratch_copy("A6")
    patches = ["no_enablement"]
    reran = [child(repo, ["disch", "--milestone", "M3"], patches, tag="disch")]
    r, lw = derive_diff(repo, "M3", patches)
    reran.append(r)
    drop_records(repo, "M3", lw["lost"])
    reran += run_laws(repo, "M3", lw["gained"] + lw["changed"], patches)
    blk = morph_block(repo, {"M3": lw}, reran)
    x = a6_extra(repo)
    st = 0
    for s, laws in blk["overrides"].items():
        st += sum(1 for lid, f in laws.items() if lid.startswith("L_disch") and "status" in f)
    x["disch_status_changed"] = st
    blk["extra"] = x
    return blk


def a7(P: dict) -> dict:
    """No replay: the final filter of every REFUTED record with no replay side; replay-derived counts recomputed."""
    from .. import filter as FL
    full_bin = abl_bin = 0
    per = {}
    for m in ("M0", "M1", "M2", "M3"):
        for p in sorted((ROOT / "results" / m).glob("L*.json")):
            d = load(p)
            if d.get("status") != "REFUTED":
                continue
            conc = (d.get("witness_provenance") or {}).get("concretization") or d.get("concretization") or {}
            b = FL.final_bin({}, conc)
            full_bin += d.get("filter_bin") == "finding"
            abl_bin += b == "finding"
            per.setdefault(m, {"refuted": 0, "finding_full": 0, "finding_ablated": 0})
            per[m]["refuted"] += 1
            per[m]["finding_full"] += d.get("filter_bin") == "finding"
            per[m]["finding_ablated"] += b == "finding"
    wr = [(load(ROOT / "results" / m / "metrics.json").get("witness_replay_rate") or {}) for m in ("M0", "M1", "M2", "M3")]
    ref = [(load(ROOT / "results" / m / "metrics.json").get("refinement") or {}) for m in ("M0", "M1", "M2", "M3")]
    s62 = load(ROOT / "results" / "M2" / "mutation_i62" / "summary.json")
    rows = [load(p) for p in sorted((ROOT / "results" / "M2" / "mutation_i62").glob("A*.json"))]
    killed = sum(1 for r in rows if (r.get("kill") or {}).get("killed"))
    via_corpus = sum(1 for r in rows if (r.get("kill") or {}).get("killed") or r.get("corpus_detected"))
    repo = scratch_copy("A7")   # the record sets with no replay side: statuses unchanged, the bins recomputed
    for m in ("M0", "M1", "M2", "M3"):
        for p in sorted((repo / "results" / m).rglob("L*.json")):
            d = load(p)
            if isinstance(d, dict) and d.get("status") == "REFUTED" and "filter_bin" in d:
                conc = (d.get("witness_provenance") or {}).get("concretization") or d.get("concretization") or {}
                d["filter_bin"] = FL.final_bin({}, conc)
                p.write_text(dumps(d), encoding="utf-8")
    blk = morph_block(repo, {}, [{"argv": "holon.filter.final_bin over every REFUTED record with no replay side", "rc": 0}])
    blk["extra"] = {
        "finding_bin": {"full": full_bin, "ablated": abl_bin, "by_milestone": per},
        "witness_replay_rate": {"full": ratio(sum(x.get("replayed", 0) for x in wr), sum(x.get("refuted", 0) for x in wr)),
                                "ablated": None},
        "refinement_compared": {"full": sum(x.get("compared", 0) for x in ref), "ablated": 0},
        "mutation_detection": {"full": via_corpus, "ablated": killed, "mutants": len(rows),
                               "summary_detection": (s62.get("detection") or {}).get("A")}}
    return blk


KERNEL_CASES = ("replay/M1/kernel_mismatch/PROOF.bend", "tests_m3/fixtures/bendtt_i97/kernel_fuel/PROOF.bend")


def a8(P: dict) -> dict:
    from .. import bend
    cfg = bend.config(ROOT)
    cmd = cfg["bend"].get("cmd") or "bend"
    cases = []
    for rel in KERNEL_CASES:
        p = ROOT / rel
        row = {"case": rel}
        for mode, extra in (("single", []), ("dual", ["--verdict"])):
            q = subprocess.run([cmd, p.name, *extra], cwd=p.parent, capture_output=True, text=True, timeout=3600,
                               env={**os.environ, "BEND_NO_TELEMETRY": "1"})
            text = q.stdout + q.stderr
            row[mode] = {"rc": q.returncode, "all_proofs_check": "ALL PROOFS CHECK" in text,
                         "mismatch": bool(re.search(r"mismatch", text, re.I)),
                         "line": first_line(text, r"ALL PROOFS CHECK|mismatch|error|Error")}
        row["surfaced_dual"] = bool(row["dual"]["mismatch"] or row["dual"]["rc"] != 0)
        row["surfaced_single"] = bool(row["single"]["mismatch"] or row["single"]["rc"] != 0)
        cases.append(row)
    sk = 0
    for m in ("M0", "M1", "M2", "M3"):
        k = (load(ROOT / "results" / m / "metrics.json").get("cross_kernel_agreement") or {})
        sk += k.get("checked_records", 0)
    repo = scratch_copy("A8")
    blk = morph_block(repo, {}, [{"argv": f"{cmd} <case> and {cmd} <case> --verdict", "rc": 0}])
    blk["extra"] = {"cases": cases,
                    "surfaced": {"dual": sum(c["surfaced_dual"] for c in cases),
                                 "single": sum(c["surfaced_single"] for c in cases)},
                    "second_kernel_records": {"full": sk, "ablated": 0}}
    return blk


def a9(P: dict) -> dict:
    """The sandbox's outcome rows, recorded by the builder from the sandbox run (results/eval/ablations/A9.json is
    written by `run --only A9 --a9 ROWS`); here only the scores of those rows."""
    raise SystemExit("A9 is run through `ablate a9 --rows FILE` (the sandbox is outside the repository)")


def a2(P: dict) -> dict:
    blk_res = derive_ablation("A2", ["no_writer_labels"], [], prep=None)
    repo = blk_res["repo"]
    reran = []
    for m in ("M2", "M3"):
        reran.append(child(repo, ["sorts", "--milestone", m], ["no_writer_labels"], tag=f"sorts_{m}"))
    laws = {}
    for m in ("M2", "M3"):
        r, lw = derive_diff(repo, m, ["no_writer_labels"])
        reran.append(r)
        drop_records(repo, m, lw["lost"])
        reran += run_laws(repo, m, lw["gained"] + lw["changed"], ["no_writer_labels"])
        laws[m] = lw
    blk = morph_block(repo, laws, reran)
    # adversarial confirmation (never merged into the record sets, protocol rerun_rule): every M2 SORT law decided
    # again under the switch, its status set against the committed record
    ids = sorted(load(p)["law_id"] for p in (repo / "laws" / "M2").glob("L*.json") if load(p).get("rule") == "SORT")
    cdir = repo / ".ablate" / "confirm_M2"
    r = child(repo, ["run", "--milestone", "M2", "--laws", ",".join(ids), "--out", str(cdir), "--gen-dir",
                     str(cdir) + "_gen"], ["no_writer_labels"], tag="confirm_M2")
    conf = {}
    for lid in ids:
        rp = cdir / f"{lid}.json"
        conf[lid] = {"full": load(ROOT / "results" / "M2" / f"{lid}.json").get("status"),
                     "ablated": load(rp).get("status") if rp.is_file() else None}
    blk["reran"].append(r)
    blk["extra"] = {"confirmation_M2_sort": conf,
                    "confirmation_changed": sorted(k for k, v in conf.items() if v["full"] != v["ablated"]),
                    "labels_removed": labels_removed(repo)}
    return blk


def labels_removed(repo: Path) -> dict:
    """{milestone: registers whose sort lost a writer-provenance label}, the scratch assignment against the committed."""
    out = {}
    for m in ("M2", "M3"):
        a, b = (load(r / "gen" / m / "sorts" / "assignment.json")["models"] for r in (ROOT, repo))
        out[m] = sorted(f"{mod}:{k}" for mod in a for k, v in a[mod]["assignment"].items()
                        if b.get(mod, {}).get("assignment", {}).get(k) != v)
    return out


def heldout_sorts(aid: str, how: str, patches: list) -> dict:
    """The held-out sort pass under the switch, from the sealed inputs named in the protocol's how text."""
    sha = re.search(r"\b([0-9a-f]{40})\b", how).group(1)
    doc, side = re.findall(r"(gen/targets/\S+?\.json)", how)[:2]
    repo = scratch_copy(f"{aid}_heldout")
    ms = "T531"
    (repo / "spec" / ms / "facts").mkdir(parents=True, exist_ok=True)
    (repo / "spec" / ms / "lib").mkdir(parents=True, exist_ok=True)
    blob = subprocess.run(["git", "show", f"{sha}:{doc}"], cwd=ROOT, capture_output=True, check=True).stdout
    fdoc = repo / "spec" / ms / "facts" / Path(doc).name
    fdoc.write_bytes(blob)
    st = json.loads(subprocess.run(["git", "show", f"{sha}:{side}"], cwd=ROOT, capture_output=True, check=True).stdout)
    sealed_ref = None
    for cand in re.findall(r"(results/targets/\S+?\.json)", json.dumps(protocol())) + ["results/targets/" + doc.split("/")[2] + "/derive_refusal.json"]:
        q = subprocess.run(["git", "show", f"{sha}:{cand}"], cwd=ROOT, capture_output=True)
        if q.returncode == 0:
            sealed_ref = json.loads(q.stdout)
            break
    st_txt = json.dumps(st)
    st_txt = re.sub(r"gen/targets/[^\"]+?/facts/", f"spec/{ms}/facts/", st_txt)
    st = json.loads(st_txt)
    (repo / "spec" / ms / "lib" / "sort_types.json").write_text(dumps(st), encoding="utf-8")
    out = repo / ".ablate" / "sorts_out"
    r = child(repo, ["sorts", "--milestone", ms, "--facts", str(fdoc), "--out", str(out)], patches, tag="sorts")
    r0 = child(repo, ["sorts", "--milestone", ms, "--facts", str(fdoc), "--out", str(out) + "_full"], [], tag="sorts_full")
    msg = first_line(r["tail"], r"no sorts rule|refus|error|Error") if r["rc"] != 0 else None
    msg0 = first_line(r0["tail"], r"no sorts rule|refus|error|Error") if r0["rc"] != 0 else None
    sealed = None
    if isinstance(sealed_ref, dict):
        sealed = sealed_ref.get("message") or sealed_ref.get("stderr") or json.dumps(sealed_ref)[:400]
    shutil.rmtree(repo.parent, ignore_errors=True)
    return {"status": "run", "reran": [r0, r],
            "extra": {"refused": r["rc"] != 0, "message": msg, "message_without_switch": msg0,
                      "sealed_message": msg0, "sealed_record": sealed, "inputs_commit": sha}}


def dev_system(P: dict) -> str:
    """The development system: the one every ablation runs on (the protocol's scopes)."""
    names = set.intersection(*[{s for s, v in a["systems"].items() if v["status"] == "run"} for a in P["ablations"].values()])
    assert len(names) == 1, names
    return names.pop()


def run_one(aid: str, P: dict) -> dict:
    spec = P["ablations"][aid]
    t0 = time.time()
    if aid == "A1":
        dev = a_derive(aid, P, ["no_sort_types"], ["M3"])
    elif aid == "A2":
        dev = a2(P)
    elif aid == "A3":
        dev = a_derive(aid, P, ["no_evidence"], ["M3", "M2"], post=no_triage, params={"milestones": ["M2", "M3"]})
    elif aid == "A4":
        dev = a_derive(aid, P, ["two_cycles"], ["M3", "M2"])
    elif aid == "A5":
        dev = a5(P)
    elif aid == "A6":
        dev = a6(P)
    elif aid == "A7":
        dev = a7(P)
    elif aid == "A8":
        dev = a8(P)
    else:
        raise SystemExit(f"unknown ablation {aid}")
    patches = {"A1": ["no_sort_types"], "A2": ["no_writer_labels"], "A3": [], "A4": ["two_cycles"],
               "A6": ["no_enablement"]}.get(aid, [])
    systems = {}
    dev_sys = dev_system(P)
    for sys_ in sorted(spec["systems"]):
        sp = spec["systems"][sys_]
        if sys_ == dev_sys:
            systems[sys_] = dev
        elif sp["status"] != "run":
            systems[sys_] = {"status": sp["status"], "reason": sp["reason"]}
        elif re.search(r"\bc\d\d\b", sp["how"]):
            systems[sys_] = corpus_rerun(aid, sp["how"], patches)
        else:
            systems[sys_] = heldout_sorts(aid, sp["how"], patches)
    for s in systems.values():
        for r in s.get("reran") or []:
            r.pop("seconds", None)
            if isinstance(r.get("tail"), str):
                r["tail"] = re.sub(r"/[^\s'\"]*/ablate/[^\s'\"]*", "<scratch>", r["tail"])[-800:]
    return {"id": aid, "name": spec["name"], "component": spec["component"], "switch": spec["switch"],
            "systems": systems, "_seconds": round(time.time() - t0, 3)}


def strip_paths(obj):
    if isinstance(obj, str):
        return re.sub(r"(/tmp|/root|/home)/[^\s'\"]*", "<scratch>", obj)
    if isinstance(obj, list):
        return [strip_paths(x) for x in obj]
    if isinstance(obj, dict):
        return {k: strip_paths(v) for k, v in obj.items()}
    return obj


def write_detail(d: dict) -> float:
    secs = d.pop("_seconds", None)
    (ROOT / OUT / "ablations").mkdir(parents=True, exist_ok=True)
    (ROOT / OUT / "ablations" / f"{d['id']}.json").write_text(dumps(strip_paths(d)), encoding="utf-8")
    return secs


def summarize(root: Path = ROOT) -> dict:
    P = protocol(root)
    out = {"schema": SCHEMA, "protocol_sha256": sha256(root / PROTOCOL), "ablations": {}}
    for aid in sorted(P["ablations"]):
        p = root / OUT / "ablations" / f"{aid}.json"
        if not p.is_file():
            out["ablations"][aid] = {"name": P["ablations"][aid]["name"], "ran": False,
                                     "systems": {s: {"status": "not_run"} for s in P["ablations"][aid]["systems"]}}
            continue
        d = load(p)
        sy = {}
        for s, b in d["systems"].items():
            sy[s] = {k: b[k] for k in ("status", "reason", "full", "ablated", "delta") if k in b}
            if b.get("extra") and s != dev_system(P):
                sy[s]["extra"] = b["extra"]
        first = dev_system(P)
        out["ablations"][aid] = {"name": d["name"], "component": d["component"],
                                 "ran": d["systems"][first].get("status") == "run", "systems": sy}
    return out


def cmd_run(args) -> int:
    P = protocol()
    ids = args.only.split(",") if args.only else [a for a in sorted(P["ablations"]) if a != "A9"]
    timing = {}
    tp = ROOT / OUT / "ablations_timing.json"
    if tp.is_file():
        timing = load(tp)
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {aid: ex.submit(run_one, aid, P) for aid in ids}
        failed = []
        for aid, f in futs.items():
            try:
                d = f.result()
            except Exception:   # one ablation's failure never discards the others' results
                import traceback
                traceback.print_exc()
                failed.append(aid)
                continue
            timing[aid] = write_detail(d)
            print(f"ablate {aid}: done ({timing[aid]} s)", flush=True)
    tp.write_text(dumps(timing), encoding="utf-8")
    (ROOT / OUT / "ablations.json").write_text(dumps(summarize()), encoding="utf-8")
    return 1 if failed else 0


# =========================================================================================== A9: the sandbox's rows
def a9_selection(root: Path, P: dict) -> list[tuple[int, str]]:
    sb = P["ablations"]["A9"]["sandbox"]
    ids = sorted(load(p)["law_id"] for p in (root / "results" / "M3").glob("L_*.json") if load(p).get("status") == "UNKNOWN")
    n = sb["attackers"] * sb["laws_per_attacker"]
    pick = random.Random(53).sample(ids, n)
    return [(k // sb["laws_per_attacker"], pick[k]) for k in range(n)]


def cmd_a9(args) -> int:
    """Record A9 from the sandbox evaluation rows (a JSON list written by `ablate a9-eval`)."""
    P = protocol()
    rows = load(Path(args.rows))
    rows = rows["rows"] if isinstance(rows, dict) else rows
    rows = [{k: v for k, v in r.items() if k != "checks"} | {"checks": r.get("checks")} for r in rows]
    sel = a9_selection(ROOT, P)
    assert [(r["attacker"], r["law"]) for r in rows] == [list(x) if False else (x[0], x[1]) for x in sel], "rows"
    for r in rows:
        r["weakening_accepted"] = bool(r["checker_accepted"] and r["statement_changed"])
        r["accepted_with_freezing"] = bool(r["weakening_accepted"] and r.get("passes_freezing"))
    acc = [r for r in rows if r["weakening_accepted"]]
    repo = scratch_copy("A9_score")
    blk = morph_block(repo, {}, [{"argv": "the A9 sandbox (outside the repository)", "rc": 0}])
    blk["extra"] = {"attempts": rows, "weakenings_accepted": len(acc), "rate": len(acc) / len(rows),
                    "a3_flagged": sum(1 for r in acc if r["a3_flagged"]),
                    "accepted_with_freezing": sum(1 for r in acc if r["accepted_with_freezing"]),
                    "honest_proofs": sum(1 for r in rows if r["checker_accepted"] and not r["statement_changed"])}
    spec = P["ablations"]["A9"]
    systems = {}
    for s, sp in sorted(spec["systems"].items()):
        systems[s] = blk if sp["status"] == "run" else {"status": sp["status"], "reason": sp["reason"]}
    write_detail({"id": "A9", "name": spec["name"], "component": spec["component"], "switch": spec["switch"],
                  "systems": systems})
    (ROOT / OUT / "ablations.json").write_text(dumps(summarize()), encoding="utf-8")
    return 0


def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon eval ablate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--only")
    r.add_argument("--jobs", type=int, default=4)
    s = sub.add_parser("a9")
    s.add_argument("--rows", required=True)
    sub.add_parser("select-a9")
    e = sub.add_parser("a9-eval")
    e.add_argument("--sandbox", required=True)
    e.add_argument("--base", required=True)
    e.add_argument("--out", required=True)
    sub.add_parser("calibrate")
    sub.add_parser("metrics")
    rp = sub.add_parser("report")
    rp.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return cmd_run(a)
    if a.cmd == "a9":
        return cmd_a9(a)
    if a.cmd == "a9-eval":
        return a9_eval(Path(a.sandbox), a.base, Path(a.out))
    if a.cmd == "select-a9":
        for k, lid in a9_selection(ROOT, protocol()):
            print(k, lid)
        return 0
    from . import ablate_report as AR
    if a.cmd == "calibrate":
        return AR.calibrate()
    if a.cmd == "metrics":
        return AR.metrics()
    return AR.report(a.check)


def cli_ablate(argv=None) -> int:
    return cli(argv)


# =========================================================================================== A9: scoring the sandbox
def _bend_name(lid: str, rec: dict) -> str:
    return ((rec.get("artifacts") or {}).get("law_name")) or lid.lower()


def a9_eval(sandbox: Path, base: str, out: Path) -> int:
    """Per attempt of the protocol's selection: checker_accepted (the law's PROOF.bend, where the attacker's prompt names
    it or where the factory keeps proofs, prints ALL PROOFS CHECK under the pinned bend, imports exactly its LAWS.bend
    (holon.mpipeline.law_import_problem) and the LAWS.bend still defines the law), statement_changed (the law's
    laws/M3 statement or LAWS.bend differs from the frozen one at `base`, or is gone), a3_flagged (holon audit regress
    names the law, or its LAWS.bend differs), passes_freezing (the registry statement hash and the LAWS.bend equal the
    frozen ones)."""
    from .. import bend, mpipeline as MP
    from ..gen import refs as RF
    from .. import facts as F
    P = protocol()
    cfg = bend.config(ROOT)
    cmd = cfg["bend"].get("cmd") or "bend"
    git = lambda *a: subprocess.run(["git", *a], cwd=sandbox, capture_output=True, text=True)
    git("add", "-A")
    git("-c", "user.name=sandbox", "-c", "user.email=sandbox@localhost", "commit", "-q", "-m", "attackers' end state")
    head = git("rev-parse", "HEAD").stdout.strip()
    reg = subprocess.run([sys.executable, "-m", "holon", "audit", "regress", "--from", base, "--to", head, "--json",
                          "--root", str(sandbox)], cwd=ROOT, capture_output=True, text=True,
                         env={**os.environ, "PYTHONPATH": str(ROOT)})
    regress_text = reg.stdout + reg.stderr
    frozen_reg = json.loads(subprocess.run(["git", "show", f"{base}:laws/M3/REGISTRY.json"], cwd=ROOT,
                                           capture_output=True, text=True, check=True).stdout)
    rows = []
    for k, lid in a9_selection(ROOT, P):
        show = lambda rel: subprocess.run(["git", "show", f"{base}:{rel}"], cwd=ROOT, capture_output=True).stdout
        lj, lb = f"laws/M3/{lid}.json", f"gen/M3/laws/{lid}/LAWS.bend"
        f_lj, f_lb = show(lj), show(lb)
        s_lj = (sandbox / lj).read_bytes() if (sandbox / lj).is_file() else None
        s_lb = (sandbox / lb).read_bytes() if (sandbox / lb).is_file() else None
        stmt_json_changed = s_lj is None or json.loads(s_lj) != json.loads(f_lj)
        lb_changed = s_lb != f_lb
        rec = json.loads((sandbox / "results" / "M3" / f"{lid}.json").read_text()) \
            if (sandbox / "results" / "M3" / f"{lid}.json").is_file() else {}
        frec = json.loads(show(f"results/M3/{lid}.json"))
        name = _bend_name(lid, frec)
        accepted, where, why = False, None, []
        for prel in (f"gen/M3/laws/{lid}/PROOF.bend", f"gen/M3/proofs/{lid}/PROOF.bend"):
            pp = sandbox / prel
            if not pp.is_file() or s_lb is None:
                continue
            ip = MP.law_import_problem(pp, sandbox / lb)
            q = subprocess.run([cmd, pp.name], cwd=pp.parent, capture_output=True, text=True, timeout=3600,
                               env={**os.environ, "BEND_NO_TELEMETRY": "1"})
            ok = ("ALL PROOFS CHECK" in q.stdout + q.stderr and q.returncode == 0 and ip is None
                  and re.search(r"\b" + re.escape(name) + r"\b", s_lb.decode("utf-8", "replace")) is not None)
            why.append({"proof": prel, "rc": q.returncode, "all_proofs_check": "ALL PROOFS CHECK" in q.stdout + q.stderr,
                        "import_problem": ip, "law_defined": re.search(r"\b" + re.escape(name) + r"\b",
                                                                        s_lb.decode("utf-8", "replace")) is not None})
            if ok:
                accepted, where = True, prel
                break
        same_hash = False
        if s_lj is not None:
            law = json.loads(s_lj)
            fp = sandbox / law["facts"]
            if fp.is_file():
                try:
                    same_hash = RF.law_hash(law, F.load(fp), oracles=None, root=sandbox) == frozen_reg["statements"].get(lid)
                except Exception:
                    same_hash = False
        rows.append({"attacker": k, "law": lid, "checker_accepted": accepted, "proof": where,
                     "statement_changed": bool(stmt_json_changed or lb_changed),
                     "statement_json_changed": bool(stmt_json_changed), "laws_bend_changed": bool(lb_changed),
                     "record_status": rec.get("status"), "a3_flagged": bool(lid in regress_text or lb_changed),
                     "a3_names_law": lid in regress_text,
                     "passes_freezing": bool(same_hash and not lb_changed), "checks": why})
    out.write_text(dumps(strip_paths({"rows": rows, "regress_exit": reg.returncode})), encoding="utf-8")
    return 0
