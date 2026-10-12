"""I5: the first adversarial audit round on M0/M1 ran, is recorded in a checkable form, and leaves no
open high-severity finding before I6 (BUILD_PLAN I5; closes D-g).

Round files: audit/M0_round1.md and audit/M1_round1.md (prose), audit/rounds/<M>/round1.json
(machine-readable, validated against spec/schemas/audit_round.schema.json), audit/findings.jsonl
(one finding per line). `python -m holon audit status` summarises the findings and exits non-zero
while any high-severity finding is open.
"""
import json
import re
import unittest

from tests_m2._m2 import ROOT, load_json, run_holon, validate

AUDIT = ROOT / "audit"
CATEGORIES = ("statement_fidelity", "gate_evasion", "model_vs_code", "vacuity", "determinism",
              "mutation_adequacy", "bindings_ledger")
SEVERITIES = ("high", "medium", "low")
STATUSES = ("open", "fixed", "wontfix", "duplicate")


def findings() -> list[dict]:
    lines = (AUDIT / "findings.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(l) for l in lines if l.strip()]


def round_json(m: str) -> dict:
    return load_json(AUDIT / "rounds" / m / "round1.json")


class TestRoundFiles(unittest.TestCase):
    def test_prose_rounds_exist(self):
        for m in ("M0", "M1"):
            with self.subTest(milestone=m):
                text = (AUDIT / f"{m}_round1.md").read_text(encoding="utf-8")
                self.assertGreater(len(text), 2000, "a round report states what was tried, not only the verdict")

    def test_round_json_validates_and_covers_every_attack(self):
        schema = ROOT / "spec" / "schemas" / "audit_round.schema.json"
        ids = {f["id"] for f in findings()}
        for m in ("M0", "M1"):
            with self.subTest(milestone=m):
                r = round_json(m)
                self.assertEqual(validate(r, schema), [])
                self.assertEqual(r["milestone"], m)
                self.assertEqual(r["round"], 1)
                self.assertRegex(r["target_commit"], r"^[0-9a-f]{40}$")
                self.assertEqual({a["category"] for a in r["attacks"]}, set(CATEGORIES))
                for a in r["attacks"]:
                    self.assertTrue(a["tried"].strip(), a["id"])
                    self.assertIn(a["result"], ("finding", "no_finding"))
                    self.assertEqual(a["result"] == "finding", bool(a["findings"]), a["id"])
                    self.assertLessEqual(set(a["findings"]), ids, a["id"])

    def test_auditor_family_is_labelled(self):
        """Q9 is unanswered: a same-family round is labelled so and does not count toward convergence."""
        for m in ("M0", "M1"):
            with self.subTest(milestone=m):
                aud = round_json(m)["auditor"]
                self.assertIn(aud["family"], ("same", "different"))
                if aud["family"] == "same":
                    self.assertIs(aud["counts_toward_convergence"], False)


class TestFindings(unittest.TestCase):
    def test_findings_are_well_formed(self):
        seen = set()
        for f in findings():
            with self.subTest(finding=f.get("id")):
                self.assertRegex(f["id"], r"^F-M[01]-\d{2}$")
                self.assertNotIn(f["id"], seen)
                seen.add(f["id"])
                self.assertIn(f["severity"], SEVERITIES)
                self.assertIn(f["category"], CATEGORIES)
                self.assertIn(f["status"], STATUSES)
                self.assertTrue(f["title"].strip())
                self.assertTrue(f["reproduction"].strip())
                self.assertRegex(f["fix_iteration"], r"^I\d+$")

    def test_fixed_findings_name_a_test(self):
        for f in findings():
            if f["status"] != "fixed":
                continue
            with self.subTest(finding=f["id"]):
                m = re.fullmatch(r"(tests_m\d+/test_\w+\.py)::(\w+)(?:\.(\w+))?", f.get("test") or "")
                self.assertIsNotNone(m, "a fixed finding names the test that pins its fix (P6)")
                src = (ROOT / m.group(1)).read_text(encoding="utf-8")
                self.assertRegex(src, rf"\b(class|def) {m.group(3) or m.group(2)}\b")

    def test_no_open_high_finding(self):
        """The I5 exit: zero open high-severity findings before I6 starts."""
        self.assertEqual([f["id"] for f in findings() if f["severity"] == "high" and f["status"] == "open"], [])

    def test_vacuity_attack_finds_no_unsatisfiable_premise(self):
        """I5-P1."""
        self.assertEqual([f["id"] for f in findings()
                          if f["category"] == "vacuity" and f["severity"] in ("high", "medium")], [])

    def test_determinism_attack_finds_no_nondeterminism(self):
        """I5-P2."""
        self.assertEqual([f["id"] for f in findings()
                          if f["category"] == "determinism" and f["severity"] in ("high", "medium")], [])


class TestAuditStatus(unittest.TestCase):
    def test_status_summarises_findings(self):
        p = run_holon(["audit", "status", "--json"])
        self.assertEqual(p.returncode, 0, p.stdout[-1000:] + p.stderr[-1000:])
        s = json.loads(p.stdout)
        fs = findings()
        self.assertEqual(s["total"], len(fs))
        for sev in SEVERITIES:
            self.assertEqual(s["open"][sev], sum(1 for f in fs if f["severity"] == sev and f["status"] == "open"))
        self.assertEqual(s["blocking"], [])


if __name__ == "__main__":
    unittest.main()
