"""I40 round 2 (not preregistered; the lead's rulings, docs/iterations/I40.md "Round 2"): the checks the frozen
tests_m3/test_refute.py does not make.

- The solver budget is the query's rlimit counted cumulatively over its check-sats (holon.smt.run.Session).
- env_mismatch: a BMC path's real external calls are checked against the answer table (holon.refute_m3.answer_mismatch).
- final_bin on hand-built cases of F1-F4 as the contract words them.
- Every gzip-compressed query (.smt2.gz, which TestEngines' rglob("*.smt2") does not see) passes TestEngines' query
  checks: the header line, QF_AUFBV, seed 0, the sidecar's rlimit, cf = n(n-1)/2 and nz per hash function, cf_asserted
  no more than cf, no quantifier; BMC queries state their steps, time = steps and cost.
"""
from __future__ import annotations

import gzip
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "gen" / "M3" / "refute"
SIDE = json.loads((ROOT / "spec" / "M3" / "lib" / "refute.json").read_text())
ENV = json.loads((ROOT / "spec" / "M3" / "refute_env.json").read_text())


def _word(x: int) -> str:
    return "%064x" % x


class TestSessionBudget(unittest.TestCase):
    def test_the_rlimit_is_cumulative_over_the_check_sats(self):
        from holon.smt.run import Session, pin_check
        if pin_check(SIDE["solver"]):
            self.skipTest("the pinned z3 is not installed")
        base = ("(set-option :rlimit 600000)\n(set-logic QF_BV)\n(declare-const a (_ BitVec 64))\n"
                "(declare-const b (_ BitVec 64))\n(assert (bvugt a #x0000000000000001))\n(check-sat)\n")
        s = Session(SIDE["solver"], rlimit=600000, memory_mb=4096, watchdog_s=None)
        try:
            self.assertEqual(s.check(base), "sat")
            r = s.more("(assert (= (bvmul a b) #x00000000deadbeef))(assert (bvugt b #x0000000000000001))\n")
            self.assertEqual(r, "unknown")
            self.assertEqual(s.used, 600000)
            self.assertIn("cumulative", s.guard)
            self.assertEqual(s.more("(assert (bvult a #x00000000ffffffff))\n"), "unknown")
        finally:
            s.close()
        s = Session(SIDE["solver"], rlimit=5000000, memory_mb=4096, watchdog_s=None)
        try:
            self.assertEqual(s.check(base.replace("600000", "5000000")), "sat")
            u1 = s.used
            self.assertEqual(s.more("(assert (= (bvmul a b) #x00000000deadbeef))(assert (bvugt b #x0000000000000001))\n"),
                             "sat")
            self.assertGreater(s.used, u1)
            self.assertLessEqual(s.used, 5000000)
        finally:
            s.close()


class TestAnswerMismatch(unittest.TestCase):
    T = 1700000123
    ACTIVE = "0x9f8a13d7"            # ISubmitter.isActive(address)
    SLASH = "0xc96be4cb"             # ISubmitter.slash(address)
    ENQ = "0xb59b1a78"               # IL1MessageQueue.getFirstUnfinalizedMessageEnqueueTime()

    def path(self, n=1):
        return [{"action": "a", "env": {"block.timestamp": self.T}} for _ in range(n)]

    def call(self, sel, arg=None, ok=True, ret=0):
        data = sel + (_word(arg) if arg is not None else "")
        return {"to": "0x5615deb798bb3e4dfa0139dfa1b3d433cc23b72f", "data": data, "ok": ok, "ret": "0x" + _word(ret)}

    def check(self, calls, n=1):
        from holon.refute_m3 import answer_mismatch
        return answer_mismatch(ROOT, SIDE, ENV, self.path(n), calls)

    def test_agreeing_calls(self):
        self.assertIsNone(self.check([[self.call(self.ACTIVE, 0x1002, ret=1), self.call(self.ENQ, ret=self.T)]]))
        self.assertIsNone(self.check([[self.call(self.ACTIVE, 0x1005, ret=0)]]))

    def test_a_different_return_is_a_mismatch(self):
        self.assertIn("isActive", self.check([[self.call(self.ACTIVE, 0x1002, ret=0)]]) or "")
        self.assertIn("getFirstUnfinalizedMessageEnqueueTime",
                      self.check([[self.call(self.ENQ, ret=self.T + 1)]]) or "")

    def test_a_different_ok_is_a_mismatch(self):
        self.assertIn("ok=False", self.check([[self.call(self.ACTIVE, 0x1002, ok=False, ret=0)]]) or "")

    def test_the_ghost_written_by_slash_is_read_later(self):
        calls = [[self.call(self.SLASH, 0x1002, ret=0)], [self.call(self.ACTIVE, 0x1002, ret=0)]]
        self.assertIsNone(self.check(calls, 2))
        calls = [[self.call(self.SLASH, 0x1002, ret=0)], [self.call(self.ACTIVE, 0x1002, ret=1)]]
        self.assertIn("isActive", self.check(calls, 2) or "")

    def test_a_call_outside_the_table_is_the_models_free_choice(self):
        self.assertIsNone(self.check([[{"to": "0x01", "data": "0xdeadbeef", "ok": False, "ret": "0x"}]]))


class TestFinalBinCases(unittest.TestCase):
    def setUp(self):
        from holon.filter import final_bin
        self.f = final_bin

    def side(self, prov="public_schedule", status="passed", obs=True):
        return {"provenance": prov, "status": status, "obstruction_observed": obs}

    def test_f1_a_failed_side(self):
        self.assertEqual(self.f({"s": self.side(status="failed")}, {"kind": "bmc", "result": "no_path"}), "model_defect")

    def test_f2_bmc_no_path(self):
        self.assertEqual(self.f({}, {"kind": "bmc", "result": "no_path"}), "known_limitation")
        self.assertEqual(self.f({}, {"kind": "direct", "result": "no_path"}), "pending")

    def test_f3_finding(self):
        self.assertEqual(self.f({"s": self.side()}, {"kind": "direct", "result": "path"}), "finding")
        self.assertEqual(self.f({"s": self.side()}, {"kind": "go_only", "result": "path"}), "pending")
        self.assertEqual(self.f({"s": self.side(obs=False)}, {"kind": "direct", "result": "path"}), "pending")
        self.assertEqual(self.f({"s": self.side(prov="library_api")}, {"kind": "direct", "result": "path"}), "pending")
        both = {"s": self.side(), "h": self.side(prov="internal_harness", obs=False)}
        self.assertEqual(self.f(both, {"kind": "direct", "result": "path"}), "pending")
        self.assertEqual(self.f(both, {"kind": "bmc", "result": "path"}), "finding")
        other = {"s": self.side(), "g": self.side(prov="library_api", obs=False)}
        self.assertEqual(self.f(other, {"kind": "direct", "result": "path"}), "pending")

    def test_f4_otherwise(self):
        self.assertEqual(self.f({}, {"kind": "direct", "result": "path"}), "pending")
        self.assertEqual(self.f({"s": self.side()}, {"kind": "bmc", "result": "unknown"}), "pending")


class TestCompressedQueries(unittest.TestCase):
    def test_every_gzip_query_passes_the_query_checks(self):
        files = sorted(GEN.rglob("*.smt2.gz"))
        if not files:
            self.skipTest("no compressed query")
        s = SIDE["solver"]
        H = int(SIDE["bmc"]["H"])
        for f in files:
            with self.subTest(query=str(f.relative_to(ROOT))):
                text = gzip.decompress(f.read_bytes()).decode("utf-8")
                head = text.splitlines()[0]
                self.assertTrue(head.startswith("; holon-smt "), head[:80])
                meta = json.loads(head[len("; holon-smt "):])
                self.assertEqual((meta["logic"], meta["random_seed"], meta["rlimit"]),
                                 ("QF_AUFBV", 0, s["rlimit_per_query"]))
                terms, inst = meta.get("terms") or {}, meta.get("instances") or {}
                hashes = {k: v for k, v in terms.items() if k in ("keccak256", "sha256")}
                if hashes:
                    self.assertEqual(inst.get("cf"), sum(n * (n - 1) // 2 for n in hashes.values()))
                    self.assertEqual(inst.get("nz"), sum(hashes.values()))
                    self.assertLessEqual(inst.get("cf_asserted", inst.get("cf")), inst.get("cf"))
                    if inst.get("cf_asserted", inst.get("cf")) < inst.get("cf"):
                        self.assertEqual(meta.get("e1"), "lazy")
                body = re.sub(r";[^\n]*", "", text)
                self.assertIsNone(re.search(r"\((forall|exists)\b", body))
                if "/bmc/" in str(f):
                    self.assertIsInstance(meta.get("steps"), int)
                    self.assertTrue(1 <= meta["steps"] <= H)
                    self.assertEqual(inst.get("time"), meta["steps"])
                    self.assertIsInstance(inst.get("cost"), int)


if __name__ == "__main__":
    unittest.main()
