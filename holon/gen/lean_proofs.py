"""Lean 4 proof generators and file assembly (I9). Untrusted: a file counts only if Lean accepts it.

One self-contained file per law: the model (holon.gen.lean_model), the statement (holon.gen.lean_laws,
statement hash in the doc comments) and a proof from one generator per class of obligation:

  pin_reduce      PROVED laws whose premises fix header fields (`h.f == bytes`): open every Header
                  binder into its byte fields, turn each premise into per-byte equations with `simp only`
                  (List/Option injectivity lemmas, no arithmetic), substitute them, and close the goal by
                  `rfl`: both sides then reduce to the same symbolic cell list.
  counter_decide  REFUTED laws: the counter-law ∃ x, premises ∧ lhs ≠ rhs at the recorded witness (the
                  refuter found it on the compiled Bend model), each conjunct by `decide` on a closed
                  term; then the negation of the frozen law, derived from it in a few lines.

Only `rfl`, `simp only`, `cases`/`obtain` and `decide` on closed goals are emitted; never `sorry`,
`native_decide`, `bv_decide`, an axiom or `unsafe` (holon.lean re-scans the file and audits
`#print axioms`). Independent of the Bend proof generators (holon/gen/proofs.py).
"""
from __future__ import annotations

from .lean_laws import CLAIM_MARK, LeanLaw, counter_prop, doc, law_prop, witness_name, witness_term
from .lean_model import NS, LeanUnsupported, emit_model, header_layout

# rfl on a 257-cell list exceeds the default maxRecDepth (512); BUILD_PLAN §1.4 probe: 20000 passes.
MAX_REC_DEPTH = 20000


def _encoder_calls(t, facts: dict, out: list) -> list:
    """(fn, var) for every encoder applied directly to a binder in an IR term, in first-use order."""
    if isinstance(t, dict):
        if "call" in t and facts["functions"].get(t["call"], {}).get("kind") == "encoder" \
                and len(t.get("args", [])) == 1 and set(t["args"][0]) == {"var"}:
            k = (t["call"], t["args"][0]["var"])
            if k not in out:
                out.append(k)
        for v in t.values():
            _encoder_calls(v, facts, out)
    elif isinstance(t, list):
        for v in t:
            _encoder_calls(v, facts, out)
    return out


def encoder_hint(facts: dict, fn: str, cell: dict[str, str]) -> list[str] | None:
    """Untrusted proof hint: the cells `fn` outputs on a header whose byte terms are `cell` (field_k -> Lean
    byte term), as Lean cell terms. Lean re-derives it by `rfl` from the model's definition, so a wrong hint
    only makes the proof fail. None when the output depends on an unpinned version byte."""
    f = facts["functions"][fn]
    widths = dict(header_layout(facts))

    def src(op) -> list[str]:
        cs: list[str] = []
        for item in op["src"]:
            if "field" in item:
                cs += [f"some {cell[f'{item['field']}_{k}']}" for k in range(widths[item["field"]])]
            elif "zeros" in item:
                cs += ["some 0x00"] * int(item["zeros"])
            else:
                cs.append(f"some 0x{int(item['const']):02x}")
        return cs

    def run(mem: list[str], ops: list) -> list[str]:
        for op in ops:
            cs = src(op)
            o = int(op["offset"])
            mem[o:o + len(cs)] = cs[:max(0, len(mem) - o)]
        return mem

    if f["lang"] == "go-bytes":
        return run(["some 0x00"] * int(f["length"]), f["ops"])
    v_term = cell.get("version_0", "")
    if not v_term.startswith("0x"):
        return None
    v = int(v_term, 16)
    if v > int(f["domain"]["version_le"]):
        return ["none"]
    lens = {int(k): int(n) for k, n in f["length_by_version"].items()}
    size = max([max(lens.values())] + [int(op["offset"]) + len(src(op)) for op in f["ops"]])
    ops = [op for op in f["ops"] if not op.get("when") or v >= int(op["when"]["version_ge"])]
    return run(["none"] * size, ops)[:lens[v]]


def proof_pin_reduce(ll: LeanLaw, law: dict, facts: dict) -> list[str] | None:
    if any(t != "Header" for _, t in ll.binders) or any(p is None for p in ll.premise_pins):
        return None
    lay = header_layout(facts)
    pinned: dict[str, dict[str, int]] = {n: {} for n, _ in ll.binders}
    for var, fld, bs in ll.premise_pins:
        for k, b in enumerate(bs):
            if pinned[var].setdefault(f"{fld}_{k}", b) != b:
                return None  # contradictory premises: vacuous, never "proved" this way
    # the byte terms of each binder once opened and its pinned bytes substituted
    cell = {var: {f"{n}_{k}": (f"0x{pinned[var][f'{n}_{k}']:02x}" if f"{n}_{k}" in pinned[var] else f"{var}_{n}_{k}")
                  for n, w in lay for k in range(w)} for var, _ in ll.binders}
    hyps = [f"p{i}" for i in range(len(ll.premises))]
    lines = ["  intro " + " ".join([n for n, _ in ll.binders] + hyps)]
    for var, _ in ll.binders:  # open the record into its byte fields
        lines.append(f"  obtain ⟨{', '.join(f'{var}_{n}_{k}' for n, w in lay for k in range(w))}⟩ := {var}")
    if hyps:  # each premise becomes per-byte equations, substituted away
        getters = sorted({f"{NS}.Hdr.get_{f}" for _, f, _ in ll.premise_pins})
        lines.append(f"  simp only [{', '.join(getters)}, List.cons.injEq, Option.some.injEq, and_true] at "
                     + " ".join(hyps))
        done: set[tuple[str, str]] = set()
        for h, (var, fld, bs) in zip(hyps, ll.premise_pins):
            if (var, fld) in done:
                lines.append(f"  clear {h}")
                continue
            done.add((var, fld))
            pat = "rfl" if len(bs) == 1 else "⟨" + ", ".join(["rfl"] * len(bs)) + "⟩"
            lines.append(f"  obtain {pat} := {h}")
    # per-cell lemmas: each encoder output on the opened header, cell by cell (checked by rfl), so the
    # final rfl compares cell lists instead of re-running the write sequence under every getter
    eqs = []
    for fn, var in _encoder_calls(law["statement"]["claim"], facts, []):
        cells = encoder_hint(facts, fn, cell[var])
        if cells is None:
            continue
        args = ", ".join(cell[var][f"{n}_{k}"] for n, w in lay for k in range(w))
        e = f"e{len(eqs)}"
        lines.append(f"  have {e} : {NS}.{fn} ⟨{args}⟩ = [{', '.join(cells)}] := rfl")
        eqs.append(e)
    if eqs:  # `rewrite`, not `rw`: no implicit rfl, so the closing rfl below is always the step that decides
        lines.append(f"  rewrite [{', '.join(eqs)}]")
    lines.append("  rfl")
    return lines


PROOF_GENERATORS = [("pin_reduce", proof_pin_reduce)]


def law_block(ll: LeanLaw, law: dict, rendered: str, facts: dict) -> tuple[list[str], str] | None:
    """The theorem stating the frozen law, with the first generator's proof (None if none applies)."""
    for gname, gen in PROOF_GENERATORS:
        body = gen(ll, law, facts)
        if body is not None:
            return [doc(ll, law, rendered), f"theorem {ll.name} :"] + law_prop(ll) + ["    := by"] + body, gname
    return None


def counter_block(ll: LeanLaw, law: dict, rendered: str, witness: dict, facts: dict) -> list[str]:
    names = [n for n, _ in ll.binders]
    if not isinstance(witness, dict) or set(witness) != set(names):
        raise LeanUnsupported(f"the recorded witness binds {sorted(witness or {})}, the law binds {names}")
    out = []
    for n, _ in ll.binders:
        ty = {"Header": f"{NS}.Hdr", "Bytes": f"{NS}.Bytes"}[dict(ll.binders)[n]]
        # noncomputable: Lean's code generator rejects constructors with more than 256 fields; the
        # definition is only ever reduced by the elaborator and the kernel, never compiled
        out += [f"/-- The witness for `{n}`, as recorded in the law's result record (the refuter found it on the "
                "compiled Bend model). -/",
                f"noncomputable def {witness_name(ll, n)} : {ty} :=", f"  {witness_term(ll, n, witness[n], facts)}", ""]
    ws = ", ".join(witness_name(ll, n) for n in names)
    decides = ", ".join(["by decide"] * (len(ll.premises) + 1))
    out += [doc(ll, law, rendered).replace(" -/", "\nCounter-law: the premises hold and the claim fails at the "
                                                  "recorded witness. -/"),
            f"theorem {ll.counter_name} :"] + counter_prop(ll) + [f"    := ⟨{ws}, {decides}⟩", ""]
    hyps = [f"p{i}" for i in range(len(ll.premises))]
    out += [f"/-- The frozen law {ll.law_id} is false (from {ll.counter_name}). -/",
            f"theorem {ll.refuted_name} :", "    ¬ ("]
    out += law_prop(ll, indent="      ", mark=False)
    out += ["    ) := by", "  intro hall",
            f"  obtain ⟨{', '.join(names + hyps + ['hne'])}⟩ := {ll.counter_name}",
            f"  exact hne (hall {' '.join(names + hyps)})"]
    return out


def emit_file(law: dict, facts: dict, facts_sha256: str, ll: LeanLaw, verdict: str, rendered: str,
              witness: dict | None = None) -> tuple[str, dict]:
    """(Lean source, info) re-checking `verdict` (PROVED: the law; REFUTED: the counter-law at `witness`).

    info: {"theorems": [names to audit], "main": the theorem that carries the verdict, "generator": class}."""
    if verdict == "PROVED":
        blk = law_block(ll, law, rendered, facts)
        if blk is None:
            raise LeanUnsupported("no Lean proof generator applies to this statement")
        body, gname = blk
        theorems, main = [ll.name], ll.name
    elif verdict == "REFUTED":
        body, gname = counter_block(ll, law, rendered, witness, facts), "counter_decide"
        theorems, main = [ll.counter_name, ll.refuted_name], ll.counter_name
    else:
        raise LeanUnsupported(f"verdict {verdict!r} has nothing to re-check")
    head = ["/-!", "GENERATED by holon.gen.lean_proofs (I9) from the frozen law IR and the facts; do not edit",
            "(fix the generator instead).", f"law_id: {ll.law_id}", f"statement_hash: {ll.statement_hash}",
            f"facts_sha256: {facts_sha256}",
            f"re-checks: {verdict} ({'the law' if verdict == 'PROVED' else 'the counter-law at the recorded witness'})"
            f", proof class {gname}", "Lean 4 core only, no imports.", "-/",
            f"set_option maxRecDepth {MAX_REC_DEPTH}", ""]
    text = "\n".join(head + [emit_model(facts, facts_sha256).rstrip(), ""] + body + [""]
                     + [f"#print axioms {t}" for t in theorems]) + "\n"
    if text.count(CLAIM_MARK) != 1:
        raise LeanUnsupported("the emitted file must mark exactly one main claim")
    return text, {"theorems": theorems, "main": main, "generator": gname}
