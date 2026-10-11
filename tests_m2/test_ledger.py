"""I1: every record states exactly its statement's premises and the model assumptions its cone reaches."""
import fnmatch
import json
import unittest

from tests_m2._m2 import (MILESTONES, ROOT, bundle_for, holon_module, independent_cone, introduces, item, laws,
                          ledger, load_json, model_defs, records)


class TestLedger(unittest.TestCase):
    def test_premises_are_exactly_the_rendered_statement_premises(self):
        ir = holon_module("holon.ir")
        for m in MILESTONES:
            ls = laws(m)
            for lid, rec in records(m).items():
                with self.subTest(law=lid):
                    self.assertEqual(rec["premises"], ir.premises(ls[lid]))
                    self.assertFalse(any("CF(" in p for p in rec["premises"]), rec["premises"])

    def test_premises_render_every_assume_clause(self):
        ir = holon_module("holon.ir")
        for m in MILESTONES:
            for lid, law in laws(m).items():
                with self.subTest(law=lid):
                    ps = ir.premises(law)
                    self.assertEqual(len(ps), len(law["statement"].get("assume", [])))
                    for p in ps:
                        self.assertNotIn("{", p, "premises are rendered, not JSON")

    def test_model_assumptions_match_prediction(self):
        want = item("I1", "I1-P1")["expected"]
        got = {lid: rec.get("model_assumptions") for m in MILESTONES for lid, rec in records(m).items()}
        self.assertEqual(sorted(got), sorted(want))
        for lid in sorted(want):
            with self.subTest(law=lid):
                self.assertEqual(got[lid], sorted(want[lid]))

    def test_own_record_carries_no_hash_assumption(self):
        rec = records("M1")["L_own_txspayload"]
        kinds = {e["id"]: e["kind"] for e in bundle_for(rec)["entries"]}
        self.assertTrue(rec["model_assumptions"])
        self.assertFalse([a for a in rec["model_assumptions"] if kinds[a] == "hash"])

    def test_fact_Z_carries_Z0(self):
        rec = records("M1")["L_fact_Z"]
        self.assertIn("Hyp-Z0-kzg", rec["model_assumptions"])
        self.assertNotIn("HypZ", rec["model_assumptions"], "HypZ is reserved for the compression hypothesis (§8.5)")

    def test_no_assumption_outside_cone(self):
        for m in MILESTONES:
            for lid, rec in records(m).items():
                with self.subTest(law=lid):
                    cone = independent_cone(rec)
                    self.assertEqual(sorted(cone), rec["cone"], "stored cone differs from an independent computation")
                    entries = {e["id"]: e for e in bundle_for(rec)["entries"]}
                    for a in rec["model_assumptions"]:
                        self.assertTrue(introduces(entries[a], cone), f"{a} has no introducer in the cone")
                    missing = [e for e in entries if introduces(entries[e], cone) and e not in rec["model_assumptions"]]
                    self.assertEqual(missing, [], "an entry introduced in the cone was dropped")

    def test_every_introducer_in_cone_is_classified(self):
        for b in ledger()["bundles"]:
            gen = "M0" if b["facts"].startswith("facts/") else "M1"
            defs = model_defs(ROOT / "gen" / gen / "model" / f"{b['model']}.bend")
            with self.subTest(model=b["model"]):
                bad = []
                for d in defs:
                    by_entry = [e["id"] for e in b["entries"]
                                if any(p != "*" and fnmatch.fnmatchcase(d, p) for p in e["introduced_by"])]
                    groups = [g for g in b["no_assumption"] if any(fnmatch.fnmatchcase(d, p) for p in g["defs"])]
                    if not by_entry and len(groups) != 1:
                        bad.append((d, len(groups)))
                self.assertEqual(bad, [], "every model definition is classified once (entries take precedence)")
                pats = [p for e in b["entries"] for p in e["introduced_by"] if p != "*"]
                pats += [p for g in b["no_assumption"] for p in g["defs"]]
                dead = [p for p in pats if not any(fnmatch.fnmatchcase(d, p) for d in defs)]
                self.assertEqual(dead, [], "a ledger pattern names no definition")

    def test_ledger_sources_resolve_and_ids_are_unique(self):
        ids = []
        for b in ledger()["bundles"]:
            facts = load_json(ROOT / b["facts"])
            import hashlib
            self.assertEqual(hashlib.sha256((ROOT / b["facts"]).read_bytes()).hexdigest(), b["facts_sha256"])
            for e in b["entries"]:
                ids.append(e["id"])
                path, _, ptr = e["source"].partition("#")
                self.assertEqual(path, b["facts"])
                cur = facts
                for part in ptr.lstrip("/").split("/"):
                    cur = cur[int(part)] if isinstance(cur, list) else cur[part]
                self.assertIsNotNone(cur)
        self.assertEqual(len(ids), len(set(ids)))

    def test_unknown_facts_bundle_is_an_error(self):
        R = holon_module("holon.records")
        with self.assertRaises(R.LedgerError):
            R.model_assumptions("0" * 64, {"run", "step"})
        rec = records("M1")["L_undo_CSR"]
        self.assertEqual(R.model_assumptions(rec["facts_sha256"], set(rec["cone"])), rec["model_assumptions"])


class TestDerivedFacts(unittest.TestCase):
    """Added after the I1 prereg: the frozen mutation test (tests/test_31) runs the pipeline over facts the
    ledger cannot know. Such records must say so (ledger_match "derived") and never pass the v2 schema."""

    def test_derived_facts_run_is_flagged(self):
        import shutil
        from tests_m2._m2 import SCHEMAS2, copy_repo, run_holon, validate
        repo = copy_repo()
        try:
            src = (repo / "facts" / "morph_header.json").read_text()
            f = repo / "facts_derived.json"
            f.write_text(src + "\n")  # same content, different sha256
            out, gen = repo / "d_results", repo / "d_gen"
            p = run_holon(["run", "--milestone", "M0", "--facts", str(f), "--out", str(out), "--gen-dir", str(gen),
                           "--no-registry"], cwd=repo)
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
            committed = records("M0")
            derived = {q.stem: load_json(q) for q in sorted(out.glob("L_*.json"))}
            self.assertEqual(sorted(derived), sorted(committed))
            for lid, rec in derived.items():
                with self.subTest(law=lid):
                    self.assertEqual(rec["ledger_match"], "derived")
                    self.assertEqual(rec["model_assumptions"], committed[lid]["model_assumptions"])
                    self.assertNotEqual(validate(rec, SCHEMAS2 / "result_record_v2.schema.json"), [])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
