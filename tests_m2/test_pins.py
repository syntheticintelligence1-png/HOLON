"""I3: the gate checks the checker that actually runs (fingerprint), quarantines on an accepted canary,
enforces a per-file budget, and has a checker-upgrade procedure."""
import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, copy_repo, holon_module, load_json, run_holon


def gate(repo: Path, m: str, checks: str, env: dict | None = None):
    rp = repo / f"g_{m}.json"
    old = {k: os.environ.get(k) for k in (env or {})}
    try:
        os.environ.update(env or {})
        p = run_holon(["gate", "--milestone", m, "--root", str(repo), "--report", str(rp), "--checks", checks], cwd=repo)
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return p, (load_json(rp) if rp.exists() else None)


class TestFingerprint(unittest.TestCase):
    def test_fingerprint_matches_config(self):
        bend = holon_module("holon.bend")
        fp = bend.fingerprint()
        cfg = load_json(ROOT / "config" / "holon.json")
        self.assertEqual(fp["fingerprint"], cfg["bend"]["pinned_fingerprint"])
        for k in ("checkout", "head", "sources_sha256", "bun"):
            self.assertTrue(fp[k], k)
        self.assertRegex(fp["fingerprint"], r"^sha256:[0-9a-f]{64}$")

    def test_no_telemetry(self):
        bend = holon_module("holon.bend")
        self.assertEqual(bend._env().get("BEND_NO_TELEMETRY"), "1")

    def test_genv_reports_the_fingerprint(self):
        repo = copy_repo()
        try:
            p, rep = gate(repo, "M0", "G9")
            self.assertTrue(rep["checks"]["GENV"]["passed"], rep["checks"]["GENV"]["detail"])
            self.assertIn("fingerprint", rep["checks"]["GENV"]["detail"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


class TestGenvRefuses(unittest.TestCase):
    def refused(self, edit=None, env=None) -> dict:
        repo = copy_repo()
        try:
            if edit:
                edit(repo)
            p, rep = gate(repo, "M0", "G9", env)
            self.assertIsNotNone(rep, p.stdout[-1000:] + p.stderr[-1000:])
            self.assertFalse(rep["checks"]["GENV"]["passed"])
            self.assertNotEqual(p.returncode, 0)
            return rep
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_wrong_pinned_fingerprint(self):
        def edit(repo):
            f = repo / "config" / "holon.json"
            c = load_json(f)
            c["bend"]["pinned_fingerprint"] = "sha256:" + "0" * 64
            f.write_text(json.dumps(c, indent=2))
        rep = self.refused(edit)
        self.assertIn("fingerprint", rep["checks"]["GENV"]["detail"])

    def test_unresolvable_override(self):
        d = Path(tempfile.mkdtemp(prefix="holon-fakebend-"))
        try:
            fake = d / "bend"
            fake.write_text("#!/bin/sh\necho 'Bend 2.0.36'\necho 'ALL PROOFS CHECK'\n")
            fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
            self.refused(env={"HOLON_BEND_CMD": str(fake)})
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_global_bunfig(self):
        d = Path(tempfile.mkdtemp(prefix="holon-home-"))
        try:
            (d / ".bunfig.toml").write_text('preload = ["./x.ts"]\n')
            rep = self.refused(env={"HOME": str(d)})
            self.assertIn("bunfig", rep["checks"]["GENV"]["detail"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_quarantine(self):
        def edit(repo):
            G = holon_module("holon.gate")
            bend = holon_module("holon.bend")
            G.quarantine(repo, bend.fingerprint()["fingerprint"], ["CANARY_test"])
        rep = self.refused(edit)
        self.assertIn("quarantine", rep["checks"]["GENV"]["detail"])


class TestBudget(unittest.TestCase):
    def test_over_budget_fails_g5_and_timings_are_written(self):
        repo = copy_repo()
        try:
            p, rep = gate(repo, "M0", "G5")
            self.assertTrue(rep["checks"]["G5"]["passed"], rep["checks"]["G5"]["detail"])
            t = load_json(repo / "results" / "M0" / "gate_timing.json")
            self.assertTrue(t["G5"])
            self.assertTrue(all(v < 120 for v in t["G5"].values()))
            f = repo / "config" / "holon.json"
            c = load_json(f)
            c["bend"]["budget_s_per_file"] = 0.001
            f.write_text(json.dumps(c, indent=2))
            p, rep = gate(repo, "M0", "G5")
            self.assertFalse(rep["checks"]["G5"]["passed"])
            self.assertIn("budget", rep["checks"]["G5"]["detail"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_gate_timing_is_not_compared_by_g1(self):
        G = holon_module("holon.gate")
        self.assertIn("gate_timing.json", G.G1_EXCLUDED)


class TestCheckerUpgrade(unittest.TestCase):
    def test_dry_run_to_the_same_fingerprint_shows_no_diff(self):
        bend = holon_module("holon.bend")
        out = Path(tempfile.mkdtemp(prefix="holon-upg-")) / "upgrade.json"
        try:
            p = run_holon(["checker-upgrade", "--to", bend.fingerprint()["fingerprint"], "--milestones", "M0",
                           "--out", str(out)])
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
            rep = load_json(out)
            self.assertEqual(rep["from"], rep["to"])
            self.assertTrue(rep["milestones"]["M0"]["gate_passed"])
            self.assertEqual(rep["milestones"]["M0"]["record_diffs"], [])
        finally:
            shutil.rmtree(out.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
