"""python -m holon eval rename / unrename (I48 rules N0-N3): the isomorphic renaming tool (contamination mitigation,
whitepaper §13). An agent that might recognise a public defect by its names reads the renamed files instead.

  rename   --root DIR --files F [F ...] --seed S --out DIR2 --map MAP
  unrename --root DIR2 --map MAP --out DIR3

Rule N1 fixes exactly which identifiers are renamed. One map per set, applied to every identifier token of every file
of the set (never inside a string, character literal or comment). A name is renamed iff
  (a) a file of the set declares it (Go: goscan's declared identifiers; Solidity: the declarations of solc's
      parse-only AST), and it holds no dot;
  (b) it is reserved for no language of the set (spec/M4/lib/rename_reserved.json, with the package-clause names of
      the set's Go files and, in its Go files that import "C", every C.X selector name);
  (c) Go in the set: it is not exported and no other file of a directory holding a .go file of the set holds it as a
      word; Solidity in the set: it is not ABI-visible, names no override, and no other .sol file under DIR holds it;
  (d) no string or character literal value of the set and no kept comment holds it as a word;
  (e) no .sol file of the set that the pinned solc cannot parse holds it as a word.
New names: v (V for an upper-case initial) and the first 10 hex digits of sha256(seed:old), lengthened until the name
is no word of DIR and no other new name. Every comment is removed into the map (a line comment becomes nothing, a
block comment holding a newline one newline, any other one space) except the kept ones: Go directives and the cgo
preamble, Solidity comments holding @solidity or @custom:.

rename checks its own output before it returns (rule N3 by the tool's own readers: the Go token stream, the Solidity
token stream and solc's AST under the map); the independent check is the instrument's.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from . import common, golang, solidity

MAP_VERSION = "holon-rename/0.1"


# ------------------------------------------------------------------------------------------------- words and names
_ASCII_WORD = re.compile(rb"[A-Za-z0-9_$]+")
_RUN = re.compile(r"[\w$]+")


def _word_char(c: str) -> bool:
    cat = unicodedata.category(c)
    return c == "_" or c == "$" or cat[0] == "L" or cat == "Nd"


def words(data: bytes) -> set[str]:
    """Rule N1's words of some bytes: every maximal run of [A-Za-z0-9_$] in the bytes, and every maximal run of
    characters that are _, $, a Unicode letter (L*) or a decimal digit (Nd) in their UTF-8 decoding (errors
    replaced)."""
    out = {w.decode("ascii") for w in _ASCII_WORD.findall(data)}
    if data.isascii():
        return out
    for run in _RUN.findall(data.decode("utf-8", errors="replace")):
        if run.isascii():
            out.add(run)
            continue
        piece = []
        for c in run:
            if _word_char(c):
                piece.append(c)
            elif piece:
                out.add("".join(piece))
                piece = []
        if piece:
            out.add("".join(piece))
    return out


def upper_initial(name: str) -> bool:
    """The first character is an upper-case letter (Unicode category Lu): exported in Go, and renamed to V..."""
    return bool(name) and unicodedata.category(name[0]) == "Lu"


def new_names(seed: str, olds, tree_words: set[str]) -> dict[str, str]:
    """The new name of each old one, given in sorted order: v or V, then sha256(seed:old)'s hex digits, 10 at first,
    one more while the name is a word of the tree or already given."""
    out: dict[str, str] = {}
    given: set[str] = set()
    for old in sorted(olds):
        digest = hashlib.sha256(f"{seed}:{old}".encode("utf-8")).hexdigest()
        prefix = "V" if upper_initial(old) else "v"
        for k in range(10, len(digest) + 1):
            name = prefix + digest[:k]
            if name not in tree_words and name not in given:
                break
        else:
            raise RuntimeError(f"no free new name for {old!r}")
        out[old] = name
        given.add(name)
    return out


def replaced_by(text: bytes) -> bytes:
    """What a removed comment becomes: nothing for a line comment, a newline for a block comment holding one, else a
    space."""
    if text.startswith(b"//"):
        return b""
    return b"\n" if b"\n" in text else b" "


def reserved(langs, package_names=(), cgo_names=()) -> tuple[set, list]:
    """Rule N1 (b): the reserved names and patterns of the set's languages."""
    r = common.load_json(common.LIB / "rename_reserved.json")
    names, pats = set(), []
    for lang in sorted(langs):
        names.update(r[lang]["names"])
        pats.extend(r[lang]["patterns"])
    if "go" in langs:
        if r["go"].get("package_clause_names"):
            names.update(package_names)
        if r["go"].get("cgo_selector_names"):
            names.update(cgo_names)
    return names, [re.compile(p) for p in pats]


def is_reserved(name: str, names: set, pats: list) -> bool:
    return name in names or any(p.fullmatch(name) for p in pats)


def tree_files(root: Path) -> list[str]:
    """Every regular file under root (a symlink counts when it leads to a file; a linked directory is not entered),
    as sorted posix paths relative to root, anything under a .git aside."""
    root = Path(root)
    out = []
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x != ".git"]
        for n in names:
            p = Path(d) / n
            if n != ".git" and p.is_file():
                out.append(p.relative_to(root).as_posix())
    return sorted(out)


# ------------------------------------------------------------------------------------------------- one set's facts
@dataclass
class FileFacts:
    path: str
    language: str
    data: bytes
    idents: list = field(default_factory=list)      # (start, end, name): every identifier token
    declared: set = field(default_factory=set)
    abi: set = field(default_factory=set)
    override: set = field(default_factory=set)
    string_words: set = field(default_factory=set)
    kept_words: set = field(default_factory=set)
    comments: list = field(default_factory=list)    # (start, end, kept)
    parsed: bool = True                             # Solidity: solc parsed it (rule N1 (e))
    ast: object = None                              # Solidity: the parse-only AST
    package: str | None = None                      # Go: the package clause
    cgo: set = field(default_factory=set)           # Go: C.X selector names when the file imports "C"


def language_of(path: str, proto: dict) -> str | None:
    for lang, exts in proto["frontend_extensions"].items():
        if any(path.endswith(e) for e in exts):
            return lang
    return None


def _go_facts(root: Path, paths: list[str]) -> dict[str, FileFacts]:
    out = {}
    for path, g in zip(paths, golang.facts([root / p for p in paths])):
        if not g["ok"]:
            raise common.Refused(f"{path} does not parse with go/parser: {g['error'][:300]}")
        data = (root / path).read_bytes()
        f = FileFacts(path, "go", data, package=g["package"], cgo=set(g["cgo"]))
        for off, name, decl in g["idents"]:
            raw = name.encode("utf-8")
            if data[off:off + len(raw)] != raw:
                raise RuntimeError(f"{path}: identifier {name!r} is not at byte {off}")
            f.idents.append((off, off + len(raw), name))
            if decl:
                f.declared.add(name)
        for _, value in g["literals"]:
            f.string_words |= words(value.encode("utf-8", errors="replace"))
        for text in g["kept_texts"]:
            f.kept_words |= words(text.encode("utf-8", errors="replace"))
        for off, end, text, kept in g["comments"]:
            if data[off:end].replace(b"\r", b"") != text.encode("utf-8").replace(b"\r", b""):
                raise RuntimeError(f"{path}: comment at byte {off} is not the scanner's")
            f.comments.append((off, end, kept))
        out[path] = f
    return out


def _sol_facts(root: Path, paths: list[str]) -> dict[str, FileFacts]:
    exe = solidity.require_solc() if paths else None
    out = {}
    for path in paths:
        data = (root / path).read_bytes()
        f = FileFacts(path, "solidity", data)
        for kind, s, e in solidity.lex(data):
            if kind == "id":
                f.idents.append((s, e, data[s:e].decode("ascii")))
            elif kind == "str":
                f.string_words |= words(solidity.literal_value(data[s:e]).encode("utf-8", errors="surrogateescape"))
            elif kind == "comment":
                kept = solidity.kept_comment(data[s:e])
                f.comments.append((s, e, kept))
                if kept:
                    f.kept_words |= words(data[s:e])
        f.ast = solidity.parse(data, exe)
        f.parsed = f.ast is not None
        if f.parsed:
            names = solidity.ast_names(f.ast)
            f.declared, f.abi, f.override = names["decls"], names["abi"], names["override"]
        out[path] = f
    return out


@dataclass
class SetFacts:
    root: Path
    files: dict            # path -> FileFacts, in the given order
    langs: list
    reserved: tuple
    tree_words: set
    blocked: set
    renamed: set           # rule N1's set
    candidates: int        # distinct identifier tokens of the set that are not reserved
    unparsed: list         # .sol files of the set solc cannot parse


def check_set(root: Path, files: list[str], proto: dict | None = None) -> None:
    """The set is renameable: relative posix paths to distinct files under root, each Go or Solidity."""
    proto = proto or common.protocol()
    if not files:
        raise common.Refused("no files given")
    if len(set(files)) != len(files):
        raise common.Refused("a file is given twice")
    for f in files:
        p = PurePosixPath(f)
        if p.is_absolute() or ".." in p.parts or p.as_posix() != f or f.startswith("./") or "\\" in f:
            raise common.Refused(f"{f}: not a normalised path relative to --root")
        if not (Path(root) / f).is_file():
            raise common.Refused(f"{f}: no such file under {root}")
        if language_of(f, proto) is None:
            raise common.Refused(f"{f}: a language outside go and solidity")


def set_facts(root: Path, files: list[str]) -> SetFacts:
    """Rule N1 on one set: every file's facts, the reserved names, the blocking words and the renamed set."""
    root = Path(root)
    proto = common.protocol()
    check_set(root, files, proto)
    langs = sorted({language_of(f, proto) for f in files})
    go_files = [f for f in files if language_of(f, proto) == "go"]
    sol_files = [f for f in files if language_of(f, proto) == "solidity"]
    if sol_files:
        solidity.require_solc()   # refuse before any work
    per = {**_go_facts(root, go_files), **_sol_facts(root, sol_files)}
    per = {f: per[f] for f in files}
    packages = {f.package for f in per.values() if f.language == "go"}
    cgo = set().union(*[f.cgo for f in per.values()])
    names, pats = reserved(langs, packages, cgo)

    every = tree_files(root)
    cache: dict[str, set] = {}

    def wds(p: str) -> set:
        if p not in cache:
            cache[p] = words((root / p).read_bytes())
        return cache[p]
    in_set = set(files)
    go_dirs = {PurePosixPath(f).parent.as_posix() for f in go_files}
    others = [x for x in every if x not in in_set
              and (PurePosixPath(x).parent.as_posix() in go_dirs or ("solidity" in langs and x.endswith(".sol")))]
    unparsed = sorted(f for f in sol_files if not per[f].parsed)
    blocked = set().union(*[wds(x) for x in others + unparsed])
    tree_words = set().union(*[wds(x) for x in every])

    def union(attr: str) -> set:
        return set().union(*[getattr(f, attr) for f in per.values()])
    off = union("abi") | union("override") | union("string_words") | union("kept_words") | blocked
    go_in = "go" in langs
    renamed = {x for x in union("declared")
               if "." not in x and not is_reserved(x, names, pats) and x not in off
               and not (go_in and upper_initial(x))}
    tokens = {name for f in per.values() for _, _, name in f.idents}
    candidates = len({x for x in tokens if not is_reserved(x, names, pats)})
    return SetFacts(root, per, langs, (names, pats), tree_words, blocked, renamed, candidates, unparsed)


# ------------------------------------------------------------------------------------------------- rename
def _apply(data: bytes, edits: list[tuple[int, int, bytes]]) -> bytes:
    out, last = [], 0
    for s, e, new in sorted(edits):
        if s < last:
            raise RuntimeError(f"overlapping edits at byte {s}")
        out += [data[last:s], new]
        last = e
    out.append(data[last:])
    return b"".join(out)


def renamed_file(f: FileFacts, idmap: dict[str, str]) -> tuple[bytes, list[dict]]:
    """One file's renamed bytes and its removed comments (map records)."""
    edits = [(s, e, idmap[name].encode("ascii")) for s, e, name in f.idents if name in idmap]
    removed = []
    for s, e, kept in f.comments:
        if kept:
            continue
        text = f.data[s:e]
        rep = replaced_by(text)
        edits.append((s, e, rep))
        removed.append({"path": f.path, "offset": s, "text": text.decode("utf-8", errors="surrogateescape"),
                        "replaced_by": rep.decode("ascii")})
    return _apply(f.data, edits), removed


def rename(root, files: list[str], seed: str, out, map_path, verify: bool = True) -> tuple[dict, SetFacts]:
    """Rename the set: write the renamed files under out (same relative paths) and the map at map_path. Returns the
    map and the set's facts. With verify, the renamed files are checked (rule N3, by the tool's own readers) and a
    failure raises."""
    root, out, map_path = Path(root), Path(out), Path(map_path)
    if not root.is_dir():
        raise common.Refused(f"--root {root} is not a directory")
    if out.resolve() == root.resolve():
        raise common.Refused("--out must differ from --root")
    sf = set_facts(root, files)
    idmap = new_names(seed, sf.renamed, sf.tree_words)
    records, comments, outputs = [], [], {}
    for path in sorted(files):
        data, removed = renamed_file(sf.files[path], idmap)
        outputs[path] = data
        comments += removed
        records.append({"path": path, "language": sf.files[path].language,
                        "sha256": common.sha256_bytes(sf.files[path].data), "renamed_sha256": common.sha256_bytes(data)})
    for path, data in outputs.items():
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    m = {"map_version": MAP_VERSION, "seed": seed, "files": records, "identifiers": dict(sorted(idmap.items())),
         "comments": sorted(comments, key=lambda c: (c["path"], c["offset"]))}
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(common.dumps(m), encoding="utf-8")
    if verify:
        problems = isomorphism_problems(sf, out, idmap)
        if problems:
            raise RuntimeError("the renamed files fail the tool's own isomorphism check: " + "; ".join(problems[:10]))
    return m, sf


def rename_files(root, files, seed, out, map_path) -> dict:
    """Library entry: rename the set (as the rename command does) and return the map."""
    return rename(root, list(files), seed, out, map_path)[0]


# ------------------------------------------------------------------------------------------------- self-check (N3)
def isomorphism_problems(sf: SetFacts, out: Path, idmap: dict[str, str]) -> list[str]:
    """The tool's own rule N3 check of renamed files (not the instrument's): Go: both files scan and parse and the
    renamed token stream (automatic semicolons and kept comments in place) is the original's under the map, with the
    same cgo preamble; Solidity: the token streams (kept comments in place) agree under the map, solc parses both or
    neither, and when both parse their ASTs agree under the map (positions, ids, references and comments aside)."""
    problems = []
    go = [p for p, f in sf.files.items() if f.language == "go"]
    if go:
        before = golang.tokens([sf.root / p for p in go])
        after = golang.tokens([out / p for p in go])
        for p, a, b in zip(go, before, after):
            if not (a["ok"] and b["ok"]):
                problems.append(f"{p}: does not parse after renaming")
                continue
            mapped = [[t, idmap.get(lit, lit) if t == "IDENT" else lit] for t, lit in a["tokens"]]
            if mapped != b["tokens"] or a["preamble"] != b["preamble"]:
                problems.append(f"{p}: token stream differs under the map")
    for p, f in sf.files.items():
        if f.language != "solidity":
            continue
        new = (out / p).read_bytes()
        if _sol_stream(f.data, idmap) != _sol_stream(new, {}):
            problems.append(f"{p}: token stream differs under the map")
        tree = solidity.parse(new)
        if (tree is None) != (f.ast is None):
            problems.append(f"{p}: solc parses only one of the original and the renamed file")
        elif tree is not None and solidity.normal_ast(f.ast, idmap) != solidity.normal_ast(tree):
            problems.append(f"{p}: solc's AST differs under the map")
    return problems


def _sol_stream(data: bytes, idmap: dict) -> list[tuple[str, bytes]]:
    out = []
    for kind, s, e in solidity.lex(data):
        text = data[s:e]
        if kind == "comment" and not solidity.kept_comment(text):
            continue
        if kind == "id":
            name = text.decode("ascii")
            text = idmap.get(name, name).encode("ascii")
        out.append((kind, text))
    return out


# ------------------------------------------------------------------------------------------------- unrename
def _identifier_spans(path: str, language: str, data: bytes, at: Path) -> list[tuple[int, int, str]]:
    if language == "go":
        g = golang.facts([at])[0]
        if not g["ok"]:
            raise common.Refused(f"{path}: the renamed file does not parse with go/parser")
        return [(off, off + len(name.encode("utf-8")), name) for off, name, _ in g["idents"]]
    return [(s, e, data[s:e].decode("ascii")) for kind, s, e in solidity.lex(data) if kind == "id"]


def restore(data: bytes, spans: list[tuple[int, int, str]], inverse: dict[str, str], comments: list[dict]) -> bytes:
    """The original bytes from a renamed file: each identifier whose name is a new name of the map gets its old name
    back, and each removed comment goes back at its original offset in place of what replaced it."""
    ids = sorted((s, e, inverse[n].encode("utf-8")) for s, e, n in spans if n in inverse)
    cs = sorted(comments, key=lambda c: c["offset"])
    out, r, i, j = bytearray(), 0, 0, 0
    while i < len(ids) or j < len(cs):
        id_at = ids[i][0] if i < len(ids) else None
        c_at = r + (cs[j]["offset"] - len(out)) if j < len(cs) else None
        if c_at is not None and c_at < r:
            raise common.Refused(f"the map's comment at {cs[j]['offset']} falls inside an identifier")
        if c_at is not None and (id_at is None or c_at <= id_at):
            rep = cs[j]["replaced_by"].encode("ascii")
            out += data[r:c_at]
            if data[c_at:c_at + len(rep)] != rep:
                raise common.Refused(f"the renamed file does not hold the comment's replacement at {c_at}")
            out += cs[j]["text"].encode("utf-8", errors="surrogateescape")
            r = c_at + len(rep)
            j += 1
        else:
            s, e, old = ids[i]
            out += data[r:s]
            out += old
            r = e
            i += 1
    out += data[r:]
    return bytes(out)


def unrename(root, map_path, out) -> list[str]:
    """Give back the original files of a map from its renamed ones under root, written under out (same relative
    paths). Every renamed file must have the map's renamed_sha256 and every restored one its sha256."""
    root, out = Path(root), Path(out)
    m = common.load_json(map_path)
    if m.get("map_version") != MAP_VERSION:
        raise common.Refused(f"{map_path} is not a {MAP_VERSION} map")
    ids = m["identifiers"]
    inverse = {new: old for old, new in ids.items()}
    if len(inverse) != len(ids):
        raise common.Refused("the map gives two names the same new name")
    restored = {}
    for rec in m["files"]:
        path = rec["path"]
        check_set(root, [path])
        at = root / path
        data = at.read_bytes()
        if common.sha256_bytes(data) != rec["renamed_sha256"]:
            raise common.Refused(f"{path}: not the renamed file the map records (sha256 differs)")
        spans = _identifier_spans(path, rec["language"], data, at)
        original = restore(data, spans, inverse, [c for c in m["comments"] if c["path"] == path])
        if common.sha256_bytes(original) != rec["sha256"]:
            raise common.Refused(f"{path}: the restored file is not the original (sha256 differs)")
        restored[path] = original
    for path, data in restored.items():
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return sorted(restored)


# ------------------------------------------------------------------------------------------------- CLI
def cli_rename(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon eval rename")
    ap.add_argument("--root", required=True)
    ap.add_argument("--files", required=True, nargs="+")
    ap.add_argument("--seed", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--map", required=True)
    a = ap.parse_args(argv)
    m, sf = rename(a.root, a.files, a.seed, a.out, a.map)
    print(f"renamed {len(m['identifiers'])} of {sf.candidates} candidate identifiers in {len(m['files'])} files, "
          f"removed {len(m['comments'])} comments; map {a.map}")
    return 0


def cli_unrename(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon eval unrename")
    ap.add_argument("--root", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if not Path(a.map).is_file():
        raise common.Refused(f"--map {a.map}: no such file")
    done = unrename(a.root, a.map, a.out)
    print(f"restored {len(done)} files under {a.out}")
    return 0
