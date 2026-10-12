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

Supported: S and S' universal (forall binders only), over the same facts file; every binder of S' is a
binder of S with the same type (S' is instantiated at S's binders). Anything else is UNSUPPORTED, with
the reason; an obligation that no class proves is UNKNOWN. Neither is ever read as PROVED.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .machine import Machine, bname
from .mlaws import EmittedM, Emitter, Unsupported, law_name
from .refs import law_hash


def obligation_ir(old: dict, new: dict) -> dict:
    """The IR of new => old (S' => S); raises Unsupported when the generator cannot state it."""
    so, sn = old["statement"], new["statement"]
    for lw, st in ((old, so), (new, sn)):
        if any(b.get("q") != "forall" for b in st.get("binders", [])):
            raise Unsupported(f"{lw.get('law_id')}: only universal statements are supported")
    if old.get("facts") != new.get("facts"):
        raise Unsupported(f"the statements are over different facts files ({old.get('facts')} / {new.get('facts')}): "
                          "an implication across models needs a refinement map")
    types = {b["name"]: b["type"] for b in so["binders"]}
    for b in sn.get("binders", []):
        if types.get(b["name"]) != b["type"]:
            raise Unsupported(f"binder {b['name']}: {b['type']} of {new.get('law_id')} is not a binder of "
                              f"{old.get('law_id')} with that type")
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


def prove(old: dict, new: dict, root: Path, cfg: dict | None = None) -> dict:
    """Generate new => old and try to prove it. Returns {status: PROVED | UNKNOWN | UNSUPPORTED, law_id,
    law_name, laws (LAWS.bend text or None), proof (the PROOF.bend text that checked, or None), generator,
    kernels, attempts, reason}."""
    from .. import bend
    from .. import facts as F
    from ..mpipeline import CompiledMachine, layout, model_name, write_pair
    from ..pipeline import law_names
    from . import mproofs
    root = Path(root)
    out = {"status": "UNSUPPORTED", "law_id": None, "law_name": None, "laws": None, "proof": None,
           "generator": None, "kernels": [], "attempts": [], "reason": ""}
    try:
        obl = obligation_ir(old, new)
        out["law_id"] = obl["law_id"]
        fp = root / obl["facts"]
        if not fp.is_file():
            raise Unsupported(f"facts file {obl['facts']} does not exist")
        sha = F.sha256_file(fp)
        bad = _facts_mismatch(old, sha) or _facts_mismatch(new, sha)
        if bad:
            raise Unsupported(bad)
        cfg = cfg or bend.config(root)
        cm = CompiledMachine.build(fp, cfg)
        missing = premises_included(old, new, cm.m)
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
            ok = rr.ok and law_names(em.text) == [law_name(obl["law_id"])] and not bend.escape_hatches(text + em.text)
            att = {"kind": "proof", "generator": gname, "exit_code": rr.code, "marker": rr.marker}
            if ok and verdict:
                v = bend.check_verdict(proof, cfg)
                att["verdict"] = {"exit_code": v.code, "marker": v.marker}
                ok = v.ok
            if not ok:
                att["error"] = "\n".join(rr.out.strip().splitlines()[:8])
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
