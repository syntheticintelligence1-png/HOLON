"""I28: the laws half of BUILD_PLAN I28: versioned machines over the extracted deployment history, PAR-init (rule PAR's
sub-form init_chain, catalog holon-rules/1.6), O9, D4 as a generated gap record and G11V's in-flight sets; F12.5 only
under reading (a) of Question 64 (whitepaper Def 4.3 S_k/A_k and MIG, §5.1 initialization coherence, §10.1 deployment
history, §11.3 O9, §11.6 D4, App. A F12.5, §12.3 L21; BUILD_PLAN I28; docs/HUMAN_ANSWERS.md Q18 and Q19). This docstring
is the contract.

Scope. I63 (= I28a) extracted the history: 26 refs in 11 code versions with 10 MIG edges and their in-flight sets, and
the proxy's on-chain timeline (gen/M3/history/morph_rollup.json, results/M3/history/). I28 keeps its number for the laws
half, which reads I63's committed outputs and never writes them: one extracted document per deployed version and one
versioned machine (step_k, run_k and the migration steps) along the deployed path; a PAR producer of initialization
coherence over the versioned documents (sub-form init_chain, in a new catalog version); its O9 law, decided on the
machine and replayed on the real code; D4 and the reverse version transition as generated gap records (G1, G2 below say
why no law); and G11V's in-flight inhabitants.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl): tests_m3/_i28.py (rules V1-V4, V8's words and keys, PI1-PI5 and S1-S3 written out a second
time, independently of holon/, over I63's instrument tests_m3/_i63.py and I26's tests_m3/_i26.py, both fixed at their own
preregs); spec/M3/lib/versions.json (the sidecar: inputs, outputs, the model name, the proxy standard A-proxy, the
upgrade path's calls and reverting probes, the reinitializer arguments, the obligations the gap records stand for,
search budgets, replay settings; no outcome); spec/M3/lib/versions_basis.json (tests_m3/_i28.py::versions_basis_doc at
the prereg: V1-V4 over I63's outputs, PI1-PI5 over the adopted head document).

Inputs, read and never written: gen/M3/history/ and results/M3/history/ (I63's outcome paths: a commit writing one is an
I63 outcome commit, which I63-R2 forbids to touch laws/, holon/rules/ or any other gen/M3 and results/M3 path);
spec/M3/lib/history.json; spec/M2/lib/extract_rollup.json (the I19 sidecar whose contract, compiler settings and commit
interfaces every version's extraction reuses); spec/M2/facts/morph_rollup.extracted.json (the adopted head document, which
stays byte-identical, as does spec/M3/lib/derive_extracted.json); replay/M2/fragments.json and
gen/M3/sorts/models/morph_rollup.extracted.init.json (the I20 binding: its proxy admin, its harness and its deployment
calls; pinned by sha256 in the key).

Versions (V1-V4; the instrument's functions of the same names)
  V1 Path. The deployed path is the versions of the timeline's matched upgrades in upgrade order, consecutive repeats
     collapsed; every consecutive pair is a history edge and the path never goes back (else holon versions refuses, exit
     2). Versions in no match are never deployed; the timeline's coverage debt is the unmatched upgrades. Every matched
     upgrade is a deployment keyed by (version, immutable words): the words of its committed code at the immutable ranges
     of the matched build (I63 Finding 4: the redeploy of one version with other immutables is visible here).
  V2 Edges. The entry edge goes from the placeholder (the proxy's first implementation, which matches no version: I63-P1)
     to the path's first version and introduces that version's reinitializers; a MIG edge joins each consecutive pair of
     the path and is the history's edge between them (introduced reinitializers, layout diff, compatibility, in-flight
     set).
  V3 In-flight types: the in-flight entries of the path's MIG edges whose kind is retyped or reinterpreted (I63 H6).
  V4 Downgrades. Each MIG edge a -> b reversed is the downgrade b -> a, with I63's H5 diff of layout b to layout a and its
     H6 in-flight set; a reverse edge whose diff is incompatible is a downgrade gap {"id": "gap:M3:downgrade:<b>-><a>",
     "kind": "downgrade", "from", "to", "retyped", "overlap", "removed", "added", "obligation", "question", "status":
     "open"} (the last three from the sidecar's gaps.downgrade: tests_m3/_i28.py::gap_meta). The versioned machine has no
     reverse step, and no rule of the catalog states an obligation over one (a downgrade's native equivalence over
     in-flight types is NAT's, I29): the gap is the record, generated from the layouts, never hand-written.

The versioned documents and machine (V5-V9)
  V5 Extraction. `python -m holon versions extract [--check]` writes, for every path version, a generated extraction
     sidecar gen/M3/versions/sidecars/<version>.json (spec/M2/lib/extract_rollup.json with its target commit, the
     version's "commit" in the history, and its output replaced) and gen/M3/versions/documents/<version>.json, the
     transitions document holon extract solidity's walk extracts from that commit's tree (materialized from git objects,
     as I63 does; the pinned solc and dependency tree); then gen/M3/versions/morph_rollup.versions.json:
     {"versions_version": "holon-versions/0.1", "history": {"path", "sha256"}, "timeline": {"path", "sha256"},
     "sidecar": {"path", "sha256"}, "contract", "path", "never_deployed", "unmatched", "deployments", "entry", "edges",
     "in_flight_types", "reverse", "downgrade_gaps", "documents": {version: {"path", "sha256", "commit": the history's
     commit of the version}}, "debt": [{"version", "reason"}]}, its V1-V4 fields equal to the instrument's (the basis's).
     A version whose extraction fails is debt with its error, never smoothed, and has no document. Exit 0 written; 1
     --check differs; 2 refused (a moved input, a path rule broken); 3 an extraction error outside the debt rule.
     Byte-identical across runs; no timestamps, no absolute paths.
  V6 The model. `python -m holon versions model [--check]` writes gen/M3/versions/models/: morph_rollup.versions.bend
     (which may import one module per version from the same directory) and morph_rollup.versions.init.json: every path
     version's document compiled by holon.sorts.model3's compiler as it compiles the adopted document (its word model,
     storage representation and hash parameters, whatever they are when the model is built: a later key may change the
     storage representation, and the versioned model follows it; run_<a>/step_<a>) without its sort section (the frozen
     assignment covers the adopted document only), under per-version names: for each version k its action type, step_k
     (one step of an action of k) and run_k (a trace of actions of k). The versioned layer, by these names: the state
     type VSt (the version and one storage for every version: the proxy keeps all storage across an upgrade, so every
     location the old code wrote reads the same word under the new code's layout); the step type VStep, with one
     constructor per action of each version, C_<version>_<action> (its inputs, then its caller as a word, then its
     environment), one per MIG edge, U_<from>_<to>, and U_entry for the entry edge (a migration's call and arguments, if
     any: A-proxy, sidecar "proxy": the admin's upgradeTo, or upgradeToAndCall with one of the reinitializers the edge
     introduces, all storage kept, the call run at the new version with the admin as caller, the whole step reverting
     when the call reverts); vr0() (VR0: the placeholder's state at the proxy's creation, every storage location reading
     zero but the EIP-1967 admin slot, which holds the binding's proxy admin); vstep(x, s, ..) (the state after step x
     from s: the migration along the next edge of the path, the entry edge included, or an action of the current version
     by a caller other than the admin; s itself when the step reverts) and vok(x, s, ..) (whether it succeeds); vrun;
     the reachability type VReach (VR0{e: s == vr0()} | VRStep{x, p, r: VReach at p, e: s == vstep(x, p, ..)}, the shape
     of I30's Reach); and vread(s, b, o, p, ..), the word at the storage location of layout coordinate (b: the family's
     base slot, o: the offset in the top-level variable, p: the mapping steps, a list of VP{k: the key word, o: the slot
     offset inside the value}), in the model's storage representation ("..": the model's table parameters, if any).
     Every I28 claim and output about storage is stated in real slots (EVM storage addresses, as the real chain and the
     instrument compute them) or layout coordinates, never in the model's encoding of a location; the model's encoding
     maps to real slots wherever an output compares with the real chain. holon/sorts/ and gen/M3/sorts/ (I30's frozen
     model and its runner closure GEN3) are not changed by I28.
     Traces. A trace is a list of steps from VR0, each {"label", "kind", "version", "caller", "calldata", "ok"}: a
     migration step has kind "migrate", label "entry" (the entry edge) or "<a>-><b>", version the new version, the
     proxy admin as caller, "call" the reinitializer it calls (null for upgradeTo) and that call's calldata ("0x" for
     none); an action step has kind "call", label and "action" the action's name, version the current version, its
     caller and its calldata; "ok" says whether the step succeeds.
  V7 Refinement of the upgrade path (P2). The upgrade path is the sidecar's (upgrade_path), 14 steps: the entry edge by
     upgradeTo; the deployment record's calls 0 and 3 (initialize and importGenesisBatch, by the binding's harness); the
     same two calls again, each of which reverts; the MIG edges of the path before the last, by upgradeToAndCall with
     the reinitializer an edge introduces and the sidecar's arguments (initialize2 with the genesis post-state root,
     initialize3 with the recorded rollup delay), or by upgradeTo; the last edge with the sidecar's reverting arguments
     (initialize4 with the cutover index 1: the whole step reverts and the version stays the edge's source); and the
     last edge with initialize4's arguments (the binding's submitter stand-in, which has code, and the cutover index 0).
     In the versioned model and, through the versioned harness (V9), on the real code of every path version: every
     step's status is the stated one in both, and so is its revert data: none ("0x") after a successful step and, on
     both sides of each reverting step, the Error(string) encoding of the reason the key names
     (thresholds.upgrade_path_reverts: the initializer guard's "Initializable: contract is already initialized" at the
     second initialize, "genesis batch imported" at the second importGenesisBatch and "cutover batch mismatch" at the
     wrong cutover); after each step, at every real slot in the union of the model's writes and the real step's writes
     (the proxy's EIP-1967 slots aside), the model's 32-byte word equals the real chain's; a reverting step writes
     nothing on either side, and every successful call (an action, or a migration with a call) writes at least one slot;
     and the Initialized version (Initializable._initialized, the low byte of real slot 0) is 1 after the first
     initialize, 2 after the edge into V4, 3 after the edge into V7 and 4 after the successful edge into V11.
  V8 In-flight inhabitants (G11V). `python -m holon versions inhabit [--check]` writes, for every MIG edge a -> b of the
     path, gen/M3/versions/inflight/<a>_<b>/INHABIT.bend, and results/M3/versions/inflight.json {"inflight_version":
     "holon-inflight/0.1", "edges": [{"edge": "<a>-><b>", "trace": [step], "key", "legacy": [{"entry", "reads", "slot",
     "base", "offset", "path", "word"}], "bend": {"exit_code", "marker"}, "verdict": {"exit_code", "marker"} | null}]}
     in path order. The trace runs from VR0 and its last two steps are a successful call of a successor site's action
     (PI1) of version a (a commit: the batch it commits is in flight at the upgrade) and the successful migration along
     a -> b, by upgradeToAndCall with the edge's introduced reinitializer when it has one, called with the sidecar's
     inflight_arguments (initialize4's expected cutover index is the key). "key" is the batch index the last commit
     writes (tests_m3/_i28.py::commit_key of its calldata). "legacy" lists the words tests_m3/_i28.py::inflight_words
     names for the edge at the key (every word of an in-flight entry of kind retyped or reinterpreted that the change
     touches; "slot" the real slot, (base, offset, path) its layout coordinate), each with the word the model's state
     holds there before the migration step, each nonzero. INHABIT.bend imports the versioned model as VM, declares no
     law, holds no escape hatch, and holds these definitions, each with its header on one line, for the trace's n steps
     and the edge's m legacy words (a word literal is VM.w_of_limbs([<its 8 limbs>]), or VM.w0() for zero): s_0 .. s_n
     of type VM.VSt (concrete states; s_0's body is exactly VM.vr0()); x_1 .. x_n of type VM.VStep (the steps: x_i's
     body is trace step i's constructor, VM.U_entry, VM.U_<a>_<b> or VM.C_<version>_<action>, applied to literal values
     whose leaf literals, in order, begin with the step's arguments, which are its calldata decoded by the parameter
     types of the function its selector names in its version's document (the action, or the migration's reinitializer;
     none for upgradeTo, whose calldata is "0x"), in parameter order and a struct's fields in declaration order, a value
     type as the word literal of its 32-byte encoding, bytes or a string as the list of its byte literals (Nil{} when
     empty), an array as its elements (tests_m3/_i28.py::abi_leaves); for an action step the next leaf literal after
     them is the word literal of the step's caller; every migration step's caller is the binding's proxy admin); r_1 ..
     r_n, each `def r_<i>() -> {s_<i>() == VM.vstep(x_<i>(), s_<i-1>(), ..) : VM.VSt}:` proved by `{==}`; ok_<n-1> and
     ok_<n>, each `def ok_<i>() -> {True{} == VM.vok(x_<i>(), s_<i-1>(), ..) : Bool}:` proved by `{==}`; lg_1 .. lg_m,
     each `def lg_<j>() -> {VM.<word> == VM.vread(s_<n-1>(), VM.<b>, VM.<o>, <p>, ..) : VM.W}:` proved by `{==}`, with
     legacy word j's word and coordinate as word literals (p as [VM.VP{VM.<k>, VM.<o>}, ..], Nil{} for no mapping step);
     and reach, of type VM.VReach<.., s_<n>()>, whose body is VM.VRStep{x_<n>(), s_<n-1>(), <the body for the first n -
     1 steps>, r_<n>()}, VM.VR0{{==}} for no step (tests_m3/test_versions.py::canonical_reach). Bend accepts it with ALL
     PROOFS CHECK and no open goal, and so does BendTT (--verdict) whenever the verdict is enabled
     (holon.bend.verdict_enabled). `holon gate --milestone M3 --checks G11V` gains the clause "every MIG edge of the
     deployed path has an in-flight inhabitant whose INHABIT.bend has V8's shape for its trace and legacy words and is
     accepted (by BendTT too when the verdict is enabled)" and reports it in its detail ("in-flight: <n> of <n> edges
     inhabited"), whatever G11V's other items say; I28 changes none of them.
  V9 Replay. `python -m holon versions replay [--check]` writes replay/M3/versions/report.json: {"replay_version":
     "holon-versions-replay/0.1", "toolchain": the pins of config/holon.json replay, "implementations": {version:
     {"commit", "config", "code_sha256"}}, "runs": [{"name", "trace", "steps": [{"model", "real", "revert": {"model",
     "real"}, "slots": [{"slot", "model", "real"}]}], "passed"}]}: the upgrade path (V7, name "upgrade_path"), every
     REFUTED PAR-init witness (name its law id) and the cutover's inhabitant (P6, name "inflight:<a>-><b>"), each run on
     the real code through the versioned harness: an OpenZeppelin 4.9.3 TransparentUpgradeableProxy of the pinned
     dependency tree over a placeholder contract, the binding's admin, every version's implementation built from its
     commit with the pinned toolchain under its matched configuration (sidecar replay.configurations) and constructed
     with the binding's constructor argument, the binding's stand-ins (and, for a legacy version's external calls, a
     labelled stand-in answering each call as the trace's environment does: Q12's legacy staking contract is I36's),
     each migration step the admin's upgradeTo or upgradeToAndCall, each other step a call by its caller. Per step: the
     model's and the real status ("ok" or "revert"); "revert", the model's and the real revert data as hex ("0x" when
     the step succeeds; a migration step's is its call's, which the proxy passes on); and "slots" (sidecar
     replay.writes): one entry per real slot in the union of the real slots the model's step writes and those whose word
     the real step changes (the harness's state diff), the proxy's EIP-1967 slots aside, with the model's and the real
     chain's full 32-byte word after the step. An inhabitant's run also carries (sidecar replay.inflight_reads)
     "legacy": [{"reads", "slot", "real"}], each legacy word read on the real chain before the migration step, and
     "after": [{"entry", "getter", "args", "real": [word]}], each retyped or reinterpreted entry's public getter called
     on the real chain after it (the trace's key for a mapping), its result as ABI words. A run passes when every step's
     statuses, revert data and words agree. A disagreement is reported, never smoothed. G6 binds every REFUTED PAR-init
     record to a passed run of this report (its witness's sha256).

PAR-init (PI1-PI6; whitepaper §5.1 initialization coherence; §11.3 O9)
  PI1 Chains. Over a transitions document, a commitment family F (I26 F1/F2) has root sites: commitment sites in an
      action with no authenticating guard reach of F, whose committed value hashes input bytes (["keccak256" | "sha256",
      X], X no memory region); and successor sites: commitment sites in an action with an authenticating guard reach of F
      at key k over input bytes P (the parent; ["==", ["map", ["storage", F], k], [hash, P]]), whose committed value
      hashes a memory region (the child).
  PI2 Cells. A cell of a region is an mstore at a literal offset o whose value is ["<<", V, s], s a literal; the cell's
      read from input bytes X is [">>", ["word", X, o], s].
  PI3 Chained pairs. (o, o', s) is a chained pair of F when, in every successor site's region, after folding additions
      of the literal 0, the cell at o is ["<<", ["+", R, Y], s] (or ["+", Y, R]), R the parent's read of the cell (o, s),
      and the cell at o' != o is ["<<", Y, s]: along every chain of successor writes, cell o is the running sum of cell
      o' (App. B's queue cursor P = total(h)). A cell chained with a literal step (an index) gives no pair.
  PI4 Basis and law. One basis element per (F, root site action, chained pair) of any path version's document. Its law:
      rule PAR, subform "init_chain", id L_pinit_<contract>_<root action>_<F>_<o>_<o'>, holon-ir/0.3 {"ir_version",
      "law_id", "milestone": "M3", "rule": "PAR", "subform": "init_chain", "rule_catalog_version", "facts":
      "gen/M3/versions/morph_rollup.versions.json", "facts_sha256", "notes", "statement": {"binders": [s: Reach, a: Act,
      e: Env, then one Fn<Bytes,Word> binder per hash function the documents apply, named as I30's laws name them],
      "assume": [], "claim": {"eq": [{"init": "<model>:chain:<F>:<o>:<o'>", "on": {"var": "a"}, "from": {"var": "s"},
      "env": {"var": "e"}}, {"bool": true}]}, "scope": {"kind": "unbounded"}}}, no "evidence", no "predicted". The init
      term (additive in spec/schemas/law_ir_0_3.schema.json, docs/adoption/Q4/schemas/ following it byte for byte; its
      statement ref init:<id> in holon.gen.refs hashes the basis element and the per-version documents it reads, by
      sha256, recomputed from the versioned document) is the Bool: when a is a call of the root site's action of s's
      version whose step succeeds at s with environment e, the cell (o, s) of the bytes it hashes equals their cell
      (o', s) (the running sum over a chain of one header equals its own increment), and true otherwise. The chain's
      first value is set by the root site, which no successor recomputes: initialization coherence (§5.1) requires it to
      be what the recurrence gives the first header. init_chain is not I24's sub-form init (rule P7: E3 equations over a
      holon-facts/0.2 machine's initial state s0), which has no instance over a transitions document (I24 G1).
  PI5 Link gaps. For every chained pair and every interface I of an external call (calls[i], a "call" or "callok" term
      "<I>.<f>") of an action that authenticates input bytes X against F, whose arguments carry X's read of the chained
      cell: a link gap {"id": "gap:M3:link:<F>:<o>:<I>", "kind": "link", "family", "cell", "incr", "interface", "sites":
      {version: [{"action", "at", "fn"}]}, "obligation", "question", "status": "open"} (the last three from the sidecar's
      gaps.link: D4, Q63). The cursor is the index the callee checks against its own registers (whitepaper App. B: the
      queue's L and P), which are in no adopted M3 document, so the invariant tying the cursor to them (§11.6 D4: P =
      total(h_LFI) <= T <= L) has no statement over this machine; generated, never hand-written.
  PI6 Decision. `holon run --milestone M3 --laws <id>` decides a PAR-init law over the versioned model: the search
      (sidecar search.par_init: path versions in path order, traces by length up to max_trace; action steps by the
      deployment record's recorded callers; the root input is the binding's recorded call of the root site's action with
      the chained cell's bytes set to the increment cell's value plus one) proposes witnesses; a witness is a trace from
      VR0 whose last step is a successful root step whose input bytes have cell o != cell o'
      (tests_m3/_i28.py::root_witness_problems), its counter-law checked by Bend (AGENTS rule 6), and by BendTT whenever
      the verdict is enabled. With neither a witness nor a proof the law is UNKNOWN with what was tried. The record has
      the M3 record fields (v1 and v2 valid), "witness": {"trace": [step], "root": {"version", "action", "caller",
      "calldata"}} (root: the trace's last step), artifacts laws, proof and model (gen/M3/laws/<id>/LAWS.bend,
      gen/M3/proofs/<id>/PROOF.bend, which imports that LAWS.bend as Laws: holon.mpipeline.law_import_problem, and the
      versioned model), and no lean4 entry (no Lean emitter reads the versioned document: holon.lean._attempted, as for
      I31's DISCH and I26's FACT laws). holon refute's concretization and final filter give it a concretization and a
      bin (I40), from V9's run.
  Analysis. `python -m holon versions analyze [--check] [--facts DOC ..] [--out PATH]` writes gen/M3/versions/par_init.json,
      tests_m3/_i28.py::analysis_doc over the versioned documents and V4's gaps ({"analysis_version":
      "holon-par-init/0.1", "versions", "basis", "link_gaps", "downgrade_gaps"}); with --facts, over the given transitions
      documents, one version each, named V0, V1, .. in argument order (S1-S3).

Catalog and derive
  holon/rules/__init__.py: CATALOGS gains "holon-rules/1.6": every rule and producer of holon-rules/1.5 (the same
  objects), and rule PAR gains the sub-form "init_chain" (holon/rules/par_init.py: PRODUCERS == {"init_chain": ..}) beside
  I24's ten; no other rule or sub-form changes. I28's catalog is the lowest catalog version holding PAR/init_chain;
  every later M3 catalog keeps its producer, the same object. The law's (rule, subform) is its catalog entry, so
  holon.statement_diff's catalog_rederivation check finds its producer in a later catalog. I24's ten sub-forms run per
  codec document as before (rule P11's order) and DERIVATION.json's I24 keys (par_basis, cycle_rank, uncovered, links)
  do not change; init_chain takes the typed context and the versioned document, and its basis elements are its laws'
  entries ({"law_id", "rule": "PAR", "subform": "init_chain", "facts", "basis"}) in DERIVATION.json "laws".
  catalog_version("M3") is holon-rules/1.6 (and every later M<k>); M2's and the test milestones' catalogs are unchanged.
  If another key holds holon-rules/1.6 at I28's merge, I28 takes the next free version and whoever merges second
  regenerates (the agreement of 2026-10-21). The producer reads its inputs through its own list (DERIVATION.json lists
  them; gen/M3/sorts/obstructions.json does not change). Re-deriving M3 changes every earlier M3 law only in
  rule_catalog_version, each change logged as a catalog_rederivation line of laws/STATEMENT_DIFF.jsonl, as I26 did.

Sensitivity (S1-S3: tests_m3/_i28.py::planted over the adopted head document; holon versions analyze --facts)
  S1 renamed: the contract, the root action and the commitment family renamed give the renamed chains, basis and law id.
  S2 no_chain: every successor site's chained cell stepping by the literal 1 gives no pair, no basis and no link gap.
  S3 no_root: without the root site's action, no family has a chain: no basis.

Gaps, stated before the build
  G1 D4. Its registers P and L are IL1MessageQueue's (spec/M2/lib/window_rollup.json marks qpend and qlen external), which
     no adopted M3 document extracts; PI5's link gap records it, and D4 moves to the key that links the queue (I36,
     Question Q63). D4 also needs premises the code does not enforce: initialization coherence (whose PAR-init law I28
     predicts REFUTED: O9) and a queue-length bound L < 2^64, since the commit adds the batch's count to the total
     unchecked and the header stores the total in 8 bytes (BatchHeaderCodecV0.storeTotalL1MessagePopped), so a total
     carried past 2^64 - 1 is stored wrapped, which breaks P <= T while T <= L can still hold. The key that states D4
     names both as premises.
  G2 The downgrade gap. V4's downgrade gaps stand for F12.5 only under reading (a) of Question 64 (a reverse version
     transition of the implementation). Under reading (b), a batch header's version going down along a chain of commits
     (at V11 _commitBatchWithBatchData checks only version <= 2), I28 states nothing about F12.5 and the gap is no
     evidence about it. The gap is a construction check, not a prediction.
  G3 Coverage. The unmatched upgrades (the placeholder, and block 21007191's untagged build without the genesis guard, I63
     Finding 3) are no version of the machine; that build's re-import of the genesis batch is outside it. Observation,
     outside I28's laws: at V3, whose importGenesisBatch lacks the index check that V4..V11 have, a genesis header with
     index k != 0 writes finalizedStateRoots[k] and leaves finalizedStateRoots[0] zero, so the guard admits a second
     import.

Own commits and the build branch
  R is the oldest commit reachable from HEAD that adds docs/iterations/I28.md, and M, the build's merge into the lead, is
  the oldest merge commit of `git rev-list --ancestry-path --merges --topo-order --reverse R..HEAD` whose second parent
  reaches R, whose first parent does not, and whose first parent's first-parent chain (`git rev-list --first-parent
  M^1`) does not hold the prereg commit. M is the same commit on the lead and on every branch that merges the lead after
  it: such a branch's own merge of the lead also brings R in by its second parent, but M is its ancestor; and a merge
  inside the build branch, whose first parent is the build branch's own line, is never M. I28's own commits are the
  non-merge commits of `git log --first-parent M^2 ^M^1 ^<prereg>`. Before M exists, when the prereg commit is on HEAD's
  first-parent chain (the build branch starts at the prereg commit, as I63's and I32's builds did), they are the
  non-merge commits of `git log --first-parent <prereg>..HEAD`; otherwise there are none (a line that has merged the
  prereg but not the build). Once docs/iterations/I28.md exists at HEAD, the list comes from one of the first two cases
  and is not empty. Three commit rules keep the cases apart and the list whole on every branch. The prereg commit
  reaches the lead only on the second-parent side of a merge commit (no direct push, no fast-forward, no squash or
  rebase merge), so it lies on no other branch's first-parent chain. The build branch reaches the lead only through its
  own merge commit M, as every key's build so far, and no other line merges it before M. The build branch merges only
  the lead, never a side branch, so every I28 commit lies on its first-parent line.

Shared files, changed only so (not outcome paths): laws/M3/ (rule_catalog_version, REGISTRY.json, DERIVATION.json);
laws/STATEMENT_DIFF.jsonl (catalog_rederivation lines); spec/bindings/M3.json and spec/bindings/changes.jsonl (every M3
law rebound, the new law bound: G2); the PAR, typed SORT, DISCH and FACT records, whose statement hashes the catalog
moves (re-made, statuses unchanged, as I26 re-made the first three under holon-rules/1.5; the 8 UNDO records, stale
since I31's bump, as I26 left them or re-made likewise), with I43's order for the PAR records (run, holon lean
--milestone M3, run: gen/M3/lean/'s report moves in statement hashes only); results/M1/ and results/M2/
(generator_sha256 and keys named seconds only: I28 edits files of the holon-ir/0.2 and 0.3 closures, never the six of
holon-ir/0.1, so no M0 record changes); results/T32/ (`holon profile --milestone T32`, in a commit of its own: the five
records of results/T32 in generator_sha256 and keys named seconds alone, since I28's code is also in I32's generator
closure, holon.profile.generator_files, which holds holon/rules/; laws/T32, gen/T32, results/T32/summary.json and
gen/M3/disch/classification.json stay byte-identical; without it I32's C1, which compares a fresh run's records with the
committed ones up to seconds, would fail on generator_sha256);
results/M3/metrics.json and summary.json; gen/M3/evidence.json (the versioned document covered with anchors, as I20's
adopted documents, so that GEVID covers the new law); spec/schemas/law_ir_0_3.schema.json and docs/adoption/Q4/ (the
init term: the schemas re-copied and the README's row, as I26 did for the fact term); I40's outputs for the new record
(holon refute: concretization, final bin); spec/M3/lib/lean_promoted.json only in a commit that changes nothing else
(I43's disposition of its review's Major 1: whoever re-makes records brings R1's baselines for exactly those records up
to date; or the human's answer to I26's Question 5); results/casestudy_coverage.json and docs/CASESTUDY.md when
tools/casestudy.py's output moves (where the downgrade gap is not F12.5's coverage: G2).

Commit rules (each an earlier key's test, checked from git): no I28 commit writes gen/M3/history/ or results/M3/history/
(I63-R2); a commit that writes an I26 or I31 outcome path (laws/M3/L_fact_* or L_disch_*, their records, LAWS.bend and
PROOF.bend files, gen/M3/fact/, gen/M3/disch/: the re-derivation and the re-made records do) touches nothing under
spec/M1/, spec/M2/facts/, spec/M2/lib/, laws/M0-M2, gen/M0-M2, results/M0-M2, replay/M1, replay/M2, gen/M3/sorts/ or a
frozen root (I26-R1, I31-R2), so the M1 and M2 records are regenerated in a commit of their own, and so are the T32
records; a commit that writes an I40 outcome path adds and deletes no record and changes a record only in filter_bin,
concretization, generator_sha256 and seconds (I40-R2), so I28's record is added before its filter commit; nothing under
gen/M3/sorts/, gen/M3/theory/ (I43-R8), laws/T32/, gen/T32/, spec/M1/, spec/M2/ or results/M0/ changes; and no module
of the holon-ir/0.1-0.3 closures or of the typed, DISCH, UNDO and FACT runners' closures comes to import, directly or
not, one of I32's six holon files (holon/__main__.py, holon/profile.py, holon/gen/profile.py,
holon/rules/disch_profile.py, holon/analysis/abstraction.py, holon/js/profile.mjs), since I32-R2 computes those closures
at HEAD (I66's verification, T4): holon/rules/__init__.py, in the 0.2 and 0.3 closures, gains the import of
holon/rules/par_init.py, which imports none of the six, directly or not, and the holon versions commands enter through
holon/__main__.py, which no closure module imports.

Re-make. At I28's end (M^2, with M as in 'Own commits and the build branch'; HEAD before M exists), every record
directly under results/M1, results/M2 and results/T32 carries a generator_sha256 other than at the prereg, one value
per milestone (holon run re-made the M1 and M2 records and holon profile the T32 records with I28's code), and laws/T32,
gen/T32 and results/T32/summary.json are the prereg's.

Earlier tests, amended at this prereg (spec/M3/amendments.jsonl), each narrowed only by what I28 adds:
  - I24, tests_m3/test_derive_par.py: _Morph.derived (and so TestDeriveM3.derived and TestPredictedMorph.derived) and
    TestDeriveM3.test_derivation_follows_the_rules leave out exactly the PAR laws and entries of sub-form init_chain
    (I28's law over the versioned document, which I24's checks never covered); TestRegistry.test_catalogs requires M3's
    catalog to keep holon-rules/1.1's PAR producers as the same objects and admits init_chain, and only it, beside them;
  - I24, tests_m3/test_par_outcomes.py: par_records and TestM3Construction.test_every_m3_law_has_a_valid_record leave out
    exactly the laws and records of sub-form init_chain;
  - I25, tests_m3/test_par_lossy.py: TestPreregInstruments.test_i25_adds_no_law_and_no_catalog requires M3's catalog to
    hold I24's PAR producers as the same objects and admits init_chain, and only it, beside them.
  At the prereg each amended test checks what it checked before. No other earlier test is amended: one that fails on
  I28's outcomes is a miss, reported. I32-R2 (tests_m3/test_disch_profile.py::TestRegressions.
  test_r2_no_closure_and_no_earlier_output_changes), which diffed the I32 prereg against HEAD and so counted every later
  key's closure edits and outputs as I32's, is re-scoped to I32's own commits by I66's prereg (PR #46, on I28's base
  a0bfc521); I28 does not amend it.

Commands
  python -m holon versions extract|model|analyze|inhabit|replay [--check]
  python -m holon derive --milestone M3                (catalog holon-rules/1.6: the PAR-init law)
  python -m holon run --milestone M3 --laws <id>       (PI6)
  python -m holon gate --milestone M3 --checks G11V    (V8's clause)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import tests_m3._i28 as I
from tests_m3._m3 import (ROOT, copy_repo, file_sha256, holon_module, item, laws, load_json, predictions, run_bend,
                          run_holon, validate)

M3 = "M3"
KEY = "I28"
REPORT = "docs/iterations/I28.md"
SIDECAR = ROOT / "spec" / "M3" / "lib" / "versions.json"
BASIS = ROOT / "spec" / "M3" / "lib" / "versions_basis.json"
DEPLOYMENT = "gen/M3/sorts/models/morph_rollup.extracted.init.json"
VERSIONS_DOC = "gen/M3/versions/morph_rollup.versions.json"
ANALYSIS = "gen/M3/versions/par_init.json"
MODELS = "gen/M3/versions/models"
MODEL = f"{MODELS}/morph_rollup.versions.bend"
INFLIGHT = "results/M3/versions/inflight.json"
REPLAY = "replay/M3/versions/report.json"
IR03 = ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json"
V2SCHEMA = ROOT / "spec" / "schemas" / "result_record_v2.schema.json"
V1SCHEMA = ROOT / "schemas" / "result_record.schema.json"
LAW = "L_pinit_Rollup_importGenesisBatch_committedBatches_17_9"
INIT_ID = "morph_rollup.versions:chain:committedBatches:17:9"
LINK_GAP = "gap:M3:link:committedBatches:17:IL1MessageQueue"
DOWNGRADE_GAP = "gap:M3:downgrade:V11->V10"
SUBFORM = "init_chain"
PATH = ["V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10", "V11"]
OLD = PATH[:-1]   # the versions whose code differs from the adopted head document's (P1, P4)
# P1, read at the prereg from each path version's Rollup.sol at its commit (functions that write committedBatches with a
# header built from an authenticated parent): the successor sites' actions, per version
SUCCESSORS = {"V3": ["commitBatch"], "V4": ["commitBatch"], "V5": ["commitBatch"], "V6": ["commitBatch"],
              "V7": ["commitBatch", "commitBatchWithProof"], "V8": ["commitBatch", "commitBatchWithProof"],
              "V9": ["commitBatch", "commitBatchWithProof", "commitState"],
              "V10": ["commitBatch", "commitBatchWithProof", "commitState"],
              "V11": ["commitBatch", "commitBatchWithProof", "commitState"]}
# V7: the upgrade path's labels and statuses (14 steps), and the Initialized version after the steps that set it
UPGRADE_LABELS = (["entry", "initialize", "importGenesisBatch", "initialize", "importGenesisBatch"]
                  + [f"{a}->{b}" for a, b in zip(PATH[:-1], PATH[1:-1])] + ["V10->V11", "V10->V11"])
UPGRADE_STATUS = ["ok"] * 3 + ["revert"] * 2 + ["ok"] * 7 + ["revert", "ok"]
INITIALIZED = {1: 1, 5: 2, 8: 3, 13: 4}   # step index (0-based) -> _initialized after it
# V7: the reason each reverting step's revert data carries (Error(string)), by step index (0-based); source reads at the
# prereg: OpenZeppelin 4.9.3's initializer guard in the pinned tree, V3's importGenesisBatch (v0.4.0 Rollup.sol:181) and
# V11's initialize4 (Rollup.sol:212, lastCommittedBatchIndex 0 against the expected 1)
UPGRADE_REVERTS = {3: "Initializable: contract is already initialized", 4: "genesis batch imported",
                   12: "cutover batch mismatch"}
SUCCESSFUL_CALLS = {1, 2, 5, 8, 13}         # the successful steps that run a call (V7: each writes a slot)
EIP1967 = {int("0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103", 16),
           int("0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc", 16)}
# the keys of a transitions document V11's extraction shares with the adopted head document
SAME_AS_HEAD = ("actions", "assumptions", "constants", "contract", "inherited_storage", "storage")
ESCAPES = re.compile(r"\?[A-Za-z_]\w*|\?TODO|@unsafe|\bdef\s+\w+\?\s*\(|import\s+\"[^\"]*\.c\"")
LOW160 = (1 << 160) - 1
CATALOG_RE = re.compile(r"^holon-rules/1\.(\d+)$")


# ---------------------------------------------------------------------------------------------- helpers
def need(rel: str) -> Path:
    p = ROOT / rel
    if not p.exists():
        raise AssertionError(f"{rel} is missing (I28 builds it)")
    return p


def git(*args, cwd: Path | None = None) -> str:
    p = subprocess.run(["git", "-C", str(cwd or ROOT), "-c", "core.quotepath=false", *args], capture_output=True,
                       text=True, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def is_ancestor(a: str, b: str) -> bool:
    """Whether commit a is b or an ancestor of b."""
    p = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", a, b], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if p.returncode not in (0, 1):
        raise AssertionError(f"git merge-base --is-ancestor {a} {b}: {p.stderr.strip()}")
    return p.returncode == 0


def prereg_commit() -> str:
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I28 (the audit's C_K)."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(doc, dict) and KEY in (doc.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I28")


def report_commit(report: str) -> str | None:
    """R: the oldest commit reachable from HEAD that adds `report`, or None."""
    cs = git("log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--", report).split()
    return cs[0] if cs else None


def build_merge(report: str) -> str | None:
    """M (the contract's 'Own commits and the build branch'): the oldest merge commit on the ancestry path from R (the
    commit adding `report`) to HEAD whose second parent reaches R, whose first parent does not, and whose first parent's
    first-parent chain does not hold the prereg commit; or None. It is the build's merge into the lead, on the lead and
    on every branch that merges the lead later (such a branch's own merge of the lead also brings R in by its second
    parent, but M is its ancestor); a merge inside the build branch, whose first parent is the build branch's own line,
    is never M."""
    r = report_commit(report)
    if r is None:
        return None
    c = None
    for m in git("rev-list", "--ancestry-path", "--merges", "--topo-order", "--reverse", f"{r}..HEAD").split():
        if is_ancestor(r, f"{m}^2") and not is_ancestor(r, f"{m}^1"):
            c = c or prereg_commit()
            if c not in git("rev-list", "--first-parent", f"{m}^1").split():
                return m
    return None


def end_commit() -> str:
    """I28's end: M's second parent (the build branch's last commit), else HEAD."""
    m = build_merge(REPORT)
    return git("rev-parse", f"{m}^2" if m else "HEAD").strip()


def own_commits() -> list:
    """I28's own commits (the contract's 'Own commits and the build branch'), oldest first, each with the paths it changes
    against its parent."""
    c = prereg_commit()
    m = build_merge(REPORT)
    if m:
        rng = [f"{m}^2", f"^{m}^1", f"^{c}"]
    elif c in git("rev-list", "--first-parent", "HEAD").split():
        rng = [f"{c}..HEAD"]
    else:
        if (ROOT / REPORT).exists():
            raise AssertionError(f"{REPORT} exists, but no merge on the ancestry path from the commit adding it to HEAD "
                                 "brings it in by its second parent, and the prereg commit is not on HEAD's first-parent "
                                 "chain: the build branch must start at the prereg commit")
        return []
    out, cur = [], None
    for ln in git("log", "--first-parent", "--no-merges", "--no-renames", "--reverse", "--format=@%H", "--name-only",
                  *rng).splitlines():
        if ln.startswith("@"):
            cur = (ln[1:], [])
            out.append(cur)
        elif ln.strip() and cur is not None:
            cur[1].append(ln.strip())
    if (ROOT / REPORT).exists() and not out:
        raise AssertionError(f"{REPORT} exists but I28 has no own commit")
    return out


def show(commit: str, rel: str):
    try:
        return json.loads(git("show", f"{commit}:{rel}"))
    except (AssertionError, ValueError):
        return None


def holon_ok(test: unittest.TestCase, args: list, cwd: Path = ROOT, timeout: int = 7200):
    p = run_holon([str(a) for a in args], cwd=cwd, timeout=timeout)
    test.assertEqual(p.returncode, 0, f"holon {' '.join(map(str, args))}: {(p.stdout + p.stderr)[-3000:]}")
    return p


def history_commit(v: str) -> str:
    return next(x["commit"] for x in I.history(ROOT)["versions"] if x["id"] == v)


def versioned_documents() -> dict:
    """{version: (path, rel)} of the per-version documents the versioned document lists, each checked by sha256 and tied
    to the history's commit of its version (V5)."""
    vd = load_json(need(VERSIONS_DOC))
    out = {}
    for v, d in vd["documents"].items():
        p = ROOT / d["path"]
        if file_sha256(p) != d["sha256"]:
            raise AssertionError(f"{d['path']} is not the document the versioned document names")
        if d["commit"] != history_commit(v):
            raise AssertionError(f"{v}: the versioned document names commit {d['commit']}, the history {history_commit(v)}")
        out[v] = (p, d["path"])
    return out


def document_abi():
    """abi(version, name) -> (selector, params) of the function of that name in the version's document (V5, V8)."""
    tab = {}
    for v, (p, _rel) in versioned_documents().items():
        for a in load_json(p)["actions"]:
            tab[(v, a["name"])] = (a.get("selector") or "", a.get("params") or [])

    def abi(version: str, name: str) -> tuple:
        return tab[(version, name)]
    return abi


def proxy_admin() -> int:
    """The binding's proxy admin: the deployment record's storage word at the sidecar's admin slot (V6's vr0)."""
    slot = num(load_json(SIDECAR)["proxy"]["admin_slot"])
    words = [num(v) for k, v in load_json(ROOT / DEPLOYMENT)["storage"].items() if num(k) == slot]
    if len(words) != 1 or not words[0]:
        raise AssertionError(f"{DEPLOYMENT} holds no proxy admin at the admin slot")
    return words[0]


def check_document(test: unittest.TestCase, vd: dict, v: str, p: Path, rel: str) -> None:
    """V5 and PI1-PI3 for one path version: the document and its generated sidecar are at the history's commit, and
    the instrument finds the one chain with the version's successor sites and the pair (17, 9, 192)."""
    d = load_json(p)
    test.assertEqual((d["facts_version"], d["extraction"]["kind"]), ("holon-facts/0.3", "transitions"))
    test.assertEqual(d["target"]["commit"], history_commit(v))
    test.assertEqual(load_json(need(f"gen/M3/versions/sidecars/{v}.json"))["target"]["commit"], history_commit(v))
    ch = I.chains(p, rel)
    test.assertEqual([(f["family"], [r["action"] for r in f["root_sites"]],
                       [s["action"] for s in f["successor_sites"]], f["pairs"]) for f in ch["families"]],
                     [("committedBatches", ["importGenesisBatch"], SUCCESSORS[v],
                       [{"cell": 17, "incr": 9, "shift": 192}])])


def basis() -> dict:
    return load_json(BASIS)


def catalog_number(v: str) -> int:
    m = CATALOG_RE.match(v)
    if not m:
        raise AssertionError(f"{v} is not a holon-rules/1.<n> catalog version")
    return int(m.group(1))


def i28_catalog() -> tuple:
    """(I28's catalog, the version before it): the lowest catalog version whose PAR holds init_chain, and the highest
    version below it (holon-rules/1.5 when I28 takes 1.6)."""
    rules = holon_module("holon.rules")
    vs = sorted((v for v in rules.CATALOGS if CATALOG_RE.match(v)), key=catalog_number)
    mine = [v for v in vs if SUBFORM in (rules.CATALOGS[v].get("PAR") or {})]
    if not mine:
        raise AssertionError(f"no catalog holds PAR/{SUBFORM}")
    below = [v for v in vs if catalog_number(v) < catalog_number(mine[0])]
    return mine[0], below[-1]


def m3_catalog() -> str:
    """The catalog M3 derives with: I28's or a later one, holding every producer of I28's catalog as the same object."""
    rules = holon_module("holon.rules")
    v = rules.catalog_version(M3)
    base = rules.CATALOGS[i28_catalog()[0]]
    for rule, subs in base.items():
        for sub, prod in subs.items():
            if (rules.CATALOGS[v].get(rule) or {}).get(sub) is not prod:
                raise AssertionError(f"M3 derives with {v}, which drops {rule}/{sub} of I28's catalog")
    return v


def record(lid: str) -> dict:
    return load_json(need(f"results/M3/{lid}.json"))


def run_named(rep: dict, name: str) -> dict:
    runs = [r for r in rep.get("runs") or [] if r.get("name") == name]
    if len(runs) != 1:
        raise AssertionError(f"{REPLAY}: {len(runs)} runs named {name!r}")
    return runs[0]


def error_string(reason: str) -> bytes:
    """The revert data of require(.., reason): Error(string)'s selector 0x08c379a0, then the string's ABI encoding."""
    b = reason.encode("utf-8")
    return bytes.fromhex("08c379a0") + (32).to_bytes(32, "big") + len(b).to_bytes(32, "big") + b + bytes(-len(b) % 32)


def revert_data(step: dict) -> tuple:
    """A replay step's revert data, (model, real), as bytes (V9's "revert")."""
    rv = step["revert"]
    return calldata_bytes(rv["model"]), calldata_bytes(rv["real"])


def bend_accepts(test: unittest.TestCase, f: Path) -> str:
    """Bend accepts f with ALL PROOFS CHECK, and so does BendTT (--verdict) whenever the verdict is enabled."""
    code, out = run_bend([f.name], cwd=f.parent, timeout=3600)
    test.assertEqual(code, 0, f"{f}: {out[-2000:]}")
    test.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), f"{f}: {out[-2000:]}")
    test.assertNotIn("TODO", out)
    if holon_module("holon.bend").verdict_enabled():
        code, vout = run_bend([f.name, "--verdict"], cwd=f.parent, timeout=3600)
        test.assertEqual(code, 0, f"{f} (BendTT): {vout[-2000:]}")
        test.assertIn("ALL PROOFS CHECK", vout, f"{f} (BendTT): {vout[-2000:]}")
    return out


def code_only(text: str) -> str:
    return "\n".join(x.split("#", 1)[0] for x in text.splitlines())


def num(x) -> int:
    return int(str(x), 0)


def calldata_bytes(calldata: str) -> bytes:
    return bytes.fromhex(calldata[2:] if calldata.startswith("0x") else calldata)


def bytes_arg(calldata: str) -> bytes:
    """The first dynamic bytes argument of an ABI call: its offset word, then its length word, then its bytes."""
    cd = calldata_bytes(calldata)
    off = int.from_bytes(cd[4:36], "big")
    n = int.from_bytes(cd[4 + off:4 + off + 32], "big")
    return cd[4 + off + 32:4 + off + 32 + n]


def word_arg(calldata: str, j: int) -> int:
    cd = calldata_bytes(calldata)
    return int.from_bytes(cd[4 + 32 * j:4 + 32 * (j + 1)], "big")


def model_text() -> str:
    """Every .bend file under gen/M3/versions/models/, in name order."""
    fs = sorted(need(MODELS).glob("*.bend"))
    if not fs:
        raise AssertionError(f"{MODELS} holds no .bend file (I28 builds it)")
    return "\n".join(f.read_text() for f in fs)


def defs(text: str) -> dict:
    """{name: (header type, body)} of the top-level definitions of a Bend text (V8: each header on one line)."""
    out, cur = {}, None
    for ln in code_only(text).splitlines():
        m = re.match(r"^def\s+(\w+)\(([^)]*)\)\s*->\s*(.*):\s*$", ln)
        if m:
            cur = m.group(1)
            out[cur] = [m.group(3), []]
        elif ln[:1] not in ("", " ", "\t"):
            cur = None
        elif cur is not None and ln.strip():
            out[cur][1].append(ln.strip())
    return {k: (t, " ".join(b)) for k, (t, b) in out.items()}


def word_lit(n: int) -> str:
    """V8: a word literal of the model, unqualified: w0() for zero, else w_of_limbs([its 8 limbs])."""
    n %= 1 << 256
    return "w0()" if n == 0 else f"w_of_limbs([{', '.join(str(x) for x in I.limbs(n))}])"


def squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


LEAF = re.compile(r"VM\.w_of_limbs\(\[\s*(\d+(?:\s*,\s*\d+){7})\s*\]\)|VM\.w0\(\)|\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]|Nil\{\}")


def bend_leaves(term: str) -> list:
    """V8: the leaf literals of a Bend term in order, in tests_m3/_i28.py::abi_leaves's form: ["w", n] for
    VM.w_of_limbs([8 limbs]) or VM.w0(), ["b", hex] for a list of byte literals, ["nil"] for Nil{} (["l", [..]] for a
    list of numbers that are not all bytes)."""
    out = []
    for m in LEAF.finditer(term):
        if m.group(1) is not None:
            out.append(["w", sum(int(x) << (32 * i) for i, x in enumerate(m.group(1).split(",")))])
        elif m.group(2) is not None:
            xs = [int(x) for x in m.group(2).split(",")]
            out.append(["b", bytes(xs).hex()] if all(x < 256 for x in xs) else ["l", xs])
        elif m.group(0) == "VM.w0()":
            out.append(["w", 0])
        else:
            out.append(["nil"])
    return out


def canonical_reach(n: int) -> str:
    """V8: reach's body for a trace of n steps: VM.VR0{{==}} inside one VM.VRStep{x_i(), s_<i-1>(), .., r_i()} per step,
    step n outermost."""
    t = "VM.VR0{{==}}"
    for i in range(1, n + 1):
        t = f"VM.VRStep{{x_{i}(), s_{i - 1}(), {t}, r_{i}()}}"
    return t


def legacy_head(w: dict, n: int) -> str:
    """V8: the start of lg_j's header for legacy word w in a trace of n steps (the model's table arguments, if any, and
    `) : VM.W}` follow)."""
    path = ", ".join(f"VM.VP{{VM.{word_lit(k)}, VM.{word_lit(o)}}}" for k, o in w["path"])
    return (f"{{VM.{word_lit(num(w['word']))} == VM.vread(s_{n - 1}(), VM.{word_lit(w['base'])}, "
            f"VM.{word_lit(w['offset'])}, {'[' + path + ']' if path else 'Nil{}'}")


def step_constructor(st: dict) -> str:
    """V6: the VStep constructor of a trace step."""
    if st.get("kind") == "migrate":
        return "U_entry" if st.get("label") == "entry" else "U_" + st["label"].replace("->", "_")
    return f"C_{st['version']}_{st['action']}"


def step_problems(i: int, st: dict, x, abi, admin: int) -> list:
    """V8: what x_i ((header type, body), or None) lacks for trace step i: a VM.VStep built by the step's constructor,
    whose literal leaves begin with the step's arguments (its calldata decoded by the parameter types of the function
    it calls, which its selector names) and, for a call, continue with its caller; a migration step's caller is the
    proxy admin, and a step that calls no function has no calldata."""
    if st.get("kind") not in ("call", "migrate"):
        return [f"step {i} has kind {st.get('kind')!r}"]
    ctor = step_constructor(st)
    t, b = x or ("", "")
    if t.strip() != "VM.VStep" or not re.match(rf"^VM\.{re.escape(ctor)}\{{", b):
        return [f"x_{i} is not a VM.VStep built by VM.{ctor}{{..}}"]
    probs, want = [], []
    name = st.get("action") if st["kind"] == "call" else st.get("call")
    cd = st.get("calldata") or "0x"
    if name:
        try:
            sel, params = abi(st.get("version"), name)
            if (cd[2:] if cd.startswith("0x") else cd)[:8].lower() != sel.lower().removeprefix("0x"):
                return [f"step {i}'s calldata does not call {name} ({sel})"]
            want = I.abi_leaves(params, cd)
        except (KeyError, ValueError) as e:
            return [f"step {i}: no arguments of {name} at {st.get('version')} ({e})"]
    elif cd not in ("0x", ""):
        probs.append(f"step {i} calls no function but has calldata")
    got = bend_leaves(b)
    if got[:len(want)] != want:
        probs.append(f"x_{i}'s first literals are not step {i}'s arguments decoded from its calldata")
    if st["kind"] == "call":
        if got[len(want):len(want) + 1] != [["w", num(st.get("caller") or "0")]]:
            probs.append(f"x_{i} does not carry step {i}'s caller as its first literal after its arguments")
    elif num(st.get("caller") or "0") != admin:
        probs.append(f"step {i} is a migration whose caller is not the proxy admin")
    return probs


def inhabit_shape_problems(text: str, trace: list, legacy: list, abi, admin: int) -> list:
    """V8: what INHABIT.bend's text lacks of its shape for this trace and these legacy words ([] when none). abi(version,
    name) is (selector, params) of a function of the version's document (V5); admin is the binding's proxy admin."""
    probs, n, d = [], len(trace), defs(text)
    if not re.search(r"(?m)^import\s+\S+\s+as\s+VM\s*$", text):
        probs.append("no `import .. as VM` line")
    for i in range(n + 1):
        if d.get(f"s_{i}", ("", ""))[0].strip() != "VM.VSt":
            probs.append(f"no s_{i} : VM.VSt")
    if squash(d.get("s_0", ("", ""))[1]) != "VM.vr0()":
        probs.append("s_0's body is not exactly VM.vr0()")
    for i, st in enumerate(trace, 1):
        probs += step_problems(i, st, d.get(f"x_{i}"), abi, admin)
        t, b = d.get(f"r_{i}", ("", ""))
        if not (t.startswith(f"{{s_{i}() == VM.vstep(x_{i}(), s_{i - 1}()") and b == "{==}"):
            probs.append(f"r_{i} is not s_{i} == vstep(x_{i}, s_{i - 1}) by computation")
    for i in (n - 1, n):
        t, b = d.get(f"ok_{i}", ("", ""))
        if not (t.startswith(f"{{True{{}} == VM.vok(x_{i}(), s_{i - 1}()") and b == "{==}"):
            probs.append(f"ok_{i} is not vok(x_{i}, s_{i - 1}) by computation")
    for j, w in enumerate(legacy, 1):
        t, b = d.get(f"lg_{j}", ("", ""))
        head, rest = squash(legacy_head(w, n)), squash(t)
        if not (rest.startswith(head) and re.fullmatch(r"(\)|,.*\)):VM\.W\}", rest[len(head):]) and b == "{==}"):
            probs.append(f"lg_{j} does not state {w['reads']} = {w['word']} at its coordinate by computation")
    t, b = d.get("reach", ("", ""))
    if not (re.fullmatch(rf"VM\.VReach<(?:.*,\s*)?s_{n}\(\)>", t.strip()) and squash(b) == squash(canonical_reach(n))):
        probs.append(f"reach is not a VM.VReach at s_{n} built from the x_i, s_i and r_i in order down to VM.VR0{{{{==}}}}")
    return probs


def shape_fixture() -> tuple:
    """The shape check's own test data (green at the prereg): a five-step trace (the entry edge; the deployment record's
    initialize and importGenesisBatch; a commitBatch whose parent is the recorded genesis header, so its key is 1; and
    the migration V10->V11 with initialize4(the submitter stand-in, 1)), its two legacy words (inflight_words at
    V10->V11 for the key 1, with words 7 and the stand-in), abi over the adopted head document's functions for every
    version, and the proxy admin."""
    head = load_json(ROOT / I.HEAD_DOC)
    tab = {a["name"]: (a.get("selector") or "", a.get("params") or []) for a in head["actions"]}
    dep = load_json(ROOT / DEPLOYMENT)
    admin, harness = proxy_admin(), num(dep["calls"][0]["caller"])
    stand_in = word_arg(dep["calls"][0]["data"], 0)
    genesis = bytes_arg(dep["calls"][3]["data"])

    def w(n: int) -> bytes:
        return n.to_bytes(32, "big")
    batch = (w(0x20) + w(0) + w(7 * 32) + w(7) + w(0) + w(0x64) + w(0x65) + w(0x66) + w(len(genesis)) + genesis
             + bytes(-len(genesis) % 32))

    def call(action: str, caller: int, calldata: str) -> dict:
        return {"label": action, "kind": "call", "action": action, "version": "V11", "caller": hex(caller),
                "calldata": calldata, "ok": True}
    trace = [{"label": "entry", "kind": "migrate", "version": "V11", "caller": hex(admin), "call": None,
              "calldata": "0x", "ok": True},
             call("initialize", harness, dep["calls"][0]["data"]),
             call("importGenesisBatch", harness, dep["calls"][3]["data"]),
             call("commitBatch", stand_in, tab["commitBatch"][0] + batch.hex()),
             {"label": "V10->V11", "kind": "migrate", "version": "V11", "caller": hex(admin), "call": "initialize4",
              "calldata": tab["initialize4"][0] + (w(stand_in) + w(1)).hex(), "ok": True}]
    legacy = [dict(x, word=hex(v)) for x, v in zip(I.inflight_words(ROOT, "V10", "V11", 1), (7, stand_in))]

    def abi(version: str, name: str) -> tuple:
        return tab[name]
    return trace, legacy, abi, admin


def shape_text(trace: list, legacy: list, abi, *, s0: str = "VM.vr0()", args: dict | None = None,
               callers: dict | None = None, before_caller: dict | None = None, lg: dict | None = None,
               reach: str | None = None) -> str:
    """An INHABIT text of V8's shape for a trace and its legacy words (the shape check's own test), with overrides: s_0's
    body, step i's argument leaves, step i's caller, a literal put between step i's arguments and its caller, legacy
    word j's lg header type and reach's body. A call step's x_i is VM.<constructor>{VM.A{<arguments>}, <caller>,
    VM.E{VM.w0()}}, a migration's VM.<constructor>{VM.A{..}} or VM.<constructor>{}."""
    args, callers, before, lg, n = args or {}, callers or {}, before_caller or {}, lg or {}, len(trace)

    def lit(leaf: list) -> str:
        if leaf[0] == "w":
            return "VM." + word_lit(leaf[1])
        if leaf[0] == "b":
            return "[" + ", ".join(str(x) for x in bytes.fromhex(leaf[1])) + "]"
        return "Nil{}"
    out = ["import morph_rollup.versions as VM", "", "def s_0() -> VM.VSt:", f"  {s0}", ""]
    for i in range(1, n + 1):
        out += [f"def s_{i}() -> VM.VSt:", f"  VM.VSt{{VM.{word_lit(i)}}}", ""]
    for i, st in enumerate(trace, 1):
        name = st.get("action") if st["kind"] == "call" else st.get("call")
        leaves = args.get(i, I.abi_leaves(abi(st["version"], name)[1], st["calldata"]) if name else [])
        a = "VM.A{" + ", ".join(lit(x) for x in leaves) + "}"
        if st["kind"] == "call":
            caller = f"VM.{word_lit(callers.get(i, num(st['caller'])))}"
            fields = [a] + ([before[i]] if i in before else []) + [caller, "VM.E{VM.w0()}"]
            body = f"VM.{step_constructor(st)}{{{', '.join(fields)}}}"
        else:
            body = f"VM.{step_constructor(st)}{{{a if leaves else ''}}}"
        out += [f"def x_{i}() -> VM.VStep:", f"  {body}", "",
                f"def r_{i}() -> {{s_{i}() == VM.vstep(x_{i}(), s_{i - 1}()) : VM.VSt}}:", "  {==}", ""]
    for i in (n - 1, n):
        out += [f"def ok_{i}() -> {{True{{}} == VM.vok(x_{i}(), s_{i - 1}()) : Bool}}:", "  {==}", ""]
    for j, w in enumerate(legacy, 1):
        out += [f"def lg_{j}() -> {lg.get(j, legacy_head(w, n) + ') : VM.W}')}:", "  {==}", ""]
    out += [f"def reach() -> VM.VReach<s_{n}()>:", f"  {reach or canonical_reach(n)}", ""]
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------- the instruments
class TestInstrument(unittest.TestCase):
    """The instruments are what the key says (construction; green at the prereg)."""

    def test_the_key_pins_the_instruments(self):
        th = predictions(KEY)["thresholds"]
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i28.py"), th["instrument_sha256"])
        self.assertEqual(hashlib.sha256(__doc__.encode("utf-8")).hexdigest(), th["contract_docstring_sha256"])
        self.assertEqual(file_sha256(SIDECAR), th["sidecar_sha256"])
        self.assertEqual(file_sha256(BASIS), th["basis_sha256"])
        for rel, sha in th["inputs_sha256"].items():
            with self.subTest(input=rel):
                self.assertEqual(file_sha256(ROOT / rel), sha)
        self.assertIn(DEPLOYMENT, th["inputs_sha256"])

    def test_the_basis_is_the_computation(self):
        """spec/M3/lib/versions_basis.json is tests_m3/_i28.py::versions_basis_doc over unchanged inputs."""
        b = basis()
        for i in b["inputs"]:
            with self.subTest(input=i["path"]):
                self.assertEqual(file_sha256(ROOT / i["path"]), i["sha256"], f"{i['path']} changed since the prereg")
        self.assertEqual({k: v for k, v in b.items() if k != "doc"}, I.versions_basis_doc(ROOT))
        self.assertTrue(b["doc"].strip())

    def test_the_basis_states_the_predicted_counts(self):
        """The counts the key's thresholds name, read off the basis: 9 path versions, 8 MIG edges, the in-flight counts,
        2 in-flight types, 10 deployments, 1 downgrade gap, and over the head document one chain with one pair and one
        link gap of 4 sites, each gap with its obligation, question and open status."""
        b, th = basis(), predictions(KEY)["thresholds"]
        self.assertEqual(b["path"], th["path"])
        self.assertEqual(b["never_deployed"], th["never_deployed"])
        self.assertEqual([f"{e['from']}->{e['to']}" for e in b["edges"]], th["mig_edges"])
        self.assertEqual({f"{e['from']}->{e['to']}": e["in_flight_count"] for e in b["edges"]}, th["in_flight_counts"])
        self.assertEqual({f"{e['from']}->{e['to']}": [r["name"] for r in e["introduced"]] for e in b["edges"]
                          if e["introduced"]}, th["introduced"])
        self.assertEqual([[x["edge"], x["entry"], x["kind"]] for x in b["in_flight_types"]], th["in_flight_types"])
        self.assertEqual([[d["version"], d["immutables"]] for d in b["deployments"]], th["deployments"])
        self.assertEqual([(g["id"], g["obligation"], g["question"], g["status"]) for g in b["downgrade_gaps"]],
                         [(DOWNGRADE_GAP, I.gap_meta("downgrade")["obligation"], "Q64", "open")])
        fams = b["head"]["chains"]["families"]
        self.assertEqual([(f["family"], [r["action"] for r in f["root_sites"]],
                           [s["action"] for s in f["successor_sites"]], f["pairs"]) for f in fams],
                         [("committedBatches", ["importGenesisBatch"], SUCCESSORS["V11"],
                           [{"cell": 17, "incr": 9, "shift": 192}])])
        self.assertEqual([(g["id"], [[s["action"], s["at"], s["fn"]] for s in g["sites"]], g["obligation"], g["question"],
                           g["status"]) for g in b["head"]["link_gaps"]],
                         [(LINK_GAP, th["link_gap_sites_V11"], "D4", "Q63", "open")])

    def test_the_shape_check_refuses_loose_inhabitants(self):
        """V8's shape check on a synthetic trace (shape_fixture; construction, green at the prereg): the instrument's
        decoder gives the arguments the test's own readers give, and refuses lengths the calldata cannot hold; a text of
        V8's shape passes; the prereg review's crafted text (s_0 = VM.vstep(VM.C_V3_evil{}, VM.vr0()), arbitrary step
        arguments, a reach over unrelated steps), which the prereg's first check passed, is refused, and so is each
        single loosening: s_0, one argument, an extra argument, a caller, a caller one field late, a migration's
        caller, a selector, a trace argument the text does not carry, reach's order, a legacy coordinate."""
        trace, legacy, abi, admin = shape_fixture()
        n = len(trace)
        cd = [st["calldata"] for st in trace]
        genesis = bytes_arg(cd[2])
        self.assertEqual(I.abi_leaves(abi("V11", "initialize")[1], cd[1]), [["w", word_arg(cd[1], j)] for j in range(6)])
        self.assertEqual(I.abi_leaves(abi("V11", "importGenesisBatch")[1], cd[2]), [["b", genesis.hex()]])
        self.assertEqual(I.abi_leaves(abi("V11", "commitBatch")[1], cd[3]),
                         [["w", 0], ["b", genesis.hex()], ["w", 7], ["w", 0], ["w", 0x64], ["w", 0x65], ["w", 0x66]])
        self.assertEqual(I.commit_key(cd[3]), 1)
        stand_in = word_arg(cd[1], 0)
        self.assertEqual(I.abi_leaves(abi("V11", "initialize4")[1], cd[4]), [["w", stand_in], ["w", 1]])
        for params, data in (([{"name": "xs", "type": "uint256[]"}], (32).to_bytes(32, "big") + (2 ** 200).to_bytes(32, "big")),
                             ([{"name": "b", "type": "bytes"}], (32).to_bytes(32, "big") + (10 ** 9).to_bytes(32, "big"))):
            with self.assertRaises(ValueError):    # a length the calldata cannot hold is refused, never allocated
                I.abi_leaves(params, "0x41f756da" + data.hex())
        self.assertEqual(canonical_reach(2), "VM.VRStep{x_2(), s_1(), VM.VRStep{x_1(), s_0(), VM.VR0{{==}}, r_1()}, r_2()}")
        self.assertEqual(legacy[1]["reads"], "Rollup.l1StakingContract")
        self.assertEqual(legacy_head(legacy[1], n), "{VM." + word_lit(stand_in) + " == VM.vread(s_4(), "
                         "VM.w_of_limbs([151, 0, 0, 0, 0, 0, 0, 0]), VM.w0(), Nil{}")
        self.assertEqual(inhabit_shape_problems(shape_text(trace, legacy, abi), trace, legacy, abi, admin), [])

        evil, junk = "VM.vstep(VM.C_V3_evil{}, VM.vr0())", "VM.VR0{{==}}"
        for _ in range(n):
            junk = f"VM.VRStep{{VM.C_V3_evil{{}}, VM.vr0(), {junk}, {{==}}}}"
        crafted = shape_text(trace, legacy, abi, s0=evil, args={i: [["w", 0]] for i in range(2, n + 1)}, reach=junk)
        self.assertEqual((junk.count("VM.VRStep{"), junk.count("VM.VR0{")), (n, 1))   # the prereg's first check's counts
        got = inhabit_shape_problems(crafted, trace, legacy, abi, admin)
        for want in ("s_0's body", "x_2's first literals", "x_5's first literals", "reach is not"):
            self.assertTrue([p for p in got if want in p], (want, got))

        tweak = list(genesis)
        tweak[0] ^= 1
        commit_leaves = I.abi_leaves(abi("V11", "commitBatch")[1], cd[3])
        moved = dict(legacy[1], offset=1)
        swapped = canonical_reach(n).replace("x_1()", "x_@").replace("x_2()", "x_1()").replace("x_@", "x_2()")
        cases = [
            ("s_0's body", {"s0": evil}, trace),
            ("x_4's first literals", {"args": {4: [commit_leaves[0], ["b", bytes(tweak).hex()]] + commit_leaves[2:]}},
             trace),
            ("x_3's first literals", {"args": {3: [["w", 0], ["b", genesis.hex()]]}}, trace),
            ("x_2 does not carry step 2's caller", {"callers": {2: stand_in}}, trace),
            ("x_2 does not carry step 2's caller", {"before_caller": {2: "VM.w0()"}}, trace),   # the caller, one field late
            ("step 5 is a migration whose caller", {}, trace[:4] + [dict(trace[4], caller=trace[1]["caller"])]),
            ("step 5's calldata does not call initialize4", {},
             trace[:4] + [dict(trace[4], calldata="0x00000000" + cd[4][10:])]),
            ("x_5's first literals", {}, trace[:4] + [dict(trace[4], calldata=cd[4][:-1] + "2")]),
            ("reach is not", {"reach": swapped}, trace),
            ("lg_2 does not state", {"lg": {2: legacy_head(moved, n) + ") : VM.W}"}}, trace),
        ]
        for k, (want, kw, checked) in enumerate(cases):
            with self.subTest(loosening=k, want=want):
                got = inhabit_shape_problems(shape_text(trace, legacy, abi, **kw), checked, legacy, abi, admin)
                self.assertTrue([p for p in got if want in p], got)

    def test_the_instrument_sees_s1_s3(self):
        """S1-S3 on the instrument's own side (the planted documents and what PI1-PI5 give on them)."""
        tmp = Path(tempfile.mkdtemp(prefix="i28-planted-"))
        try:
            got = {}
            for kind in ("renamed", "no_chain", "no_root"):
                p = tmp / f"{kind}.json"
                p.write_text(json.dumps(I.planted(kind)))
                a = I.analysis_doc({"V0": (p, None)}, [])
                got[kind] = ([b["law_id"] for b in a["basis"]], [g["id"] for g in a["link_gaps"]])
            self.assertEqual(got["renamed"], (["L_pinit_Ledger_seedChain_sealedHeaders_17_9"],
                                              ["gap:M3:link:sealedHeaders:17:IL1MessageQueue"]))
            self.assertEqual(got["no_chain"], ([], []))
            self.assertEqual(got["no_root"], ([], []))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- V1-V5, P1
class TestVersions(unittest.TestCase):
    def test_extract_reproduces(self):
        """V5 (construction): holon versions extract --check exits 0."""
        holon_ok(self, ["versions", "extract", "--check"])

    def test_the_versioned_document_is_the_basis(self):
        """V1-V5 (construction): the versioned document's path, versions in no match, unmatched upgrades, deployments, entry,
        edges, in-flight types, reverse edges and downgrade gaps are the basis's; its history, timeline and sidecar entries
        carry those files' sha256; it lists one document per path version unless that version is debt, each at the
        history's commit of its version."""
        vd = load_json(need(VERSIONS_DOC))
        b = basis()
        self.assertEqual(vd["versions_version"], "holon-versions/0.1")
        for k in ("path", "never_deployed", "unmatched", "deployments", "entry", "edges", "in_flight_types", "reverse",
                  "downgrade_gaps"):
            with self.subTest(field=k):
                self.assertEqual(vd[k], b[k])
        for k, rel in (("history", I.HISTORY), ("timeline", I.TIMELINE), ("sidecar", "spec/M3/lib/versions.json")):
            self.assertEqual(vd[k], {"path": rel, "sha256": file_sha256(ROOT / rel)})
        debt = {d["version"] for d in vd["debt"]}
        self.assertEqual(sorted(set(vd["documents"]) | debt, key=I._vkey), b["path"])
        self.assertFalse(set(vd["documents"]) & debt)
        versioned_documents()

    def test_p1_every_old_version_extracts(self):
        """I28-P1: every path version before the head's code, V3..V10, extracts (none is debt), each document and its
        generated sidecar at the history's commit of the version; in each, PI1-PI3 (the instrument over the document) find
        the one commitment family committedBatches with the root site importGenesisBatch, the successor sites the
        version's source predicts (SUCCESSORS) and the one chained pair (17, 9, 192)."""
        item(KEY, "I28-P1")
        vd = load_json(need(VERSIONS_DOC))
        self.assertEqual([d for d in vd["debt"] if d["version"] in OLD], [])
        docs = versioned_documents()
        self.assertLessEqual(set(OLD), set(docs))
        for v in OLD:
            with self.subTest(version=v):
                check_document(self, vd, v, *docs[v])

    def test_v11_is_the_adopted_document(self):
        """Construction (V5 at the head's code): V11 extracts at its history commit, with the head's chain, and its document
        equals the adopted head document in its actions, assumptions, constants, contract, inherited storage and storage
        (the seven repository units of V11's commit and of the head are byte-identical)."""
        vd = load_json(need(VERSIONS_DOC))
        docs = versioned_documents()
        self.assertIn("V11", docs)
        check_document(self, vd, "V11", *docs["V11"])
        head = load_json(ROOT / I.HEAD_DOC)
        v11 = load_json(docs["V11"][0])
        for k in SAME_AS_HEAD:
            with self.subTest(key=k):
                self.assertEqual(v11[k], head[k])


# ---------------------------------------------------------------------------------------------- V6, V7, P2
class TestModel(unittest.TestCase):
    def test_model_reproduces_and_has_no_escape_hatch(self):
        """V6 (construction): holon versions model --check exits 0; the model's files name step_<k> and run_<k> for every
        path version and the versioned layer's definitions (VSt, VStep with its C_/U_ constructors, vr0, vstep, vok, vrun,
        VReach with VR0 and VRStep, vread and VP) and hold no escape hatch; no commit of I28's own changes holon/sorts/ or
        gen/M3/sorts/."""
        holon_ok(self, ["versions", "model", "--check"])
        need(MODEL)
        text = model_text()
        self.assertEqual(ESCAPES.findall(code_only(text)), [])
        for v in PATH:
            with self.subTest(version=v):
                self.assertRegex(text, rf"(?m)^def \w*step_{v}\w*\(", f"no step_{v}")
                self.assertRegex(text, rf"(?m)^def \w*run_{v}\w*\(", f"no run_{v}")
        for name in ("VSt", "VStep", "VReach", "VP"):
            self.assertRegex(text, rf"(?m)^type {name}\b", f"no type {name}")
        for name in ("vr0", "vstep", "vok", "vrun", "vread"):
            self.assertRegex(text, rf"(?m)^def {name}\(", f"no def {name}")
        for name in ["U_entry", "VR0", "VRStep"] + [f"U_{a}_{b}" for a, b in zip(PATH, PATH[1:])]:
            self.assertRegex(text, rf"(?m)^\s+{name}\{{", f"no constructor {name}")
        self.assertEqual([n for _, names in own_commits() for n in names
                          if n.startswith(("holon/sorts/", "gen/M3/sorts/"))], [])

    def test_p2_the_machine_refines_the_real_upgrade_path(self):
        """I28-P2 (V7): the upgrade path's run in the replay report passed, over the sidecar's 14 steps: the entry edge,
        initialize and importGenesisBatch, the same two calls again (each reverting), the MIG edges before the last, the
        last edge with a wrong cutover index (reverting) and the last edge. Every step's status is the stated one in the
        model and on the real code, and so is its revert data: none after a successful step, and on both sides of each
        reverting step the Error(string) of the reason the key names (the initializer guard's "Initializable: contract is
        already initialized", "genesis batch imported", "cutover batch mismatch"); at every real slot in the union of the
        two sides' writes (one entry per real slot, the proxy's EIP-1967 slots aside) the 32-byte words agree; a reverting
        step writes nothing, each successful call writes; and the Initialized version (the low byte of real slot 0) is 1,
        2, 3, 4 after initialize and the edges into V4, V7 and V11."""
        item(KEY, "I28-P2")
        reasons = predictions(KEY)["thresholds"]["upgrade_path_reverts"]
        self.assertEqual({int(k): v for k, v in reasons.items()}, UPGRADE_REVERTS)
        self.assertEqual(sorted(UPGRADE_REVERTS), [i for i, s in enumerate(UPGRADE_STATUS) if s == "revert"])
        rep = load_json(need(REPLAY))
        r = run_named(rep, "upgrade_path")
        self.assertTrue(r["passed"], r)
        self.assertEqual([s.get("label") for s in r["trace"]], UPGRADE_LABELS)
        self.assertEqual(len(r["steps"]), len(UPGRADE_LABELS))
        got = {}
        for i, (st, want) in enumerate(zip(r["steps"], UPGRADE_STATUS)):
            with self.subTest(step=i, label=UPGRADE_LABELS[i]):
                self.assertEqual((st["model"], st["real"]), (want, want))
                why = error_string(UPGRADE_REVERTS[i]) if want == "revert" else b""
                self.assertEqual(revert_data(st), (why, why))
                slots = [num(s["slot"]) for s in st["slots"]]
                self.assertEqual(len(slots), len(set(slots)), "one entry per real slot")
                self.assertFalse(set(slots) & EIP1967)
                self.assertEqual([num(s["model"]) for s in st["slots"]], [num(s["real"]) for s in st["slots"]])
                if want == "revert":
                    self.assertEqual(st["slots"], [])
                if i in SUCCESSFUL_CALLS:
                    self.assertTrue(st["slots"], "a successful call writes")
                if i in INITIALIZED:
                    w = [s for s in st["slots"] if num(s["slot"]) == 0]
                    self.assertEqual(len(w), 1, st["slots"])
                    got[i] = num(w[0]["real"]) & 0xFF
        self.assertEqual(got, INITIALIZED)
        self.assertEqual(sorted(rep["implementations"], key=I._vkey), PATH)


# ---------------------------------------------------------------------------------------------- PI1-PI6, P3
class TestParInit(unittest.TestCase):
    def test_catalog(self):
        """Construction: I28's catalog (the lowest catalog version whose PAR holds init_chain: holon-rules/1.6, or the next
        free version) holds every rule and producer of the version before it, the same objects, and adds only PAR's
        init_chain (holon.rules.par_init.PRODUCERS); M3 derives with it or a later catalog that keeps its producers; M2
        keeps holon-rules/1.0."""
        rules = holon_module("holon.rules")
        pi = holon_module("holon.rules.par_init")
        mine, prev = i28_catalog()
        cat, before = rules.CATALOGS[mine], rules.CATALOGS[prev]
        for rule, subs in before.items():
            for sub, prod in subs.items():
                self.assertIs(cat[rule][sub], prod, f"{rule}/{sub}")
        self.assertEqual(sorted(cat), sorted(before))
        self.assertEqual({r: sorted(set(cat[r]) - set(before[r])) for r in cat if set(cat[r]) - set(before[r])},
                         {"PAR": [SUBFORM]})
        self.assertEqual(dict(pi.PRODUCERS), {SUBFORM: cat["PAR"][SUBFORM]})
        self.assertIs(rules.CATALOGS[m3_catalog()]["PAR"][SUBFORM], cat["PAR"][SUBFORM])
        self.assertEqual(rules.catalog_version("M2"), "holon-rules/1.0")

    def test_analysis_is_the_instruments(self):
        """PI1-PI5 and V4 (construction): holon versions analyze --check exits 0 and gen/M3/versions/par_init.json is
        tests_m3/_i28.py::analysis_doc over the versioned documents and the basis's downgrade gaps."""
        holon_ok(self, ["versions", "analyze", "--check"])
        got = load_json(need(ANALYSIS))
        self.assertEqual(got, json.loads(json.dumps(I.analysis_doc(versioned_documents(), basis()["downgrade_gaps"]))))

    def test_p3_the_o9_law_is_refuted_and_replays(self):
        """I28-P3 (O9): laws/M3 holds exactly one PAR law of sub-form init_chain,
        L_pinit_Rollup_importGenesisBatch_committedBatches_17_9, as PI4 states it over the analysis's one basis element;
        its record is REFUTED by a witness at the first path version V3: the trace [entry, initialize, importGenesisBatch]
        from VR0, the root step by the deployment record's caller of its genesis call, with that call's header but bytes
        17..24 set to 1 (cell 17 = 1, cell 9 = 0); its PROOF.bend imports its LAWS.bend as Laws, which states exactly the
        counter-law, and Bend accepts it (BendTT too when the verdict is enabled); and its run in the replay report passed,
        the real committedBatches[0] being keccak256 of the root input."""
        item(KEY, "I28-P3")
        mine = {k: v for k, v in laws(M3).items() if v.get("subform") == SUBFORM}
        self.assertEqual(sorted(mine), [LAW])
        law = mine[LAW]
        self.assertEqual(validate(law, IR03), [])
        an = load_json(need(ANALYSIS))
        self.assertEqual([b["law_id"] for b in an["basis"]], [LAW])
        st = law["statement"]
        self.assertEqual((law["rule"], law["milestone"], law["rule_catalog_version"], law["facts"]),
                         ("PAR", M3, m3_catalog(), VERSIONS_DOC))
        self.assertEqual(law["facts_sha256"], file_sha256(ROOT / VERSIONS_DOC))
        self.assertFalse({"evidence", "predicted"} & set(law))
        self.assertEqual([(b["name"], b["type"]) for b in st["binders"][:3]], [("s", "Reach"), ("a", "Act"), ("e", "Env")])
        self.assertTrue(st["binders"][3:] and all(b["type"] == "Fn<Bytes,Word>" for b in st["binders"][3:]),
                        st["binders"])
        self.assertEqual(st["assume"], [])
        self.assertEqual(st["claim"], {"eq": [{"init": INIT_ID, "on": {"var": "a"}, "from": {"var": "s"},
                                               "env": {"var": "e"}}, {"bool": True}]})
        rec = record(LAW)
        self.assertEqual(rec["status"], "REFUTED")
        for schema in (V1SCHEMA, V2SCHEMA):
            self.assertEqual(validate(rec, schema), [])
        w = rec["witness"]
        self.assertEqual([s.get("label") for s in w["trace"]], ["entry", "initialize", "importGenesisBatch"])
        last = w["trace"][-1]
        self.assertEqual((last.get("version"), last.get("ok")), ("V3", True))
        self.assertEqual({k: w["root"][k] for k in ("version", "action", "caller", "calldata")},
                         {"version": "V3", "action": "importGenesisBatch", "caller": last.get("caller"),
                          "calldata": last.get("calldata")})
        genesis = load_json(ROOT / DEPLOYMENT)["calls"][3]
        self.assertEqual(num(w["root"]["caller"]), num(genesis["caller"]))
        recorded, h = bytes_arg(genesis["data"]), bytes_arg(w["root"]["calldata"])
        th = predictions(KEY)["thresholds"]["witness_root_cells"]
        self.assertEqual(h, recorded[:17] + th["17"].to_bytes(8, "big") + recorded[25:])
        b = an["basis"][0]
        self.assertEqual(I.root_witness_problems(h, b), [])
        self.assertEqual((I.cell(h, b["cell"], b["shift"]), I.cell(h, b["incr"], b["shift"])), (th["17"], th["9"]))
        self.assertFalse([k for k in rec.get("kernels") or [] if k.get("name") == "lean4"])
        art = rec["artifacts"]
        proof, lawsf = ROOT / art["proof"], ROOT / art["laws"]
        self.assertIsNone(holon_module("holon.mpipeline").law_import_problem(proof, lawsf))
        self.assertEqual(re.findall(r"(?m)^law\s+([A-Za-z0-9_.]+)\s*:", code_only(lawsf.read_text())),
                         [f"cl_{LAW.lower()}"])
        self.assertEqual(re.findall(r"(?<![\w.])law\s+[A-Za-z0-9_.]+\s*:", code_only(proof.read_text())), [])
        self.assertEqual(ESCAPES.findall(code_only(proof.read_text())), [])
        bend_accepts(self, proof)
        rep = load_json(need(REPLAY))
        r = run_named(rep, LAW)
        self.assertTrue(r["passed"], r)
        self.assertEqual([(s["model"], s["real"], revert_data(s)) for s in r["steps"]], [("ok", "ok", (b"", b""))] * 3)
        from tests_m2._keccak import keccak256
        slot = I._layout(ROOT, "V3")["Rollup.committedBatches"]["slot"]
        at = int.from_bytes(keccak256(I._word(0) + I._word(slot)), "big")
        words = [s for s in r["steps"][-1]["slots"] if num(s["slot"]) == at]
        self.assertEqual([(num(s["model"]), num(s["real"])) for s in words],
                         [(int.from_bytes(keccak256(h), "big"),) * 2])

    def test_derive_reproduces_laws_m3(self):
        """Construction: holon derive --milestone M3 into a temporary directory writes laws/M3 byte for byte and the
        committed gen/M3/sorts/obstructions.json (which no commit of I28's own changes: I28-R2)."""
        out = Path(tempfile.mkdtemp(prefix="i28-derive-"))
        try:
            holon_ok(self, ["derive", "--milestone", M3, "--out", str(out / "laws"),
                            "--obstructions", str(out / "obstructions.json")])
            got = {p.name: p.read_bytes() for p in sorted((out / "laws").glob("*.json"))}
            want = {p.name: p.read_bytes() for p in sorted((ROOT / "laws" / M3).glob("*.json"))}
            self.assertEqual(sorted(got), sorted(want))
            self.assertEqual([n for n in got if got[n] != want[n]], [])
            self.assertEqual((out / "obstructions.json").read_bytes(),
                             (ROOT / "gen" / M3 / "sorts" / "obstructions.json").read_bytes())
        finally:
            shutil.rmtree(out, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- G1, G2: P4 and the gaps
def i28_added_laws() -> dict:
    """The laws/M3 law files that commits of I28's own add, by law id."""
    out = {}
    for c, names in own_commits():
        for n in names:
            if re.match(r"^laws/M3/L[^/]*\.json$", n) and show(f"{c}^", n) is None and (ROOT / n).exists():
                out[n.rsplit("/", 1)[1][:-5]] = load_json(ROOT / n)
    return out


class TestGaps(unittest.TestCase):
    def test_p4_the_d4_link_gap_at_the_old_versions(self):
        """I28-P4 (D4): the analysis holds exactly one link gap, gap:M3:link:committedBatches:17:IL1MessageQueue, and at
        every path version before the head's code, V3..V10, its sites are: the successor sites' actions calling
        IL1MessageQueue.getCrossDomainMessage, finalizeBatch calling IL1MessageQueue.popCrossDomainMessage, and no other
        function."""
        item(KEY, "I28-P4")
        an = load_json(need(ANALYSIS))
        self.assertEqual([g["id"] for g in an["link_gaps"]], [LINK_GAP])
        g = an["link_gaps"][0]
        self.assertLessEqual(set(OLD), set(g["sites"]))
        for v in OLD:
            with self.subTest(version=v):
                calls = {(s["action"], s["fn"]) for s in g["sites"][v]}
                want = {(a, "IL1MessageQueue.getCrossDomainMessage") for a in SUCCESSORS[v]}
                want.add(("finalizeBatch", "IL1MessageQueue.popCrossDomainMessage"))
                self.assertEqual(calls, want)

    def test_the_link_gap_record(self):
        """Construction (PI5 at the head's code): the link gap is for (committedBatches, 17, 9, IL1MessageQueue), has a site
        list for every path version, at V11 the basis's four sites (commitBatch calls[2], commitBatchWithProof calls[1],
        commitState calls[2], finalizeBatch calls[0]), obligation D4, question Q63 and status open; no law that commits of
        I28's own add names the queue or its registers."""
        an = load_json(need(ANALYSIS))
        g = next(x for x in an["link_gaps"] if x["id"] == LINK_GAP)
        self.assertEqual((g["kind"], g["family"], g["cell"], g["incr"], g["interface"]),
                         ("link", "committedBatches", 17, 9, "IL1MessageQueue"))
        self.assertEqual(sorted(g["sites"], key=I._vkey), PATH)
        self.assertEqual([[s["action"], s["at"], s["fn"]] for s in g["sites"]["V11"]],
                         predictions(KEY)["thresholds"]["link_gap_sites_V11"])
        self.assertEqual({k: g[k] for k in ("obligation", "question", "status")}, I.gap_meta("link"))
        self.assertFalse([lid for lid, x in i28_added_laws().items()
                          if re.search(r"IL1MessageQueue|pendingQueueIndex|nextCrossDomainMessageIndex",
                                       json.dumps(x["statement"]))])

    def test_the_downgrade_gap(self):
        """Construction (V4; F12.5 only under reading (a) of Question 64, G2): the versioned document and the analysis hold
        exactly the basis's downgrade gap, gap:M3:downgrade:V11->V10 (retyped Rollup.batchDataStore;
        Rollup.l1StakingContract overlapping Rollup.submitterContract; removed Rollup.legacyCutoverBatchIndex and
        Rollup.submitterContract; added Rollup.l1StakingContract; its obligation, question Q64 and status open); every other
        reverse edge of the path is compatible; no law that commits of I28's own add names a downgrade or a reverse edge."""
        vd, an = load_json(need(VERSIONS_DOC)), load_json(need(ANALYSIS))
        for doc in (vd, an):
            self.assertEqual(doc["downgrade_gaps"], basis()["downgrade_gaps"])
        g = vd["downgrade_gaps"][0]
        self.assertEqual((g["id"], g["retyped"], g["overlap"], g["removed"], g["added"]),
                         (DOWNGRADE_GAP, ["Rollup.batchDataStore"],
                          ["Rollup.l1StakingContract meets Rollup.submitterContract"],
                          ["Rollup.legacyCutoverBatchIndex", "Rollup.submitterContract"], ["Rollup.l1StakingContract"]))
        self.assertEqual({k: g[k] for k in ("obligation", "question", "status")}, I.gap_meta("downgrade"))
        self.assertEqual([(r["from"], r["to"]) for r in vd["reverse"] if not r["compatible"]], [("V11", "V10")])
        self.assertFalse([lid for lid, x in i28_added_laws().items()
                          if re.search(r"(?i)downgrade|V11->V10", lid + json.dumps(x["statement"]))])


# ---------------------------------------------------------------------------------------------- V8: P5, P6
class TestInflight(unittest.TestCase):
    def test_inhabit_reproduces(self):
        """V8 (construction): holon versions inhabit --check exits 0."""
        holon_ok(self, ["versions", "inhabit", "--check"])

    def test_p5_every_mig_edge_of_the_path_is_inhabited(self):
        """I28-P5 (G11V): results/M3/versions/inflight.json has one entry per MIG edge of the path (8), in path order. Each
        trace (at most the sidecar's 12 steps) ends with a successful call of a successor site's action of the edge's
        source version and the successful migration along the edge (by upgradeToAndCall with its reinitializer when it
        has one; at V10->V11 initialize4 with the binding's submitter stand-in and the key as the cutover index); its key
        is the index its last commit writes (tests_m3/_i28.py::commit_key); its legacy words are
        tests_m3/_i28.py::inflight_words at the key, every word nonzero (at V10->V11: batchDataStore[k].
        signedSequencersBitmap and l1StakingContract); each INHABIT.bend has V8's shape for its trace and legacy words
        (tests_m3/test_versions.py::inhabit_shape_problems: s_0 is VM.vr0(), every x_i carries its trace step's arguments
        decoded from the calldata and, for a call, its caller, every migration is the proxy admin's, and reach is the
        canonical chain), imports the model under gen/M3/versions/models/, declares no law, holds no escape hatch and is
        accepted by Bend (and BendTT when the verdict is enabled), as its record says; and holon gate --milestone M3
        --checks G11V reports the clause with 8 of 8 edges inhabited, whatever its other items say."""
        item(KEY, "I28-P5")
        doc = load_json(need(INFLIGHT))
        self.assertEqual(doc["inflight_version"], "holon-inflight/0.1")
        edges = basis()["edges"]
        side = load_json(SIDECAR)
        stand_in = word_arg(load_json(ROOT / DEPLOYMENT)["calls"][0]["data"], 0)
        abi, admin = document_abi(), proxy_admin()
        self.assertEqual([x["edge"] for x in doc["edges"]], [f"{e['from']}->{e['to']}" for e in edges])
        for x, e in zip(doc["edges"], edges):
            with self.subTest(edge=x["edge"]):
                a, b = e["from"], e["to"]
                self.assertLessEqual(len(x["trace"]), side["search"]["inflight"]["max_trace"])
                last, mig = x["trace"][-2], x["trace"][-1]
                self.assertEqual((last.get("kind"), last.get("version"), last.get("ok")), ("call", a, True))
                self.assertIn(last.get("action"), SUCCESSORS[a])
                self.assertEqual((mig.get("kind"), mig.get("label"), mig.get("ok")), ("migrate", f"{a}->{b}", True))
                self.assertEqual(mig.get("call"), e["introduced"][0]["name"] if e["introduced"] else None)
                self.assertEqual(num(x["key"]), I.commit_key(last["calldata"]))
                if mig.get("call") == "initialize4":
                    self.assertEqual((word_arg(mig["calldata"], 0), word_arg(mig["calldata"], 1)), (stand_in, num(x["key"])))
                want = I.inflight_words(ROOT, a, b, num(x["key"]))
                fields = ("entry", "reads", "slot", "base", "offset", "path")
                self.assertEqual([{k: w[k] for k in fields} for w in x["legacy"]], [{k: w[k] for k in fields} for w in want])
                self.assertTrue(all(num(w["word"]) != 0 for w in x["legacy"]), x["legacy"])
                self.assertEqual((x["bend"]["exit_code"], x["bend"]["marker"]), (0, "ALL PROOFS CHECK"))
                f = need(f"gen/M3/versions/inflight/{a}_{b}/INHABIT.bend")
                text = f.read_text()
                self.assertEqual(re.findall(r"(?<![\w.])law\s+[A-Za-z0-9_.]+\s*:", code_only(text)), [])
                self.assertEqual(ESCAPES.findall(code_only(text)), [])
                imp = re.search(r"(?m)^import\s+(\S+)\s+as\s+VM\s*$", text)
                self.assertTrue(imp, "no `import .. as VM`")
                self.assertEqual((f.parent / imp.group(1)).resolve().parent, (ROOT / MODELS).resolve())
                self.assertEqual(inhabit_shape_problems(text, x["trace"], x["legacy"], abi, admin), [])
                bend_accepts(self, f)
                if holon_module("holon.bend").verdict_enabled():
                    self.assertEqual((x["verdict"] or {}).get("exit_code"), 0, x.get("verdict"))
        cut = next(x for x in doc["edges"] if x["edge"] == "V10->V11")
        self.assertEqual(sorted(w["reads"] for w in cut["legacy"]),
                         ["Rollup.batchDataStore.signedSequencersBitmap", "Rollup.l1StakingContract"])
        repo = copy_repo()
        try:
            rep = repo.parent / "gate_i28.json"
            run_holon(["gate", "--milestone", M3, "--root", str(repo), "--report", str(rep), "--checks", "G11V"],
                      cwd=repo, timeout=7200)
            detail = ((load_json(rep).get("checks") or {}).get("G11V") or {}).get("detail", "") if rep.exists() else ""
            self.assertIn("in-flight: 8 of 8 edges inhabited", detail)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_p6_the_cutover_inhabitant_replays(self):
        """I28-P6: the cutover's inhabitant (V10->V11) replays on the real code: its run in the replay report passed over the
        inhabitant's trace (every step's statuses and revert data agree, and so do the words at the real slots either side
        writes); the legacy words read on the real chain before the upgrade are the inhabitant's; and after the real
        upgradeToAndCall(V11, initialize4) the real batchDataStore(k) getter returns the legacy bitmap's low 160 bits as
        its submitter, and submitterContract() returns initialize4's first argument."""
        item(KEY, "I28-P6")
        rep = load_json(need(REPLAY))
        r = run_named(rep, "inflight:V10->V11")
        self.assertTrue(r["passed"], r)
        cut = next(x for x in load_json(need(INFLIGHT))["edges"] if x["edge"] == "V10->V11")
        self.assertEqual(r["trace"], cut["trace"])
        for st in r["steps"]:
            self.assertEqual(st["model"], st["real"])
            self.assertEqual(*revert_data(st))
            self.assertEqual([num(s["model"]) for s in st["slots"]], [num(s["real"]) for s in st["slots"]])
        self.assertEqual({w["reads"]: num(w["real"]) for w in r["legacy"]},
                         {w["reads"]: num(w["word"]) for w in cut["legacy"]})
        bitmap = next(num(w["word"]) for w in cut["legacy"] if w["reads"].endswith(".signedSequencersBitmap"))
        after = {x["entry"]: x for x in r["after"]}
        self.assertEqual(sorted(after), ["Rollup.batchDataStore", "Rollup.submitterContract"])
        self.assertEqual((after["Rollup.batchDataStore"]["getter"], [num(a) for a in after["Rollup.batchDataStore"]["args"]]),
                         ("batchDataStore", [num(cut["key"])]))
        self.assertEqual(num(after["Rollup.batchDataStore"]["real"][3]), bitmap & LOW160)
        mig = cut["trace"][-1]
        self.assertEqual(after["Rollup.submitterContract"]["getter"], "submitterContract")
        self.assertEqual(num(after["Rollup.submitterContract"]["real"][0]), word_arg(mig["calldata"], 0))


# ---------------------------------------------------------------------------------------------- generic code, S1-S3
class TestGenericCode(unittest.TestCase):
    def test_s1_s3_the_analysis_is_generic(self):
        """S1-S3 (construction): holon versions analyze --facts over each planted document gives
        tests_m3/_i28.py::analysis_doc over it (no downgrade gap)."""
        tmp = Path(tempfile.mkdtemp(prefix="i28-s-"))
        try:
            for kind in ("renamed", "no_chain", "no_root"):
                with self.subTest(planted=kind):
                    p = tmp / f"{kind}.json"
                    p.write_text(json.dumps(I.planted(kind), indent=2, sort_keys=True))
                    out = tmp / f"{kind}.analysis.json"
                    holon_ok(self, ["versions", "analyze", "--facts", str(p), "--out", str(out)])
                    self.assertEqual(load_json(out), json.loads(json.dumps(I.analysis_doc({"V0": (p, None)}, []))))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_new_code_names_no_target(self):
        """Construction (AGENTS rules 2 and 4): holon/rules/par_init.py and every module under holon/versions/, and every line
        that commits of I28's own add under holon/, name no action, storage family or contract of the head document, no
        I28 law, init or gap id, no interface the gaps name and not the model's name (the sidecar's); no file under holon/
        imports tests_m3 or names tests_m3/_i28.py; no commit of I28's own changes one of the six files of the
        holon-ir/0.1 closure."""
        files = [ROOT / "holon" / "rules" / "par_init.py"] + sorted((ROOT / "holon" / "versions").glob("*.py"))
        for f in files:
            self.assertTrue(f.is_file(), f"{f.relative_to(ROOT)} is missing (I28 builds it)")
        head = load_json(ROOT / I.HEAD_DOC)
        names = {a["name"] for a in head["actions"]} | {s["name"] for s in head["storage"]} | {head["contract"]}
        names -= {"owner", "paused", "receive", "initialize", "verifier"}
        names |= {LAW, INIT_ID, LINK_GAP, DOWNGRADE_GAP, "IL1MessageQueue", "morph_rollup"}

        def hits(text: str) -> list:
            return sorted(n for n in names if re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", text))
        for f in files:
            with self.subTest(file=str(f.relative_to(ROOT))):
                self.assertEqual(hits(f.read_text()), [])
        own = own_commits()
        for c, changed in own:
            added = [ln[1:] for ln in git("show", "--format=", "--unified=0", c, "--", "holon/").splitlines()
                     if ln.startswith("+") and not ln.startswith("+++")]
            with self.subTest(commit=c[:12]):
                self.assertEqual(hits("\n".join(added)), [])
        for p in sorted((ROOT / "holon").rglob("*.py")):
            t = p.read_text(encoding="utf-8", errors="replace")
            with self.subTest(file=str(p.relative_to(ROOT))):
                self.assertNotRegex(t, r"(?m)^\s*(from|import)\s+tests_m3\b")
                self.assertNotIn("_i28", t)
        rec = holon_module("holon.records")
        v01 = set(rec.generator_files("holon-ir/0.1", ROOT))
        self.assertEqual(len(v01), 6)
        self.assertEqual([n for _, changed in own for n in changed if n in v01], [])


# ---------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    def test_r1_earlier_m3_laws_change_only_in_the_catalog(self):
        """I28-R1: no commit of I28's own deletes an M3 law or record, changes an M3 law file that exists at its parent in
        anything but rule_catalog_version (each such law then named by a catalog_rederivation line of
        laws/STATEMENT_DIFF.jsonl into that catalog), or changes the status of an M3 record that exists at its parent.
        Needs the real checkout's history: a missing .git is a failure, never a skip."""
        item(KEY, "I28-R1")
        prereg_commit()
        log = [json.loads(x) for x in (ROOT / "laws" / "STATEMENT_DIFF.jsonl").read_text().splitlines() if x.strip()]
        rederived = {(e.get("law_id"), e.get("new_catalog")) for e in log if e.get("kind") == "catalog_rederivation"}
        lawf, recf = re.compile(r"^laws/M3/L[^/]*\.json$"), re.compile(r"^results/M3/L[^/]*\.json$")
        for c, names in own_commits():
            for n in names:
                if not (lawf.match(n) or recf.match(n)):
                    continue
                with self.subTest(commit=c[:12], path=n):
                    old, new = show(f"{c}^", n), show(c, n)
                    if old is None:
                        continue
                    self.assertIsNotNone(new, "deleted")
                    if lawf.match(n):
                        self.assertEqual({k: v for k, v in old.items() if k != "rule_catalog_version"},
                                         {k: v for k, v in new.items() if k != "rule_catalog_version"})
                        if old.get("rule_catalog_version") != new.get("rule_catalog_version"):
                            self.assertIn((n.rsplit("/", 1)[1][:-5], new["rule_catalog_version"]), rederived)
                    else:
                        self.assertEqual(new.get("status"), old.get("status"))

    def test_r2_own_commits_touch_nothing_forbidden(self):
        """I28-R2: no commit of I28's own writes a frozen root, I63's outputs or instruments, spec/M1/, spec/M2/, an
        earlier M3 sidecar (spec/M3/lib/ but versions*; spec/M3/lib/lean_promoted.json only in a commit that changes
        nothing else), holon/sorts/, gen/M3/sorts/, gen/M3/theory/, laws/T32/, gen/T32/, results/T32/summary.json,
        gen/M3/disch/classification.json, laws/M0-M2, gen/M0-M2, replay/M0-M2 or results/M0/; and every results/M1,
        results/M2 or results/T32 record such a commit changes differs from its parent only in generator_sha256 and keys
        named seconds. Needs the real checkout's history."""
        item(KEY, "I28-R2")
        forbidden = ("facts/", "predictions/", "schemas/", "tests/", "bend/probes/", "AGENTS.md", "tools/freeze.py",
                     "docs/M0_SPEC.md", "docs/BEND_PRIMER.md", "FROZEN.sha256", "gen/M3/history/", "results/M3/history/",
                     "tests_m3/_i63.py", "spec/M1/", "spec/M2/", "holon/sorts/", "gen/M3/sorts/", "gen/M3/theory/",
                     "laws/T32/", "gen/T32/", "results/T32/summary.json", "gen/M3/disch/classification.json",
                     "laws/M0/", "laws/M1/", "laws/M2/", "gen/M0/", "gen/M1/", "gen/M2/",
                     "replay/M0/", "replay/M1/", "replay/M2/", "results/M0/")
        sidecars = re.compile(r"^spec/M3/lib/(?!versions)")
        rec = re.compile(r"^results/(M1|M2|T32)/(?:extracted_m1/)?L[^/]*\.json$")

        def strip(x):
            if isinstance(x, dict):
                return {k: strip(v) for k, v in x.items() if k not in ("seconds", "generator_sha256")}
            if isinstance(x, list):
                return [strip(v) for v in x]
            return x
        for c, names in own_commits():
            with self.subTest(commit=c[:12]):
                self.assertEqual([n for n in names if n.startswith(forbidden)], [])
                if names != ["spec/M3/lib/lean_promoted.json"]:
                    self.assertEqual([n for n in names if sidecars.match(n)], [])
                for n in names:
                    if rec.match(n):
                        self.assertEqual(strip(show(c, n)), strip(show(f"{c}^", n)), n)


# ---------------------------------------------------------------------------------------------- the re-make
class TestReMake(unittest.TestCase):
    def test_the_re_make_reached_every_m1_m2_and_t32_record(self):
        """Construction (the contract's Re-make): at I28's end (end_commit: M^2, M the build merge chosen by ancestry from
        the commit adding the report; HEAD before M exists) every record directly under results/M1, results/M2 and
        results/T32 carries a generator_sha256 other than at the prereg, one value per milestone, and laws/T32, gen/T32 and
        results/T32/summary.json are the prereg's."""
        c = prereg_commit()
        end = end_commit()
        for ms in ("M1", "M2", "T32"):
            names = [n for n in git("ls-tree", "--name-only", f"{end}:results/{ms}").split()
                     if n.startswith("L") and n.endswith(".json")]
            new = {n: (show(end, f"results/{ms}/{n}") or {}).get("generator_sha256") for n in names}
            old = {n: (show(c, f"results/{ms}/{n}") or {}).get("generator_sha256") for n in names}
            with self.subTest(milestone=ms):
                self.assertTrue(names)
                self.assertEqual(len(set(new.values())), 1, sorted(set(map(str, new.values()))))
                self.assertEqual([n for n in names if new[n] == old[n]], [])
        for rel in ("laws/T32", "gen/T32", "results/T32/summary.json"):
            with self.subTest(unchanged=rel):
                self.assertEqual(git("rev-parse", f"{end}:{rel}"), git("rev-parse", f"{c}:{rel}"))


if __name__ == "__main__":
    unittest.main()
