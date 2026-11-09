"""A4 representatives for the three bundle-member laws whose committed inhabitant is a corpus frame at the member's
initial state (0 prefix steps; holon audit vacuity reads their witness shape as 'unreadable'): HOLON's own inhabitant
code, holon.symb.lawrun.Decider.inhabit (member sentinel laws) and holon.bundle.lawrun.Decider.first_ok + inhabit
(payer laws), each copied here with one added condition: the chosen frame has at least one state-changing prefix step.
Everything else (the corpus, the member's model, the reduced literals, witness_proof, the checker run by check: bend2
and BendTT) is HOLON's. Run from the root of a scratch tree of the target commit; it writes gen/M3/<id>/nonvac_rep/.
Usage: python3 rep_bundle.py <out json> <law id> ..."""
import json, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from holon.bundle import lawrun as BL
from holon.symb import lawrun as SL

out, lids = Path(sys.argv[1]), sys.argv[2:]
root = Path.cwd()
res = {}

def keep(lid):
    nd = root / "gen" / "M3" / lid / "nonvac"
    kp = nd.parent / "nonvac_committed"
    if nd.is_dir() and not kp.exists():
        shutil.copytree(nd, kp)
    return nd

def after(lid, nd):
    rp = nd.parent / "nonvac_rep"
    shutil.rmtree(rp, ignore_errors=True)
    if nd.is_dir():
        shutil.copytree(nd, rp)
    kp = nd.parent / "nonvac_committed"
    same = (kp / "LAWS.bend").is_file() and (rp / "LAWS.bend").is_file() and \
        (kp / "LAWS.bend").read_text() == (rp / "LAWS.bend").read_text()
    note = next((l for l in (rp / "PROOF.bend").read_text().splitlines() if l.startswith("# inhabitant")), None) \
        if (rp / "PROOF.bend").is_file() else None
    return {"laws_identical_to_committed_inhabitant": same, "note": note}

# ---- member sentinel laws (holon.symb.lawrun): Decider.inhabit with the frame's chain required non-empty
def symb_inhabit(self, lid, e):
    p = self.paths(lid)
    sh = self.registry["statements"][lid]
    lm = self.machine(e["member"])
    base = {"parent_statement_hash": sh, "degenerate": False}
    found = None
    s0ref, s0val = lm.s0()
    for tr in self.traces():
        frames = [f for f in tr["frames"] if f["member"] == e["member"]]
        if not any(f["action"] == e["action"] for f in frames):
            continue
        kh = {}
        ref, val, chain = s0ref, s0val, []
        for f in frames:
            act = lm.act(f["action"], lm.ar(f["action"], f["args"]), lm.en(f["env"]))
            if chain and f["action"] == e["action"] and lm.fn(f"C_{e['hit']}", lambda t, ref=ref, act=act:
                                                              [{"$ref": ref}, act, t], kh):   # added: chain non-empty
                found = (tr, f, act, list(chain), kh)
                break
            nref, nval = lm.step(act, ref, kh)
            if nval != val:
                chain.append((f, act, nval))
            ref, val = nref, nval
        if found:
            break
    if found is None:
        return {**base, "status": "unknown", "bound": "no frame after a state-changing prefix step meets the premises"}
    tr, f, act, chain, kh = found
    chain, act, kh = self.reduced(lm, chain, act, e["hit"])
    p["nv_laws"].parent.mkdir(parents=True, exist_ok=True)
    p["nv_laws"].write_text(SL.nv_text(e, lid, sh, p["nv_laws"].parent, self.root, self.m), encoding="utf-8")
    acts = [lm.lit.text(a) for _f, a, _s in chain]
    states = [lm.lit.typed(s, "HSt") for _f, _a, s in chain]
    body, ch, state = SL._chain("w_", "M", acts, states, "M.s0()", "t_kh()")
    imps = self.imports(p["nv_proof"].parent, e, None) + [("./LAWS.bend", "Laws")]
    note = f"inhabitant: trace {tr['id']}, step {f['k']} frame {f['idx']} ({f['action']}); {len(chain)} prefix steps"
    p["nv_proof"].write_text(SL.witness_proof(lid, imps, SL._table(kh, lm.lit), body, state, ch,
                                              [("M.HAct", lm.lit.text(act))],
                                              f"U.{e['hit']}({{state}}, {{binders}}, t_kh())", "nonvac", note),
                             encoding="utf-8")
    chk = SL.check(p["nv_proof"])
    return {**base, "status": "inhabited" if chk["ok"] else "unknown", "checker": chk["checker"],
            "witness": {"trace": tr["id"], "step": f["k"], "frame": f["idx"], "action": f["action"],
                        "prefix": len(chain), "caller": str(f["caller"]).lower(),
                        "block_timestamp": int(f["env"].get("block.timestamp") or 0)}}

# ---- payer laws (holon.bundle.lawrun): Decider.first_ok with the frame's chain required non-empty
def first_ok(self, lm, site):
    s0_ref, s0_val = lm.s0()
    for tr in self.traces():
        mine = [f for f in tr["frames"] if f["member"] == lm.name]
        if not any(f["action"] == site["action"] for f in mine):
            continue
        kh = {}
        ref, val, chain = s0_ref, s0_val, []
        for fr in mine:
            ar, en = lm.ar(fr["action"], fr["args"]), lm.en(fr["env"])
            if chain and fr["action"] == site["action"] and lm.chk(fr["action"], ref, ar, en, kh) == 0:  # added
                return BL.Witness("corpus", tr, fr, list(chain), kh)
            act = lm.act(fr["action"], ar, en)
            nref, nval = lm.step(act, ref, kh)
            if nval != val:
                chain.append((act, nval))
            ref, val = nref, nval
    return None

sd = None
bd = None
for lid in lids:
    nd = keep(lid)
    if lid.startswith("L_sym_sentinel_"):
        if sd is None:
            sd = SL.Decider(root, "M3", root / "results" / "M3", root / "gen" / "M3", 4, log=lambda *a: None)
        r = symb_inhabit(sd, lid, sd.index[lid])
    else:
        if bd is None:
            bd = BL.Decider(BL.LawCtx(root, "M3"), root / "results" / "M3", root / "gen" / "M3", 4, log=lambda *a: None)
            BL.Decider.first_ok = first_ok
        sub, mname, site, _cls = BL.site_of(bd.lctx, lid)
        r = bd.inhabit(lid, sub, site, mname, None)
    chk = r.pop("checker", None) or r.pop("_checker", None)
    r["checker"] = {k: chk.get(k) for k in ("marker", "exit_code", "verdict")} if isinstance(chk, dict) else chk
    r.update(after(lid, nd))
    res[lid] = r
    print(lid, json.dumps(r, indent=1)[:1500], flush=True)
for d in (sd, bd):
    if d is not None:
        d.close()
out.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
