"""python -m holon eval renaming [--root DIR] [--cache DIR] [--check] (I48 rule N3's documents).

For every entry of DIR/spec/eval/corpus.json: a checkout of its repository at the pre-fix commit holding what rule N1
reads (every file directly in each directory that holds a .go file of the entry, and every .sol file of the tree; a
sparse git worktree of holon's own clone), the entry's files renamed with the entry id as seed (holon eval rename's
code), unrenamed again, and the round trip compared byte for byte. The document gen/eval/renaming/<entry>.json
(spec/M4/lib/renaming.schema.json) records the files (as in the map), the number of identifiers renamed, the
candidates (distinct identifier tokens of the files that are not reserved), on_changed_lines (renamed identifiers
that occur on a pre-fix line the fix deletes or changes, gitfacts.changed_old_lines), the files compared by AST and by
tokens alone, and the map's sha256. The map itself is never written into the repository (it pairs each original name
with its new one).

Exit 0 written (or, with --check, every document is what a fresh run gives), 1 a document differs (named) or an entry
fails its round trip or the tool's own isomorphism check, 2 refused.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

from . import common, rename


def sparse_patterns(files: list[str]) -> list[str]:
    """The non-cone sparse-checkout patterns of rule N1's checkout: each directory holding a .go file of the set with
    its files but not its subdirectories, and every .sol file of the tree when the set holds one."""
    pats = []
    for d in sorted({PurePosixPath(f).parent.as_posix() for f in files if f.endswith(".go")}):
        base = "" if d == "." else "/" + d
        pats += [f"{base}/*", f"!{base}/*/"]
    if any(f.endswith(".sol") for f in files):
        pats.append("*.sol")
    return pats


def checkout(url: str, sha: str, files: list[str], dest: Path) -> Path:
    """A sparse worktree of holon's clone of url at sha (a commit reachable from a branch or tag) for rule N1."""
    clone = common.repo_cache(url)
    if not re.fullmatch(r"[0-9a-f]{40}", sha or "") or \
            (sha not in common.reachable(clone) and sha not in common.reachable(clone, refresh=True)):
        raise common.Refused(f"{url}@{sha} is not reachable from a branch or tag")
    common.git(clone, "worktree", "add", "--no-checkout", "--detach", str(dest), sha)
    common.git(dest, "sparse-checkout", "set", "--no-cone", *sparse_patterns(files))
    common.git(dest, "checkout", "--quiet", sha)
    return dest


def drop(url: str, dest: Path) -> None:
    clone = common.repo_cache(url)
    subprocess.run(["git", "-C", str(clone), "worktree", "remove", "--force", str(dest)], capture_output=True,
                   env=common.git_env())
    subprocess.run(["git", "-C", str(clone), "worktree", "prune"], capture_output=True, env=common.git_env())


def entry_document(e: dict) -> dict:
    """Rule N3 on one corpus entry: its renaming document (raises when the round trip or the isomorphism fails)."""
    from . import gitfacts
    files = list(e["files"])
    with tempfile.TemporaryDirectory(prefix="holon-renaming-") as tmp:
        tmp = Path(tmp)
        src = tmp / "src"
        checkout(e["repo"], e["prefix_commit"], files, src)
        try:
            out, mp, back = tmp / "renamed", tmp / "map.json", tmp / "back"
            m, sf = rename.rename(src, files, e["id"], out, mp)    # raises when its own isomorphism check fails
            rename.unrename(out, mp, back)                         # refuses when a restored sha256 differs
            bad = [f for f in files if (back / f).read_bytes() != (src / f).read_bytes()]
            if bad:
                raise RuntimeError(f"{e['id']}: the round trip changed {bad}")
            ids = set(m["identifiers"])
            hit: set[str] = set()
            for f in files:
                lines = (src / f).read_bytes().split(b"\n")
                for n in gitfacts.changed_old_lines(e["repo"], e["prefix_commit"], e["fix_commit"], f):
                    if 1 <= n <= len(lines):
                        hit |= rename.words(lines[n - 1]) & ids
            by_ast = sum(1 for f in sf.files.values() if f.language == "go" or f.parsed)
            return {"entry": e["id"], "seed": e["id"], "files": m["files"], "renamed": len(ids),
                    "candidates": sf.candidates, "on_changed_lines": len(hit), "files_by_ast": by_ast,
                    "files_by_tokens": len(files) - by_ast, "roundtrip": True, "isomorphic": True,
                    "map_sha256": common.sha256_file(mp)}
        finally:
            drop(e["repo"], src)


def schema_problems(doc, schema: dict, where: str = "") -> list[str]:
    """The renaming document against its schema (the keywords that schema uses: type, properties, required,
    additionalProperties, items, minItems, minimum, pattern, const, enum)."""
    out = []
    t = schema.get("type")
    kinds = {"object": dict, "array": list, "string": str}
    if t == "integer" and (not isinstance(doc, int) or isinstance(doc, bool)):
        return [f"{where}: not an integer"]
    if t in kinds and not isinstance(doc, kinds[t]):
        return [f"{where}: not {t}"]
    if "const" in schema and doc != schema["const"]:
        out.append(f"{where}: not {schema['const']!r}")
    if "enum" in schema and doc not in schema["enum"]:
        out.append(f"{where}: not one of {schema['enum']}")
    if "minimum" in schema and isinstance(doc, int) and doc < schema["minimum"]:
        out.append(f"{where}: below {schema['minimum']}")
    if "pattern" in schema and isinstance(doc, str) and not re.search(schema["pattern"], doc):
        out.append(f"{where}: does not match {schema['pattern']}")
    if isinstance(doc, dict):
        props = schema.get("properties", {})
        out += [f"{where}.{k}: missing" for k in schema.get("required", []) if k not in doc]
        if schema.get("additionalProperties") is False:
            out += [f"{where}.{k}: not allowed" for k in doc if k not in props]
        for k, v in doc.items():
            if k in props:
                out += schema_problems(v, props[k], f"{where}.{k}")
    if isinstance(doc, list):
        if len(doc) < schema.get("minItems", 0):
            out.append(f"{where}: fewer than {schema['minItems']} items")
        for i, v in enumerate(doc):
            out += schema_problems(v, schema.get("items", {}), f"{where}[{i}]")
    return out


def cli_renaming(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon eval renaming")
    ap.add_argument("--root", default=str(common.ROOT))
    ap.add_argument("--cache", default=None, help="holon's clone cache (default ~/.holon/eval/repos)")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root)
    if a.cache:
        common.REPOS = Path(a.cache)   # every clone of this run (gitfacts' too) lives there
    corpus_path = root / "spec" / "eval" / "corpus.json"
    if not corpus_path.is_file():
        raise common.Refused(f"{corpus_path} is missing")
    entries = common.load_json(corpus_path)["entries"]
    schema = common.load_json(common.LIB / "renaming.schema.json")
    gen = root / "gen" / "eval" / "renaming"
    differs, failed = [], []
    for e in entries:
        try:
            doc = entry_document(e)
        except common.Refused:
            raise
        except Exception as x:   # noqa: BLE001  a failed entry is named, never written
            failed.append(f"{e['id']}: {x}")
            continue
        problems = schema_problems(doc, schema)
        if problems:
            failed.append(f"{e['id']}: the document fails renaming.schema.json: {problems[:5]}")
            continue
        if common.write_or_check(gen / f"{e['id']}.json", common.dumps(doc), a.check):
            differs.append(f"gen/eval/renaming/{e['id']}.json")
        print(f"{e['id']}: renamed {doc['renamed']} of {doc['candidates']} candidates in {len(doc['files'])} files, "
              f"{doc['on_changed_lines']} on changed lines")
    stale = sorted(p for p in gen.glob("*.json") if p.stem not in {e["id"] for e in entries}) if gen.is_dir() else []
    for p in stale:
        differs.append(f"gen/eval/renaming/{p.name} (no such entry)")
        if not a.check:
            p.unlink()
    for x in failed:
        print(f"holon eval renaming: {x}", file=sys.stderr)
    if a.check:
        for x in differs:
            print(f"holon eval renaming --check: {x} differs from a fresh run", file=sys.stderr)
    return 1 if failed or (a.check and differs) else 0
