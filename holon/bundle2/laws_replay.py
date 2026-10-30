"""The witnesses of Bundle II's laws on the real code, and D5's bisection (BUILD_PLAN row I84 = I37b; the contract is
the docstring of tests_m3/test_bundle2_laws.py, rules LD5, FP4, D5 and RC1-RC2).

  python -m holon bundle2 replay-laws [--check] [--root DIR] [--jobs N]

From each law's record (results/<M>/<id>.json), on the laws' deployment (holon.bundle2.laws_forge):

  link_domain (REFUTED)   the witness's prefix and action, then the callee's resolution of the call's (version, index)
                          as a call of its own: passed iff every prefix step succeeds, the action reverts and the
                          resolution returns the zero word or reverts. observed: {"steps", "proof_call": ok|revert,
                          <the resolution action's name>: "0x<20 bytes>"|"revert", "version", "index"}
  public_input (REFUTED)  both runs: passed iff every step of both succeeds, the public input each passes to the callee
                          (the call's calldata, the view's hash argument) is one word, and the consumer's field of the
                          two receiver inputs (the decoder's read; "none" for a header too short) differs.
                          observed: {"runs": [ok|fail, ..], "pi": [..], "field": [..]}
  self_controlled         D5: the calibration harness's strategy (replay/M3/bundle2/calibrate/) at backlog k with a
                          transaction gas limit L: k*_real is the least backlog whose call fails with L = G while it
                          succeeds with L = 2G, by bisection between a backlog that succeeds within G and one that fails;
                          passed iff found, with the outcomes at k*_real - 1 and k*_real recorded.
                          observed: {"k_star_real", "below": {"backlog", "within_G"}, "at": {"backlog", "within_G",
                          "within_2G"}, "probes": [[k, L, ok], ..]}
  any other law           not_run

The report is the bundle-laws sidecar's outputs.replay ({"replay_version", "laws": {id: {"status", "observed",
"detail"}}, "toolchain"}); each record's replay field is set from it. --check re-runs nothing: it checks that the report
and the records agree. Nothing here names a target.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import ROOT, BundleError, Refused, Writer, render

REPLAY_VERSION = "holon-bundle2-laws-replay/0.1"


def _rec_path(L, lid: str) -> Path:
    return L.root / "results" / L.m / f"{lid}.json"


def real_call(st: dict) -> dict:
    env = st["env"]
    return {"to": 1, "caller": env["caller"], "value": int(env.get("msg.value") or 0),
            "timestamp": int(env.get("block.timestamp") or 0), "data": st["calldata"],
            "blobs": list(env.get("blobhash") or [])}


def field_of(header_hex: str, offset: int, width: int):
    b = bytes.fromhex(header_hex[2:])
    if len(b) < offset + width:
        return "none"
    return int.from_bytes(b[offset:offset + width], "big")


def receiver_bytes(step: dict, path: list) -> str:
    v = step["args"]
    for p in path:
        v = v[p]
    return v


def resolver_info(L) -> tuple[str, str]:
    from .laws import resolver
    ld = [e for e in L.laws.values() if e["subform"] == "link_domain"]
    callee, target = ld[0]["basis"]["callee"], ld[0]["basis"]["target"]
    name = resolver(L.callee_doc(callee), target)
    a = next(x for x in L.callee_doc(callee)["actions"] if x["name"] == name)
    return name, a["selector"].lower()


def replay_link(L, forge, lid: str, rec: dict) -> dict:
    w = rec["witness"]
    name, sel = resolver_info(L)
    v, i = int(w["link"]["version"]), int(w["link"]["index"])
    steps = list(w["prefix"]) + [w["x"]]
    rcall = {"to": 2, "caller": "0x" + "00" * 20, "value": 0, "timestamp": 0, "data": sel + "%064x" % v + "%064x" % i,
             "blobs": []}
    run = forge.traces([[real_call(s) for s in steps] + [rcall]], jobs=1, tag="rl")[0]
    execs = [e for e in run.execs if e.id != "d"]
    outs = ["ok" if e.ok else "revert" for e in execs]
    res = execs[-1]
    rv = "revert" if not res.ok else ("0x" + res.ret[2:][-40:] if len(res.ret) >= 66 else res.ret)
    obs = {"steps": outs[:-2], "proof_call": outs[-2], name: rv, "version": v, "index": i}
    ok = all(o == "ok" for o in outs[:-2]) and outs[-2] == "revert" and (rv == "revert" or int(rv, 16) == 0)
    return {"status": "passed" if ok else "failed", "observed": obs,
            "detail": "every prefix step succeeds, the action reverts and the callee does not resolve the call's "
                      "(version, index)" if ok else "the real code does not behave as the witness says"}


def replay_pi(L, forge, lid: str, rec: dict) -> dict:
    from .laws import view_hash_index
    w = rec["witness"]
    e = L.laws[lid]
    con = e["basis"]["consumer"]
    inp = e["basis"]["input"]
    path = [inp[1][1], inp[2]] if inp[0] == "member" else [inp[1]]
    hidx = view_hash_index(L.I, e)
    traces = [list(r["prefix"]) + [r["x"]] for r in w["runs"]]
    runs = forge.traces([[real_call(s) for s in t] for t in traces], jobs=2, tag="rp")
    outs, pis, fields = [], [], []
    for t, run in zip(traces, runs):
        execs = [x for x in run.execs if x.id != "d"]
        outs.append("ok" if all(x.ok for x in execs) else "fail")
        callee = run.members[1]
        hits = [d for _f, to, d, _v, _ok, _r in execs[-1].calls if to == callee]
        pis.append(("0x" + hits[0][10 + 64 * hidx: 10 + 64 * (hidx + 1)]) if hits else None)
        f = field_of(receiver_bytes(t[-1], path), int(con["offset"]), int(con["width"]))
        fields.append(f)
    obs = {"runs": outs, "pi": pis, "field": fields}
    ok = outs == ["ok", "ok"] and pis[0] is not None and pis[0] == pis[1] and fields[0] != fields[1]
    return {"status": "passed" if ok else "failed", "observed": obs,
            "detail": "both runs succeed with one public input and different parent fields" if ok
            else "the real code does not behave as the witness says"}


def bisect(L, forge, jobs: int, log=print) -> dict:
    """D5 on the calibration harness: the least backlog whose call fails within G and succeeds within 2G."""
    from .laws_calibrate import CAL, CONTRACT, STATE, TEST, parse
    G = int(L.I.ceiling)
    probes = []
    memo = {}

    def ok_at(k: int, limit: int) -> bool:
        if (k, limit) not in memo:
            out = forge.run(CONTRACT, TEST, {"HOLON_K": k, "HOLON_TX_GAS": limit}, (STATE, CAL))
            _state, m = parse(out)
            if m["k"] != k:
                raise BundleError(f"backlog {k}: the harness ran another backlog")
            memo[(k, limit)] = bool(m["ok"])
            probes.append([k, limit, bool(m["ok"])])
            log(f"  D5 probe: backlog {k}, limit {limit}: {'ok' if m['ok'] else 'fail'}")
        return memo[(k, limit)]
    cal = L.calibration()
    lo = max(int(k) for k in cal["points"]) if cal else 1
    if not ok_at(lo, G):
        return {"k_star_real": None, "probes": probes, "note": f"the call fails within G at backlog {lo}"}
    hi = max(2 * lo, 2)
    from .laws import cost_coefficients, kstar
    co = cost_coefficients(cal)
    if co is not None:
        ks = kstar(co[0], co[1], G)
        if ks is not None:
            hi = max(hi, 2 * int(ks))
    while ok_at(hi, G):
        lo, hi = hi, 2 * hi
        if hi > 1 << 20:
            return {"k_star_real": None, "probes": probes, "note": "no failing backlog below 2^20"}
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ok_at(mid, G):
            lo = mid
        else:
            hi = mid
    k = hi
    below = {"backlog": k - 1, "within_G": "ok" if ok_at(k - 1, G) else "fail"}
    at = {"backlog": k, "within_G": "ok" if ok_at(k, G) else "fail", "within_2G": "ok" if ok_at(k, 2 * G) else "fail"}
    return {"k_star_real": k, "below": below, "at": at, "probes": sorted(probes)}


def replay_self(L, forge, jobs: int, log=print) -> dict:
    obs = bisect(L, forge, jobs, log)
    k = obs.get("k_star_real")
    ok = (k is not None and obs["below"] == {"backlog": k - 1, "within_G": "ok"}
          and obs["at"] == {"backlog": k, "within_G": "fail", "within_2G": "ok"})
    return {"status": "passed" if ok else "failed", "observed": obs,
            "detail": f"k*_real = {k}: the call succeeds within G at {k - 1} and fails within G, succeeds within 2G at "
                      f"{k}" if ok else f"D5 found no such backlog: {obs.get('note')}"}


def run(root: Path, check: bool, jobs: int = 2, only: list | None = None, log=print) -> int:
    from .laws import LawsCtx
    try:
        L = LawsCtx(root)
        recs = {}
        for lid in sorted(L.laws):
            p = _rec_path(L, lid)
            if p.is_file():
                recs[lid] = json.loads(p.read_text(encoding="utf-8"))
        if check:
            return check_report(L, recs)
        old = json.loads(L.replay_path.read_text(encoding="utf-8")) if L.replay_path.is_file() else {}
        laws = dict(old.get("laws") or {})
        from .laws_calibrate import Laws
        from .laws_forge import Forge
        Lc = Laws(L.root)
        forge = Forge(Lc.bctx, Lc.side, None)
        for lid, rec in recs.items():
            if only and lid not in only:
                continue
            e = L.laws[lid]
            if e["subform"] == "self_controlled":
                ent = replay_self(L, forge, jobs, log)
            elif rec.get("status") != "REFUTED":
                ent = {"status": "not_run", "observed": None, "detail": f"the law is {rec.get('status')}"}
            elif e["subform"] == "link_domain":
                ent = replay_link(L, forge, lid, rec)
            else:
                ent = replay_pi(L, forge, lid, rec)
            from .laws_decide import replay_key
            ent["key"] = replay_key(L, lid, rec)
            laws[lid] = ent
            log(f"holon bundle2 replay-laws: {lid}: {ent['status']}")
        rep = {"replay_version": REPLAY_VERSION, "laws": dict(sorted(laws.items())), "toolchain": forge.toolchain(),
               "deployment": {"versions": forge.versions, "init": forge.init}}
        w = Writer(False)
        w.put(L.replay_path, render(rep))
        for lid, rec in recs.items():
            ent = laws.get(lid)
            if ent is None:
                continue
            r2 = dict(rec, replay={"status": ent["status"], "detail": ent["detail"]})
            w.put(_rec_path(L, lid), (json.dumps(r2, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode())
        return w.finish("replay-laws")
    except Refused as e:
        print(f"holon bundle2 replay-laws: refused: {e}", file=sys.stderr)
        return 2
    except BundleError as e:
        print(f"holon bundle2 replay-laws: error: {e}", file=sys.stderr)
        return 3


def check_report(L, recs: dict) -> int:
    if not L.replay_path.is_file():
        print(f"holon bundle2 replay-laws: {L.replay_path.relative_to(L.root)} is missing", file=sys.stderr)
        return 1
    rep = json.loads(L.replay_path.read_text(encoding="utf-8"))
    bad = []
    if rep.get("replay_version") != REPLAY_VERSION:
        bad.append("replay_version")
    for lid, rec in recs.items():
        ent = (rep.get("laws") or {}).get(lid)
        want = (rec.get("replay") or {}).get("status")
        if ent is None:
            if want not in (None, "not_run"):
                bad.append(f"{lid}: no report entry, the record says {want}")
            continue
        if ent.get("status") != want:
            bad.append(f"{lid}: the report says {ent.get('status')}, the record {want}")
        if rec.get("status") == "REFUTED" and ent.get("status") != "passed":
            bad.append(f"{lid}: REFUTED with replay {ent.get('status')}")
    for b in bad:
        print(f"holon bundle2 replay-laws: {b}", file=sys.stderr)
    if not bad:
        print(f"holon bundle2 replay-laws: the report agrees with {len(recs)} records")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon bundle2 replay-laws", description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--root")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--laws", help="comma-separated law ids to replay (default: every law with a record)")
    a = ap.parse_args(argv)
    only = [x.strip() for x in a.laws.split(",")] if a.laws else None
    return run(Path(a.root).resolve() if a.root else ROOT, a.check, a.jobs, only)
