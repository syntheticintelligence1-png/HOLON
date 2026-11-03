"""I93 instrument (= I38d: O5, O6 and D3 as laws over a Go part of rule PAR), fixed at the I93 prereg (BUILD_PLAN 0.1,
"instruments are inputs").

The contract is the docstring of tests_m3/test_go_laws.py, rules G1-G12. This module computes the three bases a second
time, independently of holon/, from the documents committed at the prereg base: I67's 0.2 Go document
(spec/M3/facts/morph_blob.go.extracted.json: the 0.3 document G2 writes has the same paths, with the values 0.2 leaves
unknown), the Solidity Rollup document (spec/M2/facts/morph_rollup.extracted.json) and I91's compression sidecar and
oracle results. Nothing here imports holon/.

  GO_DOC, SOL_DOC                 the documents read
  short(fn)                       G7's short name of a Go function
  shortcut_pairs(root)            G5: [{function, p, q, call}] the size tests that short-cut a compressing path, each
                                  attributed to the innermost analyzed function holding it
  codec_pairs(root)               G4: [{encoder, entry, decoder, length, read, exact_02}] the unversioned Go codec
                                  pairs of matching length
  recompute(root)                 G6: {function: "law" | reason} for the sidecar's data_hash role
  sol_layout(root)                G6: the on-chain preimage of the batch data hash as [(kind, name, bytes)]
  cb(n)                           HypZ_len's bound CB(n) (I91's sidecar text)
  o5_numbers(root)                C, CB(C), I91's |Enc x| at |x| = C and the first expanding length
  o6_lengths()                    the Go legacy preimage of one block with no L1 message, and the on-chain lengths
  expected_law_ids(root)          G7: the law ids holon derive must write for I93, sorted
  basis(root)                     the above as one JSON object
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GO_DOC = "spec/M3/facts/morph_blob.go.extracted.json"
SOL_DOC = "spec/M2/facts/morph_rollup.extracted.json"
COMPRESSION = "spec/M3/lib/compression.json"
ORACLE = "results/M3/compression_oracle.json"
SIDECAR = "spec/M3/lib/go_laws.json"
NEG = {"<=": ">", ">": "<=", "<": ">=", ">=": "<", "==": "!=", "!=": "=="}


def load(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def short(fn: str) -> str:
    """"(*pkg.T).M" and "(pkg.T).M" -> "T_M"; "pkg.F" -> "F"."""
    if fn.startswith("("):
        recv, meth = fn[1:].split(").", 1)
        return recv.lstrip("*").rsplit(".", 1)[1] + "_" + meth
    return fn.rsplit(".", 1)[1]


def _calls(t, acc: set) -> set:
    if isinstance(t, list):
        if len(t) > 1 and t[0] == "result" and isinstance(t[1], list) and t[1][:1] == ["call"]:
            acc.add(json.dumps(t[1], sort_keys=True))
        for x in t:
            _calls(x, acc)
    return acc


def _const(t) -> bool:
    return isinstance(t, list) and bool(t) and t[0] in ("bool", "const", "nil", "str")


def _size_test(c) -> bool:
    return isinstance(c, list) and len(c) == 3 and c[0] in ("<=", "<")


def lengths_of(x) -> list:
    """The terms the 0.2 frontend writes for len(x): ["len", x], and hi - lo for a slice with an explicit high bound."""
    out = [["len", x]]
    if isinstance(x, list) and x[:1] == ["slice"] and x[3] is not None:
        out.append(["op", "-", x[3], x[2] if x[2] is not None else ["const", 0]])
    return out


def _raw_pairs(f: dict) -> list:
    out = []
    ps = f.get("paths") or []
    for i, p in enumerate(ps):
        if p.get("end") != "return" or p.get("error") != "nil" or not p.get("returns") \
                or not all(_const(r) for r in p["returns"]):
            continue
        for j, q in enumerate(ps):
            if j == i or q.get("end") != "return" or q.get("error") != "nil":
                continue
            diff = [c for c in p["cond"] if c not in q["cond"]]
            if len(diff) != 1 or not _size_test(diff[0]) or [NEG[diff[0][0]]] + diff[0][1:] not in q["cond"]:
                continue
            made = _calls(q["cond"], set()) | _calls(q["returns"], set())
            new = made - _calls(p["cond"], set()) - _calls(p["returns"], set())
            # 0.2 leaves q's value unknown ("compare"): the 0.3 value is a size test of that call's result
            if not new or not any(r == ["unknown", "compare"] for r in q["returns"]):
                continue
            calls = sorted(json.loads(c)[1] for c in new if len(json.loads(c)[2]) == 1
                           and diff[0][1] in lengths_of(json.loads(c)[2][0]))
            if calls:
                out.append({"p": i, "q": j, "call": calls[0]})
    return out


def shortcut_pairs(root: Path = ROOT) -> list:
    d = load(Path(root) / GO_DOC)["go"]
    fs = d["functions"]
    raw = {fn: _raw_pairs(f) for fn, f in fs.items()}
    callees = {}
    for e in d["calls"]["edges"]:
        if e.get("callee_kind") == "analyzed":
            callees.setdefault(e["caller"], set()).add(e["callee"])
    out = []
    for fn in sorted(raw):
        for r in raw[fn]:
            if any(r["call"] in {x["call"] for x in raw.get(g, [])} for g in callees.get(fn, ()) if g != fn):
                continue   # the pair belongs to an analyzed callee: fn only inlines it
            out.append({"function": fn, **r})
    return out


def _accepts(f: dict) -> set:
    """The lengths every non-error return path of a one-parameter decoder requires of its parameter."""
    par = f["params"][0]["name"]
    out = set()
    for p in f.get("paths") or []:
        if p.get("end") != "return" or p.get("error") != "nil":
            continue
        ls = {c[2][1] for c in p["cond"] if isinstance(c, list) and c[:2] == ["==", ["len", ["param", par]]]
              and isinstance(c[2], list) and c[2][:1] == ["const"]}
        if len(ls) != 1:
            return set()
        out |= ls
    return out


def codec_pairs(root: Path = ROOT) -> list:
    d = load(Path(root) / GO_DOC)["go"]
    cod, fs = d["codecs"], d["functions"]
    versioned = {e for m in cod.get("matches") or [] for e in m["encoders"]}
    tagged = {fs[p["function"]]["params"][0]["type"] for p in cod.get("predicates") or []}
    out = []
    entries = {}
    for e in cod["encoders"]:
        entries.setdefault(e["function"], []).append(e)
    for dec in cod["decoders"]:
        f = fs[dec["function"]]
        if len(f["params"]) != 1 or f["params"][0]["type"] in tagged:
            continue
        acc = _accepts(f)
        if len(acc) != 1:
            continue
        (length,) = acc
        for enc in sorted(entries):
            if enc in versioned:
                continue
            for k, e in enumerate(entries[enc]):
                if e["length"] != length:
                    continue
                for r in dec["reads"]:
                    cells = e["cells"][r["offset"]:r["offset"] + r["width"]]
                    vals = {json.dumps(c[1], sort_keys=True) for c in cells if c[:1] == ["byte"]}
                    ok = len(cells) == r["width"] and len(vals) == 1 \
                        and [c[2] for c in cells] == list(range(r["width"]))
                    out.append({"encoder": enc, "entry": k, "decoder": dec["function"], "length": length,
                                "read": [r["offset"], r["width"], r["via"]], "single_value": ok,
                                "exact_02": e["exact"]})
    return sorted(out, key=lambda x: (x["encoder"], x["entry"], x["decoder"]))


def sol_layout(root: Path = ROOT) -> dict:
    """The value the commit action stores at the role's store site: keccak256 over a slice of a memory term."""
    side = load(Path(root) / SIDECAR)["recompute"]["data_hash"]["solidity"]
    d = load(Path(root) / side["document"])
    a = next(a for a in d["actions"] if a["name"] == side["action"])
    (m,) = [m for m in a["mstores"] if m["src"] == side["store"]]
    v = m["value"]
    assert v[0] == "keccak256" and v[1][0] == "slice" and v[1][1][0] == "mem", v[:2]
    mem, off, ln = v[1][1][1:], v[1][2], v[1][3]
    widths = {f["name"]: f["width"] for p in a["params"] for f in p.get("fields") or []}
    lay = []
    for w in mem:
        if w[0] == "mstore" and isinstance(w[2], list) and w[2][0] == "<<":
            name = w[2][1][2]
            lay.append(("be", name, w[1], (256 - w[2][2]) // 8, widths[name] // 8))
        elif w[0] == "when" and w[2][0] == "mloop":
            body = w[2][4][0]
            lay.append(("loop", w[2][3][2], body[1][1], body[1][2][1], 32))
    return {"offset": off, "length": ln, "layout": lay}


def cb(n: int) -> int:
    return n + (n >> 8) + ((131072 - n) >> 11 if n < 131072 else 0)


def o5_numbers(root: Path = ROOT) -> dict:
    r = load(Path(root) / ORACLE)
    c = r["capacity"]["C"]
    return {"C": c, "CB_C": cb(c), "enc_len_at_C": r["expansion"]["enc_len_at_limit"],
            "first_expanding": r["expansion"]["exceeding"]["min"]}


def o6_lengths() -> dict:
    go = 58 * 1 + 32 * 0
    return {"go_one_block": go, "sol": [10 + 32 * n for n in range(4)],
            "sol_reaches_go": any(10 + 32 * n == go for n in range(go))}


def recompute(root: Path = ROOT) -> dict:
    side = load(Path(root) / SIDECAR)["recompute"]["data_hash"]["go"]
    fs = load(Path(root) / GO_DOC)["go"]["functions"]
    out = {}
    for fn in side["functions"]:
        f = fs[fn]
        rets = [p for lb in f.get("loop_bodies") or [] for p in lb["paths"] if p.get("end") == "return"] \
            + [p for p in f.get("paths") or [] if p.get("end") == "return"]
        hashed = [p["returns"][0] for p in rets if p["returns"] and p["returns"][0][:2] == ["call",
                  "github.com/morph-l2/go-ethereum/crypto.Keccak256Hash"]]
        # 0.2 writes the variadic slice's allocation for both; which one holds an allocation of its own (G1 d) is read
        # from the source: DataHash appends to a loop-carried slice, DataHashV2's calculateHash copies into make()
        out[fn] = {"hash_returns": len(hashed), "loop_bodies": len(f.get("loop_bodies") or [])}
    return out


def expected_law_ids(root: Path = ROOT) -> list:
    ids = [f"L_par_gort_{short(p['encoder'])}_{short(p['decoder'])}_{p['entry']}" for p in codec_pairs(root)]
    ids += [f"L_par_gobr_{short(p['function'])}_p{p['p']}_p{p['q']}" for p in shortcut_pairs(root)]
    ids += ["L_par_gorc_data_hash_" + short("(*morph-l2/common/batch.BatchData).DataHash")]
    return sorted(ids)


def basis(root: Path = ROOT) -> dict:
    return {"shortcut_pairs": shortcut_pairs(root), "codec_pairs": codec_pairs(root), "sol_layout": sol_layout(root),
            "o5": o5_numbers(root), "o6": o6_lengths(), "recompute": recompute(root),
            "law_ids": expected_law_ids(root)}


if __name__ == "__main__":
    print(json.dumps(basis(), indent=1))
