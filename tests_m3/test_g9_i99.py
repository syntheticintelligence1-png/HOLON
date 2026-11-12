"""I99: G9 checks that every result record's premises cover its law's assume clauses (audit M3/5 F-M3-19, high,
gate_evasion; BUILD_PLAN row I99; the key I99 of spec/M3/predictions.json). The instrument is tests_m3/_i99.py. It
imports nothing from holon/ or tools/. The instrument and this docstring are fixed at the prereg (C_K) and pinned by
sha256 in the key's thresholds; spec/M3/amendments/I99.jsonl records the finding as the key's origin and pins this
docstring as well.

Contract. <B> is the key's base_commit (b4664e4c, the lead after I98's landing #125), THIRTEEN the 13 M3 records the
finding names (_i99.THIRTEEN), and OUT is docs/iterations/I99/.

F  The finding. At <B>, 13 M3 result records list 0 premises while their laws assume 1 to 4 clauses (statement.assume):
   L_contract_C_o12_m3 (4), L_par_push_L1CrossDomainMessenger_proveAndRelayMessage_154 (2: a keccak256
   collision-freedom hypothesis and a leaf equality), and eight L_sort_cons_* and three L_sort_payer_* laws (1 each).
   M0, M1 and M2 have none. G9 validates records against the v1 and v2 schemas only, in holon/gate.py's g9 and in M3's
   per-family G9, so it passes them. It also passes a tree whose results/M3/L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_
   pinned.json has premises [], although that law has 12 clauses. The contract they break: the frozen
   schemas/result_record.schema.json defines premises as every assume clause of the law plus any oracle or
   cryptographic premise; M0_SPEC §6 and D2 of tests_m3/test_derivation_laws.py want one readable string per clause;
   and Appendix G defines G9 as "result records complete (§8.6)".
S  The build.
   S1 The writers, not the records. The bundle-law writer (holon.bundle.lawrun: the SORT conservation and payer laws
      and the PAR push law) and the contract-law writer (holon.sorts.contract3_run) write one readable premise per
      assume clause, hypotheses included, rendered as the M3 writers that already do so render them (holon.ir.premises;
      the codec writer gives 12 for 12). The 13 records are re-made through their generators: `holon run --milestone
      M3 --laws ...`, then `holon bundle replay-laws` for the bundle laws' witnesses. No law is edited, and no premise is
      added to a law or dropped from one.
   S2 G9, in every milestone, fails a record whose premises do not cover its law's assume clauses, one string per
      clause, and names the law in its detail. That is holon/gate.py's g9 (M0, M1, M2, and M3's other laws) and M3's
      per-family G9: the typed I30 laws, DISCH, FACT, the contract laws, the derivation law set and both bundle law sets.
      The check counts and compares: each clause's rendering must appear among the record's premises (holon.ir.premises;
      the derivation law set renders its own clauses with holon.derivation.decide.render_premise). Oracle and
      cryptographic premises may follow the clauses.
   S3 CI runs this module's build checks in a job of its own.
K  The pins hold, `holon audit prereg --milestone M3` prints PREREG OK, the instrument imports nothing from holon/ or
   tools/, and spec/M3/amendments/I99.jsonl holds one line for this module, pinning this docstring.
B  The build's checks.
   B1 At HEAD, `holon gate --milestone M3 --checks G9` passes.
   B2 On a copy of HEAD with _i99.plant_empty applied (premises [] on PLANTED_EMPTY, a PROVED record whose law has 12
      clauses), G9 on M3 fails, and its detail names the law.
   B3 On a copy of HEAD with _i99.plant_missing applied (the last premise dropped from PLANTED_MISSING, a PROVED record
      whose law has 4 clauses), G9 on M3 fails, and its detail names the law.
   B4 Each of THIRTEEN has its premises at HEAD: one per assume clause of its law, in order, each the clause's
      rendering (holon.ir.premises), and as many as the law has clauses.
   B5 The workflow (.github/workflows/holon-ci.yml) holds a job that runs this module.
P  The outcomes (OUT is written after C_K).
   P1 The 13 records gain premises: each one's premises are exactly its law's clauses rendered (L_contract_C_o12_m3 4,
      the push law 2, the others 1 each). None of the 13 has an oracle or cryptographic premise beyond its clauses.
   P2 No status moves: every M3 record's status at HEAD is its status at <B> (OUT/statuses.json).
   P3 No law hash changes: every file of laws/M0 to laws/M3 (law files and REGISTRY.json) is byte-identical at HEAD and
      at <B> (OUT/laws.json: their sha256 at <B>).
   P4 The new G9 fails on the old records: with I99's gate over <B>'s records, G9 on M3 fails and names exactly
      THIRTEEN, and G9 on M0, M1 and M2 passes (OUT/g9.json "before").
   P5 The new G9 passes on the new records: at HEAD, G9 passes on M0, M1, M2 and M3 (OUT/g9.json "after").
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m3 import _i99 as I

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / I.OUT
KEYFILE = ROOT / "spec" / "M3" / "predictions" / "I99.json"
TEST_ID = "tests_m3/test_g9_i99.py::<contract>"   # the audit wants "file::key"; this key names no test


def _th() -> dict:
    return json.loads(KEYFILE.read_text(encoding="utf-8"))["thresholds"]


def _sha(p) -> str:
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def _holon(*args, timeout=3600) -> subprocess.CompletedProcess:
    env = {**os.environ, "BEND_NO_TELEMETRY": "1"}
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, env=env, capture_output=True, text=True,
                          timeout=timeout)


def _load(rel: str):
    return json.loads((OUT / rel).read_text(encoding="utf-8"))


def _rec(law: str) -> dict:
    return json.loads((ROOT / "results" / "M3" / f"{law}.json").read_text(encoding="utf-8"))


def _i100_laws() -> set:
    """I100's twelve laws (the I100 key's thresholds), which I99 never knew (spec/M3/amendments/I99.jsonl)."""
    th = json.loads((ROOT / "spec" / "M3" / "predictions" / "I100.json").read_text(encoding="utf-8"))["thresholds"]
    return set(th["constant_read_laws"]) | set(th["record_laws"])


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
        src = (ROOT / "tests_m3" / "_i99.py").read_text(encoding="utf-8")
        self.assertFalse(re.search(r"(?m)^\s*(from|import)\s+(holon|tools)\b", src))

    def test_r3_the_amendment_line_pins_this_docstring(self):
        src = (ROOT / "spec" / "M3" / "amendments" / "I99.jsonl").read_text(encoding="utf-8")
        mine = [a for a in (json.loads(ln) for ln in src.splitlines() if ln.strip()) if a.get("test") == TEST_ID]
        self.assertEqual(len(mine), 1, mine)
        self.assertEqual(mine[0]["contract_sha256"], hashlib.sha256(__doc__.encode("utf-8")).hexdigest())
        agg = (ROOT / "spec" / "M3" / "amendments.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(sum(1 for ln in agg if ln.strip() and json.loads(ln) == mine[0]), 1)


class TestBuild(unittest.TestCase):
    def test_b1_head_passes_g9(self):
        _code, checks = I.gate(ROOT, "M3", "G9")
        passed, detail = checks["G9"]
        self.assertTrue(passed, detail)

    def _planted(self, plant) -> tuple[str, bool, str]:
        with tempfile.TemporaryDirectory() as tmp:
            w = I.copy(ROOT, Path(tmp) / "w")
            law = plant(w)
            _code, checks = I.gate(w, "M3", "G9")
            passed, detail = checks["G9"]
        return law, passed, detail

    def test_b2_planted_empty_premises_fail_g9(self):
        law, passed, detail = self._planted(I.plant_empty)
        self.assertEqual(law, I.PLANTED_EMPTY)
        self.assertEqual(I.clauses(ROOT, "M3", law), 12)
        self.assertEqual(_rec(law)["status"], "PROVED")
        self.assertFalse(passed, detail)
        self.assertIn(law, detail)

    def test_b3_a_planted_missing_clause_fails_g9(self):
        law, passed, detail = self._planted(I.plant_missing)
        self.assertEqual(law, I.PLANTED_MISSING)
        self.assertEqual(I.clauses(ROOT, "M3", law), 4)
        self.assertEqual(_rec(law)["status"], "PROVED")
        self.assertFalse(passed, detail)
        self.assertIn(law, detail)

    def test_b4_the_thirteen_have_their_premises(self):
        sys.path.insert(0, str(ROOT))
        from holon import ir
        for law, n in sorted(I.THIRTEEN.items()):
            with self.subTest(law=law):
                d = json.loads((ROOT / "laws" / "M3" / f"{law}.json").read_text(encoding="utf-8"))
                self.assertEqual(I.clauses(ROOT, "M3", law), n)
                pr = _rec(law).get("premises") or []
                self.assertEqual(len(pr), n, pr)
                self.assertEqual(pr, ir.premises(d))

    def test_b5_ci_runs_this_module(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        self.assertRegex(wf, r"python -m unittest[^\n]*tests_m3\.test_g9_i99")


class TestOutcome(unittest.TestCase):
    def test_p1_the_thirteen_gain_exactly_their_clauses(self):
        sys.path.insert(0, str(ROOT))
        from holon import ir
        for law in sorted(I.THIRTEEN):
            with self.subTest(law=law):
                d = json.loads((ROOT / "laws" / "M3" / f"{law}.json").read_text(encoding="utf-8"))
                self.assertEqual(_rec(law)["premises"], ir.premises(d))

    def test_p2_no_status_moves(self):
        s = _load("statuses.json")
        self.assertEqual(s["base"], s["head"])
        live = {p.stem: json.loads(p.read_text(encoding="utf-8")).get("status")
                for p in sorted((ROOT / "results" / "M3").glob("L*.json"))}
        # I100 (amended, spec/M3/amendments/I99.jsonl): I100 adds the records of its twelve laws
        later = _i100_laws()
        self.assertEqual({k: live.get(k) for k in s["head"]}, s["head"])
        self.assertEqual(sorted(set(live) - set(s["head"])), sorted(later))

    def test_p3_no_law_hash_changes(self):
        base = _load("laws.json")["base"]
        head = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for m in ("M0", "M1", "M2", "M3") for p in sorted((ROOT / "laws" / m).rglob("*.json"))}
        # I100 (amended, spec/M3/amendments/I99.jsonl): I100's catalog bump and its twelve laws; a changed file must
        # equal I99's base with rule_catalog_version masked (DERIVATION and REGISTRY without I100's twelve, the
        # registry without its derivation_sha256)
        later = _i100_laws()
        self.assertEqual(sorted(set(head) - set(base)), sorted(f"laws/M3/{lid}.json" for lid in later))
        self.assertEqual(sorted(set(base) - set(head)), [])

        def masked(rel: str, d: dict) -> dict:
            d = {k: v for k, v in d.items() if k != "rule_catalog_version"}
            if rel == "laws/M3/DERIVATION.json":
                d["laws"] = [e for e in d["laws"] if e.get("law_id") not in later]
            if rel == "laws/M3/REGISTRY.json":
                d.pop("derivation_sha256", None)
                d["statements"] = {k: v for k, v in d["statements"].items() if k not in later}
            return d
        for rel, sha in sorted(base.items()):
            if head[rel] == sha:
                continue
            old = subprocess.run(["git", "-C", str(ROOT), "show", f"{_th()['base_commit']}:{rel}"],
                                 capture_output=True, text=True, check=True).stdout
            self.assertEqual(masked(rel, json.loads((ROOT / rel).read_text(encoding="utf-8"))),
                             masked(rel, json.loads(old)), rel)

    def test_p4_the_new_g9_fails_on_the_old_records(self):
        b = _load("g9.json")["before"]
        self.assertFalse(b["M3"]["passed"])
        self.assertEqual(sorted(b["M3"]["named"]), sorted(I.THIRTEEN))
        for m in ("M0", "M1", "M2"):
            self.assertTrue(b[m]["passed"], m)

    def test_p5_the_new_g9_passes_on_the_new_records(self):
        a = _load("g9.json")["after"]
        for m in ("M0", "M1", "M2", "M3"):
            self.assertTrue(a[m]["passed"], (m, a[m].get("detail")))


if __name__ == "__main__":
    unittest.main()
