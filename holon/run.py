"""The M0/M1 pipeline: model -> proof -> refutation -> result records (M0_SPEC 6)."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from . import emit, ir, model_eval, refute, sm_emit, sm_gen, sm_refute
from .facts import DEFAULT_FACTS, ROOT, facts_sha256, load_facts
from .gen_model import bend_model

MARK_OK = model_eval.MARK_OK


def _rel(p: Path, root: Path):
    try:
        return str(p.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(p)


def _write_law_dir(d: Path, laws_src: str, proof_src: str):
    d.mkdir(parents=True, exist_ok=True)
    (d / "LAWS.bend").write_text(laws_src)
    (d / "PROOF.bend").write_text(proof_src)


def _check(dirp: Path, cfg, timeout=None) -> dict:
    code, out, secs = model_eval.run_bend(["PROOF.bend"], cwd=dirp, cfg=cfg, timeout=timeout)
    return {"exit_code": code, "output": out, "seconds": secs,
            "marker": model_eval.first_marker(out)}


def _verdict(dirp: Path, cfg) -> tuple[bool, float]:
    code, out, secs = model_eval.run_bend(["PROOF.bend", "--verdict"], cwd=dirp, cfg=cfg)
    return (code == 0 and model_eval.first_marker(out) == MARK_OK), secs


def run_sm_law(law: dict, facts: dict, gen_dir: Path, facts_path, root: Path, cfg: dict) -> dict:
    """Pipeline for kind 'sm' laws: reflection proof, then model-compiled BFS refutation."""
    lid = law["law_id"]
    d = gen_dir / lid
    bound = {"N": int(facts["config"]["N"]), "K": int(law["statement"]["bound"]["K"])}
    attempts = []
    record = {
        "law_id": lid,
        "statement_hash": ir.statement_hash(law),
        "facts_sha256": facts_sha256(facts_path),
        "status": None,
        "scope": "bounded",
        "bound": bound,
        "premises": [],
        "kernel": {"name": "bend", "version": model_eval.bend_version(cfg), "verdict": "not_run"},
        "artifacts": {"laws": None, "proof": None,
                      "model": _rel(gen_dir / "model" / "rollup_sm.bend", root),
                      "law_name": None},
        "checker": {"exit_code": None, "marker": "not_run"},
        "attempts": attempts,
        "revert_tag_ids": sm_gen._tag_ids(facts),
        "timings": {},
        "triage": "none",
        "replay": {"status": "not_run"},
    }
    budget = int(cfg["bend"].get("proof_budget_s", 600))
    _write_law_dir(d, sm_emit.emit_laws(law, facts), sm_emit.emit_proof(law, facts))
    try:
        chk = _check(d, cfg, timeout=budget)
    except subprocess.TimeoutExpired:
        chk = {"exit_code": -1, "output": "timeout", "seconds": float(budget), "marker": "timeout"}
    record["timings"]["plain_proof_s"] = chk["seconds"]
    names = emit.law_names(d / "LAWS.bend")
    proved = (chk["exit_code"] == 0 and chk["marker"] == MARK_OK and names == [lid.lower()])
    attempts.append({"proof_generator": "reflection_reach",
                     "result": "proved" if proved else f"rejected ({chk['marker']})",
                     "exit_code": chk["exit_code"], "seconds": chk["seconds"]})
    if not proved:
        witness_started = time.perf_counter()
        hit = sm_refute.find_witness(law, facts, facts_path=facts_path, root=root)
        record["timings"]["witness_search_s"] = time.perf_counter() - witness_started
        if hit:
            trace = hit["witness"]["trace"]
            _write_law_dir(d, sm_emit.emit_laws(law, facts, counter_trace=trace),
                           sm_emit.emit_proof(law, facts, counter_trace=trace))
            chk = _check(d, cfg)
            record["timings"]["counter_law_s"] = chk["seconds"]
            names = emit.law_names(d / "LAWS.bend")
            refuted = (chk["exit_code"] == 0 and chk["marker"] == MARK_OK
                       and names == ["cl_" + lid.lower()])
            attempts.append({"refuter": "bounded_bfs",
                             "result": "counter-law checked" if refuted else f"counter-law rejected ({chk['marker']})",
                             "exit_code": chk["exit_code"], "seconds": chk["seconds"]})
            if refuted:
                record["status"] = "REFUTED"
                record["witness"] = hit["witness"]
                record["reach_sizes"] = hit["reach_sizes"]
        else:
            attempts.append({"refuter": "bounded_bfs", "result": "no witness found",
                             "bound": bound})

    if record["status"] is None and not proved:
        shutil.rmtree(d, ignore_errors=True)
        record["status"] = "UNKNOWN"
        record["checker"] = {"exit_code": chk["exit_code"], "marker": chk["marker"],
                             "seconds": chk["seconds"]}
        return record

    record["artifacts"]["laws"] = _rel(d / "LAWS.bend", root)
    record["artifacts"]["proof"] = _rel(d / "PROOF.bend", root)
    record["artifacts"]["law_name"] = names[0]
    record["checker"] = {"exit_code": chk["exit_code"], "marker": chk["marker"],
                         "seconds": chk["seconds"]}
    if record["status"] is None:
        record["status"] = "PROVED"
    if cfg["bend"].get("verdict"):
        ok, secs = _verdict(d, cfg)
        record["kernel"]["verdict"] = "checked" if ok else "failed"
        attempts.append({"kernel": "bendtt --verdict",
                         "result": "checked" if ok else "kernel rejected the proof",
                         "seconds": secs})
        if not ok:
            record["status"] = "UNKNOWN"
            record["bound"] = {"N": bound["N"], "K": bound["K"],
                               "note": "kernel rejected the proof"}
    return record


def run_law(law: dict, facts: dict, gen_dir: Path, facts_path, root: Path, cfg: dict,
            model_name="morph_header") -> dict:
    lid = law["law_id"]
    d = gen_dir / lid
    attempts = []
    record = {
        "law_id": lid,
        "statement_hash": ir.statement_hash(law),
        "facts_sha256": facts_sha256(facts_path),
        "status": None,
        "scope": "unbounded",
        "bound": None,
        "premises": emit.premise_strings(law),
        "kernel": {"name": "bend", "version": model_eval.bend_version(cfg), "verdict": "not_run"},
        "artifacts": {"laws": None, "proof": None,
                      "model": _rel(gen_dir / "model" / f"{model_name}.bend", root),
                      "law_name": None},
        "checker": {"exit_code": None, "marker": "not_run"},
        "attempts": attempts,
        "triage": "none",
        "replay": {"status": "not_run"},
    }

    # 2. Proof attempt: refl_after_open.
    _write_law_dir(d, emit.emit_laws(law, facts, model_name=model_name),
                   emit.emit_proof(law, facts, model_name=model_name))
    chk = _check(d, cfg)
    names = emit.law_names(d / "LAWS.bend")
    proved = (chk["exit_code"] == 0 and chk["marker"] == MARK_OK and names == [lid.lower()])
    attempts.append({"proof_generator": "refl_after_open",
                     "result": "proved" if proved else f"rejected ({chk['marker']})",
                     "exit_code": chk["exit_code"], "seconds": chk["seconds"]})
    if not proved:
        # 3. Refutation on the compiled model.
        hit = refute.find_witness(law, facts, facts_path=facts_path, root=root)
        if hit:
            _write_law_dir(d, emit.emit_counter_laws(law, facts, hit["witness"], model_name=model_name),
                           emit.emit_counter_proof(law, facts, hit["witness"], model_name=model_name))
            chk = _check(d, cfg)
            names = emit.law_names(d / "LAWS.bend")
            refuted = (chk["exit_code"] == 0 and chk["marker"] == MARK_OK
                       and names == ["cl_" + lid.lower()])
            attempts.append({"refuter": "bounded_search",
                             "result": "counter-law checked" if refuted else f"counter-law rejected ({chk['marker']})",
                             "exit_code": chk["exit_code"], "seconds": chk["seconds"]})
            if refuted:
                record["status"] = "REFUTED"
                record["witness"] = hit["witness"]
                record["difference"] = {"lhs": hit["lhs"], "rhs": hit["rhs"]}
        else:
            attempts.append({"refuter": "bounded_search", "result": "no witness found",
                             "bound": refute.bound_description(law, facts)})

    if record["status"] is None and not proved:
        shutil.rmtree(d, ignore_errors=True)
        record["status"] = "UNKNOWN"
        record["scope"] = "bounded"
        record["bound"] = refute.bound_description(law, facts)
        record["checker"] = {"exit_code": chk["exit_code"], "marker": chk["marker"],
                             "seconds": chk["seconds"]}
        return record

    # Second kernel: --verdict on each PROVED/REFUTED proof.
    record["artifacts"]["laws"] = _rel(d / "LAWS.bend", root)
    record["artifacts"]["proof"] = _rel(d / "PROOF.bend", root)
    record["artifacts"]["law_name"] = names[0]
    record["checker"] = {"exit_code": chk["exit_code"], "marker": chk["marker"],
                         "seconds": chk["seconds"]}
    if record["status"] is None:
        record["status"] = "PROVED"
    if cfg["bend"].get("verdict"):
        ok, secs = _verdict(d, cfg)
        record["kernel"]["verdict"] = "checked" if ok else "failed"
        attempts.append({"kernel": "bendtt --verdict",
                         "result": "checked" if ok else "kernel rejected the proof",
                         "seconds": secs})
        if not ok:
            record["status"] = "UNKNOWN"
            record["scope"] = "bounded"
            record["bound"] = ("proof/counter-law accepted by the fast checker but "
                               "rejected by the BendTT kernel (--verdict)")
    return record


def _law_facts_path(law: dict, milestone: str, root: Path) -> Path:
    """Facts path declared by the law (M1), else the milestone default."""
    if "facts" in law:
        return root / law["facts"]
    if milestone == "M1":
        return root / "proposals" / "M1" / "facts" / "rollup_sm.json"
    return root / DEFAULT_FACTS


def main(args) -> int:
    root = Path.cwd() if (Path.cwd() / "laws").is_dir() else ROOT
    milestone = args.milestone
    out_dir = Path(args.out) if args.out else root / "results" / milestone
    gen_dir = Path(args.gen_dir) if args.gen_dir else root / "gen" / milestone
    cfg = model_eval.config(root)

    laws = ir.load_laws(milestone, root=root)
    law_facts: dict[str, Path] = {l["law_id"]: (Path(args.facts) if args.facts else _law_facts_path(l, milestone, root))
                                  for l in laws}
    facts_cache: dict[Path, dict] = {}

    if not args.no_registry:
        reg = ir.load_registry(milestone, root=root)
        if "laws" in reg:
            want = set(reg["laws"])
            got = {l["law_id"] for l in laws}
            if got != want:
                raise SystemExit(f"law set {sorted(got)} != registry {sorted(want)}")
            for l in laws:
                h = ir.statement_hash(l)
                if h != reg["laws"][l["law_id"]]:
                    raise SystemExit(f"{l['law_id']}: statement hash {h} != registry")
            for rel, want_sha in reg["facts"].items():
                if facts_sha256(root / rel) != want_sha:
                    raise SystemExit(f"facts {rel} hash != registry")
        else:
            fsha = facts_sha256(law_facts[laws[0]["law_id"]])
            if fsha != reg["facts_sha256"]:
                raise SystemExit(f"facts hash {fsha} != registry {reg['facts_sha256']}")
            want = set(reg["statements"])
            got = {l["law_id"] for l in laws}
            if got != want:
                raise SystemExit(f"law set {sorted(got)} != registry {sorted(want)}")
            for l in laws:
                h = ir.statement_hash(l)
                if h != reg["statements"][l["law_id"]]:
                    raise SystemExit(f"{l['law_id']}: statement hash {h} != registry")

    # 1. Models, one per distinct facts file.
    mdir = gen_dir / "model"
    mdir.mkdir(parents=True, exist_ok=True)
    for path in sorted(set(law_facts.values()), key=str):
        if path not in facts_cache:
            facts_cache[path] = load_facts(path)
        facts = facts_cache[path]
        if "state" in facts:
            (mdir / (path.stem + ".bend")).write_text(sm_gen.bend_model(facts))
        else:
            (mdir / (path.stem + ".bend")).write_text(bend_model(facts))

    out_dir.mkdir(parents=True, exist_ok=True)
    triage_cfg = {}
    tp = root / "config" / "triage.json"
    if tp.exists():
        triage_cfg = json.loads(tp.read_text()).get(milestone, {})

    summary = {}
    for law in sorted(laws, key=lambda l: l["law_id"]):
        facts_path = law_facts[law["law_id"]]
        facts = facts_cache[facts_path]
        if law["statement"].get("kind") == "sm":
            rec = run_sm_law(law, facts, gen_dir, facts_path, root, cfg)
        else:
            rec = run_law(law, facts, gen_dir, facts_path, root, cfg,
                          model_name=facts_path.stem)
        lid = law["law_id"]
        if rec["status"] == "REFUTED":
            ov = triage_cfg.get(lid, {})
            rec["triage"] = ov.get("triage", "finding")
        summary[lid] = rec["status"]
        (out_dir / f"{lid}.json").write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
        print(f"{lid}: {rec['status']} (verdict={rec['kernel']['verdict']})")
    if milestone == "M1":
        max_depth = {}
        for law in laws:
            if law["statement"].get("kind") == "sm":
                path = law_facts[law["law_id"]]
                max_depth[path] = max(max_depth.get(path, 0), int(law["statement"]["bound"]["K"]))
        reach_profiles = {}
        for path, depth in sorted(max_depth.items(), key=lambda item: str(item[0])):
            try:
                reach_profiles[path] = sm_refute.measure_reach(facts_cache[path], depth, root=root)
            except Exception as error:
                reach_profiles[path] = {"method": "compiled_bend_reach_k", "error": str(error)}
        for law in laws:
            if law["statement"].get("kind") != "sm":
                continue
            path = law_facts[law["law_id"]]
            k = int(law["statement"]["bound"]["K"])
            profile = dict(reach_profiles[path])
            if "per_layer" in profile:
                profile["per_layer"] = profile["per_layer"][:k + 1]
                profile["cumulative"] = profile["cumulative"][:k + 1]
            record_path = out_dir / f"{law['law_id']}.json"
            result = json.loads(record_path.read_text())
            result["model_checked"] = {"reach": profile}
            record_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    # Replay statuses are part of the record: apply the report when present so
    # regenerated output is identical to the committed records.
    from . import replay
    report_path = root / "replay" / milestone / "report.json"
    if report_path.is_file():
        replay.apply_replay(out_dir, report_path, root, milestone)
    return 0
