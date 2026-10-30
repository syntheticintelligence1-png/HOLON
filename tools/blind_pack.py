"""The sealed bundle of BUILD_PLAN I46's blind rerun (I82 = I46a; the contract is rules K1-K9 and L1-L6 of the
docstring of tests_m3/test_blind.py; the protocol is spec/M3/lib/blind_pack.json at the packed commit).

    python tools/blind_pack.py [--root DIR] [--commit C] [--target PATH] --out DIR

Writes DIR/bundle.tar (an uncompressed POSIX tar, byte-identical for a given commit), DIR/manifest.json (every member
with its sha256, what was excluded and by which rule, the whitepaper's redactions, the leak summary) and DIR/leaks.json
(the leak list). The bundle holds:
  target/<p>    every blob of the pinned target commit's tree (gitlinks are listed, not packed);
  tooling/<p>   every blob of commit C under the protocol's include roots and files, less its exclusions;
  tooling/whitepaper.md   C's whitepaper.md with the protocol's sections and "Morph instances" lists removed.
Every byte comes from git objects (never a working tree), every tar header field is fixed and every list is sorted,
so the outputs record neither where nor when they were made.

The leak scan reports pattern matches in the bundle's tooling/ members (the target code is the subject of analysis
and is not scanned): references to the removed sections, case-study ids, target code sites, the hand case study's law
names and the numbers of the removed sections. It filters nothing: a match is reported, not adjudicated.

This tool is not packed (its leak classes are case-study knowledge), and it imports nothing from holon/.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
SIDECAR = "spec/M3/lib/blind_pack.json"
EXTRA_CLASSES = ("law_name", "witness")
NUMBER = re.compile(r"(?<![A-Za-z0-9_.,])(?:\d{1,3}(?:,\d{3})+|\d+)(?![A-Za-z0-9_,]|\.\d)")


class PackError(Exception):
    pass


def dump(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------ git, read-only
def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_NO_REPLACE_OBJECTS="1", LC_ALL="C")
    return env


def git(repo: Path, *args: str) -> bytes:
    p = subprocess.run(["git", "-C", str(repo), "-c", "core.quotepath=off", *args], capture_output=True, env=_env(),
                       stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise PackError(f"git -C {repo} {' '.join(args)}: {p.stderr.decode(errors='replace').strip()}")
    return p.stdout


def tree_entries(repo: Path, rev: str) -> list[tuple[str, str, str, str]]:
    """(path, mode, type, oid) of every entry of rev's tree, recursively."""
    out = []
    for rec in git(repo, "ls-tree", "-r", "-z", "--full-tree", rev).split(b"\0"):
        if not rec:
            continue
        meta, path = rec.split(b"\t", 1)
        mode, kind, oid = meta.decode("ascii").split(" ")
        out.append((path.decode("utf-8"), mode, kind, oid))
    return out


class BlobReader:
    def __init__(self, repo: Path):
        self.proc = subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, env=_env())

    def read(self, oid: str) -> bytes:
        self.proc.stdin.write(oid.encode("ascii") + b"\n")
        self.proc.stdin.flush()
        header = self.proc.stdout.readline().split()
        if len(header) != 3 or header[1] != b"blob":
            raise PackError(f"object {oid} is not a blob")
        data = self.proc.stdout.read(int(header[2]))
        self.proc.stdout.read(1)   # the newline after the content
        return data

    def close(self) -> None:
        self.proc.stdin.close()
        self.proc.wait()


def show(repo: Path, rev: str, path: str) -> bytes:
    return git(repo, "show", f"{rev}:{path}")


# ------------------------------------------------------------------ the whitepaper (K5)
def heading_lines(lines: list[str]) -> list[tuple[int, int]]:
    """(index, level) of every heading line outside fenced code blocks."""
    out, in_fence = [], False
    for i, line in enumerate(lines):
        if line.startswith("```"):
            in_fence = not in_fence
        elif not in_fence and line.startswith("#"):
            out.append((i, len(line) - len(line.lstrip("#"))))
    return out


def section_spans(lines: list[str], entries: list[str]) -> list[tuple[int, int, str]]:
    heads = heading_lines(lines)
    spans = []
    for entry in entries:
        for k, (start, level) in enumerate(heads):
            if not lines[start].startswith(entry):
                continue
            end = len(lines)
            for nxt, nlevel in heads[k + 1:]:
                if nlevel <= level:
                    end = nxt
                    break
            spans.append((start, end, entry))
    return spans


def redact(text: str, sections: list[str], lists: list[str]) -> tuple[str, list[dict], list[str]]:
    """(redacted text, the spans in line order, the removed sections' texts)."""
    lines = text.split("\n")
    gone = set()
    spans = section_spans(lines, sections)
    for start, end, _ in spans:
        gone.update(range(start, end))
    section_texts = ["\n".join(lines[s:e]) for s, e, _ in sorted(spans)]
    for entry in lists:
        for i, line in enumerate(lines):
            if i in gone or line.rstrip() != entry:
                continue
            end = i + 1
            while end < len(lines) and lines[end].strip():
                end += 1
            end = min(end + 1, len(lines))   # the blank line after the list goes with it
            spans.append((i, end, entry))
            gone.update(range(i, end))
    spans.sort()
    kept = "\n".join(line for i, line in enumerate(lines) if i not in gone)
    rows = [{"what": entry, "start": s + 1, "lines": e - s, "sha256": sha256("\n".join(lines[s:e]).encode("utf-8"))}
            for s, e, entry in spans]
    return kept, rows, section_texts


# ------------------------------------------------------------------ the leak scan (L1-L6)
def table_row_names(text: str, heading: str) -> list[str]:
    """The row names of the table under the heading that starts with `heading` (L2)."""
    lines = text.split("\n")
    heads = heading_lines(lines)
    names: list[str] = []
    for k, (start, _) in enumerate(heads):
        if not lines[start].startswith(heading):
            continue
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        rows = [line for line in lines[start + 1:end] if line.startswith("|")][1:]   # less the header line
        for row in rows:
            if re.fullmatch(r"\|(\s*:?-+:?\s*\|)+\s*", row.strip()):
                continue   # the separator line
            first = re.split(r"(?<!\\)\|", row.strip().strip("|"))[0]
            names += [n.strip() for n in re.sub(r"\([^)]*\)", "", first).split(",") if n.strip()]
    return names


def law_names(entries, whitepaper: str, cfg: dict) -> list[str]:
    names = set()
    for d in cfg["from_law_dirs"]:
        for path, _, kind, _ in entries:
            rest = path[len(d):]
            if kind == "blob" and path.startswith(d) and "/" not in rest and fnmatch.fnmatchcase(rest, "L*.json"):
                names.add(rest[:-len(".json")])
    names.update(table_row_names(whitepaper, cfg["from_section"]))
    return sorted(names)


def witness_numbers(section_texts: list[str], min_digits: int) -> list[str]:
    nums = set()
    for text in section_texts:
        for m in NUMBER.finditer(text):
            plain = m.group(0).replace(",", "")
            if len(plain) >= min_digits:
                nums.add(plain)
    return sorted(nums)


def grouped(plain: str) -> str:
    head, tail = plain[:len(plain) % 3 or 3], plain[len(plain) % 3 or 3:]
    return ",".join([head] + [tail[i:i + 3] for i in range(0, len(tail), 3)])


def number_regex(plain: str) -> re.Pattern:
    forms = [grouped(plain), plain] if grouped(plain) != plain else [plain]
    return re.compile(r"(?<![A-Za-z0-9_.,])(?:" + "|".join(map(re.escape, forms)) + r")(?![A-Za-z0-9_,]|\.\d)")


def word_regex(name: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])")


def scan(members: list[tuple[str, bytes, int, str]], cfg: dict, names: list[str], numbers: list[str]) -> dict:
    patterns = {cls: [re.compile(p) for p in pats] for cls, pats in cfg["classes"].items()}
    patterns["law_name"] = [word_regex(n) for n in names]
    patterns["witness"] = [number_regex(n) for n in numbers]
    rule_context = re.compile(cfg["rule_context"])
    width = int(cfg["context_chars"])
    scanned, unscanned, matches = [], [], []
    for path, data, _, kind in members:
        if kind != "file" or not path.startswith(cfg["scan_prefix"]):
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            unscanned.append(path)
            continue
        scanned.append(path)
        for number, line in enumerate(text.split("\n"), 1):
            for cls in sorted(patterns):
                at: dict[int, str] = {}
                for pat in patterns[cls]:
                    for m in pat.finditer(line):
                        if m.start() not in at:
                            at[m.start()] = m.group(0)
                for col in sorted(at):
                    rec = {"path": path, "line": number, "col": col, "class": cls, "match": at[col],
                           "excerpt": line.strip()[:200]}
                    if cls == "case_id":
                        rec["rule_context"] = rule_context.search(line[max(0, col - width):col]) is not None
                    matches.append(rec)
    matches.sort(key=lambda r: (r["path"], r["line"], r["col"], r["class"], r["match"]))
    classes = sorted(patterns)
    by_class = {c: sum(1 for r in matches if r["class"] == c) for c in classes}
    files_by_class = {c: len({r["path"] for r in matches if r["class"] == c}) for c in classes}
    by_root: dict[str, dict[str, int]] = {}
    for r in matches:
        root = "/".join(r["path"].split("/")[:2])
        by_root.setdefault(root, {})
        by_root[root][r["class"]] = by_root[root].get(r["class"], 0) + 1
    return {"scanned": sorted(scanned), "unscanned": sorted(unscanned), "law_names": names, "witness_numbers": numbers,
            "matches": matches, "summary": {"by_class": by_class, "files_by_class": files_by_class,
                                            "by_root": by_root}}


# ------------------------------------------------------------------ the pack
def tar_mode(git_mode: str) -> int:
    return 0o755 if git_mode == "100755" else 0o644


def collect(root: Path, commit: str, target: Path, sc: dict) -> dict:
    """Every member (path, bytes, mode, kind), the exclusions, the redactions and the scan's inputs (K2, K3, K5)."""
    entries = tree_entries(root, commit)
    tooling, tgt = sc["members"]["tooling_prefix"], sc["members"]["target_prefix"]
    members: list[tuple[str, bytes, int, str]] = []
    excluded = {"prefix": [], "basename": [], "path": []}
    sources: dict[str, str] = {}
    reader = BlobReader(root)
    try:
        for path, mode, kind, oid in entries:
            if kind != "blob":
                continue
            if path not in sc["include_files"] and not any(path.startswith(r) for r in sc["include_roots"]):
                continue
            if any(path.startswith(p) for p in sc["exclude_prefixes"]):
                excluded["prefix"].append(path)
            elif any(fnmatch.fnmatchcase(path.rsplit("/", 1)[-1], b) for b in sc["exclude_basenames"]):
                excluded["basename"].append(path)
            elif path in sc["exclude_paths"]:
                excluded["path"].append(path)
            else:
                members.append((tooling + path, reader.read(oid), tar_mode(mode), "symlink" if mode == "120000"
                                else "file"))
                sources[tooling + path] = "holon"
    finally:
        reader.close()
    wp = sc["whitepaper"]
    original = show(root, commit, wp["source"]).decode("utf-8")
    redacted, redactions, removed = redact(original, wp["remove_sections"], wp["remove_lists"])
    members.append((wp["member"], redacted.encode("utf-8"), 0o644, "file"))
    sources[wp["member"]] = "redacted"
    gitlinks = []
    reader = BlobReader(target)
    try:
        for path, mode, kind, oid in tree_entries(target, sc["target"]["commit"]):
            if kind == "commit":
                gitlinks.append(path)
            elif kind == "blob":
                members.append((tgt + path, reader.read(oid), tar_mode(mode), "symlink" if mode == "120000"
                                else "file"))
                sources[tgt + path] = "target"
    finally:
        reader.close()
    members.sort(key=lambda m: m[0].encode("utf-8"))
    names = [m[0] for m in members]
    if len(set(names)) != len(names):
        raise PackError("two members share a path")
    lk = sc["leaks"]
    return {"members": members, "sources": sources,
            "excluded": {"holon": {k: sorted(v) for k, v in excluded.items()}, "target": sorted(gitlinks)},
            "redactions": redactions,
            "law_names": law_names(entries, original, lk["law_names"]),
            "witness_numbers": witness_numbers(removed, int(lk["witness_numbers"]["min_digits"]))}


def write_tar(members: list[tuple[str, bytes, int, str]]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path, data, mode, kind in members:
            info = tarfile.TarInfo(path)
            info.mtime, info.uid, info.gid, info.uname, info.gname, info.mode = 0, 0, 0, "", "", mode
            if kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = data.decode("utf-8")
                tar.addfile(info)
            else:
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def pack(root: Path, commit: str, target: Path | None, out: Path) -> dict:
    root = Path(root).resolve()
    full = git(root, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}").decode().strip()
    try:
        sc_bytes = show(root, full, SIDECAR)
    except PackError:
        raise PackError(f"{SIDECAR} does not exist at {full}") from None
    sc = json.loads(sc_bytes)
    if target is None:
        cfg = json.loads(show(root, full, "config/holon.json"))
        target = Path(cfg["extract"]["sources"][sc["target"]["repo"]])
    target = Path(target)
    tc = sc["target"]["commit"]
    try:
        git(target, "cat-file", "-e", f"{tc}^{{commit}}")
    except PackError:
        raise PackError(f"the target checkout {target} does not hold the pinned commit {tc}") from None
    c = collect(root, full, target, sc)
    tar = write_tar(c["members"])
    leaks = scan(c["members"], sc["leaks"], c["law_names"], c["witness_numbers"])
    manifest = {
        "pack_version": sc["version"],
        "holon": {"commit": full, "tree": git(root, "rev-parse", f"{full}^{{tree}}").decode().strip()},
        "target": {"repo": sc["target"]["repo"], "commit": tc,
                   "tree": git(target, "rev-parse", f"{tc}^{{tree}}").decode().strip()},
        "sidecar": {"path": SIDECAR, "sha256": sha256(sc_bytes)},
        "members": [{"path": p, "size": len(d), "sha256": sha256(d), "mode": mode, "source": c["sources"][p]}
                    for p, d, mode, _ in c["members"]],
        "excluded": c["excluded"],
        "redactions": c["redactions"],
        "leaks": leaks["summary"],
        "bundle": {"sha256": sha256(tar), "size": len(tar), "members": len(c["members"])},
    }
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "bundle.tar").write_bytes(tar)
    (out / "manifest.json").write_text(dump(manifest), encoding="utf-8")
    (out / "leaks.json").write_text(dump(leaks), encoding="utf-8")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tools/blind_pack.py", description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="the repository (default: this checkout)")
    ap.add_argument("--commit", default="HEAD", help="the commit to pack (default HEAD)")
    ap.add_argument("--target", type=Path, help="the target checkout (default: config/holon.json extract.sources)")
    ap.add_argument("--out", type=Path, required=True, help="the output directory")
    a = ap.parse_args(argv)
    try:
        man = pack(a.root, a.commit, a.target, a.out)
    except PackError as e:
        print(f"blind_pack: {e}", file=sys.stderr)
        return 2
    lk = man["leaks"]["by_class"]
    print(f"packed {man['holon']['commit'][:12]}: {man['bundle']['members']} members, bundle sha256 "
          f"{man['bundle']['sha256'][:16]}; leak matches: " + ", ".join(f"{k} {v}" for k, v in sorted(lk.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
