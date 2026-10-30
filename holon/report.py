"""The map from the whitepaper's case-study ids to mechanized law ids, and the comparison of the mechanized results
with section 11.8, Appendix A and section 11.3 (BUILD_PLAN I82 = I46a; the contract is rules A1-A9 and G1 of the
docstring of tests_m3/test_blind.py).

    python -m holon report --milestone M3 [--root DIR] [--check] [--results SET=DIR ..]

Writes spec/<M>/appendixA_map.json and docs/<M>_COMPARISON.md. The inputs are the whitepaper (its catalog: section
11.3's obstructions, 11.4's new findings, 11.6's discharged obligations, Appendix A's prior findings and section
11.8's rows), the sidecar spec/<M>/lib/appendixA.json (the record sets compared, the back-test tables, the curated
links and overrides), the laws and records of every set, the ledger spec/ledger/maps_to.json, the sets' prediction
files, the back-test tables and BUILD_PLAN (which iteration plans which id). Links come from the laws' and records'
maps_to, the ledger, section 11.8's law names, the back-test tables (an M3 law paired with an M0 or M1 law inherits
that law's links) and the sidecar. Each link carries the status that would agree with the whitepaper's manual result
(expect); the comparison sets each law's recorded status against it, per item and per basis (hand-written facts or
facts extracted from code). Nothing here names a law, an id of the catalog or a target: they all come from the data.

It reads records and never runs anything, so it is cheap; G1 calls regenerate_check with the milestone's regenerated
records in place of the committed ones, and a merge that changes any input regenerates both files with `holon report`.
Output is deterministic: sorted keys and lists, no time, no absolute path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "holon-appendixA-map/0.1"
SOURCES = ("sidecar", "maps_to", "ledger", "name", "backtest")
DECIDED = ("PROVED", "REFUTED", "checked", "failed")
NO_RECORD = "no record"
KINDS = {"obstruction": "O", "discharged": "D", "new": "N", "prior": "F", "row": "R"}
ORDER = "ODNFR"
BASES = ("hand", "code")
VERDICTS = ("reproduced", "partly reproduced", "held", "certified", "contradicted", "missed", "open", "not mechanized")


class ReportError(Exception):
    pass


def _load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def paths(m: str) -> dict:
    return {"sidecar": f"spec/{m}/lib/appendixA.json", "map": f"spec/{m}/appendixA_map.json",
            "doc": f"docs/{m}_COMPARISON.md"}


# ====================================================================== the catalog (A2)
def _headings(lines: list[str]) -> list[int]:
    out, fence = [], False
    for i, line in enumerate(lines):
        if line.startswith("```"):
            fence = not fence
        elif not fence and line.startswith("#"):
            out.append(i)
    return out


def _section(lines: list[str], prefix: str, with_heading: bool = False) -> list[str]:
    hs = _headings(lines)
    for k, i in enumerate(hs):
        if lines[i].startswith(prefix):
            end = hs[k + 1] if k + 1 < len(hs) else len(lines)
            return lines[i if with_heading else i + 1:end]
    return []


def cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def _table(lines: list[str], prefix: str) -> list[list[str]]:
    rows = [line for line in _section(lines, prefix) if line.startswith("|")][1:]
    return [cells(r) for r in rows if not re.fullmatch(r"\|(\s*:?-+:?\s*\|)+\s*", r.strip())]


def row_names(cell: str) -> list[str]:
    return [n.strip() for n in re.sub(r"\([^)]*\)", "", cell).split(",") if n.strip()]


def families(rule: str) -> list[str]:
    return sorted({re.split(r"[-\s(]", part.strip())[0] for part in re.split(r"[×/]", rule) if part.strip()})


PRIOR = re.compile(r"\b[FN]\d+(?:\.\d+|[a-f](?:,[a-f])*)?")


def catalog(text: str) -> dict:
    lines = text.split("\n")
    out = {}
    for c in _table(lines, "### 11.3"):
        if re.fullmatch(r"O\d+", c[0]):
            out[c[0]] = {"kind": "obstruction", "rule": c[1], "families": families(c[1]), "title": c[2],
                         "prior": PRIOR.findall(c[4])}
    for line in _section(lines, "### 11.4"):
        m = re.match(r"\*\*(N\d+) \((O\d+)\)\.\*\*(.*)$", line)
        if m:
            out[m.group(1)] = {"kind": "new", "o": m.group(2), "title": m.group(3).strip()}
    for c in _table(lines, "### 11.6"):
        if re.fullmatch(r"D\d+", c[0]):
            out[c[0]] = {"kind": "discharged", "title": c[1]}
    for c in _table(lines, "## Appendix A"):
        if re.fullmatch(r"F\d+", c[0]):
            out[c[0]] = {"kind": "prior", "title": c[1]}
    for k, c in enumerate(_table(lines, "### 11.8"), 1):
        out[f"R{k}"] = {"kind": "row", "name": c[0], "names": row_names(c[0]), "rule": c[1], "prediction": c[2],
                        "witness": c[3]}
    return out


def order_key(ident: str) -> tuple:
    return (ORDER.index(ident[0]), int(ident[1:]))


def _cites(token: str, number: str) -> bool:
    m = re.match(r"F(\d+)", token)
    return m is not None and m.group(1) == number


def planned_in(build_plan: str, ident: str) -> list[str]:
    lines = build_plan.split("\n")
    hs = _headings(lines)
    pat = re.compile(r"\b" + re.escape(ident) + r"\b")
    out: list[str] = []
    for k, i in enumerate(hs):
        if not lines[i].startswith("#### I"):
            continue
        end = hs[k + 1] if k + 1 < len(hs) else len(lines)
        if pat.search("\n".join(lines[i:end])):
            name = lines[i][len("#### "):].split(".")[0]
            if name not in out:
                out.append(name)
    return out


# ====================================================================== the record sets (A3)
def read_sets(root: Path, sc: dict, results: dict | None = None) -> list[dict]:
    results = results or {}
    out = []
    for s in sc["sets"]:
        res = Path(results[s["name"]]) if s["name"] in results else root / s["results"]
        if not res.is_dir():
            continue
        laws = {}
        for p in sorted((root / s["laws"]).glob("L*.json")):
            law = _load(p)
            rp = res / f"{law['law_id']}.json"
            if not rp.is_file():
                continue
            rec = _load(rp)
            mt = law.get("maps_to") if isinstance(law.get("maps_to"), str) else None
            if mt is None and isinstance(rec.get("maps_to"), str):
                mt = rec["maps_to"]
            laws[law["law_id"]] = {"rule": law.get("rule"), "status": rec.get("status"), "maps_to": mt}
        preds = {}
        pf = s.get("predictions")
        if pf and (root / pf).is_file():
            preds = {e["law_id"]: e.get("status") for e in _load(root / pf).get("laws", []) if not e.get("post_hoc")}
        out.append({"name": s["name"], "basis": s["basis"], "laws_dir": s["laws"], "results_dir": s["results"],
                    "laws": laws, "predictions": preds, "named": bool(pf)})
    led = sc["ledger"]
    if (root / led["path"]).is_file() and (root / led["hypotheses_results"]).is_file():
        hyps = _load(root / led["path"]).get("hypotheses", {})
        res = _load(root / led["hypotheses_results"])
        laws = {h: {"rule": "HYP", "status": (res.get(h) or {}).get("status"), "maps_to": None} for h in sorted(hyps)}
        out.append({"name": led["hypotheses_set"], "basis": "code", "laws_dir": led["path"],
                    "results_dir": led["hypotheses_results"], "laws": laws, "predictions": {}, "named": False})
    return out


# ====================================================================== the links (A4-A6)
class Links:
    def __init__(self, cat: dict, sets: list[dict]):
        self.cat = cat
        self.sets = {s["name"]: s for s in sets}
        self.by_key: dict[tuple, dict] = {}

    def add(self, item: str, set_name: str, law: str, expect, source: str, via: str) -> None:
        key = (item, set_name, law)
        if key in self.by_key:
            self.by_key[key]["also"].append(source)
            return
        self.by_key[key] = {"item": item, "set": set_name, "law": law,
                            "rule": self.sets[set_name]["laws"][law]["rule"], "expect": expect, "source": source,
                            "via": via, "also": [], "override": None}

    def generic_expect(self, item: str, s: dict, law: str):
        """A5 for a maps_to or ledger link."""
        if item.startswith("D"):
            return "checked" if s["laws"][law]["rule"] == "HYP" else "PROVED"
        if "DISCH" not in self.cat[item]["families"]:
            return "REFUTED"
        return s["predictions"].get(law)


def build_links(root: Path, sc: dict, cat: dict, sets: list[dict]) -> tuple[Links, list]:
    L = Links(cat, sets)
    rows_by_name = {c["name"]: i for i, c in cat.items() if c["kind"] == "row"}
    absent = []
    for e in sc.get("links", []):          # (sidecar)
        item = rows_by_name.get(e["item"][len("row:"):]) if e["item"].startswith("row:") else e["item"]
        s = L.sets.get(e["set"])
        if item is None or s is None or e["law"] not in s["laws"]:
            absent.append(e)
            continue
        L.add(item, e["set"], e["law"], e["expect"], "sidecar", e["source"])
    for s in sets:                         # (maps_to)
        for law, d in sorted(s["laws"].items()):
            if d["maps_to"]:
                for tok in re.split(r"[/\s]+", d["maps_to"].split("(")[0]):
                    if re.fullmatch(r"[OD]\d+", tok) and tok in cat:
                        L.add(tok, s["name"], law, L.generic_expect(tok, s, law), "maps_to", d["maps_to"])
    led = sc["ledger"]                     # (ledger)
    if (root / led["path"]).is_file():
        ledger = _load(root / led["path"])
        for set_name, entries in ((led["set"], ledger.get("M0", {})), (led["hypotheses_set"], ledger.get("hypotheses", {}))):
            s = L.sets.get(set_name)
            if s is None:
                continue
            for law, ids in sorted(entries.items()):
                if law in s["laws"]:
                    for tok in ids:
                        if tok in cat:
                            L.add(tok, set_name, law, L.generic_expect(tok, s, law), "ledger", led["path"])
    rows = sorted((i for i in cat if cat[i]["kind"] == "row"), key=order_key)
    for s in sets:                         # (name)
        if not s["named"]:
            continue
        for law in sorted(s["laws"]):
            for r in rows:
                for n in cat[r]["names"]:
                    if law == n or law.startswith(n + "_") or law == n.replace("ω", "omega"):
                        L.add(r, s["name"], law, s["predictions"].get(law), "name", n)
                        break
    for bt in sc.get("backtests", []):     # (backtest)
        p = root / bt["path"]
        if not p.is_file() or bt["set"] not in L.sets:
            continue
        for row in _load(p).get("rows", []):
            old, new = row.get(bt["old"]), row.get(bt["new"])
            if not new or new not in L.sets[bt["set"]]["laws"]:
                continue
            for (item, set_name, law), lk in sorted(L.by_key.items()):
                if set_name == bt["against"] and law == old and lk["source"] != "backtest":
                    L.add(item, bt["set"], new, lk["expect"], "backtest", f"{bt['path']}: {old}")
    for o in sc.get("overrides", []):
        lk = L.by_key.get((o["item"], o["set"], o["law"]))
        if lk is not None:
            lk["expect"] = o["expect"]
            lk["override"] = o["source"]
    for lk in L.by_key.values():
        item = lk["item"]
        family_ok = not item.startswith("O") or lk["rule"] in cat[item]["families"]
        hyp_ok = lk["rule"] != "HYP" or item.startswith("D")
        lk["counted"] = lk["expect"] is not None and family_ok and hyp_ok
        lk["also"] = sorted(lk["also"])
    return L, absent


# ====================================================================== the map (A7)
def build_map(root: Path, m: str, results: dict | None = None) -> tuple[dict, list[dict]]:
    root = Path(root)
    p = paths(m)
    if not (root / p["sidecar"]).is_file():
        raise ReportError(f"{p['sidecar']} does not exist")
    sc = _load(root / p["sidecar"])
    wp_text = (root / "whitepaper.md").read_text(encoding="utf-8")
    plan = (root / sc["planned_from"]).read_text(encoding="utf-8")
    cat = catalog(wp_text)
    sets = read_sets(root, sc, results)
    L, absent = build_links(root, sc, cat, sets)
    position = {s["name"]: k for k, s in enumerate(sets)}
    items = {}
    for ident in sorted(cat, key=order_key):
        it = dict(cat[ident])
        if it["kind"] in ("obstruction", "discharged", "row"):
            ls = sorted((lk for lk in L.by_key.values() if lk["item"] == ident),
                        key=lambda x: (position[x["set"]], x["law"]))
            it["links"] = [{k: v for k, v in lk.items() if k != "item"} for lk in ls]
        if it["kind"] in ("obstruction", "discharged"):
            it["planned"] = planned_in(plan, ident)
        if it["kind"] == "prior":
            number = ident[1:]
            it["via"] = [{"o": o, "cited": [t for t in cat[o]["prior"] if _cites(t, number)]}
                         for o in sorted((x for x in cat if cat[x]["kind"] == "obstruction"), key=order_key)
                         if any(_cites(t, number) for t in cat[o]["prior"])]
        items[ident] = it
    linked = {(lk["set"], lk["law"]) for lk in L.by_key.values()}
    unmapped = {s["name"]: sorted(law for law in s["laws"] if (s["name"], law) not in linked)
                for s in sets if s["basis"] == "code"}
    led = sc["ledger"]
    inputs = {}
    for rel in (["whitepaper.md", p["sidecar"], sc["planned_from"], led["path"], led["hypotheses_results"]]
                + [s["predictions"] for s in sc["sets"] if s.get("predictions")]
                + [bt["path"] for bt in sc.get("backtests", [])]):
        if (root / rel).is_file():
            inputs[rel] = _sha(root / rel)
    doc = {"doc": f"Generated by holon report --milestone {m} (holon/report.py, BUILD_PLAN I82) from the whitepaper's "
                  f"catalog, {p['sidecar']} and the inputs listed; do not edit. Each link is a law of a record set "
                  "that bears on a catalog item, with the source that gave the link and the status that would agree "
                  "with the whitepaper's manual result (expect; null for a law shown as context). The verdicts are in "
                  f"{p['doc']}.",
           "version": VERSION, "inputs": inputs,
           "sets": [{"name": s["name"], "basis": s["basis"], "laws": s["laws_dir"], "results": s["results_dir"],
                     "n_laws": len(s["laws"])} for s in sets],
           "items": items, "unmapped": unmapped, "absent": absent}
    return doc, sets


# ====================================================================== the verdicts (A8)
def verdicts(doc: dict, sets: list[dict]) -> dict:
    status = {s["name"]: {law: d["status"] for law, d in s["laws"].items()} for s in sets}
    basis = {s["name"]: s["basis"] for s in sets}
    items = doc["items"]

    def st(lk):
        return status.get(lk["set"], {}).get(lk["law"]) or NO_RECORD

    def one(ident: str, b: str) -> str:
        it = items[ident]
        ls = [lk for lk in it.get("links", []) if basis.get(lk["set"]) == b]
        counted = [lk for lk in ls if lk["counted"]]
        if counted:
            equal = [st(lk) == lk["expect"] for lk in counted]
            differs = any(st(lk) in DECIDED and st(lk) != lk["expect"] for lk in counted)
            if it["kind"] == "obstruction":
                if any(equal):
                    return "reproduced"
            elif all(equal):
                return "certified" if it["kind"] == "discharged" else "held"
            if differs:
                return "missed" if it["kind"] == "row" else "contradicted"
        return "open" if ls else "not mechanized"

    out = {i: {b: one(i, b) for b in BASES} for i, it in items.items() if "links" in it}
    for i, it in items.items():
        if it["kind"] == "new":
            out[i] = dict(out[it["o"]])
        elif it["kind"] == "prior":
            v = {}
            for b in BASES:
                vs = [out[x["o"]][b] for x in it["via"]]
                if vs and all(x == "reproduced" for x in vs):
                    v[b] = "reproduced"
                elif "reproduced" in vs:
                    v[b] = "partly reproduced"
                elif "contradicted" in vs:
                    v[b] = "contradicted"
                elif "open" in vs:
                    v[b] = "open"
                else:
                    v[b] = "not mechanized"
            out[i] = v
    return out


# ====================================================================== the comparison (A9)
def _cell(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def _links(it: dict, b: str, sets: list[dict]) -> str:
    status = {s["name"]: {law: d["status"] for law, d in s["laws"].items()} for s in sets}
    basis = {s["name"]: s["basis"] for s in sets}
    parts = [f"{lk['law']} ({lk['set']}) {status.get(lk['set'], {}).get(lk['law']) or NO_RECORD}"
             + ("" if lk["counted"] else " (context)")
             for lk in it.get("links", []) if basis.get(lk["set"]) == b]
    return "; ".join(parts) if parts else "—"


def _line(cs: list) -> str:
    return "| " + " | ".join(_cell(c) for c in cs) + " |"


def render(doc: dict, sets: list[dict], m: str) -> str:
    v = verdicts(doc, sets)
    items = doc["items"]
    ids = {k: sorted((i for i in items if i[0] == k), key=order_key) for k in ORDER}
    hand = ", ".join(s["name"] for s in sets if s["basis"] == "hand") or "none"
    code = ", ".join(s["name"] for s in sets if s["basis"] == "code") or "none"
    out = [f"# {m} comparison: the mechanized results against the whitepaper's case study", "",
           f"Generated by `holon report --milestone {m}` (holon/report.py, BUILD_PLAN I82) from the records, the "
           f"whitepaper's catalog and the map `{paths(m)['map']}`; do not edit. A merge that changes any input "
           "regenerates it, and G1 checks it byte for byte.", "",
           "**Contamination.** HOLON's tooling was developed on this target with the case study in view, and these "
           "results carry that contamination: this table compares the lead's own records with the whitepaper's "
           "manual analysis, so it is not a blind result. I46's blind rerun (`holon compare --blind`) measures how "
           "far a fresh session reproduces them from code alone, and the held-out target of M4 is the real control.",
           "",
           f"Bases. **hand**: the record sets {hand} (laws over hand-written facts). **code**: the record sets {code} "
           "(facts extracted from the pinned code; M2/view is M1's laws decided on the extracted Rollup's window view). "
           "A link reads `law (set) status`; \"(context)\" marks a link shown but not counted (its expect is null, or "
           "its law's rule is outside the item's rule families). Verdicts follow rule A8 of the docstring of "
           "tests_m3/test_blind.py: an obstruction is reproduced when some counted link has the status that agrees "
           "with the manual result; a section 11.8 row is held, and a discharged obligation certified, when every "
           "counted link has it.", ""]
    out += ["## Summary (the section 11.7 form)", "", "| Verdict | F ids, hand | F ids, code |", "|---|---|---|"]
    for verdict in ("reproduced", "partly reproduced", "contradicted", "open", "not mechanized"):
        out.append(_line([verdict] + [", ".join(f for f in ids["F"] if v[f][b] == verdict) or "—" for b in BASES]))
    out += ["", "| Items | Basis | " + " | ".join(VERDICTS) + " |", "|---|---|" + "---|" * len(VERDICTS)]
    for kind, label in (("R", "section 11.8 rows"), ("O", "obstructions (11.3)"), ("D", "discharged (11.6)"),
                        ("N", "new findings (11.4)")):
        for b in BASES:
            out.append(_line([label, b] + [str(sum(1 for i in ids[kind] if v[i][b] == x)) for x in VERDICTS]))
    out += ["", "## Section 11.8: the preregistered predictions", "",
            "| Row | Law | Rule | Prediction | Hand links | Hand | Code links | Code |", "|---|---|---|---|---|---|---|---|"]
    for i in ids["R"]:
        it = items[i]
        out.append(_line([i, it["name"], it["rule"], it["prediction"], _links(it, "hand", sets), v[i]["hand"],
                          _links(it, "code", sets), v[i]["code"]]))
    out += ["", "## Appendix A: the prior manual findings", "",
            "| F | Finding | O items | Hand | Code |", "|---|---|---|---|---|"]
    for i in ids["F"]:
        it = items[i]
        via = ", ".join(f"{x['o']} ({', '.join(x['cited'])})" for x in it["via"]) or "—"
        out.append(_line([i, it["title"], via, v[i]["hand"], v[i]["code"]]))
    out += ["", "## Section 11.3: obstructions", "",
            "| O | Rule | Prior | Hand links | Hand | Code links | Code | Planned in |",
            "|---|---|---|---|---|---|---|---|"]
    for i in ids["O"]:
        it = items[i]
        out.append(_line([i, it["rule"], ", ".join(it["prior"]) or "—", _links(it, "hand", sets), v[i]["hand"],
                          _links(it, "code", sets), v[i]["code"], ", ".join(it["planned"]) or "—"]))
    out += ["", "## Section 11.6: discharged obligations", "",
            "| D | Obligation | Hand links | Hand | Code links | Code | Planned in |", "|---|---|---|---|---|---|---|"]
    for i in ids["D"]:
        it = items[i]
        out.append(_line([i, it["title"], _links(it, "hand", sets), v[i]["hand"], _links(it, "code", sets),
                          v[i]["code"], ", ".join(it["planned"]) or "—"]))
    out += ["", "## Section 11.4: new findings", "", "| N | O item | Hand | Code |", "|---|---|---|---|"]
    for i in ids["N"]:
        out.append(_line([i, items[i]["o"], v[i]["hand"], v[i]["code"]]))
    out += ["", "## Mechanized laws outside the map", "",
            "Laws of the code sets that no link reaches: outside the section 11 catalog as far as the committed "
            "data and the sidecar say, or not yet mapped.", ""]
    for name, laws in doc["unmapped"].items():
        out.append(f"- **{name}** ({len(laws)}): " + (", ".join(f"`{law}`" for law in laws) or "none"))
    out += ["", "## Sidecar links without a record", ""]
    out += [f"- {e['item']} ({e['set']}): `{e['law']}`" for e in doc["absent"]] or ["None."]
    out += ["", "## Inputs", "", "| Path | sha256 |", "|---|---|"]
    out += [f"| `{p}` | `{h}` |" for p, h in sorted(doc["inputs"].items())]
    return "\n".join(out) + "\n"


# ====================================================================== regenerate, check, G1
def regenerate(root: Path, m: str, results: dict | None = None) -> tuple[str, str]:
    doc, sets = build_map(root, m, results)
    return dump(doc), render(doc, sets, m)


def regenerate_check(root: Path, m: str, results: dict | None = None) -> list[str]:
    """The files that differ from their regeneration (or are missing): [] when both are as committed. G1 passes the
    milestone's regenerated records as results {m: DIR}."""
    root = Path(root)
    map_text, doc_text = regenerate(root, m, results)
    p = paths(m)
    bad = []
    for rel, text in ((p["map"], map_text), (p["doc"], doc_text)):
        f = root / rel
        if not f.is_file():
            bad.append(f"{rel} is missing")
        elif f.read_text(encoding="utf-8") != text:
            bad.append(f"{rel} differs from its regeneration")
    return bad


def applies(root: Path, m: str) -> bool:
    """G1's clause applies to a milestone with the sidecar whose whitepaper still has section 11.8 (a blind bundle's
    redacted whitepaper has none)."""
    root = Path(root)
    if not (root / paths(m)["sidecar"]).is_file() or not (root / "whitepaper.md").is_file():
        return False
    return any(line.startswith("### 11.8") for line in (root / "whitepaper.md").read_text(encoding="utf-8").split("\n"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon report", description=__doc__.splitlines()[0])
    ap.add_argument("--milestone", default="M3")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--check", action="store_true", help="write nothing; exit 1 when a file differs or is missing")
    ap.add_argument("--results", action="append", default=[], metavar="SET=DIR",
                    help="read the set's records from DIR instead of its results directory")
    a = ap.parse_args(argv)
    results = {}
    for x in a.results:
        name, sep, d = x.partition("=")
        if not sep or not name or not d:
            print(f"holon report: --results takes SET=DIR, not {x!r}", file=sys.stderr)
            return 2
        results[name] = Path(d)
    root = a.root.resolve()
    try:
        if a.check:
            bad = regenerate_check(root, a.milestone, results)
            for b in bad:
                print(b)
            print("REPORT OK" if not bad else "REPORT DIFFERS")
            return 1 if bad else 0
        map_text, doc_text = regenerate(root, a.milestone, results)
    except ReportError as e:
        print(f"holon report: {e}", file=sys.stderr)
        return 2
    p = paths(a.milestone)
    for rel, text in ((p["map"], map_text), (p["doc"], doc_text)):
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    doc = json.loads(map_text)
    print(f"wrote {p['map']} ({len(doc['items'])} items) and {p['doc']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
