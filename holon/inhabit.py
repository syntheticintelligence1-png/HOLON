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
def search_law(law: dict) -> dict:
    """The parent with its claim replaced, so any refutation the search finds satisfies the premises."""
    s = copy.deepcopy(law)
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


def _inhabit_02(law: dict, root: Path, out_dir: Path, cfg: dict, cm, out: dict) -> dict:
    from .gen import mlaws, mproofs
    if any(b["q"] != "forall" for b in law["statement"]["binders"]):
        return {**out, "bound": "not attempted: only universal laws with premises need an inhabitant"}
    r = cm.explore(search_law(law))
    w = r.get("witness")
    if w is None:
        return {**out, "bound": r.get("bound") or "no assignment satisfying the premises in the searched space"}
    syn = inhabitant_ir(law)
    imp = f"../../model/{Path(cm.source).stem}.bend"
    try:
        em = mlaws.Emitter(cm.m).emit(syn, imp, note=f"non-vacuity of {law['law_id']} ({ir.statement_hash(law)})")
    except mlaws.Unsupported as e:
        return {**out, "bound": f"inhabitant inexpressible: {e}"}
    proof = mproofs.evaluate(em, cm.m, imp, w)
    if proof is None:
        return {**out, "bound": "no evaluation proof for the inhabitant"}
    ok, why = _check(out_dir / NV, em.name, em.text, proof, cfg)
    if not ok:
        shutil.rmtree(out_dir / NV, ignore_errors=True)
        return {**out, "witness": w, "bound": why}
    states = [b["name"] for b in law["statement"]["binders"] if b["type"] == "State"]
    return {**out, "status": "inhabited", "law": _rel(out_dir / NV / "LAWS.bend", root), "witness": w,
            "reachable": all(set(w[s]) == {"run"} for s in states) if states else None,
            "degenerate": (w[states[0]] == w[states[1]]) if len(states) >= 2 else None,
            "bound": r.get("bound")}


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


def _inhabit_01(law: dict, m: str, root: Path, out_dir: Path, cfg: dict, out: dict) -> dict:
    from .gen import proofs as PG
    from .model_eval import model_name
    fpath = root / ir.load_registry(m, root).get("facts", "facts/morph_header.json")
    facts = F.load(fpath)
    binders = law["statement"]["forall"]
    pins = pins_of(law)
    if pins is None or any(b["type"] != "Header" for b in binders):
        return {**out, "bound": "premise form not supported by the holon-ir/0.1 inhabitant generator"}
    widths = F.widths(facts)
    w = {b["name"]: {f["name"]: pins.get((b["name"], f["name"]), "0x" + "00" * widths[f["name"]])
                     for f in F.header_fields(facts)} for b in binders}
    name = law_name(law["law_id"])
    lines = [f"# GENERATED by holon.inhabit: non-vacuity inhabitant of {law['law_id']} ({ir.statement_hash(law)}).",
             "import Base", f"import ../../model/{model_name(fpath)}.bend as M", "", f"law {name}:"]
    lines += [f"  exs {b['name']}: M.Hdr" for b in binders]
    props = []
    for (v, f), hexv in sorted(pins.items()):
        bs = ", ".join(str(x) for x in bytes.fromhex(hexv[2:]))
        props.append(f"{{M.get_{f}({v}) == [{bs}] : List<&2, U32>}}")
    lines += [f"  exs c{i}: {p}" for i, p in enumerate(props[:-1])] + [f"  {props[-1]}"]
    laws_text = "\n".join(lines) + "\n"
    parts = [PG.literal("Header", w[b["name"]], facts) for b in binders] + ["{==}"] * len(props)
    tup = parts[-1]
    for p in reversed(parts[:-1]):
        tup = f"({p}, {tup})"
    proof = "\n".join(["# GENERATED by holon.inhabit; accepted only if Bend checks it.", "import Base",
                       f"import ../../model/{model_name(fpath)}.bend as M", "import ./LAWS.bend as Laws", "",
                       "# class evaluate: the pin header, then every premise by computation",
                       f"def Laws.{name}():", f"  {tup}"]) + "\n"
    ok, why = _check(out_dir / NV, name, laws_text, proof, cfg)
    if not ok:
        shutil.rmtree(out_dir / NV, ignore_errors=True)
        return {**out, "witness": w, "bound": why}
    return {**out, "status": "inhabited", "law": _rel(out_dir / NV / "LAWS.bend", root), "witness": w,
            "reachable": None, "degenerate": None, "bound": "pins with zeros elsewhere"}


# ---------------------------------------------------------------- G11V
def premise_mismatch(law: dict, m: str, root: Path, laws_text: str) -> str | None:
    """None when the inhabitant states exactly the parent's premises, else why not."""
    name = law_name(law["law_id"])
    if _LAW.findall(laws_text) != [name]:
        return f"states {_LAW.findall(laws_text)}, expected [{name}]"
    body = laws_text[laws_text.index(f"law {name}:"):]
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
        p = Path(nv["law"])
        p = p if p.is_absolute() else gate.root / p
        if not p.exists() or not (p.parent / "PROOF.bend").exists():
            bad.append(f"{lid}: inhabitant files missing")
            continue
        why = premise_mismatch(law, gate.m, gate.root, p.read_text())
        if why:
            bad.append(f"{lid}: inhabitant {why}")
            continue
        r = bend.check(p.parent / "PROOF.bend", gate.cfg)
        if not r.ok:
            bad.append(f"{lid}: inhabitant rejected by bend: {r.first_line}")
            continue
        if bend.verdict_enabled(gate.cfg):
            v = bend.check_verdict(p.parent / "PROOF.bend", gate.cfg)
            if not v.ok:
                bad.append(f"{lid}: inhabitant rejected by BendTT: {v.first_line}")
                continue
        n_inh += 1
    return (not bad, f"{n_inh} premised PROVED laws inhabited (dual-checked), {n_cw} premised REFUTED laws inhabited "
                     "by their counter-law witnesses" if not bad else "; ".join(bad))
