"""I4: case-study coverage computed from data (whitepaper §11, Appendix A), not counted by hand.

`tools/casestudy.py` writes results/casestudy_coverage.json and docs/CASESTUDY.md from:
- the catalog in whitepaper.md: §11.3 (O ids, rule, prior), §11.4 (N ids), §11.6 (D ids) and
  Appendix A (F ids);
- which law maps to which id: the IR `maps_to` of the M1 laws, and the sidecar
  spec/ledger/maps_to.json for M0 (frozen M0 IR cannot gain the field) and for hypotheses;
- the result records, the replay reports and results/M2/hypotheses.json.

The coverage rule (BUILD_PLAN I4), fixed here and recomputed independently below:
- an O id is "full" iff some mapped law has a rule family named in the O row's rule, is REFUTED,
  and every side of its replay passed and observed the obstruction; "partial" if it has a mapped
  law but none qualifies; "none" otherwise;
- a D id is "full" iff it has a mapped law or hypothesis, every mapped law is PROVED with a
  non-vacuity status of inhabited or no_premises, and every mapped hypothesis is "checked";
  "partial" if mapped but not full; "none" otherwise;
- an F id (Appendix A) or N id (§11.4) is covered through the O rows whose prior cites it:
  "full" iff every citing row is full, "none" iff there is no citing row or every one is none,
  "partial" otherwise.
Counts are derived data, not predictions.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m2._i4 import report, sides
from tests_m2._m2 import MILESTONES, ROOT, laws, load_json, records

WP = ROOT / "whitepaper.md"
SIDECAR = ROOT / "spec" / "ledger" / "maps_to.json"
OUT_JSON = ROOT / "results" / "casestudy_coverage.json"
OUT_MD = ROOT / "docs" / "CASESTUDY.md"
TOOL = ROOT / "tools" / "casestudy.py"


def section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i:text.index(end, i)]


def catalog() -> dict:
    text = WP.read_text(encoding="utf-8")
    out = {}
    for line in section(text, "### 11.3", "### 11.4").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if re.fullmatch(r"O\d+", cells[0]):
            prior = sorted({a + b for a, b in re.findall(r"\b([FN])(\d+)", cells[4])})
            out[cells[0]] = {"kind": "obstruction", "rule": cells[1], "prior": prior}
    for n, o in re.findall(r"\*\*(N\d+) \((O\d+)\)\.\*\*", section(text, "### 11.4", "### 11.5")):
        out[n] = {"kind": "new"}
    for line in section(text, "### 11.6", "### 11.7").splitlines():
        m = re.match(r"\|\s*(D\d+)\s*\|", line)
        if m:
            out[m.group(1)] = {"kind": "discharged"}
    for line in section(text, "## Appendix A", "## Appendix B").splitlines():
        m = re.match(r"\|\s*(F\d+)\s*\|", line)
        if m:
            out[m.group(1)] = {"kind": "prior"}
    return out


def families(rule: str) -> set[str]:
    return {re.split(r"[-\s(]", part.strip())[0] for part in re.split(r"[×/]", rule)}


def law_ids_mapped() -> dict[str, list[str]]:
    side = load_json(SIDECAR)
    out = {lid: list(ids) for lid, ids in side["M0"].items()}
    for lid, law in laws("M1").items():
        mt = law.get("maps_to")
        out[lid] = re.split(r"/", mt.split(" (")[0].strip()) if mt else []
    return out


def replay_observed(m: str, lid: str) -> bool:
    entry = report(m)["laws"].get(lid)
    if not entry:
        return False
    ss = sides(m, entry)
    return bool(ss) and all(s["status"] == "passed" and s["obstruction_observed"] is True for s in ss.values())


def expected_coverage() -> dict:
    cat = catalog()
    mapped = law_ids_mapped()
    recs = {lid: (m, r) for m in MILESTONES for lid, r in records(m).items()}
    rule = {lid: law["rule"] for m in MILESTONES for lid, law in laws(m).items()}
    hyps_map = load_json(SIDECAR)["hypotheses"]
    hyps = load_json(ROOT / "results" / "M2" / "hypotheses.json")
    ids = {}
    for cid, c in cat.items():
        if c["kind"] == "obstruction":
            ls = sorted(lid for lid, xs in mapped.items() if cid in xs)
            ok = [lid for lid in ls if rule[lid] in families(c["rule"]) and recs[lid][1]["status"] == "REFUTED"
                  and replay_observed(recs[lid][0], lid)]
            ids[cid] = {"laws": ls, "state": "full" if ok else "partial" if ls else "none"}
        elif c["kind"] == "discharged":
            ls = sorted(lid for lid, xs in mapped.items() if cid in xs)
            hs = sorted(h for h, xs in hyps_map.items() if cid in xs)
            full = bool(ls or hs) and all(
                recs[lid][1]["status"] == "PROVED"
                and recs[lid][1]["non_vacuity"]["status"] in ("inhabited", "no_premises") for lid in ls
            ) and all(hyps.get(h, {}).get("status") == "checked" for h in hs)
            ids[cid] = {"laws": ls, "hypotheses": hs, "state": "full" if full else "partial" if (ls or hs) else "none"}
    for cid, c in cat.items():
        if c["kind"] in ("prior", "new"):
            via = sorted((o for o, x in cat.items() if x["kind"] == "obstruction" and cid in x["prior"]),
                         key=lambda s: int(s[1:]))
            st = [ids[o]["state"] for o in via]
            state = ("none" if not via or all(s == "none" for s in st)
                     else "full" if all(s == "full" for s in st) else "partial")
            ids[cid] = {"via": via, "state": state}
    return ids


def run_tool(root: Path, out_json: Path, out_md: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(root / "tools" / "casestudy.py"), "--root", str(root),
                           "--json", str(out_json), "--md", str(out_md)],
                          capture_output=True, text=True, timeout=600, cwd=root)


class TestCatalog(unittest.TestCase):
    def test_catalog_is_complete(self):
        cat = catalog()
        want = ({f"O{i}" for i in range(1, 38)} | {f"D{i}" for i in range(1, 10)}
                | {f"F{i}" for i in range(1, 15)} | {f"N{i}" for i in range(1, 5)})
        self.assertEqual(set(cat), want)

    def test_sidecar_covers_m0_and_names_catalog_ids(self):
        side = load_json(SIDECAR)
        self.assertEqual(set(side["M0"]), set(laws("M0")))
        cat = catalog()
        for lid, ids in law_ids_mapped().items():
            for cid in ids:
                with self.subTest(law=lid, id=cid):
                    self.assertIn(cid, cat)
                    self.assertIn(cat[cid]["kind"], ("obstruction", "discharged"))
        self.assertEqual(side["hypotheses"], {"Hyp-Z0-kzg": ["D2"]})


class TestCoverage(unittest.TestCase):
    def test_coverage_follows_the_rule(self):
        got = load_json(OUT_JSON)["ids"]
        want = expected_coverage()
        self.assertEqual(set(got), set(want))
        for cid, w in want.items():
            with self.subTest(id=cid):
                for k, v in w.items():
                    self.assertEqual(got[cid][k], v, k)

    def test_laws_outside_the_catalog_are_listed(self):
        want = sorted(lid for lid, ids in law_ids_mapped().items() if not ids)
        self.assertEqual(load_json(OUT_JSON)["laws_outside"], want)

    def test_counts_are_the_states(self):
        doc = load_json(OUT_JSON)
        cat = catalog()
        counts = {}
        for cid, x in doc["ids"].items():
            k = counts.setdefault(cat[cid]["kind"], {"full": 0, "partial": 0, "none": 0})
            k[x["state"]] += 1
        self.assertEqual(doc["counts"], counts)

    def test_tool_is_deterministic_and_committed(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-cs-"))
        try:
            outs = []
            for i in range(2):
                j, md = tmp / f"c{i}.json", tmp / f"c{i}.md"
                p = run_tool(ROOT, j, md)
                self.assertEqual(p.returncode, 0, p.stdout[-1000:] + p.stderr[-1000:])
                outs.append((j.read_bytes(), md.read_bytes()))
            self.assertEqual(outs[0], outs[1])
            self.assertEqual(outs[0][0], OUT_JSON.read_bytes(), "results/casestudy_coverage.json is stale")
            self.assertEqual(outs[0][1], OUT_MD.read_bytes(), "docs/CASESTUDY.md is stale")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
