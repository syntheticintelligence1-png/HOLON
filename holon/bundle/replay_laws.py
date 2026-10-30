"""holon bundle replay-laws (I86; the contract is the docstring of tests_m3/test_bundle_laws.py, rules RP1-RP3):

  python -m holon bundle replay-laws [--milestone M3] [--root DIR] [--check]

Every REFUTED bundle law and every PROVED existential one is replayed on the real bundle (RP1): its witness's trace,
as the bundle corpus's rows up to the witness frame (the frame's value replaced for a value-variant witness), through
the bundle harness (holon.bundle.harness) from a fresh deployment, with the extra calls the observation needs:

  payer         the queue's fee estimate for the caller and for the key, read at the frame's pre-state (two view calls
                of the price call's function, with the frame's gas argument), then the frame: it succeeds, and the
                two fees differ
  conservation  the frame with value v > 0, and the same trace with value 0: the frame succeeds, the member's balance
                grows by v, and the member's storage writes of the frame equal those of the zero-value frame
  keyed         the guarded action's call at the witness key (the call of the earlier frame that gave the key) before
                the witness frame and again after it: before, it reverts with the obligation's check's error; after,
                it does not

replay/<M>/bundle_laws/report.json: {"replay_version", "laws": {id: {"status", "observed", "trace", "frame"}}}; each
record's replay {status, detail} is set from it (RC1). --check re-runs the harness and compares the report and the
records' replay fields. Exit codes as holon bundle's. Nothing here names a target.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from . import BundleError, Ctx, Refused, render, write_or_check

REPLAY_VERSION = "holon-bundle-laws-replay/0.1"


def _raw_call(enc, caller: str, value: int, warp: int, to_member: str, data: bytes) -> bytes:
    """A harness call step (the harness's kind 2) with its calldata as given."""
    from .harness import _enc
    payload = _enc([enc.resolve(caller), value, warp, enc.member_addr[to_member], data],
                   ["address", "uint256", "uint256", "address", "bytes"])
    return _enc([2, payload], ["uint8", "bytes"])


def _error_data(reason: str) -> str:
    from ..extracted_eval import abi_encode, parse_types
    return "0x08c379a0" + abi_encode([reason.encode()], parse_types("string")).hex()


class Replayer:
    def __init__(self, ctx: Ctx, jobs: int, log=print):
        from . import harness as H
        from .lawrun import LawCtx
        self.ctx, self.jobs, self.log, self.H = ctx, jobs, log, H
        self.lctx = LawCtx(ctx.root, ctx.milestone)
        self.corpus = ctx.load(ctx.out("corpus"))
        self.by_id = {t["id"]: t for t in self.corpus["traces"]}
        self.names = [m["name"] for m in ctx.members()]

    def run(self, plans: list) -> list:
        """Run each plan (a list of encoded steps) as one trace from a fresh deployment; the per-trace records."""
        H = self.H
        tc = H.toolchain(self.ctx)
        with tempfile.TemporaryDirectory(prefix="holon-bundle-replay-laws-") as td:
            proj = H.project(self.ctx, Path(td), tc)
            dep = H.deployment(proj, tc, self.ctx, self.log)
            self.enc = H.Encoder(self.ctx, dep)
            encoded = [["0x" + s.hex() for s in p(self.enc)] for p in plans]
            watch = sorted(set(H.watch_list(self.ctx)) | {dep.named["verifier"], dep.named["harness"]})
            inputs = [(i, i + 1, {"lens": [len(t)], "steps": t, "init": H.init_values(self.ctx), "watch": watch})
                      for i, t in enumerate(encoded)]
            trs = H.run_chunks(proj, tc, inputs, self.jobs or 4, "laws", self.log)
            self.dep = dep
        if len(trs) != len(plans):
            raise BundleError(f"the harness recorded {len(trs)} traces for {len(plans)} replays")
        return trs

    def prefix(self, w: dict) -> list:
        tr = self.by_id.get(w["trace"])
        if tr is None:
            raise Refused(f"the witness's trace {w['trace']} is not in the corpus")
        return tr["steps"][:int(w["frame"])]

    def frame_step(self, w: dict, value: int | None = None):
        """The witness frame's step, with its value replaced (value) as a raw call of its calldata."""
        st = self.by_id[w["trace"]]["steps"][int(w["frame"])]
        if value is None:
            return lambda enc: enc.step(st)
        if "call" in st:
            c = dict(st["call"], value=int(value))
            return lambda enc: enc.call(c, st.get("warp", 0))
        member = self.lctx.sites[self.lid][1]
        data = bytes.fromhex(w["data"][2:])
        return lambda enc: _raw_call(enc, w["caller"], int(value), 0, member, data)


def _ok(step) -> bool:
    return bool(step.ok)


def plans_of(rp: Replayer, lid: str, rec: dict) -> tuple:
    """(the plans of one law's replay, the observer of their records)."""
    from .lawrun import site_of
    rp.lid = lid
    sub, mname, site, _cls = site_of(rp.lctx, lid)
    w = rec["witness"]
    pre = rp.prefix(w)
    k = len(pre)
    if sub == "payer":
        frame = rp.by_id[w["trace"]]["steps"][k]["call"]
        doc = rp.ctx.load(rp.ctx.document_rel(rp.ctx.member(mname)))
        act = next(a for a in doc["actions"] if a["name"] == site["action"])
        fn_name = site["price_call"].rpartition(".")[2]
        decl = rp.ctx.load(rp.ctx.out("declaration"))
        callee = next(r[4] for r in decl["links"] if r[0] == mname and r[1] == site["action"] and r[6] == fn_name)
        cdoc = rp.ctx.load(rp.ctx.document_rel(rp.ctx.member(callee)))
        ca = next(a for a in cdoc["actions"] if a["name"] == fn_name)
        sig = f"{fn_name}({','.join(p['type'] for p in ca['params'])})"
        # the price call's arguments as the frame's call gives them (the principal argument replaced by each party)
        g = next(x for x in act["guards"] if x["src"] == site["check_src"])
        call = next(t for t in _terms(g["expr"]) if isinstance(t, list) and t[:2] == ["call", site["price_call"]])
        names = [p["name"] for p in act["params"]]
        args = []
        for t in call[2:]:
            if t == site["keys"][0]:
                args.append(None)
            elif isinstance(t, list) and t[:1] == ["param"]:
                args.append(frame["args"][names.index(t[1])])
            else:
                raise Refused(f"{lid}: a price-call argument {t} the replay cannot pass")
        who = {"caller": frame["caller"], "key": "0x%040x" % (int(w["keys"][0], 16) & ((1 << 160) - 1))}

        def fee_call(party):
            a = [(who[party] if x is None else x) for x in args]
            return {"call": {"args": a, "caller": frame["caller"], "fn": sig, "to": callee, "value": 0}}
        steps = pre + [fee_call("caller"), fee_call("key")]
        plan = [lambda enc, s=s: enc.step(s) for s in steps] + [rp.frame_step(w)]

        def observe(trs):
            t = trs[0]
            fc, fk, fr = t.steps[k], t.steps[k + 1], t.steps[k + 2]
            f1 = int(fc.ret, 16) if fc.ok and len(fc.ret) > 2 else None
            f2 = int(fk.ret, 16) if fk.ok and len(fk.ret) > 2 else None
            obs = {"fee_for_caller": None if f1 is None else str(f1), "fee_for_key": None if f2 is None else str(f2),
                   "frame": "ok" if fr.ok else "revert"}
            passed = fr.ok and f1 is not None and f2 is not None and f1 != f2
            return passed, obs
        return [_plan(plan)], observe
    if sub == "conservation":
        v = int(w["value"])
        mi = rp.names.index(mname)
        plan_v = [lambda enc, s=s: enc.step(s) for s in pre] + [rp.frame_step(w, v if w["source"] == "value_variant"
                                                                              else None)]
        plan_0 = [lambda enc, s=s: enc.step(s) for s in pre] + [rp.frame_step(w, 0)]

        def observe(trs):
            tv, t0 = trs
            fv, f0 = tv.steps[k], t0.steps[k]
            before = (tv.steps[k - 1].balances.get(mi) if k else (tv.deploy.balances.get(mi, 0) if tv.deploy else 0)) or 0
            delta = (fv.balances.get(mi, 0) or 0) - before
            wv = sorted((s, x) for m, s, x, rev in fv.writes if m == mi and not rev)
            w0 = sorted((s, x) for m, s, x, rev in f0.writes if m == mi and not rev)
            obs = {"frame": "ok" if fv.ok else "revert", "value": str(v), "balance_delta": str(delta),
                   "writes_equal": wv == w0, "zero_frame": "ok" if f0.ok else "revert"}
            return fv.ok and v > 0 and delta == v and wv == w0 and f0.ok, obs
        return [_plan(plan_v), _plan(plan_0)], observe
    # keyed: the guarded call at the key, the witness frame, the guarded call again
    kf = int(w["key_frame"])
    gstep = rp.by_id[w["trace"]]["steps"][kf]
    doc = rp.ctx.load(rp.ctx.document_rel(rp.ctx.member(mname)))
    an, span, gi = site["check"].split("#")
    act = next(a for a in doc["actions"] if a["name"] == an)
    reason = [g for g in act["guards"] if g["src"] == span][int(gi)].get("reason")
    want = _error_data(reason) if reason else None
    plan = ([lambda enc, s=s: enc.step(s) for s in pre] + [lambda enc: enc.step(gstep)] + [rp.frame_step(w)]
            + [lambda enc: enc.step(gstep)])

    def observe(trs):
        t = trs[0]
        b, fr, a = t.steps[k], t.steps[k + 1], t.steps[k + 2]

        def out(s):
            return "ok" if s.ok else f"revert {s.ret}"
        obs = {"before": out(b), "frame": out(fr), "after": out(a), "check_revert": want}
        passed = (not b.ok and want is not None and b.ret.lower() == want.lower() and fr.ok
                  and (a.ok or a.ret.lower() != want.lower()))
        return passed, obs
    return [_plan(plan)], observe


def _plan(steps: list):
    return lambda enc: [f(enc) for f in steps]


def _terms(t):
    yield t
    if isinstance(t, list):
        for x in (t[1:] if t and isinstance(t[0], str) else t):
            yield from _terms(x)


def replayable(lctx, rec: dict, sub: str) -> bool:
    return bool(rec) and rec.get("witness") and (rec.get("status") == "REFUTED" or
                                                 (rec.get("status") == "PROVED" and sub == "keyed_external"))


def build(ctx: Ctx, jobs: int, log=print) -> tuple:
    """({relative path: bytes} of the report, {law id: replay field}) over the committed records."""
    from .lawrun import bundle_entries
    rp = Replayer(ctx, jobs, log)
    ents = bundle_entries(ctx.milestone, ctx.root)
    todo, plans, spans = [], [], []
    for lid in sorted(ents):
        p = ctx.root / "results" / ctx.milestone / f"{lid}.json"
        rec = json.loads(p.read_text()) if p.is_file() else None
        if not replayable(rp.lctx, rec, ents[lid]["subform"]):
            continue
        ps, obs = plans_of(rp, lid, rec)
        todo.append((lid, rec, obs))
        spans.append((len(plans), len(plans) + len(ps)))
        plans += ps
    trs = rp.run(plans) if plans else []
    laws, fields = {}, {}
    for (lid, rec, obs), (lo, hi) in zip(todo, spans):
        passed, observed = obs(trs[lo:hi])
        w = rec["witness"]
        laws[lid] = {"status": "passed" if passed else "failed", "observed": observed, "trace": w["trace"],
                     "frame": int(w["frame"])}
        fields[lid] = {"status": laws[lid]["status"],
                       "detail": f"replayed on the real bundle (holon bundle replay-laws): " +
                                 ", ".join(f"{k} {v}" for k, v in sorted(observed.items()))}
        log(f"{lid}: {laws[lid]['status']}")
    rel = f"replay/{ctx.milestone}/bundle_laws/report.json"
    return {rel: render({"replay_version": REPLAY_VERSION, "laws": laws})}, fields


def main(ctx: Ctx, check: bool, log=print, jobs: int = 0) -> int:
    from .lawrun import dumps
    files, fields = build(ctx, jobs, log)
    recs = {}
    for lid, f in fields.items():
        p = ctx.root / "results" / ctx.milestone / f"{lid}.json"
        rec = json.loads(p.read_text())
        if rec.get("replay") != f:
            rec["replay"] = f
        recs[p.relative_to(ctx.root).as_posix()] = dumps(rec).encode("utf-8")
    return write_or_check(ctx, {**files, **recs}, check, log=log)
