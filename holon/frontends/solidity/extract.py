"""Extraction pipeline for the Solidity frontend (M2 unit S1).

  solc AST -> Translator -> facts JSON + coverage JSON.

Deterministic: fixed emission order, sorted debt items, no timestamps.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import astload
from .translate import Translator, Carrier, canon
from .sexpr import AND, OR, NOT, simplify, normalize

REPO = Path(__file__).resolve().parents[3]
SPEC_PATH = Path(__file__).parent / "specs" / "morph_rollup.spec.json"

ENTRY_FIELDS = ["ver", "tot", "n", "hb", "prev", "post", "lbn", "csr", "bvh", "tag", "bdo", "bdf", "bdn", "bds"]


def load_spec(path=None):
    return json.loads(Path(path or SPEC_PATH).read_text())


def scaffold_defs(spec):
    """Generate the window/shadow accessor defs from the storage families."""
    defs = {}
    defs["lci"] = {"params": [["lfi", "Nat"], ["win", "List<Entry>"]], "type": "Nat",
                   "body": ["-", ["+", "lfi", ["call", "len", "win"]], 1], "doc": "lastCommittedBatchIndex"}
    defs["in_win"] = {"params": [["lfi", "Nat"], ["win", "List<Entry>"], ["idx", "Nat"]], "type": "Bool",
                      "body": ["&&", [">=", "idx", "lfi"], ["<=", "idx", ["call", "lci", "lfi", "win"]]]}
    defs["w"] = {"params": [["lfi", "Nat"], ["win", "List<Entry>"], ["idx", "Nat"]], "type": "Entry",
                 "body": ["?", ["call", "in_win", "lfi", "win", "idx"], ["call", "win_at", "win", ["-", "idx", "lfi"]], ["call", "empty_entry"]],
                 "doc": "storage of batch idx; zero outside LFI..LCI (deleted below LFI; callers only read above LCI through bvh_at/tag_at)"}
    defs["bvh_at"] = {"params": [["lfi", "Nat"], ["win", "List<Entry>"], ["s_bvh", "List<Nat>"], ["idx", "Nat"]], "type": "Nat",
                      "body": ["?", ["<", "idx", "lfi"], 0, ["?", ["<=", "idx", ["call", "lci", "lfi", "win"]], ["get", ["call", "w", "lfi", "win", "idx"], "bvh"], ["call", "nth", "s_bvh", ["-", ["-", "idx", ["call", "lci", "lfi", "win"]], 1]]]],
                      "doc": "batchBlobVersionedHashes[idx], including residues above LCI"}
    defs["tag_at"] = {"params": [["lfi", "Nat"], ["win", "List<Entry>"], ["s_tag", "List<Nat>"], ["idx", "Nat"]], "type": "Nat",
                      "body": ["?", ["<", "idx", "lfi"], 0, ["?", ["<=", "idx", ["call", "lci", "lfi", "win"]], ["get", ["call", "w", "lfi", "win", "idx"], "tag"], ["call", "nth", "s_tag", ["-", ["-", "idx", ["call", "lci", "lfi", "win"]], 1]]]],
                      "ghost": True}
    return defs


def build_env(a):
    env = dict(a.get("inputs_extra", {}))
    for m, v in a.get("members", {}).items():
        if isinstance(v, dict):
            if "carrier" in v:
                env[m] = ("carrier_tok", v["carrier"])
            elif "hash_of" in v:
                env[m] = ("hash_tok", v["hash_of"])
            elif "debt" in v:
                env[m] = ("debt_tok", v["debt"])
        else:
            env[m] = v
    return env


def translate_action(world, spec, a, reasons, call_guards):
    """Translate one action; returns action dict."""
    if "declared" in a:
        d = a["declared"]
        return {"name": a["name"], "principal": d.get("principal", a.get("principal")), "src": d.get("src", a.get("src")), "inputs": a.get("inputs", d.get("inputs")), "guards": d.get("guards", []), "effects": d.get("effects", {})}
    contract, fname = a.get("fn") or a["synth_fn"]
    tr = Translator(world, spec)
    tr.reasons = reasons
    tr.call_guards = call_guards
    tr.action_spec = a
    tr.def_calls = {}
    tr.conds = []
    tr.input_map = build_env(a)
    tr.input_names = set()
    tr.local_names = a.get("local_names", {})
    tr.pending_notes = []
    tr.pending = []
    tr.cur_fn = (contract, fname)
    tr.established = []
    tr.subst = {}
    tr.expr_let_table = {}
    for el in a.get("expr_lets", []):
        key = canon(el["expr"])
        tr.expr_let_table[key] = (el["name"] if isinstance(el["name"], list) else [el["name"]])
    tr.new_idx = a.get("entry_at")

    fn = tr.find_fn(contract, fname)
    if fn is None:
        raise RuntimeError(f"{contract}.{fname} not found")
    tr.blob_indices = tr.scan_blobs(fn)
    tr.run_modifiers(fn)
    for st in fn.get("body", {}).get("statements", []):
        tr.S(st)
    tr._drain_pending()
    guards = tr.guards
    writes = tr.writes
    effects = compose_effects(tr, writes)
    out = {"name": a["name"], "principal": a.get("principal") or principal_of(fn, spec),
           "src": a["src"], "inputs": a["inputs"], "guards": guards, "effects": effects}
    if a.get("note"):
        out["note"] = a["note"]
    if a.get("effects_src"):
        out["effects_src"] = a["effects_src"]
    # fold reasons
    for s, i in tr.reasons.items():
        reasons.setdefault(s, i)
    tr.all_debt = getattr(tr, "debt", [])
    return out, tr


def principal_of(fn, spec):
    for mi in fn.get("modifiers", []):
        nm = mi.get("modifierName", {}).get("name", "")
        if nm in spec.get("principal_map", {}):
            return spec["principal_map"][nm]
    return "anyone"


def _merge_ch(merge_state, k, conds, rec, tr):
    """Merge a ch_rec write into pending set_ch state.

    merge_state[k] = {"nm": base-name, "fields": {f: e}, "replace": mk-record}.
    """
    st = merge_state
    st.setdefault("nm", "ch")
    st.setdefault("fields", {})
    st.setdefault("replace", None)
    if isinstance(rec, list) and rec[0] == "mk":
        st["replace"] = rec
        return
    if isinstance(rec, list) and rec[0] == "with":
        st["nm"] = rec[2] if isinstance(rec[2], str) else "ch"
        for m, v in rec[3].items():
            if conds:
                ctor = next((c for c in tr.spec["struct_ctors"].values() if c.get("record") == rec[1]), {})
                dv = ctor.get("fresh_defaults", {}).get(m)
                v = simplify(["?", AND(*conds), v, dv if dv is not None else ["get", st["nm"], m]])
            st["fields"][m] = v
        return
    st["replace"] = rec


def compose_effects(tr, writes):
    """Fold collected writes into final effects dict (emission order)."""
    eff = {}

    def cur(f):
        return eff.get(f, f)

    merges = {}
    merge_order = []
    for w in writes:
        kind = w[0]
        if kind == "state":
            _, f, conds, v = w
            e = v
            if conds:
                e = simplify(["?", AND(*conds), v, cur(f)])
            eff[f] = simplify(e) if isinstance(e, list) else e
        elif kind == "ch_rec":
            _, f, k, conds, rec = w
            key = canon(k)
            if key not in merges:
                merge_order.append((key, k))
            _merge_ch(merges.setdefault(key, {}), k, conds, rec, tr)
    for key, k in merge_order:
        st = merges[key]
        if st.get("replace") is not None:
            rec = st["replace"]
            if st["fields"]:
                rec = ["with", tr.spec["struct_ctors"][rec[1]]["record"], rec[2], {**rec[3], **st["fields"]}] if rec[0] == "mk" else rec
            eff["chs"] = ["call", "set_ch", "chs", k, rec]
        else:
            eff["chs"] = ["call", "set_ch", "chs", k, ["with", "Ch", st.get("nm", "ch"), st["fields"]]]
    # materialize a constructed window entry
    a = tr.action_spec
    if a.get("entry_template") and tr.new_entry is not None:
        entry = dict(a["entry_template"])
        entry.update(tr.new_entry)
        entry.update(a.get("entry_overrides", {}))
        for f in ENTRY_FIELDS:
            if f not in (tr.new_entry or {}) and f not in a.get("entry_overrides", {}):
                tr.debt.append({"element": f"entry.{f} ({a['name']})", "kind": "entry_field_default",
                                "reason": "written inside abstracted internals (_storeBatchData/_commitBatchWithBatchData); spec-declared"})
        eff["win"] = ["call", "snoc", "win", ["mk", "Entry", {f: entry[f] for f in ENTRY_FIELDS if f in entry}]]
        for s in ("s_csr", "s_bd", "s_bvh", "s_tag"):
            eff[s] = ["call", "tail", s]
    return eff


def extract(world, spec, out_path=None, cov_path=None):
    reasons = {}
    call_guards = {}

    # ---- defs: scaffold + extracted-from-source helpers
    defs = scaffold_defs(spec)
    for dname, d in spec["defs_from"].items():
        cname, fname = d["fn"]
        tr = Translator(world, spec)
        tr.reasons = {}
        tr.call_guards = {}
        tr.action_spec = {}
        tr.def_calls = {}
        tr.conds = []
        fn0 = tr.find_fn(cname, fname)
        sol_names = [p["name"] for p in fn0.get("parameters", {}).get("parameters", [])] if fn0 else []
        amap = d.get("arg_map", {})
        tr.input_map = {sol_names[i]: p for p, i in amap.items() if i < len(sol_names)}
        for p, _t in d["params"]:
            tr.input_map.setdefault(p, p)
        tr.input_names = set(tr.input_map)
        tr.local_names = {}
        tr.expr_let_table = {}
        tr.pending_notes = []
        tr.pending = []
        tr.cur_fn = (cname, fname)
        tr.established = []
        tr.subst = {}
        tr.new_idx = None
        fn = tr.find_fn(cname, fname)
        tr.blob_indices = tr.scan_blobs(fn)
        # defs: translate body, collect ret + call-site guards
        guards_before = len(tr.guards)
        for st in fn.get("body", {}).get("statements", []):
            tr.S(st)
        body = None
        if tr.ret:
            body = tr.ret[-1][1]
            for conds, val in reversed(tr.ret[:-1]):
                body = simplify(["?", AND(*conds), val, body])
        # guards emitted during def translation belong to call sites (params substituted there)
        call_guards[(cname, fname)] = {
            "params": [p[0] for p in d["params"]],
            "guards": [
                {"expr": g["require"], "reason": [k for k, v in tr.reasons.items() if v == g["reason"]][0] if tr.reasons else g["reason"], "src": g["src"], **({"site": g["site"]} if "site" in g else {})}
                for g in tr.guards[guards_before:] if "require" in g]}
        defs[dname] = {"params": d["params"], "type": d["type"], "body": body, "src": None}
        tr._drain_pending()

    # ---- actions
    actions = []
    all_debt = list(spec.get("coverage_items", []))
    seen_debt = {(i["element"], i["kind"]) for i in all_debt}
    for a in spec["actions"]:
        if "declared" in a:
            d = a["declared"]
            actions.append({"name": a["name"], "principal": d.get("principal"), "src": d.get("src"), "inputs": d.get("inputs", []), "guards": d.get("guards", []), "effects": d.get("effects", {})})
            continue
        out, tr = translate_action(world, spec, a, reasons, call_guards)
        actions.append(out)
        for it in tr.all_debt:
            k = (it["element"], it["kind"])
            if k not in seen_debt:
                seen_debt.add(k)
                all_debt.append(it)

    facts = {
        "facts_version": spec["facts_version"],
        "target": spec["target"],
        "extraction": spec["extraction"],
        "abstractions": spec["abstractions"],
        "params": spec["params"],
        "constants_doc": spec["constants_doc"],
        "types": spec["types"],
        "state": spec["state"],
        "ghost_state": spec["ghost_state"],
        "shadow": spec["shadow"],
        "initial": spec["initial"],
        "principals": spec["principals"],
        "reasons": {str(i): s for s, i in reasons.items()},
        "defs": defs,
        "actions": actions,
        "migrations": spec["migrations_declared"],
        "observers": spec["observers"],
        "disch": spec["disch"],
        "consumers": spec["consumers"],
        "coverage": spec["coverage"],
    }
    cov = {"frontend": spec["frontend_name"], "target_commit": spec["target"]["commit"],
           "items": sorted(all_debt, key=lambda i: i["element"])}

    if out_path:
        Path(out_path).write_text(json.dumps(facts, indent=1))
    if cov_path:
        Path(cov_path).write_text(json.dumps(cov, indent=1))
    return facts, cov


def main(argv=None):
    import sys
    spec = load_spec()
    morph = os.environ.get(spec["morph_root_env"], spec["morph_root_default"])
    morph = os.path.expanduser(morph)
    world = astload.run_solc(spec, morph)
    out = REPO / spec["output"]
    cov = REPO / spec["coverage_out"]
    out.parent.mkdir(parents=True, exist_ok=True)
    cov.parent.mkdir(parents=True, exist_ok=True)
    facts, coverage = extract(world, spec, out, cov)
    print(f"wrote {out} ({out.stat().st_size} bytes), {cov} ({len(coverage['items'])} debt items)")


if __name__ == "__main__":
    main()
