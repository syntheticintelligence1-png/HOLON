"""`python -m holon sorts`: the M3 sort pass.

1. infer the sort assignment of every seeded facts file (7.7) and freeze it in spec/M3/sorts/assignment/
2. generate the sorted facts (frozen facts + sort observers + cited extensions) into spec/M3/sorts/facts/
3. compile the sorts to Bend types with coercion obligations (7.8), check them, and check that the
   canaries (an obligation dropped / a false premise) are rejected
4. bind the SORT law specs to the generated facts (sha256) and write the M3 REGISTRY.json

Deterministic: running it twice leaves the tree byte-identical (tests_m3 asserts this).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .. import bend, facts as F, ir
from . import bendgen, factsgen, infer

ROOT = Path(__file__).resolve().parents[2]
M3 = Path("spec") / "M3" / "sorts"
MILESTONE = "M3_sorts"
HEADER = "facts/morph_header.json"


def _canon(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def sort_canaries(assignment: dict, workdir: Path, cfg: dict) -> list[dict]:
    """Gate G4 canaries of the sort types (7.8): a site that realizes a signed duration without its sign
    premise, a union read with the wrong tag premise, a width narrowing whose bound premise is false.
    Bend must reject each for a semantic (typing) reason, not a parse error."""
    workdir.mkdir(parents=True, exist_ok=True)
    out = []
    for name in bendgen.CANARIES:
        cp = workdir / f"{name}.bend"
        cp.write_text(bendgen.generate(assignment, canary_drop=name))
        r = bend.check(cp, cfg)
        semantic = r.marker == bend.MARK_FAIL and "Location:" in r.out and not re.search(r"- observed : '", r.out)
        lines = [l for l in r.out.strip().splitlines() if l.strip()]
        out.append({"id": f"CANARY_sort_{name}", "kind": f"sort_{name}", "source_law": "spec/M3/sorts/gen/sorts.bend", "negated": False,
                    "rejected": (not r.ok) and semantic, "checker_first_line": r.first_line, "error": (lines[-1] if lines else "")[:200],
                    "counterexample": f"canary_{name}", "law": None})
    return out


def frozen_sort_canaries(root: Path, workdir: Path, cfg: dict) -> list[dict]:
    asg = root / M3 / "assignment" / "morph_rollup.json"
    if not asg.exists():
        return []
    return sort_canaries(json.loads(asg.read_text()), workdir, cfg)


def run_sorts(root: Path | None = None, log=print) -> dict:
    root = Path(root or ROOT)
    cfg = bend.config(root)
    seeds = json.loads((root / M3 / "seeds.json").read_text())
    asg_dir = root / M3 / "assignment"
    asg_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {"assignments": {}, "sorted_facts": {}, "bend": {}, "laws": {}}
    assignments: dict = {}
    for rel, sd in seeds.items():
        if rel == "doc":
            continue
        fp = root / rel
        facts = json.loads(fp.read_text())
        sha = F.sha256_file(fp)
        if rel == HEADER:
            j = infer.infer_header(facts, sd)
        else:
            j = infer.infer(facts, sd).to_json()
        j = {"generated": factsgen.GEN_DOC.replace("factsgen", "infer"), "source_facts": rel, "facts_sha256": sha, **j}
        out = asg_dir / (Path(rel).stem + ".json")
        out.write_text(_canon(j))
        assignments[rel] = j
        n_open = len([o for o in j.get("obligations", []) if not o.get("discharged")])
        report["assignments"][rel] = {"file": str(out.relative_to(root)), "obligations": len(j.get("obligations", [])), "open": n_open,
                                      "conflicts": len(j.get("conflicts", []))}
        log(f"sorts: {rel}: {len(j.get('obligations', []))} obligations ({n_open} open), {len(j.get('conflicts', []))} conflicts")
        if rel in factsgen.EXTENSIONS:
            sp = root / M3 / "facts" / (Path(rel).stem + ".sorted.json")
            factsgen.write_sorted(fp, rel, j, sp)
            report["sorted_facts"][rel] = str(sp.relative_to(root))
    # 7.8: sorts as Bend types
    gen = root / M3 / "gen"
    gen.mkdir(parents=True, exist_ok=True)
    main_asg = assignments["spec/M1/facts/morph_rollup.json"]
    sb = gen / "sorts.bend"
    sb.write_text(bendgen.generate(main_asg))
    r = bend.check(sb, cfg)
    report["bend"]["sorts"] = {"file": str(sb.relative_to(root)), "ok": r.ok, "marker": r.marker}
    if not r.ok:
        raise RuntimeError(f"sorts.bend does not check: {r.out[:1500]}")
    if bend.escape_hatches(sb.read_text()):
        raise RuntimeError("sorts.bend uses an escape hatch")
    if bend.verdict_enabled(cfg):                 # second kernel on the sort types and their sites (8.8)
        rv = bend.check_verdict(sb, cfg)
        report["bend"]["sorts"]["verdict"] = {"ok": rv.ok, "marker": rv.marker}
        if not rv.ok:
            raise RuntimeError(f"sorts.bend fails --verdict: {rv.out[:1500]}")
    else:
        report["bend"]["sorts"]["verdict"] = {"ok": None, "marker": "not_run"}
    for c in sort_canaries(main_asg, root / "build" / "m3_canaries", cfg):
        report["bend"]["canary:" + c["kind"][5:]] = {"rejected": c["rejected"], "checker_first_line": c["checker_first_line"], "error": c["error"]}
        if not c["rejected"]:
            raise RuntimeError(f"canary {c['kind']} was accepted by bend")
    log(f"sorts: {sb.relative_to(root)} checks; {len(bendgen.CANARIES)} canaries rejected")
    # laws + registry
    ldir = root / M3 / "laws"
    laws = []
    for p in sorted(ldir.glob("L_*.json")):
        law = json.loads(p.read_text())
        law["facts_sha256"] = F.sha256_file(root / law["facts"])
        p.write_text(json.dumps(law, indent=2) + "\n")
        laws.append(law)
    facts_files = sorted({l["facts"] for l in laws})
    primary = "spec/M3/sorts/facts/morph_rollup.sorted.json"
    reg = {"milestone": MILESTONE, "facts": primary, "facts_sha256": F.sha256_file(root / primary),
           "facts_files": {f: F.sha256_file(root / f) for f in facts_files},
           "statements": {l["law_id"]: ir.statement_hash(l) for l in laws}}
    (ldir / "REGISTRY.json").write_text(json.dumps(reg, indent=2) + "\n")
    report["laws"] = {l["law_id"]: {"facts": l["facts"], "predicted": l.get("predicted")} for l in laws}
    res = root / "results" / MILESTONE
    res.mkdir(parents=True, exist_ok=True)
    (res / "sorts_report.json").write_text(_canon(report))
    log(f"sorts: {len(laws)} laws bound; registry written")
    return report
