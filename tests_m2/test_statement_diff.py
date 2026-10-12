"""I10: statement lifecycle and prover separation (whitepaper §9.4, §9.5, L14, L22; BUILD_PLAN I10).

Every statement change goes through laws/STATEMENT_DIFF.jsonl (append-only). Entry kinds:
  reextraction    unsigned only when the changed refs come from extractor output that G1 reproduces from
                  the pinned code with the pinned extractor; a hand-written facts file never qualifies
  binding_change  an emitted def changed under a fixed statement: a checked equivalence law, or a signature
  strengthening   a kernel-checked S' => S (holon/gen/implication.py generates the obligation and its proof)
  weakening       a gpg signature from keys/ (Q3) and an auditor review; without a key, always rejected
  cross_milestone a later milestone's analogue of an earlier law: a checked S_new => S_old, or a signed
                  weakening (test_cross_milestone.py)

API these tests read:
  holon.statement_diff.check_entry(entry, root) -> {"ok": bool, "reason": str, "implication": dict | None}
      implication (strengthening, cross_milestone): {"status": "PROVED" | ..., "laws": text, "proof": text}
  holon.statement_diff.check_file(path, root) -> [problem]      every entry of a STATEMENT_DIFF.jsonl
  holon.gate.laws_in_proofs(gen_dir) -> [path]                  proof files that declare a law (G3)

Prover separation: for every milestone other than M0 and M1, `holon run` writes laws under
<gen>/laws/<law_id>/ and proofs under <gen>/proofs/<law_id>/; G3 rejects a `law` declaration under proofs/.
"""
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, copy_repo, holon_module, load_json, run_holon, write_json

FIX = ROOT / "tests_m2" / "fixtures" / "statement_diff"


def entry(name: str) -> dict:
    return load_json(FIX / name)


class TestEntryKinds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.SD = holon_module("holon.statement_diff")

    def test_unsigned_weakening_is_rejected(self):
        """I10-P1."""
        r = self.SD.check_entry(entry("weakening_unsigned.json"), ROOT)
        self.assertFalse(r["ok"], r)
        self.assertIn("signature", r["reason"])

    def test_strengthening_with_a_checked_implication_is_accepted(self):
        """I10-P2: the new statement adds a conjunct; the generated S' => S checks."""
        r = self.SD.check_entry(entry("strengthening_checked.json"), ROOT)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["implication"]["status"], "PROVED", r)
        self.assertIn("law ", r["implication"]["laws"])

    def test_mislabelled_strengthening_is_rejected(self):
        """A 'strengthening' that drops a conjunct has no checked S' => S."""
        r = self.SD.check_entry(entry("strengthening_false.json"), ROOT)
        self.assertFalse(r["ok"], r)

    def test_reextraction_backed_by_hand_written_facts_is_rejected(self):
        """I10-P3."""
        r = self.SD.check_entry(entry("reextraction_handedit.json"), ROOT)
        self.assertFalse(r["ok"], r)
        self.assertIn("hand-written", r["reason"])

    def test_committed_statement_diff_log_is_valid(self):
        p = ROOT / "laws" / "STATEMENT_DIFF.jsonl"
        self.assertTrue(p.exists())
        self.assertEqual(self.SD.check_file(p, ROOT), [])


class TestProverSeparation(unittest.TestCase):
    def test_laws_and_proofs_live_apart_and_g3_rejects_a_law_in_proofs(self):
        repo = copy_repo()
        try:
            toy = "tests_m2/fixtures/toy_queue/toy_queue.facts.json"
            sha = hashlib.sha256((repo / toy).read_bytes()).hexdigest()
            d = repo / "laws" / "T1"
            d.mkdir(parents=True)
            law = load_json(ROOT / "tests_m2" / "fixtures" / "ir03" / "L3_and_true.json")
            law["facts_sha256"] = sha
            write_json(d / "L3_and_true.json", law)
            write_json(d / "REGISTRY.json", {"milestone": "T1", "facts": toy, "facts_sha256": sha,
                                             "facts_files": {toy: sha}, "statements": {"L3_and_true": None}})
            gen = repo / "t1_gen"
            p = run_holon(["run", "--milestone", "T1", "--no-registry", "--out", str(repo / "t1_out"), "--gen-dir", str(gen)],
                          cwd=repo)
            self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
            self.assertEqual(load_json(repo / "t1_out" / "L3_and_true.json")["status"], "PROVED")
            self.assertTrue((gen / "laws" / "L3_and_true" / "LAWS.bend").exists(), sorted(str(x) for x in gen.rglob("*")))
            self.assertTrue((gen / "proofs" / "L3_and_true" / "PROOF.bend").exists())
            G = holon_module("holon.gate")
            self.assertEqual(G.laws_in_proofs(gen), [])
            bad = gen / "proofs" / "L3_and_true" / "PROOF.bend"
            bad.write_text(bad.read_text(encoding="utf-8") + "\nlaw sneaky:\n  {1n == 1n : Nat}\n", encoding="utf-8")
            self.assertTrue(G.laws_in_proofs(gen))
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
