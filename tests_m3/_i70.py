"""I70's instrument (the cutover x slash laws): the contract's rules written a second time, independently of holon/.

It reads only committed JSON documents and records (and, for P1, the pinned solc of config/holon.json on the explorer's
recorded sources); it never imports holon. Fixed at the prereg: a wrong instrument is a Question and an
instrument_inconsistency line of spec/M3/amendments.jsonl, never a silent edit.

  python -m tests_m3._i70 --basis        print the basis (S1-S3) computed from the versioned document
  python -m tests_m3._i70 --write        write spec/M3/lib/cutover_slash_basis.json (at the prereg only)
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDECAR = "spec/M3/lib/cutover_slash.json"
BASIS = "spec/M3/lib/cutover_slash_basis.json"


class InstrumentError(RuntimeError):
    pass


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def side(root: Path = ROOT) -> dict:
    return load(root / SIDECAR)


# ------------------------------------------------------------------------------------------------------ terms
def contains(term, sub) -> bool:
    """`sub` occurs in `term` (structural equality of JSON terms)."""
    if term == sub:
        return True
    if isinstance(term, list):
        return any(contains(t, sub) for t in term)
    if isinstance(term, dict):
        return any(contains(t, sub) for t in term.values())
    return False


def member_reads(term, family: str) -> list:
    """Every ["member", ["map", ["storage", family], key], m] read inside `term`, as (key, m)."""
    out = []
    if isinstance(term, list):
        if (len(term) == 3 and term[0] == "member" and isinstance(term[1], list) and len(term[1]) == 3
                and term[1][0] == "map" and term[1][1] == ["storage", family]):
            out.append((term[1][2], term[2]))
        for t in term:
            out.extend(member_reads(t, family))
    return out


def _label(entry: str) -> str:
    return entry.split(".", 1)[1] if "." in entry else entry


# ------------------------------------------------------------------------------------------------------ S1-S3 basis
def edge_types(vdoc: dict) -> dict:
    """S1: per MIG edge "a->b", its retyped entries (labels) and its reinterpreted entries (label at b, read labels at
    a), from the versioned document's in-flight types."""
    out: dict = {}
    for t in vdoc.get("in_flight_types") or []:
        e = out.setdefault(t["edge"], {"retyped": [], "reinterpreted": []})
        if t["kind"] == "retyped":
            e["retyped"].append(_label(t["entry"]))
        elif t["kind"] == "reinterpreted":
            e["reinterpreted"].append({"entry": _label(t["entry"]), "reads": sorted(_label(r) for r in t["reads"])})
    for e in out.values():
        e["retyped"].sort()
        e["reinterpreted"].sort(key=lambda r: r["entry"])
    return out


def _credits(action: dict, call: dict) -> list:
    """S2 (iii): the writes of a mapping cell whose value reads the written family and holds the call's result."""
    res = ["call", call["fn"], *call["args"]]
    out = []
    for w in action.get("writes") or []:
        path = w.get("path") or []
        if not path or not isinstance(path[0], list) or path[0][0] != "map":
            continue
        val = w.get("value")
        if contains(val, res) and contains(val, ["storage", w["family"]]):
            out.append({"family": w["family"], "seq": w.get("seq"), "src": w.get("src")})
    return out


def sites(action: dict, registry_words: list, retyped: list) -> list:
    """S2: the cutover slash sites of one action at one version: a call (i) whose receiver is a registry word of the
    edge's reinterpreted entry at that version, (ii) one of whose arguments reads a member of a retyped in-flight
    entry, and (iii) whose result is credited to a mapping cell (_credits)."""
    out = []
    for c in action.get("calls") or []:
        rec = c.get("receiver")
        if not (isinstance(rec, list) and len(rec) == 2 and rec[0] == "storage" and rec[1] in registry_words):
            continue
        reads = [(fam, m) for fam in retyped for a in c.get("args") or [] for (_k, m) in member_reads(a, fam)]
        if not reads:
            continue
        cr = _credits(action, c)
        if not cr:
            continue
        out.append({"fn": c["fn"], "receiver": rec[1], "reads": sorted({f"{f}.{m}" for f, m in reads}),
                    "seq": c.get("seq"), "src": c.get("src"), "credits": cr})
    return out


def basis(root: Path = ROOT) -> dict:
    """S3: one site pair per (MIG edge a->b, action op of b with an action of a of the same selector) with at least one
    site at a and one at b; two law ids per pair."""
    s = side(root)
    vrel = s["inputs"]["versioned"]
    vdoc = load(root / vrel)
    contract = vdoc["contract"]["name"]
    types = edge_types(vdoc)
    docs = {v: load(root / d["path"]) for v, d in vdoc["documents"].items()}
    pairs = []
    for edge in sorted(types):
        a, b = edge.split("->")
        t = types[edge]
        if not t["retyped"] or not t["reinterpreted"]:
            continue
        words_b = sorted({r["entry"] for r in t["reinterpreted"]})
        words_a = sorted({x for r in t["reinterpreted"] for x in r["reads"]})
        acts_a = {x["name"]: x for x in docs[a]["actions"]}
        for op in sorted(x["name"] for x in docs[b]["actions"]):
            act_b = next(x for x in docs[b]["actions"] if x["name"] == op)
            act_a = acts_a.get(op)
            if act_a is None or act_a.get("selector") != act_b.get("selector"):
                continue
            sa = sites(act_a, words_a, t["retyped"])
            sb = sites(act_b, words_b, t["retyped"])
            if sa and sb:
                tag = f"{contract}_{a}_{b}_{op}"
                pairs.append({"edge": edge, "op": op, "selector": act_b.get("selector"), "a": sa, "b": sb,
                              "laws": {"NAT": f"L_nat_slash_{tag}", "SORT": f"L_sort_slash_{tag}"}})
    return {"basis_version": "holon-cutover-slash-basis/0.1", "contract": contract,
            "versioned": {"path": vrel, "sha256": sha256_bytes((root / vrel).read_bytes())},
            "documents": {v: {"path": d["path"], "sha256": sha256_bytes((root / d["path"]).read_bytes())}
                          for v, d in sorted(vdoc["documents"].items())},
            "edge_types": types, "pairs": pairs,
            "law_ids": sorted(x for p in pairs for x in p["laws"].values())}


# ------------------------------------------------------------------------------------------------------ P1: Q12
def _i63():
    import tests_m3._i63 as m
    return m


def explorer_record(root: Path, address: str) -> dict | None:
    p = root / side(root)["outputs"]["explorer"] / f"{address}.json"
    return load(p) if p.is_file() else None


def _entry(response) -> dict:
    """The getsourcecode entry of an explorer response: the result list's first element, or the connector's parsed
    object (which may carry the entry under "result", or be the entry itself)."""
    r = response
    if isinstance(r, str):
        r = json.loads(r)
    if isinstance(r, dict) and "result" in r:
        r = r["result"]
    if isinstance(r, list):
        r = r[0] if r else {}
    if not isinstance(r, dict):
        raise InstrumentError("the explorer response holds no source entry")
    return r


def _field(entry: dict, *names):
    low = {k.lower(): v for k, v in entry.items()}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return None


def verified_input(entry: dict) -> dict | None:
    """The verified standard-JSON input ({"language", "sources", "settings"}), or a one-file input, or None when the
    explorer holds no verified source."""
    src = _field(entry, "SourceCode", "source_code", "sourceCode")
    if src is None or src == "":
        return None
    if isinstance(src, dict):
        return src if "sources" in src else {"language": "Solidity", "sources": src, "settings": {}}
    t = str(src).strip()
    if t.startswith("{{") and t.endswith("}}"):
        return json.loads(t[1:-1])
    if t.startswith("{"):
        obj = json.loads(t)
        return obj if "sources" in obj else {"language": "Solidity", "sources": obj, "settings": {}}
    name = _field(entry, "ContractName", "contract_name") or "Contract"
    return {"language": "Solidity", "sources": {f"{name}.sol": {"content": t}}, "settings": {}}


def unit_equal(inp: dict, unit: dict) -> bool:
    """The unit criterion: a source path ending with the unit's path below its build root, its text equal to the tag's
    blob byte for byte (CRLF read as LF)."""
    tail = unit["path"].split("contracts/", 1)[1] if unit["path"].startswith("contracts/") else unit["path"]
    for path, s in sorted((inp.get("sources") or {}).items()):
        if path.endswith(tail):
            text = (s.get("content") or "").replace("\r\n", "\n")
            if sha256_bytes(text.encode("utf-8")) == unit["sha256"]:
                return True
    return False


def compile_identity(root: Path, inp: dict, name: str, entry: dict) -> str:
    """The code identity (I63's rule) of contract `name` compiled from the verified input by the pinned solc, with the
    explorer's recorded settings (the standard-JSON input's own, else the entry's optimizer fields)."""
    cfg = load(root / "config" / "holon.json")
    _i63().check_toolchain(cfg)
    settings = dict(inp.get("settings") or {})
    if not settings:
        runs = _field(entry, "Runs", "runs")
        opt = str(_field(entry, "OptimizationUsed", "optimization_used") or "0") in ("1", "true", "True")
        settings = {"optimizer": {"enabled": opt, "runs": int(runs or 200)}}
        evm = _field(entry, "EVMVersion", "evm_version")
        if evm and str(evm).lower() not in ("default", ""):
            settings["evmVersion"] = str(evm).lower()
    settings["outputSelection"] = {"*": {"*": ["evm.deployedBytecode.object",
                                               "evm.deployedBytecode.immutableReferences",
                                               "evm.deployedBytecode.linkReferences"]}}
    doc = {"language": inp.get("language") or "Solidity", "sources": inp["sources"], "settings": settings}
    with tempfile.TemporaryDirectory() as d:
        p = subprocess.run([cfg["replay"]["solc"], "--standard-json"], input=json.dumps(doc), capture_output=True,
                           text=True, cwd=d, timeout=7200)
    out = json.loads(p.stdout)
    errs = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    if errs:
        raise InstrumentError("; ".join((e.get("formattedMessage") or e["message"])[:300] for e in errs[:3]))
    hits = [c for f in out.get("contracts", {}).values() for n, c in f.items() if n == name]
    if len(hits) != 1:
        raise InstrumentError(f"the verified input compiles {len(hits)} contracts named {name}")
    dep = hits[0]["evm"]["deployedBytecode"]
    ranges = sorted([[r["start"], r["length"]] for rs in (dep.get("immutableReferences") or {}).values() for r in rs]
                    + [[r["start"], r["length"]] for f in (dep.get("linkReferences") or {}).values()
                       for rs in f.values() for r in rs])
    return sha256_bytes(_i63().code_identity(bytes.fromhex(dep["object"]), ranges)), ranges


def onchain_identity(root: Path, ranges: list) -> str:
    acq = side(root)["acquisition"]["registry"]
    code = bytes.fromhex((root / acq["code"]).read_text(encoding="utf-8").strip().removeprefix("0x"))
    return sha256_bytes(_i63().code_identity(code, ranges))


def decide_p1(root: Path = ROOT) -> dict:
    """P1's decision from the committed explorer record: {"verified", "unit_equal", "compile_match", "label"}."""
    s = side(root)
    acq = s["acquisition"]
    addr = acq["registry"]["implementation"]
    rec = explorer_record(root, addr)
    if rec is None:
        raise InstrumentError(f"no explorer record for {addr}")
    entry = _entry(rec["response"])
    inp = verified_input(entry)
    out = {"address": addr, "verified": inp is not None, "unit_equal": False, "compile_match": False,
           "compiler": _field(entry, "CompilerVersion", "compiler_version"),
           "contract": _field(entry, "ContractName", "contract_name")}
    if inp is None:
        out["label"] = acq["labels"]["tag_matched"]
        return out
    out["unit_equal"] = unit_equal(inp, acq["unit"])
    ident, ranges = compile_identity(root, inp, acq["registry"]["contract"], entry)
    out["compile_match"] = ident == onchain_identity(root, ranges)
    out["label"] = acq["labels"]["verified" if out["unit_equal"] and out["compile_match"] else "tag_matched"]
    return out


# ------------------------------------------------------------------------------------------------------ P3 recount
def recount(steps_doc: dict) -> dict:
    """The refinement record's totals recounted from its per-step rows: compared steps, disagreements, unsupported
    steps, steps per version of the versioned member, and frames per link row (caller member, callee member, selector),
    counting a frame when it is ok."""
    rows = steps_doc.get("steps") or []
    links: dict = {}
    by_version: dict = {}
    for r in rows:
        by_version[r.get("version") or "-"] = by_version.get(r.get("version") or "-", 0) + 1
        for f in r.get("frames") or []:
            _parent, caller, member, sel, _value, ok = f
            if ok:
                key = f"{caller}->{member}:{sel}"
                links[key] = links.get(key, 0) + 1
    return {"steps": len(rows), "disagreements": sum(1 for r in rows if not r.get("agree")),
            "unsupported": sum(1 for r in rows if r.get("unsupported")), "by_version": dict(sorted(by_version.items())),
            "links": dict(sorted(links.items()))}


# ------------------------------------------------------------------------------------------------------ main
def main(argv: list) -> int:
    if "--basis" in argv:
        sys.stdout.write(json.dumps(basis(ROOT), indent=1, sort_keys=True) + "\n")
        return 0
    if "--write" in argv:
        (ROOT / BASIS).write_text(json.dumps(basis(ROOT), indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return 0
    if "--p1" in argv:
        sys.stdout.write(json.dumps(decide_p1(ROOT), indent=1, sort_keys=True) + "\n")
        return 0
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
