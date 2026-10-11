"""I3: D2, the zero-blob versioned hash, is checked by code against the real Solidity and Go constants."""
import hashlib
import os
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, holon_module, load_json

ZERO = "0x010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014"


def morph_checkout() -> Path | None:
    for c in (os.environ.get("HOLON_MORPH"), "/root/work/morph"):
        if c and (Path(c) / "contracts" / "contracts" / "l1" / "rollup" / "Rollup.sol").exists():
            return Path(c)
    return None


class TestZeroBlob(unittest.TestCase):
    def test_formula(self):
        Z = holon_module("holon.oracles.zero_blob")
        want = "0x01" + hashlib.sha256(bytes([0xC0]) + bytes(47)).hexdigest()[2:]
        self.assertEqual(Z.compute(), want)
        self.assertEqual(want, ZERO)

    def test_hypotheses_file(self):
        Z = holon_module("holon.oracles.zero_blob")
        h = load_json(ROOT / "results" / "M2" / "hypotheses.json")["Hyp-Z0-kzg"]
        self.assertEqual(h["status"], "checked")
        self.assertEqual(h["computed"], Z.compute())
        self.assertEqual(h["solidity"]["path"], "contracts/contracts/l1/rollup/Rollup.sol")
        self.assertEqual(h["solidity"]["line"], 25)
        self.assertEqual(h["solidity"]["value"], Z.compute())
        self.assertEqual(h["go"]["path"], "common/blob/payload.go")
        self.assertEqual(h["go"]["line"], 22)
        self.assertEqual(h["go"]["value"], Z.compute())
        target = load_json(ROOT / "spec" / "M1" / "facts" / "morph_rollup.json")["target"]["commit"]
        self.assertEqual(h["morph_commit"], target)

    @unittest.skipUnless(morph_checkout(), "needs the morph checkout at the facts' commit (HOLON_MORPH)")
    def test_checkout_agrees(self):
        Z = holon_module("holon.oracles.zero_blob")
        h = load_json(ROOT / "results" / "M2" / "hypotheses.json")["Hyp-Z0-kzg"]
        self.assertEqual(Z.check(morph_checkout()), h)

    def test_mismatch_is_reported_not_hidden(self):
        Z = holon_module("holon.oracles.zero_blob")
        import shutil
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="holon-zb-"))
        try:
            sol = tmp / "contracts" / "contracts" / "l1" / "rollup"
            sol.mkdir(parents=True)
            lines = ["// x"] * 24 + [f"    bytes32 internal constant ZERO_VERSIONED_HASH = 0x{'11' * 32};"]
            (sol / "Rollup.sol").write_text("\n".join(lines) + "\n")
            go = tmp / "common" / "blob"
            go.mkdir(parents=True)
            glines = ["// x"] * 21 + [f'var EmptyVersionedHash = common.HexToHash("{ZERO}")']
            (go / "payload.go").write_text("\n".join(glines) + "\n")
            h = Z.check(tmp, commit=None)
            self.assertEqual(h["status"], "mismatch")
            self.assertEqual(h["solidity"]["value"], "0x" + "11" * 32)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
