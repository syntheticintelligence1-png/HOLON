"""I51's adversarial phase (run by the builder after the run; not a preregistered instrument, added after the prereg).

  python -m tests_m4.i51_adversarial [--out docs/iterations/I51/adversarial.json] [--probe DIR]

It tries to inflate recall and precision over the committed rows of results/eval/holon/corpus.json and reports what each
inflation would read, beside the preregistered scoring (tests_m4/_i51.py), so that a reader sees how far each loosening
moves the numbers and that the preregistered rules reject it:

  A1 any rule: a REFUTED, localized law of any rule counts for the entry's label (S5 asks for the label rule).
  A2 file level: a law localizes when it names any line of an entry file (S3 asks for a locus interval).
  A3 closure spans: the sites also take the src span of every action a law's DERIVATION entry names (entry_points,
     closure, actions), not only the witness's actions (S2).
  A4 any status: a derived law of the label rule meeting the locus counts, PROVED or UNKNOWN too (S5 asks REFUTED).
  A5 unreplayed as true: every finding counts as a true defect (S4 asks localized, and keeps unreplayed apart).
  A6 window: the locus is widened by 20 lines on each side.

It also runs a positive control (--probe DIR: a test-milestone tree with laws/, records/ and facts/ of a planted
contract, such as the I31 toy run of the prereg's probe): a synthetic locus on the REFUTED law's own action must give a
detection under S1-S5, and a locus elsewhere must not.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tests_m4 import _i51 as I


def _actions_named(der: dict) -> set[str]:
    out = set()
    for k in ("entry_points", "closure", "actions", "pair", "first", "second", "action"):
        v = der.get(k)
        if isinstance(v, str):
            out.add(v)
        elif isinstance(v, list):
            out.update(x for x in v if isinstance(x, str))
    return out


def loose_sites(r: dict, law_id: str) -> list[list]:
    d = I.OUT / r["id"]
    base = I.sites(law_id, d, r["files"])
    der = {e["law_id"]: e for e in I.load(d / "laws" / "DERIVATION.json")["laws"]}.get(law_id, {})
    law = I.load(d / "laws" / f"{law_id}.json")
    fp = d / "facts" / Path(law["facts"]).name
    doc = I.load(fp) if fp.is_file() else {}
    acts = _actions_named(der)
    extra = I.spans_in([a.get("src") for a in doc.get("actions") or [] if a.get("name") in acts], r["files"])
    return sorted({tuple(x) for x in base + extra})


def widen(loc: dict, n: int) -> dict:
    return {f: [[max(1, s - n), t + n] for s, t in iv] for f, iv in loc.items()}


def file_level(loc: dict) -> dict:
    return {f: [[1, 10 ** 9]] for f in loc}


def variants(rows: list[dict]) -> dict:
    out = {}

    def tally(name, det_fn, true_fn=None):
        det = [r["id"] for r in rows if det_fn(r)]
        n = sum(1 for r in rows for x in r["laws"] if x["status"] == "REFUTED")
        tr = sum(1 for r in rows for x in r["laws"] if x["status"] == "REFUTED" and (true_fn or (lambda r, x: x["class"] == "true_defect"))(r, x))
        out[name] = {"detected": det, "findings": n, "true_defect": tr, "precision": (tr / n) if n else None}

    lab = lambda r, x: x["rule"] == r["label"]
    ref = lambda x: x["status"] == "REFUTED"
    tally("preregistered", lambda r: r["detected"])
    tally("A1_any_rule", lambda r: r["detected_any"])
    tally("A2_file_level", lambda r: any(ref(x) and lab(r, x) and I.localized(x["sites"], file_level(r["locus"])) for x in r["laws"]))
    tally("A3_closure_spans", lambda r: any(ref(x) and lab(r, x) and I.localized(loose_sites(r, x["law_id"]), r["locus"]) for x in r["laws"]))
    tally("A4_any_status", lambda r: any(lab(r, x) and x["localized"] for x in r["laws"]))
    tally("A5_unreplayed_as_true", lambda r: r["detected"], lambda r, x: x["class"] in ("true_defect", "unreplayed"))
    tally("A6_window_20", lambda r: any(ref(x) and lab(r, x) and I.localized(x["sites"], widen(r["locus"], 20)) for x in r["laws"]))
    tally("A1_A2_A3_A4_A6_together", lambda r: any(I.localized(loose_sites(r, x["law_id"]), file_level(r["locus"])) for x in r["laws"]))
    return out


def positive_control(probe: Path) -> dict:
    """Under S1-S5, a planted entry whose locus is the REFUTED law's witness action is detected; elsewhere it is not."""
    res = {}
    for rp in sorted((probe / "records").glob("L*.json")):
        rec = I.load(rp)
        if rec.get("status") != "REFUTED":
            continue
        lid = rp.stem
        law = I.load(probe / "laws" / f"{lid}.json")
        doc = I.load(probe / "facts" / Path(law["facts"]).name)
        acts = I.witness_actions(rec)
        src = [a["src"] for a in doc["actions"] if a["name"] in acts]
        f = src[0].rsplit(":", 1)[0]
        a, _, b = src[0].rsplit(":", 1)[1].partition("-")
        files = [f]
        s = I.sites(lid, probe, files)
        hit = {f: [[int(a), int(b or a)]]}
        miss = {f: [[10 ** 6, 10 ** 6 + 1]]}
        row = lambda loc: {"label": law["rule"], "laws": [{"rule": law["rule"], "status": "REFUTED",
                                                            "localized": I.localized(s, loc)}]}
        res[lid] = {"sites": s, "locus_hit": hit, "detected_on_hit": I.detected(row(hit)),
                    "detected_elsewhere": I.detected(row(miss)),
                    "other_rule_on_hit": I.detected({**row(hit), "label": "PAR" if law["rule"] != "PAR" else "SORT"})}
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(I.ROOT / "docs" / "iterations" / "I51" / "adversarial.json"))
    ap.add_argument("--probe")
    a = ap.parse_args()
    rows = I.load(I.ROWS)["rows"]
    doc = {"doc": __doc__.strip().splitlines()[0], "variants": variants(rows)}
    if a.probe:
        doc["positive_control"] = positive_control(Path(a.probe))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(json.dumps(doc, indent=1, sort_keys=True)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
