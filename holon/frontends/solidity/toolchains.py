"""Toolchain selection of the Solidity frontend by version pragma (I103, D1; the contract is the docstring of
tests_m6/test_i103_frontend_reach.py, rules F1-F2).

A sidecar whose compiler.version is the word "pragma" asks the frontend to choose its compiler: the newest release of
config/toolchains.json solc_set (each pinned with its sha256) that satisfies every `pragma solidity` expression of every unit
solc will read (the sidecar's sources and, transitively, the units they import that the source tree or the include path
holds). The pragma is the source's own statement of which compilers may build it, so the choice is the language's, not
HOLON's. No pinned release satisfies them: Refused, naming the expressions and the set. A sidecar that names a version
(every hand sidecar, Morph's among them) never reaches this module.

The version-pragma grammar is solc's (libsolidity/analysis/SemVerHandler): an expression is a disjunction (`||`) of
conjunctions of space-separated comparators; a comparator is an optional operator (^ ~ = < <= > >=; none means =) and a
version of one to three numeric parts, `x`, `X` or `*` standing for a missing part.
  =V      every version V's given parts match (=0.8 is any 0.8.z)
  ^V      >= V and below the next version of V's first nonzero part (^0.5.16: < 0.6.0; ^0.0.3: < 0.0.4; ^1.2: < 2.0.0)
  ~V      >= V and below the next minor (the next major when V gives only its major)
  <V >V <=V >=V  compared with V's missing parts 0 (>V and <=V with a partial V compare its whole prefix)

Pre-0.8 arithmetic. Below 0.8.0 the compiler emits no overflow check, so the walker must not read checked arithmetic:
the release's version decides (`checked_arithmetic`), the walker treats every operation as inside an unchecked block
(wrapping), and the document records extraction.toolchain.solc.arithmetic "unchecked".
"""
from __future__ import annotations

import re
from pathlib import Path

from .. import Refused

PRAGMA_WORD = "pragma"
_PRAGMA = re.compile(r"\bpragma\s+solidity\s+([^;]*);")
_IMPORT = re.compile(r"""\bimport\s+(?:[^'";]*?\bfrom\s+)?["']([^"']+)["']""")
_CMP = re.compile(r"^(\^|~|>=|<=|>|<|=)?\s*(\d+|[xX*])(?:\.(\d+|[xX*]))?(?:\.(\d+|[xX*]))?$")


def vkey(v: str) -> tuple:
    return tuple(int(x) for x in v.split("+", 1)[0].split("-", 1)[0].split("."))


def strip_comments(text: str) -> str:
    """The text with // and /* */ comments blanked (string literals kept: a pragma never sits inside one)."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            seg = text[i:n if j < 0 else j + 2]
            out.append("".join(ch if ch == "\n" else " " for ch in seg))
            i = n if j < 0 else j + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def pragmas(text: str) -> list[str]:
    """Every `pragma solidity <expr>;` expression of a source text, in order, whitespace normalized."""
    return [" ".join(m.group(1).split()) for m in _PRAGMA.finditer(strip_comments(text))]


def imports(text: str) -> list[str]:
    return [m.group(1) for m in _IMPORT.finditer(strip_comments(text))]


def _tokens(conj: str) -> list[str]:
    """Space-separated comparators, an operator separated from its version by spaces joined back to it."""
    raw, out = conj.split(), []
    for t in raw:
        if out and out[-1] in ("^", "~", ">=", "<=", ">", "<", "="):
            out[-1] += t
        else:
            out.append(t)
    return out


def _cmp_ok(v: tuple, tok: str) -> bool:
    m = _CMP.match(tok)
    if not m:
        raise ValueError(f"not a version comparator: {tok!r}")
    op = m.group(1) or "="
    parts = [p for p in m.group(2, 3, 4) if p is not None]
    given = []
    for p in parts:
        if p in ("x", "X", "*"):
            break
        given.append(int(p))
    k = len(given)
    full = tuple(given + [0] * (3 - k))
    if op == "=":
        return v[:k] == tuple(given)
    if op == "^":
        if k == 0:
            return True
        nz = next((i for i, x in enumerate(given) if x != 0), k - 1)
        upper = list(given[:nz + 1])
        upper[nz] += 1
        upper = tuple(upper + [0] * (3 - len(upper)))
        return full <= v < upper
    if op == "~":
        if k == 0:
            return True
        upper = (given[0] + 1, 0, 0) if k == 1 else (given[0], given[1] + 1, 0)
        return full <= v < upper
    if op == ">=":
        return v >= full
    if op == "<":
        return v < full
    if op == ">":
        return v[:k] > tuple(given) if k else False
    if op == "<=":
        return v[:k] <= tuple(given) if k else True
    raise ValueError(op)


def satisfies(version: str, expr: str) -> bool:
    v = vkey(version)
    alts = [a.strip() for a in expr.split("||")]
    return any(all(_cmp_ok(v, t) for t in _tokens(a)) for a in alts if a.strip()) if any(alts) else True


def select_solc(exprs: list[str], releases) -> str | None:
    """The newest release satisfying every expression (no expression: the newest release), or None."""
    ok = [r for r in releases if all(satisfies(r, e) for e in exprs)]
    return max(ok, key=vkey) if ok else None


def checked_arithmetic(version: str) -> bool:
    return vkey(version) >= (0, 8, 0)


def unit_pragmas(source: Path, units: list[str], include: Path | None) -> dict:
    """{unit: [expr]} over the sidecar's units and the units they import (resolved as solc resolves them: relative to
    the importing unit's directory for ./ and ../, else against the base path (the source tree) and the include path);
    an import neither holds is skipped (the compile reports it)."""
    seen, todo = {}, list(units)
    while todo:
        u = todo.pop(0)
        if u in seen:
            continue
        p = source / u
        if not p.is_file() and include is not None and (include / u).is_file():
            p = include / u
        try:
            text = p.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        seen[u] = pragmas(text)
        for imp in imports(text):
            if imp.startswith("./") or imp.startswith("../"):
                parts = []
                for seg in (Path(u).parent.as_posix() + "/" + imp).split("/"):
                    if seg in ("", "."):
                        continue
                    if seg == "..":
                        if parts:
                            parts.pop()
                        continue
                    parts.append(seg)
                todo.append("/".join(parts))
            else:
                todo.append(imp)
    return {u: seen[u] for u in sorted(seen)}


def load_sets(root: Path) -> dict:
    """config/toolchains.json (I103): the pinned solc_set and go_set. Not config/holon.json, whose bytes every Morph
    law record reads as an input."""
    import json
    p = Path(root) / "config" / "toolchains.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"cannot read {p}: {e}") from e


def choose(cfg: dict, source: Path, units: list[str], include: Path | None) -> dict:
    """{version, path, sha256, pragmas, rule} of the pinned release a "pragma" sidecar compiles with; Refused when no
    pinned release satisfies the units' pragmas or the set is not configured."""
    s = cfg.get("solc_set") or {}
    rel = s.get("releases") or {}
    if not rel or not s.get("dir"):
        raise Refused("compiler.version \"pragma\": config/toolchains.json has no solc_set")
    by_unit = unit_pragmas(source, units, include)
    exprs = sorted({e for es in by_unit.values() for e in es})
    v = select_solc(exprs, rel)
    if v is None:
        raise Refused(f"compiler.version \"pragma\": no pinned solc release satisfies the units' pragmas {exprs} "
                      f"(solc_set: {min(rel, key=vkey)} .. {max(rel, key=vkey)}, {len(rel)} releases)")
    return {"version": v, "path": str(Path(s["dir"]) / f"solc-{v}"), "sha256": rel[v], "pragmas": exprs,
            "rule": "the newest pinned release (config solc_set) satisfying every version pragma of the units solc reads"}
