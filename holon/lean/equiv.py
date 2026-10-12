"""Statement-equivalence harness.

For every emitted law, the Bend-compiled model and the emitted Lean model must
give the same booleans for every premise and every claim of the frozen law
statement at the same sampled assignments. This module emits a test-only Lean
file whose `#eval` lines are those booleans (one `lhs == rhs` per proposition,
per assignment) and drives the Bend side through `CompiledModel.run_jobs`
(codec facts) or `CompiledMachine.evaluate` (machine facts). Evaluation only;
nothing here changes what is proved or checked.
"""

import json
import subprocess
from pathlib import Path

import holon.model_eval as ME
from . import codec as LC
from . import laws01 as L1
from . import laws02 as L2
from . import machine as LM

LEAN = str(Path.home() / ".elan" / "bin" / "lean")


def _bytes_list(v) -> str:
    if isinstance(v, str):
        v = [int(v[2 + i:4 + i], 16) for i in range(0, len(v) - 2, 2)]
    return "[" + ", ".join(str(int(x)) for x in v) + "]"


def hdr_lit(facts: dict, h: dict) -> str:
    """Lean literal of a chunked `Hdr` from {field: "0x.."} in facts order."""
    cells = []
    for f in __import__("holon.facts", fromlist=["header_fields"]).header_fields(facts):
        b = bytes.fromhex(h[f["name"]][2:])
        if len(b) != f["width"]:
            raise ValueError(f"{f['name']}: {len(b)} bytes != {f['width']}")
        cells += list(b)
    chs = [cells[i:i + LC.CHUNK] for i in range(0, len(cells), LC.CHUNK)]
    inner = ", ".join("⟨" + ", ".join(str(x) for x in ch) + "⟩" for ch in chs)
    return f"⟨{inner}⟩"


def codec_env(facts: dict, law: dict, w: dict) -> dict:
    env = {}
    for b in law["statement"]["forall"]:
        v = w[b["name"]]
        if b["type"] == "Header":
            env[b["name"]] = f"({hdr_lit(facts, v)} : Hdr)"
        else:
            env[b["name"]] = f"({_bytes_list(v)} : List Nat)"
    return env


def codec_props(law: dict) -> tuple[list, list]:
    st = law["statement"]
    assume = list(st.get("assume", []))
    claims = st["claim"]["all"] if "all" in st["claim"] else [st["claim"]]
    return assume, claims


def codec_eval_lem(facts: dict, law: dict, mtxt: str, assignments: list) -> tuple[str, int]:
    """Lean eval file for an ir/0.1 law; returns (text, n_props_per_sample)."""
    assume, claims = codec_props(law)
    lines = [mtxt, "", "-- statement-equivalence evals (test-generated)", ""]
    for si, w in enumerate(assignments):
        env = codec_env(facts, law, w)
        for kind, props in (("p", assume), ("c", claims)):
            for i, p in enumerate(props):
                a, b = p["eq"]
                lines.append(f"#eval (({L1.term(a, env, facts)}) == ({L1.term(b, env, facts)}))  -- s{si}{kind}{i}")
    return "\n".join(lines) + "\n", len(assume) + len(claims)


def codec_bend_bools(facts_path: Path, law: dict, assignments: list) -> list[bool]:
    """Bend booleans for each prop, in the same order codec_eval_lem emits."""
    m = ME.CompiledModel.build(facts_path)
    types = {b["name"]: b["type"] for b in law["statement"]["forall"]}
    assume, claims = codec_props(law)
    jobs, keys = [], []
    for si, w in enumerate(assignments):
        env = {n: ME.value_in(types[n], w[n], m.facts) for n in types}
        for props in (assume, claims):
            for p in props:
                jobs.append({"terms": [p["eq"][0], p["eq"][1]], "env": env})
    outs = m.run_jobs(jobs)
    return [a == b for a, b in outs]


def machine_eval_lem(emit: L2.LEmit, law: dict, mtxt: str, defs: list,
                     assignments: list) -> tuple[str, int]:
    st = law["statement"]
    binders = [(L2.ln(b["name"]), b["name"], b["type"]) for b in st["binders"]]
    types = {n: t for n, _, t in binders}
    assume = st.get("assume", [])
    claims = st["claim"]["all"] if "all" in st["claim"] else [st["claim"]]
    lines = [mtxt, "", *defs, "", "-- statement-equivalence evals (test-generated)", ""]
    for si, w in enumerate(assignments):
        env = {n: emit.value_literal(t, w[orig]) for n, orig, t in binders}
        for kind, props in (("p", assume), ("c", claims)):
            for i, p in enumerate(props):
                a, b, _ = emit.prop(p, env, types)
                lines.append(f"#eval (({a}) == ({b}))  -- s{si}{kind}{i}")
    return "\n".join(lines) + "\n", len(assume) + len(claims)


def run_lean_eval(path: Path, n_expect: int, timeout: int = 600) -> list[bool]:
    p = subprocess.run([LEAN, str(path)], capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"lean eval failed ({path.name}): {p.stderr[:2500]}")
    outs = [x.strip() for x in p.stdout.splitlines() if x.strip() in ("true", "false")]
    if len(outs) != n_expect:
        raise RuntimeError(f"{path.name}: expected {n_expect} bool evals, got {outs[:12]}")
    return [x == "true" for x in outs]


# ------------------------------------------------------------ sampling

def default_act(m: LM.Machine) -> dict:
    a = m.actions[0]
    z = {"Nat": 0, "Bool": False}
    return {"op": a["name"],
            **{n: (z[t] if t in z else []) for n, t in a["inputs"]}}


def samples_for(law: dict, m: LM.Machine | None, witness: dict | None) -> list[dict]:
    """Deterministic per-binder samples: the recorded witness (if any) plus
    zero/empty defaults (Nat 0 and 1)."""
    out = []
    if witness:
        out.append(witness)
    for n_val in (0, 1):
        w, ok = {}, True
        for b in law["statement"]["binders"]:
            t = b["type"]
            if t == "Nat":
                w[b["name"]] = n_val
            elif t == "Trace":
                w[b["name"]] = []
            elif t == "State":
                w[b["name"]] = {"run": []}
            elif t == "Act":
                if m is None:
                    ok = False
                    break
                w[b["name"]] = default_act(m)
            elif t == "Bytes":
                w[b["name"]] = "0x00"
            elif t == "Bool":
                w[b["name"]] = False
            else:
                ok = False
                break
        if ok and w not in out:
            out.append(w)
    return out
