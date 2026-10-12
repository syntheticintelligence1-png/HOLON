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

  oracle parameters (I12, holon.gen.oracles)  a parameter that a hypothesis premise constrains (a cf
                premise over it, or a hyp premise naming a hypothesis of it) takes the concrete instance of
                the entry whose hypothesis it is, and only that: the search may not pick another value.
                The witness records it as {"instance": <entry id>}; the proof supplies the instance's
                table at the points the premises query (premise_points), the instance defined in the proof
                from the entry's template. A parameter no premise mentions takes the empty table. An
                instance that violates its hypothesis yields no inhabitant (status unknown).

A REFUTED law needs nothing more: its accepted counter-law already inhabits its premises.
The non_vacuity record: {status, law, witness, reachable, degenerate, parent_statement_hash,
bound}, with status inhabited | counter_witness | no_premises | unknown.
"""
from __future__ import annotations

import copy
import json
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
    """A law has premises when it assumes something, or quantifies over Reach (I8: Reach(s) is a premise)."""
    st = law["statement"]
    return bool(st.get("assume")) or any(b.get("type") == "Reach" for b in st.get("binders", []))


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


def inhabit(law: dict, m: str, root: Path, out_dir: Path, cfg: dict, cm=None, rec: dict | None = None,
            entries: list[str] | None = None) -> dict:
    """The non_vacuity record of a law whose result record `rec` is finished. entries: a SORT-site law's entry points
    (I15), where the at_site inhabitant is searched."""
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
    if site_id(law) is not None:
        return _inhabit_site(law, root, out_dir, cfg, cm, out, entries or [])
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
EMPTY_TABLE = {"table": []}   # the default value of an oracle parameter (I12)


def _vars(t) -> set[str]:
    if isinstance(t, dict):
        return ({t["var"]} if "var" in t else set()) | set().union(*(_vars(v) for v in t.values()))
    if isinstance(t, list):
        return set().union(*(_vars(v) for v in t)) if t else set()
    return set()


def _is_param(b: dict, machine) -> bool:
    return machine is not None and b["name"] in getattr(machine, "oparams", {}) and str(b["type"]).startswith("Fn<")


def _mentioned_params(law: dict, machine) -> set[str]:
    """Oracle parameters the premises mention: applied, the function of a cf premise, or a hyp premise's (I12)."""
    if machine is None or not getattr(machine, "oparams", None):
        return set()
    out: set = set()

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("app"), str):
                out.add(x["app"])
            if isinstance(x.get("cf"), dict):
                out.add(x["cf"].get("fn"))
            if isinstance(x.get("hyp"), dict) and machine.orc is not None:
                e = machine.orc.hyp_entry(x["hyp"].get("name"))
                if e is not None:
                    out.add(e["parameter"]["name"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(law["statement"].get("assume", []))
    return out


def free_binders(law: dict, machine=None) -> list[dict]:
    """Binders no premise mentions and whose type has a default value: any value inhabits them. With the
    machine of a parametric model (I12), an oracle parameter no premise mentions is free too (the empty table)."""
    used = _vars(law["statement"].get("assume", [])) | _mentioned_params(law, machine)
    return [b for b in law["statement"]["binders"] if b["name"] not in used
            and (b["type"] in DEFAULTS or _is_param(b, machine))]


def default_of(b: dict, machine=None):
    return EMPTY_TABLE if _is_param(b, machine) else DEFAULTS[b["type"]]


def constrained_instances(law: dict, machine) -> dict:
    """{parameter: {"instance": entry id}} for every oracle parameter a hypothesis premise constrains: the
    instance of the entry whose hypothesis it is (I12). ValueError when a parameter has none, or two."""
    orc = getattr(machine, "orc", None)
    out: dict = {}
    for p in law["statement"].get("assume", []):
        if "hyp" in p:
            e = orc.hyp_entry(p["hyp"]["name"]) if orc is not None else None
            if e is None:
                raise ValueError(f"hyp premise {p['hyp']['name']!r} names no modelled hypothesis")
        elif "cf" in p and orc is not None and p["cf"].get("fn") in machine.oparams:
            e = orc.cf_entry(p["cf"]["fn"])
            if e is None:
                raise ValueError(f"cf premise over {p['cf']['fn']}: the parameter has no kind-cf entry")
        else:
            continue
        par = e["parameter"]["name"]
        if e not in orc.instances(par):
            raise ValueError(f"entry {e['id']} has no concrete instance")
        if out.get(par, e["id"]) != e["id"]:
            raise ValueError(f"premises constrain {par} by the hypotheses of two entries ({out[par]}, {e['id']}): "
                             "no one instance satisfies both by construction")
        out[par] = e["id"]
    return {par: {"instance": i} for par, i in sorted(out.items())}


def premise_points(law: dict, machine, witness: dict) -> dict:
    """{parameter: [point, ..]}: the points at which the premises (hyp premises expanded) apply each oracle
    parameter, in first-occurrence order, with the witness's values for the other binders (I12). Static:
    a point that needs the model or another oracle answer to compute raises mlaws.Unsupported."""
    from .gen import oracles as O
    from .gen.mlaws import Unsupported
    types = {b["name"]: b["type"] for b in law["statement"]["binders"]}
    ex = O.expand_hyps(law, machine.orc) if O.hyp_names(law) else law
    out: dict = {}

    def value(tm):
        if "nat" in tm:
            return int(tm["nat"])
        if "bool" in tm:
            return bool(tm["bool"])
        if "nats" in tm:
            return [int(x) for x in tm["nats"]]
        if "plus" in tm:
            return value(tm["plus"][0]) + value(tm["plus"][1])
        if "var" in tm and types.get(tm["var"]) in ("Nat", "Bool", "List<Nat>"):
            return witness[tm["var"]]
        raise Unsupported(f"an oracle point that is not a literal: {json.dumps(tm, sort_keys=True)}")

    def add(p, x):
        if p in machine.oparams:
            pts = out.setdefault(p, [])
            if x not in pts:
                pts.append(x)

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("app"), str):
                add(x["app"], value(x["args"][0]))
            if isinstance(x.get("cf"), dict) and isinstance(x["cf"].get("set"), list):
                for s in x["cf"]["set"]:
                    add(x["cf"]["fn"], value(s))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(ex["statement"].get("assume", []))
    return out


def search_law(law: dict, machine=None) -> dict:
    """The parent with its claim replaced, so any refutation the search finds satisfies the premises;
    binders no premise mentions are left out of the search (they get default values). Hyp premises are
    expanded into their predicates (I12), which the search evaluates."""
    from .gen import oracles as O
    s = copy.deepcopy(law)
    if O.hyp_names(law) and machine is not None:
        s = O.expand_hyps(s, machine.orc)
    free = {b["name"] for b in free_binders(law, machine)}
    s["statement"]["binders"] = [b for b in s["statement"]["binders"] if b["name"] not in free]
    states = [b["name"] for b in s["statement"]["binders"] if b["type"] == "State"]
    if len(states) >= 2:
        s["statement"]["claim"] = {"eq": [{"var": states[0]}, {"var": states[1]}]}
    else:
        s["statement"]["claim"] = {"eq": [{"bool": True}, {"bool": False}]}
    return s


def inhabitant_ir(law: dict) -> dict:
    st = law["statement"]
    prem = st.get("assume", [])
    if not prem:   # the only premise is a Reach binder: its evidence is the inhabitant (I8)
        prem = [{"eq": [{"bool": True}, {"bool": True}]}]
    out = {"ir_version": law["ir_version"], "law_id": "NV_" + law["law_id"], "rule": law["rule"],
           "facts": law.get("facts"), "facts_sha256": law["facts_sha256"],
           "statement": {"binders": [{"q": "exists", "name": b["name"], "type": b["type"]} for b in st["binders"]],
                         "claim": {"all": prem} if len(prem) > 1 else prem[0]}}
    if "rule_catalog_version" in law:
        out["rule_catalog_version"] = law["rule_catalog_version"]
    if st.get("scope"):   # 0.3 (audit F-M2-01): inhabited within the law's scope, e.g. by a trace of at most H actions
        out["statement"]["scope"] = dict(st["scope"])
    return out


MODEL_IMPORT = "../../model/{}.bend"   # an inhabitant lives in <gen>/<law>/nonvac/, the model in <gen>/model/


def texts_02(law: dict, machine, model_stem: str, witness: dict) -> tuple[str, str, str]:
    """(law name, LAWS.bend, PROOF.bend) of a holon-ir/0.2 inhabitant: a pure function of the frozen
    IR, the model and the witness, so G11V can regenerate and compare both files. Oracle parameters (I12)
    are supplied as the tables their witness values denote at premise_points."""
    from .gen import mlaws, mproofs
    imp = MODEL_IMPORT.format(model_stem)
    from .gen.refs import law_hash
    em = mlaws.Emitter(machine).emit(inhabitant_ir(law), imp,
                                     note=f"non-vacuity of {law['law_id']} ({law_hash(law, machine.f, getattr(machine, 'orc', None))})")
    if getattr(machine, "oparams", None):
        witness = mlaws.resolve_witness(machine, em.binders, witness, premise_points(law, machine, witness))
    proof = _evaluate(em, machine, imp, witness)
    if proof is None:
        raise ValueError("no evaluation proof for the inhabitant")
    return em.name, em.text, proof


def _evaluate(em, machine, imp: str, witness):
    """mproofs.evaluate without the core library: an inhabitant is proved by computation and calls no core lemma, so
    its text must not depend on the run's core mode (G11V regenerates it outside any run)."""
    from .gen import mproofs
    old = mproofs.CORE_MODE, mproofs.CORE_PASTE
    mproofs.CORE_MODE, mproofs.CORE_PASTE = None, ""
    try:
        return mproofs.evaluate(em, machine, imp, witness)
    finally:
        mproofs.CORE_MODE, mproofs.CORE_PASTE = old


def degenerate(cm, law: dict, witness: dict) -> bool | None:
    """True when the first two state binders are equal, decided on the compiled model."""
    states = [b["name"] for b in law["statement"]["binders"] if b["type"] == "State"]
    if len(states) < 2:
        return None
    sl = search_law(law, cm.m)
    ev = cm.evaluate(sl, {b["name"]: witness[b["name"]] for b in sl["statement"]["binders"]})
    return bool(ev["claims"][0])


def _inhabit_02(law: dict, root: Path, out_dir: Path, cfg: dict, cm, out: dict) -> dict:
    from .gen import mlaws
    if any(b["q"] != "forall" for b in law["statement"]["binders"]):
        return {**out, "bound": "not attempted: only universal laws with premises need an inhabitant"}
    try:   # oracle parameters a hypothesis constrains take the instance of its entry, and only that (I12)
        fixed = constrained_instances(law, cm.m) if getattr(cm.m, "oparams", None) else {}
    except ValueError as e:
        return {**out, "bound": f"no inhabitant by construction: {e}"}
    sl = search_law(law, cm.m)
    extra = {"fixed": fixed} if fixed else {}
    insts = ", ".join(v["instance"] for v in fixed.values())
    if fixed and {x["name"] for x in sl["statement"]["binders"]} <= set(fixed):
        # nothing left to search: the instances are the witness, and Bend alone decides whether they satisfy
        # the premises (an instance that violates its hypothesis gives an inhabitant that does not check)
        r = {"witness": dict(fixed), "bound": f"the concrete instances ({insts}) of the hypotheses' entries"}
        first = r["bound"]
    else:
        r = cm.explore(sl, {"noPerturb": True, **extra})  # first: only reachable states (run(p, s0))
        first = r.get("bound")
        if r.get("witness") is None:
            r = cm.explore(sl, extra or None)     # then constructed states too (recorded as unreachable)
    w = r.get("witness")
    if w is None:
        why = r.get("bound") or "no assignment satisfying the premises in the searched space"
        if fixed:
            why = f"the concrete instances ({insts}) do not satisfy the premises within the searched space ({why})"
        return {**out, "bound": why}
    w = {**w, **{b["name"]: default_of(b, cm.m) for b in free_binders(law, cm.m)}}
    # a failed inhabitant built on a sidecar instance claims nothing: no witness is recorded for it (I12)
    failed_w = None if fixed else w
    try:
        name, laws_text, proof = texts_02(law, cm.m, Path(cm.source).stem, w)
    except (mlaws.Unsupported, ValueError) as e:
        return {**out, "witness": failed_w, "bound": f"inhabitant inexpressible: {e}"}
    ok, why = _check(out_dir / NV, name, laws_text, proof, cfg)
    if not ok:
        shutil.rmtree(out_dir / NV, ignore_errors=True)
        if fixed:
            why = f"the inhabitant on the concrete instances ({insts}) does not check: {why}"
        return {**out, "witness": failed_w, "bound": why}
    states = [b["name"] for b in law["statement"]["binders"] if b["type"] in ("State", "Reach")]
    reach = all(set(w[x]) == {"run"} for x in states) if states else None
    note = r.get("bound") if reach is not False else f"no reachable inhabitant within ({first}); constructed states"
    return {**out, "status": "inhabited", "law": _rel(out_dir / NV / "LAWS.bend", root), "witness": w,
            "reachable": reach, "degenerate": degenerate(cm, law, w), "bound": note}


# ---------------------------------------------------------------- SORT-site laws (I15)
def site_id(law: dict) -> str | None:
    """The site of a SORT-site law (holon.mpipeline.site_law), else None."""
    from .mpipeline import site_law
    return site_law(law)


def site_inhabitant_ir(law: dict) -> dict:
    """The at_site premise of a SORT-site law as an existential statement: the parent's binders made existential,
    and the claim hit_<x>(a, s[, tables]) == true ({"at_site": ID}, the site term's premise: holon.gen.mlaws). The
    site term folds at_site in (∀p. at_site(p, s0, ℓ) → nonneg(d_ℓ)), so the Reach binder alone would be inhabited by
    s0 and say nothing (whitepaper §12.3, L21)."""
    st = law["statement"]
    term = st["claim"]["eq"][0]
    out = {"ir_version": law["ir_version"], "law_id": "NV_" + law["law_id"], "rule": law["rule"],
           "facts": law.get("facts"), "facts_sha256": law["facts_sha256"],
           "statement": {"binders": [{"q": "exists", "name": b["name"], "type": b["type"]} for b in st["binders"]],
                         "claim": {"eq": [{"at_site": term["site"], "on": term["on"], "from": term["from"]},
                                          {"bool": True}]}}}
    if "rule_catalog_version" in law:
        out["rule_catalog_version"] = law["rule_catalog_version"]
    return out


def texts_site(law: dict, machine, model_stem: str, witness: dict) -> tuple[str, str, str]:
    """(law name, LAWS.bend, PROOF.bend) of a SORT-site law's at_site inhabitant: a pure function of the frozen IR,
    the model and the witness (its oracle parameters are explicit tables), so G11V regenerates and compares both."""
    from .gen import mlaws, mproofs
    from .gen.refs import law_hash
    imp = MODEL_IMPORT.format(model_stem)
    em = mlaws.Emitter(machine).emit(site_inhabitant_ir(law), imp,
                                     note=f"non-vacuity (at_site) of {law['law_id']} "
                                          f"({law_hash(law, machine.f, getattr(machine, 'orc', None))})")
    w = mlaws.resolve_witness(machine, em.binders, witness, {}) if getattr(machine, "oparams", None) else witness
    proof = _evaluate(em, machine, imp, w)
    if proof is None:
        raise ValueError("no evaluation proof for the inhabitant")
    return em.name, em.text, proof


def _inhabit_site(law: dict, root: Path, out_dir: Path, cfg: dict, cm, out: dict, entries: list[str]) -> dict:
    """A reachable (s, a) at which a's evaluation from s reaches a hit of the site (stages S1 and S2 of the SORT-site
    search, holon/js/explore.mjs), proved like a counter-law: its state is a run from s0 with its R0/RStep chain."""
    from .gen import mlaws
    r = cm.site_search(law, "inhabit", entries)
    got = r["inhabit"]
    w = got["witness"]
    if w is None:
        return {**out, "bound": f"no reachable state and action reach a hit within: {got['bound']}"}
    for b in law["statement"]["binders"]:   # an oracle parameter is the table of its instance at the queried points
        if isinstance(w.get(b["name"]), dict) and set(w[b["name"]]) == {"instance"}:
            w = {**w, b["name"]: {"table": [list(x) for x in (got.get("tables") or {}).get(b["name"], [])]}}
    try:
        name, laws_text, proof = texts_site(law, cm.m, Path(cm.source).stem, w)
    except (mlaws.Unsupported, ValueError) as e:
        return {**out, "bound": f"inhabitant inexpressible: {e}"}
    ok, why = _check(out_dir / NV, name, laws_text, proof, cfg)
    if not ok:
        shutil.rmtree(out_dir / NV, ignore_errors=True)
        return {**out, "witness": w, "bound": why}
    return {**out, "status": "inhabited", "law": _rel(out_dir / NV / "LAWS.bend", root), "witness": w,
            "reachable": True, "degenerate": None,
            "bound": f"at_site inhabitant through {got['entry']}: {got['bound']}"}


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
    from .gen.oracles import Oracles
    from .mpipeline import m2plus
    orc = Oracles.for_milestone(m, root / law["facts"], root)
    mach = Machine(F.load(root / law["facts"]), root / law["facts"], oracles=orc, m2plus=m2plus(m))
    if site_id(law) is not None:
        return texts_site(law, mach, model, rec["non_vacuity"]["witness"])
    return texts_02(law, mach, model, rec["non_vacuity"]["witness"])


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


def unreachable(law: dict, witness, proof_text: str) -> str | None:
    """None when every State and Reach binder of the inhabitant's witness is a run from s0 and every Reach binder's
    evidence in the inhabitant's proof is the R0 / RStep chain of that run; else why not. G11V recomputes this from
    the witness and the proof file; the record's `reachable` flag is never trusted (F-M1-05, F-M2-13): a constructed
    state ({"state": ..}) can satisfy the premises at a point no trace reaches."""
    w = witness if isinstance(witness, dict) else {}
    bs = law["statement"].get("binders", [])
    not_run = [b["name"] for b in bs if b["type"] in ("State", "Reach")
               and not (isinstance(w.get(b["name"]), dict) and set(w[b["name"]]) == {"run"}
                        and isinstance(w[b["name"]]["run"], list))]
    if not_run:
        return (f"inhabitant states {not_run} are not runs from s0 (a constructed state is not shown reachable; the "
                "stored reachable flag is not trusted)")
    reach = [b["name"] for b in bs if b["type"] == "Reach"]
    if reach:
        steps = sum(len(w[x]["run"]) for x in reach)
        if proof_text.count(".R0{{==}}") < len(reach) or proof_text.count(".RStep{") < steps:
            return (f"inhabitant proof does not carry the R0 / RStep chain of its Reach binders {reach} "
                    f"({steps} steps)")
    return None


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
        if site_id(law) is not None:   # I15: the at_site premise hit_<x>, never Reach alone nor the site term itself
            from .sorts.sites import ghost_x, law_id as site_law_id
            x = ghost_x(site_law_id(site_id(law)))
            if f"M.hit_{x}(" not in laws_text or f"M.site_{x}(" in laws_text:
                bad.append(f"{lid}: the SORT-site inhabitant does not state the at_site premise hit_{x}")
                continue
        if _body(laws_text) != _body(want_laws):
            bad.append(f"{lid}: inhabitant LAWS.bend is not the one generated from the parent's IR")
            continue
        if _body(proof_text) != _body(want_proof):
            bad.append(f"{lid}: inhabitant PROOF.bend is not the evaluation proof of the recorded witness")
            continue
        if bend.escape_hatches(laws_text + proof_text):
            bad.append(f"{lid}: inhabitant uses an escape hatch")
            continue
        why = unreachable(law, nv.get("witness"), proof_text)
        if why:   # recomputed from the witness; the stored flag is not trusted (audit M1/1 F-M1-05, M2/1 F-M2-13)
            bad.append(f"{lid}: {why}")
            continue
        states = [b["name"] for b in law["statement"].get("binders", []) if b["type"] == "State"]
        if states or any(b["type"] == "Reach" for b in law["statement"].get("binders", [])):
            if nv.get("reachable") is not True:
                bad.append(f"{lid}: the record's reachable flag is {nv.get('reachable')!r}, but its witness states are "
                           "runs from s0")
                continue
            if len(states) >= 2:
                fp = gate.root / law["facts"]
                if fp not in machines:
                    from .gen.oracles import Oracles
                    from .mpipeline import m2plus
                    machines[fp] = CompiledMachine.build(fp, gate.cfg, reach=m2plus(gate.m),
                                                         oracles=Oracles.for_milestone(gate.m, fp, gate.root))
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
