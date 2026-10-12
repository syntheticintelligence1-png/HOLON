"""Audit M2/1 F-M2-11 and F-M2-12: the parametric Morph model of M2, and M2+ records that keep their ledger cone.

F-M2-11. M2's Morph models are compiled from the M1 fact documents (which may not be edited: their hash is in every
M1 statement). M2 finds its oracle sidecar at the milestone level: spec/M2/lib/oracles.json names the facts it
applies to (`facts`), and holon.gen.oracles.Oracles.for_milestone gives it to every M2 model of them (M0 and M1 never
read one). The Morph rollup model of M2 threads the blob-hash aggregate `agg` through step and run as an oracle
table; the M1 stand-in survives only as the instance. An entry is modelled exactly when the model takes its
parameter: the verifier's proof == 1 rule and the header presentation are stated inline by the M1 facts, so they
are not_in_scope, with that reason. `holon model --milestone M2 --facts F` builds and checks the model.

F-M2-12. An M2+ record's model_assumptions is exactly its hypothesis premises (§8.5, preregistered in I12); its
ledger cone stays in ledger_assumptions: the ledger entries meeting the cone minus the stand-ins the model replaces
by parameters. G9 recomputes it for M2+ records, so a record whose cone meets stand-ins never lists an empty set.
"""
import copy
import hashlib
import json
import shutil
import subprocess
import unittest

from tests_m2._m2 import ROOT, copy_repo, holon_module, load_json, run_holon, write_json

ROLLUP = ROOT / "spec" / "M1" / "facts" / "morph_rollup.json"
BATCHDATA = ROOT / "spec" / "M1" / "facts" / "morph_batchdata.json"
M2_SIDECAR = ROOT / "spec" / "M2" / "lib" / "oracles.json"


def _cfg():
    return holon_module("holon.bend").config(ROOT)


def _calls(module, calls: list) -> list:
    P = holon_module("holon.mpipeline")
    p = subprocess.run(["node", str(P.MACHINE_JS)], input=json.dumps({"module": str(module), "calls": calls}),
                       capture_output=True, text=True, timeout=600)
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads(p.stdout)["results"]


class TestMilestoneSidecar(unittest.TestCase):
    def setUp(self):
        self.O = holon_module("holon.gen.oracles")

    def test_m2_finds_its_sidecar_for_the_facts_it_names(self):
        orc = self.O.Oracles.for_milestone("M2", ROLLUP, ROOT)
        self.assertIsNotNone(orc)
        self.assertEqual(orc.path.resolve(), M2_SIDECAR.resolve())
        self.assertEqual(sorted(orc.params), ["agg"])
        self.assertIsNone(self.O.Oracles.for_milestone("M2", BATCHDATA, ROOT))   # not named by `facts`
        for m in ("M0", "M1"):
            self.assertIsNone(self.O.Oracles.for_milestone(m, ROLLUP, ROOT))
        fx = ROOT / "tests_m2" / "fixtures" / "oracles" / "facts" / "toy_oracle.facts.json"
        self.assertEqual(self.O.Oracles.for_milestone("T12", fx, ROOT).path, self.O.sidecar_path(fx))

    def test_sidecar_is_valid_with_its_facts_list(self):
        oc = holon_module("holon.oracle_check")
        self.assertEqual(oc.validate(load_json(M2_SIDECAR), ROOT), [])
        bad = copy.deepcopy(load_json(M2_SIDECAR))
        bad["facts"] = ["spec/M1/facts/no_such.json"]
        self.assertTrue(oc.validate(bad, ROOT))

    def test_modelled_iff_the_model_takes_the_parameter(self):
        """Every entry: modelled exactly when an M2 model of a fact document it names calls its parameter."""
        Mach, F = holon_module("holon.gen.machine"), holon_module("holon.facts")
        doc = load_json(M2_SIDECAR)
        used = set()
        for rel in doc["facts"]:
            fp = ROOT / rel
            used |= self.O.params_used(Mach.Machine(F.load(fp), fp, oracles=self.O.Oracles.for_milestone("M2", fp, ROOT),
                                                    m2plus=True))
        for e in doc["oracles"]:
            with self.subTest(entry=e["id"]):
                self.assertEqual(e["status"] == "modelled", e["parameter"]["name"] in used)
                if e["status"] == "not_in_scope":
                    self.assertTrue(e["reason"].strip())
        by = {e["id"]: e for e in doc["oracles"]}
        self.assertIn("inline", by["verifier"]["reason"])
        self.assertIn("hdr_hash", by["header_presentation"]["reason"])


class TestParametricMorphModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        P = holon_module("holon.mpipeline")
        cls.cm = P.milestone_model("M2", ROLLUP, _cfg())
        cls.text = cls.cm.source.read_text()
        cls.m1 = P.milestone_model("M1", ROLLUP, _cfg())

    def test_model_checks_under_both_kernels(self):
        bend = holon_module("holon.bend")
        self.assertTrue(bend.check(self.cm.source, _cfg()).ok)
        self.assertTrue(bend.check_verdict(self.cm.source, _cfg()).ok)

    def test_agg_is_threaded_and_the_stand_in_is_gone(self):
        self.assertEqual(self.cm.m.threaded, ["agg"])
        self.assertIn("def ap_agg(t: List<&2, HO_agg>, +x: List<&2, Nat>) -> Nat:", self.text)
        self.assertIn("def step(a: HAct, s: HSt, +agg: List<&2, HO_agg>) -> HSt:", self.text)
        self.assertIn("ap_agg(agg, blobs)", self.text)
        self.assertNotIn("Nat.add(1000n, b_enc(", self.text)            # the M1 stand-in, compiled in
        self.assertIn("Nat.add(1000n, b_enc(", self.m1.source.read_text())
        self.assertEqual(self.m1.source.read_text(), (ROOT / "gen" / "M1" / "model" / "morph_rollup.bend").read_text())

    def test_blob_hash_is_parametric_in_agg_with_the_stand_in_as_instance(self):
        tab = lambda v: [{"$": "HO_agg", "k": [5], "v": v}]   # noqa: E731
        got = self.cm.calls([{"fn": "d_blob_hash", "args": [{"val": 2}, {"val": [5]}, {"val": tab(7)}]},
                             {"fn": "d_blob_hash", "args": [{"val": 2}, {"val": [5]}, {"val": tab(9)}]},
                             {"fn": "d_blob_hash", "args": [{"val": 2}, {"val": [5]}, {"val": []}]}])
        self.assertEqual(got, [7, 9, 0])
        art, insts, notes = self.cm.instance_module()
        self.assertEqual([i["id"] for i in insts], ["agg"], notes)
        (inst,) = _calls(art, [{"fn": insts[0]["fn"], "args": [{"val": [5]}]}])
        (standin,) = self.m1.calls([{"fn": "d_blob_hash", "args": [{"val": 2}, {"val": [5]}]}])
        self.assertEqual(inst, standin)

    def test_laws_over_the_model_must_bind_agg(self):
        """A statement that runs the M2 model binds the parameter (I15 states its laws over it)."""
        mlaws = holon_module("holon.gen.mlaws")
        law = load_json(ROOT / "laws" / "M1" / "L_disch_stale.json")
        with self.assertRaises(mlaws.Unsupported):
            mlaws.Emitter(self.cm.m).emit(law, "../model/morph_rollup.bend")
        law3 = copy.deepcopy(law)
        law3["ir_version"] = "holon-ir/0.3"
        law3["statement"]["binders"].append({"q": "forall", "name": "agg", "type": "Fn<List<Nat>,Nat>"})
        em = mlaws.Emitter(self.cm.m).emit(law3, "../model/morph_rollup.bend")
        self.assertIn("for +agg: List<&2, M.HO_agg>", em.text)
        self.assertIn("M.step(a, s, agg)", em.text)

    def test_entry_point(self):
        p = run_holon(["model", "--milestone", "M2", "--facts", "spec/M1/facts/morph_rollup.json"], cwd=ROOT)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
        self.assertIn("parameters ['agg']; threaded through step and run: ['agg']", p.stdout)
        self.assertIn("ALL PROOFS CHECK", p.stdout)


class TestLedgerAssumptions(unittest.TestCase):
    def setUp(self):
        self.O, Mach, F = (holon_module(n) for n in ("holon.gen.oracles", "holon.gen.machine", "holon.facts"))
        self.orc = self.O.Oracles.for_milestone("M2", ROLLUP, ROOT)
        self.m = Mach.Machine(F.load(ROLLUP), ROLLUP, oracles=self.orc, m2plus=True)

    def test_only_the_replaced_stand_ins_go(self):
        self.assertEqual(self.O.replaced_stand_ins(self.orc, self.m), {"CF-keccak-blobhashes"})
        got = self.O.ledger_assumptions(["CF-keccak-blobhashes", "CF-keccak-headers", "Hyp-Z0-kzg", "abs-nat-tokens",
                                         "oracle-ISubmitter", "oracle-verifier"], self.orc, self.m)
        self.assertEqual(got, ["CF-keccak-headers", "Hyp-Z0-kzg", "abs-nat-tokens", "oracle-ISubmitter", "oracle-verifier"])

    def test_the_audit_law_keeps_its_ledger_cone(self):
        """L_sort_remaining's M1 record lists 11 ledger entries; over M2 it keeps all but the replaced stand-ins."""
        rec = load_json(ROOT / "results" / "M1" / "L_sort_remaining.json")
        self.assertEqual(len(rec["model_assumptions"]), 11)
        got = self.O.ledger_assumptions(rec["model_assumptions"], self.orc, self.m)
        self.assertEqual(got, sorted(set(rec["model_assumptions"]) - {"CF-keccak-blobhashes"}))
        self.assertIn("abs-nat-tokens", got)

    def test_g9_rejects_an_empty_or_missing_ledger_set(self):
        law = load_json(ROOT / "laws" / "M1" / "L_sort_remaining.json")
        rec = load_json(ROOT / "results" / "M1" / "L_sort_remaining.json")
        want = self.O.ledger_assumptions(sorted(set(rec["model_assumptions"])), self.orc, self.m)
        for value, ok in ((want, True), ([], False), (None, False), (want[:-1], False)):
            with self.subTest(ledger_assumptions=value):
                r = dict(rec)
                if value is None:
                    r.pop("ledger_assumptions", None)
                else:
                    r["ledger_assumptions"] = value
                probs = self.O.ledger_problems("M2", ROOT, [law], {law["law_id"]: r})
                self.assertEqual(probs == [], ok, probs)
        probs = self.O.ledger_problems("M2", ROOT, [law], {law["law_id"]: {**rec, "ledger_assumptions": []}})
        self.assertIn("lists no ledger assumption", probs[0])


class TestRecordsKeepTheirLedgerCone(unittest.TestCase):
    """A run of an I12 fixture law (T12) writes ledger_assumptions beside model_assumptions, and G9 passes on it."""

    def test_fixture_record_and_g9(self):
        repo = copy_repo()
        try:
            rel = "tests_m2/fixtures/oracles/facts/toy_oracle.facts.json"
            sha = hashlib.sha256((repo / rel).read_bytes()).hexdigest()
            d = repo / "laws" / "T12"
            d.mkdir(parents=True)
            law = load_json(ROOT / "tests_m2" / "fixtures" / "oracles" / "laws" / "L_orc_cf_commit.json")
            law["facts"], law["facts_sha256"] = rel, sha
            write_json(d / "L_orc_cf_commit.json", law)
            write_json(d / "REGISTRY.json", {"milestone": "T12", "facts": rel, "facts_sha256": sha, "facts_files": {rel: sha},
                                             "statements": {"L_orc_cf_commit": None}})
            p = run_holon(["run", "--milestone", "T12", "--no-registry"], cwd=repo, timeout=1800)
            self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
            rec = load_json(repo / "results" / "T12" / "L_orc_cf_commit.json")
            self.assertEqual(rec["model_assumptions"], ["CF-agg"])
            self.assertTrue(rec["ledger_assumptions"], rec)   # the fixture ledger's abstraction meets every cone
            G = holon_module("holon.gate")
            g = G.Gate("T12", repo)
            g.g9()
            self.assertTrue(g.checks["G9"]["passed"], g.checks["G9"]["detail"])
            rec["ledger_assumptions"] = []
            write_json(repo / "results" / "T12" / "L_orc_cf_commit.json", rec)
            g.g9()
            self.assertFalse(g.checks["G9"]["passed"])
            self.assertIn("lists no ledger assumption", g.checks["G9"]["detail"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
