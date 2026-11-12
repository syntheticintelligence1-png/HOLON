"""I52b: the I52 baselines on the held-out target (BUILD_PLAN §4 I52, its held-out half; whitepaper §13 "Baselines";
docs/HUMAN_ANSWERS.md Q16). This docstring is the contract tests_m4/test_baselines_i52b.py checks.

Instruments fixed at the prereg, pinned by sha256 in PINNED below: tests_m4/_i52b.py (the labels' rule, matching,
applicability and the predictions' readers, written independently of holon/), the held-out protocol
spec/M4/lib/I52b_heldout.json (the system, labels, budgets, adjudicator form), the labels it generates
spec/M4/lib/I52b_heldout_labels.json, the adjudicator template spec/M4/lib/I52b_match_prompt.md, the prompt
prompts/I52b_heldout_baselines.md, and I52's frozen protocol, schema and review prompt (through tests_m4/_i52.py, whose
own pins are I52's). The test process never imports a holon module.

Contamination: everything here was written after the seal on readers lifted, by a builder who had read I49's and I50's
results and the target's code. Every number carries that caveat.

Rules
  H1 (files) for tier in (primary, secondary): <dir>/<baseline>.json for each of the nine baselines (primary dir
     results/eval/heldout/, secondary results/eval/heldout/secondary/), valid against I52's schema, system heldout,
     I52's protocol sha256, the tier's budget; one record, for the target of the protocol; a <baseline>.timing.json.
  H2 (status) not_applicable exactly when the baseline's language is absent from the labelled files; missing only with
     tool.installed false and a reason; error with a reason; a target not run has no findings.
  H3 (findings) ids f0001.. in order; every location names a non-test scope file.
  H4 (matching) matches are exactly _i52b.expected_matches; located is their label set; exactly the located labels are
     adjudicated over their located findings; confirmed is a subset; the five labels of an action carry one
     prompt_sha256, the frozen template filled in (_i52b.match_prompt); detected is the confirmed labels.
  H5 (budget) per tier, a run's units' summed wall clock is at most wall_s + 60, cpus 1; agent_review one reviewer per
     tier, at most wall_s + 60, cpu null with a reason. The primary wall_s is 60 * ceil(H / 60) over
     results/eval/heldout/holon_budget.json, whose steps are I50's route (derive, run) and which was committed before
     any baseline result of the system.
  H6 (labels) the labels file is _i52b.labels_doc(), 65 labels, every anchor within the labelled file at the seal.
  H7 (nothing else moves) I52b's own non-merge commits change no protected path (I52b-R5).
  H8 (blindness) each reviewer's packet lists scope files only; its prompt_sha256 is I52's frozen review template
     filled with the sorted listing and the tier's minutes; no prompt names holon, a label id, an obligation, I49/I50.
  H9 (agnostic) no holon/ file names the target.

Predictions (key I52b of spec/M4/predictions.json): P1-P6 in TestPredictions. A miss is a red test, reported under
Surprises, never edited.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unittest
from pathlib import PurePosixPath

from tests_m4 import _i52, _i52b, _m4

ROOT = _m4.ROOT
BASE = "f47fec1e"  # the merge of I50's branch into I52's that I52b starts from; I52b's own commits come after it
PINNED = {
    "tests_m4/_i52b.py": "bab3c2c4e4bca7c4d035651e2da46c43f5ca2d00fe5771f30258013092205e43",
    "spec/M4/lib/I52b_heldout.json": "d3247da1647c08fb0d3f0d36540dde7656ef18f2f576320f98cfaf1966e84176",
    "spec/M4/lib/I52b_heldout_labels.json": "15b717c694eb4b39ab484c9e3d7c2de7ebac7f8ab7462517c035f6390cd19715",
    "spec/M4/lib/I52b_match_prompt.md": "db3664ea30cbcb99ba155e15e38689393caf7750b656496fde2a635bfbbe4e41",
    "prompts/I52b_heldout_baselines.md": "336e1a15af6f0bf3dba91b3eb8674dab0f7edfd525c72ea93b68921cb54d7555",
    "spec/M4/lib/I52_baselines.json": "2289c62bb90173f781320a9e65c3ac9452e2e192eea80dd2d451846fde117d27",
    "spec/M4/lib/I52_findings.schema.json": "e796a08465e86561f72dddc9a48314a492ca8f25a7496d9a3de2a2c02154bf61",
    "spec/M4/lib/I52_review_prompt.md": "6df1485792de8a1dfeb7e010d0864eeb9462dfadcc06d3c6d9c50a0394534980",
}
PROTECTED = [f"results/M{i}/" for i in range(4)] + [f"gen/M{i}/" for i in range(4)] + \
    [f"spec/M{i}/" for i in range(4)] + ["laws/", "replay/", "audit/", "results/targets/", "gen/targets/", "targets/",
                                          "spec/heldout/", "results/eval/morph/", "results/eval/corpus/",
                                          "results/eval/holon_budget.json", "spec/M4/predictions/I52.json",
                                          "spec/M4/lib/I52_", "tests_m4/test_baselines_i52.py", "tests_m4/_i52.py"]


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr[:500]} (I52b's tests need the repository's history)")
    return p.stdout


def key() -> dict:
    return _m4.predictions("I52b")


def doc(tier: str, b: str) -> dict:
    return _i52b.load(_i52b.result_path(tier, b))


def review_prompt(files: list[str], minutes: int) -> str:
    t = _i52.REVIEW_PROMPT.read_text(encoding="utf-8")
    return t.replace("{{MINUTES}}", str(minutes)).replace("{{FILES}}", "\n".join(f"- {f}" for f in files))


def checkout():
    cfg = json.loads((ROOT / "config" / "holon.json").read_text())
    d = cfg
    for k in _i52b.protocol()["system"]["checkout_config"]:
        d = d[k]
    return d


class TestInstruments(unittest.TestCase):
    def test_instruments_are_the_preregistered_ones(self):
        """The pinned instruments are the files on disk (PINNED holds the sha256 written at the prereg)."""
        for path, sha in sorted(PINNED.items()):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file(), path)
                if sha is not None:
                    self.assertEqual(_i52b.sha256_file(ROOT / path), sha)

    def test_protocol_names_the_seal(self):
        """The system is the sealed one: repository, commit and labelled file are spec/heldout/target.json's."""
        seal = json.loads((ROOT / "spec" / "heldout" / "target.json").read_text())
        s = _i52b.protocol()["system"]
        self.assertEqual((s["repo"], s["commit"], s["labelled_files"]), (seal["repo"], seal["commit"], [seal["target"]]))
        self.assertEqual(s["id"], "heldout")
        self.assertEqual(key()["thresholds"]["budget"]["secondary"]["wall_s"], _i52b.protocol()["budget"]["secondary"]["wall_s"])

    def test_labels_regenerate(self):
        """H6 (I52b-R4): the labels file is the rule's output over I49's committed document; 13 actions x 5 rules;
        every anchor is a line range of the labelled file at the sealed commit."""
        self.assertEqual(_i52b.load(_i52b.LABELS), _i52b.labels_doc())
        labs = _i52b.label_table()
        self.assertEqual(len(labs), key()["thresholds"]["labels_count"])
        self.assertEqual(sorted(labs, key=_i52b.label_key), [f"O{i}" for i in range(1, 66)])
        self.assertEqual(len({v["action"] for v in labs.values()}), 13)
        co = checkout()
        head = subprocess.run(["git", "-C", co, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        self.assertEqual(head, _i52b.protocol()["system"]["commit"], "the sealed checkout is needed")
        for f in _i52b.labelled_files():
            with open(f"{co}/{f}", encoding="utf-8") as fh:
                n = len(fh.read().split("\n"))
            for lab, v in labs.items():
                for a in v["anchors"]:
                    with self.subTest(label=lab, anchor=a):
                        self.assertEqual(a["file"], f)
                        self.assertTrue(1 <= a["lines"][0] <= a["lines"][1] <= n)


    def test_matching_can_fail(self):
        """The matcher is not vacuous: a finding off every anchor, in an unlabelled scope file, or whose long span only
        starts before an anchor is located nowhere; a finding on an anchor is located at exactly its action's five
        labels."""
        labs = _i52b.label_table()
        f0 = _i52b.labelled_files()[0]
        allspans = sorted({tuple(a["lines"]) for v in labs.values() for a in v["anchors"]})
        covered = {x for a, b in allspans for x in range(a, b + 1)}
        free = next(x for x in range(1, 10000) if x not in covered)
        mk = lambda f, a, b: {"id": "f0001", "locations": [{"file": f, "lines": [a, b], "function": None}]}
        self.assertEqual(_i52b.located(mk(f0, free, free)), [])
        other = PurePosixPath(f0).parent.as_posix() + "/Unlabelled.sol"
        a0, b0 = allspans[0]
        self.assertEqual(_i52b.located(mk(other, a0, b0)), [])
        self.assertEqual(_i52b.located(mk(f0, free, free + 200)), [])  # longer than 150 lines: its first line only
        lab = next(iter(sorted(labs, key=_i52b.label_key)))
        a = labs[lab]["anchors"][0]["lines"]
        act = labs[lab]["action"]
        got = _i52b.located(mk(f0, a[0], a[0]))
        self.assertTrue({k for k, v in labs.items() if v["action"] == act} <= set(got))
        self.assertTrue(all(len([k for k in got if labs[k]["action"] == x]) == 5 for x in {labs[k]["action"] for k in got}))


class TestHolonBudget(unittest.TestCase):
    def test_holon_budget_is_i50_s_route(self):
        """H5: the steps are I50's route (holon target derive, then holon target run, for the target), each with its exit
        and wall clock; sum_s is their sum; heldout_wall_s the rule's value; the file was committed before any baseline
        result of the system."""
        hb = _i52b.load(_i52b.HOLON_BUDGET)
        t = _i52b.target()
        self.assertEqual([s["argv"] for s in hb["steps"]],
                         [["python", "-m", "holon", "target", c, "--target", t, "--root", "<scratch copy>"]
                          for c in ("derive", "run")])
        for s in hb["steps"]:
            self.assertIsInstance(s["exit"], int)
            self.assertGreater(s["wall_s"], 0)
        _i52b.budget("primary")  # asserts sum and rule
        first = {}
        for c in git("rev-list", "--reverse", "--topo-order", "HEAD", "--", "results/eval/heldout/").split():
            for f in git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", c).split():
                if f.startswith("results/eval/heldout/"):
                    first.setdefault(f, c)
        hbc = first.get("results/eval/heldout/holon_budget.json")
        self.assertIsNotNone(hbc, "holon_budget.json must be committed")
        for f, c in first.items():
            if f != "results/eval/heldout/holon_budget.json":
                with self.subTest(f=f):
                    r = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", hbc, c])
                    self.assertEqual(r.returncode, 0, f"{f} first committed in {c}, not after the budget {hbc}")
                    self.assertNotEqual(c, hbc)


class TestResults(unittest.TestCase):
    def test_result_files_validate(self):
        """H1, H3."""
        psha = _i52.sha256_file(_i52.PROTOCOL)
        schema = _i52.load(_i52.SCHEMA)
        dirs = set(_i52b.scope_dirs())
        for tier in _i52b.TIERS:
            bud = _i52b.budget(tier)
            for b in _i52b.BASELINES:
                with self.subTest(tier=tier, baseline=b):
                    d = doc(tier, b)
                    self.assertEqual(_m4.mini_schema.errors(d, schema), [])
                    self.assertTrue(_i52b.timing_path(tier, b).is_file())
                    self.assertEqual((d["baseline"], d["system"], d["protocol_sha256"]), (b, "heldout", psha))
                    self.assertEqual(d["budget"], bud)
                    self.assertEqual(sorted(d["targets"]), _i52b.targets())
                    for t, r in d["targets"].items():
                        ids = [f["id"] for f in r["findings"]]
                        self.assertEqual(ids, [f"f{i:04d}" for i in range(1, len(ids) + 1)])
                        self.assertEqual(r["commit"], _i52b.protocol()["system"]["commit"])
                        for f in r["findings"]:
                            for loc in f["locations"]:
                                self.assertIn(PurePosixPath(loc["file"]).parent.as_posix(), dirs, f["id"])
                                self.assertFalse(_i52.is_test(loc["file"]), f["id"])

    def test_status_follows_applicability(self):
        """H2."""
        for tier in _i52b.TIERS:
            for b in _i52b.BASELINES:
                d = doc(tier, b)
                for t, r in d["targets"].items():
                    with self.subTest(tier=tier, baseline=b):
                        self.assertEqual(r["status"] == "not_applicable", not _i52b.applicable(b))
                        if r["status"] == "missing":
                            self.assertFalse(d["tool"]["installed"])
                        if r["status"] in ("missing", "error", "not_applicable"):
                            self.assertTrue(r["reason"])
                            self.assertEqual(r["findings"], [])
                        if not d["tool"]["installed"]:
                            self.assertIn(r["status"], ("missing", "not_applicable"))

    def test_equal_budget(self):
        """H5 (I52b-R3)."""
        for tier in _i52b.TIERS:
            w = _i52b.budget(tier)["wall_s"]
            for b in _i52b.BASELINES:
                tm = _i52b.load(_i52b.timing_path(tier, b))
                d = doc(tier, b)
                with self.subTest(tier=tier, baseline=b):
                    if b == "agent_review":
                        revs = tm["reviewers"]
                        self.assertEqual(len(revs), 1)
                        self.assertLessEqual(revs[0]["wall_s"], w + 60)
                        self.assertEqual(revs[0]["budget_s"], w)
                        self.assertIsNone(revs[0]["cpu_s"])
                        self.assertTrue(revs[0]["cpu_reason"])
                        continue
                    for t, r in d["targets"].items():
                        if r["status"] != "run":
                            continue
                        rec = tm["targets"][t]
                        self.assertEqual(rec["cpus"], 1)
                        self.assertLessEqual(sum(u["wall_s"] for u in rec["units"]), w + 60)

    def test_agent_review_is_blind(self):
        """H8 (I52b-R6)."""
        words = ["holon", "i49", "i50", "obligation", "disch", "undo", "sort", "sym", "fact"]
        dirs = set(_i52b.scope_dirs())
        for tier in _i52b.TIERS:
            r = doc(tier, "agent_review")["targets"][_i52b.target()]
            if r["status"] != "run":
                continue
            with self.subTest(tier=tier):
                files = r["scope"]["packet_files"]
                self.assertTrue(files)
                for f in files:
                    self.assertIn(PurePosixPath(f).parent.as_posix(), dirs)
                    self.assertFalse(_i52.is_test(f))
                    self.assertTrue(f.endswith(".sol"))
                text = review_prompt(sorted(files), _i52b.budget(tier)["wall_s"] // 60)
                self.assertEqual(r["scope"]["prompt_sha256"], hashlib.sha256(text.encode()).hexdigest())
                low = text.lower()
                for w in words:
                    self.assertIsNone(re.search(rf"\b{w}\b", low), w)
                self.assertIsNone(re.search(r"\bO\d+\b", text))


class TestMatching(unittest.TestCase):
    def test_matches_are_the_instrument_s(self):
        """H4: matches = the instrument's located pairs; located = their labels."""
        for tier in _i52b.TIERS:
            for b in _i52b.BASELINES:
                for t, r in doc(tier, b)["targets"].items():
                    with self.subTest(tier=tier, baseline=b):
                        got = sorted((m["finding"], m["label"]) for m in r["matches"])
                        self.assertEqual(got, _i52b.expected_matches(r))
                        self.assertEqual(r["located"], sorted({l for _, l in got}, key=_i52b.label_key))

    def test_detected_is_what_the_adjudicator_confirmed(self):
        """H4: exactly the located labels are adjudicated over their located findings, confirmed a subset; an
        action's five labels share one prompt, the frozen template filled in; detected the confirmed labels."""
        labs = _i52b.label_table()
        for tier in _i52b.TIERS:
            for b in _i52b.BASELINES:
                for t, r in doc(tier, b)["targets"].items():
                    with self.subTest(tier=tier, baseline=b):
                        loc = {}
                        for m in r["matches"]:
                            loc.setdefault(m["label"], []).append(m["finding"])
                        adj = {a["label"]: a for a in r["adjudications"]}
                        self.assertEqual(sorted(adj), sorted(loc))
                        byid = {f["id"]: f for f in r["findings"]}
                        for lab, a in adj.items():
                            self.assertEqual(sorted(a["findings"]), sorted(loc[lab]))
                            self.assertTrue(set(a["confirmed"]) <= set(a["findings"]))
                            fs = [byid[i] for i in sorted(a["findings"])]
                            want = _i52b.match_prompt(labs[lab]["action"], fs)
                            self.assertEqual(a["prompt_sha256"], hashlib.sha256(want.encode()).hexdigest(), lab)
                        self.assertEqual(r["detected"], _i52b.detected(r))


class TestPins(unittest.TestCase):
    def test_nothing_else_moves(self):
        """H7 (I52b-R5): I52b's own commits (the non-merge commits of the first-parent history after BASE)."""
        own = git("rev-list", "--first-parent", "--no-merges", f"{BASE}..HEAD").split()
        changed = sorted({f for c in own for f in git("diff-tree", "--no-commit-id", "--name-only", "-r", c).split()})
        self.assertEqual([p for p in changed if any(p.startswith(x) for x in PROTECTED)], [])

    def test_holon_names_no_target(self):
        """H9 (I52b-R7)."""
        names = json.loads((ROOT / "targets" / "scroll" / "target.json").read_text())["names"]
        pat = re.compile("|".join(re.escape(n) for n in names), re.I)
        hits = []
        for p in sorted((ROOT / "holon").rglob("*")):
            if p.is_file() and p.suffix in (".py", ".go", ".json", ".mjs", ".js", ".md", ".bend", ".sol", ".txt"):
                text = p.read_text(encoding="utf-8", errors="replace")
                if pat.search(text):
                    hits.append(p.relative_to(ROOT).as_posix())
        self.assertEqual(hits, [])


class TestPredictions(unittest.TestCase):
    def test_p1_primary_budget_is_one_minute(self):
        self.assertEqual(_i52b.budget("primary")["wall_s"], key()["predictions"][0]["expected"]["primary_wall_s"])

    def test_p2_every_applicable_baseline_runs(self):
        exp = key()["predictions"][1]["expected"]
        for tier in _i52b.TIERS:
            got = {b: _i52b.record(tier, b)["status"] for b in _i52b.BASELINES}
            with self.subTest(tier=tier):
                self.assertEqual({b: s for b, s in got.items() if b in exp["run"] and s != "run"}, {})
                self.assertEqual({b: s for b, s in got.items() if b in exp["not_applicable"] and s != "not_applicable"}, {})

    def test_p3_primary_detects_nothing(self):
        names = [b for b in _i52b.BASELINES if _i52b.applicable(b)]
        self.assertEqual([b for b in names if not _i52b.ran("primary", b)], [], "non-vacuity")
        self.assertEqual({b: sorted(_i52b.detected_set("primary", b)) for b in names if _i52b.detected_set("primary", b)}, {})
        self.assertEqual(len(_i52b.record("primary", "agent_review")["findings"]), 0)
        self.assertTrue(_i52b.load(_i52b.timing_path("primary", "agent_review"))["reviewers"][0]["timed_out"])

    def test_p4_secondary_fuzzers_and_symbolic_find_nothing_located(self):
        names = ("echidna", "medusa", "hevm", "halmos")
        self.assertEqual([b for b in names if not _i52b.ran("secondary", b)], [], "non-vacuity")
        self.assertEqual({b: sorted(_i52b.located_set("secondary", b)) for b in names if _i52b.located_set("secondary", b)}, {})
        self.assertEqual({b: sorted(_i52b.detected_set("secondary", b)) for b in names if _i52b.detected_set("secondary", b)}, {})

    def test_p5_secondary_slither_located_not_detected_and_mining(self):
        for b in ("slither", "spec_mining"):
            self.assertTrue(_i52b.ran("secondary", b), f"non-vacuity: {b}")
        self.assertGreaterEqual(len(_i52b.located_set("secondary", "slither")), 1)
        self.assertEqual(_i52b.detected_set("secondary", "slither"), set())
        self.assertEqual(_i52b.detected_set("secondary", "spec_mining"), set())

    def test_p6_secondary_agent_review(self):
        self.assertTrue(_i52b.ran("secondary", "agent_review"))
        tm = _i52b.load(_i52b.timing_path("secondary", "agent_review"))
        self.assertFalse(tm["reviewers"][0]["timed_out"])
        a = _i52b.detected_set("secondary", "agent_review")
        self.assertGreaterEqual(len(a), 1)
        union = set()
        for b in _i52b.BASELINES:
            if b != "agent_review":
                union |= _i52b.detected_set("secondary", b)
        self.assertGreater(len(a), len(union), sorted(union))


if __name__ == "__main__":
    unittest.main()
