"""Lift a `holon-extracted/go-machine/0.1` document (holon/frontends/go/own.py)
into the `holon-facts/0.2` machine-facts format `holon.mpipeline` consumes.

    python -m holon.frontends.go lift <go-machine.json> -o <facts.json>
        [--coverage <coverage.json>]

Deterministic and injective identifier sanitisation: names Bend already
accepts (incl. CamelCase) are kept verbatim; anything else is mapped into
[a-z_][a-z0-9_]* (' -> _p, other illegal chars -> _, folded). An action
input named like a state field is renamed in_<name>; where the same
identifier string means both in a term, the slice position of
go_append_heap/go_append_slice resolves to the field and the payload
position to the input -- source semantics (s = append(s, xs)). The rename
table is recorded under extraction.renames; a collision is a hard error,
never a silent merge. Anything the lifter cannot express is a
coverage.debt item of kind unlifted_<what>, never dropped silently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

LEGAL = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")
STRICT = re.compile(r"[a-z_][a-z0-9_]*")
BEND_KEYWORDS = {"match", "case", "def", "type", "law", "for", "exs", "import", "as", "do", "return", "is", "where"}
# top-level names the generated machine model defines; a machine identifier
# landing on one would shadow it in the emitted Bend
GEN_RESERVED = {"s0", "run", "step", "last_ok", "log_of"}
RESERVED = BEND_KEYWORDS | GEN_RESERVED

APPEND_CALLS = {"go_append_heap", "go_append_slice"}


class LiftError(Exception):
    pass


def _is_legal(name: str) -> bool:
    return bool(LEGAL.fullmatch(name)) and name not in RESERVED


def sanitize(name: str) -> str:
    """Deterministic map into [a-z_][a-z0-9_]* for names Bend rejects."""
    out = []
    for c in name:
        if c.isalnum() or c == "_":
            out.append(c.lower())
        elif c == "'":
            out.append("_p")
        else:
            out.append("_")
    n = re.sub(r"_+", "_", "".join(out)).strip("_") or "x"
    if not STRICT.match(n):
        n = "x_" + n
    if n in RESERVED:
        n += "_"
    return n


class Renamer:
    """Global old -> new table over every identifier in the machine."""

    def __init__(self):
        self.table: dict[str, str] = {}
        self.owners: dict[str, str] = {}

    def _claim(self, old: str, new: str) -> str:
        if new in self.owners and self.owners[new] != old:
            raise LiftError(f"sanitiser collision: {old!r} and {self.owners[new]!r} both map to {new!r}")
        self.table[old] = new
        self.owners[new] = old
        return new

    def map(self, name: str) -> str:
        if name in self.table:
            return self.table[name]
        new = name if _is_legal(name) else sanitize(name)
        return self._claim(name, new)

    def map_input(self, name: str, is_field: bool) -> str:
        """An action input. If it collides with a state field name it is
        renamed in_<name>; the collision maps under a distinct table key so
        the field name itself stays usable."""
        if not is_field:
            return self.map(name)
        key = f"{name}@input"
        if key in self.table:
            return self.table[key]
        cand = "in_" + name
        new = cand if _is_legal(cand) else sanitize(cand)
        if new in self.owners and self.owners[new] != key:
            raise LiftError(f"sanitiser collision: {key!r} and {self.owners[new]!r} both map to {new!r}")
        self.table[key] = new
        self.owners[new] = key
        return new

    def rewrites(self) -> dict:
        return {k: v for k, v in sorted(self.table.items()) if k != v}


def _rewrite(node, table: dict, amb: dict, where: str) -> None:
    """Rename identifier leaves inside a guards/effects/observer tree, in
    place. `amb` maps a string that is both a state field and an input to
    (field_target, input_target): inside a go_append_* call, the slice
    argument (index 3) resolves to the field and the payload argument
    (index 4) to the input; an ambiguous leaf anywhere else is a hard error."""
    if isinstance(node, list):
        is_app = len(node) >= 2 and node[0] == "call" and node[1] in APPEND_CALLS
        for i, x in enumerate(node):
            if isinstance(x, str):
                if x in amb:
                    f_n, i_n = amb[x]
                    if is_app and i == 3:
                        node[i] = f_n
                    elif is_app and i == 4:
                        node[i] = i_n
                    else:
                        raise LiftError(f"ambiguous identifier {x!r} outside a go_append call at {where}")
                elif x in table:
                    node[i] = table[x]
            else:
                _rewrite(x, table, amb, where)
    elif isinstance(node, dict):
        for x in node.values():
            _rewrite(x, table, amb, where)


def lift(gm: dict, src: str) -> tuple[dict, list[dict]]:
    """go-machine/0.1 -> (facts dict, coverage items)."""
    if gm.get("format") != "holon-extracted/go-machine/0.1":
        raise LiftError(f"expected holon-extracted/go-machine/0.1, got {gm.get('format')!r}")
    machines = gm.get("machines") or []
    if len(machines) != 1:
        raise LiftError(f"expected exactly one machine, got {len(machines)}")
    m = machines[0]
    debt: list[dict] = []
    R = Renamer()

    state_names = [s[0] for s in m["state"]]
    field_new = {n: R.map(n) for n in state_names}
    types = {}
    for tn, t in m.get("types", {}).items():
        ntn = R.map(tn)
        types[ntn] = {"doc": t.get("doc", ""), "fields": [[R.map(fn), ft] for fn, ft in t["fields"]]}
    # type names/fields share the value namespace with plain identifiers here
    type_names = set(types)

    actions = []
    for a in m["actions"]:
        inputs = []
        amb = {}
        for n, t in a.get("inputs", []):
            clash = n in state_names
            inputs.append([R.map_input(n, clash), t])
            if clash:
                amb[n] = (field_new[n], inputs[-1][0])
        guards = json.loads(json.dumps(a.get("guards", [])))
        for g in guards:
            if "let" in g:
                g["let"] = R.map(g["let"])
        for g in guards:
            for k in ("expr", "require"):
                if k in g:
                    _rewrite(g[k], R.table, amb, f"action:{a['name']}")
        effects = {}
        for k, v in (a.get("effects") or {}).items():
            vv = json.loads(json.dumps(v))
            holder = [vv]
            _rewrite(holder, R.table, amb, f"action:{a['name']}.effects")
            effects[field_new.get(k, R.map(k))] = holder[0]
        actions.append({"name": R.map(a["name"]), "function": a.get("function"),
                        "src": a.get("src", a.get("function")), "inputs": inputs,
                        "guards": guards, "effects": effects})
        for d in a.get("dropped", []):
            debt.append({"element": f"action:{a['name']}.dropped:{d.get('field')}", "kind": "unlifted_dropped",
                         "reason": d.get("reason", ""), "src": f"{d.get('site', {}).get('file')}:{d.get('site', {}).get('line')}"})
        for o in a.get("other_ops", []):
            debt.append({"element": f"action:{a['name']}.other_ops:{o.get('field')}", "kind": "unlifted_other_ops",
                         "reason": f"{o.get('op')}: {o.get('src', {}).get('expr', '')}",
                         "src": f"{o.get('site', {}).get('file')}:{o.get('site', {}).get('line')}"})
        if a.get("complete") is not True:
            debt.append({"element": f"action:{a['name']}.complete", "kind": "unlifted_incomplete",
                         "reason": "the go-machine marks this action's extraction incomplete"})

    observers = {}
    for on, o in (m.get("observers") or {}).items():
        body = json.loads(json.dumps(o.get("body")))
        holder = [body]
        _rewrite(holder, R.table, {}, f"observer:{on}")
        observers[R.map(on)] = {"params": [[R.map(n), t] for n, t in o.get("params", [])],
                                "type": o.get("type", "Nat"), "body": holder[0], "doc": o.get("doc", "")}

    initial = {}
    for k, v in m.get("initial", {}).items():
        initial[k if k == "doc" else field_new.get(k, R.map(k))] = v

    cov = gm.get("coverage", {})
    for d in m.get("coverage_debt", []):
        site = d.get("site", {})
        debt.append({"element": f"machine:{m.get('type')}:{d.get('field') or 'method'}", "kind": "unlifted_coverage_debt",
                     "reason": d.get("reason", ""), "src": f"{site.get('file')}:{site.get('line')}",
                     **({"in_loop": d["in_loop"]} if "in_loop" in d else {})})

    facts = {
        "facts_version": "holon-facts/0.2",
        "target": gm.get("target", {}),
        "extraction": {"method": f"lifted from {src} sha256 {_sha(src)} by holon.frontends.go.lift",
                       "renames": R.rewrites()},
        "abstractions": [],
        "params": {},
        "types": types,
        "state": [[field_new[n], s[1], s[2] if len(s) > 2 else ""] for s in m["state"] for n in [s[0]]],
        "ghost_state": [field_new[n] for n in m.get("ghost_state", [])],
        "shadow": {},
        "initial": initial,
        "principals": {},
        "reasons": {},
        "defs": {},
        "actions": actions,
        "migrations": {},
        "observers": observers,
        "disch": {},
        "consumers": {},
        "coverage": {"modelled": cov.get("modelled", []), "debt": [d["element"] for d in debt]},
        "provenance": {},
    }
    # policy: keep "batchdata" only if the go-machine carries the equivalent hint
    if gm.get("policy") == "batchdata":
        facts["policy"] = "batchdata"
    return facts, debt


def _sha(path: str) -> str:
    p = Path(path)
    if p.exists():
        return hashlib.sha256(p.read_bytes()).hexdigest()
    return "0" * 64


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon.frontends.go lift")
    ap.add_argument("src", help="go-machine/0.1 json")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--coverage", help="write coverage items json here")
    args = ap.parse_args(argv)
    gm = json.loads(Path(args.src).read_text())
    facts, debt = lift(gm, args.src)
    Path(args.out).write_text(json.dumps(facts, indent=1, sort_keys=True) + "\n")
    if args.coverage:
        cov = {"frontend": "go_lift",
               "target_commit": facts.get("target", {}).get("commit", ""),
               "items": debt}
        Path(args.coverage).write_text(json.dumps(cov, indent=1, sort_keys=True) + "\n")
    print(f"wrote {args.out}" + (f" and {args.coverage} ({len(debt)} debt items)" if args.coverage else ""))
    return 0
