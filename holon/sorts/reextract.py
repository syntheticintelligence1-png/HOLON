"""Derivation on extracted facts (I20; whitepaper §9.4 re-extraction, §10.1; BUILD_PLAN I20 "re-derivation of I15's
site laws on the extracted facts, through reextraction entries"; contract clause 5 of the docstring of
tests_m2/test_extracted_refinement.py).

A milestone adopts extracted documents for derivation through the sidecar spec/<M>/lib/derive_extracted.json:

  {"derive_extracted_version": "holon-derive-extracted/0.1", "doc",
   "documents": ["<extracted document>", ...],     holon-facts/0.3 documents holon extract wrote (G1 reproduces them)
   "reextraction": ["SORT/site", ...],             rule/subform pairs re-derived with the documents' evidence
   "width": true | false}                          rule SORT-width over the documents (holon.sorts.width)

Without the sidecar nothing here changes a derivation (the milestone keeps its statements). With it:

  * SORT-site (re-extraction). A site whose span is a source span is re-derived on the extracted facts: the site's
    spec (what the statement ref site:<id> hashes) gains "extracted": per extracted transitions document whose
    window declaration (holon.window) views the site's facts, the document's checks (guard reaches and implicit
    checks, holon.machine.document_programs) of the site's entry points whose span overlaps the site's span, each
    {"action", "check", "kind", "code", "expr"} (an empty list says the extraction has no check there). A definition
    site (no source span) is not re-derived. The statement itself is unchanged; its hash changes through the ref,
    so the change goes through a "reextraction" entry of laws/STATEMENT_DIFF.jsonl (holon.statement_diff).
  * site_evidence(..) is what both holon derive and the ref recomputation (holon.gen.refs, G2) call, so the two
    never disagree; disabled() computes a spec as it was before the adoption (what a reextraction entry's old
    refs are).

Nothing here names a target: documents come from the sidecar, links from window declarations.
"""
from __future__ import annotations

import contextlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "holon-derive-extracted/0.1"
_DISABLED = [False]


class ReextractError(ValueError):
    pass


@contextlib.contextmanager
def disabled():
    """Within the block, derivation and refs ignore the sidecar (the specs as they were before the adoption)."""
    _DISABLED.append(True)
    try:
        yield
    finally:
        _DISABLED.pop()


def sidecar_path(milestone: str, root=None) -> Path:
    return Path(root or ROOT) / "spec" / str(milestone) / "lib" / "derive_extracted.json"


def sidecar(milestone: str, root=None) -> dict | None:
    if _DISABLED[-1]:
        return None
    p = sidecar_path(milestone, root)
    if not p.is_file():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    if d.get("derive_extracted_version") != VERSION:
        raise ReextractError(f"{p}: derive_extracted_version is not {VERSION}")
    if not isinstance(d.get("documents"), list):
        raise ReextractError(f"{p}: documents is not a list")
    return d


def _load(rel: str, root: Path) -> dict:
    return json.loads((root / rel).read_text(encoding="utf-8"))


def linked_documents(milestone: str, facts_rel: str, root=None) -> list[tuple[str, dict]]:
    """(rel, document) of every transitions document of the sidecar whose window declaration views facts_rel."""
    from .. import window
    root = Path(root or ROOT)
    sc = sidecar(milestone, root)
    if sc is None:
        return []
    views = {d.get("facts"): d.get("abstraction") for _, d in window.declarations(root)}
    out = []
    for rel in sorted(sc["documents"]):
        doc = _load(rel, root)
        if (doc.get("extraction") or {}).get("kind") == "transitions" and views.get(rel) == facts_rel:
            out.append((rel, doc))
    return out


def adopts(milestone: str, rule: str, subform: str, root=None) -> bool:
    sc = sidecar(milestone, root)
    return bool(sc) and f"{rule}/{subform}" in (sc.get("reextraction") or [])


def site_evidence(milestone: str, root, facts_rel: str, site: dict, hits: list[dict]):
    """The "extracted" part of a site's spec (module docstring), or None when the site is not re-derived."""
    from ..machine import document_programs, source_span, spans_overlap
    root = Path(root or ROOT)
    if not adopts(milestone, "SORT", "site", root):
        return None
    sp = source_span(site.get("span"))
    if sp is None:
        return None
    entries = sorted({h["action"] for h in hits})
    out = []
    for rel, doc in linked_documents(milestone, facts_rel, root):
        progs = document_programs(doc)
        checks = []
        for a in entries:
            if a not in progs:
                continue
            for c in progs[a].checks():
                if spans_overlap(sp, source_span(c.src)):
                    checks.append({"action": a, "check": c.id, "kind": c.kind, "code": c.code, "expr": c.expr})
        out.append({"document": rel, "checks": checks})
    return out
