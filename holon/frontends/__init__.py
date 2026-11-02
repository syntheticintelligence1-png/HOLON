"""holon.frontends: fact extraction from target code (whitepaper §10.1), shared by every frontend.

  python -m holon extract <frontend> ...

The first argument names the frontend; `main` imports holon.frontends.<frontend> and returns that module's own
main(argv[1:]). There is no registry and this module names no frontend: a frontend is any submodule with a `main`.
Importing this package and dispatching open no file (the frontend's main reads its own inputs).

Shared pieces (the holon-facts/0.3 envelope, spec/schemas/facts_0_3.schema.json):
  FACTS_VERSION            "holon-facts/0.3"
  Refused                  exit 2: an input is refused before anything is extracted, nothing written
  ExtractionError          exit 3: the extraction failed (named), nothing written
  load_sidecar(path)       an extraction sidecar spec/<M>/lib/extract_<frontend>.json, checked for the common format
                           (sidecar_version, frontend, doc, target {repo, commit, scope}, output ".extracted.json")
  sidecars(m, root)        the sorted extraction sidecars of milestone m
  extract(sidecar, root, source)
                           the document of one sidecar, by holon.frontends.<frontend>.extract_document
  render(doc)              canonical bytes: json.dumps(doc, indent=2, sort_keys=True) + newline
  regenerate(m, root, tmp) every sidecar of m extracted again and compared byte for byte with its committed output
                           (gate G1); returns (differences, note)
"""
from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path

FACTS_VERSION = "holon-facts/0.3"
ROOT = Path(__file__).resolve().parents[2]
_NAME = re.compile(r"[a-z][a-z0-9_]*")
_COMMIT = re.compile(r"[0-9a-f]{40}")


class Refused(Exception):
    """An input is refused (exit 2): nothing is extracted, nothing written."""


class ExtractionError(Exception):
    """The extraction failed (exit 3): the message names what failed; nothing written."""


def _frontend(name: str):
    """The frontend module holon.frontends.<name>, or None when there is no such module with a main."""
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        return None
    full = f"{__name__}.{name}"
    try:
        mod = importlib.import_module(full)
    except ModuleNotFoundError as e:
        if e.name in (full, __name__):
            return None
        raise
    return mod if callable(getattr(mod, "main", None)) else None


def main(argv=None) -> int:
    """`holon extract <frontend> ...`: dispatch to holon.frontends.<frontend>.main(argv[1:])."""
    argv = list(sys.argv[1:] if argv is None else argv)
    name = argv[0] if argv else None
    mod = None if name is None or name.startswith("-") else _frontend(name)
    if mod is None:
        shown = "(none given)" if name is None else name
        print(f"holon extract: unknown frontend {shown} (usage: holon extract <frontend> ...)", file=sys.stderr)
        return 2
    return mod.main(argv[1:])


def load_sidecar(path) -> dict:
    """Read an extraction sidecar and check the format every frontend's sidecar shares; Refused if malformed."""
    p = Path(path)
    try:
        side = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"sidecar {p}: cannot read it: {e}") from e
    bad = []
    if not isinstance(side, dict):
        raise Refused(f"sidecar {p}: not a JSON object")
    if side.get("sidecar_version") != 1:
        bad.append("sidecar_version is not 1")
    if not isinstance(side.get("frontend"), str) or not _NAME.fullmatch(side.get("frontend") or ""):
        bad.append("frontend is not a frontend name")
    if not isinstance(side.get("doc"), str):
        bad.append("doc is not a string")
    t = side.get("target")
    if not isinstance(t, dict) or sorted(t) != ["commit", "repo", "scope"]:
        bad.append("target is not {repo, commit, scope}")
    else:
        if not isinstance(t["repo"], str) or not isinstance(t["scope"], str):
            bad.append("target repo and scope are strings")
        if t["commit"] is not None and not (isinstance(t["commit"], str) and _COMMIT.fullmatch(t["commit"])):
            bad.append("target.commit is neither 40 hex nor null")
    out = side.get("output")
    if not isinstance(out, str) or not out.endswith(".extracted.json") or out.startswith("/") or ".." in out.split("/"):
        bad.append("output is not a repo-relative path ending .extracted.json")
    if bad:
        raise Refused(f"sidecar {p}: malformed: " + "; ".join(bad))
    return side


def sidecars(m: str, root=ROOT) -> list[Path]:
    """The extraction sidecars of milestone m: sorted spec/<m>/lib/extract_*.json."""
    return sorted((Path(root) / "spec" / m / "lib").glob("extract_*.json"))


def extract(sidecar_path, root=ROOT, source=None) -> dict:
    """The holon-facts/0.3 document of one sidecar, extracted by the frontend the sidecar names."""
    side = load_sidecar(sidecar_path)
    mod = _frontend(side["frontend"])
    if mod is None or not callable(getattr(mod, "extract_document", None)):
        raise Refused(f"sidecar {sidecar_path}: unknown frontend {side['frontend']}")
    return mod.extract_document(side, Path(sidecar_path), Path(root), source)


def render(doc: dict) -> bytes:
    """The canonical bytes of a document."""
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode()


def regenerate(m: str, root=ROOT, tmp=None) -> tuple[list[str], str]:
    """G1: extract every sidecar of m again (into tmp when given) and compare it byte for byte with <root>/<output>.
    A difference, or an extraction that fails, names the output path. The note names every output compared."""
    root = Path(root).resolve()
    diffs, done = [], []
    for sp in sidecars(m, root):
        try:
            out_rel = load_sidecar(sp)["output"]
        except Refused as e:
            diffs.append(f"{sp.relative_to(root).as_posix()}: {e}")
            continue
        try:
            got = render(extract(sp, root))
        except (Refused, ExtractionError) as e:
            diffs.append(f"{out_rel}: extraction failed: {type(e).__name__}: {e}")
            done.append(out_rel)
            continue
        if tmp is not None:
            t = Path(tmp) / out_rel
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_bytes(got)
        want = root / out_rel
        if not want.exists():
            diffs.append(f"{out_rel}: not committed")
        elif want.read_bytes() != got:
            diffs.append(f"{out_rel}: differs from a fresh extraction")
        done.append(out_rel)
    note = (f"extracted facts regenerated: {', '.join(done)}" if done else f"no extraction sidecars for {m}")
    return diffs, note
