"""`holon run` for OWN laws (BUILD_PLAN I35; rules W10 and W11 of the docstring of tests_m3/test_own.py).

holon.codecrun hands every holon-ir/0.3 law whose facts are an OWN carrier document (holon.own, holon-own/0.1) to
`decide` here: the carrier's model gen/<M>/model/own_<stem>.bend (holon.gen.ownheap, compiled once per document),
then holon.gen.ownheap.decide (heap_disjoint, the bounded search over traces, counter-laws). The record is the run's
usual one (v1 and v2 fields, holon.records, with the carrier's generated ledger bundle; evidence fields from the
milestone's evidence set); no lean4 entry (W11); a REFUTED record's replay status, witness_provenance and filter_bin
come from the OWN replay report replay/<M>/own/report.json (W12), when it replayed this witness. The checker's word is
final: PROVED and REFUTED only through a LAWS.bend / PROOF.bend pair Bend accepts at its acceptance point
(holon.mpipeline.accepted).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from . import bend, ir, records
from . import own as OW
from .gen import ownheap as OH
from .gen import refs as R

KIND = "own"


def _load(p: Path) -> dict | None:
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def is_own_law(law: dict, root: Path) -> bool:
    if law.get("ir_version") != "holon-ir/0.3" or not isinstance(law.get("facts"), str):
        return False
    return OW.is_own(_load(Path(root) / law["facts"]))


def report_of(root: Path, milestone: str) -> dict | None:
    """replay/<M>/own/report.json (W12), the replay of the OWN laws' witnesses on the real code."""
    return _load(Path(root) / "replay" / milestone / "own" / "report.json")


class Models:
    """The carrier models a run decides laws over, generated into gen/<M>/model/ and compiled once."""

    def __init__(self, root: Path, gen: Path, cfg: dict, milestone: str):
        self.root, self.gen, self.cfg, self.milestone = Path(root), Path(gen), cfg, milestone
        self.models: dict = {}

    def of(self, rel: str):
        if rel not in self.models:
            raw = (self.root / rel).read_bytes()
            doc = json.loads(raw)
            sha = hashlib.sha256(raw).hexdigest()
            stem = OW.model_name(doc)
            growth = OH.growth_of(self.root, self.milestone)
            src = self.gen / "model" / f"{stem}.bend"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text(OH.generate(doc, sha, growth))
            cm = OH.CompiledModel.build(doc, sha, stem, growth, self.cfg)
            self.models[rel] = (doc, sha, cm, src, stem)
        return self.models[rel]


def decide(law: dict, models: Models, milestone: str, root: Path, gen: Path, cfg: dict, kver: str, verdict: bool,
           triage: dict, layout, write_pair, accepted, relpath, scope_fields, test: bool, log=print) -> tuple[dict, dict]:
    """(record, kernel-bound entry {"model", "cone"}) of one OWN law, its files written under gen."""
    from . import bindings
    from .codecrun import evidence_fields
    from .filter import record_fields
    from .replay import replay_status, witness_sha256
    lid = law["law_id"]
    rel = law["facts"]
    doc, sha, cm, model_src, stem = models.of(rel)
    shash = R.law_hash(law, doc, root=root)
    d = gen / lid
    ld, pd, up = layout(milestone, gen, lid)
    imp = f"{up}model/{model_src.name}"
    rec = {"law_id": lid, "statement_hash": shash, "facts_sha256": sha, "rule": law["rule"],
           "subform": law.get("subform"), "maps_to": law.get("maps_to"), "statement": ir.render_statement(law),
           "premises": ir.premises(law), "kernel": {"name": "bend", "version": kver, "verdict": "not_run"},
           "artifacts": {"laws": None, "proof": None, "model": relpath(model_src), "law_name": None},
           "checker": {"exit_code": None, "marker": "not_run"}, "witness": None, "difference": None,
           "triage": "none", "replay": {"status": "not_run", "detail": "no replay report entry"}}
    for x in {d, ld, pd}:
        shutil.rmtree(x, ignore_errors=True)
    stmt_text = records.ir_roots_text(law)
    search = OH.search_of(root, milestone)
    try:
        ir.check_premises(law)
        ir.check_binder_types(law, doc)
        dd = OH.decide(law, cm, ld, pd, imp, imp, cfg, shash, write_pair, accepted, search, scratch=d / "nv_check")
        res = {"status": dd.status, "attempts": dd.attempts, "bound": dd.bound,
               "statement_text": dd.statement.text if dd.statement else None}
        if dd.status in ("PROVED", "REFUTED"):
            res.update({"check": dd.check, "law_name": dd.em.name, "witness": dd.witness, "difference": dd.difference})
    except ir.IRError as e:
        res = {"status": "UNKNOWN", "attempts": [{"kind": "ir", "error": f"rejected by the IR rules (G3): {e}"}],
               "bound": "not searched: the IR rejects the statement"}
    except (RuntimeError, subprocess.TimeoutExpired) as e:   # the compiled model's evaluation (search, values) failed
        res = {"status": "UNKNOWN", "attempts": [{"kind": "model", "error": f"the compiled model's evaluation failed: "
                                                                          f"{type(e).__name__}: {str(e)[:1200]}"}],
               "bound": "not decided: the compiled model's evaluation failed (named in attempts)"}
    shutil.rmtree(d / "nv_check", ignore_errors=True)
    status = res["status"]
    if res.get("statement_text"):
        stmt_text = res["statement_text"]
    attempts = res["attempts"]
    for a in attempts:   # one line of the checker's first error is enough in a record
        if isinstance(a.get("error"), str) and len(a["error"]) > 1500:
            a["error"] = a["error"][:1500] + " [truncated]"
    if status == "UNKNOWN":
        for x in {d, ld, pd}:
            shutil.rmtree(x, ignore_errors=True)
        rec["scope"] = "bounded"
        rec["bound"] = res.get("bound") or "not searched"
    else:
        r = res["check"]
        rec["scope"] = "unbounded"
        rec["artifacts"].update({"laws": relpath(ld / "LAWS.bend"), "proof": relpath(pd / "PROOF.bend"),
                                 "law_name": res["law_name"]})
        rec["checker"] = {"exit_code": r.code, "marker": r.marker, "seconds": r.seconds}
        if verdict:
            v = bend.check_verdict(pd / "PROOF.bend", cfg)
            rec["kernel"]["verdict"] = "checked" if v.ok else "failed"
            attempts.append({"kind": "verdict", "kernel": "BendTT (Lean-proven)", "exit_code": v.code,
                             "marker": v.marker, "seconds": v.seconds})
        if status == "REFUTED":
            rec["witness"], rec["difference"] = res["witness"], res["difference"]
            t = triage.get(lid, {})
            rec["triage"] = t.get("triage", "finding")
            if t.get("why"):
                rec["triage_why"] = t["why"]
            rec["replay"] = replay_status(report_of(root, milestone), lid, res["witness"])
    rec.update(scope_fields(law, rec))
    rec["status"] = status
    rec["attempts"] = attempts
    cone_entry = {"model": model_src.stem, "cone": bindings.kernel_cone(stmt_text, bindings.kernel_entries(model_src, cfg))}
    rec.update(records.v2_fields(law, rec, stmt_text, model_src, rel, cm.artifact, root, lean_entry=None,
                                 ledger_required=not test))
    if status == "REFUTED":   # W11, W12: from the OWN replay report, when it replayed this witness
        rec["witness_provenance"], rec["filter_bin"] = record_fields(report_of(root, milestone), lid,
                                                                     rec.get("witness"), witness_sha256)
    rec["scope_v2"] = {**rec["scope_v2"], **scope_fields(law, rec)["scope_v2"]}
    rec.update(evidence_fields(law, status, root, milestone))
    # §8.5 (I12): model_assumptions are the hypothesis premises (an OWN law has none); the ledger entries meeting the
    # cone stay in ledger_assumptions
    rec["ledger_assumptions"] = sorted(rec["model_assumptions"])
    rec["model_assumptions"] = []
    rec["non_vacuity"] = non_vacuity(law, rec)
    return rec, cone_entry


def non_vacuity(law: dict, rec: dict) -> dict:
    """G11V's block: an OWN law has no premises. A PROVED alias law's checked inhabitant (W10) is among its attempts
    (kind "inhabitant": a concrete run where the writer writes into the view's backing past its end)."""
    from .inhabit import _base, premised
    out = _base(rec)
    if not premised(law):
        return {**out, "status": "no_premises"}
    return {**out, "bound": "an OWN law with premises is outside rule OWN"}
