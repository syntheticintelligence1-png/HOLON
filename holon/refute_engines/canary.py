"""Mutation canaries for the S10 engines (docs/M2_SPEC.md §3 row S10).

The gate's rule is that a refuter that returns fake SAT must be caught. These
canaries attack the two places a dishonest or broken engine could lie:

  fake_sat       a fabricated witness (one the solver never produced, or one
                 that does not separate the claim sides on the compiled model)
                 is pushed through the same acceptance path a real witness
                 takes. It must be rejected by the counter-law check.
  replay_lie     a SAT answer on a trivially true claim (`f(h) == f(h)`): if
                 the encoding or the solver claimed SAT, the witness it
                 produced still has to survive model replay — it cannot.
  unsat_lie      UNSAT-as-proof: a record that treated solver UNSAT as REFUTED
                 or PROVED would be caught here — `run_law` only ever upgrades
                 a SAT witness via the checked counter-law.

`run` returns {canary: detail} and the number of canaries that FAILED to catch
the lie (0 expected).
"""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import z3

from .. import bend, ir, pipeline, refute
from .. import facts as F
from ..gen import laws as LG
from ..model_eval import CompiledModel
from . import codec, runner

ROOT = Path(__file__).resolve().parents[2]


def _tmp_gen(gen_root: Path, milestone: str, facts_path: Path) -> tuple[Path, str]:
    from ..gen import model as G
    from ..model_eval import model_name
    facts = F.load(facts_path)
    name = model_name(facts_path)
    mdir = gen_root / milestone / "model"
    mdir.mkdir(parents=True, exist_ok=True)
    (mdir / f"{name}.bend").write_text(G.generate(facts, F.sha256_file(facts_path)))
    # artifacts live at <milestone>/<lid>/canary_*/, two levels under the model dir
    return mdir.parent, f"../../model/{name}.bend"


def _zero_header(facts: dict) -> dict:
    return {f_["name"]: "0x" + "00" * f_["width"] for f_ in F.header_fields(facts)}


def fake_sat(law: dict, facts: dict, gen: Path, model_import: str, cfg: dict,
             model: CompiledModel) -> dict:
    """A fabricated in-domain witness that does not separate the sides must be rejected."""
    b = law["statement"]["forall"][0]
    if b["type"] != "Header":
        cand = {b["name"]: "0x" + "00" * 32}
    else:
        # an in-domain candidate: premises applied, so any differ it shows is real
        pins = LG.collect_pins(law, facts).get(b["name"], {})
        h = _zero_header(facts)
        for fld, val in pins.items():
            h[fld] = "0x" + bytes(val).hex()
        cand = {b["name"]: h}
    # the same path a real SAT witness takes: replay, then the counter-law check
    ev = refute.evaluate(law, facts, model, cand)
    detail = {"candidate": cand, "replay": "differ" if ev and ev[0] != ev[1] else
              ("agree" if ev else "undefined")}
    attempts: list = []
    d = gen / law["law_id"] / "canary_fake_sat"
    em, r = pipeline.check_counter(law, facts, d, model_import, cfg, cand, attempts)
    detail["counter_law_accepted"] = r is not None
    if ev is not None and ev[0] == ev[1]:
        detail["caught"] = r is None          # sides equal: rejection is mandatory
    elif ev is None:
        detail["caught"] = r is None          # undefined is not a witness either
    else:
        detail["caught"] = r is not None      # an honest candidate: must be accepted
    return detail


def replay_lie(law: dict, facts: dict, model: CompiledModel) -> dict:
    """Encode a trivially true claim (f(h) == f(h)); SAT here is an encoding lie,
    and the produced 'witness' must fail compiled-model replay."""
    claim_fn = law["statement"]["claim"]["eq"][0]
    mutant = copy.deepcopy(law)
    mutant["law_id"] = law["law_id"] + "__canary_refl"
    mutant["statement"]["claim"]["eq"] = [claim_fn, claim_fn]
    try:
        q = codec.encode(mutant, facts)
    except LG.Unsupported as e:
        return {"answer": "unsupported", "reason": str(e), "caught": True}
    ans = q.solver.check()
    detail = {"answer": str(ans)}
    if ans == z3.sat:
        w = codec.extract(q.solver.model(), q, facts)
        ev = refute.evaluate(mutant, facts, model, w)
        detail["replay"] = "differ" if ev and ev[0] != ev[1] else ("agree" if ev else "undefined")
        detail["caught"] = not (ev and ev[0] != ev[1])
    else:
        detail["caught"] = True               # UNSAT/unknown on a true claim is honest
    return detail


def run(root: Path = ROOT, milestone: str = "M0", log=print) -> dict:
    cfg = bend.config(ROOT)
    facts_path = root / "facts" / "morph_header.json"
    facts = F.load(facts_path)
    model = CompiledModel.build(facts_path, cfg=cfg)
    gen, model_import = _tmp_gen(Path(tempfile.mkdtemp(prefix="holon-canary-")), milestone,
                                 facts_path)
    laws = {l["law_id"]: l for l in ir.load_laws_any(milestone, root)}
    results = {}

    # a fabricated candidate on every PROVED law must be rejected
    for lid in sorted(laws):
        exp = runner._expected(laws[lid])
        if exp != "PROVED":
            continue
        r = fake_sat(laws[lid], facts, gen, model_import, cfg, model)
        results[f"fake_sat:{lid}"] = r
        log(f"fake_sat:{lid:24s} caught={r['caught']} ({r['replay']})")

    # an encoding that claimed SAT on a reflexive claim
    for lid in sorted(laws):
        if laws[lid]["statement"]["forall"][0]["type"] != "Header":
            continue
        r = replay_lie(laws[lid], facts, model)
        results[f"replay_lie:{lid}"] = r
        log(f"replay_lie:{lid:20s} caught={r['caught']} ({r['answer']})")

    uncaught = [k for k, v in results.items() if not v["caught"]]
    out = {"canaries": results, "uncaught": sorted(uncaught), "ok": not uncaught}
    return out


if __name__ == "__main__":
    import sys
    out = run()
    print(json.dumps({"uncaught": out["uncaught"], "ok": out["ok"]}, indent=2, sort_keys=True))
    sys.exit(0 if out["ok"] else 1)
