"""The M0 law set of one unit (instrument law_sets.M0, kill_criterion, replay.hits, replay.partiality,
replay.model_tied, equivalence.contradictions): the 8 laws/M0 statements decided on the unit's projected header
document by `holon run --milestone M0 --no-registry`, then, per law, the model hits, their replay on the unit's code and
on the original code, the recorded witness and its Bend-checked counter-law, the baseline generator's proof attempt
with the generated model checked alone, and the K2 (c) search.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .. import bend, ir
from .. import refute as R
from ..gen import laws as LG
from ..gen import proofs as PG
from ..model_eval import CompiledModel, ModelError, value_in
from ..pipeline import law_names
from . import common as C
from . import decide as D

MODEL_NAME = "morph_header"            # the M0 inhabit step imports model/<stem>.bend (facts/morph_header.json's stem)
PROJECTION_KEY = C.PROJECTED.as_posix()


def laws(root: Path) -> dict:
    return {p.stem: json.loads(p.read_text()) for p in sorted((Path(root) / "laws" / "M0").glob("L_*.json"))}


def compiled(facts_path: Path, work: Path) -> CompiledModel:
    src = Path(work) / "eval" / f"{MODEL_NAME}.bend"
    return CompiledModel.build(facts_path, source=src)


def candidates(law: dict, facts: dict) -> list:
    """holon.refute's candidates with the law's pins, in its order: [(label, env)]; labels made unique in order."""
    out, seen = [], {}
    for label, env in R.candidates(law, facts, LG.collect_pins(law, facts)):
        k = seen.get(label, 0)
        seen[label] = k + 1
        out.append((label if k == 0 else f"{label}#{k}", env))
    return out


def model_values(law: dict, facts: dict, model: CompiledModel, envs: list) -> list:
    """The claim's (lhs, rhs) on the compiled model at each env, None where some subterm is undefined (the refuter's
    own test, holon.refute._decode)."""
    types, terms, res_t, sub_t = R._jobs_terms(law, facts)
    out = []
    for i in range(0, len(envs), 256):
        chunk = envs[i:i + 256]
        jobs = [{"terms": terms, "env": {v: value_in(types[v], env[v], facts) for v in types}} for env in chunk]
        for vals in model.run_jobs(jobs):
            try:
                out.append(R._decode(vals, res_t, sub_t))
            except (ValueError, ModelError):
                out.append(None)
    return out


def hits(law: dict, facts: dict, model: CompiledModel, cands: list, limit: int) -> list:
    """The model hits (replay.hits): candidates where the claim is false with every subterm defined, in order."""
    vals = model_values(law, facts, model, [env for _, env in cands])
    out = []
    for (label, env), v in zip(cands, vals):
        if v is not None and v[0] != v[1]:
            out.append((label, env))
            if len(out) == limit:
                break
    return out


def claim_true(v) -> bool | None:
    """True holds, False falsified, None undefined (a model value from model_values)."""
    if v is None:
        return None
    return v[0] == v[1]


def counter_law(law: dict, facts: dict, gen_dir: Path, env: dict) -> dict:
    """The Bend-checked counter-law of a witness (holon.gen.proofs.counter; the pipeline's refute_law check)."""
    d = Path(gen_dir) / f"{law['law_id']}.i61_counter"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    model_import = f"../model/{MODEL_NAME}.bend"
    em = LG.emit(law, facts, model_import, counter=True, header_note=ir.statement_hash(law))
    text = PG.counter(em, facts, model_import, env)
    (d / "LAWS.bend").write_text(em.text)
    (d / "PROOF.bend").write_text(text)
    r = bend.check(d / "PROOF.bend")
    ok = r.ok and law_names(em.text) == [em.name] and not bend.escape_hatches(text + em.text)
    marker = r.marker if ok or r.marker != D.MARK_OK else "rejected"
    return {"exit_code": r.code, "marker": marker}


def proof_attempt(law: dict, facts: dict, gen_dir: Path, generator: str) -> dict:
    """K2 (b): the baseline generator's attempt on the unit's generated model, its exit code and the first line of the
    checker's output (verdict: that line when it is one of the two markers). A generator that returns None or an
    unsupported statement gives exit_code None and the reason."""
    fns = dict(PG.GENERATORS)
    d = Path(gen_dir) / f"{law['law_id']}.i61_proof"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    model_import = f"../model/{MODEL_NAME}.bend"
    out = {"generator": generator, "exit_code": None, "marker": "not_run", "verdict": None, "model_verdict": None,
           "why": None}
    if generator not in fns:
        out["why"] = f"no proof generator named {generator}"
        return out
    try:
        em = LG.emit(law, facts, model_import, header_note=ir.statement_hash(law))
        text = fns[generator](em, facts, model_import)
    except LG.Unsupported as e:
        out["why"] = f"unsupported statement form: {e}"
        return out
    if text is None:
        out["why"] = "the generator returned None"
        return out
    (d / "LAWS.bend").write_text(em.text)
    (d / "PROOF.bend").write_text(text)
    r = bend.check(d / "PROOF.bend")
    out["exit_code"] = r.code
    out["marker"] = r.marker
    out["verdict"] = r.first_line if r.first_line in (D.MARK_OK, D.MARK_FAIL) else None
    if r.code is None:
        out["why"] = "timeout"
    elif out["verdict"] is None:
        out["why"] = "no verdict line: " + C.scrub(r.first_line)[:200]
    ok = r.ok and law_names(em.text) == [em.name] and not bend.escape_hatches(text + em.text)
    if r.marker == D.MARK_OK and not ok:
        out["why"] = "the checker accepted a file that is not this law's proof"
    return out


def model_verdict(model_bend: Path) -> str | None:
    """The generated model module checked alone (its definitions, no law): the first line of the checker's output when
    it is a verdict marker, else None (K2 (b))."""
    r = bend.check(Path(model_bend))
    return r.first_line if r.first_line in (D.MARK_OK, D.MARK_FAIL) else None


def premises_hold(law: dict, env: dict) -> bool:
    """The law's premises at a candidate (each premise an eq of a field of a binder and a constant)."""
    for p in law["statement"].get("assume", []):
        eq = p.get("eq")
        if not eq or len(eq) != 2:
            return False
        a, b = eq
        if "field" in a and "bytes" in b and "var" in a.get("of", {}):
            v = env.get(a["of"]["var"], {})
            if not isinstance(v, dict) or str(v.get(a["field"], "")).lower() != b["bytes"].lower():
                return False
        else:
            return False
    return True


def fits(header: dict, doc: dict) -> bool:
    """An enc_sol call's Header fits an entry point (equivalence.contradictions, entry-fit): no revert path of the null
    document's enc_sol holds at it, and every field value fits the extracted Header's value_bits."""
    fields = {f["name"]: f for f in doc["types"]["Header"]["fields"]}
    vals = {}
    for name, f in fields.items():
        x = header.get(name)
        if not isinstance(x, str) or not x.startswith("0x"):
            return False
        vals[name] = int(x[2:] or "0", 16)
        if vals[name] >= (1 << f["value_bits"]):
            return False
    for p in doc["functions"]["enc_sol"]["paths"]:
        if p.get("outcome") == "revert" and all(_cond(c, vals) for c in p.get("cond", [])):
            return False
    return True


def _term(t, vals):
    if isinstance(t, int):
        return t
    if isinstance(t, str):
        return vals[t]
    raise ValueError(t)


def _cond(c, vals) -> bool:
    op = c[0]
    if op == "!":
        return not _cond(c[1], vals)
    a, b = _term(c[1], vals), _term(c[2], vals)
    return {"<=": a <= b, "<": a < b, ">=": a >= b, ">": a > b, "==": a == b, "!=": a != b}[op]
