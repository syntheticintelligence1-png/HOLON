"""A4's oracle half (whitepaper §9.5 A4: "oracle hypotheses survive tests against the real oracles"; §9.7, L5; the
contract is the docstring of tests_m3/test_audit_loop.py, "Oracles").

    python -m holon audit oracles --milestone M [--root R] [--json]

  O1 hypotheses  every entry of the milestone's own oracle sidecar (holon.gen.oracles.milestone_sidecar:
                 spec/<M>/lib/oracles.json), tested against the real oracle as holon.oracle_check tests it (status
                 checked, mismatch, untestable_here or not_in_scope); {} when the milestone has none. A sidecar beside
                 an earlier milestone's facts document belongs to that milestone's models and is audited there
  O2 parameters  every function-typed binder (Fn<..>) of the milestone's laws: {name: {type, laws, constrained}}, where
                 constrained counts the laws with a premise that mentions it (a cf premise over it, a hyp premise, or an
                 application of it)
  O3 tables      every hash-table entry, a "hashes" object {keccak256 | sha256: [[key, word], ..]} anywhere in a
                 record's witness, witnesses or non_vacuity witness (results/<M>/L*.json), against the real oracle on
                 the key's bytes: Keccak-256 (holon/keccak.py) and SHA-256 (hashlib). An entry of any other oracle is a
                 mismatch: no real oracle is known for it here.

It reads files only and runs no checker, solver or node. Nothing here names a law or a target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WHERE = ("witness", "witnesses", "non_vacuity")


def _json(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def law_files(root: Path, milestone: str) -> list[Path]:
    d = Path(root) / "laws" / milestone
    return sorted(p for p in d.glob("L*.json") if p.is_file()) if d.is_dir() else []


def record_files(root: Path, milestone: str) -> list[Path]:
    d = Path(root) / "results" / milestone
    return sorted(p for p in d.glob("L*.json") if p.is_file()) if d.is_dir() else []


# ---------------------------------------------------------------- O1
def sidecars(root: Path, milestone: str, laws: list[dict]) -> list[Path]:
    """The milestone's own sidecar, when it has one (the laws are unused: no sidecar is attributed by its facts)."""
    from ..gen import oracles as O
    p = O.milestone_sidecar(milestone, Path(root))
    return [p] if p.is_file() else []


def hypotheses(root: Path, milestone: str, laws: list[dict]) -> dict:
    """{hypothesis id: {oracle, sidecar, kind, status, reason | detail}} by holon.oracle_check's A4 test."""
    from .. import oracle_check as OC
    from ..gen import oracles as O
    out: dict = {}
    for sp in sidecars(root, milestone, laws):
        doc = O.load(sp)
        rel = sp.relative_to(Path(root)).as_posix()
        for e in doc.get("oracles") or []:
            h = e["hypothesis"]["id"]
            res = {"oracle": e.get("id"), "sidecar": rel, "kind": e["hypothesis"].get("kind")}
            if e.get("status") == "not_in_scope":
                res.update({"status": "not_in_scope", "reason": e.get("reason")})
            else:
                res.update(OC._a4(e))
            out[h] = res
    return dict(sorted(out.items()))


# ---------------------------------------------------------------- O2
def _mentions(premises, name: str, hyp_params: dict) -> bool:
    found = False

    def walk(x):
        nonlocal found
        if found:
            return
        if isinstance(x, dict):
            if x.get("app") == name:
                found = True
                return
            if isinstance(x.get("cf"), dict) and x["cf"].get("fn") == name:
                found = True
                return
            if isinstance(x.get("hyp"), dict):
                par = hyp_params.get(x["hyp"].get("name"))
                if par is None or par == name:   # a hyp premise of no known parameter may constrain any of them
                    found = True
                    return
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(premises)
    return found


def parameters(laws: list[dict], hyp_params: dict) -> dict:
    out: dict = {}
    for law in laws:
        st = law.get("statement") or {}
        for b in st.get("binders") or []:
            t = str(b.get("type"))
            if not t.startswith("Fn<"):
                continue
            e = out.setdefault(b["name"], {"types": set(), "laws": 0, "constrained": 0})
            e["types"].add(t)
            e["laws"] += 1
            e["constrained"] += int(_mentions(st.get("assume") or [], b["name"], hyp_params))
    return {n: {"type": " | ".join(sorted(e["types"])), "laws": e["laws"], "constrained": e["constrained"]}
            for n, e in sorted(out.items())}


# ---------------------------------------------------------------- O3
def table_entries(rec: dict) -> list[tuple[str, str, str, str]]:
    """(where, oracle, key, word) of every hash-table entry of a record, in document order."""
    out: list = []

    def walk(x, where):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "hashes" and isinstance(v, dict):
                    for o, lst in sorted(v.items()):
                        for e in lst if isinstance(lst, list) else []:
                            out.append((where, o, e[0] if isinstance(e, list) and e else None,
                                        e[1] if isinstance(e, list) and len(e) > 1 else None))
                else:
                    walk(v, where)
        elif isinstance(x, list):
            for v in x:
                walk(v, where)
    walk(rec.get("witness"), "witness")
    walk(rec.get("witnesses"), "witnesses")
    walk((rec.get("non_vacuity") or {}).get("witness"), "non_vacuity")
    return out


def real_answer(oracle: str, key) -> int | None:
    """The real oracle's word on the key's bytes, as an integer; None when the oracle or the key is unknown."""
    if not isinstance(key, str) or not key.startswith("0x"):
        return None
    try:
        b = bytes.fromhex(key[2:])
    except ValueError:
        return None
    if oracle == "keccak256":
        from ..keccak import keccak256
        return int.from_bytes(keccak256(b), "big")
    if oracle == "sha256":
        return int.from_bytes(hashlib.sha256(b).digest(), "big")
    return None


def entry_agrees(oracle: str, key, word) -> bool:
    want = real_answer(oracle, key)
    if want is None or not isinstance(word, str) or not word.startswith("0x"):
        return False
    try:
        return int(word, 16) == want
    except ValueError:
        return False


def tables(records: dict) -> dict:
    n, by, bad = 0, {}, []
    for lid, rec in sorted(records.items()):
        for where, o, k, w in table_entries(rec):
            n += 1
            by[o] = by.get(o, 0) + 1
            if not entry_agrees(o, k, w):
                bad.append({"law": lid, "where": where, "oracle": o, "key": k})
    return {"entries": n, "oracles": dict(sorted(by.items())), "mismatches": bad}


# ---------------------------------------------------------------- the report
def report(root: Path, milestone: str) -> tuple[dict, list[Path]]:
    """(the O1-O3 report, the files it read)."""
    root = Path(root)
    lfs, rfs = law_files(root, milestone), record_files(root, milestone)
    laws = [_json(p) for p in lfs]
    records = {p.stem: _json(p) for p in rfs}
    scs = sidecars(root, milestone, laws)
    hyp_params: dict = {}
    for sp in scs:
        from ..gen import oracles as O
        for e in O.load(sp).get("oracles") or []:
            hyp_params[e["hypothesis"]["id"]] = (e.get("parameter") or {}).get("name")
    rep = {"hypotheses": hypotheses(root, milestone, laws), "parameters": parameters(laws, hyp_params),
           "tables": tables(records)}
    return rep, sorted(set(lfs) | set(rfs) | set(scs))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon audit oracles", description=__doc__.split("\n\n")[0])
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rep, _files = report(Path(a.root).resolve(), a.milestone)
    if a.json:
        print(json.dumps(rep, indent=2, sort_keys=True))
        return 0
    t = rep["tables"]
    print(f"{a.milestone}: {len(rep['hypotheses'])} hypothesis(es); "
          f"{len(rep['parameters'])} oracle parameter(s), "
          f"{sum(v['constrained'] for v in rep['parameters'].values())} constraining premise(s); "
          f"{t['entries']} table entries, {len(t['mismatches'])} mismatch(es)")
    for m in t["mismatches"]:
        print(f"  mismatch: {m['law']} {m['where']} {m['oracle']} {m['key']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
