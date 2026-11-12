"""I106's contract: fresh sealed targets by commit-reveal (key I106; docs/BUILD_PLAN.md §4 I106, HUMAN_ANSWERS Q54).

Inputs fixed at the prereg (spec/M6/lib/):
  I106_candidates.json   the candidate list and its criteria (names and URLs only)
  I106_draw.py           the draw script: seed, order, draw of 2, pin rule, seal and verify (standard library only)
The key spec/M6/predictions/I106.json holds, in thresholds.seal, T (the beacon time), sha256(salt) and the sha256 of
both sidecars.

Outcomes (spec/heldout2/):
  commitment.json   the seal: sha256(target.json), sha256(salt), the beacon block's number, hash and timestamp
  README.md         the sealed state and the sole-reader rule
  target.json       at the reveal only: the plaintext, byte-identical to the sealed bytes
  salt.txt          at the reveal only: the 64 hex characters of the salt and one newline

Rules:
  D1  The draw script imports only the standard library, and is deterministic on a fixed test vector.
  D2  The pin rule takes the greatest strict MAJOR.MINOR.PATCH release tag (peeled), else the default branch.
  C1  At least 8 candidates, unique ids, canonical github.com URLs, no excluded system.
  K1  The key's seal block equals the sidecars' sha256s; T is a whole second; sha256(salt) is 64 hex.
  S1  The seal: commitment.json's salt_sha256 is the key's; its block's timestamp is >= T; README states the rule.
  R1  The reveal: `I106_draw.py verify` passes, and target.json's beacon is the commitment's.
TestSeal is red until the seal (c); TestReveal is red until the reveal (d).
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "spec" / "M6" / "lib"
DRAW = LIB / "I106_draw.py"
CANDS = LIB / "I106_candidates.json"
KEY = ROOT / "spec" / "M6" / "predictions" / "I106.json"
H2 = ROOT / "spec" / "heldout2"
EXCLUDED = ("morph", "scroll", "arbitrum", "compound", "cosmos", "go-ethereum", "geth", "optimism", "wormhole",
            "across", "spark")


def load_draw():
    spec = importlib.util.spec_from_file_location("i106_draw", DRAW)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def key_seal() -> dict:
    return json.loads(KEY.read_text(encoding="utf-8"))["thresholds"]["seal"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class TestDraw(unittest.TestCase):
    def test_d1_stdlib_only(self):
        tree = ast.parse(DRAW.read_text(encoding="utf-8"))
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                names |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                self.assertEqual(n.level, 0)
                names.add(n.module.split(".")[0])
        std = set(sys.stdlib_module_names) | {"__future__"}
        self.assertEqual(sorted(names - std), [])

    def test_d1_test_vector(self):
        d = load_draw()
        salt = bytes(range(32))
        bh = "0x" + "ab" * 32
        s = d.seed(salt, bh)
        self.assertEqual(s, hashlib.sha256(salt + bytes.fromhex("ab" * 32)).hexdigest())
        cands = d.load_candidates()
        o1 = [c["id"] for c in d.order(s, cands)]
        o2 = [c["id"] for c in d.order(s, list(reversed(cands)))]
        self.assertEqual(o1, o2)
        self.assertEqual(sorted(o1), sorted(c["id"] for c in cands))
        sb = bytes.fromhex(s)
        keys = [hashlib.sha256(sb + i.encode()).hexdigest() for i in o1]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(d.salt_sha256(salt), hashlib.sha256(salt).hexdigest())
        with self.assertRaises(d.DrawError):
            d.seed(salt, "0x" + "AB" * 32)

    def test_d2_pin_rule(self):
        d = load_draw()
        a, b, c, e, f = ("1" * 40, "2" * 40, "3" * 40, "4" * 40, "5" * 40)
        tags = "\n".join([
            f"{a}\trefs/tags/v1.2.3",
            f"{b}\trefs/tags/v1.10.0",
            f"{c}\trefs/tags/v1.10.0^{{}}",
            f"{e}\trefs/tags/v2.0.0-rc1",
            f"{f}\trefs/tags/contracts/v9.0.0",
            f"{a}\trefs/heads/main",
        ])
        self.assertEqual(d.pin(tags, None),
                         {"kind": "tag", "ref": "refs/tags/v1.10.0", "tag": "v1.10.0", "commit": c})
        head = f"ref: refs/heads/dev\tHEAD\n{e}\tHEAD\n"
        self.assertEqual(d.pin(f"{f}\trefs/tags/release-1\n", head),
                         {"kind": "branch", "ref": "refs/heads/dev", "branch": "dev", "commit": e})
        self.assertEqual(d.pin(f"{a}\trefs/tags/1.0.0\n{b}\trefs/tags/v1.0.0\n", None)["commit"], a)


class TestCandidates(unittest.TestCase):
    def test_c1_candidates(self):
        doc = json.loads(CANDS.read_text(encoding="utf-8"))
        cands = doc["candidates"]
        self.assertGreaterEqual(len(cands), 8)
        ids = [c["id"] for c in cands]
        self.assertEqual(len(set(ids)), len(ids))
        for c in cands:
            self.assertRegex(c["repo"], r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
            blob = (c["id"] + " " + c["name"] + " " + c["repo"]).lower()
            for x in EXCLUDED:
                self.assertNotIn(x, blob, c["id"])
        for k in ("C1_well_known", "C2_multi_component", "C3_upgrade_history", "C4_public_repo", "excluded"):
            self.assertTrue(doc["criteria"][k])

    def test_k1_key_pins_the_sidecars(self):
        s = key_seal()
        self.assertEqual(s["candidates_sha256"], sha(CANDS))
        self.assertEqual(s["draw_sha256"], sha(DRAW))
        self.assertIsInstance(s["T_unix"], int)
        self.assertRegex(s["salt_sha256"], r"^[0-9a-f]{64}$")


class TestSeal(unittest.TestCase):
    def test_s1_commitment(self):
        com = json.loads((H2 / "commitment.json").read_text(encoding="utf-8"))
        s = key_seal()
        self.assertEqual(com["salt_sha256"], s["salt_sha256"])
        self.assertRegex(com["target_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(com["beacon"]["hash"], r"^0x[0-9a-f]{64}$")
        self.assertIsInstance(com["beacon"]["number"], int)
        self.assertGreaterEqual(com["beacon"]["timestamp"], s["T_unix"])
        self.assertEqual(com["T_unix"], s["T_unix"])
        self.assertTrue(com["beacon"]["source"])

    def test_s1_readme(self):
        text = (H2 / "README.md").read_text(encoding="utf-8")
        self.assertIn("sole-reader", text)
        self.assertIn("I107", text)


class TestReveal(unittest.TestCase):
    def test_r1_verify(self):
        d = load_draw()
        probs = d.verify(H2 / "target.json", H2 / "salt.txt", H2 / "commitment.json", d.load_candidates())
        self.assertEqual(probs, [])

    def test_r1_targets(self):
        doc = json.loads((H2 / "target.json").read_text(encoding="utf-8"))
        com = json.loads((H2 / "commitment.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["beacon"], com["beacon"])
        self.assertEqual(len(doc["targets"]), 2)
        for t in doc["targets"]:
            self.assertIn(t["pin"]["kind"], ("tag", "branch"))
            self.assertRegex(t["pin"]["commit"], r"^[0-9a-f]{40}$")
            self.assertTrue(re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", t["listed_at_utc"]))


if __name__ == "__main__":
    unittest.main()
