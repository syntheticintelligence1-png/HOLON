"""P4: the gate passes on the committed tree, rejects every canary, and catches tampering."""
import json
import shutil
import unittest
from pathlib import Path

from tests._util import FACTS, ROOT, config, copy_repo, load_json, run_holon, validate
from tests.reference import ref_ir as I
from tests.reference import ref_model as M

PROVED_LAW = "L_par_hdr_v1"


def run_gate(repo: Path):
    report = repo / "gate_report_test.json"
    p = run_holon(["gate", "--milestone", "M0", "--root", str(repo), "--report", str(report)], cwd=repo)
    rep = load_json(report) if report.exists() else None
    return p, rep


class TestGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        cls.proc, cls.report = run_gate(cls.repo)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo.parent, ignore_errors=True)

    def test_gate_passes_on_committed_tree(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stdout[-3000:] + self.proc.stderr[-2000:])
        self.assertIsNotNone(self.report)
        validate(self.report, "gate_report")
        self.assertTrue(self.report["passed"])
        self.assertEqual(self.report["bend_version"], config()["bend"]["pinned_version"])
        for g, c in self.report["checks"].items():
            self.assertTrue(c["passed"], f"{g}: {c['detail']}")

    def test_canaries(self):
        facts = M.load_facts(FACTS)
        cans = self.report["canaries"]
        self.assertGreaterEqual(len(cans), 10)
        self.assertGreaterEqual(len({c["kind"] for c in cans}), 3)
        for c in cans:
            with self.subTest(canary=c["id"]):
                self.assertTrue(c["rejected"], f"canary accepted by the checker: {c['id']}")
                law = c.get("law")
                self.assertIsNotNone(law, "each canary carries its IR so the oracle can confirm it is false")
                chk = I.check(law, facts, I.env_from_witness(law, facts, c["counterexample"]))
                self.assertTrue(chk["premises"])
                if c.get("negated"):
                    self.assertIs(chk["claim"], True, "a negated canary must be false: the sides are equal here")
                else:
                    self.assertIs(chk["claim"], False, "the counterexample must falsify the canary claim")


def tamper_and_gate(edit) -> tuple:
    repo = copy_repo()
    try:
        edit(repo)
        p, rep = run_gate(repo)
        return p.returncode, rep
    finally:
        shutil.rmtree(repo.parent, ignore_errors=True)


def proof_dir(repo: Path) -> Path:
    rec = load_json(repo / "results" / "M0" / f"{PROVED_LAW}.json")
    p = Path(rec["artifacts"]["proof"])
    p = p if p.is_absolute() else repo / p
    return p.parent


class TestGateCatchesTampering(unittest.TestCase):
    def check(self, edit, must_fail: list[str]):
        code, rep = tamper_and_gate(edit)
        self.assertNotEqual(code, 0, "gate passed on a tampered tree")
        self.assertIsNotNone(rep, "gate must still write its report when failing")
        self.assertFalse(rep["passed"])
        for g in must_fail:
            self.assertFalse(rep["checks"][g]["passed"], f"{g} should fail")

    def test_hole_in_proof(self):
        def edit(repo):
            f = proof_dir(repo) / "PROOF.bend"
            f.write_text(f.read_text() + "\ndef extra_hole(x: Nat) -> Nat:\n  ?TODO\n")
        self.check(edit, ["G3", "G5"])

    def test_unsafe_in_proof(self):
        def edit(repo):
            f = proof_dir(repo) / "PROOF.bend"
            f.write_text(f.read_text() + "\n@unsafe def sneaky(x: Nat) -> Nat:\n  sneaky(x)\n")
        self.check(edit, ["G3"])

    def test_proof_removed(self):
        def edit(repo):
            f = proof_dir(repo) / "PROOF.bend"
            f.write_text("import Base\nimport ./LAWS.bend as Laws\n")
        self.check(edit, ["G5"])

    def test_law_removed_is_vacuous(self):
        def edit(repo):
            d = proof_dir(repo)
            (d / "LAWS.bend").write_text("import Base\n")
            (d / "PROOF.bend").write_text("import Base\nimport ./LAWS.bend as Laws\n")
        self.check(edit, ["G11"])

    def test_statement_edited(self):
        def edit(repo):
            f = repo / "laws" / "M0" / f"{PROVED_LAW}.json"
            law = json.loads(f.read_text())
            law["statement"]["assume"] = law["statement"]["assume"][:1]
            f.write_text(json.dumps(law, indent=2))
        self.check(edit, ["G2"])

    def test_bunfig_present(self):
        def edit(repo):
            (repo / "bunfig.toml").write_text('preload = ["./x.ts"]\n')
        self.check(edit, ["GENV"])


if __name__ == "__main__":
    unittest.main()
