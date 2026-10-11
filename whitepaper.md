# HOLON v2: Violation as Obstructions to Commutation, with Proof-Carrying Obligations in Bend 2

*Specifications derived from system shape, finite-basis completeness theorems, a proof-carrying executable substrate, a factory that turns untrusted generators into checked results, and a case study on a production rollup.*

Draft v2, October 2026. Authors withheld. Supersedes the v1 draft of the same month.

---

### Changes from v1

**New material**
- **§8:** every protocol diagram compiles to a Bend 2 program. Obligations become laws, and outcomes are kernel-checked in both directions: proofs and counterexamples.
- **§9:** the HOLON factory. Untrusted generators and agents, frozen statements, fresh-context auditors, and a gate.
- **§12:** every known limitation, each paired with a remedy mechanism, its residual risk and a metric.
- **§15:** an executable roadmap with exit criteria, starting with a two-day experiment.
- **New theory:** rule OWN (aliasing and lost writes), intent contracts, an intent lane, discharge profiles, and Theorems 6.15–6.21.

**Corrections**
1. **DISCH ignored guards and time.** v1 computed the write closure over *callable* actions. The correct closure ranges over actions the obligated class can *enable*, by its own actions or by waiting. As a result, O33 is neither a halt (the manual analysis) nor purely a cost (v1). It is a discharge profile: pay one L1 message per batch, or wait for finalization (§5.7, §11.5).
2. **A global hash-injectivity axiom is inconsistent** (Thm 6.15). v1's Appendix D stated one, universally quantified. v2 uses only local collision-freedom premises, written visibly in each statement, plus ground instances in solver queries.
3. **SYM no longer promotes majority behaviour to specification** without independent evidence (§5.4).

---

## Abstract

High-value protocol stacks are assemblies of contracts, nodes, encoders and provers. Examples are rollups, bridges, and restaking and settlement systems. Their components are:
- written in different languages;
- upgraded while objects are in flight;
- driven by principals with conflicting incentives.

Their most damaging defects are *relational*. Every code path involved is locally plausible, and the defect is a relation among them. Such relations are rarely specified, and analyses that look at one component, version or execution at a time cannot see them.

These systems specify themselves. Each of the following asserts an equation or an enabledness condition:
- representing a fact twice;
- encoding in one component and decoding in another;
- carrying an object across an upgrade;
- treating timestamps or principals uniformly;
- committing on-chain to data consumed off-chain;
- undoing an action;
- guarding an action with an obligation;
- sharing a buffer.

HOLON formalizes this as a *protocol diagram* and derives its specification with eight shape rules. Defects are *obstructions* to commutation. Finite-basis theorems reduce each rule's infinite family of intended equations to a basis linear in the size of the diagram.

v2 makes the obligations proof-carrying. The diagram compiles to a Bend 2 program in which:
- carriers are types;
- code paths are functions;
- refined semantic sorts are distinct types;
- every obligation is a law that the type checker must certify.

Statements are generated deterministically and frozen by content hash. Untrusted proof generators, including AI agents, can supply proofs but can never weaken claims. Every obligation ends in exactly one of three outcomes:
- a kernel-checked proof, which is a certificate of absence relative to the model;
- a kernel-checked counter-law with a concrete witness, which is an obstruction;
- an explicitly scoped UNKNOWN.

The same model compiles to native code, so it is replayed differentially against the deployed implementations. This turns extraction soundness from an assumption into measured refinement evidence. Hash and oracle assumptions appear only as visible premises. We show that the common global injectivity axiom is inconsistent and replace it.

We applied the rules by hand to the batch lifecycle of the Morph rollup. They:
- reproduce a prior manual analysis, except two memory-ownership items that the new OWN rule now covers;
- reconcile one disputed severity as a discharge profile;
- certify several suspected issues absent, relative to the diagram;
- surface four obstructions the manual analysis missed.

We preregister the mechanized outcome of every obligation in the first two milestones, and pair each limitation of the method with a concrete remedy.

---

## 1 Introduction

### 1.1 Where defects live

A rollup consists of at least five things:
- an L1 contract suite;
- an off-chain node that re-derives L2 state from L1 data;
- a batch producer that encodes that data;
- circuits that interpret the same bytes;
- a history of upgrades that reinterpret state created under earlier code.

Each fact the system relies on is represented several times, in several languages, across several versions, and is acted upon by principals whose payoffs differ. Examples of such facts are "which L1 messages are included", "what this batch's blob commits to" and "at which L2 height the batch ends". The defects that matter are relations between these representations, not errors inside any one of them.

### 1.2 Why current approaches miss relational defects

- **Fuzzing and property testing** need an oracle and a harness. For relational defects the oracle is a cross-component equation and the harness spans languages and versions, and neither exists by default.
- **Symbolic execution and model checking** need properties, and those properties are written per component.
- **Pattern detectors** match local syntax. Relational defects have no local syntax.
- **Specification mining and deviant-behaviour inference** recover beliefs from frequency. They have no completeness notion and are typically single-language.
- **Deductive verification** proves what is specified, and the relational specification is exactly what is missing.
- **Review**, human or automated, samples. The probability of noticing a relation falls with the distance between its two halves.

### 1.3 Thesis: redundancy is specification

| If the system… | it implicitly asserts that… |
|---|---|
| represents a fact twice | the two representations agree |
| encodes in one component and decodes in another | the round trip is the identity |
| upgrades code while objects are in flight | those objects behave as if the new code had created them |
| treats timestamps, indices or principals uniformly in most transitions | the uniformity holds, so the transitions that break it are suspect |
| commits on L1 to data that something consumes off-chain | the consumption is determined by the commitment |
| undoes an action | what remains is indistinguishable from never having acted |
| guards an action with an obligation | the obligated party can discharge it |
| hands out a view of a buffer it later mutates | the view is no longer live when the buffer changes |

### 1.4 The gap v1 left

v1 produced obligations and a checking strategy. Three questions stayed open.

- **Who discharges thousands of obligations?** A single target yields hundreds to thousands of them. Hand proof does not scale. Automated provers, AI agents above all, have an incentive to weaken what they are asked to prove.
- **Why should anyone trust the discharger?** A solver's `unsat`, a fuzzer's silence and an agent's "done" are different kinds of evidence. v1 put them all under the word "certificate".
- **What links the model to the deployed code?** v1 named extraction soundness as its main limitation, without a mechanism.

v2 answers all three with one substrate and one process:
- Obligations compile to laws in a language whose type checker is a proof checker (Bend 2, §8).
- A factory surrounds that checker with deterministic generators, frozen statements, adversarial auditors and a gate (§9).
- The same compiled model runs natively against the real implementations. This measures the gap that proofs about a model cannot close.

### 1.5 Contributions

- **C1. Protocol diagrams (§4).** A single typed structure spanning languages, components, versions and principals.
- **C2. Eight shape rules (§5).** PAR, UNDO, NAT, SYM, FACT, SORT, DISCH and OWN, together with an evidence calculus, intent contracts and an intent lane.
- **C3. Obstruction theory (§6).**
  - finite-basis theorems;
  - time-aware dischargeability and discharge profiles;
  - inconsistency of global hash injectivity, and the conservativity of local premises;
  - two-sided soundness of checked outcomes;
  - sorts-as-types soundness;
  - ghost-tag exactness.
- **C4. Refined semantic sorts compiled to types (§7).** Sign, width and coherence obligations become typing obligations.
- **C5. Proof-carrying executable semantics in Bend 2 (§8),** with a kernel-agnostic law IR.
- **C6. The HOLON factory (§9).** Deterministic generators, frozen statements, untrusted provers and refuters, native replay, auditors and a gate.
- **C7. Algorithms (§10)** for extraction, basis reduction, proof and refutation, liveness, discharge profiles, symmetry splits and witness concretization.
- **C8. A case study (§11),** with preregistered predictions for the mechanized rerun.
- **C9. Limitations and remedies (§12).**
- **C10. An evaluation protocol (§13) and a roadmap (§15).**

### 1.6 Scope and non-goals

- HOLON complements fuzzing for single-function arithmetic; it does not replace it.
- Cryptographic soundness is assumed through visible premises, never proved.
- Certificates hold relative to the model. Their link to deployed code is refinement *evidence*, measured and reported, not proof.
- Bend 2 is the primary substrate, but the theory does not depend on it. Laws are kernel-agnostic and are exported to a second kernel (§8.9).

---

## 2 Motivating Example

### 2.1 The system

Morph's L1 contract accepts batches identified by headers of 249 or 257 bytes, in three versions.

**Per batch index *i*, the contract stores:**
- a header hash CB_i;
- a committed post-state root CSR_i;
- a blob-commitment value BVH_i;
- timing and attribution data BD_i.

**Ways a batch is resolved:**
- optimistic finalization after a challenge window;
- an immediate path for batches accompanied by a validity proof;
- an owner-only revert.

**Off-chain components:** a Go node derives L2 blocks from the blobs, and a Go library produces headers and blobs.

**Messaging:** an L1 message queue and a cross-domain messenger connect the layers.

### 2.2 A cycle that flips meaning

BVH_i is written by two commit paths with different meanings:
- versions 0 and 1 write one blob's versioned hash;
- version 2 writes keccak256 of all the blob versioned hashes, concatenated.

After a revert, the recommit path copies BVH_i into a header whose version the caller chooses. The Go decoder and the verifier router read header bytes 57–89 according to the header's version.

```
  β ──H(β₀‖…‖β_{k-1})──┐ commit(v=2)            commitState(v'=1)                 Dec_go^{v=1}
                       ├──▶ BVH_i ─────────────────────────────────▶ hdr[57:89] ──────────────▶ "versioned hash"
  β ──β₀ (or Z)────────┘ commit(v≤1)
```

Every edge is byte-exact, yet the fact carried around the loop returns with a different semantic type. The tag that would disambiguate BVH_i is the version byte inside the committed header. The revert erases the header hash and keeps BVH_i: the undo erases the tag and keeps the payload.

### 2.3 A residue that outlives its undo

| Register | Written by commit | Cleared by revert | Read before overwrite? |
|---|---|---|---|
| CB_i | yes | yes | — |
| CSR_i | yes | no | no |
| BVH_i | yes | no | **yes, by the guards of every commit at *i*** |
| BD_i | yes | no | no |

One of the three residues is live. It forces every future commit at *i* to reuse the reverted batch's blob.

### 2.4 An obligation with a discharge profile

The optimistic commit path is guarded by:
- κ ≡ `enq[P] + D < t`, a condition on the enqueue time of the oldest *unfinalized* message;
- ρ ≡ `n > 0`, the requirement that the batch include at least one message.

Satisfying ρ requires an *unincluded* message to exist (T < L).

| Register | Meaning | Written by |
|---|---|---|
| P | finalization cursor | finalization, which is permissionless once its window has elapsed |
| T | inclusion cursor | commit |
| L | queue length | anyone, via `sendMessage` |

The submitter cannot falsify κ immediately. It has two discharge strategies:
- **Pay:** send one L1 message, then include it. This costs one message per batch.
- **Wait:** let windows elapse and call finalization, which advances P. This costs zero, with a delay up to the finalization latency.

The discharge profile is therefore {(c_msg, 0), (0, Δ_fin)}. The manual analysis saw only the waiting strategy and called it a halt. v1 saw only the paying strategy and called it a cost. Both are points on the same Pareto frontier.

### 2.5 What mechanization adds

For each example, HOLON v2 emits a frozen law over the compiled model and drives it to a checked outcome:
- **§2.2:** a ghost-tag law at the recommit read. It is refuted by a witness trace: commit with version 2, then revert, then recommit with version 1.
- **§2.3:** three UNDO laws.
  - CSR_i and BD_i are proved, via a supplied bisimulation relation.
  - BVH_i is refuted, via a trace in which a fresh commit succeeds in one run and reverts in the other.
- **§2.4:** a DISCH profile theorem, whose two strategies are themselves checked programs.

Every witness is then replayed against the real contract.

---

## 3 Preliminaries

**3.1 Paths.**
- A directed multigraph is G = (V, E, src, tgt).
- Paths are composed in diagrammatic order: ⟦e₁⋯e_k⟧ = ⟦e_k⟧ ∘ ⋯ ∘ ⟦e₁⟧.
- P(G) is the path category. Walks may traverse edges backwards. F(G) is the free groupoid.

**3.2 Fundamental cycles.**
- Fix a spanning forest T, with tree walks t_v.
- For a non-tree edge e, c_e = t_{src(e)} · e · t_{tgt(e)}⁻¹.
- There are |E| − |V| + κ(G) of them, where κ(G) is the number of components, and π₁(G, v₀) is free on them.

**3.3 Holonomy.** Edges are labeled by bijections R_{src} → R_{tgt}. The holonomy of a closed walk is its composite, and the assignment is *flat* if every holonomy is the identity.

**3.4 Equivariance.** T is g-equivariant if (s, x, s′) ∈ T ⇔ (g·s, g·x, g·s′) ∈ T.

**3.5 Naturality.** For a migration η: S_k → S_{k+1}, naturality is η ∘ op^k = op^{k+1} ∘ η on a domain D.

**3.6 Kernels.** ker(f) = {(x, x′) : f x = f x′}. A map c factors through m on R iff c = φ ∘ m on R for some φ.

**3.7 Hyperproperties.** A 2-safety property relates pairs of executions. Product programs reduce it to ordinary safety.

**3.8 Cost-indexed systems.** The enabled set at gas ceiling G is En_G(s) = {(a, x) : γ_a(s, x) ∧ cost_a(s, x) ≤ G}.

**3.9 Solver logic.**
- **QF_UFBV:** quantifier-free bitvectors with uninterpreted functions.
- **Ground injectivity:** for the finite set of terms appearing in one query, the axioms f(t) = f(u) ⇒ t = u.
- **Projected model counting:** counting distinct values of designated variables.

**3.10 Time as environment.**
- Time progress is an environment move, and every principal may wait for it.
- A guard that depends only on time and on the actor's own registers is dischargeable by waiting, with a delay.
- A guard that depends on other principals' registers is not.

**3.11 Dependent types, laws and witnesses.**
- Propositions are types and proofs are terms. A *law* is a type, and its proof is a term the kernel checks.
- With decidable equality on finite data, a closed proposition about concrete values is checked by evaluation. A *counter-law* ∃x. ¬P(x) is therefore certified by presenting x itself.
- A total language requires terminating definitions. Unbounded behaviour is expressed through well-founded measures, invariants, bisimulations or explicit fuel. Bounded results carry their bound in their scope label.

---

## 4 Protocol Diagrams

**Definition 4.1 (Carrier).** A carrier is v = (⟦v⟧, R_v, σ_v): a value set, a reachable subset and a refined sort.

| Carrier class | Examples |
|---|---|
| Representation | byte strings, records, field-element vectors, decompressed streams |
| State | register families keyed by an index set |
| Environment | time, blob-hash vector, caller, attached value |
| Digest | outputs of hash and commitment maps |

- Records are product carriers, and field projections belong to the product structure rather than being edges.
- Interface carriers have an *external* reachable set R^ext: everything any principal can place there.

**Definition 4.2 (Edge).** Every edge has:
- a kind, one of: CODEC, HASH, STORE, LOAD, CONS, TRANS, MIG, SYM;
- an interpretation: a partial function, or a relation for TRANS;
- a component label and a version label.

TRANS edges additionally carry:
- a principal class;
- a guard;
- a cost term;
- index-sensitive read and write sets.

**Definition 4.3 (Protocol diagram).** 𝔇 = (V_rep, E_rep, {S_k}, {A_k}, M, 𝔉, Cm, Cn, Π, cost):

| Component | Meaning |
|---|---|
| V_rep, E_rep | the representation layer |
| S_k, A_k | the state carrier and transitions of version k |
| M | migrations |
| 𝔉 | candidate symmetry families |
| Cm | commitments (outputs verified on L1) |
| Cn | consumers (security-relevant outputs derived from committed data) |
| Π, cost | principal classes and cost terms |

**Definition 4.4 (Invertible and lossy fragments).**
- An edge is *invertible* if it is injective on R_src.
- HASH edges count as invertible *under local collision-freedom premises* (Cor 6.16).
- Truncations, saturations, tolerant decoders and most consumers form the lossy fragment.

**Definition 4.5 (Evidence).** For parallel paths p and q, the evidence level is the highest one supported:

| Level | Code | Source |
|---|---|---|
| strong | E1 | encoder/decoder pair, mutually inverse on some fields per the layout algebra |
| strong | E2 | written via p, read via q |
| strong | E3 | the system compares the outputs of p and q itself |
| strong | E4 | q recomputes a value stored via p |
| medium | E5 | identical refined sorts at the endpoints |
| weak | E6 | lexical only (names, comments) |

Strong and medium evidence yields defects. Weak evidence yields *intent questions*.

**Definition 4.6 (Morph excerpt).** The Morph diagram contains:
- **Header codecs:** in Solidity and Go.
- **Payload pipeline:** builder → payload → compressed → blobs → β → b57.
- **Derivation pipeline:** blobs → stream → derived blocks.
- **Commitments:** header hash, versioned hash, data hash, public input.
- **Transitions:** three commit kinds, revert, challenge, prove, finalize, pause; registry, queue and messenger actions.
- **Migrations:** η₂, η₃, η₄, η_enq, η_BVH.
- **Symmetry families:** time, index, principal and order.

Appendix B gives the full listing.

**Definition 4.7 (Executable model, refinement record).**
- **The model 𝔅(𝔇).** A Bend program with one type per carrier and one function per edge (or per transition), plus an inductive reachability predicate for each state carrier (§8.3).
- **Refinement record.** For each edge e, the record ρ(e) holds:
  - a reference to the implementation code;
  - the replay corpus;
  - the agreement count;
  - the classified disagreements;
  - the mutation-adequacy results.
- **Certificate scope.** A certificate is relative to 𝔅(𝔇), and lists the refinement records of every edge its proof uses.

---

## 5 Specifications from Shape

Each rule maps 𝔇 to *obligations*, which are compiled into frozen laws (§8.4).

### 5.1 PAR: parallel-path commutation and domain coherence

**Obligation.** For parallel paths p, q with evidence at least medium, ⟦p⟧ = ⟦q⟧ on R, *including definedness*.

**Sub-forms:**
- round trip;
- cross-component codec agreement;
- recomputation;
- consumer agreement;
- branch agreement;
- initialization coherence (E3 equations must hold in the initial states).

**Domain coherence.** At every interface carrier, all decoders must have equal domains on R^ext. Otherwise some principal can create a value that is valid in one component and fatal in another.

**Morph instances:**
- v0 decoder length domains: Solidity accepts len(h) ≥ 249, Go accepts len(h) = 249;
- the Go version byte is constant;
- clone definedness differs;
- the size estimator's fast path diverges from its slow path;
- the genesis cursor is unconstrained.

### 5.2 UNDO: undo-loop residue

**Undo pairs.** (a, ā) is an undo pair when:
- ā's guard references a's writes; or
- ā restores a cursor that a advanced; or
- ā emits an inverse event.

**Residue.** Res(a, ā)(s) = {r : (ā ∘ a)(s)(r) ≠ s(r)}.

**Obligation.** Every residue register is dead after ā (Thm 6.9).

**Morph instances:**
- commit/revert, whose live residue is BVH_i;
- challenge/cancel, whose live residue is the +W extensions.

### 5.3 NAT: naturality and native equivalence across migrations

For each migration, each in-flight object type, and each new-version operation that reads it:
- **(a) Native equivalence:** op^{k+1}(η(s)) ≈ op^{k+1}(s^nat).
- **(b) Naturality:** where op^k exists, η ∘ op^k = op^{k+1} ∘ η.
- **(c) Composition coherence:** all reachable migration sequences coincide.

**Morph instances:**
- the cutover drops bonds of in-flight batches;
- η₂ populates CSR only at the last committed index;
- η_enq leaves legacy enqueue times at zero;
- η₄ can run before η₃.

### 5.4 SYM: symmetry splits (revised)

**Candidate families:** time translation τ, index translation ι, principal permutation π within roles, unit scaling μ, and reordering ω.

**Change from v1.** v1 promoted the non-equivariant minority of an established family to defects. That treats frequency as specification: if most functions share a bug, the bug becomes the specification. v2 instead reports a *split* A = A_eq ⊎ A_break.

**A split becomes an obstruction only if:**
- **(i)** strong evidence (E1–E4), an intent contract (§5.9) or the intent lane (§5.10) marks the family as intended; or
- **(ii)** the auditor adjudicates both hypotheses, "the minority deviates" and "the majority deviates", and the evidence decides.

**Reordering pairs** are reported when:
- the two actions belong to different principal classes;
- both orders execute;
- the results differ on a sink-reaching register.

Disabling races are classified separately.

**Sentinels.** Translation splits localize *sentinel conflation*: constants compared against Time- or Idx-sorted registers.

**Morph instances:**
- proof-backed commit versus challenge (ω);
- the implicit address(0) role (π);
- `enq = 0` (τ).

### 5.5 FACT: factorization through commitments

**Obligation.** For every commitment m and every consumer c in its scope: ker(m) ⊆ ker(c) on R, under local collision-freedom premises for each hash involved (Cor 6.16). The quantitative form reports the adversary's freedom in bits.

**Morph instances:**
- "no blob" and "zero blob" are conflated by Z;
- the parent's lastBlockNumber is outside the public input;
- version-0 calldata contexts are unbound;
- slashing attribution diverges from content choice.

### 5.6 SORT: functoriality of the sort map

Sort obligations:
- edge preservation;
- no untagged-union reads at a member sort;
- sign obligations;
- width obligations;
- conservation;
- payer/bearer keying.

In v2 all of these compile to typing obligations (§7.8, Thm 6.18).

### 5.7 DISCH: dischargeability (revised)

Let action a have guard conjunct κ ⇒ ρ and obligated class X.

**Enableable write closure.** Write*_X is the least set of registers such that some action b writes them, where:
- b is callable by X (or by anyone); and
- b's guard can be made true by X's own actions and time progress alone.

Registers whose writers need another principal's action are excluded. v1 omitted the enablement condition. Under it, a permissionless action guarded by another principal's state does not count for X.

**Discharge profile** (Def 6.20). DP_X(g, s) is the Pareto set of (cost, delay) pairs over X-strategies that make the guard hold for one occurrence. A separate *persistent* profile covers strategies that falsify κ until its next trigger.

| Class | Condition |
|---|---|
| Immediate | (0, 0) ∈ DP |
| Cost-bearing | only points (c, 0) with c > 0 |
| Delay-dischargeable | only points (0, δ) with δ > 0 |
| Mixed | Pareto points of both kinds |
| External-dependent | DP_X = ∅, but DP_{X∪Y} ≠ ∅ for a named class Y |
| Non-dischargeable | empty for every principal: only an upgrade discharges it |

**Self-controlled enabledness.** If a's success harms class Y, and cost_a or γ_a depends on registers that Y can grow without bound, Y can disable its own constraint.

**Morph instances:**
- the stale challenge (external: submitters or owner);
- the BVH pin (non-dischargeable);
- the delay guard (mixed);
- the replay budget (external: owner);
- challenge gas (self-controlled).

### 5.8 OWN: aliasing and lost writes (new)

**Carriers.** Buffers carry a backing identity. A Go slice, for instance, is (backing, offset, length, capacity).

**OWN-alias.** A view returned to a caller must not have its backing region written, except through the view itself, while the view is live. The exception is a contract that explicitly declares the view volatile.

**OWN-lost-write.** A write to a copy whose lifetime ends before any read is an obstruction when strong evidence shows the effect was meant to persist. A typical case is a value receiver: evidence E2 shows the field is read later through the original object.

**Morph instances:**
- `TxsPayloadV2` returns a slice aliasing the spare capacity of the block-context buffer, and a later `Append` writes into it. This is conditional on the caller holding the view across the `Append`.
- The value-receiver header cache: its write is lost.

These were the two sub-items v1 could not classify.

### 5.9 Intent contracts (replacing bare annotations)

An asymmetry may be designed. Its annotation is then `@intended(rule, scope, L_weak)`, where:
- L_weak is a *weaker law* that must be proved;
- the obstruction is suppressed only within the scope where L_weak holds;
- contracts are frozen and re-proved on every change.

**Example (O12).** The +W extension that a challenge applies to other batches is intended. The contract bounds it:
- Statement: f_j ≤ commit_j + F + W · (number of challenges started while j is unfinalized).
- If the proof succeeds, cancellation residue within that bound is reported as *intended-bounded* rather than suppressed outright.

### 5.10 The intent lane (new)

HOLON's own laws are derived from the implementation. A system that is *consistently* wrong is therefore invisible to it: a wrong formula implemented identically everywhere means every redundancy agrees.

The intent lane closes this gap:
- **Source.** Normative documentation is atomized into evidence records with exact source spans.
- **Compilation.** The records compile into a separate law family, INTENT/, over the same model.
- **Trust.** Intent laws carry the human-trust burden of a spec transcription. Each clause is reviewed against its source span.
- **Output.** A disagreement between an intent law and the implementation is an *intent obstruction*.

---

## 6 Obstruction Theory

**Definition 6.1.**
- An equation p ≐ q is *valid* if ⟦p⟧ = ⟦q⟧ on R, including definedness.
- An *obstruction* is an equation together with a witness on which the two sides differ.

**Lemma 6.2 (Congruence).** Valid equations are closed under symmetry, transitivity and whiskering. Checking a generating set therefore establishes the congruence it generates. *Proof:* ⟦·⟧ preserves composition. ∎

**Theorem 6.3 (Domain coherence is local).** If every invertible edge maps R_src onto R_tgt, then every walk does. A mismatch on a composite implies a mismatch on some single edge. *Proof:* induction on walk length. ∎

**Theorem 6.4 (Fundamental cycles are complete for the invertible fragment).** For a connected, domain-coherent invertible fragment with spanning tree T, the following are equivalent:
- (i) every closed walk has identity holonomy;
- (ii) all parallel walks agree;
- (iii) every fundamental cycle c_e has identity holonomy.

*Proof.*
- **(i) ⇔ (ii):** t_u · p · q⁻¹ · t_u⁻¹ is closed, so by bijectivity its holonomy is the identity iff ⟦p⟧ = ⟦q⟧.
- **(iii) ⇒ (i):**
  1. After each step of γ, insert t_{u_j}⁻¹ t_{u_j}; this preserves ⟦γ⟧.
  2. This factors γ into walks t_{u_{j−1}} · e_j^{ε_j} · t_{u_j}⁻¹.
  3. Tree edges reduce to empty walks by cancelling backtracking.
  4. Non-tree edges give c_e^{±1}, which are identities by (iii). ∎

**Corollary 6.5 (Global frame).** The fragment is flat iff it has potentials φ_v with ⟦e⟧ = φ_tgt⁻¹ ∘ φ_src. It takes |E| − |V| + κ checks.

**Theorem 6.6 (Generators suffice for equivariance).** Stab(T_a) is a subgroup, or a submonoid for partial actions. *Proof:* closure under composition, plus inverses by applying the defining equivalence to g⁻¹-images. ∎

**Theorem 6.7 (Naturality).**
- **(a) Pasting:** squares for op₁ and op₂ give the square for op₂ ∘ op₁ when op₁ preserves D.
- **(b) Vertical composition:** natural η₁ and η₂ compose.
- **(c) Consequence:** it suffices to check entry points × in-flight types, plus reachable migration sequences.

*Proof:* by direct rewriting. ∎

**Theorem 6.8 (Factorization).** The following are equivalent:
- (i) c = φ ∘ m on R;
- (ii) ker(m) ∩ R² ⊆ ker(c);
- (iii) m(x) = m(x′) ⇒ c(x) = c(x′).

The freedom F(m, c) = max_μ log₂ |c(m⁻¹(μ) ∩ R)| is 0 iff these hold. ∎

**Theorem 6.9 (Undo residue is observable iff live).** For deterministic actions with observations (outputs, success or revert):
- **(i)** If every residue register is dead after ā, then s and (ā ∘ a)(s) are observationally equivalent.
- **(ii)** If some residue register is read before it is written, by a step whose observation depends on it, the two states are distinguished.

*Proof.*
- **(i):** induction on trace length. The first differing read would be a read of a residue register before any write, which contradicts deadness.
- **(ii):** the first such read is the first divergence. ∎

**Theorem 6.10 (Blocking, time-aware; revises v1).** Let Write*_X be the enableable write closure (§5.7). Suppose:
1. Read(κ) ∩ Write*_X = ∅, and
2. Dep(Sat_ρ) ∩ Write*_X = ∅.

Then from any reachable state with κ true and Sat_ρ empty, every state reachable by X-actions and time progress keeps κ true and Sat_ρ empty. X is blocked until another principal acts.

*Proof.* Time-gated actions enableable by X are already included in Write*_X. All other registers are invariant under X-actions and time. ∎

**Proposition 6.11 (No topological basis for the lossy fragment).**
- For non-injective h, h ∘ f ≐ h ∘ g does not imply f ≐ g.
- Lossy obligations must therefore be enumerated from evidence, and completeness is relative to the evidenced set.

**Lemma 6.12 (Injective pushing).** If h is injective on f(R) ∪ g(R), then h ∘ f ≐ h ∘ g ⇔ f ≐ g.

**Definition 6.13 (Quantitative measures).**

| Measure | Rule |
|---|---|
| holonomy defect size | PAR |
| naturality defect mass | NAT |
| adversarial freedom F(m, c) | FACT |
| residue liveness distance | UNDO |
| discharge profile | DISCH |

**Remark 6.14 (Sheaf reading).** Transport maps form a non-abelian Čech 1-cochain over the cover of the system by components. Flatness is the vanishing of its class. This explains why no pairwise check witnesses these obstructions.

**Theorem 6.15 (Global hash injectivity is inconsistent).** No function h from byte strings to 256-bit values is injective.

*Proof.* The 2²⁶⁴ strings of length 33 map into 2²⁵⁶ values, so two of them collide (pigeonhole). ∎

Consequence: any theory containing the axiom Inj(h) proves every law. An automated prover would eventually exploit such an axiom.

**Corollary 6.16 (Local premises are conservative).** For a finite set S, define CF(h, S) ≡ ∀x, y ∈ S. h x = h y ⇒ x = y. Then:
- CF(h, S) is satisfiable whenever |S| ≤ 2²⁵⁶.
- A law ∀h. CF(h, S) ⇒ P(h) adds no axioms.
- If proved, P(keccak) holds in every execution in which keccak has no collision on S. Under the standard assumption, a collision is an event of negligible probability.
- The solver encodings use ground injectivity only over a query's own terms, which is exactly CF(h, S_query).

**Theorem 6.17 (Two-sided soundness).** Assume kernel soundness and that the committed files add no axioms (Gate G3). Then:
- If the kernel accepts a proof of L, then L holds in 𝔅.
- If L = ∀x. P(x), and the kernel accepts a pair (w, π) with π : ¬P(w), then L fails in 𝔅 at w.
- The two outcomes are mutually exclusive, by consistency of the base theory.
- UNKNOWN carries no semantic conclusion. ∎

**Theorem 6.18 (Sorts as types).** Suppose:
- refined sorts are assigned by inference (§7.7);
- the assignment is frozen *before* type checking;
- 𝔅 is generated with one distinct type per refined sort, affine operations only as permitted, and realizations that require non-negativity proofs.

Then if 𝔅 type-checks with all coercion proofs present, every SORT obligation holds in 𝔅. Conversely, each SORT failure is localized to a type error, or to an unprovable coercion premise, at a specific site.

*Proof.* Each obligation is encoded as a typing rule or a coercion premise. ∎

The freezing condition is essential. If types were assigned *after* seeing whether the model checks, sort errors could be laundered into the type assignment.

**Proposition 6.19 (Ghost-tag exactness).**
- **Augmentation.** Give each union-typed register a ghost tag recording which writer last wrote it. Ghost fields are never read by operations that model real code, so the augmentation adds no behaviour.
- **Exactness.** A read at site ℓ that assumes member σ is safe iff the law ∀s ∈ Reach_ℓ. tag(s) = σ holds.

**Definition 6.20 (Discharge profile).**
- An X-strategy is a terminating program that interleaves X-actions with waits.
- Its outcome is (total cost, elapsed time until the guard holds).
- DP_X(g, s) is the Pareto-minimal set of outcomes. The persistent variant requires κ to stay false until its next trigger.

**Proposition 6.21 (Profile computation).** On a finite abstraction, DP_X is computed exactly by bi-criteria label-correcting search over the cost × delay graph. Each Pareto point is witnessed by a strategy that the kernel checks as a program, and blocking is witnessed by a Thm 6.10 invariant. ∎

---

## 7 Refined Semantic Sorts

### 7.1 Grammar

σ ::= Mach(w) | Time | Dur^± | Idx[κ] | Cnt[κ]^± | Prin[role] | Amt[asset] | Dig[kind] | Ver | Bool | σ₁ + σ₂ | ⟨fields⟩

### 7.2 Affine rules

Time is a torsor over Dur, and Idx[κ] is a torsor over Cnt[κ]:

| Expression | Sort |
|---|---|
| Time − Time | Dur^± |
| Time + Dur | Time |
| Time + Time | ill-sorted |
| Idx[κ] − Idx[κ] | Cnt[κ]^± |
| Idx[κ] + Cnt[κ] | Idx[κ] |
| Idx[κ] − Cnt[κ] | Idx[κ]^± |
| any operation mixing index families | ill-sorted |

A signed sort realized in unsigned arithmetic generates a sign obligation.

### 7.3 Writer-provenance refinement

Registers with the same base sort but different writer sets, and with no value flow between them, receive distinct refined sorts. For example, the queue's two cursors refine to Idx[queue]_fin (P) and Idx[queue]_inc (T).

**Obligation coherence.** A guard κ ⇒ ρ must read a sort that is written by the action family that ρ constrains.

### 7.4 Untagged unions

A register written along edges with distinct refined sorts carries σ₁ + σ₂. Reading it at a member sort is an obstruction unless the reachable states guarantee the right member (Prop 6.19).

### 7.5 Principal and amount sorts

- **Payer/bearer:** a waiver must be keyed by the principal that bears the cost.
- **Conservation:** every inflow is accounted for, and every debit has a matching outflow.

### 7.6 Width

A sum of k width-w terms, realized in width w, generates an overflow obligation.

### 7.7 Inference

1. Constraints come from types, value flow, the affine rules, comparisons, cross-component linking and lexical seeds.
2. Solve with union-find, carrying writer and role labels.
3. Detect conflicts and unions.
4. Explain each conflict with a minimal unsatisfiable core.
5. Report cross-component sort equations that the code does not imply as explicit assumptions.

### 7.8 Sorts compiled to Bend types (new)

The model generator emits one nominal type per refined sort. Affine arithmetic exists only as typed functions:
- `time_sub : Time → Time → SDur`
- `realize : (d : SDur) → Proof(d ≥ 0) → Dur`

These have three consequences.
- **Sign obligations become proof arguments.** Every unsigned realization of a signed quantity in the real code becomes a `realize` call whose proof argument the prover must supply, and which is unfillable when an underflow is reachable. At Morph's commit site, `W + s − t` becomes `realize(add(W, time_sub(s, t)), ?)`. The hole is unprovable under inChallenge ∧ t > s + W, and refutation produces exactly that state (O27).
- **Writer-provenance becomes typing.** The delay-guard constructor is typed by the cursor sort that its requirement advances (Idx_inc). Extracted code that passes P, which is Idx_fin, fails to type-check at that exact site (O16 and O33 coherence).
- **Unions become ghost-tagged sums.** Real-code reads compile to `as_member(x, ?tag_proof)`. The tag proof is the Prop 6.19 law (O26).

Type assignments come from inference and are frozen with the laws. A type error is never "fixed" by changing an assignment; it is reported.

---

## 8 Proof-Carrying Executable Semantics in Bend 2

### 8.1 Requirements

| ID | Requirement | Why HOLON needs it |
|---|---|---|
| R1 | One artifact that is both executable and provable | The model that is proved must be the model that is replayed and concretized |
| R2 | A checker that acts as a gate | Untrusted generators and agents may contribute only checked artifacts |
| R3 | Fast checking | Thousands of laws per target, re-checked from scratch on every change |
| R4 | Native compilation | High-throughput differential replay and witness concretization |
| R5 | Parallel and accelerator targets | Bounded refutation search is embarrassingly parallel |
| R6 | Kernel-agnostic statements | Independent re-checking in a second kernel |

### 8.2 The substrate

**What Bend 2 provides** (claims from public sources, not independently verified):
- It became public on 17 September 2026 and compiles to C, Metal, CUDA and JavaScript.
- Its type checker doubles as a proof checker. After each change the compiler demands a mechanical proof that every declared law still holds, and refuses to produce a binary otherwise.
- The language is affine and requires terminating recursion.
- Laws are declared in a `LAWS.bend` file and proofs live in a `PROOF.bend` file checked by the compiler.
- Its project page claims proof checking several orders of magnitude faster than other proof assistants. We treat this as a claim to measure, not a premise.
- The release documentation notes that the checker's own implementation has not yet had the human review its output is meant to replace. §8.8 addresses this.
- A proof agent, Bender, was introduced alongside the launch. In HOLON it is one untrusted prover among several.

**What HOLON assumes:**
- a sound kernel, mitigated by the measures in §8.8;
- dependent types expressive enough for ∀/∃ over finite data and inductive predicates;
- evaluation-based checking of closed decidable propositions;
- native compilation of the model.

**What HOLON does not assume:** any particular standard library, bitvector decision procedure, solver integration or tactic automation. HOLON's core library and generators supply whatever is missing.

Bend 2 is chosen for R1–R5 together. Lean 4 meets R1, R2 and R4, with mature libraries and certified bitvector automation, so it serves as the second kernel under R6 (§8.8–8.9).

### 8.3 Compiling 𝔇 to 𝔅

| Diagram element | Bend artifact |
|---|---|
| Carrier v with refined sort σ | Nominal type T_σ; records as product types; byte strings as length-indexed types |
| CODEC edge | Function; partial edges return an option type, so definedness is explicit |
| HASH edge | Opaque parameter `h : Bytes → B32`; never an axiom |
| State carrier S_k | Record with functional maps keyed by index; affine threading of the state |
| TRANS edge | `step_a : S → In → Env → Result(S, Obs)`; revert is a result variant; the guard is part of the function; cost is a sibling function |
| Loops in transitions | Structural recursion on a bounded index range, or explicit fuel |
| MIG edge | `η_k : S_k → S_{k+1}`; native-creation map `nat_k` |
| SYM generator | `g_S : S → S`, `g_In : In → In` |
| Commitment, consumer | Functions m, c, parametric in hash and oracle parameters |
| Principal class | Caller type plus a permission predicate |
| Reachable set R | Inductive predicate `Reach : S → Type`, generated by S₀ and the steps |
| External set R^ext | The full input type at the interface |
| Oracle (codec, circuit) | Module parameter together with a hypothesis predicate (§8.5) |
| Union register | Ghost-tagged sum (Prop 6.19) |

### 8.4 Law schemas

| Rule | Law (schematic) | Proof route | Refutation form |
|---|---|---|---|
| PAR | ∀x : R_u. P(x) = Q(x) | evaluation, induction, layout lemmas | x with P(x) ≠ Q(x), checked by evaluation |
| PAR-domain | ∀b : Bytes. defined(decA b) ↔ defined(decB b) | case split on length and version | b |
| UNDO | ∀s : Reach. B(s, undo(do(s))), for a supplied relation B that is a bisimulation | step lemmas per action (Thm 6.9i) | trace τ with differing observations |
| NAT | ∀s : InFlight. Obs(op′(η s)) = Obs(op′(nat s)) | per entry point | in-flight state |
| SYM | ∀s, x. step(g s, g x) = g(step(s, x)) | per generator | (s, x) |
| FACT | ∀h. CF(h, S) → ∀x, x′. m_h x = m_h x′ → c x = c x′ | relational, via a product program | (x, x′) together with the CF instance |
| SORT | typing plus coercion proofs | type checking | site, plus a state where the coercion premise fails |
| DISCH | per profile point: ∃ strategy σ. ∀ schedule ≤ H. holds(σ); blocked: ∃ invariant I preserved by X and by time | strategy programs, invariant lemmas | the "blocked" theorem *is* the obstruction |
| OWN | heap-model law: no write to a live view's backing region | heap invariants | trace |
| Intent contract | L_weak over its scope | as any law | — |
| Non-vacuity (all rules) | an inhabitant of every premise (§12, L21) | construction | premises unsatisfiable: the law is rejected as vacuous |

### 8.5 Hypothesis discipline

- **No axioms anywhere.** Gate G3 rejects any declaration that introduces a term without a definition.
- **Cryptographic assumptions are premises.** Hash assumptions enter as CF(h, S) premises (Cor 6.16).
- **Oracle assumptions are premises.** Oracle behaviour enters as hypothesis predicates. Examples:
  - `HypZ(Dec, Enc) ≡ ∀x, k ≤ K. Dec(Enc x ++ 0^k) = x`;
  - `HypC_v(circuit)` relates the public input to the payload semantics for version v.
- **Laws are parametric.** A law holds for every hash function and oracle satisfying its premises. The assumption ledger is mechanically the set of premises appearing in frozen statements.
- **Split status.** A law that holds under one oracle hypothesis and fails under another is reported as split on that hypothesis. O8 (trailing payload) is the canonical case.

### 8.6 Three outcomes and result records

Every obligation ends in one of three outcomes:
- **PROVED:** a kernel-checked proof.
- **REFUTED:** a kernel-checked witness and counter-law.
- **UNKNOWN:** a record of the budgets, bounds and engines that were tried.

The result record keeps the following fields orthogonal, adapting the result semantics of an evidence-ledger research pipeline:
- status (proved, refuted, split, unknown);
- law hash and model hash;
- premises;
- scope (bounded with horizon H, or unbounded);
- kernel or kernels;
- independence class;
- refinement records of the edges used;
- witness replay status;
- coverage.

### 8.7 Refinement evidence through native replay

𝔅 compiles to a C library. The replay harness:
- calls the Go implementation through cgo;
- runs the Solidity implementation on an EVM interpreter or a pinned fork.

It feeds model and implementation the same inputs from four sources:
1. inputs sampled from the carrier types' grammars;
2. sort boundary values: 0, 1, max, max − 1, and every sentinel constant;
3. every refutation witness;
4. historical on-chain inputs. Every past commit's calldata, and its blobs where archived, are replayed through the model's codecs and compared with the stored commitments and the node's derivations.

Each disagreement is classified as an extraction defect, a real defect or an oracle mismatch. Agreement volume and the classified disagreements populate the refinement records. The bend-ssz factory set the precedent, running its compiled library inside a production client with zero disagreements over a large decode sample.

### 8.8 Trusting the kernel

- **Canary laws.** Every gate run includes false laws, produced by mutating true laws (flipped equalities, shifted offsets). All must be rejected. A single accepted canary invalidates the run and quarantines the checker version.
- **Dual kernel.** Promoted certificates are exported through the law IR (§8.9) to Lean 4 and re-proved there. Lean's `bv_decide`, which checks SAT certificates, suits layout and codec goals. Results carry the independence class I2 when both kernels agree.
- **Kernel-independent obstructions.** A refutation witness is concrete data, so it is confirmed by running it on the real implementation. The trust in an obstruction never rests on any kernel.
- **Pinning.** Checker versions are pinned. Upgrades re-check everything, and kernel bugs found along the way are reported upstream.

### 8.9 The kernel-agnostic law IR

Statements are stored in a small typed IR covering:
- quantifiers and binders;
- types;
- references to model definitions, by hash;
- premises.

Emitters target Bend (primary) and Lean (secondary). The *statement hash is the IR hash*, so freezing does not depend on the kernel. A proof in either kernel discharges the same frozen statement.

### 8.10 What Bend does not solve

- extraction (§10.1);
- intent (§5.10);
- oracle truth (§8.5);
- economic rationality (§12, L6);
- the choice of *which* obligations matter, which is HOLON's job;
- kernel trust, which is only mitigated (§8.8).

---

## 9 The HOLON Factory

### 9.1 Overview

```
   code ─▶ Extractors ─▶ 𝔇 ─┬─▶ Law generator ─▶ LAWS/   (IR → Bend/Lean; frozen, hashed)
                            └─▶ Model generator ─▶ MODEL/ (𝔅; compiled to C)
   Provers (untrusted: tactic generators, agents) ─▶ PROOF/
   Refuters (untrusted: SMT, GPU enumeration, fuzzers) ─▶ WITNESS/ + counter-laws
   Replay harness: MODEL ⇄ real Go / EVM ─▶ REFINEMENT/
   Auditors (fresh context, different model family) ─▶ findings ─▶ filter ─▶ fixers
   Everything ─▶ GATE ─▶ main            Coordinator: the single human-facing interface
```

The design follows the bend-ssz formal-program factory:
- untrusted generators emit code and proofs;
- statements are frozen and hashed;
- each audit round uses a fresh auditor from a different model family;
- a gate regenerates and re-checks everything from scratch;
- one coordinator is the human's only window into the system.

HOLON's change is where the frozen statements come from. In bend-ssz they come from a human-transcribed specification. In HOLON they come from rules applied to an extracted diagram.

### 9.2 Loops

1. **Extraction loop:** code → facts → 𝔇, with coverage-debt accounting.
2. **Obligation loop:** rules → IR statements → law files. This loop is deterministic.
3. **Proof loop:** provers write only to PROOF/. Following bend-ssz, proofs are produced by *generators* per obligation class rather than written by hand per law. A fix to a generator then propagates to every law of that class.
4. **Refutation loop:** solvers, bounded enumeration (on GPU targets where the model fragment supports it) and fuzzing of the compiled model produce witnesses. Each witness becomes a counter-law proof checked by evaluation.
5. **Refinement loop:** native replay (§8.7).
6. **Audit loop:** §9.5.
7. **Performance loop:** a proposer changes generators, proof strategies or model encodings to cut check time. A change survives only if every law, proof, canary and replay still passes, otherwise it is reverted. The target is a per-file check budget; bend-ssz used two minutes.

### 9.3 The gate

| ID | Check |
|---|---|
| G1 | Regenerate every generated file; the diff must be empty |
| G2 | Statement hashes match the registry; changes only per §9.4 |
| G3 | No axioms, postulates or holes in any committed file |
| G4 | Canary laws are all rejected |
| G5 | From-scratch check with no cache; per-file time budget |
| G6 | Every refutation witness replays on the real code, or is labeled model-only pending replay |
| G7 | Promoted certificates are re-checked in the second kernel, or labeled single-kernel |
| G8 | A coverage report lists every in-scope code element not mapped into 𝔇 |
| G9 | Result records are complete (§8.6) |
| G10 | Intent contracts are proved; contracts affected by a change are re-proved |
| G11 | Every law with premises has a non-vacuity inhabitant |

### 9.4 Statement-freezing protocol

A statement is a function of the diagram hash, the rule-catalog version and the generator version. It can change in three ways only:
- **Re-extraction.** If the code changed, a new statement set is produced. The old results go stale through the dependency index.
- **Strengthening.** A new statement S′ is admitted only if the kernel checks S′ ⇒ S. Strengthening is itself proved.
- **Weakening.** Allowed only as an explicit scope change, with a signed rationale, auditor review and an entry in `STATEMENT_DIFF`.

Provers have no write access to LAWS/.

### 9.5 Auditing protocol

Each round uses a fresh auditor from a model family different from the provers'. Four auditor types:
- **A1, mutation.** Plant realistic misimplementations in the *real code*: off-by-one offsets, missing clears, wrong masks, swapped cursors. Re-extract, and confirm the corresponding obstruction appears. A miss is an extraction gap or a rule gap.
- **A2, hostile input.** Attack R^ext at every interface carrier through public entry points. This finds totality and panic defects such as O4, and checks that the model's partiality matches the code's.
- **A3, regression.** Compare law sets, premises and proof strengths across commits. It catches dropped laws, strengthened hypotheses and drifted constants.
- **A4, vacuity and over-strength.** Check that premises are satisfiable and that oracle hypotheses survive tests against the real oracles.

The loop has converged after k consecutive rounds with no high-priority finding.

### 9.6 The finding filter

Every candidate is sorted into one of three bins:
- **Finding:** the witness concretizes to a schedule of public entry points from a reachable state and replays on the real code.
- **Model defect:** the witness fails on the real code. The fix goes to the generator or the extraction.
- **Known limitation:** the witness requires a construction no public entry point produces.

This is the bend-ssz criterion of reproducibility through the public API, with witness concretization (§10.9) as its mechanism.

### 9.7 Trusted computing base

| Component | Trusted for | How the trust is reduced |
|---|---|---|
| Rule catalog (8 rules) | What counts as an obligation | Small, fixed, reviewed; meta-theorems formalized once in the core library |
| Law and model generators | Translating 𝔇 into IR and Bend | Deterministic; G1 regeneration; replay detects mismodeling |
| Extractors | 𝔇 matches the code | Native replay; A1 mutation adequacy; coverage accounting |
| Kernel | Proofs are valid | Canaries; dual kernel; kernel-independent witness replay |
| Hypothesis predicates | Oracle and cryptographic assumptions | Visible premises; tested against real oracles (A4) |
| Intent contracts and intent lane | Suppressions and normative claims | Proved weaker laws; source spans; human review |

---

## 10 Algorithms

### 10.1 Extraction

**Solidity**, via the solc AST, Yul and Slither IR:
- storage families become state carriers;
- external functions become transitions, with guards from `require` and modifiers;
- view calls become LOAD edges;
- `keccak256`, `blobhash` and verifier calls become commitment edges;
- loop bounds become cost terms;
- straight-line `mstore`/`mload` sequences become layouts (§10.2).

**Go**, via `go/ssa`:
- `binary.BigEndian`, constant-offset `copy` and `append` chains become codecs;
- index and slice sites become partiality annotations;
- slice headers become backing-identity facts for OWN;
- pipelines become consumers.

**Linking:** ABI bindings, shared constants (249, 257, Z, 4096 × 31) and event schemas connect the languages.

**Deployment history:** proxy upgrades, reinitializer versions and storage diffs become migrations and in-flight types.

**Translators.** Straight-line Yul and Go-SSA fragments are translated to Bend syntactically and deterministically. Each translation is validated per instance by replay. Fragments the translator does not support are recorded as coverage debt, never approximated silently.

### 10.2 Layout algebra

A layout Λ maps each byte position to (field, byte index), constant 0 or unknown.

| Language | Operation | Effect on Λ |
|---|---|---|
| EVM | `mstore(b + o, shl(8(32 − w), x))` | (x, 0..w−1) at o..o+w−1, then zeros up to o+31; later writes override earlier ones |
| EVM | `mstore8` | single position |
| EVM | `calldatacopy` | positions map to calldata |
| Go | `PutUint64` | eight positions |
| Go | `copy` | thirty-two positions |

Getters recover a field iff its positions map to it in order. For straight-line code Λ is computed exactly, and equality of two layouts is decidable in O(L).

Layout facts are emitted twice:
- as Bend definitions, so layout lemmas are proved by evaluation over symbolic field values;
- as solver queries for refutation.

### 10.3 Basis reduction

1. Identify the invertible fragment, with hashes under CF premises.
2. Check domain coherence per edge.
3. Compute the fundamental cycles.
4. Reduce SYM to generators.
5. Reduce NAT to entry points × in-flight types, plus migration sequences.
6. Enumerate lossy pairs from evidence, pushing through injective maps.

The meta-theorems (Thms 6.4, 6.6, 6.7) are formalized once in the core library and instantiated per target, so basis sufficiency is itself kernel-checked.

### 10.4 Proof engines

**Generators per obligation class:**

| Obligation class | Proof produced |
|---|---|
| Layout equality | by evaluation |
| UNDO, dead residue | bisimulation step lemmas for the relation "equal outside Res", per action |
| SYM | per-action generator lemmas |
| NAT | per entry point |
| DISCH | strategy programs, and invariant lemmas for blocking |

Agents, including Bender and general coding agents, fill the remaining goals. The only thing they can produce that matters is a proof file the kernel accepts.

### 10.5 Refutation engines

| Engine | Use | Constraint |
|---|---|---|
| Solver, QF_UFBV | General refutation search | Ground injectivity over the query's own hash terms |
| Bounded exhaustive enumeration | Small domains and short action sequences in the compiled model | GPU targets where the fragment is supported |
| Grammar- and sort-boundary fuzzing | Broader search of the compiled model | — |

Every candidate witness is re-encoded as a counter-law and checked by evaluation (Thm 6.17).

### 10.6 Liveness and bisimulation

**UNDO deadness, as a static check.** A residue register r_i is *dead* (unobservable) if every reader of r_i is preceded, in every guard-respecting order, by a writer of r_i. This is checked by a key-sensitive backward analysis, with index variables kept symbolic.

**UNDO deadness, as a certificate.** The same fact becomes a proof via a bisimulation relation, which by Thm 6.9(i) turns deadness into a checkable equivalence.

### 10.7 Discharge profiles

1. Build a finite abstraction of the guard-relevant registers.
2. Label edges with (cost, delay). Waits carry delay, and actions carry gas and value costs.
3. Run bi-criteria label-correcting search for DP_X (Prop 6.21).
4. Emit each Pareto point as a strategy law, and each blocking result as an invariant law.

### 10.8 Symmetry splits

For each family admitted by sorts, check equivariance per action, then partition the actions into a split. Promotion follows §5.4. Reordering pairs are filtered by principal class and sink reachability.

### 10.9 Witness concretization

1. Bounded model checking over the TRANS edges finds a reachable path to the witness state, with environment moves and principal constraints.
2. The path is emitted as a test against the pinned real implementation: a Foundry test for EVM code, a Go test for the node.
3. Outcome: replay success yields a finding; replay failure yields a model defect (§9.6).

### 10.10 Ranking

Rank lexicographically by sink class, then persistence, then reach class, then adversary cost. Discharge profiles feed the persistence dimension: a mixed profile ranks below a non-dischargeable one.

### 10.11 Complexity

- Obligation counts stay linear in the diagram, as in v1.
- Proof checking adds a per-law cost, bounded by the gate budget and parallel across files.
- Replay cost is linear in the corpus.
- Refutation is budgeted per obligation, with exhaustion recorded as UNKNOWN.

---

## 11 Case Study: The Morph Batch Lifecycle

### 11.1 Setup

**Subject.** morph-l2/morph at commit 3e44e79:
- **Solidity:** rollup contract, header codecs, submitter registry, message queue, messengers, Merkle verification, verifier router.
- **Go:** header, batch-data, blob and encoding packages; block-context codec; `ParseBatch`.

**Oracles,** expressed as hypothesis predicates:
- compression codec;
- circuits;
- KZG and the transaction codec;
- L2 predeploys;
- fetcher;
- sealing loop.

**Status.** All results below were obtained **by hand**, after an independent manual analysis (Appendix A). Mechanized results are pending. §11.8 preregisters them.

### 11.2 Diagram summary

```
            Enc_sol^v                  H
  BDI ──────────────────▶ Hdr^v ─────────────▶ CB_i ──(re-presented as parent)──▶ Hdr^v_{i+1}
   ▲   ABI binding          ▲  │ Dec_sol^v
 Builder  HdrStruct ─Enc_go^v─▶ HdrGo ─Dec_go─▶ fields
   ├─Payload─▶ Bytes ─Compress─▶ Comp ─Split/Canon─▶ Blobs ─VH─▶ β ─First|Agg─▶ b57 ─Store─▶ BVH_i ─Load─┐
   │                                                  └─Retrieve/Concat─▶ Comp′ ─Dec─▶ Stream ─Parse─▶ Derived
   └─DataHashV2_go─▶ Dig[data] ◀─DataHash_sol─ (lbn, n, Q[T..T+n))       commitState / commitWithProof ◀┘
```

### 11.3 Obstructions found

Impact is given as sink / reach / persistence.

| ID | Rule | Obstruction | Impact | Prior |
|---|---|---|---|---|
| O1 | PAR-domain | Solidity v0 accepts len(h) ≥ 249; Go requires 249 | derivation / owner (genesis) / until upgrade | F12.1 |
| O2 | PAR-domain | Go v1 encoder hard-codes the version byte; no v2 encoder | liveness / — / until code change | F12.2 |
| O3 | PAR-domain | Commit admits (version, index) outside the router's domain | liveness, economic / bonded / until owner | F14 |
| O4 | PAR-totality | Clone panics on non-canonical element ≥ 3968 | process / bonded / permanent with O11 | F3 |
| O5 | PAR-branch | Estimator fast path assumes non-expansion; second estimator omits contexts | off-chain / users / transient | F9 |
| O6 | PAR-recompute | Legacy Go data hash ≠ on-chain formula for v0 | proof agreement / — / conditional | F12.6 |
| O7 | PAR-cycle | lastBlockNumber cycle has no closing check | derivation / bonded / conditional | F11b,c |
| O8 | PAR-consumer | Trailing payload ignored by derivation; circuit unknown | split on HypC / bonded / oracle | F11a |
| O9 | PAR-init | P = total(h_LFI) unconstrained at genesis | finality / owner / permanent | F12.4 |
| O10 | PAR-weak | Documentation–code disagreements | intent questions | F12.8 |
| O11 | UNDO | BVH_i residue live | liveness / bonded / until upgrade | F2 |
| O12 | UNDO | Cancellation leaves +W extensions | delay / challenger, owner / transient; intent contract candidate | **N2** |
| O13 | NAT | Cutover × slash | economic / challenger / transitional | F10 |
| O14 | NAT | Cutover × defend | liveness / challenger / transitional | **N4** |
| O15 | NAT | η₂ × commit-after-revert | liveness / owner in window / latent, historical | **N1** |
| O16 | NAT | η_enq × delay predicate | censorship resistance / — / historical | F7 |
| O17 | NAT (benign) | η_BVH: migrated batches unpinned | — / — / historical | new, benign |
| O18 | NAT-composition | η₄ before η₃ leaves D = 0 | liveness / ProxyAdmin / until parameter update | A15 |
| O19 | SYM-ω | Proof-backed commit and Challenge(j) do not commute on f_i | finality / challenger / until re-proof | F5 |
| O20 | SYM-π | Implicit address(0) role; vacuous slash | economic / — / — | F5 |
| O21 | SYM-τ | Sentinel `enq = 0` | censorship resistance / — / historical | F7 |
| O22 | FACT | Z conflates no-blob and zero-blob | derivation / bonded / until upgrade with O11 | F2 |
| O23 | FACT | Parent lbn outside the public input | proof completeness / — / design | F11d |
| O24 | FACT | v0 calldata contexts unbound | derivation / bonded / conditional | F11f |
| O25 | FACT/SORT | Bonded recommitter ≠ content chooser | economic → liveness / bonded / until upgrade | **N3** |
| O26 | SORT×UNDO | Ghost tag VH vs Agg at the recommit read; tag erased by revert | finality / bonded / until upgrade | F6 |
| O27 | SORT-sign | `realize(W + s − t)` unprovable once t > s + W | liveness / challenger / until outside action | F4 |
| O28 | SORT-width | Σ n_l1 realized in uint16 | safety, liveness / users / permanent desync | F12.7 |
| O29 | SORT-payer | Replay waiver keyed on origin; caller pays | message liveness / anyone / — | F8 |
| O30 | SORT-conservation | Value attached to commit is unaccounted | accounting / submitter / permanent | F13 |
| O31 | DISCH-external | Stale challenge blocks permissionless committers | liveness / challenger / until outside action | F4 |
| O32 | DISCH-non-dischargeable | BVH pin | liveness / bonded / until upgrade | F2 |
| O33 | DISCH-mixed | Delay guard profile {(c_msg, 0), (0, Δ_fin)} | liveness cost or delay / — / per batch | **F7 reconciled** |
| O34 | DISCH-external | Replay budget: only the owner can raise it | message liveness / anyone / until owner | F8 |
| O35 | DISCH-self-controlled | Challenge cost grows with a backlog the challenged class controls | **safety** / bonded / until owner | F1 |
| O36 | OWN-alias | `TxsPayloadV2` view aliases buffer capacity later written by `Append` | off-chain integrity / — / conditional on caller | F9 sub-item |
| O37 | OWN-lost-write | Value-receiver cache write is lost | performance, consistency / — / — | F12.3 |

### 11.4 New obstructions in brief

**N1 (O15).** η₂ wrote CSR only at the last committed index. Suppose:
- at migration, LFI = a < LCI = b; and
- the owner later reverts into (a, b].

Then every commit fails the CSR equality check, and remains blocked until an upgrade. The obstruction is latent and historical, and was missed because the manual analysis modeled only the current version.

**N2 (O12).** Cancelling a challenge leaves the +W extensions it applied to other batches. An intent contract (§5.9) can bound this as designed behaviour.

**N3 (O25).** Under the BVH pin, the content of the recommitted batch is fixed by the original submitter S₁, while the bond at risk is the recommitter S₂'s. A rational S₂ therefore refuses to recommit unprovable content, which turns slashing into a liveness deterrent.

**N4 (O14).** Legacy committers cannot prove their own in-flight batches after the cutover. If no prover in the new registry acts within W, a possibly valid batch is reverted.

### 11.5 O33 reconciled

- **Write closure.** Write*_sub contains:
  - T, through commit;
  - L, through `sendMessage`;
  - P, through finalization, which is permissionless and time-gated, so it is enableable by waiting.

  It does not contain enq[P] at the current P.
- **Pay strategy.** Send a message, wait for L2 inclusion, then commit with n ≥ 1. The cost per batch is the L1 gas of `sendMessage` plus g_min × l2BaseFee (zero if the submitter is whitelisted).
- **Wait strategy.** Let windows elapse and finalize until P passes every message older than D. The cost is zero, with delay up to Δ_fin.
- **Classification:** mixed. The severity is bounded liveness degradation, not a halt.

### 11.6 Obligations discharged (certified absent, relative to 𝔇)

| ID | Obligation |
|---|---|
| D1 | Header layouts v0/v1, Solidity ≡ Go, except byte 0 (that difference is O2) |
| D2 | Z_sol = Z_go; equality with the KZG versioned hash of the zero blob is oracle-checkable |
| D3 | Block-context encode, decode and height agree; BaseFee normalization is restored by the equality helper |
| D4 | P = total(h_LFI) ≤ T ≤ L is preserved by every transition, given initialization |
| D5 | CSR_i and BD_i residues are dead |
| D6 | Sentinels `revertReqIndex = 0`, `lastIndex = 0`, `messageSendTimestamp > 0` and `originTimestamp > 0` are harmless |
| D7 | The 32-bit truncation of the tree index is discharged by leaf injectivity under CF |
| D8 | Conservation, except O30 and the annotated slash `receive` |
| D9 | Relay at most once |

### 11.7 Comparison with the manual analysis

| Outcome | Items |
|---|---|
| Reproduced | All of F1–F14; the former gaps, F9's aliasing sub-item and F12.3, are now O36 and O37 |
| Reconciled | F7, as a profile (O33) |
| New | N1–N4, plus O17 (benign) |
| Certified absent | D1–D9 |

### 11.8 Preregistered predictions for the mechanized rerun

These predictions are frozen before mechanization (milestones M0–M1, §15). Deviations will be published with explanations.

| Law | Rule | Prediction | Witness or proof |
|---|---|---|---|
| L_par_hdr_v0 | PAR | PROVED | Layout equality over 249 positions, for headers with version 0 |
| L_par_hdr_v1 | PAR | PROVED | Layout equality over 257 positions |
| L_par_hdr_v2 | PAR | REFUTED | Any header with version 2: byte 0 is 2 versus 1 |
| L_dom_v0 | PAR-domain | REFUTED | 250-byte string with byte 0 = 0: Solidity defined, Go undefined |
| L_undo_CSR, L_undo_BD | UNDO | PROVED | Relation "equal outside {CSR_i, BD_i}" |
| L_undo_BVH | UNDO | REFUTED | commit(i, β); revert(i); commitBatch(i, β′) reverts in one run, succeeds in the other |
| L_undo_cancel | UNDO | REFUTED | challenge(k); pause: f_j retains +W |
| L_sort_remaining | SORT | REFUTED | inChallenge, t = s + W + 1 |
| L_tag_BVH | SORT | REFUTED | commit v2; revert; commitState v1 |
| L_disch_delay | DISCH | Profile {(c_msg, 0), (0, Δ_fin)} | Two strategy programs |
| L_disch_stale | DISCH | Blocked for permissionless committers | Invariant inChallenge ∧ t > s + W, preserved by those committers and by time |
| L_fact_Z | FACT | REFUTED | Two transactions differing only in sidecar presence, with equal CB |
| L_sym_ω(zk, challenge) | SYM | REFUTED | Order swap leaves f_i open in one order, closed in the other |
| L_own_txspayload | OWN | REFUTED, conditional | View held across `Append` |

Every REFUTED witness must replay on the pinned real code (G6).

---

## 12 Limitations and Remedies

| # | Limitation | Root cause | Remedy | Residual risk | Metric |
|---|---|---|---|---|---|
| L1 | Model ≠ deployed code | Extraction is a translation | Deterministic translators; per-edge native replay including historical inputs; A1 mutation adequacy; coverage debt; optional formal equivalence (hevm/KEVM) for top edges | Untested input regions; semantics the translator omits | Replay volume; mutation detection rate; coverage |
| L2 | Reachable-domain approximation | R was hand-approximated in v1 | `Reach` as an inductive predicate over 𝔅; invariants proved as laws; R^ext as the full input type | Bounded by L1 | Fraction of laws stated over `Reach` |
| L3 | Lossy fragment incomplete | Prop 6.11 | Frozen evidence set; coverage metric; uncovered replay disagreements trigger evidence review; injective pushing | Inherent; no topological basis exists | Evidenced-pair coverage; uncovered disagreements |
| L4 | Annotations trusted | Blanket `@intended` in v1 | Intent contracts with proved weaker laws, frozen and scoped | A wrong contract still suppresses within its scope | Contracts with proofs: 100% |
| L5 | Oracle components | Code unavailable or too large | Hypothesis predicates; parametric laws; split status; hypotheses tested against real oracles; circuit extraction when available | Wrong hypotheses | Hypothesis test coverage |
| L6 | "Can" versus "will" | No payoff model | Bounded games over 𝔅, with strategies as checked programs; ordinal payoffs; DISCH-econ: some permitted discharger has non-negative payoff | Rationality assumptions | — |
| L7 | Missing rule families | Catalog incomplete | OWN added; every finding outside the rules files a rule-gap record; a new rule needs at least two instances and a basis argument | Unknown unknowns | Fraction of findings outside the rules |
| L8 | Hindsight; nothing mechanized | v1 applied by hand | Preregistration (§11.8); blind rerun by fresh agents without Appendix A; held-out targets | Biased predictions | Prediction accuracy; blind-rerun agreement |
| L9 | Environment | Axioms only | Environment modules: L1 fork choice, DA availability window, fetcher contracts; time-indexed FACT laws | Environment model accuracy | — |
| L10 | Consistently wrong code | Self-derived specification | Intent lane (§5.10) | Intent extraction quality | Intent-law coverage |
| L11 | SYM circularity | Frequency taken as specification | Splits; promotion only with strong evidence or intent | — | Split adjudication rate |
| L12 | DISCH ignored guards and time | v1 error | Enableable closure and profiles | Abstraction of time | — |
| L13 | Global injectivity axiom | v1 error | CF premises; ground solver instances; G3 bans axioms | Negligible-probability collisions | Axiom count: 0 |
| L14 | Statement weakening | Provers optimize for "done" | Generated, frozen statements; provers cannot write LAWS/; strengthening proved by the kernel | Generator bugs, caught by G1 and A3 | Weakening incidents |
| L15 | Proof failure read as a counterexample | Conflated outcomes | Three outcomes; UNKNOWN records budgets and bounds | — | UNKNOWN calibration |
| L16 | Young kernel | Checker not independently reviewed | Canaries; dual kernel; kernel-independent witness replay; pinning | Common-mode bugs across kernels | Canary acceptance: 0; cross-kernel agreement |
| L17 | Termination in a total language | Bend requires termination | Fuel; well-founded measures; invariants and bisimulations for unbounded claims; scope labels | Bounded results misread as global | Scope-label completeness |
| L18 | Generator mismodeling | Generators untrusted | G1 regeneration; replay; A1 | — | Model-defect rate |
| L19 | Shared AI blind spots | Same model family everywhere | Auditors from another model family, fresh context per round | — | Yield per audit round |
| L20 | Cost and scale | Thousands of laws | Basis theorems; per-file budgets; performance loop with veto; parallel checking; GPU refutation | — | From-scratch gate time |
| L21 | Vacuous laws | Unsatisfiable premises prove anything | Non-vacuity inhabitants for every premise (G11): `Reach` nonempty, CF satisfiable, in-flight sets nonempty | — | Non-vacuity coverage: 100% |
| L22 | Drift | Code and configuration change | Content-addressed dependencies; stale propagation; re-extraction on version change | — | Stale-closure latency |

### 12.1 L1, in depth: closing the gap between model and code

A certificate about 𝔅 says nothing about deployed code unless 𝔅 refines that code on the relevant cone. Formal refinement proofs for whole Solidity and Go components are out of reach, so v2 builds layered evidence instead:
- **Construction.** Straight-line fragments are translated mechanically, and each translation is replayed.
- **Behaviour.** Every edge carries a replay corpus. Historical on-chain inputs matter most, because they are the inputs that actually occurred.
- **Sensitivity.** A1 mutation adequacy measures whether a real defect in the code would surface as an obstruction in the model.
- **Coverage.** Every in-scope code element is mapped into 𝔇 or listed as debt.

Certificates report all four. "Certified absent" means: proved for 𝔅, under these premises, with this refinement evidence and this coverage. It never means more than that.

### 12.2 L16, in depth: trusting a young kernel

The obstruction and certificate paths are deliberately asymmetric.
- **Obstructions do not depend on the kernel.** They are concrete witnesses replayed on real code.
- **Certificates do.** Three independent defenses protect them:
  - canaries detect a checker that accepts falsehoods;
  - the second kernel detects a checker that accepts a particular false proof;
  - pinning with full re-checks limits the blast radius of an upgrade.

### 12.3 L21, in depth: vacuity, the silent failure of proof factories

A law with an unsatisfiable premise is true and useless. Three examples:
- a `Reach` predicate that admits no states;
- a CF premise over a set constructed to collide;
- an in-flight set that is empty because of an extraction bug.

All three would yield "certified absent" with no warning. G11 requires every premise to carry an inhabitant, and A4 audits that the inhabitants are representative rather than degenerate.

### 12.4 L10 and L6: what HOLON still cannot see

- **Consistently wrong code** requires an external source of intent. The intent lane provides one, at the cost of human review of each clause.
- **Incentive-driven failures** require payoff structure. DISCH says who *can* discharge an obligation, and the game extension says who *profits* from discharging it. Whether anyone *will* remains an empirical question outside any model.

---

## 13 Evaluation Protocol

**Corpus.** Multi-language systems with in-flight upgrades and public defect histories. Each historical defect is labeled with the minimal rule that exposes it, and analysis runs on the pre-fix commit.

**Baselines:**
- single-component analyzers;
- fuzzers with stock properties;
- symbolic executors;
- 2-cycle differential testing;
- frequency-based specification mining;
- an agent-only review at equal budget.

**Metrics:**
- recall per rule;
- precision, split into true defects, intended asymmetries and model defects;
- witness replay rate;
- certificate coverage;
- UNKNOWN rate and calibration on unsolved controls;
- canary acceptance (must be 0);
- cross-kernel agreement;
- mutation adequacy;
- refinement disagreement rate;
- from-scratch gate time;
- prediction accuracy (§11.8).

**Ablations:**
- no SORT-as-types;
- no writer provenance;
- no evidence calculus;
- 2-cycles instead of fundamental cycles;
- no native-equivalence NAT;
- no enablement in DISCH;
- no replay;
- single kernel;
- no frozen statements (measures the weakening rate).

**Threats to validity:**
- subjectivity of rule labels;
- extraction fidelity;
- historical defects biased toward what earlier tools could find;
- hypothesis strength;
- contamination of agents by public defect write-ups. Mitigate with fresh sealed targets and isomorphic renamings.

---

## 14 Related Work

**Belief inference and specification mining.** Engler et al. (SOSP 2001); Daikon (Ernst et al., TSE 2001); Ammons, Bodík and Larus (POPL 2002). HOLON derives equations from structure rather than frequency, with basis theorems. Only SYM is statistical, and v2 demotes it to splits.

**Symmetry and independence.** Symmetry reduction (Emerson and Sistla; Ip and Dill; Clarke et al., FMSD 1996), metamorphic testing (Chen et al., 1998), partial-order reduction (Godefroid, 1996), transaction-order dependence (Luu et al., CCS 2016).

**Relational verification.** Hyperproperties (Clarkson and Schneider, JCS 2010), self-composition (Barthe, D'Argenio and Rezk, CSFW 2004), product programs (Barthe, Crespo and Kunz, FM 2011).

**Under-constrained circuits.** Picus / QED² (Pailoor et al., PLDI 2023), Circomspect, ZKAP. FACT lifts their uniqueness question from a circuit to the whole pipeline.

**Lenses and bidirectional transformations.** Foster et al. (TOPLAS 2007), Stevens (SoSyM 2010). These are 2-cycle laws; PAR extends them to cycle-complete checking with semantic types.

**Migration.** Functorial data migration (Spivak, Inf. & Comp. 2012; Spivak and Wisnesky, DBPL 2015); dynamic-update correctness (Hayden et al., VSTTE 2012).

**Units and dimensions.** Kennedy (ESOP 1994; POPL 1997); Osprey (Jiang and Su, ICSE 2006). §7.8 turns affine refined sorts into dependent coercions.

**Ghost state.** Owicki and Gries (Acta Informatica 1976). Ghost tags (Prop 6.19) apply the classical technique to untagged unions.

**Proof-carrying code and translation validation.** Necula (POPL 1997); Pnueli, Siegel and Singerman (TACAS 1998). HOLON's counter-laws are proof-carrying counterexamples, and its translators are validated per instance.

**Refinement at scale.** seL4 (Klein et al., SOSP 2009) shows full refinement proofs are possible but expensive. HOLON trades proof of refinement for measured refinement evidence (§12.1).

**Proof assistants and the substrate.** Lean 4 (de Moura and Ullrich, CADE 2021), with certified bitvector automation, as the second kernel. Bend 2 (HigherOrderCO, 2026) as the primary substrate.

**Formal-program factories.** The bend-ssz factory (Rebuffo, 2026) introduced the generator–frozen statement–auditor–gate pattern on Ethereum's SSZ codec. HOLON reuses the pattern and replaces the human spec transcription with rule-generated statements.

**Sheaves and synchronization.** Goguen (MSCS 1992); Abramsky and Brandenburger (NJP 2011); Abramsky et al. (CSL 2015); Curry (2014); Hansen and Ghrist (2019); Singer (ACHA 2011); Bandeira, Singer and Spielman (SIMAX 2013).

**Smart-contract tools.** Slither (2019), Echidna (2020), KEVM (CSF 2018), MadMax (OOPSLA 2018). MadMax is closest to DISCH's cost component.

---

## 15 Roadmap

### 15.1 The first 48 hours

**Day 1**
1. Install Bend 2, run `bend guide`, and create the repository layout (Appendix H).
2. Write the law IR schema (JSON) and the Bend emitter for PAR laws.
3. Hand-write the facts for the Morph header:
   - the Solidity `mstore` sequence of Appendix C;
   - the Go `PutUint64`/`copy` sequences;
   - the v0 length checks on both sides.
4. Write the generator that turns facts into layouts, then into Bend encoders and laws.
5. Emit L_par_hdr_v0, L_par_hdr_v1, L_par_hdr_v2 and L_dom_v0, and run the checker.

**Day 2**
1. Write the refuter for small domains: version byte × length × a few field values. Emit counter-laws for v2 and for the domain law.
2. Write gate v0, covering G1–G5 and G11, with ten canary laws mutated from the true ones.
3. Export L_par_hdr_v1 to Lean through the IR and re-prove it.
4. Compare the results with §11.8.

### 15.2 Milestones

| Milestone | Scope | Exit criterion |
|---|---|---|
| M0 (2 days) | Header laws | v0 and v1 PROVED; v2 and the domain law REFUTED with the predicted witnesses; all canaries rejected; one law dual-kernel |
| M1 (~2 weeks) | Rollup state-machine slice, from hand-written facts: CB, CSR, BVH, BD, CH, LCI, LFI, P, T, L, enq, inChallenge, s, W, D | All M1 rows of §11.8 match or are explained; every REFUTED witness replays as a Foundry test on the pinned contract |
| M2 (~1 month) | Automated extraction for codecs and straight-line state updates; the replay harness (cgo plus EVM) with historical inputs | Zero unexplained replay disagreements over a historical window; mutation adequacy at or above a preregistered threshold |
| M3 (~2 months) | Full Morph bundle, all eight rules, the audit loop, and a blind rerun by fresh agents without Appendix A | Published comparison with §11.8 and Appendix A |
| M4 | A held-out second target (a different rollup or bridge) | The §13 protocol against the baselines |
| M5 | Intent lane, bounded games, environment modules | L6, L9 and L10 metrics reported |

### 15.3 Risk register

| Risk | Mitigation |
|---|---|
| Bend 2 immaturity or kernel bugs | Law IR, dual kernel, canaries, upstream reports |
| Proof automation insufficient | Per-class proof generators, as in bend-ssz; bounded checks with explicit scope; UNKNOWN is an acceptable outcome |
| Extraction does not scale | Start with codecs and straight-line updates; hand-written facts for state machines until M2 |
| Replay infrastructure cost | Begin with the header and the state-machine slice; historical inputs only for recent windows where blobs are retained |
| Agent spend | Per-milestone budgets; proofs come from generators first and agents second |

---

## 16 Conclusion

HOLON reads specifications off the shape of a system and treats defects as obstructions to commutation. v2 makes every one of those specifications a frozen law over an executable model. The model is:
- proved where the law holds;
- refuted with a replayable witness where it fails;
- labeled UNKNOWN where neither can be done;
- continuously compared against the deployed code.

The trust that remains sits in a small, auditable base: eight rules, deterministic generators, measured extraction and a dual-checked kernel. AI participates throughout, but only as an untrusted producer of proofs, witnesses and audits. It never decides what is true. The next step is the two-day header experiment in §15.1, whose outcome is already preregistered.

---

## Appendix A. Prior Manual Findings

| ID | Finding |
|---|---|
| F1 | Challenge gas grows with backlog; a bonded submitter can make challenges unaffordable. |
| F2 | Revert preserves the blob hash; recommits must reuse it, including a "no blob" Z or a malformed blob. |
| F3 | The Go blob-retrieval error path indexes out of bounds for non-canonical elements at index ≥ 3968. |
| F4 | Unsigned underflow in challenge arithmetic disables all commits once a challenge is stale. |
| F5 | A challenge on any batch reopens a proof-backed batch's window. |
| F6 | A recommit can change the version while reusing a blob hash of different meaning. |
| F7 | The delay guard reads the finalization cursor instead of the inclusion cursor (reconciled as a profile). |
| F8 | Third parties can exhaust the replay budget; the fee waiver is keyed on the original sender. |
| F9 | Estimators assume compression never expands; one omits contexts; slice aliasing. |
| F10 | Slashing is vacuous for pre-cutover batches. |
| F11 | Derivation accepts trailing payload and does not check contiguity or the last block; L1 counts are discarded; the parent lbn is not in the public input. |
| F12 | Codec domains, missing v2 encoder, ineffective cache, genesis cursor, downgrade, legacy hash, uint16 accumulators, documentation drift. |
| F13 | Attached value is unaccounted. |
| F14 | Batches can be committed at a version and index the router cannot resolve. |

## Appendix B. Morph Diagram (listing)

**Representation carriers:**
- calldata input;
- header bytes, v ∈ {0, 1, 2};
- Go header bytes and structs;
- builder;
- payload;
- compressed bytes;
- canonical blobs;
- β and b57;
- retrieved and concatenated bytes;
- stream;
- 60-byte contexts and the context struct;
- derived blocks;
- queue hashes;
- public input;
- cross-domain calldata and its leaf;
- withdrawal roots.

**State carriers:**
- per-index CB, CSR, FSR, BVH, BD, CH;
- the challenge token;
- LFI and LCI;
- the queue (L, P, enq);
- the registry;
- the messenger (finalized set, send times, replay states);
- the verifier registry.

**Environment carriers:** time, β, caller, value.

**Edges:**
- **CODEC:** header encode/decode (Solidity, Go); context encode/decode/height; payload; compress, split, retrieve, decompress; parse.
- **HASH:** header hash, VH, aggregate, data hash (three definitions), public input, leaf, root.
- **STORE/LOAD:** BVH, CB (re-presented through parent headers), CSR, BD.
- **CONS:** derivation, verifier dispatch, relay.
- **TRANS:**
  - three commits, revert, challenge, prove, finalize, pause, genesis, cutover, parameters;
  - registry actions;
  - queue actions;
  - messenger actions;
  - router update.
- **MIG:** η₂, η₃, η₄, η_enq, η_BVH.
- **SYM:** τ, ι, π, ω.
- **OWN facts:** the block-context and transaction-payload buffers with their backing identities; value-receiver methods on the header structs.

## Appendix C. Layout Algebra on the Version-1 Header

| Order | Write | Range | Contents |
|---|---|---|---|
| 1 | version | `mstore8` at 0 | version byte |
| 2 | batchIndex | [1, 33) | 8 field bytes, then zeros |
| 3 | l1MessagePopped | [9, 41) | 8 field bytes, then zeros |
| 4 | totalL1MessagePopped | [17, 49) | 8 field bytes, then zeros |
| 5 | dataHash | [25, 57) | 32 field bytes |
| 6 | b57 | [57, 89) | 32 field bytes |
| 7 | prevState | [89, 121) | 32 field bytes |
| 8 | postState | [121, 153) | 32 field bytes |
| 9 | withdrawRoot | [153, 185) | 32 field bytes |
| 10 | sequencerSetHash (zero) | [185, 217) | 32 bytes |
| 11 | parentHash | [217, 249) | 32 field bytes |
| 12 | lastBlockNumber | [249, 281) | 8 field bytes, then zeros (outside the hashed range from 257) |

**Final layout:**

```
Λ_sol[0]=(version,0)  [1..8]=(batchIndex,·)  [9..16]=(l1Popped,·)  [17..24]=(total,·)
[25..56]=(dataHash,·)  [57..88]=(b57,·)  [89..120]=(prev,·)  [121..152]=(post,·)
[153..184]=(withdraw,·)  [185..216]=(seqSet,·)  [217..248]=(parent,·)  [249..256]=(lbn,·)
```

Λ_go is identical except that Λ_go[0] is the constant 1. Equality holds iff version = 1, which yields D1 and O2.

## Appendix D. Refutation Encodings (corrected)

| Object | Encoding |
|---|---|
| keccak / sha256 | Uninterpreted K(n, x) with **ground** injectivity over the query's own hash terms only, i.e. CF(K, S_query). v1's quantified inverse axiom is withdrawn (Thm 6.15). |
| Versioned hash | Uninterpreted VH with ground injectivity; Z := VH(0); top byte 0x01 |
| Blob-hash vector | Dense prefix; nonzero entries have top byte 0x01 |
| Compression codec | Uninterpreted Enc and Dec under HypZ, instantiated up to the bound K |
| Time | Non-decreasing environment variable |
| Arithmetic | Checked: a revert predicate. Unchecked: bitvector wraparound |
| Cost | c₀ + Σ c_ℓ · iters_ℓ(s), compared against G |

Solver outputs are candidate witnesses only. Status changes only through a kernel-checked counter-law (Thm 6.17).

## Appendix E. Rule Summary

| Rule | Law form | Basis | Proof route | Refutation | Typical defects |
|---|---|---|---|---|---|
| PAR | path equality plus domain coherence | fundamental cycles; evidenced pairs | evaluation, layout lemmas | input witness | codec drift, clones, branch and consumer disagreement, init gaps |
| UNDO | bisimulation after undo | pair × residue | relation step lemmas | trace | pinned values, retained timers |
| NAT | native equivalence, naturality, coherence | entry points × in-flight types | per entry point | in-flight state | unmigrated fields, bonds, initializer order |
| SYM | equivariance; splits | generators | per generator | (s, x) or order swap | sentinels, principal confusion, order dependence |
| FACT | kernel containment under CF | commitment × consumer | product program | input pair | unbound inputs, conflated commitments, attribution |
| SORT | typing and coercions | edges | type checking | failing coercion state | type flips, underflow, width wrap, waivers, sinks |
| DISCH | profile strategies or blocking invariant | guard conjuncts | strategy programs, invariants | — | deadlocks, external dependence, gas on constraints |
| OWN | no write to a live view; no lost writes | views × writers | heap invariants | trace | aliasing, lost updates |

## Appendix F. Schematic Bend Sketches

These sketches are in a Bend-like Python syntax and **have not been checked against the Bend 2 grammar**. Take the exact surface syntax from `bend guide`.

```python
# Carriers as types; refined sorts as distinct types
type Time(U64);  type SDur(I128);  type Dur(U64)
type IdxFin(U64); type IdxInc(U64)

def time_sub(a: Time, b: Time) -> SDur: ...
def realize(d: SDur, p: Proof(d >= 0)) -> Dur: ...      # sign obligation = proof argument

# PAR: header encoders (generated from layouts)
def enc_sol(h: Header) -> Bytes(257): ...                 # Λ_sol, byte 0 = h.version
def enc_go(h: Header)  -> Bytes(257): ...                 # Λ_go,  byte 0 = 1
law par_hdr_v1(h: Header, v1: Proof(h.version == 1)): enc_sol(h) == enc_go(h)
law par_hdr_v2(h: Header, v2: Proof(h.version == 2)): enc_sol(h) == enc_go(h)
# expected: par_hdr_v1 proved by evaluation over symbolic fields;
#           par_hdr_v2 refuted by witness h0 (version = 2) — counter-law checked by evaluation

# UNDO: residue liveness against a reachable state
law undo_bvh(s: State, r: Reach(s), i: Idx, x: CommitIn, y: CommitIn):
    obs(commit_batch(revert(commit(s, x), i), y)) == obs(commit_batch(s, y))
# expected refutation: BVH[i] != 0 after revert → commit_batch reverts; original succeeds

# SORT: generated call site at commit (challenge arithmetic)
#   remaining = realize(add(W, time_sub(start, now)), ?hole)
# hole unprovable under inChallenge ∧ now > start + W → refutation produces that state

# FACT with a local collision-freedom premise (never an axiom)
law fact_z(h: Bytes -> B32, cf: CF(h, S_query), a: CommitTx, b: CommitTx):
    commit_hash(h, a) == commit_hash(h, b) -> derive(a) == derive(b)

# Canary (must be REJECTED at every gate run)
law canary_17(h: Header): enc_sol(h)[57] == enc_go(h)[58]
```

## Appendix G. Gate Checklist

Each item is checked on every gate run:
- [ ] G1 regeneration diff is empty
- [ ] G2 statement hashes match the registry, or have an approved `STATEMENT_DIFF` entry
- [ ] G3 no axioms, postulates or holes
- [ ] G4 all canaries rejected
- [ ] G5 from-scratch check within the per-file budget
- [ ] G6 every witness replays on real code, or is labeled model-only
- [ ] G7 promoted certificates are dual-kernel, or labeled single-kernel
- [ ] G8 coverage report attached
- [ ] G9 result records complete
- [ ] G10 intent contracts proved
- [ ] G11 non-vacuity inhabitants present

## Appendix H. Repository Layout

```
holon/
  ir/              law IR schema, statement registry (hashes), STATEMENT_DIFF
  frontends/       solidity/ (solc, Yul, Slither → facts), go/ (go/ssa → facts)
  facts/           per-target fact sets (hand-written allowed until M2)
  diagram/         linking, sorts, evidence calculus
  rules/           par, undo, nat, sym, fact, sort, disch, own
  gen/             law emitters (bend, lean), model generator, proof generators per class
  model/           generated 𝔅 (Bend) and compiled C
  laws/            generated LAWS (frozen)        proofs/   PROOF files (untrusted inputs)
  refute/          solver encodings, GPU/bounded enumerators, fuzzers → witnesses
  replay/          cgo harness, EVM harness, historical-input corpus, refinement records
  audit/           auditor prompts, round logs, findings, filter decisions
  gate/            G1–G11 implementation, canary generator
  core/            HOLON core library: meta-theorems, layout lemmas, bisimulation kit
  results/         result records, certificates, obstructions, predictions vs outcomes
```

## References

Sources for the Bend 2 facts in §8.2:
- [Bend 2 release notes (ai-tldr.dev)](https://ai-tldr.dev/releases/bendlang-bend-2/)
- [Bend tool page (ai-tldr.dev)](https://ai-tldr.dev/tools/bend/)
- [HigherOrderCO / Bend (EveryDev)](https://www.everydev.ai/developers/higherorderco)

The bend-ssz factory description is taken from the author's write-up (Rebuffo, 2026). The other works are cited by author and venue in §14.
