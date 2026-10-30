"""I70 (= I36c): the cutover x slash laws, O13 and O20's economic half, over the real legacy staking code (whitepaper
§5.3 NAT, §7.5 SORT, §11.3 O13 and O20, Appendix A F10; docs/HUMAN_ANSWERS.md Q12; BUILD_PLAN I36 and rows I69 and
I70). This docstring is the contract; its sha256 is the key's thresholds.contract_docstring_sha256.

Scope. BUILD_PLAN I36 predicts O13 REFUTED ("cutover x slash": F10, slashing is vacuous for pre-cutover batches) and,
for O20's economic half, that a slash on a pre-cutover batch transfers zero, so a conservation or π law is REFUTED;
O20's π split law itself is the lead's I34. I69 (= I36a) recovered the legacy registry (L1Staking's proxy
0x0dc417f8..43f7, its implementation 0xdb073410..f714 matched to the v0.6.1 tag build, metadata stripped) and
extracted it; I28 built the Rollup's versioned machine (V3..V11) whose cutover V10->V11 retypes batchDataStore (the
fourth member was signedSequencersBitmap, now submitter) and reinterprets the registry word (l1StakingContract, now
submitterContract); I83 makes the pre-V11 commits compile, so a batch committed at V10 is in flight at V11; I29 states
NAT's squares and I86 SORT's conservation. Neither can state O13 or O20's economic half: I29's square answers the
registry's call from one environment shared by both sides, so the slash's reward cannot differ between them; I86's
conservation is the inflow half, and a vacuous slash conserves (0 = 0). I70 links the legacy registry to the old
version and the new registry to the new one, and states the two laws over that link.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an instrument_inconsistency line of
spec/M3/amendments.jsonl): tests_m3/_i70.py (the rules S1-S3, P1's decision and P3's recount written a second time,
independently of holon/); spec/M3/lib/cutover_slash.json (the sidecar: outputs, acquisition plan, link, corpus, search,
replay, environment premise, catalog); spec/M3/lib/cutover_slash_basis.json (tests_m3/_i70.py::basis at the prereg).
The key's thresholds pin all three and this docstring by sha256, with the inputs of thresholds.inputs_sha256.

Acquisition (A1-A3; Q12)
  A1 The explorer's verified source of the registry implementation is read once, after the prereg is pushed, by the
     session's Etherscan connector (getsourcecode, chain 1) and committed verbatim at
     results/M3/cutover/explorer/<address>.json ({"address", "chainid", "explorer", "response"}). Never scroll-tech/*
     or spec/heldout/.
  A2 The compile match (the sidecar's criterion): the verified sources compiled by the pinned solc with the explorer's
     recorded settings give contract L1Staking a runtime code whose identity (I63's rule: immutable and link ranges
     zeroed, CBOR metadata stripped) equals the on-chain code's (I69's committed code file); and the verified source
     set holds the unit contracts/l1/staking/L1Staking.sol whose text equals the v0.6.1 blob (sha256 pinned).
  A3 `python -m holon cutover acquire [--check]` writes results/M3/cutover/acquisition.json: the registry's label (the
     sidecar's labels: verified, tag_matched, bytecode, standin), the explorer record's sha256, A2's two results, the
     eras of the edge (V10 from block 25236554 to the cutover block 26031669) and the implementations live in the V10
     era of every member the link runs (from I69's timeline and I28's versioned document). The label decides which
     code the link runs: the extracted v0.6.1 document when verified or tag_matched; otherwise the model is labelled.

The model and the link (M1-M3, L1-L4)
  M1 `python -m holon cutover model [--check]` compiles the legacy registry's document (I69's
     gen/M3/bundle/documents/l1staking.json) with holon.sorts.model3's untyped compiler, as `holon bundle model`
     compiles a head member, into gen/M3/cutover/models/l1staking.bend (+ .init.json), with its model debt in
     gen/M3/cutover/models/models.json. Any model3 extension is generic, emitted only into a model that uses it, and
     every model model3 compiled before compiles byte for byte.
  M2 The model refines the real registry: on every corpus step whose frames include the registry, the model agrees
     with the real code (status, revert key, return data, the registry's storage at every slot either side writes, its
     logs), from the registry's real pre-state with the recorded answers to its own calls
     (results/M3/cutover/refinement_models.json).
  L1 The linked cutover machine runs I69's rules L1-L8 over a bundle whose Rollup member is versioned: its program is
     the document of the state's version (gen/M3/versions/documents/<v>.json), and the edge's migration step (the
     admin's upgradeToAndCall with the edge's introduced initializer, under I28's A-proxy) switches it. The legacy
     registry is a member at the old version, linked through the old version's reads of the reinterpreted entry; the
     new registry (I69's Submitter) at the new version, through the reinterpreted entry.
  L2 The deployment (replay/M3/cutover/deployment.json): I69's members at their head builds, the Rollup proxy at V10's
     implementation built from V10's commit, the legacy registry built from v0.6.1 behind its own proxy, each
     initialized by the deployment's owner; the queue's whitelist holds the legacy registry (the sidecar's
     environment premise).
  L3 The corpus (gen/M3/cutover/corpus.json): the sidecar's planted traces T1-T4, verbatim by label, with arguments
     filled from the deployment and earlier steps only.
  L4 `python -m holon cutover refine [--check]` runs every corpus step on the linked machine and on the real code
     (forge, through a harness under replay/M3/cutover/) and compares status, revert data, return data, every member's
     storage at every touched slot, logs, balances and frames; per-step rows in results/M3/cutover/steps.json
     ({"steps": [{"trace", "index", "label", "version", "agree", "unsupported", "frames": [[parent, caller, member,
     selector, value, ok]..]}]}), totals in results/M3/cutover/refinement.json.

The laws (S1-S6, stage 2: built only after I29, I83 and I86 have landed)
  S1 For each MIG edge a->b of the versioned document: its retyped in-flight entries T and its reinterpreted entries R
     (the entry at b, its reads at a).
  S2 A cutover slash site of an action at version v is a call (i) whose receiver is a registry word of R at v (the
     entry at b, a read at a), (ii) one of whose arguments reads a member of an entry of T, and (iii) whose result is
     credited to a mapping cell (a write of a mapping family whose value reads that family and holds the call's
     result). Computed from the versioned machine's MIG-edge data and the documents alone; no target name, law id or
     action is special-cased in holon/.
  S3 One site pair per (edge a->b, action op of b with an action of a of the same selector) with a site at a and a site
     at b; per pair two holon-ir/0.3 laws: NAT sub-form "slash", L_nat_slash_<contract>_<a>_<b>_<op>, and SORT sub-form
     "slash", L_sort_slash_<contract>_<a>_<b>_<op>; facts the versioned document. The catalog: the next free
     holon-rules version when I70's predecessor in the chain lands, holding every earlier catalog's producers as the
     same objects (expected 1.12), fixed and disclosed at the re-derive; every earlier M3 law changes only in
     rule_catalog_version, each change a catalog_rederivation line.
  S4 The statement's claim is {"eq": [{"slash": "<model>:<subform>:<a>:<b>:<op>", "on": [binders]}, {"bool": true}]},
     the term additive in spec/schemas/law_ir_0_3.schema.json (docs/adoption/Q4/ following it byte for byte), hashed
     through the ref "slash:<id>" (the sha256 of the canonical {template "holon.rules.slash/<subform>",
     template_version 1, subform, edge, op, the site pair recomputed from the documents}). LAWS.bend
     (gen/M3/laws/<id>/LAWS.bend) imports the linked layer gen/M3/cutover/models/linked.bend (the versioned layer and
     both registries' models) and the claims module gen/M3/cutover/claims/slash.bend, and states over the tables, a
     linked state s with its reachability (the product of the versioned layer's VReach and each registry model's
     Reach, under the wiring premise: the Rollup's registry word at a names the legacy registry, the migration's
     registry argument names the new one, each registry's Rollup word names the Rollup), a batch index k, the edge's
     migration choice u and the registries' environments ea and eb, that the claim function is True{}; the counter-law
     cl_<id lowercased> states its negation with exs.
  S5 The answer of a site at v: the v-registry model's step on the site's call (receiver the registry word read from
     the Rollup's storage, calldata the site's call with its arguments evaluated on the Rollup's storage at the key k,
     caller the Rollup, value the site's) at the registry's state, under environment e: (ok, the return word). The
     premises: the state is at version a; k is in flight (lastFinalizedBatchIndex < k <= lastCommittedBatchIndex); u
     succeeds; every answer in ea and eb is ok (the sidecar's environment premise). NAT slash (O13): the answer of the
     b-site at the migrated state equals the answer of the a-site at s (naturality, §5.3 (b), observed at the slash
     site). SORT slash (O20's economic half): if the a-site's return word is nonzero, the b-site's is nonzero (a slash
     that would move value before the cutover still moves value after it).
  S6 Decision: the witness search of the sidecar over the compiled models (bend -o .mjs), never the oracle; a witness's
     counter-law PROOF.bend holds the linked trace's states and steps with their step equations, the link equations
     (every answer the trace's Rollup steps take from a registry equals that registry model's answer at its state
     then, by computation), and the claim false there by computation; Bend accepts it, and BendTT too when the verdict
     is enabled: REFUTED. Otherwise UNKNOWN with what was tried. No generator proves a slash law.

Replay (RP1-RP2)
  RP1 `python -m holon cutover replay [--check]` writes replay/M3/cutover/report.json: for every REFUTED slash law two
      runs on the real code (the sidecar's replay: left, the witness trace, the cutover, the challenge of k at b, the
      proof window, the op by an active principal of the new registry; right, the trace, the challenge of k at a, the
      window, the op by an active principal of the legacy registry), each step compared with the linked model, and
      each run's observed reward (the challenger's batchChallengeReward less its deposit).
  RP2 A run passes when every step agrees and the observed reward equals the model's answer of its side. G6 binds each
      REFUTED slash record to its two passed runs.

Own commits. C_K is the first commit, oldest first, whose spec/M3/predictions.json holds the key I70; end is the oldest
commit reachable from HEAD that adds docs/iterations/I70.md, else HEAD. I70's own commits are the non-merge commits of
`git log --first-parent C_K..end` when C_K is on end's first-parent chain; none otherwise. The branch reaches the lead
only as the second parent of a merge commit and merges only the lead.

Commit rules: no own commit writes a frozen root, gen/M3/versions/, gen/M3/history/, results/M3/history/,
replay/M3/versions/, holon/versions/, gen/M3/bundle/, results/M3/bundle/, replay/M3/bundle/, gen/M3/nat/,
gen/M3/bundle_laws/, I70's sidecar or basis, or another key's sidecar or instrument; an M3 law file other than the two
slash laws changes only in rule_catalog_version; an M1, M2 or T32 record changes only in generator_sha256 and keys named
seconds; an M3 record other than the two slash records keeps its status.

Commands
  python -m holon cutover acquire|model|corpus|refine|analyze|replay [--check]
  python -m holon derive --milestone M3                (the catalog with the two slash sub-forms)
  python -m holon run --milestone M3 --laws <the two slash ids>
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import unittest
from pathlib import Path

import tests_m3._i70 as I
from tests_m3._m3 import ROOT, file_sha256, load_json, predictions, run_bend

KEY = "I70"
REPORT = "docs/iterations/I70.md"
SIDECAR = ROOT / "spec" / "M3" / "lib" / "cutover_slash.json"
NAT_ID = "L_nat_slash_Rollup_V10_V11_proveState"
SORT_ID = "L_sort_slash_Rollup_V10_V11_proveState"
LAW_IDS = [NAT_ID, SORT_ID]
ESCAPES = re.compile(r"\?[A-Za-z_]\w*|\?TODO|@unsafe|\bdef\s+\w+\?\s*\(|import\s+\"[^\"]*\.c\"")
FORBIDDEN_OWN = ("gen/M3/versions/", "gen/M3/history/", "results/M3/history/", "replay/M3/versions/", "holon/versions/",
                 "gen/M3/bundle/", "results/M3/bundle/", "replay/M3/bundle/", "gen/M3/nat/", "gen/M3/bundle_laws/",
                 "spec/M3/lib/cutover_slash.json", "spec/M3/lib/cutover_slash_basis.json",
                 "facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/", "docs/M0_SPEC.md",
                 "docs/BEND_PRIMER.md", "AGENTS.md", "tools/freeze.py", "FROZEN.sha256")


def side() -> dict:
    return load_json(SIDECAR)


def need(rel: str) -> Path:
    p = ROOT / rel
    if not p.exists():
        raise AssertionError(f"{rel} is missing (I70 builds it)")
    return p


def git(*args) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), "-c", "core.quotepath=false", *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def prereg_commit() -> str:
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(doc, dict) and KEY in (doc.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I70")


def end_commit() -> str:
    out = git("log", "--format=%H", "--reverse", "--diff-filter=A", "HEAD", "--", REPORT).split()
    return out[0] if out else git("rev-parse", "HEAD").strip()


def own_commits() -> list:
    ck, end = prereg_commit(), end_commit()
    chain = git("log", "--first-parent", "--format=%H %P", f"{ck}^..{end}").splitlines()
    if not any(line.split()[0] == ck for line in chain):
        return []
    return [line.split()[0] for line in git("log", "--first-parent", "--format=%H %P", f"{ck}..{end}").splitlines()
            if len(line.split()) == 2]


def record(law_id: str) -> dict:
    return load_json(need(f"results/M3/{law_id}.json"))


# ---------------------------------------------------------------------------------------------- pins
class TestPins(unittest.TestCase):
    def test_instruments_are_the_prereg_ones(self):
        th = predictions(KEY)["thresholds"]
        self.assertEqual(file_sha256(ROOT / th["instrument"]), th["instrument_sha256"])
        self.assertEqual(file_sha256(ROOT / th["sidecar"]), th["sidecar_sha256"])
        self.assertEqual(file_sha256(ROOT / th["basis"]), th["basis_sha256"])
        import hashlib
        import ast
        doc = ast.get_docstring(ast.parse(Path(__file__).read_text(encoding="utf-8")), clean=False)
        self.assertEqual(hashlib.sha256(doc.encode("utf-8")).hexdigest(), th["contract_docstring_sha256"])

    def test_the_basis_recomputes(self):
        """S1-S3 at HEAD: the instrument's basis equals the committed one (construction)."""
        self.assertEqual(I.basis(ROOT), load_json(ROOT / predictions(KEY)["thresholds"]["basis"]))


# ---------------------------------------------------------------------------------------------- P1
class TestAcquisition(unittest.TestCase):
    def test_p1_the_registry_source_is_verified_and_compile_matched(self):
        d = I.decide_p1(ROOT)
        self.assertTrue(d["verified"], "the explorer holds no verified source for the registry implementation")
        self.assertTrue(d["unit_equal"], "the verified L1Staking.sol differs from the v0.6.1 blob")
        self.assertTrue(d["compile_match"], "the verified source does not compile to the deployed code")
        acq = load_json(need(side()["outputs"]["acquisition"]))
        self.assertEqual(acq.get("label"), side()["acquisition"]["labels"]["verified"])


# ---------------------------------------------------------------------------------------------- P2, P3
class TestModelAndLink(unittest.TestCase):
    def test_p2_the_registry_model_compiles_and_refines(self):
        out = side()["outputs"]
        need(f"{out['models']}/l1staking.bend")
        models = load_json(need(f"{out['models']}/models.json"))
        corpus = load_json(need(out["corpus"]))
        used = sorted({s["action"] for t in corpus["traces"] for s in t["steps"]
                       if s.get("member") == "l1staking" and s.get("action")})
        debt = {d["action"] for d in (models.get("l1staking") or {}).get("debt") or []}
        self.assertEqual(sorted(set(used) & debt), [], "model debt in an action the corpus calls")
        ref = load_json(need(out["model_refinement"]))
        reg = ref["members"]["l1staking"]
        self.assertGreater(reg["steps"], 0)
        self.assertEqual(reg["disagreements"], 0)
        self.assertEqual(reg["unsupported"], 0)

    def test_p3_the_linked_cutover_machine_refines_the_real_code(self):
        out = side()["outputs"]
        steps = load_json(need(out["steps"]))
        rec = load_json(need(out["refinement"]))
        rc = I.recount(steps)
        for k in ("steps", "disagreements", "unsupported", "by_version", "links"):
            self.assertEqual(rec.get(k), rc[k], k)
        self.assertEqual(rc["disagreements"], 0)
        self.assertEqual(rc["unsupported"], 0)
        traces = {r["trace"] for r in steps["steps"]}
        self.assertEqual(traces, set(side()["corpus"]["traces"]))
        self.assertGreater(rc["by_version"].get("V10", 0), 0)
        self.assertGreater(rc["by_version"].get("V11", 0), 0)
        links = rc["links"]
        for caller, callee in (("rollup", "l1staking"), ("rollup", "submitter"), ("l1staking", "messenger"),
                               ("l1staking", "rollup")):
            self.assertTrue(any(k.startswith(f"{caller}->{callee}:") for k in links), f"no ok frame {caller}->{callee}")


# ---------------------------------------------------------------------------------------------- P4-P6
class TestLaws(unittest.TestCase):
    def test_p4_the_generator_emits_the_basis(self):
        bas = load_json(ROOT / predictions(KEY)["thresholds"]["basis"])
        ana = load_json(need(side()["outputs"]["analysis"]))
        self.assertEqual(ana.get("pairs"), bas["pairs"])
        ids = sorted(p.stem for p in (ROOT / "laws" / "M3").glob("L_*_slash_*.json"))
        self.assertEqual(ids, bas["law_ids"])
        for lid, sub in ((NAT_ID, ("NAT", "slash")), (SORT_ID, ("SORT", "slash"))):
            law = load_json(ROOT / "laws" / "M3" / f"{lid}.json")
            self.assertEqual((law["rule"], law["subform"]), sub)
            claim = law["statement"]["claim"]
            self.assertEqual(claim["eq"][1], {"bool": True})
            self.assertIn("slash", claim["eq"][0])

    def _refuted(self, lid: str):
        rec = record(lid)
        self.assertEqual(rec["status"], "REFUTED", f"{lid}: {rec['status']}")
        laws = need(f"gen/M3/laws/{lid}/LAWS.bend").read_text(encoding="utf-8")
        proof = need(f"gen/M3/proofs/{lid}/PROOF.bend")
        self.assertIsNone(ESCAPES.search(laws + proof.read_text(encoding="utf-8")))
        self.assertIn(f"law cl_{lid.lower()}", laws)
        code, out = run_bend([proof.name], cwd=proof.parent, timeout=600)
        self.assertEqual(code, 0, out[-1600:])
        self.assertTrue(out.startswith("ALL PROOFS CHECK"), out[:400])
        w = rec["witness"]
        self.assertTrue(w["left"]["ok"] and w["right"]["ok"])
        rep = load_json(need(side()["outputs"]["replay"]))
        runs = {x["id"]: x for x in rep["runs"]}
        for s in ("left", "right"):
            run = runs[f"{lid}:{s}"]
            self.assertTrue(run["passed"], f"{lid}:{s}")
            self.assertEqual(int(run["observed_reward"]), int(w[s]["ret"]))
        return w

    def test_p5_o13_the_slash_naturality_law_is_refuted(self):
        w = self._refuted(NAT_ID)
        self.assertEqual(int(w["left"]["ret"]), 0)
        self.assertGreater(int(w["right"]["ret"]), 0)

    def test_p6_o20_economic_half_the_slash_value_law_is_refuted(self):
        w = self._refuted(SORT_ID)
        self.assertEqual(int(w["left"]["ret"]), 0)
        self.assertGreater(int(w["right"]["ret"]), 0)


# ---------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    def test_r1_earlier_outputs_do_not_move(self):
        th = predictions(KEY)["thresholds"]
        for rel, sha in th["inputs_sha256"].items():
            self.assertEqual(file_sha256(ROOT / rel), sha, rel)
        for cmd in (["bundle", "extract", "--check"], ["versions", "extract", "--check"]):
            p = subprocess.run(["python", "-m", "holon", *cmd], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, " ".join(cmd) + ": " + p.stderr[-600:])

    def test_r2_own_commits_touch_nothing_forbidden(self):
        bad = []
        for c in own_commits():
            for path in git("diff-tree", "--no-commit-id", "--name-only", "-r", c).split():
                if path.startswith(FORBIDDEN_OWN):
                    bad.append(f"{c[:12]} {path}")
        self.assertEqual(bad, [])

    def test_r3_prereg_audits_pass(self):
        for m in ("M3", "M2"):
            p = subprocess.run(["python", "-m", "holon", "audit", "prereg", "--milestone", m], cwd=ROOT,
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, m + ": " + p.stdout[-800:])

    def test_r4_own_code_names_no_target(self):
        """The holon files I70's own commits add or change are not among tests_m2.test_target_agnostic_exhaustive's
        failures."""
        own = set()
        for c in own_commits():
            own |= {p for p in git("diff-tree", "--no-commit-id", "--name-only", "-r", c).split()
                    if p.startswith("holon/")}
        p = subprocess.run(["python", "-m", "unittest", "tests_m2.test_target_agnostic_exhaustive"], cwd=ROOT,
                           capture_output=True, text=True)
        named = sorted(f for f in own if f in p.stdout + p.stderr)
        self.assertEqual(named, [])


if __name__ == "__main__":
    unittest.main()
