"""I82 instrument (the contract is the docstring of tests_m3/test_blind.py). Independent of holon/: it imports nothing
from holon, reads git objects, committed files and the tools' outputs, and recomputes what the contract says those
outputs must be. Written at the prereg, before tools/blind_pack.py, holon/report.py and holon/blind.py exist; its
sha256 is pinned in the key I82 of spec/M3/predictions.json.

The one place it runs holon is the closure check of rule R (closure_and_naming_problems): the contract defines the
generator closures by holon's own functions, so it asks holon for them in a subprocess at HEAD.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = "I82"
PACK_SIDECAR = "spec/M3/lib/blind_pack.json"
MAP_SIDECAR = "spec/M3/lib/appendixA.json"
PREDICTIONS = "spec/M3/predictions.json"
DRY_RUN_MILESTONES = ("M0", "M1", "M3")
SECTION_ENTRIES = ("## 2 ", "## 11 ", "## Appendix A.", "## Appendix B.")
LIST_ENTRY = "**Morph instances:**"
DECIDED = ("PROVED", "REFUTED", "checked", "failed")
NO_RECORD = "no record"
SOURCE_ORDER = ("sidecar", "maps_to", "ledger", "name", "backtest")
ALLOWED_FILES = ("tools/blind_pack.py", "holon/report.py", "holon/blind.py", "holon/__main__.py", "holon/gate.py",
                 "spec/M3/appendixA_map.json", "docs/M3_COMPARISON.md", "docs/iterations/I82.md",
                 "tests_m3/test_blind.py")
ALLOWED_PREFIXES = ("audit/blind/",)
FORBIDDEN_PREFIXES = ("facts/", "spec/", "laws/", "gen/", "results/", "replay/", "docs/", "prompts/", "tests/", "audit/")
FORBIDDEN_BASENAMES = ("maps_to*.json", "*maps_to*", "policy_hints.mjs")


# ================================================================== basics
def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p) -> str:
    return sha256_bytes(Path(p).read_bytes())


def _env() -> dict:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(root, *args, binary=False):
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, env=_env())
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.decode(errors='replace').strip()}")
    return p.stdout if binary else p.stdout.decode("utf-8")


def ls_tree(root, rev) -> list[tuple[str, str, str, str]]:
    out = git(root, "ls-tree", "-r", "-z", "--full-tree", rev, binary=True)
    rows = []
    for rec in out.split(b"\0"):
        if rec:
            meta, path = rec.split(b"\t", 1)
            mode, typ, oid = meta.decode().split()
            rows.append((path.decode("utf-8"), mode, typ, oid))
    return rows


class Blobs:
    """git cat-file --batch over one repository."""

    def __init__(self, root):
        self.p = subprocess.Popen(["git", "-C", str(root), "cat-file", "--batch"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, env=_env())

    def get(self, oid: str) -> bytes:
        self.p.stdin.write(oid.encode() + b"\n")
        self.p.stdin.flush()
        head = self.p.stdout.readline().split()
        if len(head) < 3 or head[1] != b"blob":
            raise RuntimeError(f"not a blob: {oid} {head}")
        data = self.p.stdout.read(int(head[2]))
        self.p.stdout.read(1)
        return data

    def close(self):
        self.p.stdin.close()
        self.p.wait()


def show(root, rev, path) -> bytes:
    return git(root, "show", f"{rev}:{path}", binary=True)


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ================================================================== the pack (K1-K9)
def pack_sidecar(root, commit) -> dict:
    return json.loads(show(root, commit, PACK_SIDECAR))


def target_checkout(root, commit, sc) -> Path:
    cfg = json.loads(show(root, commit, "config/holon.json"))
    return Path(cfg["extract"]["sources"][sc["target"]["repo"]])


def tar_mode(gitmode: str) -> int:
    return 0o755 if gitmode == "100755" else 0o644


def redact_text(text: str, sections, lists) -> tuple[str, list[dict]]:
    lines = text.split("\n")
    heads, fence = [], False
    for i, ln in enumerate(lines):
        if ln.startswith("```"):
            fence = not fence
            continue
        if not fence and ln.startswith("#"):
            heads.append((i, len(ln) - len(ln.lstrip("#"))))
    removed = [False] * len(lines)
    spans = []
    for entry in sections:
        for k, (i, lev) in enumerate(heads):
            if lines[i].startswith(entry):
                j = next((i2 for i2, lev2 in heads[k + 1:] if lev2 <= lev), len(lines))
                spans.append((i, j, entry))
                for x in range(i, j):
                    removed[x] = True
    for entry in lists:
        for i, ln in enumerate(lines):
            if not removed[i] and ln.rstrip() == entry:
                j = i + 1
                while j < len(lines) and lines[j].strip() != "":
                    j += 1
                j = min(j + 1, len(lines))
                spans.append((i, j, entry))
                for x in range(i, j):
                    removed[x] = True
    spans.sort()
    out = "\n".join(ln for i, ln in enumerate(lines) if not removed[i])
    return out, [{"what": e, "start": i + 1, "lines": j - i,
                  "sha256": sha256_bytes("\n".join(lines[i:j]).encode("utf-8"))} for i, j, e in spans]


def redact(root, commit) -> tuple[str, list[dict]]:
    sc = pack_sidecar(root, commit)
    w = sc["whitepaper"]
    return redact_text(show(root, commit, w["source"]).decode("utf-8"), w["remove_sections"], w["remove_lists"])


def removed_section_texts(root, commit) -> list[str]:
    sc = pack_sidecar(root, commit)
    w = sc["whitepaper"]
    lines = show(root, commit, w["source"]).decode("utf-8").split("\n")
    _, spans = redact_text("\n".join(lines), w["remove_sections"], [])
    return ["\n".join(lines[s["start"] - 1:s["start"] - 1 + s["lines"]]) for s in spans]


def expected_members(root, commit) -> dict:
    """{members: {member path: (sha256, mode, kind)}, sizes, sources, excluded, redactions}."""
    sc = pack_sidecar(root, commit)
    tp, hp = sc["members"]["target_prefix"], sc["members"]["tooling_prefix"]
    members, sizes, sources = {}, {}, {}
    excluded = {"prefix": [], "basename": [], "path": []}
    hb = Blobs(root)
    try:
        for path, mode, typ, oid in ls_tree(root, commit):
            if typ != "blob":
                continue
            if not (path in sc["include_files"] or any(path.startswith(r) for r in sc["include_roots"])):
                continue
            if any(path.startswith(x) for x in sc["exclude_prefixes"]):
                excluded["prefix"].append(path)
                continue
            if any(fnmatch.fnmatchcase(path.rsplit("/", 1)[-1], pat) for pat in sc["exclude_basenames"]):
                excluded["basename"].append(path)
                continue
            if path in sc["exclude_paths"]:
                excluded["path"].append(path)
                continue
            data = hb.get(oid)
            kind = "symlink" if mode == "120000" else "file"
            members[hp + path] = (sha256_bytes(data), tar_mode(mode), kind)
            sizes[hp + path], sources[hp + path] = len(data), "holon"
    finally:
        hb.close()
    text, spans = redact(root, commit)
    wb = text.encode("utf-8")
    wm = sc["whitepaper"]["member"]
    members[wm], sizes[wm], sources[wm] = (sha256_bytes(wb), 0o644, "file"), len(wb), "redacted"
    tgt = target_checkout(root, commit, sc)
    tb = Blobs(tgt)
    gitlinks = []
    try:
        for path, mode, typ, oid in ls_tree(tgt, sc["target"]["commit"]):
            if typ == "commit":
                gitlinks.append(path)
                continue
            if typ != "blob":
                continue
            data = tb.get(oid)
            kind = "symlink" if mode == "120000" else "file"
            members[tp + path] = (sha256_bytes(data), tar_mode(mode), kind)
            sizes[tp + path], sources[tp + path] = len(data), "target"
    finally:
        tb.close()
    return {"members": members, "sizes": sizes, "sources": sources,
            "excluded": {"holon": {k: sorted(v) for k, v in excluded.items()}, "target": sorted(gitlinks)},
            "redactions": spans, "sidecar": sc, "target_path": tgt}


def tar_members(path) -> dict:
    out = {}
    with tarfile.open(path, "r:") as t:
        for m in t.getmembers():
            if m.isfile():
                out[m.name] = (sha256_bytes(t.extractfile(m).read()), m.mode, "file")
            elif m.issym():
                out[m.name] = (sha256_bytes(m.linkname.encode("utf-8")), m.mode, "symlink")
            else:
                out[m.name] = (None, m.mode, "other")
    return out


def tar_read(path, name) -> bytes:
    with tarfile.open(path, "r:") as t:
        return t.extractfile(t.getmember(name)).read()


def tar_format_problems(path) -> list[str]:
    bad = []
    with tarfile.open(path, "r:") as t:
        names = []
        for m in t.getmembers():
            names.append(m.name)
            if not (m.isfile() or m.issym()):
                bad.append(f"{m.name}: neither a regular file nor a symlink")
            if (m.mtime, m.uid, m.gid, m.uname, m.gname) != (0, 0, 0, "", ""):
                bad.append(f"{m.name}: mtime/uid/gid/uname/gname {(m.mtime, m.uid, m.gid, m.uname, m.gname)}")
    if names != sorted(names, key=lambda n: n.encode("utf-8")):
        bad.append("members are not sorted by their UTF-8 paths")
    if len(set(names)) != len(names):
        bad.append("a member path is repeated")
    return bad


def forbidden_members(root, commit, got: dict) -> list[str]:
    """K9, from the protocol's own lists (not the sidecar's): no tooling member under an excluded directory, no test
    or audit file, no maps_to sidecar or policy hints, nothing outside target/ and tooling/."""
    bad = []
    for name in sorted(got):
        if name.startswith("target/"):
            continue
        if not name.startswith("tooling/"):
            bad.append(f"{name}: outside target/ and tooling/")
            continue
        rel = name[len("tooling/"):]
        base = rel.rsplit("/", 1)[-1]
        if rel.startswith(FORBIDDEN_PREFIXES) or re.match(r"tests_m\d", rel):
            bad.append(f"{name}: an excluded directory")
        if any(fnmatch.fnmatchcase(base, pat) for pat in FORBIDDEN_BASENAMES):
            bad.append(f"{name}: a maps_to sidecar or the policy hints")
    return bad


def _absolute_strings(obj, where="") -> list[str]:
    if isinstance(obj, dict):
        return [x for k, v in obj.items() for x in _absolute_strings(v, f"{where}.{k}")]
    if isinstance(obj, list):
        return [x for i, v in enumerate(obj) for x in _absolute_strings(v, f"{where}[{i}]")]
    if isinstance(obj, str) and (obj.startswith("/") or re.search(r"(^|[\s'\"(])/(home|root|tmp|Users)/", obj)):
        return [f"{where}: {obj[:80]}"]
    return []


def manifest_problems(root, commit, man: dict, exp: dict, outdir) -> list[str]:
    sc = exp["sidecar"]
    bad = []
    outdir = Path(outdir)
    tar = outdir / "bundle.tar"
    want_members = [{"path": p, "size": exp["sizes"][p], "sha256": exp["members"][p][0], "mode": exp["members"][p][1],
                     "source": exp["sources"][p]} for p in sorted(exp["members"], key=lambda n: n.encode("utf-8"))]
    leaks = load(outdir / "leaks.json")
    tgt = exp["target_path"]
    want = {
        "pack_version": sc["version"],
        "holon": {"commit": commit, "tree": git(root, "rev-parse", f"{commit}^{{tree}}").strip()},
        "target": {"repo": sc["target"]["repo"], "commit": sc["target"]["commit"],
                   "tree": git(tgt, "rev-parse", f"{sc['target']['commit']}^{{tree}}").strip()},
        "sidecar": {"path": PACK_SIDECAR, "sha256": sha256_bytes(show(root, commit, PACK_SIDECAR))},
        "members": want_members,
        "excluded": exp["excluded"],
        "redactions": exp["redactions"],
        "leaks": leaks["summary"],
        "bundle": {"sha256": sha256_file(tar), "size": tar.stat().st_size, "members": len(want_members)},
    }
    for k, v in want.items():
        if man.get(k) != v:
            bad.append(f"manifest {k} differs from the instrument's")
    lk = load(outdir / "leaks.json")
    lk["matches"] = [{k: v for k, v in r.items() if k not in ("excerpt", "match")} for r in lk["matches"]]
    for name, obj in (("manifest.json", man), ("leaks.json", lk)):
        bad += [f"{name}{x}" for x in _absolute_strings(obj)]
    for name in ("manifest.json", "leaks.json"):
        if (outdir / name).read_text(encoding="utf-8") != dumps(load(outdir / name)):
            bad.append(f"{name} is not in K8's form")
    return bad


def redaction_prediction_problems(text: str, spans: list[dict]) -> list[str]:
    """P3: one span per section entry, seven Morph instances lists, and none of it left."""
    bad = []
    whats = [s["what"] for s in spans]
    for e in SECTION_ENTRIES:
        if whats.count(e) != 1:
            bad.append(f"section {e!r} removed {whats.count(e)} times")
    if whats.count(LIST_ENTRY) != 7:
        bad.append(f"{whats.count(LIST_ENTRY)} Morph instances lists removed, predicted 7")
    for ln in text.split("\n"):
        if ln.rstrip() == LIST_ENTRY or any(ln.startswith(e) for e in SECTION_ENTRIES):
            bad.append(f"left in the redacted text: {ln[:60]}")
    return bad


# ================================================================== the leak scan (L1-L6)
def _cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def row_names(cell: str) -> list[str]:
    return [x.strip() for x in re.sub(r"\([^)]*\)", "", cell).split(",") if x.strip()]


def _headings(lines) -> list[int]:
    out, fence = [], False
    for i, ln in enumerate(lines):
        if ln.startswith("```"):
            fence = not fence
            continue
        if not fence and ln.startswith("#"):
            out.append(i)
    return out


def section_lines(text: str, prefix: str) -> list[str]:
    """The lines after the heading that starts with prefix, up to the next heading line (any level)."""
    lines = text.split("\n")
    hs = _headings(lines)
    for k, i in enumerate(hs):
        if lines[i].startswith(prefix):
            j = hs[k + 1] if k + 1 < len(hs) else len(lines)
            return lines[i + 1:j]
    return []


def table_rows(text: str, prefix: str) -> list[list[str]]:
    rows = [ln for ln in section_lines(text, prefix) if ln.startswith("|")]
    rows = rows[1:]
    return [_cells(r) for r in rows if not re.fullmatch(r"\|(\s*:?-+:?\s*\|)+\s*", r.strip())]


def law_names(root, commit, lk: dict, tree=None) -> list[str]:
    tree = tree if tree is not None else ls_tree(root, commit)
    names = set()
    for d in lk["law_names"]["from_law_dirs"]:
        for path, _, typ, _ in tree:
            rest = path[len(d):]
            if typ == "blob" and path.startswith(d) and "/" not in rest and fnmatch.fnmatchcase(rest, "L*.json"):
                names.add(rest[:-len(".json")])
    wp = show(root, commit, "whitepaper.md").decode("utf-8")
    for row in table_rows(wp, lk["law_names"]["from_section"]):
        names.update(row_names(row[0]))
    return sorted(names)


NUMBER = re.compile(r"(?<![A-Za-z0-9_.,])(?:\d{1,3}(?:,\d{3})+|\d+)(?![A-Za-z0-9_,]|\.\d)")


def witness_numbers(root, commit, sc: dict) -> list[str]:
    nums = set()
    for text in removed_section_texts(root, commit):
        for m in NUMBER.finditer(text):
            plain = m.group(0).replace(",", "")
            if len(plain) >= sc["leaks"]["witness_numbers"]["min_digits"]:
                nums.add(plain)
    return sorted(nums)


def _grouped(plain: str) -> str:
    s = plain
    parts = []
    while len(s) > 3:
        parts.insert(0, s[-3:])
        s = s[:-3]
    return ",".join([s] + parts)


def number_pattern(plain: str):
    g = _grouped(plain)
    alts = [re.escape(g), re.escape(plain)] if g != plain else [re.escape(plain)]
    return re.compile(r"(?<![A-Za-z0-9_.,])(?:" + "|".join(alts) + r")(?![A-Za-z0-9_,]|\.\d)")


def literal_pattern(name: str):
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])")


def leak_scan(root, commit, tar_path) -> dict:
    sc = pack_sidecar(root, commit)
    lk = sc["leaks"]
    names = law_names(root, commit, lk)
    nums = witness_numbers(root, commit, sc)
    classes = {c: [re.compile(p) for p in pats] for c, pats in lk["classes"].items()}
    classes["law_name"] = [literal_pattern(n) for n in names]
    classes["witness"] = [number_pattern(n) for n in nums]
    rule_ctx = re.compile(lk["rule_context"])
    ctx = lk["context_chars"]
    scanned, unscanned, matches = [], [], []
    with tarfile.open(tar_path, "r:") as t:
        for m in t.getmembers():
            if not m.isfile() or not m.name.startswith(lk["scan_prefix"]):
                continue
            data = t.extractfile(m).read()
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                unscanned.append(m.name)
                continue
            scanned.append(m.name)
            for ln, line in enumerate(text.split("\n"), 1):
                for cls, pats in classes.items():
                    first = {}
                    for pat in pats:
                        for mt in pat.finditer(line):
                            first.setdefault(mt.start(), mt.group(0))
                    for col, s in first.items():
                        rec = {"path": m.name, "line": ln, "col": col, "class": cls, "match": s,
                               "excerpt": line.strip()[:200]}
                        if cls == "case_id":
                            rec["rule_context"] = bool(rule_ctx.search(line[max(0, col - ctx):col]))
                        matches.append(rec)
    matches.sort(key=lambda r: (r["path"], r["line"], r["col"], r["class"], r["match"]))
    all_classes = sorted(classes)
    by_class = {c: 0 for c in all_classes}
    files = {c: set() for c in all_classes}
    by_root: dict = {}
    for r in matches:
        by_class[r["class"]] += 1
        files[r["class"]].add(r["path"])
        rt = "/".join(r["path"].split("/")[:2])
        by_root.setdefault(rt, {})
        by_root[rt][r["class"]] = by_root[rt].get(r["class"], 0) + 1
    summary = {"by_class": by_class, "files_by_class": {c: len(files[c]) for c in all_classes}, "by_root": by_root}
    return {"scanned": sorted(scanned), "unscanned": sorted(unscanned), "law_names": names, "witness_numbers": nums,
            "matches": matches, "summary": summary}


def leak_prediction_problems(leaks: dict) -> list[str]:
    """P4: the leak list is not empty, and it finds what the prereg names (thresholds.leaks)."""
    bad = []
    ms = leaks["matches"]
    wp = "tooling/whitepaper.md"
    if not ms:
        bad.append("the leak list is empty")

    def has(path_prefix, cls, pred):
        return [r for r in ms if r["path"].startswith(path_prefix) and r["class"] == cls and pred(r)]

    if not has(wp, "case_id", lambda r: r["match"] == "O12" and "Example" in r["excerpt"]):
        bad.append("no case_id O12 on the redacted whitepaper's section 5.9 example line")
    if not has(wp, "law_name", lambda r: r["match"] == "L_dom_v0"):
        bad.append("no law_name L_dom_v0 in the redacted whitepaper (section 15.1)")
    if not has(wp, "section_ref", lambda r: r["match"].replace(" ", "").startswith("§11.8")):
        bad.append("no section_ref to section 11.8 in the redacted whitepaper")
    holon = "tooling/holon/"
    files_sr = {r["path"] for r in has(holon, "section_ref", lambda r: True)}
    files_ci = {r["path"] for r in has(holon, "case_id", lambda r: r["match"].startswith("O") and not r["rule_context"])}
    if len(files_sr) < 5:
        bad.append(f"{len(files_sr)} holon files with a section_ref match, predicted at least 5")
    if len(files_ci) < 5:
        bad.append(f"{len(files_ci)} holon files with an O-id case_id match outside rule context, predicted at least 5")
    if not has(holon, "code_site", lambda r: True):
        bad.append("no code_site match in holon/")
    if not has(holon, "law_name", lambda r: True):
        bad.append("no law_name match in holon/")
    return bad


# ================================================================== the catalog and the map (A1-A9)
def families(rule: str) -> list[str]:
    out = set()
    for part in re.split(r"[×/]", rule):
        part = part.strip()
        if part:
            out.add(re.split(r"[-\s(]", part)[0])
    return sorted(out)


PRIOR = re.compile(r"\b[FN]\d+(?:\.\d+|[a-f](?:,[a-f])*)?")


def catalog(wp: str) -> dict:
    items = {}
    for c in table_rows(wp, "### 11.3"):
        if re.fullmatch(r"O\d+", c[0]):
            items[c[0]] = {"kind": "obstruction", "rule": c[1], "families": families(c[1]), "title": c[2],
                           "prior": PRIOR.findall(c[4])}
    for ln in section_lines(wp, "### 11.4"):
        m = re.match(r"\*\*(N\d+) \((O\d+)\)\.\*\*(.*)$", ln)
        if m:
            items[m.group(1)] = {"kind": "new", "o": m.group(2), "title": m.group(3).strip()}
    for c in table_rows(wp, "### 11.6"):
        if re.fullmatch(r"D\d+", c[0]):
            items[c[0]] = {"kind": "discharged", "title": c[1]}
    for c in table_rows(wp, "## Appendix A"):
        if re.fullmatch(r"F\d+", c[0]):
            items[c[0]] = {"kind": "prior", "title": c[1]}
    for k, c in enumerate(table_rows(wp, "### 11.8"), 1):
        items[f"R{k}"] = {"kind": "row", "name": c[0], "names": row_names(c[0]), "rule": c[1], "prediction": c[2],
                          "witness": c[3]}
    return items


def _order(i: str) -> tuple:
    return ("ODNFR".index(i[0]), int(i[1:]))


def _cites(token: str, n: str) -> bool:
    m = re.match(r"F(\d+)", token)
    return bool(m) and m.group(1) == n


def planned(build_plan: str, ident: str) -> list[str]:
    lines = build_plan.split("\n")
    hs = _headings(lines)
    out = []
    pat = re.compile(r"\b" + re.escape(ident) + r"\b")
    for k, i in enumerate(hs):
        if lines[i].startswith("#### I"):
            j = hs[k + 1] if k + 1 < len(hs) else len(lines)
            if pat.search("\n".join(lines[i:j])):
                name = lines[i][len("#### "):].split(".")[0]
                if name not in out:
                    out.append(name)
    return out


def map_sidecar(root) -> dict:
    return load(Path(root) / MAP_SIDECAR)


def read_sets(root, sc: dict, overrides: dict | None = None) -> list[dict]:
    """A3: the sets read, in order, the hypotheses set last; each {name, basis, laws_dir, results_dir, laws: {id:
    {rule, status, maps_to, facts, subform}}, predictions: {id: status}}."""
    root = Path(root)
    overrides = overrides or {}
    out = []
    for s in sc["sets"]:
        res = Path(overrides[s["name"]]) if s["name"] in overrides else root / s["results"]
        if not res.is_dir():
            continue
        laws = {}
        for p in sorted((root / s["laws"]).glob("L*.json")):
            law = load(p)
            lid = law["law_id"]
            rp = res / f"{lid}.json"
            if not rp.is_file():
                continue
            rec = load(rp)
            mt = law.get("maps_to") if isinstance(law.get("maps_to"), str) else None
            if mt is None and isinstance(rec.get("maps_to"), str):
                mt = rec["maps_to"]
            laws[lid] = {"rule": law.get("rule"), "status": rec.get("status"), "maps_to": mt,
                         "facts": law.get("facts"), "subform": law.get("subform")}
        preds = {}
        if s.get("predictions") and (root / s["predictions"]).is_file():
            for e in load(root / s["predictions"]).get("laws", []):
                if not e.get("post_hoc"):
                    preds[e["law_id"]] = e.get("status")
        out.append({"name": s["name"], "basis": s["basis"], "laws_dir": s["laws"], "results_dir": s["results"],
                    "laws": laws, "predictions": preds, "has_predictions": bool(s.get("predictions"))})
    led = sc["ledger"]
    if (root / led["path"]).is_file() and (root / led["hypotheses_results"]).is_file():
        hyps = load(root / led["path"]).get("hypotheses", {})
        res = load(root / led["hypotheses_results"])
        laws = {h: {"rule": "HYP", "status": (res.get(h) or {}).get("status"), "maps_to": None, "facts": None,
                    "subform": None} for h in sorted(hyps)}
        out.append({"name": led["hypotheses_set"], "basis": "code", "laws_dir": led["path"],
                    "results_dir": led["hypotheses_results"], "laws": laws, "predictions": {}, "has_predictions": False})
    return out


def build_map(root, overrides: dict | None = None) -> dict:
    """The instrument's own A2-A7: the map as the contract defines it (fields compared by map_problems)."""
    root = Path(root)
    sc = map_sidecar(root)
    wp = (root / "whitepaper.md").read_text(encoding="utf-8")
    bp = (root / sc["planned_from"]).read_text(encoding="utf-8")
    cat = catalog(wp)
    sets = read_sets(root, sc, overrides)
    byname = {s["name"]: s for s in sets}
    order = {s["name"]: k for k, s in enumerate(sets)}
    rows_by_cell = {c["name"]: i for i, c in cat.items() if c["kind"] == "row"}
    links: dict = {}

    def expect_generic(item, s, lid):
        if item.startswith("D"):
            return "checked" if s["laws"][lid]["rule"] == "HYP" else "PROVED"
        if "DISCH" not in cat[item]["families"]:
            return "REFUTED"
        return s["predictions"].get(lid)

    def add(item, sname, lid, expect, source, via):
        k = (item, sname, lid)
        if k in links:
            links[k]["also"].append(source)
            return
        links[k] = {"item": item, "set": sname, "law": lid, "rule": byname[sname]["laws"][lid]["rule"],
                    "expect": expect, "source": source, "via": via, "also": [], "override": None}

    absent = []
    for e in sc["links"]:
        item = e["item"]
        if item.startswith("row:"):
            item = rows_by_cell.get(item[len("row:"):])
        s = byname.get(e["set"])
        if item is None or s is None or e["law"] not in s["laws"]:
            absent.append(e)
            continue
        add(item, e["set"], e["law"], e["expect"], "sidecar", e["source"])
    for s in sets:
        for lid, law in sorted(s["laws"].items()):
            if law["maps_to"]:
                head = law["maps_to"].split("(")[0]
                for tok in re.split(r"[/\s]+", head):
                    if re.fullmatch(r"[OD]\d+", tok) and tok in cat:
                        add(tok, s["name"], lid, expect_generic(tok, s, lid), "maps_to", law["maps_to"])
    led = sc["ledger"]
    if (root / led["path"]).is_file():
        ledger = load(root / led["path"])
        s = byname.get(led["set"])
        if s:
            for lid, ids in sorted(ledger.get("M0", {}).items()):
                if lid in s["laws"]:
                    for tok in ids:
                        if tok in cat:
                            add(tok, s["name"], lid, expect_generic(tok, s, lid), "ledger", led["path"])
        hs = byname.get(led["hypotheses_set"])
        if hs:
            for h, ids in sorted(ledger.get("hypotheses", {}).items()):
                if h in hs["laws"]:
                    for tok in ids:
                        if tok in cat:
                            add(tok, hs["name"], h, expect_generic(tok, hs, h), "ledger", led["path"])
    for s in sets:
        if not s["has_predictions"]:
            continue
        for lid in sorted(s["laws"]):
            for rid in sorted((i for i in cat if i.startswith("R")), key=_order):
                for n in cat[rid]["names"]:
                    if lid == n or lid.startswith(n + "_") or lid == n.replace("ω", "omega"):
                        add(rid, s["name"], lid, s["predictions"].get(lid), "name", n)
                        break
    for bt in sc["backtests"]:
        p = root / bt["path"]
        if not p.is_file() or bt["set"] not in byname:
            continue
        doc = load(p)
        for row in doc.get("rows", []):
            old, new = row.get(bt["old"]), row.get(bt["new"])
            if not new or new not in byname[bt["set"]]["laws"]:
                continue
            for (item, sname, lid), lk in sorted(links.items()):
                if sname == bt["against"] and lid == old and lk["source"] != "backtest":
                    add(item, bt["set"], new, lk["expect"], "backtest", f"{bt['path']}: {old}")
    for o in sc.get("overrides", []):
        k = (o["item"], o["set"], o["law"])
        if k in links:
            links[k]["expect"] = o["expect"]
            links[k]["override"] = o["source"]
    for lk in links.values():
        fam_ok = (not lk["item"].startswith("O")) or lk["rule"] in cat[lk["item"]]["families"]
        hyp_ok = lk["rule"] != "HYP" or lk["item"].startswith("D")
        lk["counted"] = lk["expect"] is not None and fam_ok and hyp_ok
        lk["also"] = sorted(lk["also"])
    items = {}
    for i in sorted(cat, key=_order):
        c = dict(cat[i])
        if c["kind"] in ("obstruction", "discharged", "row"):
            ls = [lk for lk in links.values() if lk["item"] == i]
            ls.sort(key=lambda x: (order[x["set"]], x["law"]))
            c["links"] = [{k: v for k, v in lk.items() if k != "item"} for lk in ls]
        if c["kind"] in ("obstruction", "discharged"):
            c["planned"] = planned(bp, i)
        if c["kind"] == "prior":
            n = i[1:]
            c["via"] = [{"o": o, "cited": [t for t in cat[o]["prior"] if _cites(t, n)]}
                        for o in sorted((x for x in cat if x.startswith("O")), key=_order)
                        if any(_cites(t, n) for t in cat[o]["prior"])]
        items[i] = c
    linked = {(lk["set"], lk["law"]) for lk in links.values()}
    unmapped = {s["name"]: sorted(l for l in s["laws"] if (s["name"], l) not in linked)
                for s in sets if s["basis"] == "code"}
    inputs = {}
    paths = ["whitepaper.md", MAP_SIDECAR, sc["planned_from"], led["path"], led["hypotheses_results"]]
    paths += [s["predictions"] for s in sc["sets"] if s.get("predictions")]
    paths += [bt["path"] for bt in sc["backtests"]]
    for pth in paths:
        if (root / pth).is_file():
            inputs[pth] = sha256_file(root / pth)
    set_rows = [{"name": s["name"], "basis": s["basis"], "laws": s["laws_dir"], "results": s["results_dir"],
                 "n_laws": len(s["laws"])} for s in sets]
    return {"version": "holon-appendixA-map/0.1", "inputs": inputs, "sets": set_rows, "items": items,
            "unmapped": unmapped, "absent": absent}


def map_problems(root, doc: dict) -> list[str]:
    exp = build_map(root)
    bad = []
    for k in ("version", "inputs", "sets", "unmapped", "absent"):
        if doc.get(k) != exp[k]:
            bad.append(f"map {k} differs from the instrument's")
    want_ids = [f"O{n}" for n in range(1, 38)] + [f"D{n}" for n in range(1, 10)] + [f"N{n}" for n in range(1, 5)] \
        + [f"F{n}" for n in range(1, 15)] + [f"R{n}" for n in range(1, 15)]
    got_items = doc.get("items") or {}
    if sorted(got_items, key=_order) != sorted(want_ids, key=_order):
        bad.append(f"map items are not exactly O1-O37, D1-D9, N1-N4, F1-F14, R1-R14: {sorted(got_items)[:12]}")
    if sorted(exp["items"], key=_order) != sorted(want_ids, key=_order):
        bad.append("the instrument's catalog parse does not give O1-O37, D1-D9, N1-N4, F1-F14, R1-R14")
    for i in want_ids:
        if got_items.get(i) != exp["items"].get(i):
            bad.append(f"map item {i} differs from the instrument's")
    for i, it in got_items.items():
        for lk in it.get("links", []):
            if lk.get("source") not in SOURCE_ORDER:
                bad.append(f"{i}: a link with source {lk.get('source')!r}")
    return bad


def statuses(root, overrides: dict | None = None) -> dict:
    return {s["name"]: {lid: law["status"] for lid, law in s["laws"].items()}
            for s in read_sets(root, map_sidecar(root), overrides)}


def bases(root) -> dict:
    sc = map_sidecar(root)
    out = {s["name"]: s["basis"] for s in sc["sets"]}
    out[sc["ledger"]["hypotheses_set"]] = "code"
    return out


def verdicts(root, doc: dict, overrides: dict | None = None) -> dict:
    """A8: {item: {"hand": verdict, "code": verdict}}."""
    st = statuses(root, overrides)
    basis_of = bases(root)
    items = doc["items"]
    out = {}

    def status(lk):
        return (st.get(lk["set"]) or {}).get(lk["law"]) or NO_RECORD

    def one(item, basis):
        it = items[item]
        ls = [lk for lk in it.get("links", []) if basis_of.get(lk["set"]) == basis]
        counted = [lk for lk in ls if lk["counted"]]
        some = it["kind"] == "obstruction"
        if counted:
            eq = [status(lk) == lk["expect"] for lk in counted]
            differ = any(status(lk) in DECIDED and status(lk) != lk["expect"] for lk in counted)
            if some and any(eq):
                return "reproduced"
            if not some and all(eq):
                return "certified" if it["kind"] == "discharged" else "held"
            if differ:
                return "missed" if it["kind"] == "row" else "contradicted"
        return "open" if ls else "not mechanized"

    for i, it in items.items():
        if it["kind"] in ("obstruction", "discharged", "row"):
            out[i] = {b: one(i, b) for b in ("hand", "code")}
    for i, it in items.items():
        if it["kind"] == "new":
            out[i] = dict(out[it["o"]])
        elif it["kind"] == "prior":
            v = {}
            for b in ("hand", "code"):
                vs = [out[x["o"]][b] for x in it["via"]]
                if vs and all(x == "reproduced" for x in vs):
                    v[b] = "reproduced"
                elif any(x == "reproduced" for x in vs):
                    v[b] = "partly reproduced"
                elif any(x == "contradicted" for x in vs):
                    v[b] = "contradicted"
                elif any(x == "open" for x in vs):
                    v[b] = "open"
                else:
                    v[b] = "not mechanized"
            out[i] = v
    return out


def _render_links(root, item: dict, basis: str, st: dict, basis_of: dict) -> str:
    parts = []
    for lk in item.get("links", []):
        if basis_of.get(lk["set"]) != basis:
            continue
        s = (st.get(lk["set"]) or {}).get(lk["law"]) or NO_RECORD
        parts.append(f"{lk['law']} ({lk['set']}) {s}" + ("" if lk["counted"] else " (context)"))
    return "; ".join(parts) if parts else "—"


def doc_lines(text: str) -> dict:
    out = {}
    for ln in text.split("\n"):
        if not ln.startswith("| "):
            continue
        c = _cells(ln)
        if c and re.fullmatch(r"[RFODN]\d+", c[0]):
            out.setdefault(c[0], []).append(c)
    return out


COLUMNS = {"row": (5, 7, 4, 6), "obstruction": (4, 6, 3, 5), "discharged": (3, 5, 2, 4), "prior": (3, 4, None, None),
           "new": (2, 3, None, None)}
WIDTH = {"row": 8, "obstruction": 8, "discharged": 7, "prior": 5, "new": 4}


def comparison_problems(root, doc: dict, text: str, overrides: dict | None = None) -> list[str]:
    bad = []
    v = verdicts(root, doc, overrides)
    st = statuses(root, overrides)
    basis_of = bases(root)
    lines = doc_lines(text)
    if "contamination" not in text:
        bad.append("the comparison states no contamination caveat")
    for i, it in doc["items"].items():
        rows = lines.get(i, [])
        if len(rows) != 1:
            bad.append(f"{i}: {len(rows)} table lines, the contract says 1")
            continue
        c = rows[0]
        kind = it["kind"]
        if len(c) != WIDTH[kind]:
            bad.append(f"{i}: {len(c)} cells, the contract says {WIDTH[kind]}")
            continue
        h, k, hl, kl = COLUMNS[kind]
        if (c[h], c[k]) != (v[i]["hand"], v[i]["code"]):
            bad.append(f"{i}: verdicts {(c[h], c[k])}, the rules give {(v[i]['hand'], v[i]['code'])}")
        if hl is not None:
            for col, b in ((hl, "hand"), (kl, "code")):
                want = _render_links(root, it, b, st, basis_of).replace("\n", " ")
                if c[col] != want:
                    bad.append(f"{i}: {b} links {c[col][:80]!r}, the map gives {want[:80]!r}")
    for i in lines:
        if i not in doc["items"]:
            bad.append(f"{i}: a table line for an id the map does not hold")
    for n in range(1, 15):
        if len(lines.get(f"F{n}", [])) != 1:
            bad.append(f"F{n} has no cell")
    return bad


def g1_comparison_problems(root, holon) -> list[str]:
    """G1: holon report --check passes on the committed records, fails when one M3 status is flipped in a copy, passes
    on an unflipped copy; holon/gate.py's G1 calls holon.report.regenerate_check."""
    import tempfile
    root = Path(root)
    bad = []
    doc = load(root / "spec" / "M3" / "appendixA_map.json")
    st = statuses(root)
    target = None
    for i in sorted(doc["items"], key=_order):
        for lk in doc["items"][i].get("links", []):
            if lk["set"] == "M3" and lk["counted"] and (st.get("M3") or {}).get(lk["law"]) in ("PROVED", "REFUTED"):
                target = lk["law"]
                break
        if target:
            break
    if target is None:
        return ["no counted M3 link with a decided record to flip"]
    tmp = Path(tempfile.mkdtemp(prefix="i82-g1-"))
    try:
        same, flipped = tmp / "same", tmp / "flipped"
        shutil.copytree(root / "results" / "M3", same)
        shutil.copytree(root / "results" / "M3", flipped)
        rp = flipped / f"{target}.json"
        rec = load(rp)
        rec["status"] = "PROVED" if rec["status"] == "REFUTED" else "REFUTED"
        rp.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        p = holon("report", "--milestone", "M3", "--check", "--results", f"M3={same}")
        if p.returncode != 0:
            bad.append(f"report --check on an unflipped copy of results/M3 exits {p.returncode}: {p.stdout[-400:]}")
        p = holon("report", "--milestone", "M3", "--check", "--results", f"M3={flipped}")
        if p.returncode != 1:
            bad.append(f"report --check with {target}'s status flipped exits {p.returncode}, the contract says 1")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    gate = (root / "holon" / "gate.py").read_text(encoding="utf-8")
    if "regenerate_check" not in gate:
        bad.append("holon/gate.py does not call holon.report.regenerate_check")
    return bad


# ================================================================== the metric (B1-B6)
def _rename(t, m: dict):
    if isinstance(t, list):
        return [_rename(x, m) for x in t]
    if not isinstance(t, dict):
        return t
    out = {}
    for k, v in t.items():
        if k in ("var", "app") and isinstance(v, str):
            out[k] = m.get(v, v)
        elif k == "cf" and isinstance(v, dict):
            out[k] = {kk: (m.get(vv, vv) if kk == "fn" and isinstance(vv, str) else _rename(vv, m)) for kk, vv in v.items()}
        else:
            out[k] = _rename(v, m)
    return out


def _sides(p):
    if isinstance(p, dict):
        for rel in ("eq", "neq"):
            if rel in p and isinstance(p[rel], list) and len(p[rel]) == 2:
                q = dict(p)
                q[rel] = sorted(p[rel], key=canon)
                return q
    return p


def normal_form(st):
    if not isinstance(st, dict) or not ("binders" in st or "forall" in st) or "claim" not in st:
        return st
    if "binders" in st:
        bs = [(b.get("q", "forall"), b["name"], b["type"]) for b in st["binders"]]
    else:
        bs = [("forall", b["name"], b["type"]) for b in st["forall"]]
    m = {name: f"x{i}" for i, (_, name, _) in enumerate(bs)}
    assume = sorted({canon(_sides(_rename(p, m))) for p in st.get("assume", [])})
    claim = _rename(st["claim"], m)
    if isinstance(claim, dict) and "all" in claim:
        claim = {"all": [json.loads(x) for x in sorted({canon(_sides(c)) for c in claim["all"]})]}
    else:
        claim = _sides(claim)
    return {"binders": [[q, t] for q, _, t in bs], "assume": [json.loads(x) for x in assume], "claim": claim,
            "scope": st.get("scope") or {"kind": "unbounded"}}


def key_of(st) -> str:
    return sha256_bytes(canon(normal_form(st)).encode("utf-8"))


def tree_classes(tree, m: str) -> tuple[dict, list[str]]:
    """{key: {"laws": [ids], "status": s, "facts": [paths]}}, unrecorded ids."""
    tree = Path(tree)
    classes, unrecorded = {}, []
    for p in sorted((tree / "laws" / m).glob("L*.json")):
        law = load(p)
        lid = law["law_id"]
        rp = tree / "results" / m / f"{lid}.json"
        rec = load(rp) if rp.is_file() else {}
        if not isinstance(rec.get("status"), str):
            unrecorded.append(lid)
            continue
        c = classes.setdefault(key_of(law.get("statement")), {"laws": [], "statuses": [], "facts": []})
        c["laws"].append(lid)
        c["statuses"].append(rec["status"])
        c["facts"].append(law.get("facts"))
    for c in classes.values():
        ss = sorted(set(c["statuses"]))
        c["status"] = ss[0] if len(ss) == 1 else "MIXED:" + "+".join(ss)
        c["laws"] = sorted(c["laws"])
        c["facts"] = sorted({f for f in c["facts"] if f is not None})
        del c["statuses"]
    return classes, sorted(unrecorded)


def compare(lead, blind, milestones) -> dict:
    out, pool = {}, {"lead_keys": 0, "matched": 0, "agree": 0}
    for m in milestones:
        lc, lu = tree_classes(lead, m)
        bc, bu = tree_classes(blind, m)
        matched = sorted(set(lc) & set(bc))
        agree = [k for k in matched if lc[k]["status"] == bc[k]["status"]]
        out[m] = {"lead_keys": len(lc), "blind_keys": len(bc), "matched": len(matched), "agree": len(agree),
                  "blind_agreement": (len(agree) / len(matched)) if matched else None,
                  "matched_fraction": (len(matched) / len(lc)) if lc else None,
                  "lead_only": sorted(l for k in set(lc) - set(bc) for l in lc[k]["laws"]),
                  "blind_only": sorted(l for k in set(bc) - set(lc) for l in bc[k]["laws"]),
                  "disagreements": [{"key": k, "lead": {"laws": lc[k]["laws"], "status": lc[k]["status"]},
                                     "blind": {"laws": bc[k]["laws"], "status": bc[k]["status"]}}
                                    for k in matched if lc[k]["status"] != bc[k]["status"]],
                  "unrecorded": {"lead": lu, "blind": bu},
                  "facts_differ": [{"key": k, "lead": lc[k]["facts"], "blind": bc[k]["facts"]}
                                   for k in matched if lc[k]["facts"] != bc[k]["facts"]]}
        pool["lead_keys"] += len(lc)
        pool["matched"] += len(matched)
        pool["agree"] += len(agree)
    pool["blind_agreement"] = pool["agree"] / pool["matched"] if pool["matched"] else None
    pool["matched_fraction"] = pool["matched"] / pool["lead_keys"] if pool["lead_keys"] else None
    return {"milestones": out, "pooled": pool}


def snapshot(src, dst, milestones, rev: str | None = None, root=None) -> None:
    """B6 from a directory, or (rev given) from git objects of root at rev."""
    dst = Path(dst)
    for m in milestones:
        (dst / "laws" / m).mkdir(parents=True, exist_ok=True)
        (dst / "results" / m).mkdir(parents=True, exist_ok=True)
        if rev is None:
            items = [(p.name, p.read_bytes()) for p in sorted((Path(src) / "laws" / m).glob("L*.json"))]
        else:
            items = [(Path(path).name, show(root, rev, path)) for path, _, typ, _ in ls_tree(root, rev)
                     if typ == "blob" and path.startswith(f"laws/{m}/") and "/" not in path[len(f"laws/{m}/"):]
                     and fnmatch.fnmatchcase(Path(path).name, "L*.json")]
        for name, data in items:
            (dst / "laws" / m / name).write_bytes(data)
            lid = json.loads(data)["law_id"]
            if rev is None:
                rp = Path(src) / "results" / m / f"{lid}.json"
                rec = load(rp) if rp.is_file() else None
            else:
                try:
                    rec = json.loads(show(root, rev, f"results/{m}/{lid}.json"))
                except RuntimeError:
                    rec = None
            if rec is not None and isinstance(rec.get("status"), str):
                (dst / "results" / m / f"{lid}.json").write_text(dumps({"law_id": lid, "status": rec["status"]}),
                                                                 encoding="utf-8")


def _files(d) -> dict:
    d = Path(d)
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


def dry_run_problems(root, dryrun, rep: dict) -> list[str]:
    """P8: the dry run's provenance, its two committed trees, the report recomputed, and the predicted values."""
    import tempfile
    root, dryrun = Path(root), Path(dryrun)
    bad = []
    prov = load(dryrun / "dryrun.json")
    base = prov.get("base")
    if tuple(prov.get("milestones") or ()) != DRY_RUN_MILESTONES:
        bad.append(f"dryrun.json milestones {prov.get('milestones')}, the prereg says {list(DRY_RUN_MILESTONES)}")
    tmp = Path(tempfile.mkdtemp(prefix="i82-dry-"))
    try:
        snapshot(None, tmp, DRY_RUN_MILESTONES, rev=base, root=root)
        if _files(tmp) != _files(dryrun / "lead"):
            bad.append(f"audit/blind/dryrun/lead is not the projection of the lead at {base}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    lead, blind = dryrun / "lead", dryrun / "tree"
    for m in DRY_RUN_MILESTONES:
        if _files(lead / "laws" / m) != _files(blind / "laws" / m):
            bad.append(f"{m}: the dry run's laws are not the lead's")
    par = sorted(load(p)["law_id"] for p in sorted((lead / "laws" / "M3").glob("L*.json"))
                 if load(p).get("rule") == "PAR" and load(p).get("subform") != "init_chain")
    got_m3 = sorted(p.stem for p in (blind / "results" / "M3").glob("L*.json"))
    if got_m3 != par:
        bad.append(f"the dry run re-made {len(got_m3)} M3 records, the prereg says the {len(par)} PAR laws outside "
                   f"PAR-init")
    if prov.get("m3_laws") != par:
        bad.append("dryrun.json m3_laws is not the PAR laws outside PAR-init")
    for m in ("M0", "M1"):
        want = sorted(p.stem for p in (lead / "results" / m).glob("L*.json"))
        got = sorted(p.stem for p in (blind / "results" / m).glob("L*.json"))
        if got != want:
            bad.append(f"{m}: the dry run re-made {len(got)} records, the lead holds {len(want)}")
    exp = compare(lead, blind, DRY_RUN_MILESTONES)
    for m in DRY_RUN_MILESTONES:
        g, e = (rep.get("milestones") or {}).get(m) or {}, exp["milestones"][m]
        for k in ("lead_keys", "blind_keys", "matched", "agree", "blind_agreement", "matched_fraction", "lead_only",
                  "blind_only", "disagreements", "unrecorded", "facts_differ"):
            if g.get(k) != e[k]:
                bad.append(f"{m}: {k} {g.get(k)!r:.80} differs from the instrument's {e[k]!r:.80}")
        if e["blind_agreement"] != 1.0:
            bad.append(f"{m}: blind_agreement {e['blind_agreement']}, predicted 1.0")
    if rep.get("pooled") != exp["pooled"]:
        bad.append("pooled differs from the instrument's")
    if exp["pooled"]["blind_agreement"] != 1.0:
        bad.append(f"pooled blind_agreement {exp['pooled']['blind_agreement']}, predicted 1.0")
    for m in ("M0", "M1"):
        if exp["milestones"][m]["matched_fraction"] != 1.0:
            bad.append(f"{m}: matched_fraction {exp['milestones'][m]['matched_fraction']}, predicted 1.0")
    lc, _ = tree_classes(lead, "M3")
    par_keys = {k for k, c in lc.items() if set(c["laws"]) & set(par)}
    want = len(par_keys) / len(lc) if lc else None
    if exp["milestones"]["M3"]["matched_fraction"] != want:
        bad.append(f"M3: matched_fraction {exp['milestones']['M3']['matched_fraction']}, predicted {want} "
                   f"(the classes of the PAR laws outside PAR-init)")
    return bad


# ------------------------------------------------------------------ synthetic perturbations (P9)
def _alpha_rename(st):
    """Every binder renamed (a fresh suffix), its occurrences with it; premises reversed; eq/neq sides swapped;
    a top-level conjunction reversed."""
    if "binders" in st:
        names = [b["name"] for b in st["binders"]]
    else:
        names = [b["name"] for b in st.get("forall", [])]
    m = {n: f"{n}_alpha{i}" for i, n in enumerate(names)}

    def swap(p):
        if isinstance(p, dict):
            for rel in ("eq", "neq"):
                if rel in p and isinstance(p[rel], list) and len(p[rel]) == 2:
                    q = dict(p)
                    q[rel] = [p[rel][1], p[rel][0]]
                    return q
        return p

    out = dict(st)
    if "binders" in st:
        out["binders"] = [dict(b, name=m[b["name"]]) for b in st["binders"]]
    else:
        out["forall"] = [dict(b, name=m[b["name"]]) for b in st["forall"]]
    out["assume"] = [swap(_rename(p, m)) for p in reversed(st.get("assume", []))]
    claim = _rename(st["claim"], m)
    if isinstance(claim, dict) and "all" in claim:
        claim = {"all": [swap(c) for c in reversed(claim["all"])]}
    else:
        claim = swap(claim)
    out["claim"] = claim
    return out


def _write_law(tree: Path, m: str, law: dict, status: str | None):
    (tree / "laws" / m).mkdir(parents=True, exist_ok=True)
    (tree / "results" / m).mkdir(parents=True, exist_ok=True)
    (tree / "laws" / m / f"{law['law_id']}.json").write_text(dumps(law), encoding="utf-8")
    if status is not None:
        (tree / "results" / m / f"{law['law_id']}.json").write_text(dumps({"law_id": law["law_id"],
                                                                          "status": status}), encoding="utf-8")


def _tree_laws(tree: Path, m: str) -> list[tuple[dict, str | None]]:
    out = []
    for p in sorted((tree / "laws" / m).glob("L*.json")):
        law = load(p)
        rp = tree / "results" / m / f"{law['law_id']}.json"
        out.append((law, load(rp)["status"] if rp.is_file() else None))
    return out


def _singletons(tree: Path, m: str) -> list[str]:
    cl, _ = tree_classes(tree, m)
    return sorted(c["laws"][0] for c in cl.values() if len(c["laws"]) == 1)


FLIP = {"PROVED": "REFUTED", "REFUTED": "PROVED", "UNKNOWN": "PROVED"}


def perturbation_cases(root, tmp) -> list[dict]:
    root, tmp = Path(root), Path(tmp)
    ms = list(DRY_RUN_MILESTONES)
    lead = tmp / "lead"
    for m in ms:
        snapshot(root, lead, [m])
    cases = []

    def new(name):
        d = tmp / name
        shutil.copytree(lead, d)
        return d

    base = compare(lead, lead, ms)

    def expect(adjust=None):
        e = json.loads(json.dumps(base))
        if adjust:
            adjust(e)
        return e

    # identity and the threshold
    cases.append({"name": "identity", "lead": lead, "blind": new("identity"), "milestones": ms, "exit": 0,
                  "expect": expect()})
    cases.append({"name": "threshold-pass", "lead": lead, "blind": tmp / "identity", "milestones": ms, "exit": 0,
                  "args": ["--threshold", "0.9"], "expect": expect()})
    # alpha: binders renamed, law ids and file names changed, premises and conjuncts reordered, sides swapped
    d = tmp / "alpha"
    for m in ms:
        for law, status in _tree_laws(lead, m):
            law2 = dict(law, law_id="L_alpha_" + law["law_id"][2:], statement=_alpha_rename(law["statement"])) \
                if isinstance(law.get("statement"), dict) and ("binders" in law["statement"] or "forall" in law["statement"]) \
                else dict(law, law_id="L_alpha_" + law["law_id"][2:])
            _write_law(d, m, law2, status)

    def alpha_adj(e):
        pass
    cases.append({"name": "alpha", "lead": lead, "blind": d, "milestones": ms, "exit": 0, "expect": expect(alpha_adj),
                  "ids_renamed": True})
    # flip: three M3 singletons and one M1 singleton change status
    d = new("flip")
    flips = {"M3": _singletons(lead, "M3")[:3], "M1": _singletons(lead, "M1")[:1]}
    for m, ids in flips.items():
        for lid in ids:
            rp = d / "results" / m / f"{lid}.json"
            rec = load(rp)
            rp.write_text(dumps({"law_id": lid, "status": FLIP[rec["status"]]}), encoding="utf-8")

    def flip_adj(e):
        for m, ids in flips.items():
            x = e["milestones"][m]
            x["agree"] -= len(ids)
            x["n_disagreements"] = len(ids)
            x["blind_agreement"] = x["agree"] / x["matched"]
        e["pooled"]["agree"] -= sum(len(v) for v in flips.values())
        e["pooled"]["blind_agreement"] = e["pooled"]["agree"] / e["pooled"]["matched"]
    cases.append({"name": "flip", "lead": lead, "blind": d, "milestones": ms, "exit": 0, "expect": expect(flip_adj)})
    # drop: five M3 singletons lose their records
    d = new("drop")
    drops = _singletons(lead, "M3")[-5:]
    for lid in drops:
        (d / "results" / "M3" / f"{lid}.json").unlink()

    def drop_adj(e):
        x = e["milestones"]["M3"]
        x["blind_keys"] -= 5
        x["matched"] -= 5
        x["agree"] -= 5
        x["matched_fraction"] = x["matched"] / x["lead_keys"]
        x["lead_only"] = sorted(drops)
        e["pooled"]["matched"] -= 5
        e["pooled"]["agree"] -= 5
        e["pooled"]["matched_fraction"] = e["pooled"]["matched"] / e["pooled"]["lead_keys"]
    cases.append({"name": "drop", "lead": lead, "blind": d, "milestones": ms, "exit": 0, "expect": expect(drop_adj)})
    # change: one M1 singleton's claim gains a conjunct, so its class matches nothing
    d = new("change")
    lid = _singletons(lead, "M1")[-1]
    p = d / "laws" / "M1" / f"{lid}.json"
    law = load(p)
    st = dict(law["statement"])
    st["claim"] = {"all": [st["claim"], {"eq": [{"nat": 0}, {"nat": 1}]}]} if "all" not in st["claim"] \
        else {"all": st["claim"]["all"] + [{"eq": [{"nat": 0}, {"nat": 1}]}]}
    p.write_text(dumps(dict(law, statement=st)), encoding="utf-8")

    def change_adj(e):
        x = e["milestones"]["M1"]
        x["matched"] -= 1
        x["agree"] -= 1
        x["matched_fraction"] = x["matched"] / x["lead_keys"]
        x["lead_only"] = [lid]
        x["blind_only"] = [lid]
        e["pooled"]["matched"] -= 1
        e["pooled"]["agree"] -= 1
        e["pooled"]["matched_fraction"] = e["pooled"]["matched"] / e["pooled"]["lead_keys"]
    cases.append({"name": "change", "lead": lead, "blind": d, "milestones": ms, "exit": 0, "expect": expect(change_adj)})
    # mixed: a duplicate of one M0 law under a new id, with another status
    d = new("mixed")
    lid0 = _singletons(lead, "M0")[0]
    law = load(d / "laws" / "M0" / f"{lid0}.json")
    st0 = load(d / "results" / "M0" / f"{lid0}.json")["status"]
    _write_law(d, "M0", dict(law, law_id="L_dup_" + lid0[2:]), FLIP[st0])

    def mixed_adj(e):
        x = e["milestones"]["M0"]
        x["agree"] -= 1
        x["n_disagreements"] = 1
        x["blind_agreement"] = x["agree"] / x["matched"]
        e["pooled"]["agree"] -= 1
        e["pooled"]["blind_agreement"] = e["pooled"]["agree"] / e["pooled"]["matched"]
    cases.append({"name": "mixed", "lead": lead, "blind": d, "milestones": ms, "exit": 0, "expect": expect(mixed_adj),
                  "mixed": "MIXED:" + "+".join(sorted({st0, FLIP[st0]}))})
    # empty: laws without records
    d = new("empty")
    for m in ms:
        shutil.rmtree(d / "results" / m)
        (d / "results" / m).mkdir(parents=True)

    def empty_adj(e):
        for m in ms:
            x = e["milestones"][m]
            x["lead_only"] = sorted(l for law in [load(p) for p in sorted((lead / "laws" / m).glob("L*.json"))]
                                    for l in [law["law_id"]]
                                    if (lead / "results" / m / f"{l}.json").is_file())
            x.update(blind_keys=0, matched=0, agree=0, blind_agreement=None, matched_fraction=0.0)
        e["pooled"].update(matched=0, agree=0, blind_agreement=None, matched_fraction=0.0)
    cases.append({"name": "empty", "lead": lead, "blind": d, "milestones": ms, "exit": 0, "expect": expect(empty_adj)})
    cases.append({"name": "threshold-fail", "lead": lead, "blind": d, "milestones": ms, "exit": 1,
                  "args": ["--threshold", "0.9"]})
    # a tree without the milestone's directories
    d = tmp / "missing"
    (d / "laws").mkdir(parents=True)
    cases.append({"name": "missing", "lead": lead, "blind": d, "milestones": ["M3"], "exit": 2})
    for c in cases:
        if "expect" in c:
            c["instrument"] = compare(c["lead"], c["blind"], c["milestones"])
    return cases


FIELDS = ("lead_keys", "blind_keys", "matched", "agree", "blind_agreement", "matched_fraction")


def perturbation_problems(case: dict, rep: dict) -> list[str]:
    bad = []
    e, ins = case["expect"], case["instrument"]
    for m in case["milestones"]:
        g = (rep.get("milestones") or {}).get(m) or {}
        x = e["milestones"][m]
        for k in FIELDS:
            if g.get(k) != x[k]:
                bad.append(f"{m}: {k} {g.get(k)!r}, expected {x[k]!r}")
            if ins["milestones"][m][k] != x[k]:
                bad.append(f"{m}: the instrument's {k} {ins['milestones'][m][k]!r} disagrees with the closed form "
                           f"{x[k]!r}")
        nd = x.get("n_disagreements", 0)
        if len(g.get("disagreements") or []) != nd:
            bad.append(f"{m}: {len(g.get('disagreements') or [])} disagreements, expected {nd}")
        if not case.get("ids_renamed"):
            for k in ("lead_only", "blind_only"):
                if g.get(k) != x[k]:
                    bad.append(f"{m}: {k} {g.get(k)!r:.120}, expected {x[k]!r:.120}")
        for k in ("lead_keys", "blind_keys", "matched", "agree", "blind_agreement", "matched_fraction", "lead_only",
                  "blind_only", "disagreements", "unrecorded", "facts_differ"):
            if g.get(k) != ins["milestones"][m][k]:
                bad.append(f"{m}: {k} differs from the instrument's recomputation")
    for k in ("lead_keys", "matched", "agree", "blind_agreement", "matched_fraction"):
        if (rep.get("pooled") or {}).get(k) != e["pooled"][k]:
            bad.append(f"pooled {k} {(rep.get('pooled') or {}).get(k)!r}, expected {e['pooled'][k]!r}")
    if case.get("mixed"):
        ds = (rep.get("milestones") or {}).get("M0", {}).get("disagreements") or []
        if not ds or ds[0]["blind"]["status"] != case["mixed"]:
            bad.append(f"the duplicated class's blind status is not {case['mixed']}")
    return bad


# ================================================================== rule R
def prereg_commit(root) -> str:
    for c in git(root, "rev-list", "--topo-order", "--reverse", "HEAD", "--", PREDICTIONS).split():
        try:
            doc = json.loads(show(root, c, PREDICTIONS))
        except (RuntimeError, ValueError):
            continue
        if KEY in (doc.get("iterations") or {}):
            return c
    raise RuntimeError(f"no commit holds the key {KEY}")


def own_commits(root) -> list[str]:
    ck = prereg_commit(root)
    chain = git(root, "rev-list", "--first-parent", "--reverse", f"{ck}..HEAD").split()
    out = []
    for c in chain:
        parents = git(root, "rev-list", "--parents", "-n", "1", c).split()[1:]
        if len(parents) > 1:
            continue
        out.append(c)
        added = git(root, "diff-tree", "-r", "--no-commit-id", "--name-only", "--diff-filter=A", c).split()
        if "docs/iterations/I82.md" in added:
            break
    return out


def changed_files(root, commits) -> set[str]:
    out = set()
    for c in commits:
        out.update(f for f in git(root, "diff-tree", "-r", "--no-commit-id", "--name-only", "--no-renames", c).split())
    return out


def own_commit_problems(root) -> list[str]:
    bad = []
    for f in sorted(changed_files(root, own_commits(root))):
        if f not in ALLOWED_FILES and not f.startswith(ALLOWED_PREFIXES):
            bad.append(f"an own commit changes {f}")
    return bad


CLOSURES = r'''
import json, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
from holon import records, profile
from holon.records import _holon_imports
from holon.sorts import run3
from holon.undo import run as urun
from holon.fact import run as frun
from holon.disch import run as drun
from holon.versions import run as vrun
files = set()
for v in records.GENERATORS:
    files |= set(records.generator_files(v, root))
files |= set(profile.generator_files(root))
def closure(start):
    seen, todo = set(), list(start)
    while todo:
        r = todo.pop()
        if r in seen or not (root / r).is_file():
            continue
        seen.add(r)
        if r.endswith(".py"):
            todo.extend(sorted(_holon_imports(r, root) - seen))
    return seen
for start in (run3.GEN3, list(urun.GEN_UNDO) + list(run3.GEN3), list(frun.GEN_FACT) + list(run3.GEN3),
              list(run3.GEN3) + list(drun.GEN_DISCH), list(vrun.GEN_VERSIONS) + list(run3.GEN3)):
    files |= closure(start)
print(json.dumps(sorted(files)))
'''


def closure_files(root) -> set[str]:
    p = subprocess.run([sys.executable, "-c", CLOSURES, str(root)], capture_output=True, text=True, cwd=str(root))
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-2000:])
    return set(json.loads(p.stdout))


def closure_and_naming_problems(root) -> list[str]:
    root = Path(root)
    bad = []
    closures = closure_files(root)
    for f in sorted(changed_files(root, own_commits(root)) & closures):
        bad.append(f"an own commit changes {f}, a generator closure file")
    for f in ("holon/report.py", "holon/blind.py"):
        src = (root / f).read_text(encoding="utf-8")
        if re.search(r"""["']L_[A-Za-z0-9]""", src):
            bad.append(f"{f} holds a law-id literal")
        if re.search(r"^\s*(from|import)\s+tests", src, re.M):
            bad.append(f"{f} imports a test module")
        if f in closures:
            bad.append(f"{f} is in a generator closure")
    return bad
