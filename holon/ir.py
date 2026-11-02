"""Law IR (holon-ir/0.1, 0.2, 0.3): canonical JSON, statement hashes, loading and rendering.

The statement hash is the identity of a frozen claim (whitepaper §8.9, §9.4). Only
ir_version, law_id, rule, facts_sha256 and statement are hashed; notes and evidence
are metadata.

statement_hash is the one implementation of that identity (PV2A): every other module resolves a law's refs and hands
them in. A law's hash scheme is law.get("hash_scheme", 1), so every historical file hashes as scheme 1:
  scheme 1  0.1/0.2 over HASHED_KEYS (docs/M0_SPEC.md §3); 0.3 over HASHED_KEYS_03 plus refs; the DISCH-profile IR of a
            test milestone (holon.rules.disch_profile) over its statement alone.
  scheme 2  0.3 only: over HASHED_KEYS_03_S2 (HASHED_KEYS_03 without rule_catalog_version) plus refs, so a rule-catalog
            bump moves no statement hash; rule_catalog_version stays in the law file as an audit trail.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

IR_VERSION = "holon-ir/0.1"
IR_VERSIONS = ("holon-ir/0.1", "holon-ir/0.2", "holon-ir/0.3")
HASHED_KEYS = ("ir_version", "law_id", "rule", "facts_sha256", "statement")
# holon-ir/0.3 (I7): the statement and the content hashes of the definitions it names, never a whole
# facts bundle, so an extraction change outside a law's refs leaves its hash unchanged
HASHED_KEYS_03 = ("ir_version", "law_id", "rule", "rule_catalog_version", "statement")
# hash scheme 2 (PV2A): the 0.3 keys without rule_catalog_version, so a catalog bump adds only its own laws
HASHED_KEYS_03_S2 = ("ir_version", "law_id", "rule", "statement")
HASH_SCHEMES = (1, 2)
# a test milestone's DISCH profile laws (holon.rules.disch_profile): the statement hash is its statement's sha256
DISCH_PROFILE_IR = "holon-disch-profile/0.1"
# a milestone's hash scheme declaration (PV2A): spec/<M>/hash_scheme.json, written by `python -m holon.statement_diff
# migrate-hash --apply`; the generators stamp hash_scheme on every 0.3 law of a milestone that declares scheme 2
HASH_SCHEME_FILE = "hash_scheme.json"
# the plan-stated product laws' sidecar (BUILD_PLAN I88): holon.derivation.laws reads its path from here, so that a
# generator-closure module that needs the law set's location (holon.statement_diff's migrate-hash) never imports
# holon.derivation, which no generator closure may hold (I85's and I88's R4)
PLAN_LAWS_SIDECAR = "spec/M3/lib/derivation_laws.json"
# law files, and the result records named after them: L_* (0.1, 0.2) and, from 0.3, L3_*, L8_* etc.
# (the 0.3 schema's law_id pattern ^L[0-9]?_). Every glob over laws/<m>/ or results/<m>/ uses this one.
LAW_GLOB = "L*.json"
# binder types every IR version may use; 0.3 adds Fn<A,B>, Bytes(n), List<Nat> and record refs (a facts type)
# (I86: Args, the input of an action, its arguments as the law model's AR_<action> record holds them)
BASE_TYPES = ("State", "Trace", "Act", "Nat", "Bool", "Reach", "List<Nat>", "Word", "Env", "Args")


class IRError(ValueError):
    """A law the IR rules reject (for example a premise stating global injectivity)."""
ROOT = Path(__file__).resolve().parents[1]


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def hash_scheme(law: dict) -> int:
    """The law's statement-hash scheme: law["hash_scheme"], 1 when absent (every file written before PV2A). Scheme 2
    exists for holon-ir/0.3 only; anything else raises IRError."""
    s = law.get("hash_scheme", 1)
    if isinstance(s, bool) or s not in HASH_SCHEMES:
        raise IRError(f"{law.get('law_id')}: hash_scheme {s!r} is not one of {list(HASH_SCHEMES)}")
    if s != 1 and law.get("ir_version") != "holon-ir/0.3":
        raise IRError(f"{law.get('law_id')}: hash_scheme {s} is defined for holon-ir/0.3 laws only")
    return s


def statement_hash(law: dict, refs=None) -> str:
    """The identity of a frozen claim, the one implementation (the schemes: see the module docstring). `refs` maps each
    definition a 0.3 statement names to the content hash of its source (holon.gen.refs): a dict, or a callable
    law -> dict that resolves them, called only when the law's hash covers refs (holon-ir/0.3)."""
    irv, scheme = law.get("ir_version"), hash_scheme(law)
    if irv == DISCH_PROFILE_IR:
        core = law["statement"]
    elif irv == "holon-ir/0.3":
        core = {k: law[k] for k in (HASHED_KEYS_03 if scheme == 1 else HASHED_KEYS_03_S2)}
        r = refs(law) if callable(refs) else refs
        core["refs"] = dict(sorted((r or {}).items()))
    else:
        core = {k: law[k] for k in HASHED_KEYS}
    return "sha256:" + hashlib.sha256(canonical_json(core)).hexdigest()


def with_hash_scheme(law: dict, scheme: int) -> dict:
    """The law under hash scheme `scheme`: scheme 2 gives a holon-ir/0.3 law "hash_scheme": 2 (placed after
    rule_catalog_version); scheme 1 leaves every law as it is (a scheme-1 law carries no hash_scheme key)."""
    if scheme == 1 or law.get("ir_version") != "holon-ir/0.3":
        return law
    out = {}
    for k, v in law.items():
        if k != "hash_scheme":
            out[k] = v
        if k == "rule_catalog_version":
            out["hash_scheme"] = scheme
    out.setdefault("hash_scheme", scheme)
    hash_scheme(out)
    return out


def plan_law_set(root: Path | str | None = None) -> dict | None:
    """The "law_set" section ({milestone, laws, facts, ...}) of the plan-stated product laws' sidecar, read as data
    (holon.derivation.laws validates and generates the set), or None without the sidecar."""
    p = Path(root or ROOT) / PLAN_LAWS_SIDECAR
    if not p.is_file():
        return None
    ls = json.loads(p.read_text(encoding="utf-8")).get("law_set")
    return ls if isinstance(ls, dict) else None


def milestone_hash_scheme(milestone: str, root: Path | str | None = None) -> int:
    """The hash scheme a milestone's 0.3 laws are generated under: spec/<M>/hash_scheme.json's "hash_scheme" (the
    migration writes it: holon.statement_diff migrate-hash), 1 without the file."""
    p = Path(root or ROOT) / "spec" / str(milestone) / HASH_SCHEME_FILE
    if not p.is_file():
        return 1
    s = json.loads(p.read_text(encoding="utf-8")).get("hash_scheme")
    if isinstance(s, bool) or s not in HASH_SCHEMES:
        raise IRError(f"{p}: hash_scheme {s!r} is not one of {list(HASH_SCHEMES)}")
    return s


def check_premises(law: dict) -> None:
    """IR rules on premises (G3, whitepaper L13): a collision-freedom premise names a function binder
    and a finite set; injectivity over all values (`set: "*"` or no set) is an axiom in disguise."""
    st = law.get("statement", {})
    fn_binders = {b["name"] for b in st.get("binders", []) if str(b.get("type", "")).startswith("Fn<")}
    for prem in st.get("assume", []):
        if "cf" in prem:
            cf = prem["cf"]
            if not isinstance(cf.get("set"), list) or not cf["set"]:
                raise IRError(f"{law.get('law_id')}: a cf premise over {cf.get('set')!r} states global injectivity")
            if cf.get("fn") not in fn_binders:
                raise IRError(f"{law.get('law_id')}: cf premise over {cf.get('fn')!r}, which is not a Fn binder")
        elif "hyp" in prem:
            if not isinstance(prem["hyp"], dict) or not prem["hyp"].get("name"):
                raise IRError(f"{law.get('law_id')}: a hyp premise must name its hypothesis")
        elif set(prem) - {"eq", "neq"}:
            raise IRError(f"{law.get('law_id')}: unknown premise form {sorted(prem)}")


def check_binder_types(law: dict, facts: dict | None) -> None:
    """IR rule on binder types (0.3, audit F-M2-18): every binder type is a base type, Fn<A,B>, Bytes(n), or a
    record ref, which must name a record type the law's facts declare. A ref naming no facts type is an
    IRError (the schema can only check its shape)."""
    import re
    types = set((facts or {}).get("types", {}))
    if (facts or {}).get("linked_version") == "holon-linked/0.1":   # a linked codec document (I24): its carriers
        types = set(facts.get("carriers", {}))
    if (facts or {}).get("goops_version") == "holon-goops/0.1":     # a Go-op document (I67): its interface carrier
        types = {(facts.get("carrier") or {}).get("id")}
    if (facts or {}).get("gocount_version") == "holon-gocount/0.1":   # a count document (I90): its carrier
        types = {(facts.get("carrier") or {}).get("id")}
    if (facts or {}).get("own_version") == "holon-own/0.1":   # an OWN carrier document (I35, W8): its type's calls, values
        types = {f"{k}_{facts.get('stem')}" for k in ("Call", "Val")}
    for b in law.get("statement", {}).get("binders", []):
        t = str(b.get("type", ""))
        if t in BASE_TYPES or t.startswith("Fn<") or re.fullmatch(r"Bytes\([0-9]+\)", t):
            continue
        # I27: a 256-bit word, and the value type of a storage family of the law's transitions document
        if t == "Word" and (facts or {}).get("facts_version") == "holon-facts/0.3":
            continue
        mv = re.fullmatch(r"Val\[([A-Za-z_][A-Za-z0-9_]*)\]", t)
        if mv and mv.group(1) in {f.get("name") for f in ((facts or {}).get("storage") or []) +
                                  ((facts or {}).get("inherited_storage") or []) if isinstance(f, dict)}:
            continue
        if t not in types:
            raise IRError(f"{law.get('law_id')}: binder {b.get('name')}: {t} is neither an IR type nor a record type "
                          "of its facts")


def scope_of(law: dict) -> dict:
    """The statement's scope (0.3, whitepaper §8.6): {"kind": "unbounded"} when absent. bounded{H} bounds every
    Trace binder to at most H actions; at_state{ref} states the claim at one referenced state."""
    return dict(law.get("statement", {}).get("scope") or {"kind": "unbounded"})


def negation_law(law: dict) -> dict:
    """The negation subform of a purely existential law as its own law (BUILD_PLAN I7, audit F-M2-19): the same
    binders made universal, the same scope, and the claim negated: an equation becomes an inequation, an
    inequation an equation. Linked both ways: the result's negation_of is the law's id; the caller gives the
    existential law `negation: <result id>` when it freezes both. Raises IRError when the negation is not a
    statement of the IR: a law with a universal binder, with premises, or whose claim is a conjunction (its
    negation is a disjunction), stays UNKNOWN with that reason (I7 fallback).

    Machine-free (it reads only the IR), so `holon derive` and the rules engine can freeze the pair at derive
    time. A {"neq": [a, b]} claim is emitted exactly as the pipeline's run-time negation was:
    eq_T(a, b) == false, through the decidable equality of a's type (holon.gen.mlaws)."""
    st = law.get("statement", {})
    binders = st.get("binders", [])
    lid = law.get("law_id")
    if not binders or any(b.get("q") != "exists" for b in binders):
        raise IRError(f"{lid}: a negation subform is generated for purely existential laws")
    if st.get("assume"):
        raise IRError(f"{lid}: an existential law takes no premises")
    c = st.get("claim", {})
    if "all" in c:
        if len(c["all"]) != 1:
            raise IRError(f"{lid}: the negation of a conjunction is a disjunction, which the IR cannot state")
        c = c["all"][0]
    if set(c) == {"eq"}:
        neg_claim = {"neq": copy.deepcopy(c["eq"])}
    elif set(c) == {"neq"}:
        neg_claim = {"eq": copy.deepcopy(c["neq"])}
    else:
        raise IRError(f"{lid}: no negation of the claim form {sorted(c)}")
    out = {k: copy.deepcopy(v) for k, v in law.items() if k not in ("notes", "negation", "predicted", "evidence")}
    out["law_id"] = f"{lid}_neg"
    out["negation_of"] = lid
    out["statement"] = {"binders": [dict(b, q="forall") for b in binders], "assume": [], "claim": neg_claim,
                        "scope": scope_of(law)}
    out["notes"] = f"generated negation subform of {lid} (holon.ir.negation_law): for all binders, not the claim"
    return out


def laws_dir(milestone: str, root: Path | str | None = None) -> Path:
    return Path(root or ROOT) / "laws" / milestone


def load_laws(milestone: str = "M0", root: Path | str | None = None) -> list[dict]:
    d = laws_dir(milestone, root)
    laws = [json.loads(p.read_text()) for p in sorted(d.glob("L_*.json"))]
    for law in laws:
        if law.get("ir_version") != IR_VERSION:
            raise ValueError(f"{law.get('law_id')}: unsupported IR version {law.get('ir_version')!r}")
    return sorted(laws, key=lambda l: l["law_id"])


def record_files(results: Path | str) -> list[Path]:
    """The result records in a results directory, named like the law files load_laws_any reads (LAW_GLOB)."""
    return sorted(Path(results).glob(LAW_GLOB))


def load_laws_any(milestone: str, root: Path | str | None = None) -> list[dict]:
    """Laws of any supported IR version (0.2 adds state-machine statements)."""
    d = laws_dir(milestone, root)
    laws = [json.loads(p.read_text()) for p in sorted(d.glob(LAW_GLOB))]   # L_* and, from 0.3, L3_* etc.
    for law in laws:
        if law.get("ir_version") not in IR_VERSIONS:
            raise ValueError(f"{law.get('law_id')}: unsupported IR version {law.get('ir_version')!r}")
    return sorted(laws, key=lambda l: l["law_id"])


def ir_version_of(milestone: str, root: Path | str | None = None) -> str:
    vs = {l["ir_version"] for l in load_laws_any(milestone, root)}
    if not vs:
        raise ValueError(f"{milestone}: no law files under {laws_dir(milestone, root)}")
    if len(vs) != 1:
        raise ValueError(f"{milestone}: mixed IR versions {vs}")
    return vs.pop()


class NoRegistry(FileNotFoundError):
    """laws/<m>/REGISTRY.json does not exist: the milestone has no frozen laws to check."""


def load_registry(milestone: str = "M0", root: Path | str | None = None) -> dict:
    p = laws_dir(milestone, root) / "REGISTRY.json"
    if not p.is_file():
        raise NoRegistry(f"{p} does not exist: milestone {milestone} has no frozen laws (no registry to check)")
    return json.loads(p.read_text())


def rebind_facts(law: dict, facts_sha256: str) -> dict:
    """A copy of law re-targeted at another fact set (used with --no-registry)."""
    out = copy.deepcopy(law)
    out["facts_sha256"] = facts_sha256
    return out


# ---------------------------------------------------------------- rendering
def render_term(t: dict) -> str:
    # holon-ir/0.1 (header laws)
    if "var" in t:
        return t["var"]
    if "bytes" in t:
        b = t["bytes"]
        if len(b) > 14 and set(b[2:]) == {"0"}:
            return f"0x00*{(len(b) - 2) // 2}"
        return b
    if "field" in t:
        return f"{render_term(t['of'])}.{t['field']}"
    if "call" in t:
        return f"{t['call']}({', '.join(render_term(a) for a in t['args'])})"
    if "some" in t:
        return f"Some({render_term(t['some'])})"
    # holon-ir/0.2 (state-machine laws; grammar in holon/gen/mlaws.py)
    if "nat" in t:
        return str(int(t["nat"]))
    if "bool" in t:
        return "true" if t["bool"] else "false"
    if "nats" in t:
        return "[" + ", ".join(str(int(x)) for x in t["nats"]) + "]"
    if "s0" in t:
        return "s0"
    for k in ("run", "step", "obs"):
        if k in t:
            return f"{k}({render_term(t[k])}, {render_term(t['from'])})"
    if "trace" in t:
        return "[" + ", ".join(render_term(a) for a in t["trace"]) + "]"
    if "cat" in t:
        return " ++ ".join(render_term(x) for x in t["cat"])
    if "act" in t:
        return f"{t['act']}(" + ", ".join(f"{k}={render_term(v)}" for k, v in sorted(t["args"].items())) + ")"
    if "proj" in t:
        return f"erase[{', '.join(t['proj'])}]({render_term(t['of'])})"
    if "obsv" in t:
        return f"{t['obsv']}({render_term(t['of'])})"
    if "mig" in t:
        return f"mig_{t['mig']}(" + ", ".join(render_term(x) for x in [t["of"]] + list(t.get("args", []))) + ")"
    if "fn" in t:
        return f"{t['fn']}({', '.join(render_term(a) for a in t['args'])})"
    if "plus" in t:
        return f"({render_term(t['plus'][0])} + {render_term(t['plus'][1])})"
    # holon-ir/0.3: application of a function binder
    if "app" in t:
        return f"{t['app']}({', '.join(render_term(a) for a in t['args'])})"
    # holon-ir/0.3 (I15): a SORT-site term, every hit of the site has minuend >= subtrahend (holon.sorts.sites)
    if "site" in t and "on" in t and "from" in t:
        return f"site_ok[{t['site']}]({render_term(t['on'])}, {render_term(t['from'])})"
    # holon-ir/0.3 (I30): a SORT coercion term, every hit of coercion ID while action A runs from state S is Some
    if "coerce" in t and "on" in t and "from" in t:
        return f"coerce_ok[{t['coerce']}]({render_term(t['on'])}, {render_term(t['from'])})"
    # holon-ir/0.3 (I31): a DISCH term, disch_ok[ID](A, S, T, E) (holon.rules.disch)
    if "disch" in t and "on" in t and "from" in t:
        return (f"disch_ok[{t['disch']}]({render_term(t['on'])}, {render_term(t['from'])}, "
                f"{render_term(t.get('at'))}, {render_term(t.get('env'))})")
    # holon-ir/0.3 (I26): a FACT term, the kernel or attribution law of the fact ID over the law's binders (holon.rules.fact)
    if "fact" in t and isinstance(t.get("on"), list):
        return f"fact_ok[{t['fact']}]({', '.join(render_term(a) for a in t['on'])})"
    # holon-ir/0.3 (I28): a PAR-init term, init_ok[ID](A, S, E) over the versioned machine (holon.rules.par_init)
    if isinstance(t.get("init"), str) and "on" in t and "from" in t:
        return (f"init_ok[{t['init']}]({render_term(t['on'])}, {render_term(t['from'])}, "
                f"{render_term(t.get('env'))})")
    # holon-ir/0.3 (I70): a slash term, slash_ok[ID](S, K, U, EA, EB) over a migration's slash sites (holon.rules.slash)
    if isinstance(t.get("slash"), str) and isinstance(t.get("on"), list):
        return f"slash_ok[{t['slash']}]({', '.join(render_term(a) for a in t['on'])})"
    # holon-ir/0.3 (I29): a NAT square term, square_ok[ID](A, U, S, E) over the versioned machine (holon.rules.nat)
    if isinstance(t.get("square"), str) and isinstance(t.get("on"), list):
        return f"square_ok[{t['square']}]({', '.join(render_term(a) for a in t['on'])})"
    # holon-ir/0.3: a bundle term, bundle_ok[ID](args) over the law's binders (I84, holon.rules.bundle2: args its
    # "on" list) or over its member's law model (I86, holon.rules.bundle: args its on, from, at and env, a premise of
    # it bundle_<premise>[ID](..)); the id's sub-form names the module (holon.rules.bundle_terms)
    if isinstance(t.get("bundle"), str):
        args = [t[k] for k in ("on", "from", "at", "env") if k in t]
        flat = [x for a in args for x in (a if isinstance(a, list) else [a])]
        return f"bundle_{t.get('premise') or 'ok'}[{t['bundle']}]({', '.join(render_term(a) for a in flat)})"
    # holon-ir/0.3 (I27): an UNDO term, the undo law of the pair or residue ID over the law's binders (holon.rules.undo)
    if "undo" in t and isinstance(t.get("on"), list):
        return f"undo_ok[{t['undo']}]({', '.join(render_term(a) for a in t['on'])})"
    # holon-ir/0.3 (I35): an OWN term, the alias or lost-write law ID over the law's binders (holon.rules.own)
    if "own" in t and isinstance(t.get("on"), list):
        return f"own_ok[{t['own']}]({', '.join(render_term(a) for a in t['on'])})"
    # holon-ir/0.3 (I65): a ghost counter, the sum of E over the successful A steps of T run from S
    if isinstance(t.get("ghost"), str) and "over" in t:
        from .diagram.access import render as render_expr
        return f"ghost[{t['ghost']}, {render_expr(t.get('add'))}]({render_term(t['over'])}, {render_term(t['from'])})"
    # holon-ir/0.3 (I24): a facts expression in a state, with an action's inputs ({"expr": E, "from": S, ..})
    if "expr" in t and "from" in t:
        from .diagram.access import render as render_expr
        at = render_term(t["from"])
        if "action" in t:
            at += f", {t['action']} inputs of {render_term(t['on'])}"
        if t.get("bind"):
            at += ", " + ", ".join(f"{k} := {render_term(v)}" for k, v in sorted(t["bind"].items()))
        return f"⟦{render_expr(t['expr'])}⟧({at})"
    # holon-ir/0.3 (I20): a SORT-width term, every store at the site fits the field's width (holon.sorts.width)
    if "width_site" in t and "on" in t and "from" in t:
        return f"width_ok[{t['width_site']}]({render_term(t['on'])}, {render_term(t['from'])})"
    raise ValueError(f"unknown term {t}")


def render_prop(p: dict) -> str:
    if "all" in p:
        return " ∧ ".join(render_prop(x) for x in p["all"])
    if "cf" in p:
        s = p["cf"]["set"]
        return f"CF({p['cf']['fn']}, {{{', '.join(render_term(x) for x in s)}}})" if isinstance(s, list) else f"CF({p['cf']['fn']}, *)"
    if "hyp" in p:
        return f"Hyp({p['hyp'].get('name')})"
    if "neq" in p:
        a, b = p["neq"]
        return f"{render_term(a)} != {render_term(b)}"
    a, b = p["eq"]
    return f"{render_term(a)} == {render_term(b)}"


def premises(law: dict) -> list[str]:
    """Readable premises: one per assume clause of the frozen statement, nothing else.

    Model assumptions (hash stand-ins, oracles, abstractions) are not statement premises:
    they are joined from spec/ledger by holon.records into a record's model_assumptions.
    """
    return [render_prop(p) for p in law["statement"].get("assume", [])]


def render_statement(law: dict) -> str:
    st = law["statement"]
    if "binders" in st:
        sym = {"forall": "∀", "exists": "∃"}
        binders = ", ".join(f"{sym[b['q']]} {b['name']}: {b['type']}" for b in st["binders"])
        head = f"{binders}. "
    else:
        binders = ", ".join(f"{b['name']}: {b['type']}" for b in st["forall"])
        head = f"∀ {binders}. "
    prem = " ∧ ".join(premises(law))
    sc = st.get("scope") or {}
    tail = {"bounded": f"   [scope: bounded, every trace of at most {sc.get('H')} actions]",
            "at_state": f"   [scope: at state {sc.get('ref')}]"}.get(sc.get("kind"), "")
    return head + (f"{prem} ⇒ " if prem else "") + render_prop(st["claim"]) + tail
