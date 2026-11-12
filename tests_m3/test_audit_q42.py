"""HUMAN_ANSWERS Q42: the human's plain-language approval counts as L7's human approval, with no gpg signature (the
human, 2026-11-11). The rule is holon/audit/gaps.py (plain_approval, approval_verifies) and the ruling's sidecar is
spec/M3/lib/rule_approvals.json. The reading is tests_m3/_q42.py, which applies I87's instrument unchanged.

  A1 on the committed tree, holon's verdicts are the reading's, and PAR_record_round_trip is admitted under the
     ruling: the sidecar's entry holds its line's payload sha256, and the line's approval field is null;
  A2 on fixtures, holon agrees with the reading. A recorded approval of the line admits, its words quoted by the Q42
     row or by a row of the human's own that the entry cites. These refuse: an edited line (a changed basis, a new
     instance), an entry for another candidate, an entry whose hash names another line, an unverifiable signature
     (even with an entry), a ruling row not marked as the human's own, a missing row, words the row does not quote,
     words that do not name the candidate, an answer row not the human's, and a sidecar citing another ruling. An
     approved candidate that fails (a) or (b) is still refused;
  A3 without the sidecar, I87's (c) stands: no candidate without a signature is admitted, the committed one included;
  A4 the sidecar names the ruling HUMAN_ANSWERS Q42, docs/HUMAN_ANSWERS.md holds its row as the human's own and quotes
     each entry's words, and the paper discloses it (whitepaper.md L7).
"""
from __future__ import annotations

import copy
import json
import shutil
import unittest
from pathlib import Path

from tests_m3 import _i87 as I
from tests_m3 import _q42 as Q
from tests_m3.test_audit_loop import jsonl, run_holon, scratch_root

ROOT = Path(__file__).resolve().parents[1]
GAPS = ROOT / "audit" / "rule_gaps.jsonl"
NAME = "PAR_record_round_trip"
WORDS = "I approve the candidate rule UNSIGNED as its line stands now."
ROW = ("| **Q42** (the human, 2026-11-11) synthetic | **Yes.** The human's words: \"" + WORDS + "\" | effect |")
PERMIT = "| **Q42** (the human, 2026-11-11) synthetic | **Yes.** A plain-language approval counts. | effect |\n"


def gaps(root: Path) -> dict:
    p = run_holon(["audit", "gaps", "--root", str(root), "--json"])
    if p.returncode != 0:
        raise AssertionError(p.stdout[-1500:] + p.stderr[-1500:])
    return json.loads(p.stdout)


def verdicts(rep: dict) -> dict:
    return {k: (v["admitted"], v["fails"]) for k, v in rep["candidates"].items()}


def sidecar(entries: list, ruling: str = Q.RULING) -> dict:
    side = copy.deepcopy(Q.approvals())
    side["ruling"], side["approvals"] = ruling, entries
    return side


def entry(cand: dict, words: str = WORDS, **over) -> dict:
    e = {"candidate": cand["name"], "payload_sha256": Q.payload_sha256(cand), "by": "synthetic human",
         "date": "2026-11-11", "words": words}
    e.update(over)
    return e


def write_root(lines: list, findings: list, side: dict | None, answers: str | None, m: str = "M9") -> Path:
    root = scratch_root()
    (root / "audit").mkdir()
    (root / "audit" / "rule_gaps.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    (root / "audit" / f"{m}_findings.jsonl").write_text("".join(json.dumps(f) + "\n" for f in findings))
    (root / "spec" / "M3" / "lib").mkdir(parents=True)
    shutil.copy(ROOT / I.POLICY_REL, root / "spec" / "M3" / "lib" / "audit_loop.json")
    if side is not None:
        (root / Q.SIDECAR).write_text(json.dumps(side, indent=1) + "\n")
    if answers is not None:
        (root / "docs").mkdir()
        (root / Q.ANSWERS).write_text(answers)
    return root


def by_name(lines: list, name: str) -> dict:
    return next(x for x in lines if x.get("kind") == "candidate" and x["name"] == name)


class TestQ42(unittest.TestCase):
    def check(self, lines: list, findings: list, side: dict | None, answers: str | None, m: str = "M9") -> dict:
        root = write_root(lines, findings, side, answers, m)
        try:
            got = gaps(root)
            self.assertTrue(got["valid"], got)
            fids = Q.findings_by_milestone(root, lines, I.policy())
            want = Q.admission(lines, fids, Q.frozen_key(root), root)
            self.assertEqual(verdicts(got), {k: (v["admitted"], v["fails"]) for k, v in want.items()})
            return verdicts(got)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_a1_committed(self):
        """A1: on the committed tree holon's verdicts are the reading's; PAR_record_round_trip is admitted by Q42."""
        rep = gaps(ROOT)
        self.assertTrue(rep["valid"], rep)
        lines = jsonl(GAPS)
        want = Q.admission(lines, Q.findings_by_milestone(ROOT, lines, I.policy()), Q.frozen_key(ROOT), ROOT)
        self.assertEqual(verdicts(rep), {k: (v["admitted"], v["fails"]) for k, v in want.items()})
        self.assertEqual(verdicts(rep).get(NAME), (True, []))
        self.assertIn(Q.RULING, rep["candidates"][NAME]["why"])
        cand = by_name(lines, NAME)
        self.assertIsNone(cand["approval"])
        hit = [a for a in Q.approvals()["approvals"] if a["candidate"] == NAME]
        self.assertEqual([a["payload_sha256"] for a in hit], [Q.payload_sha256(cand)])

    def test_a2_fixtures(self):
        """A2: holon agrees with the reading on every scenario."""
        lines, findings = I.gap_fixtures()
        good = ROW + "\n"
        uns, nob, one, bog = (by_name(lines, n) for n in ("UNSIGNED", "NOBASIS", "ONE", "BOGUS"))
        edited_basis = copy.deepcopy(lines)
        by_name(edited_basis, "UNSIGNED")["basis"]["argument"] = "an edited basis argument"
        edited_inst = copy.deepcopy(lines) + [I.gap(14, "M9", "F-M9-11", "UNSIGNED")]
        by_name(edited_inst, "UNSIGNED")["instances"].append("RG-M9-14")
        findings_more = findings + [I.finding("F-M9-11", "medium", "open")]
        scenarios = [
            ("approved", lines, findings, [entry(uns)], good, (True, [])),
            ("edited basis", edited_basis, findings, [entry(uns)], good, (False, ["c"])),
            ("new instance", edited_inst, findings_more, [entry(uns)], good, (False, ["c"])),
            ("another candidate", lines, findings, [entry(uns, candidate="OTHER")], good, (False, ["c"])),
            ("another line", lines, findings, [entry(uns, payload_sha256=Q.payload_sha256(nob))], good,
             (False, ["c"])),
            ("not the human's row", lines, findings, [entry(uns)], good.replace("(the human, ", "(lead, "),
             (False, ["c"])),
            ("no row", lines, findings, [entry(uns)], "# Human answers\n", (False, ["c"])),
            ("no answers file", lines, findings, [entry(uns)], None, (False, ["c"])),
            ("words not quoted", lines, findings, [entry(uns, words="I approve everything.")], good,
             (False, ["c"])),
            ("no Q42 row", lines, findings, [entry(uns)], good.replace("**Q42**", "**Q43**"), (False, ["c"])),
            ("words that do not name the candidate", lines, findings, [entry(uns, words="I approve the candidate")],
             good, (False, ["c"])),
            ("an answer row of its own", lines, findings, [entry(uns, answer="HUMAN_ANSWERS Q45")],
             PERMIT + good.replace("**Q42**", "**Q45**"), (True, [])),
            ("an answer row not the human's", lines, findings, [entry(uns, answer="HUMAN_ANSWERS Q45")],
             PERMIT + good.replace("**Q42**", "**Q45**").replace("(the human, ", "(lead, "), (False, ["c"])),
        ]
        for name, ls, fs, entries, answers, want in scenarios:
            with self.subTest(scenario=name):
                got = self.check(ls, fs, sidecar(entries), answers)
                self.assertEqual(got["UNSIGNED"], want)
        with self.subTest(scenario="a sidecar citing a ruling other than Q42"):
            got = self.check(lines, findings, sidecar([entry(uns)], ruling="HUMAN_ANSWERS Q43"),
                             good.replace("**Q42**", "**Q43**"))
            self.assertEqual(got["UNSIGNED"], (False, ["c"]))
        with self.subTest(scenario="approved but failing (a) or (b), or carrying a bogus signature"):
            say = {c["name"]: f"I approve the candidate rule {c['name']} as its line stands now." for c in (nob, one, bog)}
            row = good.replace(WORDS, WORDS + " " + " ".join(say.values()))
            got = self.check(lines, findings, sidecar([entry(c, say[c["name"]]) for c in (nob, one, bog)]
                                                      + [entry(uns)]), row)
            self.assertEqual((got["NOBASIS"], got["ONE"], got["BOGUS"], got["UNSIGNED"]),
                             ((False, ["b"]), (False, ["a"]), (False, ["c"]), (True, [])))

    def test_a3_without_the_sidecar(self):
        """A3: without the sidecar nothing unsigned is admitted, on fixtures and on the committed files."""
        lines, findings = I.gap_fixtures()
        got = self.check(lines, findings, None, ROW + "\n")
        self.assertEqual(sorted(k for k, v in got.items() if v[0]), [])
        committed = jsonl(GAPS)
        root = write_root(committed, [], None, (ROOT / Q.ANSWERS).read_text(encoding="utf-8"), m="M8")
        try:
            shutil.copy(ROOT / "audit" / "M3_findings.jsonl", root / "audit" / "M3_findings.jsonl")
            self.assertEqual(verdicts(gaps(root)).get(NAME), (False, ["c"]))
            (root / Q.SIDECAR).write_text((ROOT / Q.SIDECAR).read_text(encoding="utf-8"))
            self.assertEqual(verdicts(gaps(root)).get(NAME), (True, []))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_a4_ruling_and_disclosure(self):
        """A4: the sidecar names Q42, its row is the human's own and quotes every entry's words; the paper says so."""
        side = Q.approvals()
        self.assertEqual(side["ruling"], Q.RULING)
        row = Q.human_row(ROOT, Q.RULING)
        self.assertIsNotNone(row, "docs/HUMAN_ANSWERS.md has no row Q42 marked as the human's own")
        for a in side["approvals"]:
            self.assertIn(a["words"], row)
        l7 = [x for x in (ROOT / "whitepaper.md").read_text(encoding="utf-8").splitlines() if x.startswith("| L7 |")]
        self.assertEqual(len(l7), 1)
        self.assertIn("`docs/HUMAN_ANSWERS.md` Q42", l7[0])


if __name__ == "__main__":
    unittest.main()
