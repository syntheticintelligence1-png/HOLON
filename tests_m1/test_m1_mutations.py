"""M1: planted bugs in the rollup facts move the outcomes exactly as predicted (mutation adequacy, A1)."""
import shutil
import unittest

from tests._util import copy_repo, load_json, run_holon
from tests_m1._m1 import SPEC, apply_edit, write_json


class TestM1Mutations(unittest.TestCase):
    def test_each_mutation(self):
        base = load_json(SPEC / "facts" / "morph_rollup.json")
        for m in load_json(SPEC / "mutations.json")["mutations"]:
            with self.subTest(mutation=m["id"]):
                repo = copy_repo()
                try:
                    fpath = repo / "facts_mutated_m1.json"
                    write_json(fpath, apply_edit(base, m["edit"]))
                    out, gen = repo / "mut_results", repo / "mut_gen"
                    p = run_holon(["run", "--milestone", "M1", "--facts", str(fpath), "--out", str(out), "--gen-dir", str(gen),
                                   "--no-registry"], cwd=repo)
                    self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
                    summary = load_json(out / "summary.json")
                    for lid, allowed in m["expect"].items():
                        self.assertIn(summary[lid], allowed, f"{m['id']}: {lid} -> {summary[lid]}")
                finally:
                    shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
