"""Law IR (holon-ir/0.1, 0.2, 0.3): canonical JSON, statement hashes, loading and rendering.

The statement hash is the identity of a frozen claim (whitepaper §8.9, §9.4). Only
ir_version, law_id, rule, facts_sha256 and statement are hashed; notes and evidence
are metadata.
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


class IRError(ValueError):
    """A law the IR rules reject (for example a premise stating global injectivity)."""
ROOT = Path(__file__).resolve().parents[1]


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def statement_hash(law: dict, refs: dict | None = None) -> str:
    """The identity of a frozen claim. 0.1/0.2: over HASHED_KEYS. 0.3: over HASHED_KEYS_03 plus
    `refs`, which maps each definition the statement names to the content hash of its source
    (holon.gen.refs)."""
    if law.get("ir_version") == "holon-ir/0.3":
        core = {k: law[k] for k in HASHED_KEYS_03}
        core["refs"] = dict(sorted((refs or {}).items()))
    else:
        core = {k: law[k] for k in HASHED_KEYS}
    return "sha256:" + hashlib.sha256(canonical_json(core)).hexdigest()


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


def laws_dir(milestone: str, root: Path | str | None = None) -> Path:
    return Path(root or ROOT) / "laws" / milestone


def load_laws(milestone: str = "M0", root: Path | str | None = None) -> list[dict]:
    d = laws_dir(milestone, root)
    laws = [json.loads(p.read_text()) for p in sorted(d.glob("L_*.json"))]
    for law in laws:
        if law.get("ir_version") != IR_VERSION:
            raise ValueError(f"{law.get('law_id')}: unsupported IR version {law.get('ir_version')!r}")
    return sorted(laws, key=lambda l: l["law_id"])


def load_laws_any(milestone: str, root: Path | str | None = None) -> list[dict]:
    """Laws of any supported IR version (0.2 adds state-machine statements)."""
    d = laws_dir(milestone, root)
    laws = [json.loads(p.read_text()) for p in sorted(d.glob("L*.json"))]   # L_* and, from 0.3, L3_* etc.
    for law in laws:
        if law.get("ir_version") not in IR_VERSIONS:
            raise ValueError(f"{law.get('law_id')}: unsupported IR version {law.get('ir_version')!r}")
    return sorted(laws, key=lambda l: l["law_id"])


def ir_version_of(milestone: str, root: Path | str | None = None) -> str:
    vs = {l["ir_version"] for l in load_laws_any(milestone, root)}
    if len(vs) != 1:
        raise ValueError(f"{milestone}: mixed IR versions {vs}")
    return vs.pop()


def load_registry(milestone: str = "M0", root: Path | str | None = None) -> dict:
    return json.loads((laws_dir(milestone, root) / "REGISTRY.json").read_text())


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
    return head + (f"{prem} ⇒ " if prem else "") + render_prop(st["claim"])
