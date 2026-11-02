"""The bundle terms {"bundle": ID, ...} of two rule catalogs, and the module that owns each one.

  holon-rules/1.10 (I84, holon.rules.bundle2)  PAR link_domain, FACT public_input, DISCH self_controlled: a term
                                                {bundle, on: [..]} whose id is <model>:<sub-form>:<action>:...
  holon-rules/1.11 (I86, holon.rules.bundle)   SORT payer and conservation, DISCH keyed_blocking, keyed_external and
                                                keyed_external_none, PAR push: a term {bundle, on, from?, at?, env?,
                                                premise?} whose id is <member>:<sub-form>:<site>[:<class>]

Both write the sub-form as the id's second field, and their sub-form sets are disjoint (each module's own table:
holon.rules.bundle2.RULE_OF, holon.rules.bundle.RULE_SUBFORMS), so the id names the module that owns a term: the one
that resolves its ref (holon.gen.refs) and decides and emits its law (holon.bindings). A term's shape does not: a PAR
push term {bundle, on: [..]} has the shape of holon-rules/1.10's. Nothing here names a target.
"""
from __future__ import annotations


def subform(bid) -> str | None:
    """The sub-form of a bundle id: its second field (None for a string with fewer than three fields)."""
    parts = bid.split(":") if isinstance(bid, str) else []
    return parts[1] if len(parts) >= 3 else None


def owner(bid):
    """The module that owns the bundle id `bid` (holon.rules.bundle2 or holon.rules.bundle), by its sub-form; None
    for an id of neither catalog's sub-forms."""
    from . import bundle, bundle2
    sub = subform(bid)
    if sub in bundle2.RULE_OF:
        return bundle2
    if sub in bundle.RULE_SUBFORMS:
        return bundle
    return None


def claim_id(law: dict) -> str | None:
    """The id of the first bundle term of a holon-ir/0.3 law's claim (None when its claim has none)."""
    def walk(t):
        if isinstance(t, dict):
            if isinstance(t.get("bundle"), str):
                return t["bundle"]
            t = list(t.values())
        if isinstance(t, list):
            for x in t:
                r = walk(x)
                if r is not None:
                    return r
        return None
    if law.get("ir_version") != "holon-ir/0.3":
        return None
    return walk((law.get("statement") or {}).get("claim"))


def law_owner(law: dict):
    """The module that owns a law whose claim is a bundle term (by the term's id), None for any other law."""
    bid = claim_id(law)
    return owner(bid) if bid is not None else None
