"""I50b: a contaminated rerun of the held-out target, beside the sealed I49/I50 result (key I50b, spec/M4/predictions.json).

Written after the sealed results were recorded (I49 #144, I50 #145; the lead ruled that they stand) and before any
change to holon/ or any rerun. The rules are spec/M4/lib/heldout_rerun.json; the instrument is tests_m4/_i50b.py.

Contract (the build must make every test here pass; it may add tests, never change these):

K1  holon.sorts.extracted.walk(model, doc, seeds, sort_types_version=V): V "holon-sort-types/0.1" (the default) is the
    pinned pass, which refuses the term 'update' (ExtractedError, "term 'update' has no sorts rule"); V
    "holon-sort-types/0.2" adds rules U1-U3 and walks a document without an update term exactly as 0.1 does.
    holon.sorts.typed_sidecar accepts both versions, and holon sorts walks with the sidecar's version.
K2  holon.frontends.load_sidecar accepts sidecar_version 1 and 2; under 2, holon.frontends.solidity.coverage_document
    applies rule D1 (dead_code debt); under 1 coverage is unchanged. The transitions document of a version-2 sidecar is
    the version-1 document but for extraction.sidecar.
K3  targets/scroll_i50b/ holds target.json (rule T1b) and extract_solidity.json; `holon target extract|coverage|diagram|
    derive|run|gate --target scroll_i50b` run R1b-R5b; a step of `holon target run` that exits non-zero is recorded in
    results/targets/scroll_i50b/run_refusal.json ({step, command, exit, message}), and the run writes records/summary.json
    ({} when nothing was decided) and replay.json.
K4  `python -m holon target compare --target scroll_i50b [--check]` writes results/targets/scroll_i50b/comparison.json
    (rule C1: {comparison_version, label, sealed, rerun, rows}); --check exits 0 iff it is what a fresh run writes.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

from tests_m4._m4 import ROOT, copy_repo, holon_module, load_json, predictions
from tests_m4 import _i49 as H
from tests_m4 import _i50b as B
from tests_m4.test_i49_heldout import holon, I49_CHECKS

KEY = "I50b"
INSTRUMENTS = ["spec/M4/lib/heldout_rerun.json", "tests_m4/_i50b.py", "tests_m4/fixtures/i50b/src/Tally.sol",
               "tests_m4/fixtures/i50b/extract_v1.json", "tests_m4/fixtures/i50b/extract_v2.json"]
NAME = B.RERUN
LIB = ROOT / "gen" / "targets" / NAME / "lib"
LAWS = ROOT / "gen" / "targets" / NAME / "laws"
RES = ROOT / "results" / "targets" / NAME
LAW_CHECKS = ["L2", "L9", "L3", "L5", "L11", "L6"]
DEAD_SRC = "src/L1/rollup/ScrollChain.sol:748-750"
# the producer modules the lead's term (b) allows, and the plumbing that runs them (every one disclosed)
PRODUCERS = ["holon/frontends/__init__.py", "holon/frontends/solidity/transitions.py", "holon/sorts/assign.py",
             "holon/sorts/extracted.py", "holon/sorts/typed_sidecar.py"]
PLUMBING = ["holon/target_extracted.py", "holon/target_rerun.py", "holon/target_run.py", "holon/target_typed.py"]
OUTPUT_PREFIXES = ("results/M0/", "results/M1/", "results/M2/", "results/M3/", "gen/M0/", "gen/M1/", "gen/M2/",
                   "gen/M3/", "laws/M0/", "laws/M1/", "laws/M2/", "laws/M3/", "replay/M0/", "replay/M1/", "replay/M2/",
                   "replay/M3/", "spec/M1/facts/", "spec/M2/facts/", "facts/")


def key() -> dict:
    return predictions(KEY)


def pred(i: int) -> dict:
    return key()["predictions"][i - 1]


def prereg() -> str:
    return H.prereg_commit(KEY)


def seeds() -> dict:
    return load_json(ROOT / load_json(ROOT / "spec" / "M3" / "lib" / "sort_types.json")["seeds"])


def walk_events(doc: dict, version: str):
    X = holon_module("holon.sorts.extracted")
    w = X.walk("t", doc, seeds(), sort_types_version=version)
    return w, [e for e in w.prog.events]


class TestPrereg(unittest.TestCase):
    def test_key_shape(self):
        k = key()
        self.assertEqual(k["tests"], ["tests_m4/test_i50b_rerun.py"])
        self.assertEqual([p["id"] for p in k["predictions"]], [f"I50b-P{i}" for i in range(1, 6)])
        self.assertEqual(k["thresholds"]["contamination_label"], B.LABEL)
        self.assertEqual(B.protocol()["contamination"]["label"], B.LABEL)
        self.assertEqual(k["thresholds"]["rule_catalog_version"], "holon-rules/1.15")

    def test_instruments_pinned(self):
        pins = key()["thresholds"]["instrument_sha256"]
        self.assertEqual(sorted(pins), sorted(INSTRUMENTS))
        for rel in INSTRUMENTS:
            self.assertEqual(H.sha256(ROOT / rel), pins[rel], rel)


# ====================================================================== the rules, on documents that are not the target
class TestSortsRule(unittest.TestCase):
    """K1: rules U1-U3 (I50b-R3), on a synthetic document and on the development target's document."""

    def test_v01_still_refuses_update(self):
        X = holon_module("holon.sorts.extracted")
        with self.assertRaises(X.ExtractedError) as cm:
            X.walk("t", B.update_document(), seeds())
        self.assertIn("term 'update' has no sorts rule", str(cm.exception))
        with self.assertRaises(X.ExtractedError):
            X.walk("t", B.update_document(), seeds(), sort_types_version="holon-sort-types/0.1")

    def test_u3_whole_struct_write(self):
        w, ev = walk_events(B.update_document(), "holon-sort-types/0.2")
        flows = {(e[1], e[2]) for e in ev if e[0] == "flow"}
        self.assertIn(("act.p", "S.a"), flows)
        self.assertIn(("act.q", "S.b"), flows)
        self.assertEqual([f for f in flows if f[1] == "S.c"], [])
        for f in ("S.a", "S.b", "S.c"):
            self.assertIn("act", w.prog.writers.get(f, set()), f)

    def test_u2_member_reads(self):
        _w, ev = walk_events(B.update_document(), "holon-sort-types/0.2")
        flows = [(e[1], e[2]) for e in ev if e[0] == "flow"]
        cmps = [(e[2], e[3], e[5].where) for e in ev if e[0] == "compare"]
        self.assertIn(("act.p", "act.r", "guards[0]"), cmps)
        g1 = [c for c in cmps if c[2] == "guards[1]"]
        self.assertEqual(len(g1), 1)
        v = g1[0][0]
        self.assertTrue(v.startswith("$"), g1)
        self.assertEqual(g1[0][1], "act.q")
        self.assertEqual(sorted(a for a, b in flows if b == v), ["S.a", "act.p"])
        g2 = [c for c in cmps if c[2] == "guards[2]"]
        self.assertEqual(len(g2), 1)
        self.assertTrue(g2[0][0].startswith("$"), g2)
        self.assertEqual([a for a, b in flows if b == g2[0][0]], [])

    def test_v02_is_v01_without_update(self):
        """On the development target's extracted rollup document (no update term) 0.2 walks as 0.1, event for event."""
        X = holon_module("holon.sorts.extracted")
        doc = load_json(ROOT / "spec" / "M2" / "facts" / "morph_rollup.extracted.json")
        self.assertNotIn('"update"', json.dumps(doc))
        a = X.walk("m", doc, seeds())
        b = X.walk("m", doc, seeds(), sort_types_version="holon-sort-types/0.2")
        self.assertEqual(a.prog.events, b.prog.events)
        self.assertEqual(json.dumps(X.build("m", a), sort_keys=True), json.dumps(X.build("m", b), sort_keys=True))

    def test_typed_sidecar_versions(self):
        TS = holon_module("holon.sorts.typed_sidecar")
        self.assertEqual(sorted(TS.VERSIONS), ["holon-sort-types/0.1", "holon-sort-types/0.2"])


class TestDeadCodeRule(unittest.TestCase):
    """K2: rule D1 (I50b-R3), on the fixture contract and on the development target's rollup."""

    def cov(self, sidecar: Path, source: Path) -> dict:
        F = holon_module("holon.frontends")
        S = holon_module("holon.frontends.solidity")
        return S.coverage_document(F.load_sidecar(sidecar), sidecar, ROOT, source)

    def test_fixture_v1_unchanged(self):
        c = self.cov(B.FIXTURE / "extract_v1.json", B.FIXTURE)
        self.assertEqual(c["debt"], [])
        self.assertEqual([u["src"] for u in c["unaccounted"]],
                         ["src/Tally.sol:34", "src/Tally.sol:47-49", "src/Tally.sol:48"])

    def test_fixture_v2_dead_code(self):
        c1 = self.cov(B.FIXTURE / "extract_v1.json", B.FIXTURE)
        c2 = self.cov(B.FIXTURE / "extract_v2.json", B.FIXTURE)
        self.assertEqual((c2["statements"], c2["extracted"]), (c1["statements"], c1["extracted"]))
        self.assertEqual(c2["unaccounted"], [{"src": "src/Tally.sol:34", "node": "VariableDeclarationStatement"}])
        self.assertEqual([(d["src"], d["kind"]) for d in c2["debt"]], [("src/Tally.sol:47-49", "dead_code")])
        m = B.DEAD_DETAIL.match(c2["debt"][0]["detail"])
        self.assertIsNotNone(m, c2["debt"][0]["detail"])
        self.assertEqual(m.group(2), "0")
        # _settle is reached with both constants: neither of its branches is dead

    def test_fixture_documents(self):
        F = holon_module("holon.frontends")
        d1 = F.extract(B.FIXTURE / "extract_v1.json", ROOT, B.FIXTURE)
        d2 = F.extract(B.FIXTURE / "extract_v2.json", ROOT, B.FIXTURE)
        self.assertNotEqual(d1["extraction"]["sidecar"], d2["extraction"]["sidecar"])
        for d in (d1, d2):
            d["extraction"].pop("sidecar")
        self.assertEqual(d1, d2)

    def test_development_rollup_unchanged_under_v2(self):
        """The development target's rollup sidecar, as version 2, gives its version-1 coverage byte for byte."""
        import tempfile
        side = load_json(ROOT / "spec" / "M2" / "lib" / "extract_rollup.json")
        cfg = load_json(ROOT / "config" / "holon.json")
        src = Path(cfg["extract"]["sources"][side["target"]["repo"]])
        d = Path(tempfile.mkdtemp())
        try:
            p1, p2 = d / "v1.json", d / "v2.json"
            p1.write_text(json.dumps(side))
            p2.write_text(json.dumps(dict(side, sidecar_version=2)))
            self.assertEqual(self.cov(p1, src), self.cov(p2, src))
        finally:
            shutil.rmtree(d, ignore_errors=True)


# ====================================================================== the rerun target and its route
class TestRerunTarget(unittest.TestCase):
    """K3: rule T1b, the scope sidecar, Q1b-Q4b (construction, I50b-R5)."""

    def test_target_follows_t1b(self):
        sealed = load_json(ROOT / "targets" / B.SEALED / "target.json")
        got = load_json(ROOT / "targets" / NAME / "target.json")
        self.assertEqual(B.drop_docs(got), B.expected_target(sealed))
        self.assertEqual(sorted(p.name for p in (ROOT / "targets" / NAME).iterdir()),
                         ["extract_solidity.json", "target.json"])
        self.assertEqual(H.heldout_target()[0], B.SEALED)

    def test_scope_sidecar(self):
        sealed = load_json(ROOT / "targets" / B.SEALED / "extract_solidity.json")
        got = load_json(ROOT / "targets" / NAME / "extract_solidity.json")
        self.assertEqual(B.drop_docs(got), B.expected_scope(sealed))

    def test_document_is_the_sealed_one(self):
        a, b = load_json(ROOT / B.SEALED_DOC), load_json(ROOT / B.DOC)
        self.assertEqual(b["extraction"]["sidecar"],
                         {"path": f"targets/{NAME}/extract_solidity.json",
                          "sha256": H.sha256(ROOT / "targets" / NAME / "extract_solidity.json")})
        for d in (a, b):
            d["extraction"].pop("sidecar")
        self.assertEqual(a, b)

    def test_sidecars_follow_q1b_q4b(self):
        for n, want in B.expected_sidecars().items():
            with self.subTest(sidecar=n):
                got = load_json(LIB / f"{n}.json")
                self.assertEqual({k: v for k, v in got.items() if k != "doc"}, want)

    def test_extract_coverage_diagram_regenerate(self):
        for cmd in ("extract", "coverage", "diagram"):
            with self.subTest(cmd=cmd):
                p = holon(["target", cmd, "--target", NAME, "--check"])
                self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])

    def test_derive_regenerates(self):
        p = holon(["target", "derive", "--target", NAME, "--check"])
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])

    def test_run_outputs(self):
        summ = load_json(RES / "records" / "summary.json")
        rep = load_json(RES / "replay.json")
        refuted = sorted(k for k, v in summ.items() if v == "REFUTED")
        self.assertEqual(sorted(rep["laws"]), refuted)
        for e in rep["laws"].values():
            self.assertIn(e["status"], ("passed", "failed", "not_run"))
            self.assertTrue(e["reason"].strip())
        rr = RES / "run_refusal.json"
        if rr.is_file():
            r = load_json(rr)
            self.assertTrue({"step", "command", "exit", "message"} <= set(r), r)
            self.assertNotEqual(r["exit"], 0)

    def test_records_are_labelled(self):
        """I50b-R6 (d): the rerun's reports carry the contamination label."""
        for rel in ("comparison.json",):
            self.assertEqual(load_json(RES / rel)["label"], B.LABEL, rel)
        for rel in ("run_refusal.json", "derive_refusal.json"):
            if (RES / rel).is_file():
                self.assertEqual(load_json(RES / rel).get("label"), B.LABEL, rel)


class TestComparison(unittest.TestCase):
    """K4: rule C1 (I50b-R6)."""

    def test_rows_are_the_instruments(self):
        c = load_json(RES / "comparison.json")
        self.assertEqual(c["comparison_version"], "holon-rerun-comparison/0.1")
        self.assertEqual((c["sealed"], c["rerun"]), (B.SEALED, NAME))
        self.assertEqual(c["rows"], B.comparison_rows())
        self.assertTrue(all(r["contaminated"] is True for r in c["rows"]))

    def test_compare_regenerates(self):
        p = holon(["target", "compare", "--target", NAME, "--check"])
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])


# ====================================================================== predictions
class TestPredictions(unittest.TestCase):
    def test_p1_sorts_accept(self):
        """I50b-P1: the sort pass (0.2) accepts the rerun document: derive is not refused at holon sorts."""
        ref = RES / "derive_refusal.json"
        self.assertFalse(ref.is_file() and load_json(ref)["step"] == "holon sorts", ref)
        self.assertTrue((ROOT / "gen" / "targets" / NAME / "sorts" / "assignment.json").is_file())

    def test_p2_derivation(self):
        """I50b-P2: derive completes; its law count is in the predicted range and its rules hold the predicted set."""
        want = pred(2)["expected"]
        self.assertFalse((RES / "derive_refusal.json").is_file())
        d = load_json(LAWS / "DERIVATION.json")
        self.assertEqual(d["rule_catalog_version"], "holon-rules/1.15")
        self.assertEqual({x["facts"] for x in d["laws"]}, {B.DOC})
        n = len(d["laws"])
        self.assertGreaterEqual(n, want["laws_at_least"])
        self.assertLessEqual(n, want["laws_at_most"])
        self.assertTrue(set(want["rules_include"]) <= {x["rule"] for x in d["laws"]})

    def test_p3_model_refuses(self):
        """I50b-P3: the run stops at holon model, on an update the unchanged model generator has no rule for."""
        want = pred(3)["expected"]
        r = load_json(RES / "run_refusal.json")
        self.assertEqual(r["step"], want["step"])
        self.assertRegex(r["message"], want["message_matches"])
        self.assertEqual(load_json(RES / "records" / "summary.json"), {})

    def test_p4_g8(self):
        """I50b-P4: rule D1 accounts the two dead statements: 0 unaccounted, one dead_code entry, I49's debt kept."""
        want = pred(4)["expected"]
        cov = load_json(ROOT / "gen" / "targets" / NAME / "coverage.json")
        sealed = load_json(ROOT / "gen" / "targets" / B.SEALED / "coverage.json")
        self.assertEqual(cov["unaccounted"], want["unaccounted"])
        dead = [d for x in cov["documents"] for d in x["debt"] if d["kind"] == "dead_code"]
        self.assertEqual([d["src"] for d in dead], want["dead_code_src"])
        for d in dead:
            self.assertIsNotNone(B.DEAD_DETAIL.match(d["detail"]), d)
        rest = [d for x in cov["documents"] for d in x["debt"] if d["kind"] != "dead_code"]
        self.assertEqual(rest, [d for x in sealed["documents"] for d in x["debt"]])
        rep = load_json(RES / "gate_report.json")
        self.assertTrue(rep["checks"]["G8"]["passed"], rep["checks"]["G8"])

    def test_p5_gate(self):
        """I50b-P5: on the rerun target I49's six checks and L2 pass (on a copy of the repo)."""
        want = pred(5)["expected"]
        repo = copy_repo()
        try:
            p = holon(["target", "gate", "--target", NAME], cwd=repo)
            rep = load_json(repo / "results" / "targets" / NAME / "gate_report.json")
            self.assertEqual(list(rep["checks"]), I49_CHECKS + LAW_CHECKS, p.stdout[-2000:])
            for c in want["passed"]:
                self.assertTrue(rep["checks"][c]["passed"], (c, rep["checks"][c]))
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


# ====================================================================== regressions
class TestRegressions(unittest.TestCase):
    def test_r1_sealed_bytes(self):
        """I50b-R1: every sealed I49/I50 file is byte for byte what it was at the I50b prereg commit."""
        at = B.sealed_files(prereg())
        self.assertTrue(at)
        now = {}
        for rel in at:
            p = ROOT / rel
            now[rel] = subprocess.run(["git", "hash-object", str(p)], capture_output=True, text=True).stdout.strip() \
                if p.is_file() else None
        self.assertEqual(now, at)
        self.assertEqual(B.sealed_files("HEAD"), at)

    def test_r2_sealed_outcomes(self):
        """I50b-R2: the sealed I49/I50 suites fail exactly the tests they failed at the prereg (the key's list)."""
        p = subprocess.run([sys.executable, "-m", "unittest", "tests_m4.test_i49_heldout", "tests_m4.test_i50_heldout"],
                           cwd=ROOT, capture_output=True, text=True, timeout=3600)
        bad = sorted(set(re.findall(r"^(?:FAIL|ERROR): (\S+) \((\S+)\)", p.stderr, re.M)))
        got = sorted(f"{cls}" for _name, cls in bad)
        self.assertEqual(got, sorted(key()["thresholds"]["sealed_outcome"]["not_ok"]), p.stderr[-3000:])
        self.assertIn(f"Ran {key()['thresholds']['sealed_outcome']['ran']} tests", p.stderr)

    def test_r3_sealed_route_reproduces(self):
        """I50b-R2 (part): under the old versions the sealed route still refuses at holon sorts, byte for byte."""
        p = holon(["target", "derive", "--target", B.SEALED, "--check"])
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
        p = holon(["target", "coverage", "--target", B.SEALED, "--check"])
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])

    def test_r4_no_m0_m3_output_changes(self):
        """I50b-R4: no M0-M3 output, fact or law file changes in any I50b commit (re-stamps wait for landing)."""
        ch = [f for f in H.git("diff", "--name-only", prereg(), "HEAD").split() if f.startswith(OUTPUT_PREFIXES)]
        self.assertEqual(ch, [])

    def test_r5_target_agnostic(self):
        """I50b-R5: no holon/ file names a declared target, the rerun target's names included (I49's R3 re-run)."""
        from tests_m4.test_i49_heldout import TestRegressions as R49
        R49.test_r3_target_agnostic(R49())

    def test_r6_changes_scoped_and_disclosed(self):
        """I50b-R6: holon/rules/ is the pin's; the holon/ files I50b changes are only the allowed producers and the
        plumbing, and each is disclosed in spec/M4/lib/heldout_disclosures.jsonl by a line naming I50b."""
        ch = H.pin_changes()
        self.assertEqual([f for f in ch["modified"] + ch["deleted"] + ch["added"] if f.startswith("holon/rules/")], [])
        mine = sorted(f for f in H.git("diff", "--name-only", prereg(), "HEAD", "--", "holon/").split())
        self.assertTrue(set(mine) <= set(PRODUCERS + PLUMBING), sorted(set(mine) - set(PRODUCERS + PLUMBING)))
        lines = [x for x in H.disclosures() if x["why"].startswith("I50b")]
        for f in mine:
            with self.subTest(path=f):
                self.assertIn(f, {x["path"] for x in lines})
        for x in lines:
            self.assertEqual(x["phase"], "post_seal")


if __name__ == "__main__":
    unittest.main()
