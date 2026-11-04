"""The operator patterns of the I61 instrument (its "operators" field), matched on the pinned code (computation items 4
and 5): Solidity on solc's compact AST (the Yul AST of inline assembly included), Go with go/ast through the helper
program holon/mutate/gosites, and each site's variants (the operators' rewrites).

A site is a dict {"op", "file", "offset", "length", "original", "fn", "lits"}: the replaced byte range of the unit
(offsets are byte offsets), its text, the enclosing function (a solc node id for Solidity, a go/ssa name for Go) and,
for the literal-shifting operators, the byte ranges of the decimal literals a variant shifts. Nothing here names a
target: the patterns are the operators' own, the state variables of swap_cursor come from the instrument's
cursor_pairs and the in-scope files and functions from the caller.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from .common import MutateError

LANGUAGE = {
    "mstore_offset": "solidity", "shl_width": "solidity", "drop_delete": "solidity", "swap_cursor": "solidity",
    "cmp_boundary": "solidity", "cmp_boundary_mirror": "solidity", "mload_offset": "solidity", "shr_width": "solidity",
    "putuint64_offset": "go", "copy_offset": "go", "drop_len_check": "go", "go_slice_offset": "go",
}
OFFSET_OPS = ("mstore_offset", "mload_offset", "putuint64_offset", "copy_offset")
WIDTH_OPS = ("shl_width", "shr_width")
DROP_OPS = ("drop_delete", "drop_len_check")
FLIPS = {"cmp_boundary": {">=": ">", ">": ">="}, "cmp_boundary_mirror": {"<=": "<", "<": "<="}}
YUL_OFFSET = {"mstore": "mstore_offset", "mstore8": "mstore_offset", "mload": "mload_offset"}
YUL_WIDTH = {"shl": "shl_width", "shr": "shr_width"}
COMPARE = {op: name for name, flips in FLIPS.items() for op in flips}
DIGITS = re.compile(r"[0-9]+")
WHITESPACE = b" \t\r\n"


def check_operators(inst: dict) -> None:
    """Every operator the instrument defines is one this module implements, in the same language, and
    operator_order names each exactly once."""
    ops = inst.get("operators") or {}
    for op, spec in sorted(ops.items()):
        if LANGUAGE.get(op) != spec.get("language"):
            raise MutateError(f"operator {op} (language {spec.get('language')}) has no implementation here")
    if sorted(inst.get("operator_order") or []) != sorted(ops):
        raise MutateError("operator_order does not name every operator exactly once")


def variants(site: dict, data: bytes) -> list:
    """[(variant, replacement)] of a site: the operator's rewrite (instrument operators.<op>.rewrite)."""
    op, text = site["op"], site["original"]
    if op in OFFSET_OPS:
        k = int(text)
        return ([("-1", str(k - 1))] if k >= 1 else []) + [("+1", str(k + 1))]
    if op in WIDTH_OPS:
        s = int(text)
        return [(label, str(s + d)) for label, d in (("-8", -8), ("+8", 8)) if 0 < s + d < 256]
    if op == "go_slice_offset":
        (a, b), (c, d) = site["lits"]
        lo, mid, hi = int(data[a:b]), data[b:c].decode(), int(data[c:d])
        return ([("-1", f"{lo - 1}{mid}{hi - 1}")] if lo >= 1 else []) + [("+1", f"{lo + 1}{mid}{hi + 1}")]
    if op in DROP_OPS:
        return [("drop", "{}" + "\n" * text.count("\n"))]
    if op in FLIPS:
        return [("flip", FLIPS[op][text])]
    if op == "swap_cursor":
        return [("swap", site["other"])]
    raise MutateError(f"operator {op} has no rewrite here")


# ---------------------------------------------------------------------------------------------- Solidity
def _src(compiled, s: str):
    a, n, fid = (int(x) for x in s.split(":"))
    unit = compiled.file_ids.get(fid)
    if unit is None:
        raise MutateError(f"solc src {s} names no source unit")
    return unit, a, n


def _decimal_literal(compiled, node) -> tuple | None:
    """(unit, offset, length) of a Yul literal whose source text is decimal digits."""
    if not isinstance(node, dict) or node.get("nodeType") != "YulLiteral" or not node.get("src"):
        return None
    unit, a, n = _src(compiled, node["src"])
    text = compiled.units[unit][a:a + n]
    return (unit, a, n) if n and DIGITS.fullmatch(text.decode("latin-1")) else None


def _yul_sites(compiled, ast_node, fn_id: int, out: list) -> None:
    stack = [ast_node]
    while stack:
        y = stack.pop()
        if isinstance(y, list):
            stack.extend(y)
            continue
        if not isinstance(y, dict):
            continue
        if y.get("nodeType") == "YulFunctionCall":
            name = (y.get("functionName") or {}).get("name")
            args = y.get("arguments") or []
            if name in YUL_OFFSET and args and isinstance(args[0], dict) \
                    and args[0].get("nodeType") == "YulFunctionCall" \
                    and (args[0].get("functionName") or {}).get("name") == "add" \
                    and len(args[0].get("arguments") or []) == 2:
                lit = _decimal_literal(compiled, args[0]["arguments"][1])
                if lit:
                    out.append(_site(compiled, YUL_OFFSET[name], lit, fn_id))
            if name in YUL_WIDTH and args:
                lit = _decimal_literal(compiled, args[0])
                if lit:
                    out.append(_site(compiled, YUL_WIDTH[name], lit, fn_id))
        stack.extend(v for v in y.values() if isinstance(v, (dict, list)))


def _site(compiled, op: str, where: tuple, fn, **extra) -> dict:
    unit, a, n = where
    s = {"op": op, "file": unit, "offset": a, "length": n,
         "original": compiled.units[unit][a:a + n].decode(), "fn": fn, "lits": [[a, a + n]]}
    s.update(extra)
    return s


def solidity_sites(compiled, scope: dict, cursors: dict) -> list:
    """The Solidity sites in the bodies of the scope's functions and modifiers ({node id: node}); cursors maps the
    declaration id of each cursor state variable to the other variable's name."""
    out = []
    for fn_id in sorted(scope):
        body = scope[fn_id].get("body")
        stack = [(body, None, None)]
        while stack:
            x, parent, key = stack.pop()
            if isinstance(x, list):
                stack.extend((v, parent, key) for v in x)
                continue
            if not isinstance(x, dict):
                continue
            nt = x.get("nodeType")
            if nt == "InlineAssembly":
                _yul_sites(compiled, x.get("AST"), fn_id, out)
                continue
            if nt == "ExpressionStatement":
                e = x.get("expression") or {}
                if e.get("nodeType") == "UnaryOperation" and e.get("operator") == "delete":
                    out.append(_delete_site(compiled, e, fn_id))
            elif nt == "BinaryOperation" and x.get("operator") in COMPARE:
                out.append(_compare_site(compiled, x, fn_id))
            elif nt == "Identifier" and x.get("referencedDeclaration") in cursors:
                written = (parent or {}).get("nodeType") == "Assignment" and key == "leftHandSide"
                stepped = (parent or {}).get("nodeType") == "UnaryOperation" \
                    and parent.get("operator") in ("++", "--", "delete")
                if not (written or stepped):
                    where = _src(compiled, x["src"])
                    s = _site(compiled, "swap_cursor", where, fn_id, other=cursors[x["referencedDeclaration"]])
                    if s["original"] != x.get("name"):
                        raise MutateError(f"{s['file']}:{s['offset']}: identifier text {s['original']!r} is not "
                                          f"its name {x.get('name')!r}")
                    out.append(s)
            for k, v in x.items():
                if isinstance(v, (dict, list)):
                    stack.append((v, x, k))
    return out


def _delete_site(compiled, e: dict, fn_id: int) -> dict:
    """The statement from 'delete' through its terminating semicolon."""
    unit, a, n = _src(compiled, e["src"])
    data = compiled.units[unit]
    if not data[a:].startswith(b"delete"):
        raise MutateError(f"{unit}:{a}: a delete expression that does not start with the keyword")
    j = a + n
    while j < len(data) and data[j] in WHITESPACE:
        j += 1
    if data[j:j + 1] != b";":
        raise MutateError(f"{unit}:{a}: a delete statement whose semicolon does not follow its expression")
    return _site(compiled, "drop_delete", (unit, a, j + 1 - a), fn_id)


def _compare_site(compiled, x: dict, fn_id: int) -> dict:
    """The operator token between the operands' source ranges."""
    op = x["operator"]
    lu, la, ln = _src(compiled, x["leftExpression"]["src"])
    ru, ra, _ = _src(compiled, x["rightExpression"]["src"])
    between = compiled.units[lu][la + ln:ra]
    if lu != ru or between.strip(WHITESPACE) != op.encode():
        raise MutateError(f"{lu}:{la}: the text between the operands of {op} is {between!r}")
    return _site(compiled, COMPARE[op], (lu, la + ln + between.index(op.encode()), len(op)), fn_id)


def cursor_declarations(index, pairs: list) -> dict:
    """{declaration id: the other variable's name} of every state variable named in a cursor pair."""
    other = {}
    for pair in pairs:
        if len(pair) != 2 or pair[0] == pair[1]:
            raise MutateError(f"cursor pair {pair} is not a pair of two names")
        other[pair[0]], other[pair[1]] = pair[1], pair[0]
    return {nid: other[n["name"]] for nid, n in sorted(index.nodes.items())
            if n.get("nodeType") == "VariableDeclaration" and n.get("stateVariable") and n.get("name") in other}


# ---------------------------------------------------------------------------------------------- Go
GOSITES = Path(__file__).resolve().parent / "gosites"
GOSITES_FILES = ("main.go", "go.mod")


def run(cmd: list, what: str, timeout: int = 1800, **kw) -> subprocess.CompletedProcess:
    """subprocess.run with captured output; a timeout or a launch failure is a MutateError naming what was run."""
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout, **kw)
    except subprocess.TimeoutExpired as e:
        raise MutateError(f"{what}: no answer within {timeout} s") from e
    except OSError as e:
        raise MutateError(f"{what}: cannot run {cmd[0]}: {e}") from e


def go_binary() -> str:
    found = shutil.which("go")
    if found:
        return found
    if Path("/usr/local/go/bin/go").is_file():
        return "/usr/local/go/bin/go"
    raise MutateError("no go toolchain: neither go on PATH nor /usr/local/go/bin/go")


def go_env(**extra) -> dict:
    """The pinned Go environment (offline, local toolchain, read-only modules)."""
    env = {k: v for k, v in os.environ.items() if k not in ("GOWORK", "GOFLAGS", "GOTOOLCHAIN", "GOPROXY")}
    env.update(GOTOOLCHAIN="local", GOFLAGS="-mod=readonly", GOPROXY="off")
    env.update(extra)
    return env


def go_version(go: str) -> str:
    p = run([go, "version"], f"{go} version", 120, text=True, env=go_env())
    if p.returncode != 0:
        raise MutateError(f"{go} version failed: {p.stderr.strip()[-300:]}")
    return p.stdout.strip()


def _gosites_binary(go: str, cache: Path) -> Path:
    h = hashlib.sha256()
    for name in GOSITES_FILES:
        h.update(name.encode() + b"\0" + (GOSITES / name).read_bytes() + b"\0")
    out = cache / "gosites" / h.hexdigest()[:16] / "gosites"
    if out.is_file() and os.access(out, os.X_OK):
        return out
    tmp = out.parent / f"gosites.tmp{os.getpid()}"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        p = run([go, "build", "-trimpath", "-o", str(tmp), "."], f"go build of {GOSITES}", cwd=GOSITES,
                env=go_env(GOWORK="off"), text=True)
        if p.returncode != 0 or not tmp.is_file():
            raise MutateError(f"cannot build {GOSITES} (exit {p.returncode}): {(p.stdout + p.stderr)[-2000:]}")
        os.replace(tmp, out)
    except OSError as e:
        raise MutateError(f"cannot place the gosites helper under {out.parent}: {e}") from e
    return out


def package_path(tree: Path, rel: str) -> str:
    """The import path of the package of a Go file: its module's path (the nearest go.mod up from the file) and the
    file's directory inside the module."""
    tree = Path(tree)
    d = (tree / rel).parent
    while True:
        mod = d / "go.mod"
        if mod.is_file():
            for line in mod.read_text().splitlines():
                t = line.split("//")[0].strip()
                if t.startswith("module "):
                    module = t[len("module "):].strip().strip('"')
                    inner = (tree / rel).parent.relative_to(d).as_posix()
                    return module if inner == "." else f"{module}/{inner}"
            raise MutateError(f"{mod} names no module")
        if d == tree or tree not in d.parents:
            raise MutateError(f"{rel}: no go.mod between the file and {tree}")
        d = d.parent


def ssa_name(pkg: str, s: dict) -> str:
    """The go/ssa name of the function enclosing a site: pkg.F, (pkg.T).M or (*pkg.T).M, $k per function literal."""
    if s.get("generic"):
        raise MutateError(f"{s['file']}:{s['start']}: a site in a method of a generic type (no go/ssa name here)")
    if s["recv"]:
        name = f"({'*' if s['ptr'] else ''}{pkg}.{s['recv']}).{s['name']}"
    elif s["name"] == "init":
        raise MutateError(f"{s['file']}:{s['start']}: a site in an init function (go/ssa numbers them per package)")
    else:
        name = f"{pkg}.{s['name']}"
    return name + "".join(f"${k}" for k in s.get("anon") or [])


def go_sites(tree: Path, files: list, cache: Path, go: str | None = None) -> list:
    """The Go sites of the files (relative to tree), from the gosites helper."""
    if not files:
        return []
    go = go or go_binary()
    exe = _gosites_binary(go, cache)
    p = run([str(exe), str(tree), *files], "gosites", 900, text=True)
    if p.returncode != 0:
        raise MutateError(f"gosites failed (exit {p.returncode}): {p.stderr.strip()[-2000:]}")
    pkgs = {f: package_path(tree, f) for f in files}
    texts = {f: (Path(tree) / f).read_bytes() for f in files}
    out = []
    for line in p.stdout.splitlines():
        s = json.loads(line)
        data = texts[s["file"]]
        out.append({"op": s["op"], "file": s["file"], "offset": s["start"], "length": s["end"] - s["start"],
                    "original": data[s["start"]:s["end"]].decode(), "fn": ssa_name(pkgs[s["file"]], s),
                    "lits": [list(x) for x in s["lits"]]})
    return out
