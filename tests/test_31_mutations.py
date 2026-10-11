"""P3: planted bugs in the facts move the outcomes exactly as predicted (mutation adequacy)."""
import json
import shutil
import unittest

from tests._util import FACTS, ROOT, copy_repo, load_json, load_law, run_holon
from tests.reference import ref_ir as I
from tests.reference import ref_model as M
from tests.reference import ref_mutate as X


class TestMutations(unittest.TestCase):
    def test_each_mutation(self):
        base = M.load_facts(FACTS)
        for m in load_json(ROOT / "predictions" / "M0_mutations.json")["mutations"]:
            with self.subTest(mutation=m["id"]):
                repo = copy_repo()
                try:
                    facts = X.apply(base, m["edit"])
                    fpath = repo / "facts_mutated.json"
                    fpath.write_text(json.dumps(facts, indent=2))
                    out, gen = repo / "mut_results", repo / "mut_gen"
                    p = run_holon(["run", "--milestone", "M0", "--facts", str(fpath), "--out", str(out),
                                   "--gen-dir", str(gen), "--no-registry"], cwd=repo)
                    self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
                    summary = load_json(out / "summary.json")
                    for lid, allowed in m["expect"].items():
                        self.assertIn(summary[lid], allowed, f"{m['id']}: {lid} -> {summary[lid]}")
                        if summary[lid] == "REFUTED":
                            r = load_json(out / f"{lid}.json")
                            law = load_law(lid)
                            chk = I.check(law, facts, I.env_from_witness(law, facts, r["witness"]))
                            self.assertIs(chk["claim"], False, f"{m['id']}: {lid} witness not valid under mutated facts")
                finally:
                    shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
