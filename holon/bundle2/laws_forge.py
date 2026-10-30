"""The forge side of Bundle II's laws (BUILD_PLAN row I84 = I37b; the contract is the docstring of
tests_m3/test_bundle2_laws.py, rules K2, D5, FP4 and LD5).

One scratch project holds I80's harness files (holon.bundle2.harness.HARNESS_FILES, unchanged) and I84's own
(LAWS_HARNESS: the laws' deployment base, the calibration harness, the law replays); it is built once, then each run is
one `forge test` of one test contract and function with an environment, whose stdout lines are kept by prefix. The
deployment's parameters come from I80's committed corpus (its init, [F, W, D, t0, r0]) and the router's versions from
I84's sidecar; nothing here names a target.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from . import BundleError, Ctx, Refused

LAWS_HARNESS = ["replay/M3/bundle2/laws/HolonBundle2LawsBase.sol",
                "replay/M3/bundle2/calibrate/HolonBundle2Calibrate.t.sol",
                "replay/M3/bundle2/laws/HolonBundle2LawReplay.t.sol"]
INIT_KEYS = ("F", "W", "D", "T0", "R0")


class Forge:
    """A built scratch project of the bundle's harnesses (I80's and I84's), and runs of it."""

    def __init__(self, bctx: Ctx, laws_side: dict, work: Path | None = None):
        import json
        from . import harness as H
        from ..replay_fragments import FragmentsError, forge_build, harness_project
        self.bctx = bctx
        self.side = laws_side
        self.tc = H._toolchain(bctx)
        b = H._binding(bctx)
        checkout = Path(bctx.source()).resolve()
        from ..replay import check_checkout
        try:
            check_checkout(checkout, bctx.side["target"]["head"])
        except SystemExit as e:
            raise Refused(str(e))
        files = list(H.HARNESS_FILES) + [f for f in LAWS_HARNESS if (bctx.root / f).is_file()]
        self.work = Path(work) if work else Path(tempfile.mkdtemp(prefix="holon-b2laws-"))
        try:
            self.proj = harness_project({"project": b["project"], "harness": {"files": files}}, self.work, bctx.root,
                                        checkout, self.tc)
            forge_build(self.proj, self.tc)
        except FragmentsError as e:
            raise BundleError(str(e))
        corpus = json.loads(bctx.path("corpus").read_text(encoding="utf-8"))
        init = corpus.get("init")
        if not (isinstance(init, list) and len(init) == len(INIT_KEYS)):
            raise Refused("the corpus has no init [F, W, D, t0, r0]")
        self.init = [int(x) for x in init]
        versions = ((laws_side.get("deployment") or {}).get("router") or {}).get("versions")
        if not versions:
            raise Refused("the laws sidecar names no router versions")
        self.versions = [int(v) for v in versions]

    def env(self, extra: dict) -> dict:
        e = dict(os.environ)
        for k, v in zip(INIT_KEYS, self.init):
            e[f"HOLON_INIT_{k}"] = str(v)
        e["HOLON_VERSIONS"] = ",".join(str(v) for v in self.versions)
        for k, v in extra.items():
            e[k] = str(v)
        return e

    def command(self, contract: str, test: str) -> list:
        return ["nice", "-n", "10", self.tc["forge"], "test", "--match-contract", f"^{contract}$", "--match-test",
                f"^{test}\\(\\)$", "--offline", "--use", self.tc["solc"], "-vv"]

    def start(self, contract: str, test: str, extra: dict) -> subprocess.Popen:
        return subprocess.Popen(self.command(contract, test), cwd=self.proj, env=self.env(extra),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    @staticmethod
    def lines(proc: subprocess.Popen, prefixes: tuple, what: str) -> list:
        out, _ = proc.communicate()
        if proc.returncode != 0:
            raise BundleError(f"forge {what} failed (exit {proc.returncode}): {(out or '')[-2500:]}")
        keep = []
        for ln in (out or "").splitlines():
            s = ln.strip()
            if s.startswith(prefixes):
                keep.append(s)
        return keep

    def run(self, contract: str, test: str, extra: dict, prefixes: tuple) -> list:
        return self.lines(self.start(contract, test, extra), prefixes, f"{contract}.{test} {extra}")

    def run_many(self, jobs: int, items: list, prefixes: tuple) -> list:
        """items: [(contract, test, extra)]; the kept lines of each, in item order, at most jobs runs at a time."""
        out: list = [None] * len(items)
        active: list = []
        for i, (c, t, x) in enumerate(items):
            while len(active) >= max(1, jobs):
                j, (cc, tt, xx), p = active.pop(0)
                out[j] = self.lines(p, prefixes, f"{cc}.{tt} {xx}")
            active.append((i, (c, t, x), self.start(c, t, x)))
        for j, (cc, tt, xx), p in active:
            out[j] = self.lines(p, prefixes, f"{cc}.{tt} {xx}")
        return out

    def toolchain(self) -> dict:
        """The pinned toolchain's hashes, as I80's records name them."""
        return {k: self.tc[k] for k in ("forge_sha256", "sol_deps_sha256", "solc_sha256") if k in self.tc}
