"""The kill decision and the survivor class of one record (instrument kill_criterion, survivor_classes, equivalence
contradictions, reporting plan_literal), computed from the record's own law entries.

A law entry carries baseline and mutant statuses, own_input {sha256, changed}, predicted, site_in_mutated_function,
proof {generator, exit_code, marker, verdict, model_verdict}, hits, replay [{label, mutant, original}], witness,
counter_law {exit_code, marker}, falsifier {label, tried, kind, model_tied, role, revert_line}.
"""
from __future__ import annotations

MARK_OK = "ALL PROOFS CHECK"
MARK_FAIL = "SOME PROOFS FAIL"
STATUSES = ("PROVED", "REFUTED", "UNKNOWN")
KILLS = ("K1", "K2")
CLASS_ORDER = ("equivalent", "error", "extraction_gap", "masked", "baseline_finding", "proof_lost_unwitnessed",
               "rule_gap")


def localized_hit(e: dict):
    """The first replayed hit that the mutant code shows and the original code does not (replay.hits)."""
    for r in e.get("replay") or []:
        if r["mutant"] is True and r["original"] is False:
            return r["label"]
    return None


def k2_rejected(e: dict) -> bool:
    """K2 (b): the baseline generator's attempt completed and the checker rejected the proof over a generated model
    that checks alone."""
    pr = e.get("proof") or {}
    return pr.get("exit_code") is not None and pr.get("verdict") == MARK_FAIL and pr.get("model_verdict") == MARK_OK


def how(e: dict):
    """The obstruction one law entry shows (kill_criterion), or None."""
    b, m = e["baseline"], e["mutant"]
    rep = e.get("replay") or []
    local = localized_hit(e)
    if b == "REFUTED":
        return "masked_obstruction" if e.get("predicted") is True and local is not None else None
    if m == "REFUTED" and b in ("PROVED", "UNKNOWN", "absent"):
        eligible = b in ("PROVED", "UNKNOWN") or e.get("site_in_mutated_function") is True
        checked = (e.get("counter_law") or {}).get("marker") == MARK_OK
        if eligible and checked and local is not None and e.get("witness") == local:
            return "K1"
        if not any(r["mutant"] is True for r in rep):
            return "replay_disagreement"
        if all(r["original"] is True for r in rep if r["mutant"] is True):
            return "baseline_finding"
        return None
    if b == "PROVED" and m == "UNKNOWN" and (e.get("own_input") or {}).get("changed") is True and k2_rejected(e):
        f = e.get("falsifier")
        return "K2" if f and f.get("kind") in ("falsification", "partiality") else "proof_lost_unwitnessed"
    return None


def kill(rec: dict) -> dict:
    by, unpredicted = [], []
    for law in sorted(rec["laws"]):
        e = rec["laws"][law]
        h = e.get("how")
        if h in KILLS:
            (by if e["predicted"] else unpredicted).append({"law": law, "how": h})
    return {"killed": bool(by), "by": by, "unpredicted": unpredicted}


def recomputed_only(rec: dict, k: dict) -> list:
    rp = (rec.get("recomputed") or {}).get("predicted") or {}
    inside = {law for v in rp.values() for law in v}
    return [x for x in k["unpredicted"] if x["law"] in inside]


def outcome(rec: dict, k: dict) -> str:
    if k["killed"]:
        return "killed"
    if any(e["predicted"] and e["mutant"] == "error" for e in rec["laws"].values()):
        return "error"
    return "survived"


def survivor_class(rec: dict, equivalent: bool) -> tuple:
    """(class, gap_stage, rule_gap_kind): the first rule of survivor_classes that holds, in its listed order."""
    if rec["outcome"] == "killed":
        return None, None, None
    if equivalent:
        return "equivalent", None, None
    if rec["outcome"] == "error":
        return "error", None, None
    if not any(d["changed"] for d in rec["documents"].values()):
        return "extraction_gap", "frontend", None
    pred = {law: e for law, e in rec["laws"].items() if e["predicted"]}
    if not pred:
        return "rule_gap", None, "no_law"
    if any(e.get("how") == "replay_disagreement" for e in pred.values()):
        return "extraction_gap", "replay", None
    moved = {law: e for law, e in pred.items()
             if (e.get("own_input") or {}).get("changed") is True or e["baseline"] == "absent"}
    if not moved:
        return "extraction_gap", "model", None
    if all(e["baseline"] == "REFUTED" for e in moved.values()):
        return "masked", None, None
    if any(e.get("how") == "baseline_finding" for e in pred.values()):
        return "baseline_finding", None, None
    if any(e.get("how") == "proof_lost_unwitnessed" for e in pred.values()):
        return "proof_lost_unwitnessed", None, None
    return "rule_gap", None, "law_unmoved"


def survivor_why(rec: dict, cls: tuple) -> str:
    """A mechanical account of the rule that gave the class."""
    c, stage, kind = cls
    pred = sorted(law for law, e in rec["laws"].items() if e["predicted"])
    if c == "equivalent":
        return "adjudicated equivalent"
    if c == "error":
        errs = sorted({law for law, e in rec["laws"].items() if e["predicted"] and e["mutant"] == "error"})
        return "predicted laws in error: " + ", ".join(errs)
    if c == "extraction_gap" and stage == "frontend":
        return "no extracted document changed (normalized sha256)"
    if c == "rule_gap" and kind == "no_law":
        return "the predicted set is empty"
    if c == "extraction_gap" and stage == "replay":
        return "replay disagreements: " + ", ".join(rec["replay_disagreements"])
    if c == "extraction_gap" and stage == "model":
        changed = sorted(p for p, d in rec["documents"].items() if d["changed"])
        return f"documents changed ({', '.join(changed)}) and no predicted law's own decided input changed"
    moved = sorted(law for law in pred if (rec["laws"][law].get("own_input") or {}).get("changed") is True
                   or rec["laws"][law]["baseline"] == "absent")
    if c == "masked":
        return "every predicted law whose own input changed is REFUTED at baseline: " + ", ".join(moved)
    if c == "baseline_finding":
        return "baseline findings: " + ", ".join(rec["baseline_findings"])
    if c == "proof_lost_unwitnessed":
        return "proof lost without a localized witness: " + ", ".join(rec["proof_lost_unwitnessed"])
    unmoved = [f"{law} {rec['laws'][law]['baseline']}->{rec['laws'][law]['mutant']}" for law in moved
               if rec["laws"][law]["baseline"] != "REFUTED"]
    return "re-decided on a changed input, kept its status: " + ", ".join(unmoved)


def finish(rec: dict, equivalent: bool | None) -> dict:
    """Fill the record's derived fields from its law entries (in place): each law's how, kill, recomputed_only, the
    obstruction lists, the outcome and, for a catalog mutant (equivalent not None), its survivor class."""
    for e in rec["laws"].values():
        e["how"] = how(e)
    k = kill(rec)
    rec["kill"] = k
    rec["recomputed_only"] = recomputed_only(rec, k)
    for key, h in (("masked_obstructions", "masked_obstruction"), ("proof_lost_unwitnessed", "proof_lost_unwitnessed"),
                   ("replay_disagreements", "replay_disagreement"), ("baseline_findings", "baseline_finding")):
        rec[key] = sorted(law for law, e in rec["laws"].items() if e["how"] == h)
    rec["outcome"] = outcome(rec, k)
    if equivalent is None:
        rec["class"], rec["gap_stage"], rec["rule_gap_kind"] = None, None, None
    else:
        rec["class"], rec["gap_stage"], rec["rule_gap_kind"] = survivor_class(rec, equivalent)
    return rec


def plan_literal(rec: dict) -> bool:
    """reporting.plan_literal: some predicted law moves to REFUTED with a checked counter-law and a hit that replays on
    the mutant (no two-sided test), or satisfies K2 (a) and (b) (no (c))."""
    for e in rec["laws"].values():
        if not e["predicted"]:
            continue
        b, m = e["baseline"], e["mutant"]
        eligible = b in ("PROVED", "UNKNOWN") or (b == "absent" and e.get("site_in_mutated_function") is True)
        if m == "REFUTED" and eligible and (e.get("counter_law") or {}).get("marker") == MARK_OK \
                and any(r["mutant"] is True for r in e.get("replay") or []):
            return True
        if e.get("how") in ("K2", "proof_lost_unwitnessed"):
            return True
    return False


def contradictions(rec: dict) -> tuple[list, bool]:
    """equivalence.contradictions for an 'equivalent' verdict: (why, reachable)."""
    why, laws = [], set()
    k1 = {x["law"] for x in rec["kill"]["by"] + rec["kill"]["unpredicted"] if x["how"] == "K1"}
    if k1:
        why.append("K1")
        laws |= k1
    fal = {law for law, e in rec["laws"].items() if e.get("falsifier")}
    if fal:
        why.append("K2 (c)")
        laws |= fal
    if rec["masked_obstructions"]:
        why.append("masked")
        laws |= set(rec["masked_obstructions"])
    if rec.get("corpus_detected"):
        why.append("corpus")
    fits = any(rec["laws"][law].get("witness_fits_entry") is True for law in laws)
    return why, bool(why) and (rec.get("corpus_detected") is True or fits)
