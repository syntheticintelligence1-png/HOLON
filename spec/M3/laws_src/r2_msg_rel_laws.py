"""AUDIT_R2 follow-up: O29/O34 stated as the obligations they violate (lead-authored, preregistered before any run).
The e2 laws state the observed behaviour and are PROVED, which bypasses G6 (AUDIT_R2 F1). Here each finding
is the payer/bearer or exit obligation, predicted REFUTED, so its closed witness trace goes through G6.
Messenger facts have no trace-search policy, so these are closed (binder-free) laws.
    python3 spec/M3/laws_src/r2_msg_rel_laws.py   ->  laws/M3_msg/L_msgr_*.json
"""
import hashlib, importlib.util, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_s = importlib.util.spec_from_file_location("e2_laws", ROOT / "spec/M3/laws_src/e2_laws.py")
E2 = importlib.util.module_from_spec(_s); _s.loader.exec_module(E2)
FACTS, MS = E2.FACTS["M3_msg"], "M3_msg"
W, S, EX, send, rep, wl, ok, rev = E2.W, E2.S, E2.EX, E2.send, E2.rep, E2.wl, E2.ok, E2.rev
WLO = [W, wl(5), send(value=0)]   # origin 5 whitelisted, caller 6 not

LAWS = [
  ("L_msgr_payer_bears_fee", "SORT", rev(WLO, rep(value=0), "Insufficient msg.value for fee"), "REFUTED", "O29 (F8)",
   "payer/bearer: a replay by a non-whitelisted caller (6) that pays 0 must fail the fee check; the waiver must follow the payer, not the origin _from."),
  ("L_msgr_sender_can_replay", "DISCH", ok(EX, rep(who=5, qi=4)), "REFUTED", "O34 (F8)",
   "exit obligation: after third-party replays, the original sender (5) can still replay its own message without owner action."),
]

def law(lid, rule, claim, pred, maps, notes):
    return {"ir_version": "holon-ir/0.2", "law_id": lid, "milestone": MS, "rule": rule, "subform": "obligation_scenario",
            "facts": FACTS, "facts_sha256": hashlib.sha256((ROOT / FACTS).read_bytes()).hexdigest(),
            "statement": {"binders": [], "assume": [], "claim": claim}, "notes": notes, "maps_to": maps, "predicted": pred}

def build():
    facts = json.loads((ROOT / FACTS).read_text())
    names = {a["name"] for a in facts["actions"]}
    msgs = set(map(str, facts["reasons"].values())) | set(facts["reasons"].keys())
    for lid, rule, c, p, m, n in LAWS:
        def chk(x):
            if isinstance(x, dict):
                if "act" in x: assert x["act"] in names, (lid, x["act"])
                if "reason" in x: assert x["reason"] in msgs, (lid, x["reason"])
                [chk(y) for y in x.values()]
            if isinstance(x, list): [chk(y) for y in x]
        chk(c)
        out = ROOT / "laws" / MS / f"{lid}.json"
        out.write_text(json.dumps(law(lid, rule, c, p, m, n), indent=2, sort_keys=True) + "\n")
        print(out.relative_to(ROOT))

if __name__ == "__main__":
    build()
