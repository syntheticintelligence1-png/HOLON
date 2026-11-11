"""The child process of `holon eval ablate` (BUILD_PLAN I53; protocol spec/M4/lib/I53_protocol.json): run one holon
command inside a scratch copy of the repository with one ablation switch applied in this process.

    python -m holon.eval.ablate_child SPEC.json

SPEC: {"patches": [name, ...], "argv": [holon argv ...], "params": {...}}. The child is started with the scratch copy
as its working directory and first on sys.path, so every holon module it imports is the scratch copy's; nothing here
writes a file of the repository the parent runs from. Each patch replaces one function or one catalog entry of the
scratch copy's modules in memory and nothing else:

  no_sort_types      derive drops every law of rule SORT's typed sub-forms (as_member, realize, reinterpret)
  no_writer_labels   holon.sorts.unions.labels gives no writer-provenance label
  two_cycles         derive drops every law of PAR's sub-forms that compare two distinct forward paths
  no_enablement      holon.analysis.closure.definitely_false is False for every check
  no_evidence        holon.diagram.evidence.build_milestone gives no atom at any level (the evidence set is empty);
                     the scratch copy's gen/<M>/evidence.json is rewritten from the patched builder (params
                     "milestones"), so derive's freshness check reads the ablated set
  budget             the controls' run budgets passed explicitly (explore.mjs, houdini.mjs, reach_search max_tries)

This module is in no generator closure (no generator imports holon.eval).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TYPED = ("as_member", "realize", "reinterpret")
OFF_PAR = ("cross_component_codec", "branch", "weak", "cycle", "recompute", "consumer", "init", "push", "go_branch",
           "go_recompute")


def _drop(pred) -> None:
    """Wrap holon.rules.compute_catalog so that the laws whose DERIVATION entry satisfies pred are not derived: their
    law, entry and registry statement are dropped and the DERIVATION text and digest recomputed."""
    import holon.rules as RU
    orig = RU.compute_catalog

    def wrapped(*a, **k):
        res = orig(*a, **k)
        gone = {e["law_id"] for e in res["derivation"]["laws"] if pred(e)}
        if not gone:
            return res
        res["laws"] = {lid: law for lid, law in res["laws"].items() if lid not in gone}
        res["derivation"]["laws"] = [e for e in res["derivation"]["laws"] if e["law_id"] not in gone]
        if "par_basis" in res["derivation"]:
            for b in res["derivation"]["par_basis"]:
                b["laws"] = [x for x in b.get("laws") or [] if x not in gone]
        res["derivation_text"] = RU.dumps(res["derivation"])
        res["registry"]["statements"] = {k2: v for k2, v in res["registry"]["statements"].items() if k2 not in gone}
        res["registry"]["derivation_sha256"] = RU.sha256_bytes(res["derivation_text"].encode("utf-8"))
        return res
    RU.compute_catalog = wrapped


def patch(name: str, params: dict) -> None:
    if name == "no_sort_types":
        _drop(lambda e: e.get("rule") == "SORT" and e.get("subform") in TYPED)
    elif name == "two_cycles":
        _drop(lambda e: e.get("rule") == "PAR" and e.get("subform") in OFF_PAR)
    elif name == "no_writer_labels":
        import holon.sorts.unions as U
        U.labels = lambda *a, **k: {}
    elif name == "no_enablement":
        import holon.analysis.closure as C
        C.definitely_false = lambda *a, **k: False
    elif name == "no_evidence":
        import holon.diagram.evidence as EV
        orig = EV.build_milestone

        def empty(*a, **k):
            doc = orig(*a, **k)
            doc["atoms"] = []
            doc["evidence_sha256"] = EV.body_sha256(doc)
            return doc
        EV.build_milestone = empty
        for m in params.get("milestones") or []:
            ep = Path("gen") / m / "evidence.json"
            if ep.is_file():
                ep.write_text(EV.render(EV.build_milestone(m, Path.cwd())), encoding="utf-8")
    elif name == "budget":
        import holon.mpipeline as MP
        run = dict(params["budget"])
        tries = int(run.pop("reach_max_tries"))
        ex, ho, rs = MP.CompiledMachine.explore, MP.CompiledMachine.houdini, MP.reach_search
        MP.CompiledMachine.explore = lambda self, law, budget=None: ex(self, law, {**run, **(budget or {})})
        MP.CompiledMachine.houdini = lambda self, budget=None: ho(self, {**run, **(budget or {})})
        MP.reach_search = lambda *a, **k: rs(*a, **{**k, "max_tries": tries})
    else:
        raise SystemExit(f"ablate_child: unknown patch {name!r}")


def main(argv: list[str]) -> int:
    spec = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    for name in spec.get("patches") or []:
        patch(name, spec.get("params") or {})
    from holon.__main__ import main as holon_main
    rc = holon_main(list(spec["argv"]))
    return int(rc or 0)


if __name__ == "__main__":
    sys.path.insert(0, str(Path.cwd()))
    sys.exit(main(sys.argv[1:]))
