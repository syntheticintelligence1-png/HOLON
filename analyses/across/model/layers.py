"""Layer models of across-protocol/contracts @ b1c4e86 (2026-10-21).

Decomposition (see REPORT.md): the protocol is factored into key-indexed guard automata (claim keys), conservation
ledgers, an attestation layer, an authority layer and a channel layer. Each class below is one projection; every
transition cites the code that implements it. Abstract values are small integers; time is a block index.
"""

from collections import namedtuple

from engine import Inv

# ---------------------------------------------------------------------------------------------------------------------
# F: destination fill automaton for ONE relay hash h (key space K_fill = relayHash, scope = one spoke instance).
#   EVM: fillStatuses[h] in {Unfilled, RequestedSlowFill, Filled}  SpokePool.sol:122
#   SVM: PDA ["fills", h] in {absent, RequestedSlowFill, Filled}    state/fill.rs:10-16, closable (fill.rs:203-226)
# deadline dl = 1, exclusivityDeadline ed = 0; t in 0..3.
# ---------------------------------------------------------------------------------------------------------------------
FillS = namedtuple("FillS", "status t leaf pay")


class FillLayer:
    ASSUMPTIONS = ("A_clk",)  # destination clock is non-decreasing across transactions

    def __init__(self, impl):
        assert impl in ("EVM", "SVM")
        self.impl = impl
        self.NAME = f"F_fill[{impl}]"

    def init(self, A):
        return FillS("U" if self.impl == "EVM" else "X", 0, False, 0)

    def succ(self, s, A):
        dl, ed = 1, 0
        out = []
        live = s.t <= dl  # SpokePool.sol:1715 / fill.rs:116, slow_fill.rs:249: revert if fillDeadline < now
        # fill: EVM SpokePool.sol:986-1003,1707-1744 ; SVM fill.rs:90-179 (init_if_needed recreates a closed PDA)
        if live and s.status != "F":
            out.append(("fillRelay", s._replace(status="F", pay=min(s.pay + 1, 3))))
        # requestSlowFill: EVM SpokePool.sol:1157-1188 (requires Unfilled); SVM slow_fill.rs:51-96 (init_if_needed)
        if live and s.t > ed and s.status in ("U", "X"):
            out.append(("requestSlowFill", s._replace(status="R")))
        # dataworker publishes a slow-fill leaf only for requested slow fills (UMIP validity, off-chain)
        if s.status == "R" and not s.leaf:
            out.append(("publishSlowLeaf", s._replace(leaf=True)))
        # executeSlowRelayLeaf: EVM SpokePool.sol:1242-1266 -> _fillRelay (1715,1739-1740)
        #                       SVM slow_fill.rs:226-309: PDA must exist (`mut`, no init) and != Filled
        slow_ok = s.status in ("U", "R") if self.impl == "EVM" else s.status == "R"
        if s.leaf and live and slow_ok:
            out.append(("executeSlowRelayLeaf", s._replace(status="F", pay=min(s.pay + 1, 3))))
        # close_fill_pda: SVM only, fill.rs:216-226: relayer-signed, requires now > fill_deadline
        if self.impl == "SVM" and s.status in ("R", "F") and s.t > dl:
            out.append(("close_fill_pda", s._replace(status="X")))
        if s.t < 3:
            out.append(("tick", s._replace(t=s.t + 1)))
        if "A_clk" not in A and s.t > 0:
            out.append(("clockBack", s._replace(t=s.t - 1)))
        return out

    INVARIANTS = {
        "I_fill_once": Inv(
            "state",
            lambda s, A: s.pay <= 1,
            "each relay hash pays its recipient at most once (fast or slow), over the life of the spoke",
        )
    }


# ---------------------------------------------------------------------------------------------------------------------
# R: root-bundle binding. Ghost entitlements eX, eY = one refund leaf for chain X / chain Y inside the SAME roots.
# Key space for refunds: (spoke instance, rootBundleId, leafId)  SpokePool.sol:1550-1558 ; replay keys for root
# delivery: native bridge (one message per groupIndex-0 leaf, HubPool.sol:671-690) or Universal store nonces
# (HubPoolStore.sol:55-79, Universal_Adapter.sol:53-69, Universal_SpokePool.sol:126-164).
# ---------------------------------------------------------------------------------------------------------------------
Inst = namedtuple("Inst", "copies imported paid")
RootS = namedtuple(
    "RootS", "props prop leaves executed store uuid pendX pendY x1 x2 y1 payX payY yExec deployed2"
)


class RootLayer:
    ASSUMPTIONS = ("A_V1_oneG0", "A_V2_noRepropose", "A_exec_nonOwner", "A_inst_single")

    def __init__(self, channel):
        assert channel in ("native", "universal")
        self.ch = channel
        self.NAME = f"R_root[{channel}]"

    def init(self, A):
        e = Inst(0, frozenset(), frozenset())
        return RootS(0, 0, frozenset(), frozenset(), frozenset(), 0, 0, 0, e, None, e, 0, 0, False, False)

    @staticmethod
    def _chain(leaf):
        return leaf[0]

    def succ(self, s, A):
        out = []
        std = frozenset({"X0", "Y0"})
        dup = frozenset({"X0", "X0b", "Y0"})
        # proposeRootBundle HubPool.sol:560-594 (noActiveRequests). Leaves are the proposer's choice.
        if s.prop == 0 and s.props == 0:
            out.append(("propose[valid]", s._replace(props=1, prop=1, leaves=std, executed=frozenset())))
            if "A_V1_oneG0" not in A:
                out.append(("propose[two groupIndex-0 leaves for X]", s._replace(props=1, prop=1, leaves=dup, executed=frozenset())))
        if s.prop == 0 and s.props == 1 and "A_V2_noRepropose" not in A:
            out.append(("propose[same roots again]", s._replace(props=2, prop=2, leaves=std, executed=frozenset())))
        # executeRootBundle HubPool.sol:612-707 ; roots relayed iff groupIndex == 0 (671-690)
        if s.prop:
            callers = ["nonOwner"] + ([] if "A_exec_nonOwner" in A else ["owner"])
            for leaf in sorted(s.leaves - s.executed):
                c = self._chain(leaf)
                for who in callers:
                    t = s._replace(executed=s.executed | {leaf})
                    if c == "Y":
                        t = t._replace(yExec=True)
                    if self.ch == "native":
                        t = t._replace(pendX=t.pendX + 1) if c == "X" else t._replace(pendY=t.pendY + 1)
                    else:
                        if who == "owner":  # Universal_Adapter.sol:66 isAdminSender -> admin nonce, target=spoke
                            t = t._replace(store=t.store | {("adm", s.uuid, c)}, uuid=s.uuid + 1)
                        else:  # HubPoolStore.sol:63-70 nonce = challengePeriodEndTimestamp (one per proposal)
                            t = t._replace(store=t.store | {("ts", s.prop, "0")})
                    if t.executed == t.leaves:
                        t = t._replace(prop=0)
                    out.append((f"executeRootBundle[{leaf} by {who}]", t))
            # emergencyDeleteProposal HubPool.sol:229-240
            out.append(("emergencyDeleteProposal", s._replace(prop=0)))
        if self.ch == "native":
            if s.pendX:
                out.append(("bridge.deliver(relayRootBundle -> X)", s._replace(pendX=s.pendX - 1, x1=s.x1._replace(copies=s.x1.copies + 1))))
            if s.pendY:
                out.append(("bridge.deliver(relayRootBundle -> Y)", s._replace(pendY=s.pendY - 1, y1=s.y1._replace(copies=s.y1.copies + 1))))
        else:
            for key in sorted(s.store):
                for name in ("x1", "x2", "y1"):
                    inst = getattr(s, name)
                    if inst is None or key in inst.imported:
                        continue
                    chain = "X" if name[0] == "x" else "Y"
                    target_ok = key[2] == "0" or (key[2] == chain and name in ("x1", "y1"))  # target in {0, this}
                    if target_ok:
                        ni = inst._replace(copies=inst.copies + 1, imported=inst.imported | {key})
                        out.append((f"executeMessage[{name}, nonce={key[0]}:{key[1]}]", s._replace(**{name: ni})))
            if "A_inst_single" not in A and not s.deployed2:
                out.append(("deploy second Universal_SpokePool on X", s._replace(x2=Inst(0, frozenset(), frozenset()), deployed2=True)))
        # executeRelayerRefundLeaf SpokePool.sol:1276-1315 ; claimed key (rootBundleId, leafId) 1550-1558
        for name, pay in (("x1", "payX"), ("x2", "payX"), ("y1", "payY")):
            inst = getattr(s, name)
            if inst is None:
                continue
            for k in range(inst.copies):
                if k not in inst.paid:
                    ni = inst._replace(paid=inst.paid | {k})
                    out.append((f"executeRelayerRefundLeaf[{name}, rootBundleId={k}]", s._replace(**{name: ni, pay: getattr(s, pay) + 1})))
        return out

    INVARIANTS = {
        "I_refund_once": Inv(
            "state",
            lambda s, A: s.payX <= 1 and s.payY <= 1,
            "each refund entitlement in a root is paid at most once per chain (over all spoke instances)",
        ),
        "I_root_authorized": Inv(
            "state",
            lambda s, A: s.payY == 0 or s.yExec,
            "a chain pays from a root only if the HubPool executed that chain's groupIndex-0 leaf (deletion revokes)",
        ),
    }


# ---------------------------------------------------------------------------------------------------------------------
# L: HubPool LP ledger for one non-bond l1Token (exact Solidity floor arithmetic, SCALE stands for 1e18).
# Write sites of L,U,F,P: see sites.py (each write site is one transition here).
# ---------------------------------------------------------------------------------------------------------------------
LedS = namedtuple("LedS", "L U F B S P Out Arr pct")
SCALE = 100
CAP = 4
SCAP = 8


def _rate(s):  # HubPool.sol:920-940 (after accrual/sync)
    if s.S == 0:
        return SCALE
    n = s.L + s.U - s.F
    return (n * SCALE) // s.S if n >= 0 else None  # negative numerator: uint256 cast wraps -> mul overflow reverts


def _sync(s):  # HubPool.sol:958-971 (non-bond token)
    if s.B > s.L:
        return s._replace(U=s.U - (s.B - s.L), L=s.B)
    return s


class LedgerLayer:
    NAME = "L_ledger"
    MAX_DEPTH = None  # finite: every variable is bounded by CAP/SCAP guards
    ASSUMPTIONS = ("A_pct0", "A_noHaircut", "A_feesBacked")

    def init(self, A):
        return LedS(0, 0, 0, 0, 0, 0, 0, 0, 0)

    def succ(self, s, A):
        out = []
        if "A_pct0" not in A:  # setProtocolFeeCapture HubPool.sol:261-270
            for v in (50, 100):
                if s.pct != v:
                    out.append((f"setProtocolFeeCapture({v}%)", s._replace(pct=v)))
        # addLiquidity HubPool.sol:449-465 (rate first; supply==0 -> 1e18 without sync, 923)
        x = 2
        tot = s.B + s.Out + s.Arr  # total tokens in the system; bounded to keep the space finite
        if tot + x <= CAP and s.L + x <= 2 * CAP:
            t = _sync(s) if s.S > 0 else s
            r = _rate(t)
            if r:  # r == 0 divides by zero (457); r is None: negative numerator overflows (939)
                sh = (x * SCALE) // r
                if t.S + sh <= SCAP:
                    out.append((f"addLiquidity({x})", t._replace(L=t.L + x, B=t.B + x, S=t.S + sh)))
        # removeLiquidity HubPool.sol:476-496
        if s.S > 0:
            t = _sync(s)
            r = _rate(t)
            if r is not None:
                for sh, lab in ((t.S, "all"), (1, "1")):
                    y = (sh * r) // SCALE
                    if y <= t.L and y <= t.B:  # 487 underflow ; 493 token transfer
                        out.append((f"removeLiquidity({lab})", t._replace(S=t.S - sh, L=t.L - y, B=t.B - y)))
        # executeRootBundle leaf for this token: _sendTokensToChainAndUpdatePooledTokenTrackers 866-918 and
        # _allocateLpAndProtocolFees 995-1011. Fee tokens f sit on spokes (deposit spread) -> Out += f.
        for n in (0, 1, 2):
            for f in (0, 2):
                if n == 0 and f == 0:
                    continue
                if n > s.L or n > s.B or tot + f > CAP:
                    continue
                p = (f * s.pct) // 100
                lp = f - p
                if s.F + lp > CAP or s.P + p > CAP or s.U + n + lp > 2 * CAP:
                    continue
                t = s._replace(B=s.B - n, L=s.L - n, U=s.U + n + lp, F=s.F + lp, P=s.P + p, Out=s.Out + n + f)
                out.append((f"executeRootBundle(netSend={n}, bundleLpFees={f})", t))
                if "A_feesBacked" not in A and f:
                    t2 = t._replace(Out=s.Out + n)
                    out.append((f"executeRootBundle(netSend={n}, bundleLpFees={f}, fees unbacked)", t2))
        # spoke returns tokens (RelayerRefundLeaf.amountToReturn, SpokePool.sol:1506-1510) and bridge arrival
        if s.Out:
            out.append(("spoke.bridgeToHub(1)", s._replace(Out=s.Out - 1, Arr=s.Arr + 1)))
        if s.Arr:
            out.append(("bridge.arrive(1)", s._replace(Arr=s.Arr - 1, B=s.B + 1)))
        if s.B > s.L:
            out.append(("sync", _sync(s)))
        if s.F:  # _updateAccumulatedLpFees 943-956 (time passes, any interaction)
            out.append(("accrueLpFees(1)", s._replace(F=s.F - 1)))
        if s.P and s.P <= s.B:  # claimProtocolFeesCaptured 802-807
            out.append(("claimProtocolFeesCaptured", s._replace(B=s.B - s.P, P=0)))
        if tot < CAP and s.U > -CAP:
            out.append(("transfer(hub, 1) [donation]", s._replace(B=s.B + 1)))
        if "A_noHaircut" not in A and s.U > -CAP:  # haircutReserves 427-431
            out.append(("haircutReserves(1)", s._replace(U=s.U - 1)))
        return out

    @staticmethod
    def _exit_ok(s):
        t = _sync(s)
        r = _rate(t)
        if r is None:
            return False
        y = (t.S * r) // SCALE
        return y <= t.L and y <= t.B

    @staticmethod
    def _rate_step(s, label, t, A):
        if s.S == 0 or t.S == 0 or label.startswith("haircut"):
            return True
        rs, rt = _rate(_sync(s)), _rate(_sync(t))
        if rs is None or rt is None:
            return True
        return rt >= rs

    INVARIANTS = {
        "I_equity_nonneg": Inv(
            "state", lambda s, A: s.S == 0 or s.L + s.U - s.F >= 0, "supply > 0 => N = L + U - F >= 0 (exchange rate defined)"
        ),
        "I_backing": Inv("state", lambda s, A: s.L <= s.B, "liquidReserves <= token balance (accounting guard is physically backed)"),
        "I_solvency": Inv(
            "state",
            lambda s, A: s.L + s.U - s.F <= s.B + s.Out + s.Arr - s.P,
            "LP equity <= physical assets (hub + spokes + in flight) - protocol claims",
        ),
        "I_exit_at_zero_util": Inv(
            "state",
            lambda s, A: not (s.S > 0 and s.U <= 0) or LedgerLayer._exit_ok(s),
            "if reported utilization is 0, every LP share is redeemable",
        ),
        "I_rate_monotone": Inv("step", lambda s, l, t, A: LedgerLayer._rate_step(s, l, t, A), "exchange rate never decreases while supply > 0 (haircut excluded)"),
        "I_donation_neutral": Inv(
            "step",
            lambda s, l, t, A: not (l.startswith("transfer(hub") or l == "sync") or (s.L + s.U - s.F) == (t.L + t.U - t.F),
            "donations and sync never change LP equity (no share-inflation lever)",
        ),
    }


# ---------------------------------------------------------------------------------------------------------------------
# H: proposal / dispute / bond attestation layer (HubPool.sol:560-796, 846-850, UMA SkinnyOO requestId uniqueness).
# Block index = timestamp. ooReq = timestamps with an existing OO request for (HubPool, identifier, t, "").
# ---------------------------------------------------------------------------------------------------------------------
HubS = namedtuple("HubS", "prop phase count bonds blk ooReq ffHigh ooBroken freeRemovals")


class ProposalLayer:
    NAME = "H_proposal"
    # A_wl  : only whitelisted proposers can post a bond (BondToken.sol transferFrom; production bondToken = ABT)
    # A_hblk: a whitelisted proposer never lands a proposal in a block after a dispute of its own proposal
    # A_ff  : UMA Store finalFee(bondToken) < bondAmount (production: 0.055 < 0.45 ABT at block 26259843)
    # A_ooOK: identifier and bond token stay whitelisted in UMA (requestAndProposePriceFor does not revert)
    ASSUMPTIONS = ("A_wl", "A_hblk", "A_ff", "A_ooOK")

    def init(self, A):
        return HubS(None, None, 0, 0, 0, frozenset(), False, False, 0)

    def succ(self, s, A):
        out = []
        same_block_reqs = {k for (b, k) in s.ooReq if b == s.blk}
        if s.prop is None:
            if "A_hblk" not in A or "H" not in same_block_reqs:
                out.append(("proposeRootBundle[honest]", s._replace(prop="H", phase="live", count=2, bonds=s.bonds + 1)))
            if "A_wl" not in A:
                out.append(("proposeRootBundle[attacker]", s._replace(prop="A", phase="live", count=2, bonds=s.bonds + 1)))
        if s.prop and s.phase == "live":  # disputeRootBundle 715-796 ; liveness check 717
            cancel = s.ffHigh or s.ooBroken or bool(same_block_reqs)  # 737-740 ; try/catch 746-771
            if cancel:  # _cancelBundle 846-850: bond back to proposer, no disputer bond, no DVM request
                t = s._replace(prop=None, phase=None, count=0, bonds=s.bonds - 1,
                               freeRemovals=min(2, s.freeRemovals + (1 if s.prop == "H" else 0)))
                out.append(("disputeRootBundle -> _cancelBundle", t))
            else:
                t = s._replace(prop=None, phase=None, count=0, bonds=s.bonds - 1, ooReq=s.ooReq | {(s.blk, s.prop)})
                out.append(("disputeRootBundle -> requestAndProposePriceFor + disputePriceFor (DVM)", t))
        if s.prop and s.phase == "past":  # executeRootBundle 622, 653, 694-695
            t = s._replace(count=s.count - 1)
            if t.count == 0:
                t = t._replace(prop=None, phase=None, bonds=s.bonds - 1)
            out.append(("executeRootBundle", t))
        if s.prop:  # emergencyDeleteProposal 229-240
            out.append(("emergencyDeleteProposal", s._replace(prop=None, phase=None, count=0, bonds=s.bonds - 1)))
        if s.blk < 2:
            out.append(("nextBlock", s._replace(blk=s.blk + 1)))
            if s.prop and s.phase == "live":
                out.append(("nextBlock[liveness ends]", s._replace(blk=s.blk + 1, phase="past")))
        if "A_ff" not in A and not s.ffHigh:
            out.append(("UMA: finalFee(bondToken) >= bondAmount", s._replace(ffHigh=True)))
        if "A_ooOK" not in A and not s.ooBroken:
            out.append(("UMA: de-whitelist identifier or collateral", s._replace(ooBroken=True)))
        return out

    INVARIANTS = {
        "I_dispute_escalates": Inv(
            "state",
            lambda s, A: s.freeRemovals == 0,
            "an honest proposal leaves liveness only by DVM escalation with a disputer bond, by execution or by admin",
        ),
        "I_bond_custody": Inv("state", lambda s, A: s.bonds == (1 if s.prop else 0), "bond held by HubPool iff a proposal is active"),
    }


# ---------------------------------------------------------------------------------------------------------------------
# B: bond collateral vs pooled reserves when the bond token may also be a pooled LP token (HubPool.sol:904, 963-964,
# 694-695, 229-233, 802-807).
# ---------------------------------------------------------------------------------------------------------------------
BondS = namedtuple("BondS", "L B active count P pct")


class BondLedgerLayer:
    NAME = "B_bond_vs_reserves"
    ASSUMPTIONS = ("A_bondNotPooled", "A_pct0")
    BOND = 2

    def init(self, A):
        return BondS(0, 0, False, 0, 0, 0)

    def succ(self, s, A):
        out = []
        pooled = "A_bondNotPooled" not in A
        bal_sans = s.B - (self.BOND if (pooled and s.active) else 0)  # 963-964 (only if pooled)
        if "A_pct0" not in A and s.pct == 0:
            out.append(("setProtocolFeeCapture(100%)", s._replace(pct=100)))
        if s.L < 4 and bal_sans >= 0:
            out.append(("addLiquidity(2)", s._replace(L=s.L + 2, B=s.B + 2)))
        if not s.active:
            out.append(("proposeRootBundle(2 leaves)", s._replace(active=True, count=2, B=s.B + (self.BOND if pooled else 0))))
        if s.active:
            # fee leaf (no send) / send leaf (netSend = n <= L). Last leaf refunds the bond 694-695.
            for n, f in ((0, 2), (1, 0), (2, 0), (3, 0), (4, 0)):
                if n > s.L or n > s.B or s.P + (f * s.pct) // 100 > 4:
                    continue
                t = s._replace(L=s.L - n, B=s.B - n, P=s.P + (f * s.pct) // 100, count=s.count - 1)
                if t.count == 0:
                    if pooled and t.B < self.BOND:
                        continue  # safeTransfer(proposer, bondAmount) reverts
                    t = t._replace(active=False, B=t.B - (self.BOND if pooled else 0))
                out.append((f"executeRootBundle(netSend={n}, fee={f})", t))
            if not (pooled and s.B < self.BOND):
                out.append(("emergencyDeleteProposal", s._replace(active=False, count=0, B=s.B - (self.BOND if pooled else 0))))
        if s.P and s.P <= s.B:
            out.append(("claimProtocolFeesCaptured", s._replace(B=s.B - s.P, P=0)))
        return out

    INVARIANTS = {
        "I_hub_live": Inv(
            "state",
            lambda s, A: not s.active or "A_bondNotPooled" in A or s.B >= BondLedgerLayer.BOND,
            "while a proposal is active the HubPool can always refund the bond (last leaf / emergency delete live)",
        )
    }


# ---------------------------------------------------------------------------------------------------------------------
# A: authority of onlyAdmin as a predicate over call frames (SpokePool.sol:296-299, 325, 413-427).
#   principal-based: Arbitrum/ZkSync (alias check), Ovm (messenger+xDomainSender), Linea, Ethereum (owner)
#   flag-based:      Polygon (callValidated: Polygon_SpokePool.sol:63-74,155,291), Universal and Tron
#                    (_adminCallValidated: Universal_SpokePool.sol:62-70,126,166,206)
# ---------------------------------------------------------------------------------------------------------------------
AuthS = namedtuple("AuthS", "stage flag upgradedBy")


class AuthorityLayer:
    ASSUMPTIONS = ("A_closedCallees",)

    def __init__(self, kind):
        assert kind in ("principal", "flag")
        self.kind = kind
        self.NAME = f"A_authority[{kind}]"

    def init(self, A):
        return AuthS("idle", False, None)

    def _auth(self, s, principal_is_admin):
        return (self.kind == "flag" and s.flag) or (self.kind == "principal" and principal_is_admin)

    def succ(self, s, A):
        out = []
        if s.stage == "idle":
            out.append(("adminMessage.begin", s._replace(stage="admin", flag=(self.kind == "flag"))))
            if self._auth(s, False):
                out.append(("anyone.upgradeTo", s._replace(upgradedBy="other")))
        if s.stage == "admin":
            out.append(("admin.upgradeTo", s._replace(upgradedBy=s.upgradedBy or "admin")))
            if "A_closedCallees" not in A:
                out.append(("admin.executeExternalCall(T) yields control", s._replace(stage="callee")))
            out.append(("adminMessage.end", s._replace(stage="idle", flag=False)))
        if s.stage == "callee":
            if self._auth(s, False):
                out.append(("T.upgradeTo(evil) [callback]", s._replace(upgradedBy="callee")))
            out.append(("T returns", s._replace(stage="admin")))
        return out

    INVARIANTS = {
        "I_admin_principal": Inv("state", lambda s, A: s.upgradedBy in (None, "admin"), "only the admin principal exercises onlyAdmin"),
    }


# ---------------------------------------------------------------------------------------------------------------------
# C: ordering of admin messages on a channel. m0 = pauseDeposits(false), m1 = pauseDeposits(true) issued in that
# order (HubPoolStore dataUuid++ ; CCTP nonce). Universal_SpokePool.executeMessage / svm handle_receive_message
# impose no sequence check.
# ---------------------------------------------------------------------------------------------------------------------
ChanS = namedtuple("ChanS", "delivered paused")


class ChannelLayer:
    NAME = "C_channel"
    ASSUMPTIONS = ("A_fifo",)

    def init(self, A):
        return ChanS((), None)

    def succ(self, s, A):
        out = []
        for m, v in ((0, False), (1, True)):
            if m in s.delivered:
                continue
            if "A_fifo" in A and m != len(s.delivered):
                continue
            out.append((f"deliver(m{m}: pauseDeposits({str(v).lower()}))", s._replace(delivered=s.delivered + (m,), paused=v)))
        return out

    INVARIANTS = {
        "I_last_writer": Inv(
            "state",
            lambda s, A: len(s.delivered) < 2 or s.paused is True,
            "after all messages are delivered, spoke state equals the effect of the last-issued message",
        )
    }


# ---------------------------------------------------------------------------------------------------------------------
# D: deposit-id binding of unsafe deposits (EVM SpokePool.sol:675-712 vs SVM deposit.rs:252-305 + DepositSeedData).
# The depositor authorises funds; the id a relayer pre-computes is H(signer, depositor, nonce).
# ---------------------------------------------------------------------------------------------------------------------
DepS = namedtuple("DepS", "authorized deposited prefilled")


class DepositIdLayer:
    ASSUMPTIONS = ("A_atomicAuth",)

    def __init__(self, impl):
        assert impl in ("EVM", "SVM")
        self.impl = impl
        self.NAME = f"D_unsafe_id[{impl}]"

    def init(self, A):
        return DepS(False, None, False)

    def succ(self, s, A):
        out = []
        if not s.prefilled and s.deposited is None:
            out.append(("relayer prefills relayHash(expected id)", s._replace(prefilled=True)))
        if s.deposited is None:
            if "A_atomicAuth" in A:
                out.append(("depositor: approve+unsafeDeposit(nonce) in one tx", s._replace(authorized=True, deposited="expected")))
            elif not s.authorized:
                out.append(("depositor: approve delegate", s._replace(authorized=True)))
            if s.authorized and "A_atomicAuth" not in A:
                out.append(("depositor: unsafeDeposit(nonce)", s._replace(deposited="expected")))
                if self.impl == "SVM":  # seed hash binds params but not (signer, nonce); depositor need not sign
                    out.append(("anyone: deposit()/unsafe_deposit(other nonce) with depositor's delegation", s._replace(deposited="other")))
        return out

    INVARIANTS = {
        "I_unsafe_id_bound": Inv(
            "state",
            lambda s, A: s.deposited in (None, "expected"),
            "the deposit consuming the depositor's funds carries the id the depositor chose",
        )
    }


LAYERS = [
    FillLayer("EVM"),
    FillLayer("SVM"),
    RootLayer("native"),
    RootLayer("universal"),
    LedgerLayer(),
    ProposalLayer(),
    BondLedgerLayer(),
    AuthorityLayer("principal"),
    AuthorityLayer("flag"),
    ChannelLayer(),
    DepositIdLayer("EVM"),
    DepositIdLayer("SVM"),
]
