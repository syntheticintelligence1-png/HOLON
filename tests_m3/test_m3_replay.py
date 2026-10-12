"""M3: replay the messenger model findings (O29/O34) on the pinned Morph contracts.

Builds a scratch Foundry project from $HOLON_MORPH_DIR/contracts (default ~/ext/morph,
must be at 3e44e79), drops replay/M3/solidity/HolonMsgReplay.t.sol into it, and runs
`forge test --match-contract HolonMsgReplay`. Skips cleanly when forge, npm, the morph
checkout or the solc binary is absent.
"""
import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MORPH = Path(os.environ.get("HOLON_MORPH_DIR", Path.home() / "ext" / "morph"))
SOLC = os.environ.get("HOLON_SOLC", str(Path.home() / ".local/share/svm/0.8.24/solc-0.8.24"))
WORK = Path(os.environ.get("HOLON_M3_WORK", Path.home() / "scratch" / "m3msg"))
LINE = re.compile(r"HOLON (\w+) (\d+) (\S+) ?(.*)")


def _available() -> bool:
    if not shutil.which("forge") and not (Path.home() / ".foundry/bin/forge").exists():
        return False
    if not shutil.which("npm"):
        return False
    if not (MORPH / "contracts" / "contracts" / "l1" / "L1CrossDomainMessenger.sol").exists():
        return False
    if not Path(SOLC).exists():
        return False
    try:
        out = subprocess.run(["git", "-C", str(MORPH), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=30)
        return out.stdout.strip().startswith("3e44e79")
    except Exception:
        return False


def _project() -> Path:
    from holon.replay import _sol_deps  # same dep provisioning as M0/M1 replay
    proj = WORK / "solidity"
    proj.mkdir(parents=True, exist_ok=True)
    if not (proj / "contracts").exists():
        shutil.copytree(MORPH / "contracts" / "contracts", proj / "contracts")
        for d in ("mock", "test"):
            shutil.rmtree(proj / "contracts" / d, ignore_errors=True)
        for f in ("foundry.toml", "remappings.txt"):
            shutil.copy(MORPH / "contracts" / f, proj / f)
    _sol_deps(proj)
    (proj / "test").mkdir(exist_ok=True)
    for t in ("HolonMsgReplay.t.sol", "HolonNatReplay.t.sol"):
        shutil.copy(ROOT / "replay" / "M3" / "solidity" / t, proj / "test")
    return proj


class _ForgeRun(unittest.TestCase):
    contract = None
    report = None

    @classmethod
    def setUpClass(cls):
        proj = _project()
        forge = shutil.which("forge") or str(Path.home() / ".foundry/bin/forge")
        cls.cmd = [forge, "test", "--match-contract", cls.contract, "-vv", "--offline",
                   "--use", SOLC]
        cls.res = subprocess.run(cls.cmd, cwd=proj, capture_output=True, text=True, timeout=3600)
        cls.lines = {}
        for m in LINE.finditer(cls.res.stdout):
            cls.lines[(m.group(1), int(m.group(2)))] = (m.group(3), m.group(4).strip())


@unittest.skipUnless(_available(), "needs forge + npm + morph @3e44e79 + solc-0.8.24")
class TestM3Replay(_ForgeRun):
    contract = "HolonMsgReplay"
    report = "msg_report.json"

    def test_forge_passed(self):
        self.assertEqual(self.res.returncode, 0, self.res.stdout[-3000:] + self.res.stderr[-1000:])
        self.assertIn("2 passed", self.res.stdout, self.res.stdout[-2000:])

    def test_budget_lines(self):
        l = self.lines  # (law, step) -> (label, outcome)
        self.assertEqual(l[("budget", 0)][1], "3", "default maxReplayTimes")
        self.assertEqual(l[("budget", 1)][1], "ok")
        for i in (2, 3, 4):
            self.assertEqual(l[("budget", i)][1], "ok", f"replay {i}")
        self.assertEqual(l[("budget", 5)][1], "Exceed maximum replay times")
        self.assertEqual(l[("budget", 9)][1], "ok", "replay after updateMaxReplayTimes(4)")

    def test_waiver_lines(self):
        l = self.lines
        self.assertEqual(l[("waiver", 1)][1], "ok feeVault=0")
        self.assertEqual(l[("waiver", 2)][1], "ok feeVault=0")
        self.assertEqual(l[("waiver", 3)][1], "ok")
        self.assertEqual(l[("waiver", 4)][1], "Insufficient msg.value for fee")

    def test_report_consistent(self):
        rep = json.loads((ROOT / "replay" / "M3" / self.report).read_text())
        self.assertTrue(rep["morph_commit"].startswith("3e44e79"))
        for lid in ("L_msg_budget_blocks_sender", "L_msg_waiver_follows_origin"):
            self.assertEqual(rep["laws"][lid]["verdict"], "agree")


@unittest.skipUnless(_available(), "needs forge + npm + morph @3e44e79 + solc-0.8.24")
class TestM3NatReplay(_ForgeRun):
    contract = "HolonNatReplay"
    report = "nat_report.json"

    def test_forge_passed(self):
        self.assertEqual(self.res.returncode, 0, self.res.stdout[-3000:] + self.res.stderr[-1000:])
        self.assertIn("2 passed", self.res.stdout, self.res.stdout[-2000:])

    def test_defend_lines(self):
        l = self.lines
        self.assertEqual(l[("defend", 1)][1], "only active submitter allowed")
        # control: past the submitter check, reverting inside the verifier
        self.assertEqual(l[("defend", 2)][1], "Invalid batch proof")

    def test_slash_lines(self):
        l = self.lines
        self.assertEqual(l[("slash", 1)][1], "ok")
        # challenger reward is deposit-only (0.1 ether): slash(Bob) is a no-op
        self.assertEqual(l[("slash", 2)][1], "100000000000000000")
        self.assertEqual(l[("slash", 3)][1], "ok")
        # native control: deposit + 1 ether * 50% = 0.6 ether
        self.assertEqual(l[("slash", 4)][1], "600000000000000000")
        self.assertEqual(l[("slash", 5)][1], "0")

    def test_report_consistent(self):
        rep = json.loads((ROOT / "replay" / "M3" / self.report).read_text())
        self.assertTrue(rep["morph_commit"].startswith("3e44e79"))
        for lid in ("L_nat_defend_legacy_blocked", "L_nat_slash_legacy_misses"):
            self.assertEqual(rep["laws"][lid]["verdict"], "agree")


if __name__ == "__main__":
    unittest.main()
