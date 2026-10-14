"""Rule DISCH over the extracted documents: the producers of the sub-forms blocking, revert, external and external_none
(BUILD_PLAN I31; whitepaper §5.7, Thm 6.10, §8.4 and App. E's DISCH row, §2.12; the contract is the docstring of
tests_m3/test_disch.py, rules D10-D12).

Registered under holon-rules/1.4 (holon.rules.CATALOGS), beside every earlier M3 producer. Each producer reads the
DISCH sidecar derive names (spec/<M>/lib/disch.json for a target milestone, --disch for a test milestone; a test
milestone without one derives nothing for DISCH) and the documents it names, through holon.analysis.closure (rules
D1-D9), and nothing else: no hand-written fact document (Q19). derive refuses (Refused, exit 2) when
gen/<M>/disch/closure.json or conjuncts.json is not what `holon disch` writes now.

  blocking       L_disch_blk_<tag>_<X>    one per basis element (B, X): Thm 6.10's invariant over x_closure_X|B
  revert         L_disch_rev_<tag>        one per B: every action excluded under B reverts while B holds
  external       L_disch_ext_<tag>_<Y>    one per (B, Y), Y named by a blocked (B, X): an existential law
  external_none  L_disch_noext_<tag>_<Y>  the same pairs: the separately generated forall-negation of external

Statements (holon-ir/0.3): binders s: Reach, t: Word, a: Act, e: Env and one Fn<Bytes,Word> binder per hash function
the typed model threads (holon.rules.sort.hash_functions), all forall (exists for external); the claim
{"eq": [{"disch": ID, "on": a, "from": s, "at": t, "env": e}, true]} with ID "<model>:<subform>:<tag>:<class>"
(class "all" for revert), hashed through the ref "disch:<ID>" (holon.analysis.closure.disch_ref).

Nothing here names a target: every name, span and term comes from the document and the sidecar.
"""
from __future__ import annotations

from pathlib import Path

from ..analysis import closure as C

RULE = "DISCH"
SUBFORMS = ("blocking", "revert", "external", "external_none")
NOTES = {
    "blocking": "Thm 6.10's invariant: while the blocked condition holds at a time no later than the step's, every "
                "step of an action of the class's closure under it (with the class's permission) keeps it, and time "
                "keeps it",
    "revert": "the generalized chain_revert: every action excluded under the blocked condition reverts while it holds "
              "(the blocked theorem is the obstruction, whitepaper §8.4)",
    "external": "external dependence (whitepaper §5.7): a reachable state where the blocked condition holds and a step "
                "of the named class after which the guard holds",
    "external_none": "the forall-negation of the external law (BUILD_PLAN §2.12: an existential law is never "
                     "REFUTED): no step of the named class discharges the guard while the blocked condition holds",
}


def law_ir(law: dict, an: dict, milestone: str, doc_rel: str, doc_sha: str, catalog_version: str,
           hashes: list[str]) -> dict:
    """The holon-ir/0.3 statement of one DISCH law (D11)."""
    q = "exists" if law["subform"] == "external" else "forall"
    binders = [{"q": q, "name": "s", "type": "Reach"}, {"q": q, "name": "t", "type": "Word"},
               {"q": q, "name": "a", "type": "Act"}, {"q": q, "name": "e", "type": "Env"}]
    binders += [{"q": q, "name": h, "type": "Fn<Bytes,Word>"} for h in hashes]
    did = C.disch_id(an["model"], law)
    return {"ir_version": "holon-ir/0.3", "law_id": law["law_id"], "milestone": milestone, "rule": RULE,
            "subform": law["subform"], "rule_catalog_version": catalog_version, "facts": doc_rel,
            "facts_sha256": doc_sha, "notes": f"{NOTES[law['subform']]}; {did}",
            "statement": {"binders": binders, "assume": [],
                          "claim": {"eq": [{"disch": did, "on": {"var": "a"}, "from": {"var": "s"},
                                            "at": {"var": "t"}, "env": {"var": "e"}}, {"bool": True}]},
                          "scope": {"kind": "unbounded"}}}


def _fresh(ctx) -> tuple[C.Sidecar, dict]:
    """The DISCH sidecar of the derivation and its analyses, after checking that gen/<M>/disch holds exactly what
    `holon disch` writes now (Refused otherwise)."""
    from . import Refused
    rel = getattr(ctx, "disch_sidecar", None)
    try:
        sc = C.Sidecar(ctx.milestone, ctx.root, rel)
        texts = C.files(ctx.milestone, sc)
        ans, inputs = sc.analyses()
    except C.Refused as e:
        raise Refused(f"the DISCH sidecar cannot be read: {e}") from None
    except C.ClassError as e:
        raise Refused(f"the DISCH analysis refuses the document: {e}") from None
    od = Path(ctx.root) / "gen" / ctx.milestone / "disch"
    for name, text in sorted(texts.items()):
        p = od / name
        have = p.read_text(encoding="utf-8") if p.is_file() else None
        if have != text:
            raise Refused(f"gen/{ctx.milestone}/disch/{name} is stale: it is not what `holon disch --milestone "
                          f"{ctx.milestone}` writes now")
    inp = getattr(ctx, "inputs", None)
    if inp is not None:   # DERIVATION's inputs: the sidecar and every file holon disch reads
        inp.read(sc.path)
        for i in sc.doc.get("inputs") or []:
            inp.read(Path(ctx.root) / i["path"])
        for i in inputs:
            inp.read(Path(ctx.root) / i["path"])
        for name in sorted(texts):
            inp.read(od / name)
    return sc, ans


class _Producer:
    def __init__(self, subform: str):
        self.subform = subform
        self.__name__ = f"holon.rules.disch.{subform}"

    def produce(self, ctx) -> list[tuple[dict, dict]]:
        if not getattr(ctx, "disch_enabled", False):
            return []
        cache = getattr(ctx, "_disch", None)
        if cache is None:
            cache = ctx._disch = _fresh(ctx)
        sc, ans = cache
        from .sort import hash_functions
        out = []
        for m in sorted(ans):
            an = ans[m]
            doc_rel, doc_sha = an["_doc"], an["_doc_sha256"]
            hashes = hash_functions(_doc(ctx, doc_rel))
            ents = C.entries(an)
            for law in an["laws"]:
                if law["subform"] != self.subform:
                    continue
                ir = law_ir(law, an, ctx.milestone, doc_rel, doc_sha, ctx.rule_catalog_version, hashes)
                out.append((ir, dict(ents[law["law_id"]], facts=doc_rel)))
        return out


def _doc(ctx, rel: str) -> dict:
    import json
    docs = getattr(ctx, "_disch_docs", None)
    if docs is None:
        docs = ctx._disch_docs = {}
    if rel not in docs:
        docs[rel] = json.loads((Path(ctx.root) / rel).read_text(encoding="utf-8"))
    return docs[rel]


BLOCKING = _Producer("blocking")
REVERT = _Producer("revert")
EXTERNAL = _Producer("external")
EXTERNAL_NONE = _Producer("external_none")
PRODUCERS = {"blocking": BLOCKING, "revert": REVERT, "external": EXTERNAL, "external_none": EXTERNAL_NONE}
