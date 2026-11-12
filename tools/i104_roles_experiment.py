"""I104's measured runs (results/M6/I104/), outside every generator closure:

  python tools/i104_roles_experiment.py morph   --worktree W [--runlogs DIR]   -> morph_roles.json, morph_auto.json, morph/
  python tools/i104_roles_experiment.py planted --worktree W --runlogs DIR     -> planted.json
  python tools/i104_roles_experiment.py smoke   --scratch DIR                  -> corpus_smoke.json

The Morph documents, the corpus entries and the role-dependence rule are the key's preregistered thresholds
(spec/M6/predictions/I104.json); nothing here names a target. A worktree W is a scratch checkout in which
`holon roles --install --roles auto` replaced the role sidecars and codecs, diagram, evidence and derive ran; each of
its role-dependent laws was then run alone (`holon run --laws <id>`, one log per law in --runlogs), so that a law the
run refuses ends UNKNOWN without hiding the others.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from holon.roles import cli as C            # noqa: E402
from holon.roles import provenance as PV    # noqa: E402
KEY = ROOT / "spec" / "M6" / "predictions" / "I104.json"
OUT = ROOT / "results" / "M6" / "I104"
SUBFORMS = ("go_round_trip", "go_branch", "go_recompute", "link_domain")


def th() -> dict:
    return json.loads(KEY.read_text())["thresholds"]


def canon(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def write(name: str, obj) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(C.dumps(obj))


def role_dependent(law: dict, m: str = "M3") -> bool:
    f = str(law.get("facts") or "")
    return f.startswith(f"gen/{m}/codec/") or f.startswith(f"gen/{m}/goops/") or law.get("subform") in SUBFORMS


def laws(d: Path) -> dict:
    return {p.stem: json.loads(p.read_text()) for p in sorted(Path(d).glob("L*.json"))}


def status_of(results: Path, lid: str, log: Path | None) -> tuple[str | None, str | None]:
    """(status, note): the record's status, or UNKNOWN with the run's refusal when the run wrote no record."""
    p = results / f"{lid}.json"
    if log is not None and log.is_file():
        txt = log.read_text()
        if not txt.rstrip().endswith("rc 0") and not p.is_file():
            tail = [x for x in txt.splitlines() if x.strip() and not x.startswith("rc ")]
            return "UNKNOWN", ("run refused: " + (tail[-1] if tail else "no output"))[:300]
    if p.is_file():
        r = json.loads(p.read_text())
        return r.get("status"), None
    return None, None


def replay_of(results: Path, lid: str) -> str:
    p = results / f"{lid}.json"
    if not p.is_file():
        return "not_attempted"
    rp = json.loads(p.read_text()).get("replay")
    if isinstance(rp, dict):
        v = str(rp.get("status") or rp.get("verdict") or "")
        if v in ("confirmed", "replayed", "reproduced", "pass", "PASS"):
            return "confirmed"
        return v or "not_attempted"
    return "not_attempted"


def morph(wt: Path, runlogs: Path | None) -> None:
    t = th()
    texts = C.build(ROOT, "M3", sorted(t["morph_documents"]), "static", None)
    d = OUT / "morph"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    for n, x in texts.items():
        (d / n).write_text(x)
    sys.path.insert(0, str(ROOT))
    from tests_m6 import _i104 as H   # the key's own item definition (fixed at the prereg)
    hand, auto = H.hand_items(ROOT), H.auto_items(d)
    m = hand & auto
    write("morph_roles.json", {
        "i104_version": "holon-i104/0.1", "mode": "static", "documents": sorted(t["morph_documents"]),
        "hand_items": sorted(map(list, hand)), "auto_items": sorted(map(list, auto)),
        "matched": sorted(map(list, m)), "missed": sorted(map(list, hand - auto)),
        "extra": sorted(map(list, auto - hand)), "precision": [len(m), len(auto)], "recall": [len(m), len(hand)]})
    man = json.loads(texts["roles.json"])
    hl, al = laws(ROOT / "laws" / "M3"), laws(wt / "laws" / "M3")
    rows = []
    for lid in sorted(set(hl) | set(al)):
        h, a = hl.get(lid), al.get(lid)
        law = a or h
        dep = role_dependent(law)
        hs = status_of(ROOT / "results" / "M3", lid, None)[0] if h else None
        if a is not None and dep:
            as_, note = status_of(wt / "results" / "M3", lid, (runlogs / f"{lid}.log") if runlogs else None)
        else:
            as_, note = (hs if a is not None and h is not None and canon(a) == canon(h) else None), None
        if a is not None and dep and as_ is None:
            note = "not run (the session's time; I107 runs every law)"
        src = PV.roles_source(law, man, "M3") if dep else "hand"
        rows.append({"law_id": lid, "rule": law.get("rule"), "subform": law.get("subform"), "role_dependent": dep,
                     "in_hand": h is not None, "in_auto": a is not None,
                     "law_same": h is not None and a is not None and canon(a) == canon(h),
                     "statement_same": h is not None and a is not None
                     and canon(a.get("statement")) == canon(h.get("statement")),
                     "hand_status": hs, "auto_status": as_, "auto_note": note,
                     "roles_source": src if a is not None else None,
                     "class": PV.classify(as_, "not_attempted", src) if a is not None else None})
    dep = [r for r in rows if r["role_dependent"] and r["hand_status"] in ("PROVED", "REFUTED")]
    same = [r for r in dep if r["auto_status"] == r["hand_status"] and r["statement_same"]]
    new = [r for r in rows if r["in_auto"] and not r["in_hand"]]
    by: dict = {}
    for r in new:
        k = r["auto_status"] or "not_run"
        by[k] = by.get(k, 0) + 1
    write("morph_auto.json", {
        "i104_version": "holon-i104/0.1", "mode": "static", "roles": "results/M6/I104/morph/roles.json",
        "doc": "Morph under --roles auto in a scratch worktree (spec/M3/lib/{go_laws,link,go_ops}.json replaced by "
               "holon roles' output; codecs, diagram, evidence and derive rerun; each role-dependent law run alone). "
               "Reported, never substituted for M3's record.",
        "summary": {"hand_laws": len(hl), "auto_laws": len(al), "role_dependent_decided": len(dep),
                    "role_dependent_rederived": len(same),
                    "role_dependent_lost": sorted(r["law_id"] for r in dep if r not in same),
                    "other_decided_unchanged": sum(1 for r in rows if not r["role_dependent"] and r["law_same"]
                                                   and r["hand_status"] in ("PROVED", "REFUTED")),
                    "new_laws": len(new), "new_by_status": dict(sorted(by.items())),
                    "findings": sum(1 for r in rows if r["class"] == "finding" and r["roles_source"] != "hand")},
        "laws": rows})


def planted(wt: Path, runlogs: Path) -> None:
    prop = json.loads((OUT / "planted_proposal.json").read_text())
    man = json.loads((wt / "spec" / "M3" / "lib" / "roles_manifest.json").read_text()) \
        if (wt / "spec" / "M3" / "lib" / "roles_manifest.json").is_file() else None
    if man is None:
        man = json.loads(C.build(wt, "M3", sorted(th()["morph_documents"]), "static+ai",
                                 OUT / "planted_proposal.json")["roles.json"])
    al = laws(wt / "laws" / "M3")
    kinds = {"link": "link", "go_ops": "go_ops", "recompute": "go_laws"}
    cases = []
    dropped = {(d["sidecar"], d["id"]): d["reason"] for d in man.get("dropped") or []}
    for kind, side in kinds.items():
        for rid in sorted(prop.get(kind) or {}):
            ls = []
            for lid, law in sorted(al.items()):
                src = PV.roles_source(law, man, "M3")
                hit = (side == "go_ops" and str(law.get("facts")) == f"gen/M3/goops/{rid}.json") or \
                      (side == "link" and str(law.get("facts")) == f"gen/M3/codec/{rid}.json") or \
                      (side == "go_laws" and lid.startswith(f"L_par_gorc_{rid}_"))
                if not hit:
                    continue
                st, note = status_of(wt / "results" / "M3", lid, runlogs / f"{lid}.log")
                rp = replay_of(wt / "results" / "M3", lid)
                ls.append({"law_id": lid, "status": st or "UNKNOWN", "note": note, "replay": rp,
                           "roles_source": src, "class": PV.classify(st or "UNKNOWN", rp, src)})
            cases.append({"id": rid, "kind": kind, "planted": prop[kind][rid],
                          "outcome": ("dropped: " + dropped[(side, rid)]) if (side, rid) in dropped
                          else ("laws" if ls else "no law derived"), "laws": ls})
    write("planted.json", {"i104_version": "holon-i104/0.1", "proposal": "results/M6/I104/planted_proposal.json",
                           "proposal_sha256": man["proposed"]["sha256"] if man.get("proposed") else None,
                           "cases": cases,
                           "findings": sum(1 for c in cases for x in c["laws"] if x["class"] == "finding")})


def smoke(scratch: Path) -> None:
    t = th()
    from holon.eval.holon_run import COPY_DIRS, _IGNORE
    entries = []
    env = dict(os.environ, BEND_NO_TELEMETRY="1")
    for eid in [e for e in t["corpus_entries"] if not os.environ.get("I104_ONLY") or e == os.environ["I104_ONLY"]]:
        fd = ROOT / "results" / "eval" / "holon" / eid / "facts"
        docs = sorted(p for p in fd.glob("*.extracted.json")) if fd.is_dir() else []
        row = {"id": eid, "documents": [p.name for p in docs], "roles": 0, "role_kinds": {}, "laws": 0,
               "law_rules": {}, "stages": {}}
        if not docs:
            row["reason"] = "no stored document (I51 stored none for this entry)"
            entries.append(row)
            continue
        s = scratch / eid
        if s.exists():
            shutil.rmtree(s)
        s.mkdir(parents=True)
        for dname in COPY_DIRS:
            shutil.copytree(ROOT / dname, s / dname, ignore=_IGNORE)
        rels = []
        for p in docs:
            rel = f"results/eval/holon/{eid}/facts/{p.name}"
            (s / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(p, s / rel)
            rels.append(rel)
        M = "M9"   # a scratch milestone: diagram and evidence take M<k> only

        def go(name, *args):  # noqa: E306
            cmd = [sys.executable, *args] if args[0] == "-c" else [sys.executable, "-m", "holon", *args]
            r = subprocess.run(cmd, cwd=s, capture_output=True, text=True, env=env,
                               timeout=3600)
            row["stages"][name] = {"exit": r.returncode,
                                   "detail": (r.stdout + r.stderr).strip().splitlines()[-1][:300]
                                   if (r.stdout + r.stderr).strip() else ""}
            return r.returncode == 0
        ok = go("roles", "roles", "--milestone", M, "--root", ".", "--documents", ",".join(rels), "--out-dir",
                f"gen/{M}/roles", "--install")
        if ok:
            man = json.loads((s / "gen" / M / "roles" / "roles.json").read_text())
            rs = [r for r in man["roles"] if r["sidecar"] != "typed"]
            row["roles"] = len(rs)
            for r in rs:
                row["role_kinds"][r["sidecar"]] = row["role_kinds"].get(r["sidecar"], 0) + 1
            lib = f"spec/{M}/lib"
            if (s / lib / "link.json").is_file():
                steps = [("codecs", ["codecs", "--milestone", M, "--root", "."])]
            else:   # holon codecs needs a link role; the Go-op documents are what it would write (render_all)
                steps = [("goops", ["-c", "import sys; from pathlib import Path; from holon.diagram import goops as G; "
                                          "d = G.goops_dir(sys.argv[1], '.'); d.mkdir(parents=True, exist_ok=True); "
                                          "[(d / n).write_text(t) for n, t in G.render_all('.', sys.argv[1]).items()]",
                                    M])]
            steps += [("diagram", ["diagram", "--milestone", M]), ("evidence", ["evidence", "--milestone", M])]
            if (s / lib / "sort_types.json").is_file():
                steps += [("sorts", ["sorts", "--milestone", M, "--root", ".", "--sidecar", f"{lib}/sort_types.json",
                                     "--out", f"gen/{M}/sorts"]),
                          ("types", ["types", "--milestone", M, "--root", ".", "--sidecar", f"{lib}/sort_types.json",
                                     "--out", f"gen/{M}/sorts"]),
                          ("model", ["model", "--milestone", M, "--root", ".", "--sidecar", f"{lib}/sort_types.json",
                                     "--out", f"gen/{M}/sorts/models"]),
                          ("disch", ["disch", "--milestone", M, "--root", ".", "--sidecar", f"{lib}/disch.json",
                                     "--out", f"gen/{M}/disch"])]
                dv = ["derive", "--milestone", M, "--root", ".", "--catalog", "holon-rules/1.16", "--sidecar",
                      f"{lib}/sort_types.json", "--disch", f"{lib}/disch.json", "--undo-sidecar", f"{lib}/undo.json",
                      "--fact-sidecar", f"{lib}/fact.json", "--obstructions", f"gen/{M}/sorts/obstructions.json"]
            else:
                dv = ["derive", "--milestone", M, "--root", ".", "--catalog", "holon-rules/1.16"]
            for name, args in steps:
                go(name, *args)
            go("derive", *dv)
            ls = sorted((s / "laws" / M).glob("L*.json")) if (s / "laws" / M).is_dir() else []
            row["laws"] = len(ls)
            for p in ls:
                r = json.loads(p.read_text()).get("rule")
                row["law_rules"][str(r)] = row["law_rules"].get(str(r), 0) + 1
        entries.append(row)
        shutil.rmtree(s, ignore_errors=True)
    write("corpus_smoke.json", {"i104_version": "holon-i104/0.1", "milestone": "M9 (a scratch milestone)", "catalog": "holon-rules/1.16",
                                "doc": "Smoke test, not a score (I107 scores): holon roles --install over the documents "
                                       "I51 stored, then codecs, diagram, evidence (and the typed stages when a "
                                       "transitions document exists) and derive. Laws are counted, not run.",
                                "entries": entries, "with_role": sum(1 for e in entries if e["roles"] > 0),
                                "with_law": sum(1 for e in entries if e["laws"] > 0)})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tools/i104_roles_experiment.py")
    ap.add_argument("what", choices=("morph", "planted", "smoke"))
    ap.add_argument("--worktree")
    ap.add_argument("--runlogs")
    ap.add_argument("--scratch")
    a = ap.parse_args(argv)
    if a.what == "morph":
        morph(Path(a.worktree), Path(a.runlogs) if a.runlogs else None)
    elif a.what == "planted":
        planted(Path(a.worktree), Path(a.runlogs))
    else:
        smoke(Path(a.scratch))
    return 0


if __name__ == "__main__":
    sys.exit(main())
