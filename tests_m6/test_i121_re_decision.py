"""I121 (M6, generality): the re-decision (HUMAN_ANSWERS Q93 (1)(b), Q96, Q97 (2), Q98 (3)).

The contract (spec/M6/predictions/I121.json):

  (b) of I119 lands whole: the opaque-arithmetic rule is the Go frontend's default for every Go document
      (holon.frontends.go.ctx.Ctx.opaque_arith_of), the narrow-arithmetic loop mode unchanged, Morph's three changed Go
      documents re-extracted.
  The re-decision channel, by case (Q96 (1)): (a) law file unchanged, decision inputs changed: re-made and re-decided,
      the binding through model_extension, binding_change or from scratch where its cone changes; (b) law file
      different only in facts_sha256: holon.statement_diff's reextraction gains a facts form, a line
      {"kind": "reextraction", "form": "facts", law_id, milestone, old, new, facts, derivation, record} accepted
      unsigned only under thresholds.facts_form's five conditions (check_entry(entry, root)); (c) the renumbered PAR
      law: the old id retired, the new id decided fresh.
  The re-decision runs in the builder's sandbox, vault first (Q96 (2)); results/M6/I121/redecide.json holds its
      aggregates only: per milestone (M0-M3) the records re-made, compared and re-decided, the verdicts changed
      (PROVED and REFUTED together, Q89), new and retired laws; per channel the counts; whether the milestone's
      affected records are withheld (Q56) and one sha256 bundle commitment of the vault's re-decided set.
  F-M6-02 fixed if small (audit/M6_findings.jsonl). One counted corpus run (spec/M6/lib/i121_run.json), aggregates
      only, smoke on contaminated data.

No law id appears in any file this key writes under results/M6/I121/ (Q56, Q89).
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests_m6" / "fixtures" / "i121"
OUT = ROOT / "results" / "M6" / "I121"
REDECIDE = OUT / "redecide.json"
PROTO = ROOT / "spec" / "M6" / "lib" / "i121_run.json"
LOG = ROOT / "laws" / "STATEMENT_DIFF.jsonl"
LAW_ID = re.compile(r"\bL_[A-Za-z0-9_]+")
MORPH_GO = ("spec/M2/facts/morph_batch.go.extracted.json", "spec/M3/facts/morph_blob.go.extracted.json",
            "spec/M3/facts/morph_go03.go.extracted.json")
REAPPLIED = "ff9e463e"   # I119 (b)'s re-extraction commit, reverted by 5587ebef and re-applied here
MILESTONES = ("M0", "M1", "M2", "M3")
CHANNELS = ("facts_form_accepted", "facts_form_refused", "model_extension", "binding_change", "from_scratch",
            "cone_unchanged", "retired", "new")


def pred(pid: str) -> dict:
    d = json.loads((ROOT / "spec" / "M6" / "predictions" / "I121.json").read_text(encoding="utf-8"))
    (p,) = [x for x in d["predictions"] if x["id"] == pid]
    return p


def redecide() -> dict:
    return json.loads(REDECIDE.read_text(encoding="utf-8"))


def git_blob(rev: str, rel: str) -> bytes:
    p = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=ROOT, capture_output=True)
    assert p.returncode == 0, p.stderr[-500:]
    return p.stdout


def facts_lines() -> list[dict]:
    out = []
    for x in LOG.read_text(encoding="utf-8").splitlines():
        if x.strip():
            e = json.loads(x)
            if e.get("kind") == "reextraction" and e.get("form") == "facts":
                out.append(e)
    return out


def protocol(rel: str | Path = PROTO) -> dict:
    p = rel if isinstance(rel, Path) else ROOT / rel
    return json.loads(p.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------------------------- P1: the flip
class TestFlip(unittest.TestCase):
    """P1: (b) re-applied whole."""

    def test_p1_default_under_every_config(self):
        from holon.frontends.go.ctx import Ctx
        for cfg in ({}, {"config_version": "holon-go-frontend/0.1"}, {"config_version": "holon-go-frontend/0.2"},
                    {"config_version": "holon-go-frontend/0.3"}, {"config_version": "holon-go-frontend/0.3",
                                                                  "ops": "typed"}):
            with self.subTest(cfg=cfg):
                self.assertIs(Ctx.opaque_arith_of(cfg), True)

    def test_p1_path_reasoner_reads_the_default(self):
        src = (ROOT / "holon" / "frontends" / "go" / "paths.py").read_text(encoding="utf-8")
        self.assertIn("Reasoner(st.cond, self.nonnil, self.ctx.opaque_arith)", src)
        self.assertNotIn("Reasoner(st.cond, self.nonnil, self.ctx.typed_ops)", src)

    def test_p1_morph_documents_are_the_reextracted_ones(self):
        for rel in MORPH_GO:
            with self.subTest(doc=rel):
                self.assertEqual(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(),
                                 hashlib.sha256(git_blob(REAPPLIED, rel)).hexdigest())

    def test_p1_i119_fixture_and_default_pass(self):
        p = subprocess.run([sys.executable, "-m", "unittest", "-v",
                            "tests_m6.test_i119_go_reasoner_soundness.TestFixture",
                            "tests_m6.test_i119_go_reasoner_soundness.TestDefault"],
                           cwd=ROOT, capture_output=True, text=True, timeout=3600)
        self.assertEqual(p.returncode, 0, p.stderr[-3000:])


# ----------------------------------------------------------------------------------------------- P2: facts form
class TestFactsForm(unittest.TestCase):
    """P2: reextraction's facts form, on the committed lines and planted variants of them."""

    @classmethod
    def setUpClass(cls):
        from holon import statement_diff as SD
        cls.SD = SD
        cls.lines = facts_lines()
        cls.tmp = Path(tempfile.mkdtemp(prefix="i121-ff-"))

    def first(self) -> dict:
        self.assertTrue(self.lines, "no facts-form reextraction line in laws/STATEMENT_DIFF.jsonl")
        return copy.deepcopy(self.lines[0])

    def refused(self, e: dict, why: str | None = None) -> None:
        r = self.SD.check_entry(e, ROOT)
        self.assertFalse(r["ok"], r)
        if why:
            self.assertIn(why, r["reason"])

    def test_p2_committed_lines_accepted_unsigned(self):
        self.assertTrue(self.lines)
        for e in self.lines:
            with self.subTest(n=self.lines.index(e)):
                self.assertFalse(e.get("signature"))
                o, n = dict(e["old"]), dict(e["new"])
                self.assertNotEqual(o.pop("facts_sha256"), n.pop("facts_sha256"))
                self.assertEqual(o, n)
                r = self.SD.check_entry(e, ROOT)
                self.assertTrue(r["ok"], r)

    def test_p2_lines_match_the_redecision_count(self):
        self.assertEqual(len(self.lines), redecide()["channels"]["M3"]["facts_form_accepted"])

    def test_p2_other_key_changed_refused(self):
        e = self.first()
        e["new"]["notes"] = str(e["new"].get("notes")) + " (changed)"
        self.refused(e)
        e = self.first()
        e["new"]["subform"] = "other"
        self.refused(e)

    def test_p2_hand_written_facts_refused(self):
        for rel in ("tests_m6/fixtures/i121/hand_facts.json", "tests_m6/fixtures/i121/hand_goops.json"):
            with self.subTest(facts=rel):
                e = self.first()
                e["new"]["facts"] = e["old"]["facts"] = e["facts"] = rel
                e["new"]["facts_sha256"] = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
                self.refused(e, "hand-written")

    def test_p2_valid_two_link_chain_recorded(self):
        """Q102: a generated facts document's line records its chain (each link's path, sha256, producer, version),
        generated document first, ending at extractor output; the check recomputes it."""
        for e in self.lines:
            ch = e["chain"]
            with self.subTest(n=self.lines.index(e)):
                self.assertEqual(ch[0]["path"], e["facts"])
                self.assertEqual(len({x["path"] for x in ch}), len(ch))
                for x in ch:
                    self.assertEqual(sorted(x), ["path", "producer", "sha256", "version"])
                    self.assertEqual(x["sha256"], hashlib.sha256((ROOT / x["path"]).read_bytes()).hexdigest())
                if e["facts"].startswith("gen/"):
                    self.assertEqual(len(ch), 2)
                    self.assertTrue(ch[1]["path"].endswith(".extracted.json"), ch[1]["path"])

    def test_p2_chain_sha256_mismatch_refused(self):
        e = self.first()
        e["chain"][-1]["sha256"] = "0" * 64
        self.refused(e)
        e = self.first()   # a generated document naming its source at another sha256
        doc = json.loads((ROOT / e["facts"]).read_text(encoding="utf-8"))
        if "document_sha256" in doc:
            doc["document_sha256"] = "0" * 64
            p = self.tmp / "sha_mismatch_ops.json"
            p.write_bytes(json.dumps(doc, indent=1, sort_keys=True).encode("utf-8"))
            e["facts"] = e["new"]["facts"] = e["old"]["facts"] = str(p)
            e["new"]["facts_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
            e["chain"][0] = dict(e["chain"][0], path=str(p), sha256=e["new"]["facts_sha256"])
            self.refused(e)

    def test_p2_generated_document_not_reproduced_refused(self):
        e = self.first()
        doc = json.loads((ROOT / e["facts"]).read_text(encoding="utf-8"))
        doc["component"] = str(doc.get("component")) + "_edited"
        p = self.tmp / "edited_ops.json"
        p.write_bytes(json.dumps(doc, indent=1, sort_keys=True).encode("utf-8"))
        e["facts"] = e["new"]["facts"] = e["old"]["facts"] = str(p)
        e["new"]["facts_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
        e["chain"][0] = dict(e["chain"][0], path=str(p), sha256=e["new"]["facts_sha256"])
        self.refused(e)

    def test_p2_producer_outside_a_generator_closure_refused(self):
        e = self.first()
        e["chain"][0]["producer"] = "tools/i121_hand_ops.py"
        self.refused(e)

    def test_p2_facts_sha256_not_the_documents_refused(self):
        e = self.first()
        e["new"]["facts_sha256"] = "0" * 64
        self.refused(e)

    def test_p2_other_derivation_refused(self):
        e = self.first()
        e["derivation"]["subform"] = "other"
        self.refused(e)

    def test_p2_carried_record_refused(self):
        """A record that is not re-decided on the new inputs (its facts sha256 the old one: the old verdict carried
        over) is refused, whatever its status."""
        e = self.first()
        rec = json.loads((ROOT / e["record"]).read_text(encoding="utf-8"))
        for status in ("PROVED", "REFUTED", "UNKNOWN"):
            with self.subTest(status=status):
                r = dict(rec, status=status)
                if "facts_sha256" in r:
                    r["facts_sha256"] = e["old"]["facts_sha256"]
                else:
                    r["statement_hash"] = "sha256:" + "0" * 64
                p = self.tmp / f"carried_{status}.json"
                p.write_text(json.dumps(r, sort_keys=True))
                bad = dict(e, record=str(p))
                self.refused(bad)

    def test_p2_verdict_flip_redecided_not_carried(self):
        """The planted flip: the re-decision instrument's own planted case, a law whose committed status differs from
        the checker's on the new inputs, ends with the checker's status (redecide.json planted.flip)."""
        f = redecide()["planted"]["flip"]
        self.assertEqual(f["committed_after"], f["checker"])
        self.assertNotEqual(f["committed_before"], f["checker"])


# ----------------------------------------------------------------------------------------------- P3-P5: re-decision
class TestRedecision(unittest.TestCase):
    """P3-P5: the re-decision's aggregates, vault first."""

    def test_names_no_law(self):
        for p in sorted(OUT.rglob("*.json")):
            with self.subTest(p=p.relative_to(ROOT).as_posix()):
                self.assertIsNone(LAW_ID.search(p.read_text(encoding="utf-8")))

    def test_shape(self):
        d = redecide()
        self.assertEqual(sorted(d["milestones"]), list(MILESTONES))
        for m in MILESTONES:
            row = d["milestones"][m]
            for k in ("remade", "compared", "redecided", "verdicts_changed", "new_laws", "retired_laws", "withheld"):
                self.assertIn(k, row, (m, k))
            self.assertNotIn("PROVED", json.dumps(row))
            self.assertNotIn("REFUTED", json.dumps(row))
        self.assertRegex(d["bundle_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(sorted(d["channels"]["M3"]), sorted(CHANNELS))

    def test_p3_m0_m2_nothing_remade(self):
        d = redecide()
        for m in ("M0", "M1", "M2"):
            with self.subTest(m=m):
                self.assertEqual(d["milestones"][m]["remade"], 0)
                self.assertEqual(d["milestones"][m]["verdicts_changed"], 0)

    def test_p4_m3_counts_consistent(self):
        row = redecide()["milestones"]["M3"]
        self.assertEqual(row["compared"], 162)
        self.assertEqual(row["redecided"], row["compared"] + row["new_laws"])
        self.assertEqual((row["new_laws"], row["retired_laws"]), (1, 1))
        self.assertLessEqual(row["verdicts_changed"], row["compared"])

    def test_p4_withheld_iff_a_verdict_changed(self):
        """Q96 (2): any change, in any direction, withholds every affected record of the milestone alike."""
        for m, row in redecide()["milestones"].items():
            with self.subTest(m=m):
                self.assertEqual(row["withheld"], row["verdicts_changed"] > 0)
        row = redecide()["milestones"]["M3"]
        held = 0
        for p in sorted((ROOT / "results" / "M3").glob("*.json")):
            try:
                r = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            reason = json.dumps(r.get("reason", "")) if isinstance(r, dict) else ""
            if "I121" in reason and "Q56" in reason:
                self.assertEqual(r.get("status"), "UNKNOWN", p.name)
                held += 1
        self.assertEqual(held, row["redecided"] if row["withheld"] else 0)

    def test_p5_channels_cover_case_a(self):
        c = redecide()["channels"]["M3"]
        case_a = c["model_extension"] + c["binding_change"] + c["from_scratch"] + c["cone_unchanged"]
        self.assertEqual(case_a + c["facts_form_accepted"] + c["facts_form_refused"] + c["retired"], 162)
        self.assertEqual((c["retired"], c["new"]), (1, 1))

    def test_p5_log_lines_for_the_cone_channels(self):
        c = redecide()["channels"]["M3"]
        kinds = {"model_extension": 0, "binding_change": 0}
        start = redecide()["log_lines_before"]
        for x in LOG.read_text(encoding="utf-8").splitlines()[start:]:
            if x.strip():
                k = json.loads(x).get("kind")
                if k in kinds:
                    kinds[k] += 1
        self.assertEqual(kinds, {k: c[k] for k in kinds})


# ----------------------------------------------------------------------------------------------- P6: F-M6-02
class TestF0602(unittest.TestCase):
    def test_p6_ledger_entry_closed(self):
        rows = [json.loads(x) for x in (ROOT / "audit" / "M6_findings.jsonl").read_text(encoding="utf-8").splitlines()
                if x.strip()]
        (f,) = [r for r in rows if r.get("id") == "F-M6-02"]
        self.assertEqual(f.get("status"), "fixed", f.get("status"))
        self.assertEqual(f.get("fix_iteration"), "I121")

    def test_p6_m3_g1_evidence(self):
        g = redecide()["g1"]["M3"]
        self.assertEqual(g["exit"], 0)
        self.assertNotIn("FileExistsError", json.dumps(g))


# ----------------------------------------------------------------------------------------------- P7: corpus run
class TestCorpusRun(unittest.TestCase):
    def test_p7_protocol_is_its_base(self):
        b = protocol()
        a = protocol(b["base_protocol"])
        b.pop("base_protocol")
        a.pop("base_protocol", None)
        for d in (a, b):
            for k in ("doc", "iteration", "out"):
                d.pop(k)
            d["go_machines"].pop("out")
        self.assertEqual(a, b)
        self.assertEqual(protocol()["iteration"], "I121")

    def test_p7_no_new_opt_in(self):
        b = protocol()
        self.assertNotIn("opaque_arith", json.dumps(b["go"]))

    def test_p7_corpus_row_aggregates_only(self):
        p = OUT / "holon" / "corpus.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(d["protocol_sha256"], hashlib.sha256(PROTO.read_bytes()).hexdigest())
        self.assertIsNone(LAW_ID.search(p.read_text(encoding="utf-8")))


# ----------------------------------------------------------------------------------------------- P8: regressions
class TestRegressions(unittest.TestCase):
    def test_p8_ci_job_lists_classes(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        self.assertIn("name: tests-m6-i121", wf)
        for c in ("TestFlip", "TestFactsForm", "TestRedecision", "TestRegressions"):
            self.assertIn(f"tests_m6.test_i121_re_decision.{c}", wf)

    def test_p8_earlier_jobs_listed(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        for job in ("tests-m6-i103", "tests-m6-i104", "tests-m6-i105", "tests-m6-i107", "tests-m6-i108",
                    "tests-m6-i109", "tests-m6-i110", "tests-m6-i111", "tests-m6-i112", "tests-m6-i113",
                    "tests-m6-i115", "tests-m6-i116", "tests-m6-i117", "tests-m6-i119"):
            self.assertIn(f"name: {job}", wf)

    def test_p8_i119_p3_stays_its_prereg_source(self):
        rel = "tests_m6/test_i119_go_reasoner_soundness.py"
        pat = re.compile(r"    def test_p3_morph_baseline_reproduces\(self\):\n(?:        .*\n|\n)*?(?=    def |\Z)")
        now = pat.search((ROOT / rel).read_text(encoding="utf-8"))
        then = pat.search(git_blob("1c3770b8", rel).decode("utf-8"))
        self.assertIsNotNone(now)
        self.assertEqual(now.group(0), then.group(0))

    def test_p8_i117_amendment_first(self):
        rows = [json.loads(x) for x in (ROOT / "spec" / "M6" / "amendments" / "I117.jsonl").read_text(
            encoding="utf-8").splitlines() if x.strip()]
        self.assertTrue(any("I119" in json.dumps(r) for r in rows))

    def test_p8_no_bend_escape_hatch(self):
        for p in sorted((ROOT / "gen" / "M3").rglob("*.bend")):
            t = p.read_text(encoding="utf-8")
            with self.subTest(p=p.relative_to(ROOT).as_posix()):
                self.assertNotIn("?TODO", t)
                self.assertNotIn("@unsafe", t)
                self.assertNotRegex(t, r'import\s+"\./[^"]+\.c"')

    def test_p8_reads_no_sealed_input(self):
        for p in sorted((ROOT / "tools").glob("i121_*.py")):
            t = p.read_text(encoding="utf-8")
            with self.subTest(p=p.name):
                for bad in ("spec/heldout", "scroll-tech", "I113_candidates", "target.json"):
                    self.assertNotIn(bad, t)

if __name__ == "__main__":
    unittest.main()
