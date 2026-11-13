"""I123 P10 (from I120's tools/i120_sealed.py, re-keyed): the composed driver on I106's targets as I107 pinned them, a measurement labelled contaminated: post-I107, under HUMAN_ANSWERS Q104's two protocols on the same code.

  python tools/i123_sealed.py run --which counted|base --vault DIR      # writes gen/i123_sealed_<which>/ (never
                                                                         # committed), runs, keeps outputs in DIR
  python tools/i123_sealed.py publish --which counted|base --vault DIR  # results/M6/I123/sealed.json (counted) or
                                                                         # results/M6/I123/sealed_base.json (base)

The entries are I107's (results/eval/generality/sealed/entries.json on the I107 landing branch, the pins of
spec/heldout2/target.json); the protocol is spec/M6/lib/i123_run.json (counted: base_run.json plus typed.sort_ops) or
spec/M6/lib/base_run.json (the baseline, reported beside), each with only corpus and out changed. Q56: the committed file holds, per target, documents attempted and extracted, the sort budget summary
(documents sorted, under the tier, over it), laws derived, decided (the two decided statuses together, Q89) and UNKNOWN, and one
bundle commitment (I107's canonical form) over everything the run wrote for the target; no per-law verdict, id,
record, class or count of findings. Q72: stage statuses with their reasons only for the stages before any law is
decided (checkout .. derive); run, replay and filter are recorded by status only, and the run and bind steps'
documents fallen back by count only (Q100 (1)(a): no reason of theirs is committed). Outside holon/: it only invokes
`holon eval holon` and reads its output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOLS = {"counted": "spec/M6/lib/i123_run.json", "base": "spec/M6/lib/base_run.json"}
OUTS = {"counted": "sealed.json", "base": "sealed_base.json"}
ENTRIES_REF = "origin/claude/ci-i107-landing:results/eval/generality/sealed/entries.json"
PRE_DECISION = ("checkout", "extract", "machines", "roles", "sorts", "types", "model", "disch", "codecs", "goops",
                "diagram", "evidence", "derive")
LABEL = "contaminated: post-I107"


def dumps(x) -> str:
    return json.dumps(x, indent=2, sort_keys=True) + "\n"


def bundle_sha(root: Path) -> tuple[str, int]:
    """I107's canonical bundle: sorted UTF-8 paths, one '<sha256>  <path>\\n' line per file; timing files left out."""
    files = sorted((p for p in Path(root).rglob("*") if p.is_file() and "timing" not in p.name),
                   key=lambda p: p.relative_to(root).as_posix().encode())
    lines = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root).as_posix()}\n" for p in files)
    return hashlib.sha256(lines.encode()).hexdigest(), len(files)


def run(vault: Path, which: str) -> int:
    WORK = ROOT / "gen" / f"i123_sealed_{which}"
    rel = WORK.relative_to(ROOT).as_posix()
    WORK.mkdir(parents=True, exist_ok=True)
    ent = subprocess.run(["git", "-C", str(ROOT), "show", ENTRIES_REF], check=True, capture_output=True).stdout
    (WORK / "entries.json").write_bytes(ent)
    from holon.eval import common
    proto = json.loads(json.dumps(common.load_json(ROOT / PROTOCOLS[which])))
    proto.update({"corpus": f"{rel}/entries.json", "out": f"{rel}/out"})
    (WORK / "protocol.json").write_text(dumps(proto))
    env = {**os.environ, "BEND_NO_TELEMETRY": "1"}
    p = subprocess.run([sys.executable, "-m", "holon", "eval", "holon", "--protocol", f"{rel}/protocol.json",
                        "--compose", "--vault", str(vault / "laws")], cwd=ROOT, env=env)
    out = WORK / "out"
    if out.is_dir():
        shutil.copytree(out, vault / "out", dirs_exist_ok=True)
        shutil.rmtree(out)
    return p.returncode


def publish(vault: Path, which: str) -> int:
    raw = json.loads((vault / "out" / "corpus.json").read_text())
    tp = vault / "out" / "corpus_timing.json"
    timing = json.loads(tp.read_text()) if tp.is_file() else {}
    targets = []
    for r in raw["rows"]:
        docs = r.get("documents") or []
        st = r.get("stages") or {}
        sb = r.get("sort_budget") or {}
        agg = r.get("laws_aggregate") or {}
        b_root = vault / "bundle" / r["id"]
        if b_root.exists():
            shutil.rmtree(b_root)
        for src in (vault / "laws" / r["id"], vault / "out" / r["id"]):
            if src.is_dir():
                shutil.copytree(src, b_root / src.parent.name, dirs_exist_ok=True)
        sha, n = bundle_sha(b_root) if b_root.is_dir() else (hashlib.sha256(b"").hexdigest(), 0)
        targets.append({
            "id": r["id"], "system": r.get("system"), "repo": r.get("repo"), "commit": r.get("prefix_commit"),
            "documents_attempted": len(docs), "documents_extracted": sum(d.get("status") == "extracted" for d in docs),
            "machine_documents": sum(len(m.get("files") or []) for m in r.get("machines") or []),
            "stages": {k: v.get("status") for k, v in sorted(st.items())},
            "stage_reasons": {k: v.get("detail") for k, v in sorted(st.items())
                              if k in PRE_DECISION and v.get("status") != "ok"},
            "documents_sorted": sb.get("documents", 0),
            "documents_under_tier": sb.get("documents", 0) - len(sb.get("over_budget") or []),
            "documents_over_tier": len(sb.get("over_budget") or []),
            "sort_work_max_under_tier": max([w for w in (sb.get("work") or {}).values() if w <= sb.get("sort_budget", 0)],
                                            default=None),
            "seconds": timing.get(r["id"], {}),   # a measurement (machine-dependent), not an outcome
            "roles_sources": r.get("roles_sources"),
            # I111 P10: documents typed versus opaque at holon types (counts only)
            "types_documents": (r.get("types_opaque") or {}).get("documents", 0),
            "types_typed": (r.get("types_opaque") or {}).get("typed", 0),
            "types_opaque": (r.get("types_opaque") or {}).get("opaque", 0),
            # I112: documents opaque per refusal class (types, before any decision: counts only)
            "types_opaque_classes": {c: sum(1 for m in (r.get("types_opaque") or {}).get("misses") or []
                                            if m.get("class") == c)
                                     for c in sorted({m.get("class") for m in (r.get("types_opaque") or {})
                                                     .get("misses") or []})},
            # I112: the run step's runners, aggregates only (laws, records, section errors; never a verdict split)
            "run_runners": {k: {x: v.get(x) for x in ("laws", "records", "section_errors", "status")}
                            for k, v in sorted((r.get("run_runners") or {}).items())},
            # I116 (kept): documents fallen back per stage (DISCH and evidence run before any decision: counts and classes)
            "fallbacks": r.get("fallbacks"),
            # I118 (R), (B): documents the typed runner and bind fell back on, counts only (Q72, Q100 (1)(a))
            "runner_fallback_documents": ((r.get("fallbacks") or {}).get("run") or {}).get("documents", 0),
            "bind_fallback_documents": ((r.get("fallbacks") or {}).get("bind") or {}).get("documents", 0),
            "laws_aggregate": {k: dict(v) for k, v in sorted(agg.items())},
            "laws_derived": sum(f["derived"] for f in agg.values()),
            "laws_decided": sum(f["decided"] for f in agg.values()),
            "laws_unknown": sum(f["unknown"] for f in agg.values()),
            "decided": sum(f["decided"] for f in agg.values()),
            "bundle_sha256": sha, "bundle_files": n})
    doc = {"label": LABEL, "doc": __doc__.split("\n\n")[0].strip(), "which": which, "protocol": PROTOCOLS[which],
           "protocol_sha256": raw.get("protocol_sha256"), "holon_sha256": raw.get("holon_sha256"),
           "entries": ENTRIES_REF, "targets": {t["id"] + ":" + str(t["system"]): t for t in targets}}
    p = ROOT / "results" / "M6" / "I123" / OUTS[which]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dumps(doc))
    print(dumps({t["id"]: {k: t[k] for k in ("documents_extracted", "documents_sorted", "documents_over_tier",
                                             "laws_derived", "laws_decided", "bundle_sha256")} for t in targets}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run", "publish"))
    ap.add_argument("--which", choices=tuple(PROTOCOLS), required=True)
    ap.add_argument("--vault", required=True, help="a directory outside the repository")
    a = ap.parse_args(argv)
    vault = Path(a.vault).resolve()
    if ROOT in vault.parents or vault == ROOT:
        raise SystemExit("the vault must be outside the repository")
    vault.mkdir(parents=True, exist_ok=True)
    vault = vault / a.which
    vault.mkdir(parents=True, exist_ok=True)
    return run(vault, a.which) if a.cmd == "run" else publish(vault, a.which)


if __name__ == "__main__":
    raise SystemExit(main())
