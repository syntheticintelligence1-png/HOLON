"""Non-vacuity inhabitants (whitepaper §12.3 and L21; gate G11V).

A law with unsatisfiable premises is true and useless. Every PROVED law that has premises
needs a kernel-checked inhabitant: an existential law, generated from the parent's frozen
IR, whose claim is the conjunction of the parent's premises, proved at a concrete witness.

  holon-ir/0.2  the parent's binders made existential and its premises as the claim,
                emitted by the same emitter (holon.gen.mlaws), so the premise texts are
                the parent's; proved by evaluation (holon.gen.mproofs.evaluate). The
                witness comes from the compiled model's search (holon/js/explore.mjs) run
                on the parent with its claim replaced: `s_a == s_b` when two binders are
                states (so a found inhabitant is non-degenerate), else `true == false`.
  holon-ir/0.1  the premises are pins of header fields; the inhabitant states them through
                the model's getters, `M.get_<field>(h) == [bytes]`, at the header carrying
                the pin bytes and zeros elsewhere.

A REFUTED law needs nothing more: its accepted counter-law already inhabits its premises.
The non_vacuity record: {status, law, witness, reachable, degenerate, parent_statement_hash,
bound}, with status inhabited | counter_witness | no_premises | unknown.
"""
from __future__ import annotations

import copy
import re
import shutil
from pathlib import Path

from . import bend, ir
from . import facts as F

ROOT = Path(__file__).resolve().parents[1]
NV = "nonvac"
_LAW = re.compile(r"^law\s+([A-Za-z0-9_.]+)\s*:", re.M)
_GETTER = re.compile(r"\{M\.get_(\w+)\((\w+)\) == \[([0-9, ]*)\] : List<&2, U32>\}")


def premised(law: dict) -> bool:
    return bool(law["statement"].get("assume"))


def law_name(law_id: str) -> str:
    return "nv_" + law_id.lower()


def _rel(p: Path, root: Path) -> str:
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(p)


def _base(rec: dict) -> dict:
    return {"status": "unknown", "law": None, "witness": None, "reachable": None, "degenerate": None,
            "parent_statement_hash": rec["statement_hash"], "bound": None}


def inhabit(law: dict, m: str, root: Path, out_dir: Path, cfg: dict, cm=None, rec: dict | None = None) -> dict:
    """The non_vacuity record of a law whose result record `rec` is finished."""
    root, out_dir = Path(root), Path(out_dir)
    out = _base(rec)
    shutil.rmtree(out_dir / NV, ignore_errors=True)
    if not premised(law):
        return {**out, "status": "no_premises"}
    if rec["status"] == "REFUTED":
        return {**out, "status": "counter_witness", "law": rec.get("artifacts", {}).get("laws"),
                "bound": "the accepted counter-law inhabits the premises"}
    if rec["status"] != "PROVED":
        return {**out, "bound": "not attempted: the law is not PROVED"}
    if law["ir_version"] == "holon-ir/0.1":
        return _inhabit_01(law, m, root, out_dir, cfg, out)
    return _inhabit_02(law, root, out_dir, cfg, cm, out)


def _check(d: Path, name: str, laws_text: str, proof_text: str, cfg: dict) -> tuple[bool, str]:
    d.mkdir(parents=True, exist_ok=True)
    (d / "LAWS.bend").write_text(laws_text)
    (d / "PROOF.bend").write_text(proof_text)
    if _LAW.findall(laws_text) != [name] or bend.escape_hatches(laws_text + proof_text):
        return False, "inhabitant file states another law or uses an escape hatch"
    r = bend.check(d / "PROOF.bend", cfg)
    if not r.ok:
        return False, f"bend rejected the inhabitant: {r.first_line} {r.out[:300]}"
    if bend.verdict_enabled(cfg):
        v = bend.check_verdict(d / "PROOF.bend", cfg)
        if not v.ok:
            return False, f"BendTT rejected the inhabitant: {v.first_line}"
    return True, ""


# ---------------------------------------------------------------- holon-ir/0.2
DEFAULTS = {"Trace": [], "Nat": 0, "Bool": False}


def _vars(t) -> set[str]:
    if isinstance(t, dict):
        return ({t["var"]} if "var" in t else set()) | set().union(*(_vars(v) for v in t.values()))
    if isinstance(t, list):
        return set().union(*(_vars(v) for v in t)) if t else set()
    return set()


def free_binders(law: dict) -> list[dict]:
    """Binders no premise mentions and whose type has a default value: any value inhabits them."""
    used = _vars(law["statement"].get("assume", []))
    return [b for b in law["statement"]["binders"] if b["name"] not in used and b["type"] in DEFAULTS]


def search_law(law: dict) -> dict:
    """The parent with its claim replaced, so any refutation the search finds satisfies the premises;
    binders no premise mentions are left out of the search (they get default values)."""
    s = copy.deepcopy(law)
    free = {b["name"] for b in free_binders(law)}
    s["statement"]["binders"] = [b for b in s["statement"]["binders"] if b["name"] not in free]
    states = [b["name"] for b in s["statement"]["binders"] if b["type"] == "State"]
    if len(states) >= 2:
        s["statement"]["claim"] = {"eq": [{"var": states[0]}, {"var": states[1]}]}
    else:
        s["statement"]["claim"] = {"eq": [{"bool": True}, {"bool": False}]}
    return s


def inhabitant_ir(law: dict) -> dict:
    st = law["statement"]
    prem = st["assume"]
    return {"ir_version": law["ir_version"], "law_id": "NV_" + law["law_id"], "rule": law["rule"],
            "facts": law.get("facts"), "facts_sha256": law["facts_sha256"],
            "statement": {"binders": [{"q": "exists", "name": b["name"], "type": b["type"]} for b in st["binders"]],
                          "claim": {"all": prem} if len(prem) > 1 else prem[0]}}


MODEL_IMPORT = "../../model/{}.bend"   # an inhabitant lives in <gen>/<law>/nonvac/, the model in <gen>/model/


def texts_02(law: dict, machine, model_stem: str, witness: dict) -> tuple[str, str, str]:
    """(law name, LAWS.bend, PROOF.bend) of a holon-ir/0.2 inhabitant: a pure function of the frozen
    IR, the model and the witness, so G11V can regenerate and compare both files."""
    from .gen import mlaws, mproofs
    imp = MODEL_IMPORT.format(model_stem)
    em = mlaws.Emitter(machine).emit(inhabitant_ir(law), imp,
                                     note=f"non-vacuity of {law['law_id']} ({ir.statement_hash(law)})")
    proof = mproofs.evaluate(em, machine, imp, witness)
    if proof is None:
        raise ValueError("no evaluation proof for the inhabitant")
    return em.name, em.text, proof


def degenerate(cm, law: dict, witness: dict) -> bool | None:
    """True when the first two state binders are equal, decided on the compiled model."""
    states = [b["name"] for b in law["statement"]["binders"] if b["type"] == "State"]
    if len(states) < 2:
        return None
    sl = search_law(law)
    ev = cm.evaluate(sl, {b["name"]: witness[b["name"]] for b in sl["statement"]["binders"]})
    return bool(ev["claims"][0])


def _inhabit_02(law: dict, root: Path, out_dir: Path, cfg: dict, cm, out: dict) -> dict:
    from .gen import mlaws
    if any(b["q"] != "forall" for b in law["statement"]["binders"]):
        return {**out, "bound": "not attempted: only universal laws with premises need an inhabitant"}
    sl = search_law(law)
    r = cm.explore(sl, {"noPerturb": True})  # first: only reachable states (run(p, s0))
    first = r.get("bound")
    if r.get("witness") is None:
        r = cm.explore(sl)                    # then constructed states too (recorded as unreachable)
    w = r.get("witness")
    if w is None:
        return {**out, "bound": r.get("bound") or "no assignment satisfying the premises in the searched space"}
    w = {**w, **{b["name"]: DEFAULTS[b["type"]] for b in free_binders(law)}}
    try:
        name, laws_text, proof = texts_02(law, cm.m, Path(cm.source).stem, w)
    except (mlaws.Unsupported, ValueError) as e:
        return {**out, "witness": w, "bound": f"inhabitant inexpressible: {e}"}
    ok, why = _check(out_dir / NV, name, laws_text, proof, cfg)
    if not ok:
        shutil.rmtree(out_dir / NV, ignore_errors=True)
        return {**out, "witness": w, "bound": why}
    states = [b["name"] for b in law["statement"]["binders"] if b["type"] == "State"]
    reach = all(set(w[x]) == {"run"} for x in states) if states else None
    note = r.get("bound") if reach is not False else f"no reachable inhabitant within ({first}); constructed states"
    return {**out, "status": "inhabited", "law": _rel(out_dir / NV / "LAWS.bend", root), "witness": w,
            "reachable": reach, "degenerate": degenerate(cm, law, w), "bound": note}


# ---------------------------------------------------------------- holon-ir/0.1
def pins_of(law: dict) -> dict[tuple[str, str], str] | None:
    """(binder, field) -> pinned bytes, or None when a premise is not a field pin."""
    pins = {}
    for p in law["statement"].get("assume", []):
        a, b = p["eq"]
        if "field" in b and "bytes" in a:
            a, b = b, a
        if not ("field" in a and "bytes" in b and "var" in a["of"]):
            return None
        pins[(a["of"]["var"], a["field"])] = b["bytes"]
    return pins


def pin_witness(law: dict, facts: dict) -> dict:
    widths = F.widths(facts)
    pins = pins_of(law)
    return {b["name"]: {f["name"]: pins.get((b["name"], f["name"]), "0x" + "00" * widths[f["name"]])
                        for f in F.header_fields(facts)} for b in law["statement"]["forall"]}


def texts_01(law: dict, facts: dict, model_stem: str, witness: dict) -> tuple[str, str, str]:
    """(law name, LAWS.bend, PROOF.bend) of a holon-ir/0.1 inhabitant (pins through the getters)."""
    from .gen import proofs as PG
    binders = law["statement"]["forall"]
    pins = pins_of(law)
    name = law_name(law["law_id"])
    imp = MODEL_IMPORT.format(model_stem)
    lines = [f"# GENERATED by holon.inhabit: non-vacuity inhabitant of {law['law_id']} ({ir.statement_hash(law)}).",
             "import Base", f"import {imp} as M", "", f"law {name}:"]
    lines += [f"  exs {b['name']}: M.Hdr" for b in binders]
    props = []
    for (v, f), hexv in sorted(pins.items()):
        bs = ", ".join(str(x) for x in bytes.fromhex(hexv[2:]))
        props.append(f"{{M.get_{f}({v}) == [{bs}] : List<&2, U32>}}")
    lines += [f"  exs c{i}: {p}" for i, p in enumerate(props[:-1])] + [f"  {props[-1]}"]
    parts = [PG.literal("Header", witness[b["name"]], facts) for b in binders] + ["{==}"] * len(props)
    tup = parts[-1]
    for p in reversed(parts[:-1]):
        tup = f"({p}, {tup})"
    proof = "\n".join(["# GENERATED by holon.inhabit; accepted only if Bend checks it.", "import Base",
                       f"import {imp} as M", "import ./LAWS.bend as Laws", "",
                       "# class evaluate: the pin header, then every premise by computation",
                       f"def Laws.{name}():", f"  {tup}"]) + "\n"
    return name, "\n".join(lines) + "\n", proof


def _inhabit_01(law: dict, m: str, root: Path, out_dir: Path, cfg: dict, out: dict) -> dict:
    from .model_eval import model_name
    fpath = root / ir.load_registry(m, root).get("facts", "facts/morph_header.json")
    facts = F.load(fpath)
    if pins_of(law) is None or any(b["type"] != "Header" for b in law["statement"]["forall"]):
        return {**out, "bound": "premise form not supported by the holon-ir/0.1 inhabitant generator"}
    w = pin_witness(law, facts)
    name, laws_text, proof = texts_01(law, facts, model_name(fpath), w)
    ok, why = _check(out_dir / NV, name, laws_text, proof, cfg)
    if not ok:
        shutil.rmtree(out_dir / NV, ignore_errors=True)
        return {**out, "witness": w, "bound": why}
    return {**out, "status": "inhabited", "law": _rel(out_dir / NV / "LAWS.bend", root), "witness": w,
            "reachable": None, "degenerate": None, "bound": "pins with zeros elsewhere"}


# ---------------------------------------------------------------- G11V
def _body(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#")).strip() + "\n"


def expected_texts(law: dict, m: str, root: Path, rec: dict) -> tuple[str, str, str]:
    """The inhabitant files G11V expects, regenerated from the frozen IR and the recorded witness."""
    root = Path(root)
    model = Path(rec["artifacts"]["model"]).stem
    if law["ir_version"] == "holon-ir/0.1":
        fpath = root / ir.load_registry(m, root).get("facts", "facts/morph_header.json")
        return texts_01(law, F.load(fpath), model, rec["non_vacuity"]["witness"])
    from .gen.machine import Machine
    return texts_02(law, Machine(F.load(root / law["facts"])), model, rec["non_vacuity"]["witness"])


def premise_mismatch(law: dict, m: str, root: Path, laws_text: str) -> str | None:
    """None when the inhabitant's premises are exactly the parent's (comments ignored), else why not.
    A coarse check kept for the tests; G11V compares whole regenerated files."""
    text = _body(laws_text)
    name = law_name(law["law_id"])
    if _LAW.findall(text) != [name]:
        return f"states {_LAW.findall(text)}, expected [{name}]"
    body = text[text.index(f"law {name}:"):]
    if law["ir_version"] == "holon-ir/0.1":
        got = {(v, f): "0x" + bytes(int(x) for x in bs.split(",") if x.strip()).hex()
               for f, v, bs in _GETTER.findall(body)}
        return None if got == pins_of(law) else f"pins {sorted(got)} differ from the parent's"
    from . import bindings
    parent = bindings.statement_text(law, m, root)
    want = re.findall(r"^\s+for h\d+: (\{.*\})\s*$", parent, re.M)
    got = re.findall(r"^\s+(?:exs c\d+: )?(\{.*\})\s*$", body, re.M)
    return None if got == want else "premises differ from the parent statement's"


def g11v(gate) -> tuple[bool, str]:
    """Gate check G11V over a Gate instance (holon.gate)."""
    from .mpipeline import CompiledMachine
    machines: dict = {}
    dual = bend.verdict_enabled(gate.cfg)
    bad, n_inh, n_cw = [], 0, 0
    for law in ir.load_laws_any(gate.m, gate.root):
        lid = law["law_id"]
        rec = gate.records().get(lid)
        if rec is None:
            bad.append(f"{lid}: no result record")
            continue
        nv = rec.get("non_vacuity")
        if not isinstance(nv, dict):
            bad.append(f"{lid}: no non_vacuity record")
            continue
        if nv.get("parent_statement_hash") != rec.get("statement_hash"):
            bad.append(f"{lid}: non_vacuity is for another statement")
        if not premised(law):
            if nv.get("status") != "no_premises":
                bad.append(f"{lid}: no premises, but non_vacuity says {nv.get('status')!r}")
            continue
        if rec.get("status") == "REFUTED":
            n_cw += 1
            if nv.get("status") != "counter_witness":
                bad.append(f"{lid}: REFUTED, but non_vacuity says {nv.get('status')!r}")
            continue
        if rec.get("status") != "PROVED":
            continue
        if nv.get("status") != "inhabited":
            bad.append(f"{lid}: premised PROVED law without an inhabitant ({nv.get('bound')})")
            continue
        d = gate.root / "gen" / gate.m / lid / NV
        files = sorted(f.name for f in d.iterdir()) if d.is_dir() else []
        if files != ["LAWS.bend", "PROOF.bend"]:
            bad.append(f"{lid}: inhabitant directory holds {files}, expected exactly LAWS.bend and PROOF.bend")
            continue
        try:
            name, want_laws, want_proof = expected_texts(law, gate.m, gate.root, rec)
        except Exception as e:  # noqa: BLE001
            bad.append(f"{lid}: inhabitant cannot be regenerated from its IR and witness: {e}")
            continue
        laws_text, proof_text = (d / "LAWS.bend").read_text(), (d / "PROOF.bend").read_text()
        if _body(laws_text) != _body(want_laws):
            bad.append(f"{lid}: inhabitant LAWS.bend is not the one generated from the parent's IR")
            continue
        if _body(proof_text) != _body(want_proof):
            bad.append(f"{lid}: inhabitant PROOF.bend is not the evaluation proof of the recorded witness")
            continue
        if bend.escape_hatches(laws_text + proof_text):
            bad.append(f"{lid}: inhabitant uses an escape hatch")
            continue
        states = [b["name"] for b in law["statement"].get("binders", []) if b["type"] == "State"]
        if states:
            if nv.get("reachable") is not True:
                bad.append(f"{lid}: inhabitant states are not all reachable (run(p, s0))")
                continue
            if len(states) >= 2:
                fp = gate.root / law["facts"]
                if fp not in machines:
                    machines[fp] = CompiledMachine.build(fp, gate.cfg)
                if degenerate(machines[fp], law, nv["witness"]) is not False:
                    bad.append(f"{lid}: inhabitant is degenerate (its two states are equal)")
                    continue
        r = bend.check(d / "PROOF.bend", gate.cfg)
        if not r.ok:
            bad.append(f"{lid}: inhabitant rejected by bend: {r.first_line}")
            continue
        if dual:
            v = bend.check_verdict(d / "PROOF.bend", gate.cfg)
            if not v.ok:
                bad.append(f"{lid}: inhabitant rejected by BendTT: {v.first_line}")
                continue
        n_inh += 1
    kernels = "dual-checked" if dual else "single-kernel: BendTT unavailable"
    return (not bad, f"{n_inh} premised PROVED laws inhabited ({kernels}; regenerated from the IR and witness; "
                     f"reachable and non-degenerate where states are involved), {n_cw} premised REFUTED laws inhabited "
                     "by their counter-law witnesses" if not bad else "; ".join(bad))
