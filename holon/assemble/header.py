"""Assemble a holon-facts/0.1 header document from the M2 extractors (S2 + S3).

Everything in the output comes from extraction on the given morph checkout:
  * Solidity side: holon.frontends.solidity.layout_extract.extract (S2).
  * Go side:       holon.frontends.go.__main__.extract (S3 gossa dump).
  * Go field names map to header field names by WIRE OFFSET — the offset at
    which an op writes / an accessor reads equals the cumulative offset of the
    header field in the S2 layout — never by a name table.

Consumed keys that have no extracted source are debt items in the coverage
document, never copied from hand-written facts.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from ..frontends.solidity import layout_extract
from ..frontends.go import __main__ as gofront

M0_LAWS = ("L_dom_hdr", "L_par_hdr_ssvh", "L_par_hdr_v0", "L_par_hdr_v1",
           "L_par_hdr_v2", "L_rt_go_v0", "L_rt_go_v1", "L_rt_go_v2")

GO_PKG = "batch.BatchHeaderBytes."
GO_ENC_V0 = "batch.BatchHeaderV0.Bytes"
GO_ENC_V1 = "batch.BatchHeaderV1.Bytes"
GO_PRED = "batch.BatchHeaderBytes.validate"

# Functions a facts document must carry for the M0 law set, and where each
# comes from. Everything not listed is descriptive and may be omitted.
CONSUMED = {
    "types": "S2 header_layouts doc (types.Header.fields gives name+width, wire order)",
    "functions.enc_sol": "S2 header_layouts doc",
    "functions.ok_sol": "S2 header_layouts doc",
    "functions.view": "S2 header_layouts doc",
    "functions.enc_go_v0": f"S3 go_codecs encoders[{GO_ENC_V0}].ops",
    "functions.enc_go_v1": f"S3 go_codecs encoders[{GO_ENC_V1}].ops",
    "functions.ok_go": f"S3 go_codecs predicates[{GO_PRED}].rules",
    "functions.dec_go": f"S3 go_codecs decoders.getters[{GO_PKG}*].accessors",
    "facts_version/target/extraction": "literal version tag + commit from the checkout",
}


def _field_offsets(fields: list[dict]) -> dict[int, str]:
    """wire offset -> header field name, from the S2 layout (cumulative widths)."""
    out, off = {}, 0
    for f in fields:
        out[off] = f["name"]
        off += f["width"]
    return out


def _version_set(when, vmax: int) -> set[int]:
    """Versions an accessor `when` condition admits (domain 0..vmax)."""
    if when is None:
        return set(range(vmax + 1))
    if "version_ge" in when:
        return {v for v in range(vmax + 1) if v >= when["version_ge"]}
    if "version_gt" in when:
        return {v for v in range(vmax + 1) if v > when["version_gt"]}
    if "version_le" in when:
        return {v for v in range(vmax + 1) if v <= when["version_le"]}
    if "version_lt" in when:
        return {v for v in range(vmax + 1) if v < when["version_lt"]}
    if "version_in" in when:
        return {v for v in when["version_in"] if v <= vmax}
    if "all" in when:
        return set.intersection(*(_version_set(w, vmax) for w in when["all"]))
    if "any" in when:
        return set().union(*(_version_set(w, vmax) for w in when["any"]))
    raise ValueError(f"unsupported accessor when {when}")


def _when_of(accessors: list[dict], vmax: int, debt: list[dict], element: str):
    """Merged `when` for a getter whose accessors cover a partition of versions."""
    cov = set().union(*(_version_set(a.get("when"), vmax) for a in accessors))
    if cov == set(range(vmax + 1)):
        return None
    simple = [a.get("when") for a in accessors if a.get("when")]
    uniq = {json.dumps(w, sort_keys=True) for w in simple}
    if len(uniq) == 1 and set(simple[0]) == {"version_ge"}:
        return simple[0]
    debt.append({"element": element, "kind": "when_merge",
                 "reason": f"accessor whens {uniq} cover versions {sorted(cov)}, not the full domain"})
    return simple[0] if len(uniq) == 1 else {"version_in": sorted(cov)}


def _go_field_offsets(getters: list[dict]) -> dict[str, list[int]]:
    """Go field name -> wire offsets at which its accessor(s) read.
    A `batch.BatchHeaderBytes.<Name>` getter's basename is the struct field
    name its accessors read (same symbol in the SSA dump); the wire-offset
    link to header fields is then purely positional."""
    out: dict[str, list[int]] = {}
    for g in getters:
        fn = g["function"]
        if not fn.startswith(GO_PKG):
            continue
        fld = fn[len(GO_PKG):]
        for a in g.get("accessors", []):
            out.setdefault(fld, [])
            if a["offset"] not in out[fld]:
                out[fld].append(a["offset"])
    for k in out:
        out[k].sort()
    return out


def _go_encoder(enc: dict, offsets: dict[int, str], go_fields: dict[str, list[int]],
                fields: list[dict], debt: list[dict]) -> dict:
    """S3 encoder ops -> facts ops; Go field names resolved by wire offset.

    Link order for a src field: (1) the field's accessor wire offset, if it
    lands on a header field boundary; (2) the op's own write offset, if a
    boundary (a decoder mutant may have moved the accessor); (3) the field's
    ordinal position in this encoder's op stream — its write order is the
    serialized field order, which matches the header's field order — keeping
    the fact modelable when a mutation shifts the boundaries."""
    src_fields = [s["field"] for op in enc["ops"] for s in op["src"] if "field" in s]
    tail = fields[len(fields) - len(src_fields):] if len(src_fields) <= len(fields) else []
    ordinal = {name: tail[i]["name"] for i, name in enumerate(src_fields)} if tail else {}
    ops = []
    for op in enc["ops"]:
        src = []
        for s in op["src"]:
            if "field" in s:
                cands = [o for o in go_fields.get(s["field"], []) if o in offsets]
                if len(cands) > 1:
                    debt.append({"element": f"{enc['function']}:{op['site']['line']}",
                                 "kind": "offset_link",
                                 "reason": f"field {s['field']} resolves to offsets {cands}; using {cands[0]}"})
                if cands:
                    name = offsets[cands[0]]
                elif op["offset"] in offsets:
                    name = offsets[op["offset"]]
                elif s["field"] in ordinal:
                    name = ordinal[s["field"]]
                    debt.append({"element": f"{enc['function']}:{op['site']['line']}",
                                 "kind": "offset_link_ordinal",
                                 "reason": f"field {s['field']} links to no header field boundary; "
                                           f"resolved to {name} by serialized order"})
                else:
                    debt.append({"element": f"{enc['function']}:{op['site']['line']}",
                                 "kind": "offset_link",
                                 "reason": f"field {s['field']} at offset {op['offset']} resolves to no header field"})
                    raise ValueError(f"{enc['function']}: field {s['field']} writes an unknown field")
                src.append({"field": name})
            elif "const" in s:
                src.append({"const": s["const"]})
            else:
                debt.append({"element": f"{enc['function']}:{op['site']['line']}",
                             "kind": "unsupported_src",
                             "reason": f"op source kind {sorted(s)} not expressible in facts ops"})
                raise ValueError(f"{enc['function']}: unsupported op source {s}")
        o = {"op": op["op"], "offset": op["offset"], "src": src,
             "code": f"{op['site']['file']}:{op['site']['line']}"}
        if op.get("when"):
            o["when"] = op["when"]
        ops.append(o)
    return {
        "kind": "encoder", "from": "Header", "to": "Bytes", "lang": "go-bytes",
        "source": [{"file": enc["file"], "fn": enc["function"], "line": enc["line"]}],
        "memory_init": enc["memory_init"],
        "length": enc["length"],
        "ops": ops,
    }


def _go_decoder(getters: list[dict], fields: list[dict], vmax: int,
                debt: list[dict]) -> dict:
    """dec_go: one getter per header field in wire order; accessors matched by
    (offset, width); `when` merged over contributing getters' version coverage."""
    by_off = {}
    for g in getters:
        fn = g["function"]
        if not fn.startswith(GO_PKG) or fn in (GO_PKG + "Bytes", GO_PKG + "Hash",
                                               GO_PKG + "validate"):
            continue
        for a in g.get("accessors", []):
            by_off.setdefault((a["offset"], a["width"]), []).append(
                {"fn": fn, "when": a.get("when")})
    out = []
    off = 0
    for f in fields:
        cand = by_off.get((off, f["width"]))
        if not cand:
            # a mutant moved the accessor: the decoder no longer reads this
            # field. Modelable fact — record the gap and drop the getter.
            debt.append({"element": f"dec_go:{f['name']}", "kind": "missing_getter",
                         "reason": f"no Go accessor reads offset {off} width {f['width']}"})
            off += f["width"]
            continue
        accessors = [{"when": c["when"]} for c in cand]
        entry = {"name": f["name"], "offset": off, "width": f["width"],
                 "code": ", ".join(sorted(c["fn"].split(".")[-1] for c in cand)) + "()"}
        when = _when_of(accessors, vmax, debt, f"dec_go:{f['name']}")
        if when:
            entry["when"] = when
        out.append(entry)
        off += f["width"]
    return {
        "kind": "decoder", "from": "Bytes", "to": "Maybe<Fields>", "lang": "go",
        "source": [{"file": "common/batch/batch_header.go",
                    "fn": "BatchHeaderBytes getters"}],
        "guard": "ok_go",
        "getters": out,
    }


def _target_commit(morph: Path) -> str:
    r = subprocess.run(["git", "-C", str(morph), "rev-parse", "HEAD"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "unknown"


# files gofront.extract writes into the repo; assemble restores them so the
# in-process call stays side-effect free
_GO_WRITES = ("spec/M2/extracted/go_codecs.json",
              "spec/M2/extracted/go_batchdata.json",
              "spec/M2/coverage/go.json")


def assemble(morph: Path, solc: Path | None = None) -> tuple[dict, dict]:
    """(facts_doc, coverage_doc) for the header slice of `morph`.

    Byte-deterministic for a fixed checkout + solc: both extractors are
    deterministic, and every merge here is order-stable.
    """
    morph = Path(morph)
    root = Path(__file__).resolve().parents[2]
    saved = {p: (root / p).read_bytes() if (root / p).exists() else None
             for p in _GO_WRITES}
    try:
        s2doc, s2debt, _aux = layout_extract.extract(morph, solc or layout_extract.SOLC)
        go = gofront.extract(morph)
    finally:
        for p, blob in saved.items():
            fp = root / p
            if blob is None:
                fp.unlink(missing_ok=True)
            else:
                fp.write_bytes(blob)
    cc = go["codecs"]
    debt = [{"element": d["element"], "kind": d.get("kind", "debt"),
             "reason": d.get("reason", "")}
            for d in s2debt]
    fields = s2doc["types"]["Header"]["fields"]
    vmax = s2doc["functions"]["enc_sol"]["domain"]["version_le"]
    offsets = _field_offsets(fields)

    functions = dict(s2doc["functions"])  # enc_sol, ok_sol, dec_sol, view
    functions.pop("dec_sol", None)      # not part of the M0 fact surface
    go_fields = _go_field_offsets(cc["decoders"]["getters"])
    functions["enc_go_v0"] = _go_encoder(cc["encoders"][GO_ENC_V0], offsets, go_fields,
                                         fields, debt)
    functions["enc_go_v1"] = _go_encoder(cc["encoders"][GO_ENC_V1], offsets, go_fields,
                                         fields, debt)
    functions["ok_go"] = {
        "kind": "predicate", "from": "Bytes", "to": "Bool", "lang": "go",
        "source": [{"file": cc["predicates"][GO_PRED]["file"],
                    "fn": GO_PRED,
                    "line": cc["predicates"][GO_PRED]["line"]}],
        "rules": cc["predicates"][GO_PRED]["rules"],
    }
    functions["dec_go"] = _go_decoder(cc["decoders"]["getters"], fields, vmax, debt)
    # deterministic key order matching the hand facts' convention
    order = ["enc_sol", "enc_go_v0", "enc_go_v1", "ok_sol", "ok_go", "dec_go", "view"]
    functions = {k: functions[k] for k in order if k in functions}

    doc = {
        "facts_version": "holon-facts/0.1",
        "target": {"repo": "morph-l2/morph", "commit": _target_commit(morph),
                   "scope": "batch header codecs + _loadBatchHeader dispatch (assembled)"},
        "extraction": {"method": "holon.assemble.header (S2 solc IR + S3 gossa)",
                       "solc": s2doc["extraction"]["tool"],
                       "driver_sha256": s2doc["extraction"]["driver"]["sha256"],
                       "ir_sha256": s2doc["extraction"]["ir_sha256"]},
        "types": s2doc["types"],
        "functions": functions,
    }
    coverage = {
        "assembler": "holon/assemble/header.py",
        "target_commit": doc["target"]["commit"],
        "consumed_keys": CONSUMED,
        "omitted_descriptive": ["types.Header.fields[].sol", "types.Header.fields[].go",
                                "functions.*.meaning", "functions.*.preconditions",
                                "assumptions (not consumed by the M0 pipeline)"],
        "debt": sorted(debt, key=lambda d: (d["element"], d["kind"])),
    }
    return doc, coverage


def write_docs(doc: dict, coverage: dict, out: Path, cov_out: Path | None = None) -> None:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n")
    if cov_out is not None:
        cov_out = Path(cov_out)
        cov_out.parent.mkdir(parents=True, exist_ok=True)
        cov_out.write_text(json.dumps(coverage, indent=2, sort_keys=False) + "\n")


def facts_sha256(doc: dict) -> str:
    return hashlib.sha256((json.dumps(doc, indent=2, sort_keys=False) + "\n").encode()).hexdigest()
