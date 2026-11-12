"""python -m holon eval holon (I51): HOLON on the corpus pre-fix commits.

  python -m holon eval holon [--root DIR] [--entries ID,ID,..] [--check]

The contract is the docstring of the test file key I51 names (rules H0-H9, S1-S6); the run protocol is
spec/M4/lib/i51_run.json. For every entry of spec/eval/corpus.json (or the named ones) this module:

  H1  checks the entry's pre-fix commit out of holon's own partial clone (holon.eval.common.repo_cache) as a detached
      worktree in a scratch directory;
  H2  generates the extraction inputs from the entry alone (a transitions sidecar per contract a .sol file declares, a
      Go frontend config per package of a .go file) and runs `holon extract solidity` / `holon extract go`;
  H3  forms test milestone <protocol milestone> in a scratch root from the transitions documents, with generated
      generic typed-sorts, DISCH, UNDO and FACT sidecars, and runs holon sorts, types, model, disch and derive;
  H4  runs holon run over the milestone and then over every law still without a record;
  H5  reads each REFUTED record's replay status (no binding is generated, so nothing replays on real code);
  S1-S6 scores the entry against its I48 label and writes its row.

Everything is written under <out>/<id>/ (sidecars, facts, laws, gen, records) and <out>/corpus.json; timings only in
<out>/corpus_timing.json. Nothing here names a target or a corpus system: every repository, commit, file and label comes
from the manifest, every value of a generated input from the protocol. No fact, law, sidecar or proof is hand-written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import common
from . import gowork
from .gitfacts import DIFF_OPTIONS

PROTOCOL_REL = "spec/M4/lib/i51_run.json"
RULES = ("PAR", "SORT", "DISCH", "UNDO", "NAT", "FACT", "SYM", "OWN")
CLASSES = ("true_defect", "intended_asymmetry", "model_defect", "unreplayed")
COPY_DIRS = ("holon", "config", "spec", "bend", "schemas")
_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", "heldout")
VAULT: Path | None = None   # I110 (--vault DIR): where withhold() keeps the withheld per-law outputs, outside the repo


# ---------------------------------------------------------------------------------------------- small helpers
def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Ctx:
    """Paths of one entry's run and the normalizer of recorded messages (protocol normalize)."""

    def __init__(self, scratch: Path, checkout: Path):
        self.scratch, self.checkout = scratch, checkout

    def norm(self, text: str) -> str:
        return paths_out(text or "", self).strip()[-1500:]


def paths_out(t: str, ctx: Ctx) -> str:
    """Scratch, checkout and home paths written as <checkout>, <root>, <scratch>, <home>, <tmp>; elapsed times <s>."""
    for p, tok in ((ctx.checkout, "<checkout>"), (ctx.scratch / "root", "<root>"), (ctx.scratch, "<scratch>")):
        for v in sorted({str(p), os.path.realpath(p)}, key=len, reverse=True):
            t = t.replace(v, tok)
    t = re.sub(r"(?<![A-Za-z0-9_.>-])" + re.escape(str(Path.home())) + r"(?=/|\b)", "<home>", t)
    t = re.sub(r"(?<![A-Za-z0-9_.>-])" + re.escape(tempfile.gettempdir()) + r"/[A-Za-z0-9._-]+", "<tmp>", t)
    return re.sub(r"\b\d+(\.\d+)? ?s\b", "<s>", t)


def holon_sha256(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted((root / "holon").rglob("*.py")):
        rel = p.relative_to(root).as_posix()
        h.update(rel.encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def toolchain(root: Path) -> dict:
    cfg = common.load_json(root / "config" / "holon.json")
    try:
        go = subprocess.run(["go", "version"], capture_output=True, text=True, timeout=120).stdout.strip()
    except OSError:
        go = None
    return {"go": go, "bend": cfg["bend"]["pinned_version"], "solc_sha256": cfg["replay"]["solc_sha256"],
            "go_pinned": cfg["replay"]["go_version"]}


# ---------------------------------------------------------------------------------------------- H1: checkout
def checkout(entry: dict, dest: Path) -> tuple[Path, str]:
    d = common.repo_cache(entry["repo"])
    sha = entry["prefix_commit"]
    if sha not in common.reachable(d) and sha not in common.reachable(d, refresh=True):
        raise common.Refused(f"{entry['repo']}@{sha} is not reachable from a branch or tag")
    fix = entry["fix_commit"]
    if fix not in common.reachable(d):
        raise common.Refused(f"{entry['repo']}@{fix} is not reachable from a branch or tag")
    subprocess.run(["git", "-C", str(d), "worktree", "prune"], capture_output=True, env=common.git_env())
    common.git(d, "worktree", "add", "--detach", "--force", str(dest), sha, timeout=7200)
    return d, common.git(d, "rev-parse", sha + "^{tree}").strip()


def drop_worktree(clone: Path, dest: Path) -> None:
    subprocess.run(["git", "-C", str(clone), "worktree", "remove", "--force", str(dest)], capture_output=True,
                   env=common.git_env())


# ---------------------------------------------------------------------------------------------- S1: the locus
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", re.M)


def intervals(diff_text: str) -> list[list[int]]:
    """Old-side intervals of a -U0 diff's hunks (rule S1), merged when they overlap or touch."""
    raw = []
    for m in _HUNK.finditer(diff_text):
        start = int(m.group(1))
        count = 1 if m.group(2) is None else int(m.group(2))
        raw.append((start, start + count - 1) if count else (max(start, 1), start + 1))
    merged: list[list[int]] = []
    for s, t in sorted(raw):
        if merged and s <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], t)
        else:
            merged.append([s, t])
    return merged


def locus(clone: Path, entry: dict) -> dict:
    out = {}
    for f in entry["files"]:
        txt = common.git(clone, *DIFF_OPTIONS, "-U0", entry["prefix_commit"], entry["fix_commit"], "--", f,
                         text=False).decode("utf-8", errors="replace")
        out[f] = intervals(txt)
    return out


# ---------------------------------------------------------------------------------------------- H2: extraction inputs
def tag(proto: dict) -> str:
    """'<iteration>: ... (<protocol path>' of the generated inputs' doc strings (I51's text under I51's protocol)."""
    return f"{proto['iteration']}", proto.get("_path", PROTOCOL_REL)


def contracts_of(text: str, pattern: str) -> list[str]:
    rx = re.compile(pattern)
    return [m.group(1) for line in text.splitlines() for m in [rx.match(line)] if m]


def _compiler(comp: dict, proto: dict, ck: Path, unit: str) -> dict:
    """The sidecar's compiler: the protocol's, plus (I108, holon.eval.layout L1-L2) the unit's Foundry project's
    remappings as solc's settings.remappings when the protocol has a layout."""
    c = json.loads(json.dumps(comp))
    if proto.get("layout"):
        from . import layout as LY
        rs = [r["remapping"] for r in LY.remappings(ck, LY.project_of(ck, unit))]
        if rs:
            c.setdefault("settings", {})["remappings"] = rs
    return c


def solidity_sidecars(entry: dict, proto: dict, ck: Path, base_rel: str) -> list[dict]:
    """One transitions sidecar per contract each .sol file declares (in file order), or a none_declared record."""
    sol = proto["solidity"]
    owner, name = common.gh_slug(entry["repo"])
    out, seen = [], {}
    for f in [x for x in entry["files"] if x.endswith(".sol")]:
        p = ck / f
        text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
        cs = contracts_of(text, sol["contract_pattern"])
        if not cs:
            out.append({"language": "solidity", "source_file": f, "unit": None, "status": "none_declared",
                        "reason": f"{f} declares no contract (pattern {sol['contract_pattern']})"})
            continue
        for c in cs:
            low = c.lower()
            seen[low] = seen.get(low, 0) + 1
            stem = low if seen[low] == 1 else f"{low}_{seen[low]}"
            fname = f"{stem}.extracted.json"
            side = {"sidecar_version": 1, "frontend": "solidity",
                    "doc": f"{tag(proto)[0]}: generated from corpus entry {entry['id']} by holon eval holon ({tag(proto)[1]} "
                           "solidity): the contract a file of the entry declares",
                    "target": {"repo": f"{owner}/{name}", "commit": entry["prefix_commit"],
                               "scope": f"contract {c} of {f}"},
                    "output": f"{base_rel}/facts/{fname}", "sources": [f],
                    "compiler": _compiler(sol["compiler"], proto, ck, f),
                    "transitions": {"contract": c, "commit_interfaces": list(sol["commit_interfaces"]),
                                    # I109 (e): the protocol's recorded term budget (absent: the frontend's default)
                                    **({"term_budget": int(sol["term_budget"])} if sol.get("term_budget") else {})}}
            out.append({"language": "solidity", "source_file": f, "unit": c, "stem": stem, "file": fname,
                        "sidecar": side})
    return out


def _module_of(ck: Path, f: str) -> Path | None:
    d = (ck / f).parent
    while True:
        if (d / "go.mod").is_file():
            return d
        if d == ck or ck not in d.parents:
            return None
        d = d.parent


def _gomod(p: Path) -> dict:
    text = (p / "go.mod").read_text(encoding="utf-8", errors="replace")
    mod = re.search(r"(?m)^\s*module\s+(\S+)", text)
    gov = re.search(r"(?m)^\s*go\s+(\S+)", text)
    reps = []
    body = re.sub(r"//[^\n]*", "", text)
    for blk in re.findall(r"(?ms)^\s*replace\s*\((.*?)\)", body):
        reps += [ln for ln in blk.splitlines() if "=>" in ln]
    reps += re.findall(r"(?m)^\s*replace\s+([^(\n][^\n]*=>[^\n]*)$", body)
    rel = []
    for ln in reps:
        tgt = ln.split("=>", 1)[1].strip().split()[0].strip('"')
        if tgt.startswith("./") or tgt.startswith("../") or tgt in (".", ".."):
            rel.append(tgt)
    return {"module": mod.group(1).strip('"') if mod else None, "go": gov.group(1) if gov else None, "rel": rel}


def go_inputs(entry: dict, proto: dict, ck: Path) -> list[dict]:
    """One Go package per directory of the entry's .go files: its module, import path and source (protocol go)."""
    pk = {}
    fails = []
    for f in [x for x in entry["files"] if x.endswith(".go")]:
        m = _module_of(ck, f)
        if m is None:
            fails.append({"language": "go", "source_file": f, "unit": None, "status": "failed", "exit": None,
                          "reason": f"{f}: no go.mod at or above its directory"})
            continue
        gm = _gomod(m)
        if not gm["module"]:
            fails.append({"language": "go", "source_file": f, "unit": None, "status": "failed", "exit": None,
                          "reason": f"{f}: its go.mod has no module line"})
            continue
        reldir = (ck / f).parent.relative_to(m).as_posix()
        ip = gm["module"] if reldir == "." else f"{gm['module']}/{reldir}"
        pk.setdefault(ip, {"module_dir": m, "files": []})["files"].append(f)
    out = []
    for n, ip in enumerate(sorted(pk), start=1):
        out.append({"language": "go", "source_file": ",".join(sorted(pk[ip]["files"])), "unit": ip,
                    "stem": f"go_{n}", "file": f"go_{n}.go.extracted.json", "module_dir": pk[ip]["module_dir"]})
    return out + fails


def go_source(ck: Path, module_dir: Path, scratch: Path, rule: str | None = None) -> tuple[Path | None, str]:
    """The source the frontend copies (protocol go.source): the module directory, or a scratch copy of the checkout
    with a generated go.work when a relative replace leaves the module (rule main_module, I103: holon.eval.gowork;
    (None, reason) when it records a conflict)."""
    gm = _gomod(module_dir)
    leaves = [t for t in gm["rel"] if module_dir not in (module_dir / t).resolve().parents
              and (module_dir / t).resolve() != module_dir]
    if not leaves:
        return module_dir, "module"
    src = scratch / "gosrc"
    if not src.exists():
        shutil.copytree(ck, src, symlinks=True, ignore=shutil.ignore_patterns(".git"))
    if (ck / "go.work").is_file():
        return src, "checkout go.work"
    if rule is not None:
        g = gowork.generate(ck, module_dir, rule)
        if g["text"] is None:
            return None, gowork.conflict_reason(g)
        (src / "go.work").write_text(g["text"])
        return src, "generated go.work: " + " ".join(g["uses"]) + "".join(
            f"; replace {r['line']} (from {r['from']})" for r in g["replaces"])
    uses, todo = [], [module_dir.resolve()]
    while todo:
        d = todo.pop()
        if d in uses or not (d / "go.mod").is_file() or ck.resolve() not in [d, *d.parents]:
            continue
        uses.append(d)
        todo += [(d / t).resolve() for t in _gomod(d)["rel"]]
    rels = sorted("./" + u.relative_to(ck.resolve()).as_posix() if u != ck.resolve() else "." for u in uses)
    text = f"go {gm['go'] or '1.21'}\n\nuse (\n" + "".join(f"\t{r}\n" for r in rels) + ")\n"
    (src / "go.work").write_text(text)
    return src, "generated go.work: " + " ".join(rels)


_SOLC_SEL = re.compile(r"solc (\d+\.\d+\.\d+) \(selected by pragma (\[[^\]]*\])\)")
_GO_SEL = re.compile(r"go (\d+\.\d+\.\d+) \(go directive (\S+) of (\S+)\)")


def toolchain_text(d: dict, facts: Path) -> str | None:
    """I103 (F7): the toolchain a document's frontend selected and why, from the document (extracted) or the
    frontend's reason; None when no selection was reached (or the protocol selects none)."""
    if d.get("status") == "extracted" and d.get("file") and (facts / d["file"]).is_file():
        ext = json.loads((facts / d["file"]).read_text(encoding="utf-8")).get("extraction") or {}
        sol = (ext.get("toolchain") or {}).get("solc")
        if sol and sol.get("selected_by"):
            return (f"solc {sol['version'].split('+', 1)[0]} (selected by pragma {sol['selected_by']['pragmas']}; "
                    f"arithmetic {sol['arithmetic']})")
        tool = ext.get("tool") or {}
        if tool.get("selected_by"):
            sb = tool["selected_by"]
            return f"go {tool['go'].removeprefix('go')} (go directive {sb['directive']} of {sb['file']})"
        return None
    r = d.get("reason") or ""
    m = _SOLC_SEL.search(r)
    if m:
        return f"solc {m.group(1)} (selected by pragma {m.group(2)})"
    m = _GO_SEL.search(r)
    if m:
        return f"go {m.group(1)} (go directive {m.group(2)} of {m.group(3)})"
    return None


# ---------------------------------------------------------------------------------------------- stage runner
class Runner:
    def __init__(self, ctx: Ctx, root: Path, proto: dict, timing: dict):
        self.ctx, self.root, self.proto, self.timing = ctx, root, proto, timing
        self.env = {**os.environ, "PYTHONPATH": str(root), "BEND_NO_TELEMETRY": "1",
                    "HOLON_BUILD_DIR": str(root.parent / "build")}
        self.env.pop("HOLON_TRACE", None)

    def holon(self, stage: str, args: list[str], timeout_key: str | None = None) -> dict:
        t0 = time.monotonic()
        tmo = self.proto["timeouts_s"].get(timeout_key or stage, 3600)
        try:
            p = subprocess.run([sys.executable, "-m", "holon", *args], cwd=self.root, env=self.env,
                               capture_output=True, text=True, timeout=tmo)
            res = {"status": "ok" if p.returncode == 0 else "failed", "exit": p.returncode,
                   "detail": self.ctx.norm(p.stderr if p.returncode else p.stdout)}
        except subprocess.TimeoutExpired:
            res = {"status": "timeout", "exit": None, "detail": f"timeout after {tmo} s"}
        self.timing[stage] = round(self.timing.get(stage, 0) + time.monotonic() - t0, 1)
        return res


def scratch_root(root: Path, dest: Path, slug: str, ck: Path) -> Path:
    """A copy of the code and spec inputs; its config names no dependency tree and maps the entry's repository to the
    checkout (extract.sources, as config/holon.json maps the development target's)."""
    s = dest / "root"
    s.mkdir(parents=True)
    for d in COPY_DIRS:
        if (root / d).is_dir():
            shutil.copytree(root / d, s / d, ignore=_IGNORE)
    cfg = common.load_json(s / "config" / "holon.json")
    cfg["replay"]["sol_deps"] = None
    cfg.setdefault("extract", {})["sources"] = {slug: str(ck)}
    (s / "config" / "holon.json").write_text(dumps(cfg))
    return s


# ---------------------------------------------------------------------------------------------- S2-S6: scoring
def _strings(x, out: list) -> None:
    if isinstance(x, str):
        out.append(x)
    elif isinstance(x, dict):
        for k in sorted(x):
            out.append(k)
            _strings(x[k], out)
    elif isinstance(x, list):
        for y in x:
            _strings(y, out)


def spans(objs, files: list[str]) -> list[list]:
    strs: list[str] = []
    _strings(objs, strs)
    got = set()
    for f in files:
        rx = re.compile(r"(?<![A-Za-z0-9_./-])" + re.escape(f) + r":([1-9][0-9]*)(?:-([1-9][0-9]*))?")
        for s in strs:
            for m in rx.finditer(s):
                a = int(m.group(1))
                b = int(m.group(2)) if m.group(2) else a
                got.add((f, a, max(a, b)))
    return [list(t) for t in sorted(got)]


def meets(sites: list[list], loc: dict) -> bool:
    return any(a <= t and s <= b for f, a, b in sites for s, t in loc.get(f, []))


def classify(replay_status, is_localized: bool) -> str:
    if replay_status == "failed":
        return "model_defect"
    if is_localized:
        return "true_defect"
    if replay_status == "passed":
        return "intended_asymmetry"
    return "unreplayed"


def law_rows(edir: Path, files: list[str], loc: dict) -> list[dict]:
    lawd = edir / "laws"
    if not lawd.is_dir():
        return []
    der = {}
    if (lawd / "DERIVATION.json").is_file():
        der = {e["law_id"]: e for e in common.load_json(lawd / "DERIVATION.json")["laws"]}
    out = []
    for p in sorted(lawd.glob("L*.json")):
        law = common.load_json(p)
        lid = p.stem
        rp = edir / "records" / f"{lid}.json"
        rec = common.load_json(rp) if rp.is_file() else {}
        objs = [law, der.get(lid, {}), rec]
        w = rec.get("witness") or {}
        acts = {s.get("action") for s in (w.get("steps") or []) if isinstance(s, dict)}
        if acts:
            fp = edir / "facts" / Path(law["facts"]).name
            doc = common.load_json(fp) if fp.is_file() else {}
            objs += [a.get("src") for a in doc.get("actions") or [] if a.get("name") in acts]
        st = rec.get("status") if rec else "UNKNOWN"
        site = spans(objs, files)
        loc_ok = meets(site, loc)
        rs = (rec.get("replay") or {}).get("status") if rec else None
        out.append({"law_id": lid, "rule": law.get("rule"), "subform": law.get("subform"), "status": st,
                    "sites": site, "localized": loc_ok, "replay": rs,
                    "class": classify(rs, loc_ok) if st == "REFUTED" else None})
    return out


def summarize(rows: list[dict]) -> dict:
    rec = {}
    for r in RULES:
        es = [x for x in rows if x["label"] == r]
        if es:
            det = [x["id"] for x in es if x["detected"]]
            rec[r] = {"entries": len(es), "detected": det, "recall": len(det) / len(es)}
    counts = dict.fromkeys(CLASSES, 0)
    for x in rows:
        for law in x["laws"]:
            if law["status"] == "REFUTED":
                counts[law["class"]] += 1
    n = sum(counts.values())
    return {"recall": rec, "detected_any": [x["id"] for x in rows if x["detected_any"]], "findings": n,
            "classes": counts, "precision": counts["true_defect"] / n if n else None}


# ---------------------------------------------------------------------------------------------- one entry
def run_entry(entry: dict, proto: dict, root: Path, stage_dir: Path, timing: dict, roles: dict | None = None,
              compose: bool = False) -> dict:
    """Run one entry; write its <id>/ directory into stage_dir; return its row. compose (I110 (b), the --compose
    opt-in): also the Go machines of every extracted Go package, the inferred roles installed, and route C's stages
    (codecs or the Go-op documents, diagram, evidence) before route A's sorts .. derive, run and replay."""
    rel = f"{proto['out']}/{entry['id']}"
    edir = stage_dir / entry["id"]
    edir.mkdir(parents=True)
    tmp = Path(tempfile.mkdtemp(prefix="holon-i51-"))
    ck = tmp / "checkout"
    ctx = Ctx(tmp, ck)
    row = {k: entry[k] for k in ("id", "system", "repo", "prefix_commit", "fix_commit", "label", "files")}
    stages: dict = {}
    docs: list = []
    machines: list = []
    clone = None
    subs: list = []
    try:
        t0 = time.monotonic()
        try:
            clone, tree = checkout(entry, ck)
            stages["checkout"] = {"status": "ok", "exit": 0, "detail": ""}
        except (common.Refused, RuntimeError, subprocess.TimeoutExpired) as e:
            raise SystemExit(f"holon eval holon: {entry['id']}: checkout failed: {ctx.norm(str(e))}")
        timing["checkout"] = round(time.monotonic() - t0, 1)
        row["tree"] = tree
        row["locus"] = locus(clone, entry)
        owner, name = common.gh_slug(entry["repo"])
        S = scratch_root(root, tmp, f"{owner}/{name}", ck)
        R = Runner(ctx, S, proto, timing)
        (S / rel / "sidecars").mkdir(parents=True)
        (S / rel / "facts").mkdir(parents=True)
        if proto.get("layout"):
            # I108 (holon.eval.layout L3): the submodules at their gitlinked commits, recorded in sidecars/layout.json
            from . import layout as LY
            t1 = time.monotonic()
            subs = LY.submodules(ck, entry["prefix_commit"], entry["repo"], init=True, root=root)
            timing["submodules"] = round(time.monotonic() - t1, 1)
            (S / rel / "sidecars" / "layout.json").write_text(dumps(
                {"layout_version": LY.LAYOUT_VERSION, "submodules": [{k: ctx.norm(v) if isinstance(v, str) else v
                                                                      for k, v in r.items()} for r in subs]}))
        # H2 Solidity
        for d in solidity_sidecars(entry, proto, ck, rel):
            if "sidecar" not in d:
                docs.append(d)
                continue
            sp = S / rel / "sidecars" / f"extract_{d['stem']}.json"
            sp.write_text(dumps(d.pop("sidecar")))
            res = R.holon("extract", ["extract", "solidity", "--root", str(S), "--sidecar", str(sp), "--source", str(ck),
                                      "--out", str(S / rel / "facts" / d["file"])])
            d.update({"status": "extracted" if res["status"] == "ok" else "failed", "exit": res["exit"],
                      "reason": None if res["status"] == "ok" else res["detail"]})
            docs.append(d)
        # H2 Go
        for d in go_inputs(entry, proto, ck):
            if "stem" not in d:
                docs.append(d)
                continue
            src, how = go_source(ck, d.pop("module_dir"), tmp, proto["go"].get("work_replace"))
            if src is None:   # rule main_module: a replace conflict the package's own module does not settle
                d.update({"status": "failed", "exit": None, "reason": how, "source": "generated go.work: none"})
                docs.append(d)
                continue
            cfg = {"config_version": proto["go"]["config_version"],
                   "doc": f"{tag(proto)[0]}: generated from corpus entry {entry['id']} by holon eval holon ({tag(proto)[1]} go)",
                   "target": {"repo": f"{owner}/{name}", "commit": entry["prefix_commit"]},
                   "source": {"path": "<given by --src>"}, "documents": {d["stem"]: [d["unit"]]},
                   "primitives": dict(proto["go"]["primitives"]), "limits": dict(proto["go"]["limits"]),
                   **({"toolchain": proto["go"]["toolchain"]} if proto["go"].get("toolchain") else {})}
            cp = S / rel / "sidecars" / f"{d['stem']}.json"
            cp.write_text(dumps(cfg))
            res = R.holon("extract", ["extract", "go", "--root", str(S), "--config", str(cp), "--src", str(src),
                                      "--out-dir", str(S / rel / "facts")])
            d.update({"status": "extracted" if res["status"] == "ok" else "failed", "exit": res["exit"],
                      "reason": None if res["status"] == "ok" else res["detail"], "source": how})
            docs.append(d)
            if compose:   # I110 (b): I105's Go machines of the same package, from the same source
                machines += go_machines(R, S, rel, proto, entry, d, cfg, src, tmp)
        for d in docs:
            d["toolchain"] = toolchain_text(d, S / rel / "facts")
            if d.get("status") == "extracted":
                b = (S / rel / "facts" / d["file"]).read_bytes()
                d["sha256"], d["bytes"] = sha256_bytes(b), len(b)
                d["stored"] = d["language"] == "solidity" or len(b) <= proto["go"]["store_max_bytes"]
                if not d["stored"]:
                    (S / rel / "facts" / d["file"]).unlink()
        ext = [d for d in docs if d.get("status") == "extracted"]
        stages["extract"] = {"status": "ok" if ext else "failed", "exit": None,
                             "detail": f"{len(ext)} of {len(docs)} documents extracted"}
        sol = [d for d in ext if d["language"] == "solidity"]
        M = proto["milestone"]
        if compose:
            mx = [m for m in machines if m["status"] == "extracted"]
            stages["machines"] = {"status": "ok" if mx else ("not_applicable" if not machines else "failed"),
                                  "exit": None, "detail": f"{len(mx)} machine documents from {len(machines)} "
                                  "Go packages" if machines else "no Go package extracted"}
            sol = sol + [{"file": f} for m in mx for f in m["files"]]
        lib = S / "spec" / M / "lib"
        before = sorted(p.name for p in lib.iterdir()) if lib.is_dir() else []
        # I104 opt-in (--roles): the role sidecars holon roles infers from the stored documents; under --compose also when
        # only machine documents exist (I110: the counted run's c12 showed derive then has no adoption sidecar)
        if roles and (ext or (compose and any("language" not in d for d in sol))):
            rels = [f"{rel}/facts/{d['file']}" for d in ext if (S / rel / "facts" / d["file"]).is_file()]
            if compose:
                rels += [f"{rel}/facts/{d['file']}" for d in sol if "language" not in d]
            args = ["roles", "--milestone", M, "--root", str(S), "--documents", ",".join(rels), "--out-dir",
                    str(S / rel / "sidecars" / "roles"), "--mode", roles["mode"]]
            if roles.get("proposed"):
                args += ["--proposed", roles["proposed"]]
            if compose:   # I110 (b): installed where no hand sidecar exists (holon.roles.cli.install, mode hand)
                args += ["--install", "--roles", "hand"]
            stages["roles"] = R.holon("roles", args)
            mp = S / rel / "sidecars" / "roles" / "roles.json"
            if mp.is_file():
                man = json.loads(mp.read_text())
                kinds: dict = {}
                for x in man["roles"]:
                    kinds[f"{x['sidecar']}:{x['roles_source']}"] = kinds.get(f"{x['sidecar']}:{x['roles_source']}", 0) + 1
                row["roles"] = {"mode": roles["mode"], "count": len(man["roles"]), "kinds": dict(sorted(kinds.items())),
                                "proposed": man.get("proposed")}
        if compose:
            row["roles_sources"] = roles_sources(lib, before, roles)
        if ext and not sol:
            stages["derive"] = {"status": "no_producer", "exit": None, "detail": proto["go_rules_doc"]}
        if sol:
            _rules(R, S, rel, M, proto, sol, stages, (lambda: _route_c(R, S, M, lib, stages)) if compose else None)
            if getattr(R, "run_outputs", None) and VAULT is not None:   # I112: each runner's own output (law ids)
                (VAULT / entry["id"]).mkdir(parents=True, exist_ok=True)
                (VAULT / entry["id"] / "run_outputs.json").write_text(dumps(R.run_outputs))
        # copy the outputs
        for sub, frm in (("sidecars", S / rel / "sidecars"), ("facts", S / rel / "facts"), ("laws", S / "laws" / M),
                         ("gen", S / "gen" / M), ("records", S / "results" / M)):
            if frm.is_dir() and any(frm.iterdir()):
                shutil.copytree(frm, edir / sub, ignore=_IGNORE)
        _scrub(edir, ctx)
        if compose:
            store_large(edir, proto["go"]["store_max_bytes"])
    finally:
        if subs:
            from . import layout as LY
            LY.drop_submodules(ck, subs)
        if clone is not None:
            drop_worktree(clone, ck)
        shutil.rmtree(tmp, ignore_errors=True)
    keys = ("stem", "file", "language", "source_file", "unit", "status", "exit", "reason", "sha256", "bytes", "stored",
            "source")
    if proto["run_version"] != "holon-corpus-run/0.1":
        keys += ("toolchain",)
    row["documents"] = [{k: d.get(k) for k in keys} for d in docs]
    if compose:
        row["machines"] = machines
        row["compose"] = True
    if isinstance(stages.get("run"), dict) and "runners" in stages["run"]:   # I112: per-runner aggregates
        row["run_runners"] = stages["run"].pop("runners")
    row["stages"] = stages
    row["laws"] = law_rows(edir, entry["files"], row["locus"])
    if compose:   # I110 (b): every derived record carries the source of the role sidecars it was derived with
        for x in row["laws"]:
            x["roles_source"] = law_roles_source(row["roles_sources"])
    sb = edir / "gen" / "sorts" / "budget.json"
    if sb.is_file():   # I110 (a): the documents over the per-document sort budget (a stage reason, before any decision)
        b = json.loads(sb.read_text())
        row["sort_budget"] = {"sort_budget": b["sort_budget"], "documents": len(b["documents"]),
                              "over_budget": b["over_budget"],
                              "work": {x["model"]: x["work"] for x in b["documents"]}}
    op = edir / "gen" / "sorts" / "opaque.json"
    if op.is_file():   # I111 (c): documents typed versus opaque (a stage reason, before any decision: Q72)
        o = json.loads(op.read_text())
        row["types_opaque"] = {"documents": len(o["typed"]) + len(o["documents"]), "typed": len(o["typed"]),
                               "opaque": len(o["documents"]),
                               "misses": [{"document": x["document"].rsplit("/", 1)[-1], "term": x["term"]}
                                          for x in o["documents"]]}
    if proto.get("stop_after") == "derive":   # I108: no law is run, so none is decided
        for x in row["laws"]:
            x["status"] = "not_run"
    ext = [d for d in docs if d.get("status") == "extracted"]
    row["status"] = "run" if ext else "not_run"
    row["reason"] = None if ext else "no document extracted: " + "; ".join(
        f"{d.get('unit') or d['source_file']}: {d.get('reason')}" for d in docs) if docs else \
        "no document extracted: the entry has no .sol or .go file"
    ref = [x for x in row["laws"] if x["status"] == "REFUTED" and x["localized"]]
    row["detected"] = any(x["rule"] == entry["label"] for x in ref)
    row["detected_any"] = bool(ref)
    row["label_rule_laws"] = sum(1 for x in row["laws"] if x["rule"] == entry["label"])
    if roles:
        withhold(row, edir)
    return row


# ---------------------------------------------------------------------------------------------- I110 (b): compose
def go_machines(R: Runner, S: Path, rel: str, proto: dict, entry: dict, d: dict, cfg: dict, src: Path,
                tmp: Path) -> list:
    """I105's Go machine frontend over one Go package, from the source and config its codec extraction used, with the
    protocol's nil-map rule (compose.nil_maps; I109's default "unknown"). Each machine document is stored next to the
    codec documents as <stem>_<machine file> (one model per file, no two sharing a stem)."""
    mc = json.loads(json.dumps(cfg))
    mc["doc"] = f"{tag(proto)[0]}: generated from corpus entry {entry['id']} by holon eval holon --compose (Go machines)"
    mc["machines"] = {"nil_maps": proto["compose"]["nil_maps"]}
    cp = S / rel / "sidecars" / f"{d['stem']}_machines.json"
    cp.write_text(dumps(mc))
    out = tmp / "machines" / d["stem"]
    res = R.holon("machines", ["extract", "go_machines", "--root", str(S), "--config", str(cp), "--src", str(src),
                               "--out-dir", str(out)], timeout_key="extract")
    files = []
    if res["status"] == "ok":
        for p in sorted(out.glob("*.extracted.json")):
            name = f"{d['stem']}_{p.name}"
            shutil.copy(p, S / rel / "facts" / name)
            files.append(name)
    return [{"unit": d["unit"], "status": "extracted" if res["status"] == "ok" else "failed", "exit": res["exit"],
             "reason": None if res["status"] == "ok" else res["detail"], "files": files,
             "nil_maps": mc["machines"]["nil_maps"]}]


def roles_sources(lib: Path, before: list, roles: dict | None) -> dict:
    """The source of every role sidecar under spec/<M>/lib at derive: "hand" when it was there before holon roles ran
    (a hand sidecar always wins: install never replaces it), else the inference mode that wrote it."""
    from ..roles.cli import ROLE_SIDECARS
    out = {}
    for n in ROLE_SIDECARS:
        if (lib / n).is_file():
            out[n] = "hand" if n in before else (roles or {}).get("mode", "static")
    return out


def law_roles_source(sources: dict) -> str:
    """A law's roles_source: "none" when no role sidecar exists; "hand" when every one is a hand sidecar; else the
    inferred modes, sorted and joined with "+" (with "hand" when some are hand). Conservative: a law is attributed to
    every role sidecar of its milestone, whether or not its rule read one."""
    vals = sorted(set(sources.values()))
    return "none" if not vals else "+".join(vals)


def _route_c(R: Runner, S: Path, M: str, lib: Path, stages: dict) -> None:
    """I104's route C stages before the typed ones: holon codecs over a link role, else the Go-op documents a go_ops
    role names (holon.diagram.goops.render_all); then holon diagram and holon evidence. A stage that fails is recorded
    and the next one runs (derive decides whether it can go on)."""
    if (lib / "link.json").is_file():
        stages["codecs"] = R.holon("codecs", ["codecs", "--milestone", M], timeout_key="derive")
    elif (lib / "go_ops.json").is_file():
        t0 = time.monotonic()
        try:
            from ..diagram import goops as GO
            gd = GO.goops_dir(M, str(S))
            gd.mkdir(parents=True, exist_ok=True)
            for n, t in GO.render_all(str(S), M).items():
                (gd / n).write_text(t)
            stages["goops"] = {"status": "ok", "exit": 0, "detail": ""}
        except Exception as e:  # noqa: BLE001: a Go-op document the role cannot render is a recorded failure
            stages["goops"] = {"status": "failed", "exit": None, "detail": R.ctx.norm(f"{type(e).__name__}: {e}")}
        R.timing["goops"] = round(time.monotonic() - t0, 1)
    stages["diagram"] = R.holon("diagram", ["diagram", "--milestone", M], timeout_key="derive")
    stages["evidence"] = R.holon("evidence", ["evidence", "--milestone", M], timeout_key="derive")


def withhold(row: dict, edir: Path) -> None:
    """I104 under HUMAN_ANSWERS Q56 (the --roles opt-in): no per-law verdict, law id or class of a law derived through
    generated roles is written until a person adjudicates it. The row keeps per-family aggregates that never split
    PROVED from REFUTED, and one commitment: the sha256 of the sorted lines "<path> <sha256>" (each ending in a newline)
    of every file under the entry's laws/ and records/, which are then removed from the written output."""
    fam: dict = {}
    for x in row["laws"]:
        k = f"{x.get('rule')}/{x.get('subform')}"
        if "roles_source" in x:   # I110 (b): the composed driver's aggregates keep the law's roles_source
            k += f" roles_source={x['roles_source']}"
        f = fam.setdefault(k, {"derived": 0, "decided": 0, "unknown": 0})
        f["derived"] += 1
        f["decided" if x.get("status") in ("PROVED", "REFUTED") else "unknown"] += 1
    lines = []
    if VAULT is not None:   # I110: the withheld per-law outputs kept outside the repository (--vault), never committed
        for sub in ("laws", "records", "gen"):
            if (edir / sub).is_dir():
                shutil.copytree(edir / sub, VAULT / edir.name / sub, dirs_exist_ok=True)
    for sub in ("laws", "records"):
        d = edir / sub
        if d.is_dir():
            lines += [f"{sub}/{q.relative_to(d).as_posix()} {sha256_bytes(q.read_bytes())}"
                      for q in sorted(d.rglob("*")) if q.is_file()]
            shutil.rmtree(d)
    row["laws_aggregate"] = dict(sorted(fam.items()))
    row["laws_bundle_sha256"] = sha256_bytes(("".join(f"{x}\n" for x in sorted(lines))).encode())
    row["laws_bundle_files"] = len(lines)
    withhold_gen(row, edir, [x["law_id"] for x in row["laws"] if x.get("law_id")])
    row["laws"] = []
    for k in ("detected", "detected_any", "label_rule_laws"):
        row[k] = None   # withheld with the verdicts (Q56); the adjudicator's run decides them


def withhold_gen(row: dict, edir: Path, ids: list[str]) -> None:
    """I112 (3): the per-law outputs withhold() did not cover (I111's tools/i111_withhold_gen.py, in the driver). Every
    file under <id>/gen/ whose path or text names one of the entry's derived law ids is removed from the written
    output (the vault keeps the whole gen/), and so is every large_files.json entry whose path names one. They are
    recorded as <id>/gen_withheld.json {files, sha256}: the sha256 of the sorted lines "<sha256>  <path>" (I111's
    canonical form), with no path or id. Every law id inside a stage's detail is replaced by "<law id withheld>"."""
    if not ids:
        return
    by_len = sorted(set(ids), key=lambda x: (-len(x), x))
    names = lambda t: any(i in t for i in by_len)   # noqa: E731
    gone = []
    g = edir / "gen"
    if g.is_dir():
        for p in sorted(g.rglob("*")):
            if p.is_file():
                rel = p.relative_to(edir).as_posix()
                if names(rel) or names(p.read_text(encoding="utf-8", errors="ignore")):
                    gone.append((rel, sha256_bytes(p.read_bytes())))
                    p.unlink()
        for d in sorted((q for q in g.rglob("*") if q.is_dir()), key=lambda q: -len(q.parts)):
            if not any(d.iterdir()):
                d.rmdir()
    lf = edir / "large_files.json"
    if lf.is_file():
        rows = json.loads(lf.read_text(encoding="utf-8"))
        keep = [r for r in rows if not names(r["path"])]
        gone += [(r["path"], r["sha256"]) for r in rows if names(r["path"])]
        if len(keep) != len(rows):
            if keep:
                lf.write_text(dumps(keep))
            else:
                lf.unlink()
    if gone:
        lines = "".join(f"{h}  {rel}\n" for rel, h in sorted(gone, key=lambda x: x[0].encode()))
        (edir / "gen_withheld.json").write_text(dumps({"files": len(gone), "sha256": sha256_bytes(lines.encode())}))
    for st in (row.get("stages") or {}).values():
        d = st.get("detail")
        if isinstance(d, str):
            for i in by_len:
                d = d.replace(i, "<law id withheld>")
            st["detail"] = d


def _rules(R: Runner, S: Path, rel: str, M: str, proto: dict, sol: list, stages: dict, before_derive=None) -> None:
    """H3-H4 over the transitions documents. before_derive (I110 (b), --compose): route C's stages, run after disch
    and before derive (derive checks that the evidence it reads is what holon evidence writes over the final tree)."""
    sd = S / rel / "sidecars"
    docs = [f"{rel}/facts/{d['file']}" for d in sol]
    typed = {"sort_types_version": proto["typed"]["sort_types_version"],
             "doc": f"{tag(proto)[0]}: generated by holon eval holon ({tag(proto)[1]} typed)", "documents": docs,
             "seeds": proto["typed"]["seeds"], "binding": proto["typed"]["binding"], "search": proto["typed"]["search"],
             # I110 (a): the protocol's per-document sort budget (absent: the pass meters nothing, as before)
             **({"sort_budget": proto["typed"]["sort_budget"]} if "sort_budget" in proto["typed"] else {}),
             # I111 (Q77): the protocol's per-document types fallback (absent: holon types refuses as before)
             **({"types_fallback": proto["typed"]["types_fallback"]} if "types_fallback" in proto["typed"] else {}),
             # I112 (Q81): the refusal classes the fallback makes opaque (absent: I111's)
             **({"types_opaque_classes": proto["typed"]["types_opaque_classes"]}
                if "types_opaque_classes" in proto["typed"] else {})}
    disch = {**{k: proto["disch"][k] for k in ("disch_version", "binding", "hypotheses", "hypothesis_verdicts", "r0",
                                                "search")},
             "doc": f"{tag(proto)[0]}: generated by holon eval holon ({tag(proto)[1]} disch)", "documents": docs,
             "model_sidecar": f"{rel}/sidecars/sort_types.json"}
    undo = {**{k: proto["undo"][k] for k in ("undo_version", "observation", "premise", "search")},
            "doc": f"{tag(proto)[0]}: generated by holon eval holon ({tag(proto)[1]} undo)",
            "sort_types": f"{rel}/sidecars/sort_types.json"}
    fact = {**{k: proto["fact"][k] for k in ("fact_version", "binding", "hypotheses", "verdicts", "search", "measure",
                                              "term_size")},
            "doc": f"{tag(proto)[0]}: generated by holon eval holon ({tag(proto)[1]} fact)", "documents": docs,
            "sort_types": f"{rel}/sidecars/sort_types.json"}
    for n, v in (("sort_types", typed), ("disch", disch), ("undo", undo), ("fact", fact)):
        (sd / f"{n}.json").write_text(dumps(v))
    ts, ds, us, fs = (f"{rel}/sidecars/{n}.json" for n in ("sort_types", "disch", "undo", "fact"))
    sorts = f"gen/{M}/sorts"
    steps = [("sorts", ["sorts", "--milestone", M, "--root", str(S), "--sidecar", ts, "--out", sorts]),
             ("types", ["types", "--milestone", M, "--root", str(S), "--sidecar", ts, "--out", sorts]),
             ("model", ["model", "--milestone", M, "--root", str(S), "--sidecar", ts, "--out", f"{sorts}/models"]),
             ("disch", ["disch", "--milestone", M, "--root", str(S), "--sidecar", ds, "--out", f"gen/{M}/disch"]),
             ("derive", ["derive", "--milestone", M, "--root", str(S), "--catalog", proto["catalog"], "--sidecar", ts,
                         "--disch", ds, "--undo-sidecar", us, "--fact-sidecar", fs, "--out", f"laws/{M}",
                         "--obstructions", f"{sorts}/obstructions.json"])]
    for name, args in steps:
        if name == "derive" and before_derive is not None:
            before_derive()
        stages[name] = R.holon(name, args)
        if stages[name]["status"] != "ok":
            return
    laws = sorted(p.stem for p in (S / "laws" / M).glob("L*.json"))
    if proto.get("stop_after") == "derive":   # I108: a smoke measure; I107 runs and scores
        stages["run"] = {"status": "not_run", "exit": None,
                         "detail": f"the protocol stops after derive (stop_after): {len(laws)} laws derived, none run"}
        return
    if not laws:
        stages["run"] = {"status": "not_applicable", "exit": None, "detail": "no law derived"}
        return
    out = ["--out", f"results/{M}", "--gen-dir", f"gen/{M}"]
    if proto.get("run_routing") == "per_runner":   # I112 (Q82): each law to its rule family's runner, with its arguments
        # the record writer reads gen/<M>/coverage.json for a law over a Solidity transitions document
        # (holon.records.coverage_field); holon coverage reads the milestone's spec sidecars, so the composed route
        # accounts for its own extraction sidecars (the frontend's walk, as for any milestone)
        xs = sorted(p.relative_to(S).as_posix() for p in (S / rel / "sidecars").glob("extract_*.json"))
        if xs:
            stages["coverage"] = R.holon("coverage", ["coverage", "--milestone", M, "--root", str(S), "--sidecars",
                                                      ",".join(xs)], timeout_key="derive")
        _run_routed(R, S, M, proto, laws, stages, ts, ds, fs, out)
        return
    r1 = R.holon("run", ["run", "--milestone", M, "--sidecar", ts, "--disch", ds, "--fact-sidecar", fs, *out])
    left = [lid for lid in laws if not (S / "results" / M / f"{lid}.json").is_file()]
    r2 = None
    if left:
        r2 = R.holon("run", ["run", "--milestone", M, "--sidecar", ts, "--fact-sidecar", fs, "--laws", ",".join(left),
                             *out])
    still = [lid for lid in laws if not (S / "results" / M / f"{lid}.json").is_file()]
    stages["run"] = {"status": "ok" if r1["status"] == "ok" and (r2 is None or r2["status"] == "ok") else "failed",
                     "exit": None, "detail": f"run 1: {r1['status']} (exit {r1['exit']}); run 2 over {len(left)} laws: "
                     f"{'not needed' if r2 is None else r2['status'] + ' (exit ' + str(r2['exit']) + ')'}; "
                     f"{len(still)} laws not decided" + ("" if r1["status"] == "ok" else "; run 1: " + r1["detail"][-600:])
                     + ("" if r2 is None or r2["status"] == "ok" else "; run 2: " + r2["detail"][-600:])}
    stages["replay"] = {"status": "not_applicable", "exit": None, "detail": proto["replay"]}
    stages["filter"] = {"status": "ok", "exit": None, "detail": proto["filter"]}


# ---------------------------------------------------------------------------------------------- I112 (1): routing
RUNNERS = ("disch", "fact", "typed", "milestone")
TYPED_SORT_SUBFORMS = ("as_member", "realize", "reinterpret")


def runner_of(entry: dict) -> str:
    """The runner of a law's rule family, from its laws/<M>/DERIVATION.json entry (holon/__main__.py's dispatch): disch
    (rule DISCH, holon.disch.run's sub-forms), fact (FACT), typed (SORT's typed sub-forms, UNDO, SYM), milestone (every
    other law: PAR and route C's families, which holon run sends to holon.pipeline or to the runner its dispatch
    names)."""
    from ..disch.run import SUBFORMS as DISCH_SUBFORMS
    rule, sub = entry.get("rule"), entry.get("subform")
    if rule == "DISCH" and sub in DISCH_SUBFORMS:
        return "disch"
    if rule == "FACT":
        return "fact"
    if (rule == "SORT" and sub in TYPED_SORT_SUBFORMS) or rule in ("UNDO", "SYM"):
        return "typed"
    return "milestone"


def route(derivation: dict, laws: list[str]) -> dict:
    """{runner: [law id, ..]} for the given laws, in RUNNERS order, each list sorted; empty groups left out. A law with
    no DERIVATION.json entry goes to milestone (holon run decides whether it knows it)."""
    ent = {e.get("law_id"): e for e in derivation.get("laws") or [] if isinstance(e, dict)}
    out: dict = {}
    for lid in sorted(laws):
        out.setdefault(runner_of(ent.get(lid) or {}), []).append(lid)
    return {k: out[k] for k in RUNNERS if k in out}


def runner_args(runner: str, proto: dict, ts: str, ds: str, fs: str) -> list[str]:
    """The arguments a runner takes beyond --milestone, --laws, --out and --gen-dir."""
    if runner == "disch":
        se = (proto.get("disch") or {}).get("section_errors")
        return ["--sidecar", ts, "--disch", ds] + (["--section-errors", se] if se else [])
    if runner == "fact":
        return ["--sidecar", ts, "--fact-sidecar", fs]
    if runner == "typed":
        return ["--sidecar", ts]
    return []


def _run_routed(R: Runner, S: Path, M: str, proto: dict, laws: list[str], stages: dict, ts: str, ds: str, fs: str,
                out: list) -> None:
    """One holon run --laws per runner group. The stage detail is aggregates only (Q72: the run decides laws): per
    runner its laws, status, exit, records written and DISCH section errors; each runner's own output (which names
    law ids) is kept in R.run_outputs for the vault, never in the row."""
    der = common.load_json(S / "laws" / M / "DERIVATION.json")
    groups = route(der, laws)
    res: dict = {}
    R.run_outputs = getattr(R, "run_outputs", {})
    for k, ids in groups.items():
        r = R.holon("run", ["run", "--milestone", M, *runner_args(k, proto, ts, ds, fs), "--laws", ",".join(ids), *out])
        R.run_outputs[k] = r["detail"]
        recs = [i for i in ids if (S / "results" / M / f"{i}.json").is_file()]
        sec: set = set()   # the documents whose DISCH section is refused (each recorded on its laws, I112)
        if k == "disch":
            for i in recs:
                rec = common.load_json(S / "results" / M / f"{i}.json")
                if any(isinstance(a, dict) and a.get("kind") == "section" for a in rec.get("attempts") or []):
                    sec.add((rec.get("disch") or {}).get("facts"))
        res[k] = {"laws": len(ids), "status": r["status"], "exit": r["exit"], "records": len(recs),
                  "section_errors": len(sec), "section_error_laws": sum(
                      1 for i in recs if k == "disch" and any(isinstance(a, dict) and a.get("kind") == "section"
                                                              for a in common.load_json(S / "results" / M / f"{i}.json")
                                                              .get("attempts") or []))}
    still = [lid for lid in laws if not (S / "results" / M / f"{lid}.json").is_file()]
    stages["run"] = {"status": "ok" if all(v["status"] == "ok" for v in res.values()) else "failed", "exit": None,
                     "detail": "per runner: " + json.dumps(res, sort_keys=True) + f"; {len(still)} laws with no record"}
    stages["run"]["runners"] = res
    stages["replay"] = {"status": "not_applicable", "exit": None, "detail": proto["replay"]}
    stages["filter"] = {"status": "ok", "exit": None, "detail": proto["filter"]}


def store_large(edir: Path, limit: int) -> list:
    """I110 (--compose): route A's storage rule (go.store_max_bytes) applied to every output file of the entry. A file
    over the limit (machine documents, large sort outputs) is recorded in <id>/large_files.json by path, sha256 and
    size, and removed from the written output; everything else is kept."""
    rows = []
    for p in sorted(edir.rglob("*")):
        if p.is_file() and p.name != "large_files.json" and p.stat().st_size > limit:
            rows.append({"path": p.relative_to(edir).as_posix(), "sha256": common.sha256_file(p),
                         "bytes": p.stat().st_size})
            p.unlink()
    if rows:
        prev = json.loads((edir / "large_files.json").read_text()) if (edir / "large_files.json").is_file() else []
        allr = {r["path"]: r for r in prev + rows}
        (edir / "large_files.json").write_text(dumps([allr[k] for k in sorted(allr)]))
    return rows


def _drop_seconds(x):
    if isinstance(x, dict):
        return {k: _drop_seconds(v) for k, v in x.items() if k != "seconds"}
    if isinstance(x, list):
        return [_drop_seconds(v) for v in x]
    return x


def _scrub(edir: Path, ctx: Ctx) -> None:
    """Normalize the copied outputs (H9): scratch paths become <checkout>, <root>, <scratch> or <home>, and every JSON
    key named "seconds" is removed (G1's normalization: timings are not outcomes)."""
    for p in sorted(edir.rglob("*")):
        if not p.is_file() or p.suffix not in (".json", ".bend", ".txt", ".jsonl"):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        n = paths_out(t, ctx) if p.suffix != ".bend" else t
        if p.suffix == ".json":
            try:
                obj = json.loads(n)
            except ValueError:
                obj = None
            if obj is not None:
                d = _drop_seconds(obj)
                if d != obj:
                    n = dumps(d)
        if n != t:
            p.write_text(n, encoding="utf-8")


# ---------------------------------------------------------------------------------------------- the command
def _tree_bytes(d: Path) -> dict:
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()} \
        if d.is_dir() else {}


def preflight(proto: dict, sets: dict) -> dict | None:
    """I112 (4), Q80: under the protocol's preflight "toolchain_sets", every binary of config/toolchains.json the
    protocol can select: with solidity.compiler.version "pragma" every solc_set release (<dir>/solc-<v> present, its
    sha256 the pin); with go.toolchain "go_directive" every go_set release (its go present and printing the pinned
    version_line: go_set pins its tarballs, not the installed binaries). None without the key."""
    if proto.get("preflight") != "toolchain_sets":
        return None
    from ..frontends.go.toolchains import vkey as gkey
    from ..frontends.solidity.toolchains import vkey as skey
    bins = []
    if ((proto.get("solidity") or {}).get("compiler") or {}).get("version") == "pragma":
        ss = sets.get("solc_set") or {}
        for v in sorted(ss.get("releases") or {}, key=skey):
            p = Path(ss["dir"]) / f"solc-{v}"
            got = common.sha256_file(p) if p.is_file() else None
            bins.append({"tool": "solc", "version": v, "path": str(p), "sha256": got,
                         "ok": got == ss["releases"][v]})
    if (proto.get("go") or {}).get("toolchain") == "go_directive":
        for v, r in sorted(((sets.get("go_set") or {}).get("releases") or {}).items(), key=lambda kv: gkey(kv[0])):
            go = str(Path(r["goroot"]) / "bin" / "go") if r.get("goroot") else (
                shutil.which("go") or "/usr/local/go/bin/go")
            line = None
            if Path(go).is_file():
                try:
                    line = subprocess.run([go, "version"], capture_output=True, text=True, timeout=60).stdout.strip()
                except (OSError, subprocess.TimeoutExpired):
                    line = None
            bins.append({"tool": "go", "version": v, "path": go, "version_line": line,
                         "ok": line == r.get("version_line")})
    count = lambda t: {"checked": sum(b["tool"] == t for b in bins), "ok": sum(b["tool"] == t and b["ok"] for b in bins)}   # noqa: E731
    return {"status": "ok" if all(b["ok"] for b in bins) else "failed", "solc": count("solc"), "go": count("go"),
            "binaries": bins}


def cli_holon(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="holon eval holon")
    ap.add_argument("--root", default=str(common.ROOT))
    ap.add_argument("--entries")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--protocol", default=PROTOCOL_REL, help="the run protocol (default I51's)")
    ap.add_argument("--roles", choices=("off", "static", "static+ai"), default="off",
                    help="I104 opt-in: also run holon roles over each entry's stored documents (default off: I51's run)")
    ap.add_argument("--proposed", help="with --roles static+ai: the proposal file (holon-roles-proposed/0.1)")
    ap.add_argument("--compose", action="store_true",
                    help="I110 opt-in: the composed route A (the protocol's compose key): Go machines, the inferred roles "
                         "installed where no hand sidecar exists (--roles, default static), codecs or Go-op documents, "
                         "diagram and evidence, then sorts .. derive, run and replay")
    ap.add_argument("--vault", help="with --roles: a directory outside the repository that keeps each entry's withheld "
                                    "laws/, records/ and gen/ (Q56: the plaintext stays in the session)")
    ap.add_argument("--out", help="I112: write the run here instead of the protocol's out (absolute or root-relative)")
    a = ap.parse_args(argv)
    global VAULT
    VAULT = Path(a.vault).resolve() if a.vault else None
    if a.compose and a.roles == "off":
        a.roles = "static"
    roles = None if a.roles == "off" else {"mode": a.roles, "proposed": a.proposed}
    root = Path(a.root).resolve()
    proto = common.load_json(root / a.protocol)
    if a.compose and not proto.get("compose"):
        raise common.Refused(f"--compose: {a.protocol} has no compose key")
    if a.protocol != PROTOCOL_REL:
        proto["_path"] = a.protocol
    # I112 (4), Q80: a run refuses to start unless every toolchain-set binary its protocol can select is installed
    sets_p = Path(os.environ.get("HOLON_TOOLCHAINS") or root / "config" / "toolchains.json")
    pf = preflight(proto, common.load_json(sets_p) if sets_p.is_file() else {})
    if pf is not None and pf["status"] != "ok":
        for b in pf["binaries"]:
            if not b["ok"]:
                print(f"holon eval holon: preflight: {b['tool']} {b['version']} at {b['path']} is missing or not its "
                      f"pin ({b.get('sha256') or b.get('version_line')})", file=sys.stderr)
        print(f"holon eval holon: preflight failed ({sets_p.name}): the run does not start", file=sys.stderr)
        return 2
    cpath = root / proto["corpus"]
    entries = common.load_json(cpath)["entries"]
    want = [x for x in (a.entries or "").split(",") if x] or [e["id"] for e in entries]
    unknown = sorted(set(want) - {e["id"] for e in entries})
    if unknown:
        raise common.Refused(f"unknown entries: {unknown}")
    out = (Path(a.out) if Path(a.out).is_absolute() else root / a.out) if a.out else root / proto["out"]
    old = common.load_json(out / "corpus.json") if (out / "corpus.json").is_file() else None
    old_rows = {r["id"]: r for r in (old or {}).get("rows", [])}
    stage = Path(tempfile.mkdtemp(prefix="holon-i51-out-"))
    timing = {}
    new_rows = {}
    try:
        for e in entries:
            if e["id"] not in want:
                continue
            print(f"holon eval holon: {e['id']} ({e['repo']} {e['prefix_commit'][:12]})", flush=True)
            t = {}
            new_rows[e["id"]] = run_entry(e, proto, root, stage, t, roles, a.compose)
            timing[e["id"]] = t
            r = new_rows[e["id"]]
            print(f"  {r['status']}: {sum(d['status'] == 'extracted' for d in r['documents'])}/{len(r['documents'])} "
                  f"documents, {len(r['laws'])} laws, {sum(x['status'] == 'REFUTED' for x in r['laws'])} REFUTED, "
                  f"detected {r['detected']}", flush=True)
        if a.check:
            bad = []
            for i, r in new_rows.items():
                if old_rows.get(i) != r:
                    bad.append(f"{i}: the row differs")
                if _tree_bytes(stage / i) != _tree_bytes(out / i):
                    a_, b_ = _tree_bytes(stage / i), _tree_bytes(out / i)
                    diff = sorted(k for k in set(a_) | set(b_) if a_.get(k) != b_.get(k))
                    bad.append(f"{i}: {len(diff)} files differ, e.g. {diff[:5]}")
            for b in bad:
                print(f"holon eval holon --check: {b}")
            print("holon eval holon --check: " + ("OK" if not bad else "DIFFERS"))
            return 1 if bad else 0
        rows = [new_rows.get(e["id"]) or old_rows.get(e["id"]) for e in entries]
        if any(r is None for r in rows):
            missing = [e["id"] for e, r in zip(entries, rows) if r is None]
            print(f"holon eval holon: no row yet for {missing}; written rows only for those run", file=sys.stderr)
            rows = [r for r in rows if r is not None]
        for i in new_rows:
            shutil.rmtree(out / i, ignore_errors=True)
            if (stage / i).is_dir():
                shutil.copytree(stage / i, out / i)
        doc = {"run_version": proto["run_version"], "corpus_sha256": common.sha256_file(cpath),
               "protocol_sha256": common.sha256_file(root / a.protocol), "holon_sha256": holon_sha256(root),
               "toolchain": toolchain(root), "rows": rows, "summary": summarize(rows)}
        if pf is not None:   # I112 (4): the preflight, in the run's snapshot
            doc["preflight"] = pf
        common.write_or_check(out / "corpus.json", dumps(doc), False)
        tp = out / "corpus_timing.json"
        tim = common.load_json(tp) if tp.is_file() else {}
        tim.update(timing)
        common.write_or_check(tp, dumps(tim), False)
        print(f"holon eval holon: {len(rows)} rows -> {out / 'corpus.json'}")
        return 0
    finally:
        shutil.rmtree(stage, ignore_errors=True)
