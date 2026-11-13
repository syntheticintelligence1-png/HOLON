"""I119 (a): the read-only audit of the Go reasoner defect I117 found (HUMAN_ANSWERS Q93 (1)).

  python tools/i119_audit.py --vault DIR [--out results/M6/I119/audit.json] [--jobs N] [--parts morph,corpus,fixture]

Every committed Go document is re-extracted in scratch copies of holon/ (outside the repository), under three readings:

  old   holon/ at HEAD as it is: the path reasoner reads Go integers as unbounded unless the config says ops "typed";
  rule  old plus I117's opaque-arithmetic rule alone: paths.py builds its Reasoner with opaque=True for every config
        (no typed section, no every-function enumeration: the rest of ops "typed" is not applied);
  a2    rule plus the same flag in the site reasoner of functions with no path set (analyses.py's dominator-atom
        Reasoner): the extension A2, reported apart.

The committed documents: Morph's (spec/M2/facts, spec/M3/facts, from spec/M2/lib/go_frontend.json,
spec/M3/lib/go_frontend.json and spec/M3/lib/go_frontend_03.json) and every corpus entry's codec documents in every
committed corpus run (a protocol whose out holds a corpus.json), deduplicated by (repository, commit, config without
its doc string, protocol go rule). Machine documents (holon extract go_machines) are not re-extracted: that frontend
imports no reasoner (holon/frontends/go_machines reads holon.frontends.go.ssaload only), so the rule cannot reach them.

A document changes when its bytes under rule differ from its bytes under old; the changed functions and sections
(paths, sites, loop_bodies, other) are counted. A committed decided law is affected when its record (status PROVED or
REFUTED) names a changed document by path or stem, or (corpus) when its run row's laws_aggregate has decided > 0 and
one of the row's documents changed. The vault gets the per-document detail and the affected-law list; the repository
gets counts only and the list's sha256 (I107's canonical form over the vault's bundle directory). Nothing under the
repository is written but --out. Inputs read: holon/ (copied), the configs and facts above, the corpus runs' rows and
sidecars, spec/eval/corpus.json and the entries' pinned checkouts (holon.eval.common.repo_cache); never a sealed input.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PATCH_RULE = ("holon/frontends/go/paths.py", "Reasoner(st.cond, self.nonnil, self.ctx.typed_ops)",
              "Reasoner(st.cond, self.nonnil, True)")
PATCH_A2 = ("holon/frontends/go/analyses.py", "rs = Reasoner(facts, self.ctx.nonnil)",
            "rs = Reasoner(facts, self.ctx.nonnil, True)")
MORPH_CONFIGS = ("spec/M2/lib/go_frontend.json", "spec/M3/lib/go_frontend.json", "spec/M3/lib/go_frontend_03.json")
MORPH_FACTS = ("spec/M2/facts", "spec/M3/facts")
FIXTURE = "tests_m6/fixtures/i119"
ENV = {**os.environ, "BEND_NO_TELEMETRY": "1"}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def bundle_sha(root: Path) -> tuple[str, int]:
    """I107's canonical bundle: sorted UTF-8 paths, one '<sha256>  <path>\\n' line per file."""
    files = sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.relative_to(root).as_posix())
    lines = "".join(f"{sha(p.read_bytes())}  {p.relative_to(root).as_posix()}\n" for p in files)
    return sha(lines.encode()), len(files)


# ------------------------------------------------------------------------------------------------------ readings
def make_readings(work: Path, at: str) -> dict:
    """holon/ as committed at `at` (git archive), three times: old, rule, a2."""
    out = {}
    for name, patches in (("old", ()), ("rule", (PATCH_RULE,)), ("a2", (PATCH_RULE, PATCH_A2))):
        d = work / "readings" / name
        d.mkdir(parents=True)
        arc = subprocess.run(["git", "-C", str(ROOT), "archive", at, "holon"], capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", str(d)], input=arc, check=True)
        for rel, a, b in patches:
            p = d / rel
            t = p.read_text(encoding="utf-8")
            if t.count(a) != 1:
                raise SystemExit(f"i119_audit: {rel}: the audited code is not the code this audit patches ({a!r})")
            p.write_text(t.replace(a, b), encoding="utf-8")
        out[name] = d
    return out


def extract(reading: Path, cfg: Path, src: Path | None, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "holon", "extract", "go", "--root", str(ROOT), "--config", str(cfg), "--out-dir",
           str(out)] + (["--src", str(src)] if src else [])
    p = subprocess.run(cmd, cwd=reading, env=ENV, capture_output=True, text=True, timeout=14400)
    files = {f.name: str(f) for f in sorted(out.glob("*.extracted.json"))}   # paths: read one pair at a time
    return {"exit": p.returncode, "files": files, "log": (p.stdout + p.stderr)[-1500:]}


def sections(a: bytes, b: bytes) -> dict:
    """The functions and sections in which two documents differ (counts) and the changed function names."""
    if a == b:
        return {"changed": False}
    da, db = json.loads(a), json.loads(b)
    fa, fb = da.get("go", {}).get("functions", {}), db.get("go", {}).get("functions", {})
    sec: dict = {}
    names = []
    for k in sorted(set(fa) | set(fb)):
        x, y = fa.get(k), fb.get(k)
        if x == y:
            continue
        names.append(k)
        for s in sorted(set(x or {}) | set(y or {})):
            if (x or {}).get(s) != (y or {}).get(s):
                key = s if s in ("paths", "sites", "loop_bodies", "typed") else "other"
                sec[key] = sec.get(key, 0) + 1
    other = sorted(k for k in set(da.get("go", {})) | set(db.get("go", {}))
                   if k != "functions" and da.get("go", {}).get(k) != db.get("go", {}).get(k))
    top = sorted(k for k in set(da) | set(db) if k != "go" and da.get(k) != db.get(k))
    ends_added = 0
    for k in names:
        ea = sorted(json.dumps(p, sort_keys=True) for p in ((fa.get(k) or {}).get("paths") or []))
        eb = sorted(json.dumps(p, sort_keys=True) for p in ((fb.get(k) or {}).get("paths") or []))
        ends_added += max(0, len(eb) - len(ea))
    return {"changed": True, "functions": len(names), "sections": sec, "go_sections": other, "top": top,
            "paths_added": ends_added, "names": names}


# ------------------------------------------------------------------------------------------------------ Morph
def morph_jobs(work: Path) -> list:
    return [{"part": "morph", "id": c, "cfg": ROOT / c, "src": None} for c in MORPH_CONFIGS]


def morph_committed() -> dict:
    out = {}
    for d in MORPH_FACTS:
        for p in sorted((ROOT / d).glob("*.extracted.json")):
            b = p.read_bytes()
            try:
                fv = json.loads(b).get("extraction", {}).get("frontend_version", "")
            except ValueError:
                continue
            if str(fv).startswith("holon-go/"):
                out[p.relative_to(ROOT).as_posix()] = b
    return out


# ------------------------------------------------------------------------------------------------------ corpus
def corpus_runs() -> list:
    runs = []
    for f in sorted((ROOT / "spec").glob("M*/lib/*_run.json")):
        try:
            proto = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        out = proto.get("out")
        if not out or "go" not in proto or not ((ROOT / out / "corpus.json").is_file()
                                                or (ROOT / out).parent.joinpath("holon_aggregates.json").is_file()):
            continue
        runs.append((f.relative_to(ROOT).as_posix(), proto, ROOT / out))
    return runs


def corpus_jobs(work: Path) -> tuple[list, list]:
    """One job per distinct codec config; rows: (run, entry id, stem, committed sha256, decided, job key)."""
    corpus = {e["id"]: e for e in json.loads((ROOT / "spec" / "eval" / "corpus.json").read_text())["entries"]}
    jobs, rows, seen = [], [], {}
    for prel, proto, out in corpus_runs():
        if (out / "corpus.json").is_file():
            cj = json.loads((out / "corpus.json").read_text(encoding="utf-8"))
        else:   # I107's corpus run: rows in holon_aggregates.json, documents from the committed sidecars and facts
            cj = json.loads(out.parent.joinpath("holon_aggregates.json").read_text(encoding="utf-8"))
            for r in cj["rows"]:
                r["laws_aggregate"] = {"all": {"decided": int(r.get("decided") or 0)}}
                docs = []
                for sp in sorted((out / r["id"] / "sidecars").glob("go_*.json")):
                    if sp.stem.endswith("_machines"):
                        continue
                    fp = out / r["id"] / "facts" / f"{sp.stem}.go.extracted.json"
                    docs.append({"language": "go", "status": "extracted", "stem": sp.stem,
                                 "sha256": sha(fp.read_bytes()) if fp.is_file() else None})
                r["documents"] = docs
        for r in cj["rows"]:
            decided = sum(int(v.get("decided", 0)) for v in (r.get("laws_aggregate") or {}).values())
            for d in r.get("documents", []):
                if d.get("language") != "go" or d.get("status") != "extracted":
                    continue
                sp = out / r["id"] / "sidecars" / f"{d['stem']}.json"
                if not sp.is_file():
                    rows.append({"run": prel, "id": r["id"], "stem": d["stem"], "key": None, "decided": decided,
                                 "committed_sha256": d.get("sha256"), "why": "no committed sidecar"})
                    continue
                cfg = json.loads(sp.read_text(encoding="utf-8"))
                cfg.pop("doc", None)
                key = sha(json.dumps([r["id"], cfg, proto["go"].get("work_replace")], sort_keys=True).encode())[:16]
                rows.append({"run": prel, "id": r["id"], "stem": d["stem"], "key": key, "decided": decided,
                             "committed_sha256": d.get("sha256"), "file": d.get("file")})
                if key not in seen:
                    seen[key] = True
                    jobs.append({"part": "corpus", "id": key, "entry": corpus[r["id"]], "proto": proto,
                                 "sidecar": sp, "stem": d["stem"]})
    return jobs, rows


def corpus_source(job: dict, tmp: Path) -> tuple[Path | None, str]:
    from holon.eval import holon_run as H
    ck = tmp / "ck"
    H.checkout(job["entry"], ck)
    for d in H.go_inputs(job["entry"], job["proto"], ck):
        if d.get("stem") == job["stem"]:
            src, how = H.go_source(ck, d["module_dir"], tmp, job["proto"]["go"].get("work_replace"))
            return src, how
    return None, "the stem is not among the entry's Go inputs"


# ------------------------------------------------------------------------------------------------------ run
def run_job(job: dict, readings: dict, work: Path) -> dict:
    t = work / "jobs" / job["part"] / job["id"].replace("/", "_")
    if t.exists():
        shutil.rmtree(t)
    t.mkdir(parents=True)
    res = {"part": job["part"], "id": job["id"]}
    try:
        if job["part"] == "corpus":
            src, how = corpus_source(job, t)
            res["source"] = how
            if src is None:
                res["refused"] = how
                return res
            cfgp = t / "cfg.json"
            shutil.copy(job["sidecar"], cfgp)
        elif job["part"] == "fixture":
            cfg = json.loads((ROOT / FIXTURE / "go_config.json").read_text())
            cfgp = t / "cfg.json"
            cfgp.write_text(json.dumps(cfg))
            src = ROOT / FIXTURE / "src"
        else:
            cfgp, src = job["cfg"], None
        for name, rd in readings.items():
            r = extract(rd, cfgp, src, t / name)
            res[name] = {"exit": r["exit"], "files": r["files"], "log": r["log"]}
            if r["exit"] != 0:
                res["refused"] = f"{name}: exit {r['exit']}"
    except Exception as e:   # recorded, never hidden
        res["refused"] = f"{type(e).__name__}: {str(e)[-800:]}"
    finally:
        ck = t / "ck"
        if job["part"] == "corpus" and ck.exists():
            from holon.eval import common, holon_run as H
            H.drop_worktree(common.repo_cache(job["entry"]["repo"]), ck)
    return res


def fixture_summary(res: dict) -> dict:
    out = {}
    for name in ("old", "rule"):
        (b,) = [Path(v).read_bytes() for v in res[name]["files"].values()]
        fs = json.loads(b)["go"]["functions"]
        pk = "example.com/holon/i119/wrap64."
        out[name] = {
            "Inc64": {"ends": sorted(p["end"] for p in fs[pk + "Inc64"]["paths"])},
            "Idx": {"ends": sorted(p["end"] for p in fs[pk + "Idx"]["paths"]),
                    "index_status": [s["status"] for s in fs[pk + "Idx"]["sites"] if s["kind"] == "index"][0]},
            "Plus": {"ends": sorted(p["end"] for p in fs[pk + "Plus"]["paths"])}}
    return out


def decided_morph_records() -> list:
    """Every committed M0-M3 record with status PROVED or REFUTED: (milestone, path, text)."""
    out = []
    for m in ("M0", "M1", "M2", "M3"):
        base = ROOT / "results" / m
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.json")):
            try:
                t = p.read_text(encoding="utf-8")
                d = json.loads(t)
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(d, dict) and d.get("status") in ("PROVED", "REFUTED") and isinstance(d.get("law_id", d.get("id")), str):
                out.append((m, p.relative_to(ROOT).as_posix(), t, d.get("law_id", d.get("id"))))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tools/i119_audit.py")
    ap.add_argument("--vault", required=True)
    ap.add_argument("--out", default="results/M6/I119/audit.json")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--parts", default="fixture,morph,corpus")
    ap.add_argument("--at", default="HEAD", help="the audited commit: holon/ is read from it (git archive)")
    a = ap.parse_args(argv)
    vault = Path(a.vault).resolve()
    if ROOT in vault.parents or vault == ROOT:
        raise SystemExit("i119_audit: the vault must be outside the repository")
    vault.mkdir(parents=True, exist_ok=True)
    parts = a.parts.split(",")
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", a.at], capture_output=True, text=True,
                          check=True).stdout.strip()
    work = Path(tempfile.mkdtemp(prefix="holon-i119-audit-", dir=os.environ.get("I119_SCRATCH")))
    readings = make_readings(work, head)
    jobs = []
    if "fixture" in parts:
        jobs.append({"part": "fixture", "id": "wrap64"})
    if "morph" in parts:
        jobs += morph_jobs(work)
    rows = []
    if "corpus" in parts:
        cj, rows = corpus_jobs(work)
        jobs += cj
    results = {}
    with cf.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = {ex.submit(run_job, j, readings, work): j for j in jobs}
        for f in cf.as_completed(futs):
            j = futs[f]
            results[(j["part"], j["id"])] = f.result()
            print(f"i119_audit: {j['part']} {j['id']} done{' (refused)' if 'refused' in results[(j['part'], j['id'])] else ''}",
                  flush=True)

    detail = {"head": head, "jobs": {}}
    changed_docs: dict = {"morph": [], "corpus": [], "morph_a2": [], "corpus_a2": []}
    summary: dict = {"audit_version": "holon-i119-audit/0.1", "audited_commit": head,
                     "rule": "paths.py Reasoner opaque=True for every config (I117's opaque-arithmetic rule alone)"}
    for (part, jid), r in sorted(results.items()):
        dj = {"refused": r.get("refused"), "source": r.get("source"), "docs": {}}
        if "refused" not in r:
            for fn in sorted(r["old"]["files"]):
                rd = lambda n: Path(r[n]["files"][fn]).read_bytes() if fn in r[n]["files"] else b""
                ob, rb, ab = rd("old"), rd("rule"), rd("a2")
                s1, s2 = sections(ob, rb), sections(rb, ab) if rb else {"changed": True}
                dj["docs"][fn] = {"old_sha256": sha(ob), "rule_sha256": sha(rb), "a2_sha256": sha(ab),
                                  "rule_vs_old": s1, "a2_vs_rule": s2}
        dj["logs"] = {n: r[n]["log"] for n in ("old", "rule", "a2") if n in r and r[n]["exit"] != 0}
        detail["jobs"][f"{part}:{jid}"] = dj

    if "fixture" in parts:
        summary["fixture"] = fixture_summary(results[("fixture", "wrap64")])

    if "morph" in parts:
        committed = morph_committed()
        produced = {}
        for c in MORPH_CONFIGS:
            for fn, d in detail["jobs"][f"morph:{c}"]["docs"].items():
                produced.setdefault(fn, []).append((c, d))
        files = []
        for path, b in sorted(committed.items()):
            name = Path(path).name
            cands = produced.get(name, []) + produced.get(name.replace(".extracted.json", ".go.extracted.json"), [])
            match = [(c, d) for c, d in cands if d["old_sha256"] == sha(b)]
            c, d = (match or cands or [(None, None)])[0]
            rec = {"path": path, "committed_sha256": sha(b), "config": c,
                   "baseline_sha256": d["old_sha256"] if d else None,
                   "rule_changed": bool(d and d["rule_vs_old"]["changed"]),
                   "a2_changed": bool(d and (d["rule_vs_old"]["changed"] or d["a2_vs_rule"]["changed"]))}
            files.append(rec)
            if rec["rule_changed"]:
                changed_docs["morph"].append(path)
            if rec["a2_changed"]:
                changed_docs["morph_a2"].append(path)
        summary["morph"] = {"documents": len(files),
                            "baseline_identical": sum(1 for f in files if f["baseline_sha256"] == f["committed_sha256"]),
                            "changed": len(changed_docs["morph"]), "changed_a2": len(changed_docs["morph_a2"]),
                            "files": [{k: f[k] for k in ("path", "committed_sha256", "baseline_sha256", "config")}
                                      for f in files]}
        sec: dict = {}
        for c in MORPH_CONFIGS:
            for d in detail["jobs"][f"morph:{c}"]["docs"].values():
                for k, v in d["rule_vs_old"].get("sections", {}).items():
                    sec[k] = sec.get(k, 0) + v
        summary["morph"]["changed_function_sections"] = sec

    affected = {"M0": [], "M1": [], "M2": [], "M3": [], "corpus": []}
    affected_a2 = {"M0": [], "M1": [], "M2": [], "M3": [], "corpus": []}
    if "morph" in parts:
        recs = decided_morph_records()
        for docs, acc in ((changed_docs["morph"], affected), (changed_docs["morph_a2"], affected_a2)):
            needles = set()
            for p in docs:
                n = Path(p).name
                needles |= {p, n, n.split(".")[0]}
            for m, rp, t, lid in recs:
                if any(x in t for x in needles):
                    acc[m].append(lid)

    if "corpus" in parts:
        n_ok = sum(1 for j in results if j[0] == "corpus" and "refused" not in results[j])
        n_ref = sum(1 for j in results if j[0] == "corpus" and "refused" in results[j])
        ch_keys, ch_a2, base_ok, base_n = set(), set(), 0, 0
        for (part, jid), r in results.items():
            if part != "corpus" or "refused" in r:
                continue
            for fn, d in detail["jobs"][f"corpus:{jid}"]["docs"].items():
                if d["rule_vs_old"]["changed"]:
                    ch_keys.add(jid)
                if d["rule_vs_old"]["changed"] or d["a2_vs_rule"]["changed"]:
                    ch_a2.add(jid)
        for row in rows:
            dj = detail["jobs"].get(f"corpus:{row['key']}")
            if not dj or dj["refused"]:
                continue
            docs = list(dj["docs"].values())
            if docs and row.get("committed_sha256"):
                base_n += 1
                base_ok += int(any(d["old_sha256"] == row["committed_sha256"] for d in docs))
            if row["key"] in ch_keys and row["decided"]:
                affected["corpus"].append(f"{row['run']}:{row['id']}:{row['decided']}")
            if row["key"] in ch_a2 and row["decided"]:
                affected_a2["corpus"].append(f"{row['run']}:{row['id']}:{row['decided']}")
        summary["corpus"] = {"runs": len(corpus_runs()), "rows_with_go": len(rows), "configs": n_ok + n_ref,
                             "extracted": n_ok, "refused": n_ref, "changed_configs": len(ch_keys),
                             "changed_configs_a2": len(ch_a2), "baseline_identical_rows": base_ok,
                             "baseline_compared_rows": base_n,
                             "machine_documents": "not re-extracted: holon.frontends.go_machines imports no reasoner"}
        sec: dict = {}
        for (part, jid), r in results.items():
            if part == "corpus" and "refused" not in r:
                for d in detail["jobs"][f"corpus:{jid}"]["docs"].values():
                    for k, v in d["rule_vs_old"].get("sections", {}).items():
                        sec[k] = sec.get(k, 0) + v
        summary["corpus"]["changed_function_sections"] = sec

    def corpus_count(lst):
        return sum(int(x.rsplit(":", 1)[1]) for x in lst)

    # the vault: the detail and the affected-law lists; the repository: counts and the bundle's sha256
    bd = vault / "bundle"
    if bd.exists():
        shutil.rmtree(bd)
    bd.mkdir()
    (bd / "affected.json").write_text(dumps({"rule": {k: sorted(v) for k, v in affected.items()},
                                             "a2": {k: sorted(v) for k, v in affected_a2.items()}}))
    (bd / "changed_documents.json").write_text(dumps(changed_docs))
    (vault / "detail.json").write_text(dumps(detail))
    (vault / "rows.json").write_text(dumps(rows))
    bs, bn = bundle_sha(bd)
    summary["affected_decided_laws"] = {k: (corpus_count(v) if k == "corpus" else len(v)) for k, v in affected.items()}
    summary["affected_decided_laws_a2"] = {k: (corpus_count(v) if k == "corpus" else len(v))
                                           for k, v in affected_a2.items()}
    summary["affected_bundle_sha256"] = bs
    summary["affected_bundle_files"] = bn
    out = Path(a.out) if Path(a.out).is_absolute() else ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumps(summary))
    print(f"i119_audit: wrote {a.out}; affected (rule) {summary['affected_decided_laws']}; bundle {bs}")
    print(f"i119_audit: scratch kept at {work} (no started run's output is deleted)")
    return 0




# ------------------------------------------------------------------------------------------------------ recount
def recount(vault: Path, out: Path) -> dict:
    """The affected count by holon land's own notion of a law's inputs (holon.land.dirty_laws): a decision trace
    (traces/<M>/<law>.json) whose reads include a changed document, or a statement whose derivation input names one.
    The counted run's text match over records (main) both over- and under-counts (a model file named like a document
    stem; documents read through the trace, not named in the record), so this replaces it as the measure; the counted
    run's audit.json stays as it was written. Decided laws with no trace are counted apart: their reads are not
    recorded, so whether they read a changed document is not determined by committed data."""
    ch = json.loads((vault / "bundle" / "changed_documents.json").read_text())
    summary = {"recount_version": "holon-i119-recount/0.1", "basis": "decision traces' reads and laws/<M> statements"}
    lists: dict = {}
    for reading, docs in (("rule", set(ch["morph"])), ("a2", set(ch["morph_a2"]))):
        per, untraced = {}, {}
        for m in ("M0", "M1", "M2", "M3"):
            hit, unt = [], 0
            stmt = set()
            ld = ROOT / "laws" / m
            if ld.is_dir():
                for p in sorted(ld.glob("L_*.json")):
                    t = p.read_text(encoding="utf-8")
                    if any(d in t for d in docs):
                        stmt.add(p.stem)
            for p in sorted((ROOT / "results" / m).glob("L*.json")) if (ROOT / "results" / m).is_dir() else []:
                try:
                    r = json.loads(p.read_text(encoding="utf-8"))
                except ValueError:
                    continue
                if r.get("status") not in ("PROVED", "REFUTED"):
                    continue
                lid = r.get("law_id") or p.stem
                tp = ROOT / "traces" / m / f"{lid}.json"
                reads = set(json.loads(tp.read_text()).get("reads") or {}) if tp.is_file() else None
                if (reads is not None and reads & docs) or lid in stmt:
                    hit.append(lid)
                elif reads is None:
                    unt += 1
            per[m], untraced[m] = len(hit), unt
            lists[f"{reading}:{m}"] = sorted(hit)
        summary[f"affected_decided_laws_{reading}"] = per
        summary[f"decided_without_trace_{reading}"] = untraced
    bd = vault / "bundle_recount"
    if bd.exists():
        shutil.rmtree(bd)
    bd.mkdir()
    (bd / "affected.json").write_text(dumps(lists))
    summary["affected_bundle_sha256"], summary["affected_bundle_files"] = bundle_sha(bd)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumps(summary))
    return summary


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "recount":   # tools/i119_audit.py recount --vault DIR [--out PATH]
        ap = argparse.ArgumentParser(prog="tools/i119_audit.py recount")
        ap.add_argument("--vault", required=True)
        ap.add_argument("--out", default="results/M6/I119/audit_recount.json")
        x = ap.parse_args(sys.argv[2:])
        s = recount(Path(x.vault).resolve(), ROOT / x.out)
        print(f"i119_audit recount: {s['affected_decided_laws_rule']}; without trace {s['decided_without_trace_rule']}")
        sys.exit(0)
    sys.exit(main())
