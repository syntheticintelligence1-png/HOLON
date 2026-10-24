"""`python -m holon historical exit`: the M2 exit report (whitepaper §15.2; the contract is the docstring of
tests_m2/test_historical_exit.py, "historical exit").

    python -m holon historical exit [--milestone M2] [--check]

results/<M>/m2_exit.json and docs/M2_EXIT.md are functions of results/<M>/metrics.json, the instrument
(spec/<M>/lib/historical_exit.json), the historical refinement records (results/<M>/refinement/historical/) and the
diagrams under gen/<M>/diagram/; exit (b)'s threshold, while its metric is not applicable, is the preregistered one
(spec/<M>/predictions.json, the thresholds entry exit_b_threshold_q6; docs/HUMAN_ANSWERS.md Q6).

  exit_a  met iff metrics refinement.historical.compared > 0, refinement.historical.unexplained == 0 and
          refinement.unexplained == 0. Its windows are the instrument's; compared, disagreements and unexplained are
          refinement.historical's; substitute is false (the inputs are the chain's, never a substitute corpus).
          coverage.replayed: "<record facts>#<record diagram_edge>" of every historical record with a diagram edge;
          coverage.not_replayed: every other CODEC, CONS or TRANS edge of every diagram ("<diagram facts>#<edge id>")
          with why it was not replayed on historical inputs, from the diagram's own fields:
            CONS       a consumer edge: its consumer runs off chain (the L2 node's derivation);
            TRANS env  an environment edge (time): not a transaction;
            TRANS      the hand abstraction of an action whose extracted counterpart was replayed (for a diagram whose
                       provenance.extraction names a window declaration, the window view's action: I66, rule V7 of
                       tests_m3/test_view_evidence.py), or an action no in-scope transaction of the trans window calls;
            CODEC      an edge with no historical record.
  exit_b  read from metrics mutation_adequacy (its rate_non_equivalent and meets_threshold): "pending" while that
          metric is not_applicable (I22's replacement I60 has not run); I23 never computes it.
  closed  iff both are met.
docs/M2_EXIT.md is rendered from the same values; it holds the lines "M2 exit (a): <STATUS>" and
"M2 exit (b): <STATUS>" (MET, NOT MET, PENDING) and names every not_replayed edge with its why. --check rebuilds both
in memory and exits 1 if either differs from the committed bytes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .. import ir

ROOT = Path(__file__).resolve().parents[2]
LABEL = {"met": "MET", "not_met": "NOT MET", "pending": "PENDING"}
CRITERION_A = ("zero unexplained replay disagreements over a historical window (whitepaper §15.2, M2 exit (a)): met "
               "iff metrics refinement.historical.compared > 0, refinement.historical.unexplained == 0 and "
               "refinement.unexplained == 0")
CRITERION_B = ("mutation adequacy at or above a preregistered threshold (whitepaper §15.2, M2 exit (b)); the threshold "
               "is the human's answer Q6, preregistered")


def _load(p: Path):
    return json.loads(Path(p).read_text())


def threshold(milestone: str, root: Path, met: dict):
    ma = met.get("mutation_adequacy")
    if isinstance(ma, dict) and ma.get("threshold") is not None:
        return ma["threshold"]
    p = Path(root) / "spec" / milestone / "predictions.json"
    its = (_load(p).get("iterations") or {}) if p.is_file() else {}
    for k in sorted(its):
        t = (its[k].get("thresholds") or {}).get("exit_b_threshold_q6")
        if t is not None:
            return t
    return None


def coverage(milestone: str, root: Path, inst: dict, recs: list[dict]) -> dict:
    replayed = sorted({f"{r['facts']}#{r['diagram_edge']}" for r in recs if r.get("diagram_edge")})
    trans = {r["edge"]: r for r in recs if str(r.get("diagram_edge") or "").startswith("TRANS.")}
    codec_fns = sorted(r["edge"] for r in recs if str(r.get("diagram_edge") or "").startswith("CODEC."))
    tw = inst["windows"]["trans"]
    acts = sorted(trans)
    n_in = sum(r["compared"] for r in trans.values())
    not_replayed = {}
    for p in sorted((Path(root) / "gen" / milestone / "diagram").glob("*.json")):
        d = _load(p)
        how = ((d.get("provenance") or {}).get("extraction") or {}).get("method")
        view = ((d.get("provenance") or {}).get("extraction") or {}).get("declaration") is not None   # a window view
        for e in d.get("edges") or []:
            kind = e.get("kind")
            if kind not in ("CODEC", "CONS", "TRANS"):
                continue
            key = f"{d['facts']}#{e['id']}"
            if key in replayed:
                continue
            comp = e.get("component") or e["id"].split(".", 1)[-1]
            if kind == "CONS":
                why = (f"a consumer edge ({e.get('doc') or comp}): its consumer is the L2 node's derivation, off "
                       "chain, so no transaction of either window replays it; the node's derivation over I59's "
                       "commits is I21-P13's (auditor A2 runs the node's decoders on them), not this report's")
            elif kind == "TRANS" and e.get("env"):
                why = (f"an environment edge ({e.get('source') or comp}): not a transaction, so it has no historical "
                       "input")
            elif kind == "TRANS" and comp in trans:
                r = trans[comp]
                who = f"the window view's {comp}" if view else f"the hand abstraction of {comp}"
                why = (f"{who} ({d['facts']}" + (f", {how}" if how else "") + "); its "
                       f"extracted counterpart {r['facts']}#{r['diagram_edge']} was replayed on the trans window's "
                       f"{r['compared']} {comp} transactions")
            elif kind == "TRANS":
                why = (f"no in-scope transaction of the trans window [{tw['from_block']}, {tw['to_block']}] calls "
                       f"{comp}: its {n_in} transactions call only {', '.join(acts) or 'nothing'}"
                       + (f" (the edge's code: {e['source']})" if e.get("source") else ""))
            else:
                why = (f"no historical record of {e.get('model_fn') or comp}: the codec window replays "
                       f"{', '.join(codec_fns) or 'no codec edge'}")
            not_replayed[key] = why
    return {"replayed": replayed, "not_replayed": dict(sorted(not_replayed.items()))}


def build(milestone: str = "M2", root: Path = ROOT) -> tuple[dict, str]:
    root = Path(root)
    met = _load(root / "results" / milestone / "metrics.json")
    from .stepper import instrument
    inst = instrument(milestone, root)
    recs = [_load(p) for p in sorted((root / "results" / milestone / "refinement" / "historical").glob("*.json"))]
    rf = met.get("refinement") or {}
    h = rf.get("historical") or {}
    a_met = bool(h) and h.get("compared", 0) > 0 and h.get("unexplained") == 0 and rf.get("unexplained") == 0
    wins = {k: {x: inst["windows"][k][x] for x in ("from_block", "to_block", "to_block_hash")}
            for k in ("codec", "trans")}
    exit_a = {"criterion": CRITERION_A, "status": "met" if a_met else "not_met", "windows": wins,
              "compared": h.get("compared", 0), "disagreements": h.get("disagreements", 0),
              "unexplained": h.get("unexplained", 0), "substitute": False,
              "metrics": f"results/{milestone}/metrics.json", "coverage": coverage(milestone, root, inst, recs)}
    ma = met.get("mutation_adequacy")
    if "mutation_adequacy" in (met.get("not_applicable") or {}) or not isinstance(ma, dict):
        exit_b = {"criterion": CRITERION_B, "status": "pending", "threshold": threshold(milestone, root, met),
                  "rate_non_equivalent": None, "source": None,
                  "why": (met.get("not_applicable") or {}).get("mutation_adequacy")}
    else:
        exit_b = {"criterion": CRITERION_B, "status": "met" if ma.get("meets_threshold") else "not_met",
                  "threshold": threshold(milestone, root, met), "rate_non_equivalent": ma.get("rate_non_equivalent"),
                  "source": f"results/{milestone}/metrics.json mutation_adequacy"}
    doc = {"milestone": milestone, "exit_a": exit_a, "exit_b": exit_b,
           "closed": exit_a["status"] == "met" and exit_b["status"] == "met"}
    return doc, render(doc, inst, recs, met)


def render(doc: dict, inst: dict, recs: list[dict], met: dict) -> str:
    a, b = doc["exit_a"], doc["exit_b"]
    rf = met.get("refinement") or {}
    L = [f"# {doc['milestone']} exit", "",
         "Generated by `python -m holon historical exit` from `results/M2/metrics.json`, the instrument "
         "`spec/M2/lib/historical_exit.json`, the historical refinement records `results/M2/refinement/historical/` "
         "and the diagrams `gen/M2/diagram/`. Do not edit: `--check` reproduces it byte for byte.", "",
         f"M2 exit (a): {LABEL[a['status']]}", "",
         f"M2 exit (b): {LABEL[b['status']]}", "",
         f"M2 closed: {'yes' if doc['closed'] else 'no'}", "",
         "## Exit (a): zero unexplained replay disagreements over a historical window", "",
         a["criterion"] + ".", "",
         "| window | from block | to block | to block hash |", "|---|---|---|---|"]
    for k in ("codec", "trans"):
        w = a["windows"][k]
        L.append(f"| {k} | {w['from_block']} | {w['to_block']} | `{w['to_block_hash']}` |")
    L += ["", f"- Historical inputs compared: {a['compared']}; disagreements: {a['disagreements']}; unexplained: "
              f"{a['unexplained']}.",
          f"- Whole refinement (every M2 refinement record): compared {rf.get('compared')}, disagreements "
          f"{rf.get('disagreements')}, unexplained {rf.get('unexplained')}; refinement disagreement rate "
          f"{met.get('refinement_disagreement_rate')}.",
          "- Substitute corpus: no. Every input is the chain's (I59's snapshot and the supplementary acquisition).", "",
          "### The historical refinement records", "",
          "| edge | diagram edge | window | compared | agree | disagreements | real side |", "|---|---|---|---|---|---|---|"]
    for r in recs:
        im = r.get("implementation") or {}
        side = im.get("target") or (f"{im.get('address')} (code sha256 `{str(im.get('code_sha256'))[:16]}…`, "
                                    f"{im.get('source')} at {str(im.get('commit'))[:8]})")
        wk = "trans" if str(r.get("diagram_edge") or "").startswith("TRANS.") else "codec"
        L.append(f"| {r['edge']} | {r.get('diagram_edge') or '(domain)'} | {wk} | {r['compared']} | {r['agree']} | "
                 f"{r['disagreements']} | {side} |")
    L += ["", "### Which edges the historical windows replayed", "",
          "A certificate is relative to its refinement evidence (whitepaper §12.1). Replayed on historical inputs:", ""]
    L += [f"- `{x}`" for x in a["coverage"]["replayed"]]
    L += ["", "Not replayed on historical inputs, and why:", ""]
    L += [f"- `{k}`: {v}" for k, v in a["coverage"]["not_replayed"].items()]
    pi = (inst.get("premise_inhabitants") or {}).get("laws") or {}
    cc = inst.get("codec_corpus") or {}
    L += ["", "### The M0 certificates' domains on mainnet", "",
          f"Premise inhabitants among the {cc.get('parents')} real parent headers of the codec window (the instrument's "
          "premise_inhabitants: headers the Go validator accepts whose decoded fields satisfy the law's premises; a "
          "Bytes law counts every header):", "", "| law | inhabitants |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in sorted(pi.items())]
    zero = sorted(k for k, v in pi.items() if v == 0)
    one = sorted(k for k, v in pi.items() if v == 1)
    if zero:
        L += ["", f"A certificate of {', '.join(zero)} holds over a domain that no mainnet header of the window "
                  "occupies."]
    if one:
        bs = (inst.get("premise_inhabitants") or {}).get("v0_ssvh0_batches") or []
        L += ["", f"{', '.join(one)}: one inhabitant each"
                  + (f" (the header of batch {', '.join(str(x) for x in bs)})" if bs else "") + "."]
    L += ["", "## Exit (b): mutation adequacy", "", b["criterion"] + ".", "",
          f"- Threshold: {b['threshold']}.",
          f"- Source: {b['source'] or 'none: the metric is not applicable'}; rate of non-equivalent mutants detected: "
          f"{b['rate_non_equivalent']}."]
    if b["status"] == "pending":
        L += [f"- Pending: `metrics.json` lists mutation_adequacy as not applicable ({b.get('why')}). I23 never "
              "computes it."]
    return "\n".join(L) + "\n"


def write(doc: dict, md: str, milestone: str, root: Path) -> None:
    p = Path(root) / "results" / milestone / "m2_exit.json"
    p.write_bytes(ir.canonical_json(doc) + b"\n")
    (Path(root) / "docs" / "M2_EXIT.md").write_text(md, encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon historical exit")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed files differ from a rebuild")
    a = ap.parse_args(argv)
    try:
        doc, md = build(a.milestone, ROOT)
    except (OSError, ValueError, KeyError) as e:
        print(f"historical exit: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    jp, mp = ROOT / "results" / a.milestone / "m2_exit.json", ROOT / "docs" / "M2_EXIT.md"
    if a.check:
        bad = [str(p.relative_to(ROOT)) for p, want in ((jp, ir.canonical_json(doc) + b"\n"), (mp, md.encode()))
               if not p.is_file() or p.read_bytes() != want]
        if bad:
            print(f"historical exit --check: differs from its rebuild: {', '.join(bad)}", file=sys.stderr)
            return 1
        print("historical exit --check: m2_exit.json and docs/M2_EXIT.md are reproduced")
        return 0
    write(doc, md, a.milestone, ROOT)
    print(f"M2 exit (a): {LABEL[doc['exit_a']['status']]}; M2 exit (b): {LABEL[doc['exit_b']['status']]}")
    print(f"wrote {jp} and {mp}")
    return 0
