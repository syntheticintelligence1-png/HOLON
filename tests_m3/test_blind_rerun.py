"""I46: the blind rerun from code, the generated comparison, and the M3 exit (BUILD_PLAN I46 and row I46; the key
I46 of spec/M3/predictions.json). The protocol is spec/M3/lib/blind_rerun.json, the blind session's brief is
spec/M3/lib/blind_session.md, the scope tool is tests_m3/blind_scope.py and the instrument is tests_m3/_i46.py, which
imports nothing from holon/ or tools/ and reuses I82's instrument (tests_m3/_i82.py). All four, and this docstring, are
fixed at the prereg (C_K) and pinned by sha256 in the key's thresholds.

Contract. <P> is the pack commit, OUT is audit/blind/I46/.

K  The pack commit. <P> is the lead at the commit that lands I70: the oldest commit of the lead's first-parent chain
   whose tree holds docs/iterations/I70.md (_i46.pack_commit; without the lead's ref, _i46.pack_commit_problems: <P>
   holds it and its first parent does not). OUT/run.json names <P>. OUT/pack/manifest.json is tools/blind_pack.py's
   manifest of <P> (its holon.commit is <P>) and OUT/pack/leaks.json its leak list, never filtered.
S  The scope set. OUT/scope/ is tests_m3/blind_scope.py's output for <P>: stripped.json, scope.json and files/ equal the
   instrument's recomputation of the protocol's rules at <P> (_i46.scope_problems), and no file given still holds a
   member the rules strip. At the base, the instrument's listing equals the sidecar's at_base.
B  The brief holds no outcome: no status word, no law id of the tree, no match of any leak class of the pack protocol
   (_i46.brief_problems), at the base and at <P>.
L  The reads check. OUT/session/run.json is {"W", "pack", "scope", "pack_commit", "family", "transcript_sha256",
   "tool_calls"}; family is "same" (Q9). OUT/session/tool_calls.jsonl is the projection of the session's transcript
   (_i46.tool_calls: every tool call in order, {i, tool, input}), as many lines as run.json's tool_calls.
   _i46.calls_problems finds nothing. OUT/session/log.jsonl is the session's own log, and every file it logs as
   authored is kept under OUT/authored/<path>.
C  The comparison. OUT/lead is the projection of the lead at <P> for M0-M3: each law file byte for byte, each record
   {law_id, status}. OUT/tree is the projection of the blind tree for the milestones it holds. OUT/compare.json is
   `holon compare --blind OUT/tree --lead OUT/lead --milestone <those milestones>` and equals I82's instrument's
   recomputation. Per milestone, per rule and per family the numbers are the instrument's (_i46.breakdown), with a
   milestone the blind tree does not hold counted as 0 matched classes.
E  The exit (_i46.exit_clauses): E1 `holon report --milestone M3 --check` exits 0 on the final head; E2 M3's
   blind_agreement >= 0.90 over at least 40 matched M3 classes; E3 results/M3/audit_status.json at <P> has converged
   true; E4 results/M3/backtest.json at <P> has no exit_blockers; E5 the reads check passes. The M3 exit is met iff
   E1-E5 hold; I46's own clause is E1, E2 and E5. Its claim is scoped to the matched set, labelled same-family.
R  Own commits are the non-merge commits of `git log --first-parent <C_K>..<end>`, <end> the first commit adding
   docs/iterations/I46.md (HEAD while there is none). They change only OUT and docs/iterations/I46.md.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from tests_m3 import _i46 as I
from tests_m3 import _i82 as I82

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / I.OUT
KEYFILE = ROOT / "spec" / "M3" / "predictions" / "I46.json"


def _key() -> dict:
    return json.loads(KEYFILE.read_text(encoding="utf-8"))


def _sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _holon(*args, timeout=1800):
    e = dict(os.environ)
    e.update({"BEND_NO_TELEMETRY": "1", "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")})
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, env=e, capture_output=True, text=True,
                          timeout=timeout)


def _git(*args) -> str:
    return I82.git(ROOT, *args)


def _load(rel):
    return json.loads((OUT / rel).read_text(encoding="utf-8"))


def _pack_commit() -> str:
    run = _load("session/run.json")
    return run["pack_commit"]


def _milestones(tree: Path) -> list[str]:
    return [m for m in ("M0", "M1", "M2", "M3") if (tree / "laws" / m).is_dir() and (tree / "results" / m).is_dir()]


def _compare():
    blind, lead = OUT / "tree", OUT / "lead"
    return I82.compare(lead, blind, ["M0", "M1", "M2", "M3"]), _milestones(blind)


class TestPrereg(unittest.TestCase):
    def test_r0_the_prereg_pins_hold(self):
        t = _key()["thresholds"]
        doc = sys.modules[__name__].__doc__.encode("utf-8")
        self.assertEqual(hashlib.sha256(doc).hexdigest(), t["contract_docstring_sha256"])
        for name in ("instrument", "i82_instrument", "sidecar", "brief", "scope_tool"):
            self.assertEqual(_sha(ROOT / t[name]["path"]), t[name]["sha256"], name)

    def test_r1_the_brief_holds_no_outcome(self):
        commits = [_key()["thresholds"]["base_commit"]]
        if (OUT / "session" / "run.json").is_file():
            commits.append(_pack_commit())
        for c in commits:
            self.assertEqual(I.brief_problems(ROOT, c), [], c[:8])

    def test_r2_the_prereg_audit_passes(self):
        p = _holon("audit", "prereg", "--milestone", "M3")
        self.assertEqual(p.returncode, 0, (p.stdout + p.stderr)[-2000:])
        self.assertIn("PREREG OK", p.stdout)

    def test_r3_own_commits_touch_only_what_the_contract_allows(self):
        ck = _git("log", "--diff-filter=A", "--format=%H", "--", str(KEYFILE.relative_to(ROOT))).split()[-1]
        added = _git("log", "--first-parent", "--diff-filter=A", "--format=%H", f"{ck}..HEAD", "--",
                     "docs/iterations/I46.md").split()
        end = added[-1] if added else "HEAD"
        own = _git("log", "--first-parent", "--no-merges", "--format=%H", f"{ck}..{end}").split()
        for c in own:
            for f in _git("diff-tree", "--no-commit-id", "--name-only", "-r", c).split("\n"):
                if f:
                    self.assertTrue(f.startswith(I.OUT + "/") or f == "docs/iterations/I46.md", f"{c[:8]}: {f}")

    def test_r4_the_scope_listing_at_the_base_is_the_rules(self):
        base = _key()["thresholds"]["base_commit"]
        at = I.sidecar(ROOT)["scope"]["at_base"]
        self.assertEqual(at["commit"], base)
        got = I.at_base_listing(I.scope_expected(ROOT, base))
        self.assertEqual(got, {k: at[k] for k in ("given", "stripped", "withheld")})


class TestRun(unittest.TestCase):
    """Red until the blind run's outputs are committed under audit/blind/I46/ (stage 2)."""

    def test_r5_the_pack_is_the_lead_at_the_commit_that_lands_i70(self):
        p = _pack_commit()
        self.assertEqual(I.pack_commit_problems(ROOT, p), [])
        try:
            self.assertEqual(I.pack_commit(ROOT), p)
        except Exception:  # noqa: BLE001  the lead's ref is not in every clone; K's local property is checked above
            pass
        man, leaks = _load("pack/manifest.json"), _load("pack/leaks.json")
        self.assertEqual(man["holon"]["commit"], p)
        self.assertEqual(man["leaks"], leaks["summary"])

    def test_p1_the_scope_set_at_the_pack_commit(self):
        p = _pack_commit()
        self.assertEqual(I.scope_problems(ROOT, p, OUT / "scope"), [])
        got = I.at_base_listing(I.scope_expected(ROOT, p))
        at = I.sidecar(ROOT)["scope"]["at_base"]
        self.assertEqual(got, {k: at[k] for k in ("given", "stripped", "withheld")})

    def test_p2_the_blind_session_read_only_its_pack(self):
        run = _load("session/run.json")
        self.assertEqual(run["family"], "same")
        lines = (OUT / "session" / "tool_calls.jsonl").read_text(encoding="utf-8").splitlines()
        calls = [json.loads(x) for x in lines]
        self.assertEqual(len(calls), run["tool_calls"])
        self.assertEqual(I.calls_problems(calls, run, ROOT), [])
        log = [json.loads(x) for x in (OUT / "session" / "log.jsonl").read_text(encoding="utf-8").splitlines()]
        for e in log:
            if e.get("kind") == "authored":
                rel = Path(e["path"]).relative_to(run["W"]) if Path(e["path"]).is_absolute() else Path(e["path"])
                self.assertTrue((OUT / "authored" / rel).is_file(), str(rel))

    def _lead_is_the_projection_of_p(self, p: str):
        tree = I82.ls_tree(ROOT, p)
        blobs = {path for path, _, typ, _ in tree if typ == "blob"}
        for m in ("M0", "M1", "M2", "M3"):
            for path in sorted(x for x in blobs if x.startswith(f"laws/{m}/L") and x.endswith(".json")
                               and "/" not in x[len(f"laws/{m}/"):]):
                self.assertEqual((OUT / "lead" / path).read_bytes(), I82.show(ROOT, p, path), path)
                lid = json.loads(I82.show(ROOT, p, path))["law_id"]
                rp = f"results/{m}/{lid}.json"
                status = json.loads(I82.show(ROOT, p, rp)).get("status") if rp in blobs else None
                if isinstance(status, str):
                    self.assertEqual((OUT / "lead" / rp).read_text(encoding="utf-8"),
                                     I82.dumps({"law_id": lid, "status": status}), rp)

    def test_p3_matched_fraction_per_milestone(self):
        p = _pack_commit()
        self._lead_is_the_projection_of_p(p)
        cmp, held = _compare()
        committed = _load("compare.json")
        self.assertEqual(committed, I82.compare(OUT / "lead", OUT / "tree", held))
        band = _key()["thresholds"]["bands"]["matched_fraction"]
        ms = cmp["milestones"]
        self.assertEqual(ms["M0"]["matched"], 0)
        self.assertEqual(ms["M1"]["matched"], 0)
        self.assertLessEqual(ms["M2"]["matched_fraction"] or 0.0, band["M2_max"])
        self.assertGreaterEqual(ms["M3"]["matched_fraction"] or 0.0, band["M3"][0])
        self.assertLessEqual(ms["M3"]["matched_fraction"] or 0.0, band["M3"][1])

    def test_p4_matched_fraction_per_rule_and_family(self):
        band = _key()["thresholds"]["bands"]["per_rule_family"]
        b = I.breakdown(OUT / "lead", OUT / "tree", "M3")
        fam, rule = b["family"], b["rule"]
        self.assertGreaterEqual(fam["codec"]["matched_fraction"], band["codec_min"])
        for f, g in fam.items():
            if f != "codec":
                self.assertLessEqual(g["matched_fraction"], band["other_family_max"], f)
        self.assertEqual(fam.get("versions", {"matched": 0})["matched"], 0)
        self.assertGreaterEqual(rule["PAR"]["matched_fraction"], band["PAR_min"])
        for r in ("DISCH", "SORT", "UNDO", "FACT", "OWN"):
            if r in rule:
                self.assertLessEqual(rule[r]["matched_fraction"], band["typed_max"], r)
        for r in ("NAT", "SYM"):
            if r in rule:
                self.assertEqual(rule[r]["matched"], 0, r)

    def test_p5_agreement_on_matched_statements(self):
        band = _key()["thresholds"]["bands"]["agreement"]
        cmp, _ = _compare()
        self.assertGreaterEqual(cmp["milestones"]["M3"]["blind_agreement"], band["M3_min"])
        self.assertGreaterEqual(cmp["pooled"]["blind_agreement"], band["pooled_min"])
        self.assertEqual(I.flips(cmp), [])

    def test_p6_the_exit_decision(self):
        p = _pack_commit()
        cmp, _ = _compare()
        run = _load("session/run.json")
        calls = [json.loads(x) for x in (OUT / "session" / "tool_calls.jsonl").read_text().splitlines()]
        rep = _holon("report", "--milestone", "M3", "--check")
        e = I.exit_clauses(ROOT, p, cmp, I.calls_problems(calls, run, ROOT) == [], rep.returncode == 0)
        want = _key()["thresholds"]["exit_predicted"]
        self.assertEqual({k: e[k] for k in want}, want)


if __name__ == "__main__":
    unittest.main()
