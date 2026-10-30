"""I81 (= I44a): Def 6.13's measures and §10.10's ranking over the M3 laws (BUILD_PLAN row I81; whitepaper Def 6.13,
Thm 6.8, Thm 6.9, Def 6.20, §10.10 and §11.3's Impact column). This docstring is the contract.

Command. `python -m holon rank --milestone M3 [--root R] [--out PATH] [--check]` writes results/M3/ranking.json
(ranking_version holon-ranking/0.1, valid against spec/schemas/ranking.schema.json): JSON with sorted keys, indent 1
and a final newline, no timestamps, computed from committed files only (no checker, no solver, no node). `--check`
writes nothing and exits 0 iff the regeneration is byte-identical to the committed file (1 otherwise, naming the first
difference). Its `inputs` list every file it read, each with its sha256, sorted by path.

Inputs: laws/<M>/L*.json and results/<M>/L*.json; results/<M>/refute/concretization.json; replay/<M>/undo/report.json
and replay/<M>/sorts/report.json; gen/<M>/disch/closure.json and conjuncts.json (the latter through I32's
holon.profile.classification); the documents the laws name (their `facts`); spec/<M>/lib/fact.json; and the policy
sidecar spec/<M>/lib/ranking.json (measures, channels, orders, pending keys).

Measures (holon/measures.py): `measures` holds one entry per law of laws/<M>, keyed by law id, {rule, measure, unit,
kind, value, lower, upper, certified, scope, pending, why, detail}; kind is value, bound, pending or not_applicable;
`rules` holds each Def 6.13 rule's measure and status, and `pending_measures` the sidecar's list.
  M-PAR  holonomy defect size, in positions. PROVED: value 0, certified (the kernel accepted the proof, so the two
         paths agree on every input of the premises). REFUTED: lower = the positions where the record's difference
         sides differ (two byte strings: the differing bytes of their common prefix, then every position past the
         shorter; any other unequal pair: one position); upper = the positions where the claim's two encoder layouts
         (in the law's `facts` document, at the versions its premises pin) differ once the premises apply (a field
         correspondence makes two fields one, a constant pin makes a field's bytes constants, an opaque cell differs
         from every cell), plus every position past the shorter layout; a claim whose values are not byte strings
         has upper one position. lower and upper are the sets' sizes; detail.over is "bytes" or "value", and
         detail.lower_positions and detail.upper_positions their ranges ([first, last] pairs; null for an upper bound
         not computed). Certified iff the two sets are equal: kind value, value their size, detail.positions their
         ranges. UNKNOWN: kind bound, lower 0, upper as for REFUTED when computable, else null.
  M-UNDO residue liveness distance, in steps. REFUTED: upper = i + 1, i the first index of the witness's continuation
         t where the model's observations of the two runs differ in replay/<M>/undo/report.json (len(t) without an
         entry there); lower = 1 (an empty continuation has no observation, so no trace shorter than one step tells
         two states apart); certified iff lower == upper. PROVED: value "infinite" (the residue is dead), certified.
         UNKNOWN: kind bound, lower 1, upper null.
  M-FACT F(m, c), in bits, for the kernel subform: I26's measure recomputed (holon.rules.fact.analyse over the law's
         document and spec/<M>/lib/fact.json, which calls holon.measures_fact), exact over I26's domain (scope: its
         alphabet and maximum length); certified for a PROVED law (Thm 6.8: the factorization holds, so F = 0). The
         attribution subform: not_applicable (it states no kernel pair; the sidecar's why_not).
  M-DISCH discharge profile: pending (the sidecar's key: M3 has no cost model), with detail.class, the I32 class of
         the law's basis element (holon.profile.classification): its own class's for a blocking law, else the most
         persistent (rule PE2) of its element's classes.
  M-NAT  naturality defect mass: pending (I29) for any NAT law; `rules.NAT` is pending I29 when no NAT law exists.
  M-NA   a rule Def 6.13 gives no measure (SORT, any other): not_applicable.

Ranking (holon/rank.py): `ranking` holds one entry per REFUTED law, ordered by its key [sink tier, persistence tier,
reach tier, cost, law id], a tier the index of the sidecar order's inner list that holds the class (for reach, the
kind) and an unknown cost 2^30 (last); each entry is {rank, law_id, rule,
subform, triage, filter_bin, measure (its kind and value), impact: {sink: {class, channel, why}, persistence: {class,
why}, reach: {class, kind, classes, pending, why}, cost: {calls, gas, why}}, key}.
  Channel, the first rule that applies:
  K1 the record's triage is intent_question: intent.
  K2 a DISCH law: guard (its basis element is a guard that blocks a principal class's actions).
  K3 an UNDO law, at the first divergent step of t (M-UNDO): view when that step's action is a view or pure action of
     the law's document; else revert when the two observations' statuses differ; else store. No entry: undecided.
  K4 a FACT law: attribution for the attribution subform; for the kernel subform, store when its consumer (I26's
     basis element) is a storage variable of the law's document, else commitment (the transaction carries it and
     readers off the contract consume it).
  K5 a SORT law: revert when a witness run of the law ends in a revert on the model (replay/<M>/sorts/report.json),
     else store. No entry: undecided.
  K6 a PAR law over a Go-op document (holon-goops): abort when a side of the record's difference is false (an ok_<op>
     domain, so the op panics) or the Go-op model's panic outcome; else representation.
  K7 a PAR law whose claim is a versioned machine's init term: store.
  K8 a PAR law whose claim compares two functions of a codec document (ok_<f> standing for f): representation when
     their languages differ, store when they are the same.
  Otherwise undecided. The sink class is the sidecar's channels[channel] (undecided for undecided).
  Persistence:
  PE1 a PAR law whose binders hold no Reach (its sides are pure functions): code.
  PE2 a DISCH law: the most persistent, in the sidecar's persistence_order, of the I32 classes M-DISCH reads.
  PE3 otherwise: undecided.
  Reach:
  RE1 the witness schedule: UNDO prefix, x, y, t; FACT kernel each run's prefix and x; FACT attribution prefix, y, t;
      SORT and DISCH steps; a PAR law with an init claim, its trace's call steps (a migrate step deploys the version;
      it is no principal's call); another PAR law, its concretization path (results/<M>/refute/concretization.json)
      when the result is a path, pending (the sidecar's pending_reach key) when its kind is named there, otherwise
      undecided.
  RE2 a call's class: the I31 principal class whose actions hold its action (gen/<M>/disch/closure.json), else
      anyone; the class's kind from its predicate: none, anyone; a raw storage slot (sload), slot; an external call,
      call; a caller-keyed mapping, mapping; the caller equal to a storage register, owner; else undecided.
  RE3 the reach is the call whose kind ranks last in the sidecar's reach_order (the most privileged class the schedule
      needs; ties by class id), with every class of the schedule in `classes`.
  CO1 cost: the number of the schedule's calls whose action is not a view or pure action of the law's document (null
      without a schedule); gas: pending (the sidecar's cost.gas).

Nothing in holon/measures.py or holon/rank.py names a law, an action, a register or a target: every name comes from
the laws, the records, the documents and the sidecar. Neither imports tests/ or tests_m3/.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests_m3 import _i81 as I
from tests_m3._m3 import ROOT, holon_module, laws, predictions, records, run_holon, validate

KEY = "I81"
M = "M3"
OUT = ROOT / "results" / M / "ranking.json"
SCHEMA = ROOT / "spec" / "schemas" / "ranking.schema.json"


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
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I81 (the audit's C_K)."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(doc, dict) and KEY in (doc.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I81")


def own_commits() -> dict[str, list[str]]:
    """I81's own commits: the non-merge commits of `git log --first-parent <C_K>..<end>`, end the first commit adding
    docs/iterations/I81.md (HEAD before it exists), each with the paths it changes. Along the first-parent line of the
    merge that brings the branch into the lead when there is one."""
    pre = prereg_commit()
    added = git("log", "--full-history", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--",
                "docs/iterations/I81.md").split()
    end = added[0] if added else "HEAD"
    revs = [f"{pre}..{end}"]
    if added:
        for line in git("rev-list", "--ancestry-path", "--merges", "--reverse", "--parents", f"{end}..HEAD").splitlines():
            c, *parents = line.split()
            if len(parents) > 1 and _is_ancestor(end, parents[1]) and not _is_ancestor(end, parents[0]):
                revs = [parents[1], f"^{parents[0]}", f"^{pre}"]
                break
    out: dict[str, list[str]] = {}
    for c in git("log", "--first-parent", "--no-merges", "--format=%H", *revs).split():
        out[c] = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--no-renames", c).split()
    return out


def base_law_ids() -> set[str]:
    """The law ids of laws/M3 at the base commit (the M3 laws that exist today, for this key)."""
    names = git("ls-tree", "-r", "--name-only", I.BASE, "--", f"laws/{M}/").split()
    return {Path(n).stem for n in names if Path(n).name.startswith("L") and n.endswith(".json")}


def doc() -> dict:
    return json.loads(OUT.read_text())


def entries() -> dict[str, dict]:
    return {e["law_id"]: e for e in doc()["ranking"]}


# ====================================================================== the command and the document
class TestCommand(unittest.TestCase):
    def test_r3_regenerates_byte_identically(self):
        """R3: `holon rank --milestone M3 --check` passes on the committed file, and two runs write the same bytes."""
        p = run_holon(["rank", "--milestone", M, "--check"], timeout=600)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.json", Path(d) / "b.json"
            for out in (a, b):
                p = run_holon(["rank", "--milestone", M, "--out", str(out)], timeout=600)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(a.read_bytes(), OUT.read_bytes())


class TestDocument(unittest.TestCase):
    def test_r6_schema(self):
        """R6: results/M3/ranking.json is valid against spec/schemas/ranking.schema.json."""
        self.assertTrue(SCHEMA.is_file(), SCHEMA)
        self.assertEqual(validate(doc(), SCHEMA), [])
        try:
            import jsonschema
        except ImportError:
            return
        jsonschema.validate(doc(), json.loads(SCHEMA.read_text()))

    def test_r6_inputs_are_current(self):
        """R6: every input the document lists is the file on disk (its sha256), the sidecar among them."""
        import hashlib
        d = doc()
        paths = [x["path"] for x in d["inputs"]]
        self.assertEqual(paths, sorted(paths))
        self.assertIn("spec/M3/lib/ranking.json", paths)
        for x in d["inputs"]:
            self.assertEqual(hashlib.sha256((ROOT / x["path"]).read_bytes()).hexdigest(), x["sha256"], x["path"])


# ====================================================================== the measures
class TestMeasures(unittest.TestCase):
    def test_p1_par_cc_defects(self):
        """P1: each REFUTED cross-component codec law's holonomy defect is exactly bytes 185..216, certified (its
        witness differs there and the layouts can differ nowhere else); no REFUTED PAR law's defect holds byte 0."""
        ms, lw, rc = doc()["measures"], laws(M), records(M)
        codec = I.load(ROOT / lw[I.CC[0]]["facts"])
        for lid in I.CC:
            m = ms[lid]
            self.assertEqual((m["kind"], m["value"], m["certified"]), ("value", 32, True), lid)
            self.assertEqual(m["detail"]["positions"], [[185, 216]], lid)
            self.assertEqual(I.par_positions(rc[lid]), I.SSVH, lid)
            self.assertEqual(I.layout_bound(lw[lid], codec), I.SSVH, lid)
        over: dict[str, int] = {}
        for lid, r in rc.items():
            if r["rule"] != "PAR" or r["status"] != "REFUTED":
                continue
            m = ms[lid]
            over[m["detail"]["over"]] = over.get(m["detail"]["over"], 0) + 1
            if m["detail"]["over"] == "bytes":
                for rng in ("lower_positions", "upper_positions"):
                    self.assertFalse(any(a <= 0 <= b for a, b in m["detail"][rng]), (lid, rng))
            else:
                self.assertEqual((m["kind"], m["value"], m["lower"], m["upper"], m["certified"]),
                                 ("value", 1, 1, 1, True), lid)
        self.assertEqual(over, {"bytes": 3, "value": 5})

    def test_p2_undo_distance(self):
        """P2: the three REFUTED UNDO laws (the L_undo_BVH analogue first) have residue liveness distance 1, certified
        minimal (lower 1: an empty continuation observes nothing; upper 1: the model's observations first differ at
        t[0])."""
        ms = doc()["measures"]
        rep = I.load(ROOT / "replay" / M / "undo" / "report.json")["laws"]
        for lid in I.UNDO_REFUTED:
            m = ms[lid]
            self.assertEqual((m["kind"], m["value"], m["lower"], m["upper"], m["certified"]),
                             ("value", 1, 1, 1, True), lid)
            self.assertEqual(I.undo_divergence(rep[lid]), 0, lid)

    def test_p5_measure_kinds(self):
        """P5: over the base's 136 laws (no NAT law among them): value 87, bound 9, pending 35, not_applicable 5;
        rules.NAT is pending I29; every law of laws/M3 has a measure."""
        d = doc()
        ids = base_law_ids()
        self.assertEqual(len(ids), 136)
        self.assertEqual(set(d["measures"]), set(laws(M)))
        kinds: dict[str, int] = {}
        for lid in ids:
            k = d["measures"][lid]["kind"]
            kinds[k] = kinds.get(k, 0) + 1
        self.assertEqual(kinds, I.KINDS)
        self.assertEqual((d["rules"]["NAT"]["status"], d["rules"]["NAT"]["pending"]), ("pending", "I29"))


# ====================================================================== the ranking
class TestRanking(unittest.TestCase):
    def test_p3_sink_classes(self):
        """P3: the computed sink class of every REFUTED base law is the prereg's (economic 2, liveness 10, derivation
        6, state 2, process 3, off-chain 1); against §11.3's Impact column, 14 of the 16 analogue laws match and the
        PAR-init and SORT-tag laws differ (state, against finality)."""
        es = entries()
        got = {lid: es[lid]["impact"]["sink"]["class"] for lid in I.EXPECTED}
        self.assertEqual(got, {lid: v[0] for lid, v in I.EXPECTED.items()})
        cmp = {lid: I.compare(es[lid]) for lid in I.IMPACT}
        self.assertEqual({lid for lid, c in cmp.items() if not c["sink"]}, I.SINK_DIFFER)

    def test_p4_reach_against_impact(self):
        """P4: the computed reach of every REFUTED base law is the prereg's; against §11.3, the reach matches for the
        PAR-init law, the commitBatch FACT kernel law, the SORT realize law and the two rollup_363 DISCH laws of the
        challenger's schedules, and differs for the other 11 analogue laws."""
        es = entries()
        got = {lid: (es[lid]["impact"]["reach"]["class"], es[lid]["impact"]["reach"]["kind"]) for lid in I.EXPECTED}
        self.assertEqual(got, {lid: (v[2], v[3]) for lid, v in I.EXPECTED.items()})
        self.assertEqual({lid for lid in I.IMPACT if I.compare(es[lid])["reach"]}, I.REACH_MATCH)

    def test_p6_persistence_and_cost(self):
        """P6: the computed persistence and cost of every REFUTED base law are the prereg's; against §11.3 the
        persistence matches for the four pure-function analogue laws (O1 and O4) only."""
        es = entries()
        got = {lid: (es[lid]["impact"]["persistence"]["class"], es[lid]["impact"]["cost"]["calls"])
               for lid in I.EXPECTED}
        self.assertEqual(got, {lid: (v[1], v[4]) for lid, v in I.EXPECTED.items()})
        self.assertEqual({lid for lid in I.IMPACT if I.compare(es[lid])["persistence"]}, I.PERSISTENCE_MATCH)

    def test_p7_order(self):
        """P7: the ranking is the prereg's order: the two FACT attribution laws first, the batchDataStore residue
        last."""
        d = doc()
        got = [e["law_id"] for e in d["ranking"] if e["law_id"] in I.EXPECTED]
        self.assertEqual(got, I.ORDER)

    def test_lexicographic(self):
        """Construction: one entry per REFUTED law, ranks 1..n, sorted by the key; each key is the tiers of the
        sidecar's orders."""
        d, sc, rc = doc(), I.sidecar(), records(M)
        refuted = sorted(lid for lid, r in rc.items() if r["status"] == "REFUTED")
        self.assertEqual(sorted(e["law_id"] for e in d["ranking"]), refuted)
        self.assertEqual([e["rank"] for e in d["ranking"]], list(range(1, len(refuted) + 1)))

        def tier(order, x):
            return next(i for i, t in enumerate(order) if x in t)
        big = 1 << 30
        for e in d["ranking"]:
            imp = e["impact"]
            want = [tier(sc["sink_order"], imp["sink"]["class"]),
                    tier(sc["persistence_order"], imp["persistence"]["class"]),
                    tier(sc["reach_order"], imp["reach"]["kind"]),
                    imp["cost"]["calls"] if imp["cost"]["calls"] is not None else big, e["law_id"]]
            self.assertEqual(e["key"], want, e["law_id"])
        keys = [e["key"] for e in d["ranking"]]
        self.assertEqual(keys, sorted(keys))


# ====================================================================== regressions and construction
class TestRegressions(unittest.TestCase):
    def test_r1_fact_bits(self):
        """R1: each FACT kernel law's measure is its record's (I26's F(m, c)): 1.0, 1.0 and 0.0 bits."""
        ms, rc = doc()["measures"], records(M)
        n = 0
        for lid, r in rc.items():
            if r["rule"] == "FACT" and r.get("subform") == "kernel":
                n += 1
                self.assertEqual(ms[lid]["value"], r["fact"]["measure"]["bits"], lid)
            elif r["rule"] == "FACT":
                self.assertEqual(ms[lid]["kind"], "not_applicable", lid)
        self.assertEqual(n, 3)

    def test_r2_disch_classes(self):
        """R2: the DISCH measures read I32's classes: the regeneration equals gen/M3/disch/classification.json, and
        every DISCH law is pending I37 with its class."""
        prof = holon_module("holon.profile")
        self.assertEqual(prof.classification(ROOT), I.load(ROOT / "gen" / M / "disch" / "classification.json"))
        for lid, m in doc()["measures"].items():
            if m["rule"] == "DISCH":
                self.assertEqual((m["kind"], m["pending"]), ("pending", "I37"), lid)
                self.assertIn(m["detail"]["class"], {x for t in I.sidecar()["persistence_order"] for x in t}, lid)

    def test_r4_no_target_vocabulary(self):
        """R4: holon/measures.py and holon/rank.py name no law, action, register, span or target, and import no test
        code."""
        import re
        bad = ["L_par_", "L_undo_", "L_fact_", "L_disch_", "L_sort_", "L_pinit", "Rollup", "commitBatch",
               "revertBatch", "batchBlobVersionedHashes", "contracts/", "morph", "Morph", "onlyOwner",
               "onlyActiveSubmitter", "onlyChallenger", "OPanic", "ssvh", "SequencerSetVerifyHash"]
        for rel in ("holon/measures.py", "holon/rank.py"):
            text = (ROOT / rel).read_text()
            for b in bad:
                self.assertNotIn(b, text, f"{rel} holds {b!r}")
            self.assertIsNone(re.search(r"(?m)^\s*(from|import)\s+tests", text), f"{rel} imports test code")

    def test_r5_nothing_else_changes(self):
        """R5: no own commit of I81 changes a law, a record, a generated or replay file other than
        results/M3/ranking.json."""
        for c, paths in own_commits().items():
            for p in paths:
                if p.split("/")[0] in ("laws", "results", "gen", "replay"):
                    self.assertEqual(p, "results/M3/ranking.json", f"{c[:12]} changes {p}")

    def test_r7_instrument_agrees(self):
        """R7 (construction): for every REFUTED law, holon's channel, persistence, reach, cost and (PAR, UNDO) measure
        bounds are what the instrument computes by its own reading of the rules."""
        lw, rc, es, ms = laws(M), records(M), entries(), doc()["measures"]
        conc = I.load(ROOT / "results" / M / "refute" / "concretization.json")
        cls, sc = I.classes(), I.sidecar()
        acts_of: dict[str, dict] = {}
        for lid, r in rc.items():
            if r["status"] != "REFUTED":
                continue
            law, e = lw[lid], es[lid]
            self.assertEqual(e["impact"]["sink"]["channel"], I.channel_of(law, r), lid)
            self.assertEqual(e["impact"]["persistence"]["class"], I.persistence_of(law), lid)
            steps, pend = I.schedule(law, r, conc)
            reach = I.reach_of(steps, pend, cls, sc)
            self.assertEqual((e["impact"]["reach"]["class"], e["impact"]["reach"]["kind"]),
                             (reach["class"], reach["kind"]), lid)
            if law["facts"] not in acts_of:
                d = I.load(ROOT / law["facts"])
                acts_of[law["facts"]] = {a["name"]: a for a in d.get("actions") or []}
            self.assertEqual(e["impact"]["cost"]["calls"], I.cost_of(steps, acts_of[law["facts"]]), lid)
            if r["rule"] == "PAR":
                pos = I.par_positions(r)
                self.assertEqual(ms[lid]["lower"], len(pos), lid)
        self.assertEqual(predictions(KEY)["tests"], ["tests_m3/test_ranking.py"])


if __name__ == "__main__":
    unittest.main()
