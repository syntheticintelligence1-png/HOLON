"""The implementation never imports the test oracle and never ships Bun config files."""
import re
import unittest

from tests._util import ROOT


class TestHygiene(unittest.TestCase):
    def test_holon_does_not_import_oracle(self):
        pkg = ROOT / "holon"
        self.assertTrue(pkg.is_dir(), "holon/ package missing")
        bad = []
        for f in pkg.rglob("*.py"):
            src = f.read_text()
            if re.search(r"^\s*(from|import)\s+tests\b", src, re.M) or "tests/reference" in src or "tests.reference" in src:
                bad.append(str(f.relative_to(ROOT)))
        self.assertEqual(bad, [], "holon/ must not use the test oracle")

    def test_no_bun_config_in_repo(self):
        # bun reads bunfig.toml / .env from the working directory: a preload there could patch the checker.
        found = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
                 if p.name in ("bunfig.toml", ".env") and ".git" not in p.parts]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
