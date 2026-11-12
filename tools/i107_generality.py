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


# ------------------------------------------------------------------------------------------- assemble
def furthest(stages: dict) -> dict | None:
    last = None
    for s in STAGES:
        st = stages.get(s)
        if st is None:
            continue
        if st.get("status") not in ("ok",):
            return {"stage": s, "status": st.get("status"), "reason": (st.get("detail") or "")[:400]}
        last = s
    return {"stage": last, "status": "ok", "reason": "every stage ok; no law of the label rule REFUTED and localized"}


def a_row(r: dict) -> dict:
    laws = r.get("laws") or []
    failed = [d for d in r.get("documents", []) if d.get("status") == "failed"]
    tc = r["status"] == "not_run" and bool(failed) and all(TOOLCHAIN_RX.search(d.get("reason") or "") for d in failed)
    st = r.get("stages", {})
    classes: dict = {}
    for x in laws:
        if x.get("status") == "REFUTED":
            k = x.get("class") or "unreplayed"
            classes[k] = classes.get(k, 0) + 1
    return {"id": r["id"], "reached_extraction": r["status"] == "run", "toolchain_refused": tc,
            "derive_status": (st.get("derive") or {}).get("status"),
            "laws_A": len(laws), "decided": sum(1 for x in laws if x.get("status") in DECIDED),
            "refuted": sum(1 for x in laws if x.get("status") == "REFUTED"),
            "refuted_unreplayed": sum(1 for x in laws if x.get("status") == "REFUTED"
                                      and (x.get("replay") in (None, "not_applicable", "unreplayed")
                                           or x.get("class") in (None, "unreplayed"))),
            "by_status": dict(sorted(_count(laws, "status").items())), "by_rule": dict(sorted(_count(laws, "rule").items())),
            "detected": bool(r.get("detected")), "detected_any": bool(r.get("detected_any")), "classes": classes,
            "documents": {"attempted": sum(1 for d in r.get("documents", []) if d.get("status") in ("extracted", "failed")),
                          "extracted": sum(1 for d in r.get("documents", []) if d.get("status") == "extracted")},
            "miss": None if r.get("detected") else (
                {"stage": "extract", "status": "not_run", "reason": (r.get("reason") or "")[:600]}
                if r["status"] == "not_run" else furthest(st))}


def _count(xs, k):
    c: dict = {}
    for x in xs:
        c[str(x.get(k))] = c.get(str(x.get(k)), 0) + 1
    return c


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
    a = load(OUT / "corpus" / "holon" / "corpus.json")
    if a is None:
        return None
    b, c = b_rows(load(OUT / "corpus" / "go_machines.json")), c_rows(load(OUT / "corpus" / "roles_derive.json"))
    rows = []
    for r in a["rows"]:
        x = a_row(r)
        x["laws"] = {"A": x.pop("laws_A"), "B": b.get(r["id"], {}).get("laws", 0), "C": c.get(r["id"], {}).get("laws", 0)}
        x["route_B"], x["route_C"] = b.get(r["id"]), c.get(r["id"])
        x["reached_derive"] = x["derive_status"] in ("ok", "failed") or bool(b.get(r["id"], {}).get("derive_ran")) \
            or bool(c.get(r["id"], {}).get("derive_ran"))
        rows.append(x)
    tot = {"extracted": sum(r["reached_extraction"] for r in rows),
           "toolchain_refused": sum(r["toolchain_refused"] for r in rows),
           "reached_derive": sum(r["reached_derive"] for r in rows),
           "entries_with_law": sum(1 for r in rows if sum(r["laws"].values()) > 0),
           "laws": {k: sum(r["laws"][k] for r in rows) for k in ("A", "B", "C")},
           "decided_laws": sum(r["decided"] for r in rows), "detected": sum(r["detected"] for r in rows),
           "detected_any": sorted(r["id"] for r in rows if r["detected_any"]),
           "true_defect": sum(r["classes"].get("true_defect", 0) for r in rows)}
    return {"label": "contaminated: post-I51", "rows": rows, "totals": tot}


def sealed_section() -> dict | None:
    a = load(OUT / "sealed" / "static" / "corpus.json")
    ver = load(OUT / "sealed" / "verify.json")
    if a is None and ver is None:
        return None
    c = c_rows(load(OUT / "sealed" / "roles_derive.json"))
    adj = load(OUT / "sealed" / "adjudication.json") or {"items": []}
    sl = load(OUT / "sealed" / "slither.json") or {"targets": {}}
    sai = load(OUT / "sealed" / "static_ai.json") or {"targets": {}}
    wl = OUT / "sealed" / "withheld.jsonl"
    withheld: dict = {}
    if wl.is_file():
        for ln in wl.read_text().splitlines():
            w = json.loads(ln)
            withheld[w["class"]] = withheld.get(w["class"], 0) + 1
    targets = []
    for r in (a or {}).get("rows", []):
        x = a_row(r)
        mine = [i for i in adj["items"] if i.get("target") == r["id"] and i.get("source") == "holon"]
        cls: dict = {}
        for i in mine:
            cls[i["class"]] = cls.get(i["class"], 0) + 1
        targets.append({"id": r["id"], "system": r["system"], "attempted": x["documents"]["attempted"],
                        "extracted": x["documents"]["extracted"], "derive_status": x["derive_status"],
                        "laws": {"A": x["laws_A"], "C": c.get(r["id"], {}).get("laws", 0)}, "by_status": x["by_status"],
                        "by_rule": x["by_rule"], "decided": x["decided"], "refuted": x["refuted"],
                        "refuted_unreplayed": x["refuted_unreplayed"], "adjudicated": dict(sorted(cls.items())),
                        "route_C": c.get(r["id"]), "miss": furthest(r.get("stages", {})) if r["status"] == "run" else
                        {"stage": "extract", "status": "not_run", "reason": (r.get("reason") or "")[:600]},
                        "static_ai": sai["targets"].get(r["id"], {}).get("status"),
                        "slither": sl["targets"].get(r["id"], {"status": None})})
    hand = subprocess.run(["git", "-C", str(ROOT), "log", "--diff-filter=A", "--name-only", "--format=", "--grep=^I107",
                           "--", "targets/"], capture_output=True, text=True).stdout.split()
    return {"label": "sealed in the repository (I106 commit-reveal), not sealed from the agent's priors",
            "verify": (ver or {}).get("verify"), "targets": targets, "withheld": dict(sorted(withheld.items())),
            "hand_written_target_files": sorted(set(hand))}


def morph_section() -> dict | None:
    r, a = load(OUT / "morph" / "morph_roles.json"), load(OUT / "morph" / "morph_auto.json")
    if r is None or a is None:
        return None
    s = a["summary"]
    i104 = load(ROOT / "results" / "M6" / "I104" / "morph_auto.json")["summary"]
    i104r = load(ROOT / "results" / "M6" / "I104" / "morph_roles.json")
    return {"label": "contaminated: the development target; reported, never substituted for M3's record",
            "precision": r["precision"], "recall": r["recall"],
            "role_dependent_decided": s["role_dependent_decided"], "role_dependent_rederived": s["role_dependent_rederived"],
            "role_dependent_lost": s["role_dependent_lost"], "new_laws": s["new_laws"], "new_by_status": s["new_by_status"],
            "findings": s.get("findings"), "auto_laws": s["auto_laws"], "hand_laws": s["hand_laws"],
            "i104": {"precision": i104r["precision"], "recall": i104r["recall"], **i104}}


def assemble() -> str:
    return dumps({"doc": "I107 summary (tools/i107_generality.py assemble) over results/eval/generality/; the protocol is "
                         "spec/M6/lib/i107_protocol.json, the key spec/M6/predictions/I107.json.",
                  "corpus": corpus_section(), "sealed": sealed_section(), "morph": morph_section(),
                  "summary_version": "holon-i107-summary/0.1"})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("roles-derive")
    p.add_argument("--src", required=True); p.add_argument("--entries", required=True)
    p.add_argument("--scratch", required=True); p.add_argument("--out", required=True)
    p = sp.add_parser("assemble"); p.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    if a.cmd == "roles-derive":
        roles_derive(Path(a.src), a.entries.split(","), Path(a.scratch), Path(a.out))
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
