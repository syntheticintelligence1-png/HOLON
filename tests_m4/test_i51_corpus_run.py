"""I51: HOLON on the corpus pre-fix commits (key I51, spec/M4/predictions.json; BUILD_PLAN §4 I51; whitepaper §13
"Corpus", "Metrics": recall per rule, precision split into true defects, intended asymmetries and model defects;
docs/HUMAN_ANSWERS.md Q19: no hand-written facts, unreachable components are coverage debt, and the lead's guidance
that the corpus tests generality beyond rollups). This docstring is the contract that this file checks.

Instruments fixed at the prereg, each pinned by its sha256 in PINNED below (a later edit is a change of this file, so it
needs an amendment): tests_m4/_i51.py (rules S1-S6 and H7 written out a second time, independently of holon/),
tests_m4/_i48.py and tests_m4/_m4.py (I48's clones and git helpers, reused unchanged), spec/M4/lib/i51_run.json (the run
protocol: clone, generated extraction inputs, scratch milestone, generic rule sidecars, timeouts, what is committed),
and the corpus spec/eval/corpus.json with its labels (I48's, read, never written). The test process never imports a
holon module: holon runs in child processes.

What the plan asks
  BUILD_PLAN I51: run extraction, rules, replay and filtering on every corpus pre-fix commit, then compute per-rule
  recall and precision (true defects, intended asymmetries, model defects). Exit: results/eval/holon/corpus.json has a
  row for every entry, with "not run" only for extraction failures that carry a reason. Risk: extraction gaps on foreign
  codebases are misses, never exclusions; a frontend HOLON lacks is a reasoned miss, never a hand-written fact.

The tool
  python -m holon eval holon [--root DIR] [--entries ID,ID,..] [--check]
  writes results/eval/holon/corpus.json and results/eval/holon/<id>/ for every entry (or the named ones, the other rows
  kept as committed), and results/eval/holon/corpus_timing.json (seconds only, compared by nothing). --check writes
  nothing: it reruns the named entries (default all) in scratch and exits 0 iff every byte of their rows and of their
  <id>/ directories equals the committed ones.

Rules (holon/eval/holon_run.py; tests_m4/_i51.py writes S1-S6 and H7 again)
  H0 Inputs. The corpus manifest and the protocol only; the public repositories the manifest names, cloned into
     ~/.holon/eval/repos (never inside the repository); a repository under an excluded_repos pattern of
     spec/M4/lib/corpus_protocol.json (the sealed and the development target) is never cloned. No fact, law, sidecar
     or proof is written by hand: every input of every stage is generated from the entry and the protocol.
  H1 Checkout. A detached worktree at the entry's prefix_commit; the row records its tree (prefix^{tree}).
  H2 Extraction (protocol solidity and go). Every .sol file: one transitions sidecar per declared contract, extracted by
     `holon extract solidity` with the pinned solc 0.8.24, no dependency tree and no commit interface. Every .go file:
     its package (nearest go.mod), one holon-go-frontend/0.3 config with no primitives, extracted by `holon extract go`.
     A failure is recorded with its exit code and its normalized message (protocol normalize), never retried with
     changed inputs.
  H3 Rules. In a scratch root (a copy of holon/, config/ with sol_deps null, and the spec inputs the pipeline reads) the
     transitions documents form test milestone T510 with generated typed-sorts, DISCH, UNDO and FACT sidecars (protocol
     typed, disch, undo, fact); then holon sorts, types, model, disch and derive --catalog holon-rules/1.15, in that
     order, each stage's exit and message recorded; a stage that fails ends the entry's pipeline there. A Go document
     derives nothing (protocol go_rules_doc): stage derive is no_producer when the entry has no transitions document.
  H4 Decision. holon run over the milestone, then holon run --laws over every law still without a record; each law's
     status is its record's (PROVED, REFUTED or UNKNOWN), or UNKNOWN with reason not_decided when no record exists.
  H5 Replay and filter. No deployment of a foreign contract is generated (binding null), so no witness replays; the
     row records each REFUTED law's replay status as its record holds it.
  H6 Committed artifacts (protocol commit): sidecars/, facts/, laws/, gen/, records/ under results/eval/holon/<id>/;
     a stored document's bytes have the sha256 its row names.
  H7 Evidence. Every REFUTED law of a row has its record (status REFUTED) and its counter-law: Bend re-checks the
     committed proof in a scratch copy (ALL PROOFS CHECK) and the laws file names the counter-law.
  H8 Rows. corpus.json is {run_version, corpus_sha256, protocol_sha256, holon_sha256, toolchain, rows, summary}; one row
     per corpus entry in corpus order: {id, system, repo, prefix_commit, fix_commit, label, files, tree, status,
     reason, stages, documents, laws, locus, label_rule_laws, detected, detected_any}. status is "run", or "not_run"
     exactly when no document of the entry was extracted, and then reason is a non-empty string naming every failure.
     Every law of laws/ is in the row's laws with {law_id, rule, subform, status, sites, localized, replay, class}.
  H9 Determinism. Sorted iteration, no timestamps, no random seed (the searches are deterministic); --check reproduces.

Scoring (both holon_run.py and _i51.py)
  S1 Locus. For every entry file, the old-side intervals of `git diff -U0 prefix fix -- file`: a hunk -a,b with b > 0
     is [a, a+b-1]; a pure insertion (b = 0) is [max(a,1), a+1]; merged when they overlap or touch.
  S2 Sites of a law. Every span <file>:<a>[-<b>] naming an entry file in the law, its DERIVATION entry and its record,
     plus the src span of every action of the law's facts document that the record's witness steps name.
  S3 Localized: some site meets some locus interval of the same file.
  S4 Class of a finding (a REFUTED law): replay failed: model_defect; else localized: true_defect; else replay passed:
     intended_asymmetry; else unreplayed.
  S5 Detection. detected: some REFUTED, localized law of the entry's label rule; detected_any: of any rule. An entry
     labelled none counts in no recall. label_rule_laws: the number of derived laws of the label rule (any status).
  S6 Summary. recall per label rule present (entries, detected ids, detected / entries); detected_any ids; findings and
     their class counts; precision = true_defect / findings (null when there is no finding). c13 is flagged by I48 (its
     recorded fix is not the defect's fix) and is kept, never excluded; the report also gives PAR's recall without it.

Predictions (counted; spec/M4/predictions.json key I51; outcomes recorded nowhere before the run)
  P1 No entry is detected: detected is false for all 20 (the per-entry table is the key's expected.detected).
  P2 Extraction reach: c17 extracts at least one document; c02, c05, c10, c15 and c20 (the other Solidity entries) and
     c01, c07 and c12 (the Go entries of the same system as c17) extract none; at least 7 of the other 11 Go entries
     extract at least one document.
  P3 No entry derives a law of its own label rule (label_rule_laws is 0 in every row).
  P4 Every finding, if there is any, is unreplayed: true_defect, intended_asymmetry and model_defect counts are all 0.
Regressions and construction checks: R1 the exit (a row per entry, not_run only with a reason, H8); R2 the rows are the
corpus's and their trees the instrument's (H1); R3 the scoring is the instrument's (S1-S6) and can fail; R4 the evidence
(H6, H7); R5 determinism (--check on a subset); R6 nothing in M0-M3 changes and holon/eval/ names no corpus system,
enters no generator closure and imports no test module.

A miss is a Surprise, never a reason to edit anything. These tests need the network (clones) and the toolchain; a
missing one is a failure, never a skip.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from tests_m4 import _i51 as I
from tests_m4._m4 import ROOT, load_json, predictions, run_holon

KEY = "I51"
BASE = "7dc50894695b7c37c9a3ec4f2d1d5bfcdfcc545c"   # I47's head, the commit I51 is stacked on
PINNED = {
    "tests_m4/_i51.py": None,
    "tests_m4/_i48.py": None,
    "tests_m4/_m4.py": None,
    "spec/M4/lib/i51_run.json": None,
    "spec/eval/corpus.json": None,
}
ROW_KEYS = sorted(["id", "system", "repo", "prefix_commit", "fix_commit", "label", "files", "tree", "status", "reason",
                   "stages", "documents", "laws", "locus", "label_rule_laws", "detected", "detected_any"])
LAW_KEYS = sorted(["law_id", "rule", "subform", "status", "sites", "localized", "replay", "class"])
STATUSES = ("PROVED", "REFUTED", "UNKNOWN")
M03 = ("laws/M0/", "laws/M1/", "laws/M2/", "laws/M3/", "results/M0/", "results/M1/", "results/M2/", "results/M3/",
       "gen/M0/", "gen/M1/", "gen/M2/", "gen/M3/", "spec/M1/", "spec/M2/", "spec/M3/", "facts/", "replay/", "tests/",
       "tests_m1/", "tests_m2/", "tests_m3/", "spec/eval/", "gen/eval/")


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def key() -> dict:
    return predictions(KEY)


def need(p: Path):
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing (run python -m holon eval holon)")
    return load_json(p)


def rows() -> list[dict]:
    return need(I.ROWS)["rows"]


def row_map() -> dict[str, dict]:
    return {r["id"]: r for r in rows()}


def git(*args) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()} (needs the real checkout's history)")
    return p.stdout


class TestInstruments(unittest.TestCase):
    def test_instruments_are_the_preregistered_ones(self):
        """Every instrument has the sha256 the key pins (thresholds.instrument_sha256)."""
        pins = key()["thresholds"]["instrument_sha256"]
        self.assertEqual(sorted(pins), sorted(PINNED))
        for rel, want in sorted(pins.items()):
            self.assertEqual(sha(ROOT / rel), want, rel)

    def test_protocol_names_no_corpus_system(self):
        """The protocol is generic: no system, repository owner or repository name of the corpus occurs in it."""
        text = (ROOT / "spec/M4/lib/i51_run.json").read_text().lower()
        for w in sorted(corpus_words()):
            self.assertIsNone(re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", text), w)

    def test_hunk_rule_examples(self):
        """S1 on synthetic hunks (the instrument's own rule)."""
        d = "@@ -3,2 +3,1 @@\n@@ -10,0 +10,2 @@\n@@ -0,0 +1,1 @@\n@@ -11 +12 @@\n"
        self.assertEqual(I.hunk_lines(d), [[1, 1], [3, 4], [10, 11]])


def corpus_words() -> set[str]:
    out = set()
    for e in I.entries():
        out.add(e["system"].lower())
        m = re.fullmatch(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?", e["repo"])
        out.update({m.group(1).lower(), m.group(2).lower()})
    return out


class TestRows(unittest.TestCase):
    def test_a_row_for_every_entry(self):
        """I51-R1 (the exit, H8): one row per corpus entry in corpus order, with the row keys; status run, or not_run
        exactly when no document was extracted, then with a non-empty reason."""
        doc = need(I.ROWS)
        self.assertEqual(sorted(doc), sorted(["run_version", "corpus_sha256", "protocol_sha256", "holon_sha256",
                                              "toolchain", "rows", "summary"]))
        self.assertEqual(doc["corpus_sha256"], sha(I.CORPUS))
        self.assertEqual(doc["protocol_sha256"], sha(I.PROTOCOL))
        self.assertEqual([r["id"] for r in doc["rows"]], [e["id"] for e in I.entries()])
        for r in doc["rows"]:
            with self.subTest(entry=r["id"]):
                self.assertEqual(sorted(r), ROW_KEYS)
                extracted = [d for d in r["documents"] if d["status"] == "extracted"]
                self.assertIn(r["status"], ("run", "not_run"))
                self.assertEqual(r["status"] == "not_run", not extracted)
                if r["status"] == "not_run":
                    self.assertIsInstance(r["reason"], str)
                    self.assertTrue(r["reason"].strip())
                    self.assertEqual(r["laws"], [])
                    self.assertTrue(r["documents"], "a not_run row lists the documents that failed")
                    for d in r["documents"]:
                        self.assertTrue(isinstance(d.get("reason"), str) and d["reason"].strip(), d)

    def test_rows_are_the_corpus(self):
        """I51-R2: every row's inputs are its corpus entry's, and its label is I48's final label."""
        for e, r in zip(I.entries(), rows()):
            with self.subTest(entry=e["id"]):
                for k in ("id", "system", "repo", "prefix_commit", "fix_commit", "label", "files"):
                    self.assertEqual(r[k], e[k], k)

    def test_trees_are_the_instruments(self):
        """I51-R2 (H1): the recorded tree is prefix^{tree} in the instrument's own clone."""
        for e, r in zip(I.entries(), rows()):
            with self.subTest(entry=e["id"]):
                self.assertEqual(r["tree"], I.prefix_tree(e))

    def test_laws_are_the_derived_ones(self):
        """I51-R4 (H3, H4, H8): a row's laws are exactly the L*.json of its laws/ (DERIVATION's, rule and subform
        theirs) and each status is its record's, or UNKNOWN when it has none."""
        for r in rows():
            with self.subTest(entry=r["id"]):
                d = I.OUT / r["id"]
                files = sorted(p.stem for p in (d / "laws").glob("L*.json")) if (d / "laws").is_dir() else []
                self.assertEqual([x["law_id"] for x in r["laws"]], files)
                if files:
                    der = {x["law_id"]: x for x in load_json(d / "laws" / "DERIVATION.json")["laws"]}
                    self.assertEqual(sorted(der), files)
                for x in r["laws"]:
                    self.assertEqual(sorted(x), LAW_KEYS)
                    law = load_json(d / "laws" / f"{x['law_id']}.json")
                    self.assertEqual((x["rule"], x["subform"]), (law["rule"], law["subform"]))
                    rp = d / "records" / f"{x['law_id']}.json"
                    want = load_json(rp)["status"] if rp.is_file() else "UNKNOWN"
                    self.assertIn(x["status"], STATUSES)
                    self.assertEqual(x["status"], want)

    def test_documents_are_committed(self):
        """I51-R4 (H6): every extracted document a row stores is under facts/ with the sha256 the row names."""
        for r in rows():
            for dd in r["documents"]:
                if dd["status"] == "extracted" and dd.get("stored"):
                    with self.subTest(entry=r["id"], doc=dd["stem"]):
                        self.assertEqual(sha(I.OUT / r["id"] / "facts" / dd["file"]), dd["sha256"])


class TestScoring(unittest.TestCase):
    def test_locus_is_the_instruments(self):
        """I51-R3 (S1)."""
        for e, r in zip(I.entries(), rows()):
            with self.subTest(entry=e["id"]):
                self.assertEqual(r["locus"], I.locus(e))

    def test_sites_localization_and_class(self):
        """I51-R3 (S2-S4): each law's sites, localized and class are the instrument's."""
        for r in rows():
            d = I.OUT / r["id"]
            for x in r["laws"]:
                with self.subTest(entry=r["id"], law=x["law_id"]):
                    s = I.sites(x["law_id"], d, r["files"])
                    self.assertEqual(x["sites"], s)
                    self.assertEqual(x["localized"], I.localized(s, r["locus"]))
                    if x["status"] == "REFUTED":
                        rec = load_json(d / "records" / f"{x['law_id']}.json")
                        self.assertEqual(x["replay"], (rec.get("replay") or {}).get("status"))
                        self.assertEqual(x["class"], I.finding_class(rec, x["localized"]))
                    else:
                        self.assertIsNone(x["class"])

    def test_detection_and_summary(self):
        """I51-R3 (S5, S6): detected, detected_any, label_rule_laws and the summary are the instrument's."""
        rs = rows()
        for r in rs:
            with self.subTest(entry=r["id"]):
                self.assertEqual((r["detected"], r["detected_any"]), I.detected(r))
                self.assertEqual(r["label_rule_laws"], sum(1 for x in r["laws"] if x["rule"] == r["label"]))
        self.assertEqual(need(I.ROWS)["summary"], I.score(rs))

    def test_scoring_can_fail(self):
        """I51-R3: planted rows turn the instrument's verdict: a localized REFUTED law of the label rule is a
        detection; the same law of another rule, unlocalized or PROVED is not; a failed replay is a model defect."""
        base = {"id": "x", "label": "DISCH", "laws": []}
        law = {"rule": "DISCH", "status": "REFUTED", "localized": True, "class": "true_defect"}
        self.assertEqual(I.detected({**base, "laws": [law]}), (True, True))
        self.assertEqual(I.detected({**base, "laws": [{**law, "rule": "SYM"}]}), (False, True))
        self.assertEqual(I.detected({**base, "laws": [{**law, "localized": False}]}), (False, False))
        self.assertEqual(I.detected({**base, "laws": [{**law, "status": "PROVED"}]}), (False, False))
        self.assertEqual(I.finding_class({"replay": {"status": "failed"}}, True), "model_defect")
        self.assertEqual(I.finding_class({"replay": {"status": "passed"}}, False), "intended_asymmetry")
        self.assertEqual(I.finding_class({"replay": {"status": "not_applicable"}}, False), "unreplayed")
        self.assertTrue(I.localized([["a.sol", 5, 9]], {"a.sol": [[9, 12]]}))
        self.assertFalse(I.localized([["a.sol", 5, 8]], {"a.sol": [[9, 12]]}))
        self.assertFalse(I.localized([["b.sol", 9, 9]], {"a.sol": [[9, 12]]}))
        s = I.score([{**base, "detected": True, "detected_any": True, "laws": [law]}])
        self.assertEqual((s["recall"]["DISCH"]["recall"], s["precision"]), (1.0, 1.0))


class TestEvidence(unittest.TestCase):
    def test_refuted_counter_laws_check(self):
        """I51-R4 (H7): Bend re-checks every REFUTED law's committed counter-law."""
        for r in rows():
            d = I.OUT / r["id"]
            for x in r["laws"]:
                if x["status"] != "REFUTED":
                    continue
                with self.subTest(entry=r["id"], law=x["law_id"]):
                    rec = load_json(d / "records" / f"{x['law_id']}.json")
                    self.assertEqual(rec["status"], "REFUTED")
                    ok, out = I.recheck(d, rec)
                    self.assertTrue(ok, out)


class TestDeterminism(unittest.TestCase):
    def test_check_reproduces_a_subset(self):
        """I51-R5 (H9): holon eval holon --check reproduces the rows and directories of the first not_run entry and
        the first entry with a derived law (byte for byte)."""
        rs = rows()
        pick = [r["id"] for r in rs if r["status"] == "not_run"][:1] + [r["id"] for r in rs if r["laws"]][:1]
        self.assertTrue(pick)
        p = run_holon(["eval", "holon", "--check", "--entries", ",".join(pick)], timeout=6 * 3600)
        self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-3000:])


class TestPredictions(unittest.TestCase):
    def test_p1_no_entry_is_detected(self):
        """I51-P1."""
        exp = key()["predictions"][0]["expected"]["detected"]
        self.assertEqual({r["id"]: r["detected"] for r in rows()}, exp)

    def test_p2_extraction_reach(self):
        """I51-P2."""
        ex = {r["id"]: any(d["status"] == "extracted" for d in r["documents"]) for r in rows()}
        e = key()["predictions"][1]["expected"]
        self.assertEqual([i for i in e["extracts"] if not ex[i]], [])
        self.assertEqual([i for i in e["extracts_none"] if ex[i]], [])
        self.assertGreaterEqual(sum(ex[i] for i in e["others"]), e["others_at_least"])

    def test_p3_no_label_rule_law(self):
        """I51-P3."""
        self.assertEqual({r["id"]: r["label_rule_laws"] for r in rows() if r["label_rule_laws"]}, {})

    def test_p4_findings_unreplayed(self):
        """I51-P4."""
        c = need(I.ROWS)["summary"]["classes"]
        self.assertEqual((c["true_defect"], c["intended_asymmetry"], c["model_defect"]), (0, 0, 0))


class TestRegressions(unittest.TestCase):
    def test_i51_changes_nothing_in_m0_m3(self):
        """I51-R6: no first-parent, non-merge commit of I51 (after BASE) changes a file under M03 or holon/ outside
        holon/eval/."""
        commits = git("rev-list", "--first-parent", "--no-merges", f"{BASE}..HEAD").split()
        self.assertTrue(commits)
        for c in commits:
            touched = [f for f in git("diff-tree", "--no-commit-id", "--name-only", "-r", "-z", c).split("\0") if f]
            bad = [f for f in touched if f.startswith(M03) or (f.startswith("holon/") and not f.startswith("holon/eval/"))]
            self.assertEqual(bad, [], c)

    def test_runner_names_no_corpus_system(self):
        """I51-R6 (target-agnostic): holon/eval/holon_run.py names no system, owner or repository of the corpus."""
        p = ROOT / "holon" / "eval" / "holon_run.py"
        self.assertTrue(p.is_file(), "holon/eval/holon_run.py is missing")
        text = p.read_text().lower()
        for w in sorted(corpus_words()):
            self.assertIsNone(re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", text), w)

    def test_runner_imports_no_test_module(self):
        """I51-R6 (AGENTS rule 5)."""
        p = ROOT / "holon" / "eval" / "holon_run.py"
        tree = ast.parse(p.read_text())
        bad = re.compile(r"^tests(_m[0-9]+)?(\.|$)")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse([a.name for a in node.names if bad.match(a.name)])
            elif isinstance(node, ast.ImportFrom):
                self.assertFalse(node.level == 0 and bad.match(node.module or ""), node.module)

    def test_runner_enters_no_generator_closure(self):
        """I51-R6: holon/eval/holon_run.py is in no holon-ir generator closure (M0-M3 records keep their digests)."""
        code = ("import json,sys; from pathlib import Path; import holon.records as R; "
                "print(json.dumps(sorted(set().union(*[set(R.generator_files(v, Path(sys.argv[1]))) "
                "for v in ('holon-ir/0.1','holon-ir/0.2','holon-ir/0.3')]))))")
        p = subprocess.run([os.sys.executable, "-c", code, str(ROOT)], cwd=ROOT, capture_output=True, text=True,
                           env={**os.environ, "PYTHONPATH": str(ROOT)})
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        self.assertNotIn("holon/eval/holon_run.py", json.loads(p.stdout))


if __name__ == "__main__":
    unittest.main()
