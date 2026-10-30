"""I80 (= I37a): Bundle II's extraction and acquisition, with no law (whitepaper §10.1 Solidity and linking, §8.5
HypC, §8.7 refinement, App. D cost, §11.1 scope; BUILD_PLAN I37 and row I80; docs/HUMAN_ANSWERS.md Q12, Q18, Q19).
This docstring is the contract; its sha256 is the key's thresholds.contract_docstring_sha256.

Scope. BUILD_PLAN I37 (Bundle II: router, public input, HypC, calibrated cost) predicts O3, O23, the calibrated cost and
O35; its laws depend on I36 (Bundle I) and I32. Extracting Bundle II's contracts depends on neither, so it goes first,
under its own key, as I69 (= I36a) does for Bundle I. I80 extracts the verifier router (MultipleVersionRollupVerifier)
at the pinned head 3e44e795, models it, links it with the adopted Rollup into one machine and refines both against the
real code; extracts the zkEVM verifier (ZkEvmVerifierV1 with its SP1Verifier and PlonkVerifier bases) only, naming its
debt (it is the circuit oracle, which I37 states as HypC); reads the public-input view and the cost sites from the
documents; and writes acquisition notes from committed records and git objects, with no network read. It states no
law, changes no rule catalog, adopts no document into M3's derivation (spec/M3/lib/derive_extracted.json stays I24's),
adds no coverage entry (gen/M2/coverage.json and gen/M3/coverage.json do not change) and changes no file of any
generator closure, so no record is re-made. I37 keeps its number for the laws.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and a line in spec/M3/amendments.jsonl):
tests_m3/_i80.py (the rules below written a second time, independently of holon/, over I63's instrument
tests_m3/_i63.py and tests_m2/_keccak.py); spec/M3/lib/bundle2.json (the sidecar: members, wiring, deployment, corpus,
observables, acquisition inputs; no outcome); spec/M3/lib/bundle2_basis.json (tests_m3/_i80.py::basis at the prereg:
rules A1-A2). The key's thresholds pin all three and this docstring by sha256.

Inputs, read and never written: the adopted Rollup document spec/M2/facts/morph_rollup.extracted.json and its sidecar
spec/M2/lib/extract_rollup.json (a member as it is); I20's binding replay/M2/fragments.json, deployment parameters
(spec/M1/facts/morph_rollup.json) and harness files replay/M1/solidity/HolonTraceReplay.t.sol,
replay/M2/solidity/HolonStepBase.sol and replay/M2/solidity/HolonExtractedStep.t.sol (copied into the scratch project,
never edited); I63's committed receipt of the Rollup proxy's initialization (the sidecar's acquisition.anchor); the
target repository's git objects (config/holon.json extract.sources), with lazy fetching disabled.

Extraction (E1-E6)
  E1 Members. The sidecar's members are rollup (the adopted document, unchanged) and router; its extracted_only member
     is zkevm. For router and zkevm, `holon bundle2 extract` writes a generated extraction sidecar
     gen/M3/bundle2/sidecars/<member>.json (the base sidecar spec/M2/lib/extract_rollup.json with target.commit the
     member's commit, target.scope "bundle2 member <name> (<contract>)", sources [the member's source], transitions
     {contract, commit_interfaces} the member's, output gen/M3/bundle2/documents/<member>.json and a doc of its own),
     then that document, extracted by I19's frontend (holon.frontends.solidity: its walk and its coverage rules,
     unchanged). The action set is I19's: every external or public function with a body of the contract and its bases,
     most derived first, one per selector. Each member's extraction runs in a child process bounded by the sidecar's
     extract.timeout_s (wall clock); an extraction error or a timeout is debt {"member", "reason"} with no document,
     never smoothed.
  E2 The declaration gen/M3/bundle2/bundle2.json: {"bundle2_version": "holon-bundle2/0.1", "sidecar": {"path", "sha256"},
     "members": [{"name", "contract", "commit", "sidecar": {"path", "sha256"} or null for the adopted Rollup, "document":
     {"path", "sha256"}}], "extracted_only": [same shape], "debt": [{"member", "reason"}], "coverage": [one entry per
     generated document, sorted by document, in holon.coverage's entry format {"document", "statements", "extracted",
     "debt", "unaccounted"}: the frontend's coverage_document on the generated sidecar], "links": rule L2's rows,
     "public_input": rule E4's rows, "cost_sites": rule E5's rows}.
  E3 No earlier output moves: the adopted Rollup document re-extracts byte for byte, `holon coverage --milestone M2
     --check` and `--milestone M3 --check` pass, and the typed and untyped M3 model texts (.bend) of the adopted
     document regenerate byte for byte (not its init.json: since F40, `holon run` writes it with the deployment's code
     table, which `holon model` does not write).
  E4 The public-input view: for every link row (L2) of kind action whose call record is a COMMIT edge, the views of the
     call's argument terms (tests_m3/_i80.py::_view: a 32-byte word of an input at an offset, its leading n bytes by a
     right shift of 256 - 8n, a parameter, an immutable, a keccak256 of abi.encodePacked components, else the term):
     the inputs of I37's PI = K(...).
  E5 The cost sites: one row per loop record of every action of every member document: [member, action, loop span,
     the record's seq, whether a cost term of the action names the span, the record's count term] (the inputs of I37's
     tools/calibrate_gas.py: a loop whose body writes storage is loop_storage_write debt, not a cost term).
  E6 holon/ names no target: every contract, function, address, slot or host comes from the sidecars, the documents or
     the compiler's output; holon/ does not import tests_m3.

Models (M1-M4)
  M1 `holon bundle2 model` writes gen/M3/bundle2/models/<member>.bend and <member>.init.json for every member but the
     adopted Rollup (whose models are I30's), each the member's document compiled by holon.sorts.model3's untyped
     machine (no sort section, no site section), extended additively by holon/bundle2 for storage dynamic arrays (index
     reads and writes, length, push and pop at the compiler's slots: the length at the array's slot, element i at
     keccak256(slot) + i * the slots per element, with sub-word packing); the extension lives under holon/bundle2/,
     outside every generator closure, and changes no text model3 emits for a document without such arrays. Its initial
     state is the member's storage after the deployment (C1's record). gen/M3/bundle2/models/models.json:
     {"models_version": "holon-bundle2-models/0.1", "models": {member: {"path", "sha256", "document_sha256"}}, "debt":
     [{"member", "action", "error"}]}: an action the generator cannot compile is debt with its GenError, never left out.
  M2 Every model passes the pinned Bend's check (`bend <model>.bend`: ALL PROOFS CHECK; it states no law, so this shows
     only that every definition type-checks and terminates), and holds no escape hatch (I30's N6).
  M3 Member refinement. For each modelled member, every compared corpus step whose top-level callee is that member runs
     on its model compiled to JavaScript (holon.sorts.evaluate3), from the member's real pre-state, with the answers
     the real code received to the member's own external calls (the harness's record): status, revert key, the member's
     storage writes and its logs are compared (I20's observables; evaluate3 gives no return data). Record
     results/M3/bundle2/refinement_models.json {"refinement_models_version": "holon-bundle2-refinement-models/0.1",
     "corpus": {"path", "sha256"}, "members": {member: {"model", "model_sha256", "steps", "disagreements": [{"id",
     "class", "links"}], "unexplained", "unsupported"}}}.
  M4 Nothing under gen/M3/ but gen/M3/bundle2/ changes.

The linked machine (L1-L8; holon/bundle2/, generic, over holon.extracted_eval's programs of the members' documents)
  L1 State: every member's raw storage (slot -> word).
  L2 Static links. For every member document, every call record of every action whose receiver term is ["storage", f]
     or ["immutable", f] with "<member>.<f>" in the sidecar's wiring: a row [member, action, src, fn, callee, kind,
     target], where kind is "action" (the callee's document has an action named as the called function: target that
     name), "getter" (it has none, but a storage family of that name: target that family) or "receive" (a low-level
     address.<kind> call). Sorted. These are the deployment's linked call sites.
  L3 Dispatch. A call to a member runs the member's action whose selector is the calldata's first four bytes; empty
     calldata runs its receive action; a selector of no action but of a public storage family's getter returns that
     getter's ABI encoding of the value at the compiler's slots (the mapping keys and array indices are the decoded
     arguments; a struct gives its members that are neither mappings nor arrays); any other selector reverts with empty
     data, as the compiler's dispatcher does (no member here has a fallback).
  L4 Linked calls. An external call term of a running frame whose receiver evaluates, when the call is made, to a
     member's address runs that member as a nested frame (L3) with the calling member as caller and the term's value,
     on the bundle state as the step's earlier frames left it (a finished frame's writes, and the writes so far of the
     frames on the stack); its result answers the term: callok holds when the frame succeeded and its return data
     decodes by the called function's output types, and the call's value is that decoding. A high-level call whose
     frame reverts makes the caller revert with the frame's revert data (with empty data when only the decoding
     failed); a low-level call's failure is a value; a failed frame's writes and logs are discarded, as are every
     frame's when the step reverts.
  L5 Re-entry. A nested frame on a member already on the frame stack runs only when its action writes no storage (its
     document's effects are empty: a view, a pure function, a getter or an empty receive); otherwise the step is
     unsupported ("reentry: <member>.<action>"), never guessed.
  L6 Depth. A step that would nest more frames than the sidecar's link.depth is unsupported ("depth").
  L7 Non-members. A high-level call whose receiver is no member and no account the deployment created (C1's record:
     an EOA, address(0)) reverts with empty data (the compiler's code-size check for a function without outputs; the
     undecodable empty return data otherwise). A call to another non-member is answered from the harness's record of
     that call by that caller (to, data, ok, return data), as I20's env.calls; a call with no recorded answer is
     unsupported.
  L8 A step's result: status; revert data; return data (the top frame's ABI encoding of its action's returns, by the
     action's output types); every member's writes (slot -> word); the members' logs (emitter, topics, data) in order;
     the frames [callee member, selector, persisted] in call order, persisted meaning the frame and every frame
     enclosing it succeeded and the step did not revert (forge's state-diff "reverted" flag, negated).

Harness and corpus (C1-C6; replay/M3/bundle2/, gen/M3/bundle2/corpus.json)
  C1 Deployment. Each trace starts from a fresh deployment, made as the sidecar's deployment section says: I20's
     deployment with the real router as the Rollup's verifier (versions 0, 1 and 2 mapped to the stand-in Z1,
     initialized with the Rollup proxy) and the stand-ins Z1 and Z2. Its record replay/M3/bundle2/deployment.json gives
     every member's address, the stand-ins' and every other account the deployment created, and every member's
     non-zero slots after the deployment.
  C2 Harness. A generic multi-member step base (I20's HolonStepBase generalized to a member set:
     replay/M3/bundle2/HolonBundle2Base.sol) records per step every storage write of every member, every member's
     logs, every frame on a member (forge's state diff: depth, callee, selector, value, reverted), every call a member
     made to an account other than itself with its answer (re-run in order from the state before the step, as that
     member), vm.load of every slot of every member's layout after the step, and the poked slots; the concrete harness
     (replay/M3/bundle2/HolonBundle2Step.t.sol) deploys C1 and translates the sidecar's abstract rows: ops 1-11 as I20's
     harness does (its code copied), ops 12-21 as the sidecar's corpus.rows says. I20's files are copied, never edited.
  C3 Corpus. `holon bundle2 corpus` writes gen/M3/bundle2/corpus.json, deterministically, from three sources: m1: I20's
     base corpus (holon.fragments_corpus.m1_traces, seed 20261011, 300 traces) as I20's abstract rows; seed: the
     sidecar's five planted traces; random: the sidecar's 60 traces (tests_m3/_i80.py::random_corpus). Rows are
     13-word lists; the file is {"corpus_version": "holon-bundle2-corpus/0.1", "sidecar": {"path", "sha256"}, "init":
     [F, W, D, t0, r0], "traces": [{"source", "label", "rows"}]}.
  C4 States. Every member's storage is tracked exactly: the deployment's writes, then every step's writes that were
     not reverted, and the poked slots before their step. After every step the tracked state must equal the harness's
     vm.load of every layout slot of every member, else the run is an error (exit 3).
  C5 Comparison. Every call step (every row but ops 9-11, environment steps run and tracked as in I20) is compared: the
     linked machine runs the step's call from the real pre-state of every member, with the step's environment: status;
     revert key on two reverts (holon.replay_fragments.revert_key); return data on two oks; every member's storage at
     every slot a write of the step touches on either side; the members' logs in order; the frames. A difference, or a
     step the machine leaves unsupported, is a disagreement, filed in results/M3/bundle2/disagreements.json as I20 files
     them (an id that is a function of the step, "unexplained" with no links; a class only from links).
  C6 Records. results/M3/bundle2/refinement.json: {"refinement_version": "holon-bundle2-refinement/0.1", "corpus":
     {"path", "sha256", "sources": {"m1", "seed", "random"} (trace counts)}, "traces", "steps", "observables" (the
     sidecar's), "disagreements": [{"id", "class", "links"}], "unexplained", "unsupported", "frames_ok": {member:
     {action: n}}, "links_ok": [[member, action, src, fn, n]], "by_member_action": {member: {action: {"ok",
     "revert"}}}, "toolchain"}; results/M3/bundle2/steps.json: {"steps": [{"trace", "id", "source", "compared",
     "status", "frames": [[parent, callee, selector, persisted]]}]} (the harness's frames, parent -1 for the top
     frame), from which tests_m3/_i80.py::recount recomputes the counts. `holon bundle2 refine` writes them, M3's
     record and the disagreements; with `holon bundle2 deploy` it is the only command that runs forge.

Acquisition notes (A1-A3; Q12, Q18: what the deployed bundle is, from committed records; nothing is read from the
network)
  A1 Anchor: the Rollup proxy's UpdateVerifier logs in I63's committed receipt of its initialization (the sidecar's
     acquisition.anchor): the verifier the Rollup was initialized with.
  A2 Builds: the blobs of every member's units at the sidecar's 25 pinned tags (I63's) and the head, from tree listings;
     the router's and zkevm's head builds under I63's three configurations (I63's code identity and length).
     spec/M3/lib/bundle2_basis.json is their computation at the prereg.
  A3 `holon bundle2 acquire` writes gen/M3/bundle2/acquisition.json: {"acquisition_version":
     "holon-bundle2-acquisition/0.1", "anchor", "tags", "builds" (A1, A2: equal to the basis's), "to_read" (the
     sidecar's list)}.

Shared files, changed only so (not outcome paths): the code under holon/ outside every generator closure (new modules
under holon/bundle2/ and holon/__main__.py's dispatch); no file of the closures pinned in thresholds.closures (the
holon-ir 0.1-0.3 closures of holon.records.generator_files, holon.sorts.run3.GEN3 and its unions with GEN_FACT,
GEN_UNDO and GEN_DISCH, and holon.profile.generator_files, at the prereg), so no record under results/ but
results/M3/bundle2/ changes.

Own commits: the non-merge commits of `git log --first-parent <prereg>..<end>`, end the first commit adding
docs/iterations/I80.md (HEAD while none does). Commit rules (I80-R2): at least one adds gen/M3/bundle2/bundle2.json;
none changes a frozen root, laws/, spec/, holon/rules/, holon/frontends/, a file of thresholds.closures, a file under
replay/ outside replay/M3/bundle2/, a file under gen/ outside gen/M3/bundle2/, or a file under results/ outside
results/M3/bundle2/.

Earlier tests amended at this prereg: none. I80 adopts no document, adds no rule, law, catalog or coverage entry, moves
no generator closure and writes under new paths only. One that fails on I80's outcomes is a miss, reported.

Commands
  python -m holon bundle2 extract|deploy|model|corpus|refine|acquire [--check]
  Exit codes: 0 written (or --check reproduced); 1 --check differs; 2 refused (a missing or stale input, a missing git
  object), nothing written; 3 an extraction, model or harness error, nothing written. Outputs are canonical JSON
  (sorted keys, indent 1, a final newline), byte-identical across runs, with no timestamps and no absolute paths.
  `refine --check` re-runs nothing: it checks that the records name the committed corpus and that steps.json recounts
  to refinement.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m3._m3 import ROOT, file_sha256, holon_module, item, load_json, predictions, run_holon

KEY = "I80"
SIDE = ROOT / "spec" / "M3" / "lib" / "bundle2.json"
BASIS = ROOT / "spec" / "M3" / "lib" / "bundle2_basis.json"
DECL = ROOT / "gen" / "M3" / "bundle2" / "bundle2.json"
DOCS = ROOT / "gen" / "M3" / "bundle2" / "documents"
MODELS = ROOT / "gen" / "M3" / "bundle2" / "models"
CORPUS = ROOT / "gen" / "M3" / "bundle2" / "corpus.json"
ACQ = ROOT / "gen" / "M3" / "bundle2" / "acquisition.json"
DEPLOY = ROOT / "replay" / "M3" / "bundle2" / "deployment.json"
REF = ROOT / "results" / "M3" / "bundle2" / "refinement.json"
REFM = ROOT / "results" / "M3" / "bundle2" / "refinement_models.json"
STEPS = ROOT / "results" / "M3" / "bundle2" / "steps.json"
DIS = ROOT / "results" / "M3" / "bundle2" / "disagreements.json"
ROLLUP_DOC = "spec/M2/facts/morph_rollup.extracted.json"
MODELLED = ("router",)
_CACHE: dict = {}


def th() -> dict:
    return predictions(KEY)["thresholds"]


def need(p: Path) -> dict:
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing")
    return load_json(p)


def instrument():
    import tests_m3._i80 as I
    return I


def doc(member: str) -> dict:
    return need(DOCS / f"{member}.json")


def ifaces() -> dict:
    if "ifaces" not in _CACHE:
        _CACHE["ifaces"] = instrument().interfaces(ROOT)
    return _CACHE["ifaces"]


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def prereg_commit() -> str:
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I80 (the audit's C_K)."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            d = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(d, dict) and KEY in (d.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I80")


def own_commits() -> list:
    """I80's own commits: the non-merge commits of `git log --first-parent <prereg>..<end>`, end the first commit adding
    docs/iterations/I80.md (HEAD while none does), oldest first, each with its (status, path) pairs."""
    added = git("log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--", "docs/iterations/I80.md").split()
    end = added[0] if added else "HEAD"
    commits, cur = [], None
    for ln in git("log", "--first-parent", "--no-merges", "--no-renames", "--reverse", "--format=@%H", "--name-status",
                  f"{prereg_commit()}..{end}").splitlines():
        if ln.startswith("@"):
            cur = (ln[1:], [])
            commits.append(cur)
        elif ln.strip() and cur is not None:
            st, path = ln.split("\t", 1)
            cur[1].append((st[0], path.strip()))
    return commits


def holon_ok(args: list, timeout: int = 7200):
    p = run_holon(args, timeout=timeout)
    return p.returncode, (p.stdout[-1500:] + p.stderr[-1500:])


def closures(root: Path = ROOT) -> list:
    """Every file of the generator closures at root (holon modules imported here, inside the call)."""
    rec = holon_module("holon.records")
    run3 = holon_module("holon.sorts.run3")
    out = set()
    for v in ("holon-ir/0.1", "holon-ir/0.2", "holon-ir/0.3"):
        out |= set(rec.generator_files(v, root))
    starts = [list(run3.GEN3)]
    for mod, name in (("holon.fact.run", "GEN_FACT"), ("holon.undo.run", "GEN_UNDO"), ("holon.disch.run", "GEN_DISCH")):
        starts.append(list(getattr(holon_module(mod), name)) + list(run3.GEN3))
    for start in starts:
        seen, todo = set(), list(start)
        while todo:
            r = todo.pop()
            if r in seen or not (root / r).is_file():
                continue
            seen.add(r)
            if r.endswith(".py"):
                todo.extend(sorted(rec._holon_imports(r, root) - seen))
        out |= seen
    out |= set(holon_module("holon.profile").generator_files(root))
    return sorted(out)


# ---------------------------------------------------------------------------------------------- instruments
class TestInstrument(unittest.TestCase):
    """The frozen inputs are what they say they are (construction; green at the prereg)."""

    def test_the_key_pins_the_instruments(self):
        t = th()
        self.assertEqual(file_sha256(SIDE), t["sidecar_sha256"])
        self.assertEqual(file_sha256(BASIS), t["basis_sha256"])
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i80.py"), t["instrument_sha256"])
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i63.py"), t["i63_instrument_sha256"])
        d = sys.modules[__name__].__doc__
        self.assertEqual(hashlib.sha256(d.encode("utf-8")).hexdigest(), t["contract_docstring_sha256"])
        self.assertEqual(need(BASIS)["sidecar_sha256"], file_sha256(SIDE))

    def test_the_basis_recomputes(self):
        """A1-A2 recomputed by the instrument from the committed receipt and the repository's objects equal the frozen
        basis."""
        self.assertEqual(instrument().basis(ROOT), need(BASIS))

    def test_the_sidecar_names_committed_facts(self):
        """The acquisition's tags and configurations are I63's; the anchor receipt is one of I63's committed receipts
        and names one verifier; the wiring names families of the documents' storage as solc lays them out; the
        router's rollup slot is solc's; the deployment's init keys are I20's binding's; every seed and prefix row is
        13 words and uses only the documented ops; the router's and zkevm's sources are at the head."""
        I = instrument()
        side, hist = load_json(SIDE), load_json(ROOT / "spec" / "M3" / "lib" / "history.json")
        acq = side["acquisition"]
        self.assertEqual((acq["tags"], acq["compiler_configs"]), (hist["tags"], hist["compiler_configs"]))
        a = I.anchor(ROOT)
        self.assertTrue(acq["anchor"]["receipt"].startswith("results/M3/history/receipts/"))
        self.assertEqual(len(a["logs"]), 1)
        self.assertEqual(a["logs"][0]["emitter"], hist["proxy"]["address"])
        f = ifaces()
        rollup_fams = {s["name"] for s in load_json(ROOT / ROLLUP_DOC)["storage"]}
        self.assertIn("verifier", rollup_fams)
        self.assertIn("rollup", f["router"]["own"])
        self.assertEqual(I.slot_of(f, "router", "rollup"), side["corpus"]["router_rollup_slot"])
        b = load_json(ROOT / side["deployment"]["init"]["binding"])
        self.assertEqual(side["deployment"]["init"]["keys"], b["init"]["keys"])
        ops = set(range(1, 22))
        for label, rows in sorted(side["corpus"]["seed"].items()):
            for r in rows:
                self.assertEqual(len(r), 13, label)
                self.assertIn(r[0], ops, label)
        for r in side["corpus"]["random"]["prefix"]:
            self.assertEqual(len(r), 13)
        self.assertEqual(sorted(side["corpus"]["seed"]), ["S1_router", "S2_prove_committed", "S3_prove_state",
                                                          "S4_owner", "S5_rollup_word"])
        self.assertEqual(sorted(int(k) for k in side["corpus"]["random"]["ops"]), list(range(12, 21)))

    def test_the_rollup_rows_and_views_read_the_adopted_document(self):
        """Disclosed construction facts over the committed Rollup document: its rows of rule L2 into the router are the
        three COMMIT calls (commitBatchWithProof, proveCommittedBatchState, proveState at Rollup.sol:779-784), and their
        public-input views (E4) are one and the same: header byte 0, header bytes 1..8, the proof, and keccak256 of the
        chain-id immutable and the header's 32-byte words at 89, 121, 153, 185, 25 and 57."""
        I = instrument()
        docs = {"rollup": load_json(ROOT / ROLLUP_DOC)}
        rows = [r for r in I.link_table(docs, load_json(SIDE)["wiring"])]
        self.assertEqual([r[:2] + r[3:] for r in rows],
                         [["rollup", a, "IRollupVerifier.verifyAggregateProof", "router", "unresolved",
                           "verifyAggregateProof"] for a in ("commitBatchWithProof", "proveCommittedBatchState",
                                                             "proveState")])
        h = "_batchHeader"
        want = [{"input": h, "from": 0, "length": 1}, {"input": h, "from": 1, "length": 8}, {"param": "_batchProof"},
                {"hash": "keccak256", "packed": [{"immutable": "LAYER_2_CHAIN_ID"}] +
                 [{"input": h, "from": k, "length": 32} for k in (89, 121, 153, 185, 25, 57)]}]
        doc_r = docs["rollup"]
        for r in rows:
            act = next(x for x in doc_r["actions"] if x["name"] == r[1])
            c = next(x for x in act["calls"] if x["src"] == r[2] and x["fn"] == r[3])
            self.assertTrue(c.get("commit"))
            self.assertEqual([I._view(x) for x in c["args"]], want, r[1])


# ---------------------------------------------------------------------------------------------- extraction
class TestExtraction(unittest.TestCase):
    def test_p1_the_router_is_extracted_as_read(self):
        """I80-P1: the router's document exists, with no member debt; its coverage has no unaccounted statement and
        exactly the predicted debt entries; its action names, own families in declaration order, inherited entries,
        constants, loop records per action, cost spans per action and COMMIT edges per action are as read."""
        item(KEY, "I80-P1")
        t = th()
        decl = need(DECL)
        self.assertNotIn("router", [d["member"] for d in decl["debt"]])
        cov = {d["document"]: d for d in decl["coverage"]}["gen/M3/bundle2/documents/router.json"]
        self.assertEqual(cov["unaccounted"], [])
        self.assertEqual([[d["src"], d["kind"], d["detail"]] for d in cov["debt"]], t["debt"]["router"])
        d, want = doc("router"), t["structure"]["router"]
        self.assertEqual(sorted(a["name"] for a in d["actions"]), want["actions"])
        self.assertEqual([s["name"] for s in d["storage"]], want["storage"])
        self.assertEqual(len(d["inherited_storage"]), want["inherited"])
        self.assertEqual(d["constants"], want["constants"])
        self.assertEqual({a["name"]: len(a.get("loops") or []) for a in d["actions"] if a.get("loops")}, want["loops"])
        self.assertEqual({a["name"]: sorted({x["loop"] for x in a["cost"]["terms"]})
                          for a in d["actions"] if a["cost"]["terms"]}, want["cost"])
        self.assertEqual({a["name"]: sorted({e["fn"] for e in a.get("edges") or [] if e["kind"] == "COMMIT"})
                          for a in d["actions"] if any(e["kind"] == "COMMIT" for e in a.get("edges") or [])},
                         want["commit_edges"])

    def test_p2_the_zkevm_verifier_is_extracted_with_named_debt(self):
        """I80-P2: the zkEVM verifier's extraction ends within the sidecar's budget with a document (no member debt);
        its action names are as read; its coverage has no unaccounted statement; its debt holds the three external self
        calls (this.verifyPlonk, this.verifyProof, this.Verify) as external_call entries at their spans, and at least
        one unsupported entry in PlonkVerifier.sol (the circuit's precompile calls)."""
        item(KEY, "I80-P2")
        t = th()
        decl = need(DECL)
        self.assertNotIn("zkevm", [d["member"] for d in decl["debt"]])
        d = doc("zkevm")
        self.assertEqual(sorted(a["name"] for a in d["actions"]), t["structure"]["zkevm"]["actions"])
        cov = {x["document"]: x for x in decl["coverage"]}["gen/M3/bundle2/documents/zkevm.json"]
        self.assertEqual(cov["unaccounted"], [])
        ext = sorted([x["src"], x["kind"]] for x in cov["debt"] if x["kind"] == "external_call")
        self.assertEqual(ext, t["debt"]["zkevm_external_calls"])
        plonk = [x for x in cov["debt"] if x["kind"] == "unsupported"
                 and x["src"].startswith("contracts/contracts/libraries/verifier/PlonkVerifier.sol:")]
        self.assertGreater(len(plonk), 0)

    def test_extract_reproduces(self):
        """Construction (E1, E2): holon bundle2 extract --check reproduces the generated sidecars, documents and
        declaration."""
        code, out = holon_ok(["bundle2", "extract", "--check"])
        self.assertEqual(code, 0, out)

    def test_the_generated_sidecars_and_the_action_sets(self):
        """Construction (E1): every generated sidecar is the base sidecar with the member's commit, scope, source,
        contract, commit interfaces and output; every document's action names are the instrument's over solc's AST."""
        I = instrument()
        side = load_json(SIDE)
        base = load_json(ROOT / side["base_sidecar"])
        decl = need(DECL)
        members = {m["name"]: m for m in side["members"] + side["extracted_only"]}
        for e in decl["members"] + decl["extracted_only"]:
            m = members[e["name"]]
            if m.get("adopted"):
                self.assertIsNone(e["sidecar"])
                self.assertEqual(e["document"], {"path": m["document"], "sha256": file_sha256(ROOT / m["document"])})
                continue
            with self.subTest(member=e["name"]):
                sc = need(ROOT / e["sidecar"]["path"])
                self.assertEqual(e["sidecar"]["sha256"], file_sha256(ROOT / e["sidecar"]["path"]))
                want = dict(base, output=f"gen/M3/bundle2/documents/{e['name']}.json", sources=[m["source"]],
                            transitions={"contract": m["contract"], "commit_interfaces": m["commit_interfaces"]})
                want["target"] = dict(base["target"], commit=m["commit"],
                                      scope=f"bundle2 member {e['name']} ({m['contract']})")
                self.assertEqual({k: v for k, v in sc.items() if k != "doc"},
                                 {k: v for k, v in want.items() if k != "doc"})
                d = doc(e["name"])
                self.assertEqual(d["extraction"]["sidecar"], e["sidecar"])
                self.assertEqual(sorted(a["name"] for a in d["actions"]),
                                 I.ast_actions(ROOT, m["source"], m["contract"], m["commit"]))

    def test_the_views_and_cost_sites_follow_e4_e5(self):
        """Construction (E4, E5): the declaration's public_input and cost_sites are the instrument's rules over the
        committed documents and the declaration's links."""
        I = instrument()
        decl = need(DECL)
        docs = {"rollup": load_json(ROOT / ROLLUP_DOC), "router": doc("router")}
        self.assertEqual(decl["public_input"], I.public_input(docs, decl["links"]))
        self.assertEqual(decl["cost_sites"], I.cost_sites(docs))


# ---------------------------------------------------------------------------------------------- models
class TestModel(unittest.TestCase):
    def test_p6_the_router_model_compiles_and_refines(self):
        """I80-P6: the router's model compiles with no model debt and passes the pinned Bend's check, and refines the
        router on every top-level corpus step on it: no disagreement and no unsupported step."""
        item(KEY, "I80-P6")
        ms = need(MODELS / "models.json")
        self.assertEqual(sorted(ms["models"]), sorted(MODELLED))
        self.assertEqual(ms["debt"], [])
        for m, e in ms["models"].items():
            self.assertEqual(e["sha256"], file_sha256(ROOT / e["path"]))
            self.assertEqual(e["document_sha256"], file_sha256(DOCS / f"{m}.json"))
            text = (ROOT / e["path"]).read_text(encoding="utf-8")
            for rx in (r"\?[A-Za-z_]", r"@unsafe", r"def\s+\w+\?\s*\(", r'import\s+"'):
                self.assertIsNone(re.search(rx, "\n".join(ln.split("#", 1)[0] for ln in text.splitlines())), rx)
            p = subprocess.run(["bend", e["path"]], cwd=str(ROOT), capture_output=True, text=True, timeout=3600,
                               env={**os.environ, "BEND_NO_TELEMETRY": "1"})
            self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])
            self.assertEqual(p.stdout.splitlines()[0].strip() if p.stdout.strip() else "", "ALL PROOFS CHECK")
        r = need(REFM)
        self.assertEqual(r["corpus"], {"path": "gen/M3/bundle2/corpus.json", "sha256": file_sha256(CORPUS)})
        self.assertEqual(sorted(r["members"]), sorted(MODELLED))
        for m, x in r["members"].items():
            with self.subTest(member=m):
                self.assertGreater(x["steps"], 0)
                self.assertEqual((x["disagreements"], x["unexplained"], x["unsupported"]), ([], 0, 0))
                self.assertEqual(x["model_sha256"], file_sha256(ROOT / x["model"]))

    def test_models_reproduce(self):
        """Construction (M1): holon bundle2 model --check reproduces the member models and models.json."""
        code, out = holon_ok(["bundle2", "model", "--check"])
        self.assertEqual(code, 0, out)


# ---------------------------------------------------------------------------------------------- the linked machine
class TestLink(unittest.TestCase):
    def test_p3_the_static_links_are_as_read(self):
        """I80-P3: the declaration's static links are the predicted four rows (three Rollup proof checks into the
        router's verifyAggregateProof, the router's finalization check into the Rollup's lastFinalizedBatchIndex
        getter), and they follow rule L2 over the committed documents."""
        item(KEY, "I80-P3")
        decl = need(DECL)
        self.assertEqual(decl["links"], th()["links"])
        docs = {"rollup": load_json(ROOT / ROLLUP_DOC), "router": doc("router")}
        self.assertEqual(decl["links"], instrument().link_table(docs, load_json(SIDE)["wiring"]))

    def test_p4_the_linked_machine_refines_the_bundle(self):
        """I80-P4: on the whole corpus (300 m1, 5 seed and 60 random traces) the linked machine agrees with the real
        Rollup and router in every observable: no disagreement and no unsupported step."""
        item(KEY, "I80-P4")
        t = th()
        r = need(REF)
        self.assertEqual(r["corpus"]["path"], "gen/M3/bundle2/corpus.json")
        self.assertEqual(r["corpus"]["sha256"], file_sha256(CORPUS))
        self.assertEqual(r["corpus"]["sources"], t["corpus_traces"])
        self.assertEqual(r["observables"], load_json(SIDE)["observables"])
        self.assertGreater(r["steps"], 0)
        self.assertEqual((r["disagreements"], r["unexplained"], r["unsupported"]), ([], 0, 0))
        self.assertEqual(need(DIS).get("disagreements"), [])

    def test_p5_the_corpus_reaches_every_link_and_router_action(self):
        """I80-P5, recounted by the instrument from the harness's frames: every static link row was executed with a
        persisted frame at least once, and every one of the router's eight actions ended in a persisted frame, top-level
        or nested, at least once."""
        item(KEY, "I80-P5")
        rc = instrument().recount(need(STEPS), ifaces(), th()["links"])
        for row in rc["links_ok"]:
            with self.subTest(link=row[:4]):
                self.assertGreater(row[4], 0)
        for a in th()["structure"]["router"]["actions"]:
            with self.subTest(action=a):
                self.assertGreater(rc["frames_ok"].get("router", {}).get(a, 0), 0)

    def test_the_record_recounts(self):
        """Construction (C6): refinement.json's counts are the instrument's recount of steps.json."""
        rc = instrument().recount(need(STEPS), ifaces(), need(DECL)["links"])
        r = need(REF)
        for k in ("traces", "steps", "frames_ok", "by_member_action", "links_ok"):
            with self.subTest(field=k):
                self.assertEqual(r[k], rc[k])

    def test_corpus_reproduces(self):
        """Construction (C3): holon bundle2 corpus --check reproduces gen/M3/bundle2/corpus.json (no forge run), whose
        seed part is the sidecar's and whose random part is the instrument's."""
        code, out = holon_ok(["bundle2", "corpus", "--check"], timeout=1800)
        self.assertEqual(code, 0, out)
        c = need(CORPUS)
        side = load_json(SIDE)
        self.assertEqual([t["rows"] for t in c["traces"] if t["source"] == "seed"],
                         [side["corpus"]["seed"][k] for k in sorted(side["corpus"]["seed"])])
        self.assertEqual([t["rows"] for t in c["traces"] if t["source"] == "random"],
                         instrument().random_corpus(side))
        self.assertEqual(len([t for t in c["traces"] if t["source"] == "m1"]), side["corpus"]["m1"]["traces"])


# ---------------------------------------------------------------------------------------------- acquisition
class TestAcquisition(unittest.TestCase):
    def test_the_notes_are_the_basis(self):
        """Construction (A1-A3): holon bundle2 acquire --check reproduces gen/M3/bundle2/acquisition.json, whose anchor,
        tags and builds are the basis's and whose to_read is the sidecar's."""
        code, out = holon_ok(["bundle2", "acquire", "--check"])
        self.assertEqual(code, 0, out)
        a, b = need(ACQ), need(BASIS)
        for k in ("anchor", "tags", "builds"):
            with self.subTest(field=k):
                self.assertEqual(a[k], b[k])
        self.assertEqual(a["to_read"], load_json(SIDE)["acquisition"]["to_read"])


# ---------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    def test_r1_earlier_extractions_and_models_regenerate(self):
        """I80-R1 (fresh runs at HEAD; green at the prereg): the pinned inputs keep their sha256; the adopted Rollup
        document re-extracts byte for byte with its sidecar; holon coverage --milestone M2 --check and --milestone M3
        --check pass; the typed and untyped M3 model texts of the adopted document regenerate byte for byte."""
        item(KEY, "I80-R1")
        for rel, sha in th()["inputs_sha256"].items():
            with self.subTest(input=rel):
                self.assertEqual(file_sha256(ROOT / rel), sha)
        code, out = holon_ok(["extract", "solidity", "--sidecar", "spec/M2/lib/extract_rollup.json", "--check"], 1800)
        self.assertEqual(code, 0, out)
        for m in ("M2", "M3"):
            code, out = holon_ok(["coverage", "--milestone", m, "--check"], 1800)
            self.assertEqual(code, 0, f"{m}: {out}")
        for flag, sub, files in (([], "models", ("morph_rollup_extracted.bend",)),
                                 (["--untyped"], "untyped/models", ("morph_rollup_extracted.bend",))):
            with tempfile.TemporaryDirectory(prefix="i80-r1-") as td:
                code, out = holon_ok(["model", "--milestone", "M3", *flag, "--out", td], 1800)
                self.assertEqual(code, 0, out)
                for f in files:
                    with self.subTest(model=f"{sub}/{f}"):
                        self.assertEqual((Path(td) / f).read_bytes(),
                                         (ROOT / "gen" / "M3" / "sorts" / sub / f).read_bytes())

    def test_r2_own_commits_touch_nothing_forbidden(self):
        """I80-R2: at least one own commit adds gen/M3/bundle2/bundle2.json. No own commit changes a frozen root,
        laws/, spec/, holon/rules/, holon/frontends/, a file of thresholds.closures, a file under replay/ outside
        replay/M3/bundle2/, a file under gen/ outside gen/M3/bundle2/, or a file under results/ outside
        results/M3/bundle2/."""
        item(KEY, "I80-R2")
        commits = own_commits()
        self.assertTrue([c for c, ch in commits if ("A", "gen/M3/bundle2/bundle2.json") in ch],
                        "no own commit adds gen/M3/bundle2/bundle2.json")
        frozen = ("facts/", "laws/", "predictions/", "schemas/", "tests/", "bend/probes/", "AGENTS.md",
                  "tools/freeze.py", "docs/M0_SPEC.md", "docs/BEND_PRIMER.md", "FROZEN.sha256")
        never = frozen + ("spec/", "holon/rules/", "holon/frontends/")
        closed = set(th()["closures"])
        for c, ch in commits:
            for _st, f in ch:
                with self.subTest(commit=c[:12], path=f):
                    self.assertFalse(f.startswith(never), "a forbidden path")
                    self.assertNotIn(f, closed, "a file of a generator closure")
                    for top, mine in (("replay/", "replay/M3/bundle2/"), ("gen/", "gen/M3/bundle2/"),
                                      ("results/", "results/M3/bundle2/")):
                        if f.startswith(top):
                            self.assertTrue(f.startswith(mine), f"a file under {top} outside {mine}")

    def test_r3_the_prereg_audits_pass(self):
        """I80-R3 (the tested part; green at the prereg): holon audit prereg passes for M2 and M3."""
        item(KEY, "I80-R3")
        for m in ("M2", "M3"):
            code, out = holon_ok(["audit", "prereg", "--milestone", m], 1800)
            self.assertEqual(code, 0, f"{m}: {out}")

    def test_r4_holon_bundle2_is_generic_and_outside_every_closure(self):
        """I80-R4: holon/bundle2/ exists, imports no test module, names no target (no contract, address or host of the
        sidecar), and no file of it is in any generator closure at HEAD."""
        item(KEY, "I80-R4")
        d = ROOT / "holon" / "bundle2"
        self.assertTrue(d.is_dir(), "holon/bundle2/ is missing")
        side = load_json(SIDE)
        names = [m["contract"] for m in side["members"] + side["extracted_only"]]
        names += ["morph", "0x759894", "0x87c1d0"]
        for p in sorted(d.rglob("*.py")):
            text = p.read_text(encoding="utf-8")
            with self.subTest(file=p.name):
                self.assertIsNone(re.search(r"^\s*(from|import)\s+tests", text, re.M))
                for n in names:
                    self.assertNotIn(n, text)
        self.assertEqual([f for f in closures(ROOT) if f.startswith("holon/bundle2/")], [])
