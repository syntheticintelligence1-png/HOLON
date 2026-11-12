"""I111 (HUMAN_ANSWERS Q77): the per-document `holon types` fallback (the contract is the docstring of
tests_m6/test_i111_types_totality.py, rules O1-O7, and spec/M6/predictions/I111.json thresholds.opaque).

Opt-in only: a typed-sorts sidecar names "types_fallback": "opaque" (the only value; any other is refused). Without
the key nothing here runs: holon types refuses a milestone on an ill-sorted term (N2), as before.

Under the key, holon types types each document on its own, and a document whose typed model generation raises the
ill-sorted error (holon.sorts.model3.GenError) is opaque: a recorded miss in gen/<M>/sorts/opaque.json

  {"document": "opaque", "opaque_version", "milestone", "sorts_sha256", "documents": [{"document", "sha256", "model",
   "term", "reason"}], "typed": [document]}

(canonical JSON, sorted, no timestamp). An opaque document has no typed model, so no state of it is constrained and
none of its actions is modelled; no law is derived over it, and every claim over it is UNKNOWN. Every later stage of
the typed part (model, disch, derive, run) reads the typed documents only: typed_sidecar.Sidecar.documents leaves the
opaque ones out, and Sidecar.all_documents (the sort pass and holon types) keeps every one. Another document assumes
nothing new about an opaque one: every typed model is one document's, and another contract is reached only through an
external call, whose answer is a free value (A-env) whether or not the callee is typed.
"""
from __future__ import annotations

import json
from pathlib import Path

VERSION = "holon-opaque/0.1"
MODES = ("opaque",)
# I112 (Q81, the lead's correction): the per-document refusal classes the fallback may make opaque, named by the
# sidecar's types_opaque_classes (absent: I111's, gen_error only, and every output is I111's)
CLASSES = ("gen_error", "member_layout", "unsupported")


def mode(doc: dict) -> str | None:
    """The sidecar's types_fallback: None without the key, "opaque", or a ValueError for any other value."""
    if "types_fallback" not in doc:
        return None
    v = doc["types_fallback"]
    if v not in MODES:
        raise ValueError(f"types_fallback {v!r}: the only fallback is {MODES[0]!r}")
    return v


def classes(doc: dict) -> tuple:
    """The refusal classes a sidecar's fallback makes opaque: () without types_fallback; I111's ("gen_error",) without
    types_opaque_classes; else that non-empty, sorted, duplicate-free subset of CLASSES (anything else: ValueError)."""
    named = "types_opaque_classes" in doc
    if mode(doc) is None:
        if named:
            raise ValueError("types_opaque_classes needs types_fallback \"opaque\"")
        return ()
    if not named:
        return ("gen_error",)
    v = doc["types_opaque_classes"]
    if not isinstance(v, list) or not v or any(x not in CLASSES for x in v) or v != sorted(set(v)):
        raise ValueError(f"types_opaque_classes {v!r}: a non-empty sorted subset of {list(CLASSES)}")
    return tuple(v)


def class_of(e: BaseException) -> str | None:
    """The refusal class of a document's typed model generation error, or None (a refusal of the milestone): GenError
    (whatever its case) gen_error; holon.machine.MemberLayoutError member_layout; holon.extracted_eval.Unsupported
    unsupported. Every other error, ModelError included, is None."""
    from .. import extracted_eval
    from ..machine import MemberLayoutError
    from .model3 import GenError
    if isinstance(e, GenError):
        return "gen_error"
    if isinstance(e, MemberLayoutError):
        return "member_layout"
    if isinstance(e, extracted_eval.Unsupported):
        return "unsupported"
    return None


def path(milestone: str, root: Path) -> Path:
    return Path(root) / "gen" / milestone / "sorts" / "opaque.json"


def excluded(milestone: str, root: Path) -> set[str]:
    """The documents the milestone's last `holon types` made opaque (none when it has not run under the key)."""
    p = path(milestone, root)
    if not p.is_file():
        return set()
    d = json.loads(p.read_text(encoding="utf-8"))
    return {x["document"] for x in d.get("documents") or []}


def term_of(message: str) -> str:
    """The ill-sorted term an error names: its first clause (the action, then the operation), before ': ' or ' (at '."""
    head = message.split(" (at ", 1)[0]
    parts = head.split(": ")
    return ": ".join(parts[:2]) if len(parts) > 1 else head


def record(milestone: str, sorts_sha256: str | None, misses: list[dict], typed: list[str]) -> dict:
    return {"document": "opaque", "opaque_version": VERSION, "milestone": milestone, "sorts_sha256": sorts_sha256,
            "documents": sorted(misses, key=lambda x: x["document"]), "typed": sorted(typed)}
