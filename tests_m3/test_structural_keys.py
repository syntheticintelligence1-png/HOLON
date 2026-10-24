"""I68: structural storage keys in the M3 model (the Q21 fix: docs/HUMAN_ANSWERS.md, Q21, I30's Question 1; BUILD_PLAN
row I68). This docstring is the contract.

Scope. The M3 model (holon.sorts.model3) keeps the contract's storage as raw slots, and computes a mapping value's
slot as h_get(kh, key ++ slot), a lookup in the law's keccak256 table parameter. Every M3 typed law quantifies that
table (binder keccak256: Fn<Bytes,Word>), so a law must hold for every finite table, including the empty one, where
every mapping slot is 0 + member and aliases slot 0. That makes true laws false (I30 Q1: the toy's tag_exact law) and
leaves frames over mapping state with no proof route (I31's 14 UNKNOWN blocking laws). The human's answer to Q21:
the M3 model keys compiler-generated mapping storage structurally, as (base slot, key path); the evaluator maps a
structural key to its real slot with the real keccak256 only where it compares with real traces (R5) and in replay;
a raw sload/sstore at a computed slot stays a raw slot; a generated check tests every raw slot against the real-slot
image of every structural key the model touches, a collision being a finding; the idealisation is the named model
assumption A-keccak-structural, validated by every R5 storage comparison; the law statements do not change. I68
implements that answer through the model, its evaluator, its deployment, its search and its sections, and the proof
routes it opens: the SK frame library, the DISCH routes' key split and convoy over SK, loop frames, and the tag_exact
proof class for SORT tag laws.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl): tests_m3/_i68.py (rules S2's real-slot mapping, S5's classification and S7's keys check,
independently of holon/).

S1 The store. holon.sorts.prelude3 gains, for the typed model and its sections:
     type SP is Data: SP_m{k: W, o: W}                one hashed step: the mapping key word, then the slot offset;
     type SK is Data: SK{b: W, o: W, p: List<&2, SP>}  a location: base slot, offset in the top-level variable, path;
     sp_eq(a, b) (offsets first, then keys), sps_eq, sk_eq(a, b) (base first, then offset, then path);
     type KV is Data: KV{k: SK, v: W};  HSt{sl: List<&2, KV>};
     sload(s: HSt, +k: SK) -> W, the first entry whose key sk_eq's k, else w0(); sstore(s, +k: SK, +v: W) -> HSt, the
     A30 shape of kw_put/kw_set over KV; HOut's touched list tw: List<&2, SK>.
   W, w_eq, KW and kw_get/kw_put/kw_set (the environment's balance table), HKB and h_get (code-level hashes) keep their
   text, so F32's eight pinned helpers keep theirs (tests_m3/test_eqprove.py). MODEL3_VERSION is holon-model-m3/0.3,
   and the model header names its storage: "structural keys (A-keccak-structural)".
S2 Canonical keys. Every compiler-generated access to one real slot compiles to one SK:
   - a scalar at slot b: SK{W{b}, w0(), Nil}, masked at its byte offset as today (byte offsets stay outside the key);
   - a top-level struct member m: SK{W{b}, W{m.slot}, Nil}; a top-level static array of words at index i:
     SK{W{b}, w_mul(i, n), Nil} (sub-word elements stay a GenError);
   - a mapping value at key k: SK{W{b}, w0(), [SP_m{clean(k), w0()}]}, clean(k) the key word as solc hashes it
     (holon.sorts.model3.key_bytes's rule applied to the word: narrow keys masked, bytesN left-aligned);
   - a mapping value's struct member m: SK{W{b}, w0(), [SP_m{clean(k), W{m.slot}}]}, masked at m.offset;
   - a nested mapping m[k1][k2]: SK{W{b}, w0(), [SP_m{clean(k1), w0()}, SP_m{clean(k2), w0()}]}; a mapping value's
     static array element i: SK{W{b}, w0(), [SP_m{clean(k), W{i*n}}]};
   - a whole-struct write or delete: one SK per member from the key word, bound once.
   The offset word is always present (w0() when none), so m[k][0] and m[k][i] with i = 0 are one key by w_eq. No
   storage key of any M3 model (the typed model, its untyped twin, the DISCH, UNDO and FACT sections) contains h_get.
   The real slot of SK{b, o, p}: s = b + o, then for each step SP_m{k, o2}: s = keccak256(pad32(k) ++ pad32(s)) + o2,
   all mod 2**256 (holon.sorts.skeys.real_slot, and the instrument's real_slot).
S3 Raw slots. A raw ["sload", r] or sstore at r compiles to SK{r, w0(), Nil}, the key of a scalar at literal slot r.
   On the Rollup the only raw access is initialize4's read of the EIP-1967 admin slot.
S4 Storage modes (option A1 of the Q21 design). holon.sorts.model3 compiles storage in one of two modes: structural
   (the typed model and every section built from it) and raw (the mode it has today), which I28's versioned generator
   (holon/versions) passes, so I28's outputs stay byte-identical and its records carry no A-keccak-structural. The
   untyped M3 twin (gen/M3/sorts/models, typed off) is structural too.
S5 The deployment. s0 is converted from the deployment's captured raw slots (gen/M3/sorts/models/*.init.json, from
   holon.sorts.deploy3) with the preimages the capture records: a captured slot of a top-level variable becomes its
   literal key, a slot that is keccak256(k ++ b) + o2 for a recorded 64-byte preimage k ++ b whose b is a mapping
   family's base becomes SK{W{b}, w0(), [SP_m{k, W{o2}}]}, and any other captured slot stays raw (SK{r, w0(), Nil}).
   On the Rollup's capture: 9 literal, 7 structural, 2 raw (the EIP-1967 implementation and admin slots). The real
   image of s0 (every key mapped by real_slot) is the captured storage exactly.
S6 The evaluator (holon.sorts.evaluate3, holon/js/eval3.mjs) maps keys to real slots with the real keccak256 only:
   in R5's pre-state fixpoint and write comparison; in the replays (holon.disch.run's, holon.refute_m3's direct tests,
   which read real words at B's slots); in the deployment conversion (S5); and in the search's heuristics (candidates
   only). The model and its proofs never use it. The search offers the structural keys' key words where it offered
   slot preimages (I31's pool).
S7 The keys check. holon.sorts.skeys writes gen/M3/sorts/keys.json: every raw slot, every literal slot and the real
   image of every structural key that the deployment, the R5 corpus and every committed witness and inhabitant of an
   M3 typed record touch. A raw or literal slot equal to a structural image, or two different structural keys with
   one image, is a collision: a finding, listed, never an assumption. The committed check lists none.
S8 The ledger. A-keccak-structural enters the ledger through spec/M3/ledger.json, introduced by SK, sk_eq and the
   store's definitions (sload, sstore, kv_*). spec/M2/ledger.json does not change. Every record over a structural model
   lists it (SORT and DISCH records in model_assumptions, UNDO and FACT records in ledger_assumptions); no M0-M2 record,
   no PAR record and no record over I28's raw versioned machine does.
S9 The SK frame library (holon/disch/lemmas.py and order.py, fixed text emitted and checked with each proof file):
   sp_self, sps_self, sk_self (sk_eq is reflexive), sp_refl, sps_refl, sk_refl (sk_eq true implies equal keys),
   sst_same (a store at k is read back at k) and sst_frame (a store at k1 leaves k2 when sk_eq is false both ways),
   plus the ghost-map twins. The DISCH routes (holon/disch/proofs.py, section.py, mirror.py) prove frames over SK: by
   evaluation across families and members; by a key split on w_eq of the program's own key words within a family;
   carrying each passed check's equation down an action's chain (the convoy); and through loops whose stores avoid
   B's keys (loop frames). The refusals "B reads a slot that is not a literal" and "a store goes through the law's
   keccak256 parameter" are gone; a route that does not apply still leaves its law UNKNOWN, naming what it lacks.
S10 tag_exact (holon/sorts/tag_exact.py): a SORT tag law (I30) whose coercion follows from an invariant of the form
   "for every key k, F[k] != 0 implies companion[k] == member_fn(V[k])" over the structural store is proved by a Reach
   induction: the invariant at s0 by computation, one step lemma per action (a key split for the actions that write
   F or V, a frame by evaluation for the others), and the coercion at the hit from the guard's equation and the
   invariant; with a checked reachable inhabitant. A law whose invariant is not inductive stays UNKNOWN, naming the
   failing step lemma.
S11 The lifecycle (Q21's H1). The 51 M3 typed laws' statements, law files, REGISTRY.json, DERIVATION.json and every
   LAWS.bend are unchanged; only their bound models' cones change, and no extensional equivalence can exist (the
   store's type and its aliasing differ by design). holon.statement_diff gains the kind remodel, accepted unsigned only
   when all of these hold mechanically: (a) the law file, the emitted statement and counter-law and the model path are
   unchanged, only the cone differs; (b) the entry names the human answer that licenses the remodel (Q21), the model
   versions (holon-model-m3/0.2 to holon-model-m3/0.3) and the ledger entry it adds (A-keccak-structural); (c) the new
   model regenerates byte for byte from the pinned generators and inputs; (d) the new model's R5 record on the frozen
   I20 corpus has I20's counts and 0 disagreements, and the keys check lists no collision; (e) the law's record is
   remade on the new model (a status change is an outcome, never a statement change). `holon bind` rebinds the 51 laws
   through remodel entries, and G2 accepts them. Whether this channel stands is the human's to confirm (Question H1).
S12 Regenerated, never hand-written, by this recipe, after I28's build is on the lead:
   - holon sorts --milestone M3 (the typed model, its untyped twin, types, taint, term sizes), holon.sorts.skeys
     (gen/M3/sorts/keys.json), the DISCH, UNDO and FACT sections and their models;
   - the R5 record (gen/M3/sorts/refinement or wherever I30 writes it) on the frozen I20 corpus;
   - holon run --milestone M3 for the 51 typed laws (SORT 3, DISCH 35, UNDO 8, FACT 5), their records and their
     replays; holon bind (51 remodel lines); holon refute --milestone M3 --only filter; holon metrics --milestone M3;
   - every M1, M2, T32 and PAR record in generator_sha256 and seconds alone (the holon-ir/0.2 and 0.3 closures and
     I32's hold holon/sorts and holon/disch);
   - the toy T30's models and records (tests_m3/fixtures), where I30's tests build them.
S13 Earlier tests, amended in this prereg's pull request and logged, each narrowed to I68's outcomes: I43-R1
   (statuses and pinned .bend files of the typed records), I32-R2 (closure edits after its prereg), I30's R6 toy
   clause (the tag_exact law decided), and the tests that pin the typed model's raw store text. No other earlier test is
   amended: one that fails on I68's outcomes is a miss, reported.
"""
