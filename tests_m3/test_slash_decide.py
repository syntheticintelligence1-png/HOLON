"""I94 (= I36d): O13 and O20's economic half decided by the checker, and model3's clearing of a deleted struct's
dynamic members (BUILD_PLAN rows I36, I70 and I94; whitepaper §5.3 NAT, §7.5 SORT, §11.3 O13 and O20, Appendix A
F10). This docstring is the contract; its sha256 is the key's thresholds.contract_docstring_sha256.

Scope. I70 (= I36c) derived the two laws L_nat_slash_Rollup_V10_V11_proveState (O13) and
L_sort_slash_Rollup_V10_V11_proveState (O20's economic half) and left both UNKNOWN as model debt (docs/iterations/
I70.md, Not done). I94 builds what they lack and decides them; their statements (laws/M3/, the IR) do not change.
I70-Q1 is answered (the coordinator, 2026-11-03): a witness reaches V10 through the deployed path V3..V10, as I83's
in-flight inhabitants do. The sidecar spec/M3/lib/slash_decide.json (fixed at the prereg, pinned by sha256) names the
inputs, the outputs, the registry's initial state, the search and the replay.

The model3 fix (F1-F2)
  F1 A struct written with the zero value (Solidity's delete, as the extracted documents record it) clears every
     member, as the compiler does: an in-place member as before; a bytes or string member its length slot and, in the
     long form (the slot's lowest bit set), its ceil(length / 32) data slots from keccak256(slot); each slot cleared
     is a touched word. Generic: no target, member or family named.
  F2 Every model model3 compiled before the fix comes out byte-identical, except a model that deletes such a struct:
     of the committed ones, the legacy registry's (gen/M3/cutover/models/l1staking.bend). I70's M2 (`holon cutover
     refine`, results/M3/cutover/refinement_models.json) re-run with the fixed model has 0 disagreements.

The registries' models and the linked layer (K1-K3)
  K1 `holon cutover model` writes both registries' models under gen/M3/cutover/models/: the legacy registry (the
     cutover sidecar's link.a.registry, I70's EXT1 compile) and the new one (link.b.registry, I69's document of it).
     Each model's initial state is that registry's storage in the cutover harness, read from the real code's run: the
     legacy registry's after the sidecar's registry_s0 step (both stakers registered), the new registry's at the
     deployment. replay/M3/cutover/registry_s0.json records it with its source: the trace and step, the harness's block
     number and timestamp, the addresses, and how it was read.
  K2 `holon cutover linked` writes gen/M3/cutover/models/linked.bend from the sidecar's link spec alone: a caller and
     its callees, each either a model3 member model (its store and Reach) or a versioned layer (its versioned state,
     its own version chain and VReach), each callee with the caller's version at which it is linked. It imports every
     member's module and defines, per callee, the conversions of words, stores, hash tables, call answers and
     environments between the caller's module and the callee's, generated from the modules' own type definitions, and
     the linked reachability: the product of the caller's VReach and each callee's Reach or VReach. Nothing in
     holon/ names a member, version or family: I94's instance is the link spec's (the Rollup's versioned layer calling
     the legacy registry at V10 and the new one at V11, both model3 member models); a link whose callee is versioned
     (I92's queue) is another spec. Bend accepts the layer (ALL PROOFS CHECK). The genericity check: the generator run
     on the sidecar's generic_check spec (a callee that is a versioned layer) writes a layer Bend also accepts.
  K3 The claims module gen/M3/cutover/claims/slash.bend (I70's rule S5): the answer of a site at version v is the
     v-registry model's run of the site's action (its argument read from the Rollup's storage at the key k by the
     version's layout, the caller the Rollup's address, which each registry's Rollup word names) at the registry's
     state under its environment: (ok, the first return word). Premises: the state is at the edge's old version; k is
     in flight (lastFinalizedBatchIndex < k <= lastCommittedBatchIndex); the migration u succeeds; the registry word
     the old version reads names the legacy registry's address and the one u writes the new registry's; both
     registries' Rollup words are equal; every answer in each environment is ok. NAT: the new site's answer after u
     equals the old site's at s. SORT: a nonzero old return word implies a nonzero new one. A claim whose premises fail
     is true. Bend accepts the module.

The decision (D1-D4)
  D1 LAWS.bend (gen/M3/laws/<id>/LAWS.bend) states each law over the table kh, the Rollup's state s and its VReach r,
     each registry's state and its Reach (under the converted table), k, u and the two registries' environments, and
     the counter-law cl_<id lowercased> its negation with exs; the binding (holon.bindings) is that emission.
  D2 The search (`holon cutover search`, results/M3/cutover/search.json) runs over the compiled claims module (bend -o
     .mjs), never the oracle. Its candidates: I83's V10->V11 inhabitant trace (results/M3/versions/inflight.json) up to
     the edge's old version, with the initializer's registry argument set to the legacy registry's address and the
     deployment of the cutover harness's other parameters unchanged, then the old version's commit by each staker of
     the registry's initial state in order, its registry calls answered by the registry model's runs at that state and
     its other calls by I83's stand-in; each paired with every k in flight, increasing; u = the edge's initializer with
     the new registry's address and the state's lastCommittedBatchIndex; each environment answers ok every call its
     registry's run makes. The first candidate at which a law's claim is false is its witness (at most the sidecar's
     max_candidates).
  D3 A witness's counter-law PROOF.bend (gen/M3/proofs/<id>/PROOF.bend) holds the trace's states, steps and step
     equations by computation, the link equations (each answer a commit step takes from the registry equals the
     registry model's answer at its state then, by computation), the registries' initial-state proofs, and the claim
     false by computation. Bend accepts it, and BendTT (--verdict) too when the environment enables it: REFUTED, the
     record naming its witness: {"trace", "k", "u", "left": {"ok", "ret"}, "right": {"ok", "ret"}} with left the new
     site's answer after u and right the old site's at s. Otherwise UNKNOWN, with what was tried and what is missing,
     construct by construct. No generator proves a slash law.
  D4 The replay (`holon cutover replay`, replay/M3/cutover/report.json; I70's RP1-RP2): for each REFUTED law two runs
     on the real code through the cutover harness, each from a fresh deployment with the stakers registered as the
     corpus registers them: left, the commit of the witness's batch at the old version by its committer, the
     migration, the challenge of k at the new version, the proof window, the op by an active principal of the new
     registry; right, the commit, the challenge of k at the old version, the window, the op by an active principal of
     the legacy registry. A run passes when every step agrees with the linked machine (holon.cutover.machine) and the
     reward it credits the challenger (its batchChallengeReward less its deposit) equals the witness's answer of its
     side ({id}:left, {id}:right).

Own commits. C_K is the first commit, oldest first, whose spec/M3/predictions.json holds the key I94; end is the oldest
commit reachable from HEAD that adds docs/iterations/I94.md, else HEAD. I94's own commits are the non-merge commits of
`git log --first-parent C_K..end` when C_K is on end's first-parent chain; none otherwise.

Commit rules: no own commit writes a frozen root, gen/M3/versions/, gen/M3/bundle/, gen/M3/bundle2/, gen/M3/sorts/,
gen/M3/nat/, gen/M3/bundle_laws/, results/M3/versions/, results/M3/bundle/, replay/M3/bundle/, replay/M3/versions/,
laws/M3/ (the statements do not change), I70's sidecar, basis or instrument, or I94's sidecar.

Commands
  python -m holon cutover model|linked|search|replay|refine [--check]
  python -m holon run --milestone M3 --laws L_nat_slash_Rollup_V10_V11_proveState,L_sort_slash_Rollup_V10_V11_proveState
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests_m3._m3 import ROOT, file_sha256, load_json, predictions, run_bend

KEY = "I94"
REPORT = "docs/iterations/I94.md"
SIDECAR = ROOT / "spec" / "M3" / "lib" / "slash_decide.json"
NAT_ID = "L_nat_slash_Rollup_V10_V11_proveState"
SORT_ID = "L_sort_slash_Rollup_V10_V11_proveState"
LAW_IDS = [NAT_ID, SORT_ID]
ESCAPES = re.compile(r"\?[A-Za-z_]\w*|\?TODO|@unsafe|\bdef\s+\w+\?\s*\(|import\s+\"[^\"]*\.c\"")
FORBIDDEN_OWN = ("gen/M3/versions/", "gen/M3/bundle/", "gen/M3/bundle2/", "gen/M3/sorts/", "gen/M3/nat/",
                 "gen/M3/bundle_laws/", "results/M3/versions/", "results/M3/bundle/", "replay/M3/bundle/",
                 "replay/M3/versions/", "laws/M3/", "spec/M3/lib/cutover_slash.json",
                 "spec/M3/lib/cutover_slash_basis.json", "tests_m3/_i70.py", "spec/M3/lib/slash_decide.json",
                 "facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/", "docs/M0_SPEC.md",
                 "docs/BEND_PRIMER.md", "AGENTS.md", "tools/freeze.py", "FROZEN.sha256")


def th() -> dict:
    return predictions(KEY)["thresholds"]


def side() -> dict:
    return load_json(SIDECAR)


def need(rel: str) -> Path:
    p = ROOT / rel
    if not p.exists():
        raise AssertionError(f"{rel} is missing (I94 builds it)")
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
    raise AssertionError("no commit holds the key I94")


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


def holon(*args, timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(["python", "-m", "holon", *args], cwd=ROOT, capture_output=True, text=True,
                          timeout=timeout, env={**os.environ, "BEND_NO_TELEMETRY": "1"})


# ---------------------------------------------------------------------------------------------- pins
class TestPins(unittest.TestCase):
    def test_sidecar_and_contract_are_the_prereg_ones(self):
        self.assertEqual(file_sha256(SIDECAR), th()["sidecar_sha256"])
        import ast
        import hashlib
        doc = ast.get_docstring(ast.parse((ROOT / "tests_m3" / "test_slash_decide.py").read_text(encoding="utf-8")))
        self.assertEqual(hashlib.sha256(doc.encode("utf-8")).hexdigest(), th()["contract_docstring_sha256"])

    def test_the_laws_do_not_change(self):
        for lid, sh in th()["statement_hashes"].items():
            self.assertEqual(load_json(ROOT / "laws" / "M3" / "REGISTRY.json")["statements"][lid], sh, lid)


# ---------------------------------------------------------------------------------------------- P1: F1-F2
class TestFix(unittest.TestCase):
    def test_p1_the_registry_model_refines_with_no_disagreement(self):
        ref = load_json(need("results/M3/cutover/refinement_models.json"))
        reg = ref["members"]["l1staking"]
        self.assertGreater(reg["steps"], 0)
        self.assertEqual(reg["disagreements"], 0, ref["details"].get("l1staking"))
        p = holon("cutover", "refine", "--check")
        self.assertEqual(p.returncode, 0, p.stderr[-800:])

    def test_p1_every_earlier_model_is_byte_identical(self):
        for cmd in (["bundle", "model", "--check"], ["versions", "model", "--check"], ["bundle", "laws", "--check"],
                    ["bundle2", "model", "--check"]):
            p = holon(*cmd)
            self.assertEqual(p.returncode, 0, " ".join(cmd) + ": " + (p.stdout + p.stderr)[-800:])
        with tempfile.TemporaryDirectory() as td:
            for flags, rel in (([], "gen/M3/sorts/models"), (["--untyped"], "gen/M3/sorts/untyped/models")):
                out = Path(td) / ("u" if flags else "t")
                p = holon("model", "--milestone", "M3", *flags, "--out", str(out))
                self.assertEqual(p.returncode, 0, p.stderr[-800:])
                for f in sorted(out.glob("*.bend")):
                    self.assertEqual(f.read_bytes(), (ROOT / rel / f.name).read_bytes(), f"{rel}/{f.name}")


# ---------------------------------------------------------------------------------------------- P4: K1-K3
class TestLinked(unittest.TestCase):
    def test_p4_the_linked_layer_and_claims_module_check(self):
        s0 = load_json(need(side()["outputs"]["registry_s0"]))
        for k in ("trace", "step", "block_number", "timestamp", "address", "stakers", "read", "storage"):
            self.assertIn(k, s0)
        for rel in (side()["outputs"]["linked"], side()["outputs"]["claims"]):
            f = need(rel)
            self.assertIsNone(ESCAPES.search(f.read_text(encoding="utf-8")), rel)
            code, out = run_bend([f.name], cwd=f.parent, timeout=1800)
            self.assertEqual(code, 0, out[-1600:])
            self.assertTrue(out.startswith("ALL PROOFS CHECK"), out[:400])


    def test_p5_the_linked_layer_is_generic(self):
        import importlib
        L = importlib.import_module("holon.cutover.linked")
        spec = side()["generic_check"]
        with tempfile.TemporaryDirectory(dir=ROOT / "gen" / "M3" / "cutover" / "models") as td:
            out = Path(td) / "generic.bend"
            L.write_layer(ROOT, spec, out)
            text = out.read_text(encoding="utf-8")
            self.assertIsNone(ESCAPES.search(text))
            code, outp = run_bend([out.name], cwd=out.parent, timeout=1800)
            self.assertEqual(code, 0, outp[-1600:])
            self.assertTrue(outp.startswith("ALL PROOFS CHECK"), outp[:400])


# ---------------------------------------------------------------------------------------------- P2, P3: D1-D4
class TestLaws(unittest.TestCase):
    def _refuted(self, lid: str) -> dict:
        rec = load_json(need(f"results/M3/{lid}.json"))
        self.assertEqual(rec["status"], "REFUTED", f"{lid}: {rec['status']}")
        laws = need(f"gen/M3/laws/{lid}/LAWS.bend").read_text(encoding="utf-8")
        proof = need(f"gen/M3/proofs/{lid}/PROOF.bend")
        self.assertIsNone(ESCAPES.search(laws + proof.read_text(encoding="utf-8")))
        self.assertIn(f"law cl_{lid.lower()}", laws)
        code, out = run_bend([proof.name], cwd=proof.parent, timeout=3600)
        self.assertEqual(code, 0, out[-1600:])
        self.assertTrue(out.startswith("ALL PROOFS CHECK"), out[:400])
        self.assertIn(rec["kernel"].get("verdict"), ("checked", "not_run"))
        w = rec["witness"]
        exp = th()["expected_witness"]
        self.assertEqual(int(w["k"]), exp["k"])
        self.assertTrue(w["left"]["ok"] and w["right"]["ok"])
        self.assertEqual(int(w["left"]["ret"]), exp["left_ret"])
        self.assertEqual(int(w["right"]["ret"]), exp["right_ret"])
        rep = load_json(need(side()["outputs"]["replay"]))
        runs = {x["id"]: x for x in rep["runs"]}
        for s in ("left", "right"):
            run = runs[f"{lid}:{s}"]
            self.assertTrue(run["passed"], f"{lid}:{s}")
            self.assertEqual(int(run["observed_reward"]), int(w[s]["ret"]))
        return rec

    def test_p2_o13_the_slash_naturality_law_is_refuted(self):
        self._refuted(NAT_ID)

    def test_p3_o20_economic_half_the_slash_value_law_is_refuted(self):
        self._refuted(SORT_ID)


# ---------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    def test_r1_earlier_inputs_do_not_move(self):
        for rel, sha in th()["inputs_sha256"].items():
            self.assertEqual(file_sha256(ROOT / rel), sha, rel)
        for cmd in (["bundle", "extract", "--check"], ["versions", "extract", "--check"]):
            p = holon(*cmd)
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
            p = holon("audit", "prereg", "--milestone", m)
            self.assertEqual(p.returncode, 0, m + ": " + p.stdout[-800:])

    def test_r4_own_code_names_no_target(self):
        """The holon files I94's own commits add or change are not among tests_m2.test_target_agnostic_exhaustive's
        failures."""
        own = set()
        for c in own_commits():
            own |= {p for p in git("diff-tree", "--no-commit-id", "--name-only", "-r", c).split()
                    if p.startswith("holon/")}
        p = subprocess.run(["python", "-m", "unittest", "tests_m2.test_target_agnostic_exhaustive"], cwd=ROOT,
                           capture_output=True, text=True)
        failing = set(re.findall(r"file='([^']+)'", p.stdout + p.stderr))
        self.assertEqual(sorted(own & failing), [])


if __name__ == "__main__":
    unittest.main()
