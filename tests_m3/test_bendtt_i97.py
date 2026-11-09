"""I97: the F-M3-13 fix, BendTT (G7) on M3 in CI and the six BendTT rejections classified (BUILD_PLAN row I97; the key
I97 of spec/M3/predictions.json). The instrument is tests_m3/_i97.py. It imports nothing from holon/ or tools/. The
instrument and this docstring are fixed at the prereg (C_K) and pinned by sha256 in the key's thresholds.

Contract. <B> is the key's base_commit, SIX the six records of round 3's F-M3-13 (_i97.SIX), and OUT is
docs/iterations/I97/.

R  The ruling (the lead, F-M3-13 high under Q8). A BendTT rejection of a proof that bend2 accepts is a cross-kernel
   disagreement unless a minimized repro shows BendTT rejecting a construct it does not implement (or cannot normalize
   within its kernel), not an invalid proof.
S  The build.
   S1  The registry spec/M3/lib/bendtt_constructs.json declares each unsupported construct: its name, the mechanical
       detection rule (holon.bend.construct_of) and its minimized repro, a PROOF.bend/LAWS.bend pair (with any model
       file) under tests_m3/fixtures/bendtt_i97/<construct>/, which bend2 accepts and BendTT rejects. It names no law.
   S2  holon.bend.classify_rejection(proof, cfg) is None when BendTT accepts the proof; otherwise {"class":
       "unsupported", "construct", "repro"} when a registered construct is detected in the proof, else {"class":
       "disagreement"}.
   S3  The record-making code (the shared bend2-then-BendTT check of holon/bundle/lawrun.py, which the Go and the
       member laws use, and every other place that records a BendTT verdict) records an unsupported rejection as the
       bendtt entry {"result": "unsupported", "reason": "<construct>: <repro>"}, independence_class I1, the status
       unchanged; a disagreement leaves the law undecided (UNKNOWN, the disagreement in its attempt), never decided on
       one kernel against the other. No law is dropped.
   S4  G7 (holon/gate.py) re-checks every decided proof with BendTT, as before. A rejection passes only when the
       record's bendtt entry is "unsupported" with a registered construct, holon.bend.construct_of detects that
       construct in the proof, and the construct's repro still has bend2 accept and BendTT reject. A record whose
       bendtt entry claims "checked" and whose re-check fails, fails G7.
   S5  CI (.github/workflows/holon-ci.yml) runs G7 for M3, and G4 and G6 where the budget allows; a check left out is
       named with its reason in the workflow and in the report.
K  The pins hold, `holon audit prereg --milestone M3` prints PREREG OK, and the instrument imports nothing from holon/
   or tools/.
B  The build's checks.
   B1  Each registered repro has bend2 accept and BendTT reject (_i97.bend_pair).
   B2  The registry names no law id of the lead's tree, and holon/bend.py's classifier names no target.
   B3  holon.bend.classify_rejection classifies each of SIX's committed proofs as OUT/classification.json records.
   B4  The forged tree is refused: on a copy of HEAD with _i97.forge applied, `holon gate --milestone M3 --checks G7`
       fails, and its detail names every forged law.
   B5  The workflow holds an M3 job whose command runs `holon gate --milestone M3` with G7 among its checks.
P  The outcomes (OUT is written after C_K).
   P1  All six are unsupported constructs, none a real disagreement, in at most two constructs: one for the two Go
       laws and one for the four member laws (OUT/classification.json).
   P2  The six keep REFUTED, as single-kernel I1 records with their reason; no other M3 record changes status.
   P3  G7 passes on M3 at HEAD after the re-make (OUT/g7.json, from `holon gate --milestone M3 --checks G7`).
   P4  CI's M3 check set gains G7, G4 and G6, and each passes on the lead; G1 is left out, with its reason (its
       regeneration of M3's outputs exceeds a job's budget) (OUT/ci.json).
   P5  The forged tree is refused by CI's M3 check set: G7 fails and names all six (OUT/forge.json).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m3 import _i97 as I

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / I.OUT
KEYFILE = ROOT / "spec" / "M3" / "predictions" / "I97.json"
SKIP = {".git", "cache", "build", "node_modules"}


def _th() -> dict:
    return json.loads(KEYFILE.read_text(encoding="utf-8"))["thresholds"]


def _sha(p) -> str:
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def _holon(*args, timeout=3600) -> subprocess.CompletedProcess:
    env = {**os.environ, "BEND_NO_TELEMETRY": "1"}
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, env=env, capture_output=True, text=True,
                          timeout=timeout)


def _load(rel: str):
    return json.loads((OUT / rel).read_text(encoding="utf-8"))


def _registry() -> dict:
    return json.loads((ROOT / I.REGISTRY).read_text(encoding="utf-8"))


class TestPrereg(unittest.TestCase):
    def test_r0_the_prereg_pins_hold(self):
        th = _th()
        self.assertEqual(hashlib.sha256(__doc__.encode("utf-8")).hexdigest(), th["contract_docstring_sha256"])
        for name, pin in th["pins"].items():
            self.assertEqual(_sha(pin["path"]), pin["sha256"], name)

    def test_r1_the_prereg_audit_passes(self):
        r = _holon("audit", "prereg", "--milestone", "M3", timeout=900)
        self.assertIn("PREREG OK", r.stdout + r.stderr)

    def test_r2_the_instrument_imports_nothing_from_holon_or_tools(self):
        src = (ROOT / "tests_m3" / "_i97.py").read_text(encoding="utf-8")
        self.assertFalse(re.search(r"(?m)^\s*(from|import)\s+(holon|tools)\b", src))


class TestBuild(unittest.TestCase):
    def test_r3_b1_the_repros_reproduce(self):
        reg = _registry()
        self.assertTrue(reg["constructs"])
        for c in reg["constructs"]:
            self.assertEqual(I.bend_pair(ROOT / c["repro"]), (True, False), c["name"])

    def test_r4_b2_the_registry_and_classifier_name_no_target(self):
        ids = {p.stem for p in (ROOT / "laws" / "M3").glob("L*.json")}
        text = (ROOT / I.REGISTRY).read_text(encoding="utf-8")
        self.assertEqual([w for w in re.findall(r"\bL_[A-Za-z0-9_]+", text) if w in ids], [])
        src = (ROOT / "holon" / "bend.py").read_text(encoding="utf-8")
        self.assertFalse(re.search(r"(?i)rollup|morph|messenger|batchdata|L1MessageQueue", src))

    def test_r5_b3_the_six_are_classified(self):
        from holon import bend
        got = {}
        for lid in I.SIX:
            rec = json.loads((ROOT / "results" / "M3" / f"{lid}.json").read_text(encoding="utf-8"))
            c = bend.classify_rejection(ROOT / rec["artifacts"]["proof"], bend.config(ROOT))
            got[lid] = c
        self.assertEqual(got, _load("classification.json")["laws"])

    def test_r6_b4_the_forged_tree_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = Path(tmp) / "w"
            shutil.copytree(ROOT, w, ignore=lambda d, names: [n for n in names if Path(d) == ROOT and n in SKIP])
            forged = I.forge(w)
            code, checks = I.gate(w, "G7")
        self.assertTrue(set(I.SIX) <= set(forged), forged)
        self.assertNotEqual(code, 0)
        passed, detail = checks["G7"]
        self.assertFalse(passed)
        for lid in forged:
            self.assertIn(lid, detail)

    def test_r7_b5_ci_runs_g7_on_m3(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        runs = re.findall(r"holon gate --milestone M3 --checks ([A-Z0-9,]+)", wf)
        self.assertTrue(any("G7" in r.split(",") for r in runs), runs)


class TestOutcome(unittest.TestCase):
    def test_p1_the_six_are_unsupported_constructs(self):
        laws = _load("classification.json")["laws"]
        self.assertEqual(sorted(laws), sorted(I.SIX))
        self.assertEqual({v["class"] for v in laws.values()}, {"unsupported"})
        gox = {laws[l]["construct"] for l in I.SIX if l.startswith("L_par_gobr_")}
        sym = {laws[l]["construct"] for l in I.SIX if l.startswith("L_sym_")}
        self.assertEqual((len(gox), len(sym)), (1, 1))
        self.assertLessEqual(len(gox | sym), 2)

    def test_p2_the_six_keep_refuted_as_single_kernel(self):
        rec = _load("records.json")
        for lid in I.SIX:
            # amended (spec/M3/amendments/I97.jsonl, TestAmendG9's G1): the schema-valid encoding of an unsupported
            # construct is the bendtt entry not_run, its note naming the construct
            self.assertEqual((rec[lid]["status"], rec[lid]["bendtt"], rec[lid]["independence_class"]),
                             ("REFUTED", "not_run", "I1"), lid)
            self.assertTrue(str(rec[lid].get("note") or "").startswith("kernel_fuel: "), lid)
        self.assertEqual(rec["other_status_changes"], [])

    def test_p3_g7_passes_on_m3(self):
        g7 = _load("g7.json")
        self.assertTrue(g7["passed"], g7.get("detail"))

    def test_p4_the_ci_check_set(self):
        ci = _load("ci.json")
        self.assertEqual(sorted(ci["added"]), ["G4", "G6", "G7"])
        self.assertTrue(all(ci["passed_on_lead"][c] for c in ci["added"]), ci["passed_on_lead"])
        self.assertIn("G1", ci["left_out"])

    def test_p5_the_forge_is_refused(self):
        f = _load("forge.json")
        self.assertFalse(f["g7_passed"])
        self.assertTrue(set(I.SIX) <= set(f["named"]), f["named"])


class TestAmendF14(unittest.TestCase):
    """Added after C_K (950ccd38) by the disclosed prereg amendment for audit M3/4 F-M3-14, under the lead's ruling of
    2026-11-09 04:35 (spec/M3/amendments/I97.jsonl; its line for this class pins this docstring's sha256). Nothing
    above changes: R0-R7 and P1-P5 stand as preregistered. These are build checks, not counted predictions.

    F-M3-14 (round 4, PR #121 head abc1cbb9; high, gate_evasion). A committed .env.local that sets BENDTT to a fake
    kernel makes holon.bend.check_verdict print ALL PROOFS CHECK on a counter-law the pinned BendTT rejects. GENV's
    unsafe_env_files refused only bunfig.toml and .env, but bun also loads .env.local and .env.<NODE_ENV> from the
    checker's working directory.

    A1  GENV refuses bunfig.toml and every name that starts with ".env", at any depth of the tree outside .git:
        holon.bend.unsafe_env_files(root) lists each such path (relative to root, sorted), and holon.gate.Gate.genv
        fails on a root where it lists one, naming it.
    A2  holon.bend runs bun (bend2) with an allowlisted environment, holon.bend.checker_env(cfg): from the caller's
        environment only the names in holon.bend.ENV_ALLOW, plus what holon.bend sets itself (BEND_NO_TELEMETRY, the
        JavaScriptCore stack and, once it is built, BENDTT as the pinned toolchain's --verdict kernel:
        holon.bend.verdict_kernel_path of the resolved checkout). check and check_verdict run in a fresh empty working
        directory, the file by its absolute path; every other run refuses a working directory that holds a name A1
        refuses. An inherited BENDTT never reaches the checker: one that differs from the pinned path raises
        holon.bend.EnvRefused, whose message names BENDTT; it is never silently used.
    A3  The tests plant .env.local, .env.production and a nested bunfig.toml. Each is refused (A1), and so is a run in a
        working directory that holds one (A2). The round-4 repro (abc1cbb9:audit/rounds/M3/round4/a7/repro.sh, its
        steps on a scratch copy) no longer flips the verdict: with .env.local beside the proof setting BENDTT to a fake
        kernel, check_verdict still gives the pinned kernel's rejection, and the fake never runs.
    """
    TEST_ID = "tests_m3/test_bendtt_i97.py::TestAmendF14"
    PLANTS = (".env.local", "a/b/.env.production", "c/d/bunfig.toml")
    REPRO_LAW = "L_sym_tau_L1MessageQueueWithGasPriceOracle_getMessageEnqueueTimestamp"
    REPRO_FILES = ("gen/M3/proofs/{law}/PROOF.bend", "gen/M3/laws/{law}/LAWS.bend", "gen/M3/symb/sections/queue.bend",
                   "gen/M3/bundle/models/queue.bend")

    @staticmethod
    def _root(tmp) -> Path:
        """A scratch root that holds only the checker config (holon.gate.Gate reads config/holon.json)."""
        r = Path(tmp) / "root"
        (r / "config").mkdir(parents=True)
        for f in ("holon.json", "holon.example.json"):
            if (ROOT / "config" / f).is_file():
                shutil.copy2(ROOT / "config" / f, r / "config" / f)
        return r

    @staticmethod
    def _plant(r, rel: str) -> Path:
        p = Path(r) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("BENDTT=/nonexistent/fake-bendtt\n", encoding="utf-8")
        return p

    def test_a0_the_amendment_is_disclosed_and_pins_this_contract(self):
        src = (ROOT / "spec" / "M3" / "amendments" / "I97.jsonl").read_text(encoding="utf-8")
        mine = [a for a in (json.loads(ln) for ln in src.splitlines() if ln.strip()) if a.get("test") == self.TEST_ID]
        self.assertEqual(len(mine), 1, mine)
        self.assertEqual(mine[0]["iteration"], "I97")
        self.assertEqual(mine[0]["contract_sha256"], hashlib.sha256(type(self).__doc__.encode("utf-8")).hexdigest())
        agg = (ROOT / "spec" / "M3" / "amendments.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(sum(1 for ln in agg if ln.strip() and json.loads(ln) == mine[0]), 1)

    def test_a1_env_files_are_refused_anywhere_in_the_tree(self):
        from holon import bend
        with tempfile.TemporaryDirectory() as tmp:
            r = self._root(tmp)
            for f in ("x.env", "env", "docs/dotenv.md", "bunfig.toml.bak", ".git/.env.local"):
                self._plant(r, f)
            self.assertEqual(bend.unsafe_env_files(r), [])
            for p in self.PLANTS:
                self._plant(r, p)
                self.assertIn(p, bend.unsafe_env_files(r))
            self.assertEqual(bend.unsafe_env_files(r), sorted(self.PLANTS))

    def test_a1_genv_fails_on_each_plant(self):
        from holon.gate import Gate
        for p in self.PLANTS:
            with tempfile.TemporaryDirectory() as tmp:
                r = self._root(tmp)
                self._plant(r, p)
                g = Gate("M3", r)
                self.assertFalse(g.genv(), p)
                self.assertIn(p, g.checks["GENV"]["detail"])

    def test_a2_the_checker_environment_is_allowlisted(self):
        from unittest import mock
        from holon import bend
        cfg = bend.config(ROOT)
        planted = {"HOLON_I97_PROBE": "1", "NODE_OPTIONS": "--require /nonexistent.js", "BUN_OPTIONS": "--preload x",
                   "NODE_ENV": "production", "BEND_LIB": "/nonexistent", "BEND_HUB": "http://127.0.0.1:9"}
        with mock.patch.dict(os.environ, planted):
            os.environ.pop("BENDTT", None)
            env = bend.checker_env(cfg)
        own = {"BEND_NO_TELEMETRY", "BUN_JSC_maxPerThreadStackUsage", "BENDTT"}
        self.assertEqual(sorted(set(env) - set(bend.ENV_ALLOW) - own), [])
        self.assertEqual(sorted(set(planted) & set(env)), [])
        if "BENDTT" in env:
            self.assertEqual(env["BENDTT"], str(bend.verdict_kernel_path(bend.resolve_checker(cfg)[1])))

    def test_a2_a_foreign_bendtt_is_refused_by_name(self):
        from unittest import mock
        from holon import bend
        cfg = bend.config(ROOT)
        rp = ROOT / _registry()["constructs"][0]["repro"] / "PROOF.bend"
        with mock.patch.dict(os.environ, {"BENDTT": "/nonexistent/fake-bendtt"}):
            for f in (bend.check_verdict, bend.check):
                with self.assertRaises(bend.EnvRefused) as cm:
                    f(rp, cfg)
                self.assertIn("BENDTT", str(cm.exception))

    def test_a3_a_run_in_a_directory_that_holds_one_is_refused(self):
        from holon import bend
        cfg = bend.config(ROOT)
        for p in self.PLANTS:
            with tempfile.TemporaryDirectory() as tmp:
                f = self._plant(tmp, p)
                with self.assertRaises(bend.EnvRefused) as cm:
                    bend.run(["version"], cwd=f.parent, cfg=cfg)
                self.assertIn(f.name, str(cm.exception))

    def test_a3_the_round4_repro_no_longer_flips_the_verdict(self):
        from holon import bend
        cfg = bend.config(ROOT)
        law = self.REPRO_LAW
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "w"
            for f in self.REPRO_FILES:
                dst = work / f.format(law=law)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / f.format(law=law), dst)
            marker, fake = Path(tmp) / "fake-ran", Path(tmp) / "fake-bendtt"
            fake.write_text(f"#!/bin/sh\ntouch '{marker}'\necho ALL PROOFS CHECK\nexit 0\n", encoding="utf-8")
            fake.chmod(0o755)
            proof = work / "gen" / "M3" / "proofs" / law / "PROOF.bend"
            before = bend.check_verdict(proof, cfg)
            self.assertFalse(before.ok, before.out[-300:])
            (proof.parent / ".env.local").write_text(f"BENDTT={fake}\n", encoding="utf-8")
            self.assertEqual(bend.unsafe_env_files(work), [f"gen/M3/proofs/{law}/.env.local"])
            after = bend.check_verdict(proof, cfg)
            self.assertFalse(after.ok, after.out[-300:])
            self.assertEqual(after.first_line, before.first_line)
            self.assertFalse(marker.exists())



class TestAmendG9(unittest.TestCase):
    """Added after C_K (950ccd38) by the disclosed prereg amendment for the schema conformance of I97's records: the lead's
    landing of I97 (#123) failed G9 on the six re-made records (spec/M3/amendments/I97.jsonl; its line for this class
    pins this docstring's sha256). Nothing else above changes, except P2's test, which the same amendment licenses.

    G1  The encoding. A rejection by a registered construct is recorded within the record schemas' enums. The v1
        kernel.verdict is not_run (schemas/result_record.schema.json admits not_run, checked and failed). The v2 bendtt
        entry is {"result": "not_run", "reason": "heartbeats", "note": "<construct>: <repro> (def <d>)"}: heartbeats is
        the v2 enum's evaluation-budget reason (Lean's heartbeat limit), the analogue of BendTT's fuel. The construct
        also stays in the record's checker.bendtt.construct. This supersedes S3's {"result": "unsupported", "reason":
        "<construct>: <repro>"}, which neither schema admits. Neither the frozen v1 schema nor v2's enum is extended. G7
        accepts a BendTT rejection only from a bendtt entry not_run whose note names a registered construct that G7
        re-detects in the proof and whose repro still reproduces; a not_run entry with any other note is refused.
    G2  G9 accepts a re-made kernel_fuel record: one of SIX, re-made by `holon run` into a scratch directory, validates
        under both record schemas as holon.sorts.gate3.Gate3.g9 validates every record, and its bendtt entry is G1's.
    """
    TEST_ID = "tests_m3/test_bendtt_i97.py::TestAmendG9"
    LAW = "L_par_gobr_BatchData_EstimateCompressedSizeWithNewPayload_p0_p3"

    def test_a0_the_amendment_is_disclosed_and_pins_this_contract(self):
        src = (ROOT / "spec" / "M3" / "amendments" / "I97.jsonl").read_text(encoding="utf-8")
        mine = [a for a in (json.loads(ln) for ln in src.splitlines() if ln.strip()) if a.get("test") == self.TEST_ID]
        self.assertEqual(len(mine), 1, mine)
        self.assertEqual(mine[0]["contract_sha256"], hashlib.sha256(type(self).__doc__.encode("utf-8")).hexdigest())
        agg = (ROOT / "spec" / "M3" / "amendments.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(sum(1 for ln in agg if ln.strip() and json.loads(ln) == mine[0]), 1)

    def test_g2_g9_accepts_a_remade_kernel_fuel_record(self):
        sys.path.insert(0, str(ROOT))
        from holon import schema as S
        with tempfile.TemporaryDirectory() as tmp:
            r = _holon("run", "--milestone", "M3", "--laws", self.LAW, "--out", str(Path(tmp) / "results"),
                       "--gen-dir", str(Path(tmp) / "gen"), timeout=3600)
            self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-1500:])
            rec = json.loads((Path(tmp) / "results" / f"{self.LAW}.json").read_text(encoding="utf-8"))
        v1 = json.loads((ROOT / "schemas" / "result_record.schema.json").read_text(encoding="utf-8"))
        v2 = json.loads((ROOT / "spec" / "schemas" / "result_record_v2.schema.json").read_text(encoding="utf-8"))
        self.assertEqual((S.errors(rec, v1), S.errors(rec, v2)), ([], []))
        self.assertEqual(rec["status"], "REFUTED")
        bt = next(k for k in rec["kernels"] if k["name"] == "bendtt")
        self.assertEqual((bt["result"], bt.get("reason")), ("not_run", "heartbeats"))
        self.assertTrue(bt["note"].startswith("kernel_fuel: "), bt["note"])
        self.assertEqual(rec["checker"]["bendtt"]["construct"]["name"], "kernel_fuel")


if __name__ == "__main__":
    unittest.main()
