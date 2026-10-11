"""The M0 pipeline: model -> proof -> refutation -> result records (M0_SPEC 6)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import emit, ir, model_eval, refute
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


def _check(dirp: Path, cfg) -> dict:
    code, out, secs = model_eval.run_bend(["PROOF.bend"], cwd=dirp, cfg=cfg)
    return {"exit_code": code, "output": out, "seconds": secs,
            "marker": model_eval.first_marker(out)}


def _verdict(dirp: Path, cfg) -> tuple[bool, float]:
    code, out, secs = model_eval.run_bend(["PROOF.bend", "--verdict"], cwd=dirp, cfg=cfg)
    return (code == 0 and model_eval.first_marker(out) == MARK_OK), secs


def run_law(law: dict, facts: dict, gen_dir: Path, facts_path, root: Path, cfg: dict) -> dict:
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
        "artifacts": {"laws": None, "proof": None, "model": _rel(gen_dir / "model" / "morph_header.bend", root),
                      "law_name": None},
        "checker": {"exit_code": None, "marker": "not_run"},
        "attempts": attempts,
        "triage": "none",
        "replay": {"status": "not_run"},
    }

    # 2. Proof attempt: refl_after_open.
    _write_law_dir(d, emit.emit_laws(law, facts), emit.emit_proof(law, facts))
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
            _write_law_dir(d, emit.emit_counter_laws(law, facts, hit["witness"]),
                           emit.emit_counter_proof(law, facts, hit["witness"]))
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


def main(args) -> int:
    root = Path.cwd() if (Path.cwd() / "laws").is_dir() else ROOT
    milestone = args.milestone
    facts_path = Path(args.facts) if args.facts else root / DEFAULT_FACTS
    out_dir = Path(args.out) if args.out else root / "results" / milestone
    gen_dir = Path(args.gen_dir) if args.gen_dir else root / "gen" / milestone
    cfg = model_eval.config(root)

    facts = load_facts(facts_path)
    fsha = facts_sha256(facts_path)
    laws = ir.load_laws(milestone, root=root)

    if not args.no_registry:
        reg = ir.load_registry(milestone, root=root)
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
    else:
        for l in laws:
            l["facts_sha256"] = fsha

    # 1. Model.
    mdir = gen_dir / "model"
    mdir.mkdir(parents=True, exist_ok=True)
    (mdir / "morph_header.bend").write_text(bend_model(facts))

    out_dir.mkdir(parents=True, exist_ok=True)
    triage_cfg = {}
    tp = root / "config" / "triage.json"
    if tp.exists():
        triage_cfg = json.loads(tp.read_text()).get(milestone, {})

    summary = {}
    for law in sorted(laws, key=lambda l: l["law_id"]):
        rec = run_law(law, facts, gen_dir, facts_path, root, cfg)
        lid = law["law_id"]
        if rec["status"] == "REFUTED":
            ov = triage_cfg.get(lid, {})
            rec["triage"] = ov.get("triage", "finding")
        summary[lid] = rec["status"]
        (out_dir / f"{lid}.json").write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
        print(f"{lid}: {rec['status']} (verdict={rec['kernel']['verdict']})")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return 0
