"""The scope set of BUILD_PLAN I46's blind rerun: the extraction-scope sidecars the blind session is given beside the
sealed bundle of tools/blind_pack.py, each with every member that could carry an outcome stripped.

    python tests_m3/blind_scope.py [--root DIR] [--commit C] [--protocol FILE] --out DIR

The protocol is the "scope" section of FILE (default: spec/M3/lib/blind_rerun.json of the working tree, I46's prereg
sidecar). The files and the leak classes are read from git objects of commit C:
  files    every blob of C that matches one of the protocol's globs, sorted by path;
  strip    a member of a JSON object is removed when
             its key matches the protocol's key pattern,
             a string in it, or a key under it, has the form of a statement or record hash (the protocol's pattern), or
             a scalar in it, or a key under it, matches a leak class of tools/blind_pack.py's protocol
             (spec/M3/lib/blind_pack.json at C: every class, the law names and the numbers of the removed whitepaper
             sections included, in rule context or not);
           an object is entered and stripped member by member, and a list or a scalar is removed whole, so a member is
           removed at the smallest object member that holds the match. A file whose top level is not an object, or
           that does not parse, is withheld whole;
  output   DIR/files/<path>: the source bytes when nothing is stripped, otherwise the stripped document (JSON, indent 2,
           the source's member order, a final newline);
           DIR/stripped.json: {path: [stripped key paths]}, which the blind session is given with the files;
           DIR/scope.json: the commit, the protocol's sha256, and per file its source and output sha256 and each
           stripped member's key path with the reasons (not given to the blind session: the reasons name leak classes).
A key path joins object keys with "/". Every byte comes from git objects of C, every list is sorted, and nothing
records a time or a machine path, so one commit gives the same bytes. It imports nothing from holon/. It lives
beside the tests because it is part of I46's prereg (a prereg input, fixed at C_K), and is never packed.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import blind_pack  # noqa: E402  (tools/blind_pack.py: the pack's git readers and leak classes; imports nothing from holon/)

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "spec/M3/lib/blind_rerun.json"


class ScopeError(Exception):
    pass


def dump(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def leak_patterns(root: Path, commit: str) -> dict:
    """{class: [compiled patterns]} of the pack protocol at commit: its classes, its law names and its numbers."""
    sc = json.loads(blind_pack.show(root, commit, blind_pack.SIDECAR))
    lk, wp = sc["leaks"], sc["whitepaper"]
    original = blind_pack.show(root, commit, wp["source"]).decode("utf-8")
    _, _, removed = blind_pack.redact(original, wp["remove_sections"], wp["remove_lists"])
    entries = blind_pack.tree_entries(root, commit)
    pats = {cls: [re.compile(p) for p in ps] for cls, ps in lk["classes"].items()}
    pats["law_name"] = [blind_pack.word_regex(n) for n in blind_pack.law_names(entries, original, lk["law_names"])]
    pats["witness"] = [blind_pack.number_regex(n) for n in
                       blind_pack.witness_numbers(removed, int(lk["witness_numbers"]["min_digits"]))]
    return pats


def _scalars(v):
    """Every scalar under v, and every key under it, as text (bools and nulls carry no text)."""
    if isinstance(v, dict):
        for k, x in v.items():
            yield k
            yield from _scalars(x)
    elif isinstance(v, list):
        for x in v:
            yield from _scalars(x)
    elif isinstance(v, str):
        yield v
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        yield json.dumps(v)


def reasons_of(key: str, value, key_re, hash_re, leaks: dict) -> list[str]:
    out = []
    if key_re.search(key):
        out.append("key")
    texts = [key] + list(_scalars(value)) if not isinstance(value, dict) else [key]
    if any(hash_re.search(t) for t in texts):
        out.append("hash")
    for cls in sorted(leaks):
        if any(p.search(t) for p in leaks[cls] for t in texts):
            out.append(f"leak:{cls}")
    return out


def strip(doc: dict, key_re, hash_re, leaks: dict, at: str = "") -> tuple[dict, list[dict]]:
    kept, removed = {}, []
    for k, v in doc.items():
        path = f"{at}/{k}" if at else k
        why = reasons_of(k, v, key_re, hash_re, leaks)
        if why:
            removed.append({"key": path, "reasons": why})
        elif isinstance(v, dict):
            sub, rem = strip(v, key_re, hash_re, leaks, path)
            kept[k] = sub
            removed += rem
        else:
            kept[k] = v
    return kept, removed


def scope(root: Path, commit: str, protocol: dict, protocol_sha: str) -> tuple[dict, dict, dict]:
    """({path: output bytes}, stripped.json's document, scope.json's document)."""
    sc = protocol["scope"]
    key_re, hash_re = re.compile(sc["strip_key_pattern"]), re.compile(sc["strip_hash_pattern"])
    leaks = leak_patterns(root, commit)
    paths = sorted(p for p, _, kind, _ in blind_pack.tree_entries(root, commit)
                   if kind == "blob" and any(fnmatch.fnmatchcase(p, g) for g in sc["files"]))
    outputs, given, files = {}, {}, []
    for p in paths:
        src = blind_pack.show(root, commit, p)
        rec = {"path": p, "source_sha256": sha256(src)}
        try:
            doc = json.loads(src.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            doc = None
        if not isinstance(doc, dict):
            rec.update({"withheld": "not a JSON object"})
            files.append(rec)
            continue
        kept, removed = strip(doc, key_re, hash_re, leaks)
        out = src if not removed else (json.dumps(kept, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        outputs[p] = out
        given[p] = [r["key"] for r in removed]
        rec.update({"sha256": sha256(out), "stripped": removed})
        files.append(rec)
    doc = {"commit": commit, "protocol": {"path": PROTOCOL, "sha256": protocol_sha}, "files": files,
           "leak_classes": sorted(leaks)}
    return outputs, given, doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="blind_scope.py", description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="the repository (default: this checkout)")
    ap.add_argument("--commit", default="HEAD", help="the packed commit (default HEAD)")
    ap.add_argument("--protocol", type=Path, help=f"the protocol (default: {PROTOCOL} of the working tree)")
    ap.add_argument("--out", type=Path, required=True, help="the output directory (created; must be empty)")
    a = ap.parse_args(argv)
    try:
        commit = blind_pack.git(a.root, "rev-parse", "--verify", f"{a.commit}^{{commit}}").decode().strip()
        pb = (a.protocol or (a.root / PROTOCOL)).read_bytes()
        outputs, given, doc = scope(a.root, commit, json.loads(pb), sha256(pb))
    except (blind_pack.PackError, ScopeError, OSError, KeyError, ValueError) as e:
        print(f"blind_scope: {e}", file=sys.stderr)
        return 2
    if a.out.exists() and any(a.out.iterdir()):
        print(f"blind_scope: {a.out} is not empty", file=sys.stderr)
        return 2
    for p, b in sorted(outputs.items()):
        (a.out / "files" / p).parent.mkdir(parents=True, exist_ok=True)
        (a.out / "files" / p).write_bytes(b)
    (a.out / "stripped.json").write_text(dump(given), encoding="utf-8")
    (a.out / "scope.json").write_text(dump(doc), encoding="utf-8")
    n = sum(len(v) for v in given.values())
    print(f"blind_scope: {len(outputs)} files given, {n} members stripped, "
          f"{sum(1 for f in doc['files'] if 'withheld' in f)} withheld; commit {commit[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
