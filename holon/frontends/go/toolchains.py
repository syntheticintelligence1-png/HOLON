"""Toolchain selection of the Go frontend by go directive (I103, D1; the contract is the docstring of
tests_m6/test_i103_frontend_reach.py, rules F3-F4).

A frontend config with "toolchain": "go_directive" asks the frontend to choose its go: the lowest release of
config/toolchains.json go_set at or above the go directive of the source's go.work (when the source has one) or go.mod. The
directive is the module's own statement of the least toolchain that builds it (since go 1.21 a go older than the
directive refuses the module), and the lowest such release is the one Go's own GOTOOLCHAIN=auto would move to. None at
or above it: Refused with the directive and the set. A config without "toolchain" (every hand config, Morph's among
them) runs replay.go_version's toolchain exactly as before and never reads this module.
"""
from __future__ import annotations

import re
from pathlib import Path

from .. import Refused

RULE = "go_directive"
_GO = re.compile(r"(?m)^\s*go\s+(\d+(?:\.\d+){0,2})(?:\S*)\s*(?://.*)?$")


def vkey(v: str) -> tuple:
    parts = [int(x) for x in re.match(r"\d+(?:\.\d+)*", v).group(0).split(".")]
    return tuple(parts + [0] * (3 - len(parts)))


def select_go(directive: str, releases) -> str | None:
    """The lowest release at or above the directive ("1.N" is 1.N.0), or None."""
    want = vkey(directive)
    ok = [r for r in releases if vkey(r) >= want]
    return min(ok, key=vkey) if ok else None


def directive(src: Path) -> tuple[str | None, str]:
    """(go directive, the file it came from) of a source tree: go.work when present, else go.mod."""
    for name in ("go.work", "go.mod"):
        p = src / name
        if p.is_file():
            m = _GO.search(re.sub(r"(?s)/\*.*?\*/", "", p.read_text(encoding="utf-8", errors="replace")))
            return (m.group(1) if m else None), name
    return None, "none"


def choose(holon_cfg: dict, src: Path) -> dict:
    """{version, goroot, version_line, directive, file, rule} of the release a go_directive config runs."""
    rel = ((holon_cfg or {}).get("go_set") or {}).get("releases") or {}
    if not rel:
        raise Refused("toolchain \"go_directive\": config/toolchains.json has no go_set")
    d, f = directive(src)
    if d is None:
        raise Refused(f"toolchain \"go_directive\": the source has no go directive ({f})")
    v = select_go(d, rel)
    if v is None:
        raise Refused(f"toolchain \"go_directive\": no pinned go release at or above the go directive {d} of {f} "
                      f"(go_set: {', '.join(sorted(rel, key=vkey))})")
    r = rel[v]
    return {"version": v, "goroot": r.get("goroot"), "version_line": r["version_line"], "directive": d, "file": f,
            "rule": "the lowest pinned release (config go_set) at or above the source's go directive"}
