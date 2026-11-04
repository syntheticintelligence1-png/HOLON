"""holon bundle2 refine (rules C4-C6 and M3 of the contract): one forge run of the corpus, the linked machine on every
call step, and the member models on every top-level step on a modelled member.

The comparison per call step (C5): status; the revert key on two reverts (holon.replay_fragments.revert_key); the
return data on two oks; every member's storage at every slot a write of the step touches on either side (on two oks);
the members' logs in order (on two oks); and the frames [parent, member, selector, persisted] (always). A difference
or an unsupported step is a disagreement, filed with an id that is a function of the step, "unexplained" and no links.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

from . import Ctx, Refused, Writer, file_sha, render
from . import harness as H

OBS_ORDER = ("status", "revert", "return", "storage", "logs", "frames")


def _hex32(v: int) -> str:
    return "0x%064x" % v


def members(ctx: Ctx, proj: Path, run: H.B2Run, root: Path):
    from ..replay_fragments import immutables_of, interface_selectors
    from .. import evm_abi as abi
    from .link import Member
    from .members import load_member
    out = []
    for (i, m, art), addr in zip(H.member_layouts(ctx, proj), run.members):
        model = load_member(ctx, m)
        doc = model.doc
        imm = {}
        src = (run.impl.get(addr) or (None, None))[1] or run.code.get(addr) or "0x"
        for name, (start, n) in immutables_of(proj, art).items():
            w = src[2 + 2 * start: 2 + 2 * (start + n)]
            if len(w) == 2 * n:
                imm[name] = "0x" + w
        out.append(Member(m["name"], model, addr, abi.functions(art.get("abi") or []), run.code.get(addr, "0x"), imm,
                          interface_selectors(proj, doc)))
    return out


def real_frames(e: H.B2Exec, names: dict) -> list:
    out, stack = [], []
    for depth, _caller, callee, sel, _value, reverted in e.frames:
        while stack and stack[-1][0] >= depth:
            stack.pop()
        parent = stack[-1][1] if stack else -1
        out.append([parent, names.get(callee, callee), sel, not reverted])
        stack.append((depth, len(out) - 1))
    return out


def compare(res: dict, e: H.B2Exec, before: dict, after: dict, real_fr: list) -> list:
    from ..replay_fragments import revert_key
    if res["status"] not in ("ok", "revert"):
        return ["unsupported"]
    diff = []
    real_status = "ok" if e.ok else "revert"
    if res["status"] != real_status:
        diff.append("status")
    elif res["status"] == "revert":
        if revert_key(res["revert"]) != revert_key(e.ret):
            diff.append("revert")
    else:
        if (res["return"] or "0x").lower() != (e.ret or "0x").lower():
            diff.append("return")
        touched = {}
        for addr, sl, _v, rev in e.writes:
            if not rev:
                touched.setdefault(addr, set()).add(sl)
        for addr, d in res["writes"].items():
            touched.setdefault(addr, set()).update(d)
        bad = False
        for addr, slots in touched.items():
            for sl in slots:
                mv = res["writes"].get(addr, {}).get(sl, before.get(addr, {}).get(sl, 0))
                if mv != after.get(addr, {}).get(sl, 0):
                    bad = True
        if bad:
            diff.append("storage")
        real_logs = [{"emitter": em, "topics": t, "data": d} for em, t, d in e.logs]
        if res["logs"] != real_logs:
            diff.append("logs")
    if res.get("frames") != real_fr:
        diff.append("frames")
    return diff


def step_id(label: str, sid: str, e: H.B2Exec) -> str:
    key = json.dumps([label, sid, e.to, e.caller, e.value, e.data], sort_keys=True)
    return "b2-" + hashlib.sha256(key.encode()).hexdigest()[:16]


def env_of(e: H.B2Exec) -> dict:
    env = dict(e.env)
    env.update({"block.timestamp": e.timestamp, "block.number": e.number, "blobhash": list(e.blobs),
                "balance": dict(e.balances)})
    return env


def counts(ctx: Ctx, mems: list, links: list, steps: list) -> dict:
    """frames_ok, by_member_action and links_ok from the per-step frames (the harness's), traces and compared steps."""
    names = {m.name: {(a.get("selector") or "").lower(): n for n, a in m.model.actions.items() if a.get("selector")}
             for m in mems}
    getters = {m.name: {f["name"]: s for s, f in m.fns.items()} for m in mems}
    want = {}
    for r in links:
        callee, kind, target = r[4], r[5], r[6]
        if kind == "receive":
            sel = None
        elif kind == "getter":
            sel = getters[callee].get(target)
        else:
            sel = next((s for s, n in names[callee].items() if n == target), None)
        want[(r[0], r[1], callee, sel)] = r
    frames_ok, bma, lk = {}, {}, Counter()
    traces, compared = set(), 0
    for st in steps:
        traces.add(st["trace"])
        fr = st["frames"]
        for parent, callee, sel, ok in fr:
            act = names.get(callee, {}).get(sel)
            if ok and act is not None:
                frames_ok.setdefault(callee, Counter())[act] += 1
            if ok and parent >= 0:
                p = fr[parent]
                pact = names.get(p[1], {}).get(p[2])
                if (p[1], pact, callee, sel) in want:
                    lk[(p[1], pact, callee, sel)] += 1
        if st["compared"]:
            compared += 1
            top = [f for f in fr if f[0] < 0]
            if top:
                act = names.get(top[0][1], {}).get(top[0][2])
                if act is not None:
                    e = bma.setdefault(top[0][1], {}).setdefault(act, {"ok": 0, "revert": 0})
                    e["ok" if st["status"] == "ok" else "revert"] += 1
    return {"traces": len(traces), "steps": compared,
            "frames_ok": {m: dict(sorted(c.items())) for m, c in sorted(frames_ok.items())},
            "by_member_action": {m: dict(sorted(v.items())) for m, v in sorted(bma.items())},
            "links_ok": sorted([*r[:4], lk[k]] for k, r in want.items())}


def refine(ctx: Ctx, args) -> int:
    from .link import Bundle
    root = ctx.root
    corpus_p = ctx.path("corpus")
    decl_p = ctx.path("declaration")
    for p in (corpus_p, decl_p):
        if not p.is_file():
            raise Refused(f"{ctx.rel(p)} is missing")
    corpus = json.loads(corpus_p.read_text())
    decl = json.loads(decl_p.read_text())
    tc = H._toolchain(ctx)
    work = H._work(ctx, args)
    try:
        proj = H.project(ctx, work, tc)
        sm, sl = H._slots(ctx, proj)
        traces = [t["rows"] for t in corpus["traces"]]
        print(f"holon bundle2 refine: {len(traces)} traces, {sum(map(len, traces))} steps; forge ...", flush=True)
        runs = H.run_traces(proj, tc, traces, sm, sl, corpus["init"], getattr(args, "jobs", 4) or 4)
        mems = members(ctx, proj, runs[0], root)
        models = model_evaluators(ctx, root)
    finally:
        if not getattr(args, "work", None):
            shutil.rmtree(work, ignore_errors=True)
    depth = int((ctx.side.get("link") or {}).get("depth") or 8)
    steps, dis, unsupported = [], [], 0
    refm = {name: {"steps": 0, "disagreements": [], "unsupported": 0} for name in models}
    for t, run in zip(corpus["traces"], runs):
        if [m.address for m in mems] != run.members:
            for m, a in zip(mems, run.members):
                m.address = a
        bundle = Bundle(mems, set(run.created), depth)
        names = {m.address: m.name for m in mems}
        for e, before, after in H.track(run, sm, sl)[1:]:
            rec = {"trace": t["label"], "id": e.id, "source": t["source"], "compared": e.kind == "call",
                   "status": "ok" if e.ok else "revert", "frames": real_frames(e, names)}
            steps.append(rec)
            if e.kind != "call":
                continue
            res = bundle.step(before, e.caller, e.to, e.value, bytes.fromhex(e.data[2:]), env_of(e), e.calls)
            diff = compare(res, e, before, after, rec["frames"])
            if diff:
                if diff == ["unsupported"]:
                    unsupported += 1
                dis.append({"id": step_id(t["label"], e.id, e), "class": "unexplained", "links": {},
                            "step": {"trace": t["label"], "id": e.id, "to": e.to, "caller": e.caller,
                                     "data": e.data[:202]},
                            "observables": diff, "reason": res.get("reason"),
                            "real": {"status": rec["status"], "ret": e.ret[:202], "frames": rec["frames"]},
                            "machine": {k: res.get(k) for k in ("status", "revert", "return", "frames")}})
            top = names.get(e.to)
            if top in models:
                model_step(models[top], refm[top], mems, top, e, before, after, t["label"])
    for ev in models.values():
        ev["evaluator"].close()
    c = counts(ctx, mems, decl["links"], steps)
    srcs = Counter(t["source"] for t in corpus["traces"])
    ref = {"refinement_version": H.REF_VERSION,
           "corpus": {"path": ctx.rel(corpus_p), "sha256": file_sha(corpus_p),
                      "sources": {k: srcs.get(k, 0) for k in ("m1", "seed", "random")}},
           "observables": list(ctx.side.get("observables") or []),
           "disagreements": [{"id": d["id"], "class": d["class"], "links": d["links"]} for d in dis],
           "unexplained": len(dis), "unsupported": unsupported,
           "toolchain": {k: tc[k] for k in ("forge_sha256", "solc_sha256", "sol_deps_sha256")}, **c}
    refm_doc = {"refinement_models_version": H.REFM_VERSION,
                "corpus": {"path": ctx.rel(corpus_p), "sha256": file_sha(corpus_p)},
                "members": {n: {"model": models[n]["path"], "model_sha256": file_sha(root / models[n]["path"]),
                                "steps": r["steps"],
                                "disagreements": [{"id": d["id"], "class": "unexplained", "links": {}}
                                                  for d in r["disagreements"]],
                                "unexplained": len(r["disagreements"]), "unsupported": r["unsupported"]}
                            for n, r in sorted(refm.items())}}
    w = Writer(False)
    w.put(ctx.path("refinement"), render(ref))
    w.put(ctx.path("refinement_models"), render(refm_doc))
    w.put(ctx.path("steps"), render({"steps": steps}))
    w.put(ctx.path("disagreements"), render({"disagreements": dis + [dict(d, member=n) for n, r in sorted(refm.items())
                                                                     for d in r["disagreements"]]}))
    print(f"holon bundle2 refine: {c['steps']} compared steps, {len(dis)} disagreements ({unsupported} unsupported); "
          + "; ".join(f"model {n}: {r['steps']} steps, {len(r['disagreements'])} disagreements"
                      for n, r in sorted(refm.items())))
    return w.finish("refine")


# ------------------------------------------------------------------------------------------------ member models (M3)
def model_evaluators(ctx: Ctx, root: Path) -> dict:
    """{member: {"path", "evaluator", "doc"}} of the committed models (gen/M3/bundle2/models/models.json)."""
    from ..sorts.evaluate3 import Evaluator
    from .members import load_member
    mp = ctx.path("models") / "models.json"
    if not mp.is_file():
        raise Refused(f"{ctx.rel(mp)} is missing (run holon bundle2 model)")
    ms = json.loads(mp.read_text())
    by = {m["name"]: m for m in ctx.members()}
    out = {}
    for name, e in sorted((ms.get("models") or {}).items()):
        out[name] = {"path": e["path"], "evaluator": Evaluator.build(root / e["path"], load_member(ctx, by[name]))}
    return out


def model_step(ev: dict, acc: dict, mems: list, name: str, e: H.B2Exec, before: dict, after: dict, label: str) -> None:
    """One top-level step on a modelled member, on its compiled model (evaluate3's A/B interface): status, revert key,
    the member's writes and logs."""
    from .. import evm_abi as abi
    from ..replay_fragments import revert_key
    m = next(x for x in mems if x.name == name)
    sel = e.data[:10]
    action = m.action_of(sel if len(e.data) >= 10 else None)
    acc["steps"] += 1
    fn = m.fns.get(sel)
    args = {}
    if fn is not None:
        try:
            args = abi.decode_args(fn["inputs"], bytes.fromhex(e.data[10:]))
        except abi.AbiError:
            try:
                args = abi.decode_args(fn["inputs"], bytes.fromhex(e.data[10:]), strict=False)
            except abi.AbiError:
                args = {}
    calls = []
    for frm, to, cdata, _val, ok, ret in e.calls:
        if frm != m.address:
            continue
        cname, fe = m.call_names.get(cdata[:10], (None, None))
        cargs = None
        if fe is not None:
            try:
                cargs = abi.decode_args(fe["inputs"], bytes.fromhex(cdata[10:]))
            except abi.AbiError:
                cargs = None
        calls.append({"to": to, "data": cdata, "fn": cname, "args": cargs, "ok": ok, "ret": ret})
    env = env_of(e)
    env.update({"caller": e.caller, "this": m.address, "msg.value": e.value, "msg.data.length": (len(e.data) - 2) // 2,
                "calls": calls, "code": {m.address: m.code}})
    state = {_hex32(k): _hex32(v) for k, v in sorted(before.get(m.address, {}).items())}
    diff = []
    if action is None:
        out = {"status": "unsupported", "reason": f"no action for selector {sel}"}
    else:
        try:
            out = ev["evaluator"].step(state, action, args, env)
        except Exception as x:   # noqa: BLE001: the model's failure is a disagreement, never a crash of the run
            out = {"status": "unsupported", "reason": f"{type(x).__name__}: {str(x)[:300]}"}
    st = out.get("status")
    if st not in ("ok", "revert"):
        acc["unsupported"] += 1
        diff = ["unsupported"]
    elif st != ("ok" if e.ok else "revert"):
        diff = ["status"]
    elif st == "revert":
        if revert_key(out.get("revert")) != revert_key(e.ret):
            diff = ["revert"]
    else:
        mw = {int(k, 16): int(v, 16) for k, v in (out.get("writes") or {}).items()}
        slots = set(mw) | {sl for a, sl, _v, rev in e.writes if a == m.address and not rev}
        if any(mw.get(s, before.get(m.address, {}).get(s, 0)) != after.get(m.address, {}).get(s, 0) for s in slots):
            diff.append("storage")
        mlogs = [{"topics": [t.lower() for t in ev_["topics"]], "data": ev_["data"].lower()}
                 for ev_ in out.get("events") or []]
        rlogs = [{"topics": t, "data": d} for em, t, d in e.logs if em == m.address]
        if mlogs != rlogs:
            diff.append("logs")
    if diff:
        acc["disagreements"].append({"id": step_id(label, e.id, e), "observables": diff,
                                     "reason": out.get("reason"), "step": {"trace": label, "id": e.id}})


def refine_check(ctx: Ctx) -> int:
    """--check: the records name the committed corpus, and steps.json recounts to refinement.json (no forge run)."""
    try:
        ref = json.loads(ctx.path("refinement").read_text())
        refm = json.loads(ctx.path("refinement_models").read_text())
        steps = json.loads(ctx.path("steps").read_text())["steps"]
        decl = json.loads(ctx.path("declaration").read_text())
    except (OSError, ValueError) as e:
        raise Refused(str(e))
    corpus_p = ctx.path("corpus")
    bad = []
    for r in (ref, refm):
        if r["corpus"]["path"] != ctx.rel(corpus_p) or r["corpus"]["sha256"] != file_sha(corpus_p):
            bad.append("a record names another corpus")
    want = recount_plain(steps, decl["links"], ctx)
    for k, v in want.items():
        if ref.get(k) != v:
            bad.append(f"refinement.json {k} differs from the recount of steps.json")
    for b in bad:
        print(f"holon bundle2 refine: {b}")
    if not bad:
        print("holon bundle2 refine: the records name the committed corpus and recount")
    return 1 if bad else 0


def recount_plain(steps: list, links: list, ctx: Ctx) -> dict:
    """counts() from the members' documents (action selectors) and the links' getters (a getter without arguments:
    its selector is its name's; one with arguments needs the compiled ABI, so --check refuses it)."""
    from ..evm_abi import selector
    from .link import Member

    class _M:
        def __init__(self, actions):
            self.actions = actions
    mems = []
    for m in ctx.members():
        doc_rel = m["document"] if m.get("adopted") else f"{ctx.out['documents']}/{m['name']}.json"
        doc = json.loads((ctx.root / doc_rel).read_text())
        fns = {}
        for r in links:
            if r[4] == m["name"] and r[5] == "getter":
                fam = next((s for s in doc.get("storage") or [] if s["name"] == r[6]), None)
                if fam is None or fam.get("kind") != "scalar":
                    raise Refused(f"link {r[:4]}: a getter with arguments (run holon bundle2 refine)")
                fns[selector(r[6], [])] = {"name": r[6]}
        mems.append(Member(m["name"], _M({a["name"]: a for a in doc["actions"]}), "", fns))
    return counts(ctx, mems, links, steps)
