"""F-M3-27 (M3 audit round 6; the lead's triage, landed via #133): a round that claims to count toward convergence
carries its evidence. The rule is spec/M3/lib/audit_evidence.json, read by holon/audit/rounds.py (evidence_problems,
qualifies, RD2) and holon/audit/converge.py (CV1), beside I87's policy spec/M3/lib/audit_loop.json, which stays
byte-identical to its prereg.

With that file in the root, a round whose auditor.counts_toward_convergence is true qualifies only if its own directory
audit/rounds/<M>/round<n>/ holds a1.json, a2.json, a4.json and packet.json. Each is a JSON object with its version
field (a1_version, a2_version, a4_version, packet_version), and names the round's milestone, number and target commit.
a1.json, a2.json and a4.json are each cited in the evidence of an attack of the round that ran with auditor type A1,
A2 and A4 respectively. packet.json is the round's packet.path, with that sha256. A round that claims to count without
its evidence is refused by RD2 and not counted by CV1. A round that does not claim to count is not checked. A root
without the file keeps I87's rule (and Q9b's).

  E1 on a scratch copy of the committed M3 audit tree with the rule, one change at a time to round 6 (counted, clean):
     a4.json removed, packet.json changed by a byte, a4.json naming round 5, a4.json without a4_version, or the A4
     attack no longer citing a4.json: each makes RD2 refuse round 6, which is then not counted, so the number of
     counted rounds falls by one and the streak does not rise; the unchanged copy is valid, with round 6 counted, and
     its status is the committed one (whatever later rounds have added);
  E2 without the rule, the copy with a4.json removed is valid and round 6 is counted, with the committed status's
     counted rounds and streak: the rule is the file's;
  E3 F-M3-27's probe (audit/rounds/M3/round6/a7/cv1_probe.py) on a scratch tree of its target ed893be8: without the
     rule its three evidence-less rounds pass and are counted clean (the finding, reproduced); with the rule each is
     refused by RD2, none is counted, and the streak is 0;
  E4 the committed rounds of M3 are valid under the rule, and results/M3/audit_status.json regenerates byte for byte;
  E5 the rule names F-M3-27 and requires exactly a1.json (A1), a2.json (A2), a4.json (A4) and packet.json.
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from tests_m3.test_audit_loop import load, run_holon

ROOT = Path(__file__).resolve().parents[1]
M = "M3"
RULE = Path("spec") / M / "lib" / "audit_evidence.json"
PROBE = ROOT / "audit" / "rounds" / M / "round6" / "a7" / "cv1_probe.py"
PROBE_TARGET = "ed893be8abb2fa2c57804cf32e0cd45de7184fbb"


def copy_audit_tree(dst: Path, with_rule: bool = True) -> Path:
    """The committed M3 audit tree (rounds, findings, policy, rulings) and, with_rule, the evidence rule."""
    shutil.copytree(ROOT / "audit" / "rounds" / M, dst / "audit" / "rounds" / M)
    shutil.copy(ROOT / "audit" / f"{M}_findings.jsonl", dst / "audit" / f"{M}_findings.jsonl")
    (dst / "spec" / M / "lib").mkdir(parents=True)
    for name in ("audit_loop.json", "audit_rulings.json") + (("audit_evidence.json",) if with_rule else ()):
        shutil.copy(ROOT / "spec" / M / "lib" / name, dst / "spec" / M / "lib" / name)
    return dst


def verdicts(root: Path) -> tuple[list, dict]:
    """(holon audit round's problems, holon audit converge's status document) on the root."""
    p = run_holon(["audit", "round", "--milestone", M, "--root", str(root), "--json"])
    rep = json.loads(p.stdout)
    out = root / "status.json"
    q = run_holon(["audit", "converge", "--milestone", M, "--root", str(root), "--out", str(out)])
    if q.returncode != 0:
        raise AssertionError(q.stdout[-1500:] + q.stderr[-1500:])
    return rep["problems"], load(out)


def row(st: dict, n: int) -> dict:
    return next(r for r in st["rounds"] if r["round"] == n)


def rewrite(p: Path, change) -> None:
    d = json.loads(p.read_text(encoding="utf-8"))
    change(d)
    p.write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8")


def drop_a4_citation(r: dict) -> None:
    for a in r["attacks"]:
        if a.get("auditor_type") == "A4":
            a["evidence"] = [e for e in a.get("evidence") or [] if not e.endswith("/a4.json")]


R6 = Path("audit") / "rounds" / M / "round6"
CHANGES = {
    "a4.json removed": lambda s: (s / R6 / "a4.json").unlink(),
    "packet.json changed by a byte": lambda s: (s / R6 / "packet.json").write_bytes(
        (s / R6 / "packet.json").read_bytes() + b" "),
    "a4.json names round 5": lambda s: rewrite(s / R6 / "a4.json", lambda d: d.__setitem__("round", 5)),
    "a4.json without a4_version": lambda s: rewrite(s / R6 / "a4.json", lambda d: d.pop("a4_version")),
    "the A4 attack does not cite a4.json": lambda s: rewrite(s / R6.parent / "round6.json", drop_a4_citation),
}


class TestEvidence(unittest.TestCase):
    def scratch(self) -> Path:
        d = Path(tempfile.mkdtemp(prefix="f27-"))
        self.addCleanup(shutil.rmtree, d, True)
        return d

    def test_e1_round6_without_its_evidence_is_refused(self):
        """E1: each removal or mismatch of round 6's evidence makes RD2 refuse it, and it is not counted."""
        problems, st0 = verdicts(copy_audit_tree(self.scratch()))
        self.assertEqual(problems, [])
        self.assertTrue(row(st0, 6)["counted"], row(st0, 6))
        committed = load(ROOT / "results" / M / "audit_status.json")
        self.assertEqual((st0["counted"], st0["streak"]), (committed["counted"], committed["streak"]))
        for name, change in CHANGES.items():
            with self.subTest(change=name):
                s = copy_audit_tree(self.scratch())
                change(s)
                problems, st = verdicts(s)
                self.assertTrue(any(p.startswith("RD2: round6 ") and "F-M3-27" in p for p in problems), problems)
                self.assertFalse(row(st, 6)["counted"], row(st, 6))
                self.assertIn("F-M3-27", row(st, 6)["why"])
                self.assertEqual(st["counted"], st0["counted"] - 1)
                self.assertLessEqual(st["streak"], st0["streak"])
                self.assertFalse(st["converged"])

    def test_e2_without_the_rule_i87s_reading_stands(self):
        """E2: without spec/M3/lib/audit_evidence.json, round 6 without a4.json is valid and counted."""
        s = copy_audit_tree(self.scratch(), with_rule=False)
        CHANGES["a4.json removed"](s)
        problems, st = verdicts(s)
        self.assertEqual(problems, [])
        self.assertTrue(row(st, 6)["counted"])
        committed = load(ROOT / "results" / M / "audit_status.json")
        self.assertEqual((st["counted"], st["streak"]), (committed["counted"], committed["streak"]))

    def test_e3_the_findings_probe(self):
        """E3: F-M3-27's probe passes without the rule and is refused with it."""
        for with_rule in (False, True):
            with self.subTest(with_rule=with_rule):
                s = self.scratch() / "tree"
                s.mkdir()
                tar = subprocess.run(["git", "-C", str(ROOT), "archive", PROBE_TARGET], capture_output=True,
                                     check=True).stdout
                tarfile.open(fileobj=io.BytesIO(tar)).extractall(s, filter="data")
                if with_rule:
                    shutil.copy(ROOT / RULE, s / RULE)
                p = subprocess.run([sys.executable, "-I", str(PROBE), str(s)], capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
                problems, st = verdicts(s)
                probe = [row(st, n) for n in (6, 7, 8)]
                if with_rule:
                    for n in (6, 7, 8):
                        self.assertTrue(any(x.startswith(f"RD2: round{n} ") and "F-M3-27" in x for x in problems),
                                        problems)
                    self.assertFalse(any(r["counted"] for r in probe), probe)
                    self.assertEqual(st["streak"], 0)
                else:
                    self.assertEqual(problems, [])
                    self.assertTrue(all(r["counted"] and r["clean"] for r in probe), probe)
                    self.assertEqual(st["streak"], 3)

    def test_e4_the_committed_rounds(self):
        """E4: the committed rounds of M3 are valid under the rule, and the status regenerates byte for byte."""
        self.assertTrue((ROOT / RULE).is_file())
        p = run_holon(["audit", "round", "--milestone", M, "--json"])
        self.assertEqual(json.loads(p.stdout)["problems"], [])
        q = run_holon(["audit", "converge", "--milestone", M, "--check"])
        self.assertEqual(q.returncode, 0, q.stdout[-1500:] + q.stderr[-1500:])

    def test_e5_the_rule(self):
        """E5: the rule names F-M3-27 and requires exactly the four records."""
        req = load(ROOT / RULE)["counted_round_requires"]
        self.assertEqual(req["finding"], "F-M3-27")
        self.assertEqual({k: (v.get("auditor_type"), v.get("packet", False), v["version_field"])
                          for k, v in req["records"].items()},
                         {"a1.json": ("A1", False, "a1_version"), "a2.json": ("A2", False, "a2_version"),
                          "a4.json": ("A4", False, "a4_version"), "packet.json": (None, True, "packet_version")})


if __name__ == "__main__":
    unittest.main()
