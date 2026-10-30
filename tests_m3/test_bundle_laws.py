"""I86 (= I36b): Bundle I's laws over the current deployment, over I69's extraction (whitepaper §7.5 payer and
conservation, §5.7 DISCH external and blocking, Lemma 6.12 and Cor 6.16 injective pushing, §11.6 D7-D9, Appendix A
O29/F8, O30/F13, O34/F8; docs/HUMAN_ANSWERS.md Q28 and Q21; BUILD_PLAN I36 and rows I69 and I86). This docstring is the
contract; its sha256 is the key's thresholds.contract_docstring_sha256.

Scope. BUILD_PLAN I36 predicts, for the current deployment: O29 REFUTED; O34 blocking PROVED and the owner strategy
PROVED; D7 PROVED through injective pushing under CF (I25); D9 PROVED; O30 REFUTED; D8 PROVED with annotated
exceptions; and Q28 asks I36 to rerun BMC over the linked queue. I69 (= I36a) extracted, modelled, linked and refined
the bundle (the messenger, the queue, the whitelist and the Submitter beside the adopted Rollup) and left model debt:
model3 cannot compile the messenger's four actions that build abi.encodeWithSignature, Verify.sol's fold (a shift by a
non-constant amount) or the queue's four (a storage array's length, Yul's byte). I86 pays the messenger's debt, states
the laws under a new rule catalog, decides them with the pinned Bend over the law models, replays every witness on the
real bundle and reruns BMC with the queue linked. O13 and O20's economic half are I70's (= I36c).

The coordinator's ruling (2026-10-30): a law whose decision needs Q21's structural storage keys (I68, not yet on the
lead) is predicted UNKNOWN, naming I68; every other law is predicted on its merits.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and a line in spec/M3/amendments.jsonl):
tests_m3/_i86.py (the rules below written a second time, independently of holon/); spec/M3/lib/bundle_laws.json (the
sidecar: the catalog's sub-forms, the keyed obligations, the push candidates, the witness sources, the law models, the
whitepaper's annotation, Q28's settings, the replay, the named dependencies; no outcome); spec/M3/lib/bundle_laws_basis.json
(tests_m3/_i86.py::basis at the prereg, I69's outputs read from its pushed branch, thresholds.i69_rev). The key's
thresholds pin all three and this docstring by sha256.

Inputs, read and never written but as the rules say: I69's declaration gen/M3/bundle/bundle.json, its member documents
gen/M3/bundle/documents/*.json, its corpus gen/M3/bundle/corpus.json, its deployment record
replay/M3/bundle/deployment.json, its harness replay/M3/bundle/ and its models gen/M3/bundle/models/ (re-made by DB3);
the adopted Rollup document spec/M2/facts/morph_rollup.extracted.json; I25's sidecar spec/M3/lib/par_lossy.json (its
deferred entries); I40's BMC settings in spec/M3/lib/refute.json.

Classes (DC1-DC2)
  DC1 An action's principal class is its document's principal modifier (onlyOwner, onlyRollup, ...), "anyone" without
      one. DC2 An initializer (modifier initializer or reinitializer) belongs to no class: the bundle's deployment ran
      each member's initializer, so every later call of it reverts.

The model debt (DB1-DB3)
  DB1 holon.sorts.model3 gains three generic constructs, each emitted only into a model that uses it:
      abi.encodeWithSignature(sig, a1..an) (the selector is the first four bytes of keccak256 of the signature string,
      computed by the generator with holon.keccak, followed by the ABI head/tail encoding model3 already builds for a
      call's arguments); a shift by a non-constant amount (a bounded bit shift over W); and the packed width of a
      loop-carried name whose entry is a 32-byte hash or whose type the document gives as bytes32 (Verify.sol's fold).
  DB2 Every model model3 compiled before compiles byte for byte: the adopted Rollup's typed and untyped M3 models, I20's
      M2 model (gen/M2/extracted/), I80's router model, and I69's queue, whitelist and Submitter models.
  DB3 `holon bundle model` and `holon bundle refine` (I69's commands, unchanged) re-make I69's models and model
      refinement record (gen/M3/bundle/models/, results/M3/bundle/refinement_models.json) under I86's commit rules, as
      I69's rule m7 asks of a key that changes model3.

The law models (LM1-LM2)
  LM1 A head member's law model is its I69 model after DB3; the adopted member's (the Rollup's) is compiled by I69's
      rule M3 (model3's untyped machine, the bundle deployment's storage as s0) into gen/M3/bundle_laws/models/rollup.bend.
      Each defines HSt, HEnv, HKB, HAct (A_<action>{ar, en}), AR_<action>, s0, step(a, s, kh),
      chk_<action>(st, ar, en, kh) (0 when every check holds), post_<action>, Reach<kh, s> (R0, RStep).
  LM2 `holon bundle laws` writes the claims modules gen/M3/bundle_laws/claims/<member>.bend (each importing its law
      model as M): every predicate and term a law below names, compiled from the document's terms by model3's term
      compiler; and the analysis gen/M3/bundle_laws/laws.json (the basis as holon computes it). A law states its
      claim over M and C only.

The catalog (C1-C2)
  C1 holon-rules/1.11: the rules of the newest catalog version at the build's base, unchanged (the same producer
     objects), plus SORT payer and conservation, DISCH keyed_blocking, keyed_external and keyed_external_none, and PAR
     push, whose producers read the sidecar, I69's declaration, the member documents and I25's deferred entries;
     catalog_version of M3 and later is holon-rules/1.11. The build's report names the base version (1.7 I71's, 1.8
     I29's, 1.9 I35's, 1.10 I84's; whichever has not landed is chained when it merges, by whoever merges second).
  C2 `holon derive --milestone M3` writes exactly the basis's law ids for the six sub-forms (rule N1) and changes no
     other law but in rule_catalog_version.

Law ids (N1): SORT payer L_sort_payer_<contract>_<action>_<price check line>; SORT conservation
L_sort_cons_<contract>_<action>; DISCH keyed L_disch_kblk_<tag>_<class>, L_disch_kext_<tag>_<class>,
L_disch_knoext_<tag>_<class> (tag: slug(check span)_x8(B)); PAR push L_par_push_<contract>_<action>_<Merkle check line>.
The basis's law_ids lists them (17).

Statements (ST1): holon-ir/0.3, rule and subform as above, facts the member's document; the claim
{"eq": [{"bundle": ID, ...}, {"bool": true}]} with ID "<member>:<subform>:<site>[:<class>]", hashed through the ref
"bundle:<ID>" (the sha256 of the canonical {template "holon.rules.bundle/<subform>", template_version 1, subform,
member, site: the basis entry recomputed from the document, the declaration and the sidecar}). The Bend statement is
gen/M3/laws/<id>/LAWS.bend, importing the law model as M and the claims module as C.

SORT payer (PY1-PY4; O29)
  PY1 A price check is a guard of a payable action whose expression is [">=", msg.value, R] or ["<=", R, msg.value]; a
      price call is a ["call", fn, args..] term of R with a principal argument (the caller, tx.origin, or an
      address-typed parameter, scalar storage family or immutable): its keys.
  PY2 One law per (action, price check, price call).
  PY3 The claim (§7.5: a waiver must be keyed by the principal that bears the cost): for every table kh, reachable
      state s (Reach<kh, s>), input ar and environment en, if chk_<action>(s, ar, en, kh) == 0 then every key, as the
      model computes it (C.key_<site>_<i>), equals the payer, the step's caller (M.ge_e_caller(en)): Bend
      {C.key(..) == M.ge_e_caller(en) : M.W} under the premise binder ok: {M.chk_<action>(s, ar, en, kh) == 0 : U32}.
  PY4 A key that is the caller term is the caller by computation: the proof is the generator's {==}.

SORT conservation (CS1-CS5; O30, D8's inflow half)
  CS1 One site per payable action of a member (receive included): the inflow half of §7.5, "every inflow is accounted
      for". D8's debit half ("every debit has a matching outflow") is not stated by I86 (see the prompt's Deviations).
  CS2 The class of a site: unaccounted when msg.value reaches the value of no write and of no value call; ledger when it
      reaches the value of a write of a mapping family (a credited mapping cell); outflow when it reaches the value of
      a value call (a forwarded inflow); both when both.
  CS3 The claim, under the premise ok as in PY3: unaccounted: {M.ge_e_msg_value(en) == M.w0() : M.W}; ledger:
      {C.credit_<site>(s, ar, en, kh) == M.ge_e_msg_value(en) : M.W}, credit the sum over the site's credited mapping
      cells c of post(c) - pre(c) when the write's value reads c, else post(c) (post by M.post_<action>); outflow:
      msg.value equals the sum of the step's value-call values plus the inflow the step commits to a message (an input
      the price check adds to the price and the hashed message encodes) — not expressible over the M3 model, which
      records no value outflow (the sidecar's dependency "outflow").
  CS4 A law of the ledger class depends on I68 (dependency "I68"); of the outflow class on the outflow record
      (dependency "outflow"). With a dependency unmet no proof is attempted; the witness search still runs where the
      claim is expressible, and the law is UNKNOWN naming the dependency unless a witness refutes it.
  CS5 The sidecar's annotation (the whitepaper's "annotated slash receive") marks the record of
      L_sort_cons_Rollup_receive: triage annotated, with the annotation's text; it changes no statement.

DISCH keyed (K1-K8; O34, D9)
  K1 Each sidecar obligation names a check of a member action; its conjunct (the guard's expression after K2's normal
     form) reads exactly one mapping at a key computed from the action's inputs (the key term).
  K2 Normal form: a member read of a struct value updated at another member reads the value before the update. The
     blocked condition B(k) is the conjunct's negation (a double negation removed) with the key term replaced by k.
  K3 The families B reads; K4 their writers: every action of the member with a write of such a family, but the
     guarded action itself (it writes only when its guard holds, that is when B does not) and DC2's initializers.
  K5 A class whose actions include a writer discharges B; any other class of the member is blocked.
  K6 Laws: keyed_blocking per blocked class X; keyed_external and keyed_external_none per discharging class Y.
  K7 Claims, over binders kh, s (Reach<kh, s>), k: M.W and a: M.HAct (a step of any action, its environment inside):
     with B, in(X, a) (a's action belongs to class X), ok(a, s) (its check code is 0) and step = M.step(a, s, kh):
       keyed_blocking X     forall: {C.kblk(kh, s, k, a) == True{} : Bool}, kblk = not (B(s,k) and in(X,a) and ok(a,s))
                            or B(step, k)
       keyed_external Y     exists: {C.kext(kh, s, k, a) == True{} : Bool}, kext = B(s,k) and in(Y,a) and ok(a,s) and
                            not B(step, k)
       keyed_external_none Y forall: the keyed_blocking claim for Y (an existential law is never REFUTED: §2.12)
  K8 Every keyed_blocking law depends on I68 (it frames a mapping cell at a quantified key under a quantified table): no
     proof is attempted; the witness search runs; UNKNOWN naming I68 unless a witness refutes it.

PAR push (PP1-PP6; D7)
  PP1 A push candidate is a loop record of a member action with a carried name whose entry is
      ["keccak256", ["abi.encodeWithSignature", sig, args..]] (the leaf) and whose next value selects on
      ["&", [">>", ["param", P], ["iter", loop]], 1] (the index P): a Merkle fold that reads only bits 0..bound-1 of P.
      I86 states the candidates that I25 deferred to it (spec/M3/lib/par_lossy.json "deferred": D7).
  PP2 The leaf's preimage enc(x) is the encodeWithSignature term over the arguments x; the index field is its 32 bytes
      at offset 4 + 32 times P's position among the arguments (every argument before P a static word). The claims
      module defines them as <x>_enc(a1, .., an) and <x>_field(b), x the law id lower-cased.
  PP3 One law per candidate, line the Merkle check's (the guard reading the fold's exit).
  PP4 The claim (Lemma 6.12 pushing, Cor 6.16): for an erased hash -h: List<&2, U32> -> M.W, two argument tuples x1 and
      x2 (one binder per argument: a word for address and uint256, a byte list for bytes), a CF premise
      cf: {h(C.enc(x1)) == h(C.enc(x2)) : M.W} -> {C.enc(x1) == C.enc(x2) : List<&2, U32>} and an equal-leaves premise
      e: {h(C.enc(x1)) == h(C.enc(x2)) : M.W}: {C.field(C.enc(x1)) == C.field(C.enc(x2)) : List<&2, U32>}, field the
      32 bytes at PP2's offset (M.b_take(32n, M.b_drop(b, off), 0)); C.enc and C.field are PP2's <x>_enc and <x>_field.
      The truncated index plus the leaf determine the message: what the Merkle check binds holds the full index, not
      only its low bits.
  PP5 The proof generator: core_inj_push's step (cf applied to e), then congruence under field.
  PP6 Construction check: for each of the sidecar's sample inputs, Bend's normal form of C.field(C.enc(x)) is the index
      parameter's 32-byte big-endian word, and C.enc(x) is tests_m3/_i86.py::enc_relay's bytes (with the selector of
      tests_m2/_keccak.py); words are M.W{l0..l7}, l0 the low 32 bits, and bytes a list of U32.

Witnesses and decisions (W1-W5, D1-D4)
  W1 Sources, in order: the bundle corpus (I69's, m1, seed, random, in its order), each trace run by the linked machine
     (holon.bundle.machine) from the deployment; then, for a conservation law with no corpus witness, the value
     variants (each corpus frame of the site's action that ran ok, msg.value replaced by each sidecar value).
  W2 A candidate is a top-level frame of the law's member, with its input, environment and call answers as the linked
     machine gave them; its state is the law model's own state chain over the trace's earlier frames of that member
     (from M.s0), and the table holds the real keccak256 of every key the chain looks up (holon.sorts.evaluate3).
  W3 For a keyed law, the keys are the obligation's key term evaluated at every earlier frame of the guarded action in
     the trace; each (candidate, key) pair is a candidate.
  W4 A forall law's witness is the first candidate on which the compiled law model makes its claim false; an exists
     law's, the first on which it makes it true. The search's bound is the number of candidates of each source.
  D1 A witness's counter-law (the exs form, BEND_PRIMER §5.4) or, for an existential law, its proof, checked by the
     pinned Bend (ALL PROOFS CHECK, the expected law present): REFUTED or PROVED.
  D2 A forall law with no witness: its sub-form's proof generator when the law has no unmet dependency (PY4, PP5);
     PROVED when Bend accepts. A PROVED law with premises carries a checked inhabitant of them
     (gen/M3/<id>/nonvac/: a corpus frame for PY, x1 = x2 = a PP6 sample for PP).
  D3 Otherwise UNKNOWN, recorded with the dependencies, the bound and what was tried.
  D4 BendTT (--verdict) re-checks every accepted file where the environment provides it; its verdict is recorded and
     never changes a status.

Records and replay (RC1-RC3, RP1-RP3)
  RC1 Every law has a record results/M3/<id>.json written as the M3 typed records are (holon.records), plus rule,
      subform, dependencies (a list of "I68" and "outflow"), the attempts and bound, replay {status:
      passed|failed|not_run, detail}, the inhabitant for D2 and, for a REFUTED or existential law, the witness: {"source"
      (corpus or value_variant), "trace", "frame", "caller", "value" (decimal), "table" (preimage, hash pairs), and
      "keys" (payer: the keys' values) or "key" (keyed)}; addresses and words as 0x-prefixed lower-case hex.
  RC2 The annotation (CS5) sets the record's triage to "annotated" with the annotation's source and text.
  RC3 gen/M3/laws/<id>/LAWS.bend states exactly the law (or its counter-law cl_<id>), as G11 requires.
  RP1 Every REFUTED law and every PROVED existential law is replayed on the real bundle: its witness trace as corpus
      rows through I69's harness, from a fresh deployment (holon.bundle.harness).
  RP2 Observations: payer: the witness frame succeeds with the witness's caller and value, and the real queue's
      estimateCrossDomainMessageFee for the caller differs from its estimate for the key, both read at the frame's
      pre-state; conservation (unaccounted): the frame succeeds with value v > 0, the member's balance grows by v, and
      its storage writes equal those of the same frame with value 0; keyed: the guarded action's call at the witness
      key reverts at the obligation's check before the class's step and passes that check after it.
  RP3 replay/M3/bundle_laws/report.json: {"replay_version": "holon-bundle-laws-replay/0.1", "laws": {id: {"status",
      "observed"}}}, observed holding at least, for payer, "fee_for_caller" and "fee_for_key" (decimal strings), for
      conservation "balance_delta" and "writes_equal", for keyed "before" and "after" (the guarded call's outcome);
      `holon bundle replay-laws --check` re-runs the harness and compares.

Q28's BMC over the linked queue (Q1-Q5)
  Q1 The targets: every check of the adopted Rollup's actions whose expression calls or callok's the queue's
     getFirstUnfinalizedMessageEnqueueTime (the basis's q28.targets: callok, fits, guard and checks kinds).
  Q2 The encoding: I40's engine (holon.bmc) and budget (spec/M3/lib/refute.json bmc.H and solver.rlimit), from the
     bundle deployment's Rollup and queue storage (replay/M3/bundle/deployment.json); the queue's storage families
     join the state, and every call of the Rollup into the queue is answered by the queue document's program run
     symbolically on that state (its view functions read it, popCrossDomainMessage writes it); a step may also be the
     enqueue move, the queue's appendCrossDomainMessage by its MESSENGER with any gas limit and data the queue's own
     checks admit.
  Q3 Verdicts: path (a k <= H with a sat query), no_path (every k <= H unsat), unknown (a budget ran out); a path counts
     once concretized and replayed on the real bundle (I69's harness: the enqueue move as the messenger's sendMessage
     by the sidecar's actor, with the value its fee needs, time moves as warps); a path whose replay fails is unknown.
  Q4 results/M3/bundle_laws/bmc.json: {"bmc_version": "holon-bundle-bmc/0.1", "settings", "targets": {id: {"verdict",
     "k", "path", "reason", "replay"}}}; `holon bundle bmc --check` re-runs and compares.
  Q5 No law changes: Q28 reopens I40's verdicts, which stay in results/M3/refute/ as I40 wrote them.

Commands
  python -m holon bundle laws [--check]           LM2: the analysis, the claims modules, the Rollup's law model
  python -m holon bundle model|refine             I69's, re-made under DB1 (DB3)
  python -m holon derive --milestone M3           C1-C2
  python -m holon run --milestone M3 --laws <ids> W1-W5, D1-D4, RC1-RC3
  python -m holon bundle replay-laws [--check]    RP1-RP3
  python -m holon bundle bmc [--check]            Q1-Q5
  Exit codes: 0 written (or --check reproduced); 1 --check differs; 2 refused (a missing or stale input), nothing
  written; 3 a harness, model or checker error, nothing written. Outputs are canonical JSON, byte-identical across runs,
  with no timestamps and no absolute paths.

Own commits: the non-merge commits of `git log --first-parent <prereg>..<end>`, end the first commit adding
docs/iterations/I86.md (HEAD while none does). Commit rules (I86-R2): judged one by one against its first parent, no own
commit changes a frozen root, an earlier M3 law but in rule_catalog_version, or an earlier M3 record's status; at end,
every record directly under results/M1, results/M2 and results/T32 carries a generator_sha256 other than at the prereg
(re-made: holon/sorts/model3.py and holon/rules/ are in their closures).

Earlier tests amended at this prereg: none. A test of another key that fails on I86's outcomes is reported under
Surprises, with an amendment line only when its assertion is wrong. I69's own --check tests over gen/M3/bundle/models
and results/M3/bundle/refinement_models.json are red between DB1 and DB3, and green after DB3.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests_m3._m3 import ROOT, file_sha256, holon_module, item, load_json, predictions, run_bend, run_holon

KEY = "I86"
SIDE = ROOT / "spec" / "M3" / "lib" / "bundle_laws.json"
BASIS = ROOT / "spec" / "M3" / "lib" / "bundle_laws_basis.json"
MODELS_REC = ROOT / "gen" / "M3" / "bundle" / "models" / "models.json"
REFM = ROOT / "results" / "M3" / "bundle" / "refinement_models.json"
ANALYSIS = ROOT / "gen" / "M3" / "bundle_laws" / "laws.json"
CLAIMS = ROOT / "gen" / "M3" / "bundle_laws" / "claims"
ROLLUP_MODEL = ROOT / "gen" / "M3" / "bundle_laws" / "models" / "rollup.bend"
REPLAY = ROOT / "replay" / "M3" / "bundle_laws" / "report.json"
BMC = ROOT / "results" / "M3" / "bundle_laws" / "bmc.json"
REPORT = "docs/iterations/I86.md"
SUBFORMS = {"payer": "SORT", "conservation": "SORT", "keyed_blocking": "DISCH", "keyed_external": "DISCH",
            "keyed_external_none": "DISCH", "push": "PAR"}
FROZEN = ("facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/", "AGENTS.md", "tools/freeze.py",
          "docs/M0_SPEC.md", "docs/BEND_PRIMER.md", "FROZEN.sha256")
TARGET_NAMES = ("L1CrossDomainMessenger", "L1MessageQueueWithGasPriceOracle", "Submitter", "Whitelist", "Rollup",
                "replayMessage", "proveAndRelayMessage", "sendMessage", "maxReplayTimes", "finalizedWithdrawals",
                "replayStates", "estimateCrossDomainMessageFee", "commitBatch", "challengeState",
                "getFirstUnfinalizedMessageEnqueueTime", "appendCrossDomainMessage", "relayMessage")


def th() -> dict:
    return predictions(KEY)["thresholds"]


def need(p: Path) -> dict:
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing")
    return load_json(p)


def instrument():
    import tests_m3._i86 as I
    return I


def basis() -> dict:
    return need(BASIS)


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def show(rev: str, rel: str):
    p = subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{rel}"], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout)
    except ValueError:
        return None


def prereg_commit() -> str:
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I86 (the audit's C_K)."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        d = show(c, "spec/M3/predictions.json")
        if isinstance(d, dict) and KEY in (d.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I86")


def end_commit() -> str:
    added = git("log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--", REPORT).split()
    return added[0] if added else "HEAD"


def own_commits() -> list:
    """I86's own commits, oldest first, each with the paths it changes against its first parent."""
    commits, cur = [], None
    for ln in git("log", "--first-parent", "--no-merges", "--no-renames", "--reverse", "--format=@%H", "--name-only",
                  f"{prereg_commit()}..{end_commit()}").splitlines():
        if ln.startswith("@"):
            cur = (ln[1:], [])
            commits.append(cur)
        elif ln.strip() and cur is not None:
            cur[1].append(ln.strip())
    return commits


def law(lid: str) -> dict:
    return need(ROOT / "laws" / "M3" / f"{lid}.json")


def record(lid: str) -> dict:
    return need(ROOT / "results" / "M3" / f"{lid}.json")


def ids(sub: str) -> list:
    return list(basis()["law_ids"][sub])


def checked(test: unittest.TestCase, lid: str, rec: dict) -> None:
    """A decided record: the checker printed ALL PROOFS CHECK, the law file states the expected law (G11: the law or its
    counter-law cl_<id>), and the proof re-checks with the pinned Bend now."""
    test.assertEqual((rec.get("checker") or {}).get("marker"), "ALL PROOFS CHECK", lid)
    art = rec.get("artifacts") or {}
    laws_file, proof = ROOT / art.get("laws", "-"), ROOT / art.get("proof", "-")
    test.assertTrue(laws_file.is_file() and proof.is_file(), f"{lid}: {art}")
    names = re.findall(r"(?m)^law (\w+):", laws_file.read_text(encoding="utf-8"))
    want = lid.lower() if rec["status"] == "PROVED" else "cl_" + lid.lower()
    test.assertEqual(names, [want], lid)
    rc, out = run_bend([proof.name], cwd=proof.parent, timeout=1800)
    test.assertEqual(rc, 0, f"{lid}: {out[-800:]}")
    test.assertTrue(out.lstrip().startswith("ALL PROOFS CHECK"), f"{lid}: {out[-800:]}")


def replayed(test: unittest.TestCase, lid: str, rec: dict) -> None:
    rep = need(REPLAY)
    test.assertEqual(rep.get("replay_version"), "holon-bundle-laws-replay/0.1")
    entry = (rep.get("laws") or {}).get(lid) or {}
    test.assertEqual(entry.get("status"), "passed", f"{lid}: {entry}")
    test.assertEqual((rec.get("replay") or {}).get("status"), "passed", f"{lid}: {rec.get('replay')}")


def unknown_naming(test: unittest.TestCase, lid: str, rec: dict, deps: list) -> None:
    test.assertEqual(rec.get("status"), "UNKNOWN", lid)
    test.assertEqual(sorted(rec.get("dependencies") or []), sorted(deps), lid)
    test.assertTrue(rec.get("attempts"), f"{lid}: an UNKNOWN record names what was tried")


# ================================================================================================ instruments
class TestInstrument(unittest.TestCase):
    def test_pins(self):
        t = th()
        I = instrument()
        self.assertEqual(file_sha256(ROOT / t["instrument"]), t["instrument_sha256"])
        self.assertEqual(file_sha256(SIDE), t["sidecar_sha256"])
        self.assertEqual(file_sha256(BASIS), t["basis_sha256"])
        import tests_m3.test_bundle_laws as me
        self.assertEqual(hashlib.sha256(me.__doc__.encode("utf-8")).hexdigest(), t["contract_docstring_sha256"])
        self.assertEqual(I.BASIS_VERSION, basis()["basis_version"])

    def test_basis_recomputes_from_the_merged_outputs(self):
        """The basis, recomputed from the working tree once I69 has merged, equals the committed one (but its rev)."""
        I = instrument()
        have = I.basis(ROOT)
        want = dict(basis())
        want.pop("rev", None)
        have.pop("rev", None)
        self.assertEqual(have, want)

    def test_expected_law_ids(self):
        b = basis()
        self.assertEqual(b["law_ids"], th()["law_ids"])
        self.assertEqual(b["law_count"], 17)
        self.assertEqual(instrument().expected_status(b, need(SIDE)), th()["expected_status"])


# ================================================================================================ catalog
class TestCatalog(unittest.TestCase):
    def test_c1_the_catalog(self):
        R = holon_module("holon.rules")
        v = th()["catalog"]
        self.assertEqual(R.catalog_version("M3"), v)
        cat = R.CATALOGS[v]
        for sub, rule in SUBFORMS.items():
            self.assertIn(sub, cat.get(rule, {}), f"{rule}/{sub}")
        prev = [k for k in R.CATALOGS if k != v and k.startswith("holon-rules/1.")]
        base = max(prev, key=lambda k: tuple(int(x) for x in k.split("/")[1].split(".")))
        for rule, subs in R.CATALOGS[base].items():
            for sub, prod in subs.items():
                self.assertIs(cat[rule][sub], prod, f"{rule}/{sub} is not the base's producer object")

    def test_c2_the_law_ids(self):
        prefix = {"payer": "L_sort_payer_", "conservation": "L_sort_cons_", "keyed_blocking": "L_disch_kblk_",
                  "keyed_external": "L_disch_kext_", "keyed_external_none": "L_disch_knoext_", "push": "L_par_push_"}
        names = {p.stem for p in (ROOT / "laws" / "M3").glob("L_*.json")}
        for sub, pre in prefix.items():
            self.assertEqual(sorted(n for n in names if n.startswith(pre)), sorted(ids(sub)), sub)
            for lid in ids(sub):
                lw = law(lid)
                self.assertEqual((lw.get("rule"), lw.get("subform")), (SUBFORMS[sub], sub), lid)
                self.assertEqual(lw.get("rule_catalog_version"), th()["catalog"], lid)


# ================================================================================================ the model debt
class TestDebt(unittest.TestCase):
    def test_p1_the_messengers_model_compiles_and_refines(self):
        rec = need(MODELS_REC)
        debt = rec.get("debt") or []
        self.assertEqual([d for d in debt if d.get("member") == "messenger"], [], "messenger debt remains")
        self.assertEqual(sorted(d["action"] for d in debt if d.get("member") == "queue"), th()["queue_debt"])
        text = (ROOT / rec["models"]["messenger"]["path"]).read_text(encoding="utf-8")
        for a in th()["messenger_debt_paid"]:
            self.assertIn(f"def run_{a}(", text, a)
        for bad in ("?TODO", "@unsafe", 'import "'):
            self.assertNotIn(bad, text)
        rm = need(REFM)
        det = (rm.get("details") or {}).get("messenger") or []
        newly = set(th()["messenger_debt_paid"])
        for d in det:
            self.assertNotIn("model debt", str(d.get("reason")), d)
            if d.get("action") in newly:
                self.assertTrue(str(d.get("reason") or "").startswith("the model gives no return data"), d)

    def test_r1_earlier_models_compile_byte_for_byte(self):
        """DB2: the adopted Rollup's typed M3 model (committed) and untyped M3 model (its sha256 at the prereg), I80's
        router model (holon bundle2 model --check) and I69's queue, whitelist and Submitter models (their sha256 in I69's
        models record) do not move; I69's models record is reproduced (holon bundle model --check, after DB3)."""
        with tempfile.TemporaryDirectory() as td:
            for untyped in (False, True):
                out = Path(td) / ("u" if untyped else "t")
                p = run_holon(["model", "--milestone", "M3", "--out", str(out)] + (["--untyped"] if untyped else []),
                              timeout=3600)
                self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])
                got = (out / "morph_rollup_extracted.bend").read_bytes()
                if untyped:
                    self.assertEqual(hashlib.sha256(got).hexdigest(), th()["rollup_untyped_model_sha256"])
                else:
                    self.assertEqual(got, (ROOT / "gen/M3/sorts/models/morph_rollup_extracted.bend").read_bytes())
        for args in (["bundle", "model", "--check"], ["bundle2", "model", "--check"]):
            p = run_holon(args, timeout=3600)
            self.assertEqual(p.returncode, 0, f"{args}: {p.stdout[-800:]}{p.stderr[-800:]}")
        rec = need(MODELS_REC)
        for m, sha in th()["i69_model_sha256"].items():
            self.assertEqual(rec["models"][m]["sha256"], sha, f"{m}'s model moved")


# ================================================================================================ SORT payer
class TestPayer(unittest.TestCase):
    def test_p2_o29_the_replay_waiver_is_keyed_on_the_origin(self):
        (lid,) = [x for x in ids("payer") if "_replayMessage_" in x]
        rec = record(lid)
        self.assertEqual(rec.get("status"), "REFUTED", lid)
        checked(self, lid, rec)
        w = rec.get("witness") or {}
        self.assertTrue(w.get("keys"), w)
        self.assertNotIn(str(w.get("caller", "")).lower(), [str(k).lower() for k in w["keys"]], w)
        replayed(self, lid, rec)
        obs = ((need(REPLAY).get("laws") or {}).get(lid) or {}).get("observed") or {}
        self.assertNotEqual(obs.get("fee_for_caller"), obs.get("fee_for_key"), obs)

    def test_p3_the_send_waivers_are_keyed_on_the_payer(self):
        for lid in [x for x in ids("payer") if "_replayMessage_" not in x]:
            rec = record(lid)
            self.assertEqual(rec.get("status"), "PROVED", lid)
            checked(self, lid, rec)
            nv = ROOT / "gen" / "M3" / lid / "nonvac" / "PROOF.bend"
            self.assertTrue(nv.is_file(), f"{lid}: no inhabitant")
            rc, out = run_bend([nv.name], cwd=nv.parent, timeout=1800)
            self.assertTrue(rc == 0 and out.lstrip().startswith("ALL PROOFS CHECK"), f"{lid}: {out[-600:]}")


# ================================================================================================ SORT conservation
class TestConservation(unittest.TestCase):
    def test_p4_o30_value_attached_to_commit_is_unaccounted(self):
        lid = "L_sort_cons_Rollup_commitBatch"
        self.assertIn(lid, ids("conservation"))
        rec = record(lid)
        self.assertEqual(rec.get("status"), "REFUTED", lid)
        checked(self, lid, rec)
        self.assertGreater(int(str((rec.get("witness") or {}).get("value", "0")), 0), 0)
        replayed(self, lid, rec)

    def test_p5_the_receives_are_unaccounted(self):
        for lid in ("L_sort_cons_Rollup_receive", "L_sort_cons_L1CrossDomainMessenger_receive"):
            self.assertIn(lid, ids("conservation"))
            rec = record(lid)
            self.assertEqual(rec.get("status"), "REFUTED", lid)
            checked(self, lid, rec)
            replayed(self, lid, rec)
        ann = record("L_sort_cons_Rollup_receive")
        self.assertEqual(ann.get("triage"), "annotated")
        self.assertEqual((ann.get("annotation") or {}).get("source"), need(SIDE)["annotations"][0]["source"])
        self.assertNotEqual(record("L_sort_cons_L1CrossDomainMessenger_receive").get("triage"), "annotated")

    def test_p6_the_other_inflows_are_unknown_with_their_dependencies(self):
        b = basis()
        rest = [s for s in b["conservation"] if s["class"] != "unaccounted"]
        self.assertEqual(len(rest), 5)
        for s in rest:
            unknown_naming(self, s["law_id"], record(s["law_id"]), s["dependencies"])


# ================================================================================================ DISCH keyed
class TestKeyed(unittest.TestCase):
    def obligation(self, name: str) -> dict:
        return next(k for k in basis()["keyed"] if k["obligation"] == name)

    def test_p7_o34_the_owner_can_raise_the_replay_budget(self):
        k = self.obligation("O34")
        (ext,) = k["laws"]["keyed_external"]
        (none,) = k["laws"]["keyed_external_none"]
        r1, r2 = record(ext), record(none)
        self.assertEqual(r1.get("status"), "PROVED", ext)
        self.assertEqual(r2.get("status"), "REFUTED", none)
        checked(self, ext, r1)
        checked(self, none, r2)
        replayed(self, ext, r1)

    def test_p8_o34_blocking_waits_on_i68(self):
        (blk,) = self.obligation("O34")["laws"]["keyed_blocking"]
        unknown_naming(self, blk, record(blk), ["I68"])

    def test_p9_d9_relay_at_most_once_waits_on_i68(self):
        laws = self.obligation("D9")["laws"]
        self.assertEqual(len(laws["keyed_blocking"]), 2)
        self.assertEqual(laws["keyed_external"], [])
        for blk in laws["keyed_blocking"]:
            unknown_naming(self, blk, record(blk), ["I68"])


# ================================================================================================ PAR push
class TestPush(unittest.TestCase):
    def test_p10_d7_the_leaf_binds_the_whole_index(self):
        (lid,) = ids("push")
        rec = record(lid)
        self.assertEqual(rec.get("status"), "PROVED", lid)
        checked(self, lid, rec)
        nv = ROOT / "gen" / "M3" / lid / "nonvac" / "PROOF.bend"
        self.assertTrue(nv.is_file(), f"{lid}: no inhabitant of the premises")
        rc, out = run_bend([nv.name], cwd=nv.parent, timeout=1800)
        self.assertTrue(rc == 0 and out.lstrip().startswith("ALL PROOFS CHECK"), out[-600:])

    def test_pp6_the_index_field_is_the_index(self):
        """Construction: Bend's normal form of the claims module's field(enc(x)) is the index word, and enc(x) is the
        instrument's ABI bytes, for every sample (the claims module and its law model copied into a scratch tree with
        their relative layout)."""
        from tests_m2._keccak import keccak256
        I = instrument()
        (p,) = basis()["push"]
        x = p["law_id"].lower()
        sel = keccak256(p["signature"].encode("ascii"))[:4]
        types = [t for _n, t in p["arguments"]]
        model_rel = need(MODELS_REC)["models"][p["member"]]["path"]
        claims_rel = f"gen/M3/bundle_laws/claims/{p['member']}.bend"
        for smp in need(SIDE)["push"]["samples"]:
            vals = []
            for n, t in p["arguments"]:
                v = smp[n]
                vals.append(bytes.fromhex(v[2:]) if t == "bytes" else int(v, 16) if isinstance(v, str) else int(v))
            want = I.enc_relay(sel, types, vals)
            idx = vals[p["index_position"]]
            with tempfile.TemporaryDirectory() as td:
                for rel in (model_rel, claims_rel):
                    dst = Path(td) / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes((ROOT / rel).read_bytes())
                main = Path(td) / Path(claims_rel).parent / "pp6_main.bend"
                rel_model = os.path.relpath(Path(td) / model_rel, main.parent)
                args = ", ".join(self.lit(v, t) for v, t in zip(vals, types))
                main.write_text(
                    "import Base\n"
                    f"import ./{p['member']}.bend as C\n"
                    f"import {rel_model if rel_model.startswith('.') else './' + rel_model} as M\n\n"
                    "def main() -> List<&2, U32> & List<&2, U32>:\n"
                    f"  (C.{x}_enc({args}), C.{x}_field(C.{x}_enc({args})))\n", encoding="utf-8")
                rc, out = run_bend([main.name], cwd=main.parent, timeout=600)
                self.assertEqual(rc, 0, out[-600:])
                nums = [int(v) for v in re.findall(r"\d+", out.split("ALL PROOFS CHECK")[-1])]
                self.assertEqual(nums, list(want) + list(idx.to_bytes(32, "big")))

    @staticmethod
    def lit(v, t: str) -> str:
        if t == "bytes":
            return "[" + ", ".join(str(b) for b in v) + "]"
        limbs = [(v >> (32 * i)) & 0xFFFFFFFF for i in range(8)]
        return "M.W{" + ", ".join(str(x) for x in limbs) + "}"


# ================================================================================================ Q28
class TestQ28(unittest.TestCase):
    def test_p11_bmc_over_the_linked_queue(self):
        rec = need(BMC)
        self.assertEqual(rec.get("bmc_version"), "holon-bundle-bmc/0.1")
        q = basis()["q28"]
        tg = rec.get("targets") or {}
        self.assertEqual(sorted(tg), sorted(t["id"] for t in q["targets"]))
        for cid in q["callok"]:
            self.assertEqual(tg[cid].get("verdict"), "no_path", cid)
        for cid in th()["q28_paths"]:
            self.assertEqual(tg[cid].get("verdict"), "path", cid)
            self.assertEqual((tg[cid].get("replay") or {}).get("status"), "passed", cid)


# ================================================================================================ regressions
class TestRegressions(unittest.TestCase):
    def test_r2_own_commits_move_no_earlier_outcome(self):
        mine = set()
        for sub in SUBFORMS:
            mine.update(ids(sub))
        base = prereg_commit()
        for c, paths in own_commits():
            for p in paths:
                self.assertFalse(p.startswith(FROZEN), f"{c[:12]} changes the frozen {p}")
                m = re.fullmatch(r"laws/M3/(L_\w+)\.json", p)
                if m and m.group(1) not in mine:
                    old, new = show(f"{c}^", p), show(c, p)
                    if old is not None and new is not None:
                        old.pop("rule_catalog_version", None)
                        new.pop("rule_catalog_version", None)
                        self.assertEqual(old, new, f"{c[:12]} changes the earlier law {p}")
                m = re.fullmatch(r"results/M3/(L_\w+)\.json", p)
                if m and m.group(1) not in mine:
                    old, new = show(f"{c}^", p), show(c, p)
                    if old is not None and new is not None:
                        self.assertEqual(old.get("status"), new.get("status"), f"{c[:12]} moves {p}'s status")
        for d in ("results/M1", "results/M2", "results/T32"):
            for p in sorted((ROOT / d).glob("*.json")):
                rel = p.relative_to(ROOT).as_posix()
                now = load_json(p)
                then = show(base, rel)
                if isinstance(now, dict) and "generator_sha256" in now and isinstance(then, dict):
                    self.assertNotEqual(now.get("generator_sha256"), then.get("generator_sha256"), f"{rel} not re-made")

    def test_r3_the_prereg_audits_pass(self):
        for m in ("M2", "M3"):
            p = run_holon(["audit", "prereg", "--milestone", m], timeout=1800)
            self.assertEqual(p.returncode, 0, f"{m}: {p.stdout[-1500:]}{p.stderr[-800:]}")

    def test_r4_the_new_code_names_no_target(self):
        added: dict = {}
        for c, _paths in own_commits():
            diff = git("show", "--format=", "--unified=0", "--no-renames", c, "--", "holon/")
            cur = None
            for ln in diff.splitlines():
                if ln.startswith("+++ b/"):
                    cur = ln[6:]
                elif ln.startswith("+") and not ln.startswith("+++") and cur:
                    added.setdefault(cur, []).append(ln[1:])
        for path, lines in sorted(added.items()):
            for ln in lines:
                code = ln.split("#", 1)[0]
                if code.strip().startswith(('"', "'")):
                    continue
                for name in TARGET_NAMES:
                    self.assertNotRegex(code, rf"\b{name}\b", f"{path}: {ln.strip()}")
                self.assertNotRegex(code, r"0x[0-9a-fA-F]{40}", f"{path}: {ln.strip()}")


if __name__ == "__main__":
    unittest.main()
