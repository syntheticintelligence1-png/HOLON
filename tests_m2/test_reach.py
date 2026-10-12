"""I8: core library and Reach (whitepaper §8.3 (R), §6 core library, §10.3, L2; BUILD_PLAN I8).

holon/gen/core.py emits a core library <gen_dir>/core/{LAWS.bend, PROOF.bend}: shared lemmas,
checked once and imported, never pasted unchecked. Generated proofs of M2+ milestones (any milestone
other than M0 and M1) import `../core/PROOF.bend`, never `core/LAWS.bend` alone; G3 bans a bare core
LAWS import textually, and a G4 canary leaves one core law unproved. M0 and M1 keep their pasted CORE.

For M2+ milestones the model carries `Reach : HSt -> Type` (constructors for s0 and for one step), and
the IR 0.3 binder type `Reach` quantifies over reachable states. `mproofs.reach_invariant` proves
invariants by induction on Reach; `holon/js/houdini.mjs` (untrusted) proposes strengthenings, which
live only in proof files. A Reach premise is inhabited by an s0 / step chain (G11V).

API these tests read:
  holon.gen.core.emit(gen_dir, omit=None) -> [law names]   writes gen_dir/core/{LAWS,PROOF}.bend;
                                                            omit leaves that law without a proof
  holon.gen.core.bare_laws_imports(text) -> [str]           the lines importing a core LAWS module
  holon run --core {import,paste}                            M2+ proofs import the core (default) or
                                                            paste the same core text (baseline for P4)
"""
import hashlib
import json
import shutil
import statistics
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, copy_repo, holon_module, load_json, run_holon, write_json

FIX = ROOT / "tests_m2" / "fixtures" / "reach"
TOY = "tests_m2/fixtures/toy_reach/toy_reach.facts.json"
TRUE_IDS = ["L8_reach_y", "L8_reach_x"]
FALSE_IDS = ["L8_reach_k", "L8_reach_flag"]
IDS = TRUE_IDS + FALSE_IDS
PROBE = ROOT / "bend" / "notes" / "p_core_import"


def bend(args: list[str], cwd: Path | None = None) -> tuple[int, str]:
    from tests._util import run_bend
    return run_bend(args, cwd=cwd) if cwd else run_bend(args)


def run_reach(core: str = "import") -> tuple[dict, str, Path]:
    """Run the four fixtures on the toy reach machine as milestone T2; returns (records, log, kept gen dir)."""
    repo = copy_repo()
    keep = Path(tempfile.mkdtemp(prefix=f"holon-reach-{core}-"))
    try:
        sha = hashlib.sha256((repo / TOY).read_bytes()).hexdigest()
        d = repo / "laws" / "T2"
        d.mkdir(parents=True)
        for lid in IDS:
            law = load_json(FIX / f"{lid}.json")
            law["facts_sha256"] = sha
            write_json(d / f"{lid}.json", law)
        write_json(d / "REGISTRY.json", {"milestone": "T2", "facts": TOY, "facts_sha256": sha,
                                         "facts_files": {TOY: sha}, "statements": {i: None for i in IDS}})
        out, gen = repo / "t2_results", repo / "t2_gen"
        p = run_holon(["run", "--milestone", "T2", "--no-registry", "--core", core, "--out", str(out), "--gen-dir", str(gen)],
                      cwd=repo)
        recs = {lid: load_json(out / f"{lid}.json") for lid in IDS if (out / f"{lid}.json").exists()}
        if gen.exists():
            shutil.copytree(gen, keep / "gen")
        return recs, p.stdout[-3000:] + p.stderr[-3000:], keep / "gen"
    finally:
        shutil.rmtree(repo.parent, ignore_errors=True)


def law_files_of(gen: Path, lid: str) -> list[Path]:
    """The law's own generated files, whatever the layout (gen/<law>/ or gen/{laws,proofs}/<law>/),
    without its non-vacuity inhabitant or generated negation."""
    return sorted(p for p in gen.rglob("*.bend") if lid in p.parts and not {"nonvac", "neg"} & set(p.parts))


class TestCoreImportProbe(unittest.TestCase):
    def test_unproved_imported_law_fails(self):
        """I8-P1: probe (a). bend/notes/p_core_import/a/user/PROOF.bend imports ../core/LAWS.bend, whose law
        c_open has no proof anywhere, and uses c_open as a lemma: its check must fail."""
        proof = PROBE / "a" / "user" / "PROOF.bend"
        self.assertTrue(proof.exists(), proof)
        self.assertIn("core/LAWS.bend", proof.read_text(encoding="utf-8"))
        code, out = bend([str(proof)])
        self.assertFalse(out.strip().startswith("ALL PROOFS CHECK"), out[-800:])


class TestCoreLibrary(unittest.TestCase):
    def setUp(self):
        self.C = holon_module("holon.gen.core")
        self.tmp = Path(tempfile.mkdtemp(prefix="holon-core-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_core_is_emitted_and_checks_under_both_kernels(self):
        names = self.C.emit(self.tmp)
        self.assertGreaterEqual(len(names), 3)
        laws = (self.tmp / "core" / "LAWS.bend").read_text(encoding="utf-8")
        for n in names:
            self.assertIn(f"law {n}:", laws)
        proof = self.tmp / "core" / "PROOF.bend"
        code, out = bend([str(proof)])
        self.assertEqual(code, 0, out[-800:])
        self.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), out[-800:])
        code, out = bend([str(proof), "--verdict"])
        self.assertIn("ALL PROOFS CHECK", out)

    def test_core_canary_with_an_unproved_law_is_rejected(self):
        """I8-P5 (exit): a core library with one law left unproved fails its check."""
        names = self.C.emit(self.tmp)
        shutil.rmtree(self.tmp / "core")
        self.C.emit(self.tmp, omit=names[0])
        code, out = bend([str(self.tmp / "core" / "PROOF.bend")])
        self.assertFalse(out.strip().startswith("ALL PROOFS CHECK"), out[-800:])

    def test_g3_flags_a_bare_core_laws_import(self):
        """I8-P5: G3 bans importing core/LAWS.bend alone."""
        self.assertTrue(self.C.bare_laws_imports("import Base\nimport ../core/LAWS.bend as C\n"))
        self.assertEqual(self.C.bare_laws_imports("import Base\nimport ../core/PROOF.bend as C\n"), [])


class TestReachToy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recs, cls.log, cls.gen = run_reach("import")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.gen.parent, ignore_errors=True)

    def rec(self, lid: str) -> dict:
        self.assertIn(lid, self.recs, self.log)
        return self.recs[lid]

    def test_true_invariants_proved(self):
        """I8-P2."""
        for lid in TRUE_IDS:
            with self.subTest(law=lid):
                self.assertEqual(self.rec(lid)["status"], "PROVED", self.rec(lid).get("attempts"))

    def test_false_invariants_refuted(self):
        """I8-P2: refuted at reachable states, given as traces from s0."""
        for lid in FALSE_IDS:
            with self.subTest(law=lid):
                r = self.rec(lid)
                self.assertEqual(r["status"], "REFUTED", r.get("attempts"))
                self.assertIsInstance(r["witness"]["s"]["run"], list)
                self.assertTrue(r["witness"]["s"]["run"])

    def test_strengthening_lives_in_the_proof_file(self):
        """I8-P2: x == 0 needs a strengthening; it is in PROOF.bend, never in LAWS.bend."""
        r = self.rec("L8_reach_x")
        att = [a for a in r["attempts"] if a.get("generator") == "reach_invariant" and a.get("marker") == "ALL PROOFS CHECK"]
        self.assertTrue(att, r["attempts"])
        self.assertTrue(att[-1].get("strengthening"), att[-1])
        texts = {str(p.relative_to(self.gen)): p.read_text(encoding="utf-8") for p in law_files_of(self.gen, "L8_reach_x")}
        law_files = [t for t in texts.values() if "\nlaw " in t]
        self.assertEqual(len(law_files), 1, list(texts))
        self.assertEqual(law_files[0].count("\nlaw "), 1)
        self.assertIn("strengthening", "".join(t for t in texts.values() if "\nlaw " not in t))

    def test_reach_checks_under_verdict(self):
        """I8-P3: every decided toy reach law is re-checked by BendTT."""
        for lid in IDS:
            with self.subTest(law=lid):
                self.assertEqual(self.rec(lid)["kernel"]["verdict"], "checked", self.rec(lid).get("attempts"))

    def test_reach_premise_inhabited(self):
        """I8-P6 (G11V): a PROVED law over Reach has a kernel-checked Reach inhabitant."""
        for lid in TRUE_IDS:
            with self.subTest(law=lid):
                nv = self.rec(lid)["non_vacuity"]
                self.assertEqual(nv["status"], "inhabited", nv)
                self.assertTrue(nv["reachable"], nv)


class TestCoreCost(unittest.TestCase):
    def test_core_import_costs_at_most_20_percent(self):
        """I8-P4: G5 time on the toy (the re-check of every proof file, median of 3 per file) with the core
        imported is at most 1.2x the time with the same core pasted into each proof."""
        recs_i, log_i, gen_i = run_reach("import")
        recs_p, log_p, gen_p = run_reach("paste")
        try:
            self.assertEqual({k: r["status"] for k, r in recs_i.items()}, {k: r["status"] for k, r in recs_p.items()},
                             log_i + log_p)

            def g5(gen: Path) -> float:
                total = 0.0
                proofs = [p for lid in IDS for p in law_files_of(gen, lid) if p.name == "PROOF.bend"]
                self.assertEqual(len(proofs), len(IDS), [str(p) for p in proofs])
                for proof in proofs:
                    ts = []
                    for _ in range(3):
                        t0 = time.monotonic()
                        code, out = bend([str(proof)])
                        ts.append(time.monotonic() - t0)
                        self.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), f"{proof}: {out[-400:]}")
                    total += statistics.median(ts)
                return total
            ti, tp = g5(gen_i), g5(gen_p)
            self.assertGreater(tp, 0)
            self.assertLessEqual(ti / tp, 1.2, f"import {ti:.2f}s vs paste {tp:.2f}s")
        finally:
            shutil.rmtree(gen_i.parent, ignore_errors=True)
            shutil.rmtree(gen_p.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
