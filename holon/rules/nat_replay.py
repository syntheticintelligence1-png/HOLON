"""Rule N9: `python -m holon nat replay [--check]`, rule NAT's REFUTED witnesses on the real code (BUILD_PLAN I29; the
contract is the docstring of tests_m3/test_nat.py).

Per REFUTED NAT record two runs through I28's versioned harness (holon.versions.replay: the OpenZeppelin 4.9.3
TransparentUpgradeableProxy over the placeholder, every path version's implementation built from its commit, the
labelled stand-ins): "<id>:left", the witness's trace then its left steps (the migration, then the op at the new
version), and "<id>:right", the trace then its right steps (the op at the old version, then the migration). Each is
compared step by step as I28's runs are (statuses, revert data, the words of the union of the model's and the real
step's written slots, the proxy's EIP-1967 slots aside) and passes when every step agrees. The report is
replay/<M>/nat/report.json; G6 binds each REFUTED NAT record to its two passed runs (witness_sha256), and `stamp` brings
the records' replay fields up to the report. A disagreement is reported, never smoothed.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

REPLAY_VERSION = "holon-nat-replay/0.1"


def witness_sha256(w: dict) -> str:
    return hashlib.sha256(json.dumps(w, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def run_steps(w: dict, side: str) -> list:
    """The trace of a witness's run (side "left" or "right"): its trace, then the square's steps of that side."""
    return list(w.get("trace") or []) + [{k: v for k, v in st.items() if k != "revert"}
                                         for st in (w.get("square") or {}).get(side) or []]


def load(nctx) -> dict | None:
    p = nctx.root / nctx.out("replay")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def replay_status(nctx, rep: dict | None, lid: str, witness: dict | None) -> dict:
    """A REFUTED NAT record's replay field from the report: passed or failed only when the report's runs <lid>:left and
    <lid>:right replayed this witness (their traces and its sha256), else not_run."""
    rel = nctx.out("replay")
    if not isinstance(rep, dict):
        return {"status": "not_run", "detail": f"no replay report ({rel})"}
    runs = {}
    for side in ("left", "right"):
        rs = [r for r in rep.get("runs") or [] if isinstance(r, dict) and r.get("name") == f"{lid}:{side}"]
        if len(rs) != 1:
            return {"status": "not_run", "detail": f"{rel} has {len(rs)} runs named {lid}:{side}"}
        r = rs[0]
        if not isinstance(witness, dict) or r.get("witness_sha256") != witness_sha256(witness) \
                or r.get("trace") != run_steps(witness, side):
            return {"status": "not_run", "detail": f"{rel}'s run {lid}:{side} replayed another witness"}
        runs[side] = r
    ok = all(r.get("passed") is True for r in runs.values())
    n = sum(len(r.get("steps") or []) for r in runs.values())
    return {"status": "passed" if ok else "failed",
            "detail": f"runs {lid}:left and {lid}:right of {rel}: {n} steps, statuses, revert data and words "
                      + ("agree" if ok else "disagree")}


def refuted(nctx) -> dict:
    """{law id: record} of the REFUTED NAT records."""
    from .nat_run import nat_entries
    out = {}
    for lid in sorted(nat_entries(nctx.milestone, nctx.root)):
        p = nctx.root / "results" / nctx.milestone / f"{lid}.json"
        if not p.is_file():
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        if rec.get("status") == "REFUTED" and rec.get("witness"):
            out[lid] = rec
    return out


def report(nctx, log=None) -> dict:
    from ..versions.machine import Machine, cd_bytes
    from ..versions import replay as VR
    m = Machine(nctx.vctx)
    try:
        plan = VR.Plan(m)
        for lid, rec in refuted(nctx).items():
            w = rec["witness"]
            for side in ("left", "right"):
                plan.add(f"{lid}:{side}", run_steps(w, side), extra={"witness_sha256": witness_sha256(w)})
        cfgs = VR.matched_configs(nctx.vctx)
        impls, meta = [], {}
        for vid in m.path:
            b = VR.build_implementation(nctx.vctx, vid, cfgs[vid])
            impls.append(b["creation"] + VR.constructor_args(m, b["abi"]))
            meta[vid] = {"commit": b["commit"], "config": cfgs[vid]}
        called = {int(str(c["to"]), 0) if isinstance(c["to"], str) else c["to"] for run in plan.runs
                  for o in run["outs"] for c in o.get("calls") or [] if c.get("to") is not None}
        runs = []
        toolchain = None
        if plan.runs:
            data = VR.harness_input(nctx.vctx, m, plan, impls, called)
            work = Path(tempfile.mkdtemp(prefix="holon-nat-replay-"))
            try:
                res = VR.run_harness(nctx.vctx, data, work)
            finally:
                shutil.rmtree(work, ignore_errors=True)
            out = res["out"]
            toolchain = res["toolchain"]
            for i, vid in enumerate(m.path):
                meta[vid]["code_sha256"] = hashlib.sha256(cd_bytes(out["K"].get(i, "0x"))).hexdigest()
            runs = [VR.compare(nctx.vctx, run, r, out) for r, run in enumerate(plan.runs)]
        if log:
            for x in runs:
                log(f"{x['name']}: {'passed' if x['passed'] else 'FAILED'} ({len(x['steps'])} steps)")
        return {"replay_version": REPLAY_VERSION, "toolchain": toolchain, "implementations": meta, "runs": runs}
    finally:
        m.close()


def stamp(nctx, rep: dict) -> list:
    """Bring the REFUTED NAT records' replay field up to the report; the ids changed."""
    changed = []
    for lid, rec in refuted(nctx).items():
        new = replay_status(nctx, rep, lid, rec.get("witness"))
        if new != rec.get("replay"):
            rec["replay"] = new
            p = nctx.root / "results" / nctx.milestone / f"{lid}.json"
            p.write_text(json.dumps(rec, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
            changed.append(lid)
    return changed


def run(nctx, check: bool) -> int:
    from ..versions import render, write_or_check
    doc = report(nctx, log=lambda s: print(f"holon nat replay: {s}"))
    target = nctx.root / nctx.out("replay")
    ok = write_or_check(target, render(doc), check)
    if check:
        print(f"holon nat replay: {nctx.out('replay')} {'reproduces' if ok else 'differs from a fresh replay'}")
        return 0 if ok else 1
    print(f"holon nat replay: wrote {nctx.out('replay')} ({sum(1 for r in doc['runs'] if r['passed'])} of "
          f"{len(doc['runs'])} runs passed)")
    for lid in stamp(nctx, doc):
        print(f"holon nat replay: {lid}: record replay field brought up to the report")
    return 0


# ------------------------------------------------------------------------------------------------ the gate and filter
def _nctx(milestone: str, root):
    from .nat_run import NatCtx, SIDECAR
    root = Path(root)
    if not (root / SIDECAR.format(milestone)).is_file():
        return None
    return NatCtx(root, milestone)


def g6(milestone: str, root) -> tuple[bool, str] | None:
    """G6 over the NAT laws of a milestone with a NAT sidecar (None without one): every REFUTED NAT record is bound to
    its two passed runs of the NAT replay report (its witness's sha256), and its replay field says so."""
    from .nat_run import nat_entries
    nctx = _nctx(milestone, root)
    if nctx is None:
        return None
    rep = load(nctx)
    bad, n = [], 0
    for lid in sorted(nat_entries(milestone, nctx.root)):
        p = nctx.root / "results" / milestone / f"{lid}.json"
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            bad.append(f"{lid}: no readable result record")
            continue
        if not isinstance(rec, dict) or rec.get("status") != "REFUTED":
            continue
        n += 1
        st = replay_status(nctx, rep, lid, rec.get("witness"))
        if st["status"] != "passed":
            bad.append(f"{lid}: {st['detail']}")
        elif rec.get("replay") != st:
            bad.append(f"{lid}: the record's replay field is not the report's ({(rec.get('replay') or {}).get('status')})")
    return not bad, (f"{n} REFUTED NAT records bound to passed runs of {nctx.out('replay')}" if not bad
                     else "; ".join(bad))


def side(root, milestone: str, lid: str, witness: dict | None) -> dict | None:
    """The replay side (holon.filter's sides format) of a REFUTED NAT record from its two runs, None when there is no
    NAT sidecar or the report has no runs of this witness. The runs are public schedules on a deployed system. The
    obstruction is observed when both runs passed and, on the real chain, the two runs' last steps disagree in the
    square's way: the op's success differs between the left and the right run, or their final written words differ."""
    nctx = _nctx(milestone, root)
    if nctx is None:
        return None
    rep = load(nctx)
    st = replay_status(nctx, rep, lid, witness)
    if st["status"] == "not_run":
        return None
    runs = {s: next(x for x in rep["runs"] if x.get("name") == f"{lid}:{s}") for s in ("left", "right")}
    L, R = runs["left"]["steps"], runs["right"]["steps"]
    op_left, op_right = L[-1]["real"], R[-2]["real"]
    seen = bool(st["status"] == "passed" and op_left != op_right)
    return {"status": st["status"], "provenance": "public_schedule", "obstruction_observed": seen,
            "run": f"{lid}:left,{lid}:right", "report": nctx.out("replay"),
            "basis": (f"runs {lid}:left and {lid}:right of {nctx.out('replay')}: every step agrees with the model; on the "
                      f"real code the op {'succeeds' if op_right == 'ok' else 'reverts'} before the migration and "
                      f"{'succeeds' if op_left == 'ok' else 'reverts'} after it") if seen else
                     f"runs {lid}:left and {lid}:right of {nctx.out('replay')}: the real op's outcome does not differ "
                     "between the two orders"}
