"""Determinism + live-extraction checks.

* `extract` over the recorded cache twice produces byte-identical output.
* With HOLON_MORPH + HOLON_LINK_CACHE set, re-extracting reproduces the
  committed links.json / migrations.json / coverage / manifest byte for byte
  (the "re-running reproduces the output" guarantee).
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from . import _util

CACHE = Path(os.environ.get("HOLON_LINK_CACHE", Path.home() / ".holon" / "cache" / "m2" / "link"))


def _have_cache():
    return (CACHE / "record.json").exists() and (CACHE / "sourcify").is_dir()


class TestDeterminism(unittest.TestCase):
    def setUp(self):
        if not (_util.morph_available() and _have_cache()):
            self.skipTest("needs morph checkout + link cache (HOLON_MORPH/HOLON_LINK_CACHE)")

    def _extract(self, out):
        subprocess.run(
            ["python3", "-m", "holon.frontends.link", "extract",
             "--cache", str(CACHE), "--morph", str(_util.MORPH), "--out", str(out)],
            cwd=_util.REPO, check=True, capture_output=True, timeout=600)

    def test_extract_is_byte_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self._extract(a)
            self._extract(b)
            for rel in ("spec/M2/extracted/links.json",
                        "spec/M2/extracted/migrations.json",
                        "spec/M2/coverage/link.json",
                        "spec/M2/manifests/link.json"):
                fa, fb = Path(a) / rel, Path(b) / rel
                self.assertTrue(fa.exists() and fb.exists(), rel)
                self.assertEqual(fa.read_bytes(), fb.read_bytes(), rel)

    def test_extract_matches_committed(self):
        with tempfile.TemporaryDirectory() as a:
            self._extract(a)
            for rel in ("spec/M2/extracted/links.json",
                        "spec/M2/extracted/migrations.json",
                        "spec/M2/coverage/link.json",
                        "spec/M2/manifests/link.json"):
                got = (Path(a) / rel).read_bytes()
                want = (_util.REPO / rel).read_bytes()
                self.assertEqual(got, want, f"{rel} drifted — re-run extract and commit")


if __name__ == "__main__":
    unittest.main()
