"""I103 (M6): frontend reach. The contract of the key (spec/M6/predictions/I103.json, prompts/I103_frontend_reach.md).

The protocol of the measured run is spec/M6/lib/i103_run.json (I51's protocol with four toolchain and producer
changes). Its outcomes live under results/M6/i103/: corpus.json and <id>/ (python -m holon eval holon --protocol
spec/M6/lib/i103_run.json) and sorts_coverage.json (python -m holon sorts coverage).

Rules.
  F1  solc by pragma. holon.frontends.solidity.toolchains:
      - pragmas(text) is the list of `pragma solidity <expr>;` expressions of a source text, comments ignored, in order;
      - satisfies(version, expr) follows solc's version-pragma grammar: space-separated comparators are a conjunction,
        `||` a disjunction; ^ and ~ on 0.x.y (and on partial versions) bound the minor version; = < <= > >= compare;
        a bare version is =;
      - select_solc(exprs, releases) is the newest release (by numeric version) satisfying every expression, or None.
  F2  the pinned solc set. config/holon.json solc_set.releases maps every pinned release to its sha256: every final
      0.8.x from 0.8.0 to 0.8.38 and the last release of 0.5, 0.6 and 0.7 (0.5.17, 0.6.12, 0.7.6); 0.8.24's sha256 is
      replay.solc_sha256; replay.solc and replay.solc_sha256 are unchanged.
  F3  go by directive. holon.frontends.go.toolchains.select_go(directive, releases) is the lowest pinned release at or
      above the go directive (a directive "1.N" means 1.N.0), or None.
  F4  the pinned go set. config/holon.json go_set.releases holds 1.24.7 (replay.go_version's toolchain, unchanged) and
      1.25.14 with the sha256 of go1.25.14.linux-amd64.tar.gz.
  F5  go.work. holon.eval.gowork.generate(checkout, module_dir) (rule main_module) returns {"text", "uses", "go",
      "replaces", "conflicts"}: uses the closure of module_dir under relative replaces (paths "./rel", sorted); go the
      highest go directive of the used modules; for each module path two used modules replace with different targets,
      the main module's replace when it has one (in replaces, and as a replace line of text), else a conflict entry
      {"path", "targets"} and text None.
  F6  the total sort pass. holon.sorts.extracted.walk(model, doc, seeds, "holon-sort-types/0.3") walks a document with
      a term head that has no sorts rule to the end; walk.debt lists each unknown head once per (head, actor, where)
      with its count, sorted; the 0.2 pass refuses the same document; on a document without unknown terms 0.3's walk
      (events, grounds, subtraction sites) equals 0.2's and its debt is empty.

  F7  the corpus row. Under protocol holon-corpus-run/0.2 every document of a row has "toolchain": the text "solc
      <version> (...)" or "go <version> (...)" naming the toolchain the frontend selected and why, or null when no
      selection was reached; a refusal of the frontend's own reason names the toolchain too.

Contract tests read committed outcomes or call pure functions; none needs a network, a compiler or a clone.
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = "I103"
OUT = ROOT / "results" / "M6" / "i103"
NOT_RUN = ("c01", "c02", "c05", "c06", "c07", "c10", "c11", "c12", "c15", "c16", "c20")
TOOLCHAIN_REFUSALS = ("requires different compiler version", "go.mod requires go >=", "conflicting replacements for")
SOLC_SET = ["0.5.17", "0.6.12", "0.7.6"] + [f"0.8.{i}" for i in range(39)]
GO_1_25 = ("1.25.14", "a21ae5633a269bcd7e90cf767e48225633795e99d831742cbf3397064fee7712")
SKELETON = "5bae37d78fdd6511c400d569b094894dff9b66a8"   # the M6 skeleton commit, I103's base (Morph's record as landed)
MORPH_DIRS = ("results/M0", "results/M1", "results/M2", "results/M3", "laws/M0", "laws/M1", "laws/M2", "laws/M3")
C17_DOC = "results/eval/holon/c17/facts/onestepproverhostio.extracted.json"
MORPH_DOC = "spec/M2/facts/morph_rollup.extracted.json"
SEEDS = "spec/M3/lib/sort_seeds.json"


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def key():
    return load(f"spec/M6/predictions/{KEY}.json")


def expected(pid):
    return next(p["expected"] for p in key()["predictions"] + key()["regressions"] if p["id"] == pid)


def corpus_rows():
    return {r["id"]: r for r in load("results/M6/i103/corpus.json")["rows"]}


def coverage():
    return load("results/M6/i103/sorts_coverage.json")


def strip_stamp(x):
    if isinstance(x, dict):
        return {k: strip_stamp(v) for k, v in x.items() if k != "generator_sha256"}
    if isinstance(x, list):
        return [strip_stamp(v) for v in x]
    return x


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True).stdout


def first_guard(doc):
    for a in sorted(doc["actions"], key=lambda x: x["name"]):
        if a.get("guards"):
            return a
    raise AssertionError("the document has no guard")


def first_check(doc):
    """The first action (by name) with a check record: a check's expr is a term the sort pass walks (a guard's own
    expr is not: the pass walks a guard through its reaches)."""
    for a in sorted(doc["actions"], key=lambda x: x["name"]):
        if a.get("checks"):
            return a
    raise AssertionError("the document has no check")


# ---------------------------------------------------------------------------------------------- F1-F5: toolchains
class TestSolcSelection(unittest.TestCase):
    def test_f1_pragmas_ignore_comments(self):
        from holon.frontends.solidity import toolchains as T
        text = ("// SPDX-License-Identifier: MIT\n// pragma solidity 0.4.0;\n/* pragma solidity 0.5.0;\n*/\n"
                "pragma solidity >=0.6.2 <0.8.0;\npragma experimental ABIEncoderV2;\npragma solidity ^0.7.0;\n")
        self.assertEqual(T.pragmas(text), [">=0.6.2 <0.8.0", "^0.7.0"])

    def test_f1_satisfies(self):
        from holon.frontends.solidity import toolchains as T
        yes = [("0.5.17", "^0.5.16"), ("0.8.15", "0.8.15"), ("0.8.15", "=0.8.15"), ("0.8.38", "^0.8.0"),
               ("0.8.19", ">=0.8.0 <0.8.20"), ("0.7.6", ">=0.6.2 <0.8.0"), ("0.8.20", "~0.8.15"),
               ("0.7.6", "^0.8.0 || ^0.7.0"), ("0.8.3", ">0.8.2"), ("0.8.2", "<=0.8.2")]
        no = [("0.6.12", "^0.5.16"), ("0.8.24", "0.8.15"), ("0.8.20", ">=0.8.0 <0.8.20"), ("0.8.0", "^0.7.0"),
              ("0.8.2", ">0.8.2"), ("0.8.3", "<=0.8.2"), ("0.5.17", "^0.8.0 || ^0.7.0")]
        for v, e in yes:
            self.assertTrue(T.satisfies(v, e), (v, e))
        for v, e in no:
            self.assertFalse(T.satisfies(v, e), (v, e))

    def test_f1_select_newest_satisfying(self):
        from holon.frontends.solidity import toolchains as T
        self.assertEqual(T.select_solc(["^0.5.16"], SOLC_SET), "0.5.17")
        self.assertEqual(T.select_solc(["0.8.15"], SOLC_SET), "0.8.15")
        self.assertEqual(T.select_solc(["^0.8.0", "0.8.15"], SOLC_SET), "0.8.15")
        self.assertEqual(T.select_solc([">=0.8.0 <0.8.20"], SOLC_SET), "0.8.19")
        self.assertEqual(T.select_solc([">=0.6.2 <0.8.0"], SOLC_SET), "0.7.6")
        self.assertEqual(T.select_solc(["^0.8.0"], SOLC_SET), "0.8.38")
        self.assertEqual(T.select_solc([], SOLC_SET), "0.8.38")
        self.assertIsNone(T.select_solc(["^0.4.24"], SOLC_SET))
        self.assertIsNone(T.select_solc(["^0.8.0", "^0.7.0"], SOLC_SET))

    def test_f2_pinned_solc_set(self):
        cfg = load("config/holon.json")
        rel = cfg["solc_set"]["releases"]
        self.assertEqual(sorted(rel, key=lambda v: tuple(map(int, v.split(".")))), SOLC_SET)
        for v, sha in rel.items():
            self.assertRegex(sha, r"^[0-9a-f]{64}$", v)
        self.assertEqual(rel["0.8.24"], cfg["replay"]["solc_sha256"])
        self.assertEqual(cfg["replay"]["solc"], "/root/work/solc-0.8.24")
        self.assertEqual(cfg["replay"]["solc_sha256"], "fb03a29a517452b9f12bcf459ef37d0a543765bb3bbc911e70a87d6a37c30d5f")


class TestGoSelection(unittest.TestCase):
    def test_f3_lowest_at_or_above_the_directive(self):
        from holon.frontends.go import toolchains as T
        R = ["1.24.7", "1.25.14"]
        for d, want in (("1.21", "1.24.7"), ("1.24", "1.24.7"), ("1.24.7", "1.24.7"), ("1.24.8", "1.25.14"),
                        ("1.25", "1.25.14"), ("1.25.0", "1.25.14"), ("1.25.14", "1.25.14"), ("1.25.15", None),
                        ("1.26", None), ("1.26.0", None)):
            self.assertEqual(T.select_go(d, R), want, d)

    def test_f4_pinned_go_set(self):
        cfg = load("config/holon.json")
        rel = cfg["go_set"]["releases"]
        self.assertEqual(sorted(rel), ["1.24.7", "1.25.14"])
        self.assertEqual(rel[GO_1_25[0]]["sha256"], GO_1_25[1])
        self.assertEqual(cfg["replay"]["go_version"], "go version go1.24.7 linux/amd64")


class TestGoWork(unittest.TestCase):
    def tree(self, mods: dict) -> Path:
        d = Path(tempfile.mkdtemp(prefix="i103-gowork-"))
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(d)]))
        for rel, text in mods.items():
            (d / rel).mkdir(parents=True, exist_ok=True)
            (d / rel / "go.mod").write_text(text)
        return d

    def test_f5_main_module_replace_wins(self):
        from holon.eval import gowork
        ck = self.tree({
            "a": "module a\n\ngo 1.22\n\nreplace b => ../b\n\nreplace example.com/y => example.com/y1 v1.0.0\n",
            "b": "module b\n\ngo 1.25.0\n\nreplace example.com/y => example.com/y2 v1.0.0\n"})
        g = gowork.generate(ck, ck / "a")
        self.assertEqual(g["uses"], ["./a", "./b"])
        self.assertEqual(g["go"], "1.25.0")
        self.assertEqual(g["conflicts"], [])
        self.assertEqual([r["path"] for r in g["replaces"]], ["example.com/y"])
        self.assertIn("go 1.25.0\n", g["text"])
        self.assertRegex(g["text"], r"(?m)^\s*(replace\s+)?example\.com/y => example\.com/y1 v1\.0\.0\s*$")

    def test_f5_unsettled_conflict_is_a_reason(self):
        from holon.eval import gowork
        ck = self.tree({
            "a": "module a\n\ngo 1.22\n\nreplace (\n\tb => ../b\n\tc => ../c\n)\n",
            "b": "module b\n\ngo 1.22\n\nreplace example.com/y => example.com/y2 v1.0.0\n",
            "c": "module c\n\ngo 1.22\n\nreplace example.com/y => example.com/y3 v1.0.0\n"})
        g = gowork.generate(ck, ck / "a")
        self.assertEqual(g["uses"], ["./a", "./b", "./c"])
        self.assertIsNone(g["text"])
        self.assertEqual([c["path"] for c in g["conflicts"]], ["example.com/y"])

    def test_f5_equal_replaces_do_not_conflict(self):
        from holon.eval import gowork
        ck = self.tree({
            "a": "module a\n\ngo 1.22\n\nreplace b => ../b\n\nreplace example.com/y => example.com/y1 v1.0.0\n",
            "b": "module b\n\ngo 1.22\n\nreplace example.com/y => example.com/y1 v1.0.0\n"})
        g = gowork.generate(ck, ck / "a")
        self.assertEqual(g["conflicts"], [])
        self.assertEqual(g["replaces"], [])
        self.assertIsNotNone(g["text"])


# ---------------------------------------------------------------------------------------------- F6: total sort pass
class TestTotalSortPass(unittest.TestCase):
    def test_f6_unknown_head_is_debt_not_a_refusal(self):
        from holon.sorts import extracted as E
        doc = load(C17_DOC)
        seeds = load(SEEDS)
        bad = copy.deepcopy(doc)
        a = first_check(bad)
        a["checks"][0]["expr"] = ["i103_unknown_head", a["checks"][0]["expr"], ["i103_unknown_head", 7]]
        with self.assertRaises(E.ExtractedError):
            E.walk("c17", bad, seeds, E.SORT_TYPES_0_2)
        w = E.walk("c17", bad, seeds, "holon-sort-types/0.3")
        self.assertEqual(w.debt, [{"head": "i103_unknown_head", "actor": a["name"], "where": "checks[0]",
                                   "count": 2}])

    def test_f6_no_unknown_term_no_change(self):
        from holon.sorts import extracted as E
        seeds = load(SEEDS)
        for rel in (C17_DOC, MORPH_DOC):
            doc = load(rel)
            w2 = E.walk("m", copy.deepcopy(doc), seeds, E.SORT_TYPES_0_2)
            w3 = E.walk("m", copy.deepcopy(doc), seeds, "holon-sort-types/0.3")
            self.assertEqual(w3.prog.events, w2.prog.events, rel)
            self.assertEqual(w3.grounds, w2.grounds, rel)
            self.assertEqual(w3.subs, w2.subs, rel)
            self.assertEqual(w3.debt, [], rel)


# ---------------------------------------------------------------------------------------------- predictions
class TestPredictions(unittest.TestCase):
    def test_p1_no_toolchain_refusal_remains(self):
        rows = corpus_rows()
        hits = [(i, d.get("unit")) for i in NOT_RUN for d in rows[i]["documents"]
                if any(p in (d.get("reason") or "") for p in TOOLCHAIN_REFUSALS)]
        self.assertEqual({"toolchain_refusals": len(hits)}, expected("I103-P1"), hits)

    def test_p2_extraction_reach(self):
        rows = corpus_rows()
        got = sorted(i for i in NOT_RUN if any(d.get("status") == "extracted" for d in rows[i]["documents"]))
        self.assertEqual({"extracts": got}, expected("I103-P2"))

    def test_p3_every_failure_names_its_cause(self):
        rows = corpus_rows()
        bad = [(i, d.get("unit")) for i in NOT_RUN for d in rows[i]["documents"] if d.get("status") != "extracted"
               and (not (d.get("reason") or "").strip() or "Traceback (most recent call last)" in d["reason"])]
        self.assertEqual({"unnamed_failures": len(bad)}, expected("I103-P3"), bad)

    def test_p4_selected_toolchains(self):
        rows = corpus_rows()
        got = {}
        for i in NOT_RUN:
            texts = " ".join(str(d.get("toolchain") or "") + " " + (d.get("reason") or "") for d in rows[i]["documents"])
            m = re.search(r"\bsolc (\d+\.\d+\.\d+)\b", texts) or re.search(r"\bgo (\d+\.\d+\.\d+)\b", texts)
            got[i] = m.group(1) if m else None
        self.assertEqual(got, expected("I103-P4"))

    def test_p5_sort_pass_completes_everywhere(self):
        cov = coverage()
        refused = sorted(d["path"] for d in cov["documents"] if d["status"] != "complete")
        self.assertEqual({"refused": refused}, expected("I103-P5"))

    def test_p6_debt_on_known_documents(self):
        cov = {d["path"]: d for d in coverage()["documents"]}
        exp = expected("I103-P6")
        self.assertEqual({p: cov[p]["debt_heads"] for p in exp}, exp)


# ---------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    def test_r1_morph_record_moves_only_by_restamp(self):
        moved = []
        for d in MORPH_DIRS:
            base = {ln.split("\t", 1)[1]: ln.split()[2] for ln in git("ls-tree", "-r", SKELETON, "--", d)
                    .decode().splitlines()}
            head = {ln.split("\t", 1)[1]: ln.split()[2] for ln in git("ls-tree", "-r", "HEAD", "--", d)
                    .decode().splitlines()}
            for p in sorted(set(base) | set(head)):
                if base.get(p) == head.get(p):
                    continue
                if p not in base or p not in head or not p.endswith(".json"):
                    moved.append(p)
                    continue
                a = json.loads(git("cat-file", "blob", base[p]))
                b = json.loads(git("cat-file", "blob", head[p]))
                if strip_stamp(a) != strip_stamp(b):
                    moved.append(p)
        self.assertEqual(moved, [])

    def test_r2_hand_sidecars_name_their_toolchain(self):
        named = []
        for p in sorted((ROOT / "spec").rglob("*.json")):
            rel = p.relative_to(ROOT).as_posix()
            if rel.startswith(("spec/M6/", "spec/heldout")):
                continue
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if isinstance(d, dict) and d.get("frontend") == "solidity" and (d.get("compiler") or {}).get("version") == "pragma":
                named.append(rel)
            if isinstance(d, dict) and str(d.get("config_version", "")).startswith("holon-go-frontend/") and "toolchain" in d:
                named.append(rel)
        self.assertEqual(named, [])

    def test_r3_pre_08_documents_say_unchecked(self):
        for p in sorted(OUT.glob("*/facts/*.extracted.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            solc = ((d.get("extraction") or {}).get("toolchain") or {}).get("solc") or {}
            v = tuple(int(x) for x in re.match(r"(\d+)\.(\d+)\.(\d+)", solc.get("version", "0.8.0")).groups())
            if v < (0, 8, 0):
                self.assertEqual(solc.get("arithmetic"), "unchecked", p)
                for a in d.get("actions") or []:
                    for pn in a.get("panics") or []:
                        self.assertNotEqual(pn.get("code"), 17, (p, a["name"]))

    def test_r4_coverage_is_recomputed(self):
        from holon.sorts import extracted as E
        cov = coverage()
        seeds = load(cov["seeds"])
        self.assertTrue(cov["documents"])
        for d in cov["documents"]:
            doc = load(d["path"])
            try:
                w = E.walk("m", doc, seeds, "holon-sort-types/0.3")
                debt, status = w.debt, "complete" if not w.refusals else "refused"
            except E.ExtractedError:
                debt, status = None, "refused"
            self.assertEqual(status, d["status"], d["path"])
            if debt is not None:
                self.assertEqual(debt, d["debt"], d["path"])
                heads = {}
                for e in debt:
                    heads[e["head"]] = heads.get(e["head"], 0) + e["count"]
                self.assertEqual(heads, d["debt_heads"], d["path"])

    def test_r5_coverage_covers_every_transitions_document(self):
        cov = coverage()
        tracked = git("ls-files", "--", "gen", "spec", "results").decode().splitlines()
        want = []
        for rel in tracked:
            if not rel.endswith(".extracted.json") or rel.endswith(".go.extracted.json"):
                continue
            d = load(rel)
            if isinstance(d, dict) and isinstance(d.get("actions"), list) \
                    and (d.get("extraction") or {}).get("kind") == "transitions":
                want.append(rel)
        self.assertEqual([d["path"] for d in cov["documents"]], sorted(want))


if __name__ == "__main__":
    unittest.main()
