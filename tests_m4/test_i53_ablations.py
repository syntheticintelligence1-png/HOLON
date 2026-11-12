"""I53: ablations, UNKNOWN calibration and the §13 metrics (key I53, spec/M4/predictions.json; BUILD_PLAN §4 I53, which
closes the M4 exit; whitepaper §13 "Metrics" and "Ablations", L14, L15). This docstring is the contract that this file
checks.

Instruments fixed at the prereg, pinned by sha256 in PINNED: spec/M4/lib/I53_protocol.json (the nine switches, their
scopes per system, the rerun rule, the metric definitions and sources, the delta rule, the calibration protocol, the
sandbox), spec/M4/lib/I53_a3_prompt.md (the sandbox attackers' prompt) and tests_m4/_i53.py (every score written a
second time, independently of holon/). The test process never imports a holon module.

The tool
  python -m holon eval ablate run [--only A1,..] [--jobs N]   the ablations, in scratch copies outside the repository:
                                                             results/eval/ablations/<id>.json, results/eval/ablations.json
  python -m holon eval ablate calibrate                      the 14 controls as T48: results/eval/calibration.json and
                                                             results/eval/calibration/<control>.json (the records)
  python -m holon eval ablate metrics                        results/eval/metrics.json from the recorded sources
  python -m holon eval ablate report [--check]               docs/M4_EVAL.md and results/eval/ablations.json from the
                                                             committed outputs; --check rewrites nothing and exits 0 iff
                                                             results/eval/metrics.json and docs/M4_EVAL.md equal their
                                                             regeneration byte for byte
  Timings go to results/eval/ablations_timing.json only.

Rules
  B1 Exit. ablations.json names exactly A1-A9, each with ran true and Morph status run; every system's status is the
     protocol's (an ablation the protocol scopes to a system runs there, every other system carries the protocol's
     reason). An ablation that has not run fails this rule: the M4 exit is not met.
  B2 Scores. For every system that ran, full equals the instrument's morph_metrics of the committed records, ablated
     equals morph_metrics of the committed records after the detail's removed, overrides and added, and delta is
     ablated - full (the protocol's delta rule).
  B3 Switch reach. The lost laws of A1 are SORT laws of the typed sub-forms; of A3, PAR laws; of A4, PAR laws of the
     off sub-forms; of A5, NAT laws outside composition, naturality and slash. Every lost law exists in the committed
     laws/<M>/ and every gained law does not.
  B4 Calibration. 14 rows, the controls of spec/eval/controls.json in order, each with I48's truth, within_budget and
     expected, its outcome the status of the committed record results/eval/calibration/<id>.json, that record's law
     the control's law; the metrics are the instrument's.
  B5 Metrics. results/eval/metrics.json holds every §13 metric for morph, corpus and heldout, each a value with its
     source or missing with a reason; the morph values the instrument reads from the sources equal the file's;
     canary acceptance is 0; each baseline delta is holon - baseline.
  B6 Sandbox. A9's attempts are 12 rows (attacker, law) dealt by the protocol's rule from the committed UNKNOWN M3
     laws; weakenings accepted are the rows with checker_accepted and statement_changed; rate = accepted / 12; no
     committed path names the sandbox.
  B7 Regressions. No non-merge commit of I53's first-parent history after BASE touches an M0-M3 outcome, a frozen file,
     or a holon/ file outside holon/eval/; holon/eval/ablate*.py names no target or corpus system and imports no test
     module; no generator closure lists it; report --check passes.
"""
from __future__ import annotations

import json
import random
import re
import subprocess
import sys
import unittest
from pathlib import Path

from tests_m4 import _i53 as I
from tests_m4._m4 import file_sha256

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "spec" / "M4" / "lib" / "I53_protocol.json"
PROMPT = ROOT / "spec" / "M4" / "lib" / "I53_a3_prompt.md"
INSTRUMENT = ROOT / "tests_m4" / "_i53.py"
EVAL = ROOT / "results" / "eval"
ABL = EVAL / "ablations.json"
ABL_DIR = EVAL / "ablations"
CAL = EVAL / "calibration.json"
METRICS = EVAL / "metrics.json"
DOC = ROOT / "docs" / "M4_EVAL.md"
MAP = ROOT / "spec" / "M3" / "appendixA_map.json"
CONTROLS = ROOT / "spec" / "eval" / "controls.json"
BASE = "c81a82bfa6706745e6ef4337b3ba6b7076f32fe9"   # the merge of I52's branch into I53, before the prereg
PINNED = {
    "spec/M4/lib/I53_protocol.json": "f806599483b3a0607551f6b13eabf0acbd25fd641423000810b84d2eebd38904",
    "spec/M4/lib/I53_a3_prompt.md": "93d9f5d88f5f83222fd63a735a75f752234fa499c6c876f3a0865ba05d1dc0f3",
    "tests_m4/_i53.py": "2ffd8e5de9b93d9a7ba36a5050477b1b812bd7752a5045f1129e465e97c5af91",
}
TYPED = ("as_member", "realize", "reinterpret")
OFF_PAR = ("cross_component_codec", "branch", "weak", "cycle", "recompute", "consumer", "init", "push", "go_branch",
           "go_recompute")
NAT_KEPT = ("composition", "naturality", "slash")
PROTECTED = ("laws/", "results/M0/", "results/M1/", "results/M2/", "results/M3/", "results/T32/", "gen/M", "replay/",
             "spec/M0/", "spec/M1/", "spec/M2/", "spec/M3/", "facts/", "tests/", "tests_m1/", "tests_m2/", "tests_m3/",
             "predictions/", "schemas/", "bend/probes/", "AGENTS.md", "FROZEN.sha256", "tools/freeze.py",
             "docs/M0_SPEC.md", "docs/BEND_PRIMER.md")


def protocol() -> dict:
    return I.load(PROTOCOL)


def summary() -> dict:
    return I.load(ABL)


def detail(aid: str) -> dict:
    return I.load(ABL_DIR / f"{aid}.json")


def morph(aid: str) -> dict:
    return detail(aid)["systems"]["morph"]


def full_records() -> tuple[dict, dict]:
    md = I.load(MAP)
    return md, I.committed_statuses(ROOT, md)


def law_doc(lid: str) -> dict | None:
    for d in sorted((ROOT / "laws").iterdir()):
        p = d / f"{lid}.json"
        if p.is_file():
            return I.load(p)
    return None


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


class TestInstruments(unittest.TestCase):
    def test_instruments_pinned(self):
        for rel, sha in PINNED.items():
            self.assertEqual(file_sha256(ROOT / rel), sha, rel)

    def test_instrument_reads_the_report(self):
        """The instrument's verdicts on the committed records equal the committed map's verdict tables' counts
        (docs/M3_COMPARISON.md summary: 12 obstructions reproduced per basis, rows held 13 hand and 8 code)."""
        md, recs = full_records()
        m = I.morph_metrics(md, recs)
        self.assertEqual(m["obstructions_reproduced"], {"hand": 12, "code": 12})
        self.assertEqual(m["rows_held"], {"hand": 13, "code": 8})

    def test_scores_can_fail(self):
        """Planted removals move the instrument: dropping O15's links' laws drops both bases by one."""
        md, recs = full_records()
        r = I.apply(recs, removed=[["M1", "L_nat_eta2"], ["M2/view", "L_nat_eta2"]])
        m0, m1 = I.morph_metrics(md, recs), I.morph_metrics(md, r)
        self.assertEqual(I.delta(m1["obstructions_reproduced"]["code"], m0["obstructions_reproduced"]["code"]), -1)
        self.assertEqual(I.delta(m1["findings"], m0["findings"]), -2)
        rows = [{"within_budget": True, "truth": False, "outcome": "PROVED", "expected": "REFUTED"}]
        self.assertEqual(I.calibration(rows)["wrong_decisions"], 1)


class TestExit(unittest.TestCase):
    def test_nine_ablations_ran(self):
        s = summary()
        self.assertEqual(sorted(s["ablations"]), list(I.ABLATIONS))
        for aid in I.ABLATIONS:
            a = s["ablations"][aid]
            self.assertIs(a["ran"], True, aid)
            self.assertEqual(a["systems"]["morph"]["status"], "run", aid)

    def test_system_statuses_are_the_protocols(self):
        p, s = protocol(), summary()
        self.assertEqual(s["protocol_sha256"], file_sha256(PROTOCOL))
        for aid in I.ABLATIONS:
            for sys_ in I.SYSTEMS:
                want = p["ablations"][aid]["systems"][sys_]
                got = s["ablations"][aid]["systems"][sys_]
                self.assertEqual(got["status"], want["status"], (aid, sys_))
                if want["status"] != "run":
                    self.assertEqual(got.get("reason"), want["reason"], (aid, sys_))

    def test_generated_outputs_reproduce(self):
        self.assertTrue(DOC.is_file() and METRICS.is_file())
        p = subprocess.run([sys.executable, "-m", "holon", "eval", "ablate", "report", "--check"], cwd=ROOT,
                           capture_output=True, text=True, timeout=1800)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


class TestScoring(unittest.TestCase):
    def test_full_ablated_and_delta(self):
        md, recs = full_records()
        full = I.morph_metrics(md, recs)
        for aid in I.ABLATIONS:
            m = morph(aid)
            self.assertEqual(m["full"], full, aid)
            abl = I.morph_metrics(md, I.apply(recs, m.get("removed"), m.get("overrides"), m.get("added")))
            self.assertEqual(m["ablated"], abl, aid)
            for k in ("findings",):
                self.assertEqual(m["delta"][k], I.delta(abl[k], full[k]), aid)
            for k in ("obstructions_reproduced", "rows_held"):
                for b in I.BASES:
                    self.assertEqual(m["delta"][k][b], I.delta(abl[k][b], full[k][b]), (aid, k, b))
            self.assertEqual(summary()["ablations"][aid]["systems"]["morph"]["delta"], m["delta"], aid)

    def test_switch_reach(self):
        for aid, ok in (("A1", lambda l: l["rule"] == "SORT" and l.get("subform") in TYPED),
                        ("A3", lambda l: l["rule"] == "PAR"),
                        ("A4", lambda l: l["rule"] == "PAR" and l.get("subform") in OFF_PAR),
                        ("A5", lambda l: l["rule"] == "NAT" and l.get("subform") not in NAT_KEPT)):
            m = morph(aid)
            for ms, laws in m["laws"].items():
                for lid in laws["lost"]:
                    l = law_doc(lid)
                    self.assertIsNotNone(l, (aid, lid))
                    self.assertTrue(ok(l), (aid, lid, l.get("rule"), l.get("subform")))
                for lid in laws["gained"]:
                    self.assertFalse((ROOT / "laws" / ms / f"{lid}.json").exists(), (aid, lid))

    def test_switch_is_complete(self):
        """The switch removed everything it names: every committed M3 law of A1's typed sub-forms and of A4's off PAR
        sub-forms is lost, and A5 removes every NAT law outside the kept sub-forms from every record set."""
        m3 = [I.load(p) for p in sorted((ROOT / "laws" / "M3").glob("L_*.json"))]
        for aid, ok in (("A1", lambda l: l["rule"] == "SORT" and l.get("subform") in TYPED),
                        ("A4", lambda l: l["rule"] == "PAR" and l.get("subform") in OFF_PAR)):
            want = sorted(l["law_id"] for l in m3 if ok(l))
            self.assertEqual(sorted(morph(aid)["laws"]["M3"]["lost"]), want, aid)
        md, recs = full_records()
        nat = sorted([s, lid] for s, laws in recs.items() for lid in laws
                     if (law_doc(lid) or {}).get("rule") == "NAT" and (law_doc(lid) or {}).get("subform") not in NAT_KEPT
                     and s != "M3")
        self.assertEqual(sorted(morph("A5")["removed"]), nat)

    def test_removed_are_lost(self):
        """Every removed [set, law] link is a lost law of a milestone the ablation reran (or A5's selection)."""
        for aid in I.ABLATIONS:
            m = morph(aid)
            lost = {lid for laws in m["laws"].values() for lid in laws["lost"]}
            for _s, lid in m.get("removed") or []:
                self.assertIn(lid, lost, aid)


class TestCalibration(unittest.TestCase):
    def test_rows_are_the_controls(self):
        c, ctl = I.load(CAL), I.load(CONTROLS)["controls"]
        self.assertEqual([r["id"] for r in c["rows"]], [x["id"] for x in ctl])
        for r, x in zip(c["rows"], ctl):
            for k in ("family", "size", "truth", "within_budget", "expected"):
                self.assertEqual(r[k], x[k], (x["id"], k))
            rec = I.load(EVAL / "calibration" / f"{x['id']}.json")
            self.assertEqual(rec["law_id"], x["law_id"])
            self.assertEqual(r["outcome"], rec["status"], x["id"])
            self.assertEqual(rec["statement_hash"], r["statement_hash"])
            self.assertEqual(r["bound"], I.bound_of(rec), x["id"])

    def test_metrics(self):
        c = I.load(CAL)
        self.assertEqual(c["metrics"], I.calibration(c["rows"]))


class TestMetrics(unittest.TestCase):
    def test_every_metric(self):
        m = I.load(METRICS)
        for sys_ in I.SYSTEMS:
            for k in I.METRICS:
                e = m["systems"][sys_][k]
                self.assertTrue(("value" in e and e.get("source")) or e.get("missing"), (sys_, k, e))

    def test_morph_values_are_the_sources(self):
        m, src = I.load(METRICS)["systems"]["morph"], I.sources(ROOT)
        for k in ("witness_replay_rate", "canary_acceptance", "unknown_rate", "refinement_disagreement_rate",
                  "cross_kernel_agreement", "mutation_adequacy", "from_scratch_gate_time"):
            self.assertEqual(m[k]["value"], src[k], k)
        self.assertEqual(m["canary_acceptance"]["value"]["accepted"], 0)
        md, recs = full_records()
        full = I.morph_metrics(md, recs)
        self.assertEqual(m["recall_per_rule"]["value"], full["recall_per_rule"])
        self.assertEqual(m["precision"]["value"], full["precision"])

    def test_baseline_deltas(self):
        m = I.load(METRICS)
        for row in m.get("baseline_deltas") or []:
            self.assertEqual(row["delta"], I.delta(row["holon"], row["baseline"]), row)


class TestSandbox(unittest.TestCase):
    def test_attempts(self):
        a9 = morph("A9")["extra"]
        ids = sorted(json.loads(p.read_text())["law_id"] for p in (ROOT / "results" / "M3").glob("L_*.json")
                     if json.loads(p.read_text()).get("status") == "UNKNOWN")
        pick = random.Random(53).sample(ids, 12)
        rows = a9["attempts"]
        self.assertEqual([(r["attacker"], r["law"]) for r in rows], [(k // 4, pick[k]) for k in range(12)])
        acc = [r for r in rows if r["checker_accepted"] and r["statement_changed"]]
        self.assertEqual([r["weakening_accepted"] for r in rows],
                         [bool(r["checker_accepted"] and r["statement_changed"]) for r in rows])
        self.assertEqual(a9["weakenings_accepted"], len(acc))
        self.assertEqual(a9["rate"], len(acc) / 12)

    def test_nothing_of_the_sandbox_is_committed(self):
        for p in (ABL, ABL_DIR / "A9.json"):
            self.assertNotIn("/tmp/", p.read_text())


class TestPredictions(unittest.TestCase):
    def test_p1_no_sort_types(self):
        m = morph("A1")
        self.assertEqual(len(m["laws"]["M3"]["lost"]), 3)
        self.assertEqual(len(m["laws"]["M3"]["gained"]), 0)
        self.assertEqual(m["delta"]["findings"], -1)
        self.assertEqual(m["delta"]["obstructions_reproduced"]["code"], 0)
        self.assertEqual(m["delta"]["rows_held"]["code"], 0)
        self.assertEqual(detail("A1")["systems"]["corpus"]["extra"]["laws"], 0)

    def test_p2_no_writer_provenance(self):
        m = morph("A2")
        m3 = m["laws"]["M3"]
        self.assertEqual(len(m3["lost"]) + len(m3["changed"]) + len(m3["gained"]), 0)
        m2 = m["laws"]["M2"]
        self.assertGreaterEqual(len(m2["lost"]) + len(m2["changed"]), 1)
        self.assertEqual(m["delta"]["obstructions_reproduced"]["code"], 0)
        h = detail("A2")["systems"]["heldout"]["extra"]
        self.assertIs(h["refused"], True)
        self.assertEqual(h["message"], h["sealed_message"])

    def test_p3_no_evidence_calculus(self):
        m = morph("A3")
        lost = m["laws"]["M3"]["lost"]
        self.assertTrue(70 <= len(lost) <= 90, len(lost))
        refuted = [l for l in lost if (ROOT / "results" / "M3" / f"{l}.json").is_file()
                   and I.load(ROOT / "results" / "M3" / f"{l}.json")["status"] == "REFUTED"]
        self.assertGreaterEqual(len(refuted), 2)
        changed = [l for ms in m["laws"].values() for l in ms["changed"] + ms["lost"]]
        self.assertEqual([l for l in changed if law_doc(l)["rule"] != "PAR"], [])
        self.assertEqual(m["delta"]["rows_held"]["code"], -2)
        self.assertEqual(m["delta"]["obstructions_reproduced"]["code"], 0)
        self.assertLessEqual(I.delta(m["ablated"]["precision"]["intended_asymmetry"],
                                     m["full"]["precision"]["intended_asymmetry"]), -1)

    def test_p4_two_cycles(self):
        m = morph("A4")
        lost = m["laws"]["M3"]["lost"]
        self.assertEqual(len(lost), 15)
        refuted = [l for l in lost if I.load(ROOT / "results" / "M3" / f"{l}.json")["status"] == "REFUTED"]
        self.assertEqual(len(refuted), 7)
        self.assertEqual(len(m["laws"]["M3"]["gained"]), 0)
        self.assertEqual(m["delta"]["rows_held"]["code"], -2)
        self.assertEqual(m["delta"]["obstructions_reproduced"]["code"], 0)

    def test_p5_no_native_equivalence(self):
        m = morph("A5")
        self.assertEqual(m["delta"]["obstructions_reproduced"], {"hand": -1, "code": -1})
        md, recs = full_records()
        v0 = I.verdicts(md, recs)
        v1 = I.verdicts(md, I.apply(recs, m.get("removed"), m.get("overrides"), m.get("added")))
        self.assertEqual(sorted(i for i in v0 if i.startswith("O") and v0[i] != v1[i]), ["O15"])
        self.assertEqual(sorted(i for i in v0 if i.startswith("R") and v0[i] != v1[i]), [])
        self.assertEqual(m["delta"]["findings"], -2)

    def test_p6_no_enablement(self):
        m = morph("A6")
        x = m["extra"]
        self.assertEqual(x["dead_after"], 0)
        self.assertGreaterEqual(len(m["laws"]["M3"]["changed"]) + len(m["laws"]["M3"]["gained"]), 1)
        self.assertEqual(m["delta"]["obstructions_reproduced"]["code"], 0)
        self.assertGreaterEqual(x["disch_status_changed"], 1)

    def test_p7_no_replay(self):
        m = morph("A7")
        x = m["extra"]
        self.assertEqual(x["finding_bin"]["ablated"], 0)
        self.assertGreater(x["finding_bin"]["full"], 0)
        self.assertIsNone(x["witness_replay_rate"]["ablated"])
        self.assertEqual(x["refinement_compared"]["ablated"], 0)
        self.assertEqual(m["delta"]["obstructions_reproduced"]["code"], 0)
        self.assertEqual(m["delta"]["rows_held"]["code"], 0)
        self.assertLessEqual(x["mutation_detection"]["ablated"], x["mutation_detection"]["full"])

    def test_p8_single_kernel(self):
        x = morph("A8")["extra"]
        self.assertEqual(x["surfaced"], {"dual": 2, "single": 0})
        self.assertEqual(x["second_kernel_records"]["ablated"], 0)

    def test_p9_no_frozen_statements(self):
        x = morph("A9")["extra"]
        self.assertEqual(len(x["attempts"]), 12)
        self.assertGreaterEqual(x["weakenings_accepted"], 1)
        acc = [r for r in x["attempts"] if r["weakening_accepted"]]
        self.assertTrue(all(r["a3_flagged"] for r in acc))
        self.assertEqual(sum(1 for r in acc if r["accepted_with_freezing"]), 0)

    def test_p10_calibration(self):
        c = I.load(CAL)["metrics"]
        self.assertEqual(c["wrong_decisions"], 0)
        self.assertEqual(c["decided_within_budget"], 1.0)
        self.assertGreaterEqual(c["unknown_beyond_budget_count"], 7)
        self.assertEqual(c["unknown_with_bound"], 1.0)

    def test_p11_morph_recall_beats_baselines(self):
        rows = [r for r in I.load(METRICS).get("baseline_deltas") or []
                if r["system"] == "morph" and r["metric"] == "obstructions_detected" and r.get("run_targets")]
        self.assertTrue(rows, "no Morph baseline ran: the prediction is not tested")
        for r in rows:
            self.assertGreater(r["delta"], 0, r)


class TestRegressions(unittest.TestCase):
    def test_no_m0_m3_outcome_changed(self):
        commits = git("rev-list", "--first-parent", "--no-merges", f"{BASE}..HEAD").split()
        for c in commits:
            for f in git("diff-tree", "--no-commit-id", "--name-only", "-r", c).split():
                self.assertFalse(f.startswith(PROTECTED), (c[:12], f))
                if f.startswith("holon/"):
                    self.assertTrue(f.startswith("holon/eval/"), (c[:12], f))

    def test_runner_is_target_agnostic(self):
        names = ("morph", "scroll", "arbitrum", "compound", "cosmos", "go-ethereum", "optimism", "wormhole", "nitro")
        for p in sorted((ROOT / "holon" / "eval").glob("ablate*.py")):
            text = p.read_text().lower()
            for n in names:
                self.assertIsNone(re.search(r"\b" + re.escape(n) + r"\b", text), (p.name, n))
            self.assertNotIn("tests_m", text)
            self.assertNotIn("tests.reference", text)

    def test_not_in_a_generator_closure(self):
        """No holon-ir generator closure (holon.records.generator_files, run in a child process) lists an ablate
        module, so every M0-M3 record keeps its generator digest."""
        code = ("import json,sys; from pathlib import Path; import holon.records as R; "
                "print(json.dumps(sorted(set().union(*[set(R.generator_files(v, Path(sys.argv[1]))) "
                "for v in ('holon-ir/0.1','holon-ir/0.2','holon-ir/0.3')]))))")
        p = subprocess.run([sys.executable, "-c", code, str(ROOT)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        self.assertEqual([f for f in json.loads(p.stdout) if f.startswith("holon/eval/ablate")], [])


if __name__ == "__main__":
    unittest.main()
