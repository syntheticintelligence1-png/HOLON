"""I58's contract: the M5 report (key I58; docs/BUILD_PLAN.md §4 I58, "Closes the M5 exit").

Outputs, written by `python -m holon m5 report [--root DIR] [--check]` (holon/m5/report.py):

  results/M5/metrics.json   holon.metrics' document for M5 (`python -m holon metrics --milestone M5` writes the same
                            bytes, so a landing's regen keeps it) with three more top-level keys, "L6", "L9" and "L10",
                            and "m5_report" (what was read and how). Each metric block holds:
                              value         the metric's document as I54's stub (holon.m5.metrics) computes it from
                                            the committed records (L6 through I56's V9 wrapper)
                              overall       value.overall; thresholds: value.thresholds
                              labels        {measure: measured | insufficient_n | not_measured} for each proportion
                              pins          [{role, path, sha256, key, field}]: each truth file the metric reads, with
                                            its sha256, equal to the measuring key's pin
                              pin_sets      [{role, key, files: {path: sha256}}]
                              corpus_truth_sha256   the corpus-truth file's sha256 the metric pins, or null (L9)
                              agrees_with   {path, equal: true}: the measuring iteration's committed output
                            L10 also holds corpus_recall (I55b) and trivially_true (I55, beside coverage)
  docs/M5_REPORT.md         generated from the same document and spec/M5/lib/I58_report.json

Rules:
  M1  metrics.json holds L6, L9 and L10, and equals holon.metrics.render(holon.metrics.compute("M5")).
  M2  Never rounded up: each overall equals common.overall of its thresholds; a threshold whose label is not
      measured is never meets; a metric reported as meeting needs every threshold meets.
  M3  Pins: every pin's sha256 equals the file's and the key's pin; L6 and L10 name the corpus-truth sha256; L9 none.
  M4  No pooling: L10 carries no pooled precision; L6's controls and corpus are separate blocks.
  G1  `python -m holon m5 report --check` prints CHECK OK, and two renders are byte-identical.
  G2  The report prints each metric's overall and each threshold verdict exactly as metrics.json holds them, every
      prediction of every M5 key with the outcome its iteration report records, every condition and limitation of the
      sidecar, and the corpus-truth sha256.
  A1  Adversarial: the generator refuses (holon.m5.report.ReportError) a document whose overall is rounded up, a
      threshold judged on an unmeasured measure, a truth file off its pin, and a failing evidence check.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m5 import _i54, _i58
from tests_m5._m5 import ROOT, holon_module, predictions

METRICS = ROOT / "results" / "M5" / "metrics.json"
REPORT = ROOT / "docs" / "M5_REPORT.md"
SIDECAR = ROOT / "spec" / "M5" / "lib" / "I58_report.json"
NAMES = ("L6", "L9", "L10")


def _doc() -> dict:
    return json.loads(METRICS.read_text(encoding="utf-8"))


def _run(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, BEND_NO_TELEMETRY="1")
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, capture_output=True, text=True, env=env)


def _shared(ref: dict, got: dict, path: str = "") -> list[str]:
    """Differences on every field ref holds (a reference may omit a field holon adds, never the reverse)."""
    out = []
    if isinstance(ref, dict):
        if not isinstance(got, dict):
            return [f"{path}: {got!r} is not an object"]
        for k in sorted(ref):
            if k == "reason":     # the not_measured reason's wording is the implementation's
                continue
            if k not in got:
                out.append(f"{path}/{k}: missing")
            else:
                out += _shared(ref[k], got[k], f"{path}/{k}")
        return out
    return [] if ref == got else [f"{path}: reference {ref!r}, reported {got!r}"]


class TestMetrics(unittest.TestCase):
    def test_m1_metrics_file(self):
        doc = _doc()
        for n in NAMES:
            self.assertIn(n, doc)
            for f in ("value", "overall", "thresholds", "labels", "pins", "pin_sets", "corpus_truth_sha256",
                      "agrees_with"):
                self.assertIn(f, doc[n], f"{n}.{f}")
        M = holon_module("holon.metrics")
        self.assertEqual(M.render(M.compute("M5", ROOT)), METRICS.read_text(encoding="utf-8"))

    def test_m2_never_rounded_up(self):
        common = holon_module("holon.m5.common")
        doc = _doc()
        for n in NAMES:
            b = doc[n]
            self.assertEqual(b["overall"], b["value"]["overall"])
            self.assertEqual(b["thresholds"], b["value"]["thresholds"])
            self.assertEqual(b["overall"], common.overall(b["thresholds"]), n)
            if b["overall"] == "meets":
                self.assertEqual(set(b["thresholds"].values()), {"meets"})
            for m, lab in b["labels"].items():
                if lab != "measured" and m in b["thresholds"]:
                    self.assertNotIn(b["thresholds"][m], ("meets", "misses"), f"{n}.{m} judged while {lab}")
        self.assertEqual(doc["L10"]["corpus_recall"]["label"], "insufficient_n")

    def test_m3_pins(self):
        doc = _doc()
        for n in NAMES:
            for p in doc[n]["pins"]:
                self.assertEqual(p["sha256"], _i58.sha(ROOT / p["path"]), p["path"])
                k = predictions(p["key"])
                v = k
                for t in p["field"].strip("/").split("/"):
                    v = v[t.replace("~1", "/").replace("~0", "~")]
                self.assertEqual(p["sha256"], v, f"{n} {p['path']}: not the {p['key']} pin")
            for s in doc[n]["pin_sets"]:
                self.assertTrue(s["files"])
                for rel, h in s["files"].items():
                    self.assertEqual(h, _i58.sha(ROOT / rel), rel)
        truth = _i58.sha(ROOT / "spec/M5/truth/corpus.json")
        self.assertEqual(doc["L6"]["corpus_truth_sha256"], truth)
        self.assertEqual(doc["L10"]["corpus_truth_sha256"], truth)
        self.assertIsNone(doc["L9"]["corpus_truth_sha256"])

    def test_m4_no_pooling(self):
        doc = _doc()
        self.assertNotIn("pooled_precision", json.dumps(doc["L10"]))
        self.assertIn("controls", doc["L6"]["value"])
        self.assertIn("corpus", doc["L6"]["value"])
        self.assertNotEqual(doc["L6"]["value"]["controls"].get("items"), None)


class TestReport(unittest.TestCase):
    def test_g1_regenerates(self):
        r = _run("m5", "report", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CHECK OK", r.stdout)
        R = holon_module("holon.m5.report")
        self.assertEqual(R.render(ROOT), R.render(ROOT))
        self.assertEqual(R.render(ROOT), REPORT.read_text(encoding="utf-8"))

    def test_g2_report_contents(self):
        text = REPORT.read_text(encoding="utf-8")
        doc = _doc()
        for n in NAMES:
            self.assertRegex(text, rf"\| {n} \|[^\n]*\| {doc[n]['overall']} \|")
            for t, v in doc[n]["thresholds"].items():
                self.assertRegex(text, rf"\| {n} \| `{re.escape(t)}` \|[^\n]*\| {v} \|", f"{n}.{t}")
        self.assertIn(_i58.sha(ROOT / "spec/M5/truth/corpus.json"), text)
        for k in _i58.KEYS:
            for pid, o in _i58.outcomes(ROOT, k).items():
                self.assertRegex(text, rf"\| {re.escape(pid)} \|[^\n]*\| {o['result']} \|", pid)
            for p in predictions(k)["predictions"]:
                self.assertIn(f"| {p['id']} |", text, p["id"])
        side = json.loads(SIDECAR.read_text(encoding="utf-8"))
        for c in side["conditions"] + side["limitations"]:
            self.assertIn(f"**{c['id']}.**", text)


class TestAdversarial(unittest.TestCase):
    def test_a1_refuses_rounding_up(self):
        R = holon_module("holon.m5.report")
        block = R.metrics_block(ROOT)
        self.assertEqual(R.validate(block), [])
        bad = copy.deepcopy(block)
        bad["L10"]["overall"] = "meets"
        self.assertTrue(R.validate(bad))
        bad = copy.deepcopy(block)
        bad["L9"]["value"]["thresholds"]["coverage"] = "meets"
        bad["L9"]["thresholds"]["coverage"] = "meets"
        self.assertTrue(R.validate(bad))
        bad = copy.deepcopy(block)      # judged on an insufficient measure
        bad["L10"]["labels"]["control_recall"] = "insufficient_n"
        self.assertTrue(R.validate(bad))
        bad = copy.deepcopy(block)      # an unmeasured measure reported as met
        bad["L6"]["thresholds"]["corpus_decided_accuracy"] = "meets"
        bad["L6"]["value"]["thresholds"]["corpus_decided_accuracy"] = "meets"
        self.assertTrue(R.validate(bad))
        bad = copy.deepcopy(block)
        bad["L10"]["corpus_recall"]["label"] = "measured"
        self.assertTrue(R.validate(bad))

    def _tree(self, tmp: Path) -> Path:
        for p in ROOT.iterdir():
            if p.name not in ("spec", "results", ".git"):
                (tmp / p.name).symlink_to(p, target_is_directory=p.is_dir())
        for top in ("spec", "results"):
            shutil.copytree(ROOT / top, tmp / top, symlinks=True)
        return tmp

    def test_a1_refuses_off_pin_truth_and_failed_evidence(self):
        R = holon_module("holon.m5.report")
        with tempfile.TemporaryDirectory(prefix="holon-i58-") as t:
            root = self._tree(Path(t))
            p = root / "spec/M5/truth/corpus.json"
            d = json.loads(p.read_text(encoding="utf-8"))
            d["entries"]["c17"]["l10"] = "no"
            p.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaises(R.ReportError):
                R.metrics_block(root)
        with tempfile.TemporaryDirectory(prefix="holon-i58-") as t:
            root = self._tree(Path(t))
            p = root / "results/M5/games/v9.json"
            d = json.loads(p.read_text(encoding="utf-8"))
            d["holds"] = False
            p.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaises(R.ReportError):
                R.render(root)
        with tempfile.TemporaryDirectory(prefix="holon-i58-") as t:   # a game record forged to rational
            root = self._tree(Path(t))
            p = sorted((root / "results/M5/games/records").glob("L_*.json"))[0]
            d = json.loads(p.read_text(encoding="utf-8"))
            d["verdict"] = "rational"
            p.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            try:
                block = R.metrics_block(root)
            except R.ReportError:
                block = None
            if block is not None:
                self.assertEqual(block["L6"]["value"]["decided"]["numerator"], 0)


class TestAdversarialBuild(unittest.TestCase):
    """Probes added after the prereg (the adversarial phase on the build): each must be refused."""

    _tree = TestAdversarial._tree

    def _refused(self, edit) -> str:
        R = holon_module("holon.m5.report")
        with tempfile.TemporaryDirectory(prefix="holon-i58-") as t:
            root = self._tree(Path(t))
            edit(root)
            with self.assertRaises(R.ReportError) as cm:
                R.metrics_block(root)
            return str(cm.exception)

    def test_a2_forged_game_record_with_its_output_regenerated(self):
        """A target record forged to rational (V1-V8 still pass) with I56b's output regenerated to match: the record's
        class verdicts are not the vector its committed Bend module states, so the report refuses."""
        def edit(root):
            p = sorted((root / "results/M5/games/records").glob("L_*.json"))[0]
            r = json.loads(p.read_text(encoding="utf-8"))
            for c in r["classes"]:
                if not c["trusted"]:
                    c.update(verdict="rational", payoff="nonneg", strategy_length=r["witness_length"])
                    break
            r["verdict"] = "rational"
            p.write_text(json.dumps(r, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            G = holon_module("holon.games.cli")
            out = G.Out(root)
            G.corpus_files(root, out)
            out.write(())
        self.assertIn("not the vector its committed module states", self._refused(edit))

    def test_a3_evidence_naming_no_committed_law(self):
        def edit(root):
            p = sorted((root / "results/M5/intent/records").glob("L_intent_*.json"))[0]
            r = json.loads(p.read_text(encoding="utf-8"))
            r["evidence"] = {"law": "l_forged", "marker": "ALL PROOFS CHECK", "law_present": True}
            p.write_text(json.dumps(r, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.assertIn("stated by no LAWS.bend", self._refused(edit))

    def test_a4_doctored_definitions(self):
        def edit(root):
            p = root / "spec/M5/preregistration.json"
            d = json.loads(p.read_text(encoding="utf-8"))
            d["definitions"]["L9"]["thresholds"]["coverage"]["value"] = 0.001
            p.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.assertIn("preregistration.json", self._refused(edit))

    def test_a5_threshold_flipped_against_its_number(self):
        R = holon_module("holon.m5.report")
        block = R.metrics_block(ROOT)
        for n, t in (("L9", "coverage"), ("L6", "decided"), ("L10", "coverage"), ("L9", "validated_categories")):
            bad = copy.deepcopy(block)
            for d in (bad[n]["thresholds"], bad[n]["value"]["thresholds"]):
                d[t] = "meets"
            probs = R.validate(bad, ROOT)
            self.assertTrue(any(f"{n}.{t}: reported meets" in x for x in probs), (n, t, probs))
        with self.assertRaises(R.ReportError):
            bad = copy.deepcopy(block)
            bad["L6"]["thresholds"]["decided"] = bad["L6"]["value"]["thresholds"]["decided"] = "meets"
            R.render(ROOT, bad)


class TestPredictions(unittest.TestCase):
    def _expect(self, pid: str):
        return next(p for p in predictions("I58")["predictions"] if p["id"] == pid)["expected"]

    def test_p1_l6_status(self):
        e, b = self._expect("I58-P1"), _doc()["L6"]
        self.assertEqual(b["overall"], e["overall"])
        self.assertEqual(b["thresholds"], e["thresholds"])
        self.assertEqual([b["value"]["decided"]["numerator"], b["value"]["decided"]["denominator"]], e["decided"])

    def test_p2_l9_status(self):
        e, b = self._expect("I58-P2"), _doc()["L9"]
        self.assertEqual(b["overall"], e["overall"])
        self.assertEqual(b["thresholds"], e["thresholds"])
        for m in ("coverage", "base_coverage"):
            self.assertEqual([b["value"][m]["numerator"], b["value"][m]["denominator"]], e[m])
        nc = b["value"]["new_coverage"]
        self.assertEqual([nc["numerator"], nc["denominator"], b["labels"]["new_coverage"]], e["new_coverage"])

    def test_p3_l10_status(self):
        e, b = self._expect("I58-P3"), _doc()["L10"]
        self.assertEqual(b["overall"], e["overall"])
        self.assertEqual(b["thresholds"], e["thresholds"])
        self.assertEqual([b["value"]["coverage"]["numerator"], b["value"]["coverage"]["denominator"]], e["coverage"])
        cr = b["corpus_recall"]
        self.assertEqual([cr["corpus_recall"]["numerator"], cr["corpus_recall"]["denominator"], cr["label"]],
                         e["corpus_recall"])

    def test_p4_agrees_with_iterations(self):
        doc = _doc()
        l6 = json.loads((ROOT / "results/M5/corpus/l6_corpus.json").read_text())
        l9 = json.loads((ROOT / "results/M5/l9_I57.json").read_text())["L9"]
        l10 = json.loads((ROOT / "results/M5/intent/l10.json").read_text())["l10"]
        self.assertEqual(doc["L6"]["value"], l6)
        self.assertEqual(doc["L9"]["value"], l9)
        self.assertEqual(doc["L10"]["value"], l10)
        for n in NAMES:
            self.assertTrue(doc[n]["agrees_with"]["equal"])

    def test_p5_l6_reference(self):
        ref = _i54.l6(_i58.l6_inputs(ROOT))
        self.assertEqual(_shared(ref, _doc()["L6"]["value"]), [])

    def test_p6_l10_reference(self):
        doc = _doc()["L10"]
        self.assertEqual(_shared(_i54.l10(_i58.l10_inputs(ROOT)), doc["value"]), [])
        cr = _i58.corpus_recall(ROOT)
        self.assertEqual(cr["corpus_recall"], doc["corpus_recall"]["corpus_recall"])
        self.assertEqual(cr["label"], doc["corpus_recall"]["label"])

    def test_p7_v4_independent(self):
        inp = _i58.l6_inputs(ROOT)
        targets = [r for r in inp["records"] if r["kind"] == "target"]
        self.assertEqual(len(targets), 9)
        for r in targets:
            self.assertEqual(r["witness_length"], inp["expect"][r["finding"]]["witness_length"], r["finding"])
        self.assertEqual(_i54.l6(inp)["invalid"], {})


class TestL9Reference(unittest.TestCase):
    def test_l9_reference(self):
        self.assertEqual(_shared(_i54.l9(_i58.l9_inputs(ROOT)), _doc()["L9"]["value"]), [])


class TestRegressions(unittest.TestCase):
    def test_r1_nothing_earlier_changes(self):
        M = holon_module("holon.metrics")
        for m in ("M0", "M1", "M2", "M3"):
            self.assertEqual(M.render(M.compute(m, ROOT)), (ROOT / "results" / m / "metrics.json").read_text(), m)
        rec = holon_module("holon.records")
        for v in rec.GENERATORS:
            names = {str(Path(f)) for f in rec.generator_files(v)}
            self.assertFalse(any("holon/m5" in n or n.endswith("holon/metrics.py") for n in names), v)
        r = subprocess.run([sys.executable, "tools/freeze.py", "check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        base = "f8842357"
        out = subprocess.run(["git", "log", "--first-parent", "--no-merges", "--name-only", "--format=",
                              f"{base}..HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        bad = [p for p in out.split("\n") if re.match(r"^(results|gen|laws)/M[0-4]/|^replay/", p)]
        self.assertEqual(bad, [])

    def test_r2_iteration_outputs_unchanged(self):
        for args in (("m5", "prereg"), ("m5", "controls"), ("m5", "census"), ("m5", "l9"), ("m5", "metrics", "--base"),
                     ("intent", "metrics"), ("intent", "corpus-score"), ("games", "corpus")):
            r = _run(*args, "--check")
            self.assertEqual(r.returncode, 0, f"{args}: {r.stdout[-800:]}{r.stderr[-800:]}")
            self.assertIn("CHECK OK", r.stdout, args)

    def test_r3_prediction_tally(self):
        want = next(r for r in predictions("I58")["regressions"] if r["id"] == "I58-R3")["expected"]
        for k, (held, n) in want.items():
            preds = predictions(k)["predictions"]
            informed = set(((predictions(k)["thresholds"].get("counting") or {}).get("informed") or {}).get("ids", []))
            counted = [p["id"] for p in preds if p["id"] not in informed]
            got = _i58.outcomes(ROOT, k)
            self.assertEqual(sorted(got), sorted(p["id"] for p in preds), k)
            self.assertEqual([sum(got[i]["result"] == "held" for i in counted), len(counted)], [held, n], k)


if __name__ == "__main__":
    unittest.main()
