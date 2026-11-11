"""The atomizer (key I55 design A1-A6): NatSpec and Go doc comments of the measured scope and of the intent controls,
cut into sentences, kept when normative, each recorded with its exact source span.

  python -m holon intent atomize [--root DIR] [--out PATH] [--check]

writes results/M5/intent/atoms.json (spec/M5/lib/intent.schema.json#/$defs/atoms_document). It reads the facts
documents at the key's scope_commit and the scope's files through git (holon.intent.scope), and the control sources at
their pinned bytes; nothing else.

Spans. Every kept character of a comment line keeps its column in the raw line. A sentence's pieces are, per line, the
range of columns its characters came from; joining the raw line slices with one space and collapsing whitespace gives
the sentence's text (tests_m5/_i55.span_problems checks this against the file).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .common import CONTROL_REPO, OUT, ROOT, dumps, sha256_bytes
from . import scope as SC

ATOMS_VERSION = "holon-intent-atoms/0.1"
ATOM_MARKERS = ("must", "must not", "shall", "shall not", "should", "should not", "may only", "can only", "may not",
                "cannot", "can not", "never", "always", "only", "at most", "at least", "exactly", "no more than",
                "no less than", "not allowed", "is allowed", "are allowed", "forbidden", "invariant", "enforce",
                "enforces", "enforced", "require", "requires", "required", "ensure", "ensures", "guarantee",
                "guarantees", "revert", "reverts", "reverted")
VERB_MARKERS = frozenset(("revert", "reverts", "reverted", "require", "requires", "required", "ensure", "ensures",
                          "guarantee", "guarantees", "enforce", "enforces", "enforced"))
DETERMINERS = frozenset(("the", "a", "an", "this", "that", "these", "those", "its", "their", "each", "any", "no"))
_MARKER_RX = {m: re.compile(r"(?<![a-z])" + re.escape(m) + r"(?![a-z])") for m in ATOM_MARKERS}
_TAG = re.compile(r"^@[A-Za-z][A-Za-z:-]*")
_GO_DECL = re.compile(r"^\s*(func|type|var|const)\b")
_ABBREV = re.compile(r"(?i)(?:^|[^a-z.])(?:e\.g|i\.e|etc|vs|cf)$")
_SOL_DECL = re.compile(r"^(?:abstract\s+)?(function|modifier|contract|interface|library|event|error|struct|enum|"
                       r"constructor|fallback|receive)\b\s*([A-Za-z_][A-Za-z0-9_]*)?")
_GO_NAME = re.compile(r"^(func|type|var|const)\s+(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)?")


# ------------------------------------------------------------------ A1: comments, with each kept character's column
def _strip(raw: str, a: int, b: int) -> list[tuple[int, str]]:
    """[(column, char)] of raw[a:b] with leading and trailing whitespace removed."""
    while a < b and raw[a].isspace():
        a += 1
    while b > a and raw[b - 1].isspace():
        b -= 1
    return [(k, raw[k]) for k in range(a, b)]


def _sol_comments(lines: list[str]):
    """(first line, last line, [(line number, [(col, ch)])], decl line index or None) per comment."""
    i, n = 0, len(lines)
    while i < n:
        raw = lines[i]
        s = raw.lstrip()
        if s.startswith("///") and not s.startswith("////"):
            body, j = [], i
            while j < n and lines[j].lstrip().startswith("///") and not lines[j].lstrip().startswith("////"):
                r = lines[j]
                a = len(r) - len(r.lstrip()) + 3
                body.append((j + 1, _strip(r, a, len(r))))
                j += 1
            yield i + 1, j, body, _next_decl(lines, j)
            i = j
        elif s.startswith("/**") and not s.startswith("/**/"):
            body, j = [], i
            a = raw.index("/**") + 3
            while True:
                r = lines[j]
                end = r.find("*/", a)
                b = end if end >= 0 else len(r)
                k = a
                while k < b and r[k].isspace():
                    k += 1
                if j > i and k < b and r[k] == "*":
                    k += 1
                body.append((j + 1, _strip(r, k, b)))
                if end >= 0 or j + 1 >= n:
                    break
                j, a = j + 1, 0
            yield i + 1, j + 1, body, _next_decl(lines, j + 1)
            i = j + 1
        else:
            i += 1


def _next_decl(lines: list[str], j: int) -> int | None:
    while j < len(lines):
        s = lines[j].strip()
        if s and not s.startswith("//") and not s.startswith("/*") and not s.startswith("*"):
            return j
        j += 1
    return None


def _go_comments(lines: list[str]):
    i, n = 0, len(lines)
    while i < n:
        if lines[i].lstrip().startswith("//"):
            j = i
            while j < n and lines[j].lstrip().startswith("//"):
                j += 1
            if j < n and _GO_DECL.match(lines[j]):
                body = []
                for k in range(i, j):
                    r = lines[k]
                    a = len(r) - len(r.lstrip()) + 2
                    body.append((k + 1, _strip(r, a, len(r))))
                yield i + 1, j, body, j
            i = j
        else:
            i += 1


def _decl(path: str, lines: list[str], idx: int | None):
    if idx is None:
        return None
    text = lines[idx].strip()
    if path.endswith(".go"):
        m = _GO_NAME.match(text)
        return {"line": idx + 1, "kind": m.group(1) if m else "other", "name": (m.group(2) if m else None), "text": text}
    m = _SOL_DECL.match(text)
    if not m:
        return {"line": idx + 1, "kind": "other", "name": None, "text": text}
    kind = m.group(1)
    name = kind if kind in ("constructor", "fallback", "receive") else m.group(2)
    return {"line": idx + 1, "kind": kind, "name": name, "text": text}


# ------------------------------------------------------------------ A2, A3: segments and sentences
def _segments(body):
    """[(tag, [(line, col, ch) or (None, None, ' ')])] with whitespace collapsed and ends stripped."""
    segs, cur, tag = [], [], None
    for ln, chars in body:
        text = "".join(c for _, c in chars)
        if not text:
            if cur:
                segs.append((tag, cur))
            cur, tag = [], None
            continue
        m = _TAG.match(text)
        if m and cur:
            segs.append((tag, cur))
            cur = []
        if not cur:
            tag = m.group(0) if m else None
        if cur:
            cur.append((None, None, " "))
        cur.extend((ln, col, c) for col, c in chars)
    if cur:
        segs.append((tag, cur))
    out = []
    for tag, cs in segs:
        col = []
        for x in cs:
            if x[2].isspace():
                if col and not col[-1][2].isspace():
                    col.append((x[0], x[1], " "))
            else:
                col.append(x)
        while col and col[-1][2] == " ":
            col.pop()
        out.append((tag, col))
    return out


def _sentences(chars):
    """Cut a segment's characters after '.', ';', '!' or '?' followed by whitespace or the end (A3)."""
    text = "".join(c for _, _, c in chars)
    cuts, start = [], 0
    for k, ch in enumerate(text):
        if ch in ".;!?" and (k + 1 == len(text) or text[k + 1].isspace()):
            if ch == "." and _ABBREV.search(text[start:k]):
                continue
            cuts.append((start, k + 1))
            start = k + 1
    if start < len(text):
        cuts.append((start, len(text)))
    out = []
    for a, b in cuts:
        while a < b and text[a].isspace():
            a += 1
        if a < b:
            out.append(chars[a:b])
    return out


# ------------------------------------------------------------------ A4: normative
def markers(sentence: str) -> list[str]:
    low = sentence.lower()
    out = []
    for m in ATOM_MARKERS:
        for hit in _MARKER_RX[m].finditer(low):
            if m in VERB_MARKERS:
                before = re.findall(r"[a-z]+", low[:hit.start()])
                if before and before[-1] in DETERMINERS:
                    continue
            out.append(m)
            break
    return sorted(out)


# ------------------------------------------------------------------ A5: records
def _pieces(chars) -> list[list[int]]:
    by: dict = {}
    for ln, col, _ in chars:
        if ln is None:
            continue
        lo, hi = by.get(ln, (col, col))
        by[ln] = (min(lo, col), max(hi, col))
    return [[ln, lo, hi + 1] for ln, (lo, hi) in sorted(by.items())]


def atoms_of(repo: str, commit, path: str, text: str, control=None) -> list[dict]:
    lines = text.split("\n")
    comments = _go_comments(lines) if path.endswith(".go") else _sol_comments(lines)
    out = []
    for _first, _last, body, decl_idx in comments:
        decl = _decl(path, lines, decl_idx)
        for tag, seg in _segments(body):
            for k, sent in enumerate(_sentences(seg)):
                s = "".join(c for _, _, c in sent)
                ms = markers(s)
                if not ms:
                    continue
                pieces = _pieces(sent)
                first = pieces[0][0]
                aid = sha256_bytes(f"{repo}:{path}:{first}:{k}:{s}".encode("utf-8"))[:16]
                out.append({"id": aid, "repo": repo, "commit": commit, "file": path,
                            "lines": [pieces[0][0], pieces[-1][0]], "text": s, "tag": tag, "pieces": pieces,
                            "sentence": k, "decl": decl, "markers": ms, "control": control})
    return out


def document(root: Path) -> dict:
    scope, files = SC.target_files(root)
    atoms = []
    for (repo, path), text in sorted(files.items()):
        atoms += atoms_of(repo, scope[repo]["commit"], path, text)
    ctl = []
    for cid, (rel, text) in sorted(SC.control_files(root).items()):
        ctl += atoms_of(CONTROL_REPO, None, rel, text, cid)
    key = lambda a: (a["file"], a["lines"], a["id"])  # noqa: E731
    return {"atoms_version": ATOMS_VERSION, "scope_commit": SC.scope_commit(root), "scope": scope,
            "atoms": sorted(atoms, key=key), "controls": sorted(ctl, key=key)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="holon intent atomize")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = a.root.resolve()
    out = a.out or root / OUT / "atoms.json"
    text = dumps(document(root))
    if a.check:
        ok = out.is_file() and out.read_text(encoding="utf-8") == text
        print(f"intent atomize: {'CHECK OK' if ok else 'CHECK FAILED: ' + str(out) + ' differs'}")
        return 0 if ok else 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"intent atomize: wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
