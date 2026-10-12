"""I16: metrics (whitepaper §13 "Metrics"; BUILD_PLAN I16, invariant 6).

holon/metrics.py writes a deterministic results/<M>/metrics.json. Timings, including the from-scratch
gate time, go to results/<M>/metrics_timing.json, which G1 excludes. M2 exit (a) is later read as
metrics.refinement.unexplained == 0 (I23).

CLI these tests run:
  python -m holon metrics --milestone M [--root DIR]
      writes <root>/results/<M>/metrics.json, a function of the committed records, results/<M>/gate_report.json,
      replay/<M>/report.json, results/M2/refinement/*.json, spec/M2/disagreements.json and the files
      holon.refinement.classify reads, only (re-running it rewrites the same bytes), and
      <root>/results/<M>/metrics_timing.json (its from_scratch_gate_s is the wall time the last full gate
      run recorded; the gate records it in a file G1 excludes).
  python -m holon gate --milestone M0 --checks G1 --root R --report P
      G1 regenerates metrics.json and compares it byte for byte; a difference names metrics.json in the G1
      detail. holon.gate.G1_EXCLUDED contains "metrics_timing.json".

results/<M>/metrics.json, for M in {M0, M1}:
  milestone
  laws                          {"total", "PROVED", "REFUTED", "UNKNOWN"} counted over results/<M>/L_*.json
  unknown_rate                  UNKNOWN / total
  witness_replay_rate           {"refuted": r, "replayed": k, "rate": k / r}; k = REFUTED records whose
                                replay.status is "passed"
  canary_acceptance             {"total": canaries in results/<M>/gate_report.json, "accepted": those with
                                rejected false} (§13: must be 0)
  refinement                    {"compared", "disagreements", "unexplained"}: M0 sums compared and
                                disagreements over the results/M2/refinement/*.json records whose milestone is
                                M0; M1 takes the M1 corpus (replay/M1/report.json refinement.steps and
                                n_disagreements); unexplained counts the spec/M2/disagreements.json entries of
                                that milestone whose links classify to "unexplained" (holon.refinement.classify;
                                checked against tests_m2/_i16.py::expected_class)
  refinement_disagreement_rate  refinement.disagreements / refinement.compared
  each other §13 metric (recall_per_rule, precision, certificate_coverage, unknown_calibration (the UNKNOWN
  rate's "calibration on unsolved controls"), cross_kernel_agreement, mutation_adequacy,
  prediction_accuracy): a key, or an entry of not_applicable {metric: reason}, never both
  no timing anywhere: no key, at any depth, matching seconds | time | timing | wall | duration | *_s
results/<M>/metrics_timing.json: {"from_scratch_gate_s": seconds of the last full gate run (> 0), ...}
"""
import re
import shutil
import unittest
from pathlib import Path

from tests_m2 import _i16 as H
from tests_m2._m2 import MILESTONES, ROOT, copy_repo, holon_module, load_json, records, run_holon, write_json

COMPUTED = ("laws", "unknown_rate", "witness_replay_rate", "canary_acceptance", "refinement",
            "refinement_disagreement_rate")
OTHER_S13 = ("recall_per_rule", "precision", "certificate_coverage", "unknown_calibration",
             "cross_kernel_agreement", "mutation_adequacy", "prediction_accuracy")
TIMING_KEY = re.compile(r"(seconds|time|timing|wall|duration|_s$)", re.I)


def metrics(m: str, root: Path = ROOT) -> dict:
    return load_json(root / "results" / m / "metrics.json")


def keys(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield f"{path}.{k}", k
            yield from keys(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from keys(v, f"{path}[{i}]")


class TestMetricsFiles(unittest.TestCase):
    def test_metrics_written_for_m0_and_m1(self):
        for m in MILESTONES:
            with self.subTest(milestone=m):
                doc = metrics(m)
                self.assertEqual(doc["milestone"], m)
                for k in COMPUTED:
                    self.assertIn(k, doc)

    def test_counts_follow_the_records(self):
        for m in MILESTONES:
            with self.subTest(milestone=m):
                recs, doc = records(m), metrics(m)
                st = [r["status"] for r in recs.values()]
                want = {"total": len(st), **{s: st.count(s) for s in ("PROVED", "REFUTED", "UNKNOWN")}}
                self.assertEqual(doc["laws"], want)
                self.assertAlmostEqual(doc["unknown_rate"], want["UNKNOWN"] / want["total"], places=12)
                refuted = [r for r in recs.values() if r["status"] == "REFUTED"]
                replayed = sum(1 for r in refuted if r["replay"]["status"] == "passed")
                w = doc["witness_replay_rate"]
                self.assertEqual((w["refuted"], w["replayed"]), (len(refuted), replayed))
                self.assertAlmostEqual(w["rate"], replayed / len(refuted), places=12)

    def test_canary_acceptance_follows_the_gate_report(self):
        for m in MILESTONES:
            with self.subTest(milestone=m):
                can = load_json(ROOT / "results" / m / "gate_report.json")["canaries"]
                self.assertEqual(metrics(m)["canary_acceptance"],
                                 {"total": len(can), "accepted": sum(1 for c in can if not c["rejected"])})
                self.assertEqual(metrics(m)["canary_acceptance"]["accepted"], 0)

    def test_refinement_section(self):
        entries = load_json(H.DISAGREEMENTS)["disagreements"]
        recs = [load_json(f) for f in sorted(H.REF_DIR.glob("*.json"))]
        m1 = load_json(ROOT / "replay" / "M1" / "report.json")["refinement"]
        want = {
            "M0": {"compared": sum(r["compared"] for r in recs if r["milestone"] == "M0"),
                   "disagreements": sum(r["disagreements"] for r in recs if r["milestone"] == "M0")},
            "M1": {"compared": m1["steps"], "disagreements": m1["n_disagreements"]},
        }
        for m in MILESTONES:
            with self.subTest(milestone=m):
                doc = metrics(m)
                unexplained = sum(1 for e in entries if e["milestone"] == m and H.expected_class(e, ROOT) == "unexplained")
                self.assertEqual(doc["refinement"], {**want[m], "unexplained": unexplained})
                self.assertGreater(want[m]["compared"], 0)
                self.assertAlmostEqual(doc["refinement_disagreement_rate"],
                                       want[m]["disagreements"] / want[m]["compared"], places=12)

    def test_every_section13_metric_is_reported_or_not_applicable(self):
        for m in MILESTONES:
            doc = metrics(m)
            na = doc.get("not_applicable", {})
            for k in OTHER_S13:
                with self.subTest(milestone=m, metric=k):
                    self.assertTrue((k in doc) != (k in na), f"{k}: a key or not_applicable, exactly one")
                    if k in na:
                        self.assertIsInstance(na[k], str)
                        self.assertTrue(na[k].strip())
            for k in COMPUTED:
                self.assertNotIn(k, na)

    def test_no_timings_in_metrics(self):
        for m in MILESTONES:
            with self.subTest(milestone=m):
                hits = [p for p, k in keys(metrics(m)) if TIMING_KEY.search(k)]
                self.assertEqual(hits, [])

    def test_timings_file_has_the_from_scratch_gate_time(self):
        for m in MILESTONES:
            with self.subTest(milestone=m):
                t = load_json(ROOT / "results" / m / "metrics_timing.json")
                self.assertIsInstance(t["from_scratch_gate_s"], (int, float))
                self.assertNotIsInstance(t["from_scratch_gate_s"], bool)
                self.assertGreater(t["from_scratch_gate_s"], 0)

    def test_g1_excludes_the_timings_file(self):
        self.assertIn("metrics_timing.json", holon_module("holon.gate").G1_EXCLUDED)


class TestMetricsRegeneration(unittest.TestCase):
    def test_regeneration_is_byte_identical(self):
        """Determinism: `holon metrics` in a copy (no .git) rewrites the committed bytes, twice."""
        repo = copy_repo()
        try:
            for m in MILESTONES:
                for _ in range(2):
                    p = run_holon(["metrics", "--milestone", m, "--root", str(repo)], cwd=repo)
                    self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
                    self.assertEqual((repo / "results" / m / "metrics.json").read_bytes(),
                                     (ROOT / "results" / m / "metrics.json").read_bytes(), m)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_g1_compares_metrics_and_ignores_timings(self):
        """Differential, on one copy: with only metrics_timing.json changed G1 passes; once metrics.json is
        changed too, G1 fails and names metrics.json."""
        repo = copy_repo()

        def g1(tag: str) -> dict:
            report = repo / f"gate_report_i16_{tag}.json"
            proc = run_holon(["gate", "--milestone", "M0", "--root", str(repo), "--report", str(report),
                              "--checks", "G1"], cwd=repo)
            self.assertTrue(report.exists(), proc.stdout[-2000:] + proc.stderr[-2000:])
            return load_json(report)["checks"]["G1"]
        try:
            t = repo / "results" / "M0" / "metrics_timing.json"
            write_json(t, {**load_json(t), "from_scratch_gate_s": 123456789.0})
            first = g1("timing_only")
            self.assertTrue(first["passed"], first["detail"])
            p = repo / "results" / "M0" / "metrics.json"
            doc = load_json(p)
            doc["laws"]["total"] += 100
            write_json(p, doc)
            second = g1("metrics_changed")
            self.assertFalse(second["passed"], second["detail"])
            self.assertIn("metrics.json", second["detail"])
            self.assertNotIn("metrics_timing.json", second["detail"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
