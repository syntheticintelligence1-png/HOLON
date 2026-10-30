"""I69 (= I36a): Bundle I's extraction and acquisition, with no law (whitepaper §10.1 Solidity, deployment history and
linking, §8.7 refinement, §9.3 G8, §11.1 scope; BUILD_PLAN I36 and row I69; docs/HUMAN_ANSWERS.md Q12, Q18, Q19, Q21,
Q23, Q28). This docstring is the contract; its sha256 is the key's thresholds.contract_docstring_sha256.

Scope. BUILD_PLAN I36 (Bundle I: messenger, queue, Merkle, accounting, cutover) is split three ways (row I69). I69
extracts what Bundle I's laws read and links it into one machine: the messenger (L1CrossDomainMessenger), the message
queue (L1MessageQueueWithGasPriceOracle), the whitelist (Whitelist) and the registry of the current Rollup
(Submitter), each at the pinned head 3e44e795; and the legacy registry (L1Staking), recovered from chain as Q12
requires and extracted at the last tag that holds it, v0.6.1. It states no law, changes no rule catalog and adopts no
document into M3's derivation (spec/M3/lib/derive_extracted.json stays I24's). I36 keeps its number for the laws over
the current deployment (O29, O30, O34, D7, D8, D9, Q28's BMC rerun, and D4 if Q63 moves it to the key that links the
queue); I70 (= I36c) takes the cutover's economics (O13, O20's economic half), after I28's build and I29, and links
L1Staking with the V10 Rollup of I28's versioned machine; a fix key I68 builds Q21's structural storage keys.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and a line in spec/M3/amendments.jsonl):
tests_m3/_i69.py (the rules below written a second time, independently of holon/, over I63's instrument
tests_m3/_i63.py and tests_m2/_keccak.py; its one network read is A7's anchor read, `python -m tests_m3._i69
--second-read`, run once after the build's fetch); spec/M3/lib/bundle.json (the sidecar: members, wiring, deployment,
corpus, observables, the registry's tags and compiler configurations, proxies, window and hosts; no outcome);
spec/M3/lib/bundle_basis.json (tests_m3/_i69.py::basis at the prereg: rules A1-A2 over the registry's 24 tags and the
four members' head builds). The key's thresholds pin all three, this docstring, and the sha256 of C3's m1 part
(thresholds.corpus.m1_sha256, holon.mreplay.random_corpus's output at the prereg) by sha256.

Inputs, read and never written: spec/M2/facts/morph_rollup.extracted.json and its sidecar
spec/M2/lib/extract_rollup.json (the adopted Rollup document, a member as it is); spec/M1/facts/morph_rollup.json and
replay/M2/fragments.json (I20's deployment parameters and base corpus); replay/M1/solidity/ and replay/M2/solidity/
(I20's harness, copied, never edited); I63's committed cutover receipt and on-chain snapshot (results/M3/history/),
whose SubmitterContractUpdated log names the legacy registry's and the Submitter's proxies; I23's call record
results/M2/historical/trans.json, which names the queue's proxy; the target repository's git objects (config/holon.json
extract.sources), with lazy fetching disabled.

Extraction (E1-E7)
  E1 Members. The sidecar's members are the Rollup (its adopted document, unchanged) and messenger, queue, whitelist
     and submitter; its extracted_only member is l1staking. For every member but the Rollup, `holon bundle extract`
     writes a generated extraction sidecar gen/M3/bundle/sidecars/<member>.json: spec/M2/lib/extract_rollup.json with
     target.commit the member's commit, target.scope "bundle member <name> (<contract>)", sources [the member's
     source], transitions {contract, commit_interfaces} the member's, output gen/M3/bundle/documents/<member>.json and
     a doc of its own; then that document, the transitions document I19's frontend (holon.frontends.solidity, its walk
     and its coverage rules) extracts from it.
  E2 Overloads. Where two actions of a contract share a function name (distinct selectors), each is named
     <name>_<the 8 hex digits of its selector>; every other action keeps its name (its kind for receive and fallback).
     The same rule names a called function: an external call of a function f declared in I, where I has more than one
     external function named f, is "<I>.<f>_<selector>". No document extracted before I69 changes (none has an
     overload). The action set is I19's rule: every external or public function with a body of the contract and its
     bases, most derived first, one per selector.
  E3 Tag-pinned trees. A sidecar whose target.commit is not the checkout's HEAD is compiled from that commit's tree,
     materialized from the target repository's objects (its contracts/ tree, written to a temporary directory outside
     both repositories) with the pinned solc and dependency tree, as I63 builds tags and as I28's V5 extracts versions
     (one mechanism in holon.frontends.solidity, whichever key builds it first). The target repository's refs, index,
     working tree and objects are never written: lazy fetching is disabled, and an object the repository lacks refuses
     the extraction (exit 2), never fetches it.
  E4 The declaration. gen/M3/bundle/bundle.json: {"bundle_version": "holon-bundle/0.1", "sidecar": {"path", "sha256"},
     "members": [{"name", "contract", "commit", "sidecar": {"path", "sha256"} or null for the adopted Rollup,
     "document": {"path", "sha256"}}], "extracted_only": [same shape], "debt": [{"member", "reason"}], "coverage": [one
     entry per generated document, sorted by document, in holon.coverage's entry format: {"document", "statements",
     "extracted", "debt", "unaccounted"}, the frontend's coverage_document on the generated sidecar, over E3's tree when
     the commit is not HEAD], "links": rule L2's rows}. A member whose extraction fails is debt with its error, never
     smoothed, and has no document.
  E5 Coverage. `holon coverage --milestone M3` lists, besides what it lists at the prereg, the entry of every member of
     the milestone's bundle sidecar (spec/<M>/lib/bundle.json) whose commit is the target's pinned head (the four head
     members, compiled from the checkout as the Rollup is), equal to the declaration's entry. The Rollup's entry and the
     report's format do not change; G8 on M3 thus requires unaccounted == [] for the four head documents. An
     extracted_only member's entry is the declaration's alone: its tree comes from git objects (E3), which CI's partial
     clone of the target at the pinned head does not hold, so no gate check reads it.
  E6 No earlier extraction moves: the frontend changes are additive, and every document holon extract writes for M2
     (I17, I19, I18) and gen/M2/coverage.json regenerate byte for byte.
  E7 holon/ names no target: every contract, function, address, slot or host comes from the sidecars, the documents or
     the compiler's output; holon/ does not import tests_m3.

Models (M1-M6)
  M1 The evaluator of record (holon.extracted_eval) computes every term of the four head documents, by additive
     extensions only: at least push and pop writes of a storage dynamic array (its length at its slot, its elements from
     keccak256 of the slot) with index reads and writes and lengths, index reads and writes of static arrays of sub-word
     elements (the compiler's packing), abi.encodeWithSignature (the first four bytes of keccak256 of the literal
     signature, then the ABI encoding of the arguments by their types), abi.encodeCall (the called function's selector,
     then the encoding of the tuple), and an action's return value as ABI-encoded return data. A step it computed
     before, it computes the same.
  M2 holon.sorts.model3 compiles the same terms, and also shifts by a non-constant amount and the packed width of an
     abi.encodePacked operand that is a loop-carried name (the type of its entry, confirmed by its next value: a hash is
     bytes32) or an index into a calldata static array (its element type). Emission is additive: the fixed PRELUDE and
     _COMMON texts and MODEL3_VERSION do not change, a new helper is emitted only into a model that uses it, and the
     typed and untyped models of the adopted Rollup document regenerate byte for byte.
  M3 Member models. `holon bundle model` writes gen/M3/bundle/models/<member>.bend and <member>.init.json for the four
     head members, each the member's document compiled by model3 as `holon model --untyped` compiles one (no sort
     section: the frozen assignment covers the adopted document only), its initial state the member's storage after the
     bundle deployment (C1's record), in whatever storage representation model3 has when they are built (I68 may
     change it; the models follow); and gen/M3/bundle/models/models.json {"models_version": "holon-bundle-models/0.1",
     "models": {member: {"path", "sha256", "document_sha256"}}, "debt": [{"member", "action", "error"}]}: an action
     model3 cannot compile is debt with its GenError, never left out, and its steps are unsupported under M4.
  M4 Member refinement. For each head member, every corpus step whose top-level callee is that member is run on its
     model compiled to JavaScript (holon.sorts.evaluate3's driver, as I30's typed model is refined), from the member's
     real pre-state, with the answers the real code received to the member's own external calls (the harness's
     record), and the code lengths and balances C5 names: status; the revert key on two reverts; the return data on
     two oks (the ABI encoding of the action's return value, so views and pure functions are compared on what they
     return); the member's storage at every slot a write of the step touches on either side; and its logs. Record:
     results/M3/bundle/refinement_models.json {"refinement_models_version": "holon-bundle-refinement-models/0.1",
     "corpus": {"path", "sha256"}, "observables": ["status", "revert", "return", "storage", "events"], "members":
     {member: {"model", "model_sha256", "steps", "disagreements": [{"id", "class", "links"}], "unexplained",
     "unsupported"}}}.
  M5 Nothing under gen/M3/sorts/, gen/M3/undo/, gen/M3/disch/, gen/M3/fact/, gen/M3/theory/ or gen/M3/theory2/ changes.
     I69 regenerates none of them: R1 regenerates the adopted document's typed and untyped M3 models and I20's M2
     model (gen/M2/extracted/{model.bend, layout.json, window_check.json}, holon.machine.write_model as gate-M2's G1
     does) in scratch; the UNDO, FACT and DISCH section models are checked at the next M3 re-make.
  M6 Every claim about storage is stated in real slots (EVM storage addresses), never in a model's encoding of a
     location (Q21: structural keys may replace the keccak table; real slots are what the harness compares).

The linked machine (L1-L8; holon/bundle/, generic, over holon.extracted_eval's programs of the members' documents)
  L1 State: every member's raw storage (slot -> word) and every member's ETH balance.
  L2 Static links. For every member document, every call record of every action whose receiver term is ["storage", f]
     or ["immutable", f] with "<member>.<f>" in the sidecar's wiring: a row [member, action, src, fn, callee, kind,
     target], where kind is "action" (the callee's document has an action named as the called function: target that
     name), "getter" (it has none, but a storage family of that name: target that family; its public getter) or
     "receive" (a low-level address.call: target "receive"). Sorted. These are the deployment's linked call sites.
  L3 Dispatch. A call to a member runs the member's action whose selector is the calldata's first four bytes; empty
     calldata runs its receive action; a selector of no action but of a public storage family's getter returns that
     getter's ABI encoding of the storage word(s), read at the compiler's slots; any other selector reverts with empty
     data, as the compiler's dispatcher does. Dispatch comes first: such a revert is decided before L5 is consulted,
     whether or not the member is already on the frame stack. msg.value moves from the caller's balance to the
     callee's.
  L4 Linked calls. An external call term of a running action whose receiver evaluates, when the call is made, to a
     member address runs that member as a nested frame (L3) with the calling member as caller and the term's value, on
     the bundle state as the transaction's earlier frames left it; its result answers the term: callok holds when the
     frame succeeded and its return data decodes by the called function's output types (the frontend's callok, which
     includes the decoder's checks), and the call's value is that decoding. A high-level call whose frame reverts makes
     the caller revert with the frame's revert data (with empty data when only the decoding failed); a low-level call's
     failure is a value, and the failed frame's writes and value move are discarded. A revert of the step discards every
     write and value move of the step.
  L5 Re-entry. A nested frame on a member already on the frame stack runs only when its action writes no storage (its
     document's effects are empty: a view, a pure function or an empty receive); otherwise the step is unsupported
     ("reentry: <member>.<action>"), never guessed. So every member document's A-reentrancy holds in every step the
     machine evaluates.
  L6 Depth. A step that would nest more frames than the sidecar's link.depth (8) is unsupported ("depth").
  L7 Non-members. A call whose receiver is not a member is answered from the harness's record of that call (to, data,
     value, ok, return data), as I20's env.calls, its callok as in L4 (a call to an address without code succeeds with
     empty return data, which no output type decodes); a call with no recorded answer is unsupported; value sent to a
     non-member leaves the caller's balance when the answer is ok. The verifier is I20's stand-in, a non-member.
  L8 A step's result: status, revert data, return data, the writes of every member (slot -> word), the logs (emitter,
     topics, data) in order, every member's balance after the step, the outgoing calls (from, to, value, data) in
     order, and the frames in C2's form (the static link rows a step executed follow from them, C6).
  Environment reads. A step's ["code", a] terms (address.code.length) and balance reads are answered from the
     deployment record (C1): every member, the harness w1, I20's verifier stand-in and the proxy admin have their
     deployed code's length; the actors w2..w9 and every other address have none; a member's balance is the bundle
     state's, another address's balance is the harness's record of it before the step.

Harness and corpus (C1-C6; replay/M3/bundle/, gen/M3/bundle/corpus.json)
  C1 Deployment. Each trace starts from a fresh deployment, made as the sidecar's deployment section says (the real
     Rollup, messenger, queue and Submitter behind OpenZeppelin 4.9.3 TransparentUpgradeableProxy contracts with the
     admin 0xAD, the real Whitelist, I20's verifier stand-in; I20's parameters F, W, D, t0 and r0; w2 and w3 registered
     and staked submitters, w4 the challenger, w6 the fee vault, w8 the enforced-transaction gateway; the genesis batch
     imported). Its record replay/M3/bundle/deployment.json gives every member's address, implementation and immutable
     words, and every member's non-zero slots and balance after the deployment.
  C2 Harness. A generic multi-target step base (I20's HolonStepBase generalized: per step and per member, its storage
     writes, its logs, its balance after the step, every frame on a member with its selector, value and outcome, every
     call leaving the bundle with its answer, and vm.load of every slot of every member's layout after the step) and the
     concrete harness (C1's deployment; row, call and relay steps). I20's harness files are copied, never edited. A
     frame is [parent, caller, callee, selector, value, ok]: the callee a member (a call to a member's address, through
     its proxy if it has one), parent the index in the step's frame list of the nearest enclosing member frame (-1 for
     none), caller a member name, "@w<K>" or a lowercase 0x address, selector "0x" and the calldata's first four bytes
     ("0x" alone for empty calldata), ok true when the frame returned without reverting and no enclosing frame of the
     step reverted (its writes were kept); frames in the order they begin.
  C3 Corpus. `holon bundle corpus` writes gen/M3/bundle/corpus.json, deterministically: {"corpus_version":
     "holon-bundle-corpus/0.1", "sidecar": {"path", "sha256"}, "sources": {"m1", "seed", "random"} (trace counts),
     "traces": [{"id", "source", "steps"}]}, the m1 traces, then the seed traces, then the random ones, from three
     sources. m1: I20's base corpus (holon.mreplay.random_corpus on the M1 model of spec/M1/facts/morph_rollup.json,
     seed 20261011, 300 traces), ids m1/000..m1/299, each step {"row": the row dict}; its sha256 (tests_m3/_i69.py::
     m1_sha256: of json.dumps(the 300 lists of row dicts, sort_keys=True, separators=(",", ":"))) is
     thresholds.corpus.m1_sha256, computed at the prereg; the harness runs the rows as I20's harness translates them but
     for sendMessage {who}, which becomes the real messenger's sendMessage(address,uint256,bytes,uint256)(0x7a, 0,
     empty, 1000000) by who's actor with no value, while wait and @legacy_eta2 rows are environment steps as in I20
     (run and tracked, not compared). seed: the sidecar's seven planted traces verbatim (rows, calls and relays), ids
     seed/<name> in the sidecar's order. random: tests_m3/_i69.py::random_corpus, which is this rule: R = the
     sidecar's corpus.random, rng = random.Random(R.seed); members = the sidecar's members' names sorted; per member,
     the actions of rule E2 at its commit (the adopted Rollup's at its document's commit) sorted by name, each with
     solc's ABI entry (by selector; receive and fallback by kind); then for t in 0..R.traces-1 (id random/<t, 3
     digits>), with a uint pool initialized to R.uints, for each of R.steps steps, in this draw order: warp =
     rng.choice(R.warp.seconds) if rng.randrange(den) < num (R.warp.probability = num/den) else 0; member =
     rng.choice(members); action = rng.choice(its actions); caller = rng.choice(R.callers); value =
     rng.choice(R.values) if the action is payable else 0; then each ABI input in order, recursively: T[] draws its
     length by rng.choice(R.array_lengths) then its elements, T[k] its k elements, a tuple its components, address
     rng.choice(R.addresses), bool rng.choice([False, True]), uintN rng.choice(pool) mod 2^N (appended to the pool when
     new), intN rng.choice(pool) mod 2^(N-1) (likewise), bytes rng.choice(R.bytes), bytesN the first N bytes of
     rng.choice(R.words); the step is {"call": {"to": member, "fn": the ABI signature ("receive" or "fallback" for
     those), "caller", "value", "args"}}, plus "warp": warp when it is not 0 (the harness warps by it before the
     call). The corpus is checked against this rule by tests_m3/_i69.py::corpus_differences; a step no harness or
     machine can run is unsupported, never dropped.
  C4 Relay steps. The leaf is keccak256 of
     abi.encodeWithSignature("relayMessage(address,address,uint256,uint256,bytes)", from, to, value, nonce, message);
     the root folds 32 zero siblings over it at index nonce (Verify.sol's rule); the step pokes the Rollup's
     withdrawalRoots entry (family slot 163, the adopted document's) of that root to 1 (root "valid"), of the root of
     message ++ 0x00 ("mismatch") or of nothing ("unknown"), then calls proveAndRelayMessage with the 32 zero siblings
     and the root. The sidecar's check gives seed S2_relay step 1's leaf, root and poked slot.
  C5 Comparison. Per step, the linked machine runs the step's call from the real pre-state of every member (the tracked
     storage, confirmed by vm.load) and the real member balances, with the step's environment (the environment reads
     above; non-member answers as L7): status; revert key on two reverts (holon.replay_fragments.revert_key); return
     data on two oks; every member's storage at every slot a write of the step touches on either side; the members'
     logs in order; every member's balance after the step; the outgoing calls; and the frames (the machine's, in C2's
     form, equal to the harness's). A difference, or a step the machine leaves unsupported, is a disagreement, filed in
     results/M3/bundle/disagreements.json as I20 files them (an id that is a function of the step, "unexplained" with no
     links; a class only from links, holon.refinement.classify).
  C6 Record. results/M3/bundle/steps.json, the per-step evidence: {"steps_version": "holon-bundle-steps/0.1",
     "corpus": {"path", "sha256"}, "steps": [{"trace", "step" (its index in the trace), "compared" (false for
     environment steps), "status" ("ok" or "revert"; the top-level call's, null for an environment step), "frames" (the
     harness's, C2's form), "agree" (the comparison's verdict), "unsupported" (the machine's reason, or null)}]} in
     corpus order. results/M3/bundle/refinement.json: {"refinement_version": "holon-bundle-refinement/0.1", "corpus":
     {"path", "sha256", "sources": {"m1", "seed", "random"} (trace counts)}, "traces", "steps" (compared steps),
     "observables" (the sidecar's), "disagreements": [{"id", "class", "links"}], "unexplained", "unsupported",
     "frames_ok": {member: {action: n}} (kept frames on a member whose selector is the action's, top-level or nested),
     "links_ok": [[member, action, src, fn, n]] (every L2 row with the number of kept frames on its callee, at its
     target's selector, whose parent frame is on its member at its action's selector), "by_member_action": {member:
     {action: {"ok", "revert"}}} (the top-level frames of compared steps), "toolchain"}. traces, steps, frames_ok,
     by_member_action and links_ok are tests_m3/_i69.py::recount over steps.json, decided from the harness's frames
     alone. `holon bundle refine` writes both, M4's record and the disagreements; it is the one command that runs
     forge.

Acquisition (A1-A7; Q12: the legacy registry found from on-chain history, its code fetched and matched by
metadata-stripped bytecode; Q18's cross-check, for the registry's proxy and the live bundle's)
  A1 Registry refs. The sidecar's 24 pinned tags (every pinned tag of I63's sidecar whose tree holds
     contracts/contracts/l1/staking/L1Staking.sol), each at its pin and holding the unit, by committer time then name;
     no head ref (the unit is absent at the head).
  A2 Builds. I63's H2-H6 over those refs under I63's three configurations (version configuration "hardhat"), with every
     build's immutable ranges by name; and the four members' builds at the head under the same configurations (code
     identity, length, ranges, immutable ranges by name). spec/M3/lib/bundle_basis.json is their computation at the
     prereg; `holon bundle history` writes gen/M3/bundle/history/l1staking.json in I63's history format (its refs,
     versions and edges equal to the basis's registry part).
  A3 Fetch (`holon bundle fetch`, the one command of holon that touches the network; --check verifies offline). Through
     the sidecar's RPC, with fetch_block the latest block when the fetch starts (at or after the window's end): for each
     proxy (the registry 0x0dc417f8...43f7 and the Submitter 0xf2d50000...bef6, from I63's cutover receipt; the queue
     0x3931ade8...c1ef, from I23's record; the messenger, the low 20 bytes of the MESSENGER immutable word of the queue's
     last implementation in the window), eth_getLogs over [the window's from_block 19426587, fetch_block] for the
     Upgraded, AdminChanged and Initialized topics, in chunks, and eth_getStorageAt of its EIP-1967 implementation slot
     (the sidecar's acquisition.eip1967) at fetch_block; the receipt of every transaction with an Upgraded log of a
     proxy, stored in I59's canonical form (results/M3/bundle/receipts/<tx>.json); the runtime code of every
     implementation at fetch_block (results/M3/bundle/code/<address>.hex, lowercase hex, no 0x, a final newline); the
     queue proxy's word at the queue's whitelistChecker slot (from solc's layout, which the queue document's storage
     gives) at fetch_block, and the code of the address it names. results/M3/bundle/onchain.json: {"onchain_version":
     "holon-bundle-onchain/0.1", "sidecar": {"path", "sha256"}, "rpc": {"host", "methods"}, "fetch_block", "window":
     [from_block, to_block], "proxies": {name: {"address", "logs": [{"block", "tx", "log_index", "topics", "data"}]
     (every log the scan returned, by block then log index), "upgrades": [{"block", "tx", "log_index",
     "receipt_sha256", "implementation", "code_sha256", "code_length"}], "implementation_slot": {"slot", "block",
     "word"}}}, "whitelist": {"proxy", "slot", "block", "word", "address", "code_sha256", "code_length"}}. Addresses,
     hashes, topics, data and words are lowercase 0x-hex throughout; blocks, log indexes and slots are integers.
  A4 Decode: a receipt's logs of the proxy, in log-index order: Upgraded (topic 1), Initialized (its version word),
     AdminChanged (previous and new); its from and contractAddress (tests_m3/_i69.py::decode).
  A5 Match: I63's H7 identity against the registry's versions (every configuration) and against each member's head
     builds; for a single match, the implementation's words at the matched build's ranges of each immutable.
  A6 Timeline (`holon bundle timeline`): results/M3/bundle/timeline.json, equal to tests_m3/_i69.py::timeline, which
     recomputes it from the committed snapshot's raw material and trusts none of holon's derived fields: every log
     inside [from_block, fetch_block], of its proxy, unique; the proxies' addresses the sidecar's (the messenger's, the
     queue's last implementation's MESSENGER word); each proxy's upgrades rebuilt from its raw Upgraded logs, each
     confirmed by its committed receipt (that transactionHash, blockNumber and status 0x1, the same log at its log
     index) and decoded from it, its implementation matched on its committed code; the implementation slot word at
     fetch_block naming the implementation of the proxy's last Upgraded log (the scan complete at its end); the
     whitelist the low 20 bytes of the queue proxy's word at the whitelistChecker slot. An upgrade after the window's
     end is listed apart (after_window). A snapshot that fails any of these refuses the timeline (InstrumentError), so
     P1 and P2 are not held.
  A7 Anchors. The registry's and the Submitter's addresses come from I63's cutover receipt, whose sha256 I59 recorded;
     the queue's from I23's record. The other reads have no anchor in the repository, so after the fetch
     `python -m tests_m3._i69 --second-read` (the instrument, not holon) reads them again from the first answering
     host of the sidecar's rpc.second, independently of holon's fetch, and writes results/M3/bundle/second_read.json:
     {"second_read_version": "holon-bundle-second-read/0.1", "host", "methods", "fetch_block", "latest_block",
     "proxies": {name: {"address", "logs" (the same scan over [from_block, fetch_block]), "implementation_slot_latest"}},
     "whitelist_slot_latest", "receipts": {tx: the sha256 of its canonical bytes}, "code": {address: {"sha256",
     "length"}}}. tests_m3/_i69.py::second_read_differences compares it with the snapshot, the receipt files and the
     code files; when they differ, I69-P1 and I69-P2 are UNKNOWN (neither held nor missed), by the anchor test.

Shared files, changed only so (not outcome paths): gen/M3/coverage.json (E5: the four head members' entries added, the
Rollup's entry unchanged); the code under holon/ but holon/rules/ (among others holon/frontends/solidity/,
holon/extracted_eval.py, holon/machine.py, holon/sorts/model3.py, holon/sorts/evaluate3.py, holon/coverage.py,
holon/__main__.py's dispatch and new modules under holon/bundle/); the records directly under results/M1/ and
results/M2/ (holon run --milestone M1 and --milestone M2, then I40's filter stage, holon refute --milestone M3 --only
filter, in the same commit: generator_sha256 and keys named seconds alone, since I69 edits files of the holon-ir/0.2 and
0.3 generator closures, never the six of holon-ir/0.1; results/M3/refute/filter.json unchanged; holon lean need not run,
since holon run rebuilds each lean4 kernel entry from the committed Lean reports and I69's extensions change no Lean
text of an existing law); the five records directly under results/T32/ (I32's; holon profile --milestone T32:
generator_sha256 and keys named seconds alone, since I69's code is in I32's generator closure,
holon.profile.generator_files; laws/T32, gen/T32, results/T32/summary.json and gen/M3/disch/classification.json stay
byte-identical; without it I32's C1, which compares a fresh run's records with the committed ones up to seconds, fails);
lines appended to spec/M3/amendments.jsonl whose iteration is I69 (the contract's route for a wrong instrument; the
file is append-only, so the commit only adds such lines). No M3 record is re-made: every M3 record's generator_sha256
trails I69's closures (GEN3, GEN_FACT, GEN_UNDO, GEN_DISCH, holon-ir/0.3) until the next M3 re-make, as after I66; the
full M3 gate's G1 fails on that staleness meanwhile, and CI's M3 jobs run no G1. holon/bundle/ is imported by no module
of any generator closure (holon.records.generator_files, holon.sorts.run3.GEN3, holon.fact.run, holon.undo.run,
holon.disch.run, holon.profile.generator_files). A later key that changes holon.frontends.solidity,
holon.extracted_eval, holon.sorts.model3, holon.sorts.evaluate3 or holon/bundle/ so that `holon bundle extract`,
`model`, `corpus`, `history` or `timeline --check` differs re-makes gen/M3/bundle/ and results/M3/bundle/ under its own
commit rules (refine on a forge runner); until it does, the R5 --check tests are expected red, and that key says so.

Own commits (LANE_RULES' one-PR rule): the non-merge commits of `git log --first-parent <C_K>..<end>`, C_K the prereg
commit (the oldest commit whose spec/M3/predictions.json holds the key I69, found with --full-history) and end the
oldest commit adding docs/iterations/I69.md (--full-history; HEAD while none does). Process rules that make this
exactly I69's commits: the prereg, its fold, the build, the outcomes and the report are commits of one branch
(claude/brave-wright-2c5d0o-i36) whose first-parent line runs from C_K to the report; the branch takes the lead's
changes only by merge commits whose first parent is the branch, so no lead commit lies on that line, whether the lead's
commits came by merge or were pushed to the lead directly; the report is the branch's last own commit and is written
once (no draft report is committed before the build ends); the branch reaches the lead only as the second parent of a
merge commit. A commit after the report on the branch is outside the rule; the process makes none.
Commit rules (I69-R2; they imply the earlier keys' I63-R2, I43-R8, I26-R1, I31-R2 and I40-R2): at least one own commit
adds gen/M3/bundle/bundle.json; no own commit changes a frozen root, laws/, spec/ (but appended I69 lines of
spec/M3/amendments.jsonl), holon/rules/, a file under replay/ outside replay/M3/bundle/, a file under gen/ outside
gen/M3/bundle/ but gen/M3/coverage.json (whose entries at the commit's parent stay as they are: the commit only adds),
or a file under results/ outside results/M3/bundle/ but the records directly under results/M1/, results/M2/ and
results/T32/ (none added or deleted, each keeping its status and differing from its parent's version only in
generator_sha256 and keys named seconds).

Earlier tests amended at this prereg: none. I69 adopts no document (I24's and I25's pins of the M3 documents, models
and records hold), adds no rule, law or catalog, and its outputs live under new paths. One that fails on I69's outcomes
is a miss, reported. I32-R2 (tests_m3/test_disch_profile.py::TestRegressions.
test_r2_no_closure_and_no_earlier_output_changes) was re-scoped by I66's prereg (merged into the lead at a0bfc521) to
I32's own commits found by ancestry path, so I69's closure edits and outputs are not counted as I32's; I69 does not
amend it.

Commands
  python -m holon bundle extract|model|corpus|refine|history|fetch|timeline [--check]
  python -m holon coverage --milestone M3 [--check]     (E5)
  Exit codes: 0 written (or --check reproduced); 1 --check differs; 2 refused (a missing or stale input, a missing git
  object), nothing written; 3 an extraction, model, harness or fetch error, nothing written. Outputs are canonical JSON
  (sorted keys, indent 1, a final newline) but receipts (I59's compact canonical bytes); byte-identical across runs; no
  timestamps, no absolute paths.
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

KEY = "I69"
SIDE = ROOT / "spec" / "M3" / "lib" / "bundle.json"
BASIS = ROOT / "spec" / "M3" / "lib" / "bundle_basis.json"
DECL = ROOT / "gen" / "M3" / "bundle" / "bundle.json"
DOCS = ROOT / "gen" / "M3" / "bundle" / "documents"
MODELS = ROOT / "gen" / "M3" / "bundle" / "models"
HIST = ROOT / "gen" / "M3" / "bundle" / "history" / "l1staking.json"
CORPUS = ROOT / "gen" / "M3" / "bundle" / "corpus.json"
REF = ROOT / "results" / "M3" / "bundle" / "refinement.json"
REFM = ROOT / "results" / "M3" / "bundle" / "refinement_models.json"
DIS = ROOT / "results" / "M3" / "bundle" / "disagreements.json"
ONCHAIN = ROOT / "results" / "M3" / "bundle" / "onchain.json"
TIMELINE = ROOT / "results" / "M3" / "bundle" / "timeline.json"
STEPS = ROOT / "results" / "M3" / "bundle" / "steps.json"
SECOND = ROOT / "results" / "M3" / "bundle" / "second_read.json"
COV3 = ROOT / "gen" / "M3" / "coverage.json"
ROLLUP_DOC = "spec/M2/facts/morph_rollup.extracted.json"
HEAD_MEMBERS = ("messenger", "queue", "submitter", "whitelist")
BUNDLE_DOCS = ("l1staking", "messenger", "queue", "submitter", "whitelist")
ZERO = "0x" + "00" * 20
_CACHE: dict = {}


def th() -> dict:
    return predictions(KEY)["thresholds"]


def need(p: Path) -> dict:
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing")
    return load_json(p)


def instrument():
    import tests_m3._i69 as I
    return I


def doc(member: str) -> dict:
    return need(DOCS / f"{member}.json")


def word(addr: str) -> str:
    return "0x" + "00" * 12 + addr.lower()[2:]


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def prereg_commit() -> str:
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I69 (the audit's C_K)."""
    for c in git("log", "--full-history", "--format=%H", "--reverse", "HEAD", "--",
                 "spec/M3/predictions.json").split():
        try:
            d = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(d, dict) and KEY in (d.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I69")


def own_commits() -> list:
    """I69's own commits (the contract's one-PR rule): the non-merge commits of `git log --first-parent <C_K>..<end>`,
    end the oldest commit adding docs/iterations/I69.md (HEAD while none does), oldest first, each with its (status,
    path) pairs."""
    added = git("log", "--full-history", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--",
                "docs/iterations/I69.md").split()
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


def added_lines(commit: str, rel: str) -> list:
    """The lines a commit adds to a file (its diff against its first parent)."""
    out = git("diff", "--no-renames", "-U0", f"{commit}^", commit, "--", rel)
    return [ln[1:] for ln in out.splitlines() if ln.startswith("+") and not ln.startswith("+++")]


def show(commit: str, rel: str):
    try:
        return json.loads(git("show", f"{commit}:{rel}"))
    except (AssertionError, ValueError):
        return None


def ifaces() -> dict:
    """The instrument's interfaces of every member (solc at its commit), computed once."""
    if "ifaces" not in _CACHE:
        _CACHE["ifaces"] = instrument().interfaces(ROOT)
    return _CACHE["ifaces"]


def recomputed() -> dict:
    """The instrument's timeline over the committed snapshot and the frozen basis, computed once (A6)."""
    if "timeline" not in _CACHE:
        need(ONCHAIN)
        _CACHE["timeline"] = instrument().timeline(ROOT, need(BASIS), ifaces())
    return _CACHE["timeline"]


def recounted() -> dict:
    """C6 recounted by the instrument from the per-step evidence and the predicted link rows."""
    if "recount" not in _CACHE:
        _CACHE["recount"] = instrument().recount(need(STEPS), ifaces(), th()["links"])
    return _CACHE["recount"]


def holon_ok(args: list, timeout: int = 7200):
    p = run_holon(args, timeout=timeout)
    return p.returncode, (p.stdout[-1500:] + p.stderr[-1500:])


# ---------------------------------------------------------------------------------------------- instruments
class TestInstrument(unittest.TestCase):
    """The frozen inputs are what they say they are (construction; green at the prereg)."""

    def test_the_key_pins_the_instruments(self):
        t = th()
        self.assertEqual(file_sha256(SIDE), t["sidecar_sha256"])
        self.assertEqual(file_sha256(BASIS), t["basis_sha256"])
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i69.py"), t["instrument_sha256"])
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i63.py"), t["i63_instrument_sha256"])
        d = sys.modules[__name__].__doc__
        self.assertEqual(hashlib.sha256(d.encode("utf-8")).hexdigest(), t["contract_docstring_sha256"])
        b = need(BASIS)
        self.assertEqual(b["sidecar_sha256"], file_sha256(SIDE))
        self.assertEqual([[v["id"], v["refs"]] for v in b["registry"]["versions"]], t["registry_versions"])
        self.assertEqual(sorted(b["members"]), sorted(HEAD_MEMBERS))

    def test_the_basis_recomputes(self):
        """A1-A2 recomputed from the repository's objects by the instrument equal the frozen basis (every registry ref
        and every member built under every configuration)."""
        self.assertEqual(instrument().basis(ROOT), need(BASIS))

    def test_the_sidecar_names_committed_facts(self):
        """The registry's tags are I63's pins of the 24 tags whose tree holds L1Staking.sol; the registry's and the
        Submitter's proxies are the cutover receipt's SubmitterContractUpdated topics, the receipt hashing to I63's
        (I59-anchored) receipt_sha256; the queue's proxy is the address I23's record names once per IL1MessageQueue
        call; the configurations, events, window and RPC are I63's; the relay check is the instrument's C4 over seed
        S2_relay step 1, and the family slot 163 is the adopted document's withdrawalRoots slot; the Rollup's wiring
        names families of its document."""
        I = instrument()
        side, hist = load_json(SIDE), load_json(ROOT / "spec" / "M3" / "lib" / "history.json")
        acq = side["acquisition"]
        holding = I.tags_with_unit(hist["tags"], acq["registry"]["contract"]["source"], ROOT)
        self.assertEqual(len(holding), 24)
        self.assertEqual(sorted(set(hist["tags"]) - set(holding)), ["v0.6.3"])
        self.assertEqual(acq["registry"]["tags"], {t: hist["tags"][t] for t in holding})
        cut = I.cutover_registries(ROOT)
        self.assertEqual((cut["old"], cut["new"], cut["index"], cut["emitter"]),
                         (acq["proxies"]["registry"]["address"], acq["proxies"]["submitter"]["address"], 60477,
                          hist["proxy"]["address"]))
        onchain = load_json(ROOT / "results" / "M3" / "history" / "onchain.json")
        self.assertEqual([u["receipt_sha256"] for u in onchain["upgrades"] if u["block"] == 26031669],
                         [cut["receipt_sha256"]])
        q = I.queue_of_i23(ROOT)
        top = max(q["counts"].items(), key=lambda kv: kv[1])
        self.assertEqual((top[0], top[1]), (acq["proxies"]["queue"]["address"], q["queue_calls"]))
        self.assertEqual((acq["compiler_configs"], acq["events"], acq["rpc"]["url"]),
                         (hist["compiler_configs"], hist["events"], hist["rpc"]["url"]))
        self.assertEqual((acq["window"]["from_block"], acq["window"]["to_block"]),
                         (hist["upgrades"]["window"]["from_block"], hist["upgrades"]["window"]["to_block"]))
        rel = side["corpus"]["relay"]
        step = side["corpus"]["seed"][rel["check"]["step"][0]][rel["check"]["step"][1]]["relay"]
        actors = side["deployment"]["actors"]
        leaf = I.relay_leaf(int(actors[step["from"][1:]], 16), int(actors[step["to"][1:]], 16), step["value"],
                            step["nonce"], bytes.fromhex(step["message"][2:]))
        root = I.relay_root(leaf, step["nonce"])
        self.assertEqual(("0x" + leaf.hex(), "0x" + root.hex(), "0x" + I.poke_slot(root, rel["slot"]).hex()),
                         (rel["check"]["leaf"], rel["check"]["root"], rel["check"]["poke_slot"]))
        fams = {s["name"]: s["slot"] for s in load_json(ROOT / ROLLUP_DOC)["storage"]}
        self.assertEqual(fams[rel["family"]], rel["slot"])
        for k in side["wiring"]:
            if k.startswith("rollup."):
                self.assertIn(k.split(".", 1)[1], fams, k)

    def test_the_legacy_sources_are_one_unit_from_v040(self):
        """Disclosed reading, checked from the tags' trees: at the 22 tags v0.4.0..v0.6.1, L1Staking.sol and five of its
        six repository imports are one blob each; ICrossDomainMessenger.sol is 9ec8f339 at v0.4.0-v0.4.2 and 8d0ee03f
        from v0.4.3, the two texts differing in the pragma line alone; and the basis's registry version V3 is exactly
        those 22 tags under every configuration."""
        I = instrument()
        tab = I.closure_table(ROOT)
        late = sorted(t for t in tab if not t.startswith("v0.2"))
        self.assertEqual(len(late), 22)
        for p in I.REGISTRY_IMPORTS:
            blobs = {tab[t][p] for t in late}
            if p.endswith("ICrossDomainMessenger.sol"):
                self.assertEqual({b[:8] for b in blobs}, {"9ec8f339", "8d0ee03f"})
                a, b = sorted(blobs, key=lambda x: x[:8] != "9ec8f339")
                ta, tb = I.blob_text(a, ROOT).splitlines(), I.blob_text(b, ROOT).splitlines()
                self.assertEqual([(x, y) for x, y in zip(ta, tb) if x != y],
                                 [("pragma solidity ^0.8.9;", "pragma solidity =0.8.24;")])
                self.assertEqual(len(ta), len(tb))
            else:
                self.assertEqual(len(blobs), 1, p)
        v3 = [v for v in need(BASIS)["registry"]["versions"] if v["id"] == "V3"]
        self.assertEqual(len(v3), 1)
        self.assertEqual(sorted(v3[0]["refs"]), late)

    def test_the_construction_pins_are_solc_s(self):
        """thresholds.structure's construction parts (action names, own families, inherited entries, constants) are the
        instrument's solc reading of every bundle document's contract at its commit, and the 28 link rows have unique
        (member, action, callee, target selector), so the harness's frames decide each row (C6)."""
        I = instrument()
        t = th()
        for m in BUNDLE_DOCS:
            got = I.structure(ifaces(), m)
            with self.subTest(member=m):
                self.assertEqual({k: t["structure"][m][k] for k in ("actions", "storage", "inherited", "constants")},
                                 got)
        self.assertEqual([x[4] for x in I.recount({"steps": []}, ifaces(), t["links"])["links_ok"]], [0] * 28)

    def test_the_random_corpus_is_pinned(self):
        """C3's random part, regenerated by the instrument from the sidecar and solc's interfaces, hashes to
        thresholds.corpus.random_sha256 (recorded at the prereg)."""
        I = instrument()
        rc = I.random_corpus(load_json(SIDE), ifaces())
        self.assertEqual(hashlib.sha256(json.dumps(rc, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                         th()["corpus"]["random_sha256"])

    def test_rule_e2_reads_the_adopted_rollup(self):
        """The instrument's E2 over solc's AST gives the adopted Rollup document's 33 action names (no overload)."""
        acts = instrument().ast_actions(ROOT, "contracts/contracts/l1/rollup/Rollup.sol", "Rollup",
                                        load_json(SIDE)["target"]["head"])
        self.assertEqual(acts, sorted(a["name"] for a in load_json(ROOT / ROLLUP_DOC)["actions"]))


# ---------------------------------------------------------------------------------------------- extraction
class TestExtraction(unittest.TestCase):
    def test_p3_documents_and_coverage(self):
        """I69-P3: five documents and no member debt; the declaration's coverage gives each no unaccounted statement and
        exactly the predicted debt entries; holon coverage --milestone M3 lists the four head documents with the
        declaration's entries beside the unchanged Rollup entry, with no unaccounted statement in all."""
        item(KEY, "I69-P3")
        t = th()
        decl = need(DECL)
        self.assertEqual(decl["debt"], [])
        self.assertEqual(sorted(m["name"] for m in decl["members"] + decl["extracted_only"]),
                         sorted(("rollup",) + BUNDLE_DOCS))
        rel = {m: f"gen/M3/bundle/documents/{m}.json" for m in BUNDLE_DOCS}
        dcov = {d["document"]: d for d in decl["coverage"]}
        self.assertEqual(sorted(dcov), sorted(rel.values()))
        cov = need(COV3)
        by = {d["document"]: d for d in cov["documents"]}
        self.assertEqual(sorted(by), sorted([ROLLUP_DOC] + [rel[m] for m in HEAD_MEMBERS]))
        self.assertEqual(hashlib.sha256(json.dumps(by[ROLLUP_DOC], sort_keys=True).encode()).hexdigest(),
                         t["rollup_coverage_entry_sha256"])
        self.assertEqual(cov["unaccounted"], 0)
        for m in BUNDLE_DOCS:
            with self.subTest(member=m):
                e = dcov[rel[m]]
                self.assertEqual(e["unaccounted"], [])
                self.assertEqual([[d["src"], d["kind"], d["detail"]] for d in e["debt"]], t["debt"][m])
                if m in HEAD_MEMBERS:
                    self.assertEqual(by[rel[m]], e)

    def test_p4_the_documents_are_as_read(self):
        """I69-P4: per document, the loop records per action and the loop spans of the cost terms per action, as the
        sources were read before the prereg (thresholds.structure's loops and cost)."""
        item(KEY, "I69-P4")
        t = th()["structure"]
        for m in BUNDLE_DOCS:
            d, want = doc(m), t[m]
            with self.subTest(member=m):
                loops = {a["name"]: len(a.get("loops") or []) for a in d["actions"] if a.get("loops")}
                self.assertEqual(loops, want["loops"])
                cost = {a["name"]: sorted({x["loop"] for x in a["cost"]["terms"]})
                        for a in d["actions"] if a["cost"]["terms"]}
                self.assertEqual(cost, want["cost"])

    def test_the_documents_carry_solc_s_structure(self):
        """Construction (R5; the review's m1): per document, the action names (rule E2), the own storage families in
        declaration order, the number of inherited entries and the constants are solc's at the member's commit (the
        instrument's structure()), and equal thresholds.structure's (computed so at the prereg)."""
        I = instrument()
        t = th()["structure"]
        for m in BUNDLE_DOCS:
            d, want, got = doc(m), t[m], I.structure(ifaces(), m)
            with self.subTest(member=m):
                self.assertEqual({k: want[k] for k in ("actions", "storage", "inherited")},
                                 {k: got[k] for k in ("actions", "storage", "inherited")})
                self.assertEqual(sorted(a["name"] for a in d["actions"]), want["actions"])
                self.assertEqual([x["name"] for x in d["storage"]], want["storage"])
                self.assertEqual(len(d["inherited_storage"]), want["inherited"])
                self.assertEqual(sorted(d["constants"]), sorted(got["constants"]))
                self.assertEqual(d["constants"], want["constants"])
                for k, v in got["constants"].items():
                    if v is not None:
                        self.assertEqual(str(d["constants"][k]), v, k)

    def test_extract_reproduces(self):
        """Construction (E1, E4): holon bundle extract --check reproduces the generated sidecars, documents and
        declaration."""
        code, out = holon_ok(["bundle", "extract", "--check"])
        self.assertEqual(code, 0, out)

    def test_the_generated_sidecars_and_rule_e2(self):
        """Construction (E1, E2): every generated sidecar is extract_rollup.json with the member's commit, source,
        contract, commit interfaces and output; every document's action names are the instrument's E2 over solc's AST
        at the member's commit."""
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
                want = dict(base, output=f"gen/M3/bundle/documents/{e['name']}.json", sources=[m["source"]],
                            transitions={"contract": m["contract"], "commit_interfaces": m["commit_interfaces"]})
                want["target"] = dict(base["target"], commit=m["commit"],
                                      scope=f"bundle member {e['name']} ({m['contract']})")
                self.assertEqual({k: v for k, v in sc.items() if k not in ("doc",)},
                                 {k: v for k, v in want.items() if k not in ("doc",)})
                d = doc(e["name"])
                self.assertEqual(d["extraction"]["sidecar"], e["sidecar"])
                self.assertEqual(sorted(a["name"] for a in d["actions"]),
                                 I.ast_actions(ROOT, m["source"], m["contract"], m["commit"]))


# ---------------------------------------------------------------------------------------------- models
class TestModel(unittest.TestCase):
    def test_p5_member_models_compile_and_refine(self):
        """I69-P5: the four head members' models compile with no model debt, and each refines its member on every
        top-level corpus step on it (status, revert key, return data, the member's storage at every touched slot and
        its logs): no disagreement and no unsupported step."""
        item(KEY, "I69-P5")
        ms = need(MODELS / "models.json")
        self.assertEqual(sorted(ms["models"]), sorted(HEAD_MEMBERS))
        self.assertEqual(ms["debt"], [])
        for m, e in ms["models"].items():
            self.assertEqual(e["sha256"], file_sha256(ROOT / e["path"]))
            self.assertEqual(e["document_sha256"], file_sha256(DOCS / f"{m}.json"))
        r = need(REFM)
        self.assertEqual(r["corpus"], {"path": "gen/M3/bundle/corpus.json", "sha256": file_sha256(CORPUS)})
        self.assertEqual(r["observables"], ["status", "revert", "return", "storage", "events"])
        self.assertEqual(sorted(r["members"]), sorted(HEAD_MEMBERS))
        for m, x in r["members"].items():
            with self.subTest(member=m):
                self.assertGreater(x["steps"], 0)
                self.assertEqual((x["disagreements"], x["unexplained"], x["unsupported"]), ([], 0, 0))
                self.assertEqual(x["model_sha256"], file_sha256(ROOT / x["model"]))

    def test_models_reproduce(self):
        """Construction (M3): holon bundle model --check reproduces the member models and models.json."""
        code, out = holon_ok(["bundle", "model", "--check"])
        self.assertEqual(code, 0, out)


# ---------------------------------------------------------------------------------------------- the linked machine
class TestLink(unittest.TestCase):
    def test_p6_the_linked_machine_refines_the_bundle(self):
        """I69-P6: the declaration's static links are the predicted 28 rows (the 16 rows of the messenger, the queue and
        the Submitter predicted by reading; the Rollup's 12 are rule L2 on the committed document, construction), and
        on the whole corpus the linked machine agrees with the real bundle in every observable, its frames included:
        no disagreement and no unsupported step, in the record and in every step of the per-step evidence."""
        item(KEY, "I69-P6")
        t = th()
        self.assertEqual(need(DECL)["links"], t["links"])
        r = need(REF)
        self.assertEqual(r["corpus"]["path"], "gen/M3/bundle/corpus.json")
        self.assertEqual(r["corpus"]["sha256"], file_sha256(CORPUS))
        self.assertEqual(r["corpus"]["sources"], t["corpus_traces"])
        self.assertEqual(need(CORPUS)["sources"], t["corpus_traces"])
        self.assertEqual(r["observables"], load_json(SIDE)["observables"])
        self.assertGreater(r["steps"], 0)
        self.assertEqual((r["disagreements"], r["unexplained"], r["unsupported"]), ([], 0, 0))
        d = need(DIS)
        self.assertEqual(d.get("disagreements"), [])
        st = need(STEPS)
        self.assertEqual(st["corpus"], {"path": "gen/M3/bundle/corpus.json", "sha256": file_sha256(CORPUS)})
        bad = [(x["trace"], x["step"]) for x in st["steps"] if x["compared"] and (not x["agree"] or x["unsupported"])]
        self.assertEqual(bad[:20], [])
        self.assertEqual((r["traces"], r["steps"]), (recounted()["traces"], recounted()["steps"]))

    def test_p7_the_corpus_reaches_every_link_and_action(self):
        """I69-P7, decided on the instrument's recount of the harness's frames (C6): every static link row was executed
        with a kept frame at least once, and every action of the four head members but their initializers ended ok
        in at least one kept frame, top-level or nested; the record's counts are the recount's."""
        item(KEY, "I69-P7")
        t = th()
        rc = recounted()
        r = need(REF)
        for k in ("frames_ok", "links_ok", "by_member_action"):
            with self.subTest(record=k):
                self.assertEqual(r[k], rc[k])
        ok = {tuple(x[:4]): x[4] for x in rc["links_ok"]}
        for row in t["links"]:
            with self.subTest(link=row[:4]):
                self.assertGreater(ok.get(tuple(row[:4]), 0), 0)
        for m in HEAD_MEMBERS:
            for a in doc(m)["actions"]:
                if {"initializer", "reinitializer"} & set(a.get("modifiers") or []):
                    continue
                with self.subTest(member=m, action=a["name"]):
                    self.assertGreater(rc["frames_ok"].get(m, {}).get(a["name"], 0), 0)

    def test_the_links_follow_rule_l2(self):
        """Construction (L2): the declaration's links are the instrument's rule over the committed documents and the
        sidecar's wiring."""
        docs = {m: doc(m) for m in HEAD_MEMBERS}
        docs["rollup"] = load_json(ROOT / ROLLUP_DOC)
        self.assertEqual(need(DECL)["links"], instrument().link_table(docs, load_json(SIDE)["wiring"]))

    def test_corpus_reproduces(self):
        """Construction (C3): holon bundle corpus --check reproduces gen/M3/bundle/corpus.json (no forge run)."""
        code, out = holon_ok(["bundle", "corpus", "--check"], timeout=1800)
        self.assertEqual(code, 0, out)

    def test_the_corpus_is_rule_c3(self):
        """Construction (C3; the review's M4): the m1 part hashes to the prereg's pin, the seed part is the sidecar's
        traces verbatim, the random part is the instrument's regeneration, and the sources are counted."""
        c = need(CORPUS)
        self.assertEqual(c["sidecar"], {"path": "spec/M3/lib/bundle.json", "sha256": file_sha256(SIDE)})
        self.assertEqual(instrument().corpus_differences(c, load_json(SIDE), ifaces(), th()["corpus"]["m1_sha256"]),
                         [])


# ---------------------------------------------------------------------------------------------- acquisition
class TestAcquisition(unittest.TestCase):
    def test_p1_the_legacy_registry_is_recovered_and_matches(self):
        """I69-P1, decided on the instrument's recomputation from the committed snapshot's raw logs, receipts and code
        (A6), and UNKNOWN when the anchor test (A7) fails: the registry's proxy has two Upgraded logs in the window;
        the first is its creation over I63's placeholder by the Rollup proxy's deployer (one AdminChanged from zero to
        it, no Initialized, no match); the second, before the cutover, sets the one implementation, which matches the
        registry's version V3 (v0.4.0..v0.6.1) under hardhat alone, logs Initialized(1) in its transaction, and holds
        OTHER_STAKING = the L2 staking predeploy and MESSENGER = the queue's MESSENGER word."""
        item(KEY, "I69-P1")
        t = th()["p1"]
        tl = recomputed()
        reg = tl["proxies"]["registry"]
        self.assertEqual(reg["address"], load_json(SIDE)["acquisition"]["proxies"]["registry"]["address"])
        ups = reg["upgrades"]
        self.assertEqual(len(ups), 2)
        u1, u2 = ups
        self.assertEqual(u1["decoded"]["contract_address"], reg["address"])
        self.assertEqual((u1["implementation"], u1["decoded"]["from"]), (t["placeholder"], t["deployer"]))
        self.assertEqual(u1["decoded"]["admin_changed"], [{"previous": ZERO, "new": t["deployer"]}])
        self.assertEqual((u1["decoded"]["initialized"], u1["matches"]), ([], []))
        self.assertLess(u1["block"], u2["block"])
        self.assertLess(u2["block"], t["cutover_block"])
        self.assertEqual(u2["matches"], [["V3", "hardhat"]])
        self.assertEqual(u2["decoded"]["initialized"], [1])
        self.assertEqual(u2["immutables"]["OTHER_STAKING"], [word(t["other_staking"])])
        self.assertEqual(len(u2["immutables"]["MESSENGER"]), 1)
        q = tl["proxies"]["queue"]["upgrades"][-1]
        self.assertEqual(u2["immutables"]["MESSENGER"], q["immutables"]["MESSENGER"])

    def test_p2_the_live_bundle_is_the_modelled_code(self):
        """I69-P2 (A6; UNKNOWN when the anchor test fails): the last implementation in the window of the queue's proxy
        matches the queue's head build under hardhat alone, with ROLLUP_CONTRACT the Rollup proxy; the messenger's proxy
        (the queue's MESSENGER word) last implementation matches the messenger's head build under hardhat alone; the
        Submitter's proxy last implementation matches the Submitter's head build under the deployed configuration
        alone; the whitelist the queue names matches the Whitelist's head build under hardhat (whose build equals
        foundry's), not under the deployed one."""
        item(KEY, "I69-P2")
        t = th()["p2"]
        tl = recomputed()
        side = load_json(SIDE)["acquisition"]["proxies"]
        self.assertEqual((tl["proxies"]["queue"]["address"], tl["proxies"]["submitter"]["address"]),
                         (side["queue"]["address"], side["submitter"]["address"]))
        q = tl["proxies"]["queue"]["upgrades"][-1]
        self.assertEqual(q["matches"], [["queue", "hardhat"]])
        self.assertEqual(q["immutables"]["ROLLUP_CONTRACT"], [word(t["rollup_proxy"])])
        msg = tl["proxies"]["messenger"]
        self.assertEqual(word(msg["address"]), q["immutables"]["MESSENGER"][0])
        self.assertEqual(msg["upgrades"][-1]["matches"], [["messenger", "hardhat"]])
        self.assertEqual(tl["proxies"]["submitter"]["upgrades"][-1]["matches"], [["submitter", "deployed"]])
        self.assertEqual(tl["whitelist"]["matches"], [["whitelist", "foundry"], ["whitelist", "hardhat"]])

    def test_the_second_read_agrees(self):
        """The anchor (A7): the instrument's second read from a host of rpc.second, committed after the fetch, agrees
        with the snapshot, the receipt files and the code files. When it does not, I69-P1 and I69-P2 are UNKNOWN."""
        need(SECOND)
        self.assertEqual(instrument().second_read_differences(ROOT), [])

    def test_history_is_the_basis(self):
        """Construction (A2): holon bundle history --check reproduces gen/M3/bundle/history/l1staking.json, whose refs,
        versions and edges are the basis's registry part."""
        code, out = holon_ok(["bundle", "history", "--check"])
        self.assertEqual(code, 0, out)
        h, b = need(HIST), need(BASIS)["registry"]
        for k in ("refs", "versions", "edges"):
            with self.subTest(field=k):
                self.assertEqual(h[k], b[k])

    def test_fetch_check_and_timeline_reproduce(self):
        """Construction (A3, A6): holon bundle fetch --check verifies the snapshot offline; holon bundle timeline --check
        reproduces the timeline, which equals the instrument's."""
        for step in ("fetch", "timeline"):
            code, out = holon_ok(["bundle", step, "--check"], timeout=1800)
            self.assertEqual(code, 0, f"{step}: {out}")
        self.assertEqual(need(TIMELINE), recomputed())


# ---------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    def test_r1_earlier_extractions_and_models_regenerate(self):
        """I69-R1 (fresh runs at HEAD; green at the prereg): the adopted Rollup document re-extracts byte for byte with
        its sidecar, holon coverage --milestone M2 --check passes, the typed and untyped M3 models of the adopted
        document regenerate byte for byte (the typed model's init as the committed one but for F40's code table, which
        holon.sorts.run3 adds and holon model does not), I20's M2 model (gen/M2/extracted/model.bend, layout.json and
        window_check.json, by holon.machine.write_model as gate-M2's G1 regenerates them) regenerates byte for byte, the
        pinned inputs keep their sha256, and gen/M3/coverage.json's Rollup entry is the prereg's."""
        item(KEY, "I69-R1")
        t = th()
        for rel, sha in t["inputs_sha256"].items():
            with self.subTest(input=rel):
                self.assertEqual(file_sha256(ROOT / rel), sha)
        code, out = holon_ok(["extract", "solidity", "--sidecar", "spec/M2/lib/extract_rollup.json", "--check"], 1800)
        self.assertEqual(code, 0, out)
        code, out = holon_ok(["coverage", "--milestone", "M2", "--check"], 1800)
        self.assertEqual(code, 0, out)
        for flag, sub, files in (([], "models", ("morph_rollup_extracted.bend", "morph_rollup.extracted.init.json")),
                                 (["--untyped"], "untyped/models", ("morph_rollup_extracted.bend",))):
            with tempfile.TemporaryDirectory(prefix="i69-r1-") as td:
                code, out = holon_ok(["model", "--milestone", "M3", *flag, "--out", td], 1800)
                self.assertEqual(code, 0, out)
                for f in files:
                    with self.subTest(model=f"{sub}/{f}"):
                        got, want = (Path(td) / f).read_bytes(), (ROOT / "gen" / "M3" / "sorts" / sub / f).read_bytes()
                        if f.endswith(".init.json"):
                            # F40 (5b369d4c): holon.sorts.run3 adds the deployment's code table, init["code"]
                            # (holon.sorts.envcode3.with_code); holon model writes the init without it
                            want_d = json.loads(want)
                            want_d.pop("code", None)
                            self.assertEqual(json.loads(got), want_d)
                        else:
                            self.assertEqual(got, want)
        with tempfile.TemporaryDirectory(prefix="i69-r1-m2-") as td:
            rc = holon_module("holon.machine").write_model(ROLLUP_DOC, Path(td), ROOT, check=False,
                                                           log=lambda *a: None)
            self.assertEqual(rc, 0)
            for f in ("model.bend", "layout.json", "window_check.json"):
                with self.subTest(m2=f):
                    self.assertEqual((Path(td) / f).read_bytes(), (ROOT / "gen" / "M2" / "extracted" / f).read_bytes())
        by = {d["document"]: d for d in need(COV3)["documents"]}
        self.assertEqual(hashlib.sha256(json.dumps(by[ROLLUP_DOC], sort_keys=True).encode()).hexdigest(),
                         t["rollup_coverage_entry_sha256"])

    def test_r2_own_commits_touch_nothing_forbidden(self):
        """I69-R2: at least one own commit adds gen/M3/bundle/bundle.json. No own commit changes a frozen root, laws/,
        spec/ (but lines of iteration I69 appended to spec/M3/amendments.jsonl), holon/rules/, a file under replay/
        outside replay/M3/bundle/, a file under gen/ outside gen/M3/bundle/ but gen/M3/coverage.json, whose entries at
        the commit's parent stay as they are (the commit only adds), or a file under results/ outside
        results/M3/bundle/ but the records directly under results/M1, results/M2 and results/T32, none of which it adds
        or deletes, each keeping its status and differing from its parent's version only in generator_sha256 and keys
        named seconds."""
        item(KEY, "I69-R2")
        commits = own_commits()
        self.assertTrue([c for c, ch in commits if ("A", "gen/M3/bundle/bundle.json") in ch],
                        "no own commit adds gen/M3/bundle/bundle.json")
        frozen = ("facts/", "laws/", "predictions/", "schemas/", "tests/", "bend/probes/", "AGENTS.md",
                  "tools/freeze.py", "docs/M0_SPEC.md", "docs/BEND_PRIMER.md", "FROZEN.sha256")
        never = frozen + ("spec/", "holon/rules/")
        rec = re.compile(r"^results/(M1|M2|T32)/L[^/]*\.json$")

        def secs(x):
            if isinstance(x, dict):
                return {k: secs(v) for k, v in x.items() if k != "seconds"}
            if isinstance(x, list):
                return [secs(v) for v in x]
            return x
        for c, ch in commits:
            for st, f in ch:
                with self.subTest(commit=c[:12], path=f):
                    if f == "spec/M3/amendments.jsonl" and st == "M":
                        old = git("show", f"{c}^:{f}")
                        new = git("show", f"{c}:{f}")
                        self.assertTrue(new.startswith(old), "amendments.jsonl changed, not appended")
                        for ln in new[len(old):].splitlines():
                            self.assertEqual(json.loads(ln).get("iteration"), KEY, "an appended line not I69's")
                        continue
                    self.assertFalse(f.startswith(never), "a forbidden path")
                    if f.startswith("replay/"):
                        self.assertTrue(f.startswith("replay/M3/bundle/"), "a replay file outside replay/M3/bundle/")
                    if f.startswith("results/") and not f.startswith("results/M3/bundle/"):
                        self.assertTrue(rec.match(f), "a results file but an M1, M2 or T32 record")
                        self.assertEqual(st, "M", "a record added or deleted")
                        new, old = secs(show(c, f)), secs(show(f"{c}^", f))
                        self.assertEqual(new.get("status"), old.get("status"))
                        self.assertLessEqual({k for k in set(new) | set(old) if new.get(k) != old.get(k)},
                                             {"generator_sha256"})
                    if f.startswith("gen/") and not f.startswith("gen/M3/bundle/"):
                        self.assertEqual((st, f), ("M", "gen/M3/coverage.json"), "a generated file outside gen/M3/bundle/")
                        new, old = show(c, f), show(f"{c}^", f)
                        olds = {d["document"]: d for d in old["documents"]}
                        news = {d["document"]: d for d in new["documents"]}
                        self.assertEqual({k: news.get(k) for k in olds}, olds)

    def test_r3_coverage_reproduces_and_the_audits_pass(self):
        """I69-R3 (part, run here): holon coverage --milestone M3 --check reproduces the committed report (G8's
        reproduction, over the four head documents after the build), and holon audit prereg exits 0 for M3 and M2. The
        rest of R3 is CI's on the build head, named in the report: gates M0, M1 and M2 in full; gate-M3-partial and
        gate-M3-G2 failing only on the base's items; tests-m3-catalog, the frozen suite and freeze-check passing."""
        item(KEY, "I69-R3")
        code, out = holon_ok(["coverage", "--milestone", "M3", "--check"], 1800)
        self.assertEqual(code, 0, out)
        for m in ("M3", "M2"):
            with self.subTest(audit=m):
                code, out = holon_ok(["audit", "prereg", "--milestone", m], 1800)
                self.assertEqual(code, 0, out)

    def test_r4_holon_is_generic_and_the_link_is_outside_every_closure(self):
        """I69-R4 (construction): holon/bundle/ exists; neither its files nor the lines I69's own commits add to any
        other file under holon/ name a member contract, a member-specific function, a proxy address, a host of the
        sidecar's rpc (url and second) or an I69 id, or import a tests module; no module of a generator closure
        (holon-ir/0.1-0.3, GEN3, GEN_FACT, GEN_UNDO, GEN_DISCH and I32's GEN_PROFILE; transitively) imports holon/bundle/."""
        item(KEY, "I69-R4")
        d = ROOT / "holon" / "bundle"
        self.assertTrue(d.is_dir(), "holon/bundle/ is missing")
        side = load_json(SIDE)
        names = {m["contract"] for m in side["members"] + side["extracted_only"]}
        names |= {"sendMessage", "relayMessage", "withdrawalRoots", "isSenderAllowed", "proveAndRelayMessage",
                  "replayMessage", "appendCrossDomainMessage", "verifyMerkleProof", "whitelistChecker", "MESSENGER",
                  "ROLLUP_CONTRACT", "OTHER_STAKING", "morph"}
        rpc = side["acquisition"]["rpc"]
        for url in [rpc["url"], *rpc["second"]]:
            host = url.split("//", 1)[-1].split("/", 1)[0]
            names |= {host, *(p for p in host.split(".") if len(p) > 3 and p not in ("mainnet", "gateway", "ethereum"))}
        addrs = {x["address"] for x in side["acquisition"]["proxies"].values() if x.get("address")}
        texts = {str(p.relative_to(ROOT)): p.read_text(encoding="utf-8") for p in sorted(d.rglob("*.py"))}
        for c, ch in own_commits():
            for st, f in ch:
                if f.startswith("holon/") and not f.startswith("holon/bundle/") and st != "D":
                    texts[f"{f}@{c[:12]}"] = "\n".join(added_lines(c, f))
        for where, text in sorted(texts.items()):
            with self.subTest(file=where):
                for n in sorted(names):
                    self.assertIsNone(re.search(rf"(?i)(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", text), n)
                for a in sorted(addrs):
                    self.assertNotIn(a[2:].lower(), text.lower())
                self.assertNotRegex(text, r"\bI69\b|\bI36a\b")
                self.assertNotRegex(text, r"(?m)^\s*(from|import)\s+tests(_m\d)?\b")
        records = holon_module("holon.records")
        closure = set()
        for v in ("holon-ir/0.1", "holon-ir/0.2", "holon-ir/0.3"):
            closure |= set(records.generator_files(v, ROOT))
        todo = list(holon_module("holon.sorts.run3").GEN3) + list(holon_module("holon.fact.run").GEN_FACT) \
            + list(holon_module("holon.undo.run").GEN_UNDO) + list(holon_module("holon.disch.run").GEN_DISCH)
        todo += list(holon_module("holon.profile").GEN_PROFILE)                # I32's
        while todo:
            f = todo.pop()
            if f in closure or not (ROOT / f).is_file():
                continue
            closure.add(f)
            if f.endswith(".py"):
                todo.extend(sorted(records._holon_imports(f, ROOT) - closure))
        self.assertEqual(sorted(f for f in closure if f.startswith("holon/bundle/")), [])


if __name__ == "__main__":
    unittest.main()
