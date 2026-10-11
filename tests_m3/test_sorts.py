"""M3 sorts acceptance tests (stdlib only). Run: python -m unittest discover -s tests_m3 -t ."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from holon import ir  # noqa: E402
from holon.sorts import grammar as G, rules as R, infer as I, bendgen as B  # noqa: E402

M3 = ROOT / "spec" / "M3" / "sorts"
SEEDS = json.loads((M3 / "seeds.json").read_text())
ROLLUP = ROOT / "spec" / "M1" / "facts" / "morph_rollup.json"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class Grammar(unittest.TestCase):
    def test_parse_roundtrip(self):
        for txt in ["Mach(256)", "Time", "Dur", "Dur-", "Idx[batch]", "Cnt[msg]", "Prin[submitter]", "Amt[eth]", "Dig[root]", "Ver",
                    "Null+Prin[submitter]", "List<Dig[bvh]>"]:
            self.assertEqual(str(G.parse(txt)), txt)

    def test_union_is_canonical(self):
        self.assertEqual(G.union(G.parse("Prin[x]"), G.NULL), G.union(G.NULL, G.parse("Prin[x]")))
        self.assertEqual(G.union(G.TIME, G.TIME), G.TIME)


class Affine(unittest.TestCase):
    def test_point_minus_point_is_signed(self):
        self.assertEqual(R.combine("-", G.TIME, G.TIME), G.SDUR)
        self.assertEqual(R.combine("-", G.parse("Idx[batch]"), G.parse("Idx[batch]")), G.parse("Cnt[batch]-"))

    def test_point_plus_point_is_ill_sorted(self):
        for a, b in [(G.TIME, G.TIME), (G.parse("Prin[a]"), G.parse("Prin[a]")), (G.parse("Amt[eth]"), G.parse("Cnt[msg]"))]:
            with self.assertRaises(R.IllSorted):
                R.combine("+", a, b)

    def test_shift_and_counts(self):
        self.assertEqual(R.combine("+", G.TIME, G.DUR), G.TIME)
        self.assertEqual(R.combine("+", G.DUR, G.TIME), G.TIME)
        self.assertEqual(R.combine("+", G.parse("Cnt[msg]"), G.parse("Cnt[msg]")), G.parse("Cnt[msg]"))

    def test_union_arithmetic_skips_null(self):
        self.assertEqual(R.combine("-", G.parse("Null+Time"), G.TIME), G.SDUR)

    def test_width_of_sum(self):
        self.assertEqual(R.width_of_sum([64, 16]), 65)
        self.assertEqual(R.width_obligation(65, 64)["bound"], 2 ** 64)
        self.assertIsNone(R.width_obligation(16, 16))

    def test_signed_needs_proof(self):
        self.assertEqual(R.realize_obligation(G.SDUR)["unsigned"], "Dur")
        self.assertIsNone(R.realize_obligation(G.DUR))


class Inference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = I.infer(json.loads(ROLLUP.read_text()), SEEDS["spec/M1/facts/morph_rollup.json"]).to_json()

    def test_no_conflicts(self):
        self.assertEqual(self.a["conflicts"], [])

    def test_o27_realize_obligation_at_commit_site(self):
        obs = [o for o in self.a["obligations"] if o["kind"] == "realize" and o["where"] == "action:commitBatch/guard[24]"]
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["sort"], "Dur-")
        self.assertIn("16", obs[0]["discharged"])          # discharged only by the Panic(0x11) guard

    def test_o20_null_principal_unions(self):
        self.assertEqual(self.a["fields"]["Ch.c"], "Null+Prin[challenger]")
        self.assertEqual(self.a["fields"]["Entry.bds"], "Null+Prin[submitter]")

    def test_o21_time_sentinel(self):
        self.assertTrue(any(o["kind"] == "sentinel" and o["sort"] == "Time" and o["where"] == "def:enq_first" for o in self.a["obligations"]))

    def test_o28_width(self):
        ws = [o for o in self.a["obligations"] if o["kind"] == "width" and o["register"] == "Entry.tot"]
        self.assertTrue(ws and all(o["needed"] == 65 for o in ws))

    def test_frozen_assignment_matches(self):
        frozen = json.loads((M3 / "assignment" / "morph_rollup.json").read_text())
        for k in ("registers", "fields", "obligations"):
            self.assertEqual(frozen[k], self.a[k])


class Laws(unittest.TestCase):
    def test_o27_agrees_with_m1(self):
        m1 = json.loads((ROOT / "laws" / "M1" / "L_sort_remaining.json").read_text())
        m3 = json.loads((M3 / "laws" / "L_sort3_remaining.json").read_text())
        self.assertEqual(m1["statement"], m3["statement"])

    def test_registry_binds_laws(self):
        reg = json.loads((M3 / "laws" / "REGISTRY.json").read_text())
        laws = ir.load_laws_any("M3_sorts", ROOT)
        self.assertEqual(set(reg["statements"]), {l["law_id"] for l in laws})
        for l in laws:
            self.assertEqual(reg["statements"][l["law_id"]], ir.statement_hash(l))
            self.assertEqual(l["facts_sha256"], sha(ROOT / l["facts"]))

    def test_frozen_roots_untouched(self):
        reg1 = json.loads((ROOT / "laws" / "M1" / "REGISTRY.json").read_text())
        for f, h in reg1["facts_files"].items():
            self.assertEqual(sha(ROOT / f), h)


class BendTypes(unittest.TestCase):
    def test_canary_texts_differ_from_main(self):
        a = json.loads((M3 / "assignment" / "morph_rollup.json").read_text())
        main = B.generate(a)
        self.assertEqual(main, (M3 / "gen" / "sorts.bend").read_text())
        for c in B.CANARIES:
            self.assertNotEqual(main, B.generate(a, canary_drop=c))

    def test_sorts_report_canaries_rejected(self):
        rep = json.loads((ROOT / "results" / "M3_sorts" / "sorts_report.json").read_text())
        self.assertTrue(rep["bend"]["sorts"]["ok"])
        for c in B.CANARIES:
            self.assertTrue(rep["bend"][f"canary:{c}"]["rejected"], c)


class GateAndReplay(unittest.TestCase):
    """The committed tree: gate passed with both canary families; every REFUTED record is replayed or labelled."""

    def test_gate_report(self):
        g = json.loads((ROOT / "results" / "M3_sorts" / "gate_report.json").read_text())
        self.assertTrue(g["passed"], g["checks"])
        kinds = {c["kind"] for c in g["canaries"]}
        self.assertTrue({"negated", "witness_prefix"} <= kinds)
        self.assertTrue({"sort_" + c for c in B.CANARIES} <= kinds)
        self.assertTrue(all(c["rejected"] for c in g["canaries"]))

    def test_refuted_records_are_replayed_or_labelled(self):
        for p in sorted((ROOT / "results" / "M3_sorts").glob("L_*.json")):
            r = json.loads(p.read_text())
            if r["status"] != "REFUTED":
                continue
            with self.subTest(law=r["law_id"]):
                st = r["replay"]["status"]
                self.assertIn(st, ("passed", "not_run"))
                if st == "not_run":
                    self.assertIn("model-only pending replay", r["replay"]["detail"])

    def test_expected_verdicts(self):
        want = {"L_sort3_remaining": ("REFUTED", "passed"), "L_sort3_width_l1num": ("REFUTED", "passed"),
                "L_sort3_prin_submitter": ("REFUTED", "passed"), "L_sort3_prin_challenger": ("REFUTED", "not_run"),
                "L_sort3_enq_sentinel": ("REFUTED", "not_run"), "L_sort3_enq_fresh": ("UNKNOWN", "not_run")}
        for lid, (status, rp) in want.items():
            r = json.loads((ROOT / "results" / "M3_sorts" / f"{lid}.json").read_text())
            self.assertEqual((r["status"], r["replay"]["status"]), (status, rp), lid)

    def test_replay_report_witnesses_match(self):
        rep = json.loads((ROOT / "replay" / "M3_sorts" / "report.json").read_text())
        from holon.replay import witness_sha256
        for lid, h in rep["witness_sha256"].items():
            r = json.loads((ROOT / "results" / "M3_sorts" / f"{lid}.json").read_text())
            self.assertEqual(h, witness_sha256(r["witness"]), lid)
        self.assertEqual(rep["refinement"]["n_disagreements"], 0)


class Determinism(unittest.TestCase):
    def test_sorts_pass_is_idempotent(self):
        before = {p: sha(p) for p in M3.rglob("*") if p.is_file()}
        subprocess.run([sys.executable, "-m", "holon", "sorts"], cwd=ROOT, check=True, capture_output=True)
        after = {p: sha(p) for p in M3.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
