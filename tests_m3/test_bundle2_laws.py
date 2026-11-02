"""I84 (= I37b): Bundle II's laws over I80's extraction (whitepaper §5.1 PAR-domain, §5.5 FACT, §5.7 DISCH and
self-controlled enabledness, §3.8 En_G, §8.5 HypC, App. D cost; Appendix A O3/F14, O23/F11d, O35/F1; BUILD_PLAN I37 and
row I84). This docstring is the contract; its sha256 is the key's thresholds.contract_docstring_sha256.

Scope. BUILD_PLAN I37 predicts O3 REFUTED, O23 REFUTED with F(PI, parent lbn) = 64 bits, calibrated costs within 5% of
forge gas at backlogs 1..64, and O35 (some submitter strategy with backlog k <= 64 pushes challengeState out of En_G).
I80 (= I37a, merged at 873cb0d9) extracted, modelled, linked and refined the verifier router and named the zkEVM
verifier's debt; its report names a loop-record gap (the router's break-only `found`, Q-I80-e) that leaves the router's
getVerifier and verifyAggregateProof as model debt. I84 closes that gap with a generic frontend rule, states I37's laws
under a new rule catalog, calibrates the backlog cost, decides the laws with the pinned Bend and replays every witness
on the real code.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and a line in spec/M3/amendments.jsonl):
tests_m3/_i84.py (the rules below written a second time, independently of holon/); spec/M3/lib/bundle2_laws.json (the
sidecar: the laws' deployment, the gas ceiling's source, the calibration design, the consumers' receiver binding,
budgets and search bounds; no outcome); spec/M3/lib/bundle2_laws_basis.json (tests_m3/_i84.py::basis at the prereg).
The key's thresholds pin all three and this docstring by sha256.

Inputs, read and never written: I80's sidecar spec/M3/lib/bundle2.json and its declaration's links (L2), public-input
views (E4) and cost sites (E5) in gen/M3/bundle2/bundle2.json; the adopted Rollup document
spec/M2/facts/morph_rollup.extracted.json; the extracted Go derivation document
spec/M2/facts/morph_derivation.go.extracted.json and codec document spec/M2/facts/morph_batch.go.extracted.json; the
gas ceiling G = spec/M3/lib/refute.json's gas_limit (I40's); the target's git objects at the pinned head 3e44e795, with
lazy fetching disabled.

The frontend's loop rule (FR1-FR3)
  FR1 A local that a loop's body assigns on a break path only, and that the loop's exit reads (a name of the record's
      at_break or exit that is not carried), is recorded among the loop's carried names: entry its value before the
      loop (the walk's context), value its carried value; a non-breaking iteration leaves it unchanged (its next value,
      where the record lists one, is its carried value). Nothing else of a loop record changes, so a document none of
      whose loops holds such a name extracts byte for byte as before.
  FR2 The adopted Rollup document has no such name (I84-R1): it re-extracts byte for byte, coverage --check passes for
      M2 and M3, and its typed and untyped M3 model texts regenerate byte for byte.
  FR3 `holon bundle2 extract`, `model` and `refine` regenerate I80's outputs under FR1: the router's document, its
      model (with model3's untyped machine and I80's additive extension), the corpus run and the refinement records.

The catalog (C1-C2)
  C1 holon-rules/1.10: the rules of the newest catalog version at the build's base, unchanged (the same producer
     objects), plus PAR's link_domain, FACT's public_input and DISCH's self_controlled, whose producers read the
     sidecar and I80's declaration; catalog_version of M3 and later is holon-rules/1.10. The build's report names the
     base version (holon-rules/1.7, 1.8 and 1.9 are I71's, I29's and I35's; whichever has not landed is chained when it
     merges, by whoever merges second).
  C2 `holon derive --milestone M3` writes exactly the basis's law ids for the three sub-forms (rule N1) and changes no
     other law but in rule_catalog_version.

Law ids (N1): PAR link_domain L_par_ldom_<caller contract>_<action>_<callee contract>_<callee action>, one per link row
(L2) of kind action; FACT public_input L_fact_pi_<contract>_<action>_<getter>, one per consumer field (FC1-FC3) for each
E4 row whose action has an input member named consumers.receiver.solidity_member; DISCH self_controlled
L_disch_self_<contract>_<action>_<loop lines>, one per state-indexed cost site (D1). The basis's law_ids lists them.

PAR link_domain (LD1-LD5; O3)
  LD1 The laws' deployment: I80's deployment, except that the router is constructed with the target's own deploy
      script's arguments (contracts/deploy/016-RollupInit.ts:38-40: versions [1], verifiers [the zkEVM verifier], here
      the stand-in Z1; the basis's deploy_script).
  LD2 The router's domain: dom(vs, v, i) holds iff getVerifier(v, i) on the router's model from state vs succeeds and
      returns a non-zero address (tests_m3/_i84.py::resolve is the same rule over the router's storage).
  LD3 The claim, per link row (rollup, p, src, fn, router, action, b): for every state s the Rollup reaches from the laws'
      deployment, every router state vs the router reaches from its deployment, every input x of p and every
      environment e: if p succeeds at (s, x, e) on the Rollup's typed model (its external calls answered by e: the
      router as an oracle, as HypC states the circuit), then dom(vs, v, i), where v and i are the call's version and
      index arguments by E4's view of x (header byte 0; header bytes 1..8).
  LD4 Search: breadth first over the Rollup's steps from the laws' deployment, up to search.link_domain_max_prefix
      steps before p, the committed batches' versions drawn from search.versions, at the router's deployment state; the
      first witness found is kept.
  LD5 A witness's counter-law, checked by the pinned Bend, makes the law REFUTED; otherwise it is UNKNOWN with its bound.
      Replay: the witness's steps on the real Rollup and router deployed as LD1 says (forge): p reverts on the real code,
      and the real router's getVerifier(v, i) returns address(0) or reverts.

FACT public_input (FC1-FC3, FP1-FP4, FM1-FM3; O23)
  FC1 The consumers are the derivation document's call edges whose callee is a decoder of the codec document of the
      sidecar's header codec, one per decoder (the basis's consumers: BatchIndex, LastBlockNumber, TotalL1MessagePopped,
      Version, each read by ParseBatch and fetchBatchInfoOutline).
  FC2 A consumer's field is its decoder's one read (offset, width, via) in the codec document.
  FC3 The receiver of those reads is the header the derivation takes from the commit transaction's parentBatchHeader
      (the sidecar's sites, checked in the target's git objects: each line as stated, its file's only BatchHeaderBytes(
      construction); on the Solidity side, the action's input member named consumers.receiver.solidity_member).
  FP1 One law per (E4 row whose action has that input member, consumer field): L_fact_pi_<contract>_<action>_<getter>.
  FP2 The claim, Thm 6.8 (iii)'s ker(m) within ker(c): for two runs (s1, x1, e1) and (s2, x2, e2) of the action from
      reachable states that both succeed on the typed model: PI(x1) = PI(x2) implies field(x1) = field(x2), where PI is
      E4's hash argument (keccak256 by the model's own table, under CF) and field the decoder's read of the parent header
      input (a header too short for it reads "none", equal only to "none").
  FP3 Search: runs whose prefixes have at most search.public_input_max_prefix steps, inputs drawn from search's
      versions, last block numbers and L1 message counts, bucketed by PI; the first bucket holding two field values gives
      the witness.
  FP4 A witness's counter-law, checked by the pinned Bend, makes the law REFUTED; otherwise UNKNOWN with its bound.
      Replay: both runs on the real Rollup (forge, the laws' deployment): both succeed, the PI words each passes to the
      router (read from the call's calldata) are equal, and the parent headers' fields differ as the witness says.
  FM1 The measure F(PI, field) of a law: by the class of the field in the headers the commit actions store (the basis's
      field_classes): free (an input member no non-ABI check reads outside a hash preimage) gives the value 8 * width
      bits; checked_joint gives the bound [1, log2 of the admitted values]; computed gives the bound [1, 8 * width].
  FM2 A REFUTED law's lower bound is at least 1 bit (its witness holds two field values in one fiber); a PROVED law's
      measure is 0.
  FM3 The law's record carries the measure under fact.measure: {kind, value, lower, upper, class}.

Calibration (K1-K5; App. D cost)
  K1 The state-indexed cost sites are E5's rows whose count term reads storage only (no parameter, input, environment
      or abstract count): the basis's state_cost_sites (challengeState's loop, Rollup.sol:489-493, count
      lastCommittedBatchIndex - lastFinalizedBatchIndex when positive, else 0).
  K2 The harness replay/M3/bundle2/calibrate/ runs the sidecar's calibration.strategy on the real code for every backlog
      of fit_backlogs and eval_backlogs, from a fresh deployment each, and records the action's calldata and its call
      frame's gas before refunds (vm.lastCallGas().gasTotalUsed) and refund.
  K3 cost(k) = intrinsic(calldata) + frame gas (tests_m3/_i84.py::intrinsic: 21000 + 4 per zero byte + 16 per nonzero
     byte); iters(k) = the count term on the state before the call = k.
  K4 (c0, c1) = ordinary least squares of cost on iters over fit_backlogs only; error(k) = |c0 + c1 * iters(k) -
     cost(k)| / cost(k) over eval_backlogs; the model is calibrated iff every error is at most calibration.tolerance,
     else "uncalibrated" (BUILD_PLAN I37's fallback).
  K5 results/M3/bundle2/calibration.json: {"calibration_version": "holon-bundle2-calibration/0.1", "site", "gas_ceiling",
     "points": {k: {"iters", "calldata", "frame_gas", "refund", "cost"}}, "fit_backlogs", "eval_backlogs", "c0", "c1",
     "errors", "max_error" (decimals rounded to 6), "status", "toolchain"}; `python tools/calibrate_gas.py` writes it and
     `--check` re-runs the harness and compares.

DISCH self_controlled (D1-D6; O35)
  D1 One law per state-indexed cost site of an adopted member's action a (K1): L_disch_self_<contract>_<a>_<lines>.
  D2 The claim, a in En_G (§3.8): for every reachable state s, input x and environment e, if a succeeds at (s, x, e) on
     the typed model then c0 + c1 * iters(s) <= G, with K5's coefficients and G the gas ceiling. The record classifies
     the law self-controlled by the permission classes of the actions that write the count's storage families (from the
     document's writes and principals) and names the class whose actions the witness strategy uses.
  D3 k*_model is the least backlog k with c0 + c1 * k > G (tests_m3/_i84.py::kstar).
  D4 Uncalibrated: UNKNOWN ("uncalibrated"). Calibrated and k*_model <= o35.kernel_budget_steps: the strategy (k*_model
     commits by the active submitter class from the deployment, then a's guards) is searched on the typed model and its
     counter-law over Reach is checked by the pinned Bend: REFUTED when accepted. Calibrated and k*_model beyond the
     budget: UNKNOWN, its attempts naming the calibration, k*_model and the budget.
  D5 Replay on the real code (the laws' deployment): by bisection over the calibration strategy's backlog, k*_real is the
     least backlog at which a's call with a transaction gas limit of G fails while it succeeds with 2G; the report
     records the outcomes at k*_real - 1 (succeeds within G) and at k*_real (fails within G, succeeds within 2G).
  D6 The REFUTED path exists (construction): with the ceiling replaced by c0 + 2 * c1 - 1 (so k* = 2), the decider
     refutes the law with a two-commit witness that the pinned Bend accepts, written outside the repository.

Records and replay (RC1-RC2)
  RC1 Every law of N1 has a holon-record/0.2 record under results/M3/: status, the checker's verdict for a REFUTED law,
      its witness, attempts and, for an UNKNOWN law, the bound; replay {status, detail}.
  RC2 replay/M3/bundle2/laws/report.json: {"replay_version": "holon-bundle2-laws-replay/0.1", "laws": {law_id: {"status":
      passed|failed|not_run, "observed": ..}}} with D5's k*_real for the DISCH law; `holon bundle2 replay-laws --check`
      re-runs nothing and checks the report against the records.

Commands
  python -m holon bundle2 laws [--check]     the analysis gen/M3/bundle2/laws.json (inputs, consumers, classes,
                                             measures, the deployment, k*_model) and the claims modules
  python tools/calibrate_gas.py [--check]    K2-K5
  python -m holon derive --milestone M3      C1-C2
  python -m holon run --milestone M3 --laws <ids>
  python -m holon bundle2 replay-laws [--check]
  Exit codes: 0 written (or --check reproduced); 1 --check differs; 2 refused (a missing or stale input), nothing
  written; 3 a harness, model or checker error, nothing written. Outputs are canonical JSON, byte-identical across runs,
  with no timestamps and no absolute paths.

Own commits: the non-merge commits of `git log --first-parent <prereg>..<end>`, end the first commit adding
docs/iterations/I84.md (HEAD while none does). Commit rules (I84-R2): judged one by one against its first parent, no own
commit changes a frozen root, an earlier M3 law but in rule_catalog_version, or an earlier M3 record's status; at end,
every record directly under results/M1, results/M2 and results/T32 carries a generator_sha256 other than at the prereg
(re-made: the frontend and holon/rules/ are in their closures).

Earlier tests amended at this prereg: none. A test of another key that fails on I84's outcomes is reported under
Surprises, with an amendment line only when its assertion is wrong.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from tests_m3._m3 import ROOT, file_sha256, holon_module, item, load_json, predictions, run_bend, run_holon

KEY = "I84"
SIDE = ROOT / "spec" / "M3" / "lib" / "bundle2_laws.json"
BASIS = ROOT / "spec" / "M3" / "lib" / "bundle2_laws_basis.json"
DECL = ROOT / "gen" / "M3" / "bundle2" / "bundle2.json"
ROUTER_DOC = "gen/M3/bundle2/documents/router.json"
MODELS = ROOT / "gen" / "M3" / "bundle2" / "models"
REF = ROOT / "results" / "M3" / "bundle2" / "refinement.json"
REFM = ROOT / "results" / "M3" / "bundle2" / "refinement_models.json"
CAL = ROOT / "results" / "M3" / "bundle2" / "calibration.json"
ANALYSIS = ROOT / "gen" / "M3" / "bundle2" / "laws.json"
REPLAY = ROOT / "replay" / "M3" / "bundle2" / "laws" / "report.json"
REPORT = "docs/iterations/I84.md"
SUBFORMS = {"link_domain": "PAR", "public_input": "FACT", "self_controlled": "DISCH"}
FROZEN = ("facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/", "AGENTS.md", "tools/freeze.py",
          "docs/M0_SPEC.md", "docs/BEND_PRIMER.md", "FROZEN.sha256")


def th() -> dict:
    return predictions(KEY)["thresholds"]


def need(p: Path) -> dict:
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing")
    return load_json(p)


def instrument():
    import tests_m3._i84 as I
    return I


def basis() -> dict:
    return need(BASIS)


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def show(rev: str, rel: str):
    p = subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{rel}"], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout)
    except ValueError:
        return None


def prereg_commit() -> str:
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I84 (the audit's C_K)."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        d = show(c, "spec/M3/predictions.json")
        if isinstance(d, dict) and KEY in (d.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I84")


def end_commit() -> str:
    added = git("log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--", REPORT).split()
    return added[0] if added else "HEAD"


def own_commits() -> list:
    """I84's own commits, oldest first, each with the paths it changes against its first parent."""
    commits, cur = [], None
    for ln in git("log", "--first-parent", "--no-merges", "--no-renames", "--reverse", "--format=@%H", "--name-only",
                  f"{prereg_commit()}..{end_commit()}").splitlines():
        if ln.startswith("@"):
            cur = (ln[1:], [])
            commits.append(cur)
        elif ln.strip() and cur is not None:
            cur[1].append(ln.strip())
    return commits


def holon_ok(args: list, timeout: int = 7200):
    p = run_holon(args, timeout=timeout)
    return p.returncode, (p.stdout[-1500:] + p.stderr[-1500:])


def law(lid: str) -> dict:
    return need(ROOT / "laws" / "M3" / f"{lid}.json")


def record(lid: str) -> dict:
    return need(ROOT / "results" / "M3" / f"{lid}.json")


def replay_of(lid: str) -> dict:
    rep = need(REPLAY)
    ent = (rep.get("laws") or {}).get(lid)
    if ent is None:
        raise AssertionError(f"{REPLAY.relative_to(ROOT)} has no entry for {lid}")
    return ent


def checked(rec: dict) -> bool:
    ch = rec.get("checker") or {}
    return ch.get("exit_code") == 0 and ch.get("marker") == "ALL PROOFS CHECK"


def ids(sub: str) -> list:
    return basis()["law_ids"][sub]


def calibration_fit():
    """The instrument's fit over the committed calibration record's raw points (K3-K4)."""
    I = instrument()
    cal = need(CAL)
    pts = {int(k): v for k, v in cal["points"].items()}
    side = load_json(SIDE)["calibration"]
    c0, c1 = I.fit(pts, side["fit_backlogs"])
    errs = I.errors(c0, c1, pts, side["eval_backlogs"])
    return cal, pts, c0, c1, errs


# ---------------------------------------------------------------------------------------------- instruments
class TestInstrument(unittest.TestCase):
    """The frozen inputs are what they say they are (construction; green at the prereg)."""

    def test_the_key_pins_the_instruments(self):
        t = th()
        self.assertEqual(file_sha256(SIDE), t["sidecar_sha256"])
        self.assertEqual(file_sha256(BASIS), t["basis_sha256"])
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i84.py"), t["instrument_sha256"])
        d = sys.modules[__name__].__doc__
        self.assertEqual(hashlib.sha256(d.encode("utf-8")).hexdigest(), t["contract_docstring_sha256"])
        self.assertEqual(basis()["sidecar_sha256"], file_sha256(SIDE))

    def test_the_basis_recomputes(self):
        """LD1, FC1-FC3, FM1, E4, K1, N1 recomputed by the instrument from the committed documents, the declaration's
        stable sections and the target's git objects equal the frozen basis."""
        self.assertEqual(instrument().basis(ROOT), basis())

    def test_the_sidecar_names_committed_facts(self):
        """The deploy script's three lines and both receiver sites read as stated; the gas ceiling is I40's; the
        consumer's Solidity member is an input member of the action FP1 names."""
        b = basis()
        self.assertEqual(b["deploy_script"]["matches"], [True, True, True])
        self.assertEqual(b["deploy_script"]["versions"], load_json(SIDE)["deployment"]["router"]["versions"])
        for s in b["receiver_sites"]:
            with self.subTest(site=s["path"]):
                self.assertTrue(s["matches"])
                self.assertEqual(s["constructions"], 1)
        self.assertEqual(b["gas_ceiling"], load_json(ROOT / "spec" / "M3" / "lib" / "refute.json")["gas_limit"])
        self.assertEqual(b["gas_ceiling"], th()["gas_ceiling"])
        self.assertEqual(sorted(b["law_ids"]["public_input"]), sorted(th()["law_ids"]["public_input"]))


# ---------------------------------------------------------------------------------------------- the frontend
class TestFrontend(unittest.TestCase):

    def test_p1_the_router_carries_found_and_compiles(self):
        """I84-P1: FR1 on the router. Every loop record's at_break and exit names are carried; the router's document
        differs from I80's only in its loop records' carried and next lists; its model compiles all eight actions with
        no model debt, holds no escape hatch and the pinned Bend prints ALL PROOFS CHECK on it."""
        item(KEY, "I84-P1")
        doc = need(ROOT / ROUTER_DOC)
        old = show(th()["base_commit"], ROUTER_DOC)
        self.assertIsNotNone(old, "I80's router document at the base")
        for a in doc["actions"]:
            for lp in a.get("loops") or []:
                carried = {c["name"] for c in lp.get("carried") or [] if isinstance(c["name"], str)}
                names = {c["name"] for c in (lp.get("at_break") or []) + (lp.get("exit") or [])
                         if isinstance(c["name"], str)}
                with self.subTest(action=a["name"], loop=lp.get("src")):
                    self.assertLessEqual(names, carried)
                    found = [c for c in lp["carried"] if c["name"] == "found"]
                    self.assertEqual(len(found), 1)
                    self.assertEqual(found[0]["entry"], 0)

        def strip(d):
            d = json.loads(json.dumps(d))
            for a in d["actions"]:
                for lp in a.get("loops") or []:
                    lp.pop("carried", None)
                    lp.pop("next", None)
            d.pop("extraction", None)
            return d
        self.assertEqual(strip(doc), strip(old))
        mj = need(MODELS / "models.json")
        self.assertEqual(mj.get("debt"), [])
        text = (MODELS / "router.bend").read_text()
        for name in ("getVerifier", "verifyAggregateProof"):
            self.assertRegex(text, rf"(?m)^def run_{name}\(")
        for bad in ("?TODO", "@unsafe", 'import "'):
            self.assertNotIn(bad, text)
        code, out = run_bend([MODELS / "router.bend"], cwd=str(ROOT), timeout=3600)
        self.assertEqual(code, 0, out[-1500:])
        self.assertEqual(out.splitlines()[0].strip() if out.strip() else "", "ALL PROOFS CHECK")

    def test_r1_the_rollup_document_and_models_do_not_move(self):
        """I84-R1 (FR2): the adopted Rollup document re-extracts byte for byte with its sidecar; holon coverage
        --milestone M2 and M3 --check pass; the typed and untyped M3 model texts of the adopted document regenerate byte
        for byte."""
        item(KEY, "I84-R1")
        self.assertEqual(file_sha256(ROOT / "spec" / "M2" / "facts" / "morph_rollup.extracted.json"),
                         th()["rollup_document_sha256"])
        code, out = holon_ok(["extract", "solidity", "--sidecar", "spec/M2/lib/extract_rollup.json", "--check"], 1800)
        self.assertEqual(code, 0, out)
        for m in ("M2", "M3"):
            code, out = holon_ok(["coverage", "--milestone", m, "--check"], 1800)
            self.assertEqual(code, 0, f"{m}: {out}")
        for flag, sub in (([], "models"), (["--untyped"], "untyped/models")):
            with tempfile.TemporaryDirectory(prefix="i84-r1-") as td:
                code, out = holon_ok(["model", "--milestone", "M3", *flag, "--out", td], 1800)
                self.assertEqual(code, 0, out)
                f = "morph_rollup_extracted.bend"
                with self.subTest(model=f"{sub}/{f}"):
                    self.assertEqual((Path(td) / f).read_bytes(),
                                     (ROOT / "gen" / "M3" / "sorts" / sub / f).read_bytes())


class TestRefinement(unittest.TestCase):

    def test_p2_the_refinement_rerun(self):
        """I84-P2 (FR3): I80's corpus re-run under FR1. The linked machine: no disagreement and no unsupported step on
        all 365 traces. The router's model: no unsupported step and exactly one disagreement, which is one of I80's
        committed model disagreements (the S5_rollup_word step-3 status disagreement of I80's Surprise 1)."""
        item(KEY, "I84-P2")
        ref = need(REF)
        self.assertEqual(ref["traces"], 365)
        self.assertEqual(ref["disagreements"], [])
        self.assertEqual(ref["unsupported"], 0)
        refm = need(REFM)["members"]["router"]
        self.assertEqual(refm["unsupported"], 0)
        self.assertEqual(len(refm["disagreements"]), 1)
        old = show(th()["base_commit"], "results/M3/bundle2/refinement_models.json")
        old_ids = {d["id"] for d in old["members"]["router"]["disagreements"]}
        self.assertIn(refm["disagreements"][0]["id"], old_ids)


# ---------------------------------------------------------------------------------------------- the catalog
class TestCatalog(unittest.TestCase):

    def test_c1_the_catalog_version(self):
        """C1 (construction): holon-rules/1.10 holds every rule of the version it chains to with the same producer
        objects, plus the three sub-forms; M3 derives with it."""
        R = holon_module("holon.rules")
        self.assertEqual(R.catalog_version("M3"), "holon-rules/1.10")
        cat = R.CATALOGS["holon-rules/1.10"]
        for sub, rule in SUBFORMS.items():
            with self.subTest(subform=sub):
                self.assertIn(sub, cat.get(rule) or {})
        prev = [v for v in R.CATALOGS if v != "holon-rules/1.10" and v.startswith("holon-rules/1.")]
        base = max(prev, key=lambda v: int(v.rsplit(".", 1)[1]))
        for rule, subs in R.CATALOGS[base].items():
            for sub, prod in subs.items():
                with self.subTest(rule=rule, subform=sub):
                    self.assertIs(cat[rule][sub], prod)

    def test_c2_the_laws_are_the_basis_ids(self):
        """C2/N1 (construction): laws/M3 holds exactly the basis's ids for the three sub-forms, each with its rule,
        subform and rule_catalog_version holon-rules/1.10."""
        have = {}
        for p in sorted((ROOT / "laws" / "M3").glob("L*.json")):
            d = load_json(p)
            if d.get("subform") in SUBFORMS and d.get("rule") == SUBFORMS[d["subform"]]:
                have.setdefault(d["subform"], []).append(p.stem)
        for sub in SUBFORMS:
            with self.subTest(subform=sub):
                self.assertEqual(sorted(have.get(sub, [])), sorted(ids(sub)))
                for lid in ids(sub):
                    self.assertEqual(law(lid).get("rule_catalog_version"), "holon-rules/1.10")


# ---------------------------------------------------------------------------------------------- calibration
class TestCalibration(unittest.TestCase):

    def test_p3_the_cost_is_calibrated_within_tolerance(self):
        """I84-P3 (BUILD_PLAN I37's prediction; K1-K5): fitted on fit_backlogs only, the calibrated cost of the
        state-indexed cost site is within 5% of forge gas at every backlog of eval_backlogs (the instrument's fit over
        the record's raw points), and the record says calibrated."""
        item(KEY, "I84-P3")
        I = instrument()
        cal, pts, c0, c1, errs = calibration_fit()
        side = load_json(SIDE)["calibration"]
        self.assertEqual(cal["site"], basis()["state_cost_sites"][0][:3])
        for k in side["fit_backlogs"] + side["eval_backlogs"]:
            with self.subTest(backlog=k):
                p = pts[k]
                self.assertEqual(p["iters"], k)
                self.assertEqual(p["cost"], I.intrinsic(bytes.fromhex(p["calldata"][2:])) + p["frame_gas"])
        for k, e in errs.items():
            with self.subTest(backlog=k):
                self.assertLessEqual(e, Fraction(side["tolerance"]).limit_denominator(10 ** 6))
        self.assertEqual(cal["status"], "calibrated")
        self.assertEqual(round(float(c0), 6), cal["c0"])
        self.assertEqual(round(float(c1), 6), cal["c1"])

    def test_c3_the_calibration_reproduces(self):
        """K5 (construction): tools/calibrate_gas.py --check re-runs the harness on the real code and reproduces the
        record byte for byte."""
        p = subprocess.run([sys.executable, "tools/calibrate_gas.py", "--check"], cwd=ROOT, capture_output=True,
                           text=True, timeout=7200, env={**os.environ, "BEND_NO_TELEMETRY": "1"})
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])


# ---------------------------------------------------------------------------------------------- O35
class TestO35(unittest.TestCase):

    def lid(self) -> str:
        return ids("self_controlled")[0]

    def test_p4_plan_a_strategy_within_64_leaves_en_g(self):
        """I84-P4 (BUILD_PLAN I37's O35 prediction, registered as written): some submitter strategy with backlog k <= 64
        pushes challengeState out of En_G: the DISCH law is REFUTED by a kernel-checked counter-law whose witness's
        backlog is at most 64."""
        item(KEY, "I84-P4")
        rec = record(self.lid())
        self.assertEqual(rec["status"], "REFUTED")
        self.assertTrue(checked(rec))
        an = need(ANALYSIS)
        self.assertLessEqual(an["self_controlled"][self.lid()]["k_star_model"], 64)

    def test_p5_the_backlog_out_of_en_g_and_its_replay(self):
        """I84-P5 (the agent's prediction; D3-D5): k*_model (the instrument's kstar over the record's coefficients and
        G) and k*_real (D5's bisection on the real code) both lie in thresholds.k_star_band; the law is UNKNOWN with
        attempts naming the calibration, k*_model and the kernel budget; and the replay passes (k*_real - 1 succeeds
        within G; k*_real fails within G and succeeds within 2G)."""
        item(KEY, "I84-P5")
        I = instrument()
        cal, pts, c0, c1, errs = calibration_fit()
        lo, hi = th()["k_star_band"]
        ks = I.kstar(c0, c1, th()["gas_ceiling"])
        self.assertIsNotNone(ks)
        self.assertTrue(lo <= ks <= hi, f"k*_model {ks}")
        an = need(ANALYSIS)["self_controlled"][self.lid()]
        self.assertEqual(an["k_star_model"], ks)
        rec = record(self.lid())
        self.assertEqual(rec["status"], "UNKNOWN")
        att = json.dumps(rec.get("attempts"))
        for word in (str(ks), str(load_json(SIDE)["o35"]["kernel_budget_steps"]), "calibrat"):
            self.assertIn(word, att)
        rep = replay_of(self.lid())
        self.assertEqual(rep["status"], "passed")
        obs = rep["observed"]
        self.assertTrue(lo <= obs["k_star_real"] <= hi, f"k*_real {obs['k_star_real']}")
        self.assertEqual(obs["below"], {"backlog": obs["k_star_real"] - 1, "within_G": "ok"})
        self.assertEqual(obs["at"], {"backlog": obs["k_star_real"], "within_G": "fail", "within_2G": "ok"})

    def test_c4_the_refuted_path_exists(self):
        """D6 (construction): with the ceiling c0 + 2 * c1 - 1 the decider refutes the law with a two-commit witness that
        the pinned Bend accepts (written outside the repository)."""
        B = holon_module("holon.bundle2.laws")
        with tempfile.TemporaryDirectory(prefix="i84-d6-") as td:
            res = B.planted_ceiling(ROOT, self.lid(), Path(td))
            self.assertEqual(res["status"], "REFUTED", res)
            self.assertEqual(res["backlog"], 2)
            self.assertEqual(res["checker"]["marker"], "ALL PROOFS CHECK")


# ---------------------------------------------------------------------------------------------- O23
class TestO23(unittest.TestCase):

    def fact_law(self, getter: str) -> str:
        return next(x for x in ids("public_input") if x.endswith("_" + getter))

    def check_refuted_with_measure(self, getter: str):
        lid = self.fact_law(getter)
        rec = record(lid)
        self.assertEqual(rec["status"], "REFUTED", lid)
        self.assertTrue(checked(rec), lid)
        want = basis()["field_classes"][getter]
        m = (rec.get("fact") or {}).get("measure") or {}
        self.assertEqual(m.get("class"), want["class"])
        self.assertEqual(m.get("kind"), want["kind"])
        if want["kind"] == "value":
            self.assertEqual(m.get("value"), want["value"])
        self.assertEqual(m.get("upper"), want["upper"])
        self.assertGreaterEqual(m.get("lower"), 1.0)
        rep = replay_of(lid)
        self.assertEqual(rep["status"], "passed", lid)
        obs = rep["observed"]
        self.assertEqual(obs["runs"], ["ok", "ok"])
        self.assertEqual(obs["pi"][0], obs["pi"][1])
        self.assertNotEqual(obs["field"][0], obs["field"][1])
        self.assertEqual((rec.get("replay") or {}).get("status"), "passed")

    def test_p6_the_parent_lbn_is_outside_the_public_input(self):
        """I84-P6 (BUILD_PLAN I37's O23 prediction): the FACT public_input law for the parent header's LastBlockNumber
        is REFUTED by a kernel-checked counter-law, its measure is F(PI, parent lbn) = 64 bits (a value: the field is
        free), and its witness replays (equal PI words at the router call, different parent last block numbers)."""
        item(KEY, "I84-P6")
        self.check_refuted_with_measure("LastBlockNumber")
        self.assertEqual(record(self.fact_law("LastBlockNumber"))["fact"]["measure"]["value"], 64.0)

    def test_p7_the_other_parent_reads_are_outside_too(self):
        """I84-P7: the same sub-form's laws for the derivation's other parent-header reads (Version, BatchIndex,
        TotalL1MessagePopped) are REFUTED, each witness replays, and each measure is the basis's class (Version a bound
        [1, log2 3]; BatchIndex and TotalL1MessagePopped bounds [1, 64])."""
        item(KEY, "I84-P7")
        for g in ("Version", "BatchIndex", "TotalL1MessagePopped"):
            with self.subTest(getter=g):
                self.check_refuted_with_measure(g)


# ---------------------------------------------------------------------------------------------- O3
class TestO3(unittest.TestCase):

    def test_p8_commits_outside_the_router_domain(self):
        """I84-P8 (BUILD_PLAN I37's O3 prediction): under the laws' deployment (the router constructed as the deploy
        script constructs it), the three link_domain laws are REFUTED by kernel-checked counter-laws; each witness's
        (version, index) is outside the router's domain by the instrument's rule (a version the deploy script does not
        configure) and its replay passes (the Rollup's proof call reverts on the real code)."""
        item(KEY, "I84-P8")
        I = instrument()
        conf = load_json(SIDE)["deployment"]["router"]["versions"]
        latest = {v: (0, 1) for v in conf}
        for lid in ids("link_domain"):
            with self.subTest(law=lid):
                rec = record(lid)
                self.assertEqual(rec["status"], "REFUTED")
                self.assertTrue(checked(rec))
                an = need(ANALYSIS)["link_domain"][lid]
                v, i = an["witness"]["version"], an["witness"]["index"]
                self.assertNotIn(v, conf)
                self.assertFalse(I.in_domain(latest, {}, v, i))
                rep = replay_of(lid)
                self.assertEqual(rep["status"], "passed")
                self.assertEqual(rep["observed"]["proof_call"], "revert")
                self.assertIn(rep["observed"]["getVerifier"], ("0x" + "00" * 20, "revert"))


# ---------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):

    def test_r2_own_commits_move_no_earlier_outcome(self):
        """I84-R2: judged one by one against its first parent, no own commit changes a frozen root, an earlier M3 law
        but in rule_catalog_version, or an earlier M3 record's status; at end, every record directly under results/M1,
        results/M2 and results/T32 carries a generator_sha256 other than at the prereg."""
        item(KEY, "I84-R2")
        mine = set(ids("link_domain") + ids("public_input") + ids("self_controlled"))
        own = own_commits()
        for sha, paths in own:
            for p in paths:
                with self.subTest(commit=sha[:12], path=p):
                    self.assertFalse(p.startswith(FROZEN), "a frozen root")
                    m = re.fullmatch(r"laws/M3/(L\w+)\.json", p)
                    if m and m.group(1) not in mine:
                        new, old = show(sha, p), show(f"{sha}^", p)
                        if old is not None and new is not None:
                            old.pop("rule_catalog_version", None)
                            new.pop("rule_catalog_version", None)
                            self.assertEqual(new, old, "an earlier law beyond rule_catalog_version")
                    m = re.fullmatch(r"results/M3/(L\w+)\.json", p)
                    if m and m.group(1) not in mine:
                        new, old = show(sha, p), show(f"{sha}^", p)
                        if old is not None and new is not None:
                            self.assertEqual(new.get("status"), old.get("status"), "an earlier record's status")
        if not (ROOT / REPORT).exists():
            self.fail(f"{REPORT} is missing (I84 builds it)")
        c, end = prereg_commit(), end_commit()
        for m in ("M1", "M2", "T32"):
            for p in sorted((ROOT / "results" / m).glob("L*.json")):
                rel = p.relative_to(ROOT).as_posix()
                old, new = show(c, rel), show(end, rel)
                if old is None or new is None:
                    continue
                with self.subTest(record=rel):
                    self.assertNotEqual(new.get("generator_sha256"), old.get("generator_sha256"))

    def test_r3_the_prereg_audits_pass(self):
        """I84-R3: holon audit prereg passes for M2 and M3 (CI's gates are read from the run, in the report)."""
        item(KEY, "I84-R3")
        for m in ("M2", "M3"):
            code, out = holon_ok(["audit", "prereg", "--milestone", m], 1800)
            self.assertEqual(code, 0, f"{m}: {out}")

    def test_r4_the_new_code_names_no_target(self):
        """I84-R4: the modules I84 adds (holon/bundle2/laws*.py, holon/rules/bundle2*.py, tools/calibrate_gas.py) name
        no contract, function, address or host of the target: every one comes from the documents, the declaration or
        the sidecars."""
        item(KEY, "I84-R4")
        files = sorted(ROOT.glob("holon/bundle2/laws*.py")) + sorted(ROOT.glob("holon/rules/bundle2*.py"))
        files.append(ROOT / "tools" / "calibrate_gas.py")
        for f in files:
            self.assertTrue(f.is_file(), f"{f.relative_to(ROOT)} is missing")
        words = ("Rollup", "MultipleVersionRollupVerifier", "ZkEvmVerifier", "challengeState", "commitBatch",
                 "getVerifier", "verifyAggregateProof", "lastCommittedBatchIndex", "lastFinalizedBatchIndex",
                 "parentBatchHeader", "LastBlockNumber", "ParseBatch", "morph", "0x87c1")
        for f in files:
            text = f.read_text()
            body = re.sub(r'(?s)^""".*?"""', "", text, count=1)
            body = "\n".join(ln for ln in body.splitlines() if not ln.lstrip().startswith("#"))
            for w in words:
                with self.subTest(file=f.relative_to(ROOT).as_posix(), word=w):
                    self.assertNotIn(w, body)


if __name__ == "__main__":
    unittest.main()
