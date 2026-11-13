"""`holon run` for codec laws (BUILD_PLAN I24; "Deciding the laws" in the docstring of tests_m3/test_derive_par.py).

holon.mpipeline.run_m1 hands every holon-ir/0.3 law whose facts are a codec document to `decide` here:

  * a holon-facts/0.1 document: the M0 machinery (holon.gen.codec01: the model of holon.gen.model, the proof
    generators of holon.gen.proofs, holon.refute's candidates and a Bend-checked counter-law);
  * a linked codec document (holon.diagram.linked): rule X9 (holon.gen.linked: the component model
    gen/<M>/model/<role>.bend, proofs over records, refutation by fills or, over the linked byte carrier, by probes;
    a byte-string law no probe refutes is UNKNOWN with its bound, gap G6).

Machine laws (holon-facts/0.2) stay with holon.mpipeline. The record is the run's usual one (v1 and v2 fields,
holon.records; evidence fields from the milestone's evidence set, or for a test milestone from the set its laws'
codec documents give, built here in memory), with non_vacuity for every PROVED law with premises, and (I43) for a
target milestone the lean4 kernel entry holon.lean.kernel_entry_v2 reads from the committed Lean report of the law's
Lean directory. The checker's word is final: PROVED and REFUTED only through a LAWS.bend / PROOF.bend pair Bend accepts
at its acceptance point (holon.mpipeline.accepted).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from . import bend, ir, records
from . import lean as LN
from .diagram import gocount as GC
from .diagram import goops as GO
from .diagram import linked as L
from .gen import codec01 as C1
from .gen import gocount as GN
from .gen import goloop as GG
from .gen import linked as GL
from .gen import refs as R

NV = "nonvac"


def _load(p: Path) -> dict | None:
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def codec_kind(law: dict, root: Path) -> str | None:
    """"linked" (a law over a linked codec document), "goops" (over a Go-op document, I67), "gocount" (over a count
    document, I90), "own" (over an OWN carrier document, I35: holon.own_run decides it), "facts01" (a holon-ir/0.3
    law over a holon-facts/0.1 document), or None (any other law: holon.mpipeline decides it)."""
    if law.get("ir_version") != "holon-ir/0.3" or not isinstance(law.get("facts"), str):
        return None
    doc = _load(Path(root) / law["facts"])
    if doc is None:
        return None
    if L.is_linked(doc):
        return "linked"
    if GO.is_goops(doc):
        return "goops"
    if GC.is_gocount(doc):
        return "gocount"
    from .own import is_own
    if is_own(doc):
        return "own"
    if C1.is_facts01(doc):
        return "facts01"
    return None


# I115 (Q88 (2)): `holon run --unbound unknown` sets this. A law is bound by the kernel cone of its statement over the
# model it is decided on (holon.bindings.kernel_cone); a statement naming a definition its model does not define cannot
# be bound, so it cannot be decided: under "unknown" such a law is UNKNOWN, recorded with the error, nothing attempted
# for it, and every other law is decided as before. None (the default): a BindingError stops the runner, as before.
UNBOUND = None
UNBOUND_BOUND = "not decided: the statement cannot be bound to its model: {}"


def unbound_error(stmt_text: str, model_src: Path, cfg: dict) -> str | None:
    """Under UNBOUND "unknown": the BindingError's text when the statement cannot be bound to the model, else None
    (and None whenever the option is off: nothing is computed)."""
    if UNBOUND != "unknown":
        return None
    from . import bindings
    try:
        bindings.kernel_cone(stmt_text, bindings.kernel_entries(model_src, cfg))
    except bindings.BindingError as e:
        return str(e)
    return None


def precheck_text(law: dict, emit) -> str:
    """F-M6-15 (HUMAN_ANSWERS Q113): the text the binding is checked on before a law is decided, under --unbound
    unknown. It is the statement text the run's own emitter writes for the law (emit(), called without deciding
    anything), so the check before the decision and the check after it (on the decided statement's text) never
    disagree on a law the emitter can express; records.ir_roots_text only where the emitter refuses the statement.
    Never computed when the option is off."""
    try:
        t = emit()
    except (C1.Unsupported, GL.Unsupported, GG.Unsupported, GN.Unsupported, ir.IRError):
        t = None
    return t if t is not None else records.ir_roots_text(law)


def emitted_text(law: dict, kind: str, doc: dict, cm, imp: str, shash: str) -> str:
    """precheck_text for a codec-runner law: the emitter its decide() writes the statement with, for its kind."""
    if kind == "linked":
        return precheck_text(law, lambda: GL.emit(law, cm.doc, imp, note=shash).text)
    if kind == "goops":
        return precheck_text(law, lambda: GG.emit(law, cm.doc, imp, note=shash).text)
    if kind == "gocount":
        return precheck_text(law, lambda: GN.emit(law, cm.doc, imp, note=shash).text)
    return precheck_text(law, lambda: C1.emit(C1.to01(law), doc, imp, header_note=shash).text)


def unbound_res(err: str) -> dict:
    return {"status": "UNKNOWN", "attempts": [{"kind": "binding", "error": err}], "bound": UNBOUND_BOUND.format(err)}


# I125 (F-M6-05, Q105 (6), Q117): `holon run --unbound-reason goops` sets this (with --unbound unknown). holon.gen.goloop
# writes an op outside its classes as the line '# <op>: unsupported (<reason>)' and defines neither <op> nor ok_<op>, so
# a Go-op law naming one cannot be bound. Under "goops" such a law stays UNKNOWN (nothing decided, nothing attempted
# beyond the binding) and its reason is goops' refusal, read from the generated model's text, the binding error kept
# beside it. Nothing else moves: a law that binds, a binding failure naming no refused op, and every other kind of law
# are as without the option. None (the default): nothing is computed.
UNBOUND_REASON = None
OP_REFUSED_BOUND = "not decided: the statement names {} that the Go-op model's generator refuses ({}), so it cannot be bound"
_REFUSAL_LINE = re.compile(r"^# (\S+): unsupported \((.*)\)$", re.M)


def goops_refusals(model_text: str) -> dict:
    """{op: {"class", "reason"}} of every op a generated Go-op model writes as '# <op>: unsupported (<reason>)'. The
    class is "straight-line" where the refusal is the straight-line class's (I117), "loop" otherwise (goloop's loop
    classes, I67 and I122, which are tried for every op that is not straight-line)."""
    out = {}
    for op, why in _REFUSAL_LINE.findall(model_text):
        out[op] = {"class": "straight-line" if ": straight-line class: " in why else "loop", "reason": why}
    return out


def op_refused_res(kind: str, stmt_text: str, model_text: str, ub: str | None) -> dict | None:
    """Under UNBOUND_REASON "goops": the UNKNOWN result of a Go-op law whose binding failed (ub) and whose statement
    names, as M.<op> or M.ok_<op> (comments stripped), an op the model refuses; None in every other case."""
    if UNBOUND_REASON != "goops" or ub is None or kind != "goops":
        return None
    from .bindings import _QUAL
    ref = goops_refusals(model_text)
    named = set()
    for tok in _QUAL.findall(re.sub(r"#[^\n]*", "", stmt_text)):
        head = tok.split(".")[0]
        for op in (head, head[3:] if head.startswith("ok_") else None):
            if op in ref:
                named.add(op)
    if not named:
        return None
    ops = [{"op": op, "class": ref[op]["class"], "reason": ref[op]["reason"]} for op in sorted(named)]
    return {"status": "UNKNOWN", "attempts": [{"kind": "op_refused", "binding_error": ub, "ops": ops}],
            "bound": OP_REFUSED_BOUND.format(", ".join(o["op"] for o in ops),
                                             "; ".join(f"{o['class']}: {o['reason']}" for o in ops))}


def _unbound(kind: str, stmt_text: str, model_src: Path, ub: str) -> dict:
    """unbound_res, or goops' refusal under UNBOUND_REASON "goops" (I125)."""
    r = op_refused_res(kind, stmt_text, model_src.read_text(encoding="utf-8"), ub) if UNBOUND_REASON else None
    return r if r is not None else unbound_res(ub)


class Models:
    """The models of the codec documents a run decides laws over, generated into gen/<M>/model/ and compiled once."""

    def __init__(self, root: Path, gen: Path, cfg: dict):
        self.root, self.gen, self.cfg = Path(root), Path(gen), cfg
        self.linked: dict = {}
        self.goops: dict = {}
        self.gocount: dict = {}
        self.facts01: dict = {}
        self.own = None   # I35: holon.own_run.Models, made on the first OWN law

    def of_linked(self, rel: str):
        if rel not in self.linked:
            raw = (self.root / rel).read_bytes()
            doc = json.loads(raw)
            sha = hashlib.sha256(raw).hexdigest()
            stem = doc["role"]
            src = self.gen / "model" / f"{stem}.bend"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text(GL.generate(doc, sha))
            cm = GL.CompiledModel.build(doc, sha, stem, self.cfg)
            self.linked[rel] = (doc, sha, cm, src, stem)
        return self.linked[rel]

    def of_goops(self, rel: str):
        """I67 (rules Y6-Y8 of tests_m3/test_go_loop.py): a Go-op document's model gen/<M>/model/<component>.bend."""
        if rel not in self.goops:
            raw = (self.root / rel).read_bytes()
            doc = json.loads(raw)
            sha = hashlib.sha256(raw).hexdigest()
            stem = doc["component"]
            src = self.gen / "model" / f"{stem}.bend"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text(GG.generate(doc, sha))
            cm = GG.CompiledModel.build(doc, sha, stem, self.cfg)
            self.goops[rel] = (doc, sha, cm, src, stem)
        return self.goops[rel]

    def of_gocount(self, rel: str):
        """I90 (rules C4-C6 of tests_m3/test_go_counts.py): a count document's model gen/<M>/model/<component>.bend."""
        if rel not in self.gocount:
            raw = (self.root / rel).read_bytes()
            doc = json.loads(raw)
            sha = hashlib.sha256(raw).hexdigest()
            stem = doc["component"]
            src = self.gen / "model" / f"{stem}.bend"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text(GN.generate(doc, sha))
            cm = GN.CompiledModel.build(doc, sha, stem, self.cfg)
            self.gocount[rel] = (doc, sha, cm, src, stem)
        return self.gocount[rel]

    def of_facts01(self, rel: str):
        if rel not in self.facts01:
            from . import facts as F
            from .gen import model as G
            from .model_eval import CompiledModel, model_name
            fp = self.root / rel
            facts = F.load(fp)
            sha = F.sha256_file(fp)
            stem = model_name(fp)
            src = self.gen / "model" / f"{stem}.bend"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text(G.generate(facts, sha))
            cm = CompiledModel.build(fp, cfg=self.cfg)
            self.facts01[rel] = (facts, sha, cm, src, stem)
        return self.facts01[rel]


# ---------------------------------------------------------------- evidence of a test milestone's PAR laws
_EV_CACHE: dict = {}


def evidence_fields(law: dict, status: str, root: Path, milestone: str) -> dict:
    """The record's evidence fields: from the milestone's committed evidence set (holon.records) for a target
    milestone; for a PAR law of a test milestone, which has no committed set, from the set its derivation built
    (test_evidence_set), when that set is rebuilt exactly (its evidence_sha256 is DERIVATION.json's); else as
    holon.records gives them (null levels for a law the set does not cover)."""
    from .diagram import evidence as EV
    from .mpipeline import test_milestone
    if not test_milestone(milestone) or law.get("rule") != "PAR":
        return records.evidence_fields(law, {"status": status}, root)
    key = (str(Path(root).resolve()), milestone)
    if key not in _EV_CACHE:
        _EV_CACHE[key] = test_evidence_set(milestone, Path(root))
    ev = _EV_CACHE[key]
    if ev is None:
        return records.evidence_fields(law, {"status": status}, root)
    ovs, _ = EV.load_overrides(root)
    ov = ((ovs or {}).get(law.get("milestone")) or {}).get(law.get("law_id"))
    return EV.expected_fields(EV.law_evidence(law, ev), status, ov)


def test_evidence_set(milestone: str, root: Path) -> dict | None:
    """A test milestone's evidence set as holon derive built it (holon.rules._given_par_inputs): the diagrams of the
    documents its laws are about (fact documents, and linked codec documents through holon.diagram.linked), the sorts
    assignment `holon sorts` gives those fact documents (computed here in memory), built with adopted=False. None
    unless it reproduces laws/<milestone>/DERIVATION.json's evidence_sha256: a record never takes evidence from a
    set its derivation did not use."""
    from .diagram import evidence as EV
    from .diagram.build import build as build_diagram
    lp = Path(root) / "laws" / milestone
    der = _load(lp / "DERIVATION.json")
    if der is None or not der.get("evidence_sha256"):
        return None
    rels = sorted({law.get("facts") for law in (_load(p) or {} for p in sorted(lp.glob("L*.json")))
                   if isinstance(law.get("facts"), str)})
    fpaths, cdocs = [], []
    try:
        for rel in rels:
            p = Path(root) / rel
            raw = p.read_bytes()
            doc = json.loads(raw)
            if L.is_linked(doc):
                cdocs.append((p, L.diagram(doc, rel, hashlib.sha256(raw).hexdigest())))
            else:
                fpaths.append(p)
        assignment = {"models": {}, "sites": [], "sorts_sha256": None}
        if fpaths:
            from .sorts.assign import run_pass
            assignment = run_pass(fpaths, Path(root), None)["assignment"]
        diagrams = {}
        for p in fpaths:
            dg = build_diagram(p, Path(root)).to_json()
            diagrams[dg["model"]] = dg
        ev = EV.build(fpaths, Path(root), diagrams=diagrams, assignment=assignment, milestone=milestone,
                      components=cdocs, adopted=False)
    except Exception:  # noqa: BLE001  (no set: the records get null levels; nothing is decided from evidence)
        return None
    return ev if ev.get("evidence_sha256") == der["evidence_sha256"] else None


# ---------------------------------------------------------------- one law
def decide(law: dict, kind: str, models: Models, milestone: str, root: Path, gen: Path, cfg: dict, kver: str,
           verdict: bool, triage: dict, report, layout, write_pair, accepted, relpath, scope_fields,
           test: bool, log=print) -> tuple[dict, dict]:
    """(record, kernel-bound entry {"model", "cone"}) of one codec law, its files written under gen."""
    from . import bindings
    from .replay import replay_status
    if kind == "own":   # I35 (rules W10, W11 of tests_m3/test_own.py)
        from . import own_run
        if models.own is None:
            models.own = own_run.Models(models.root, models.gen, models.cfg, milestone)
        return own_run.decide(law, models.own, milestone, root, gen, cfg, kver, verdict, triage, layout, write_pair,
                              accepted, relpath, scope_fields, test, log)
    lid = law["law_id"]
    rel = law["facts"]
    if kind == "linked":
        doc, sha, cm, model_src, stem = models.of_linked(rel)
        compiled = cm.artifact
    elif kind == "goops":
        doc, sha, cm, model_src, stem = models.of_goops(rel)
        compiled = cm.artifact
    elif kind == "gocount":
        doc, sha, cm, model_src, stem = models.of_gocount(rel)
        compiled = cm.artifact
    else:
        doc, sha, cm, model_src, stem = models.of_facts01(rel)
        compiled = cm.artifact
    shash = R.law_hash(law, doc, root=root)
    d = gen / lid
    ld, pd, up = layout(milestone, gen, lid)
    imp = f"{up}model/{model_src.name}"
    rec = {"law_id": lid, "statement_hash": shash, "facts_sha256": sha, "rule": law["rule"],
           "subform": law.get("subform"), "maps_to": law.get("maps_to"), "statement": ir.render_statement(law),
           "premises": ir.premises(law), "kernel": {"name": "bend", "version": kver, "verdict": "not_run"},
           "artifacts": {"laws": None, "proof": None, "model": relpath(model_src), "law_name": None},
           "checker": {"exit_code": None, "marker": "not_run"}, "witness": None, "difference": None,
           "triage": "none", "replay": {"status": "not_run", "detail": "codec laws are not replayed in I24"}}
    for x in {d, ld, pd}:
        shutil.rmtree(x, ignore_errors=True)
    stmt_text = records.ir_roots_text(law)
    if UNBOUND == "unknown":   # F-M6-15: the pre-check binds the emitter's statement text, as the check after does
        stmt_text = emitted_text(law, kind, doc, cm, imp, shash)
    ub = unbound_error(stmt_text, model_src, cfg)   # I115: the binding first (None unless --unbound unknown)
    try:
        if ub is not None:
            res = _unbound(kind, stmt_text, model_src, ub)
        else:
            ir.check_premises(law)
            ir.check_binder_types(law, doc)
            if kind == "linked":
                res = _decide_linked(law, doc, cm, ld, pd, imp, cfg, shash, write_pair, accepted)
            elif kind == "goops":
                res = _decide_goops(law, cm, ld, pd, imp, cfg, shash, write_pair, accepted)
            elif kind == "gocount":
                res = _decide_gocount(law, cm, ld, pd, imp, cfg, shash, write_pair, accepted)
            else:
                res = _decide_facts01(law, doc, cm, ld, pd, imp, cfg, shash, write_pair, accepted)
    except ir.IRError as e:
        res = {"status": "UNKNOWN", "attempts": [{"kind": "ir", "error": f"rejected by the IR rules (G3): {e}"}],
               "bound": "not searched: the IR rejects the statement"}
    if res.get("statement_text"):
        stmt_text = res["statement_text"]
    if ub is None:   # I115: a law whose decided statement cannot be bound is UNKNOWN the same way (a decision dropped)
        ub = unbound_error(stmt_text, model_src, cfg)
        if ub is not None:
            res = _unbound(kind, stmt_text, model_src, ub)
    status = res["status"]
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
            if res.get("conjunct") is not None:   # I100: the binding's counter-law sha256 is that conjunct's
                rec["failing_conjunct"] = res["conjunct"]
            t = triage.get(lid, {})
            rec["triage"] = t.get("triage", "finding")
            if t.get("why"):
                rec["triage_why"] = t["why"]
            rec["replay"] = replay_status(goops_report(root, milestone) if kind == "goops" else
                                          gocount_report(root, milestone) if kind == "gocount" else report, lid,
                                          res["witness"])
    rec.update(scope_fields(law, rec))
    rec["status"] = status
    rec["attempts"] = attempts
    cone_entry = {"model": model_src.stem, "cone": [] if ub is not None else
                  bindings.kernel_cone(stmt_text, bindings.kernel_entries(model_src, cfg))}
    # I43: the lean4 entry, from the committed Lean report under root (never one under gen), once status, witness and
    # attempts are final; none for a test milestone
    lean_entry = None if test else LN.kernel_entry_v2(LN.dir_key_for(milestone, root / rel, root), law, root / rel,
                                                     rec, root)
    rec.update(records.v2_fields(law, rec, stmt_text, model_src, rel, compiled, root, lean_entry=lean_entry,
                                 ledger_required=not test))
    if kind == "goops" and status == "REFUTED":   # I67 (rule Y8): its replay report is replay/<M>/goops/report.json
        from .filter import record_fields
        from .replay import witness_sha256
        rec["witness_provenance"], rec["filter_bin"] = record_fields(goops_report(root, milestone), lid,
                                                                     rec.get("witness"), witness_sha256)
    if kind == "gocount" and status == "REFUTED":   # I90 (rule C6): its replay report is replay/<M>/gocount/report.json
        from .filter import record_fields
        from .replay import witness_sha256
        rec["witness_provenance"], rec["filter_bin"] = record_fields(gocount_report(root, milestone), lid,
                                                                     rec.get("witness"), witness_sha256)
    rec["scope_v2"] = {**rec["scope_v2"], **scope_fields(law, rec)["scope_v2"]}
    rec.update(evidence_fields(law, status, root, milestone))
    # §8.5 (I12): model_assumptions are the hypothesis premises (a codec law has none); the ledger entries meeting the
    # cone stay in ledger_assumptions (F-M2-12)
    rec["ledger_assumptions"] = sorted(rec["model_assumptions"])
    rec["model_assumptions"] = []
    rec["non_vacuity"] = non_vacuity(law, kind, rec, doc, stem, d, cfg, root)
    return rec, cone_entry


def _decide_linked(law, doc, cm, ld, pd, imp, cfg, shash, write_pair, accepted) -> dict:
    dd = GL.decide(law, cm, ld, pd, imp, imp, cfg, shash, write_pair, accepted)
    out = {"status": dd.status, "attempts": dd.attempts, "bound": dd.bound,
           "statement_text": dd.statement.text if dd.statement else None}
    if dd.status in ("PROVED", "REFUTED"):
        out.update({"check": dd.check, "law_name": dd.em.name, "witness": dd.witness, "difference": dd.difference})
    if dd.status == "REFUTED" and dd.conjunct is not None:   # I100: a conjunction's counter-law states one conjunct
        out["conjunct"] = dd.conjunct
    return out


def _decide_goops(law, cm, ld, pd, imp, cfg, shash, write_pair, accepted) -> dict:
    dd = GG.decide(law, cm, ld, pd, imp, imp, cfg, shash, write_pair, accepted)
    out = {"status": dd.status, "attempts": dd.attempts, "bound": dd.bound,
           "statement_text": dd.statement.text if dd.statement else None}
    if dd.status in ("PROVED", "REFUTED"):
        out.update({"check": dd.check, "law_name": dd.em.name, "witness": dd.witness, "difference": dd.difference})
    return out


def _decide_gocount(law, cm, ld, pd, imp, cfg, shash, write_pair, accepted) -> dict:
    dd = GN.decide(law, cm, ld, pd, imp, imp, cfg, shash, write_pair, accepted)
    out = {"status": dd.status, "attempts": dd.attempts, "bound": dd.bound,
           "statement_text": dd.statement.text if dd.statement else None}
    if dd.status in ("PROVED", "REFUTED"):
        out.update({"check": dd.check, "law_name": dd.em.name, "witness": dd.witness, "difference": dd.difference})
    return out


def gocount_report(root: Path, milestone: str) -> dict | None:
    """I90 (rule C7): replay/<M>/gocount/report.json, the replay of the count laws' witnesses on the real code."""
    return _load(Path(root) / "replay" / milestone / "gocount" / "report.json")


def goops_report(root: Path, milestone: str) -> dict | None:
    """I67 (rule Y9): replay/<M>/goops/report.json, the replay of the Go-op laws' witnesses on the real code."""
    return _load(Path(root) / "replay" / milestone / "goops" / "report.json")


def _decide_facts01(law, facts, cm, ld, pd, imp, cfg, shash, write_pair, accepted) -> dict:
    from .gen import proofs as PG
    attempts: list = []
    try:
        law01 = C1.to01(law)
        em = C1.emit(law01, facts, imp, header_note=shash)
    except C1.Unsupported as e:
        return {"status": "UNKNOWN", "attempts": [{"kind": "emit", "error": f"unsupported statement form: {e}"}],
                "bound": "not searched: the emitter cannot express this statement faithfully"}
    for gname, gen_ in PG.GENERATORS:
        text = gen_(em, facts, imp)
        if text is None:
            continue
        pf = write_pair(ld, pd, em.text, text)
        rr = bend.check(pf, cfg)
        ok, why = accepted(rr, pf, ld / "LAWS.bend", em, text)
        attempts.append({"kind": "proof", "generator": gname, "exit_code": rr.code, "marker": rr.marker,
                         "seconds": rr.seconds, **({} if ok else {"error": why})})
        if ok:
            return {"status": "PROVED", "attempts": attempts, "check": rr, "law_name": em.name,
                    "statement_text": em.text}
    try:
        s = C1.search(law01, facts, cm)
    except C1.Unsupported as e:
        attempts.append({"kind": "refute", "error": f"unsupported: {e}"})
        return {"status": "UNKNOWN", "attempts": attempts, "bound": "not searched: the refuter cannot evaluate it",
                "statement_text": em.text}
    attempts.append({"kind": "refute", "engine": "compiled-model search", "bound": s.bound, "tried": s.tried,
                     "undefined": s.undefined, "hit": s.witness is not None, "notes": s.notes})
    if s.witness is None:
        return {"status": "UNKNOWN", "attempts": attempts, "bound": s.bound, "statement_text": em.text}
    em2 = C1.emit(law01, facts, imp, counter=True, header_note=shash)
    text = PG.counter(em2, facts, imp, s.witness)
    for x in {ld, pd}:
        shutil.rmtree(x, ignore_errors=True)
    pf = write_pair(ld, pd, em2.text, text)
    rr = bend.check(pf, cfg)
    ok, why = accepted(rr, pf, ld / "LAWS.bend", em2, text)
    attempts.append({"kind": "counter-law", "generator": "counter", "exit_code": rr.code, "marker": rr.marker,
                     "seconds": rr.seconds, **({} if ok else {"error": why})})
    if not ok:
        return {"status": "UNKNOWN", "attempts": attempts, "bound": s.bound, "statement_text": em.text}
    return {"status": "REFUTED", "attempts": attempts, "check": rr, "law_name": em2.name, "witness": s.witness,
            "difference": s.difference, "statement_text": em.text}


# ---------------------------------------------------------------- non-vacuity (G11V)
def _rel(p: Path, root: Path) -> str:
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(p)


def inhabitant(law: dict, kind: str, doc: dict, stem: str, witness: dict, note: str) -> tuple[str, str, str]:
    """(name, LAWS.bend, PROOF.bend) of a codec law's inhabitant at a witness (G11V regenerates it from these)."""
    if kind == "linked":
        return GL.inhabitant_texts(law, doc, stem, witness)
    return C1.inhabitant_texts(law, doc, stem, witness, note)


def inhabitant_witness(law: dict, kind: str, doc: dict) -> dict:
    return GL.inhabitant_witness(law, doc) if kind == "linked" else C1.inhabitant_witness(C1.to01(law), doc)


def non_vacuity(law: dict, kind: str, rec: dict, doc: dict, stem: str, d: Path, cfg: dict, root: Path) -> dict:
    from .inhabit import _base, _check, premised
    out = _base(rec)
    shutil.rmtree(d / NV, ignore_errors=True)
    if not premised(law):
        return {**out, "status": "no_premises"}
    if rec["status"] == "REFUTED":
        return {**out, "status": "counter_witness", "law": rec.get("artifacts", {}).get("laws"),
                "bound": "the accepted counter-law inhabits the premises"}
    if rec["status"] != "PROVED":
        return {**out, "bound": "not attempted: the law is not PROVED"}
    try:
        w = inhabitant_witness(law, kind, doc)
        name, laws_text, proof = inhabitant(law, kind, doc, stem, w, rec["statement_hash"])
    except (GL.Unsupported, C1.Unsupported, KeyError, ValueError) as e:
        return {**out, "bound": f"no inhabitant generated: {e}"}
    ok, why = _check(d / NV, name, laws_text, proof, cfg)
    if not ok:
        shutil.rmtree(d / NV, ignore_errors=True)
        return {**out, "witness": w, "bound": why}
    return {**out, "status": "inhabited", "law": _rel(d / NV / "LAWS.bend", root), "witness": w, "reachable": None,
            "degenerate": None, "bound": ("the premise classes at zeros (pins and correspondences applied)"
                                          if kind == "linked" else "pins with zeros elsewhere")}
