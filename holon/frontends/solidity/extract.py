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


def init_tr(world, spec, a, reasons, call_guards):
    contract, fname = a.get("fn") or a["synth_fn"]
    tr = Translator(world, spec)
    tr.reasons = reasons
    tr.call_guards = call_guards
    tr.action_spec = a
    tr.fact_inputs = {n for n, _ in a.get("inputs", [])}
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
    tr.let_names = {k: list(v) for k, v in a.get("let_names", {}).items()}
    tr.hoist_used = {}
    tr.hoist_bound = {}
    tr.hoist_policy = dict(spec.get("hoist_policy", {}))
    tr.in_require_arg = 0
    tr.self_idx_alias = None
    tr.let_values = {}
    tr.guard_prov = []
    tr.write_prov = []
    tr.entry_prov = {}
    tr.new_idx = a.get("entry_at")
    return tr, contract, fname


def translate_action(world, spec, a, reasons, call_guards):
    """Translate one action; returns (action dict, translator)."""
    tr, contract, fname = init_tr(world, spec, a, reasons, call_guards)
    fn = tr.find_fn(contract, fname, a.get("fn_arity"))
    if fn is None:
        raise RuntimeError(f"{contract}.{fname} not found")
    tr.blob_indices = tr.scan_blobs(tr.world.units[fn["__file"]].node)
    tr.run_modifiers(fn)
    for st in fn.get("body", {}).get("statements", []):
        tr.S(st)
    tr._drain_pending()
    guards = tr.guards
    writes = tr.writes
    effects, effects_prov = compose_effects(tr, writes)
    inputs = list(a["inputs"])
    inputs += [[n, "Nat"] if isinstance(n, str) else list(n)
               for n in getattr(tr, "oracle_inputs", [])
               if (n if isinstance(n, str) else n[0]) not in {i[0] for i in inputs}]
    out = {"name": a["name"], "principal": a.get("principal") or principal_of(fn, spec),
           "src": a["src"], "inputs": inputs, "guards": guards, "effects": effects}
    if a.get("note"):
        out["note"] = a["note"]
    if a.get("effects_src"):
        out["effects_src"] = a["effects_src"]
    # fold reasons
    for s, i in tr.reasons.items():
        reasons.setdefault(s, i)
    tr.all_debt = getattr(tr, "debt", [])
    tr.effects_prov = effects_prov
    return out, tr


def principal_of(fn, spec):
    for mi in fn.get("modifiers", []):
        nm = mi.get("modifierName", {}).get("name", "")
        if nm in spec.get("principal_map", {}):
            return spec["principal_map"][nm]
    return "anyone"


def _merge_ch(merge_state, k, conds, rec, tr):
    """Merge a record write (ch_rec) into pending set_ch/set_rec state.

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
        st["rec"] = rec[1]
        for m, v in rec[3].items():
            if conds:
                ctor = next((c for c in tr.spec["struct_ctors"].values() if c.get("record") == rec[1]), {})
                dv = ctor.get("fresh_defaults", {}).get(m)
                v = simplify(["?", AND(*conds), v, dv if dv is not None else ["get", st["nm"], m]])
            st["fields"][m] = v
        return
    st["replace"] = rec


def compose_effects(tr, writes):
    """Fold collected writes into final effects dict; also reports per-field provenance."""
    eff = {}
    eprov = {}          # field -> 'ast'|'spec'
    field_prov = {}     # field -> [provs of contributing writes]

    def cur(f):
        return eff.get(f, f)

    merges = {}
    merge_order = []
    for w, wp in zip(writes, tr.write_prov + ["ast"] * (len(writes) - len(tr.write_prov))):
        kind = w[0]
        if kind == "state":
            _, f, conds, v = w
            field_prov.setdefault(f, []).append(wp)
            e = v
            if conds:
                e = simplify(["?", AND(*conds), v, cur(f)])
            eff[f] = simplify(e) if isinstance(e, list) else e
        elif kind == "ch_rec":
            _, f, k, conds, rec = w
            tgt = f["field"]
            field_prov.setdefault(tgt, []).append(wp)
            key = (tgt, canon(k))
            if key not in merges:
                merge_order.append((key, tgt, k, f.get("record", "Ch")))
            _merge_ch(merges.setdefault(key, {}), k, conds, rec, tr)
    for key, tgt, k, rname in merge_order:
        st = merges[key]
        op = "set_ch" if rname == "Ch" else "set_rec"
        if st.get("replace") is not None:
            rec = st["replace"]
            if st["fields"]:
                rec = ["with", tr.spec["struct_ctors"][rec[1]]["record"], rec[2], {**rec[3], **st["fields"]}] if rec[0] == "mk" else rec
            eff[tgt] = ["call", op, tgt, k, rec]
        else:
            eff[tgt] = ["call", op, tgt, k, ["with", rname, st.get("nm", "ch"), st["fields"]]]
    # materialize a constructed window entry
    a = tr.action_spec
    if tr.new_entry is not None:
        entry = dict(tr.new_entry)
        for f in ENTRY_FIELDS:
            if f not in entry:
                entry[f] = 0
                tr.entry_prov[f] = "spec"
                tr.debt.append({"element": f"entry.{f} ({a['name']})", "kind": "entry_field_default",
                                "reason": "no AST write reached this Entry field; emitted as 0"})
        field_prov.setdefault("win", []).append(
            "spec" if any(v == "spec" for v in tr.entry_prov.values()) else "ast")
        eff["win"] = ["call", "snoc", "win", ["mk", "Entry", {f: entry[f] for f in ENTRY_FIELDS}]]
        for s in ("s_csr", "s_bd", "s_bvh", "s_tag"):
            eff[s] = ["call", "tail", s]
            field_prov.setdefault(s, []).append("ast")
    for f in eff:
        ps = field_prov.get(f, [])
        eprov[f] = "spec" if "spec" in ps else "ast"
    return eff, eprov


def extract(world, spec, out_path=None, cov_path=None):
    reasons = {}
    call_guards = {}

    # ---- defs: scaffold + extracted-from-source helpers
    defs = scaffold_defs(spec)
    defs = {k: v for k, v in defs.items() if k in spec.get("defs_scaffold", [])}
    defs_prov = {k: "spec" for k in defs}
    def_debt = []
    for dname, d in spec.get("defs_from", {}).items():
        cname, fname = d["fn"]
        tr = Translator(world, spec)
        tr.reasons = {}
        tr.call_guards = {}
        tr.action_spec = {}
        tr.def_calls = {}
        tr.conds = []
        tr.let_names = {k: list(v) for k, v in d.get("let_names", {}).items()}
        tr.hoist_used = {}
        tr.hoist_bound = {}
        tr.hoist_policy = {}
        tr.in_require_arg = 0
        tr.self_idx_alias = None
        tr.let_values = {}
        tr.guard_prov = []
        tr.write_prov = []
        tr.entry_prov = {}
        fn0 = tr.find_fn(cname, fname)
        sol_names = [p["name"] for p in fn0.get("parameters", {}).get("parameters", [])] if fn0 else []
        amap = d.get("arg_map", {})
        tr.input_map = {sol_names[i]: p for p, i in amap.items() if i < len(sol_names)}
        for p, _t in d["params"]:
            tr.input_map.setdefault(p, p)
        tr.input_names = set(tr.input_map)
        # Def params are fact-level names (substituted at call sites), so they
        # are bound names for _unbound_names during body translation. Without
        # this every let/guard referencing a param is silently dropped.
        tr.fact_inputs = {p[0] for p in d["params"]}
        tr.local_names = {}
        tr.pending_notes = []
        tr.pending = []
        tr.cur_fn = (cname, fname)
        tr.established = []
        tr.subst = {}
        tr.new_idx = None
        fn = tr.find_fn(cname, fname)
        tr.blob_indices = tr.scan_blobs(tr.world.units[fn["__file"]].node)
        for rp in fn0.get("returnParameters", {}).get("parameters", []):
            tr.env[rp["name"]] = ("unbound", rp["name"])
        # defs: translate body, collect ret + call-site guards
        guards_before = len(tr.guards)
        for st in fn.get("body", {}).get("statements", []):
            tr.S(st)
        tr._drain_pending()
        body = None
        if tr.ret:
            body = tr.ret[-1][1]
            for conds, val in reversed(tr.ret[:-1]):
                body = simplify(["?", AND(*conds), val, body])
        if body is None:
            # named return variables: functions that assign their return var instead
            # of using `return` (e.g. _computeBlobVersionedHash in asm blocks)
            rnames = [p_["name"] for p_ in fn0.get("returnParameters", {}).get("parameters", [])]
            if len(rnames) == 1 and rnames[0] in tr.env:
                v = tr.env[rnames[0]]
                if isinstance(v, list):
                    v = tr.rewrite_lets(v)
                body = v if not isinstance(v, tuple) else None
        if d.get("body_forced") and d.get("body") is not None:
            # spec-declared body wins even when an AST derivation exists but is
            # partial (e.g. an unsupported loop leaves a shadow-local unbound).
            body = d["body"]
            defs_prov[dname] = "spec"
            def_debt.append({"element": f"defs.{dname}.body", "kind": "spec_bound",
                             "reason": "AST derivation partial or unsupported; spec-declared explicit value"})
        elif body is None and d.get("body") is not None:
            body = d["body"]
            defs_prov[dname] = "spec"
            def_debt.append({"element": f"defs.{dname}.body", "kind": "spec_bound",
                             "reason": "no faithful AST derivation (named return / abstracted internals); spec-declared explicit value"})
        else:
            defs_prov.setdefault(dname, "ast")
        # guards emitted during def translation belong to call sites (params substituted there).
        # Let names bound inside the def are inlined so the guard is closed over the
        # def's params only.
        def _inline_lets(e):
            if isinstance(e, str) and e in tr.let_values:
                return _inline_lets(tr.let_values[e])
            if isinstance(e, list):
                return [_inline_lets(x) for x in e]
            return e
        call_guards[(cname, fname)] = {
            "params": [p[0] for p in d["params"]],
            "guards": [
                {"expr": _inline_lets(g["require"]), "reason": [k for k, v in tr.reasons.items() if v == g["reason"]][0] if tr.reasons else g["reason"], "src": g["src"], **({"site": g["site"]} if "site" in g else {})}
                for g in tr.guards[guards_before:] if "require" in g]}
        defs[dname] = {"params": d["params"], "type": d["type"], "body": body, "src": None}

    # ---- actions
    actions = []
    prov = {}
    all_debt = list(spec.get("coverage_items", [])) + def_debt
    seen_debt = {(i["element"], i["kind"]) for i in all_debt}

    def add_debt_item(element, kind, reason, src=None):
        k = (element, kind)
        if k in seen_debt:
            return
        seen_debt.add(k)
        it = {"element": element, "kind": kind, "reason": reason}
        if src:
            it["src"] = src
        all_debt.append(it)

    # top-level sections copied from the spec -> labelled spec_bound
    for sec in ("params", "constants_doc", "principals", "abstractions", "types",
                "state", "ghost_state", "shadow", "initial"):
        prov[sec] = "spec"
        add_debt_item(f"facts.{sec}", "spec_bound",
                      "model vocabulary declared in the spec, not derivable from the AST",
                      src=f"spec:{sec}")
    for sec in ("observers", "disch", "consumers", "coverage"):
        prov[sec] = "spec"
        add_debt_item(f"facts.{sec}", "spec_bound",
                      "cross-cutting model section has no source counterpart", src=f"spec:{sec}")
    for o in spec.get("observers", {}):
        add_debt_item(f"observer:{o}", "spec_bound",
                      "spec-declared observer; a named read over model state, no source counterpart",
                      src="spec:observers")
    for h in spec.get("handlers", {}):
        add_debt_item(f"handler:{h}", "spec_bound",
                      "abstracted call handled by spec rule (emitted guards/writes are spec-provided)")
    for st in spec.get("sites", []):
        add_debt_item(f"site:{st.get('site')}", "spec_bound",
                      "evaluator site label declared in spec")
    for gname in ("ghost_tag",):
        for a in spec["actions"]:
            if gname in a:
                add_debt_item(f"action:{a['name']}:{gname}", "spec_bound",
                              "ghost tag twin has no source expression")
    for a in spec["actions"]:
        if "declared" in a:
            d = a["declared"]
            actions.append({"name": a["name"], "principal": d.get("principal"), "src": d.get("src"), "inputs": d.get("inputs", []), "guards": d.get("guards", []), "effects": d.get("effects", {})})
            prov[f"actions.{a['name']}"] = "spec"
            add_debt_item(f"action:{a['name']}", "spec_bound", "declared action; no AST source")
            continue
        out, tr = translate_action(world, spec, a, reasons, call_guards)
        actions.append(out)
        nm = a["name"]
        gspec = any(p == "spec" for p in tr.guard_prov)
        espec = any(p == "spec" for p in tr.effects_prov.values())
        prov[f"actions.{nm}.guards"] = "spec" if gspec else "ast"
        prov[f"actions.{nm}.effects"] = "spec" if espec else "ast"
        prov[f"actions.{nm}.entry"] = "spec" if "spec" in tr.entry_prov.values() else ("ast" if tr.entry_prov else "ast")
        for i, p_ in enumerate(tr.guard_prov):
            if p_ == "spec":
                g = tr.guards[i]
                el = f"action:{nm}.guards[{i}]"
                add_debt_item(el, "spec_bound", "spec-provided guard (handler, ghost or oracle rule), not AST-derived", src=g.get("src"))
        for f, p_ in tr.effects_prov.items():
            if p_ == "spec":
                add_debt_item(f"action:{nm}.effects.{f}", "spec_bound", "spec-provided effect (handler or oracle rule), not AST-derived")
        for it in tr.all_debt:
            k = (it["element"], it["kind"])
            if k not in seen_debt:
                seen_debt.add(k)
                all_debt.append(it)

    prov["facts_version"] = "spec"
    prov["target"] = "spec"
    prov["extraction"] = "spec"
    prov["reasons"] = "ast"
    prov["defs"] = "spec" if "spec" in defs_prov.values() else "ast"
    for dn, dp in defs_prov.items():
        prov[f"defs.{dn}"] = dp
    prov["migrations"] = "spec"
    add_debt_item("facts.migrations", "spec_bound", "declared environment actions; no source", src="spec:migrations_declared")

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
        "migrations": spec.get("migrations_declared", {}),
        "observers": spec["observers"],
        "disch": spec["disch"],
        "consumers": spec["consumers"],
        "coverage": spec["coverage"],
        "provenance": prov,
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
    argv = sys.argv[1:] if argv is None else argv
    spec_path = argv[0] if argv else None
    spec = load_spec(spec_path)
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
