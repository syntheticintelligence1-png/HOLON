"""The INTENT law family's IR (holon-intent/0.1; key I55 design T3, S): statement hashes and the LAWS.bend text."""
from __future__ import annotations

import hashlib

from .common import canonical_json
from .model import render

IR_VERSION = "holon-intent/0.1"


def statement_hash(law: dict) -> str:
    keep = {k: law[k] for k in ("ir_version", "law_id", "template", "clauses", "facts_sha256", "statement")}
    return "sha256:" + hashlib.sha256(canonical_json(keep)).hexdigest()


def model_import(law: dict) -> str:
    return f"import ../model/{law['contract']}.bend as M"


def binder_lines(binders: list[dict], quant: str = "for") -> list[str]:
    return [f"  {quant} {b['name']}: M.{b['type']}" for b in binders]


def law_text(law: dict, name: str | None = None) -> str:
    """LAWS.bend of a law: exactly the law law_id lower-cased, over the model imported as M."""
    st = law["statement"]
    name = name or law["law_id"].lower()
    lines = ["import Base", model_import(law), "", f"law {name}:", *binder_lines(st["binders"]),
             f"  {{{render(st['holds'], 'M.')} == True{{}} : Bool}}"]
    return "\n".join(lines) + "\n"
