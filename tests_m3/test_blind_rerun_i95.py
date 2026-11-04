"""I95 (= I46b): moving I46's E2 with the lead's rulings (BUILD_PLAN row I95; the key I95 of spec/M3/predictions.json).
The protocol is spec/M3/lib/blind_rerun_i95.json and the instrument is tests_m3/_i95.py, which imports nothing from
holon/ or tools/ and reuses I82's and I46's instruments (tests_m3/_i82.py, tests_m3/_i46.py). The amended reads
scorer is tests_m3/_i46_reads.py. Both instruments, the protocol, I46's scope tools and this docstring are fixed at
the prereg (C_K) and pinned by sha256 in the key's thresholds.

Contract. <P> is the pack commit (_i95.pack_commit: the lead at the commit that lands I95), and OUT is
audit/blind/I95/.

K  The pins hold, `holon audit prereg --milestone M3` prints PREREG OK, and the instrument imports nothing from holon/
   or tools/.
B  Stage 1's build (the lead lands it before the pack is cut):
   B1  `python -m holon binding --milestone M3 --check` exits 0: a fresh forge run of the deployment, with no cache,
       reproduces the committed record gen/M3/binding/<stem>.json for every typed document of
       spec/M3/lib/sort_types.json.
   B2  The binding spec spec/M3/lib/binding.json holds configuration only: the keys harness, project, target and init,
       plus binding_version and doc. Its init is a literal list. It has no storage, calls or code member, and the
       scope's strip rules strip nothing from it.
   B3  The brief spec/M3/lib/blind_session_i95.md holds no outcome (no status word, no law id of the lead's tree, no
       leak-class match). It names `python -m holon binding --milestone M3` and `python -m holon coverage
       --milestone M3`, and it states every key and value of spec/M3/lib/disch.json's search section.
   B4  No lead M3 record at the base carries DISCH's clock-atom refusal ("a clock atom of B has a form the route does
       not know"). The route's extension is additive.
P  Stage 2's run (OUT is written after the landing). OUT/session/run.json is {"W", "pack", "scope", "pack_commit",
   "family", "transcript_sha256", "tool_calls"}, with family "same". OUT/session/tool_calls.jsonl is the session's
   tool calls (_i46.tool_calls). OUT/lead and OUT/tree are the projections, OUT/compare.json is `holon compare
   --blind` over M3, and OUT/binding.json is _i95.binding_rows of the blind tree. The predictions are the key's
   I95-P1..P7; each test below checks one of them against these files and the thresholds.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from tests_m3 import _i46 as I46
from tests_m3 import _i46_reads as R
from tests_m3 import _i95 as I

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / I.OUT
KEYFILE = ROOT / "spec" / "M3" / "predictions" / "I95.json"


def _key() -> dict:
    return json.loads(KEYFILE.read_text(encoding="utf-8"))


def _th() -> dict:
    return _key()["thresholds"]


def _sha(p) -> str:
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def _holon(*args, timeout=3600) -> subprocess.CompletedProcess:
    env = {**os.environ, "BEND_NO_TELEMETRY": "1"}
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, env=env, capture_output=True, text=True,
                          timeout=timeout)


def _load(rel: str):
    return json.loads((OUT / rel).read_text(encoding="utf-8"))


class TestPrereg(unittest.TestCase):
    def test_r0_the_prereg_pins_hold(self):
        th = _th()
        self.assertEqual(hashlib.sha256(__doc__.encode("utf-8")).hexdigest(), th["contract_docstring_sha256"])
        for name, pin in th["pins"].items():
            self.assertEqual(_sha(pin["path"]), pin["sha256"], name)

    def test_r1_the_prereg_audit_passes(self):
        r = _holon("audit", "prereg", "--milestone", "M3", timeout=900)
        self.assertIn("PREREG OK", r.stdout + r.stderr)

    def test_r2_the_instrument_imports_nothing_from_holon_or_tools(self):
        src = (ROOT / "tests_m3" / "_i95.py").read_text(encoding="utf-8")
        self.assertFalse(re.search(r"(?m)^\s*(from|import)\s+(holon|tools)\b", src))


class TestBuild(unittest.TestCase):
    def test_r3_b1_the_binding_step_reproduces(self):
        r = _holon("binding", "--milestone", "M3", "--check")
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-2000:])

    def test_r4_b2_the_binding_spec_is_configuration(self):
        spec = json.loads((ROOT / "spec" / "M3" / "lib" / "binding.json").read_text(encoding="utf-8"))
        self.assertEqual(set(spec) - {"binding_version", "doc"}, {"harness", "project", "target", "init"})
        # amended after C_K (spec/M3/amendments/I95.jsonl): the lead's condition reads the parameters from the pack's
        # copy of the M1 facts' initial members ({"facts", "keys"}), never from a literal list; the copy holds facts
        init = spec["init"]
        self.assertEqual(set(init), {"facts", "keys"})
        copy = json.loads((ROOT / init["facts"]).read_text(encoding="utf-8"))
        self.assertEqual(set(copy) - {"facts_copy_version", "doc"}, {"copy_of", "copy_of_sha256", "initial"})
        self.assertEqual(set(copy["initial"]), {k.split(".")[0] for k in init["keys"]})
        sys.path.insert(0, str(ROOT / "tests_m3"))
        import blind_scope as S
        sc = json.loads((ROOT / "spec" / "M3" / "lib" / "blind_rerun.json").read_text(encoding="utf-8"))["scope"]
        _, removed = S.strip(spec, re.compile(sc["strip_key_pattern"]), re.compile(sc["strip_hash_pattern"]),
                             S.leak_patterns(ROOT, "HEAD"))
        self.assertEqual(removed, [])

    def test_r5_b3_the_brief(self):
        text = (ROOT / "spec" / "M3" / "lib" / "blind_session_i95.md").read_text(encoding="utf-8")
        self.assertFalse(I46.STATUS_WORDS.search(text))
        ids = {p.stem for p in (ROOT / "laws" / "M3").glob("L*.json")}
        self.assertFalse([w for w in re.findall(r"\bL_[A-Za-z0-9_]+", text) if w in ids])
        self.assertIn("python -m holon binding --milestone M3", text)
        self.assertIn("python -m holon coverage --milestone M3", text)
        search = json.loads((ROOT / "spec" / "M3" / "lib" / "disch.json").read_text(encoding="utf-8"))["search"]
        for k, v in search.items():
            self.assertRegex(text, rf"`?{re.escape(k)}`?\D+{re.escape(str(v))}\b", k)

    def test_r6_b4_no_lead_record_carries_the_clock_atom_refusal(self):
        hit = [p.name for p in (ROOT / "results" / "M3").glob("L_disch_*.json")
               if "a clock atom of B has a form the route does not know" in p.read_text(encoding="utf-8")]
        self.assertEqual(hit, [])


class TestRun(unittest.TestCase):
    def _p(self) -> str:
        return _load("session/run.json")["pack_commit"]

    def _cmp(self) -> dict:
        return _load("compare.json")

    def test_p1_the_binding_row(self):
        rows = _load("binding.json")
        self.assertTrue(rows)
        self.assertTrue(all(r["equal"] for r in rows), rows)

    def test_p2_the_reads_check_under_both_scorers(self):
        run = _load("session/run.json")
        calls = [json.loads(l) for l in (OUT / "session" / "tool_calls.jsonl").read_text().splitlines() if l]
        self.assertEqual(len(calls), run["tool_calls"])
        self.assertTrue(I46.calls_problems(calls, run))
        self.assertEqual(R.reads_problems(calls, run), [])

    def test_p3_matched_classes(self):
        cmp, th = self._cmp(), _th()
        self.assertGreaterEqual(cmp["milestones"]["M3"]["matched"], th["matched_m3_min"])
        for m in ("M0", "M1", "M2"):
            self.assertEqual((cmp["milestones"].get(m) or {"matched": 0})["matched"], 0, m)

    def test_p4_agreement_per_rule_and_overall(self):
        cmp, th = self._cmp(), _th()
        pr = I.per_rule(OUT / "lead", OUT / "tree", cmp)
        for rule, lo in th["per_rule_min"].items():
            c = pr.get(rule, {"matched": 0, "agree": 0})
            self.assertGreater(c["matched"], 0, rule)
            self.assertGreaterEqual(c["agree"] / c["matched"], lo, rule)
        self.assertGreaterEqual(cmp["milestones"]["M3"]["blind_agreement"], th["overall_min"])
        self.assertEqual(I.flips(cmp), [])

    def test_p5_the_named_laws(self):
        th = _th()
        i46 = ROOT / "audit" / "blind" / "I46"
        c = I.carried(i46 / "lead", i46 / "run2" / "tree",
                      json.loads((i46 / "run2" / "compare.json").read_text()), OUT / "lead", OUT / "tree", self._cmp())
        self.assertEqual(c["i46_disagreements"], len(th["i46_disagreements"]))
        self.assertGreaterEqual(c["now_agree"], th["now_agree_min"])
        self.assertGreaterEqual(c["kept"], th["kept_min"])

    def test_p6_the_route_moves_no_lead_disch_status(self):
        p, base = self._p(), _th()["base_commit"]
        moved = []
        for lid in sorted(p_.stem for p_ in (ROOT / "laws" / "M3").glob("L_disch_*.json")):
            a = subprocess.run(["git", "-C", str(ROOT), "show", f"{base}:results/M3/{lid}.json"], capture_output=True)
            b = subprocess.run(["git", "-C", str(ROOT), "show", f"{p}:results/M3/{lid}.json"], capture_output=True)
            if a.returncode == 0 and b.returncode == 0 and \
                    json.loads(a.stdout)["status"] != json.loads(b.stdout)["status"]:
                moved.append(lid)
        self.assertEqual(moved, [])

    def test_p7_the_exit(self):
        run = _load("session/run.json")
        calls = [json.loads(l) for l in (OUT / "session" / "tool_calls.jsonl").read_text().splitlines() if l]
        rep = _holon("report", "--milestone", "M3", "--check", timeout=900)
        e = I.exit_clauses(ROOT, self._p(), self._cmp(), not I46.calls_problems(calls, run),
                           not R.reads_problems(calls, run), "REPORT OK" in rep.stdout)
        self.assertEqual(e, _th()["exit_predicted"])


if __name__ == "__main__":
    unittest.main()
