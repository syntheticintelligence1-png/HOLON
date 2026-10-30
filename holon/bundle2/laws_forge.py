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

    # ------------------------------------------------------------------ concrete traces (the law replay harness)
    def traces(self, traces: list, jobs: int = 2, tag: str = "laws") -> list:
        """Each trace (a list of concrete calls {"to": 1 (member 0) | 2 (member 1), "caller", "value", "timestamp",
        "data", "blobs"}) through the law replay harness from a fresh laws' deployment each; the parsed runs
        (holon.bundle2.harness.B2Run), in trace order. A trace with no call records the deployment alone."""
        import json
        from . import harness as H
        datas: list = []
        index: dict = {}
        rows_of = []
        for t in traces:
            rows = []
            for c in t:
                d = str(c["data"]).lower()
                if d not in index:
                    index[d] = len(datas)
                    datas.append(d)
                blobs = [int(b, 16) if isinstance(b, str) else int(b) for b in c.get("blobs") or []]
                caller = int(c["caller"], 16) if isinstance(c["caller"], str) else int(c["caller"])
                rows.append([100, caller, int(c.get("value") or 0), int(c.get("timestamp") or 0), int(c["to"]),
                             index[d], len(blobs)] + blobs)
            rows_of.append(rows)
        parts = [(i, i + 1) for i in range(len(rows_of))]
        runs: list = [None] * len(rows_of)
        pending = []
        for k, (a, b) in enumerate(parts):
            fin, fout = self.proj / f"holon_b2l_{tag}_{k}.json", self.proj / f"holon_b2l_{tag}_{k}.out"
            fin.write_text(json.dumps({"lens": [len(t) for t in rows_of[a:b]],
                                       "steps": [H._encode(r) for t in rows_of[a:b] for r in t],
                                       "slot_members": [], "slots": [], "init": [int(x) for x in self.init],
                                       "calldata": datas}))
            fout.unlink(missing_ok=True)
            env = self.env({"HOLON_STEPS_IN": fin.name, "HOLON_STEPS_OUT": fout.name, "HOLON_LO": 0,
                            "HOLON_HI": b - a})
            pending.append((k, a, b, fin, fout, env))
        active: list = []

        def finish(item, proc):
            k, a, b, fin, fout, _env = item
            out, _ = proc.communicate()
            text = fout.read_text() if fout.exists() else ""
            if proc.returncode != 0 or not text.rstrip().endswith(f"DONE 0 {b - a}"):
                raise BundleError(f"the law replay harness, trace {a} failed (exit {proc.returncode}): "
                                  f"{(out or '')[-2500:]}")
            for r in H.parse_output(text):
                r.tid += a
                for e in r.execs:
                    e.tid = r.tid
                runs[r.tid] = r
            fin.unlink(missing_ok=True)
            fout.unlink(missing_ok=True)

        for item in pending:
            while len(active) >= max(1, jobs):
                it, pr = active.pop(0)
                finish(it, pr)
            proc = subprocess.Popen(self.command("HolonBundle2LawReplayTest", "test_steps"), cwd=self.proj,
                                    env=item[5], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            active.append((item, proc))
        for it, pr in active:
            finish(it, pr)
        for i, r in enumerate(runs):
            if r is None or len([e for e in r.execs if e.id != "d"]) != len(rows_of[i]):
                raise BundleError(f"the law replay harness recorded no complete run for trace {i}")
        return runs

    def deployment(self) -> dict:
        """The laws' deployment as the harness records it: the members (in the declaration's order) with their
        addresses, storage (the deployment's surviving writes, non-zero words) and code (and an EIP-1967 proxy's
        implementation and its code), the accounts it created, the harness's address and the clock and chain."""
        probe = {"to": 1, "caller": "0x" + "%040x" % 0x1005, "value": 0, "timestamp": 0, "data": "0x", "blobs": []}
        run = self.traces([[probe]], jobs=1, tag="deploy")[0]
        d = next(e for e in run.execs if e.id == "d")
        call = next(e for e in run.execs if e.id != "d")
        from . import harness as H
        from ..replay_fragments import immutables_of
        storage: dict = {m: {} for m in run.members}
        for m, slot, val, rev in d.writes:
            if rev or m not in storage:
                continue
            storage[m][slot] = val
        members = []
        for (_i, mem, art), m in zip(H.member_layouts(self.bctx, self.proj), run.members):
            impl = run.impl.get(m)
            src = (impl[1] if impl else None) or run.code.get(m) or "0x"
            imm = {}
            for name, (start, n) in sorted(immutables_of(self.proj, art).items()):
                w = src[2 + 2 * start: 2 + 2 * (start + n)]
                if len(w) == 2 * n:
                    imm[name] = "0x" + w
            members.append({"name": mem["name"], "address": m, "code": run.code.get(m, "0x"),
                            "implementation": impl[0] if impl else None, "implementation_code": impl[1] if impl else None,
                            "immutables": imm,
                            "storage": {"0x%064x" % k: "0x%064x" % v for k, v in sorted(storage[m].items()) if v}})
        out = {"harness": run.harness, "members": members, "created": sorted(run.created),
               "timestamp": d.timestamp, "number": d.number, "chainid": int(call.env.get("block.chainid") or 0)}
        out["deploy_calls"] = self.deploy_calls()
        return out

    def deploy_calls(self) -> dict:
        """The deployment's calls into member 0 and its writes to member 0's storage, in access order (deploy3's
        capture form: calls [{entry, caller, value, data, reverted}], writes [[entry, slot, value, reverted]])."""
        calls, writes = [], []
        for ln in self.run("HolonBundle2LawReplayTest", "test_deploy_calls", {}, ("DC ", "DW ")):
            f = ln.split(" ")
            if f[0] == "DC":
                calls.append({"entry": int(f[1]), "caller": f[2].lower(), "value": int(f[3]), "reverted": f[4] == "1",
                              "data": f[5].lower()})
            else:
                writes.append([int(f[1]), "0x%064x" % int(f[2], 16), "0x%064x" % int(f[3], 16), f[4] == "1"])
        if not calls:
            raise BundleError("the deployment made no call into member 0")
        return {"calls": calls, "writes": writes}
