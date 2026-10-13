"""I15, builder B: proofs (coercion_guard), refutation with one witness per entry point, Foundry replay, M2 records
and the M2 gate. The derivation contract (CLI, laws, site term, hit-point rules R7-R11, DERIVATION.json,
REGISTRY.json, obstructions.json, the instrumented model) is the docstring of tests_m2/test_sort_sites.py.

`python -m holon run --milestone M2` (and --laws ID,ID: only those laws are decided)
  Runs every SORT-site law of laws/M2 on the instrumented model of its document (holon.sorts.sites.instrumented_model
  with laws/M2/DERIVATION.json), written to gen/M2/model/<model>.bend. Layout as for every M2+ milestone (I10):
  gen/M2/laws/<id>/LAWS.bend, gen/M2/proofs/<id>/PROOF.bend, gen/M2/core/. It never deletes what other commands
  wrote under gen/M2 (diagram/, sorts/, oracles/, evidence.json): it removes and rewrites only model/, core/, laws/,
  proofs/ and gen/M2/L* (today run_m1 removes the whole gen dir).
  Order per law: the proof generators (holon.gen.mproofs, with the new class coercion_guard), then refutation.
  coercion_guard (whitepaper §7.8 realize, Thm 6.18): for a SORT-site law, prove site_<x>(a, s) == True for every a
  and s by mirroring the ghost chain of each entry point; at each hit, one condition the evaluation has passed (a
  require before the hit, in guard order, or a path condition of the occurrence, inside definitions included)
  implies minuend >= subtrahend: ONE condition, never two combined (the toy's len - 1 stays UNKNOWN), through the
  imported core library (C.core_*, holon.gen.core.CATALOG, proved there by its per-class generators; F-M2-04): zero
  or more Bool.and projections of that condition (a definition call such as in_win unfolds by computation), then ONE
  comparison lemma. Lemma shapes the predicted sites need:
  is_gt(a,b) => is_le(b,a); is_lt(a,b) => is_le(a,b); is_ge(a,b) => is_le(b,a); Bool.and(x,y) == True => x == True;
  is_le(a,b) == False => is_le(b,a); is_le(a,b) == False => is_le(1, sub(a,b)). The class does not apply (None, recorded)
  when some hit has no such condition; it never assumes reachability (its proof holds for every state). Every
  accepted PROOF.bend imports its law, gen/M2/laws/<id>/LAWS.bend, as Laws and defines Laws.<its law name> (audit
  F-M2-07: under prover separation a proof that imports no law would check vacuously). A guard's equation is Type, not
  Data, so it can be used once (docs/iterations/I8.md): a proof that needs one guard at two hits derives the Bool fact
  once and shares that.
  Refutation of a SORT-site law runs once per entry point e (DERIVATION entry_points, sorted), on the compiled model
  (holon/js/explore.mjs; untrusted: only a Bend-checked counter-law counts):
    S1 candidates at a state: e's actions from the search policy (target hints or the generic policy), then, for each
       of them and each Nat input in input order, the variants input := v - 1 (when v >= 1), v + 1, 0, without
       repeats (boundary values, §8.7);
    S2 prefixes: the explorer's reachable prefixes (BFS over successful policy actions; prefixDepth, maxPrefixes),
       in order; e's witness is the first (prefix, candidate) at which the site term is false;
    S3 neighbourhood, only when S2 found none and another entry point of the same law has a witness: for each such
       witness (entry points sorted), each insertion position i of its prefix (0..len) and each sequence of one or two
       successful policy actions at the state after prefix[:i] (BFS order), the prefix prefix[:i] ++ seq ++ prefix[i:]
       if all of its actions succeed; then S1's candidates for e there; at most 20,000 prefixes per entry point.
  Each witness found gives a counter-law (the law's counter-law, holon.gen.mlaws: exs s, its Reach evidence, a, the
  parameters; site != True) checked by Bend (and BendTT when the verdict kernel is enabled) in
  gen/M2/proofs/<id>/entry_<e>/PROOF.bend, importing gen/M2/laws/<id>/LAWS.bend. The law is REFUTED iff at least one
  entry point's counter-law checks; its primary witness (record "witness", gen/M2/proofs/<id>/PROOF.bend) is the
  first entry point, sorted, with a checked counter-law. Otherwise UNKNOWN with the bound (scope bounded).

Non-vacuity (I3's G11V; whitepaper §12.3, L21). The plan's statement ∀p. at_site(p, s0, ℓ) → nonneg(d_ℓ) has the
  premise at_site; the site term folds it in, so the Reach binder alone would be inhabited by s0 and say nothing. For a
  SORT-site law, holon.inhabit's inhabitant states the at_site premise: law nv_<id lower>: exs s, its Reach evidence,
  a [, the parameters]. {M.hit_<x>(a, s) == True{} : Bool} (hit_<x>: the ghost predicate of the instrumented model,
  tests_m2/test_sort_sites.py), at a concrete reachable (s, a) found by stages S1 and S2 (the same budgets) and proved
  like a counter-law; the record's non_vacuity is I3's {status, law, witness, reachable, degenerate,
  parent_statement_hash, bound}: "inhabited" (reachable true) when it checks, "counter_witness" for a REFUTED law,
  else "unknown" with the bound. G11V fails a PROVED SORT-site law without a checked at_site inhabitant, and checks
  that the inhabitant states hit_<x>, not Reach alone.

Records (results/M2/<law_id>.json): v1 and v2 (spec/schemas/result_record_v2.schema.json, which gains, additively,
these two optional properties) and
  "site": the law's site id;
  "witnesses": {} for a PROVED law, else {e: {"status": "REFUTED" | "UNKNOWN",
                 "witness": {"s": {"run": [actions]}, "a": action, ..parameters} | null,
                 "laws": path | null, "proof": path | null (gen/M2/proofs/<id>/entry_<e>/PROOF.bend),
                 "checker": {"exit_code", "marker"} | null, "verdict": "checked" | "failed" | "not_run",
                 "stage": "S2" | "S3" | null, "bound": str,
                 "replay": {"status", "detail", "panic_site": "<path>:<line>" | null}}} for every entry point;
  model_assumptions (with ledger_assumptions, where the foundation lane keeps the ledger cone in a field of its own)
  keeps every spec/ledger entry of the document's bundle that meets the record's cone, as M1 records do (F-M2-12):
  for a rollup law at least abs-nat-tokens (Nat for uint256: the very abstraction a sign obligation probes) and
  scope-rollup-coverage-debt; refinement_refs names replay/M2/report.json#/refinement/per_action/<a> for every
  step_<a> in the cone.

`python -m holon replay --milestone M2` writes replay/M2/report.json (the I16 harness files under replay/M2/go and
replay/M2/solidity are I16's and stay untouched): the M1 report's form (morph_commit, command, toolchain,
witness_sha256, laws, refinement: the M1 corpus rule, seed and size, run on the M2 model), where laws[<id>] of a
SORT-site law also holds "entries": {e: {"trace": prefix ++ [action], "model": [obs], "real": [outcome], "status":
"passed" | "failed", "panic_site": "<path>:<line>" | null, "obstruction_observed": bool}} for every REFUTED entry
point, and "entry_witness_sha256": {e: sha256 of the canonical witness}. panic_site is where the real code raised the
last step's Panic, located from solc's source map of a Foundry debugger dump of that step (the rule written out in
tests_m2/_i15.py::locate_panic; holon implements its own), path as the facts spell spans (morph-root-relative).
obstruction_observed: the last step reverts with panic:0x11 at a line of the site's span. An entry passes when the real
outcome of every step equals the model's. The law's status is passed iff every entry passed. G6 binds every REFUTED
SORT-site record, and each of its REFUTED entry points, to a passed entry with obstruction_observed.

`python -m holon gate --milestone M2` runs every check (GENV, G2, G1, G3, G5, G11, G11V, G6, G9, GREF, G7, G4, and I14's
GEVID once merged) and passes; a check with no meaning for M2 is listed under not_applicable with a reason (§2.10).
G2 checks IR 0.3 hashes with refs (F-M2-10) and spec/bindings/M2.json (`holon bind --milestone M2`); G1 regenerates
the run's outputs and the derive outputs (laws/M2, obstructions.json) and compares them; G5 and G7 re-check every
per-entry proof too; G4 rejects at least 10 canaries of at least 3 kinds built from the M2 laws (F-M2-05, F-M2-06).
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2 import _i15 as H
from tests_m2._m2 import ROOT, SCHEMAS2, copy_repo, holon_module, load_json, records, run_holon, validate, write_json

V1 = ROOT / "schemas" / "result_record.schema.json"
V2 = SCHEMAS2 / "result_record_v2.schema.json"
ROLLUP_REL = "spec/M1/facts/morph_rollup.json"
TOY_REL = "tests_m2/fixtures/sort_sites/toy_sites.json"
COMMITS = ("commitBatch", "commitBatchWithProof", "commitState")
LAW_363 = "L_sort_site_rollup_363_1fc7f88a"
LAW_636 = "L_sort_site_rollup_636_e68daf06"
LAW_MUT2_NEW = "L_sort_site_rollup_360_364_1fc7f88a"
# I15-P1, I15-P2: the predicted outcome of the site laws that are not refuted (reasons: spec/M2/predictions.json)
PROVED_BY_COERCION = ("L_sort_site_rollup_441_b4cd5068",            # revertBatch let p = idx - lfi, after idx > lfi
                      "L_sort_site_rollup_485_495_b4cd5068",        # challengeState effect idx - lfi, after lfi < idx
                      "L_sort_site_rollup_644_660_e68daf06",        # finalizeBatch effect idx - 1, after idx >= 1
                      "L_sort_site_def_w_b4cd5068",                 # def w: idx - lfi under in_win(lfi, win, idx)
                      "L_sort_site_def_bvh_at_6126d1f1",            # def bvh_at: idx - lci under !(idx <= lci)
                      "L_sort_site_def_bvh_at_e064679d")            # def bvh_at: (idx - lci) - 1 under !(idx <= lci)
UNKNOWN_INVARIANT = ("L_sort_site_l1messagequeuewithgaspriceoracle_325_f89daf17",   # btot - bn: needs tot >= n on win
                     "L_sort_site_def_lci_356891e4")                                 # lfi + len(win) - 1: needs win != []
REFUTED = (LAW_363, LAW_636)
SPAN_RE = re.compile(r"^(?P<path>\S+?):(?P<lo>\d+)(?:-(?P<hi>\d+))?$")


def law(lid: str) -> dict:
    return load_json(H.LAWS2 / f"{lid}.json")


def derivation() -> dict[str, dict]:
    return {e["law_id"]: e for e in load_json(H.LAWS2 / "DERIVATION.json")["laws"]}


def rec(lid: str) -> dict:
    p = H.RESULTS2 / f"{lid}.json"
    if not p.exists():
        raise AssertionError(f"no record {p.relative_to(ROOT)}")
    return load_json(p)


def resolve(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else ROOT / q


def bend_check(path: Path) -> tuple[int, str]:
    from tests._util import run_bend
    return run_bend([path.name], cwd=path.parent)


def in_span(site_span: str, panic: dict | None) -> bool:
    """Whether a located panic (instrument path, relative to the copied contracts/ tree) lies in a site's span
    (facts paths are relative to the morph root, whose contracts/ directory the instrument copies)."""
    if not panic:
        return False
    m = SPAN_RE.match(site_span)
    lo, hi = int(m["lo"]), int(m["hi"] or m["lo"])
    return m["path"] == "contracts/" + panic["path"] and lo <= panic["line"] <= hi


# ---------------------------------------------------------------------------------------------- construction
class TestRecords(unittest.TestCase):
    def test_every_m2_law_has_a_record_valid_under_v1_and_v2(self):
        laws = {p.stem for p in H.LAWS2.glob("L*.json")}
        recs = records("M2")
        self.assertTrue(laws, "laws/M2 holds no law")
        self.assertEqual(sorted(recs), sorted(laws))
        reg = load_json(H.LAWS2 / "REGISTRY.json")
        dv = derivation()
        for lid, r in recs.items():
            with self.subTest(law=lid):
                self.assertEqual(validate(r, V1), [])
                self.assertEqual(validate(r, V2), [])
                self.assertEqual(r["statement_hash"], reg["statements"][lid])
                self.assertIn(r["status"], ("PROVED", "REFUTED", "UNKNOWN"))
                if dv[lid].get("subform") != "site":   # amended (I20, spec/M2/amendments.jsonl): a SORT-width law
                    continue                          # has no site and no per-entry witnesses (I20's contract)
                self.assertEqual(r["site"], dv[lid]["basis"]["site_id"])
                if r["status"] == "PROVED":
                    self.assertEqual(r["witnesses"], {})
                else:
                    self.assertEqual(sorted(r["witnesses"]), dv[lid]["entry_points"])
                    for e, w in r["witnesses"].items():
                        self.assertIn(w["status"], ("REFUTED", "UNKNOWN"))
                        self.assertTrue(w["bound"])
                if r["status"] == "REFUTED":
                    first = next(e for e in sorted(r["witnesses"]) if r["witnesses"][e]["status"] == "REFUTED")
                    self.assertEqual(r["witness"], r["witnesses"][first]["witness"])
                if r["status"] == "UNKNOWN":
                    # I15 amendment (spec/M2/amendments.jsonl, F-M2-01): a 0.3 record's scope is its statement's; the
                    # search bound of an UNKNOWN law is r["bound"]
                    self.assertEqual(r["scope"], "unbounded" if law(lid)["statement"]["scope"]["kind"] == "unbounded"
                                     else "bounded")
                    self.assertTrue(r["bound"])
                    self.assertTrue(all(w["status"] == "UNKNOWN" for w in r["witnesses"].values()))

    def test_proved_site_laws_are_not_vacuous(self):
        """Construction (non-vacuity, I3 G11V, §12.3 L21): every PROVED SORT-site law carries a Bend-checked inhabitant of
        its at_site premise (exs s: Reach, a. hit_<x>(a, s)), not merely of Reach; REFUTED ones point at a counter-law."""
        recs = records("M2")
        self.assertTrue(recs, "results/M2 holds no law record")
        for lid, r in recs.items():
            with self.subTest(law=lid):
                nv = r["non_vacuity"]
                self.assertIsInstance(nv, dict)
                self.assertEqual(nv["parent_statement_hash"], r["statement_hash"])
                if r["status"] == "REFUTED":
                    self.assertEqual(nv["status"], "counter_witness")
                if r["status"] != "PROVED":
                    continue
                self.assertEqual((nv["status"], nv["reachable"]), ("inhabited", True), nv.get("bound"))
                lp = resolve(nv["law"])
                text = lp.read_text()
                x = lid[len("L_sort_site_"):]
                self.assertEqual(re.findall(r"(?m)^law\s+(\w+)\s*:", text), ["nv_" + lid.lower()])
                self.assertRegex(text, r"(?m)^\s*exs\s")
                self.assertIn(f"M.hit_{x}(", text, "the inhabitant states the at_site premise")
                self.assertNotIn(f"M.site_{x}(", text)
                code, out = bend_check(lp.with_name("PROOF.bend"))
                self.assertEqual(code, 0, out[-1500:])

    def test_the_committed_model_is_the_instrumented_model(self):
        sites = holon_module("holon.sorts.sites")
        p = ROOT / "gen" / "M2" / "model" / "morph_rollup.bend"
        self.assertTrue(p.exists(), "gen/M2/model/morph_rollup.bend is not committed")
        want = sites.instrumented_model(ROOT / ROLLUP_REL, load_json(H.LAWS2 / "DERIVATION.json"))
        self.assertEqual(p.read_text(), want)
        recs = records("M2")
        self.assertTrue(recs, "results/M2 holds no law record")
        for lid, r in recs.items():
            if law(lid).get("subform") != "site":   # amended (I20): a SORT-width record is over the extracted model
                continue
            self.assertEqual(r["artifacts"]["model"], "gen/M2/model/morph_rollup.bend", lid)

    def test_ledger_assumptions_survive(self):
        """F-M2-12: an M2 record over the rollup keeps the ledger entries that meet its cone (Nat for uint256 above all)."""
        recs = records("M2")
        self.assertTrue(recs, "results/M2 holds no law record")
        for lid, r in recs.items():
            if law(lid)["facts"] != ROLLUP_REL:   # amended (I20): the records over the rollup facts (a SORT-width
                continue                          # record is over the extracted document, with its own bundle)
            with self.subTest(law=lid):
                got = set(r.get("model_assumptions") or []) | set(r.get("ledger_assumptions") or [])
                self.assertLessEqual({"abs-nat-tokens", "scope-rollup-coverage-debt"}, got)

    def test_refinement_refs_name_the_m2_corpus(self):
        rep = load_json(H.REPLAY2)
        pa = sorted((rep.get("refinement") or {}).get("per_action") or {})
        self.assertTrue(pa, "replay/M2/report.json has no refinement corpus")
        recs = records("M2")
        self.assertTrue(recs, "results/M2 holds no law record")
        for lid, r in recs.items():
            with self.subTest(law=lid):
                want = sorted(f"replay/M2/report.json#/refinement/per_action/{a}" for a in pa if f"step_{a}" in r["cone"])
                self.assertEqual(r["refinement_refs"], want)
                self.assertTrue(want)


    def test_m2_refinement_corpus_agrees(self):
        """Regression: the M2 refinement corpus (the M1 corpus rule, seed and size, on the M2 model, whose transition
        function is the M1 model's) shows no disagreement and no harness mismatch, as the M1 corpus does."""
        rep = load_json(H.REPLAY2)
        rf = rep["refinement"]
        self.assertEqual((rf["traces"], rf["seed"]), (300, 20261011))
        self.assertEqual(rf["n_disagreements"], 0)
        self.assertFalse(rep.get("harness_mismatch"))
        self.assertTrue(all(v["disagree"] == 0 for v in rf["per_action"].values()))


class TestToyOutcomes(unittest.TestCase):
    """Construction checks: the toy fixture, derived and run as milestone T15, decides every class as designed."""

    def test_toy_statuses(self):
        repo = copy_repo()
        try:
            tmp = repo.parent
            a = run_holon(["sorts", "--facts", TOY_REL, "--out", str(tmp / "sorts")], cwd=repo)
            b = run_holon(["derive", "--milestone", "T15", "--facts", TOY_REL, "--assignment",
                           str(tmp / "sorts" / "assignment.json"), "--out", str(repo / "laws" / "T15"),
                           "--obstructions", str(tmp / "obstructions.json")], cwd=repo)
            # F-M2-25: what other commands wrote under the milestone's gen dir survives `holon run`
            sentinels = {tmp / "gen" / "diagram" / "sentinel.json": b'{"sentinel": "diagram"}\n',
                         tmp / "gen" / "sorts" / "sentinel.json": b'{"sentinel": "sorts"}\n',
                         tmp / "gen" / "oracles" / "sentinel.bend": b"# sentinel\n",
                         tmp / "gen" / "evidence.json": b'{"sentinel": "evidence"}\n'}
            for sp, sb in sentinels.items():
                sp.parent.mkdir(parents=True, exist_ok=True)
                sp.write_bytes(sb)
            c = run_holon(["run", "--milestone", "T15", "--out", str(tmp / "results"), "--gen-dir", str(tmp / "gen")],
                          cwd=repo, timeout=3600)
            log = "\n".join(x.stdout[-2000:] + x.stderr[-2000:] for x in (a, b, c))
            self.assertEqual((a.returncode, b.returncode, c.returncode), (0, 0, 0), log)
            got = {p.stem: load_json(p) for p in (tmp / "results").glob("L*.json")}
            want = {"L_sort_site_toy_12_b4cd5068": "PROVED", "L_sort_site_toy_34_b2fa4afd": "REFUTED",
                    "L_sort_site_toy_52_e68daf06": "REFUTED", "L_sort_site_toy_56_58_e68daf06": "PROVED",
                    "L_sort_site_toy_56_58_7f392a5d": "UNKNOWN", "L_sort_site_def_after_aca797ff": "PROVED",
                    "L_sort_site_def_lci_ed147249": "UNKNOWN"}
            self.assertEqual({k: v["status"] for k, v in got.items()}, want, log)
            for lid, st in want.items():
                r = got[lid]
                if st == "PROVED":
                    acc = [x for x in r["attempts"] if x.get("kind") == "proof" and x.get("marker") == "ALL PROOFS CHECK"]
                    self.assertEqual([x["generator"] for x in acc], ["coercion_guard"], lid)
            self.assertEqual(got["L_sort_site_toy_52_e68daf06"]["witnesses"]["finalize"]["witness"]["a"]["idx"], 0)
            self.assertEqual(got["L_sort_site_toy_34_b2fa4afd"]["witnesses"]["commit"]["status"], "REFUTED")
            for lid, st in want.items():   # non-vacuity: each PROVED toy site is reached (an at_site inhabitant)
                if st == "PROVED":
                    nv = got[lid]["non_vacuity"]
                    self.assertEqual((nv["status"], nv["reachable"]), ("inhabited", True), (lid, nv.get("bound")))
            for sp, sb in sentinels.items():
                self.assertTrue(sp.exists() and sp.read_bytes() == sb, f"holon run removed or rewrote {sp.relative_to(tmp)}")
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_toy_site_without_its_guard_is_refuted(self):
        """Construction (ghost faithfulness, mutation-style): the toy's PROVED window offset idx - lfi (revertTo, let p,
        after the require idx > lfi) is REFUTED through revertTo once that require is replaced by true in a copy (as
        MUT2 does): a ghost predicate that skipped the let, or a proof that did not rest on the guard, would leave it
        PROVED. The law is found by its basis and hit, since its span (so its id) changes with the guard."""
        repo = copy_repo()
        try:
            tmp = repo.parent
            p = repo / TOY_REL
            f = load_json(p)
            act = next(a for a in f["actions"] if a["name"] == "revertTo")
            gi = [i for i, g in enumerate(act["guards"]) if g.get("require") == [">", "idx", "lfi"]]
            self.assertEqual(len(gi), 1, "the toy's revertTo guard idx > lfi")
            act["guards"][gi[0]]["require"] = True
            write_json(p, f)
            a = run_holon(["sorts", "--facts", TOY_REL, "--out", str(tmp / "sorts")], cwd=repo)
            b = run_holon(["derive", "--milestone", "T15", "--facts", TOY_REL, "--assignment",
                           str(tmp / "sorts" / "assignment.json"), "--out", str(repo / "laws" / "T15"),
                           "--obstructions", str(tmp / "obstructions.json")], cwd=repo)
            log = "\n".join(x.stdout[-2000:] + x.stderr[-2000:] for x in (a, b))
            self.assertEqual((a.returncode, b.returncode), (0, 0), log)
            dv = load_json(repo / "laws" / "T15" / "DERIVATION.json")["laws"]
            hit = [e["law_id"] for e in dv if e["basis"]["expr"] == ["-", "idx", "lfi"]
                   and [(h["action"], h["kind"]) for h in e["hits"]] == [("revertTo", "occurrence")]]
            self.assertEqual(len(hit), 1, [e["law_id"] for e in dv])
            c = run_holon(["run", "--milestone", "T15", "--out", str(tmp / "results"), "--gen-dir", str(tmp / "gen")],
                          cwd=repo, timeout=3600)
            self.assertEqual(c.returncode, 0, c.stdout[-2000:] + c.stderr[-2000:])
            r = load_json(tmp / "results" / f"{hit[0]}.json")
            self.assertEqual(r["status"], "REFUTED", c.stdout[-2000:])
            w = r["witnesses"]["revertTo"]
            self.assertEqual((w["status"], w["witness"]["a"]["op"]), ("REFUTED", "revertTo"))
            self.assertEqual(w["checker"]["marker"], "ALL PROOFS CHECK")
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


class TestGateM2(unittest.TestCase):
    """Exit (construction check): `holon gate --milestone M2` passes on a copy of the committed tree."""

    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        report = cls.repo / "gate_report_M2.json"
        cls.proc = run_holon(["gate", "--milestone", "M2", "--root", str(cls.repo), "--report", str(report)],
                             cwd=cls.repo, timeout=7200)
        cls.report = load_json(report) if report.exists() else None

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo.parent, ignore_errors=True)

    def test_gate_m2_passes(self):
        self.assertIsNotNone(self.report, self.proc.stdout[-2000:] + self.proc.stderr[-2000:])
        for g in ("GENV", "G2", "G1", "G3", "G5", "G11", "G11V", "G6", "G9", "GREF", "G7", "G4"):
            with self.subTest(check=g):
                self.assertIn(g, set(self.report["checks"]) | set(self.report.get("not_applicable") or {}))
        for g, c in self.report["checks"].items():
            self.assertTrue(c["passed"], f"{g}: {c['detail']}")
        self.assertEqual(self.proc.returncode, 0)
        for g in ("G1", "G2", "G5", "G6", "G9", "G4"):
            self.assertIn(g, self.report["checks"], f"{g} must run for M2")
        n = len(records("M2"))
        self.assertIn(f"{n} records identical", self.report["checks"]["G1"]["detail"])
        cs = self.report.get("canaries") or []
        self.assertGreaterEqual(len(cs), 10)
        self.assertGreaterEqual(len({c["kind"] for c in cs}), 3)


# ---------------------------------------------------------------------------------------------- predictions
class TestPredictedOutcomes(unittest.TestCase):
    def test_guard_implied_sites_are_proved_by_coercion_guard(self):
        """I15-P1: the six sites whose hit is preceded by a guard, or guarded by a path condition, that
        implies non-negativity are PROVED by coercion_guard, each proof calling an imported core lemma."""
        for lid in PROVED_BY_COERCION:
            with self.subTest(law=lid):
                r = rec(lid)
                self.assertEqual(r["status"], "PROVED")
                acc = [x for x in r["attempts"] if x.get("kind") == "proof" and x.get("marker") == "ALL PROOFS CHECK"]
                self.assertEqual([x["generator"] for x in acc], ["coercion_guard"])
                proof = resolve(r["artifacts"]["proof"])
                code, out = bend_check(proof)
                self.assertEqual(code, 0, out[-1500:])
                text = proof.read_text()
                self.assertRegex(text, r"(?m)^import \S*core/PROOF\.bend as \w+")
                self.assertIn("C.core_", text, "the proof calls a core lemma through the imported core")
                self.assertRegex(text, r"(?m)^import \S*laws/" + re.escape(lid) + r"/LAWS\.bend as Laws$",
                                 "the proof imports its law (F-M2-07)")
                names = re.findall(r"(?m)^law\s+(\w+)\s*:", (H.GEN2 / "laws" / lid / "LAWS.bend").read_text())
                self.assertEqual(len(names), 1, names)
                self.assertIn(f"def Laws.{names[0]}(", text, "the proof fills its law")

    def test_invariant_sites_stay_unknown_with_their_bound(self):
        """I15-P2: btot - bn (L1MessageQueue...:325) and def lci need an invariant of the reachable states
        (every window entry has tot >= n; the window is never empty); no guard implies them, no witness exists, so they
        stay UNKNOWN with their bound (BUILD_PLAN I15 risks: an unguarded site without a witness stays UNKNOWN)."""
        for lid in UNKNOWN_INVARIANT:
            with self.subTest(law=lid):
                r = rec(lid)
                self.assertEqual(r["status"], "UNKNOWN")
                # I15 amendment (spec/M2/amendments.jsonl, F-M2-01): the scope is the statement's (unbounded), the
                # search's bound is r["bound"]
                self.assertEqual(r["scope"], "unbounded" if law(lid)["statement"]["scope"]["kind"] == "unbounded"
                                 else "bounded")
                self.assertTrue(r["bound"])
                self.assertTrue(r["witnesses"])
                self.assertTrue(all(w["status"] == "UNKNOWN" and w["witness"] is None for w in r["witnesses"].values()))

    def test_363_is_refuted_with_one_checked_witness_per_entry_point(self):
        """I15-P3 (model half): the :363 law is REFUTED with one Bend-checked witness per entry point (commitBatch,
        commitBatchWithProof, commitState): each witness's action is that entry point and its counter-law proof
        re-checks."""
        self.check_entry_witnesses(LAW_363, list(COMMITS))

    def test_636_is_refuted_by_finalize_batch_at_index_zero(self):
        """I15-P4 (model half): the :636 law is REFUTED (NOT proved by coercion_guard, as the plan expected): its only
        entry point finalizeBatch reaches the checked _batchIndex - 1 with idx = 0, from a state where lfi = 0."""
        self.check_entry_witnesses(LAW_636, ["finalizeBatch"])
        w = rec(LAW_636)["witnesses"]["finalizeBatch"]["witness"]
        self.assertEqual(w["a"]["idx"], 0)

    def check_entry_witnesses(self, lid: str, entries: list[str]) -> None:
        r = rec(lid)
        self.assertEqual(r["status"], "REFUTED")
        self.assertEqual(sorted(r["witnesses"]), entries)
        laws_bend = H.GEN2 / "laws" / lid / "LAWS.bend"
        self.assertTrue(laws_bend.exists())
        lt = laws_bend.read_text()
        self.assertEqual(re.findall(r"(?m)^law\s+(\w+)\s*:", lt), ["cl_" + lid.lower()])
        self.assertRegex(lt, r"(?m)^\s*exs\s+a\s*:")
        self.assertIn("!= True{}", lt)
        for e in entries:
            with self.subTest(entry=e):
                w = r["witnesses"][e]
                self.assertEqual(w["status"], "REFUTED")
                self.assertEqual(w["witness"]["a"]["op"], e)
                self.assertIsInstance(w["witness"]["s"]["run"], list)
                self.assertEqual(w["checker"]["marker"], "ALL PROOFS CHECK")
                proof = resolve(w["proof"])
                self.assertEqual(proof, H.GEN2 / "proofs" / lid / f"entry_{e}" / "PROOF.bend")
                code, out = bend_check(proof)
                self.assertEqual(code, 0, out[-1500:])
                pt = proof.read_text()
                self.assertIn(f"M.A_{e}{{", pt)
                self.assertRegex(pt, r"(?m)^import \S*laws/" + re.escape(lid) + r"/LAWS\.bend as Laws$")


class TestReplay(unittest.TestCase):
    """The REFUTED per-entry witnesses on the real code, through the prereg instrument (tests_m2/_i15.py), and holon's
    own replay report. One instrument run for all of them."""

    @classmethod
    def setUpClass(cls):
        cls.items = []
        for lid in REFUTED:
            p = H.RESULTS2 / f"{lid}.json"
            if not p.exists():
                continue
            r = load_json(p)
            for e in sorted(r.get("witnesses") or {}):
                w = r["witnesses"][e]
                if w.get("status") == "REFUTED" and w.get("witness"):
                    cls.items.append((lid, e, H.witness_trace(w["witness"])))
        cls.real = H.run_site_instrument([t for _, _, t in cls.items]) if cls.items else []

    def replayed(self, lid: str) -> dict:
        got = {e: (t, res) for (l, e, t), res in zip(self.items, self.real) if l == lid}
        self.assertTrue(got, f"no REFUTED witness of {lid} to replay")
        return got

    def check_panics_at(self, lid: str, entries: list[str], span: str) -> None:
        got = self.replayed(lid)
        self.assertEqual(sorted(got), entries)
        for e, (trace, res) in sorted(got.items()):
            with self.subTest(entry=e):
                self.assertEqual(res["outcomes"][:-1], ["ok"] * (len(trace) - 1), "every prefix step succeeds")
                self.assertEqual(res["outcomes"][-1], "rev panic:0x11")
                self.assertIsNotNone(res["panic"], "the last step raised no Panic")
                self.assertEqual(res["panic"]["code"], 0x11)
                self.assertEqual(res["panic"]["contract"], "Rollup")
                self.assertTrue(in_span(span, res["panic"]), res["panic"])

    def test_363_witnesses_replay_as_panic_0x11_at_rollup_363(self):
        """I15-P3 (replay half): each of the three witnesses replays on the real code at the pinned commit with every
        prefix step succeeding and the entry point reverting with Panic(0x11) raised at Rollup.sol:363."""
        self.check_panics_at(LAW_363, list(COMMITS), "contracts/contracts/l1/rollup/Rollup.sol:363")

    def test_636_witness_replays_as_panic_0x11_at_rollup_636(self):
        """I15-P4 (replay half): finalizeBatch at index 0 reverts on the real code with Panic(0x11) raised at
        Rollup.sol:636 (finalizedStateRoots[_batchIndex - 1]), before the 'incorrect batch index' check at :643."""
        self.check_panics_at(LAW_636, ["finalizeBatch"], "contracts/contracts/l1/rollup/Rollup.sol:636")

    def test_holon_replay_report_agrees_with_the_instrument(self):
        """Construction: replay/M2/report.json binds every REFUTED per-entry witness, says passed and observed, and names
        the same panic site as the instrument; each record's per-entry replay status is passed."""
        self.assertTrue(self.items, "no REFUTED per-entry witness to compare")
        rep = load_json(H.REPLAY2)
        canon = lambda w: H.sha256_json(w)
        for (lid, e, trace), res in zip(self.items, self.real):
            with self.subTest(law=lid, entry=e):
                self.assertIsNotNone(res["panic"], "the instrument located no Panic")
                ent = rep["laws"][lid]["entries"][e]
                self.assertEqual(ent["trace"], trace)
                self.assertEqual(ent["status"], "passed")
                self.assertTrue(ent["obstruction_observed"])
                self.assertEqual(ent["panic_site"], f"contracts/{res['panic']['path']}:{res['panic']['line']}")
                r = rec(lid)
                self.assertEqual(rep["entry_witness_sha256"][lid][e], canon(r["witnesses"][e]["witness"]))
                self.assertEqual(r["witnesses"][e]["replay"]["status"], "passed")
                self.assertEqual(r["witnesses"][e]["replay"]["panic_site"], ent["panic_site"])
            self.assertEqual(rep["laws"][lid]["status"], "passed")


class TestMut2Outcomes(unittest.TestCase):
    """MUT2 in a copy (as tests_m2/test_sort_sites.py::TestMut2Derivation), then `holon run --milestone M2 --laws`."""

    def test_363_still_refuted_through_the_two_unmutated_entry_points(self):
        """I15-P5 (run half): under MUT2 the :363 law is REFUTED through commitBatch and commitState, one checked witness
        each, and reaches commitBatchWithProof no more; the new :360-364 law is REFUTED through commitBatchWithProof (the
        mutated model computes W + cstart - t unchecked: the site law catches what the dropped require modelled)."""
        repo = copy_repo()
        try:
            mut = next(m for m in load_json(H.MUTATIONS)["mutations"] if m["id"].startswith("MUT2"))
            p = repo / ROLLUP_REL
            f = load_json(p)
            node, *path = mut["edit"]["pointer"].strip("/").split("/")
            cur = f[node]
            for k in path[:-1]:
                cur = cur[int(k)] if isinstance(cur, list) else cur[k]
            cur[path[-1]] = mut["edit"]["value"]
            write_json(p, f)
            tmp = repo.parent
            a = run_holon(["sorts", "--milestone", "M2"], cwd=repo)
            b = run_holon(["derive", "--milestone", "M2"], cwd=repo)
            c = run_holon(["run", "--milestone", "M2", "--laws", f"{LAW_363},{LAW_MUT2_NEW}", "--out", str(tmp / "results"),
                           "--gen-dir", str(tmp / "gen")], cwd=repo, timeout=5400)
            log = "\n".join(x.stdout[-2000:] + x.stderr[-2000:] for x in (a, b, c))
            self.assertEqual((a.returncode, b.returncode, c.returncode), (0, 0, 0), log)
            r = load_json(tmp / "results" / f"{LAW_363}.json")
            self.assertEqual(r["status"], "REFUTED", log)
            self.assertEqual(sorted(r["witnesses"]), ["commitBatch", "commitState"])
            for e, w in r["witnesses"].items():
                self.assertEqual((w["status"], w["witness"]["a"]["op"]), ("REFUTED", e))
                self.assertEqual(w["checker"]["marker"], "ALL PROOFS CHECK")
            n = load_json(tmp / "results" / f"{LAW_MUT2_NEW}.json")
            self.assertEqual(n["status"], "REFUTED", log)
            self.assertEqual(sorted(n["witnesses"]), ["commitBatchWithProof"])
            self.assertEqual(n["witnesses"]["commitBatchWithProof"]["status"], "REFUTED")
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
