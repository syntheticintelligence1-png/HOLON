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
from .gitfacts import DIFF_OPTIONS

PROTOCOL_REL = "spec/M4/lib/i51_run.json"
RULES = ("PAR", "SORT", "DISCH", "UNDO", "NAT", "FACT", "SYM", "OWN")
CLASSES = ("true_defect", "intended_asymmetry", "model_defect", "unreplayed")
COPY_DIRS = ("holon", "config", "spec", "bend", "schemas")
_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", "heldout")


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
def contracts_of(text: str, pattern: str) -> list[str]:
    rx = re.compile(pattern)
    return [m.group(1) for line in text.splitlines() for m in [rx.match(line)] if m]


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
                    "doc": f"I51: generated from corpus entry {entry['id']} by holon eval holon (spec/M4/lib/i51_run.json "
                           "solidity): the contract a file of the entry declares",
                    "target": {"repo": f"{owner}/{name}", "commit": entry["prefix_commit"],
                               "scope": f"contract {c} of {f}"},
                    "output": f"{base_rel}/facts/{fname}", "sources": [f],
                    "compiler": json.loads(json.dumps(sol["compiler"])),
                    "transitions": {"contract": c, "commit_interfaces": list(sol["commit_interfaces"])}}
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


def go_source(ck: Path, module_dir: Path, scratch: Path) -> tuple[Path, str]:
    """The source the frontend copies (protocol go.source): the module directory, or a scratch copy of the checkout
    with a generated go.work when a relative replace leaves the module."""
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
def run_entry(entry: dict, proto: dict, root: Path, stage_dir: Path, timing: dict, roles: dict | None = None) -> dict:
    """Run one entry; write its <id>/ directory into stage_dir; return its row."""
    rel = f"{proto['out']}/{entry['id']}"
    edir = stage_dir / entry["id"]
    edir.mkdir(parents=True)
    tmp = Path(tempfile.mkdtemp(prefix="holon-i51-"))
    ck = tmp / "checkout"
    ctx = Ctx(tmp, ck)
    row = {k: entry[k] for k in ("id", "system", "repo", "prefix_commit", "fix_commit", "label", "files")}
    stages: dict = {}
    docs: list = []
    clone = None
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
            src, how = go_source(ck, d.pop("module_dir"), tmp)
            cfg = {"config_version": proto["go"]["config_version"],
                   "doc": f"I51: generated from corpus entry {entry['id']} by holon eval holon (spec/M4/lib/i51_run.json go)",
                   "target": {"repo": f"{owner}/{name}", "commit": entry["prefix_commit"]},
                   "source": {"path": "<given by --src>"}, "documents": {d["stem"]: [d["unit"]]},
                   "primitives": dict(proto["go"]["primitives"]), "limits": dict(proto["go"]["limits"])}
            cp = S / rel / "sidecars" / f"{d['stem']}.json"
            cp.write_text(dumps(cfg))
            res = R.holon("extract", ["extract", "go", "--root", str(S), "--config", str(cp), "--src", str(src),
                                      "--out-dir", str(S / rel / "facts")])
            d.update({"status": "extracted" if res["status"] == "ok" else "failed", "exit": res["exit"],
                      "reason": None if res["status"] == "ok" else res["detail"], "source": how})
            docs.append(d)
        for d in docs:
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
        if roles and ext:   # I104 opt-in (--roles): the role sidecars holon roles infers from the stored documents
            rels = [f"{rel}/facts/{d['file']}" for d in ext if (S / rel / "facts" / d["file"]).is_file()]
            args = ["roles", "--milestone", M, "--root", str(S), "--documents", ",".join(rels), "--out-dir",
                    str(S / rel / "sidecars" / "roles"), "--mode", roles["mode"]]
            if roles.get("proposed"):
                args += ["--proposed", roles["proposed"]]
            stages["roles"] = R.holon("roles", args)
            mp = S / rel / "sidecars" / "roles" / "roles.json"
            if mp.is_file():
                man = json.loads(mp.read_text())
                kinds: dict = {}
                for x in man["roles"]:
                    kinds[f"{x['sidecar']}:{x['roles_source']}"] = kinds.get(f"{x['sidecar']}:{x['roles_source']}", 0) + 1
                row["roles"] = {"mode": roles["mode"], "count": len(man["roles"]), "kinds": dict(sorted(kinds.items())),
                                "proposed": man.get("proposed")}
        if ext and not sol:
            stages["derive"] = {"status": "no_producer", "exit": None, "detail": proto["go_rules_doc"]}
        if sol:
            _rules(R, S, rel, M, proto, sol, stages)
        # copy the outputs
        for sub, frm in (("sidecars", S / rel / "sidecars"), ("facts", S / rel / "facts"), ("laws", S / "laws" / M),
                         ("gen", S / "gen" / M), ("records", S / "results" / M)):
            if frm.is_dir() and any(frm.iterdir()):
                shutil.copytree(frm, edir / sub, ignore=_IGNORE)
        _scrub(edir, ctx)
    finally:
        if clone is not None:
            drop_worktree(clone, ck)
        shutil.rmtree(tmp, ignore_errors=True)
    row["documents"] = [{k: d.get(k) for k in ("stem", "file", "language", "source_file", "unit", "status", "exit",
                                               "reason", "sha256", "bytes", "stored", "source")} for d in docs]
    row["stages"] = stages
    row["laws"] = law_rows(edir, entry["files"], row["locus"])
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


def withhold(row: dict, edir: Path) -> None:
    """I104 under HUMAN_ANSWERS Q56 (the --roles opt-in): no per-law verdict, law id or class of a law derived through
    generated roles is written until a person adjudicates it. The row keeps per-family aggregates that never split
    PROVED from REFUTED, and one commitment: the sha256 of the sorted lines "<path> <sha256>" (each ending in a newline)
    of every file under the entry's laws/ and records/, which are then removed from the written output."""
    fam: dict = {}
    for x in row["laws"]:
        k = f"{x.get('rule')}/{x.get('subform')}"
        f = fam.setdefault(k, {"derived": 0, "decided": 0, "unknown": 0})
        f["derived"] += 1
        f["decided" if x.get("status") in ("PROVED", "REFUTED") else "unknown"] += 1
    lines = []
    for sub in ("laws", "records"):
        d = edir / sub
        if d.is_dir():
            lines += [f"{sub}/{q.relative_to(d).as_posix()} {sha256_bytes(q.read_bytes())}"
                      for q in sorted(d.rglob("*")) if q.is_file()]
            shutil.rmtree(d)
    row["laws_aggregate"] = dict(sorted(fam.items()))
    row["laws_bundle_sha256"] = sha256_bytes(("".join(f"{x}\n" for x in sorted(lines))).encode())
    row["laws_bundle_files"] = len(lines)
    row["laws"] = []
    for k in ("detected", "detected_any", "label_rule_laws"):
        row[k] = None   # withheld with the verdicts (Q56); the adjudicator's run decides them


def _rules(R: Runner, S: Path, rel: str, M: str, proto: dict, sol: list, stages: dict) -> None:
    """H3-H4 over the transitions documents."""
    sd = S / rel / "sidecars"
    docs = [f"{rel}/facts/{d['file']}" for d in sol]
    typed = {"sort_types_version": proto["typed"]["sort_types_version"],
             "doc": "I51: generated by holon eval holon (spec/M4/lib/i51_run.json typed)", "documents": docs,
             "seeds": proto["typed"]["seeds"], "binding": proto["typed"]["binding"], "search": proto["typed"]["search"]}
    disch = {**{k: proto["disch"][k] for k in ("disch_version", "binding", "hypotheses", "hypothesis_verdicts", "r0",
                                                "search")},
             "doc": "I51: generated by holon eval holon (spec/M4/lib/i51_run.json disch)", "documents": docs,
             "model_sidecar": f"{rel}/sidecars/sort_types.json"}
    undo = {**{k: proto["undo"][k] for k in ("undo_version", "observation", "premise", "search")},
            "doc": "I51: generated by holon eval holon (spec/M4/lib/i51_run.json undo)",
            "sort_types": f"{rel}/sidecars/sort_types.json"}
    fact = {**{k: proto["fact"][k] for k in ("fact_version", "binding", "hypotheses", "verdicts", "search", "measure",
                                              "term_size")},
            "doc": "I51: generated by holon eval holon (spec/M4/lib/i51_run.json fact)", "documents": docs,
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
        stages[name] = R.holon(name, args)
        if stages[name]["status"] != "ok":
            return
    laws = sorted(p.stem for p in (S / "laws" / M).glob("L*.json"))
    if not laws:
        stages["run"] = {"status": "not_applicable", "exit": None, "detail": "no law derived"}
        return
    out = ["--out", f"results/{M}", "--gen-dir", f"gen/{M}"]
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


def cli_holon(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="holon eval holon")
    ap.add_argument("--root", default=str(common.ROOT))
    ap.add_argument("--entries")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--roles", choices=("off", "static", "static+ai"), default="off",
                    help="I104 opt-in: also run holon roles over each entry's stored documents (default off: I51's run)")
    ap.add_argument("--proposed", help="with --roles static+ai: the proposal file (holon-roles-proposed/0.1)")
    a = ap.parse_args(argv)
    roles = None if a.roles == "off" else {"mode": a.roles, "proposed": a.proposed}
    root = Path(a.root).resolve()
    proto = common.load_json(root / PROTOCOL_REL)
    cpath = root / proto["corpus"]
    entries = common.load_json(cpath)["entries"]
    want = [x for x in (a.entries or "").split(",") if x] or [e["id"] for e in entries]
    unknown = sorted(set(want) - {e["id"] for e in entries})
    if unknown:
        raise common.Refused(f"unknown entries: {unknown}")
    out = root / proto["out"]
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
            new_rows[e["id"]] = run_entry(e, proto, root, stage, t, roles)
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
               "protocol_sha256": common.sha256_file(root / PROTOCOL_REL), "holon_sha256": holon_sha256(root),
               "toolchain": toolchain(root), "rows": rows, "summary": summarize(rows)}
        common.write_or_check(out / "corpus.json", dumps(doc), False)
        tp = out / "corpus_timing.json"
        tim = common.load_json(tp) if tp.is_file() else {}
        tim.update(timing)
        common.write_or_check(tp, dumps(tim), False)
        print(f"holon eval holon: {len(rows)} rows -> {out / 'corpus.json'}")
        return 0
    finally:
        shutil.rmtree(stage, ignore_errors=True)
