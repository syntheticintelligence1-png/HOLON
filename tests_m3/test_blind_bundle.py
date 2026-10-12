"""M3: the blind-rerun bundle must carry the G9 record/facts schemas.

tools/blind_bundle.py excludes spec/M2/ wholesale but keeps the three schema
files via its explicit include list. This test builds a bundle into a temp
dir and checks exactly that: the schemas are present and byte-identical,
nothing else under spec/M2/ is, and the laws/results exclusions still hold.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = (
    "spec/M2/schemas/result_v2.json",
    "spec/M2/schemas/go_codecs.schema.json",
    "spec/M2/schemas/go_machine.schema.json",
)


class TestBlindBundle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "bundle"
        self.addCleanup(self.tmp.cleanup)
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "blind_bundle.py"), str(self.out)],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_g9_schemas_included_byte_identical(self):
        for rel in SCHEMAS:
            bundled = self.out / rel
            self.assertTrue(bundled.is_file(), f"{rel} missing from bundle")
            self.assertEqual(bundled.read_bytes(), (ROOT / rel).read_bytes(), f"{rel} differs")

    def test_nothing_else_under_spec_m2(self):
        extra = [p for p in self.out.rglob("*")
                 if p.is_file() and p.relative_to(self.out).as_posix().startswith("spec/M2/")
                 and p.relative_to(self.out).as_posix() not in SCHEMAS]
        self.assertEqual(extra, [], f"unexpected spec/M2 files in bundle: {extra}")

    def test_findings_still_excluded(self):
        for prefix in ("laws/", "results/", "predictions/", "replay/", "facts/"):
            hits = [p for p in self.out.rglob("*")
                    if p.is_file() and p.relative_to(self.out).as_posix().startswith(prefix)]
            self.assertEqual(hits, [], f"{prefix} leaked into bundle: {hits[:3]}")
        manifest = self.out / "BLIND_MANIFEST.json"
        self.assertTrue(manifest.is_file())


if __name__ == "__main__":
    unittest.main()
