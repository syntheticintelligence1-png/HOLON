"""The differential harness of the typed model's sort operations (I123; the contract is the docstring of
tests_m6/test_i123_typed_sort_operations.py). It runs only on planted fixtures written from the EVM and Solidity
semantics (tests_m6/fixtures/i123/sol), never on a target.

  cases() / pre_cases(contract)   the edge cases: (function, arguments, block.timestamp, the slot it stores)
  reference(case)                 the stored word by the EVM and Solidity rules (computed here, from the rules alone)
  Fixture(root, src, tmp)         the fixture extracted by the pinned solc its pragma selects (holon extract solidity),
                                  sorted (holon sorts) with and without the opt-in in a scratch root
    .model(contract, sort_ops)    the typed model's text (holon.sorts.model3.generate), or None with .errors[...]
    .real(contract, cases)        the stored words of the compiled code, run by the pinned forge (vm.load after calls)
    .differential(contract, cases, sort_ops)   the cases where the typed model's step (holon.sorts.evaluate3, the
                                  runner's evaluator) and the compiled code disagree (status or a stored word)
  bend_check(cases, values, work) the typed model's definitions of the cases' terms, checked as laws by Bend's
                                  evaluation (law dK: {code == value : W}, proof {==})
  false_laws() / true_laws()      planted laws over single cases: false under the EVM, true under it
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

MASK = (1 << 256) - 1
SIGN = 1 << 255
M = "T123"
XS = [0, 1, 2, SIGN - 1, SIGN, MASK - 1, MASK]
NS = [0, 1, 7, 8, 255, 256, 257, 300, MASK]
X8 = [0, 1, 0x7F, 0x80, 0xFF]
NS8 = [0, 1, 7, 8, 9, 255, 256]
TS = [0, 1, 0xFFFFFFFF, 1 << 32, (1 << 40) + 12345]
FILES = {"SortOps": "SortOps.sol", "RSdiv": "SortOps.sol", "RSmod": "SortOps.sol", "RAddmod": "SortOps.sol",
         "RMulmod": "SortOps.sol", "RSignext": "SortOps.sol", "RCheckedT": "SortOps.sol", "RSignSite": "SortOps.sol",
         "Pre05": "Pre05.sol", "PreVar05": "Pre05.sol", "Pre06": "Pre06.sol", "PreVar06": "Pre06.sol",
         "Pre07": "Pre07.sol", "PreVar07": "Pre07.sol"}


# ----------------------------------------------------------------------------------------------- the rules
def sgn(x: int) -> int:
    return x - (1 << 256) if x & SIGN else x


def shl(x: int, n: int) -> int:
    return (x << n) & MASK if n < 256 else 0


def shr(x: int, n: int) -> int:
    return x >> n if n < 256 else 0


def sar(x: int, n: int) -> int:
    return (sgn(x) >> min(n, 256)) & MASK


def s8(x: int) -> int:
    """an int8 value from its low byte, as a 256-bit two's complement word."""
    x &= 0xFF
    return (x - 256 if x & 0x80 else x) & MASK


def _c(i, fn, args, slot, ts=None, op=None, term=None):
    return {"id": f"{fn}#{i}", "fn": fn, "args": args, "slot": slot, "ts": ts, "op": op, "term": term}


def cases() -> list[dict]:
    out = []
    i = 0
    for x in XS:
        for n in NS:
            for fn, op in (("shlV", "<<"), ("shrV", ">>"), ("sarV", "sar"), ("shlY", "<<"), ("shrY", ">>"),
                           ("sarY", "sar")):
                i += 1
                out.append(_c(i, fn, [x, n], 1 if fn == "sarV" else 0, op=op, term=[op, x, n]))
        for fn, op, n in (("shlC", "<<", 255), ("shrC", ">>", 255), ("sarC", "sar", 7), ("sarYC", "sar", 300)):
            i += 1
            out.append(_c(i, fn, [x], 1 if fn == "sarC" else 0, op=op, term=[op, x, n]))
    for x in X8:
        for n in NS8:
            for fn in ("shl8", "shr8", "sar8", "shlS8"):
                i += 1
                term = {"shl8": ["trunc", 8, ["<<", x, n]], "shr8": [">>", x, n], "sar8": ["sar", s8(x), n],
                        "shlS8": ["sext", 8, ["<<", s8(x), n]]}[fn]
                out.append(_c(i, fn, [x, n], 1 if fn in ("sar8", "shlS8") else 0, op=fn, term=term))
    for ts in TS:
        for k in (0, 1, 0xFF00FF, MASK):
            for fn in ("xorT", "orT"):
                i += 1
                out.append(_c(i, fn, [k], 0, ts=ts, op=fn, term=["^" if fn == "xorT" else "|", ts, k]))
        for lo in (0, 1, (1 << 64) - 1):
            i += 1
            out.append(_c(i, "packT", [lo], 0, ts=ts, op="packT", term=["|", ["<<", ts, 64], lo]))
        for n in (0, 1, 32, 255, 256):
            i += 1
            out.append(_c(i, "shrT", [n], 0, ts=ts, op=">>", term=[">>", ts, n]))
        for fn in ("maskT", "notT", "uncheckedT"):
            i += 1
            term = {"maskT": ["&", ts, 0xFFFFFFFF], "notT": ["~", ts], "uncheckedT": ["+", ts, ts],
                    "uncheckedSubT": ["-", ["-", ts, ts], ts]}[fn]
            out.append(_c(i, fn, [], 0, ts=ts, op=fn, term=term))
    return out


def pre_cases(contract: str) -> list[dict]:
    out = []
    i = 0
    for x in XS:
        for fn, slot in (("shlC", 0), ("shrC", 0), ("sarC", 1)) + ((("sarYC", 0),) if contract != "Pre05" else ()):
            i += 1
            out.append(_c(i, fn, [x], slot, op=fn))
    for x in X8:
        i += 1
        out.append(_c(i, "shl8C", [x], 0, op="shl8C"))
    return out


def reference(c: dict) -> int:
    fn, a, ts = c["fn"], c["args"], c.get("ts")
    if fn in ("shlV", "shlY"):
        return shl(a[0], a[1])
    if fn in ("shrV", "shrY"):
        return shr(a[0], a[1])
    if fn in ("sarV", "sarY"):
        return sar(a[0], a[1])
    if fn == "shlC":
        return shl(a[0], 200 if c.get("pre") else 255)
    if fn == "shrC":
        return shr(a[0], 3 if c.get("pre") else 255)
    if fn == "sarC":
        return sar(a[0], 3 if c.get("pre") else 7)
    if fn == "sarYC":
        return sar(a[0], 260 if c.get("pre") else 300)
    if fn == "shl8C":
        return shl(a[0], 3) & 0xFF
    if fn == "shl8":
        return shl(a[0], a[1]) & 0xFF
    if fn == "shr8":
        return shr(a[0] & 0xFF, a[1])
    if fn == "sar8":
        return sar(s8(a[0]), a[1])
    if fn == "shlS8":
        return s8(shl(s8(a[0]), a[1]))
    if fn == "xorT":
        return ts ^ a[0]
    if fn == "orT":
        return ts | a[0]
    if fn == "packT":
        return shl(ts, 64) | a[0]
    if fn == "shrT":
        return shr(ts, a[0])
    if fn == "maskT":
        return ts & 0xFFFFFFFF
    if fn == "notT":
        return MASK ^ ts
    if fn == "uncheckedT":
        return (ts + ts) & MASK
    if fn == "uncheckedSubT":
        return (ts - ts - ts) & MASK
    raise ValueError(fn)


def args_of(c: dict) -> list:
    """The call's ABI arguments (an int8 argument as its signed value)."""
    if c["fn"] in ("sarV", "sarC"):
        return [sgn(c["args"][0])] + c["args"][1:]
    if c["fn"] in ("sar8", "shlS8"):
        return [sgn(s8(c["args"][0]))] + c["args"][1:]
    return list(c["args"])


# ----------------------------------------------------------------------------------------------- the fixture
def _gitify(src: Path) -> str:
    e = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
         "GIT_COMMITTER_EMAIL": "t@t"}
    for a in (["init", "-q"], ["add", "."], ["commit", "-qm", "fixture"]):
        subprocess.run(["git", "-C", str(src), *a], check=True, capture_output=True, env=e)
    return subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True).stdout.strip()


class Fixture:
    def __init__(self, root: Path, fix: Path, tmp: Path, proto_name: str = "spec/M6/lib/i123_run.json"):
        from ..eval import common
        from ..eval import holon_run as H
        self.root, self.fix, self.tmp = Path(root), Path(fix), Path(tmp)
        self.src = self.tmp / "src"
        shutil.copytree(self.fix, self.src)
        self.head = _gitify(self.src)
        self.proto = json.loads(json.dumps(common.load_json(self.root / proto_name)))
        self.S = H.scratch_root(self.root, self.tmp, "holon/i123", self.src)
        self.rel = "results/eval/holon/i123"
        for d in ("sidecars", "facts"):
            (self.S / self.rel / d).mkdir(parents=True, exist_ok=True)
        self.R = H.Runner(H.Ctx(self.tmp, self.src), self.S, self.proto, {})
        self.docs: dict = {}
        self.errors: dict = {}
        self.models: dict = {}
        self._real: dict = {}
        self._sorted: dict = {}

    # -- extraction and sorts
    def doc(self, n: str) -> str:
        """The repo-relative (scratch) path of contract n's transitions document."""
        if n not in self.docs:
            side = {"sidecar_version": 1, "frontend": "solidity", "doc": "I123 planted fixture",
                    "target": {"repo": "holon/i123", "commit": self.head, "scope": f"contract {n}"},
                    "output": f"{self.rel}/facts/{n}.extracted.json", "sources": [FILES[n]],
                    "compiler": {"version": "pragma", "settings": {"optimizer": {"enabled": False}}},
                    "transitions": {"commit_interfaces": [], "contract": n}}
            sp = self.S / self.rel / "sidecars" / f"extract_{n}.json"
            sp.write_text(json.dumps(side, indent=1, sort_keys=True) + "\n")
            out = self.S / self.rel / "facts" / f"{n}.extracted.json"
            r = self.R.holon("extract", ["extract", "solidity", "--root", str(self.S), "--sidecar", str(sp),
                                         "--source", str(self.src), "--out", str(out)])
            if r["status"] != "ok":
                raise RuntimeError(f"extract {n}: {r['detail'][-2000:]}")
            self.docs[n] = f"{self.rel}/facts/{n}.extracted.json"
        return self.docs[n]

    def selected(self, n: str) -> str:
        d = json.loads((self.S / self.doc(n)).read_text(encoding="utf-8"))
        return d["extraction"]["toolchain"]["solc"]["version"].split("+")[0]

    def sidecar(self, n: str, sort_ops: bool) -> str:
        """The typed sidecar of contract n alone (with or without the opt-in), and its sort pass run."""
        key = (n, sort_ops)
        if key not in self._sorted:
            name = f"sort_types_{n}_{'w' if sort_ops else 'b'}"
            ty = self.proto["typed"]
            side = {"sort_types_version": ty["sort_types_version"], "doc": "I123 planted fixture",
                    "documents": [self.doc(n)], "seeds": ty["seeds"], "binding": None, "search": ty["search"],
                    **({"sort_ops": "word"} if sort_ops else {})}
            sp = self.S / self.rel / "sidecars" / f"{name}.json"
            sp.write_text(json.dumps(side, indent=1, sort_keys=True) + "\n")
            out = self.S / "gen" / f"{M}_{name}" / "sorts"
            r = self.R.holon("sorts", ["sorts", "--milestone", M, "--root", str(self.S), "--sidecar", str(sp),
                                       "--out", str(out)])
            if r["status"] != "ok":
                raise RuntimeError(f"sorts {n}: {r['detail'][-2000:]}")
            self._sorted[key] = (str(sp), out / "assignment.json")
        return self._sorted[key][0]

    # -- the compiled code (the pinned solc the file's pragma selects, run by the pinned forge)
    def real(self, n: str, cs: list[dict]) -> dict:
        key = (n, tuple(c["id"] for c in cs))
        if key not in self._real:
            r = run_real(self.fix, n, cs, self.selected(n), self.tmp, self.root)
            self._real[key] = r
        return {k: (v[1] if v[0] else None) for k, v in self._real[key].items()}

    def real_status(self, n: str, cs: list[dict]) -> dict:
        self.real(n, cs)
        return self._real[(n, tuple(c["id"] for c in cs))]

    def real_one(self, law: dict) -> int | None:
        """The compiled code's stored word at a planted law's case (every planted law's case in one forge run)."""
        cs = [lw["case"] for lw in false_laws()]
        if law["case"]["id"] not in {c["id"] for c in cs}:
            cs = [law["case"]]
        return self.real(law.get("contract", "SortOps"), cs)[law["case"]["id"]]

    # -- the typed model's steps (holon.sorts.evaluate3, the runner's evaluator) against the compiled code
    def evaluator(self, n: str, sort_ops: bool):
        from . import evaluate3
        from ..machine import load_extracted
        text = self.model(n, sort_ops)
        if text is None:
            return None
        mp = self.tmp / f"model_{n}_{'w' if sort_ops else 'b'}.bend"
        mp.write_text(text, encoding="utf-8")
        return evaluate3.Evaluator.build(mp, load_extracted(self.S / self.doc(n), self.S))

    def differential(self, n: str, cs: list[dict], sort_ops: bool = True) -> list:
        ev = self.evaluator(n, sort_ops)
        if ev is None:
            return [("no model", self.errors.get((n, sort_ops)))]
        real = self.real_status(n, cs)
        bad = []
        try:
            for c in cs:
                params = [p["name"] for p in ev.doc.params(c["fn"]) or []]
                ts = c.get("ts")
                state = {"0x" + "%064x" % 2: "0x%064x" % ts} if ts else {}
                env = env_of(c, 1 if ts is None else ts)
                out = ev.step(state, c["fn"], dict(zip(params, args_of(c))), env)
                ok = out.get("status") == "ok"
                slot = "0x%064x" % c["slot"]
                w = int((out.get("writes") or {}).get(slot, state.get(slot, "0x0")), 16) if ok else None
                rok, rw = real[c["id"]]
                if ok != rok or (ok and w != rw):
                    bad.append((c["id"], out.get("status"), None if w is None else hex(w), rok, hex(rw),
                                out.get("reason")))
        finally:
            ev.close()
        return bad

    def model_pre_i123(self, n: str) -> str | None:
        """Contract n's typed model by the generator before I123 (the holon/ tree of the parent of I123's prereg
        commit, from git), over the same document, sidecar (without the opt-in) and assignment."""
        pre = pre_i123_tree(self.root, self.tmp)
        sp = self.sidecar(n, False)
        out = self.tmp / f"pre_{n}.bend"
        code = ("import json, sys\nfrom pathlib import Path\nfrom holon.sorts import model3\n"
                "a = json.loads(Path(sys.argv[4]).read_text())\n"
                "try:\n    t, _mm = model3.generate(sys.argv[1], Path(sys.argv[2]), sys.argv[3], sidecar=sys.argv[5], "
                "assignment=a)\nexcept model3.GenError as e:\n    t = None\n"
                "Path(sys.argv[6]).write_text(json.dumps(t))\n")
        p = subprocess.run(["python3", "-c", code, M, str(self.S), self.doc(n), str(self._sorted[(n, False)][1]), sp,
                            str(out)], cwd=pre, env={**os.environ, "PYTHONPATH": str(pre)}, capture_output=True,
                           text=True, timeout=1800)
        if p.returncode != 0:
            raise RuntimeError(p.stderr[-2000:])
        return json.loads(out.read_text(encoding="utf-8"))

    def typed_runner(self, names: tuple, proto_name: str) -> dict:
        """The composed route's typed part (holon.eval.holon_run: roles installed, then _rules with route C, the run
        step included) over the named contracts in a fresh scratch root, with the protocol's own keys. Returns
        {"laws": {law id: status or None}, "documents": {law id: its document}, "stages": {stage: status}}."""
        from ..eval import common
        from ..eval import holon_run as H
        proto = json.loads(json.dumps(common.load_json(self.root / proto_name)))
        t = self.tmp / f"runner_{len(list(self.tmp.glob('runner_*')))}"
        t.mkdir()
        S = H.scratch_root(self.root, t, "holon/i123", self.src)
        rel = self.rel
        for d in ("sidecars", "facts"):
            (S / rel / d).mkdir(parents=True, exist_ok=True)
        R = H.Runner(H.Ctx(t, self.src), S, proto, {})
        files = []
        for n in names:
            shutil.copy(self.S / self.doc(n), S / rel / "facts" / f"{n}.extracted.json")
            shutil.copy(self.S / rel / "sidecars" / f"extract_{n}.json", S / rel / "sidecars" / f"extract_{n}.json")
            files.append(f"{n}.extracted.json")
        Mx = proto["milestone"]
        stages: dict = {}
        rels = [f"{rel}/facts/{f}" for f in files]
        stages["roles"] = R.holon("roles", ["roles", "--milestone", Mx, "--root", str(S), "--documents", ",".join(rels),
                                            "--out-dir", str(S / rel / "sidecars" / "roles"), "--mode", "static",
                                            "--install", "--roles", "hand"])
        lib = S / "spec" / Mx / "lib"
        H._rules(R, S, rel, Mx, proto, [{"file": f} for f in files], stages, lambda: H._route_c(R, S, Mx, lib, stages))
        laws, docs = {}, {}
        for lp in sorted((S / "laws" / Mx).glob("L_*.json")):
            lw = json.loads(lp.read_text(encoding="utf-8"))
            facts = lw.get("facts") or ""
            docs[lp.stem] = facts if isinstance(facts, str) else json.dumps(facts)
            rp = S / "results" / Mx / lp.name
            laws[lp.stem] = json.loads(rp.read_text(encoding="utf-8")).get("status") if rp.is_file() else None
        return {"laws": laws, "documents": docs,
                "stages": {k: v.get("status") if isinstance(v, dict) else v for k, v in stages.items()}}

    def section_shift(self, n: str, sort_ops: bool) -> tuple[bool, str]:
        """D1: a section over contract n's typed model compiling a term with a constant shift the model does not
        define (holon.undo.trace.Trace.compile_word); (Bend checks the section, its output)."""
        return _section_probe(self, n, sort_ops)

    def model(self, n: str, sort_ops: bool):
        key = (n, sort_ops)
        if key not in self.models:
            from . import model3
            sp = self.sidecar(n, sort_ops)
            assignment = json.loads(self._sorted[key][1].read_text(encoding="utf-8"))
            try:
                text, mm = model3.generate(M, self.S, self.doc(n), sidecar=sp, assignment=assignment)
                self.models[key] = (text, mm)
            except model3.GenError as e:
                self.models[key] = None
                self.errors[key] = f"GenError: {e}"
        m = self.models[key]
        return m[0] if m else None


# ----------------------------------------------------------------------------------------------- Bend's evaluation
class _Doc:
    """The least document model3's term compiler reads (a release of 0.8.0 or later: R1 does not apply)."""

    def __init__(self, version: str = "0.8.24"):
        self.doc = {"extraction": {"frontend": "solidity", "toolchain": {"solc": {"version": version}}}}


VAR_FNS = ("shlV", "shrV", "sarV", "shlY", "shrY", "sarY", "shl8", "shr8", "sar8", "shlS8", "shrT")


def model_term(c: dict):
    """The case's term with a variable amount where the function's amount is a parameter (["|", n, 0] is a non-literal
    term of value n, so the compiler takes its variable-amount path)."""
    t = c["term"]
    if c["fn"] not in VAR_FNS:
        return t

    def var(u):
        if isinstance(u, list) and u and u[0] in ("<<", ">>", "sar") and isinstance(u[2], int):
            return [u[0], u[1], ["|", u[2], 0]]
        if isinstance(u, list):
            return [var(x) if isinstance(x, list) else x for x in u]
        return u
    return var(t)


def check_text(cs: list[dict], values: list[int]) -> tuple[int, str]:
    """(laws, the Bend module): the prelude, the definitions the terms need (model3's own shifts and helpers) and one
    law per case, {code == value : W}, each proved by {==} (Bend's own evaluation)."""
    from . import model3
    from .model3 import Gen, Scope, wlit
    g = Gen(_Doc(), typed=False)
    g.sort_ops = True
    laws = []
    for i, (c, v) in enumerate(zip(cs, values)):
        code = g.w(model_term(c), Scope("diff"))
        laws.append(f"law d{i}:\n  {{{code} == {wlit(v)} : W}}\n\ndef d{i}():\n  {{==}}\n")
    parts = ["# GENERATED by holon.sorts.sortops_diff (I123's check of the typed model's definitions).", "import Base",
             model3.prelude("raw"), *g.shift_defs(), *laws]
    return len(laws), "\n".join(x.rstrip("\n") + "\n" for x in parts)


def bend_check(cs: list[dict], values: list[int], work: Path) -> tuple[int, dict]:
    from .. import bend
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    cs2 = [(c, v) for c, v in zip(cs, values) if c.get("term") is not None]
    n, text = check_text([c for c, _ in cs2], [v for _, v in cs2])
    (work / "k.bend").write_text(text, encoding="utf-8")
    r = bend.run(["k.bend"], cwd=work, timeout=3600)
    return n, {"code": r.code, "text": r.out}


# ----------------------------------------------------------------------------------------------- the compiled code
SIGS = {"shlV": "uint256,uint256", "shrV": "uint256,uint256", "shlC": "uint256", "shrC": "uint256",
        "sarV": "int256,uint256", "sarC": "int256", "shlY": "uint256,uint256", "shrY": "uint256,uint256",
        "sarY": "uint256,uint256", "sarYC": "uint256", "shl8": "uint8,uint256", "shr8": "uint8,uint256",
        "sar8": "int8,uint256", "shlS8": "int8,uint256", "packT": "uint64", "maskT": "", "xorT": "uint256",
        "notT": "", "orT": "uint256", "shrT": "uint256", "uncheckedT": "", "shl8C": "uint8"}
VM = "0x7109709ECfa91a80626fF3989D68f67F5b1DD12D"


def calldata(c: dict) -> bytes:
    from ..keccak import keccak256
    sel = keccak256(f"{c['fn']}({SIGS[c['fn']]})".encode())[:4]
    return sel + b"".join((a & MASK).to_bytes(32, "big") for a in args_of(c))


def harness(contract: str, cs: list[dict], pragma: str) -> str:
    lines = [f"pragma solidity {pragma};", f'import "../src/{FILES[contract]}";', "",
             "interface Vm {", "    function warp(uint256) external;",
             "    function store(address, bytes32, bytes32) external;",
             "    function load(address, bytes32) external returns (bytes32);", "}", "",
             "contract Diff {", "    event log_named_bytes32(string key, bytes32 val);",
             f"    Vm constant vm = Vm({VM});", ""]
    for k in range(0, len(cs), 40):
        lines += [f"    function test_chunk_{k // 40:03d}() public {{", f"        {contract} t = new {contract}();",
                  "        bool ok;", "        bytes32 w;"]
        for c in cs[k:k + 40]:
            ts = c.get("ts")
            lines += ["        vm.store(address(t), bytes32(uint256(0)), bytes32(0));",
                      "        vm.store(address(t), bytes32(uint256(1)), bytes32(0));",
                      f"        vm.store(address(t), bytes32(uint256(2)), bytes32(uint256({ts or 0})));",
                      f"        vm.warp({1 if ts is None else ts});",
                      f"        (ok, ) = address(t).call(hex\"{calldata(c).hex()}\");",
                      f"        w = vm.load(address(t), bytes32(uint256({c['slot']})));",
                      f"        emit log_named_bytes32(\"{c['id']}\", ok ? w : bytes32(uint256(0xdead)));",
                      f"        emit log_named_bytes32(\"{c['id']}#ok\", ok ? bytes32(uint256(1)) : bytes32(0));"]
        lines += ["    }", ""]
    lines.append("}")
    return "\n".join(lines) + "\n"


def run_real(fix: Path, contract: str, cs: list[dict], version: str, work: Path, root: Path) -> dict:
    """{case id: (ok, stored word)} of the compiled code: the pinned forge, the fixture compiled by solc `version`."""
    from ..replay import replay_config
    rc = replay_config(root)
    sets = json.loads((Path(root) / "config" / "toolchains.json").read_text(encoding="utf-8"))["solc_set"]
    solc = Path(sets["dir"]) / f"solc-{version}"
    got = hashlib.sha256(solc.read_bytes()).hexdigest()
    if got != sets["releases"][version]:
        raise RuntimeError(f"{solc}: sha256 {got} is not the pinned {sets['releases'][version]}")
    proj = Path(work) / f"forge_{contract}"
    if proj.exists():
        shutil.rmtree(proj)
    (proj / "src").mkdir(parents=True)
    (proj / "test").mkdir()
    shutil.copy(Path(fix) / FILES[contract], proj / "src" / FILES[contract])
    (proj / "test" / "Diff.t.sol").write_text(harness(contract, cs, version), encoding="utf-8")
    (proj / "foundry.toml").write_text(f'[profile.default]\nsrc = "src"\ntest = "test"\nout = "out"\nlibs = []\n'
                                       f'solc = "{solc}"\noffline = true\noptimizer = false\n'
                                       f'gas_limit = "18446744073709551615"\n', encoding="utf-8")
    p = subprocess.run([rc["forge"], "test", "-vv", "--offline"], cwd=proj, capture_output=True, text=True,
                       timeout=3600, env={**os.environ, "FOUNDRY_DISABLE_NIGHTLY_WARNING": "1"})
    out: dict = {}
    for m in re.finditer(r"^\s+(\S+#\d+(?:#ok)?): (0x[0-9a-f]{64})\s*$", p.stdout, re.M):
        out[m.group(1)] = int(m.group(2), 16)
    res = {}
    for c in cs:
        if c["id"] not in out or c["id"] + "#ok" not in out:
            raise RuntimeError(f"forge gave no result for {c['id']}: {p.stdout[-2000:]}{p.stderr[-2000:]}")
        res[c["id"]] = (bool(out[c["id"] + "#ok"]), out[c["id"]])
    return res


def env_of(c: dict, ts: int) -> dict:
    """A step's environment (holon.replay_fragments's A/B interface), the harness's own values."""
    z = "0x" + "00" * 20
    return {"caller": "0x" + "10" * 20, "this": "0x" + "20" * 20, "msg.value": 0,
            "msg.data.length": len(calldata(c)), "block.timestamp": ts, "block.number": 1, "block.chainid": 31337,
            "block.basefee": 0, "block.prevrandao": 0, "block.coinbase": z, "block.gaslimit": 30000000,
            "block.blobbasefee": 1, "tx.origin": "0x" + "10" * 20, "tx.gasprice": 0, "blobhash": [], "calls": [],
            "balance": {}, "code": {}}


# ----------------------------------------------------------------------------------------------- planted laws
def _law_case(i: int, fn: str, args: list, slot: int, ts=None) -> dict:
    c = _c(1000 + i, fn, args, slot, ts=ts)
    for x in cases():
        if x["fn"] == fn and x["args"] == args and x.get("ts") == ts:
            c["term"] = x["term"]
            break
    if c["term"] is None and fn == "uncheckedT":
        c["term"] = ["+", ts, ts]
    if c["term"] is None and fn == "shlV":
        c["term"] = ["<<", args[0], args[1]]
    return c


BIG_TS = SIGN + 1


def _laws():
    """(id, case, the value a false reading claims): each false only if the EVM's rule did not hold."""
    return [("shl_256_keeps", _law_case(1, "shlV", [1, 256], 0), 1),
            ("shr_300_mod_256", _law_case(2, "shrV", [MASK, 300], 0), MASK >> 44),
            ("sar_past_255_negative_zero", _law_case(3, "sarV", [MASK, 256], 1), 0),
            ("sar_is_logical", _law_case(4, "sarY", [SIGN, 1], 0), SIGN >> 1),
            ("mask_keeps_high_bits", _law_case(5, "maskT", [], 0, ts=(1 << 40) + 12345), (1 << 40) + 12345),
            ("int8_shl_not_truncated", _law_case(6, "shlS8", [0x7F, 1], 1), 0xFE),
            ("unchecked_time_sum_saturates", _law_case(7, "uncheckedT", [], 0, ts=BIG_TS), MASK)]


def false_laws() -> list[dict]:
    return [{"id": i, "case": c, "claimed": v, "contract": "SortOps"} for i, c, v in _laws()]


def true_laws() -> list[dict]:
    return [{"id": i, "case": c, "claimed": reference(c), "contract": "SortOps"} for i, c, _v in _laws()]


# ----------------------------------------------------------------------------------------------- D1 sections
PROBE_SHIFT = 77    # a constant shift no fixture function uses


def _section_probe(fx, n: str, sort_ops: bool) -> tuple[bool, str]:
    from .. import bend
    from ..undo.trace import Trace
    from .model3 import GenError
    text = fx.model(n, sort_ops)
    if text is None:
        return False, fx.errors.get((n, sort_ops), "")
    _t, mm = fx.models[(n, sort_ops)]
    doc = json.loads((fx.S / fx.doc(n)).read_text(encoding="utf-8"))
    a = sorted(x["name"] for x in doc["actions"] if (mm.m.params(x["name"]) or []))[0]
    p = mm.m.params(a)[0]["name"]
    if f"w_shl_{PROBE_SHIFT}" in text:
        return False, f"the model already defines w_shl_{PROBE_SHIFT}"
    tr = Trace(mm, text, doc, mm.hashes, [])
    try:
        w = tr.compile_word(a, ["<<", ["param", p], PROBE_SHIFT])
    except GenError as e:
        return False, f"GenError: {e}"
    work = fx.tmp / f"section_{n}_{int(sort_ops)}"
    work.mkdir(parents=True, exist_ok=True)
    (work / "model.bend").write_text(text, encoding="utf-8")
    sec = ["import Base", "import ./model.bend as M", "", *tr.defs,
           f"def probe(+x: M.{mm.xt(a)}) -> M.W:\n  {w}\n"]
    (work / "section.bend").write_text("\n".join(x.rstrip("\n") + "\n" for x in sec), encoding="utf-8")
    r = bend.run(["section.bend"], cwd=work, timeout=1800)
    return r.code == 0, r.out


def pre_i123_commit(root: Path) -> str:
    """The parent of I123's prereg commit (the generator before I123)."""
    p = subprocess.run(["git", "-C", str(root), "log", "--format=%H", "--grep=^I123 prereg:"], capture_output=True,
                       text=True, check=True)
    hs = p.stdout.split()
    if not hs:
        raise RuntimeError("no I123 prereg commit in the history")
    return subprocess.run(["git", "-C", str(root), "rev-parse", hs[-1] + "^"], capture_output=True, text=True,
                          check=True).stdout.strip()


def pre_i123_tree(root: Path, tmp: Path) -> Path:
    d = Path(tmp) / "pre_i123"
    if not (d / "holon").is_dir():
        d.mkdir(parents=True, exist_ok=True)
        c = pre_i123_commit(root)
        a = subprocess.run(["git", "-C", str(root), "archive", c, "holon"], capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", str(d)], input=a, check=True)
    return d


def morph_models_changed(root: Path) -> int:
    """Morph's committed typed models (gen/M3/sorts/models/*.bend) that the generator, without the opt-in (no Morph
    sidecar names sort_ops), would now write differently: each regenerated over the committed assignment."""
    from . import model3
    from .typed_sidecar import load
    root = Path(root)
    sc = load("M3", root)
    if sc.sort_ops is not None:
        raise RuntimeError("Morph's sidecar names sort_ops")
    assignment = json.loads((root / "gen" / "M3" / "sorts" / "assignment.json").read_text(encoding="utf-8"))
    n = 0
    seen = 0
    for doc in model3.documents_of("M3", root, None):
        mp = root / "gen" / "M3" / "sorts" / "models" / f"{model3.model_name(doc)}.bend"
        if not mp.is_file():
            continue
        seen += 1
        text, _mm = model3.generate("M3", root, doc, init=model3.init_of("M3", root, None, doc), assignment=assignment)
        n += text != mp.read_text(encoding="utf-8")
    if not seen:
        raise RuntimeError("no committed typed model of Morph found")
    return n
