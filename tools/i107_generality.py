"""I107's driver (spec/M6/lib/i107_protocol.json), outside every generator closure; it touches nothing under holon/.

  python tools/i107_generality.py roles-derive --src DIR --entries ID,.. --scratch S --out FILE
      route C: I104's smoke route (tools/i104_roles_experiment.py smoke, its stage list unchanged) over the documents
      route A stored under DIR/<id>/facts/; laws counted, not run.
  python tools/i107_generality.py assemble [--check]
      results/eval/generality/summary.json from the run outputs (the shape is tests_m6/test_i107_generality.py's).

Routes A and B are the merged tree's own commands, run as the protocol states (holon eval holon, holon eval
go-machines); this file only invokes route C and assembles.
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "eval" / "generality"
DECIDED = ("PROVED", "REFUTED")
TOOLCHAIN_RX = re.compile(r"pinned toolchain|pinned compiler|no pinned release|requires go >=|go\.mod requires go")
STAGES = ("checkout", "extract", "roles", "sorts", "types", "model", "disch", "derive", "run", "replay")


def dumps(x) -> str:
    return json.dumps(x, indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def load(p: Path):
    p = Path(p)
    return json.loads(p.read_text()) if p.is_file() else None


# ------------------------------------------------------------------------------------------- route C
def roles_derive(src: Path, ids: list[str], scratch: Path, out: Path) -> None:
    sys.path.insert(0, str(ROOT / "tools"))
    import i104_roles_experiment as X
    fake = scratch / "root"
    if fake.exists():
        shutil.rmtree(fake)
    (fake / "results" / "eval").mkdir(parents=True)
    from holon.eval.holon_run import COPY_DIRS
    for d in COPY_DIRS:
        (fake / d).parent.mkdir(parents=True, exist_ok=True)
        if not (fake / d).exists():
            os.symlink(ROOT / d, fake / d)
    os.symlink(src.resolve(), fake / "results" / "eval" / "holon")
    X.ROOT = fake
    X.OUT = scratch / "out"
    X.th = lambda: {"corpus_entries": ids}
    X.smoke(scratch / "work")
    doc = json.loads((X.OUT / "corpus_smoke.json").read_text())
    doc["doc"] = ("I107 route C (spec/M6/lib/i107_protocol.json routes.C): I104's smoke route, its stage list unchanged, "
                  f"over the documents route A stored under {src.relative_to(ROOT)}/<id>/facts/. " + doc["doc"])
    for e in doc["entries"]:
        e["documents"] = sorted(e["documents"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumps(doc))


# ------------------------------------------------------------------------------------------- Q56: publish
PER_LAW = ("laws", "gen", "records")


def bundle_sha(root: Path) -> str:
    """The canonical bundle (spec/M6/lib/i107_protocol.json disclosure.bundle): sorted UTF-8 paths, one
    '<sha256>  <path>\\n' line per file, sha256 of the concatenation. Timing files are left out."""
    files = sorted((p for p in Path(root).rglob("*") if p.is_file() and "timing" not in p.name),
                   key=lambda p: p.relative_to(root).as_posix().encode())
    lines = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root).as_posix()}\n" for p in files)
    return hashlib.sha256(lines.encode()).hexdigest()


def family_counts(laws: list) -> dict:
    fam: dict = {}
    for x in laws:
        f = fam.setdefault(str(x.get("rule")), {"derived": 0, "decided": 0, "unknown": 0})
        f["derived"] += 1
        f["decided" if x.get("status") in DECIDED else "unknown"] += 1
    return dict(sorted(fam.items()))


def safe_row(r: dict) -> dict:
    """Q56 rule 1 / 4: a row's aggregates, never splitting PROVED from REFUTED; a corpus detection keeps its law id."""
    laws = r.get("laws") or []
    docs = r.get("documents", [])
    failed = [d for d in docs if d.get("status") == "failed"]
    st = r.get("stages", {})
    det = [x for x in laws if x.get("status") == "REFUTED" and x.get("localized") and x.get("rule") == r.get("label")]
    miss = None
    if not r.get("detected"):
        if r["status"] == "not_run":
            miss = {"stage": "extract", "status": "not_run", "reason": (r.get("reason") or "")[:600]}
        else:
            miss = furthest(st)
            if miss and miss["stage"] in ("run", "replay", "filter", "score"):
                miss["reason"] = "the run decided or left UNKNOWN the derived laws; no detection (verdicts bundled, Q56)"
    return {"id": r["id"], "system": r.get("system"), "label": r.get("label"),
            "reached_extraction": r["status"] == "run",
            "toolchain_refused": r["status"] == "not_run" and bool(failed)
            and all(TOOLCHAIN_RX.search(d.get("reason") or "") for d in failed),
            "attempted": sum(1 for d in docs if d.get("status") in ("extracted", "failed")),
            "extracted": sum(1 for d in docs if d.get("status") == "extracted"),
            "document_failures": sorted({(d.get("reason") or "")[:300] for d in failed})[:20],
            "stage_status": {k: (v or {}).get("status") for k, v in sorted(st.items())},
            "derive_status": (st.get("derive") or {}).get("status"), "derive_detail": ((st.get("derive") or {}).get("detail") or "")[:400],
            "laws_A": len(laws), "decided": sum(1 for x in laws if x.get("status") in DECIDED),
            "unknown": sum(1 for x in laws if x.get("status") not in DECIDED), "by_family": family_counts(laws),
            "roles": r.get("roles"), "detected": bool(r.get("detected")),
            "detection": sorted(x["law_id"] for x in det) or None if r.get("label") else None,
            "true_defect": sum(1 for x in det if x.get("class") == "true_defect"), "miss": miss}


def publish(run: str, src: Path, vault: Path) -> None:
    """Move route A's per-law outputs and raw corpus.json into the vault; commit aggregates and commitments."""
    raw = load(src / "corpus.json")
    v = vault / run
    v.mkdir(parents=True, exist_ok=True)
    bundles = load(OUT / "bundles.json") or {}
    rows = []
    for r in raw["rows"]:
        dest = v / r["id"] / src.name
        dest.mkdir(parents=True, exist_ok=True)
        for d in PER_LAW:
            if (src / r["id"] / d).is_dir():
                if (dest / d).exists():
                    shutil.rmtree(dest / d)
                shutil.move(str(src / r["id"] / d), str(dest / d))
        rows.append(safe_row(r))
        bundles[f"{run}/{r['id']}"] = bundle_sha(v / r["id"])
    shutil.move(str(src / "corpus.json"), str(v / f"{src.name}_corpus.json"))
    (OUT / run).mkdir(parents=True, exist_ok=True)
    (OUT / run / f"{src.name}_aggregates.json").write_text(dumps({
        "doc": f"I107 {run} route A aggregates (Q56): per-law outputs are bundled outside the repo", "rows": rows,
        "toolchain": raw.get("toolchain"), "holon_sha256": raw.get("holon_sha256"),
        "protocol_sha256": raw.get("protocol_sha256"), "corpus_sha256": raw.get("corpus_sha256")}))
    (OUT / "bundles.json").write_text(dumps(dict(sorted(bundles.items()))))


def publish_morph(work: Path, vault: Path) -> None:
    """Morph (c): copy morph_roles.json; aggregate morph_auto.json; bundle the new laws' files (Q56 rule 3)."""
    src = work / "results" / "M6" / "I104"
    (OUT / "morph").mkdir(parents=True, exist_ok=True)
    shutil.copy(src / "morph_roles.json", OUT / "morph" / "morph_roles.json")
    a = load(src / "morph_auto.json")
    new = [r for r in a["rows"] if r["in_auto"] and not r["in_hand"]]
    v = vault / "morph" / "new_laws"
    if v.exists():
        shutil.rmtree(v)
    for r in new:
        for d in ("laws/M3", "results/M3"):
            f = work / d / f"{r['law_id']}.json"
            if f.is_file():
                (v / d).mkdir(parents=True, exist_ok=True)
                shutil.copy(f, v / d / f.name)
    shutil.copy(src / "morph_auto.json", vault / "morph" / "morph_auto.json")
    s = a["summary"]
    old = [r for r in a["rows"] if r["in_hand"]]
    (OUT / "morph" / "aggregates.json").write_text(dumps({
        "doc": "I107 (c): Morph under --roles auto (tools/i104_roles_experiment.py morph in a scratch copy). Laws already on "
               "the lead keep their public verdicts; the new laws are aggregated only (Q56 rule 3).",
        "hand_laws": s["hand_laws"], "auto_laws": s["auto_laws"], "role_dependent_decided": s["role_dependent_decided"],
        "role_dependent_rederived": s["role_dependent_rederived"], "role_dependent_lost": s["role_dependent_lost"],
        "lost": [{k: r[k] for k in ("law_id", "hand_status", "auto_status", "auto_note")} for r in old
                 if r["law_id"] in s["role_dependent_lost"]],
        "other_decided_unchanged": s["other_decided_unchanged"], "new_laws": len(new),
        "new_decided": sum(1 for r in new if r["auto_status"] in DECIDED),
        "new_unknown": sum(1 for r in new if r["auto_status"] not in DECIDED),
        "new_by_family": family_counts([{"rule": r["rule"], "status": r["auto_status"]} for r in new])}))
    b = load(OUT / "bundles.json") or {}
    b["morph/new_laws"] = bundle_sha(v) if v.exists() else hashlib.sha256(b"").hexdigest()
    (OUT / "bundles.json").write_text(dumps(dict(sorted(b.items()))))


# ------------------------------------------------------------------------------------------- assemble
def furthest(stages: dict) -> dict | None:
    for s in STAGES:
        st = stages.get(s)
        if st is not None and st.get("status") not in ("ok",):
            return {"stage": s, "status": st.get("status"), "reason": (st.get("detail") or "")[:400]}
    return {"stage": "score", "status": "ok", "reason": "every stage ok; no detection"}


def b_rows(doc) -> dict:
    out = {}
    for r in (doc or {}).get("rows", []):
        laws = r.get("laws")
        n = len(laws) if isinstance(laws, list) else (laws or 0)
        st = r.get("stages") or {}
        bad = next(({"stage": s, "reason": (st[s].get("detail") or "")[:400]} for s in st
                    if isinstance(st[s], dict) and st[s].get("status") not in ("ok", None)), None)
        out[r["id"]] = {"laws": n, "derive_ran": "derive" in st, "first_failure": bad}
    return out


def c_rows(doc) -> dict:
    out = {}
    for e in (doc or {}).get("entries", []):
        out[e["id"]] = {"laws": e.get("laws", 0), "roles": e.get("roles", 0), "role_kinds": e.get("role_kinds", {}),
                        "law_rules": e.get("law_rules", {}), "derive_ran": "derive" in (e.get("stages") or {}),
                        "derive": (e.get("stages") or {}).get("derive"), "reason": e.get("reason")}
    return out


def corpus_section() -> dict | None:
    a = load(OUT / "corpus" / "holon_aggregates.json")
    if a is None:
        return None
    b, c = b_rows(load(OUT / "corpus" / "go_machines.json")), c_rows(load(OUT / "corpus" / "roles_derive.json"))
    rows = []
    for x in a["rows"]:
        x = dict(x)
        x["laws"] = {"A": x.pop("laws_A"), "B": b.get(x["id"], {}).get("laws", 0), "C": c.get(x["id"], {}).get("laws", 0)}
        x["route_B"], x["route_C"] = b.get(x["id"]), c.get(x["id"])
        x["reached_derive"] = x["derive_status"] in ("ok", "failed") or bool(b.get(x["id"], {}).get("derive_ran")) \
            or bool(c.get(x["id"], {}).get("derive_ran"))
        rows.append(x)
    tot = {"extracted": sum(r["reached_extraction"] for r in rows),
           "toolchain_refused": sum(r["toolchain_refused"] for r in rows),
           "reached_derive": sum(r["reached_derive"] for r in rows),
           "entries_with_law": sum(1 for r in rows if sum(r["laws"].values()) > 0),
           "laws": {k: sum(r["laws"][k] for r in rows) for k in ("A", "B", "C")},
           "decided_laws": sum(r["decided"] for r in rows), "detected": sum(r["detected"] for r in rows),
           "true_defect": sum(r["true_defect"] for r in rows)}
    return {"label": "contaminated: post-I51", "rows": rows, "totals": tot}


def sealed_section() -> dict | None:
    a = load(OUT / "sealed" / "static_aggregates.json")
    ver = load(OUT / "sealed" / "verify.json")
    if a is None and ver is None:
        return None
    c = c_rows(load(OUT / "sealed" / "roles_derive.json"))
    sl = load(OUT / "sealed" / "slither.json") or {"targets": {}}
    sai = load(OUT / "sealed" / "static_ai.json") or {"targets": {}}
    bundles = load(OUT / "bundles.json") or {}
    targets = []
    for x in (a or {}).get("rows", []):
        targets.append({"id": x["id"], "system": x["system"], "attempted": x["attempted"], "extracted": x["extracted"],
                        "document_failures": x["document_failures"], "stage_status": x["stage_status"],
                        "derive_status": x["derive_status"], "derive_detail": x["derive_detail"],
                        "laws": {"A": x["laws_A"], "C": c.get(x["id"], {}).get("laws", 0)},
                        "decided": x["decided"], "unknown": x["unknown"], "by_family": x["by_family"],
                        "roles": x["roles"], "route_C": c.get(x["id"]), "miss": x["miss"],
                        "static_ai": sai["targets"].get(x["id"], {}).get("status"),
                        "slither": sl["targets"].get(x["id"], {"status": None})})
    hand = subprocess.run(["git", "-C", str(ROOT), "log", "--diff-filter=A", "--name-only", "--format=", "--grep=^I107",
                           "--", "targets/"], capture_output=True, text=True).stdout.split()
    return {"label": "sealed in the repository (I106 commit-reveal), not sealed from the agent's priors",
            "verify": (ver or {}).get("verify"), "targets": targets,
            "P8": {"status": "withheld (embargo)",
                   "commitments": {x["id"]: bundles.get(f"sealed/{x['id']}") for x in targets}},
            "hand_written_target_files": sorted(set(hand))}


def morph_section() -> dict | None:
    r, a = load(OUT / "morph" / "morph_roles.json"), load(OUT / "morph" / "aggregates.json")
    if r is None or a is None:
        return None
    i104 = load(ROOT / "results" / "M6" / "I104" / "morph_auto.json")["summary"]
    i104r = load(ROOT / "results" / "M6" / "I104" / "morph_roles.json")
    return {"label": "contaminated: the development target; reported, never substituted for M3's record",
            "precision": r["precision"], "recall": r["recall"], **{k: v for k, v in a.items() if k != "doc"},
            "i104": {"precision": i104r["precision"], "recall": i104r["recall"],
                     **{k: i104[k] for k in ("role_dependent_decided", "role_dependent_rederived",
                                             "role_dependent_lost", "new_laws", "auto_laws", "hand_laws")}}}


def assemble() -> str:
    return dumps({"doc": "I107 summary (tools/i107_generality.py assemble) over results/eval/generality/; the protocol is "
                         "spec/M6/lib/i107_protocol.json, the key spec/M6/predictions/I107.json. Q56: no per-law verdict.",
                  "corpus": corpus_section(), "sealed": sealed_section(), "morph": morph_section(),
                  "snapshot": load(OUT / "snapshot.json"), "summary_version": "holon-i107-summary/0.2"})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("roles-derive")
    p.add_argument("--src", required=True); p.add_argument("--entries", required=True)
    p.add_argument("--scratch", required=True); p.add_argument("--out", required=True)
    p = sp.add_parser("assemble"); p.add_argument("--check", action="store_true")
    p = sp.add_parser("publish"); p.add_argument("--run", required=True); p.add_argument("--src", required=True)
    p.add_argument("--vault", required=True)
    p = sp.add_parser("publish-morph"); p.add_argument("--work", required=True); p.add_argument("--vault", required=True)
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    if a.cmd == "roles-derive":
        roles_derive(Path(a.src), a.entries.split(","), Path(a.scratch), Path(a.out))
        return 0
    if a.cmd == "publish":
        publish(a.run, Path(a.src), Path(a.vault))
        return 0
    if a.cmd == "publish-morph":
        publish_morph(Path(a.work), Path(a.vault))
        return 0
    text = assemble()
    if a.check:
        ok = (OUT / "summary.json").is_file() and (OUT / "summary.json").read_text() == text
        print("assemble --check: " + ("OK" if ok else "DIFFERS"))
        return 0 if ok else 1
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(text)
    print(f"wrote {(OUT / 'summary.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
