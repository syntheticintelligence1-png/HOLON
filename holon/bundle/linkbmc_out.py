"""holon bundle bmc, the replay and the document (I86; tests_m3/test_bundle_laws.py rules Q3 and Q4): the paths
holon.bundle.linkbmc's search gives, replayed on the real bundle through the bundle harness, and
results/<M>/bundle_laws/bmc.json. The rules are holon.bundle.linkbmc's docstring. Nothing here names a target.
"""
from __future__ import annotations

from pathlib import Path

from . import BundleError, Ctx, render, write_or_check
from .linkbmc import BMC_VERSION, CACHE_ENV, Setup, search_all


def revert_data(check) -> str | None:
    """The revert data a check's failure gives (the document's error and literal arguments, a panic's code), or None
    when the document does not fix it."""
    from ..extracted_eval import abi_encode, parse_types
    if check.kind == "panic" and check.code is not None:
        return "0x4e487b71" + int(check.code).to_bytes(32, "big").hex()
    err = check.error or {}
    if err.get("selector") and err.get("signature"):
        args = check.args or []
        if all(isinstance(a, list) and a[:1] == ["str"] for a in args):
            types = err["signature"].split("(", 1)[1][:-1]
            vals = [bytes.fromhex(a[1]) for a in args]
            return err["selector"] + abi_encode(vals, parse_types(types)).hex()
        return None
    if check.kind in ("callvalue", "calldatasize", "abi", "slice"):
        return "0x"
    return None


# ------------------------------------------------------------------------------------------------ Q3: the replay
class Replay:
    """The paths, replayed on the real bundle through the bundle harness (each from a fresh deployment)."""

    def __init__(self, s: Setup, log=print, jobs: int = 0):
        self.s, self.log, self.jobs = s, log, jobs
        self.move_cfg = s.q28["enqueue"]
        self.sender = {}
        self.fees: dict = {}
        self.fee_queries: dict = {}
        for name, mv in s.moves.items():
            mdoc = s.ctx.load(s.ctx.document_rel(s.ctx.member(mv["member"])))
            acts = {a["name"]: a for a in mdoc["actions"]}
            cands = sorted(mv["senders"], key=lambda a: (len(acts[a].get("params") or []), a))
            self.sender[name] = (mv["member"], acts[cands[0]])

    def sender_values(self, enc, name: str) -> tuple:
        """(the sender action, its ABI parameters, the values the move's call passes): the address parameter the
        sidecar's target, the bytes parameter its data, the last unsigned parameter its gas limit, any other 0."""
        from ..machine import _doc_param
        _member, act = self.sender[name]
        ps = [_doc_param(p) for p in act.get("params") or []]
        uints = [i for i, p in enumerate(ps) if str(p.get("type") or "").startswith("uint")]
        vals = []
        for i, p in enumerate(ps):
            t = str(p.get("type") or "")
            if t == "address":
                v = int(enc.resolve(self.move_cfg["target"]), 16)
            elif t == "bytes":
                v = bytes.fromhex(self.move_cfg["data"][2:])
            elif t.startswith("uint"):
                v = int(self.move_cfg["gas_limit"]) if uints and i == uints[-1] else 0
            else:
                raise BundleError(f"{act['name']}: a {t} parameter the sidecar's enqueue does not fill")
            vals.append(v)
        return act, ps, vals

    def sender_call(self, enc, name: str) -> bytes:
        """The move's realization: the calling member's sender action with the sidecar's target, data and gas limit."""
        from ..extracted_eval import abi_encode, norm
        act, ps, vals = self.sender_values(enc, name)
        return bytes.fromhex(act["selector"][2:]) + abi_encode([norm(v, p) for v, p in zip(vals, ps)], ps)

    def fee_query(self, enc, name: str) -> dict | None:
        """The move's fee query (Q3: the value its fee needs): the price call of the sender action's payer site in the
        bundle-laws basis, by the replay actor, its payer argument the replay actor and its other arguments the sender
        call's. None when the sender action has no payer site: the move then carries no value."""
        from ..rules import bundle as RB
        from .replay_laws import _terms
        ctx = self.s.ctx
        member, act = self.sender[name]
        sites = [st for _lid, (sub, m, st, _c) in sorted(RB.sites(RB.basis(ctx.root, ctx.milestone)).items())
                 if sub == "payer" and m == member and st.get("action") == act["name"]]
        if not sites:
            return None
        site = sites[0]
        fn = site["price_call"].rpartition(".")[2]
        decl = ctx.load(ctx.out("declaration"))
        callee = next(r[4] for r in decl["links"] if r[0] == member and r[1] == act["name"] and r[6] == fn)
        cact = next(a for a in ctx.load(ctx.document_rel(ctx.member(callee)))["actions"] if a["name"] == fn)
        g = next(x for x in act["guards"] if x["src"] == site["check_src"])
        call = next(t for t in _terms(g["expr"]) if isinstance(t, list) and t[:2] == ["call", site["price_call"]])
        _act, _ps, vals = self.sender_values(enc, name)
        names = [p.get("name") for p in act.get("params") or []]
        args = []
        for t in call[2:]:
            if t == site["keys"][0]:
                args.append(self.move_cfg["replay_actor"])
            elif isinstance(t, list) and t[:1] == ["param"] and t[1] in names:
                args.append(vals[names.index(t[1])])
            else:
                raise BundleError(f"{act['name']}: a price-call argument {t} the fee query cannot pass")
        sig = f"{fn}({','.join(p['type'] for p in cact['params'])})"
        return {"caller": self.move_cfg["replay_actor"], "fn": sig, "args": args, "to": callee, "value": 0}

    def plan(self, path: list):
        from .replay_laws import _raw_call
        s = self.s

        def build(enc, t0: int):
            cur, out = t0, []
            for st in path:
                ts = int(str(st["env"]["block.timestamp"]), 0)
                warp = max(0, ts - cur)
                cur = max(cur, ts)
                if st["action"] in s.moves:
                    member = self.sender[st["action"]][0]
                    out.append(_raw_call(enc, self.move_cfg["replay_actor"], self.fees.get(st["action"], 0), warp,
                                         member, self.sender_call(enc, st["action"])))
                else:
                    out.append(_raw_call(enc, st["env"]["caller"], int(st["env"]["msg.value"]), warp,
                                         s.link.adopted, bytes.fromhex(st["calldata"][2:])))
            return out
        return build

    def run(self, items: list) -> list:
        """items: [(target id, path)] -> the per-trace harness records, in order."""
        import tempfile
        from . import harness as H
        ctx = self.s.ctx
        tc = H.toolchain(ctx)
        with tempfile.TemporaryDirectory(prefix="holon-bundle-bmc-") as td:
            proj = H.project(ctx, Path(td), tc)
            dep = H.deployment(proj, tc, ctx, self.log)
            enc = H.Encoder(ctx, dep)
            t0 = int(getattr(dep.deploy, "timestamp", 0) or self.s.side["deployment"]["deployed_at"])
            self.t0 = t0
            watch = sorted(set(H.watch_list(ctx)) | {dep.named["verifier"], dep.named["harness"]})
            # the moves' fees: each move's fee query, run once on the deployment (one trace; the queries only read)
            moved = sorted({st["action"] for _tid, path in items for st in path if st["action"] in self.s.moves})
            qs = [(n, q) for n in moved for q in [self.fee_query(enc, n)] if q is not None]
            if qs:
                steps = ["0x" + enc.call(q).hex() for _n, q in qs]
                ftr = H.run_chunks(proj, tc, [(0, 1, {"lens": [len(steps)], "steps": steps,
                                                      "init": H.init_values(ctx), "watch": watch})],
                                   1, "bmcfee", self.log)
                if len(ftr) != 1 or len(ftr[0].steps) != len(qs):
                    raise BundleError("the harness did not record the fee queries' trace")
                for (n, q), r in zip(qs, ftr[0].steps):
                    if not r.ok or len(r.ret) < 66:
                        raise BundleError(f"the fee query of {n} ({q['fn']}) failed on the deployment: {r.ret[:138]}")
                    self.fees[n] = int(r.ret[:66], 16)
                    self.fee_queries[n] = {"query": q["fn"], "member": q["to"], "args": [
                        str(a) if isinstance(a, int) else a for a in q["args"]], "fee": str(self.fees[n])}
            encoded = [["0x" + x.hex() for x in self.plan(path)(enc, t0)] for _tid, path in items]
            inputs = [(i, i + 1, {"lens": [len(t)], "steps": t, "init": H.init_values(ctx), "watch": watch})
                      for i, t in enumerate(encoded)]
            trs = H.run_chunks(proj, tc, inputs, self.jobs or 4, "bmc", self.log)
        if len(trs) != len(items):
            raise BundleError(f"the harness recorded {len(trs)} traces for {len(items)} replays")
        return trs

    def observe(self, check, path: list, tr) -> dict:
        steps = tr.steps
        if len(steps) != len(path):
            return {"status": "failed", "detail": f"the harness recorded {len(steps)} steps for {len(path)}"}
        for i, (st, r) in enumerate(zip(path[:-1], steps[:-1])):
            if not r.ok:
                return {"status": "failed", "detail": f"step {i} ({st['action']}) reverted: {r.ret[:138]}"}
        callee = "0x%040x" % self.s.callee_addr
        idx = [i for i, (a, _impl) in sorted(tr.members.items()) if a == callee]
        moves = []
        for i, (st, r) in enumerate(zip(path, steps)):
            if st["action"] in self.s.moves:
                n = len([w for w in r.writes if idx and w[0] == idx[0] and not w[3]])
                moves.append({"step": i, "linked_member_writes": n})
                if not n:
                    return {"status": "failed", "detail": f"step {i}: the move wrote nothing of the linked member",
                            "observed": {"moves": moves}}
        last = steps[-1]
        want = revert_data(check)
        obs = {"last_reverted": not last.ok, "revert_data": last.ret, "timestamps": [r.timestamp for r in steps],
               "moves": moves}
        if last.ok:
            return {"status": "failed", "detail": "the last step succeeded", "observed": obs}
        if want is not None and last.ret != want:
            return {"status": "failed", "detail": f"the last step reverted with {last.ret[:138]}, not the target "
                                                  f"check's {want[:138]}", "observed": obs}
        return {"status": "passed", "detail": "every step but the last succeeded; the last reverted at the target "
                                              "check" + ("" if want is None else " with its revert data"),
                "observed": obs}


# ------------------------------------------------------------------------------------------------ Q4: the document
def build(ctx: Ctx, log=print, jobs: int = 0, cache: str | None = None) -> dict:
    from .. import bmc as BMC
    from ..machine import document_programs
    s = Setup(ctx)
    res = search_all(s, log, cache)
    checks = {c.id: c for prog in document_programs(s.adoc).values() for c in prog.checks()}
    for r in res.values():
        rr = r.get("realistic")
        r["recorded"] = rr[0] if rr and rr[0] is not None else r.get("path")
        r["recorded_why"] = rr[1] if rr else None
    paths = [(tid, r["recorded"]) for tid, r in sorted(res.items()) if r["verdict"] == "path"]
    reps = {}
    rp = Replay(s, log, jobs)
    if paths:
        trs = rp.run(paths)
        for (tid, path), tr in zip(paths, trs):
            reps[tid] = rp.observe(checks[tid], path, tr)
    from ..refute_m3 import clock
    targets = {}
    H, rl = int(s.side["bmc"]["H"]), int(s.side["solver"]["rlimit_per_query"])
    for tid, r in sorted(res.items()):
        rep = reps.get(tid) or {"status": "not_run", "detail": "no path to replay"}
        verdict, reason = r["verdict"], r["reason"]
        if verdict == "path" and rep["status"] != "passed":
            verdict = "unknown"
            reason = f"a candidate path of length {r['length']} whose replay failed ({rep['detail']}): {r['reason']}"
        path = None
        if r.get("recorded"):
            path = []
            for st in r["recorded"]:
                x = {"action": st["action"], "args": st["args"], "calldata": st["calldata"], "env": st["env"]}
                if st["action"] in s.moves:
                    _member, act = rp.sender[st["action"]]
                    x["move"] = {"member": s.moves[st["action"]]["member"], "replayed_as": act["name"],
                                 "actor": s.q28["enqueue"]["replay_actor"], "value": str(rp.fees.get(st["action"], 0))}
                path.append(x)
        ck = clock(r.get("recorded"))
        targets[tid] = {"kind": r["kind"], "verdict": verdict, "k": r["length"], "path": path, "reason": reason,
                        "replay": rep, "clock": ck, "clock_resolve": r.get("recorded_why"),
                        "bound": {"H": H, "rlimit": rl, "largest_k": r["largest_k"], "unroll": BMC.UNROLL},
                        "approx": r.get("approx") or []}
    p = s.problem()
    settings = {
        "engine": "holon.bmc (I40's engine, unchanged): iterative deepening k = 1..H over the cone's levels",
        "H": H, "rlimit_per_query": rl, "byte_length_max": int(s.side["smt"]["byte_length_max"]),
        "blob_count_max": int(s.side["blob_count_max"]), "deployed_at": int(s.side["deployment"]["deployed_at"]),
        "principals": [[n, "0x%040x" % a] for n, a in p.principals],
        "adopted": {"member": s.link.adopted, "document": s.adopted_rel, "r0": s.r0_info},
        "linked": {"member": s.link.callee, "clock": s.link.clock, "functions": s.link.fns,
                   "moves": {k: {"action": v["action"], "member": v["member"], "senders": v["senders"]}
                             for k, v in sorted(s.moves.items())},
                   "ghosts": s.ghosts.all_names(),
                   "r0": {g: {str(k): v for k, v in sorted(e.items())} for g, e in sorted(s.r0_ghosts.items()) if e},
                   "answers": {fn: s.answers[fn] for fn in sorted(s.notes)},
                   "approximations": {fn: n for fn, n in sorted(s.notes.items()) if n}},
        "answer_model": {"path": s.env_rel, "label": (s.env.get("environment") or {}).get("label"),
                         "used_for": "every external call the link does not answer"},
        "replay": {"harness": "holon.bundle.harness (a fresh deployment per path)", "enqueue": s.q28["enqueue"],
                   "value": "the move's fee: its sender action's payer price call (the bundle-laws basis) for the "
                            "replay actor, read on the real bundle at the deployment (0 without a payer site)",
                   "fees": {n: q for n, q in sorted(rp.fee_queries.items())}},
        "inputs": s.input_refs(),
    }
    return {"bmc_version": BMC_VERSION, "settings": settings, "targets": targets}


def main(ctx: Ctx, check: bool, log=print, jobs: int = 0) -> int:
    import os
    out = f"results/{ctx.milestone}/bundle_laws/bmc.json"
    doc = build(ctx, log, jobs, None if check else (os.environ.get(CACHE_ENV) or None))
    for tid, t in sorted(doc["targets"].items()):
        log(f"{tid}: {t['verdict']} (k {t['k']}, replay {t['replay']['status']})")
    return write_or_check(ctx, {out: render(doc)}, check, log=log)
