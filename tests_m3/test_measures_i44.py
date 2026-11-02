"""I44 (= I44b): Def 6.13's measures that I81 (= I44a) left pending, and the ranking over them (BUILD_PLAN row I44;
whitepaper Def 6.13, §5.3, Def 6.20, §10.10). This docstring is the contract. It extends I81's (the docstring of
tests_m3/test_ranking.py): I81's command, document, rules and policy sidecar (spec/<M>/lib/ranking.json) stand, except
where this contract replaces them.

M-NAT (replaces I81's M-NAT). Naturality defect mass, in components. The sidecar's NAT entry names the measure, its
unit, the replay sub-directory whose runs hold the model's observations, and the observation; it names no pending key.
The observation of a NAT square is its claim's (I29): the end version of each side; the success of each step the two
sides share (the k-th step of a label on one side is paired with the k-th step of that label on the other; a step
without a partner differs); and each storage word that either side's end state holds (an absent word is the zero
word). The mass counts the components on which the two sides end differently.
  REFUTED, with a bound replay: the record's witness ({square: {edge, op, left, right}, trace}) and the runs
         "<id>:left" and "<id>:right" of replay/<M>/<replay>/report.json that replay it: each run's witness_sha256 is
         the sha256 of the witness's canonical JSON (sorted keys, separators "," and ":"), and its trace is the
         witness's trace, then that side's square steps without their revert field. The model's observation of a
         side: its storage is the fold, in step order, of every step's slots (slot -> its "model" value) from the empty
         storage; a square step succeeds iff its step's "model" status is "ok"; its end version is the version of its
         last square step. kind value; value = lower = upper = the mass; certified; scope names the witness (the mass
         is the square's at the witness's state and arguments: BUILD_PLAN I44 measures it "on its witness state");
         detail {words: the differing words, sorted, each "0x" + 64 hex digits; outcomes: the labels whose success
         differs, sorted; version: whether the end versions differ; replay: the report's path}.
  REFUTED, without a bound replay: kind bound; lower = the components that differ among the end versions and the
         steps' successes as the witness's square steps record them (their version and ok); upper null; detail.words
         null.
  PROVED: kind value, value 0, certified (the kernel proved the square: its two paths agree at every state it ranges
         over).
  UNKNOWN: kind bound, lower 0, upper null (no witness; no footprint bound is computed).
  rules.NAT is computed, with the number of NAT laws, when the sidecar's NAT entry names no pending key; the
  document's pending_measures is the sidecar's list, which holds no NAT entry. The ranking is I81's: each REFUTED
  NAT law's ranking entry carries its measure's kind and value; its impact follows I81's rules unchanged. I29's
  native-gap records (gen/M3/nat/nat.json native_gaps) are not laws and get no measure entry.

Stage 2 (after I84 = I37b and I89 = I39c land on the lead). Each clause below holds at every head; before its input
lands it holds as stated for that state.
  M-FACT, public_input sub-form (I84's O23). When laws/<M> holds a FACT law of sub-form public_input, the sidecar's
         FACT subforms hold public_input and pending_measures no longer holds F(PI, parent lbn). A REFUTED
         public_input law's measure is its record's fact.measure (I84's rules): its kind, value, lower and upper,
         certified iff kind value. An UNKNOWN one: kind bound, lower 0 (no kernel-checked witness), upper its
         record's upper. While laws/<M> holds no such law, pending_measures holds F(PI, parent lbn) with key I37.
  M-DISCH. Every DISCH law's measure is kind pending, with detail.class its I32 class as in I81's M-DISCH (undecided
         for a basis element I32 never classified); its why names what the profile lacks.
  F(Z, derivation). pending_measures holds it.
  Persistence. Every REFUTED UNDO, FACT, SORT or NAT law, and every REFUTED PAR law whose claim is a versioned
         machine's init term, has persistence undecided (I81's PE3), unless a blocking law that decides its witness's
         failing check is decided (stage 2), in which case the report names the rule.

Regressions.
  R1 `holon rank --milestone M3 --check` passes, two runs write the same bytes, and the document is valid against
     spec/schemas/ranking.schema.json with every listed input current.
  R2 holon/measures.py names no law, action, register or target and imports no test code.
  R3 judged at each own commit: no law, record, generated or replay file changes except results/M3/ranking.json.
  R4 for every REFUTED NAT law, holon's mass, words, outcomes and version flag equal the instrument's own reading of
     the replay (tests_m3/_i44.py).
  R5 the stage-1 outcome commit (the first own commit that changes results/M3/ranking.json) changes, against its first
     parent's version, only: the NAT laws' measure entries and their ranking entries' measure, rules.NAT,
     pending_measures, sidecar, inputs and summary.kinds.

Own commits: the non-merge commits of `git log --first-parent <C_K>..<end>`, end the first commit adding
docs/iterations/I44.md (HEAD before it exists), along the first-parent line of the merge that brings the branch into
the lead when there is one.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests_m3 import _i44 as I
from tests_m3._m3 import ROOT, laws, predictions, records, run_holon, validate

KEY = "I44"
M = "M3"
OUT = ROOT / "results" / M / "ranking.json"
SCHEMA = ROOT / "spec" / "schemas" / "ranking.schema.json"
SIDECAR = ROOT / "spec" / M / "lib" / "ranking.json"
RANKING_REL = "results/M3/ranking.json"


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), "-c", "core.quotepath=false", *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def _is_ancestor(a: str, b: str) -> bool:
    p = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", a, b], capture_output=True, text=True)
    if p.returncode not in (0, 1):
        raise AssertionError(f"git merge-base --is-ancestor {a} {b}: {p.stderr.strip()}")
    return p.returncode == 0


def prereg_commit() -> str:
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I44 (the audit's C_K)."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(doc, dict) and KEY in (doc.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I44")


def own_commits() -> dict[str, list[str]]:
    """I44's own commits, oldest first, each with the paths it changes (the contract's own-commit rule)."""
    pre = prereg_commit()
    added = git("log", "--full-history", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--",
                "docs/iterations/I44.md").split()
    end = added[0] if added else "HEAD"
    revs = [f"{pre}..{end}"]
    if added:
        for line in git("rev-list", "--ancestry-path", "--merges", "--reverse", "--parents", f"{end}..HEAD").splitlines():
            c, *parents = line.split()
            if len(parents) > 1 and _is_ancestor(end, parents[1]) and not _is_ancestor(end, parents[0]):
                revs = [parents[1], f"^{parents[0]}", f"^{pre}"]
                break
    out: dict[str, list[str]] = {}
    for c in git("log", "--first-parent", "--no-merges", "--reverse", "--format=%H", *revs).split():
        out[c] = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--no-renames", c).split()
    return out


def doc() -> dict:
    return json.loads(OUT.read_text())


def entries() -> dict[str, dict]:
    return {e["law_id"]: e for e in doc()["ranking"]}


def nat_laws() -> dict[str, dict]:
    return {lid: law for lid, law in laws(M).items() if law.get("rule") == "NAT"}


def words_of(m: dict) -> tuple[set[int], int]:
    """(the declared slots among a NAT measure's differing words, the number of hashed words among them)."""
    ws = [int(w, 16) for w in (m.get("detail") or {}).get("words") or []]
    return {w for w in ws if w < I.DECLARED_BELOW}, sum(1 for w in ws if w >= I.DECLARED_BELOW)


# ====================================================================== M-NAT (stage 1)
class TestNat(unittest.TestCase):
    def test_p1_composition_masses(self):
        """P1: the six REFUTED composition laws' masses are the prereg's (8, 8, 7, 2, 2, 2), each kind value and
        certified at its witness: the early initializer's outcome differs, and so do exactly the predicted words."""
        ms = doc()["measures"]
        for lid, (mass, slots, hashed, labels, version) in I.NAT_EXPECTED.items():
            m = ms[lid]
            self.assertEqual((m["rule"], m["measure"], m["unit"]), ("NAT", "naturality_defect_mass", "components"), lid)
            self.assertEqual((m["kind"], m["value"], m["lower"], m["upper"], m["certified"]),
                             ("value", mass, mass, mass, True), lid)
            self.assertEqual(words_of(m), (set(slots), hashed), lid)
            self.assertEqual(m["detail"]["outcomes"], list(labels), lid)
            self.assertEqual(m["detail"]["version"], version, lid)

    def test_p2_cutover_squares(self):
        """P2: the three UNKNOWN cutover squares get kind bound, lower 0, upper null."""
        ms, rc = doc()["measures"], records(M)
        for lid in I.NAT_UNKNOWN:
            self.assertEqual(rc[lid]["status"], "UNKNOWN", lid)
            m = ms[lid]
            self.assertEqual((m["rule"], m["kind"], m["lower"], m["upper"], m["certified"]),
                             ("NAT", "bound", 0, None, False), lid)

    def test_p3_rules_and_ranking(self):
        """P3: rules.NAT is computed over the 9 NAT laws (value 6, bound 3), pending_measures holds no NAT entry, and
        each REFUTED NAT law's ranking entry carries its measure's kind and value."""
        d, nl = doc(), nat_laws()
        self.assertEqual(len(nl), 9)
        self.assertEqual(d["rules"]["NAT"], {"measure": "naturality_defect_mass", "laws": 9, "status": "computed",
                                             "pending": None})
        self.assertFalse([x for x in d["pending_measures"] if x.get("rule") == "NAT"])
        kinds: dict[str, int] = {}
        for lid in nl:
            kinds[d["measures"][lid]["kind"]] = kinds.get(d["measures"][lid]["kind"], 0) + 1
        self.assertEqual(kinds, I.NAT_KINDS)
        es = entries()
        for lid in nl:
            if records(M)[lid]["status"] == "REFUTED":
                m = d["measures"][lid]
                self.assertEqual(es[lid]["measure"], {"kind": m["kind"], "value": m["value"]}, lid)


# ====================================================================== stage 2
class TestStage2(unittest.TestCase):
    def test_p4_disch_pending(self):
        """P4: every DISCH law's measure is pending, with I32's class (detail.class) and a why."""
        d = doc()
        orders = {x for t in json.loads(SIDECAR.read_text())["persistence_order"] for x in t}
        n = 0
        for lid, m in d["measures"].items():
            if m["rule"] == "DISCH":
                n += 1
                self.assertEqual(m["kind"], "pending", lid)
                self.assertIn(m["detail"]["class"], orders, lid)
                self.assertTrue(m["why"], lid)
        self.assertGreaterEqual(n, 35)

    def test_p5_public_input(self):
        """P5: with I84's public_input laws present, M-FACT gives the prereg's values (F(PI, parent lbn) = 64 bits,
        a value) and pending_measures drops F(PI, parent lbn); before I84 lands, it is pending I37."""
        d, lw = doc(), laws(M)
        pi = {lid for lid, law in lw.items() if law.get("rule") == "FACT" and law.get("subform") == "public_input"}
        pend = {x["pair"]: x for x in d["pending_measures"]}
        if not pi:
            self.assertEqual(pend.get(I.PI_PAIR, {}).get("key"), "I37")
            return
        self.assertNotIn(I.PI_PAIR, pend)
        self.assertEqual(pi, set(I.PUBLIC_INPUT))
        for lid, (kind, value, lower, upper) in I.PUBLIC_INPUT.items():
            m = d["measures"][lid]
            self.assertEqual((m["kind"], m["value"], m["lower"], m["upper"]), (kind, value, lower, upper), lid)
            self.assertEqual(m["certified"], kind == "value", lid)
        self.assertEqual(d["measures"][I.PI_LAW]["value"], 64.0)

    def test_p6_fz_pending(self):
        """P6: F(Z, derivation) stays pending."""
        self.assertIn(I.Z_PAIR, {x["pair"] for x in doc()["pending_measures"]})

    def test_p7_persistence(self):
        """P7: every REFUTED UNDO, FACT, SORT and NAT law, and every REFUTED PAR-init law, has persistence undecided."""
        lw, es = laws(M), entries()
        for lid, e in es.items():
            law = lw[lid]
            term = law["statement"]["claim"]["eq"][0]
            if law.get("rule") in I.PERSISTENCE_RULES or (law.get("rule") == "PAR" and isinstance(term, dict)
                                                         and "init" in term):
                self.assertEqual(e["impact"]["persistence"]["class"], "undecided", lid)


# ====================================================================== regressions and construction
class TestRegressions(unittest.TestCase):
    def test_r1_command_and_document(self):
        """R1: `holon rank --check` passes; two runs agree byte for byte; the document is valid and its inputs current."""
        import hashlib
        p = run_holon(["rank", "--milestone", M, "--check"], timeout=600)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t) / "a.json", Path(t) / "b.json"
            for out in (a, b):
                p = run_holon(["rank", "--milestone", M, "--out", str(out)], timeout=600)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertEqual(a.read_bytes(), b.read_bytes())
        d = doc()
        self.assertEqual(validate(d, SCHEMA), [])
        for x in d["inputs"]:
            self.assertEqual(hashlib.sha256((ROOT / x["path"]).read_bytes()).hexdigest(), x["sha256"], x["path"])
        self.assertIn(f"replay/{M}/nat/report.json", [x["path"] for x in d["inputs"]])

    def test_r2_no_target_vocabulary(self):
        """R2: holon/measures.py names no law, action, register or target and imports no test code."""
        bad = ["L_par_", "L_undo_", "L_fact_", "L_disch_", "L_sort_", "L_pinit", "L_nat_", "Rollup", "commitBatch",
               "revertBatch", "batchBlobVersionedHashes", "contracts/", "morph", "Morph", "onlyOwner",
               "onlyActiveSubmitter", "onlyChallenger", "initialize", "rollupDelayPeriod", "committedStateRoots",
               "submitterContract", "batchDataStore", "proveState", "challengeState", "LastBlockNumber"]
        text = (ROOT / "holon" / "measures.py").read_text()
        for b in bad:
            self.assertNotIn(b, text, f"holon/measures.py holds {b!r}")
        self.assertIsNone(re.search(r"(?m)^\s*(from|import)\s+tests", text))

    def test_r3_nothing_else_changes(self):
        """R3: no own commit changes a law, a record, a generated or replay file other than results/M3/ranking.json."""
        for c, paths in own_commits().items():
            for p in paths:
                if p.split("/")[0] in ("laws", "results", "gen", "replay"):
                    self.assertEqual(p, RANKING_REL, f"{c[:12]} changes {p}")

    def test_r4_instrument_agrees(self):
        """R4: for every REFUTED NAT law, holon's mass, words, outcomes and version flag are the instrument's."""
        ms, rc, rep = doc()["measures"], records(M), I.nat_report()
        n = 0
        for lid in nat_laws():
            if rc[lid]["status"] != "REFUTED":
                continue
            n += 1
            obs = I.nat_observation(lid, rc[lid], rep)
            self.assertIsNotNone(obs, f"{lid}: no bound replay")
            mass, words, labels, version = I.nat_mass(obs)
            m = ms[lid]
            self.assertEqual(m["value"], mass, lid)
            self.assertEqual([int(w, 16) for w in m["detail"]["words"]], words, lid)
            self.assertEqual((m["detail"]["outcomes"], m["detail"]["version"]), (labels, version), lid)
        self.assertEqual(n, len(I.NAT_EXPECTED))

    def test_r5_stage1_outcome_moves_only_nat(self):
        """R5: the first own commit that changes results/M3/ranking.json changes only what M-NAT moves."""
        cs = [c for c, paths in own_commits().items() if RANKING_REL in paths]
        self.assertTrue(cs, "no own commit changes results/M3/ranking.json yet")
        c = cs[0]
        new, old = (json.loads(git("show", f"{r}:{RANKING_REL}")) for r in (c, f"{c}^"))
        nat = {lid for lid, m in new["measures"].items() if m["rule"] == "NAT"}
        for k in sorted(set(new) | set(old)):
            if k in ("rules", "pending_measures", "sidecar", "inputs", "measures", "ranking", "summary"):
                continue
            self.assertEqual(new.get(k), old.get(k), k)
        self.assertEqual({r: v for r, v in new["rules"].items() if r != "NAT"},
                         {r: v for r, v in old["rules"].items() if r != "NAT"})
        self.assertEqual(set(new["measures"]), set(old["measures"]))
        for lid in sorted(set(new["measures"]) - nat):
            self.assertEqual(new["measures"][lid], old["measures"][lid], lid)
        strip = (lambda e: {k: v for k, v in e.items() if k != "measure" or e["law_id"] not in nat})
        self.assertEqual([strip(e) for e in new["ranking"]], [strip(e) for e in old["ranking"]])
        self.assertEqual({k: v for k, v in new["summary"].items() if k != "kinds"},
                         {k: v for k, v in old["summary"].items() if k != "kinds"})

    def test_key_names_this_file(self):
        """Construction: the key's tests list is this file."""
        self.assertEqual(predictions(KEY)["tests"], ["tests_m3/test_measures_i44.py"])


if __name__ == "__main__":
    unittest.main()
