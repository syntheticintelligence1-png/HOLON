"""I52: baselines on Morph and the corpus pre-fix commits (whitepaper §13 "Baselines"; BUILD_PLAN I52; docs/HUMAN_ANSWERS.md
Q16 (the baseline installs) and Q20 (N = 20)). This docstring is the contract tests_m4/test_baselines_i52.py checks.

Instruments fixed at the prereg, pinned by sha256 in PINNED below: tests_m4/_i52.py (the matching rules, applicability
and the predictions' readers, written independently of holon/), the frozen protocol spec/M4/lib/I52_baselines.json
(baselines, stock modes, scope, equal budget, matching, adjudicator, relational ids), the common findings schema
spec/M4/lib/I52_findings.schema.json, the Morph anchors spec/M4/lib/I52_morph_anchors.json, the agent review prompt
I52_review_prompt.md, the match adjudicator prompt I52_match_prompt.md, and the prompt prompts/I52_baselines.md. The
test process never imports a holon module.

What the plan asks
  Pinned slither, echidna, medusa, hevm and halmos under ~/.holon/tools, plus Go fuzzing, 2-cycle round-trip testing,
  frequency-based spec mining and agent-only review; all at equal budget, in a common findings schema, on Morph, the
  corpus pre-fix commits and the held-out target. Exit: results/eval/<system>/<baseline>.json for every system. This
  session covers Morph and the corpus; the held-out run is one command, pending I49/I50 (it never reads spec/heldout/).

Rules
  B1 (files) results/eval/<system>/<baseline>.json for system in (morph, corpus) and each of the nine baselines,
     valid against the schema, with the protocol's sha256 and the system's budget; one record per target (morph: the
     single target "morph"; corpus: c01..c20); a <baseline>.timing.json beside it.
  B2 (status) not_applicable exactly when the baseline's language is absent from the target (Solidity tools: no
     Solidity; go_fuzz, two_cycle: no Go); missing only when tool.installed is false, with a reason; error with a reason.
     A target that is not run has no findings.
  B3 (findings) ids f0001.. in order; every location names a scope file of the target.
  B4 (matching) matches are exactly the located pairs of _i52.expected_matches; located is their label set; exactly the
     located labels are adjudicated, with the located findings listed; confirmed is a subset; detected is
     _i52.detected (labels with a confirmed finding).
  B5 (budget) per target, the summed wall clock of the units of a run is at most wall_s + 60; cpus is 1. The agent
     review is one reviewer per system (the lead's ruling): at most wall_s + 60 on Morph and 20 x wall_s + 60 on the
     corpus; its cpu is null with a reason. HOLON's own budget is measured by the protocol's holon_budget rule and
     compared in the report.
  B6 (pins) config/holon.json "baselines" names every tool; the existing entries bend, lean, replay, hevm and z3 are
     the base's; .github/ci/verify_toolchain.py still checks exactly its 13 pins.
  B7 (no M0-M3 change) nothing under results/M0..M3, gen/M0..M3, laws/, replay/, spec/M0..M3 or audit/ differs from the
     base commit 4fd64a52.
  B8 (blindness) Morph's packet lists Morph scope files; the corpus packet lists exactly <entry>/<labelled file> for
     every entry (I48's renamings, never the original repositories); prompt_sha256 is the frozen template filled with
     the packet's sorted listing and the reviewer's minutes.
  B9 (non-vacuity) a "detects nothing" prediction holds only if each baseline it names ran on at least half of the
     targets where it applies (_i52.ran_enough); otherwise it is a miss.

Predictions (key I52 of spec/M4/predictions.json): P1-P8 in TestPredictions. A miss is a red test, reported under
Surprises, never edited.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import PurePosixPath

from tests_m4 import _i52, _m4

ROOT = _m4.ROOT
BASE = "4fd64a52"
PINNED = {
    "tests_m4/_i52.py": "f1d60619407995138642a4d50eaa06f3deba683dc13ac092b02b3e87e94fc1c6",
    "spec/M4/lib/I52_baselines.json": "2289c62bb90173f781320a9e65c3ac9452e2e192eea80dd2d451846fde117d27",
    "spec/M4/lib/I52_findings.schema.json": "e796a08465e86561f72dddc9a48314a492ca8f25a7496d9a3de2a2c02154bf61",
    "spec/M4/lib/I52_morph_anchors.json": "4410ff8ac8de5139a119c5f87d3bd5a018d9fb2190e9f124656b636594dab4a1",
    "spec/M4/lib/I52_review_prompt.md": "6df1485792de8a1dfeb7e010d0864eeb9462dfadcc06d3c6d9c50a0394534980",
    "spec/M4/lib/I52_match_prompt.md": "f97d7f796e71fdcc67a6c68e5b4ad3915269bbcaa1b59140fd98e9606cd19e4b",
    "prompts/I52_baselines.md": "be7efaa35ce30b70e2dce048ad65035b95ac3f7c0fe3c61c959a7d67b8d16440",
}
PINS_13 = ("bend", "lean", "replay", "hevm")


def result(system: str, baseline: str) -> dict:
    return _i52.load(_i52.result_path(system, baseline))


def key() -> dict:
    return _m4.predictions("I52")


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr[:500]} (I52's tests need the repository's history)")
    return p.stdout


def review_prompt(files: list[str], minutes: int) -> str:
    t = _i52.REVIEW_PROMPT.read_text(encoding="utf-8")
    return t.replace("{{MINUTES}}", str(minutes)).replace("{{FILES}}", "\n".join(f"- {f}" for f in files))


class TestInstruments(unittest.TestCase):
    def test_instruments_are_the_preregistered_ones(self):
        """The pinned instruments are the files on disk (PINNED holds the sha256 written at the prereg)."""
        for path, sha in sorted(PINNED.items()):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file(), path)
                if sha is not None:
                    self.assertEqual(_i52.sha256_file(ROOT / path), sha)

    def test_protocol_is_complete(self):
        """The protocol names the nine baselines, the same budget for every baseline of a system, the window, and
        relational and single-component ids that partition O1..O37."""
        p = _i52.protocol()
        self.assertEqual(sorted(p["baselines"]), sorted(_i52.BASELINES))
        self.assertEqual(p["matching"]["window_lines"], _i52.WINDOW)
        ids = p["relational"]["ids"] + p["relational"]["single_component_ids"]
        self.assertEqual(sorted(ids, key=lambda k: int(k[1:])), [f"O{i}" for i in range(1, 38)])
        self.assertEqual(sorted(_i52.anchors(), key=lambda k: int(k[1:])), [f"O{i}" for i in range(1, 38)])
        self.assertEqual(key()["thresholds"]["budget"]["morph"], p["budget"]["morph"])
        self.assertEqual(key()["thresholds"]["budget"]["corpus"], p["budget"]["corpus"])

    def test_anchor_spans_are_functions_of_the_pinned_checkout(self):
        """Every anchor span starts at a line naming its function and ends at a closing brace, in the pinned Morph
        checkout (config/holon.json replay.morph at the anchors' commit)."""
        cfg = json.loads((ROOT / "config" / "holon.json").read_text())
        morph = cfg["replay"]["morph"]
        head = subprocess.run(["git", "-C", morph, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        self.assertEqual(head, _i52.load(_i52.ANCHORS)["commit"], "the pinned Morph checkout is needed")
        for oid, o in _i52.anchors().items():
            for a in o["anchors"]:
                with open(f"{morph}/{a['file']}", encoding="utf-8") as fh:
                    lines = fh.read().split("\n")
                s, e = a["lines"]
                with self.subTest(o=oid, f=a["function"]):
                    self.assertIn(a["function"].split(".")[-1], lines[s - 1])
                    self.assertEqual(lines[e - 1].strip(), "}")


class TestResults(unittest.TestCase):
    def test_result_files_validate_and_cover_every_target(self):
        """B1, B3: the exit's files exist, validate, name the protocol and budget, cover every target, ids in order,
        locations in scope."""
        psha = _i52.sha256_file(_i52.PROTOCOL)
        schema = _i52.load(_i52.SCHEMA)
        budget = {s: _i52.budget(s) for s in _i52.SYSTEMS}
        for system in _i52.SYSTEMS:
            for b in _i52.BASELINES:
                with self.subTest(system=system, baseline=b):
                    doc = result(system, b)
                    self.assertEqual(_m4.mini_schema.errors(doc, schema), [])
                    self.assertTrue(_i52.timing_path(system, b).is_file())
                    self.assertEqual((doc["baseline"], doc["system"], doc["protocol_sha256"]), (b, system, psha))
                    self.assertEqual(doc["budget"], budget[system])
                    self.assertEqual(sorted(doc["targets"]), sorted(_i52.targets(system)))
                    for t, r in doc["targets"].items():
                        ids = [f["id"] for f in r["findings"]]
                        self.assertEqual(ids, [f"f{i:04d}" for i in range(1, len(ids) + 1)], t)
                        dirs = set(_i52.scope_dirs(system, t))
                        for f in r["findings"]:
                            for loc in f["locations"]:
                                self.assertIn(PurePosixPath(loc["file"]).parent.as_posix(), dirs, (t, f["id"]))
                                self.assertFalse(_i52.is_test(loc["file"]), (t, f["id"]))

    def test_status_follows_applicability(self):
        """B2."""
        for system in _i52.SYSTEMS:
            for b in _i52.BASELINES:
                doc = result(system, b)
                for t, r in doc["targets"].items():
                    with self.subTest(system=system, baseline=b, target=t):
                        app = _i52.applicable(b, system, t)
                        self.assertEqual(r["status"] == "not_applicable", not app)
                        if r["status"] == "missing":
                            self.assertFalse(doc["tool"]["installed"])
                        if r["status"] in ("missing", "error", "not_applicable"):
                            self.assertTrue(r["reason"])
                            self.assertEqual(r["findings"], [])
                        if not doc["tool"]["installed"]:
                            self.assertIn(r["status"], ("missing", "not_applicable"))

    def test_equal_budget(self):
        """B5: every baseline but agent_review: per target, the units' summed wall clock is at most wall_s + 60 with
        cpus 1. agent_review: one reviewer per system (timing reviewers), at most wall_s + 60 on Morph and
        20 x wall_s + 60 on the corpus, cpu null with a reason."""
        budget = {s: _i52.budget(s) for s in _i52.SYSTEMS}
        for system in _i52.SYSTEMS:
            for b in _i52.BASELINES:
                tm = _i52.load(_i52.timing_path(system, b))
                doc = result(system, b)
                with self.subTest(system=system, baseline=b):
                    if b == "agent_review":
                        revs = tm["reviewers"]
                        self.assertEqual(len(revs), 1)
                        cap = budget[system]["wall_s"] * len(_i52.targets(system)) + 60
                        self.assertLessEqual(revs[0]["wall_s"], cap)
                        self.assertIsNone(revs[0]["cpu_s"])
                        self.assertTrue(revs[0]["cpu_reason"])
                        continue
                    for t, r in doc["targets"].items():
                        if r["status"] != "run":
                            continue
                        rec = tm["targets"][t]
                        self.assertEqual(rec["cpus"], 1, t)
                        self.assertLessEqual(sum(u["wall_s"] for u in rec["units"]), budget[system]["wall_s"] + 60, t)

    def test_agent_review_is_blind(self):
        """B8: Morph's packet lists Morph scope files; the corpus packet lists <entry>/<labelled file> of every entry
        (I48's renamings); one prompt per system, the frozen template filled with the packet's sorted listing and
        the reviewer's minutes; no prompt names holon, the corpus, a fix commit or spec/eval."""
        budget = {s: _i52.budget(s) for s in _i52.SYSTEMS}
        for system in _i52.SYSTEMS:
            doc = result(system, "agent_review")
            ran = {t: r for t, r in doc["targets"].items() if r["status"] == "run"}
            if not ran:
                continue
            listing = []
            for t, r in sorted(ran.items()):
                files = r["scope"]["packet_files"]
                with self.subTest(system=system, target=t):
                    self.assertTrue(files)
                    if system == "morph":
                        dirs = set(_i52.scope_dirs(system, t))
                        for f in files:
                            self.assertIn(PurePosixPath(f).parent.as_posix(), dirs)
                            self.assertFalse(_i52.is_test(f))
                    else:
                        e = next(x for x in _i52.entries() if x["id"] == t)
                        self.assertEqual(sorted(files), sorted(f"{t}/{f}" for f in e["files"]))
                listing += files
            minutes = budget[system]["wall_s"] * len(_i52.targets(system)) // 60
            text = review_prompt(sorted(listing), minutes)
            for t, r in ran.items():
                self.assertEqual(r["scope"]["prompt_sha256"], hashlib.sha256(text.encode()).hexdigest(), t)
            for word in ("holon", "corpus", "fix_commit", "spec/eval"):
                self.assertNotIn(word, text.lower())


class TestMatching(unittest.TestCase):
    def test_matches_are_the_instrument_s(self):
        """B4: matches = the instrument's located pairs; located = their labels."""
        for system in _i52.SYSTEMS:
            for b in _i52.BASELINES:
                doc = result(system, b)
                for t, r in doc["targets"].items():
                    with self.subTest(system=system, baseline=b, target=t):
                        got = sorted((m["finding"], m["label"]) for m in r["matches"])
                        self.assertEqual(got, _i52.expected_matches(system, t, r))
                        self.assertEqual(r["located"], sorted({l for _, l in got}, key=lambda k: (k[0], int(k[1:]))))

    def test_detected_is_what_the_adjudicator_confirmed(self):
        """B4: exactly the located labels are adjudicated, over their located findings; confirmed is a subset;
        detected is the confirmed labels."""
        for system in _i52.SYSTEMS:
            for b in _i52.BASELINES:
                doc = result(system, b)
                for t, r in doc["targets"].items():
                    with self.subTest(system=system, baseline=b, target=t):
                        loc = {}
                        for m in r["matches"]:
                            loc.setdefault(m["label"], []).append(m["finding"])
                        adj = {a["label"]: a for a in r["adjudications"]}
                        self.assertEqual(sorted(adj), sorted(loc))
                        for lab, a in adj.items():
                            self.assertEqual(sorted(a["findings"]), sorted(loc[lab]))
                            self.assertTrue(set(a["confirmed"]) <= set(a["findings"]))
                        self.assertEqual(r["detected"], _i52.detected(r))


class TestHolonBudget(unittest.TestCase):
    def test_holon_budget_is_measured_by_the_rule(self):
        """The protocol's holon_budget rule: m0_s..m2_s are the base's recorded from_scratch_gate_s, m3 was measured
        by a gate run that passed (exit 0), and Morph's wall_s is 60 * ceil(sum / 60) (_i52.budget)."""
        hb = _i52.load(_i52.HOLON_BUDGET)
        for i in range(3):
            base = json.loads(git("show", f"{BASE}:results/M{i}/metrics_timing.json"))
            self.assertEqual(hb[f"m{i}_s"], base["from_scratch_gate_s"])
        m = hb["m3_measurement"]
        if m["exit"] != 0:
            # amendment (spec/M4/amendments/I52.jsonl): exit 1 only when the report lists every check the full gate
            # runs, G1 alone failed (the check CI leaves out of M3, I97) and its failure detail is recorded
            from holon.gate import CHECK_ORDER
            self.assertEqual(m["exit"], 1)
            self.assertEqual(sorted(set(m["checks"]) | set(m["not_applicable"])), sorted(CHECK_ORDER))
            self.assertEqual(m["failed_checks"], ["G1"])
            self.assertEqual(sorted(k for k, ok in m["checks"].items() if not ok), ["G1"])
            self.assertTrue(m["failed_details"]["G1"])
        self.assertEqual(hb["m3_s"], hb["m3_measurement"]["wall_s"])
        self.assertGreater(_i52.budget("morph")["wall_s"], 0)


class TestPins(unittest.TestCase):
    def test_baseline_pins_are_separate_and_the_13_are_unchanged(self):
        """B6 (I52-R4)."""
        cfg = json.loads((ROOT / "config" / "holon.json").read_text())
        base = json.loads(git("show", f"{BASE}:config/holon.json"))
        for k in (*PINS_13, "z3"):
            self.assertEqual(cfg[k], base[k], k)
        tools = cfg["baselines"]["tools"]
        for name in ("slither", "echidna", "medusa", "halmos", "go_fuzz"):
            self.assertIn(name, tools)
            t = tools[name]
            self.assertTrue(t.get("version"))
            if t.get("missing"):
                self.assertTrue(t.get("missing_reason"))
            else:
                self.assertTrue(t.get("sha256") or t.get("lock_sha256") or t.get("go_version"))
        vt = (ROOT / ".github" / "ci" / "verify_toolchain.py").read_text()
        self.assertEqual(vt, git("show", f"{BASE}:.github/ci/verify_toolchain.py"))

    def test_no_m0_m3_outcome_changed(self):
        """B7 (I52-R5)."""
        prefixes = [f"results/M{i}/" for i in range(4)] + [f"gen/M{i}/" for i in range(4)] + \
            [f"spec/M{i}/" for i in range(4)] + ["laws/", "replay/", "audit/"]
        # I52's own commits: the non-merge commits of the first-parent history after BASE (a merge of the lead is not
        # I52's change; amendment spec/M4/amendments/I52.jsonl)
        own = git("rev-list", "--first-parent", "--no-merges", f"{BASE}..HEAD").split()
        changed = sorted({f for c in own for f in git("diff-tree", "--no-commit-id", "--name-only", "-r", c).split()})
        self.assertEqual([p for p in changed if any(p.startswith(x) for x in prefixes)], [])


class TestPredictions(unittest.TestCase):
    def test_p1_no_relational_obstruction_by_single_component_analyzers(self):
        rel = set(_i52.protocol()["relational"]["ids"])
        names = _i52.protocol()["single_component_analyzers"]
        self.assertEqual([b for b in names if not _i52.ran_enough("morph", b)], [], "non-vacuity")
        got = {b: sorted(_i52.morph_detected(b) & rel) for b in names}
        self.assertEqual({b: v for b, v in got.items() if v}, {})

    def test_p2_two_cycle_finds_o2_not_o1(self):
        d = _i52.morph_detected("two_cycle")
        self.assertIn("O2", d)
        self.assertNotIn("O1", d)

    def test_p3_solidity_tools_detect_no_corpus_entry(self):
        self.assertEqual([b for b in _i52.SOLIDITY if not _i52.ran_enough("corpus", b)], [], "non-vacuity")
        self.assertEqual({b: sorted(_i52.corpus_detected(b)) for b in _i52.SOLIDITY if _i52.corpus_detected(b)}, {})

    def test_p4_go_stock_tools_detect_no_corpus_entry(self):
        self.assertEqual([b for b in _i52.GO if not _i52.ran_enough("corpus", b)], [], "non-vacuity")
        self.assertEqual({b: sorted(_i52.corpus_detected(b)) for b in _i52.GO if _i52.corpus_detected(b)}, {})

    def test_p5_spec_mining(self):
        self.assertTrue(_i52.ran_enough("corpus", "spec_mining") and _i52.ran_enough("morph", "spec_mining"))
        c = _i52.corpus_detected("spec_mining")
        self.assertIn("c06", c)
        self.assertLessEqual(len(c), 2, sorted(c))
        self.assertEqual(_i52.morph_detected("spec_mining"), set())

    def test_p6_agent_review(self):
        self.assertGreaterEqual(len(_i52.corpus_detected("agent_review")), 5)
        self.assertGreaterEqual(len(_i52.morph_detected("agent_review")), 2)

    def test_p7_agent_beats_the_union(self):
        union = set()
        for b in _i52.BASELINES:
            if b != "agent_review":
                union |= _i52.corpus_detected(b)
        self.assertGreater(len(_i52.corpus_detected("agent_review")), len(union), sorted(union))

    def test_p8_expected_detection_table(self):
        exp = key()["thresholds"]["expected_detections"]
        right = total = 0
        for b in _i52.BASELINES:
            got = _i52.corpus_detected(b)
            for t in _i52.targets("corpus"):
                if _i52.applicable(b, "corpus", t):
                    total += 1
                    right += (t in got) == (t in exp["corpus"][b])
            total += 1
            right += _i52.morph_detected(b) == set(exp["morph"][b])
        self.assertGreaterEqual(right / total, 0.85, f"{right}/{total}")


if __name__ == "__main__":
    unittest.main()
