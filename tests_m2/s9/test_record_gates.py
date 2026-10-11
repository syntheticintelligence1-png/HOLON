"""S9(2): the record gates G6, G8, G9, G11-inhabitance (audit R2).

Each gate has a positive test on the real M1 data and negative tests on planted
defects. G11 is also tested with a canary law whose premises are contradictory:
a vacuously 'proved' law must fail the gate.
"""

import copy
import json
import shutil
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from holon import facts as F
from holon import gate_records, ir, records_v2
from holon.model_eval import CompiledModel
from holon.mpipeline import CompiledMachine
from holon.replay import load_report, witness_sha256

from tests_m2.s9._util import REPO, StubGate, m1_law, m1_record

M1 = "M1"
ROLLUP = "spec/M1/facts/morph_rollup.json"


class TestG6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = StubGate(REPO)
        cls.report = load_report(M1, REPO)
        cls.recs = cls.gate.records()

    def test_m1_passes(self):
        res = gate_records.g6_check(self.recs, self.report)
        self.assertTrue(res["passed"], res["detail"])

    def _refuted(self, lid="L_nat_eta2"):
        return {lid: copy.deepcopy(self.recs[lid])}

    def test_witness_hash_mismatch_fails(self):
        """Replay evidence for a DIFFERENT witness does not satisfy G6."""
        recs = self._refuted()
        report = copy.deepcopy(self.report)
        report["witness_sha256"]["L_nat_eta2"] = "0" * 64
        res = gate_records.g6_check(recs, report)
        self.assertFalse(res["passed"])
        self.assertIn("L_nat_eta2", res["detail"])

    def test_missing_report_entry_fails(self):
        recs = self._refuted()
        report = copy.deepcopy(self.report)
        del report["laws"]["L_nat_eta2"]
        res = gate_records.g6_check(recs, report)
        self.assertFalse(res["passed"])

    def test_model_only_label_passes(self):
        """A REFUTED record explicitly 'model-only pending replay' is accepted."""
        recs = self._refuted()
        recs["L_nat_eta2"]["replay"] = {"status": "not_run",
                                        "detail": "model-only pending replay: no harness step for this act"}
        res = gate_records.g6_check(recs, {"laws": {}, "witness_sha256": {}})
        self.assertTrue(res["passed"], res["detail"])

    def test_model_only_label_via_report(self):
        """The M3_sorts convention: report entry not_run + model-only observed."""
        recs = self._refuted()
        rec = recs["L_nat_eta2"]
        wh = witness_sha256(rec["witness"])
        report = {"laws": {"L_nat_eta2": {"status": "not_run",
                                        "observed": "model-only pending replay: no Foundry harness step"}},
                  "witness_sha256": {"L_nat_eta2": wh}, "morph_commit": "0" * 40}
        res = gate_records.g6_check(recs, report)
        self.assertTrue(res["passed"], res["detail"])

    def test_unlabelled_not_run_fails(self):
        recs = self._refuted()
        recs["L_nat_eta2"]["replay"] = {"status": "not_run", "detail": "no replay report entry"}
        res = gate_records.g6_check(recs, {"laws": {}, "witness_sha256": {}})
        self.assertFalse(res["passed"])


class TestG8(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = StubGate(REPO)
        cls.res = gate_records.g8_check(cls.gate)
        cls.report = json.loads((cls.gate.results / "coverage_report.json").read_text())

    def test_m1_passes(self):
        self.assertTrue(self.res["passed"], self.res["detail"])

    def test_report_lists_actions_and_registers(self):
        cov = self.report["facts"][ROLLUP]
        self.assertEqual(cov["kind"], "machine")
        self.assertIn("commitBatch", cov["actions"])
        self.assertIn("s_csr", cov["registers"])
        # every action and register carries the list of laws touching it
        for a, v in cov["actions"].items():
            self.assertIn("direct", v)
            self.assertIn("quantified", v)
            self.assertTrue(v["direct"] or v["quantified"], f"{a} untouched")
        for r, v in cov["registers"].items():
            self.assertIn("laws", v)
            if r != "log":
                self.assertTrue(v["laws"], f"register {r} untouched")

    def test_known_touches(self):
        cov = self.report["facts"][ROLLUP]
        self.assertIn("L_undo_CSR", cov["registers"]["s_csr"]["laws"])
        self.assertIn("proj", cov["registers"]["s_csr"]["how"]["L_undo_CSR"])
        self.assertIn("L_disch_stale_commit", cov["actions"]["commitBatchWithProof"]["direct"])
        self.assertIn("kappa", str(cov["registers"]["inch"]["how"]))

    def test_drift_fails(self):
        facts = F.load(REPO / ROLLUP)
        law = copy.deepcopy(m1_law("L_undo_CSR"))
        law["statement"]["assume"] = [{"eq": [{"act": "no_such_action", "args": {}},
                                            {"act": "commitBatch", "args": {}}]}]
        _, problems = gate_records._machine_coverage(facts, [law])
        self.assertTrue(any("unknown action" in p for p in problems))

    def test_coverage_hole_fails(self):
        # an untouched register is a hole unless debt explains it
        holes = gate_records._coverage_holes([f"{ROLLUP}: register s_csr"], {}, set())
        self.assertTrue(any("s_csr" in h for h in holes))
        self.assertEqual(gate_records._coverage_holes(
            [f"{ROLLUP}: register s_csr"], {ROLLUP: {"s_csr"}}, set()), [])
        # the log channel and codec functions are exempt
        self.assertEqual(gate_records._coverage_holes([f"{ROLLUP}: register log"], {}, set()), [])
        self.assertEqual(gate_records._coverage_holes(
            ["spec/M1/facts/h.json: function dec_go"], {}, set()), [])

    def test_stale_debt_symbol_semantics(self):
        # stale iff the element's symbol (leading token) is a modelled name
        mbf = {ROLLUP: {"commitBatch", "s_csr"}}
        stale = gate_records._stale_debt(mbf, {ROLLUP: ["commitBatch is modelled"]}, [])
        self.assertTrue(any("commitBatch" in s for s in stale))
        self.assertFalse(any("s_csr" in s for s in stale))
        # a modelled name later in the element (not the symbol) is NOT stale
        self.assertEqual(gate_records._stale_debt(mbf, {ROLLUP: ["revert of commitBatch"]},
                                                  []), [])
        # facts debt is scoped to its own file's namespace
        other = "spec/M1/facts/morph_batchdata.json"
        self.assertEqual(gate_records._stale_debt({other: {"view"}},
                                                  {ROLLUP: ["view fn"]}, []), [])

    def test_stale_debt_spec_items(self):
        """A spec/M2/coverage item is stale iff its element's symbol is a
        modelled name — checked against the union of all facts' namespaces."""
        mbf = {ROLLUP: {"commitBatch"}, "spec/M1/facts/morph_batchdata.json": {"append"}}
        # exact match on a modelled facts action: stale
        stale = gate_records._stale_debt(mbf, {}, [{"element": "append",
                                                  "source": "spec/M2/coverage/x.json"}])
        self.assertTrue(any("append" in s for s in stale))
        # a Go source-site element whose text contains a modelled name: NOT stale
        items = [{"element": "common/batch/batch_data.go:39 append BatchData.l1TxHashes",
                  "source": "spec/M2/coverage/go.json"}]
        self.assertEqual(gate_records._stale_debt(mbf, {}, items), [])
        # S3's real go.json does not trigger stale debt at all
        go = json.loads((REPO / "spec/M2/coverage/go.json").read_text())
        real_items = [{"element": i["element"], "source": "spec/M2/coverage/go.json"}
                      for i in go["items"]]
        self.assertEqual(gate_records._stale_debt(mbf, {}, real_items), [])
        # reason text is never consulted
        items = [{"element": "site/x", "source": "spec/M2/coverage/x.json",
                  "reason": "no append, no commitBatch"}]
        self.assertEqual(gate_records._stale_debt(mbf, {}, items), [])

    def test_malformed_debt_file_fails(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            cdir = tmp / "spec" / "M2" / "coverage"
            cdir.mkdir(parents=True)
            (cdir / "bad.json").write_text(json.dumps({"frontend": 3, "items": "nope"}))
            _, problems = gate_records._debt_files(tmp)
            self.assertTrue(problems)
        finally:
            shutil.rmtree(tmp)


class TestG9(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = StubGate(REPO)
        cls.res = gate_records.g9_check(cls.gate)

    def test_m1_passes(self):
        self.assertTrue(self.res["passed"], self.res["detail"])

    def _tmp_results(self, mutate=None):
        tmp = Path(tempfile.mkdtemp()) / "results_m1"
        shutil.copytree(REPO / "results" / M1, tmp, ignore=shutil.ignore_patterns("v2"))
        if mutate:
            mutate(tmp)
        return tmp

    def test_corrupt_statement_hash_fails(self):
        def mangle(tmp):
            p = tmp / "L_undo_CSR.json"
            rec = json.loads(p.read_text())
            rec["statement_hash"] = "sha256:" + "0" * 64
            p.write_text(json.dumps(rec, indent=2))
        tmp = self._tmp_results(mangle)
        try:
            res = gate_records.g9_check(StubGate(REPO, results=tmp))
            self.assertFalse(res["passed"])
            self.assertIn("statement_hash", res["detail"])
        finally:
            shutil.rmtree(tmp.parent)

    def test_missing_record_fails(self):
        tmp = self._tmp_results(lambda t: (t / "L_undo_BD.json").unlink())
        try:
            res = gate_records.g9_check(StubGate(REPO, results=tmp))
            self.assertFalse(res["passed"])
            self.assertIn("L_undo_BD", res["detail"])
        finally:
            shutil.rmtree(tmp.parent)

    def test_summary_mismatch_fails(self):
        def mangle(tmp):
            p = tmp / "summary.json"
            s = json.loads(p.read_text())
            s["L_undo_CSR"] = "UNKNOWN"
            p.write_text(json.dumps(s, indent=2))
        tmp = self._tmp_results(mangle)
        try:
            res = gate_records.g9_check(StubGate(REPO, results=tmp))
            self.assertFalse(res["passed"])
        finally:
            shutil.rmtree(tmp.parent)


class TestG11(unittest.TestCase):
    """Premise inhabitance (audit R2): vacuously proved laws must fail."""

    @classmethod
    def setUpClass(cls):
        import holon.bend as bend
        cls.cfg = bend.config(REPO)
        cls.cm = CompiledMachine.build(REPO / ROLLUP, cls.cfg)

    def test_inhabitant_found_for_proved_law(self):
        w, bound = gate_records.inhabit_machine(self.cm, m1_law("L_undo_CSR"))
        self.assertIsNotNone(w)
        self.assertTrue(all(w["premises"]))
        self.assertIn("point", w)

    def test_inhabitant_found_for_disch(self):
        """The kappa premise is inhabited: an in-challenge state with a live challenger."""
        w, _ = gate_records.inhabit_machine(self.cm, m1_law("L_disch_stale"))
        self.assertIsNotNone(w)
        self.assertTrue(all(w["premises"]))
        s = w["point"]["s"]["state"]
        self.assertTrue(s["inch"])  # the point is genuinely in a challenge

    def test_codec_inhabitant(self):
        model = CompiledModel.build(REPO / "spec/M1/facts/morph_header_m1.json", cfg=self.cfg)
        facts = F.load(REPO / "spec/M1/facts/morph_header_m1.json")
        law = m1_law("L_par_hdr_v2_composed")
        found, _ = gate_records.inhabit_par(model, facts, law)
        self.assertIsNotNone(found)
        h = found["point"]["h"]
        self.assertEqual(h["version"], "0x02")  # the pinned premise holds at the point

    def test_contradictory_premises_fail(self):
        """The canary: a law whose premises cannot all be true is NOT inhabited."""
        canary = copy.deepcopy(m1_law("L_disch_stale"))
        canary["law_id"] = "L_g11_canary_vacuous"
        canary["statement"]["assume"].append(
            {"eq": [{"obsv": "kappa", "of": {"var": "s"}}, {"bool": False}]})
        w, _ = gate_records.inhabit_machine(self.cm, canary)
        self.assertIsNone(w)

    def test_gate_fails_on_vacuous_law(self):
        """End to end: plant a contradictory-premise law with a PROVED record;
        G11 must report it as vacuous."""
        laws = ir.load_laws_any(M1, REPO)
        recs = {l["law_id"]: m1_record(l["law_id"]) for l in laws}
        canary = copy.deepcopy(m1_law("L_disch_stale"))
        canary["law_id"] = "L_g11_canary_vacuous"
        canary["statement"]["assume"].append(
            {"eq": [{"obsv": "kappa", "of": {"var": "s"}}, {"bool": False}]})
        # a non-vacuous certificate for the canary (its LAWS.bend states its law)
        cert = tempfile.NamedTemporaryFile("w", suffix=".bend", delete=False)
        cert.write("law l_g11_canary_vacuous: P\n")
        cert.close()
        recs["L_g11_canary_vacuous"] = {"law_id": "L_g11_canary_vacuous", "status": "PROVED",
                                        "artifacts": {"laws": cert.name}}
        stub = StubGate(REPO)
        stub.records = lambda: recs
        with mock.patch.object(gate_records.ir, "load_laws_any",
                               return_value=[*laws, canary]):
            res = gate_records.g11_inhabitance(stub)
        self.assertFalse(res["passed"])
        self.assertIn("L_g11_canary_vacuous", res["detail"])

    def test_refuted_witness_reverified(self):
        """The recorded REFUTED witness is itself an inhabitant of its premises."""
        law = m1_law("L_fact_Z")
        rec = m1_record("L_fact_Z")
        prems = gate_records._evaluate_premises(self.cm, law, rec["witness"])
        self.assertIsNotNone(prems)
        self.assertTrue(all(prems))


if __name__ == "__main__":
    unittest.main()
