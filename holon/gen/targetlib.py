"""Target libraries (holon-lib/0.1): the target-specific part of a generated model (BUILD_PLAN I6).

The model generator (holon.gen.machine) knows only generic machinery: records, state, guarded
actions, a small prelude of list and Nat helpers. Everything specific to one target lives in
library files next to its facts and is read as input, like the facts themselves:

  spec/lib/*.lib.json           libraries for any target (emitted only when their types occur)
  <facts dir>/../lib/*.lib.json libraries for the facts of that milestone (e.g. spec/M1/lib/)
  <facts dir>/../policy_hints.mjs  untrusted search hints for the explorer (optional)

A window view (holon.differential: a facts document whose extraction block names a window declaration of holon.window)
is anchored to the declaration's abstraction (anchor; I66, rule V3 of tests_m3/test_view_evidence.py, the library half
of I65's anchor, tests_m3/test_o12.py rule O4): it takes the abstraction's libraries, as the differential's runs of the
abstraction's laws over the view do. Every other document takes its own.

A library holds:
  builtins       DSL function name -> {"arity": n | null, "bend": template, "type": DSL type,
                 "kind": "nth_default" | "set_default" | "default" (optional), "default": name}
                 Templates: $0..$9 are the compiled arguments, $args all of them comma-separated,
                 ${param:NAME:DEFAULT} a facts parameter.
  prelude        Bend blocks emitted in the prelude slot (between the generic list helpers and the
                 Nat helpers), in library order.
  record_blocks  [{"when_types": [...], "bend": text} | {"when_types": [...], "emit":
                 "shadow_projections", "record": T}] emitted after the generic empty_<T> values, in
                 library order, when the facts declare every listed type.
  shadow_values  shadow field -> Bend expression of a projected element (default: the field).

Libraries are untrusted inputs: G1 regenerates the model from them, and their bytes are part of the
generator hash of every record (holon.records.generator_files).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB_VERSION = "holon-lib/0.1"
WINDOW_VERSION = "holon-window/0.1"   # a window declaration (holon.window: spec/<M>/lib/window_*.json)
_TOKEN = re.compile(r"\$\{(\w+):([^{}]*)\}|\$(args|\d)")


class LibError(Exception):
    pass


def _repo_path(x) -> bool:
    return isinstance(x, str) and bool(x) and not Path(x).is_absolute() and ".." not in Path(x).parts


@lru_cache(maxsize=None)
def _named_declaration(path: str, mtime_ns: int, size: int) -> str | None:
    """The "declaration" of the extraction block of the JSON document at path (cached per file state), or None."""
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return None
    if b'"declaration"' not in raw:   # most documents name none: no parse
        return None
    try:
        doc = json.loads(raw)
    except ValueError:
        return None
    ex = doc.get("extraction") if isinstance(doc, dict) else None
    d = ex.get("declaration") if isinstance(ex, dict) else None
    return d if _repo_path(d) else None


def window_declaration(facts_path: Path | str | None, root: Path | str = ROOT) -> tuple[str, dict] | None:
    """(its repository path, the declaration) when the facts document at facts_path is a window view: a document whose
    extraction block names a window declaration under root (holon.window: {"window_version": "holon-window/0.1",
    "abstraction": the abstraction's repository path, ...}; holon.differential writes the view); else None."""
    if facts_path is None:
        return None
    p = Path(facts_path)
    try:
        if p.suffix != ".json" or not p.is_file():
            return None
        st = p.stat()
    except OSError:
        return None
    rel = _named_declaration(str(p.resolve()), st.st_mtime_ns, st.st_size)
    if rel is None:
        return None
    try:
        decl = json.loads((Path(root) / rel).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(decl, dict) or decl.get("window_version") != WINDOW_VERSION \
            or not _repo_path(decl.get("abstraction")) or not (Path(root) / decl["abstraction"]).is_file():
        return None
    return rel, decl


def anchor(facts_path: Path | str | None, root: Path | str = ROOT) -> Path | str | None:
    """The facts file whose target libraries apply to facts_path: for a window view (window_declaration), its
    declaration's abstraction, as holon.differential's runs of the abstraction's laws over the view take them (the run's
    anchor, holon.mpipeline); for any other document, facts_path itself."""
    w = window_declaration(facts_path, root)
    return Path(root) / w[1]["abstraction"] if w is not None else facts_path


def lib_files(facts_path: Path | str | None, root: Path | str = ROOT) -> list[Path]:
    """Library files applying to a facts file: the global ones, then the milestone's (a window view: its abstraction's,
    anchor), each sorted."""
    root = Path(root)
    out = sorted((root / "spec" / "lib").glob("*.lib.json"))
    if facts_path is not None:
        mine = Path(anchor(facts_path, root)).resolve().parent.parent / "lib"
        if mine.resolve() != (root / "spec" / "lib").resolve():
            out += sorted(mine.glob("*.lib.json"))
    return out


def hints_for(facts_path: Path | str | None) -> Path | None:
    """The untrusted search-hints module for a facts file, if its milestone has one."""
    if facts_path is None:
        return None
    p = Path(facts_path).resolve().parent.parent / "policy_hints.mjs"
    return p if p.exists() else None


class Library:
    """The merged libraries of one facts file."""

    def __init__(self, docs: list[dict], params: dict | None = None):
        self.params = params or {}
        self.builtins: dict[str, dict] = {}
        self.prelude: list[str] = []
        self.record_blocks: list[dict] = []
        self.shadow_values: dict[str, str] = {}
        self.names: list[str] = []
        for d in docs:
            if d.get("lib_version") != LIB_VERSION:
                raise LibError(f"{d.get('name')}: lib_version {d.get('lib_version')!r} is not {LIB_VERSION}")
            self.names.append(d["name"])
            for k, b in d.get("builtins", {}).items():
                if k in self.builtins:
                    raise LibError(f"builtin {k} defined by two libraries")
                self.builtins[k] = b
            self.prelude += d.get("prelude", [])
            self.record_blocks += d.get("record_blocks", [])
            for k, v in d.get("shadow_values", {}).items():
                if k in self.shadow_values:
                    raise LibError(f"shadow value {k} defined by two libraries")
                self.shadow_values[k] = v

    @classmethod
    def for_facts(cls, facts_path: Path | str | None, params: dict | None = None,
                  root: Path | str = ROOT) -> "Library":
        return cls([json.loads(p.read_text(encoding="utf-8")) for p in lib_files(facts_path, root)], params)

    def render(self, name: str, args: list[str]) -> tuple[str, str]:
        b = self.builtins[name]
        if b.get("arity") is not None and len(args) != b["arity"]:
            raise LibError(f"{name} takes {b['arity']} arguments")

        def sub(m: re.Match) -> str:
            if m.group(3) == "args":
                return ", ".join(args)
            if m.group(3) is not None:
                return args[int(m.group(3))]
            kind, rest = m.group(1), m.group(2)
            if kind == "param":
                pname, _, default = rest.partition(":")
                return str(self.params.get(pname, default))
            raise LibError(f"{name}: unknown template token {m.group(0)}")
        return _TOKEN.sub(sub, b["bend"]), b["type"]

    def kind(self, name: str) -> str | None:
        b = self.builtins.get(name)
        return b.get("kind") if b else None

    def default_of(self, name: str) -> str | None:
        b = self.builtins.get(name)
        return b.get("default") if b else None
