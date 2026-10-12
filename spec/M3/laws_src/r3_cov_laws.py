"""M3 coverage laws for the G8 holes left after AUDIT_R2 (lead-authored, preregistered before any run).
Each law is a closed scenario on an action or register no earlier law touched. Every prediction comes
from the pinned Solidity source, not from the model. A miss is a published surprise, never a fix to the law.
    python3 spec/M3/laws_src/r3_cov_laws.py   ->  laws/M3_{nat,msg,router}/L_cov_*.json
"""
import hashlib, importlib.util, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_s = importlib.util.spec_from_file_location("e2_laws", ROOT / "spec/M3/laws_src/e2_laws.py")
E2 = importlib.util.module_from_spec(_s); _s.loader.exec_module(E2)
act, ok, rev, W, send, upd = E2.act, E2.ok, E2.rev, E2.W, E2.send, E2.upd
FACTS = {"M3_nat": "spec/M3/extracted/morph_rollup.json", "M3_msg": E2.FACTS["M3_msg"], "M3_router": E2.FACTS["M3_router"]}
OWN = "Ownable: caller is not the owner"

def not_ok(setup, probe): return {"eq": [{"fn": "last_ok", "args": [{"step": probe, "from": E2.run_of(setup)}]}, {"bool": False}]}

# ---- M3_nat (Rollup.sol). s0: t=10, W=10, F=40, D=20, owner 1, active [2,3]; genesis batch 0 at t=10.
msg = act("sendMessage", who=5)
def wait(dt): return act("wait", dt=dt)
def bd(fn, who=2, parent=0, prev=100, post=101, blobs=(7,), **x):
    return act(fn, who=who, ver=1, parent=parent, n=1, lbn=parent + 1, prev=prev, post=post, blobs=list(blobs), **x)
def rb(who=1, idx=1, count=1): return act("revertBatch", who=who, idx=idx, count=count)
def fin(idx=1, who=5): return act("finalizeBatch", who=who, idx=idx)
def sp(status, who=1): return act("setPause", who=who, status=status)
C1 = [msg, bd("commitBatch")]                      # batch 1 committed at t=10, finalizeTimestamp 50
NAT = [
  ("L_cov_finalize_window", "DISCH", rev(C1, fin(), "batch in challenge window"), "Rollup.sol:633 finalizeTimestamp(50) > t(10)"),
  ("L_cov_finalize_after", "DISCH", ok(C1 + [wait(41)], fin()), "Rollup.sol:625-650 at t=51 batch 1 finalizes; fsr[0]=100=prev"),
  ("L_cov_revert_owner", "UNDO", rev(C1, rb(who=5), OWN), "Rollup.sol:430 onlyOwner"),
  ("L_cov_revert_count0", "UNDO", rev(C1, rb(count=0), "count must be nonzero"), "Rollup.sol:431"),
  ("L_cov_revert_ok", "UNDO", ok(C1, rb()), "Rollup.sol:430-462 owner reverts the last unfinalized batch"),
  ("L_cov_commitstate_nohash", "SORT", rev([msg], bd("commitState", blobs=()), "no stored blob hash for this batch"), "Rollup.sol:279"),
  ("L_cov_commitstate_after_revert", "UNDO", ok(C1 + [rb()], bd("commitState", blobs=())), "Rollup.sol:273-286 recommit on the stored blob hash after revertBatch"),
  ("L_cov_cbwp_timing", "DISCH", rev([msg], bd("commitBatchWithProof", who=5, proof=1), "invalid timing"), "Rollup.sol:388-400 neither delay elapsed at t=10 (D=20)"),
  ("L_cov_pause_owner", "SORT", rev([], sp(True, who=5), OWN), "Rollup.sol:573 onlyOwner"),
  ("L_cov_pause_blocks_commit", "SORT", rev([sp(True), msg], bd("commitBatch"), "Pausable: paused"), "Rollup.sol:573 + whenNotPaused"),
  ("L_cov_unpause_unpaused", "SORT", rev([], sp(False), "Pausable: not paused"), "OZ PausableUpgradeable whenPaused"),
  ("L_cov_delay_same", "SORT", rev([], act("updateRollupDelayPeriod", who=1, p=20), "invalid new rollup delay period"), "Rollup.sol:519"),
  ("L_cov_delay_ok", "SORT", ok([], act("updateRollupDelayPeriod", who=1, p=30)), "Rollup.sol:518-522"),
  ("L_cov_window_same", "SORT", rev([], act("updateProofWindow", who=1, w=10), "invalid new proof window"), "Rollup.sol:501"),
  ("L_cov_window_ok", "SORT", ok([], act("updateProofWindow", who=1, w=20)), "Rollup.sol:500-504"),
  ("L_cov_finper_same", "SORT", rev([], act("updateFinalizePeriodSeconds", who=1, p=40), "invalid new finalize period"), "Rollup.sol:510"),
  ("L_cov_finper_ok", "SORT", ok([], act("updateFinalizePeriodSeconds", who=1, p=50)), "Rollup.sol:509-513"),
  ("L_cov_verifier_owner", "SORT", rev([], act("updateVerifier", who=5, nv=8), OWN), "Rollup.sol updateVerifier onlyOwner"),
  ("L_cov_verifier_ok", "SORT", ok([], act("updateVerifier", who=1, nv=8)), "Rollup.sol updateVerifier"),
  ("L_cov_init3_zero", "SORT", rev([], act("initialize3", who=1, dly=0), "invalid rollup delay period"), "Rollup.sol:200"),
  ("L_cov_init3_anyone", "SORT", ok([], act("initialize3", who=5, dly=5)), "Rollup.sol:199 reinitializer(3) has no caller check (B2 finding; one-shot-ness is debt)"),
]
# ---- M3_msg (L1CrossDomainMessenger.sol)
def send2(xh=11, who=5, value=4): return act("sendMessage2", who=who, to=9, val=0, gl=1, ra=5, xh=xh, value=value, mn=0, amt=4)
MSG = [
  ("L_cov_send2_ok", "SORT", ok([W], send2()), "L1CrossDomainMessenger.sol:112-118 refund-address overload enqueues"),
  ("L_cov_send2_dup", "SORT", rev([W, send()], send2(), "Duplicated message"), "L1CrossDomainMessenger.sol:304 both overloads share messageSendTimestamp"),
]
# ---- M3_router (MultipleVersionRollupVerifier.sol)
def ini(who=1, r=5): return act("initialize", who=who, r=r)
def vap(v, idx, who=5): return act("verifyAggregateProof", who=who, v=v, idx=idx)
ROUTER = [
  ("L_cov_rt_init_ok", "SORT", ok([], ini()), "MVRV:80-84 first initialize by the owner succeeds"),
  ("L_cov_rt_init_once", "SORT", rev([ini()], ini(r=6), "initialized"), "MVRV:81"),
  ("L_cov_rt_init_owner", "SORT", rev([], ini(who=5), OWN), "MVRV:80 onlyOwner"),
  ("L_cov_rt_vap_registered", "PAR", ok([upd(0, 1, 8, 0)], vap(0, 2)), "MVRV:130-139 registered version routes (verifyBatch is an oracle)"),
  ("L_cov_rt_vap_unregistered_fails", "PAR", not_ok([], vap(3, 1)), "MVRV:118 getVerifier reverts ErrorVerifierNotFound for an unregistered version"),
]

def law(ms, lid, rule, claim, notes):
    f = FACTS[ms]
    return {"ir_version": "holon-ir/0.2", "law_id": lid, "milestone": ms, "rule": rule, "subform": "coverage_scenario",
            "facts": f, "facts_sha256": hashlib.sha256((ROOT / f).read_bytes()).hexdigest(),
            "statement": {"binders": [], "assume": [], "claim": claim}, "notes": notes, "predicted": "PROVED"}

def build():
    for ms, tab in (("M3_nat", NAT), ("M3_msg", MSG), ("M3_router", ROUTER)):
        facts = json.loads((ROOT / FACTS[ms]).read_text())
        names = {a["name"]: {i[0] for i in a["inputs"]} for a in facts["actions"]}
        msgs = set(map(str, facts["reasons"].values()))
        for lid, rule, c, n in tab:
            def chk(x):
                if isinstance(x, dict):
                    if "act" in x:
                        assert x["act"] in names, (lid, x["act"])
                        assert set(x["args"]) == names[x["act"]], (lid, x["act"], sorted(x["args"]), sorted(names[x["act"]]))
                    if "reason" in x: assert x["reason"] in msgs, (lid, x["reason"])
                    [chk(y) for y in x.values()]
                if isinstance(x, list): [chk(y) for y in x]
            chk(c)
            out = ROOT / "laws" / ms / f"{lid}.json"
            out.write_text(json.dumps(law(ms, lid, rule, c, n), indent=2, sort_keys=True) + "\n")
            print(out.relative_to(ROOT))

if __name__ == "__main__":
    build()
