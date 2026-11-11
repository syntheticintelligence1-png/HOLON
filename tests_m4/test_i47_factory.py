"""I47: target-agnostic factory, parallel checking, performance loop, drift trigger (key I47, spec/M4/predictions.json).

Contract (the build must make every test here pass; it may add tests, never change these):

T0  Targets. A target is a directory targets/<name>/ holding target.json (spec/M4/lib/target.schema.json,
    holon-target/0.1). Everything the factory needs to know about a target that is not a law, a fact document or a
    committed outcome lives there: its identity names, its upstream (url, pinned commit, the watched ref prefix and
    the refs seen at the pin), where its checkout is configured, how its documents are extracted, how it is run and
    where its dependency index is. targets/morph/target.json describes the development target (pinned commit
    3e44e795586af3e11285b603ab642c67823add51, upstream morph-l2/morph). targets/abacus/ is the toy second target:
    exactly the files of tests_m4/fixtures/i47_abacus/ (target.json, laws/*.json), with facts/abacus.facts.json the
    fixture's upstream_v1/abacus.facts.json.
T1  `python -m holon target run --target NAME [--jobs N]` runs a target whose run.kind is "machine" through the
    state-machine pipeline (holon run) under run.milestone, from its laws and documents, and writes run.out (records,
    summary.json, deps.json) and run.gen at those repo-relative paths. Exit 0 when every law ended in a status.
T2  `python -m holon run --milestone M --jobs N` (N > 1, state-machine milestones) decides the laws in N worker
    processes (concurrent.futures.ProcessPoolExecutor) and merges their outputs deterministically. Without --jobs,
    or with --jobs 1, the run is the sequential run as it was at BASE. The merged outputs are the sequential run's
    after G1's normalization (every JSON key named "seconds" removed; every other byte equal).
T3  `python -m holon gate --milestone M [--jobs N]`: N workers for the checks that re-check or regenerate per law.
    Without --jobs the gate is sequential, as at BASE. The checks, their verdicts and the canaries are the same.
T4  `python tools/perf_loop.py --target NAME --candidate DIR [--min-gain X] [--apply]`: the section 9.2(7)
    performance loop. A candidate is a directory of files that replace (or add) repo files at the same relative
    paths. The loop measures the baseline and the candidate in fresh copies, and the candidate survives only if its
    outputs are the baseline's (G1's normalization; so every law, proof and counter-law is unchanged) and, for a
    milestone (--milestone M in place of --target), the gate passes (canaries and replay included). A surviving
    candidate is "kept" when it is at least min-gain (default 0.05) faster, else "no_gain"; otherwise "vetoed",
    naming what failed. The working tree changes only with --apply and only for "kept". It prints one JSON object.
T5  `python -m holon drift --target NAME [--remote URL]`: `git ls-remote` of the upstream (or URL), compared on the
    watched ref prefix with upstream.pinned_refs. No new or moved ref: changed false, nothing extracted. Otherwise the
    newest new ref (by commit date, then name) is fetched into a scratch directory, its documents re-extracted with
    the target's extract method, every re-extracted document whose bytes differ is remodelled (the same generator
    as the run), the kernel index of the new model (holon.bindings.defs_index) compared with the committed one, and
    the stale set is every law whose cone (index.deps, dependents_by_model) holds a definition whose kernel form
    changed or disappeared. It writes drift.out (deterministic: refs compared, the new ref, documents, changed
    definitions, stale laws) and drift.timing (stale_closure_latency_s: seconds from the ls-remote that showed the
    change to the stale set; not compared by anything). It never writes under targets/.
T6  Target-agnostic scan (_i47.scan): nothing under holon/ names a declared target (the names of every
    targets/*/target.json and PINNED_NAMES), in a file's path or its code, except files whose bytes a committed record
    hashes (the record-pinned files of _i47_probe.py), which I47 may not change; those are exactly RESIDUE below
    (computed at BASE) and are byte-identical to BASE.

Claims about the tree (T6, R1) are evaluated at I47's exit commit (_i47.exit_commit: the commit of I47 that adds
docs/iterations/I47.md), and claims about history (P1, R2) over I47's own commits (_i47.i47_commits), so a later
iteration's edit or a merge of the lead does not turn them red.

Regressions: R1 every generator_sha256 digest at the exit equals BASE's (no committed record would move); R2 no
non-merge commit of I47 changes a committed M0-M3 outcome; R3 the target files validate and pin what the contract
says.

P2's baseline is BASE's sequential gate (BASE's own code), measured alternately with the parallel gate, two runs each.
P4 has a third tag: v3 also changes inc_b's effect, which every trace law reaches through the run.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

from tests_m4._m4 import ROOT, copy_repo, load_json, predictions, run_holon, validate
from tests_m4 import _i47 as H

KEY = "I47"
SCHEMA = ROOT / "spec" / "M4" / "lib" / "target.schema.json"
FIX = H.FIXTURE
TOY_LAWS = ["L_abacus_a_reach", "L_abacus_b_reach", "L_abacus_small"]
MORPH_COMMIT = "3e44e795586af3e11285b603ab642c67823add51"
INSTRUMENTS = ["tests_m4/_i47.py", "tests_m4/_i47_probe.py", "spec/M4/lib/target.schema.json"] + sorted(
    f.relative_to(ROOT).as_posix() for f in FIX.rglob("*") if f.is_file())
# T6: the names the scan looks for whatever the target files say (the target files add their own "names")
PINNED_NAMES = {"morph", "morph-l2", "morphl2", "abacus"}
# T6: the files under holon/ that name the development target in code at BASE and whose bytes committed records hash
# (tests_m4/_i47_probe.py at BASE). I47 may not change them; every other holon/ file must name no target.
RESIDUE = sorted([
    "holon/bindings.py", "holon/consumers.py", "holon/corpus.py", "holon/derivation/refine.py", "holon/inhabit.py",
    "holon/lean.py", "holon/model_eval.py", "holon/model_native.py", "holon/mpipeline.py", "holon/mreplay.py",
    "holon/oracles/zero_blob.py", "holon/pipeline.py", "holon/refinement.py", "holon/refute3.py", "holon/refute_m3.py",
    "holon/replay.py", "holon/replay_fragments.py", "holon/sorts/deploy3.py", "holon/sorts/run3.py",
])
# R2: committed outcomes of M0-M3 that I47 must not change
OUTCOMES = ["facts/", "laws/", "results/M0/", "results/M1/", "results/M2/", "results/M3/", "gen/M0/", "gen/M1/",
            "gen/M2/", "gen/M3/", "replay/", "spec/bindings/", "spec/M0/", "spec/M1/", "spec/M2/", "spec/M3/",
            "audit/"]


def env() -> dict:
    e = dict(os.environ)
    e["BEND_NO_TELEMETRY"] = "1"
    return e


def holon(args: list[str], cwd: Path, timeout: int = 7200) -> subprocess.CompletedProcess:
    e = env()
    e["PYTHONPATH"] = str(cwd) + os.pathsep + e.get("PYTHONPATH", "")
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=cwd, env=e, capture_output=True, text=True,
                          timeout=timeout)


def tree_sha(d: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(d.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            h.update(f.relative_to(d).as_posix().encode() + b"\0" + hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()


def toy_status(repo: Path) -> dict:
    t = load_json(repo / "targets" / "abacus" / "target.json")
    return load_json(repo / t["run"]["out"] / "summary.json")


class TestPrereg(unittest.TestCase):
    def test_key_and_fixture(self):
        k = predictions(KEY)
        self.assertEqual(k["tests"], ["tests_m4/test_i47_factory.py"])
        self.assertEqual({p["id"] for p in k["predictions"]}, {f"I47-P{i}" for i in range(1, 6)})
        self.assertEqual(validate(load_json(FIX / "target.json"), SCHEMA), [])
        for v in ("v1", "v2", "v3"):
            self.assertTrue((FIX / f"upstream_{v}" / "abacus.facts.json").is_file())

    def test_instruments_pinned(self):
        pins = predictions(KEY)["thresholds"]["instrument_sha256"]
        self.assertEqual(sorted(pins), sorted(INSTRUMENTS))
        for rel in INSTRUMENTS:
            with self.subTest(file=rel):
                self.assertEqual(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), pins[rel])

    def test_upstream_is_deterministic(self):
        import tempfile
        d = Path(tempfile.mkdtemp(prefix="holon-i47-up-"))
        try:
            shas = H.upstream_repo(d / "u", ["v1", "v2", "v3"])
            self.assertEqual(shas["v1"], load_json(FIX / "target.json")["upstream"]["pinned_commit"])
            self.assertEqual(shas, predictions(KEY)["thresholds"]["upstream_shas"])
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestTargets(unittest.TestCase):
    """R3 and T0."""

    def test_target_files_validate(self):
        for f in sorted((ROOT / "targets").glob("*/target.json")):
            with self.subTest(target=f.parent.name):
                d = load_json(f)
                self.assertEqual(validate(d, SCHEMA), [])
                self.assertEqual(d["name"], f.parent.name)
        self.assertTrue({"morph", "abacus"} <= {f.parent.name for f in (ROOT / "targets").glob("*/target.json")})

    def test_morph_target(self):
        d = load_json(ROOT / "targets" / "morph" / "target.json")
        self.assertEqual(d["upstream"]["pinned_commit"], MORPH_COMMIT)
        self.assertTrue({"morph", "morph-l2"} <= set(d["names"]))
        self.assertIn("morph-l2/morph", d["upstream"]["url"])

    def test_abacus_is_the_fixture(self):
        t = ROOT / "targets" / "abacus"
        want = {"target.json": FIX / "target.json", "facts/abacus.facts.json": FIX / "upstream_v1" / "abacus.facts.json"}
        want |= {f"laws/{p.name}": p for p in sorted((FIX / "laws").glob("*.json"))}
        have = {f.relative_to(t).as_posix() for f in t.rglob("*") if f.is_file()}
        self.assertEqual(have, set(want))
        for rel, src in want.items():
            with self.subTest(file=rel):
                self.assertEqual((t / rel).read_bytes(), src.read_bytes())


def clear_toy_outputs(repo: Path) -> dict:
    """Remove the toy's committed run outputs and drift files from a copy, so a run must re-create them."""
    t = load_json(repo / "targets" / "abacus" / "target.json")
    for k in ("out", "gen"):
        shutil.rmtree(repo / t["run"][k], ignore_errors=True)
    return t


def clear_run_outputs(repo: Path, m: str) -> None:
    """Remove what `holon run --milestone m` writes from a copy (records, summary, deps, splits; the generated model,
    core and law directories); the gate's and other tools' files beside them stay."""
    out, gen = repo / "results" / m, repo / "gen" / m
    for f in list(out.glob("L*.json")) + [out / n for n in ("summary.json", "deps.json", "splits.json")]:
        if f.is_file():
            f.unlink()
    for x in ("model", "core", "laws", "proofs"):
        shutil.rmtree(gen / x, ignore_errors=True)
    for x in gen.glob("L*"):
        shutil.rmtree(x) if x.is_dir() else x.unlink()


def statuses(repo: Path) -> dict:
    t = load_json(repo / "targets" / "abacus" / "target.json")
    return load_json(repo / t["run"]["out"] / "summary.json")


TOY_STATUS = {"L_abacus_a_reach": "PROVED", "L_abacus_b_reach": "PROVED", "L_abacus_small": "REFUTED"}


class TestToyTarget(unittest.TestCase):
    """I47-P1: the toy runs with zero edits to holon/."""

    def _check_outputs(self, repo: Path, t: dict):
        self.assertEqual(statuses(repo), TOY_STATUS)
        out, gen = repo / t["run"]["out"], repo / t["run"]["gen"]
        small = load_json(out / "L_abacus_small.json")
        incs = [a for a in small["witness"]["p"] if a["op"] == "inc_a"]
        self.assertGreaterEqual(len(incs), 3, small["witness"])
        for lid in TOY_LAWS:
            self.assertTrue((out / f"{lid}.json").is_file(), lid)
        model = next((gen / "model").glob("*.bend")).read_text()
        self.assertIsNone(H.name_pattern(["morph", "morph-l2", "Rollup"]).search(model))

    def test_toy_runs_on_the_holon_before_it(self):
        """The commit of I47 that adds targets/abacus/ changes no holon/ file, and the toy runs on the holon/ (and
        config/) of that commit's parent: holon/ was written before the toy existed."""
        adds = [c for c, ps in H.i47_commits() if len(ps) == 1
                and any(f.startswith("targets/abacus/") for f in H.changed_files(c, ps[0]))]
        self.assertTrue(adds, "no commit of I47 adds targets/abacus/")
        c = adds[0]
        parent = H.git(ROOT, "rev-parse", f"{c}^")
        self.assertEqual([f for f in H.changed_files(c, parent) if f.startswith("holon/")], [])
        tree = H.export_tree(parent, ["holon", "config"])
        try:
            self.assertFalse((tree / "targets").exists())
            dst = tree / "targets" / "abacus"
            (dst / "facts").mkdir(parents=True)
            (dst / "target.json").write_bytes((FIX / "target.json").read_bytes())
            (dst / "facts" / "abacus.facts.json").write_bytes((FIX / "upstream_v1" / "abacus.facts.json").read_bytes())
            shutil.copytree(FIX / "laws", dst / "laws")
            p = holon(["target", "run", "--target", "abacus"], tree)
            self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-3000:])
            self._check_outputs(tree, load_json(dst / "target.json"))
        finally:
            shutil.rmtree(tree, ignore_errors=True)

    def test_toy_runs(self):
        repo = copy_repo()
        try:
            t = clear_toy_outputs(repo)
            before = tree_sha(repo / "holon")
            p = holon(["target", "run", "--target", "abacus"], repo)
            self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-3000:])
            self.assertEqual(tree_sha(repo / "holon"), before)
            self._check_outputs(repo, t)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_committed_toy_outputs_regenerate(self):
        repo = copy_repo()
        try:
            t = load_json(repo / "targets" / "abacus" / "target.json")
            want = {k: H.normalized_tree(repo / t["run"][k]) for k in ("out", "gen")}
            clear_toy_outputs(repo)
            p = holon(["target", "run", "--target", "abacus"], repo)
            self.assertEqual(p.returncode, 0, p.stderr[-3000:])
            for k in ("out", "gen"):
                got = H.normalized_tree(repo / t["run"][k])
                keep = {x for x in want[k] if not x.startswith("drift")}
                self.assertGreater(len(keep), 0)
                self.assertEqual({x: got.get(x) for x in sorted(keep | set(got))}, {x: want[k].get(x) for x in
                                                                                     sorted(keep | set(got))})
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


class TestParallelRun(unittest.TestCase):
    """I47-P3: parallel outputs are the sequential run's."""

    def _compare(self, a: Path, b: Path, dirs: list[str]):
        for d in dirs:
            with self.subTest(dir=d):
                ta, tb = H.normalized_tree(a / d), H.normalized_tree(b / d)
                self.assertGreater(len(ta), 0)
                self.assertEqual(sorted(set(ta) ^ set(tb)), [])
                self.assertEqual([x for x in sorted(ta) if ta[x] != tb[x]], [])

    def test_m1_run_parallel_equals_sequential(self):
        a, b = copy_repo(), copy_repo()
        try:
            for r in (a, b):
                clear_run_outputs(r, "M1")
            pa = holon(["run", "--milestone", "M1"], a)
            pb = holon(["run", "--milestone", "M1", "--jobs", "4"], b)
            self.assertEqual(pa.returncode, 0, pa.stderr[-3000:])
            self.assertEqual(pb.returncode, 0, pb.stderr[-3000:])
            self.assertIn("shards merged", pb.stdout)
            self.assertEqual(len(list((b / "results" / "M1").glob("L_*.json"))), 16)
            self._compare(a, b, ["results/M1", "gen/M1"])
        finally:
            shutil.rmtree(a.parent, ignore_errors=True)
            shutil.rmtree(b.parent, ignore_errors=True)

    def test_toy_run_parallel_equals_sequential(self):
        t = load_json(FIX / "target.json")
        a, b, c = copy_repo(), copy_repo(), copy_repo()
        try:
            for r in (a, b, c):
                clear_toy_outputs(r)
            ps = [holon(["target", "run", "--target", "abacus"], a),
                  holon(["target", "run", "--target", "abacus", "--jobs", "2"], b),
                  holon(["target", "run", "--target", "abacus", "--jobs", "3"], c)]
            for p in ps:
                self.assertEqual(p.returncode, 0, p.stderr[-3000:])
            self.assertIn("shards merged", ps[1].stdout + ps[2].stdout)
            self._compare(a, b, [t["run"]["out"], t["run"]["gen"]])
            self._compare(a, c, [t["run"]["out"], t["run"]["gen"]])
        finally:
            for r in (a, b, c):
                shutil.rmtree(r.parent, ignore_errors=True)


class TestGateSpeed(unittest.TestCase):
    """I47-P2: the M1 gate with 4 workers takes at most half the wall time of BASE's sequential gate, with the same
    verdicts. The baseline is BASE's own code (so HEAD's sequential path cannot be slowed to inflate the ratio); the
    runs alternate (parallel, sequential, parallel, sequential) and the medians are compared."""

    def test_m1_gate_speedup(self):
        th = predictions(KEY)["thresholds"]
        self.assertGreaterEqual(os.cpu_count() or 1, th["workers"],
                                f"this machine has {os.cpu_count()} CPUs; I47-P2 is stated for {th['workers']} workers "
                                "on a machine with at least as many")
        base = H.export_tree(H.BASE, ["."])
        head = copy_repo()
        try:
            times = {"seq": [], "par": []}
            reports = {}
            for kind in ("par", "seq", "par", "seq"):
                tree = head if kind == "par" else base
                rep = tree.parent / f"{kind}{len(times[kind])}.json"
                args = ["gate", "--milestone", "M1", "--root", str(tree), "--report", str(rep)]
                if kind == "par":
                    args += ["--jobs", str(th["workers"])]
                t0 = time.monotonic()
                p = holon(args, tree)
                times[kind].append(time.monotonic() - t0)
                self.assertEqual(p.returncode, 0, p.stdout[-3000:])
                reports[kind] = load_json(rep)
            ra, rb = reports["seq"], reports["par"]
            self.assertEqual({g: c["passed"] for g, c in ra["checks"].items()},
                             {g: c["passed"] for g, c in rb["checks"].items()})
            self.assertEqual(ra.get("not_applicable"), rb.get("not_applicable"))
            self.assertEqual(json.dumps(ra["canaries"], sort_keys=True), json.dumps(rb["canaries"], sort_keys=True))
            ts, tp = sorted(times["seq"])[0] + sorted(times["seq"])[1], sorted(times["par"])[0] + sorted(times["par"])[1]
            self.assertGreaterEqual(ts / tp, th["speedup_at_least"], f"sequential {times['seq']} s, "
                                                                       f"{th['workers']} workers {times['par']} s")
        finally:
            shutil.rmtree(base, ignore_errors=True)
            shutil.rmtree(head.parent, ignore_errors=True)


class TestPerfLoop(unittest.TestCase):
    """I47-R4 (construction): the loop vetoes a candidate that changes an outcome and leaves the tree as it was."""

    def _loop(self, cand: Path) -> dict:
        p = subprocess.run([sys.executable, str(ROOT / "tools" / "perf_loop.py"), "--target", "abacus",
                            "--candidate", str(cand)], cwd=ROOT, env=env(), capture_output=True, text=True,
                           timeout=3600)
        self.assertEqual(p.returncode, 0, p.stderr[-3000:])
        return json.loads(p.stdout)

    def test_veto_and_neutral(self):
        import tempfile
        d = Path(tempfile.mkdtemp(prefix="holon-i47-cand-"))
        try:
            before = H.git(ROOT, "status", "--porcelain", "--untracked-files=all")
            before_holon = tree_sha(ROOT / "holon")
            bad = d / "bad" / "holon" / "js"
            bad.mkdir(parents=True)
            (bad / "explore.mjs").write_text("process.exit(3);\n")   # the refuter finds nothing: a REFUTED law moves
            r = self._loop(d / "bad")
            self.assertEqual(r["verdict"], "vetoed", r)
            self.assertTrue(r["failed"], r)
            neutral = d / "neutral" / "holon" / "js"
            neutral.mkdir(parents=True)
            (neutral / "explore.mjs").write_text((ROOT / "holon" / "js" / "explore.mjs").read_text()
                                                 + "\n// a neutral candidate (I47 test)\n")
            r = self._loop(d / "neutral")
            self.assertIn(r["verdict"], ("kept", "no_gain"), r)
            self.assertFalse(r["failed"], r)
            self.assertEqual(tree_sha(ROOT / "holon"), before_holon, "the loop changed holon/ without --apply")
            self.assertEqual(H.git(ROOT, "status", "--porcelain", "--untracked-files=all"), before,
                             "the loop changed the working tree without --apply")
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestDrift(unittest.TestCase):
    """I47-P4: a simulated new tag triggers re-extraction and marks exactly the predicted stale set."""

    def _drift(self, repo: Path, up: Path) -> dict:
        p = holon(["drift", "--target", "abacus", "--remote", str(up)], repo)
        self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-3000:])
        t = load_json(repo / "targets" / "abacus" / "target.json")
        return load_json(repo / t["drift"]["out"])

    def test_new_tag_marks_the_stale_set(self):
        import tempfile
        p4 = next(p for p in predictions(KEY)["predictions"] if p["id"] == "I47-P4")["expected"]
        repo = copy_repo()
        up = Path(tempfile.mkdtemp(prefix="holon-i47-upstream-"))
        try:
            targets_before = tree_sha(repo / "targets")
            t = load_json(repo / "targets" / "abacus" / "target.json")
            for k in ("out", "timing"):
                (repo / t["drift"][k]).unlink(missing_ok=True)
            # only the pinned tag: no change, nothing extracted
            H.upstream_repo(up / "u1", ["v1"])
            r0 = self._drift(repo, up / "u1")
            self.assertFalse(r0["changed"], r0)
            self.assertIsNone(r0["new_ref"])
            self.assertEqual(r0["documents"], {})
            self.assertEqual(r0["stale"], [])
            # tag v2: only observer a_small changes
            shas = H.upstream_repo(up / "u2", ["v1", "v2"])
            r1 = self._drift(repo, up / "u2")
            self.assertTrue(r1["changed"])
            self.assertEqual(r1["new_ref"], {"ref": "refs/tags/v2", "commit": shas["v2"]})
            self.assertTrue(r1["documents"]["abacus.facts.json"]["changed"], r1["documents"])
            self.assertEqual(r1["stale"], p4["stale"])
            self.assertIn(p4["changed_definition"], r1["changed_definitions"])
            tm = load_json(repo / t["drift"]["timing"])
            self.assertGreater(tm["stale_closure_latency_s"], 0)
            r1b = (repo / t["drift"]["out"]).read_bytes()
            self._drift(repo, up / "u2")
            self.assertEqual((repo / t["drift"]["out"]).read_bytes(), r1b, "drift.json is not deterministic")
            # tag v3 (newest): inc_b's effect changes too, which every trace law reaches through the run
            shas = H.upstream_repo(up / "u3", ["v1", "v2", "v3"])
            r2 = self._drift(repo, up / "u3")
            self.assertEqual(r2["new_ref"], {"ref": "refs/tags/v3", "commit": shas["v3"]})
            self.assertEqual(r2["refs_new_or_moved"], ["refs/tags/v2", "refs/tags/v3"])
            self.assertEqual(r2["stale"], p4["v3_stale"])
            self.assertIn(p4["changed_definition"], r2["changed_definitions"])
            self.assertTrue([d for d in r2["changed_definitions"] if "inc_b" in d], r2["changed_definitions"])
            self.assertEqual(tree_sha(repo / "targets"), targets_before, "drift wrote under targets/")
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)
            shutil.rmtree(up, ignore_errors=True)

    def test_morph_drift_recorded(self):
        """Construction: the committed morph drift report compares the live upstream's refs with the pin."""
        t = load_json(ROOT / "targets" / "morph" / "target.json")
        r = load_json(ROOT / t["drift"]["out"])
        self.assertEqual(r["target"], "morph")
        self.assertEqual(r["pinned_commit"], MORPH_COMMIT)
        self.assertIn("changed", r)
        self.assertGreater(len(r["refs_seen"]), 0)


class TestTargetAgnostic(unittest.TestCase):
    """I47-P5: nothing in holon/ names a target but the record-pinned residue, unchanged. Evaluated at I47's exit
    commit (_i47.exit_commit)."""

    def test_scan(self):
        tree = H.export_tree(H.exit_commit(), ["holon", "targets"])
        try:
            names = H.target_names(tree)
            self.assertTrue({"morph", "abacus"} <= set(names))
            flat = sorted({n for ns in names.values() for n in ns} | PINNED_NAMES)
            hits = H.scan(tree, flat)
            self.assertEqual(sorted(hits), RESIDUE, {f: v for f, v in hits.items() if f not in RESIDUE})
        finally:
            shutil.rmtree(tree, ignore_errors=True)

    def test_residue_is_unchanged_and_pinned(self):
        ex = H.exit_commit()
        tree = H.export_tree(ex, ["holon", "spec"])
        try:
            pinned = set(H.closures(tree)["files"])
            for rel in RESIDUE:
                with self.subTest(file=rel):
                    self.assertIn(rel, pinned)
                    base = subprocess.run(["git", "show", f"{H.BASE}:{rel}"], cwd=ROOT, capture_output=True).stdout
                    self.assertEqual((tree / rel).read_bytes(), base)
        finally:
            shutil.rmtree(tree, ignore_errors=True)

    def test_scan_catches_planted_names(self):
        import tempfile
        d = Path(tempfile.mkdtemp(prefix="holon-i47-scan-"))
        try:
            (d / "holon").mkdir()
            (d / "holon" / "a.py").write_text('"""Morph in a docstring is documentation."""\n# morph in a comment\n'
                                              'X = {"morph_commit": 1}\n')
            (d / "holon" / "b.mjs").write_text('// abacus\nconst y = "isomorphic";\n')
            (d / "holon" / "c.go").write_text('import "github.com/morph-l2/go-ethereum/x"\n')
            (d / "holon" / "abacus_x.py").write_text("Y = 1\n")
            self.assertEqual(H.scan(d, ["morph", "morph-l2", "abacus"]),
                             {"holon/a.py": ["morph"], "holon/abacus_x.py": ["abacus"], "holon/c.go": ["morph-l2"]})
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestRegressions(unittest.TestCase):
    def test_r1_generator_digests_unchanged(self):
        """At I47's exit commit, every generator digest and the files they read are BASE's."""
        base = H.export_tree(H.BASE, ["holon", "spec"])
        ex = H.export_tree(H.exit_commit(), ["holon", "spec"])
        try:
            a, b = H.closures(base), H.closures(ex)
            self.assertEqual(a["digests"], b["digests"])
            self.assertEqual(a["files"], b["files"])
        finally:
            shutil.rmtree(base, ignore_errors=True)
            shutil.rmtree(ex, ignore_errors=True)

    def test_r2_outcomes_unchanged(self):
        """No non-merge commit of I47 (HEAD's first-parent chain from C_K to the exit) changes a committed M0-M3
        outcome; a merge of the lead brings the lead's own."""
        for c, ps in H.i47_commits():
            if len(ps) != 1:
                continue
            with self.subTest(commit=c):
                self.assertEqual([f for f in H.changed_files(c, ps[0]) if any(f.startswith(o) for o in OUTCOMES)], [])


if __name__ == "__main__":
    unittest.main()
