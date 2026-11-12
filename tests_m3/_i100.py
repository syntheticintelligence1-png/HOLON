"""I100's instrument, fixed at the prereg (C_K) and pinned by sha256 in the key's thresholds: what rule
PAR_record_round_trip and the record map give over the committed documents, computed here independently of holon/;
the plants of the build checks; the target-agnostic scan; the outcome files of docs/iterations/I100/; and the runs of
round 3's mutants. It imports nothing from holon/ or tools/: holon is run as a subprocess.

    python -m tests_m3._i100 outcomes  [--root R]                 docs/iterations/I100/{statuses,registry,backtest}.json
    python -m tests_m3._i100 mutations --work DIR [--root R]      docs/iterations/I100/mutations.json
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = "I100"
OUT = "docs/iterations/I100/"
BASE = "4fd64a52f030438cac06595f8673840d6c5c6525"
CODEC_DIR = "gen/M3/codec"
HAND = "facts/morph_header.json"
MAP = "spec/M3/lib/backtest_map.json"
RECORD_MAP = "spec/M3/lib/backtest_record_map.json"
BASIS = "gen/M3/par_record/basis.json"
BACKTEST = "results/M3/backtest.json"
CATALOG, PREVIOUS = "holon-rules/1.16", "holon-rules/1.15"
SUBFORMS = ("constant_read", "record_round_trip")
TAGS = {"constant_read": "rt", "record_round_trip": "rec"}
ROWS = ("L_rt_go_v0", "L_rt_go_v1", "L_rt_go_v2")
MUTANTS = ("m05", "m06", "m07", "m08")
SPEC = "audit/rounds/M3/round3/a1_spec_{}.json"
GO_METHOD = re.compile(r"\((\*?)(.*)\)\.([^.()]+)")
CALL = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(")
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
UNBOUNDED = {"kind": "unbounded"}
GENERIC = {"version", "Bytes", "Bool", "Byte", "Fields"}   # HOLON's own vocabulary, not a target's


def load(root, rel: str):
    return json.loads((Path(root) / rel).read_text(encoding="utf-8"))


def sha256(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def git(root, *args) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout


def at(root, commit: str, rel: str):
    """A committed JSON file at a commit, or None."""
    p = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{rel}"], capture_output=True, text=True)
    return json.loads(p.stdout) if p.returncode == 0 else None


# ================================================================== the rule, computed here
def codec_docs(root) -> list[tuple[str, dict]]:
    """The committed linked codec documents (gen/M3/codec/*.json with a linked_version), by path."""
    out = []
    for p in sorted((Path(root) / CODEC_DIR).glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("linked_version"):
            out.append((p.relative_to(root).as_posix(), d))
    return out


def family_of(f: dict) -> tuple | None:
    """A decoder's getter family: (its document, its source's qualifier, the qualifier's last identifier), the
    qualifier being the source text before its last "." ("(pkg.T)" for a Go method "(pkg.T).M"); None without one."""
    src = f.get("source") or ""
    if "." not in src:
        return None
    q = src.rsplit(".", 1)[0]
    name = re.sub(r"[()*]", "", q).rsplit(".", 1)[-1].rsplit("/", 1)[-1]
    return (f.get("document"), q, name) if IDENT.fullmatch(name) else None


def active(f: dict, v: int) -> bool:
    return f.get("versions") is None or v in f["versions"]


def component(lay: list, rd: dict) -> dict:
    """What an encoder's layout holds in a decoder's read range: a field's bytes 0..w-1 in order, constants, or
    neither (missing: what the range holds instead)."""
    o, w = rd["offset"], rd["width"]
    cells = [lay[i] if i < len(lay) else ["unknown"] for i in range(o, o + w)]
    if cells and cells[0][0] == "field" and all(c == ["field", cells[0][1], k] for k, c in enumerate(cells)):
        return {"component": "field", "field": cells[0][1]}
    if cells and all(c[0] == "const" for c in cells):
        return {"component": "constant", "bytes": "0x" + bytes(int(c[1]) for c in cells).hex()}
    return {"component": None, "holds": {"fields": sorted({c[1] for c in cells if c[0] == "field"}),
                                         "constant_cells": sum(1 for c in cells if c[0] == "const"),
                                         "other_cells": sum(1 for c in cells if c[0] not in ("field", "const"))}}


def version_premise(doc: dict, carrier: str, v: int) -> list:
    """P0 as rule P1 states it: a record carrier with a field named version gets version = v (the field's width)."""
    rec = doc["carriers"].get(carrier) or {}
    ws = [f["width"] for f in rec.get("fields") or [] if f["name"] == "version"] if rec.get("kind") == "record" else []
    return [{"eq": [{"field": "version", "of": {"var": "h"}}, {"bytes": "0x" + v.to_bytes(ws[0], "big").hex()}]}] \
        if ws else []


def conjunct(enc: str, dec: str, comp: dict) -> dict:
    rhs = {"field": comp["field"], "of": {"var": "h"}} if comp["component"] == "field" else {"bytes": comp["bytes"]}
    return {"eq": [{"call": dec, "args": [{"call": enc, "args": [{"var": "h"}]}]}, {"some": rhs}]}


def statement(enc_from: str, assume: list, claim: dict) -> dict:
    return {"binders": [{"q": "forall", "name": "h", "type": enc_from}], "assume": assume, "claim": claim,
            "scope": dict(UNBOUNDED)}


def expected(root, docs: list[tuple[str, dict]] | None = None) -> dict:
    """The rule over the documents (default the committed ones): every instance (encoder into a byte carrier, getter
    family, version) with its members in (read offset, read width, name) order and their components; the
    constant_read laws (one per constant component of a decoder from the carrier); the record_round_trip laws (one
    per instance without a missing member); the obstructions; the unversioned encoders."""
    docs = codec_docs(root) if docs is None else docs
    out = {"instances": [], "constant_read": {}, "record_round_trip": {}, "obstructions": [], "unversioned": []}
    for rel, doc in docs:
        fs = doc["functions"]
        for c in sorted(cid for cid, car in doc["carriers"].items() if car.get("kind") == "bytes"):
            decs = {n: f for n, f in fs.items() if f["kind"] == "decoder" and f["from"] == c}
            fams: dict = {}
            for n, f in decs.items():
                k = family_of(f)
                if k is not None:
                    fams.setdefault(k, []).append(n)
            for e in sorted(n for n, f in fs.items() if f["kind"] == "encoder" and f["to"] == c):
                vs = fs[e].get("versions")
                if not vs:
                    out["unversioned"].append({"document": rel, "encoder": e})
                    continue
                for v in sorted(vs):
                    lay = fs[e]["layouts"][str(v)]
                    vp = version_premise(doc, fs[e]["from"], v)
                    for d in sorted(n for n in decs if active(decs[n], v)):
                        comp = component(lay, decs[d]["read"])
                        if comp["component"] == "constant":
                            lid = f"L_par_{TAGS['constant_read']}_{e}_{d}_v{v}"
                            out["constant_read"][lid] = statement(fs[e]["from"], vp, conjunct(e, d, comp))
                    for key in sorted(fams, key=lambda k: (k[2], k[0] or "", k[1])):
                        mem = sorted((n for n in fams[key] if active(decs[n], v)),
                                     key=lambda n: (decs[n]["read"]["offset"], decs[n]["read"]["width"], n))
                        if not mem:
                            continue
                        members = [dict(getter=n, reads=[decs[n]["read"]["offset"], decs[n]["read"]["width"]],
                                        **component(lay, decs[n]["read"])) for n in mem]
                        missing = [m["getter"] for m in members if m["component"] is None]
                        lid = None if missing else f"L_par_{TAGS['record_round_trip']}_{e}_{key[2]}_v{v}"
                        inst = {"document": rel, "encoder": e, "carrier": c, "family": key[2], "version": v,
                                "members": members, "law": lid, "missing": missing}
                        out["instances"].append(inst)
                        if missing:
                            out["obstructions"].append({"kind": "missing_component", "document": rel, "encoder": e,
                                                        "family": key[2], "version": v, "getters": missing})
                        else:
                            out["record_round_trip"][lid] = statement(
                                fs[e]["from"], vp, {"all": [conjunct(e, m["getter"], m) for m in members]})
    return out


# ================================================================== plants (build checks)
def plant_shift(doc: dict, enc: str, version: int, field: str, by: int = -1) -> dict:
    """Round 3's m08 in kind: the field's cells of enc's layout at version written `by` bytes off; the cells it leaves
    hold nothing written (unknown), the cells it lands on are overwritten."""
    d = copy.deepcopy(doc)
    lay = d["functions"][enc]["layouts"][str(version)]
    idx = [i for i, c in enumerate(lay) if c[0] == "field" and c[1] == field]
    cells = {i: lay[i] for i in idx}
    for i in idx:
        lay[i] = ["unknown"]
    for i in idx:
        lay[i + by] = cells[i]
    return d


def plant_guard(doc: dict, getter: str, version: int) -> dict:
    """Round 3's m06 in kind: a getter's version guard that drops a version (its versions without it)."""
    d = copy.deepcopy(doc)
    f = d["functions"][getter]
    f["versions"] = [v for v in f["versions"] if v != version]
    return d


# ================================================================== the record map (B1 amended), computed here
def code_method(f: dict) -> str:
    src = f.get("source") or ""
    m = GO_METHOD.fullmatch(src)
    return m.group(3) if m else src.rsplit(".", 1)[-1]


def record_map_doc(root=ROOT) -> dict:
    """The content of spec/M3/lib/backtest_record_map.json without its "doc": for each hand decoder whose getters
    are, in order, a hand projection's order, every getter slot -> the component decoder (from an image carrier of the
    decoder's argument type under B1's map) implementing the method the slot's getter code calls first, when exactly
    one does (else null); and the getter family those decoders share (family_of), when they share one."""
    root = Path(root)
    hand, mu = load(root, HAND), load(root, MAP)
    comps = [(rel, d) for rel, d in codec_docs(root) if d.get("component") in mu["components"]]
    records = []
    for dn, df in sorted(hand["functions"].items()):
        if df.get("kind") != "decoder" or not df.get("getters"):
            continue
        order = [g["name"] for g in df["getters"]]
        projs = sorted(pn for pn, pf in hand["functions"].items()
                       if pf.get("kind") == "projection" and pf.get("order") == order)
        if len(projs) != 1:
            continue
        carriers = mu["types"].get(df["from"]) or []
        for rel, doc in comps:
            decs = {n: f for n, f in doc["functions"].items() if f["kind"] == "decoder" and f["from"] in carriers}
            slots = []
            for g in df["getters"]:
                m = CALL.match(g.get("code") or "")
                hits = sorted(n for n, f in decs.items() if m and code_method(f) == m.group(1))
                slots.append({"slot": g["name"], "getter": hits[0] if len(hits) == 1 else None})
            fams = {family_of(decs[s["getter"]])[2] for s in slots if s["getter"] and family_of(decs[s["getter"]])}
            records.append({"decoder": dn, "projection": projs[0], "component": doc["component"], "document": rel,
                            "family": sorted(fams)[0] if len(fams) == 1 else None, "slots": slots})
    ins = [HAND, MAP] + [rel for rel, _ in comps]
    return {"map_version": "holon-backtest-record-map/0.1", "against": mu["against"], "hand": HAND,
            "base": {"path": MAP, "sha256": sha256(root / MAP)},
            "inputs": [{"path": p, "sha256": sha256(root / p)} for p in ins], "records": records}


# ================================================================== the target-agnostic scan
def target_names(root=ROOT) -> list[str]:
    """Names of the target: the codec documents' functions, carriers, record fields, component and role; the hand
    document's functions, types and fields; every law id of laws/M0 to laws/M3; the target repository's name. Names of
    two characters or fewer and HOLON's own vocabulary (GENERIC) are left out."""
    root = Path(root)
    names: set = {"morph", "Morph"}
    for _, d in codec_docs(root):
        names |= set(d["functions"]) | set(d["carriers"]) | {d.get("component"), d.get("role")}
        for c in d["carriers"].values():
            names |= {f["name"] for f in c.get("fields") or []}
    hand = load(root, HAND)
    names |= set(hand["functions"]) | set(hand["types"])
    names |= {f["name"] for t in hand["types"].values() for f in t.get("fields") or [] if isinstance(f, dict)}
    for m in ("M0", "M1", "M2", "M3"):
        names |= {p.stem for p in (root / "laws" / m).glob("L_*.json")}
    return sorted(n for n in names if isinstance(n, str) and len(n) > 2 and n not in GENERIC)


def added_lines(root, base: str = BASE, under: str = "holon/") -> list[tuple[str, str]]:
    """(file, line) for every line the commits since base add under `under` (git diff base..HEAD)."""
    out, cur = [], None
    for ln in git(root, "diff", "-U0", f"{base}..HEAD", "--", under).splitlines():
        if ln.startswith("+++ "):
            cur = ln[6:] if ln.startswith("+++ b/") else None
        elif ln.startswith("+") and cur:
            out.append((cur, ln[1:]))
    return out


def scan(lines: list[tuple[str, str]], names: list[str]) -> list[tuple[str, str, str]]:
    pats = [(n, re.compile(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])")) for n in names]
    return [(f, n, ln.strip()) for f, ln in lines for n, p in pats if p.search(ln)]


# ================================================================== outcomes
def _statuses(root, commit: str | None) -> dict:
    if commit is None:
        return {p.stem: json.loads(p.read_text(encoding="utf-8")).get("status")
                for p in sorted((Path(root) / "results" / "M3").glob("L*.json"))}
    names = git(root, "ls-tree", "--name-only", f"{commit}:results/M3").split()
    out = {}
    for n in sorted(x for x in names if x.startswith("L") and x.endswith(".json")):
        r = at(root, commit, f"results/M3/{n}")
        out[n[:-5]] = (r or {}).get("status")
    return out


def _table(t: dict | None) -> dict | None:
    if t is None:
        return None
    return {"exit_blockers": t.get("exit_blockers"),
            "rows": {r["old"]: {"new": r["new"], "acceptance": r["acceptance"], "implication": r["implication"],
                                "gap": r["gap"], "bridges": sorted([b["fn"], b["status"]] for b in r["bridges"])}
                     for r in t["rows"]}}


def outcomes(root=ROOT) -> dict:
    """OUT/statuses.json (every M3 record's status at BASE and at HEAD), OUT/registry.json (the M3 registry's
    catalog and statements at BASE and at HEAD) and OUT/backtest.json (the back-test table's rows and exit blockers
    at BASE and at HEAD)."""
    root = Path(root)
    rb, rh = at(root, BASE, "laws/M3/REGISTRY.json"), load(root, "laws/M3/REGISTRY.json")
    return {"statuses.json": {"base": _statuses(root, BASE), "head": _statuses(root, None)},
            "registry.json": {"base": {"rule_catalog_version": rb["rule_catalog_version"],
                                       "statements": rb["statements"]},
                              "head": {"rule_catalog_version": rh["rule_catalog_version"],
                                       "statements": rh["statements"]}},
            "backtest.json": {"before": _table(at(root, BASE, BACKTEST)), "after": _table(load(root, BACKTEST))}}


# ================================================================== round 3's mutants
def _env(tree: Path | None = None) -> dict:
    e = dict(os.environ)
    e["BEND_NO_TELEMETRY"] = "1"
    e.setdefault("GOTOOLCHAIN", "local")
    e.setdefault("GOFLAGS", "-mod=readonly")
    if tree is not None:   # the tree's own code, cwd and ROOT, as the A1 driver runs holon in a mutant's tree
        e["PYTHONPATH"] = str(tree)
        e.pop("HOLON_BUILD_DIR", None)
    return e


def holon(cwd: Path, args: list, tree: Path | None = None, timeout: int = 5400) -> tuple[int | None, str]:
    try:
        p = subprocess.run([sys.executable, "-m", "holon", *[str(a) for a in args]], cwd=str(cwd), env=_env(tree),
                           capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return None, f"timeout after {timeout} s"


def _instances(basis: dict | None) -> dict:
    """{(encoder, family, version): {"law", "missing", "conjuncts"}} of a par_record basis document."""
    out = {}
    for x in (basis or {}).get("instances") or []:
        out[(x["encoder"], x["family"], x["version"])] = {
            "law": x.get("law"), "missing": sorted(x.get("missing") or []),
            "conjuncts": sum(1 for m in x.get("members") or [] if m.get("component") is not None)}
    return out


def run_mutation(root, mid: str, work: Path) -> dict:
    """One of round 3's mutants on HEAD's tree: `holon audit mutation` (its spec, --max-law-runs 0, the trees kept
    under work), then in the mutant's tree: one round trip of the codec document whose statement the mutant keeps
    (holon run regenerates the component model the record bridges import), the mutant's record laws (holon run), and
    the back-test (holon backtest --out). The kept trees are removed. No scratch path is recorded."""
    root, work = Path(root), Path(work)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    head = git(root, "rev-parse", "HEAD").strip()
    rc, txt = holon(root, ["audit", "mutation", "--milestone", "M3", "--round", "3", "--spec", SPEC.format(mid),
                           "--target", head, "--out", work / "a1.json", "--work", work / "w", "--keep-trees",
                           "--max-law-runs", "0"])
    res = {"mutant": mid, "spec": SPEC.format(mid), "spec_sha256": sha256(root / SPEC.format(mid)), "target": head,
           "driver": {"exit": rc}}
    tree = work / "w" / "m" / mid / "tree"
    try:
        if (work / "a1.json").is_file():
            m = json.loads((work / "a1.json").read_text(encoding="utf-8"))["mutations"][0]
            der = m.get("derivation") or {}
            res["driver"].update(verdict=m.get("verdict"), why=m.get("why"),
                                 added=der.get("added"), dropped=der.get("dropped"),
                                 statement_changed=der.get("statement_changed"))
        if not (tree / BASIS).is_file():
            res["verdict"] = ["not_evaluated"]
            res["detail"] = "no par_record basis in the mutant's tree: " + txt[-600:].replace(str(work), "<work>")
            return res
        base, mut = _instances(load(root, BASIS)), _instances(load(tree, BASIS))
        res["instances"] = {f"{e}|{f}|v{v}": x for (e, f, v), x in sorted(mut.items())}
        res["changed"] = sorted(f"{e}|{f}|v{v}" for (e, f, v) in base if mut.get((e, f, v)) != base[(e, f, v)])
        res["dropped"] = sorted(f"{e}|{f}|v{v}" for (e, f, v) in base if (e, f, v) not in mut)
        res["obstructed"] = sorted(f"{e}|{f}|v{v}" for (e, f, v), x in mut.items() if x["missing"])
        keep = None
        for p in sorted((tree / "laws" / "M3").glob("L_par_rt_*.json")):
            lw = json.loads(p.read_text(encoding="utf-8"))
            old = root / "laws" / "M3" / p.name
            if lw.get("subform") == "round_trip" and lw.get("facts", "").startswith(CODEC_DIR + "/") and old.is_file() \
                    and json.loads(old.read_text(encoding="utf-8"))["statement"] == lw["statement"]:
                keep = p.stem
                break
        rc1, t1 = holon(tree, ["run", "--milestone", "M3", "--laws", keep], tree=tree) if keep else (None, "none")
        res["model_refresh"] = {"law": keep, "exit": rc1}
        recs = sorted(x["law"] for x in mut.values() if x["law"])
        rc2, _ = holon(tree, ["run", "--milestone", "M3", "--laws", ",".join(recs)], tree=tree) if recs else (None, "")
        st = {}
        for lid in recs:
            rp = tree / "results" / "M3" / f"{lid}.json"
            r = json.loads(rp.read_text(encoding="utf-8")) if rp.is_file() else {}
            st[lid] = {"status": r.get("status"), "failing_conjunct": r.get("failing_conjunct"),
                       "statement_hash": r.get("statement_hash")}
        res["record_runs"] = {"exit": rc2, "laws": st}
        rc3, t3 = holon(tree, ["backtest", "--milestone", "M3", "--out", work / "backtest.json"], tree=tree)
        bt = json.loads((work / "backtest.json").read_text(encoding="utf-8")) if (work / "backtest.json").is_file() \
            else None
        res["backtest"] = {"exit": rc3, **(_table(bt) or {"detail": t3[-600:].replace(str(work), "<work>")})}
        v = []
        if res["obstructed"]:
            v.append("obstructed")
        if any(x["status"] == "REFUTED" for x in st.values()) or any(
                s == "REFUTED" for r in (res["backtest"].get("rows") or {}).values() for _, s in r["bridges"]):
            v.append("refuted")
        if res["dropped"]:
            v.append("dropped")
        if not v:
            v = ["not_caught"] if rc == 0 and rc3 == 0 and bt is not None else ["not_evaluated"]
        res["verdict"] = v
        res["caught"] = bool({"obstructed", "refuted"} & set(v))
        return res
    finally:
        shutil.rmtree(work / "w", ignore_errors=True)


def mutations(root, work: Path) -> dict:
    return {"document": "i100_mutations", "key": KEY,
            "mutants": {mid: run_mutation(root, mid, Path(work) / mid) for mid in MUTANTS}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tests_m3._i100")
    ap.add_argument("what", choices=("outcomes", "mutations"))
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--work")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    out = root / OUT
    out.mkdir(parents=True, exist_ok=True)
    if a.what == "outcomes":
        for name, doc in outcomes(root).items():
            (out / name).write_text(dumps(doc), encoding="utf-8")
    else:
        if not a.work:
            ap.error("mutations needs --work")
        (out / "mutations.json").write_text(dumps(mutations(root, Path(a.work))), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
