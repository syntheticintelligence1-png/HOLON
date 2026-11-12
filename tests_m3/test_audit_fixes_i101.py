"""I101: the lead's post-exit fixes of three findings that M3's audit rounds 8 and 9 filed and the M3 exit left open
(docs/M3_EXIT.md): F-M3-37 (round 8, medium, gate_evasion), F-M3-38 (round 8, low, gate_evasion) and F-M3-42 (round 9,
low, determinism); BUILD_PLAN row I101; the key I101 of spec/M3/predictions.json. The instrument is tests_m3/_i101.py.
It imports nothing from holon/ or tools/. The instrument and this docstring are fixed at the prereg (C_K) and pinned by
sha256 in the key's thresholds; spec/M3/amendments/I101.jsonl records the findings as the key's origin and pins this
docstring as well.

Contract. <B> is the key's base_commit (a3666ec5, the lead after #164), OUT is docs/iterations/I101/, and a copy is a
scratch directory holding the committed M3 audit tree (audit/rounds/M3, audit/M3_findings.jsonl) and spec/M3/lib's
audit_loop.json and audit_rulings.json, with an evidence rule beside them (_i101.copy_audit_tree).

F  The findings, at <B>.
   F37 The counted-round evidence rule (F-M3-27: spec/M3/lib/audit_evidence.json, read by holon/audit/rounds.py
       evidence_problems for RD2 and CV1) reads only each record's version field, milestone, round and target commit.
       A round whose a1.json holds one refused mutant, whose a2.json holds one unsupported case, and whose a4.json and
       packet.json hold only those four fields, passes `holon audit round` and is counted clean by `holon audit
       converge`. On round 8's target, with that round as round 8 (audit/rounds/M3/round8/a7_hollow_round.py), M3 is
       reported converged. Nothing rebuilds a counted round's records from its target.
   F38 `holon coordinator audit-prompt` renders audit/prompts/round.md, which states Q9's counting rule ("Only a
       `different`-family round ... counts toward convergence") and the auditor fields {session, family,
       counts_toward_convergence}. It omits HUMAN_ANSWERS Q9b's admission (auditor.ruling) and the evidence a counted
       round must carry.
   F42 `holon run --milestone M3 --laws <one law>` deletes the committed gen/M3/model files that law does not use, and
       rewrites results/M3/summary.json and results/M3/deps.json to that one law.
S  The build.
   S1 (F37) The rule gains each record's content, which evidence_problems reads (RD2, CV1):
      - a1.json holds a mutant whose verdict is not refused;
      - a2.json holds a case whose verdict is not unsupported;
      - a4.json is valid against spec/M3/lib/audit_a4.schema.json, its laws are exactly packet.json's, and its
        counts are the tally of its laws' classes;
      - packet.json is valid against spec/M3/lib/audit_packet.schema.json and holds at least one law.
      The two schemas are inputs of this prereg. F-M3-27's header rule is unchanged.
   S2 (F37) `holon audit evidence --milestone M --rebuild [--rounds streak|all|n,..]` rebuilds each round's a4.json
      (`holon audit vacuity --check`) and packet.json (`holon audit hostile --check`) from its own target commit. By
      default it covers the rounds of the milestone's current streak (results/<M>/audit_status.json), and it exits 0
      iff each record is identical. CI runs it on M3.
   S3 (F38) The rendered prompt states three things from the milestone's sidecars (spec/<M>/lib/audit_loop.json,
      audit_rulings.json, audit_evidence.json), not from the template's text: the counting rule, the auditor fields,
      and the evidence a counted round carries. A milestone without rulings or evidence keeps I87's rule.
   S4 (F42) A run with --laws keeps what it does not own. No file under gen/<M>/model or gen/<M>/core that existed
      before the run is missing after it. summary.json and deps.json are the committed ones, with the listed laws'
      entries replaced by the run's. A run without --laws is unchanged, and no file of a generator closure changes.
K  The pins hold, `holon audit prereg --milestone M3` prints PREREG OK, the instrument imports nothing from holon/ or
   tools/, and spec/M3/amendments/I101.jsonl holds one line for this module, pinning this docstring.
B  The build's checks.
   B1 On a copy with HEAD's rule, a hollow round (_i101.hollow_round, numbered after the copy's last) is refused by
      RD2, naming F-M3-37 and each of a1.json, a2.json, a4.json and packet.json, and is not counted.
   B2 On a copy with HEAD's rule, each change of _i101.TAMPERS, made alone to round 9, makes RD2 refuse round 9 (naming
      F-M3-37), and CV1 does not count it. The changes:
      - every A1 mutant refused;
      - every A2 case unsupported;
      - a4.json's laws emptied;
      - a4.json without one of the packet's laws;
      - a4.json's counts off by one;
      - a4.json failing its schema;
      - packet.json's laws emptied.
      The unchanged copy is valid, with round 9 counted, and its status is the committed one.
   B3 At HEAD, every committed round of M3 is valid under the rule, and results/M3/audit_status.json regenerates byte for
      byte (`holon audit converge --milestone M3 --check`).
   B4 `holon audit evidence --milestone M3 --rebuild --rounds 9 --root <copy>` exits non-zero and names round 9's
      packet.json, on a copy whose round 9 packet.json has one law's statement_hash changed (the round file's
      packet.sha256 updated to match).
   B5 The rendered prompts of M3 round 9, for each type A1-A4:
      - state HUMAN_ANSWERS Q9b's admission, auditor.ruling "HUMAN_ANSWERS Q9b", and each other condition of CV1;
      - name the four evidence records, with the content each must carry;
      - list the auditor fields session, family, ruling and counts_toward_convergence;
      - do not state "Only a `different`-family round".
      On a root without audit_rulings.json and audit_evidence.json, the rendered prompt states I87's rule.
   B6 In a detached worktree of HEAD, `holon run --milestone M3 --laws <_i101.SUBSET_LAW>` exits 0 with the law
      PROVED. It deletes no file, leaves summary.json and deps.json byte-identical, and changes only the law's record.
   B7 No target name (I100's _i100.target_names) is in the lines I101 adds under holon/ before its report.
   B8 The workflow (.github/workflows/holon-ci.yml) holds a job that runs this module's build checks, and one that runs
      `holon audit evidence --milestone M3 --rebuild`.
   B9 No file of a generator closure differs from <B> (holon.records.generator_files for each IR version,
      holon.profile.generator_files, the bundle-law closure). So no committed record's generator_sha256 moves.
P  The outcomes (OUT is written after C_K).
   P1 F37 is fixed. On F-M3-37's reproduction root (_i101.probe_tree at round 8's target, with its hollow round 8),
      under the base's rule the round is counted clean and M3 is reported converged (the finding, reproduced on HEAD's
      code). Under HEAD's rule, RD2 refuses round 8, CV1 does not count it, and M3 is not converged, with streak 2
      (OUT/f37.json).
   P2 F38 is fixed (OUT/prompts.json: each rendered prompt's sha256 and its counting-rule lines), as B5.
   P3 F42 is fixed (OUT/subset.json). B6 holds, and so does its two-law form: `--laws <_i101.SUBSET_PAIR>`, both
      PROVED, deletes no file, leaves summary.json and deps.json byte-identical, and changes only the two records.
   P4 Rounds 3, 4 and 5's a4.json, rebuilt from their own targets (`holon audit evidence --rebuild --rounds 3,4,5`),
      are identical (OUT/rebuild_early.json).
   P5 M3 stays converged under the new rule. results/M3/audit_status.json is <B>'s byte for byte: converged, streak 4,
      7 counted rounds (OUT/status.json: its sha256 at <B> and at HEAD).
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

from tests_m3 import _i101 as I

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / I.OUT
KEYFILE = ROOT / "spec" / "M3" / "predictions" / "I101.json"
TEST_ID = "tests_m3/test_audit_fixes_i101.py::<contract>"   # the audit wants "file::key"; this key names no test
STATUS = ROOT / "results" / "M3" / "audit_status.json"


def _th() -> dict:
    return json.loads(KEYFILE.read_text(encoding="utf-8"))["thresholds"]


def _sha(p) -> str:
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def _load(rel: str):
    return json.loads((OUT / rel).read_text(encoding="utf-8"))


def _rd2(problems: list, n: int) -> list:
    return [p for p in problems if p.startswith(f"RD2: round{n} ")]


def _prompt(root: Path, n: int, typ: str) -> str:
    p = I.holon(["coordinator", "audit-prompt", "--milestone", "M3", "--round", n, "--type", typ, "--root", root])
    if p.returncode != 0:
        raise AssertionError(p.stdout[-800:] + p.stderr[-800:])
    return p.stdout


def _flat(text: str) -> str:
    """The rendered text with every run of whitespace one space: the template wraps its sentences."""
    return " ".join(text.split())


class TestPrereg(unittest.TestCase):
    def test_r0_the_prereg_pins_hold(self):
        th = _th()
        self.assertEqual(hashlib.sha256(__doc__.encode("utf-8")).hexdigest(), th["contract_docstring_sha256"])
        for name, pin in th["pins"].items():
            self.assertEqual(_sha(pin["path"]), pin["sha256"], name)

    def test_r1_the_prereg_audit_passes(self):
        r = I.holon(["audit", "prereg", "--milestone", "M3"], timeout=900)
        self.assertIn("PREREG OK", r.stdout + r.stderr)

    def test_r2_the_instrument_imports_nothing_from_holon_or_tools(self):
        src = (ROOT / "tests_m3" / "_i101.py").read_text(encoding="utf-8")
        self.assertFalse(re.search(r"(?m)^\s*(from|import)\s+(holon|tools)\b", src))

    def test_r3_the_amendment_pins_this_docstring(self):
        lines = [json.loads(x) for x in (ROOT / "spec" / "M3" / "amendments" / "I101.jsonl").read_text(
            encoding="utf-8").splitlines() if x.strip()]
        mine = [x for x in lines if x.get("test") == TEST_ID]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]["contract_sha256"], hashlib.sha256(__doc__.encode("utf-8")).hexdigest())


class TestBuild(unittest.TestCase):
    def test_b1_a_hollow_round_is_refused(self):
        with tempfile.TemporaryDirectory(prefix="i101-b1-") as tmp:
            s = I.copy_audit_tree(Path(tmp), (ROOT / I.RULE).read_bytes())
            n = I.last_round(s) + 1
            I.hollow_round(s, n, "0" * 40)
            problems, st = I.verdicts(s)
            rd2 = _rd2(problems, n)
            self.assertEqual(len(rd2), 1, problems)
            self.assertIn("F-M3-37", rd2[0])
            for name in ("a1.json", "a2.json", "a4.json", "packet.json"):
                self.assertIn(f"round{n}/{name}", rd2[0])
            self.assertFalse(I.row(st, n)["counted"])

    def test_b2_each_content_change_is_refused(self):
        with tempfile.TemporaryDirectory(prefix="i101-b2-") as tmp:
            base = I.copy_audit_tree(Path(tmp) / "base", (ROOT / I.RULE).read_bytes())
            problems, st = I.verdicts(base)
            self.assertEqual(problems, [])
            self.assertTrue(I.row(st, I.TAMPERED)["counted"])
            committed = json.loads(STATUS.read_text(encoding="utf-8"))
            self.assertEqual({k: v for k, v in st.items() if k != "generated_from"},
                             {k: v for k, v in committed.items() if k != "generated_from"})
            for name, change in sorted(I.TAMPERS.items()):
                with self.subTest(change=name):
                    s = Path(tmp) / re.sub(r"\W+", "_", name)
                    shutil.copytree(base, s)
                    change(s)
                    problems, st = I.verdicts(s)
                    rd2 = _rd2(problems, I.TAMPERED)
                    self.assertEqual(len(rd2), 1, problems)
                    self.assertIn("F-M3-37", rd2[0])
                    self.assertFalse(I.row(st, I.TAMPERED)["counted"])

    def test_b3_the_committed_rounds(self):
        p = I.holon(["audit", "round", "--milestone", "M3", "--json"])
        self.assertEqual(json.loads(p.stdout)["problems"], [])
        q = I.holon(["audit", "converge", "--milestone", "M3", "--check"])
        self.assertEqual(q.returncode, 0, q.stdout[-1500:] + q.stderr[-1500:])

    def test_b4_a_changed_packet_does_not_rebuild(self):
        with tempfile.TemporaryDirectory(prefix="i101-b4-") as tmp:
            s = I.copy_audit_tree(Path(tmp), (ROOT / I.RULE).read_bytes())
            pk = s / "audit" / "rounds" / "M3" / "round9" / "packet.json"
            d = I.load(pk)
            lid = sorted(d["laws"])[0]
            d["laws"][lid]["statement_hash"] = "0" * 64
            pk.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            rp = s / "audit" / "rounds" / "M3" / "round9.json"
            r = I.load(rp)
            r["packet"]["sha256"] = I.sha256(pk)
            rp.write_text(json.dumps(r, indent=1) + "\n", encoding="utf-8")
            p = I.holon(["audit", "evidence", "--milestone", "M3", "--rebuild", "--rounds", "9", "--root", s,
                         "--only", "packet", "--work", Path(tmp) / "w"], timeout=1800)
            self.assertNotEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
            self.assertIn("round9/packet.json", p.stdout + p.stderr)

    def test_b5_the_rendered_prompts_state_the_rule_in_force(self):
        for typ in ("A1", "A2", "A3", "A4"):
            with self.subTest(type=typ):
                text = _flat(_prompt(ROOT, 9, typ))
                self.assertNotIn("Only a `different`-family round", text)
                self.assertIn("HUMAN_ANSWERS Q9b", text)
                self.assertIn("auditor.ruling", text)
                for cond in ("A1, A2, A3 and A4", "dry run", "earlier round"):
                    self.assertIn(cond, text)
                for rec in ("a1.json", "a2.json", "a4.json", "packet.json"):
                    self.assertIn(rec, text)
                for word in ("refused", "unsupported", "audit_a4.schema.json", "audit_packet.schema.json"):
                    self.assertIn(word, text)
                self.assertRegex(text, r"session.*family.*ruling.*counts_toward_convergence")
        with tempfile.TemporaryDirectory(prefix="i101-b5-") as tmp:
            s = Path(tmp)
            shutil.copytree(ROOT / "audit" / "prompts", s / "audit" / "prompts")
            (s / "audit" / "rounds" / "M3" / "round9").mkdir(parents=True)
            shutil.copy(ROOT / "audit" / "rounds" / "M3" / "round9" / "packet.json",
                        s / "audit" / "rounds" / "M3" / "round9" / "packet.json")
            (s / "spec" / "M3" / "lib").mkdir(parents=True)
            shutil.copy(ROOT / "spec" / "M3" / "lib" / "audit_loop.json", s / "spec" / "M3" / "lib" / "audit_loop.json")
            text = _flat(_prompt(s, 9, "A1"))
            self.assertIn("Only a `different`-family round", text)
            self.assertNotIn("HUMAN_ANSWERS Q9b", text)

    def test_b6_a_subset_run_keeps_what_it_does_not_own(self):
        with tempfile.TemporaryDirectory(prefix="i101-b6-") as tmp:
            r = I.subset_run([I.SUBSET_LAW], Path(tmp))
            self.assertEqual(r["exit"], 0, r["tail"])
            self.assertEqual(r["status"], {I.SUBSET_LAW: "PROVED"})
            self.assertEqual(r["deleted"], [])
            self.assertEqual(r["identical"], {"summary.json": True, "deps.json": True})
            self.assertEqual(r["changed"], [f"results/M3/{I.SUBSET_LAW}.json"])

    def test_b7_target_agnostic(self):
        from tests_m3 import _i100
        added = I.git(ROOT, "log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--",
                      "docs/iterations/I101.md").split()
        head = added[0] if added else "HEAD"
        out = I.added_lines(ROOT, _th()["base_commit"], head)
        self.assertTrue(out, "I101 adds no line under holon/")
        self.assertEqual(_i100.scan(out, _i100.target_names(ROOT)), [])

    def test_b8_ci_runs_them(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        self.assertIn("tests_m3.test_audit_fixes_i101.TestBuild", wf)
        self.assertRegex(wf, r"holon audit evidence --milestone M3 --rebuild")

    def test_b9_no_generator_closure_moves(self):
        base = _th()["base_commit"]
        changed = set(I.git(ROOT, "diff", "--name-only", f"{base}..HEAD").split())
        code = (
            "import json, sys\n"
            "from pathlib import Path\n"
            "from holon import records, profile\n"
            "from holon.bundle import lawrun\n"
            "from holon.records import _holon_imports\n"
            "from holon.sorts.run3 import GEN3\n"
            "root = Path('.')\n"
            "fs = set()\n"
            "for v in records.GENERATORS:\n"
            "    fs |= set(records.generator_files(v, root))\n"
            "fs |= set(profile.generator_files(root))\n"
            "seen, todo = set(), list(lawrun.GEN_LAWS) + list(GEN3)\n"
            "while todo:\n"
            "    r = todo.pop()\n"
            "    if r in seen or not (root / r).is_file():\n"
            "        continue\n"
            "    seen.add(r)\n"
            "    if r.endswith('.py'):\n"
            "        todo.extend(sorted(_holon_imports(r, root) - seen))\n"
            "print(json.dumps(sorted(fs | seen)))\n")
        p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=600)
        self.assertEqual(p.returncode, 0, p.stderr[-1500:])
        closure = set(json.loads(p.stdout))
        self.assertTrue(closure)
        self.assertEqual(sorted(changed & closure), [])


class TestOutcome(unittest.TestCase):
    def test_p1_f37_reproduced_and_fixed(self):
        res = {}
        for which, rule in (("base", I.base_rule()), ("head", (ROOT / I.RULE).read_bytes())):
            with tempfile.TemporaryDirectory(prefix=f"i101-p1-{which}-") as tmp:
                s = I.probe_tree(Path(tmp))
                (s / I.RULE).write_bytes(rule)
                I.hollow_round(s, I.PROBE_ROUND, I.PROBE_TARGET)
                problems, st = I.verdicts(s)
                r8 = I.row(st, I.PROBE_ROUND)
                res[which] = {"rd2": _rd2(problems, I.PROBE_ROUND), "counted": r8["counted"], "clean": r8["clean"],
                              "converged": st["converged"], "streak": st["streak"]}
        self.assertEqual(res["base"]["rd2"], [])
        self.assertTrue(res["base"]["counted"] and res["base"]["clean"] and res["base"]["converged"])
        self.assertEqual(len(res["head"]["rd2"]), 1)
        self.assertFalse(res["head"]["counted"])
        self.assertFalse(res["head"]["converged"])
        self.assertEqual(res["head"]["streak"], 2)
        rec = _load("f37.json")
        self.assertEqual({k: {kk: vv for kk, vv in v.items() if kk != "rd2"} for k, v in rec.items()},
                         {k: {kk: vv for kk, vv in v.items() if kk != "rd2"} for k, v in res.items()})

    def test_p2_f38_the_prompts(self):
        rec = _load("prompts.json")
        for typ in ("A1", "A2", "A3", "A4"):
            with self.subTest(type=typ):
                raw = _prompt(ROOT, 9, typ)
                self.assertEqual(rec[typ]["sha256"], hashlib.sha256(raw.encode("utf-8")).hexdigest())
                text = _flat(raw)
                self.assertNotIn("Only a `different`-family round", text)
                self.assertIn("HUMAN_ANSWERS Q9b", text)

    def test_p3_f42_the_subset_runs(self):
        rec = _load("subset.json")
        for laws in ([I.SUBSET_LAW], list(I.SUBSET_PAIR)):
            with self.subTest(laws=laws):
                r = next(x for x in rec["runs"] if x["laws"] == laws)
                self.assertEqual(r["exit"], 0)
                self.assertEqual(r["status"], {lid: "PROVED" for lid in laws})
                self.assertEqual(r["deleted"], [])
                self.assertEqual(r["identical"], {"summary.json": True, "deps.json": True})
                self.assertEqual(r["changed"], sorted(f"results/M3/{lid}.json" for lid in laws))

    def test_p4_the_early_rounds_rebuild(self):
        rec = _load("rebuild_early.json")
        self.assertEqual(sorted(rec["rounds"]), ["3", "4", "5"])
        for n, x in sorted(rec["rounds"].items()):
            with self.subTest(round=n):
                self.assertEqual(x["a4.json"], "identical")

    def test_p5_m3_stays_converged(self):
        rec = _load("status.json")
        self.assertEqual(rec["base_sha256"], rec["head_sha256"])
        self.assertEqual(I.sha256(STATUS), rec["head_sha256"])
        st = json.loads(STATUS.read_text(encoding="utf-8"))
        self.assertTrue(st["converged"])
        self.assertEqual(st["streak"], 4)
        self.assertEqual(sum(1 for r in st["rounds"] if r["counted"]), 7)


if __name__ == "__main__":
    unittest.main()
