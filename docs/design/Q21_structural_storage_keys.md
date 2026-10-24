# IQ21 design: structural storage keys in the M3 model (Q21)

Base `fde1f819`, worktree `/home/user/HOLON-i36` (read only). "IQ21" is a placeholder key; the orchestrator assigns
the number. Human answer: `docs/HUMAN_ANSWERS.md:36` (Q21, I30 Q1).

**What was done for this note.**
- Reading only, plus scratch probes under `/tmp/claude-0/-home-user-HOLON/36cc748b-c392-5d49-873b-8207b8fa8fb5/scratchpad/q21/`.
- No worktree was edited. Nothing was committed or pushed.
- No generator, refuter, gate or forge ran on the subject.
- The two programs dumps (`probe/programs.txt`, the toy's) were made with `holon.machine.load_extracted`, which only
  reads the documents.
- The Bend probes (Appendix A) are self-contained files, checked with `BEND_NO_TELEMETRY=1` in bend2 and in BendTT
  (`--verdict`).
- Every per-law outcome below is a *reading* of the code and the committed records, not a run. The prereg must
  disclose it as such.

---

## 0. Summary

### The design in ten lines

1. **Storage becomes a finite map from structural keys to words.** A key is `SK{b, o, p}`:
   - `b` is the family's literal base slot (the compiler's layout);
   - `o` is the slot offset inside a top-level variable;
   - `p` is the list of hashed steps. A step is `SP_m{key word, slot offset}`. `SP_d` (a dynamic array's data) and
     `SP_b` (a bytes or string key) are reserved for I36.
2. **`sload` and `sstore` compare keys with `sk_eq`.** It checks the base first, then the offset, then the path, and
   within a step the offset before the key. No storage location goes through the keccak256 table any more. The law's
   `keccak256` binder now reaches code-level hashes only: about 80 of the model's 377 `h_get` uses. The other 295 are
   slot lookups and disappear.
3. **A raw `sload`/`sstore` at slot r compiles to `SK{r, 0, []}`.** That is the same key as a scalar at literal slot
   r. On the Rollup the only raw access is `initialize4`'s read of the EIP-1967 admin slot.
4. **s0 is converted from the deployment's captured raw slots,** using the preimages the capture already records.
   - The Rollup's 18 slots split into 9 literal, 7 structural and 2 raw (EIP-1967 implementation and admin).
   - The image of s0 must reproduce the captured storage exactly.
5. **The evaluator maps a structural key to its real slot with the real keccak256 in four places only:**
   - R5: the pre-state fixpoint, and the write comparison;
   - the replays: the DISCH replay and `refute_m3`'s direct tests, which read real words at B's slots;
   - the deployment conversion;
   - the search's EV heuristics, which are candidates only.

   The model and its proofs never use it.
6. **A generated keys check lists every raw slot and the real image of every structural key** that the deployment,
   the R5 corpus and every witness touch. A collision is a finding, never an assumption.
7. **`A-keccak-structural` enters the ledger** through a new `spec/M3/ledger.json` extension, introduced by `SK`,
   `sk_eq` and the store's other definitions.
   - SORT and DISCH records then list it in `model_assumptions`; UNDO and FACT records list it in
     `ledger_assumptions`.
   - R5 validates it empirically, 8894 comparisons at a time.
8. **A fixed SK frame library replaces the refusals "no frame over hashed slots".**
   - The library: `sk_self`, `sk_refl`, `st_same` and `st_frame` over SK.
   - Three generated pieces sit on top: key splits, the convoy (each passed check's equation, carried down the chain)
     and loop frames.
   - The library and a Reach induction over it check in both kernels (Appendix A).
9. **`tag_exact` is built on the same machinery.** It is a Reach induction of the invariant "F[k] ≠ 0 implies
   companion[k] = member_fn(V[k])".
10. **Statements do not change, and that creates a gate problem.** `laws/M3`, REGISTRY, DERIVATION and every
    `LAWS.bend` stay byte-identical. Only the 51 typed-model laws' cones change. **G2 has no channel for a
    meaning-changing model rebuild** (H1).

### What a law over mapping state may rely on after IQ21 (for I33; §2.6)

- **Distinct key paths are distinct storage locations, by construction.** No table and no premise are involved.
- **A missing key reads 0, and no other entry answers for it.** Two absent batch keys never share a slot.
- **The frame facts**, all checked in both kernels in scratch:
  - across families, by evaluation;
  - across members of one entry, by evaluation;
  - same family, from `w_eq(k1, k2) == False` about the program's own key words;
  - a case split on key equality otherwise.
- **What becomes unnecessary in I33's work list:** W3 entirely (`h_get` presence, preimage disequality, `sep`, `dep`,
  slot ranges); W4's frames over hashed slots; W9's `present`/`sep` premises.
- **What IQ21 builds for I33:** W6's symbolic slot keys and its convoy, and loop *frames*.
- **What I33 keeps:** W1 (Word↔Nat), W2 (packed byte, unless IQ21 bundles the bit-field lemmas), W5(ii) (the +W loop
  transport) and W7-W10.

### Blast radius (headline)

- **The models and the 51 records over them are remade.** That is the typed model, its untyped twin, the DISCH, UNDO
  and FACT sections, and the records: 3 SORT, 35 DISCH, 8 UNDO and 5 FACT.
- **The 80 PAR records and every M1/M2 record change in `generator_sha256` only.** The 0.2/0.3 closures hold
  `holon/sorts/*`, `holon/disch/*` and `holon/records.py`.
- **Regenerated:**
  - the R5 record;
  - the replays (sorts, disch, undo, fact);
  - I40's M3 concretization and filter outputs;
  - `types.json`/`taint.json`, `term_size.json`, metrics, summary and deps.
- **The 51 typed-model laws need rebinding.** No extensional equivalence can exist, so this is H1.
- **Earlier tests need amendment lines or re-baselining** (§4.3):
  - I43-R1: statuses and 507 pinned `.bend` files;
  - I32-R2: closure edits after its prereg;
  - I28's prereg V6, which names model3's *raw* storage.
- **The F32 helpers and I62-D3's ledger pin are avoided by design.**

### Predicted outcomes (core scope, §5)

- **I30-R6's toy clause passes.** `L_sort_tag_toytypes_83_33f98e53` is PROVED by `tag_exact` with an inhabitant. The
  other four toy laws are decided as designed, and the guard mutation is REFUTED. I30-R6 as a whole (it includes
  `test_gate_m3_passes`) still fails unless H1 is ruled and G11V's `_initialized >= 4` inhabitant is found.
- **I31's 14 UNKNOWN blocking laws: 12 PROVED, 2 UNKNOWN.**
  - PROVED: 77 ×3, 132 ×4, TI3, TI4, 213 ×2 and 228.
  - UNKNOWN: TI2 (a packed-slot update; PROVED if the bit-field lemmas are bundled) and 363_anyone (it needs a
    monotone transport). Neither is REFUTED.
  - `rev_rollup_363` also becomes PROVED.
  - DISCH: 13/7/15 → **26/7/2** (27/7/1 with the bit-field lemmas).
- **No other M3 status changes.** No PROVED law relied on keccak-as-parameter.

### Top risks (§6.3)

1. G2 has no channel (H1).
2. `tag_exact` is the first Reach induction on the M3 word model. It needs loop frames and the convoy.
3. BendTT's fuel on long mirrored chains (cBWP, finalizeBatch).
4. Search drift: the slot preimages leave the candidate pool unless they are re-offered.
5. Canonical-form holes on constructs the Rollup lacks (I36's arrays).
6. The coupling to I28's versioned machine.

### Order

- **Working assumption: after I28's build.**
  - IQ21 then keeps model3's raw mode for I28's versioned generator, or I28's still-uncommitted prereg rewords V6 to be
    storage-agnostic now.
  - IQ21 re-makes the 51 typed records once. Any earlier re-make of them (I28's statement-hash pass, a pending F40) is
    superseded, so it should be cheap (`--resume`) or folded in.
- **Cheapest overall: IQ21 before I28's build.** There is then one conversion and one re-make, but it delays I28 by an
  iteration.

---

## 1. Today's storage model on M3 (question 1)

### 1.1 How a slot is computed and stored

**The store is a raw slot list.** `HSt{sl: List<&2, KW>}` with `KW{k: W, v: W}` (`holon/sorts/prelude3.py:521-558`).
- `sload` is `kw_get` (the first matching entry, else `w0()`).
- `sstore` is `kw_put` (it updates the first match, or appends).
- The touched list is `HOut.tw: List<&2, W>` (`prelude3.py:659-660`).

**A mapping slot is a lookup in the law's keccak256 table.** `Gen.locate` (`holon/sorts/model3.py:555-589`) folds the
access path over the family's literal slot. A `map` accessor becomes
`h_get(kh, key_bytes(k) ++ b_of_w(slot))` (`:567`).
- `kh` is the table parameter: `List<&2, HKB>`, one per trace.
- `h_get` answers the first entry whose bytes equal the key, and **0 when there is none** (`prelude3.py:560-629`;
  model `morph_rollup_extracted.bend:844-848`).
- `key_bytes` cleans narrow keys exactly as solc does (`:544-553`).

**Members and indexes are added to the hashed word.**
- A struct member is `w_add(code, member.slot)` (`:570-579`).
- A static array index is `w_add(code, i)`, for word elements only. Sub-word and dynamic arrays are refused (`:580-588`;
  push `:1687`).

**Packed fields are masked.**
- Reads mask and shift: `read_word`, `:591-603`.
- Writes rewrite the slot as `w_or(w_and(sload(view, slot), ~mask), v << 8·off)`: `write_word`, `:614-628`.
- Struct writes bind `+k = {slot : W}` once and write each member at `w_add(k, m)` (`write_body`, `:1649-1690`).

**Raw slots.** `["sload", x]` is `sload(st, x)` (`:440-441`).

**Reach and s0.**
- The typed model's state is `GSt{st, companions}`.
- `Reach<-kh, -s: GSt>` is `R0 | RStep` over `gh_step(a, p, kh)` (`:2058-2061`; model `:14609`). Every step takes the
  same `kh`.
- `s0()` is the captured deployment as 18 literal `KW` entries (`s0_text`, `:2276-2278`; model `:13878-13880`).

**The laws state the table as a universally quantified binder.** Every M3 typed law has
`{"name": "keccak256", "q": "forall", "type": "Fn<Bytes,Word>"}`, for example
`laws/M3/L_disch_blk_rollup_363_e11d8bb2_anyone.json`. So a law must hold for **every** finite table, including `[]`,
where every mapping slot is `0 + member` and aliases `_initialized`'s slot 0.

**Size today.** The 979 KB typed model has 377 `h_get` uses. 295 of them are slot lookups: challenges 166,
batchBlobVersionedHashes 36, batchDataStore 34, committedBatches 30, committedStateRoots 10, batchChallengeReward 7,
isChallenger 5, finalizedStateRoots 5, withdrawalRoots 1.

### 1.2 Where else the hashed slot is baked in

| place | code | what it does |
|---|---|---|
| UNDO trace section | `holon/undo/trace.py:138-162` (`slots_of`, `base_slot`, `slot_i`) | a register's slot is `h_get(kh, key ++ slot)` "exactly as the typed model computes it" |
| FACT section | `holon/fact/section.py:108-123` (`reg_words`) | inherits `base_slot`; reads the commitment and member words |
| DISCH section | `holon/disch/section.py:61` (`_SLOAD_LIT`), `:82`, `:125-132` | B's slot keys are recognised only as `M.sload(st, M.W{..})` literals. B_228 (`finalizedStateRoots[0]`) and B_363 (`challenges[batchChallenged].startTime`) contain `h_get`, so `blk["v"]` is None (`gen/M3/disch/models/morph_rollup_extracted_disch.bend:641-647`, `:719-721`) |
| DISCH proofs | `holon/disch/proofs.py:287-288`, `:441-445`, `:447-451` | refuses "B reads a slot that is not a literal", "it stores at a slot that is not a literal … goes through the law's keccak256 parameter", and a non-literal store at B's slot (bit-field) |
| DISCH core lemmas | `holon/disch/lemmas.py:186-213` (`kw_fr_c`, `kw_frame`, `st_frame`), `holon/disch/order.py:256-291` (`st_same`) | the frame and transport facts over W keys only |
| evaluator (R5) | `holon/sorts/evaluate3.py:201-203` (`state_in`: real slots in), `:305-323` (`run_fix`: the keccak fixpoint over every key, slot preimages included), `:325-349` (`outcome`: `tw` slots out) | the real pre-state is passed as raw slots, and slots come back raw |
| JS driver | `holon/js/eval3.mjs:30-49` | hooks `h_get`, `hs_get` and `c_find` (the native tables) |
| search | `holon/sorts/search3.py:156-167` (deployment preimages into `kh`), `:305-312` (`learn`), `:350-355` (`state`: raw slot dict) | S1 offers "the words of the byte strings the deployment and the trace hashed", slot preimages included |
| deployment | `holon/sorts/deploy3.py:142-201` (`preimages`), `:226-233` (raw `storage`) | s0 is raw slots |
| DISCH replay | `holon/disch/run.py:722-790` | EV (real-slot evaluator) over the model's states (`mm.state(g)`) finds the slots B and c read, then dumps them from the harness |
| I40 direct tests | `holon/refute_m3.py:1143-1166` | the same, for the DISCH direct records' emitted tests |

### 1.3 Why induction over reachable states with mapping state fails

**Both failure modes are the universally quantified table.**

**(a) Aliasing makes ∀-laws false.**
- I30 Q1 (`docs/iterations/I30.md:338-349`): with `kh = []`, `[putg(1,2) with a blob, putg(5,1), keepg(1,1)]` violates
  the kept-register coercion. bend2 and BendTT both accept that counter-law (scratch, I30).
- I31 Q2 (`I31.md:366-374` and its review): for B reading `challenges[batchChallenged].startTime` or
  `finalizedStateRoots[0]`, "an adversarial hash table can alias a slot any step writes with B's", so blk_363 ×2,
  noext_363 ×2 and blk_228 "may not hold for every table".

**(b) Even true laws have no proof route.**
- A frame needs `w_eq(written slot, B's slot) == False`.
- For `h_get(kh, ..)` versus a literal slot, or versus another `h_get`, that is undecidable without a table premise,
  and AGENTS rule 2 forbids adding one.
- The I31 gap table (`I31.md:170-180`) lists mapping-slot stores as the blocker of blk 77 (3), 132 (4), 213 (2) and
  TI2/3/4 (finalizeBatch), and of noext 77/132/213. It lists "B reads a mapping slot" for blk 363 (both) and 228.
- The other two gaps are separate:
  - loops: the mirror refuses `lq_..`;
  - packed slots: no bit-field lemmas.

**(c) What the proofs need.** Structural keys deliver every item on this list except the last two, which are separate
deliverables.
- Distinct keys or families are distinct locations.
- A store at one location leaves every other location's word.
- A read at the stored key gives the stored word.
- A missing key reads 0.
- The deployment state is stated without a table.
- Loops can be followed.
- Byte fields of a packed word can be reasoned about.

---

## 2. The structural design (question 2)

### 2.1 Types and the store

The following is the probe's text (`bendprobe/skmodel.bend`, appended to the real `PRELUDE`). It checks in bend2.

```python
type SP is Data:                       # one hashed step: the mapping key word, then the slot offset inside the value
  SP_m{k: W, o: W}                     # (IQ21 emits only SP_m; SP_d{o} = a dynamic array's data, SP_b{kb, o} = a
                                       #  bytes/string key are added when I36 needs them)
type SK is Data:                       # a location: base slot of the family, offset in the top-level variable, path
  SK{b: W, o: W, p: List<&2, SP>}

def sp_eq(a: SP, b: SP) -> Bool:       # offset first: two members of one entry differ by evaluation, key symbolic
  match a b:
    case SP_m{ak, ao} SP_m{bk, bo}:
      Bool.and(w_eq(ao, bo), w_eq(ak, bk))
def sk_eq(a: SK, b: SK) -> Bool:       # base first: two families differ by evaluation whatever their keys
  match a b:
    case SK{ab, ao, ap} SK{bb, bo, bp}:
      Bool.and(w_eq(ab, bb), Bool.and(w_eq(ao, bo), sps_eq(ap, bp)))
type KV is Data:
  KV{k: SK, v: W}
type HSt is Data:                      # HSt keeps its name: every consumer's type still says HSt
  HSt{sl: List<&2, KV>}
def sload(s: HSt, +k: SK) -> W         # kv_get: first entry with sk_eq, else w0()  (A30 shape: no reusable list binder)
def sstore(s: HSt, +k: SK, +v: W) -> HSt   # kv_put/kv_set, the A30 shape of kw_put
```

**Kept unchanged:**
- `W`, `w_eq`, `KW`, `kw_get`/`kw_put`/`kw_set` (still the env balance table), `HKB` and `h_get` (code-level hashes).
- This keeps F32's eight pinned helpers' text (`tests_m3/test_eqprove.py:34`) and passes.

**Changed:**
- `HOut.tw` becomes `List<&2, SK>`.
- `MODEL3_VERSION` becomes `holon-model-m3/0.3`.
- The model header names the storage: "structural keys (A-keccak-structural)".

**Canonical form.** The rule that keeps the model faithful is that every compiler-generated access to one real slot
yields the same SK.
- Member slot offsets and index × element-slots are summed into the step's (or top-level) offset word, which is
  **always present**, possibly `w0()`. So `m[k][0]` (a literal 0) and `m[k][i]` with i = 0 are the same key by
  `w_eq`.
- Key words are *cleaned* as solc hashes them (address keys masked to 160 bits, bytesN left-aligned). This is
  `key_bytes`'s rule applied to the word.
- Byte offsets of packed fields stay outside the key: one key per slot, with masks at read and write time.
- Each real slot of the layout belongs to exactly one top-level variable, and solc's bounds checks (Panic 0x32,
  recorded as checks under A-implicit) keep in-range offsets inside it. So canonical keys of different real slots
  differ.
- The only cross-representation case is a raw access, `SK{r, 0, []}`, against a structural image. That is exactly what
  the generated check of §3.2 tests.

**Real slot of a key.** The Python function in a new `holon/sorts/skeys.py` mirrors `extracted_eval.locate`:

`s = b + o`; for each step: `SP_m{k, o'}: s = keccak(pad32(k) ‖ pad32(s)) + o'`
(`SP_d{o'}: keccak(pad32(s)) + o'`; `SP_b{kb, o'}: keccak(kb ‖ pad32(s)) + o'`), all mod 2^256.

### 2.2 How each access kind compiles

`base` is the family's literal slot. "Key words are bound once" means `+kw = {<key expr> : W}` precedes the stores, as
`write_body` binds `+k` today.

| access | today | IQ21 |
|---|---|---|
| scalar at slot b, byte offset off, width n | `sload(st, W{b})` masked | `sload(st, SK{W{b}, w0(), Nil})` masked; the write is the same masked `sstore` |
| top-level struct member m | `W{b+m}` literal | `SK{W{b}, W{m}, Nil}` |
| top-level static array, index i (word elements) | `w_add(W{b}, i)` | `SK{W{b}, w_mul(i, n), Nil}` (sub-word elements stay a GenError, as today) |
| mapping value, key k | `h_get(kh, b_of_w(clean k) ++ b_of_w(W{b}))` | `SK{W{b}, w0(), [SP_m{clean k, w0()}]}` |
| mapping → struct member m (slot m.slot, byte offset m.offset) | `w_add(h_get(..), W{m.slot})` | `SK{W{b}, w0(), [SP_m{clean k, W{m.slot}}]}`, masked at m.offset |
| nested mapping `m[k1][k2]` | `h_get(kh, k2 ++ h_get(kh, k1 ++ b))` | `SK{W{b}, w0(), [SP_m{k1, w0()}, SP_m{k2, w0()}]}` |
| mapping → static array element i | `w_add(h_get(..), i·n)` | `SK{W{b}, w0(), [SP_m{k, w(i·n)}]}` |
| whole-struct write or `delete m[k]` | one `w_add(k, m)` per member | one SK per member from the bound key word |
| dynamic array length / element i (I36) | refused | length at the array's own SK; element at `p ++ [SP_d{w(i·n + m)}]`; push and pop are the two writes |
| raw `sload(r)` / `sstore(r, v)` | `sload(st, r)` | `sload(st, SK{r, w0(), Nil})` (= the scalar at literal r) |

**On the Rollup:**
- 9 scalar families plus `_initialized|_initializing` packed in slot 0;
- 9 mapping families: two to structs, `challenges` with packed member slots +0 and +3;
- no nested mapping and no array access (the `__gap`s are never read);
- one raw constant read: `initialize4`'s EIP-1967 admin slot `0xb531…6103` (facts `initialize4`, `["sload", 81955…]`).

### 2.3 What becomes trivial

The probe `bendprobe/skproof.bend` (380 lines over the real prelude) checks in bend2 in 0.57 s and in BendTT in
0.75 s.
- The library: `sp_self`, `sps_self`, `sk_self` (sk_eq is reflexive), and `sp_refl`, `sps_refl`, `sk_refl` (sk_eq True
  implies equal keys).
- `sst_same`: a store at k is read back at k, for any k, symbolic paths included.
- `sst_frame`: a store at kw leaves k when `sk_eq` is False both ways. It is the DISCH `kw_frame` generalised; the proof
  shape is unchanged.
- Five demonstrations:

| fact | proof | probe def |
|---|---|---|
| different families (e.g. `batchDataStore[k1].originTimestamp` vs `_paused`), keys symbolic | `sst_frame(.., {==}, {==})`: **evaluation only** | `demo_cross` |
| two members of one entry (`challenges[k].finished` +3 vs `.startTime` +2), k symbolic | evaluation only | `demo_member` |
| one family, keys k1 ≠ k2 | `skm_ne` from `w_eq(k1, k2) == False`: **a fact about the program's key words, never a table** | `demo_key` |
| a missing key | `ssload(ssstore(SSt{Nil}, K(k1), v), K(k2)) == w0()` given k1 ≠ k2 | `demo_missing` |
| any two keys | `ssload(ssstore(s, K(k1), v), K(k2)) == ite(w_eq(k1,k2), v, ssload(s, K(k2)))` | `demo_split` |

**Planted errors.** Each claims a same-family frame by evaluation, for two symbolic keys and for one key with the same
member. Both **fail**, and the residual obligation is printed as `Bool.and(M.w_eq(k1, k2), True{})`. That is exactly
the key disequality, and nothing about a table.

**A Reach induction of a kept-register invariant**, ∀k: `g[k] ≠ 0 → vg[k] == 7`, holds over a two-action machine on
the structural store (`bendprobe/reach_model.bend`, `reach_proof.bend`, 440 lines).
- putg splits on the key; mark is framed by evaluation. s0 is closed by computation, and the induction runs on
  `Reach` with the state erased (`-s`, as `tests_m3/fixtures/intake/proofs/valid/PROOF.bend:81` does).
- bend2 0.57 s, BendTT 0.76 s. A planted variant fails.
- This is `tag_exact`'s architecture in miniature.

**Performance hint (micro-benchmark only).** A 24-entry store, 12 reads and a 12-store chain, against the same
accesses through `h_get` over a 44-key table:
- bend2 1.3 s vs 2.7 s;
- BendTT about 4.5 s vs 5.9 s (base cost about 0.4 / 0.55 s).

The real step's cost is dominated by A30's context growth, so this predicts nothing about rollup counter-laws.

### 2.4 Generated lemmas still needed

**Fixed library, emitted and checked with each proof file** (`holon/disch/lemmas.py` and `order.py`, rewritten over
SK):
- the store facts above;
- the ghost-map twins `gk_same`/`gk_frame`. The companion map `GKT` is keyed by the mapping's key word (`model3.py`
  Ghost), so these are the old W-keyed lemmas.

**Generated, per use** (all generic; none names a target):

1. **Key split.** At a same-family store with a symbolic key against a claim key, split on `w_eq(kw, k)`.
   - Equal branch: `sk_refl`, then `st_same` (transport of the stored value), or a contradiction.
   - Other branch: `skm_ne`, then `st_frame`.
2. **The convoy.** Each passed check's equation `{cond == True}` is carried down the statement chain as a hypothesis,
   so a later key split can close its equal branch against it. `tag_exact` needs it at keepg (`v == vg[k]`, toy :84);
   blk_228 needs it at finalizeBatch (Rollup.sol:640).
3. **Loop frames (L1).** A fuel induction over `lp_<a>_<n>` for each loop on a path.
   - (i) The loop never writes storage, so `ov` is untouched: cBWP's loops `Rollup.sol:901-908` and `:936-943`,
     finalizeBatch's `:744-751`, put/putg's `_digest` loop `ToyTypes.sol:36-43`.
   - (ii) Every store in the loop is at a base other than the claim's, by evaluation per iteration: revertBatch
     `:444-467`, the toy's sweep `:143-145`.
   - A loop that reverts or runs out of fuel reverts the step, which keeps the state.
4. **`tag_exact`** (`holon/sorts/tag_exact.py`, new; the run3 dispatch already names it, `run3.py:563-567`).
   - **Invariant:** `I(g) := ∀k. F[k] ≠ 0 → companion_F[k] = member_fn(V[k])`. F is the union register, V the register
     its write sites write with the member function's parameter, at the same key. This is the I30 contract's own
     description (`tests_m3/test_sort_types.py:229-231`), found by an untrusted search and checked by Bend.
   - **Lemmas:** s0 by computation, with a key split per same-family s0 entry; one step lemma per action through the
     mirror (frames, key splits, convoy, loops, ghost effects); the Reach induction; and the coerce lemma at the hit
     (the passed checks give `F[k] ≠ 0` and the guard equation).
5. **Optional bit-field lemmas (F).** A byte field after `w_or(w_and(x, ~mask), v << s)` reads back `v`, and the other
   fields of x are unchanged. This gives TI2, and serves I33's W2 and I36's O34 (ReplayState packs two uint128).
6. **Optional monotone transport (K-mono).** A store that moves an atom of B in B's direction keeps B, via the order
   lemmas (`w_le_lt`); this is TimeMono's argument for another operand. This gives blk_363_anyone, and serves I36's O34
   (`times + 1`).

### 2.5 The mirror and DISCH routes after IQ21

**Frame route.**
- Today: `frame_invs` (`proofs.py:426-459`) refuses any non-literal store key.
- After IQ21: a store whose key's base (or member offset) differs from the claim's is framed by evaluation
  (`st_frame(.., {==}, {==})`).
- A same-family store with a symbolic key goes to the key split, and the equal branch is closed by the convoy or by
  transport.
- B's slot keys may be any **closed** SK: a literal SK such as B_228's `SK{160, 0, [SP_m{0, 0}]}` gets `blkv`.

**Section.** `section.py`'s literal recogniser (`_SLOAD_LIT`) accepts closed SK terms.

**Optional: a state-dependent key whose inner reads are B's own literal slots** (B_363's `SP_m{sload(st,167), 2}`). It
is framed as long as slot 167 is framed.

**Mirror.** It follows loops through the L1 lemmas instead of refusing `lq_..` (`mirror.py:16`, `:242`), and carries
the convoy.

### 2.6 For I33: exactly what a law over mapping state can rely on

The coordinator asked for this.

**(1) Distinct key paths are distinct storage locations, by construction.**
- The store is a map keyed by SK values, compared by `sk_eq`. Two keys that differ in base, top-level offset, path
  length, any step's offset or any step's key word are different entries.
- A store at one never changes the word at the other (`sst_frame`), for every hash table, with no premise.
- What counts as "the same key path" is the canonical form:
  - member and index offsets are folded into the step's offset word;
  - key words are cleaned as solc cleans them.

  So `m[k].a` and `m[k]` with a at slot offset 0 are one location, exactly as on chain.

**(2) A missing key reads the default, without aliasing.** `sload` of an absent SK is `w0()`, and only an `sk_eq`-equal
entry answers.
- There is no table, so there is no "missing table key" any more.
- `batchDataStore[k].finalizeTimestamp` is `SK{162, 0, [SP_m{k, 1}]}` for every k.
- challengeState's loop writes `SK{162, 0, [SP_m{i, 1}]}` for each i ≠ batchIndex in range, distinct for distinct i, so
  W is added once per batch. I33 §1.2 points 3 and 4 disappear.

**(3) The frame lemmas.**
- The facts:
  - `st_same(s, k, v)`: `sload(sstore(s,k,v),k) == v`, for any k;
  - `st_frame(s, kw, v, k, ne1, ne2)`: given `sk_eq(kw,k) == False` and `sk_eq(k,kw) == False`, the word at k is
    unchanged.
- Discharging `ne`:
  - different families or members: `{==}`, by evaluation;
  - same family: from `w_eq(k1,k2) == False` (`skm_ne`), a fact about the program's key values that comes from a check
    (the convoy) or from a case split (`demo_split`). Never from a table.
- Overlay versus pre-state: the document's terms read the pre-state `st`, and stores go to `ov`. The fact
  `gh_get_st(gh_go_<a>(x, g)) = ov` on code 0 is unchanged.
- Loops still need a fuel induction. IQ21 provides the frame forms (L1). A transport through a loop, such as
  challengeState's `+W`, remains I33's.

**(4) I33's work list against IQ21 (core scope):**

| I33 item | after IQ21 |
|---|---|
| W3 table and slots: `h_get` presence, preimage disequality, `sep` (≥4 apart, ≥256, distinct keys), `dep`, "missing keys land in 0..3" | **unnecessary**, entirely, for storage. `h_get` matters only for code-level hashes, which O12 does not read |
| W4 storage frames over hashed slots | **replaced** by IQ21's SK library. The overlay and `gh_go` facts stay |
| W9 `present(kh, F, k)` and the `sep` premise; G's `dep` | **unnecessary**. L2's premises shrink to "x succeeds from s, y succeeds from s1". G keeps `gP = 0` and `gT = 0` |
| W6: the stepper's refusal of non-literal slots | **done by IQ21**: SK stores framed by evaluation or by key split with the convoy |
| W6: the convoy | **done by IQ21**, because `tag_exact` needs it |
| W6/W5(i): loop frames | **done by IQ21** (L1) |
| W5(ii): challengeState's +W transport through its loop (in-range i ≠ bi) | **remains I33's** |
| W2 packed byte | **remains**, unless IQ21 bundles the bit-field lemmas (F) |
| W1 Word↔Nat; W7-W10 | **remain** |

**What a law may *not* rely on:**
- that the real contract agrees. That is `A-keccak-structural`, validated by R5 and the keys check;
- anything about code-level hash *values*: `keccak256` stays ∀ in the frozen statements, so batch hashes are still
  adversarial, and a law that needs them takes a CF premise from its rule, as FACT's `cf:keccak256` does.

### 2.7 What IQ21 unblocks for I36 (its M9)

| I36 item | the wall today | after IQ21 |
|---|---|---|
| **O34 blocking** (B(k) = `replayStates[k].times ≥ maxReplayTimes`; every anyone action writes mapping slots) | hashed slots and a packed `ReplayState` | SK frames and the key split are built. The equal-key branch at `replayMessage(k)` needs K-mono (`times + 1` keeps `≥`) and F (two uint128 in one slot). The law itself still needs I36's keyed DISCH producer (M8) |
| **D9** (relay at most once; `finalizedWithdrawals[h]`) | frames at mapping slots | frames and the key split are available. The producer (M10) and A-reentrancy remain |
| **D8** (per-action conservation with two or more writes) | multi-write aliasing under the ∀ table | gone: writes at distinct keys are distinct by construction. The ledger rules and M5/M6 remain |
| **Dynamic arrays and bytes keys** (`messageQueue`, `blsKeys`) | refused | the `SP_d`/`SP_b` steps are designed (§2.1-2.2) but emitted only when I36a needs them; R5 on the bundle validates them |

---

## 3. The evaluator side (question 3)

### 3.1 Where the real keccak256 is applied, and where it is not

**Never in the model or any proof.** The model, `Reach`, every law, every proof and counter-law, and the witnesses'
storage are structural. Counter-law states are SK literals through `proofs3.Lit.typed`. Its record parser
(`evaluate3.records`) must learn multi-constructor types (`SP`) or keep `SP` single-constructor.

**Applied, through one function `skeys.real_slot`:**

1. **R5** (`holon fragments --evaluator <typed model>`).
   - `run_fix` gains a third table: the SKs the run read. `eval3.mjs` hooks `sload`/`kv_get` as it hooks `h_get`.
   - For each read key the driver adds `KV{sk, real_state[real_slot(sk)]}` to the pre-state and reruns until no key is
     new, as the keccak fixpoint does today.
   - `outcome` maps the post-state's touched SKs (`tw`) to real slots for the `writes` comparison. This keeps I20's
     A/B interface and its slot counting (8894) unchanged.
2. **Replays.**
   - `disch/run.py:replay_one` and `refute_m3.py:1143-1166` evaluate B and c with EV over the model's states.
     `Model.state(g)` returns the real image.
   - The sorts replay compares outcomes and calls only, so it is unchanged.
   - I28's versioned replay compares slot words, so it needs images if that machine is converted.
3. **Deployment** (`deploy3`). Captured raw slots become the structural s0.
   - Match each slot against `keccak(p) + m` for the 64-byte preimages the capture already records, with
     `p = key ‖ base` and m below the value's slot count. Nest by fixpoint.
   - Slots with no match and above the literal range stay raw.
   - Refuse unless the image of s0 equals the captured storage exactly.
   - Rollup (computed in scratch from the committed init):
     - literal: slots 0, 51, 151-153, 155, 156, 169, 172;
     - structural: committedBatches[0], batchBlobVersionedHashes[0], batchDataStore[0] (+0, +1),
       finalizedStateRoots[0], isChallenger[0x1004], committedStateRoots[0];
     - raw: `0x3608…2bbc` (EIP-1967 implementation) and `0xb531…6103` (EIP-1967 admin, 0xad).
   - The init JSON keeps its fields additively: I28's prereg reads its admin, harness and calls.
4. **Search heuristics** (candidates only).
   - `Model.state` gives the image for EV's directed values.
   - Each SK touched is re-offered as its *virtual preimage* (key word ‖ parent real slot), so S1's pool equals today's
     pool, which held the slot preimages.
   - Code-level keys keep the keccak fixpoint. The witness tables shrink to code-level keys: I30's 16-18 keys per
     witness were mostly slots.

### 3.2 The generated raw-slot check

**Output:** `gen/M3/sorts/models/<model>.keys.json`, regenerated by G1 and byte-identical.

**What it holds:**
- **Raw slots:**
  - every constant `sload`/`sstore` argument of the document. Rollup: 1, the admin slot;
  - every raw slot evaluated on a run. Rollup: none computed;
  - the deployment's leftover raw slots. Rollup: 2.
- **Literal slots:** the layout's scalars.
- **Structural keys with their real images:** from s0. The R5 record carries the corpus's keys and collisions
  (`results/M3/sorts/refinement.json` gains a `keys` block), and each record carries its witness's or inhabitant's
  keys.

**The checks.** Each is mechanical over concrete keys:
- (a) no raw or literal slot equals the image of a non-empty-path SK;
- (b) no two distinct SKs share an image (keccak injectivity on the observed keys, the empirical half of
  A-keccak-structural);
- (c) no image of a step's offset range overlaps another key's image (near-collision).

**Expected on the Rollup:** 0, trivially at s0 (two EIP-1967 constants against 7 images and 9 literals), and on the
corpus.

**A gate clause** fails on any listed collision. The collision is filed as a finding: the affected raw access is then
modelled at the structural key, with the finding's id. It is never silently merged.

### 3.3 `A-keccak-structural`: text and plumbing

**Proposed text:** "Compiler-generated storage locations are keyed structurally (the family's base slot, the offset in
the top-level variable, and the mapping keys with their slot offsets). The model treats distinct structural keys as
distinct locations, and a raw slot as distinct from every structural key's location. This holds of the real contract
when keccak256 has no collision and no near-collision among the locations a run touches, and no raw slot equals such a
location. It is validated empirically by every R5 storage comparison (each structural key mapped to its real slot by
the real keccak256) and by the generated keys check."

**Ledger:**
- The Rollup's bundle (facts `a38d416c…`) lives in `spec/M2/ledger.json`. I62-D3
  (`tests_m2/test_mutation_adequacy_i62.py:2689-2706`) pins that bundle and its `extends` to I61's version, so **do not
  edit it**.
- Instead add `spec/M3/ledger.json` with `{"extends": [{"facts", "facts_sha256", "entries": [A-keccak-structural:
  introduced_by ["SK", "sk_eq", "sps_eq", "sp_eq", "kv_get", "kv_put", "kv_set"]], "no_assumption": [..]}]}`.
- Teach `holon.records.milestone_extensions`/`all_bundles` (`records.py:197-249`) to merge an extension's `entries`.
- Pass the milestone to `model_assumptions` (`:286`) from the four typed runners: run3 `:672`, disch/run `:700`,
  undo/run `:409`, fact/run `:688`.
- These names occur only in structural models, so no M1, M2 or PAR record changes its assumptions.

**Records:**
- SORT/DISCH list it in `model_assumptions`.
- UNDO/FACT move ledger entries to `ledger_assumptions` and keep hypothesis premises in `model_assumptions`
  (`undo/run.py:428-433`).

**Pre-existing inconsistency to know:** the M2 bundle's `introduced_by` patterns `chk_*`, `step_*` and `post_*` rarely
meet M3 cones, which go through `k_*`/`s_*`/`gh_*`. Typed records therefore list A-env and A-reach but rarely A-loop or
A-reentrancy (e.g. `results/M3/L_disch_rev_rollup_132_d953872f.json`). A new IQ21 test should assert that every record
over a structural model lists A-keccak-structural. It is reported, not fixed here.

**Validation:**
- R5's record (its new `keys` block, with collisions `[]`) plus the keys check.
- R5 is not part of G1 today; it is a build-time record checked by `tests_m3/test_sort_types.py:1679-1696`. Whether
  G1 should rerun it is lead question L4.

---

## 4. Blast radius (question 4)

### 4.1 Artifacts that change

| artifact | change |
|---|---|
| `gen/M3/sorts/models/morph_rollup_extracted.bend` (+ link), `.init.json`, new `.keys.json` | regenerated: SK store, structural s0; text shrinks (295 slot `h_get`s become short SK literals) |
| `gen/M3/sorts/untyped/models/…` (termsize baseline), `gen/M3/sorts/types.json`, `taint.json`, `term_size.json` | regenerated: model sha, cone sizes. P8's ratio bound (1.5) is expected to hold |
| `gen/M3/disch/models/*.disch.bend`, `gen/M3/undo/models/*`, `gen/M3/fact/models/*` | regenerated over SK |
| `gen/M3/laws/<51>/LAWS.bend` | **byte-identical** (they import the model and state `exs kh`, `Reach<kh, s>`: unchanged) |
| `gen/M3/proofs/<51>/…`, `gen/M3/<id>/nonvac/…` | regenerated: counter-laws with SK literal states and smaller tables; new DISCH and tag_exact proofs |
| `results/M3/` 3 SORT, 35 DISCH, 8 UNDO, 5 FACT records | remade: model sha, witnesses' tables, attempts; 12 DISCH statuses change (§5) |
| `results/M3/` 80 PAR records; `results/M1`, `M2`, `M2/extracted_m1` records | `generator_sha256` and seconds only |
| `results/M3/sorts/refinement.json` (+ side files), `replay/M3/{sorts,disch,undo,fact}/report.json` | regenerated |
| I40's M3 outputs: concretization fields, `results/M3/refute/filter.json`, emitted direct tests | regenerated (same slots and words if the image is exact) |
| `results/M3/metrics.json`, `summary.json`, `deps.json`; gate report | regenerated |
| `spec/bindings/M3.json`, `changes.jsonl`; `laws/STATEMENT_DIFF.jsonl` | 51 rebinds plus 51 lifecycle lines, **of a kind that does not exist yet (H1)** |
| `spec/M3/ledger.json` (new); `spec/M3/lib/lean_promoted.json` (I43's baselines) | new file; re-baselined (§4.3) |
| unchanged | `laws/M0-M3` (REGISTRY, DERIVATION), catalog (no producer change), every document, `gen/M0-M2`, `gen/M3/model/header_length.bend`, `gen/M3/evidence.json`, BMC (`holon/bmc.py` has its own E1 encoding) |

### 4.2 Gate checks to rerun

**Gate M3** (`holon/sorts/gate3.py:1-35`):
- GENV;
- **G2**: bindings and the lifecycle tie; blocked by H1;
- **G1**: full rerun, sharded, in the background (Q24);
- G3, G5 (every new PROOF.bend), G11, **G11V** (new PROVED laws need inhabitants), G6 (every REFUTED witness), G9,
  G10;
- **G7**: BendTT on every decided law;
- **G4**: the I30 canaries, and now the 10 disch_writer canaries, non-vacuously for the first time;
- the joined DISCH and FACT gates; GEVID; the new keys clause.

**Gates M1 and M2:** G1, for the generator hashes.

**Partial-gate CI jobs:** as Q32-Q38 describe.

### 4.3 Tests that pin hashes or counts

| test (file:line) | what it pins | after IQ21 |
|---|---|---|
| `tests_m3/test_sort_types.py:370`, `:1679-1696` (I30-R5) | 460/3013/8894, 0 disagreements, by_action, panics, `evaluator_sha256` = the committed model | **predicted to pass unchanged** (the image keeps the slot counting); this is the empirical check |
| `tests_m3/test_sort_types.py:1676`, `:1245` | records and `taint.json` name the committed model's sha | pass after regeneration (dynamic) |
| `tests_m3/test_sort_types.py:398-401`, `:1344-1388`, `:1390-1420` (I30-R6 toy) | keepg PROVED by `tag_exact` with an inhabitant; the mutation REFUTED | **predicted to pass** (needs `tag_exact`) |
| `tests_m3/test_sort_types.py:1698-1716` (in I30-R6) | the full M3 gate passes | fails unless H1 is ruled and G11V's TI4 inhabitant is found |
| `tests_m3/test_lean_promoted.py:1002-1046` (I43-R1) with `spec/M3/lib/lean_promoted.json` | the status of every record in 4 dirs; 507 `.bend` files byte-identical (among them `gen/M3/{sorts,undo,disch}/models/*`, the 51 laws' proofs); 46 `unregenerated_records` (statement, generator, witness and kernel hashes) | **re-baseline the sidecar**, as the I43 follow-up `4bcf535d` did for F35, **plus an amendment line** for the 12 DISCH status changes (`spec/M3/amendments.jsonl`, iteration I43) |
| `tests_m3/test_disch_profile.py:311-336` (I32-R2) | no closure file and no M0-M3 output changes after I32's prereg; M1's `L_disch_delay_*` records dict-equal | **fails** (closure edits; `generator_sha256` of the M1 records). I28's prereg amends it; IQ21 needs the same amendment, or I28's, and must check that the M1-record clause is covered |
| `tests_m2/test_mutation_adequacy_i62.py:2689-2706` (I62-D3) | the Rollup's bundle and `extends` in `spec/M2/ledger.json` | untouched by design (ledger entry in `spec/M3/ledger.json`) |
| `tests_m3/test_eqprove.py:34` (F32) | `w_eq, w_add, w_add_ok, w_sub, u_b4, u_be4, h_get, kw_set` provably equal to the I30 prelude | untouched by design (those definitions keep their text) |
| `tests_m3/test_disch.py:938-981`, `:902-916`, `:982-990`, `:1105`, `:1150` (I31) | P8/P9 statuses, P10 and R1 statuses with inhabitants, counts 27/7/1, gate+canaries, non-DISCH statuses | P8 and P9 start passing; P10 fails on TI2 (unless F) and TI4's inhabitant; R1 fails on 363_anyone; counts 26/7/2; R3 passes. No amendment needed (I31 is scored; nothing it pinned as passing breaks) |
| I28's prereg (`/home/user/HOLON-i28/tests_m3/test_versions.py`, untracked): V6 "holon.sorts.model3's raw storage, … keccak256 and sha256 as table parameters"; V5-V9 `--check` byte identity; "nothing under gen/M3/sorts/ … changes" (an I28-commit rule only) | a versioned model built on model3 | if IQ21 follows I28 and changes model3's default, `holon versions model --check` fails. Keep a raw mode for it, or reword V6 before I28's prereg is committed (§4.5) |
| I24 (`tests_m3/test_derive_par.py:627-647`), I25-R3, `test_catalog_rederivation.py` | adoption and catalog | unaffected (no document or catalog change) |

### 4.4 The lifecycle problem (G2): why H1 is needed

`spec/bindings/M3.json` binds the 51 typed-model laws: 38 to the typed model, 8 to the UNDO section and 5 to the FACT
section. Each cone holds 1765-2395 definitions in the records sampled, and every one sampled contains `HSt`, `sload` and `sstore`.

**The only unsigned channel for a cone change is `binding_change`** (`holon/statement_diff.py:24-31`, `:626-690`).
- It requires a kernel-checked **extensional equivalence** of every changed root, old against new
  (`holon.gen.equivalence`).
- Here none can exist. The state type changes (`KW{W,W}` to `KV{SK,W}`), and the meanings differ by design: the old
  model aliases under some tables, the new one never does.
- Signatures are impossible too: "No key" (Q40, `HUMAN_ANSWERS.md:55`), and "a signature is the human's act" (Q31).
- So G2 stays red on 51 laws until the human rules on a channel (H1).

**Proposal: a mechanical kind `remodel`**, accepted unsigned only when all of the following hold:
- (a) the law file and the emitted statement and counter-law (`statement_sha256`, `counter_sha256`) are unchanged, as
  is the model path. Only the cone differs;
- (b) the entry names the human answer that licenses the remodel (`Q21`), the model versions (`holon-model-m3/0.2` →
  `0.3`) and the ledger entry it adds;
- (c) G1 regenerates the new model byte for byte from the pinned generators and inputs;
- (d) the new model's R5 record on the frozen I20 corpus has I20's counts and 0 disagreements, and the keys check is
  empty;
- (e) the law's record is remade on the new model. A status change is reported as an outcome, never treated as a
  statement change.

### 4.5 I28, F40, order and bundling

**I28 (laws half; prereg in progress, untracked in `/home/user/HOLON-i28`).**
- Its build moves M3 to holon-rules/1.6.
- It re-makes "the M3 records whose statement hash the catalog moves (re-made, statuses unchanged)", which is all 131,
  and refreshes M1 and M2.
- It builds `gen/M3/versions/models/morph_rollup.versions.bend` "as the M3 machine compiles the adopted document
  (holon.sorts.model3's raw storage, … keccak256 and sha256 as table parameters)" (V6).
- **Structural keys are compatible with I28's MIG semantics.** "Every slot kept across an upgrade" holds key by key,
  because bases and offsets are layout numbers.
  - V10→V11's reinterpretation of slot 151 and the retyping of `batchDataStore`'s 4th member act on the same
    `SK{151,0,[]}` and `SK{162,0,[SP_m{k,3}]}`, read with the new version's masks.
- **I28's laws do not need frames.** O9 is a witness, D4 and F12.5 are gap records, and the in-flight inhabitants are
  concrete traces. NAT (I29), which runs over that machine, will.

**Options, given the working assumption (IQ21 after I28's build):**

| option | effect |
|---|---|
| **A1 (recommended if I28's prereg is already committed)** | model3 gains an explicit `storage` mode: `structural` for the typed model and its sections, `raw` passed by I28's versioned generator. I28's outputs stay byte-identical. Records over the raw machine do not get A-keccak-structural. Convert the versioned machine when NAT needs frames (I29), with I28's amendments then |
| **A2 (recommended if I28's prereg is not yet committed)** | word V6 as "holon.sorts.model3's storage representation". IQ21 then regenerates the versioned machine in-contract, and only I28's `--check` outputs move: its outcome files, the PAR-init record, INHABIT.bend and the replay, which must map SK to real slots |
| **B (cheapest overall, delays I28)** | IQ21 before I28's build. One conversion; I28's 1.6 re-make then happens once, on the structural model |

**Re-make economy.** The 51 typed records cost hours each time they are re-made:
- DISCH: I31's outcome run took 3 h 21 min with 540 s time boxes;
- UNDO: about 6 h at full budget (Q33);
- SORT: hours, Q24;
- FACT: about 1-2 h.

So, under the working assumption:
- I28's statement-hash pass over them should use `--resume` (build-time convenience, Q24).
- Or the lead accepts that IQ21's full re-make supersedes it.
- **The pending F40 re-make:** if it touches any of the 51 typed-model records, schedule it after IQ21 or fold it into
  IQ21's outcome run. If it only refreshes M1/M2/PAR `generator_sha256`, it is superseded anyway (IQ21 edits the
  0.2/0.3 closures). Either way IQ21's code should rebase on F40 before its outcome run.

**Bundle with IQ21:**
- **(i)** The DISCH route extensions (SK frames, key split, convoy, L1). They share the mirror with `tag_exact`, and the
  DISCH records are re-made anyway.
- **(ii) Optionally** the bit-field lemmas (F: TI2, and I33's W2 and I36's O34) and the monotone transport (K-mono:
  363_anyone and O34). Each is one more prediction, at small extra risk.
- **(iii) Not** I36's arrays or bytes keys. The `SP_d`/`SP_b` steps stay GenErrors until I36a.

---

## 5. Expected outcomes to preregister (question 5)

### 5.1 I30-R6: the toy's tag_exact law

**Predicted PROVED by `tag_exact`, with a checked reachable `chit` inhabitant** (keepg after a putg of the same key).

**Why it is true for every table once keys are structural:**
- The invariant is `∀k. g[k] ≠ 0 → gc_g[k] = mf(vg[k])`, with `mf(v) = (v == 2 ? Dig[Agg] : Dig[VH])`.
- **It is inductive.**
  - `putg(k, v)` writes `g[k] := _digest(v)` and `vg[k] := v`. Its ghost step sets `gc_g[k] := tag(_digest(v)) =
    mf(v)`. The tag term does not depend on the loop or on kh.
  - `keepg(k, v)` passes `blobhash(0) == 0`, `g[k] ≠ 0` and `v == vg[k]` (convoy). It writes `g[k] := g[k]` and
    `vg[k] := v`, and copies the tag.
  - Every other action writes other families: put, recommit, setW, challenge, commitT, elapsed, send, setD, finalize,
    commitQ, mark, and sweep through its loop. They are framed by evaluation.
  - If kh hashes the blob list to 0, `g[k]` becomes 0, the invariant is vacuous at k, and keepg cannot hit.
- At the hit, the guard equation and the invariant give the coercion.
- The empty-table counterexample is gone: `SK{2,0,[SP_m{1,0}]} ≠ SK{2,0,[SP_m{5,0}]}` by construction.

**The rest of the toy:**
- The other four toy laws keep their designed outcomes:
  - REFUTED: 72 at recommit, 100 at commitT, 133 at commitQ;
  - PROVED by coercion_guard: 107.
- The keepg-guard mutation is REFUTED through keepg, with the last putg of the key on the other side of 2. That witness
  is a genuine one; no aliasing is available.

**Whole R6.** It also requires `test_gate_m3_passes`, so it is a PASS only if:
- H1 is ruled and G2 passes;
- G11V finds inhabitants for `rev_initializable_120_d9a34b48` and for the newly PROVED TI4 blocking law. No explored
  state has `_initialized >= 4` (Q36);
- the hours-long G1 passes.

The prereg should score the toy clause and the gate clause separately in its own predictions. **Predict R6 as a whole
MISS on the gate clause**, unless the lead also schedules the TI4 inhabitant search (L3).

### 5.2 I31's 15 blocking laws (14 UNKNOWN, one REFUTED)

Closures are from `gen/M3/disch/closure.json`. Program order is from `probe/programs.txt`. The writes and loops are
those of the facts.

| law | B | closure actions that need more than chain_revert (the rest revert at a modifier before any loop) | needs | core | +F |
|---|---|---|---|---|---|
| blk_pausableupgradeable_77 ×3 (anyone, onlyActiveSubmitter, onlyChallenger) | `_paused` (slot 101) | initialize2 (`committedStateRoots[lastCommitted]` store, slot 0 bit-field writes at another slot), initialize3 (slots 0, 172) | SK | **PROVED** | |
| blk_rollup_132 ×4 (anyone, caller_rollup_210, onlyActiveSubmitter, onlyChallenger) | `revertReqIndex ≠ 0` (168) | initialize2, initialize3; initialize4 reverts at :214 | SK | **PROVED** | |
| blk_initializable_120_b95c70f1_anyone (TI3) | `_initialized ≥ 3 ∨ _initializing` (slot 0) | cBWP (loops :901-908 and :936-943, no writes; mapping stores; slot 158), finalizeBatch (loop :744-751, no writes; mapping stores; 157); initialize2 by the arithmetic implication | SK + L1 | **PROVED** | |
| blk_initializable_120_d9a34b48_caller_rollup_210 (TI4) | `≥ 4 ∨ initializing` | cBWP, finalizeBatch; initialize2/3/4 revert | SK + L1 | **PROVED** (G11V unknown) | |
| blk_rollup_213 ×2 (caller_rollup_210, onlyChallenger) | `inChallenge` (166) | cBWP, finalizeBatch, initialize2; challengeState reverts at :475 and initialize4 at :213 | SK + L1 | **PROVED** | |
| blk_rollup_228_79cc3e9a_onlyOwner | `finalizedStateRoots[0] ≠ 0` (a closed SK) | finalizeBatch stores `finalizedStateRoots[_batchIndex]`: split on `_batchIndex == 0`; the equal branch contradicts B by the passed check at :640 (convoy). revertBatch's loop writes other bases (L1-ii); cBWP (L1-i); setPause etc. by evaluation | SK + L1 + key split + convoy | **PROVED** | |
| blk_initializable_120_b8d46c45_anyone (TI2) | `≥ 2 ∨ initializing` | as TI3, plus initialize3's masked slot-0 update (`_initialized := 3`, the I31-P10 "transport" case) | + bit-field | UNKNOWN (bit-field) | **PROVED** |
| blk_rollup_363_e11d8bb2_anyone | `inChallenge ∧ ¬realize(pw + challenges[bc].startTime − t) ∧ add_ok` | finalizeBatch's `delete challenges[_batchIndex − 1]` (:660) at the same family: no check relates `_batchIndex − 1` to `bc`, so the equal branch needs `startTime := 0` to keep B (pw ≤ pw + st < t): a monotone transport | + K-mono | UNKNOWN (named) | UNKNOWN |
| blk_rollup_363_e11d8bb2_onlyActiveSubmitter | | | | REFUTED (witness, unchanged) | |
| rev_rollup_363_e11d8bb2 (not a blocking law; the 15th UNKNOWN) | | commitBatch, cBWP, commitState reach :363 after no-write loops; the check reads the pre-state, as B does | L1 | **PROVED** | |

**None is predicted REFUTED.** Each UNKNOWN law is true by the reading above. The searches stay at I31's budget, with
the same 540 s time box if the prereg keeps it.

**DISCH totals:** core 26 PROVED / 7 REFUTED / 2 UNKNOWN; with F 27/7/1; with F and K-mono 28/7/0.

I31 predicted 27/7/1, with 228 UNKNOWN and 363_anyone PROVED. The reading here swaps those two: 228 has a route (the
convoy), and 363_anyone needs an arithmetic transport that no route gives.

**Non-vacuity.**
- B_77: setPause(true) by the owner. B_132: S3's proveState-timeout prefix. TI3: initialize3 from s0. 213:
  challengeState. 228: holds at s0.
- **TI4 is predicted unknown**, as rev TI4 already is.

**G4.** The 10 preregistered disch_writer canaries become applicable. Each canary whose source law is now PROVED
should be rejected. That is I31's exit criterion "a canary that adds one non-X writer is rejected", met for the first
time.

### 5.3 Laws whose status might flip

**No PROVED law relied on keccak-as-parameter.**
- Under a ∀ table no frame over hashed slots could be proved: that is precisely the refusal.
- The PROVED typed-model laws are:
  - 6 DISCH ext (witnessed);
  - 7 DISCH rev (chain_revert: the check and B read the same pre-state terms, `h_get` subterms included, so they
    re-prove over SK unchanged);
  - the FACT kernel law on commitState (the `guard` route over the blob check, `gen/M3/proofs/L_fact_kernel_…/PROOF.bend`;
    its CF and NZ premises are unchanged).

**No REFUTED law relied on an adversarial table.** Every witness carries the real keccak256 of each key it hashes
(I30's `settle`), and on such a trace the structural model computes what the hashed model computed (R5).

**Risks to statuses** come from the re-run, not the semantics:
- search drift: the candidate pool and exploration order (I31 Surprise 8) — mitigated by re-offering virtual
  preimages;
- BendTT fuel on new counter-laws.

The prereg should predict every status other than §5.2's as unchanged.

**The typed SORT 406 law stays UNKNOWN.** `tag_exact` will be attempted on it and should fail, because its coercion
is false in the model whenever the A-env verifier accepts (I30-P2). A witness under the deployment's verifier is still
Q23's matter.

### 5.4 Statements unchanged

- `laws/M3/*.json`, `REGISTRY.json`, `DERIVATION.json` and `gen/M3/laws/*/LAWS.bend` stay byte-identical. No
  `catalog_rederivation` is needed.
- The 51 lifecycle lines are of H1's kind, cone only.

### 5.5 Draft predictions and regressions (key "IQ21", core scope; F and K-mono as marked options)

| id | claim (draft) | check (to be written) |
|---|---|---|
| IQ21-P1 | R5 on the structural typed model: 460 traces, 3013 steps, 8894 storage comparisons, 0 disagreements, I20's statuses per action and four panic sites; the record's `keys` block lists every structural key the corpus touched with its real slot, and 0 collisions | `test_sort_types.py::test_typed_model_agrees_…` (unchanged) + a new keys test |
| IQ21-P2 | the keys check: raw slots {EIP-1967 admin (read by initialize4), EIP-1967 implementation}, 9 literal, 7 structural s0 entries; no raw or literal slot equals a structural image of s0, the R5 corpus or any witness or inhabitant; no two structural keys share an image | new |
| IQ21-P3 | the toy: `L_sort_tag_toytypes_83_33f98e53` PROVED by tag_exact with a checked reachable inhabitant; the four other toy laws and the guard mutation as I30 designed; the aliasing trace `[putg(1,2)+blob, putg(5,1), keepg(1,1)]` gives no counter-law that bend2 accepts on the structural model | `test_sort_types.py::TestToy` (unchanged) + new |
| IQ21-P4 | DISCH: blk_77 ×3, blk_132 ×4, TI3, TI4, blk_213 ×2, blk_228 and rev_363 PROVED; TI2 and blk_363_anyone UNKNOWN, each record naming its blocker (packed-slot update; monotone transport); blk_363_onlyActiveSubmitter REFUTED. [F: TI2 PROVED. K-mono: 363_anyone PROVED] | new (its own key; I31 stays scored) |
| IQ21-P5 | non-vacuity: every newly PROVED law except blk_TI4 has a checked reachable inhabitant; TI4's is unknown (no explored state with `_initialized ≥ 4`) | new |
| IQ21-P6 | G4: every preregistered disch_writer canary whose source law is PROVED is rejected | new |
| IQ21-P7 | every new proof and every remade counter-law checks in bend2 and BendTT within `budget_s_per_file` (no `out of fuel`) | new |
| IQ21-R1 | `laws/M0-M3`, REGISTRY, DERIVATION and every `LAWS.bend` byte-identical; no catalog change | new |
| IQ21-R2 | every other M3 status unchanged: SORT 279 REFUTED, :363 REFUTED, 406 UNKNOWN; DISCH ext ×6 PROVED, noext ×6 REFUTED, rev ×7 PROVED; UNDO 3 REFUTED / 5 UNKNOWN; FACT 4 REFUTED / 1 PROVED; 80 PAR; every REFUTED witness replays (G6) | new |
| IQ21-R3 | M0-M2 records and the 80 PAR records change only in `generator_sha256` and seconds; `gen/M0-M2` and `gen/M3/model` byte-identical | new |
| IQ21-R4 | F32's eight helpers keep their text (`test_eqprove.py` passes); `spec/M2/ledger.json` unchanged (I62-D3 passes) | existing |
| IQ21-R5 | every record over a structural model names A-keccak-structural (SORT/DISCH `model_assumptions`, UNDO/FACT `ledger_assumptions`); no M0-M2 or PAR record does | new |

**Construction checks (not predictions):**
- no `h_get` in a storage key of any M3 model;
- the SK library checks alone in both kernels;
- the model and its keys file are deterministic;
- no target names in `holon/`.

---

## 6. Size and risk (question 6)

### 6.1 Code change, by file and function (estimate)

| area | files and functions | lines (approx.) |
|---|---|---|
| store and key types | `holon/sorts/prelude3.py` (SK/SP/KV, sk_eq…, HSt over KV, sload/sstore, HOut.tw); keep W-keyed helpers | +120 |
| compiler | `holon/sorts/model3.py`: `locate` (an SK builder), `write_body`/`struct_value` (member SKs from bound key words), `write_path`/`path_slots`, `t_sload` and raw stores, `s0_text`, header/version, a `storage` mode (option A1) | ±250 |
| keys | `holon/sorts/skeys.py` (new): `real_slot`, `real_state`, s0 conversion, keys check, keys.json | +250 |
| deployment | `holon/sorts/deploy3.py`: structural s0 from preimages, exact image check | +80 |
| evaluator | `holon/sorts/evaluate3.py` (SK fixpoint in `run_fix`, `outcome` mapping, multi-constructor records); `holon/js/eval3.mjs` (sload hook) | +100 |
| search | `holon/sorts/search3.py` (`state` image, virtual preimages to S1) | +60 |
| sections | `holon/undo/trace.py` (`base_slot`/`slot_i` → SK); `holon/fact/section.py`, `product.py` (regexes) | +60 |
| DISCH | `holon/disch/lemmas.py` and `order.py` (SK library: the probe's text); `section.py` (closed-SK keys); `proofs.py` (frame by evaluation, key split, convoy); `mirror.py` (SK terms, L1 loop lemmas, convoy) | +700-1000 |
| tag_exact | `holon/sorts/tag_exact.py` (new): invariant proposal, s0, step and induction lemmas, coerce; `run3.py` dispatch | +700-1000 |
| replays | `holon/disch/run.py:739-760`, `holon/refute_m3.py:1143-1166` (images) | +20 |
| ledger | `holon/records.py` (extension entries, milestone plumbing); 4 runners; `spec/M3/ledger.json` | +60 |
| lifecycle | `holon/statement_diff.py` + `holon/bindings.py`: the `remodel` kind, if H1 approves | +150 |
| tests | prereg contract `tests_m3/test_structural_keys.py` and an independent instrument `tests_m3/_iq21.py` (its own SK→slot mapping and collision check, re-derived from solc's layout rules) | +900-1300 |
| options | F bit-field lemmas (+250-350); K-mono transport (+150-250) | |

**Total core: about 3,300-4,500 lines** of generator, library and test code.

### 6.2 Runtime of the re-make (machine time; the 4-CPU shared container)

| step | time |
|---|---|
| model, types, termsize | minutes |
| deployment capture | minutes, or cached under `~/.holon/cache/m3init` |
| R5 rerun | about 1-2 h (estimate; the SK fixpoint adds rounds and drops slot-key rounds) |
| SORT 3 laws | 2-6 h; the :363 commitState search dominates (Q24/Q36) |
| DISCH 35 laws | about 3.5 h with 540 s time boxes (I31's outcome run: 3 h 21 min, the shared exploration included; that exploration alone took about 50 min in the later re-run), plus the new proof checks (seconds each) |
| UNDO 8 laws | about 6 h at full budget (Q33: four of them were rerun at full budget in about 6 h) |
| FACT 5 laws | 1-2 h (estimate; the kernel law's search used 1079 prefix states) |
| toy T30 | tens of minutes, in tests |
| rebind (if H1) | one BendTT translation per model, minutes |
| M1/M2 generator refresh | about 1 h |
| `holon refute --check` for G1 | about 2 h sharded (Q37) |

**Total about 15-25 machine-hours**, shardable by law (Q24): roughly a night's background job.

### 6.3 Top risks and fallbacks

| # | risk | fallback |
|---|---|---|
| 1 | **G2 channel** (H1): no unsigned way to rebind 51 laws whose model meaning changed | G2 stays red and labelled, under Q32's rule, until the human rules; nothing is weakened |
| 2 | **tag_exact** is the first Reach induction on the M3 word model. It needs the mirror to carry loops (put/putg's `_digest` loop, sweep's), the convoy and key splits through 15 toy actions | the scratch probe proves the shape (§2.3); if a piece slips, R6's toy law stays UNKNOWN with the failing lemma named |
| 3 | **BendTT fuel** on mirrored chains of long actions (cBWP: 51 check records plus 2 loops; finalizeBatch: 23 plus 1) and on remade rollup counter-laws (Q22 history) | A30-style per-statement lemmas; SK keys cut per-access cost (micro-probe); a fuel stop is recorded as budget exhaustion, never acceptance |
| 4 | **Search drift**: the S1 pool loses slot preimages, and the exploration depends on learned keys (I31 Surprise 8), so a witness may not be re-found → a REFUTED or ext law turns UNKNOWN | re-offer virtual preimages (§3.1); predict R2; a lost witness is a MISS, reported |
| 5 | **Canonical-form holes** (two access shapes to one real slot): none known on the Rollup or the toy; I36's arrays, packed small elements and bytes keys raise them | R5 and the keys check catch exercised cases; unsupported shapes stay GenErrors |
| 6 | **R5 exactness**: key cleaning, bytesN alignment, member offsets in `real_slot` must match `extracted_eval.locate` bit for bit | the instrument re-derives the mapping independently; R5's 0 disagreements is P1 |
| 7 | **I28 coupling** (§4.5): V6's raw-storage wording, `--check` outputs, and two re-makes of the same records | options A1/A2/B; decide before I28's prereg is committed |
| 8 | **Brittle text matchers** over `M.sload(st, M.W{..})` (DISCH section, FACT product, UNDO trace) | one shared recogniser in `skeys`; G1 byte identity catches drift |
| 9 | **Ledger under-reporting** (A-loop and A-reentrancy rarely listed today) could hide that the new entry is missing | IQ21-R5's per-record test |
| 10 | **Lean twins**: none exists for the typed model. I43 carved typed, UNDO and DISCH laws out (LP-G9, `I43.md:37-45`); M1's M-alpha twin is a different machine | a later Lean DISCH iteration (I43 Q4) must model storage as a finite map keyed by an inductive key with decidable equality. No change now |

---

## 7. Questions

### For the human (only the real ones)

**H1. The G2 channel for the remodel.**
- Q21 changes the M3 model's meaning under 51 unchanged frozen statements (3 SORT, 35 DISCH, 8 UNDO, 5 FACT).
- G2's `binding_change` needs a kernel-checked extensional equivalence, which cannot exist here: the store's type and
  its aliasing semantics differ by design. There is no key to sign with (Q40).
- Approve an unsigned lifecycle kind `remodel` with the mechanical criteria of §4.4 (a)-(e)? Or name another channel?
- Without one, G2 stays red on those 51 laws, labelled as pending.

**H2. Does Q21's "the M3 model" include I28's versioned machine?**
- I28's prereg (not yet committed) builds it on model3's raw storage and keccak tables.
- Its own laws need no frames: O9 is a witness, D4 and F12.5 are gaps, and the inhabitants are concrete.
- NAT (I29) over it will need frames.
- Convert it with IQ21 (or from I28's build if IQ21 lands first)? Or may it stay raw, labelled, until NAT?

### For the lead or orchestrator

| id | question |
|---|---|
| L1 | Scope: core (structural keys, frame library, key split, convoy, loop frames, tag_exact), plus F (bit-field: TI2, and groundwork for I33 W2 and I36 O34) and/or K-mono (363_anyone, O34)? Recommendation: core + F |
| L2 | Order: IQ21 after I28's build with option A1 or A2, or IQ21 before it (B). Whether I28's statement-hash re-make of the 51 typed records may use `--resume` since IQ21 supersedes it. F40's content relative to the 51 records |
| L3 | Schedule the full-budget inhabitant search for `_initialized ≥ 4` (rev TI4 and the new TI4 law), for example S1 offering `this` (the only address with code in `base_env`) to address arguments that a code-length check reads. Without it, G11V, and so I30-R6's gate clause, stays red |
| L4 | Should G1 rerun R5 (hours), so that A-keccak-structural's validation is regenerated with the model? Today R5 is a build-time record checked by a test |
| L5 | I43-R1: re-baseline `spec/M3/lib/lean_promoted.json` (precedent `4bcf535d`) plus one amendment line for the 12 DISCH status changes. I32-R2: rely on I28's amendment, or carry the same one, and check that its M1-record clause covers `generator_sha256` |
| L6 | I31's Question 2 (re-score the blocking predictions under a new key) is unanswered in `HUMAN_ANSWERS.md`. IQ21 would be that key: it scores its own predictions and leaves I31's MISSes as they are |
| L7 | The DISCH outcome run's budget: I31's 540 s per-law time box, for comparability, or the full sidecar budget (about a day) |

---

## Appendix A. Probes (scratch only; each re-runnable)

Directory: `/tmp/claude-0/-home-user-HOLON/36cc748b-c392-5d49-873b-8207b8fa8fb5/scratchpad/q21/`.

| file | what | result |
|---|---|---|
| `probe/prog.py` → `probe/programs.txt` | the Rollup document's program order per action (checks, loops with their write counts, writes with access kinds), via `load_extracted` | basis of §5.2 |
| `probe/prog_toy.py` | the same for the toy T30 | the toy's loops: put and putg `ToyTypes.sol:36-43` (no writes), sweep `:143-145` (writes `marks`) |
| `bendprobe/skmodel.bend` | the real `PRELUDE` + `_COMMON` + the SK store (1047 lines) | bend2: ALL PROOFS CHECK |
| `bendprobe/skproof.bend` | the SK frame library and the five facts of §2.3 (380 lines) | bend2 0.57 s, BendTT 0.75 s: ALL PROOFS CHECK |
| `bendprobe/skproof_bad.bend`, `skproof_bad2.bend` | a same-family frame and a same-member frame claimed by evaluation | both SOME PROOFS FAIL; residual `Bool.and(M.w_eq(k1, k2), True{})` |
| `bendprobe/perf_sk.bend`, `perf_h.bend`, `perf_base.bend` | SK store against a hashed store, the same reads and stores | bend2 1.3 s vs 2.7 s; BendTT about 4.5 s vs 5.9 s; base about 0.4 / 0.55 s |
| `bendprobe/reach_model.bend`, `reach_proof.bend` | a Reach induction of `∀k. g[k] ≠ 0 → vg[k] = 7`: putg with a key split, mark framed by evaluation, s0 by computation, induction over `Reach<-s>` | bend2 0.57 s, BendTT 0.76 s: ALL PROOFS CHECK |
| `bendprobe/reach_model_bad.bend`, `reach_proof_bad.bend` | putg writes 8 | SOME PROOFS FAIL |
| (inline) | the deployment's 18 slots classified by the recorded preimages | §3.1: 9 literal, 7 structural, 2 raw |

**Lessons, for the builder:**
- `%e : P` rewrites the goal: to replace T by T′, pass `e : {T′ == T}` (often `Equal.sym(..)`).
- A hypothesis used twice needs `+`. So does a state used twice.
- A Reach induction erases the state index (`-s`) so that `r` is the decreasing argument.

## Appendix B. Evidence index

| claim | where |
|---|---|
| Q21's answer | `docs/HUMAN_ANSWERS.md:36` |
| I30 Q1: the kh = [] counterexample; R6 MISS | `docs/iterations/I30.md:58-60`, `:260`, `:338-349` |
| I31's gap table, Q2, Not done | `docs/iterations/I31.md:170-180`, `:366-374`, `:386-392` |
| store, keys and tables in the prelude | `holon/sorts/prelude3.py:11-13`, `:521-558`, `:560-629`, `:659-660` |
| locate / read / write / struct writes / raw sload / s0 / Reach | `holon/sorts/model3.py:544-553`, `:555-589` (`:567`), `:591-603`, `:614-628`, `:630-674`, `:1649-1690`, `:440-441`, `:2276-2278`, `:2058-2061`, `:2321-2323` |
| model facts: 377 `h_get` uses, 295 of them slots; `h_get` default 0; s0; Reach | `gen/M3/sorts/models/morph_rollup_extracted.bend:844-848`, `:13878-13880`, `:14539`, `:14609` |
| init: 18 slots, 7 preimages | `gen/M3/sorts/models/morph_rollup.extracted.init.json` |
| B_228 and B_363 through `h_get` | `gen/M3/disch/models/morph_rollup_extracted_disch.bend:641-647`, `:719-721` |
| DISCH refusals and literal recogniser | `holon/disch/proofs.py:287-288`, `:426-459`; `holon/disch/section.py:61`, `:125-132` |
| DISCH frame and store lemmas over W | `holon/disch/lemmas.py:186-213`; `holon/disch/order.py:256-291` |
| UNDO and FACT slot builders | `holon/undo/trace.py:138-162`; `holon/fact/section.py:108-123` |
| evaluator, driver, search, deployment | `holon/sorts/evaluate3.py:201-203`, `:305-349`; `holon/js/eval3.mjs:30-49`; `holon/sorts/search3.py:156-167`, `:350-355`; `holon/sorts/deploy3.py:142-242` |
| replays using model states | `holon/disch/run.py:722-790`; `holon/refute_m3.py:1143-1166` |
| ledger and records | `spec/M2/ledger.json` (bundle `a38d416c…`); `holon/records.py:197-289`; `holon/undo/run.py:428-433` |
| lifecycle: binding_change needs equivalence; no key | `holon/statement_diff.py:24-31`, `:626-690`; `docs/HUMAN_ANSWERS.md:46` (Q31), `:55` (Q40) |
| bindings: 38 typed, 8 UNDO, 5 FACT, 80 PAR | `spec/bindings/M3.json` |
| closures, modifiers, checks | `gen/M3/disch/closure.json`; Morph `Rollup.sol:119-134`, `:188-224`, `:382-427`, `:430-468`, `:471-497`, `:625-669`, `:744-751` |
| I28's prereg V6 and records clause | `/home/user/HOLON-i28/tests_m3/test_versions.py` (untracked) |
| I43's carve-out and R1 | `docs/iterations/I43.md:37-45`; `tests_m3/test_lean_promoted.py:1002-1046`; `spec/M3/lib/lean_promoted.json` |
| I32-R2 | `tests_m3/test_disch_profile.py:311-336` |
| I62-D3 | `tests_m2/test_mutation_adequacy_i62.py:2689-2706` |
| F32 helpers | `tests_m3/test_eqprove.py:34` |
| I33's needs | `/tmp/claude-0/-home-user-HOLON/36cc748b-c392-5d49-873b-8207b8fa8fb5/scratchpad/i33/design.md` §1.2-1.3, §3.2 |
| I36's M9 | `/tmp/claude-0/-home-user-HOLON/36cc748b-c392-5d49-873b-8207b8fa8fb5/scratchpad/i36/design.md` §0 item 7, §b.8 |

## Coordination with the other session (2026-10-23, after the design)

- Key: I68 = the Q21 fix, all of it (model3 through the DISCH section) in one key. The other session reviews the DISCH lemma/section changes when ready (it knows that code from I31/I32).
- F40 lands first; rebase I68 onto it. Invariants F40 needs:
  - F40's Q36 inhabitant for L_disch_rev_initializable_120_d9a34b48 is a successful initialize4, whose guard reads sload(ERC-1967 admin slot) == caller. Keep the EIP-1967 admin slot RAW (this design already does).
  - F40 adds holon/sorts/envcode3.py (init["code"], consumed in search3.full_env only for actions whose entry reads code) and widens the caller pool (search3.pools_of: caller values from guards comparing ["caller"] with a stored slot/family). Orthogonal to the key representation, but the search3 hunks (pools_of, full_env, _code_reads) need a small rebase.
- F40's DISCH+FACT re-make is running on CI now; I68's re-make supersedes it for the 51 typed records (fine).
- I67 (the other session's I38a) folds its 0.3 record re-make after I65-build + I28 + (ideally) I68, to collapse machine-hours.
- Finding from I67's O4 work: a loop counter-law checks in both kernels at the real 4096-element size only when the model consumes structurally with a Nat index; per-step U32 index arithmetic (Word(32n) = 32 bit-ops per op) blows BendTT's 4e8 fuel. Keep per-step work in any I68 lemma that iterates over mapping state off U32.
