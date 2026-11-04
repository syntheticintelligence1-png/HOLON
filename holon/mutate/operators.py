"""The I61 catalog recomputed from the pinned checkout, and the diff sheet (holon.mutate.operators).

Contract: the docstring of tests_m2/test_mutation_adequacy_i61.py. Rules: the frozen instrument
spec/M2/lib/mutation_catalog_i61.json, computation items 2-8 and 10 and its fields operators, operator_order,
variant_order, cursor_pairs, strata, in_scope, stillborn, tce, roles, predicted and structural.

    catalog(instrument, checkout, sol_deps) -> [mutant]
        The scope (the I19 walker's reached set plus the header codec libraries; the Go strata), the sites of every
        operator (holon.mutate.sites), one mutant per site and variant in the instrument's order, the Solidity
        mutants compiled (tce) and the Go mutants built (stillborn ones dropped), and each mutant's edges, actions,
        predicted sets and structural class from the pinned artifacts (instrument pins). Equal to the instrument's
        "mutants" list. Every intermediate value the instrument records (in_scope, roles, the baseline's statuses,
        cones and entry points) is checked against the recomputation; a difference is a MutateError.
    stillborn(instrument, checkout, sol_deps) -> [stillborn mutant]   (the instrument's "stillborn" format)
    apply(mutant, data) -> bytes
    sources(instrument, checkout, sol_deps) -> {file: bytes}
    render_sheet(instrument, sources) -> str
    recompute(instrument, mutant, tree, sol_deps, holon_root) -> {"edges", "actions", "predicted": {"M0", "M1x", "M2"}}
    mutated_function_lines(instrument, mutant, tree, sol_deps) -> (unit, lo, hi) | None
    main(cmd, argv) -> exit code   (python -m holon mutate list | sheet)

The compile and build results are cached by mutant_sha256 under ~/.holon/cache/mutate/ (solc/, gobuild/): an entry
holds the inputs it was computed from beside its result, and an entry whose inputs differ is a miss, recomputed. The
cache never changes a result.

Nothing here names a file, function, variable, type or field of the target: the units, contracts, roles, documents
and state variables come from the instrument, the extraction sidecar and the documents at run time.
"""
from __future__ import annotations

import copy
import difflib
import fnmatch
import json
import os
import shutil
import sys
from pathlib import Path

from . import common
from . import sites as S
from .common import MutateError

CACHE = Path.home() / ".holon" / "cache" / "mutate"
CACHE_VERSION = 1                                  # recorded in every cache entry's inputs
SIDECAR = "spec/M2/lib/extract_rollup.json"      # the walk of the adopted rollup document (strata.A.rule)
ADOPTION = "spec/M2/lib/derive_extracted.json"   # adopts the sidecar's document (strata.A.rule)
FUNCTION_NODES = ("FunctionDefinition", "ModifierDefinition")
REF_NODES = ("Identifier", "IdentifierPath", "MemberAccess")
LAYOUT_OPS = ("mstore_offset", "shl_width")       # structural.projection_read
COMPARE_OPS = ("cmp_boundary", "cmp_boundary_mirror")
GUARDED_BY = {"dec_go": "ok_go"}                   # roles.doc: dec_go is guarded by ok_go
LIVE = ("PROVED", "UNKNOWN")                       # structural.M0 'reads'
STEP = "step_"                                     # predicted.rule: a cone names action a iff it holds step_<a>
TCE_SETTINGS = {"optimizer": {"enabled": False}, "evmVersion": "cancun",
                "metadata": {"bytecodeHash": "none", "appendCBOR": False}}   # computation item 6, tce.rule


# ---------------------------------------------------------------------------------------------- small helpers
def apply(mutant: dict, data: bytes) -> bytes:
    """data[:offset] + replacement + data[offset + length:], after checking data[offset:offset + length] is the
    mutant's original text (ValueError otherwise)."""
    off, n = mutant.get("offset"), mutant.get("length")
    if type(off) is not int or type(n) is not int or off < 0 or n < 0:
        raise ValueError(f"{mutant.get('id') or mutant.get('file')}: offset and length must be integers >= 0")
    if data[off:off + n] != str(mutant["original"]).encode():
        raise ValueError(f"{mutant.get('id') or mutant.get('file')}: the bytes at {off}..{off + n} are "
                         f"{data[off:off + n][:80]!r}, not the original text {str(mutant['original'])[:80]!r}")
    return data[:off] + str(mutant["replacement"]).encode() + data[off + n:]


def sources(instrument: dict, checkout, sol_deps) -> dict:
    """{file: bytes} of the in-scope files (root checkout or sol_deps), each checked against in_scope.files' sha256
    (MutateError naming the file otherwise)."""
    files = instrument["in_scope"]["files"]
    order = instrument["in_scope"].get("order") or sorted(files)
    if sorted(order) != sorted(files):
        raise MutateError("in_scope.order does not list exactly the in-scope files")
    roots = {"checkout": Path(checkout), "sol_deps": Path(sol_deps)}
    out = {}
    for f in order:
        spec = files[f]
        base = roots.get(spec.get("root"))
        if base is None:
            raise MutateError(f"{f}: unknown root {spec.get('root')!r} in in_scope.files")
        try:
            data = (base / f).read_bytes()
        except OSError as e:
            raise MutateError(f"{f}: cannot read it under {spec['root']} {base}: {e}") from e
        got = common.sha256_bytes(data)
        if got != spec["sha256"]:
            raise MutateError(f"{f}: sha256 {got} under {spec['root']} {base} is not the instrument's {spec['sha256']}")
        out[f] = data
    return out


def render_sheet(instrument: dict, sources: dict) -> str:
    """Computation item 10: diff_sheet.header, then per mutant in id order its heading and a unified diff (3 lines
    of context) of the pinned file and the mutated one."""
    out = "\n".join(instrument["diff_sheet"]["header"]) + "\n"
    for m in instrument["mutants"]:
        before = sources[m["file"]]
        diff = difflib.unified_diff(before.decode().splitlines(), apply(m, before).decode().splitlines(),
                                    f"a/{m['file']}", f"b/{m['file']}", n=3, lineterm="")
        out += (f"\n## {m['id']} {m['operator']} {m['variant']} {m['file']}:{m['line']}:{m['col']} {m['function']}\n\n"
                + "```diff\n" + "\n".join(diff) + "\n```\n")
    return out


def _agree(what: str, got, want) -> None:
    if got != want:
        raise MutateError(f"{what}: recomputed {_short(got)}, the instrument has {_short(want)}")


def _short(x) -> str:
    t = json.dumps(x, sort_keys=True, default=sorted)
    return t if len(t) <= 600 else t[:600] + "..."


def _language(file: str) -> str:
    return "solidity" if file.endswith(".sol") else "go"


def _line_col(data: bytes, offset: int) -> tuple:
    return data.count(b"\n", 0, offset) + 1, offset - (data.rfind(b"\n", 0, offset) + 1) + 1


_run = S.run


def _git_env() -> dict:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def check_checkout(checkout, commit: str) -> None:
    """Computation item 1: the checkout is a clean git checkout (git status empty) at the target commit."""
    head = _run(["git", "-C", str(checkout), "rev-parse", "HEAD"], f"git rev-parse in {checkout}", 300, text=True,
                env=_git_env())
    if head.returncode != 0 or head.stdout.strip() != commit:
        raise MutateError(f"checkout {checkout}: HEAD is {head.stdout.strip() or '?'}, not the target commit {commit}")
    st = _run(["git", "-C", str(checkout), "status", "--porcelain"], f"git status in {checkout}", 600, text=True,
              env=_git_env())
    if st.returncode != 0 or st.stdout.strip():
        raise MutateError(f"checkout {checkout} is not clean: {(st.stdout or st.stderr).strip()[:500]}")


def _with_sol_deps(cfg: dict, sol_deps) -> dict:
    """The config with replay.sol_deps naming the directory whose node_modules is sol_deps (the include path)."""
    sol_deps = Path(sol_deps)
    if sol_deps.name != "node_modules" or not sol_deps.is_dir():
        raise MutateError(f"sol_deps {sol_deps} is not a node_modules directory")
    out = copy.deepcopy(cfg)
    out.setdefault("replay", {})["sol_deps"] = str(sol_deps.parent)
    return out


# ---------------------------------------------------------------------------------------------- artifacts
class Artifacts:
    """The committed artifacts the rules read, under a HOLON root. With pins (instrument "pins"), only pinned files
    are read, each with its pinned sha256: from the working tree when it holds the pinned bytes, else from git at
    pins.holon_commit."""

    def __init__(self, root, pins: dict | None = None):
        self.root = Path(root)
        self.pins = pins
        self._json = {}

    def paths(self, pattern: str) -> list:
        if self.pins is not None:
            return sorted(p for p in self.pins["files"] if fnmatch.fnmatchcase(p, pattern))
        return sorted(p.relative_to(self.root).as_posix() for p in self.root.glob(pattern) if p.is_file())

    def read(self, path: str) -> bytes:
        p = self.root / path
        if self.pins is None:
            try:
                return p.read_bytes()
            except OSError as e:
                raise MutateError(f"cannot read {p}: {e}") from e
        want = self.pins["files"].get(path)
        if want is None:
            raise MutateError(f"{path} is not a pinned artifact (instrument pins.files)")
        try:
            data = p.read_bytes()
            if common.sha256_bytes(data) == want:
                return data
        except OSError:
            pass
        g = _run(["git", "-C", str(self.root), "show", f"{self.pins['holon_commit']}:{path}"],
                 f"git show {path}", 300, env=_git_env())
        if g.returncode != 0 or common.sha256_bytes(g.stdout) != want:
            raise MutateError(f"{path}: neither {p} nor git at {self.pins['holon_commit']} holds the pinned bytes")
        return g.stdout

    def json(self, path: str):
        if path not in self._json:
            try:
                self._json[path] = json.loads(self.read(path))
            except ValueError as e:
                raise MutateError(f"{path} is not valid JSON: {e}") from e
        return self._json[path]


def solidity_roles(instrument: dict, art: Artifacts) -> dict:
    """{role: {"walk", "origins", "units", "entry", "reverts"}} of the Solidity roles (instrument roles.solidity) on
    their extracted edges: walk functions, the origin functions of the ok paths' ops, the units of every op's origin,
    the entry function and the revert paths' lines."""
    out = {}
    for r, spec in sorted(instrument["roles"]["solidity"].items()):
        f = art.json(spec["document"])["functions"].get(spec["edge"])
        if not isinstance(f, dict):
            raise MutateError(f"{spec['document']} has no edge {spec['edge']} (role {r})")
        ops = [(p, op) for p in f.get("paths") or [] for op in p.get("ops") or []]
        out[r] = {"walk": set(f["walk"]["functions"]),
                  "origins": {op["origin"]["fn"] for p, op in ops if p.get("outcome") == "ok"},
                  "units": {op["origin"]["src"].rsplit(":", 1)[0] for _, op in ops},
                  "entry": f["entry"]["fn"],
                  "reverts": {p["src"] for p in f.get("paths") or [] if p.get("outcome") == "revert" and p.get("src")}}
    return out


def go_roles(instrument: dict, art: Artifacts) -> dict:
    """{role: functions} of the Go roles: the named functions and every function they call transitively through the
    document's call edges with callee_kind 'analyzed'."""
    graphs, out = {}, {}
    for r, spec in sorted(instrument["roles"]["go"].items()):
        if spec["document"] not in graphs:
            g = {}
            for e in art.json(spec["document"])["go"]["calls"]["edges"]:
                if e.get("callee_kind") == "analyzed":
                    g.setdefault(e["caller"], set()).add(e["callee"])
            graphs[spec["document"]] = g
        g = graphs[spec["document"]]
        seen, todo = set(spec["named"]), sorted(spec["named"])
        while todo:
            for y in sorted(g.get(todo.pop(), ())):
                if y not in seen:
                    seen.add(y)
                    todo.append(y)
        out[r] = seen
    return out


def _statement_calls(statement) -> set:
    out, stack = set(), [statement]
    while stack:
        t = stack.pop()
        if isinstance(t, dict):
            if isinstance(t.get("call"), str):
                out.add(t["call"])
            stack.extend(t.values())
        elif isinstance(t, list):
            stack.extend(t)
    for a, b in GUARDED_BY.items():
        if a in out:
            out.add(b)
    return out


def law_sets(art: Artifacts) -> tuple:
    """(M0 law -> roles its statement calls, M1x law -> its recorded cone, M2 law -> its entry points)."""
    m0 = {Path(p).stem: _statement_calls(art.json(p)["statement"]) for p in art.paths("laws/M0/L_*.json")}
    cones = {}
    for p in art.paths("results/M2/extracted_m1/L_*.json"):
        r = art.json(p)
        cones[r.get("law_id") or Path(p).stem] = set(r.get("cone") or [])
    entry = {e["law_id"]: set(e.get("entry_points") or []) for e in art.json("laws/M2/DERIVATION.json")["laws"]}
    return m0, cones, entry


def predicted(edges, actions, m0: dict, cones: dict, entry: dict) -> dict:
    """Instrument predicted.rule."""
    edges, actions = set(edges), set(actions)
    return {"M0": sorted(law for law, roles in m0.items() if roles & edges),
            "M1x": sorted(law for law, cone in cones.items() if any(STEP + a in cone for a in actions)),
            "M2": sorted(law for law, eps in entry.items() if eps & actions)}


def structural(m: dict, sol_roles: dict, m0: dict, status: dict) -> dict:
    """Instrument structural: the projection-read roles of the site, the predicted M0 laws reading them, the class."""
    read = set()
    for r in m["edges"]:
        x = sol_roles.get(r)
        if x is None:
            read.add(r)
        elif (m["operator"] in LAYOUT_OPS and m["function"] in x["origins"]) or (
                m["operator"] in COMPARE_OPS and (m["function"] == x["entry"]
                                                  or f"{m['file']}:{m['line']}" in x["reverts"])):
            read.add(r)
    reads = sorted(law for law in m["predicted"]["M0"] if m0[law] & read)
    live = [law for law in reads if status[law] in LIVE]
    p0, p1, p2 = (m["predicted"][k] for k in ("M0", "M1x", "M2"))
    m0c = "reads" if live else "masked" if reads else "carried" if p0 else "none"
    cls = {"reads": "reachable", "masked": "masked", "carried": "projection_carried"}.get(m0c) \
        or ("abstraction_carried" if (p1 or p2) else "no_predicted_law")
    return {"class": cls, "M0": m0c, "M0_reading_laws": reads, "M1x": "carried" if p1 else "none",
            "M2": "carried" if p2 else "none"}


# ---------------------------------------------------------------------------------------------- the solc walk
class Walked:
    """A source tree compiled by the I17 frontend's compile step (with storage layouts) and walked by the I19
    walker (transitions.walk_contract): the per-action closures of computation item 2 and predicted.actions."""

    def __init__(self, cfg: dict, side: dict, tree, walk: bool = True):
        from ..frontends import ExtractionError, Refused
        from ..frontends.solidity import compile as comp
        from ..frontends.solidity import transitions as T
        from ..frontends.solidity.ast import Index
        try:
            self.compiled = comp.compile_sources(cfg, side, Path(tree), storage_layout=walk)
            if walk:
                self.index, self.contract, self.acts, self.coll = T.walk_contract(self.compiled, side)
                self.action_nodes = T.actions_of(self.index, self.contract)
            else:
                self.index = Index(self.compiled)
        except (ExtractionError, Refused) as e:
            raise MutateError(f"the solc {'walk' if walk else 'compile'} of {tree} failed: {e}") from e

    def closures(self) -> dict:
        """{action name: ids of the FunctionDefinitions and ModifierDefinitions reachable from the action's
        FunctionDefinition through Identifier, IdentifierPath, MemberAccess and ModifierInvocation references}."""
        nodes, out = self.index.nodes, {}
        for fn, a in zip(self.action_nodes, self.acts):
            seen, todo = {fn["id"]}, [fn["id"]]
            while todo:
                for r in sorted(_refs(nodes[todo.pop()])):
                    if r not in seen and (nodes.get(r) or {}).get("nodeType") in FUNCTION_NODES:
                        seen.add(r)
                        todo.append(r)
            if a["name"] in out:
                raise MutateError(f"two actions named {a['name']}")
            out[a["name"]] = seen
        return out

    def name(self, node: dict) -> str:
        return self.index.fn_name(node)

    def lines(self, node: dict) -> tuple:
        unit, span = self.index.span(node["src"]).rsplit(":", 1)
        lo, _, hi = span.partition("-")
        return unit, int(lo), int(hi or lo)

    def enclosing(self, mutant: dict) -> dict:
        """The innermost FunctionDefinition or ModifierDefinition of the mutant's unit whose source range holds the
        mutant's offset; its walker name must be the mutant's function."""
        unit, off = mutant["file"], mutant["offset"]
        best = None
        for n in self.index.nodes.values():
            if n.get("nodeType") not in FUNCTION_NODES:
                continue
            a, k, fid = (int(x) for x in n["src"].split(":"))
            if self.compiled.file_ids.get(fid) == unit and a <= off < a + max(k, 1) \
                    and (best is None or k < best[0]):
                best = (k, n)
        if best is None:
            raise MutateError(f"{mutant.get('id') or unit}: no function or modifier of {unit} holds offset {off}")
        if self.name(best[1]) != mutant["function"]:
            raise MutateError(f"{mutant.get('id') or unit}: the function holding offset {off} is "
                              f"{self.name(best[1])}, not {mutant['function']}")
        return best[1]


def _refs(node) -> set:
    out, stack = set(), [node]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            nt = x.get("nodeType")
            if nt in REF_NODES and type(x.get("referencedDeclaration")) is int:
                out.add(x["referencedDeclaration"])
            elif nt == "ModifierInvocation":
                r = (x.get("modifierName") or {}).get("referencedDeclaration")
                if type(r) is int:
                    out.add(r)
            stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
        elif isinstance(x, list):
            stack.extend(x)
    return out


def _sidecar(art: Artifacts, pinned_commit: bool) -> dict:
    side = copy.deepcopy(art.json(SIDECAR))
    if not pinned_commit:
        side.setdefault("target", {})["commit"] = None   # a scratch tree is no pinned checkout (frontends' marker)
    return side


# ---------------------------------------------------------------------------------------------- compile, build, cache
def _cached(kind: str, key: str, inputs: dict, compute):
    """The cached result of compute() for key and inputs (a miss, or different inputs, recomputes)."""
    p = CACHE / kind / f"{key}.json"
    try:
        e = json.loads(p.read_text())
        if e.get("key") == key and e.get("inputs") == inputs and "result" in e:
            return e["result"]
    except (OSError, ValueError, AttributeError):
        pass
    result = compute()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.parent / f".{p.name}.{os.getpid()}.tmp"
        tmp.write_text(common.dump({"key": key, "inputs": inputs, "result": result}))
        os.replace(tmp, p)
    except OSError:
        pass   # an unwritable cache is only slower
    return result


class Bytecode:
    """Computation item 6: the deployed bytecode of the sidecar's contract, solc standard JSON on the sidecar's unit
    (base path the checkout, include path sol_deps, the tce settings), one run per mutant with the mutated unit
    given as content."""

    def __init__(self, cfg: dict, side: dict, checkout, sol_deps, units: dict, commit: str):
        from ..frontends import Refused
        from ..frontends.solidity import compile as comp
        if len(side.get("sources") or []) != 1:
            raise MutateError(f"{SIDECAR} must name exactly one source unit")
        self.unit, self.contract = side["sources"][0], side["transitions"]["contract"]
        try:
            self.solc, sha, _ = comp.check_solc(cfg, (side.get("compiler") or {}).get("version"))
        except Refused as e:
            raise MutateError(str(e)) from e
        self.checkout, self.sol_deps = Path(checkout), Path(sol_deps)
        self.settings = dict(copy.deepcopy(TCE_SETTINGS),
                             outputSelection={self.unit: {self.contract: ["evm.deployedBytecode.object"]}})
        self.inputs = {"cache_version": CACHE_VERSION, "solc_sha256": sha, "settings": self.settings,
                       "unit": self.unit, "contract": self.contract, "target": commit,
                       "units": {u: common.sha256_bytes(b) for u, b in sorted(units.items())}}
        self.base = units[self.unit]

    def run(self, file: str | None = None, data: bytes | None = None) -> str:
        """sha256 of the deployed bytecode object, with file's content data (None: the pinned code)."""
        srcs = {self.unit: {"content": self.base.decode()}}
        if file is not None:
            srcs[file] = {"content": data.decode()}
        inp = json.dumps({"language": "Solidity", "sources": srcs, "settings": self.settings}, sort_keys=True)
        p = _run([self.solc, "--standard-json", "--base-path", ".", "--include-path", str(self.sol_deps)],
                 f"solc on a mutant of {file}" if file else "solc on the pinned code", input=inp, text=True,
                 cwd=str(self.checkout))
        try:
            out = json.loads(p.stdout)
        except ValueError as e:
            raise MutateError(f"solc produced no JSON for {file} (exit {p.returncode}): {p.stderr[-500:]}") from e
        errs = [e.get("formattedMessage") or e.get("message", "") for e in out.get("errors", [])
                if e.get("severity") == "error"]
        if errs:
            raise MutateError(f"a mutant of {file} does not compile (computation item 6): {errs[0][:1000]}")
        obj = out["contracts"][self.unit][self.contract]["evm"]["deployedBytecode"]["object"]
        return common.sha256_text(obj)

    def mutant(self, file: str, data: bytes) -> str:
        key = common.sha256_bytes(data)
        return _cached("solc", key, dict(self.inputs, file=file),
                       lambda: {"deployed_sha256": self.run(file, data)})["deployed_sha256"]


class GoBuild:
    """Computation item 7: go build of the mutated package in a scratch copy of the checkout's go.work modules,
    one build per mutant (the copy is restored after each)."""

    def __init__(self, checkout, go: str, version: str, commit: str):
        self.checkout, self.go = Path(checkout), go
        env = S.go_env()
        self.inputs = {"cache_version": CACHE_VERSION, "go": version, "target": commit,
                       "env": {k: env[k] for k in ("GOFLAGS", "GOTOOLCHAIN", "GOPROXY")}}
        self.tree = None

    def run(self, file: str, data: bytes) -> dict:
        if self.tree is None:
            self.tree = common.copy_tree(self.checkout, common.scratch_dir("i61-gobuild-") / "tree")
        p = self.tree / file
        if not p.is_file():
            raise MutateError(f"{file} is not in the scratch copy of the go.work modules")
        orig = p.read_bytes()
        p.write_bytes(data)
        try:
            b = _run([self.go, "build", "./" + Path(file).parent.as_posix()], f"go build of a mutant of {file}",
                     cwd=str(self.tree), env=S.go_env(), text=True)
        finally:
            p.write_bytes(orig)
        if b.returncode == 0:
            return {"ok": True, "error": None}
        lines = [x for x in (b.stderr + b.stdout).splitlines() if x.strip() and not x.startswith("#")]
        return {"ok": False, "error": "go build: " + (lines[0].strip() if lines else f"exit {b.returncode}")}

    def mutant(self, file: str, data: bytes) -> dict:
        return _cached("gobuild", common.sha256_bytes(data), dict(self.inputs, file=file), lambda: self.run(file, data))

    def close(self) -> None:
        if self.tree is not None:
            shutil.rmtree(self.tree.parent, ignore_errors=True)
            self.tree = None


# ---------------------------------------------------------------------------------------------- the catalog
MUTANT_KEYS = ("id", "stratum", "operator", "variant", "file", "root", "offset", "length", "line", "col", "function",
               "original", "replacement", "mutant_sha256", "tce", "edges", "actions", "predicted", "structural")


def catalog(instrument: dict, checkout, sol_deps) -> list:
    """The mutants recomputed from the pinned checkout and sol_deps: the instrument's 'mutants' (stillborn excluded)."""
    return enumerate_mutants(instrument, checkout, sol_deps)[0]


def stillborn(instrument: dict, checkout, sol_deps) -> list:
    """The generated mutants that do not build (computation item 7), in the instrument's 'stillborn' format."""
    return enumerate_mutants(instrument, checkout, sol_deps)[1]


def enumerate_mutants(instrument: dict, checkout, sol_deps, root=None) -> tuple:
    """(mutants, stillborn) of computation items 2-8 (module docstring)."""
    inst, checkout, sol_deps = instrument, Path(checkout), Path(sol_deps)
    root = common.root(root)
    S.check_operators(inst)
    files, order = inst["in_scope"]["files"], inst["in_scope"]["order"]
    commit = inst["target"]["commit"]
    check_checkout(checkout, commit)
    srcs = sources(inst, checkout, sol_deps)
    art = Artifacts(root, inst["pins"])
    side = _sidecar(art, pinned_commit=True)
    _agree("sidecar target commit", (side.get("target") or {}).get("commit"), commit)
    if side.get("output") not in (art.json(ADOPTION).get("documents") or []):
        raise MutateError(f"{ADOPTION} does not adopt {side.get('output')}, the document of {SIDECAR}")
    cfg = _with_sol_deps(common.config(root), sol_deps)

    # roles and law sets from the pinned artifacts, checked against the instrument
    sol_roles, go_fns = solidity_roles(inst, art), go_roles(inst, art)
    for r, x in sol_roles.items():
        spec = inst["roles"]["solidity"][r]
        got = {"walk_functions": sorted(x["walk"]), "origin_functions": sorted(x["origins"]), "entry": x["entry"],
               "revert_lines": sorted(x["reverts"])}
        _agree(f"roles.solidity, role {r}", got, {k: spec.get(k) for k in got})
    for r, fs in go_fns.items():
        _agree(f"roles.go, role {r}: functions", sorted(fs), inst["roles"]["go"][r]["functions"])
    m0, cones, entry = law_sets(art)
    _agree("roles.m0_law_roles", {k: sorted(v) for k, v in m0.items()}, inst["roles"]["m0_law_roles"])
    status = {law: art.json(f"results/M0/{law}.json")["status"] for law in sorted(m0)}
    base = inst["baseline"]
    _agree("baseline.M0", status, base["M0"])
    _agree("baseline.M1x_cone_actions",
           {k: sorted(c[len(STEP):] for c in v if c.startswith(STEP) and len(c) > len(STEP)) for k, v in cones.items()},
           base["M1x_cone_actions"])
    _agree("baseline.M2_entry_points", {k: sorted(v) for k, v in entry.items()}, base["M2_entry_points"])

    # the Solidity scope (computation item 2) and its sites
    w = Walked(cfg, side, checkout)
    for u, b in sorted(w.compiled.units.items()):
        if u in srcs and srcs[u] != b:
            raise MutateError(f"{u}: solc read other bytes than the in-scope file")
    scope = dict(w.coll.reached)
    for u in sorted(set().union(*(x["units"] for x in sol_roles.values()))):
        if u not in w.compiled.asts:
            raise MutateError(f"{u}, a unit of the header edges' op origins, is not compiled with {SIDECAR}")
        for c in w.compiled.asts[u].get("nodes") or []:
            if c.get("nodeType") == "ContractDefinition":
                for f in c.get("nodes") or []:
                    if f.get("nodeType") in FUNCTION_NODES and f.get("body") is not None:
                        scope.setdefault(f["id"], f)
    closures = w.closures()
    reach = set().union(*closures.values()) & set(scope)
    _agree("the union of the per-action closures (computation item 2)", sorted(reach), sorted(w.coll.reached))
    fn_actions = {fid: sorted(a for a, c in closures.items() if fid in c) for fid in scope}
    got = {}
    for fid, f in scope.items():
        unit, lo, hi = w.lines(f)
        got.setdefault(unit, []).append({"function": w.name(f), "lines": [lo, hi], "actions": fn_actions[fid],
                                         "kind": "modifier" if f["nodeType"] == "ModifierDefinition" else "function"})
    want = {u: v["functions"] for u, v in files.items() if "functions" in v}
    _agree("in_scope Solidity functions (computation item 2)",
           {u: sorted(map(common.compact, v)) for u, v in got.items()},
           {u: sorted(map(common.compact, v)) for u, v in want.items()})
    cursors = S.cursor_declarations(w.index, inst["cursor_pairs"])
    found = S.solidity_sites(w.compiled, scope, cursors)
    for s in found:
        s["actions"] = fn_actions[s["fn"]]
        s["fn"] = w.name(scope[s["fn"]])

    # the Go strata (computation item 3) and their sites
    gofiles = [f for f in order if _language(f) == "go"]
    _check_go_strata(inst, art, gofiles)
    go = S.go_binary()
    version = S.go_version(go)
    _agree("go version (config replay.go_version)", version, cfg["replay"].get("go_version"))
    gofound = S.go_sites(checkout, gofiles, CACHE, go)
    for s in gofound:
        s["actions"] = []
    for f in gofiles:
        _agree(f"in_scope.files[{f}].site_functions", sorted({s["fn"] for s in gofound if s["file"] == f}),
               files[f].get("site_functions"))

    # one candidate per site and variant, in the instrument's order (computation item 5)
    seen, cands = set(), []
    for s in found + gofound:
        if s["file"] not in files:
            raise MutateError(f"a site in {s['file']}, which is not in scope")
        key = (s["op"], s["file"], s["offset"], s["length"])
        if key in seen:
            raise MutateError(f"site {key} matched twice")
        seen.add(key)
        data = srcs[s["file"]]
        if data[s["offset"]:s["offset"] + s["length"]].decode() != s["original"]:
            raise MutateError(f"site {key}: its text is not the pinned file's")
        line, col = _line_col(data, s["offset"])
        for variant, repl in S.variants(s, data):
            if variant not in inst["variant_order"]:
                raise MutateError(f"variant {variant} of {s['op']} is not in variant_order")
            m = {"stratum": files[s["file"]]["stratum"], "operator": s["op"], "variant": variant, "file": s["file"],
                 "root": files[s["file"]]["root"], "offset": s["offset"], "length": s["length"], "line": line,
                 "col": col, "function": s["fn"], "original": s["original"], "replacement": repl}
            mutated = apply(m, data)
            if mutated.count(b"\n") != data.count(b"\n"):
                raise MutateError(f"{key} {variant}: the replacement changes the file's line count")
            m["mutant_sha256"] = common.sha256_bytes(mutated)
            sort_key = (m["stratum"], inst["operator_order"].index(m["operator"]), order.index(m["file"]),
                        m["offset"], inst["variant_order"].index(variant), m["length"])
            cands.append((sort_key, m, s["actions"], mutated))
    cands.sort(key=lambda c: c[0])

    # compile (tce, item 6) and build (stillborn, item 7)
    bytecode = Bytecode(cfg, side, checkout, sol_deps, w.compiled.units, commit)
    original = bytecode.run()
    build = GoBuild(checkout, go, version, commit)
    mutants, born_dead, n = [], [], {}
    try:
        for _, m, actions, mutated in cands:
            if _language(m["file"]) == "solidity":
                m["tce"] = bytecode.mutant(m["file"], mutated) == original
            else:
                b = build.mutant(m["file"], mutated)
                if not b["ok"]:
                    born_dead.append({k: m[k] for k in ("stratum", "operator", "variant", "file", "offset", "length",
                                                         "line", "col", "function", "original", "replacement")}
                                     | {"error": b["error"]})
                    continue
                m["tce"] = None
            n[m["stratum"]] = n.get(m["stratum"], 0) + 1
            m["id"] = f"{m['stratum']}{n[m['stratum']]:03d}"
            m["edges"] = (sorted(r for r, x in sol_roles.items() if m["function"] in x["walk"])
                          if _language(m["file"]) == "solidity" else
                          sorted(r for r, fs in go_fns.items() if m["function"] in fs)) if m["stratum"] == "A" else []
            m["actions"] = actions
            m["predicted"] = predicted(m["edges"], actions, m0, cones, entry)
            m["structural"] = structural(m, sol_roles, m0, status)
            mutants.append({k: m[k] for k in MUTANT_KEYS})
    finally:
        build.close()
    return mutants, born_dead


def _check_go_strata(inst: dict, art: Artifacts, gofiles: list) -> None:
    """Computation item 3: stratum A is every Go file holding a CODEC edge's or a domain predicate's implementation in
    a diagram under gen/M2/diagram/; stratum B every other file holding a codec a committed Go document lists."""
    a_files = set()
    for path in art.paths("gen/M2/diagram/*.json"):
        d = art.json(path)
        fns = {e["component"] for e in d.get("edges") or [] if e.get("kind") == "CODEC"}
        fns |= set(d.get("predicates") or {})
        if not fns:
            continue
        facts = art.json(d["facts"])
        for fn in sorted(fns):
            f = facts["functions"][fn]
            if str(f.get("lang") or "").startswith("go"):
                a_files |= {s["file"] for s in f.get("source") or []}
    codecs = {}
    for path in art.paths("spec/M2/facts/*.go.extracted.json"):
        g = art.json(path)["go"]
        for k in ("encoders", "decoders", "predicates"):
            for c in g["codecs"].get(k) or []:
                f = g["functions"][c["function"]]["span"].rsplit(":", 1)[0]
                codecs.setdefault(f, {}).setdefault(path, set()).add(c["function"])
    strata = {f: "A" for f in a_files}
    strata.update({f: "B" for f in codecs if f not in a_files})
    files = inst["in_scope"]["files"]
    _agree("Go strata (computation item 3)", strata, {f: files[f]["stratum"] for f in gofiles})
    for f in gofiles:
        docs = codecs.get(f) or {}
        _agree(f"in_scope.files[{f}] document and codec_functions",
               {"document": sorted(docs), "codec_functions": sorted(set().union(*docs.values()) if docs else ())},
               {"document": [files[f].get("document")], "codec_functions": files[f].get("codec_functions")})


# ---------------------------------------------------------------------------------------------- a mutant's run
def recompute(instrument: dict, mutant: dict, tree, sol_deps, holon_root) -> dict:
    """The record's "recomputed" field: the rules of roles and predicted applied to a run's own artifacts under
    holon_root (spec/M2/facts documents, results/M2/extracted_m1 cones, laws/M2/DERIVATION.json entry points, laws/M0
    roles) and to a solc walk of tree (the mutated source tree laid out as the checkout) with sol_deps. mutant is a
    catalog mutant or a planted control."""
    art = Artifacts(holon_root)
    spec = instrument["in_scope"]["files"].get(mutant["file"])
    if spec is None:
        raise MutateError(f"{mutant.get('id') or mutant['file']}: {mutant['file']} is not in scope")
    m0, cones, entry = law_sets(art)
    if _language(mutant["file"]) == "solidity":
        roles = solidity_roles(instrument, art)
        edges = sorted(r for r, x in roles.items() if mutant["function"] in x["walk"]) if spec["stratum"] == "A" else []
        cfg = _with_sol_deps(common.config(holon_root), sol_deps)
        w = Walked(cfg, _sidecar(art, pinned_commit=False), tree)
        fid = w.enclosing(mutant)["id"]
        actions = sorted(a for a, c in w.closures().items() if fid in c)
    else:
        roles = go_roles(instrument, art)
        edges = sorted(r for r, fs in roles.items() if mutant["function"] in fs) if spec["stratum"] == "A" else []
        actions = []
    return {"edges": edges, "actions": actions, "predicted": predicted(edges, actions, m0, cones, entry)}


def mutated_function_lines(instrument: dict, mutant: dict, tree, sol_deps):
    """(unit, lo, hi): the 1-based line range of the Solidity FunctionDefinition or ModifierDefinition holding the
    mutant's site in the mutated tree (unit is the mutant's file); None for a Go mutant."""
    if _language(mutant["file"]) != "solidity":
        return None
    if mutant["file"] not in instrument["in_scope"]["files"]:
        raise MutateError(f"{mutant.get('id') or mutant['file']}: {mutant['file']} is not in scope")
    art = Artifacts(common.ROOT)
    w = Walked(_with_sol_deps(common.config(), sol_deps), _sidecar(art, pinned_commit=False), tree, walk=False)
    return w.lines(w.enclosing(mutant))


# ---------------------------------------------------------------------------------------------- CLI
USAGE = """usage:
  python -m holon mutate list                         the catalog recomputed from the pinned checkout, as JSON
  python -m holon mutate sheet [--out PATH] [--check]  the diff sheet (default spec/M2/lib/mutation_diff_sheet_i61.md)
exit 0 ok; 1 --check found a difference; 2 refused, nothing written"""


def main(cmd: str, argv: list) -> int:
    argv = list(argv)
    try:
        if cmd == "list":
            if argv:
                print(USAGE, file=sys.stderr)
                return 2
            inst = common.instrument()
            sys.stdout.write(common.dump(catalog(inst, common.checkout(), common.sol_deps())))
            return 0
        if cmd == "sheet":
            out, check = None, False
            while argv:
                a = argv.pop(0)
                if a == "--check" and not check:
                    check = True
                elif a == "--out" and out is None and argv:
                    out = Path(argv.pop(0))
                elif a.startswith("--out=") and out is None and len(a) > len("--out="):
                    out = Path(a[len("--out="):])
                else:
                    print(USAGE, file=sys.stderr)
                    return 2
            return _sheet(out, check)
    except (MutateError, ValueError, OSError) as e:
        print(f"holon mutate {cmd}: {e}", file=sys.stderr)
        return 2
    print(USAGE, file=sys.stderr)
    return 2


def _sheet(out: Path | None, check: bool) -> int:
    frozen = common.ROOT / common.SHEET
    out = out or frozen
    inst = common.instrument()
    text = render_sheet(inst, sources(inst, common.checkout(), common.sol_deps()))
    cur = out.read_bytes() if out.is_file() else None
    if check:
        if cur == text.encode():
            return 0
        if cur is None:
            print(f"holon mutate sheet --check: {out} is missing", file=sys.stderr)
        else:
            diff = difflib.unified_diff(cur.decode(errors="replace").splitlines(), text.splitlines(),
                                        str(out), "rendered", n=1, lineterm="")
            print("\n".join(list(diff)[:40]), file=sys.stderr)
        return 1
    if cur is not None and cur != text.encode() and out.resolve() == frozen.resolve():
        print(f"holon mutate sheet: refused: {common.SHEET} is frozen and the rendering differs from it "
              f"(write elsewhere with --out, or compare with --check)", file=sys.stderr)
        return 2
    common.write_text(out, text)
    return 0
