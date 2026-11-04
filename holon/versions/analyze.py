"""Rules PI1-PI5 over transitions documents: commitment chains, their chained pairs, the PAR-init basis and the link
gaps; with V4's downgrade gaps, the analysis <outputs.analysis> (`holon versions analyze`).

  PI1 chains      a commitment family F (I26 F1/F2: a mapping family with a final, whole, keyed, unconditional hash write
                  in a state action and an authenticating guard reach in some action) has root sites, commitment sites
                  in an action with no authenticating guard reach of F over input bytes, whose committed value hashes
                  input bytes; and successor sites, commitment sites in an action with one (the first gives the parent
                  bytes P), whose committed value hashes a memory region
  PI2 cells       an mstore at a literal offset o with value ["<<", V, s], s a literal; its read from bytes X is
                  [">>", ["word", X, o], s]
  PI3 pairs       (o, o', s) such that in every successor site's region the cell at o is ["<<", R + Y, s] (after folding
                  additions of the literal 0), R the parent's read of (o, s), and the cell at o' != o is ["<<", Y, s]; a
                  literal step gives no pair
  PI4 basis       one element per (F, root action, pair) of any document; law id L_pinit_<contract>_<root>_<F>_<o>_<o'>,
                  init id <model>:chain:<F>:<o>:<o'>
  PI5 link gaps   per pair and interface I of an external call ("call" or "callok" "<I>.<f>") of an action that
                  authenticates input bytes X against F, whose arguments carry X's read of the chained cell

Nothing here names a target: every family, action, contract and interface comes from the documents, the model's name
and the gaps' obligations from the sidecar.
"""
from __future__ import annotations

from pathlib import Path

from . import ANALYSIS_VERSION, Ctx, Refused, read_json, render, vkey, write_or_check

from ..rules.par_init import authenticated_inputs, basis, chains, is_op, occurs


def _call_terms(t, out: list) -> None:
    if is_op(t) and t[0] in ("call", "callok") and len(t) > 1 and isinstance(t[1], str):
        out.append(t)
    if isinstance(t, list):
        for x in t:
            _call_terms(x, out)


def link_gaps(d: dict, ch: dict, meta: dict, milestone: str) -> list:
    """PI5 over one document and its chains."""
    out = []
    for f in ch["families"]:
        F = f["family"]
        for pr in f["pairs"]:
            by_if = {}
            for a in d.get("actions") or []:
                reads = [[">>", ["word", X, pr["cell"]], pr["shift"]] for _w, _k, X in authenticated_inputs(a, F)]
                if not reads:
                    continue
                for i, c in enumerate(a.get("calls") or []):
                    terms = []
                    _call_terms(c.get("expr"), terms)
                    for t in terms:
                        if any(occurs(t[2:], r) for r in reads):
                            by_if.setdefault(t[1].split(".", 1)[0], set()).add((a["name"], f"calls[{i}]", t[1]))
            for iface in sorted(by_if):
                out.append({"id": f"gap:{milestone}:link:{F}:{pr['cell']}:{iface}", "kind": "link", "family": F,
                            "cell": pr["cell"], "incr": pr["incr"], "interface": iface,
                            "sites": [{"action": n, "at": at, "fn": fn} for n, at, fn in sorted(by_if[iface])],
                            **meta})
    return out


def analysis(docs: dict, gaps: list, model: str, meta: dict, milestone: str) -> dict:
    """The analysis over {version: document}: the chains, the PAR-init basis, the link gaps merged over the versions and
    the given downgrade gaps."""
    per = {v: chains(d) for v, d in docs.items()}
    merged = {}
    for v in sorted(docs, key=vkey):
        for g in link_gaps(docs[v], per[v], meta, milestone):
            m = merged.setdefault(g["id"], {k: g[k] for k in ("id", "kind", "family", "cell", "incr", "interface",
                                                              "obligation", "question", "status")})
            m.setdefault("sites", {})[v] = g["sites"]
    return {"analysis_version": ANALYSIS_VERSION, "versions": per, "basis": basis(per, model),
            "link_gaps": [merged[k] for k in sorted(merged)], "downgrade_gaps": gaps}


def versioned_analysis(ctx: Ctx) -> dict:
    vd = ctx.versions_doc()
    docs = {v: read_json(p, "document") for v, (p, _rel) in ctx.documents().items()}
    return analysis(docs, vd.get("downgrade_gaps") or [], ctx.model, ctx.gap_meta("link"), ctx.milestone)


def run(ctx: Ctx, check: bool, facts: list | None = None, out: str | None = None) -> int:
    if facts:
        docs = {}
        for i, f in enumerate(facts):
            p = Path(f)
            p = p if p.is_absolute() else Path.cwd() / p
            d = read_json(p, "document")
            if d.get("facts_version") != "holon-facts/0.3" or (d.get("extraction") or {}).get("kind") != "transitions":
                raise Refused(f"{f}: not a holon-facts/0.3 transitions document")
            docs[f"V{i}"] = d
        doc = analysis(docs, [], ctx.model, ctx.gap_meta("link"), ctx.milestone)
    else:
        doc = versioned_analysis(ctx)
    target = Path(out) if out else ctx.root / ctx.out("analysis")
    if not target.is_absolute():
        target = Path.cwd() / target
    ok = write_or_check(target, render(doc), check)
    if check:
        print(f"holon versions analyze: {target} {'is up to date' if ok else 'differs from a fresh analysis'}")
        return 0 if ok else 1
    print(f"holon versions analyze: wrote {target} ({len(doc['basis'])} basis elements, {len(doc['link_gaps'])} link "
          f"gaps, {len(doc['downgrade_gaps'])} downgrade gaps)")
    return 0

