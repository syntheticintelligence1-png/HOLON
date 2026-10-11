"""Case-study coverage from data (BUILD_PLAN I4; whitepaper §11, Appendix A).

    python tools/casestudy.py [--root ROOT] [--json PATH] [--md PATH]

Writes results/casestudy_coverage.json and docs/CASESTUDY.md (both generated; do not edit) from:
- the catalog in whitepaper.md: §11.3 (obstructions O1..O37 with rule and prior), §11.4 (new
  findings N1..N4), §11.6 (discharged obligations D1..D9) and Appendix A (prior findings F1..F14);
- which law bears on which id: the IR `maps_to` of each M1 law, and spec/ledger/maps_to.json for the
  M0 laws (frozen M0 IR cannot gain the field) and for checked hypotheses;
- the result records, the replay reports (replay/<M>/report.json) and results/M2/hypotheses.json.

Coverage rule (preregistered at I4, tests_m2/test_casestudy.py):
- O id: "full" iff some mapped law has a rule family named in the row's rule (PAR-domain -> PAR,
  SORT×UNDO -> SORT and UNDO), is REFUTED, and every side of its replay passed and observed the
  obstruction; "partial" if a law is mapped but none qualifies; "none" otherwise.
- D id: "full" iff a law or hypothesis is mapped, every mapped law is PROVED with non-vacuity
  inhabited or no_premises, and every mapped hypothesis is "checked"; "partial" if mapped but not
  full; "none" otherwise.
- F id / N id: through the O rows whose prior cites it: "full" iff every citing row is full, "none"
  iff no row cites it or every citing row is none, "partial" otherwise.
Counts are derived data, not predictions.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
MILESTONES = ("M0", "M1")
KIND_ORDER = ("obstruction", "discharged", "prior", "new")
KIND_TITLE = {"obstruction": "Obstructions (§11.3)", "discharged": "Discharged obligations (§11.6)",
              "prior": "Prior manual findings (Appendix A)", "new": "New findings (§11.4)"}


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i:text.index(end, i)]


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_catalog(wp: str) -> dict[str, dict]:
    cat: dict[str, dict] = {}
    for line in _between(wp, "### 11.3", "### 11.4").splitlines():
        c = _cells(line)
        if len(c) >= 5 and re.fullmatch(r"O\d+", c[0]):
            prior = sorted({k + n for k, n in re.findall(r"\b([FN])(\d+)", c[4])}, key=_key)
            cat[c[0]] = {"kind": "obstruction", "rule": c[1], "title": c[2], "prior": prior}
    sec = _between(wp, "### 11.4", "### 11.5")
    for m in re.finditer(r"\*\*(N\d+) \((O\d+)\)\.\*\*", sec):
        nxt = re.search(r"\n\*\*N\d+ |\n### ", sec[m.end():])
        body = sec[m.end():m.end() + nxt.start()] if nxt else sec[m.end():]
        cat[m.group(1)] = {"kind": "new", "title": f"{m.group(2)}: " + re.sub(r"\s+", " ", body.replace("- ", " ")).strip()}
    for line in _between(wp, "### 11.6", "### 11.7").splitlines():
        c = _cells(line)
        if len(c) >= 2 and re.fullmatch(r"D\d+", c[0]):
            cat[c[0]] = {"kind": "discharged", "title": c[1]}
    for line in _between(wp, "## Appendix A", "## Appendix B").splitlines():
        c = _cells(line)
        if len(c) >= 2 and re.fullmatch(r"F\d+", c[0]):
            cat[c[0]] = {"kind": "prior", "title": c[1]}
    return cat


def _key(cid: str) -> tuple:
    return (cid[0], int(cid[1:]))


def families(rule: str) -> list[str]:
    return sorted({re.split(r"[-\s(]", part.strip())[0] for part in re.split(r"[×/]", rule)})


def mapping(root: Path) -> tuple[dict[str, list[str]], dict[str, list[str]], dict]:
    side = load(root / "spec" / "ledger" / "maps_to.json")
    laws = {lid: list(ids) for lid, ids in side["M0"].items()}
    for p in sorted((root / "laws" / "M1").glob("L_*.json")):
        law = load(p)
        mt = law.get("maps_to")
        laws[law["law_id"]] = mt.split(" (")[0].strip().split("/") if mt else []
    return laws, dict(side.get("hypotheses", {})), dict(side.get("notes", {}))


def _sides(entry: dict) -> dict:
    if "sides" in entry:
        return dict(entry["sides"])
    return {k: v for k, v in entry.items() if isinstance(v, dict)}


def compute(root: Path) -> dict:
    root = Path(root)
    cat = parse_catalog((root / "whitepaper.md").read_text(encoding="utf-8"))
    law_ids, hyp_ids, notes = mapping(root)
    info: dict[str, dict] = {}
    for m in MILESTONES:
        rep_p = root / "replay" / m / "report.json"
        rep = load(rep_p) if rep_p.exists() else {"laws": {}}
        for p in sorted((root / "laws" / m).glob("L_*.json")):
            law = load(p)
            lid = law["law_id"]
            rec_p = root / "results" / m / f"{lid}.json"
            rec = load(rec_p) if rec_p.exists() else {}
            entry = rep.get("laws", {}).get(lid)
            ss = _sides(entry) if entry else {}
            info[lid] = {"milestone": m, "rule": law["rule"], "status": rec.get("status"),
                         "non_vacuity": (rec.get("non_vacuity") or {}).get("status"),
                         "observed": bool(ss) and all(s.get("status") == "passed" and s.get("obstruction_observed") is True
                                                      for s in ss.values()),
                         "filter_bin": rec.get("filter_bin")}
    hp = root / "results" / "M2" / "hypotheses.json"
    hyps = load(hp) if hp.exists() else {}
    ids: dict[str, dict] = {}
    for cid in sorted(cat, key=_key):
        c = cat[cid]
        if c["kind"] == "obstruction":
            ls = sorted(lid for lid, xs in law_ids.items() if cid in xs)
            fam = families(c["rule"])
            ok = [lid for lid in ls if info[lid]["rule"] in fam and info[lid]["status"] == "REFUTED" and info[lid]["observed"]]
            state = "full" if ok else "partial" if ls else "none"
            why = (f"{', '.join(ok)}: REFUTED, rule family in {fam}, obstruction observed on every replay side" if ok
                   else "; ".join(f"{lid}: {_why_not(info[lid], fam)}" for lid in ls) or "no law maps to this id")
            ids[cid] = {**c, "laws": ls, "state": state, "why": why,
                        "bins": {lid: info[lid]["filter_bin"] for lid in ls},
                        "finding_law": any(info[lid]["filter_bin"] == "finding" for lid in ok)}
        elif c["kind"] == "discharged":
            ls = sorted(lid for lid, xs in law_ids.items() if cid in xs)
            hs = sorted(h for h, xs in hyp_ids.items() if cid in xs)
            law_ok = [info[lid]["status"] == "PROVED" and info[lid]["non_vacuity"] in ("inhabited", "no_premises")
                      for lid in ls]
            hyp_ok = [(hyps.get(h) or {}).get("status") == "checked" for h in hs]
            full = bool(ls or hs) and all(law_ok) and all(hyp_ok)
            state = "full" if full else "partial" if (ls or hs) else "none"
            parts = [f"{lid}: {info[lid]['status']}, non-vacuity {info[lid]['non_vacuity']}" for lid in ls]
            parts += [f"{h}: {(hyps.get(h) or {}).get('status', 'missing')}" for h in hs]
            ids[cid] = {**c, "laws": ls, "hypotheses": hs, "state": state,
                        "why": "; ".join(parts) or "no law or hypothesis maps to this id"}
    for cid in sorted(cat, key=_key):
        c = cat[cid]
        if c["kind"] in ("prior", "new"):
            via = sorted((o for o, x in cat.items() if x["kind"] == "obstruction" and cid in x["prior"]), key=_key)
            st = [ids[o]["state"] for o in via]
            state = ("none" if not via or all(s == "none" for s in st)
                     else "full" if all(s == "full" for s in st) else "partial")
            ids[cid] = {**c, "via": via, "state": state,
                        "why": ", ".join(f"{o} {ids[o]['state']}" for o in via) or "no §11.3 row cites it"}
    counts: dict[str, dict] = {}
    for cid, x in ids.items():
        counts.setdefault(x["kind"], {"full": 0, "partial": 0, "none": 0})[x["state"]] += 1
    full_finding = sorted((cid for cid, x in ids.items() if x["kind"] == "obstruction" and x["state"] == "full"
                           and x["finding_law"]), key=_key)
    outside = sorted(lid for lid, xs in law_ids.items() if not xs)
    mapped_notes = {lid: notes[lid] for lid in sorted(notes) if law_ids.get(lid)}
    return {
        "doc": "Generated by tools/casestudy.py from whitepaper.md §11 and Appendix A, the law IR maps_to, "
               "spec/ledger/maps_to.json, the result records, the replay reports and results/M2/hypotheses.json. "
               "Do not edit. The coverage rule is preregistered in the docstring of tests_m2/test_casestudy.py "
               "(I4 prereg 15ecf46); the tool's docstring restates it. Counts are derived data, not predictions. "
               "'full' means the obstruction was observed on every replay side, whatever the side's provenance; "
               "full_with_finding lists the full obstructions with a law in the provisional finding bin.",
        "full_with_finding": full_finding,
        "ids": ids,
        "laws_outside": outside,
        "laws_outside_notes": {lid: notes[lid] for lid in outside if lid in notes},
        "law_notes": mapped_notes,
        "counts": counts,
    }


def _why_not(i: dict, fam: list[str]) -> str:
    if i["rule"] not in fam:
        return f"rule {i['rule']} is not in {fam}"
    if i["status"] != "REFUTED":
        return f"{i['status']}, so no replay can observe the obstruction"
    return "REFUTED but the obstruction is not observed on every replay side"


def markdown(doc: dict) -> str:
    ids = doc["ids"]
    out = ["# Case-study coverage", "",
           "Generated by `tools/casestudy.py`; do not edit. Source data: whitepaper §11 and Appendix A, the law IR "
           "`maps_to`, `spec/ledger/maps_to.json`, the result records, the replay reports and "
           "`results/M2/hypotheses.json`. The coverage rule is preregistered in the docstring of "
           "`tests_m2/test_casestudy.py` (I4 prereg `15ecf46`); the tool's docstring restates it. Counts are "
           "derived data, not predictions.", "",
           "\"full\" means the obstruction was observed on every replay side, whatever the side's provenance. It "
           "is not the same as a finding: the Laws column shows each law's provisional filter bin.", "",
           "| Kind | full | partial | none |", "|---|---|---|---|"]
    for k in KIND_ORDER:
        c = doc["counts"].get(k, {"full": 0, "partial": 0, "none": 0})
        out.append(f"| {KIND_TITLE[k]} | {c['full']} | {c['partial']} | {c['none']} |")
    ff = doc["full_with_finding"]
    out += ["", f"Full obstructions with a law in the provisional `finding` bin (derived): {len(ff)} "
                f"({', '.join(ff) or 'none'})."]
    for k in KIND_ORDER:
        out += ["", f"## {KIND_TITLE[k]}", ""]
        rows = [(cid, x) for cid, x in ids.items() if x["kind"] == k]
        rows.sort(key=lambda r: _key(r[0]))
        if k == "obstruction":
            out += ["| ID | Rule | Obstruction | Laws | State | Why |", "|---|---|---|---|---|---|"]
            out += [f"| {cid} | {x['rule']} | {_md(x['title'])} | {_laws_with_bins(x)} | {x['state']} | "
                    f"{_md(x['why'])} |" for cid, x in rows]
        elif k == "discharged":
            out += ["| ID | Obligation | Laws and hypotheses | State | Why |", "|---|---|---|---|---|"]
            out += [f"| {cid} | {_md(x['title'])} | {', '.join(x['laws'] + x['hypotheses']) or '—'} | {x['state']} | "
                    f"{_md(x['why'])} |" for cid, x in rows]
        else:
            out += ["| ID | Finding | Via | State |", "|---|---|---|---|"]
            out += [f"| {cid} | {_md(x['title'])} | {', '.join(x['via']) or '—'} | {x['state']} |" for cid, x in rows]
    if doc["law_notes"]:
        out += ["", "## Notes on mapped laws", ""]
        out += [f"- `{lid}`: {_md(n)}" for lid, n in doc["law_notes"].items()]
    out += ["", "## Laws outside the catalog", ""]
    if doc["laws_outside"]:
        out += [f"- `{lid}`: {_md(doc['laws_outside_notes'].get(lid, 'no note'))}" for lid in doc["laws_outside"]]
    else:
        out.append("None.")
    return "\n".join(out) + "\n"


def _laws_with_bins(x: dict) -> str:
    return ", ".join(f"{lid} ({x['bins'][lid]})" for lid in x["laws"]) or "—"


def _md(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tools/casestudy.py", description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--md", type=Path)
    a = ap.parse_args(argv)
    root = a.root.resolve()
    doc = compute(root)
    j = a.json or root / "results" / "casestudy_coverage.json"
    md = a.md or root / "docs" / "CASESTUDY.md"
    j.parent.mkdir(parents=True, exist_ok=True)
    j.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(markdown(doc), encoding="utf-8")
    c = doc["counts"]
    print("; ".join(f"{k}: {c[k]['full']} full, {c[k]['partial']} partial, {c[k]['none']} none" for k in KIND_ORDER if k in c))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
