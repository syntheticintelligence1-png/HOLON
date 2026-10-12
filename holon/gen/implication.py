"""Implication obligations S' => S between two statements (I10; whitepaper §9.4, L22).

A statement change counts as a strengthening, and a later milestone's analogue S_new counts as covering an
earlier S_old, only when the new statement implies the old one with a kernel-checked proof. This module
generates that obligation as ONE Bend law over the model both statements are about, and tries to prove it:

    law impl_<new>__<old>:
      for +x: T            S's binders (all universal)
      for h0: {..}         S's premises, as S renders them
      for hK: {..}         then every conjunct of S''s claim
      exs c0: {..}         S's claim
      {..}

Why it suffices: S''s premises must be among S's premises (textual inclusion, as rendered). Under S's
premises S' therefore applies and gives its claim; the obligation turns S's premises plus S''s claim into
S's claim. So S' and the obligation together give S.

Proof: the existing proof classes (holon.gen.mproofs.GENERATORS), then `pick`: every conjunct of the
claim is one of the premise binders as rendered (a conjunct of S''s claim, or a premise of S). Untrusted
like every generator: a proof counts only when Bend accepts it, BendTT (--verdict) too when it is
available, the law file states exactly the expected law, and neither file uses an escape hatch.

Supported: S and S' universal (forall binders only), over the same facts file. S' is instantiated at S's
binders, unified up to renaming (audit F-M2-23): by an explicit binder map {S' binder: S binder} (a STATEMENT_DIFF
entry's or a DERIVATION link's `binder_map`), else by name when every binder of S' is a binder of S with the same
type, else by position when S''s binders have, in order, the types of S's first binders. Laws from independent
generators (holon derive, the rules engine) name their binders themselves, so names alone cannot decide. A binder
named like an oracle parameter of the model is that parameter (I12) and is never renamed. Anything else is
UNSUPPORTED, with the reason; an obligation that no class proves is UNKNOWN. Neither is ever read as PROVED.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .machine import Machine, bname
from .mlaws import EmittedM, Emitter, Unsupported, law_name
from .refs import law_hash


def unify_binders(old: dict, new: dict, binder_map: dict | None = None) -> dict:
    """{S' binder: S binder} instantiating S' at S's binders (see the module docstring); raises Unsupported."""
    ob = [(b["name"], b["type"]) for b in old["statement"].get("binders", [])]
    nb = [(b["name"], b["type"]) for b in new["statement"].get("binders", [])]
    otypes = dict(ob)
    if binder_map is not None:
        if set(binder_map) != {n for n, _ in nb} or len(set(binder_map.values())) != len(binder_map):
            raise Unsupported(f"the binder map {binder_map} must map every binder of {new.get('law_id')} to a distinct "
                              f"binder of {old.get('law_id')}")
        for n, t in nb:
            if otypes.get(binder_map[n]) != t:
                raise Unsupported(f"binder map: {n}: {t} of {new.get('law_id')} -> {binder_map[n]}, which is not a "
                                  f"binder of {old.get('law_id')} of that type")
        return dict(binder_map)
    if all(otypes.get(n) == t for n, t in nb):
        return {n: n for n, _ in nb}
    if len(nb) <= len(ob) and all(t == ob[i][1] for i, (_, t) in enumerate(nb)):
        return {n: ob[i][0] for i, (n, _) in enumerate(nb)}
    raise Unsupported(f"the binders {nb} of {new.get('law_id')} are neither binders of {old.get('law_id')} by name and "
                      f"type nor, in order, of the types of its first binders {ob[:len(nb)]}; give a binder_map")


def rename_binders(law: dict, mapping: dict) -> dict:
    """The law with its binders renamed simultaneously (vars, function applications, CF function names)."""
    if all(k == v for k, v in mapping.items()):
        return law

    def walk(x, in_cf=False):
        if isinstance(x, list):
            return [walk(v) for v in x]
        if not isinstance(x, dict):
            return x
        out = {}
        for k, v in x.items():
            if k in ("var", "app") and isinstance(v, str):
                out[k] = mapping.get(v, v)
            elif in_cf and k == "fn" and isinstance(v, str):
                out[k] = mapping.get(v, v)
            else:
                out[k] = walk(v, in_cf=(k == "cf"))
        return out
    st = law["statement"]
    nst = {**walk({k: v for k, v in st.items() if k != "binders"}),
           "binders": [dict(b, name=mapping.get(b["name"], b["name"])) for b in st.get("binders", [])]}
    return {**law, "statement": nst}


def obligation_ir(old: dict, new: dict, binder_map: dict | None = None) -> dict:
    """The IR of new => old (S' => S), S' instantiated at S's binders (unify_binders); raises Unsupported when the
    generator cannot state it."""
    so, sn = old["statement"], new["statement"]
    for lw, st in ((old, so), (new, sn)):
        if any(b.get("q") != "forall" for b in st.get("binders", [])):
            raise Unsupported(f"{lw.get('law_id')}: only universal statements are supported")
    if old.get("facts") != new.get("facts"):
        raise Unsupported(f"the statements are over different facts files ({old.get('facts')} / {new.get('facts')}): "
                          "an implication across models needs a refinement map")
    sn = rename_binders(new, unify_binders(old, new, binder_map))["statement"]
    # S' applies wherever the obligation uses its claim only if S''s scope covers S's (whitepaper §8.6)
    sco, scn = so.get("scope") or {"kind": "unbounded"}, sn.get("scope") or {"kind": "unbounded"}
    if scn.get("kind") != "unbounded" and not (sco.get("kind") == scn.get("kind") == "bounded"
                                               and isinstance(scn.get("H"), int) and isinstance(sco.get("H"), int)
                                               and scn["H"] >= sco["H"]):
        raise Unsupported(f"the scope {scn} of {new.get('law_id')} does not cover the scope {sco} of {old.get('law_id')}")
    c = sn["claim"]
    conj = c["all"] if "all" in c else [c]
    return {"ir_version": old["ir_version"], "law_id": f"IMPL_{new['law_id']}__{old['law_id']}",
            "milestone": old.get("milestone"), "rule": old.get("rule"),
            "rule_catalog_version": old.get("rule_catalog_version"), "facts": old.get("facts"),
            "facts_sha256": old.get("facts_sha256", ""),
            "notes": f"generated obligation {new['law_id']} => {old['law_id']} (holon.gen.implication)",
            "statement": {"binders": [dict(b) for b in so["binders"]],
                          "assume": list(so.get("assume", [])) + list(conj),
                          "claim": so["claim"], "scope": so.get("scope", {"kind": "unbounded"})}}


def premises_included(old: dict, new: dict, m: Machine) -> list[str]:
    """The rendered premises of S' that are not premises of S (textual inclusion; empty when included)."""
    types = {b["name"]: b["type"] for b in old["statement"]["binders"]}
    env = {n: bname(n) for n in types}

    def rendered(law: dict) -> list:
        E = Emitter(m)
        return [x for p in law["statement"].get("assume", []) for x in E.premise_props(p, env, types)]
    have = rendered(old)
    return [f"{{{a} == {b} : {t}}}" for a, b, t in rendered(new) if (a, b, t) not in have]


def pick(em: EmittedM, m: Machine, model_import: str) -> str | None:
    """Class pick: every conjunct of the claim is one of the premise binders as rendered."""
    from .mproofs import _imports, _tuple
    if any(qq != "forall" for qq, _, _ in em.binders) or not em.claims:
        return None
    hits = [next((i for i, a in enumerate(em.assume) if a == c), None) for c in em.claims]
    if None in hits:
        return None
    params = [bname(n) for _, n, _ in em.binders] + [f"h{i}" for i in range(len(em.assume))]
    lines = ["# class pick: every conjunct of the claim is a premise as rendered (" +
             ", ".join(f"h{i}" for i in hits) + ")",
             f"def Laws.{em.name}({', '.join(params)}):", f"  {_tuple([f'h{i}' for i in hits])}"]
    return "\n".join(_imports(model_import) + lines) + "\n"


def _facts_mismatch(law: dict, sha: str) -> str | None:
    want = law.get("facts_sha256") or ""
    if want and want != sha:
        return f"{law.get('law_id')} names facts {want[:12]}.., but {law.get('facts')} hashes to {sha[:12]}.."
    return None


def prove(old: dict, new: dict, root: Path, cfg: dict | None = None, binder_map: dict | None = None) -> dict:
    """Generate new => old and try to prove it. Returns {status: PROVED | UNKNOWN | UNSUPPORTED, law_id,
    law_name, laws (LAWS.bend text or None), proof (the PROOF.bend text that checked, or None), generator,
    kernels, attempts, reason, binder_map}."""
    from .. import bend
    from .. import facts as F
    from ..mpipeline import CompiledMachine, law_import_problem, layout, model_name, write_pair
    from ..pipeline import law_names
    from . import mproofs
    root = Path(root)
    out = {"status": "UNSUPPORTED", "law_id": None, "law_name": None, "laws": None, "proof": None,
           "generator": None, "kernels": [], "attempts": [], "reason": "", "binder_map": None}
    try:
        obl = obligation_ir(old, new, binder_map)
        out["law_id"] = obl["law_id"]
        mapping = unify_binders(old, new, binder_map)
        out["binder_map"] = mapping
        fp = root / obl["facts"]
        if not fp.is_file():
            raise Unsupported(f"facts file {obl['facts']} does not exist")
        sha = F.sha256_file(fp)
        bad = _facts_mismatch(old, sha) or _facts_mismatch(new, sha)
        if bad:
            raise Unsupported(bad)
        cfg = cfg or bend.config(root)
        cm = CompiledMachine.build(fp, cfg)
        renamed = [f"{n} -> {o}" for n, o in mapping.items() if n != o and (n in cm.m.oparams or o in cm.m.oparams)]
        if renamed:
            raise Unsupported(f"a binder named like an oracle parameter is that parameter and is never renamed: {renamed}")
        missing = premises_included(old, rename_binders(new, mapping), cm.m)
        if missing:
            raise Unsupported(f"premises of {new['law_id']} are not premises of {old['law_id']}: {missing}")
    except (Unsupported, KeyError, TypeError) as e:
        out["reason"] = f"unsupported obligation: {e}"
        return out
    tmp = Path(tempfile.mkdtemp(prefix="impl-", dir=_workdir()))
    try:
        (tmp / "model").mkdir()
        name = f"{model_name(fp)}.bend"
        (tmp / "model" / name).write_text(cm.source.read_text())
        ld, pd, up = layout("", tmp, obl["law_id"])   # prover separation, as for milestones after M1
        imp = f"{up}model/{name}"
        try:
            em = Emitter(cm.m).emit(obl, imp, note=law_hash(obl, cm.facts))
        except Unsupported as e:
            out["reason"] = f"unsupported obligation: {e}"
            return out
        out.update({"status": "UNKNOWN", "law_name": em.name, "laws": em.text,
                    "reason": "no proof class produced a proof that checks"})
        verdict = bend.verdict_enabled(cfg)
        for gname, g in list(mproofs.GENERATORS) + [("pick", pick)]:
            try:
                text = g(em, cm.m, imp)
            except Exception as e:  # noqa: BLE001  (an untrusted generator that crashes proves nothing)
                out["attempts"].append({"kind": "proof", "generator": gname, "error": f"{type(e).__name__}: {e}"})
                continue
            if text is None:
                continue
            proof = write_pair(ld, pd, em.text, text)
            rr = bend.check(proof, cfg)
            imp_bad = law_import_problem(proof, ld / "LAWS.bend")   # the proof must import the obligation (F-M2-07)
            ok = (rr.ok and law_names(em.text) == [law_name(obl["law_id"])] and not bend.escape_hatches(text + em.text)
                  and imp_bad is None)
            att = {"kind": "proof", "generator": gname, "exit_code": rr.code, "marker": rr.marker}
            if ok and verdict:
                v = bend.check_verdict(proof, cfg)
                att["verdict"] = {"exit_code": v.code, "marker": v.marker}
                ok = v.ok
            if not ok:
                att["error"] = imp_bad if (rr.ok and imp_bad) else "\n".join(rr.out.strip().splitlines()[:8])
            out["attempts"].append(att)
            if ok:
                out.update({"status": "PROVED", "proof": proof.read_text(), "generator": gname,
                            "kernels": ["bend"] + (["BendTT"] if verdict else []),
                            "reason": f"{new['law_id']} => {old['law_id']} checked by "
                                      f"{' and '.join(['bend'] + (['BendTT --verdict'] if verdict else []))} (class {gname})"})
                break
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _workdir() -> Path:
    from .. import bend
    d = bend.build_dir() / "implication"
    d.mkdir(parents=True, exist_ok=True)
    return d
