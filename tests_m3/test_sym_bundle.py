"""I92 (= I34b) contract: rule SYM over Bundle I (O21 and the messenger's sentinels).

I34 states SYM over the typed Rollup alone (tests_m3/test_sym.py J12). I92 builds the three prerequisites I34's J1 scope
names (the queue's enqueue actions in model3, a migrated legacy-queue state, nominal sorts over the bundle members) and
derives SYM's tau and sentinel laws over the queue and the messenger, with O21 as a sentinel invariant over the versioned
queue. Its instrument is tests_m3/_i92.py (independent of holon/); its sidecar spec/M3/lib/sym_bundle.json and basis
spec/M3/lib/sym_bundle_basis.json are fixed here.

K1 Members. The queue (L1MessageQueueWithGasPriceOracle) and the messenger (L1CrossDomainMessenger): I69's documents
   gen/M3/bundle/documents/queue.json and messenger.json at the pinned head (sidecar target.head). The legacy queue is
   the same contract at sidecar legacy.tag (v0.4.9, the last tag before messageEnqueueTime and
   getFirstUnfinalizedMessageEnqueueTime enter, at v0.4.10), extracted with I69's frontend and sidecar into
   gen/M3/symb/legacy/queue.json.
K2 Sorts. gen/M3/symb/sorts.json {"symb_version", "members": {member: {"time": [..], "idx": [..], "idx_keys": [..]}}}
   holds the members' nominal sorts: a register path ("family" or "family.member") whose value sort is Time or Idx, and a
   map family whose key domain is Idx. A term is Time when it is env block.timestamp, a read of a Time register or a call
   answer whose callee action's return term is Time; Idx when it is the length of a storage array, a read of an Idx
   register, a call answer whose callee's return term is Idx, or a trunc or a constant addition over an Idx term. A
   register takes a sort when a write stores a term of it there or a comparison sets it against one; a map's key domain
   is Idx when a write or a read indexes it with an Idx term. The instrument computes the same fixed point.
K3 Link and versions. The link runs the messenger's calls to the queue (nextCrossDomainMessageIndex,
   appendCrossDomainMessage) with the queue's extracted actions (the lastIndex sentinel law). The versioned queue runs the
   legacy document until an upgrade step and the head document after it (the O21 invariant). eta_enq
   (gen/M3/symb/eta_enq.json {"from": {"tag", "commit", "document_sha256"}, "to": {...}, "map": [{"register",
   "from_slot", "to_slot"}], "fresh": [register]}) maps each legacy register to the head register of the same name and
   slot and lists the head registers the legacy layout lacks, which the upgrade leaves empty. The Bend linked layer and
   versioned reach are I94's (its P5: a link spec parametric in the callee member, its kind and the caller version;
   sidecar depends_on); a piece it does not provide I92 writes under gen/M3/symb/.
K4 Sentinels (whitepaper §5.4: constants compared against Time- or Idx-sorted registers). A sentinel register is a Time
   or Idx register compared against an integer constant in a guard, a check, a view's return or a write's condition;
   one sentinel law per write of it whose value is not the literal constant. On the members: messageEnqueueTime (queue,
   0: the getter's != 0), messageSendTimestamp (messenger, 0: sendMessage's == 0, replayMessage's > 0) and
   replayStates.lastIndex (messenger, 0: replayMessage's == 0 before prevReplayIndex). A Time sentinel law has I34's
   premise block_timestamp(x) >= 1; the lastIndex law is stated over the messenger-queue link (K3), where the value is
   the queue's length. A view whose return is a conditional on a conjunction holding R != c (R a sentinel register, c
   its constant) next to another conjunct G reads c as absence under G: one sentinel invariant per such view, stated
   over the versioned member (K3) with every reach step's block_timestamp >= 1 (on chain no block has timestamp 0; a
   premise, disclosed): on every reachable state, G implies R != c. On the queue: the getter's
   pendingQueueIndex < length => messageEnqueueTime[pendingQueueIndex] != 0, which O21 states.
K5 Laws (holon-ir/0.3, I34's terms and templates):
   - tau, one per member action touching a Time word: L_sym_tau_<Contract>_<action>, I34's statement and comparison
     (holon.gen.symsec: a key the store does not hold is not translated, its documented limit), except that a view's
     return word whose return term K2 sorts Time is translated in the first run's observation, as J3 compares the
     outcome and the logs' Time words;
   - sentinel, one per K4 site: L_sym_sentinel_<Contract>_<path with _>_<action>_<line>;
   - sentinel invariant, one per K4 reader: L_sym_sentinel_inv_<Contract>_<path with _>_<view>.
   Exactly the instrument's law ids, under the next free rule catalog version that holds SYM's producers (J4's shape).
K6 Decision. I34's J6: PROVED by Bend-checked proof with BendTT's verdict, REFUTED by a Bend-accepted counter-law with a
   reachable witness replayed on the real code, else UNKNOWN naming its bound. A tau law's REFUTED record names, in its
   sym block, the site its witness crosses (site, site_kind); a sentinel invariant's names the view it reads (site) and
   the reach steps of its witness prefix (sym.prefix: [{"member", "action" or "upgrade", "block_timestamp"}]).
K7 Replays. Every REFUTED law's witness runs on the real code (forge, the pinned builds; the legacy queue's
   implementation at legacy.tag behind the proxy, upgraded to the head implementation at the prefix's upgrade step):
   replay/M3/symb/<law>.json {"law", "worlds": [{"name", "outcome"}], "agree": true when the two worlds differ as the
   counter-law states}.
K8 Model3. model3 compiles the queue's four debt actions (appendCrossDomainMessage, appendEnforcedTransaction,
   getCrossDomainMessage, computeTransactionHash) and the legacy queue's enqueue actions. Three constructs are missing at
   the prereg, all in EXT1 (I70's extension): the length of a storage dynamic array read as a storage path (EXT1's length
   takes only a carried view); Yul byte (["wbyte", x, n]: byte n of the word x, 0 the most significant, 0 past the word);
   and a top-level conditional memory write, which model3 inlines into both branches of a conditional (the enqueue
   actions' RLP encoding has 18, and the memory term passes 90 MB), compiled instead as a helper of the action's input and
   the memory, as a memory loop is. The bundle compiles its members with EXT1. Every model model3 compiled before I92
   stays byte-identical, except the queue's bundle model, which gains the four actions.
K9 Records. Every I92 law has results/M3/<law>.json (v2 record); GEVID enforces on them as on I34's.
K10 Earlier tests amended in this prereg: none. One that fails on I92's outcomes is a miss, reported.
K11 Rules. I92 adds SYM laws and no other; changes no I34 law (statement or record); names no law id, action, register
   or contract of the target in holon/; writes no frozen root. Its outcome paths are the predictions file's.
K12 Not this key's: pi and omega over the members, iota's laws (the Idx sort admits the family; no law), tau over the
   Rollup-queue link (absent keys are not translated, so the migrated zero is no tau break: O21 is the invariant's), the
   Rollup's index sentinel revertReqIndex (Q-S4), the members' other versions.

Commands
  python -m tests_m3._i92                    the instrument's basis (K2, K4, K5)
  python -m holon derive --milestone M3       K5
  python -m holon run --milestone M3 --laws ID
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path

from tests_m3 import _i92 as I

ROOT = Path(__file__).resolve().parents[1]
KEY = "I92"
SIDECAR = ROOT / "spec" / "M3" / "lib" / "sym_bundle.json"
BASIS = ROOT / "spec" / "M3" / "lib" / "sym_bundle_basis.json"
SYMB = ROOT / "gen" / "M3" / "symb"
RESULTS = ROOT / "results" / "M3"
REPLAY = ROOT / "replay" / "M3" / "symb"
MODELS = ROOT / "gen" / "M3" / "bundle" / "models" / "models.json"
O21_SITE = "L1MessageQueueWithGasPriceOracle.sol:262"


def o21_site(site) -> bool:
    """The getter's comparison of messageEnqueueTime[pendingQueueIndex] against 0: line 262, inside the getter whose
    facts src is 261-268 (a view's return term carries no finer src), named by line, by that range or by the getter."""
    s = str(site or "")
    return bool(re.search(r"L1MessageQueueWithGasPriceOracle\.sol:(262|261-268)\b", s)) or I.GETTER in s


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def record(law: str) -> dict:
    p = RESULTS / f"{law}.json"
    if not p.exists():
        raise AssertionError(f"{law}: no record at {p.relative_to(ROOT)}")
    return load(p)


def key() -> dict:
    return load(ROOT / "spec" / "M3" / "predictions" / f"{KEY}.json")


class TestBasis(unittest.TestCase):
    def test_k_the_basis_is_the_instruments(self):
        """The committed basis is the instrument's recomputation at HEAD (the member documents are inputs that do not
        move: R1)."""
        self.assertEqual(load(BASIS), I.basis(ROOT))

    def test_k_the_key_pins_the_basis_law_ids(self):
        self.assertEqual(key()["thresholds"]["law_ids"], load(BASIS)["law_ids"])

    def test_k_the_key_pins_its_inputs(self):
        """The key pins this contract's docstring, the instrument, the sidecar and the basis by sha256."""
        t = key()["thresholds"]
        self.assertEqual(hashlib.sha256(__doc__.encode("utf-8")).hexdigest(), t["contract_docstring_sha256"])
        for name in ("instrument", "sidecar", "basis"):
            self.assertEqual(sha256(ROOT / t[name]), t[f"{name}_sha256"], name)


class TestModels(unittest.TestCase):
    def test_p1_the_queue_enqueue_actions_compile(self):
        """I92-P1 (K8): the queue's bundle model has no debt (appendCrossDomainMessage, appendEnforcedTransaction,
        getCrossDomainMessage and computeTransactionHash compile), and the legacy queue's model compiles its enqueue
        actions."""
        m = load(MODELS)
        self.assertEqual([d for d in m["debt"] if d["member"] == "queue"], [])
        legacy = load(SYMB / "legacy" / "models.json")
        ldebt = {d["action"] for d in legacy.get("debt") or []}
        for act in ("appendCrossDomainMessage", "appendEnforcedTransaction"):
            self.assertNotIn(act, ldebt)
        self.assertTrue((ROOT / legacy["models"]["queue"]["path"]).exists())

    def test_p2_eta_enq_is_the_layout_map(self):
        """I92-P2 (K1, K3): the legacy document is the queue at sidecar legacy.tag; eta_enq maps every legacy register to
        the head register of the same name and slot, and lists exactly messageEnqueueTime as fresh."""
        sc = load(SIDECAR)
        eta = load(SYMB / "eta_enq.json")
        legacy = load(SYMB / "legacy" / "queue.json")
        head = I.doc("queue", ROOT)
        self.assertEqual(eta["from"]["tag"], sc["legacy"]["tag"])
        self.assertEqual(eta["from"]["commit"], sc["legacy"]["commit"])
        self.assertEqual(eta["from"]["document_sha256"], sha256(SYMB / "legacy" / "queue.json"))
        self.assertEqual(eta["to"]["document_sha256"], sha256(ROOT / I.MEMBERS["queue"][0]))
        lslots = {s["name"]: int(s["slot"]) for s in legacy["storage"]}
        hslots = {s["name"]: int(s["slot"]) for s in head["storage"]}
        want = sorted([{"register": n, "from_slot": s, "to_slot": hslots[n]} for n, s in lslots.items() if n in hslots],
                      key=lambda x: x["register"])
        self.assertEqual(sorted(eta["map"], key=lambda x: x["register"]), want)
        for x in want:
            self.assertEqual(x["from_slot"], x["to_slot"], x)
        self.assertEqual(sorted(eta["fresh"]), sorted(set(hslots) - set(lslots)))
        self.assertEqual(eta["fresh"], ["messageEnqueueTime"])


class TestSorts(unittest.TestCase):
    def test_p3_the_member_sorts_are_the_instruments(self):
        """I92-P3 (K2): holon's member sorts equal the instrument's fixed point."""
        s = load(SYMB / "sorts.json")["members"]
        b = load(BASIS)
        for m in I.MEMBERS:
            self.assertEqual(sorted(s[m]["time"]), b["time_registers"][m], m)
            self.assertEqual(sorted(s[m]["idx"]), b["idx_registers"][m], m)
            self.assertEqual(sorted(s[m]["idx_keys"]), b["idx_keys"][m], m)


class TestLaws(unittest.TestCase):
    def ids(self, prefix: str) -> list:
        return [x for x in load(BASIS)["law_ids"] if x.startswith(prefix)]

    def test_k5_derive_writes_exactly_the_basis(self):
        derived = sorted(p.name for p in (ROOT / "gen" / "M3" / "laws").iterdir()
                         if any(p.name.startswith(x) for x in load(SIDECAR)["law_prefixes"]))
        self.assertEqual(derived, load(BASIS)["law_ids"])

    def test_p4_the_sentinel_laws_are_proved(self):
        """I92-P4 (K4): every sentinel law is PROVED: the four Time sentinels (block_timestamp >= 1) and the lastIndex
        sentinel over the messenger-queue link (the replayed message's send appended to the queue)."""
        ids = self.ids("L_sym_sentinel_")
        self.assertEqual(len(ids), 5)
        for law in ids:
            self.assertEqual(record(law)["status"], "PROVED", law)

    def test_p5_member_tau_laws(self):
        """I92-P5: the messenger's three tau laws are REFUTED at the comparison of messageSendTimestamp against 0
        (sendMessage's at :304, replayMessage's at :193; site_kind compare); the queue getter's tau law is REFUTED at its
        return's comparison of messageEnqueueTime against 0; getMessageEnqueueTimestamp's is REFUTED (an index the store
        does not hold: I34's absent-key limit against K5's translated return word); the enqueue actions' two are not."""
        for law in self.ids("L_sym_tau_L1CrossDomainMessenger_"):
            r = record(law)
            self.assertEqual(r["status"], "REFUTED", law)
            self.assertEqual(r["sym"]["site_kind"], "compare", law)
            self.assertTrue(re.search(r"L1CrossDomainMessenger\.sol:(193|304)\b", r["sym"]["site"]), (law, r["sym"]))
        for law in self.ids("L_sym_tau_L1MessageQueueWithGasPriceOracle_"):
            r = record(law)
            if law.endswith("_" + I.GETTER):
                self.assertEqual(r["status"], "REFUTED", law)
                self.assertEqual(r["sym"]["site_kind"], "compare", law)
                self.assertTrue(o21_site(r["sym"]["site"]), (law, r["sym"]))
            elif law.endswith("_getMessageEnqueueTimestamp"):
                self.assertEqual(r["status"], "REFUTED", law)
            else:
                self.assertNotEqual(r["status"], "REFUTED", law)

    def test_p6_o21_the_queue_invariant_is_refuted_after_the_upgrade(self):
        """I92-P6 (O21): the sentinel invariant is REFUTED; its witness prefix holds the queue's upgrade step (eta_enq)
        after a message was enqueued under the legacy version, every step with block_timestamp >= 1, and ends in a state
        where pendingQueueIndex < length and messageEnqueueTime[pendingQueueIndex] = 0; the real-code replay agrees."""
        ids = self.ids("L_sym_sentinel_inv_")
        self.assertEqual(len(ids), 1)
        for law in ids:
            r = record(law)
            self.assertEqual(r["status"], "REFUTED", law)
            self.assertTrue(o21_site(r["sym"]["site"]), (law, r["sym"].get("site")))
            prefix = r["sym"]["prefix"]
            ups = [i for i, st in enumerate(prefix) if st.get("action") == "upgrade" and st.get("member") == "queue"]
            self.assertEqual(len(ups), 1, law)
            self.assertTrue(any(st.get("action") != "upgrade" for st in prefix[:ups[0]]), law)
            self.assertTrue(all(int(st["block_timestamp"]) >= 1 for st in prefix if "block_timestamp" in st), law)
            rp = load(REPLAY / f"{law}.json")
            self.assertEqual(rp["law"], law)
            self.assertTrue(rp["agree"], law)

    def test_p6_head_only_contrast(self):
        """I92-P6 (contrast): with the queue at the head only (no legacy version) and the same budgets, the invariant has
        no witness (results/M3/symb/head_only.json {law: {"status", "bound"}}, status not REFUTED)."""
        h = load(ROOT / "results" / "M3" / "symb" / "head_only.json")
        for law in self.ids("L_sym_sentinel_inv_"):
            self.assertNotEqual(h[law]["status"], "REFUTED", law)


class TestRegressions(unittest.TestCase):
    def test_r1_earlier_outputs_do_not_move(self):
        """I92-R1: the inputs of thresholds.inputs_sha256 keep their sha256; I34's SYM law statements are unchanged
        (sidecar i34_laws_sha256: each gen/M3/laws/L_sym_*/LAWS.bend); every bundle model but the queue's keeps its
        sha256."""
        th = key()["thresholds"]
        for rel, h in th["inputs_sha256"].items():
            self.assertEqual(sha256(ROOT / rel), h, rel)
        for rel, h in load(SIDECAR)["i34_laws_sha256"].items():
            self.assertEqual(sha256(ROOT / rel), h, rel)
        m = load(MODELS)["models"]
        for member, h in load(SIDECAR)["bundle_models_sha256"].items():
            if member != "queue":
                self.assertEqual(m[member]["sha256"], h, member)

    def test_r2_own_commits_touch_nothing_forbidden(self):
        """I92-R2: I92's own commits (the non-merge commits of git log --first-parent <C_K>..<end>, end the oldest commit
        adding docs/iterations/I92.md, HEAD while there is none) write no frozen root and no other key's prediction,
        prompt or contract file."""
        def git(*a):
            return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, check=True).stdout
        ck = git("log", "--diff-filter=A", "--format=%H", "--", f"spec/M3/predictions/{KEY}.json").split()[-1]
        added = git("log", "--first-parent", "--diff-filter=A", "--format=%H", f"{ck}..HEAD", "--",
                    f"docs/iterations/{KEY}.md").split()
        end = added[-1] if added else "HEAD"
        frozen = ("facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/", "docs/M0_SPEC.md",
                  "docs/BEND_PRIMER.md", "AGENTS.md", "tools/freeze.py")
        others = re.compile(r"^(spec/M\d/predictions/(?!I92\.json)|prompts/(?!I92_)|tests_m3/test_(?!sym_bundle\.py))")
        for c in git("log", "--first-parent", "--no-merges", "--format=%H", f"{ck}..{end}").split():
            for f in git("diff-tree", "--no-commit-id", "--name-only", "-r", c).split("\n"):
                if f:
                    self.assertFalse(f.startswith(frozen), f"{c[:8]}: {f}")
                    self.assertFalse(others.match(f), f"{c[:8]}: {f}")

    def test_r3_prereg_audits_pass(self):
        """I92-R3: holon audit prereg passes for M3 and M2 at HEAD."""
        for m in ("M3", "M2"):
            p = subprocess.run(["python", "-m", "holon", "audit", "prereg", "--milestone", m], cwd=str(ROOT),
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])

    def test_r4_own_code_names_no_target(self):
        """I92-R4 (K11): no holon/ file names a target identifier of the members (their contracts, registers or the
        sentinel registers' names)."""
        names = ("L1MessageQueueWithGasPriceOracle", "L1CrossDomainMessenger", "messageEnqueueTime",
                 "messageSendTimestamp", "replayStates", "getFirstUnfinalizedMessageEnqueueTime")
        for p in (ROOT / "holon").rglob("*.py"):
            text = p.read_text(encoding="utf-8")
            for n in names:
                self.assertNotIn(n, text, f"{p.relative_to(ROOT)} names {n}")


if __name__ == "__main__":
    unittest.main()
