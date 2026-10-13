"""I19: coverage accounting, gate check G8, and cross-language linking (whitepaper §9.3 G8, L1 coverage, §10.1
linking; BUILD_PLAN I19). The extraction formats are in the docstring of tests_m2/test_extract_transitions.py.

Coverage (holon/coverage.py; python -m holon coverage --milestone M2 writes gen/M2/coverage.json, canonical JSON):
  {"documents": [{"document": "<extracted document>", "statements": n,
                  "extracted": n, "debt": [{"src", "kind", "detail"}], "unaccounted": [{"src", "node"}]}],
   "unaccounted": n}
  - statements: every Statement node of the bodies of the contract's external/public functions and of every
    internal function and modifier they reach.
  - Each statement must be extracted (it contributes to a guard, effect, cost term, edge or principal, or is
    plain local computation feeding one), or be listed as debt.
  - debt kinds:
      external_call       an external call that is not a COMMIT edge;
      loop_storage_write  a loop whose body writes storage;
      value_transfer      a call with value;
      unsupported         a statement the walker cannot represent, with its node type.
  - unaccounted lists the statements that are neither extracted nor debt.

G8 (holon/gate.py; M2+ milestones): the coverage report exists, a fresh run reproduces it byte for byte, and
unaccounted is 0 for every extracted document. M0 and M1 list G8 under not_applicable. Records v2 gain
"coverage": {"document", "debt": n, "unaccounted": n} for M2 laws over an extracted document, and null otherwise.
The "pending:I19" value is removed; the change to the I1 pending-field assertion is logged as a pending-field
amendment.

Linking (holon/frontends/link.py; python -m holon link --milestone M2 writes gen/M2/link.json, canonical JSON):
  {"links": [{"role", "solidity": <value>, "go": <value>, "equal": bool}]}
  The roles and their sources are in spec/M2/lib/link.json. Values are read from the extracted documents only:
    header_length        a sorted list of [first byte, length] pairs;
    zero_versioned_hash  a 0x-hex string.
"""
import json
import unittest

from tests_m2._m2 import ROOT, load_json, run_holon

R = "contracts/contracts/l1/rollup/Rollup.sol"


def report(name: str) -> dict:
    p = ROOT / "gen" / "M2" / name
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing")
    return load_json(p)


class TestCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = report("coverage.json")
        cls.roll = [d for d in cls.c["documents"] if d["document"].endswith("morph_rollup.extracted.json")]

    def test_nothing_is_unaccounted(self):
        """I19-P7: unaccounted = 0 for the rollup document."""
        self.assertEqual(len(self.roll), 1)
        self.assertEqual(self.roll[0]["unaccounted"], [])
        self.assertEqual(self.c["unaccounted"], 0)

    def test_storage_writing_loops_and_external_calls_are_debt(self):
        """I19-P8: the storage-writing loops of revertBatch (:444) and challengeState (:489) are loop_storage_write
        debt; the submitter check (:120) and the value transfer (:816) are external_call and value_transfer debt."""
        debt = {(d["kind"], d["src"].rsplit(":", 1)[-1].split("-")[0]) for d in self.roll[0]["debt"]
                if d["src"].startswith(R + ":")}
        for want in (("loop_storage_write", "444"), ("loop_storage_write", "489"), ("external_call", "120"),
                     ("value_transfer", "816")):
            with self.subTest(debt=want):
                self.assertIn(want, debt)

    def test_coverage_cli_reproduces_the_report(self):
        """Construction: a fresh run equals the committed report."""
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "coverage.json"
            p = run_holon(["coverage", "--milestone", "M2", "--out", str(out)], timeout=900)
            self.assertEqual(p.returncode, 0, p.stderr[-1500:])
            self.assertEqual(out.read_bytes(), (ROOT / "gen" / "M2" / "coverage.json").read_bytes())


class TestLink(unittest.TestCase):
    def test_header_lengths_and_the_zero_versioned_hash_agree_across_languages(self):
        """I19-P9: the header length per version and the zero versioned hash are equal across Solidity and Go."""
        links = {l["role"]: l for l in report("link.json")["links"]}
        self.assertEqual(set(links), {"header_length", "zero_versioned_hash"})
        for role, l in links.items():
            with self.subTest(role=role):
                self.assertTrue(l["equal"], l)
                self.assertEqual(l["solidity"], l["go"])
        self.assertEqual(links["header_length"]["solidity"], [[0, 249], [1, 257], [2, 257]])


class TestRecordsAndGate(unittest.TestCase):
    def test_records_carry_coverage(self):
        """Construction: no record says pending:I19; M2 site-law records over extracted documents carry coverage."""
        for m in ("M0", "M1", "M2"):
            for p in sorted((ROOT / "results" / m).glob("L*.json")):
                with self.subTest(record=f"{m}/{p.name}"):
                    self.assertNotEqual(load_json(p).get("coverage"), "pending:I19")

    def test_g8_passes_on_m2(self):
        """Construction: G8 PASS in a fresh M2 gate run of G8 alone."""
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as t:
            rep = Path(t) / "g8.json"
            p = run_holon(["gate", "--milestone", "M2", "--checks", "G8", "--report", str(rep)], timeout=1800)
            self.assertTrue(rep.is_file(), p.stdout[-1500:] + p.stderr[-1500:])
            self.assertTrue(json.loads(rep.read_text())["checks"]["G8"]["passed"])


if __name__ == "__main__":
    unittest.main()
