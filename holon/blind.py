"""The blind-rerun agreement metric (BUILD_PLAN I82 = I46a; the contract is rules B1-B6 of the docstring of
tests_m3/test_blind.py).

    python -m holon compare --blind DIR [--lead DIR] [--milestone M[,M..]] [--out FILE] [--threshold X]
    python -m holon compare --snapshot SRC --into DST [--milestone M[,M..]]

A tree is a directory with laws/<M>/L*.json (law IR) and results/<M>/L*.json (records). Two trees are compared on the
statuses of alpha-equivalent statements: each recorded law's statement is put in an alpha-normal form (binders renamed
x0, x1, .. in binder order; premises a sorted set; each eq/neq's sides sorted; a top-level conjunction a sorted set),
laws are grouped by its sha256, and a group's status is its members' common status ("MIXED:.." when they differ).
blind_agreement is the fraction of the groups found in both trees whose statuses agree; matched_fraction is the
fraction of the lead's groups found in the blind tree. Law ids, facts paths and every other field are not part of the
comparison, so a blind rerun that names laws differently, or keeps its facts elsewhere, still matches.

Nothing here names a law or a target. Output is deterministic (sorted keys and lists, no time).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNBOUNDED = {"kind": "unbounded"}


class TreeError(Exception):
    pass


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def dump(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ====================================================================== the alpha-normal form (B2)
def _rename(t, m: dict):
    """Binder occurrences renamed: {"var": n}, {"app": n} and a cf premise's fn."""
    if isinstance(t, list):
        return [_rename(x, m) for x in t]
    if not isinstance(t, dict):
        return t
    out = {}
    for k, v in t.items():
        if k in ("var", "app") and isinstance(v, str):
            out[k] = m.get(v, v)
        elif k == "cf" and isinstance(v, dict):
            out[k] = {kk: (m.get(vv, vv) if kk == "fn" and isinstance(vv, str) else _rename(vv, m))
                      for kk, vv in v.items()}
        else:
            out[k] = _rename(v, m)
    return out


def _sides_sorted(p):
    if isinstance(p, dict):
        for rel in ("eq", "neq"):
            if rel in p and isinstance(p[rel], list) and len(p[rel]) == 2:
                return {**p, rel: sorted(p[rel], key=canonical_json)}
    return p


def normal_form(statement):
    """B2. A statement without binders (holon-ir/0.1 forall or later binders) and a claim is its own normal form."""
    st = statement
    if not isinstance(st, dict) or "claim" not in st or not ("binders" in st or "forall" in st):
        return st
    if "binders" in st:
        binders = [(b.get("q", "forall"), b["name"], b["type"]) for b in st["binders"]]
    else:
        binders = [("forall", b["name"], b["type"]) for b in st["forall"]]
    names = {name: f"x{i}" for i, (_, name, _) in enumerate(binders)}
    assume = sorted({canonical_json(_sides_sorted(_rename(p, names))) for p in st.get("assume", [])})
    claim = _rename(st["claim"], names)
    if isinstance(claim, dict) and "all" in claim:
        claim = {"all": [json.loads(x) for x in sorted({canonical_json(_sides_sorted(c)) for c in claim["all"]})]}
    else:
        claim = _sides_sorted(claim)
    return {"binders": [[q, t] for q, _, t in binders], "assume": [json.loads(x) for x in assume], "claim": claim,
            "scope": st.get("scope") or dict(UNBOUNDED)}


def statement_key(statement) -> str:
    return hashlib.sha256(canonical_json(normal_form(statement)).encode("utf-8")).hexdigest()


# ====================================================================== trees (B1, B3)
def classes(tree: Path, milestone: str) -> tuple[dict, list[str]]:
    """{key: {"laws", "status", "facts"}} of a tree's recorded laws, and its unrecorded law ids."""
    tree = Path(tree)
    laws_dir, res_dir = tree / "laws" / milestone, tree / "results" / milestone
    if not laws_dir.is_dir() or not res_dir.is_dir():
        raise TreeError(f"{tree} has no laws/{milestone} or results/{milestone}")
    groups: dict[str, dict] = {}
    unrecorded = []
    for p in sorted(laws_dir.glob("L*.json")):
        law = _load(p)
        lid = law["law_id"]
        rp = res_dir / f"{lid}.json"
        status = _load(rp).get("status") if rp.is_file() else None
        if not isinstance(status, str):
            unrecorded.append(lid)
            continue
        g = groups.setdefault(statement_key(law.get("statement")), {"laws": [], "statuses": set(), "facts": set()})
        g["laws"].append(lid)
        g["statuses"].add(status)
        if law.get("facts") is not None:
            g["facts"].add(law["facts"])
    out = {}
    for key, g in groups.items():
        ss = sorted(g["statuses"])
        out[key] = {"laws": sorted(g["laws"]), "status": ss[0] if len(ss) == 1 else "MIXED:" + "+".join(ss),
                    "facts": sorted(g["facts"])}
    return out, sorted(unrecorded)


# ====================================================================== the comparison (B4, B5)
def compare_milestone(lead: Path, blind: Path, milestone: str) -> dict:
    lc, lu = classes(lead, milestone)
    bcls, bunk = classes(blind, milestone)
    matched = sorted(set(lc) & set(bcls))
    agree = [k for k in matched if lc[k]["status"] == bcls[k]["status"]]
    return {
        "lead_keys": len(lc),
        "blind_keys": len(bcls),
        "matched": len(matched),
        "agree": len(agree),
        "blind_agreement": len(agree) / len(matched) if matched else None,
        "matched_fraction": len(matched) / len(lc) if lc else None,
        "lead_only": sorted(lid for k in set(lc) - set(bcls) for lid in lc[k]["laws"]),
        "blind_only": sorted(lid for k in set(bcls) - set(lc) for lid in bcls[k]["laws"]),
        "disagreements": [{"key": k, "lead": {"laws": lc[k]["laws"], "status": lc[k]["status"]},
                           "blind": {"laws": bcls[k]["laws"], "status": bcls[k]["status"]}}
                          for k in matched if lc[k]["status"] != bcls[k]["status"]],
        "unrecorded": {"lead": lu, "blind": bunk},
        "facts_differ": [{"key": k, "lead": lc[k]["facts"], "blind": bcls[k]["facts"]}
                         for k in matched if lc[k]["facts"] != bcls[k]["facts"]],
    }


def compare(lead: Path, blind: Path, milestones: list[str]) -> dict:
    per = {m: compare_milestone(lead, blind, m) for m in milestones}
    lead_keys = sum(x["lead_keys"] for x in per.values())
    matched = sum(x["matched"] for x in per.values())
    agree = sum(x["agree"] for x in per.values())
    return {"milestones": per,
            "pooled": {"lead_keys": lead_keys, "matched": matched, "agree": agree,
                       "blind_agreement": agree / matched if matched else None,
                       "matched_fraction": matched / lead_keys if lead_keys else None}}


# ====================================================================== the projection (B6)
def snapshot(src: Path, dst: Path, milestones: list[str]) -> dict:
    """Copy src's law files byte for byte and project each recorded law's record to {law_id, status}."""
    src, dst = Path(src), Path(dst)
    counts = {}
    for m in milestones:
        laws_dir, res_dir = src / "laws" / m, src / "results" / m
        if not laws_dir.is_dir() or not res_dir.is_dir():
            raise TreeError(f"{src} has no laws/{m} or results/{m}")
        (dst / "laws" / m).mkdir(parents=True, exist_ok=True)
        (dst / "results" / m).mkdir(parents=True, exist_ok=True)
        n_laws = n_rec = 0
        for p in sorted(laws_dir.glob("L*.json")):
            data = p.read_bytes()
            (dst / "laws" / m / p.name).write_bytes(data)
            n_laws += 1
            lid = json.loads(data)["law_id"]
            rp = res_dir / f"{lid}.json"
            status = _load(rp).get("status") if rp.is_file() else None
            if isinstance(status, str):
                (dst / "results" / m / f"{lid}.json").write_text(dump({"law_id": lid, "status": status}),
                                                                 encoding="utf-8")
                n_rec += 1
        counts[m] = {"laws": n_laws, "records": n_rec}
    return counts


# ====================================================================== CLI
def _milestones(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon compare", description=__doc__.splitlines()[0])
    ap.add_argument("--blind", type=Path, help="the blind tree (laws/<M>, results/<M>)")
    ap.add_argument("--lead", type=Path, default=ROOT, help="the lead tree (default: the repository root)")
    ap.add_argument("--milestone", default="M3", help="milestones, comma-separated (default M3)")
    ap.add_argument("--out", type=Path, help="write the report here instead of stdout")
    ap.add_argument("--threshold", type=float, help="exit 1 when the pooled blind_agreement is null or below this")
    ap.add_argument("--snapshot", type=Path, help="project this tree (B6) into --into")
    ap.add_argument("--into", type=Path, help="the projection's destination")
    a = ap.parse_args(argv)
    ms = _milestones(a.milestone)
    if a.snapshot is not None:
        if a.into is None or a.blind is not None:
            print("holon compare --snapshot SRC needs --into DST and no --blind", file=sys.stderr)
            return 2
        try:
            counts = snapshot(a.snapshot, a.into, ms)
        except TreeError as e:
            print(f"holon compare: {e}", file=sys.stderr)
            return 2
        print("; ".join(f"{m}: {c['laws']} laws, {c['records']} records" for m, c in counts.items()))
        return 0
    if a.blind is None:
        print("holon compare needs --blind DIR (or --snapshot SRC --into DST)", file=sys.stderr)
        return 2
    try:
        rep = compare(a.lead, a.blind, ms)
    except TreeError as e:
        print(f"holon compare: {e}", file=sys.stderr)
        return 2
    text = dump(rep)
    if a.out is not None:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text, encoding="utf-8")
        p = rep["pooled"]
        print(f"blind_agreement {p['blind_agreement']} over {p['matched']} matched statements "
              f"(matched_fraction {p['matched_fraction']}); written to {a.out}")
    else:
        sys.stdout.write(text)
    if a.threshold is not None:
        ba = rep["pooled"]["blind_agreement"]
        return 0 if ba is not None and ba >= a.threshold else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
