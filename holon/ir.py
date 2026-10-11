"""Law IR (holon-ir/0.1): canonical JSON, statement hashes, loading and rendering.

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
HASHED_KEYS = ("ir_version", "law_id", "rule", "facts_sha256", "statement")
ROOT = Path(__file__).resolve().parents[1]


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def statement_hash(law: dict) -> str:
    core = {k: law[k] for k in HASHED_KEYS}
    return "sha256:" + hashlib.sha256(canonical_json(core)).hexdigest()


def laws_dir(milestone: str, root: Path | str | None = None) -> Path:
    return Path(root or ROOT) / "laws" / milestone


def load_laws(milestone: str = "M0", root: Path | str | None = None) -> list[dict]:
    d = laws_dir(milestone, root)
    laws = [json.loads(p.read_text()) for p in sorted(d.glob("L_*.json"))]
    for law in laws:
        if law.get("ir_version") != IR_VERSION:
            raise ValueError(f"{law.get('law_id')}: unsupported IR version {law.get('ir_version')!r}")
    return sorted(laws, key=lambda l: l["law_id"])


def load_registry(milestone: str = "M0", root: Path | str | None = None) -> dict:
    return json.loads((laws_dir(milestone, root) / "REGISTRY.json").read_text())


def rebind_facts(law: dict, facts_sha256: str) -> dict:
    """A copy of law re-targeted at another fact set (used with --no-registry)."""
    out = copy.deepcopy(law)
    out["facts_sha256"] = facts_sha256
    return out


# ---------------------------------------------------------------- rendering
def render_term(t: dict) -> str:
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
    raise ValueError(f"unknown term {t}")


def render_prop(p: dict) -> str:
    a, b = p["eq"]
    return f"{render_term(a)} == {render_term(b)}"


def premises(law: dict) -> list[str]:
    """Readable premises: one per assume clause (plus none for M0's oracle-free laws)."""
    return [render_prop(p) for p in law["statement"].get("assume", [])]


def render_statement(law: dict) -> str:
    st = law["statement"]
    binders = ", ".join(f"{b['name']}: {b['type']}" for b in st["forall"])
    prem = " ∧ ".join(premises(law))
    return f"∀ {binders}. " + (f"{prem} ⇒ " if prem else "") + render_prop(st["claim"])
