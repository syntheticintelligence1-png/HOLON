"""Protected files are byte-identical to the human-approved manifest."""
import subprocess
import sys
import unittest

from tests._util import ROOT


class TestFreeze(unittest.TestCase):
    def test_manifest_matches(self):
        p = subprocess.run([sys.executable, str(ROOT / "tools" / "freeze.py"), "check"],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, "Frozen files changed. Agents may not edit them; "
                         "stop and ask the human.\n" + p.stdout)


if __name__ == "__main__":
    unittest.main()
