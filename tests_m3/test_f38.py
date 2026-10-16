"""F38 (lead rulings Q39-Q41, not preregistered): G2 verifies claimed signatures itself; each gate re-checks only its own
milestone's binding_change proofs; the checker runs with a registered JavaScript stack.

  signatures  a committed line that carries a signature, or whose acceptance record claims one ("verified against
              keys/"), is verified by G2 against keys/ as the commit that appended it had it; with no key there, the
              line fails (never taken on trust), and a binding_change's equivalence re-check is skipped only for a
              signature that verifies.
  scope       on git, a committed binding_change line of a law of another milestone than the gated one gets every
              check but the re-check of its proofs, which its own milestone's G2 makes (listed in "elsewhere").
  stack       the checker's environment carries no inherited BUN_JSC_* option and the registered stack
              (config/holon.json bend.js_stack_mb); a 20000-deep expression, which overflows bun's default stack,
              gets a verdict.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests_m3._m3 import ROOT  # noqa: F401  (puts the repository on sys.path)

from holon import bend
from holon import statement_diff as SD


def head() -> str:
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


SIG = "-----BEGIN PGP SIGNATURE-----\n\nAAAA\n-----END PGP SIGNATURE-----\n"


class TestSignatureClaims(unittest.TestCase):
    def acc(self, kind, **kw):
        return {"kind": kind, "facts": {}, **kw}

    def test_a_claimed_signature_is_verified_and_fails_without_a_key(self):
        self.assertFalse((ROOT / "keys").is_dir() and any((ROOT / "keys").iterdir()), "keys/ holds no key at HEAD")
        e = {"kind": "weakening", "law_id": "L_x", "signature": SIG}
        why = SD._verify_committed(e, self.acc("weakening", signature="verified against keys/"), head(), ROOT)
        self.assertIsNotNone(why)
        self.assertIn("signature", why)

    def test_a_claim_with_no_signature_fails_and_never_skips_the_equivalence(self):
        e = {"kind": "binding_change", "law_id": "L_x", "milestone": "M3"}
        with mock.patch.object(SD, "_verify_equivalence", side_effect=AssertionError("must not be reached")):
            why = SD._verify_committed(e, self.acc("binding_change", signature="verified against keys/"), head(), ROOT)
        self.assertIsNotNone(why)
        self.assertIn("signature", why)

    def test_an_unsigned_binding_change_is_rechecked_unless_it_is_another_milestones(self):
        e = {"kind": "binding_change", "law_id": "L_x", "milestone": "M3"}
        with mock.patch.object(SD, "_verify_equivalence", return_value=None) as m:
            self.assertIsNone(SD._verify_committed(e, self.acc("binding_change"), head(), ROOT))
            self.assertEqual(m.call_count, 1)
            self.assertIsNone(SD._verify_committed(e, self.acc("binding_change"), head(), ROOT, recheck=False))
            self.assertEqual(m.call_count, 1)
        with mock.patch.object(SD, "_verify_equivalence", return_value="bend2 no longer accepts it"):
            self.assertEqual(SD._verify_committed(e, self.acc("binding_change"), head(), ROOT),
                             "bend2 no longer accepts it")


class TestG2Scope(unittest.TestCase):
    def test_another_milestones_proofs_are_not_rechecked_here(self):
        with mock.patch.object(SD, "_verify_equivalence", side_effect=AssertionError("re-checked outside its gate")):
            out = SD.scan(ROOT / SD.LOG, ROOT, milestone="M0")
        self.assertTrue(out["git"])
        self.assertEqual(out["problems"], [])
        bc = [x["line"] for x in out["entries"] if (x["entry"] or {}).get("kind") == "binding_change"]
        self.assertTrue(bc, "the log holds binding_change lines (M3's)")
        self.assertEqual(sorted(out.get("elsewhere", [])), sorted(bc))
        self.assertTrue(all(x["ok"] for x in out["entries"] if x["line"] in bc))
        self.assertIn("their own milestone's G2", out["note"])

    def test_a_line_about_no_milestones_law_is_rechecked_by_every_gate(self):
        self.assertEqual(SD._law_milestone(ROOT, "L_sort_realize_rollup_363_4a64383b"), "M3")
        self.assertIsNone(SD._law_milestone(ROOT, "L_no_such_law"))
        self.assertIsNone(SD._law_milestone(ROOT, "../M3/L_sort_realize_rollup_363_4a64383b"))


class TestCheckerStack(unittest.TestCase):
    def test_the_environment_carries_only_the_registered_stack(self):
        with mock.patch.dict(os.environ, {"BUN_JSC_useJIT": "0", "BUN_JSC_maxPerThreadStackUsage": "1"}):
            env = bend._env()
        self.assertNotIn("BUN_JSC_useJIT", env)
        self.assertEqual(env["BUN_JSC_maxPerThreadStackUsage"],
                         str(int(bend.config()["bend"]["js_stack_mb"]) * 1024 * 1024))

    def test_a_deep_file_gets_a_verdict_not_a_stack_overflow(self):
        body = "0n"
        for _ in range(20000):
            body = f"(1n + {body})"
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "deep.bend"
            p.write_text(f"def f() -> Nat:\n  {body}\n\nassert f() == f() : Nat\n")
            # bun's default (about 4 MB): the machine stack overflows, no verdict
            with mock.patch.object(bend, "js_stack_bytes", return_value=4 * 1024 * 1024):
                small = bend.check(p, timeout=240)
            self.assertTrue(bend.crashed(small), small.out[-300:])
            r = bend.check(p, timeout=240)
            self.assertFalse(bend.crashed(r), r.out[-300:])
            self.assertFalse(bend.timed_out(r))


if __name__ == "__main__":
    unittest.main()
