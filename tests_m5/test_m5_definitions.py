"""I54: the L6, L9 and L10 definitions, preregistered (BUILD_PLAN §4 I54; docs/HUMAN_ANSWERS.md Q11; whitepaper §12 rows
L6, L9 and L10, §12.4, §5.7, §5.9-§5.10, §13). This docstring is the contract that tests_m5/test_m5_definitions.py
checks.

The definitions are thresholds.definitions of the key I54 (spec/M5/predictions/I54.json): immutable under the prereg
audit. Instruments fixed at the prereg, pinned by sha256 in PINNED: tests_m5/_i54.py (the definitions written out a
second time, independently of holon/: control documents, the game-truth interpreter, the census rule, a reference
computation of every measure, fixtures), tests_m5/_m5.py, tests_m5/__init__.py, spec/M5/lib/environment_classes.json,
spec/M5/lib/inputs.schema.json, spec/M5/lib/truth_protocol.json, spec/M5/lib/truth_prompt.md and
prompts/I54_m5_definitions.md.

What the plan asks
  BUILD_PLAN I54: the exact definitions and thresholds of L6, L9 and L10 in spec/M5/preregistration.json before the work
  they measure (I55-I57); exit: the definitions committed, a computation stub, tests on fixtures. Q11: target-agnostic,
  measured against ground truth, never against HOLON's own outputs alone; L6 bounded games with ordinal payoffs
  (decided fraction, accuracy against corpus truth, a negative control); L9 time-indexed environment modules
  (environment-premise coverage, module accuracy on held-out time slices, sensitivity with every change replayed);
  L10 the paper's metric, intent-law coverage (and its residual, intent extraction quality).

Rules (tests below; the key's definitions hold the full text)
  D1 The key holds the definitions (common, L6, L9, L10, controls) and the instrument's constants equal its numbers.
  D2 spec/M5/preregistration.json is rendered by `python -m holon m5 prereg` from the key: its definitions are the key's;
     base.commit is the key's base_commit; base.l6_findings and base.l9_dependent are F(M3) and the environment-dependent
     records of M2 and M3, read from the base commit through git (49 and 222 at this base: I54-R1, I54-R2); its
     instruments map each instrument path to its sha256. --check exits 0.
  K1 `python -m holon m5 controls` writes spec/M5/controls/games/<id>.json, spec/M5/controls/intent/<id>.json and
     <id>.sol, exactly the instrument's documents (14 game controls, 12 intent controls); --check exits 0.
  K2 Each game control's truth is what the instrument's interpreter computes from the document without its truth.
  K3 Family truths: free_trigger, profit, recoup and deep rational; trusted_only and costly irrational (the negative
     controls); incomparable UNKNOWN; deep's untrusted depth exceeds its horizon; recoup's witness is negative at its end.
  K4 No module of holon/ other than holon/m5/controls.py holds a control's id or name token.
  C1 holon.m5.census.census_of(path, text) equals the instrument's census_of on the control sources and the fixture texts.
  C2 `python -m holon m5 census` writes results/M5/l10_census_base.json: {"repos": {repo: {"commit", "files",
     "unresolved"}}, "clauses": [...]}, the census of M3's scope at the base (scope from the base commit's facts
     documents; files read through git at each document's target.commit from config/holon.json extract.sources); the
     instrument recomputes it; --check exits 0. A missing checkout fails, never skips.
  M6 holon.m5.metrics.l6(inputs) equals the instrument's l6 on every fixture (five engines, and the clean fixture); the
     validity rules demote exactly f4 (V1), f5 (V4), f6 (one_record), f7 (V6) and f8 (V8); a constant 'rational' engine
     is caught by false_rational (the four negative controls) and by controls_beats_majority; a horizon-bounded engine by
     false_irrational (deep); a trigger-time payoff by false_irrational (recoup); the clean fixture meets every threshold.
  M9 holon.m5.metrics.l9(inputs) equals the instrument's l9 on every fixture; circular observations fail R1, a one-class
     history R5, an unpinned parameter R6; a dropped premise leaves the law in both coverage denominators, uncovered;
     an unlisted id is unclassified; the clean fixture meets every threshold.
  M10 holon.m5.metrics.l10(inputs) equals the instrument's l10 on every fixture; a short atomization leaves the census
     denominator unchanged; self-review covers nothing; weak (all PROVED) transcriptions fail control_recall; the honest
     fixture meets every threshold.
  B1 `python -m holon m5 metrics --base` writes results/M5/definitions_base.json: L6 and L9 over the base commit's
     records with no game, module or intent record, and L10's census size; it equals the instrument's computation;
     --check exits 0. `python -m holon m5 metrics --inputs F --out G` computes the three metrics of an inputs document.
  S1 Every fixture record validates against spec/M5/lib/inputs.schema.json.

Predictions (I54-P1..P3; outcomes recorded nowhere before the build): the census of C2 holds 100..1000 clauses; Rollup.sol
contributes the most; at least a quarter come from .go files. A miss is a Surprise, never a reason to edit anything.

Gaps preregistered
  E-G1 Same author. The instrument and holon/m5 are written by the same session; their agreement checks are not
       independent evidence (as I48's build review M2 said of its pair). The independent truth is the controls'
       interpreter (enumeration of every schedule) and the history and corpus truth, which no metric code produces.
  E-G2 Constructed truth is public. The controls are in the repository; K4 guards against naming them, not against an
       engine tuned to their families. Constructed and documented truth are reported apart and never pooled.
  E-G3 Corpus truth is thin. Read by the builder before the prereg (not as truth): the I48 texts document a trigger by an
       untrusted actor with no value flow for about four to six entries (peer-to-peer and view-call denial of service)
       and a costly trigger for about one, and I51 has not run, so L6's corpus accuracy may well be insufficient_n.
  E-G4 L9 truth needs new observations. The I59 snapshot's source field is inadmissible for a retention window (R1) and
       its retrievability holds no negative (R5); I57 must record admissible probes. Module families are three; a module
       of another family is not validated until a later key adds one.
  E-G5 The census is lexical (MARKERS over sentences): it over-counts descriptive sentences with a marker word and
       misses normative text without one; Go comments inside a declaration body are outside it.
  E-G6 Same family. The corpus truth's labellers will be the build's family (Q9), as I48's were.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m5 import _i54 as I
from tests_m5._m5 import (ROOT, blobs, dumps, file_sha256, holon_module, load_json, predictions, tree_files,
                          validate)

KEY = "I54"
PINNED = {
    "prompts/I54_m5_definitions.md": "7dad55ce9619d1b645bf0e36e25233ff234b278658bcfe89f11c46b2be31d43f",
    "spec/M5/lib/environment_classes.json": "b7bd9f9b264a70a2f39c9ca18a44c821b8c1838d8db3ed1e18e63f9bf6d23aab",
    "spec/M5/lib/inputs.schema.json": "986f5f368afb61d55e06c39b9c600197eac3bb64d57b796eef61dd43ee738581",
    "spec/M5/lib/truth_prompt.md": "75a1445a7f17f325047f222ad3cc92bfee9ea55344a4fbc2612a54e1ba17f762",
    "spec/M5/lib/truth_protocol.json": "015ea6d9641ca5690835615e8704dc1e16e8b23edec588e0c7bc749a6a758930",
    "tests_m5/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "tests_m5/_i54.py": "024caa738f1280680bc41a5050f262162cf8f94988c3dc1196e74757bb6721e3",
    "tests_m5/_m5.py": "32f96f8b4fa27aa266ab9f4e443cc10fa5c54c8c83bae5a0fa21dceb4fde90d6",
}


def key() -> dict:
    return predictions(KEY)


def defs() -> dict:
    return key()["thresholds"]["definitions"]


def base_commit() -> str:
    return key()["thresholds"]["base_commit"]


def classification() -> dict:
    return load_json(ROOT / "spec" / "M5" / "lib" / "environment_classes.json")


def schema() -> dict:
    return load_json(ROOT / "spec" / "M5" / "lib" / "inputs.schema.json")


def holon(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, capture_output=True, text=True,
                          timeout=1800)


_BASE = {}


def base_records() -> list[dict]:
    """Every result record of M2 and M3 at the base commit."""
    if "records" not in _BASE:
        c = base_commit()
        paths = [p for m in ("M2", "M3") for p in tree_files(c, f"results/{m}/")
                 if re.fullmatch(rf"results/{m}/L_[^/]+\.json", p)]
        _BASE["records"] = [json.loads(b) for p, b in sorted(blobs(c, paths).items()) if b is not None]
        _BASE["m3"] = [json.loads(b) for p, b in sorted(blobs(c, [p for p in paths if p.startswith("results/M3/")]).items())]
    return _BASE["records"]


def base_f() -> list[str]:
    base_records()
    return sorted(r["law_id"] for r in _BASE["m3"] if r["status"] == "REFUTED"
                  and r.get("filter_bin") not in ("model_defect", "known_limitation", "intended_bounded"))


def base_dependent() -> list[str]:
    cls = classification()
    return sorted(r["law_id"] for r in base_records() if I.env_premises(r, cls))


def census_reference() -> dict:
    """The instrument's census of M3's scope at the base (rule C2)."""
    if "census" in _BASE:
        return _BASE["census"]
    c = base_commit()
    docs = [p for m in ("M2", "M3") for p in tree_files(c, f"spec/{m}/facts/") if p.endswith(".extracted.json")]
    texts = blobs(c, docs)
    src = load_json(ROOT / "config" / "holon.json")["extract"]["sources"]
    by = {}
    for p in sorted(texts):
        d = json.loads(texts[p])
        t = d["target"]
        by.setdefault((t["repo"], t["commit"]), set()).update(I.scope_paths([texts[p].decode("utf-8")]))
    repos, clauses = {}, []
    for (repo, commit), paths in sorted(by.items()):
        checkout = Path(src[repo])
        got = blobs(commit, sorted(paths), cwd=checkout)
        files = sorted(p for p, b in got.items() if b is not None)
        repos[repo] = {"commit": commit, "files": files, "unresolved": sorted(p for p, b in got.items() if b is None)}
        for p in files:
            clauses += I.census_of(p, got[p].decode("utf-8"))
    out = {"repos": repos, "clauses": sorted(clauses, key=lambda x: (x["file"], x["lines"], x["id"]))}
    _BASE["census"] = out
    return out


class TestPreregistration(unittest.TestCase):
    def test_instruments_are_the_preregistered_ones(self):
        self.assertTrue(PINNED, "PINNED is empty")
        for p, h in sorted(PINNED.items()):
            self.assertEqual(file_sha256(ROOT / p), h, p)
        self.assertEqual(sorted(PINNED), sorted(key()["thresholds"]["instruments"]))

    def test_key_holds_the_definitions(self):  # D1
        d = defs()
        self.assertEqual(sorted(d), ["L10", "L6", "L9", "common", "controls"])
        c = d["common"]
        self.assertEqual(c["min_n"], I.MIN_N)
        self.assertEqual((d["L9"]["K"], d["L9"]["slice_min_n"], d["L9"]["slice_accuracy"]),
                         (I.K, I.SLICE_MIN_N, I.SLICE_ACCURACY))
        t6, t9, t10 = d["L6"]["thresholds"], d["L9"]["thresholds"], d["L10"]["thresholds"]
        self.assertEqual((t6["decided"]["value"], t6["controls_decided_accuracy"]["value"],
                          t6["controls_strict_accuracy"]["value"], t6["corpus_decided_accuracy"]["value"]),
                         (0.5, 0.8, 0.75, 0.8))
        self.assertEqual((t9["coverage"]["value"], t9["base_coverage"]["value"]), (0.25, 0.1))
        self.assertEqual(t9["validated_categories"]["value"], ["da", "fetcher", "l1_chain"])
        self.assertEqual((t10["coverage"]["value"], t10["precision"]["value"], t10["review"]["value"],
                          t10["control_recall"]["value"]), (0.3, 0.8, 0.9, 0.75))
        self.assertEqual(sorted(d["L6"]["validity"]), [f"V{i}" for i in range(1, 9)])
        self.assertEqual(sorted(d["L9"]["validation"]), [f"R{i}" for i in range(1, 7)])
        self.assertEqual(sorted(d["L10"]["validity"]), ["W1", "W2", "W3"])
        self.assertEqual(tuple(d["controls"]["game_families"]), I.GAME_FAMILIES)
        self.assertEqual(tuple(d["controls"]["intent_families"]), I.INTENT_FAMILIES)
        self.assertEqual(classification()["categories"], list(I.CATEGORIES))

    def test_preregistration_file(self):  # D2
        p = ROOT / "spec" / "M5" / "preregistration.json"
        doc = load_json(p)
        self.assertEqual(doc["key"], KEY)
        self.assertEqual(doc["definitions"], defs())
        self.assertEqual(doc["base"]["commit"], base_commit())
        self.assertEqual(doc["instruments"], {q: file_sha256(ROOT / q) for q in key()["thresholds"]["instruments"]})
        self.assertEqual(p.read_text(encoding="utf-8"), dumps(doc))
        r = holon("m5", "prereg", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_base_populations(self):  # D2, I54-R1, I54-R2
        doc = load_json(ROOT / "spec" / "M5" / "preregistration.json")
        f = base_f()
        self.assertEqual(len(f), 49)
        self.assertEqual(doc["base"]["l6_findings"], f)
        dep = base_dependent()
        self.assertEqual(len(dep), 222)
        self.assertEqual(doc["base"]["l9_dependent"], dep)
        out = I.l9({"records": base_records(), "classification": classification(), "modules": [],
                    "observation_sets": [], "sensitivity": [], "base_dependent": dep})
        self.assertEqual(out["coverage"]["numerator"], 0)
        self.assertEqual(out["unclassified"], [])
        self.assertEqual(out["by_category"]["l1_chain"]["forms"], {"axiom": 4, "havoc": 222})


class TestControls(unittest.TestCase):
    def test_controls_are_the_instruments(self):  # K1
        base = ROOT / "spec" / "M5" / "controls"
        games, intents = I.game_controls(), I.intent_controls()
        self.assertEqual((len(games), len(intents)), (14, 12))
        self.assertEqual(sorted(p.name for p in (base / "games").iterdir()), sorted(g["id"] + ".json" for g in games))
        for g in games:
            self.assertEqual((base / "games" / (g["id"] + ".json")).read_text(encoding="utf-8"), dumps(g), g["id"])
        want = sorted([c["id"] + ".json" for c in intents] + [c["id"] + ".sol" for c in intents])
        self.assertEqual(sorted(p.name for p in (base / "intent").iterdir()), want)
        for c in intents:
            self.assertEqual((base / "intent" / (c["id"] + ".json")).read_text(encoding="utf-8"), dumps(c), c["id"])
            self.assertEqual((base / "intent" / (c["id"] + ".sol")).read_text(encoding="utf-8"), c["source"], c["id"])
        r = holon("m5", "controls", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_truth_is_recomputed(self):  # K2
        for g in I.game_controls():
            bare = {k: v for k, v in g.items() if k != "truth"}
            self.assertEqual(I.game_truth(bare), g["truth"], g["id"])
        solve = holon_module("holon.m5.controls").game_truth
        for g in I.game_controls():
            self.assertEqual(solve({k: v for k, v in g.items() if k != "truth"}), g["truth"], g["id"])

    def test_family_truths(self):  # K3
        want = {"free_trigger": "rational", "profit": "rational", "recoup": "rational", "deep": "rational",
                "trusted_only": "irrational", "costly": "irrational", "incomparable": "UNKNOWN"}
        for g in I.game_controls():
            self.assertEqual(g["truth"]["verdict"], want[g["family"]], g["id"])
            if g["family"] == "deep":
                self.assertGreater(g["truth"]["depth"], g["horizon"])
                self.assertLessEqual(len(g["witness"]), g["horizon"])
            if g["family"] == "recoup":
                self.assertGreater(g["truth"]["depth"], len(g["witness"]))
        for c in I.intent_controls():
            self.assertEqual(c["truth"]["obstruction"], "_wrong_" in c["id"], c["id"])

    def test_no_module_names_a_control(self):  # K4
        toks = set()
        for g in I.game_controls():
            toks.add(g["id"])
            toks.update(a["id"] for a in g["actors"])
            toks.update(a["id"] for a in g["actions"])
            toks.update(g["assets"])
            toks.update(g["vars"])
        for c in I.intent_controls():
            toks.add(c["id"])
            toks.add(c["file"][:-4])
        pat = re.compile(r"\b(" + "|".join(sorted(map(re.escape, toks))) + r")\b")
        hits = []
        for p in sorted((ROOT / "holon").rglob("*")):
            rel = p.relative_to(ROOT).as_posix()
            if p.is_file() and p.suffix in (".py", ".mjs", ".js", ".json") and rel != "holon/m5/controls.py":
                m = pat.search(p.read_text(encoding="utf-8", errors="replace"))
                if m:
                    hits.append(f"{rel}: {m.group(0)}")
        self.assertEqual(hits, [])


SOL_FIXTURE = """pragma solidity 0.8.24;
/**
 * @title A fixture.
 * @notice The value must not exceed the cap. It is stored once.
 * @dev Reverts when called twice; anyone may read it.
 */
contract F {
    /// @param x The new value, which should be at most 10.
    /// @return ok Always true.
    function set(uint256 x) external returns (bool ok) {}
    /** @dev Only the owner. */
    function own() external {}
    // must is not a doc comment here.
}
"""
GO_FIXTURE = """package f

// Get returns the value. It must not be called
// before Init; callers should check the error.
//
// Deprecated: never use this.
func Get() int { return 0 }

// a free comment that must be ignored

var x = 1
// T only holds positive numbers.
type T int
"""


class TestCensus(unittest.TestCase):
    def test_census_rule(self):  # C1
        census_of = holon_module("holon.m5.census").census_of
        cases = [("F.sol", SOL_FIXTURE), ("f.go", GO_FIXTURE)] + [(c["file"], c["source"])
                                                                  for c in I.intent_controls()]
        for path, text in cases:
            self.assertEqual(census_of(path, text), I.census_of(path, text), path)
        texts = [c["text"] for c in I.census_of("F.sol", SOL_FIXTURE)]
        self.assertEqual(texts, ["@notice The value must not exceed the cap.",
                                 "@dev Reverts when called twice;",
                                 "@param x The new value, which should be at most 10.",
                                 "@return ok Always true.",
                                 "@dev Only the owner."])
        self.assertEqual([c["text"] for c in I.census_of("f.go", GO_FIXTURE)],
                         ["It must not be called before Init;", "callers should check the error.",
                          "Deprecated: never use this.", "T only holds positive numbers."])

    def test_census_base(self):  # C2
        p = ROOT / "results" / "M5" / "l10_census_base.json"
        want = census_reference()
        self.assertEqual(p.read_text(encoding="utf-8"), dumps(want))
        r = holon("m5", "census", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for c in want["clauses"]:
            self.assertFalse(validate(c, dict(schema(), **schema()["$defs"]["census_clause"])), c["id"])


def _same(test, got, want, what):
    test.assertEqual(json.loads(json.dumps(got, sort_keys=True)), json.loads(json.dumps(want, sort_keys=True)), what)


class TestMetrics(unittest.TestCase):
    def test_l6(self):  # M6
        l6 = holon_module("holon.m5.metrics").l6
        for e in ("honest", "rational", "irrational", "bounded", "trigger_payoff"):
            inp = I.fixture_l6(e)
            _same(self, l6(inp), I.l6(inp), e)
        out = I.l6(I.fixture_l6("honest"))
        self.assertEqual(out["invalid"], {"f4": ["V1"], "f5": ["V4"], "f6": ["one_record"], "f7": ["V6"],
                                          "f8": ["V8"]})
        self.assertEqual((out["decided"]["numerator"], out["decided"]["denominator"]), (3, 9))
        self.assertEqual(out["corpus"]["false_rational"], ["c3"])
        r = I.l6(I.fixture_l6("rational"))
        self.assertEqual(r["controls"]["false_rational"], ["g_costly_1", "g_costly_2", "g_trusted_only_1",
                                                          "g_trusted_only_2"])
        self.assertEqual(r["thresholds"]["controls_beats_majority"], "misses")
        self.assertEqual(r["thresholds"]["controls_strict_accuracy"], "misses")
        self.assertEqual(I.l6(I.fixture_l6("bounded"))["controls"]["false_irrational"], ["g_deep_1", "g_deep_2"])
        self.assertEqual(I.l6(I.fixture_l6("trigger_payoff"))["controls"]["false_irrational"],
                         ["g_recoup_1", "g_recoup_2"])
        for e in ("rational", "irrational", "bounded", "trigger_payoff"):
            self.assertEqual(I.l6(I.fixture_l6(e))["overall"], "misses", e)
        clean = I.fixture_l6_clean()
        _same(self, l6(clean), I.l6(clean), "clean")
        self.assertEqual(I.l6(clean)["overall"], "meets")

    def test_l9(self):  # M9
        l9 = holon_module("holon.m5.metrics").l9
        cls = classification()
        for v in ("honest", "circular", "one_class", "unpinned", "drop"):
            inp = I.fixture_l9(cls, v)
            _same(self, l9(inp), I.l9(inp), v)
        rules = lambda v: I.l9(I.fixture_l9(cls, v))["modules"]["m_win"]["rules"]  # noqa: E731
        self.assertTrue(all(rules("honest").values()))
        self.assertFalse(rules("circular")["R1"])
        self.assertFalse(rules("one_class")["R5"])
        self.assertFalse(rules("unpinned")["R6"])
        h, d = I.l9(I.fixture_l9(cls, "honest")), I.l9(I.fixture_l9(cls, "drop"))
        self.assertEqual(h["coverage"]["denominator"], d["coverage"]["denominator"])
        self.assertEqual(d["base_dropped"], ["r2"])
        self.assertEqual(h["unclassified"], ["A-new-thing"])
        self.assertEqual(h["sensitivity"]["counted"], ["r1"])
        self.assertEqual(h["sensitivity"]["unreplayed"], ["r2"])
        clean = I.fixture_l9_clean(cls)
        _same(self, l9(clean), I.l9(clean), "clean")
        self.assertEqual(I.l9(clean)["overall"], "meets")

    def test_l10(self):  # M10
        l10 = holon_module("holon.m5.metrics").l10
        for v in ("honest", "few_atoms", "self_review", "weak"):
            inp = I.fixture_l10(v)
            _same(self, l10(inp), I.l10(inp), v)
        h, f = I.l10(I.fixture_l10("honest")), I.l10(I.fixture_l10("few_atoms"))
        self.assertEqual(h["census"], f["census"])
        self.assertEqual(h["overall"], "meets")
        self.assertEqual(I.l10(I.fixture_l10("self_review"))["coverage"]["numerator"], 0)
        self.assertEqual(I.l10(I.fixture_l10("weak"))["thresholds"]["control_recall"], "misses")
        for v in ("few_atoms", "self_review", "weak"):
            self.assertEqual(I.l10(I.fixture_l10(v))["overall"], "misses", v)

    def test_base_metrics(self):  # B1
        p = ROOT / "results" / "M5" / "definitions_base.json"
        cls = classification()
        dep = base_dependent()
        f = base_f()
        want = {
            "L6": I.l6({"population": f, "expect": {}, "records": [], "controls": I.game_controls(),
                        "corpus_truth": None, "corpus_expect": {}}),
            "L9": I.l9({"records": base_records(), "classification": cls, "modules": [], "observation_sets": [],
                        "sensitivity": [], "base_dependent": dep}),
            "L10": {"census": len(census_reference()["clauses"])},
            "base_commit": base_commit(),
        }
        self.assertEqual(p.read_text(encoding="utf-8"), dumps(want))
        self.assertEqual(want["L6"]["decided"]["numerator"], 0)
        r = holon("m5", "metrics", "--base", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_metrics_cli(self):  # B1
        with tempfile.TemporaryDirectory() as d:
            inp = {"L6": I.fixture_l6_clean(), "L9": I.fixture_l9_clean(classification()), "L10": I.fixture_l10()}
            (Path(d) / "in.json").write_text(json.dumps(inp), encoding="utf-8")
            r = holon("m5", "metrics", "--inputs", str(Path(d) / "in.json"), "--out", str(Path(d) / "out.json"))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            got = json.loads((Path(d) / "out.json").read_text(encoding="utf-8"))
        _same(self, got, {"L6": I.l6(inp["L6"]), "L9": I.l9(inp["L9"]), "L10": I.l10(inp["L10"])}, "cli")

    def test_fixture_records_validate(self):  # S1
        s = schema()
        sub = lambda name: dict(s, **s["$defs"][name])  # noqa: E731
        probs = []
        for inp in [I.fixture_l6(e) for e in ("honest", "bounded")] + [I.fixture_l6_clean()]:
            probs += [r["finding"] + str(validate(r, sub("game_record"))) for r in inp["records"]
                      if validate(r, sub("game_record"))]
        probs += [g["id"] for g in I.game_controls() if validate(g, sub("game_control"))]
        probs += [c["id"] for c in I.intent_controls() if validate(c, sub("intent_control"))]
        cls = classification()
        for inp in [I.fixture_l9(cls, "honest"), I.fixture_l9_clean(cls)]:
            probs += [m["id"] for m in inp["modules"] if validate(m, sub("module_record"))]
            probs += [o["set"] for o in inp["observation_sets"] if validate(o, sub("observation_set"))]
            probs += [p["law"] for p in inp["sensitivity"] if validate(p, sub("sensitivity_pair"))]
            probs += [r["law_id"] for r in inp["records"] if "environment" in r
                      and validate(r["environment"], sub("environment_block"))]
        inp = I.fixture_l10()
        probs += [c["id"] for c in inp["census"] if validate(c, sub("census_clause"))]
        probs += [a["id"] for a in inp["atomized"] if validate(a, sub("atom_clause"))]
        probs += [lw["law"] for lw in inp["laws"] if validate(lw, sub("intent_law"))]
        self.assertEqual(probs, [])


class TestPredictions(unittest.TestCase):
    def census(self) -> dict:
        return load_json(ROOT / "results" / "M5" / "l10_census_base.json")

    def test_p1_census_size(self):
        self.assertTrue(100 <= len(self.census()["clauses"]) <= 1000, len(self.census()["clauses"]))

    def test_p2_census_largest_file(self):
        n = {}
        for c in self.census()["clauses"]:
            n[c["file"]] = n.get(c["file"], 0) + 1
        top = max(n.values())
        self.assertEqual([f for f, k in n.items() if k == top], ["contracts/contracts/l1/rollup/Rollup.sol"], n)

    def test_p3_census_go_share(self):
        cl = self.census()["clauses"]
        self.assertGreaterEqual(sum(1 for c in cl if c["file"].endswith(".go")) / len(cl), 0.25)


if __name__ == "__main__":
    unittest.main()
