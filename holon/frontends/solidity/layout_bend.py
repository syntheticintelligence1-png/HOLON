"""S2 translator: straight-line Yul fragment programs -> Bend (M2, docs/M2_SPEC.md §3).

The input is the fragment program produced by `layout_extract`: a sequence of
memory ops (`mstore`, `mstore8`), reads (`mload`/`shr`), copies (`calldatacopy`),
guards (`require`), allocation markers and hash edges, each traced from one Yul
statement of the compiled codec/consumer code. Translation is syntactic: every
op maps to exactly one Bend expression by the rules below; anything without a
rule is a hard `Unsupported` and lands in coverage debt — never approximated.

The emitted model follows the same conventions as holon.gen.model (one U32 per
byte, 57005 = undefined EVM memory, version dispatch through `<fn>_at`), so the
generated M0 model and this translated one can be evaluated side by side.
"""
from __future__ import annotations

import json
from pathlib import Path

from ... import facts as F
from ...gen import model as G


class Unsupported(Exception):
    pass


BYTES = G.BYTES
FIELDS = G.FIELDS
MAYBE_FIELDS = G.MAYBE_FIELDS


def _list(xs: list[str]) -> str:
    return "[" + ", ".join(xs) + "]" if xs else "Nil{}"


def _cell(c: list) -> str:
    return G._cell(c)


def _indent(lines: list[str], n: int) -> list[str]:
    return [" " * n + l for l in lines]


def fields(doc: dict) -> list[dict]:
    return doc["types"]["Header"]["fields"]


def widths(doc: dict) -> dict:
    return {f["name"]: f["width"] for f in fields(doc)}


def cell_names(doc: dict) -> list[str]:
    return [f"{f['name']}_{k}" for f in fields(doc) for k in range(f["width"])]


def hdr_pattern(doc: dict, reuse: bool = True) -> str:
    pre = "+" if reuse else ""
    return "Hdr{" + ", ".join(pre + c for c in cell_names(doc)) + "}"


# ---------------------------------------------------------------- per-op rules
def translate_store(op: dict, mem: str, i: int, w: dict) -> list[str]:
    """mstore/mstore8 at a constant offset -> one put().

    op["src"] is the extractor's cell list for the written value
    ([{"field": name}, {"zeros": n}] | [{"const": b}..])."""
    cells = F.src_cells(op["src"], w)
    F.check_op_width("enc_sol", op, len(cells))
    lines = [f"# {op.get('code', op['op'])}".replace("?", "")]
    lines.append(f"{mem}{i + 1} = put({mem}{i}, {op['offset']}n, {_list([_cell(c) for c in cells])})")
    return lines


def translate_program(prog: list, mem: str, w: dict, when_filter=None) -> tuple[list[str], int, list[str]]:
    """A straight-line op list -> put-chain body, the final memory var, and debt."""
    lines, i, debt = [f"{mem}0 = {mem}0"], 0, []
    for op in prog:
        kind = op["op"]
        if when_filter is not None and not when_filter(op):
            continue
        if kind in ("mstore", "mstore8"):
            lines += translate_store(op, mem, i, w)
            i += 1
        elif kind in ("alloc", "fmp_write", "comment"):
            if kind == "comment":
                lines.append(f"# {op['text']}")
            continue
        elif kind == "edge":
            debt.append(f"{kind}:{op.get('kind', '?')}")
            lines.append(f"# edge {op.get('kind', '?')} (out of byte-layout scope)")
            continue
        else:
            raise Unsupported(f"no translation rule for op {kind}")
    return lines, i, debt


# ---------------------------------------------------------------- the encoder
def gen_encoder(doc: dict, prog: list) -> list[str]:
    f = doc["functions"]["enc_sol"]
    w = widths(doc)
    versions = F.encoder_versions(f)
    size = F.evm_memory_size(f, w)
    out = ["# enc_sol: translated store sequence (solidity-evm-memory)"]
    out += ["def enc_sol_at(n: Nat, h: Hdr) -> " + BYTES + ":", "  match n:"]
    for pat, v in G.nat_cases(max(versions)):
        out.append(f"    case {pat}:")
        if v in versions:
            ops = [op for op in prog if op["op"] in ("mstore", "mstore8") and F.when_ok(op.get("when"), v)]
            body = [f"m0 = List.replicate(U32, {size}n, {F.UNDEF})"]
            i = 0
            for op in ops:
                body += translate_store(op, "m", i, w)
                i += 1
            body.append(f"List.take(&2, U32, m{i}, {f['length_by_version'][str(v)]}n)")
            out += ["      match h:", f"        case {hdr_pattern(doc)}:"] + _indent(body, 10)
        else:
            out.append(f"      [{F.UNDEF}]")
    out += ["", "def enc_sol(+h: Hdr) -> " + BYTES + ":", "  enc_sol_at(hdr_version(h), h)"]
    return out


# ---------------------------------------------------------------- the predicate
def gen_predicate(doc: dict) -> list[str]:
    rules = doc["functions"]["ok_sol"]["rules"]
    out = ["# ok_sol: translated _loadBatchHeader/_getBatchVersion guards"]
    out += ["def ok_sol_at(n: Nat, t: " + BYTES + ") -> Bool:", "  match n:"]
    k = G.max_version_const(rules)
    for pat, v in G.nat_cases(k):
        r = G._first_rule("ok_sol", rules, False, v)
        out += [f"    case {pat}:", f"      # {r.get('code', '')}".replace("?", "").rstrip(),
                f"      {G._rule_value('ok_sol', r['then'])}"]
    empty = G._first_rule("ok_sol", rules, True, None)
    if not isinstance(empty["then"], bool):
        raise Unsupported("ok_sol: the empty-input rule must be a constant")
    out += ["", "def ok_sol(b: " + BYTES + ") -> Bool:", "  match b:", "    case Nil{}:",
            f"      {G._rule_value('ok_sol', empty['then'])}", "    case Con{h, t}:",
            "      ok_sol_at(U32.to_nat(h), t)"]
    return out


# ---------------------------------------------------------------- the decoder
def gen_decoder(doc: dict) -> list[str]:
    f = doc["functions"]["dec_sol"]
    getters = f["getters"]
    k = max([g.get("when", {}).get("version_ge", 0) for g in getters] + [0])
    out = ["# dec_sol: translated codec getters (mload/shr -> slice)"]
    out += ["def dec_sol_fields_at(n: Nat, +b: " + BYTES + ") -> " + FIELDS + ":", "  match n:"]
    for pat, v in G.nat_cases(k):
        gs = [f"slice(b, {g['offset']}n, {g['width']}n)" for g in getters if F.when_ok(g.get("when"), v)]
        out += [f"    case {pat}:", f"      {_list(gs)}"]
    out += ["", "def dec_sol_fields(b: " + BYTES + ") -> " + FIELDS + ":", "  match b:",
            "    case Nil{}:", "      Nil{}", "    case Con{+h, +t}:",
            "      dec_sol_fields_at(U32.to_nat(h), Con{h, t})", "",
            "def dec_sol_sel(c: Bool, b: " + BYTES + ") -> " + MAYBE_FIELDS + ":", "  match c:",
            "    case True{}:", "      Some{dec_sol_fields(b)}", "    case False{}:", "      None{}", "",
            "# None unless the extracted guard ok_sol accepts b",
            "def dec_sol(+b: " + BYTES + ") -> " + MAYBE_FIELDS + ":", "  dec_sol_sel(ok_sol(b), b)"]
    return out


# ---------------------------------------------------------------- the projection
def gen_projection(doc: dict) -> list[str]:
    f = doc["functions"]["view"]
    w = widths(doc)
    when = f.get("when", {})
    k = max([when.get(n, {}).get("version_ge", 0) for n in f["order"]] + [0])
    out = ["# view: header projection in extracted getter order"]
    out += ["def view_at(n: Nat, h: Hdr) -> " + FIELDS + ":", "  match n:"]
    for pat, v in G.nat_cases(k):
        items = [_list([f"{n}_{i}" for i in range(w[n])]) for n in f["order"]
                 if F.when_ok(when.get(n), v)]
        out += [f"    case {pat}:", "      match h:", f"        case {hdr_pattern(doc)}:",
                f"          {_list(items)}"]
    out += ["", "def view(+h: Hdr) -> " + FIELDS + ":", "  view_at(hdr_version(h), h)"]
    return out


# ---------------------------------------------------------------- the module
def generate(doc: dict, aux: dict) -> str:
    prog = aux["program"]
    unsupported = [op for op in prog if op["op"] not in
                   ("mstore", "mstore8", "alloc", "fmp_write", "comment", "edge")]
    if unsupported:
        raise Unsupported(f"untranslatable ops: {[o['op'] for o in unsupported]}")
    lines = [
        "# GENERATED by holon.frontends.solidity.layout_bend from extracted layouts;",
        "# do not edit (fix the extractor/translator instead).",
        f"# target: {doc['target']['repo']} @ {doc['target']['commit']}",
        "import Base", "",
        "# Header carrier: one U32 per byte, in declaration order.",
        "type Hdr is Data:",
        "  Hdr{" + ", ".join(f"{c}: U32" for c in cell_names(doc)) + "}", "",
        G.PRELUDE,
        "def hdr_version(h: Hdr) -> Nat:", "  match h:", f"    case {hdr_pattern(doc, reuse=False)}:",
        "      U32.to_nat(version_0)", "",
    ]
    w = widths(doc)
    for name in w:
        lines += [f"def get_{name}(h: Hdr) -> {BYTES}:", "  match h:",
                  f"    case {hdr_pattern(doc)}:", f"      {_list([f'{name}_{i}' for i in range(w[name])])}", ""]
    lines += gen_encoder(doc, prog) + [""]
    lines += gen_predicate(doc) + [""]
    lines += gen_decoder(doc) + [""]
    lines += gen_projection(doc) + [""]
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="holon.frontends.solidity.layout_bend",
                                 description="S2: translate extracted layout program to Bend")
    ap.add_argument("--layouts", default=str(Path(__file__).resolve().parents[3]
                                             / "spec" / "M2" / "extracted" / "header_layouts.json"))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[3]
                                         / "gen" / "M2" / "sol_layout" / "morph_header.bend"))
    a = ap.parse_args(argv)
    doc = json.loads(Path(a.layouts).read_text())
    # regenerate the program from the committed document (no solc needed):
    # the ops list of enc_sol is the store sequence; alloc/fmp markers are fixed.
    prog = [{"op": "alloc", "var": "batchPtr", "init": "fmp"}, {"op": "fmp_write"},
            {"op": "comment", "text": "encoder: composed store sequence"}]
    prog += [{"op": op["op"], "offset": op["offset"], "src": op["src"],
              "when": op.get("when"), "code": op.get("code")}
             for op in doc["functions"]["enc_sol"]["ops"]]
    prog.append({"op": "edge", "kind": "keccak256"})
    text = generate(doc, {"program": prog})
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    print("wrote", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
