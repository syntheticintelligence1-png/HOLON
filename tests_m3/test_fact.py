"""I26: the FACT rule, attribution (O25/N3) and the measure F(m, c), decided on the extracted real code (whitepaper §5.5,
Thm 6.8, Def 6.13, §8.4 FACT row, §8.5 hypothesis discipline, Cor 6.16, App. D, App. E FACT row, App. F fact_z, §11.3
O22/O25, §11.4 N3, §11.8 L_fact_Z; BUILD_PLAN I26 and §2; docs/HUMAN_ANSWERS.md Q19: extracted facts are the input of
every M3 law). This docstring is the contract.

Why. M1's only FACT law, laws/M1/L_fact_Z (REFUTED), is a statement over the hand abstraction spec/M1/facts. The
whitepaper's FACT obligation (§5.5: for every commitment m and every consumer c in its scope, ker(m) within ker(c) on R,
under local collision-freedom premises) has never been derived; its quantitative form F(m, c) (Def 6.13) never computed;
and its attribution instance, N3/O25 (under the BVH pin the content of a recommitted batch is fixed by the original
submitter S1 while the bond at risk is the recommitter S2's), never stated. Here commitments, consumers, pins and the
attribution register are computed from the extracted transitions, every law is stated over I30's typed model, decided
by the M3 pipeline, and every REFUTED law carries a witness that replays on the real Rollup.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment in
spec/M3/amendments.jsonl): spec/M3/lib/fact.json (the FACT sidecar: the model sidecar it builds on, the documents, the
binding, the hypotheses with their roles and I21 verdicts, the search budget, the measure's domain, the term budget, the
frozen back-test map); spec/M3/lib/fact_basis.json (every commitment, consumer, pin, law, premise, measure and predicted
outcome on the rollup document, computed at the prereg by tests_m3/_i26.py::fact_basis_doc, which writes rules F1-F9 a
second time, independently of holon/); tests_m3/_i26.py (that instrument, the back-test move, the raw-call replay);
tests_m3/fixtures/fact/harness/*.txt (byte copies of the I20 step harness taken at this prereg).

Scope and inputs
  - Milestone M3. The documents are those of spec/M3/lib/fact.json "documents": spec/M2/facts/morph_rollup.extracted.json
    (I19/A19, adopted by I20; G1 re-extracts it). Its model is its file name without ".json": morph_rollup.extracted; its
    contract the document's "contract": Rollup. Reach's initial state, the typed model, the witness step format, the
    hash binders and the real side of every replay are I30's (tests_m3/test_sort_types.py, clauses N1-N10, Refutation
    and Replay; model sidecar spec/M3/lib/sort_types.json; binding replay/M2/fragments.json).
  - No hand-written fact document and nothing computed from one is read by an I26 command (spec/M1/facts/, facts/,
    spec/M1/lib/, gen/M2/sorts/, gen/M2/extracted/m1_view.json). The back-test alone reads laws/M1/L_fact_Z.json,
    results/M1/L_fact_Z.json and the M1 model gen/M1/model/morph_rollup.bend.
  - Never edit spec/M1/, spec/M2/facts/, spec/M2/lib/, laws/M0-M2, gen/M0-M2, results/M0-M2, replay/M1, replay/M2,
    gen/M3/sorts/ or a frozen file. I20's differential (results/M2/differential.json) is not re-decided. Checked from
    git: no commit that writes an I26 outcome path (spec/M3/predictions.json, key I26) changes a path under those roots
    (TestRegressions.test_outcome_commits_touch_no_earlier_milestone; needs the real checkout's history, a missing .git
    is a failure, never a skip).

Terms
  A record of an action is an entry of its sections guards (each reach), checks, panics, calls, writes, events,
  mstores and loops. A write record has family, path ([] a scalar, [["map", k]] a whole register at key k, longer: a
  member), value, cond and seq. Its key is k (none for a scalar); it is whole when its path has at most one element;
  unconditional when cond is 1; final when no later write of the same action writes the same family whole at the
  syntactically same key. Conjuncts: ["&&", x, y, ..] splits recursively. A hash term has head keccak256 or sha256. Keys
  and terms are compared syntactically (canonical JSON). A blob-hash term is ["blobhash", i]; a blob loop is a loop record
  whose break term holds a blob-hash term, and its count term ["count", span] is a blob term too.

Commitments and consumers (rules F1-F7; whitepaper Def 4.3 Cm, Cn; App. B CONS)
  F1 Commitments. A mapping family F is a commitment when some non-view action has a commitment write of F (F2) and some
     action has an authenticating guard reach of F: a reach with a top-level conjunct ["==", R, H] or ["==", H, R],
     R = ["map", ["storage", F], k], H a hash term (the code authenticates an input against the stored digest at k).
  F2 Commitment sites: every final, whole, keyed, unconditional write of F in a non-view action whose value is a hash
     term. Site: {"action", "at": "writes[i]", "key"}.
  F3 Delivered data. A site's action that holds a blob-hash term in any record delivers the transaction's blobs with the
     commitment: the consumer "blobhash" (what off-chain derivation consumes, App. B CONS: derivation), its value the
     step's list of blob versioned hashes. One kernel basis element per such site: {"action", "at", "commitment",
     "consumer": "blobhash"}.
  F4 Kernel law per kernel basis element: law id "L_fact_kernel_<contract>_<action>_<F>_<consumer>"; fact id
     "<model>:kernel:<action>:<F>:<consumer>"; basis {"kind": "fact_kernel", "model", "contract", "action", "at",
     "commitment", "consumer"}.
  F5 Attribution consumers. An argument of an external call record calls[i] of an action b that is exactly ["member",
     ["map", ["storage", A], k], m], where b has an authenticating guard reach of a commitment F at the syntactically same
     key k with a smaller seq than the call: the register member A.m is a principal the call acts on, in the scope of F.
     Record {"family": A, "member": m, "commitment": F, "action": b, "at": "calls[i]", "fn"}.
  F6 Pins. A final, whole, unconditional write of a family P (not F) by a commitment site's action, at the
     syntactically same key as the site, whose value is the copy C = ["map", ["storage", P], key] ("how": "copy") or a ?
     term with C among its branches at any depth ("branch"): the stored content is reused (the BVH pin, App. A F2).
     Record {"action", "at", "family", "how", "commitment"}. The writers of a pinned family P: every whole write of P in
     every action, kind "copy" (value exactly C), "branch", "clear" (the literal 0) or "fresh" (otherwise).
  F7 Attribution basis: one per (pin of P by action w, attribution consumer (A, m) in the scope of the same commitment)
     such that w records A.m at the pin's key (a member of a final whole unconditional struct write of A there, or a
     member write); "recorded" is that member's value term. Law id "L_fact_attr_<contract>_<w>_<P>_<A>_<m>"; fact id
     "<model>:attribution:<w>:<P>:<A>.<m>"; basis {"kind": "fact_attribution", "model", "contract", "action": w, "pin":
     "writes[i]", "content": P, "commitment", "consumer": {"family", "member", "action", "at", "fn"}, "recorded"}.
  F8 Premises, the same strings in the law's fact ref, its DERIVATION entry and its record (sorted): "blobs_wf" (every
     entry of every step's blob-hash list is a nonzero word whose top byte is 0x01: EIP-4844 transaction validity, App.
     D "dense prefix; nonzero entries have top byte 0x01"); "cf:<h>" and "nz:<h>" for each hash binder h of I30's laws
     over the document (CF(h, S) over S = every key h is applied to in the law's steps, Cor 6.16, App. D; no hash value
     those steps compute is the zero word, I27's NZ); and, for a kernel law, "hyp:<id>" for each hypothesis of the
     sidecar with role "premise" whose constant's value (the document's constants) occurs as an integer literal in the
     records of its action. hyp:Hyp-Z0-kzg asserts that the document constant ZERO_VERSIONED_HASH equals the sidecar's
     recorded KZG versioned hash of the all-zero blob (a closed proposition; I3 and I21 checked it: pass).
  F9 The measure F(m, c) of a kernel basis element (Def 6.13: max over committed values mu of log2 |c(m^-1(mu) n R)|; Thm
     6.8: 0 iff the factorization holds). The commitment's value is a hash of a memory region; V is the list of its cells
     (mstore values, mloop blocks) that hold a blob term. Under CF, two steps with equal commitments and equal other
     inputs differ only in what V reads of the blobs, so the fiber of a committed value is the set of admissible blob
     lists B with equal (context, V(B)). Atoms: the maximal subterms of V and of the evaluable guards that are not
     literals, blob terms, operators (? == != ! || && < <= > >= + - *), hashes of regions or iter (here the version
     parameter and, for commitBatchWithProof, the stored word batchBlobVersionedHashes[k]); an atom's candidate values: 0
     and c - 1, c, c + 1 for every integer literal c it is compared with (those >= 0). Evaluable guards: every guard
     reach and check of the action that holds a blob term and only terms F9 interprets (others, such as the header-hash
     check relating the blobs to a free calldata parameter, are listed as "unevaluated"), plus those holding no blob
     term whose atoms are all atoms already found. The domain: the alphabet (the document's constants that are
     admissible blob hashes, plus spec/M3/lib/fact.json measure.fresh) and lists of length 0..max_length; ["blobhash", i]
     reads B[i] or 0; a blob loop's count is the first iteration at which its break holds; a hash of a region is an
     injective symbolic image of its cells (CF). Over every context (candidate combination) and every list satisfying the
     evaluable guards, group by (context, V(B)): "max_fiber" the largest group, "bits" log2 of it (6 decimals),
     "max_fibers" every largest group {"context": [[atom, value]..] sorted, "lists": the groups' lists as 0x-hex words,
     sorted}, "domain" {"alphabet", "max_length", "atoms": {atom: candidates}}, "unevaluated" ["guards[i].reaches[j]" |
     "checks[i]"] sorted. The attribution sub-form has no measure (null): its chooser ranges over a principal class that
     is an A-env predicate (ISubmitter is not extracted; gap G5).

Hypotheses in records (rule H1; whitepaper §8.5; I21's verdicts)
  For each hypothesis of spec/M3/lib/fact.json "hypotheses" a law lists it with "roles" (sorted): "premise" when
  "hyp:<id>" is among its premises; "witness" when the law is REFUTED and a step of its witness has an environment call
  whose fn is among the hypothesis's "functions" (the binding's stand-in answered it); "interpretation" when the law's
  consumer ("blobhash", or the attribution consumer's fn) is among its "interpretation". Record field
  [{"id", "roles", "result", "finding"}] sorted by id (result and finding the sidecar's, copied from
  audit/rounds/M2/round2/a4.json); "unconditional" is false iff a listed hypothesis with role premise or witness has a
  result other than "pass" (a failed hypothesis, or one no test can decide, such as HypV-proof1: "untestable");
  "impact_conditional_on" the sorted ids of listed hypotheses with result "fail" and role interpretation. A law resting on
  a failed or an undecided hypothesis is never presented as unconditional: HypZ fails (F-M2-41; T2: ParseBatch rejects
  the 8 mainnet zero-blob commits), Hyp-ISubmitter fails (F-M2-40) and HypV-proof1 is untestable (no prover).

The analysis (holon/rules/fact.py: F1-F8; holon/measures_fact.py: F9)
  python -m holon fact --milestone M [--root DIR] [--fact-sidecar PATH] [--facts PATH ..] [--out DIR] [--classify]
  [--backtest] writes <out, default gen/<M>/fact>/<model>.json for every document of the sidecar (default
  spec/<M>/lib/fact.json), or of --facts (planted documents): {"document": "fact", "fact_version": "holon-fact/0.1",
  "milestone", "model", "contract", "facts", "facts_sha256", "inputs": [{"path", "sha256"}] sorted by path,
  "commitments": [{"family", "sites": [{"action", "at", "key"}] sorted by (action, at), "authenticated_by": [{"action",
  "at": "guards[i]"}] sorted}] sorted by family, "kernel": [F3 records] sorted by (action, commitment),
  "attribution_consumers": [F5 records] sorted by (family, member, action, at), "pins": [F6 records] sorted by (family,
  action, at), "writers": {P: [{"action", "at", "kind"}] sorted by (action, at)}, "attribution": [{"action", "pin",
  "content", "commitment", "consumer", "recorded"}] sorted by (action, content, consumer family, member), "laws":
  {law_id: {"subform", "fact_id", "basis", "premises", "measure"}}}. Exit 0 written; 2 refused, nothing written (a
  sidecar or document missing or malformed); 1 an unreadable input. --classify writes results/<M>/fact/
  classification.json (after the run); --backtest writes results/M3/fact/backtest.json and gen/M3/fact/backtest/. Every
  file: json.dumps(obj, indent=2, sort_keys=True) + "\n"; deterministic, no timestamps, no absolute paths.

Laws (rule FACT; law ids a deterministic function of rule, subform and basis, BUILD_PLAN §2.3)
  Catalog. holon/rules/__init__.py: CATALOGS gains "holon-rules/1.5", whose rules are those of every earlier M3
  catalog version holon-rules/1.1 to 1.4 that exists when I26 builds (I24's PAR, I30's SORT, I27's UNDO at 1.3 and
  I31's DISCH at 1.4, the same producer objects) plus "FACT": {"kernel": .., "attribution": ..} (holon.rules.fact.
  PRODUCERS, SUBFORMS in that order); catalog_version("M3") == "holon-rules/1.5" (and every later M<k>); every earlier
  version and M2's catalog unchanged; test milestones keep their catalog. I25 adds no catalog version (its prereg
  733b947, rule L-G1: "holon.rules.CATALOGS and catalog_version('M3') are untouched by I25"), so 1.5 is the next free
  number after I31's 1.4; a catalog number is never reused.
  Law IR (holon-ir/0.3, laws/<M>/<law_id>.json): {"ir_version": "holon-ir/0.3", "law_id", "milestone", "rule": "FACT",
  "subform": "kernel" | "attribution", "rule_catalog_version", "facts", "facts_sha256", "notes", "statement":
  {"binders": B, "assume": [], "claim": {"eq": [{"fact": <fact id>, "on": [{"var": b} for each binder b, in order]},
  {"bool": true}]}, "scope": {"kind": "unbounded"}}}; no "evidence", no "predicted". B: kernel (s1, Reach), (x1, Act),
  (s2, Reach), (x2, Act); attribution (p, Trace), (y, Act); then the hash binders exactly as I30's laws over the same
  document have them. The fact term is new in IR 0.3 (additive: the schema gains it; holon.ir.render_term renders
  fact_ok[ID](args)); it is hashed through the ref "fact:<ID>": sha256 of canonical {"template":
  "holon.rules.fact/<subform>", "template_version": 1, "subform", "basis", "premises"}, recomputed from the document and
  the sidecar. canonical(o) = json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False) in UTF-8.
  Semantics of the generated Bool function fact_<x> (x the law id without "L_fact_"):
    kernel       (Thm 6.8 (iii), the product program of §8.4) if the premises hold, x1 and x2 are calls of the action,
                 both succeed (x1 from s1, x2 from s2) and the commitment F at x1's write key after x1 equals F at x2's
                 write key after x2, then blobs(x1) == blobs(x2); otherwise true.
    attribution  with (s, g) the state and the generated chooser companions after running p from Reach's initial state
                 (a reverted step changes neither): if the premises hold and y is a call of w that succeeds from s and
                 writes P at key k by its copy branch (the pin), then g_P[k] is bottom or A[k].m after y == g_P[k];
                 otherwise true (c = phi o m with m the content's chooser and phi the identity: whose bond is at risk
                 against who chose the content).
    chooser_P    a generated ghost companion per pinned family P (Prop 6.19 augmentation; never read by real code):
                 key -> address | bottom, bottom everywhere initially; in the ghost step of every action, each whole
                 write of P at key k that happens sets g_P[k] := the step's caller when its taken branch is fresh and
                 its value is not the literal 0, bottom when it is the literal 0 (a clear), and leaves it on a copy.
    fhit_<x>     the premises alone; a reachable inhabitant of it is the G11V non-vacuity witness of a PROVED law.
  Generated files: gen/M3/fact/models/<model>.fact.bend (the FACT section over I30's typed model gen/M3/sorts/models/
  <model>.bend, imported as M, never copied: blobs, the commitment's read after a step, chooser companions, run_fact, and
  per law fact_<x> and fhit_<x>); gen/M3/laws/<id>/LAWS.bend; gen/M3/proofs/<id>/PROOF.bend for a PROVED law or
  gen/M3/proofs/<id>/witness/PROOF.bend (the counter-law) for a REFUTED one; gen/M3/<id>/nonvac/{LAWS,PROOF}.bend. Each
  LAWS.bend declares exactly one law, naming fact_<x> (fhit_<x> in nonvac/); each deciding PROOF.bend imports it and only
  files under gen/M3. No hole, @unsafe, def f?, foreign import or law without proof under gen/M3. Taint (as I30's G4): no
  definition above the FACT section's ghost marker names a chooser companion or a definition below it.
  DERIVATION.json entry: {"law_id", "rule": "FACT", "subform", "facts", "basis", "premises", "measure": {"bits",
  "max_fiber"} | null, "statement_hash"}.

Deciding (python -m holon run --milestone M3)
  PROVED: a Bend- and BendTT-checked proof by a fixed route, assembled by holon.gen.mproofs.product (the product program:
  both runs' steps side by side, their checks and writes paired, the CF premise instantiated at the pairs of keys the
  two runs hash): "guard" (each run's success implies the evaluable guards, which fix the consumer: both lists []) or
  "injective" (equal commitments give equal hashed regions under CF, hence equal blob cells, and V is injective on the
  admissible lists); for attribution, "provenance" (an invariant over Reach relating A[k].m to g_P[k], proposed by an
  untrusted search, checked by Bend). A product program whose law_terms (spec/M3/lib/term_size.json measure (1)) exceeds
  the budget there (1000) is not checked: UNKNOWN, with "term_size" recorded (BUILD_PLAN I26 risks). law_terms of a FACT
  law is that measure exactly: terms of the law blocks of gen/M3/laws/<id>/LAWS.bend plus the largest terms(f) over the
  PROOF.bend files that discharge it (every PROOF.bend under gen/M3/proofs/<id>/, and gen/M3/<id>/nonvac/PROOF.bend);
  a discharging PROOF.bend imports only Base, the FACT section, I30's typed model, gen/M3/core and the LAWS.bend it
  discharges, and no other .bend file lies beside it under gen/M3/proofs/<id>/, so no part of a proof sits in an
  uncounted module. A PROVED law carries a checked reachable inhabitant of fhit_<x> (G11V) and its record names the
  route.
  REFUTED: a Bend- and BendTT-checked counter-law at a concrete witness, steps in I30's witness step format ({"action",
  "args", "calldata", "env": {"caller", "msg.value", "block.timestamp", "blobhash", "calls"}}), hash tables the real
  keccak256/sha256 of every key, block.timestamp never 0 and never decreasing along a run, external-call answers what the
  binding's deployment answers:
    kernel       {"runs": [{"prefix": [steps], "x": step}, {"prefix": [steps], "x": step}], "hashes"}
    attribution  {"prefix": [steps], "y": step, "t": [steps], "k", "chooser", "bonded", "hashes"}: chooser g_P[k] before y,
                 bonded A[k].m after y; t the consumer continuation (below), possibly [].
  The search (spec/M3/lib/fact.json "search"; I30's argument and environment variants plus the sidecar's time
  candidates; a deterministic order; at most max_candidates candidates per law; the first witness found):
    kernel (K1)  prefixes shared by both runs, breadth first up to prefix_depth steps, at most max_prefixes; x1 a
                 succeeding candidate step of the action; x2 each single-component variant of x1 (one argument, or the
                 caller, msg.value, block.timestamp or blob-hash list) that succeeds; the first pair with equal
                 commitments and different consumers. Runs with different prefixes are not searched (the bound says so).
    attribution  prefixes breadth first up to prefix_depth steps with the chooser companions; y a candidate step of w
                 taking the pin; the first (prefix, y) whose claim fails. Then t: the first sequence of at most
                 continuation_depth successful steps after y whose last step makes the consumer's external call (F5)
                 with A[k].m; t = [] when none within that bound (the record says so).
  UNKNOWN otherwise, the record naming the bound and the attempts.

Replay (replay/M3/fact/report.json, written by python -m holon replay --milestone M3, never by hand)
  {"document": "fact_replay", "laws": {law_id: entry}} for every REFUTED FACT law; an observation per step is
  {"status": "ok" | "revert", "ret", "logs": [{"topics", "data"}], "calls": [{"to", "data"}]} (logs and calls empty for a
  revert; bytes, words and addresses lowercase 0x-hex). Kernel entry {"runs": [{"trace": prefix + [x], "model": [obs], "real": [obs]} x 2],
  "commitment": {"model": [w1, w2], "real": [w1, w2]} (F at the write key after x, the real one read with vm.load at the
  document's layout), "consumers": [blob list 1, blob list 2], "calls_agree", "status"}; passed iff model == real at
  every step of both runs, every external call each real step made equals the witness's env call in order, both x
  succeed, the real commitments are equal and equal the model's, and the consumers differ. Attribution entry {"trace":
  prefix + [y] + t, "model": [obs], "real": [obs], "y_at": len(prefix), "chooser", "bonded": {"model", "real"},
  "consumer_call": {"step": index in the trace, "fn", "argument"} | null, "calls_agree", "status"}; passed iff model ==
  real at every step, calls agree, the real A[k].m after y (vm.load) equals the model's bonded and differs from the
  chooser, and, when t is non-empty, its last step's real external call to the consumer's function passes that value.
  Each run starts from the binding's deployment; the real side is the I20 step harness, one call step per step. G6 binds
  every REFUTED FACT record to a passed entry.

Records (results/<M>/<law_id>.json): valid under v1 and v2 (v2 gains "fact" additively); "fact": {"subform", "fact_id",
  "measure": {"bits", "max_fiber"} | null, "hypotheses": H1's list, "unconditional", "impact_conditional_on",
  "term_size": {"law_terms", "budget"} | null (non-null for every PROVED law), "route": "guard" | "injective" |
  "provenance" for a PROVED law, else null, "consumer_continuation": {"steps", "bound"} for a REFUTED attribution law,
  else null}; "premises": the law's (F8); "witness" as above for a REFUTED law, else null; "artifacts" (the FACT
  section, the law, the proof), "model_sha256" (the FACT section's), "non_vacuity" and "coverage" (I19's field).

Classification (Thm 6.8: F(m, c) = 0 iff the factorization holds)
  results/<M>/fact/classification.json {"document": "fact_classification", "milestone", "laws": {law_id: {"subform",
  "bits", "kernel": the record's status, "agree"}}, "disagreements": [law ids]}: for a kernel law agree iff (bits == 0)
  == (status == "PROVED") with a status PROVED or REFUTED (UNKNOWN never agrees); attribution laws carry bits null and
  agree null. A disagreement is a Surprise.

Back-test against M1 (rules FB1-FB4; BUILD_PLAN §2 invariant 7, the I24 back-test across documents)
  FB1 The map: spec/M3/lib/fact.json "backtest", fixed at the prereg: the M1 FACT law L_fact_Z, its analogue (the law id
      F4 gives for commitBatch, committedBatches, blobhash) and the move. holon fact --backtest reads it and never
      recomputes it; derive never reads it.
  FB2 Witness transfer. When both laws are REFUTED, the analogue's witness is moved to the M1 model's inputs by the map's
      move (tests_m3/_i26.py::move_kernel_witness: principals by the binding's table and the owner's token, the clock by
      the offset with M.A_wait steps joining the shared prefix, blob hashes to tokens, the input's fields to the M1 act
      M.A_commitBatch{who, ver, parent, n, lbn, prev, post, blobs}); the M1 counter-law cl_l_fact_z (the law of
      gen/M1/L_fact_Z/LAWS.bend) at (p, c1, c2) goes to gen/M3/fact/backtest/W_L_fact_Z/{LAWS,PROOF}.bend, importing
      gen/M1/model/morph_rollup.bend, and must be accepted by Bend: M3 still finds M1's obstruction.
  FB3 The CF bridge. The analogue is parametric in keccak256 under CF; M1 fixes its stand-in agg (version-2 blob hash,
      1000 + b_enc). CF(agg, S), S the distinct blob-token lists of the moved commit acts (c1, c2 and every commit act
      of p), is checked by computation: gen/M3/fact/backtest/CF_agg_L_fact_Z/{LAWS,PROOF}.bend states, for every pair of
      distinct elements of S, M.d_blob_hash(2n, a) != M.d_blob_hash(2n, b), proved by evaluation; Bend accepts it.
  FB4 results/M3/fact/backtest.json {"document": "fact_backtest", "milestone": "M3", "against": "M1", "map": {"path",
      "sha256"}, "rows": [{"old", "old_status", "old_statement_hash", "new", "new_status", "same_status", "moved": {"p",
      "c1", "c2"} | null (acts as move_kernel_witness writes them), "witness_transfer": {"law", "status": "checked" |
      "rejected" | null}, "cf_bridge": {"fn": "agg", "set": S, "law", "status"}, "acceptance": "witness" | null,
      "implication": "accepted" | "missing", "gap": null | gap id}], "gaps": [..], "complete": bool, "exit_blockers":
      [..]}: acceptance "witness" iff both REFUTED, the transfer is checked and the bridge is checked; then implication
      "accepted". Otherwise an open gap of kind "implication" (M3 exit cannot be claimed while one is open).

Sensitivity (static; the variants are built by the test from the committed document, never committed)
  S1 Renaming: every JSON string exactly equal to a renamed action, family, member or contract name is replaced; holon
     fact on the copy gives the instrument's analysis of the copy: the same basis under the new names, the new law ids.
  S2 Unpinned: commitState's write of the pinned family is deleted and commitBatchWithProof's is replaced by its value
     with the copy branch removed: no pin, no attribution law; the kernel basis and measures unchanged.
  S3 Zero sentinel: the integer literal ZERO_VERSIONED_HASH is replaced by 0 in every record of commitBatch and
     commitBatchWithProof: the no-blob value is not an admissible blob hash, both measures are 0 bits and neither kernel
     law carries hyp:Hyp-Z0-kzg.

Gate: python -m holon gate --milestone M3 --checks G1,G6,G11V passes on a copy of the tree: G1 regenerates gen/M3/fact,
  the FACT laws, the classification and the back-test byte for byte; G6 binds every REFUTED FACT record to a passed
  replay entry; G11V covers the PROVED FACT laws.

Gaps preregistered
  G1 O23 (the parent's lastBlockNumber outside the public input) and verifier dispatch: the public input is a hash passed
     to an external verifier, not a stored commitment, and its consumers are the circuits (HypC); I37.
  G2 O24 (version-0 calldata contexts): no such input on the adopted rollup document; the Go derivation documents are
     M3 inputs from I38/I39.
  G3 On-chain registers written at the commitment key (committedStateRoots, finalizedStateRoots, the BVH word) are not
     consumers here: consumers are the CONS edges (derivation, verifier dispatch, relay; App. B) and the attribution
     register a principal-keyed call acts on.
  G4 The derivation output (ParseBatch) is not a consumer of the rollup document: the delivered blob list stands for it;
     its decoder is HypZ's subject, and HypZ fails (impact_conditional_on).
  G5 The attribution sub-form has no measure (its chooser ranges over an A-env principal class).
  G6 The commitBatchWithProof recommit's consumer continuation needs a reopened window (F5/O19), beyond the continuation
     depth.
  G7 Kernel runs with different prefixes are not searched (K1).

Rules (AGENTS.md is binding): generate, never hand-write (laws only from holon/rules, with DERIVATION.json); no target,
  family, action, member, span or law id under holon/; never tune to a prediction (the sidecars and budgets are fixed);
  witnesses come from the compiled model; the real contract decides replay; no skips.

Residual risk, stated: the tests_m2 helpers the instrument imports (tests_m2/_i15.py: the Foundry toolchain check;
  tests_m2/_i16.py: the pinned checkout; tests_m2/_keccak.py) are fingerprinted only under the M2 keys that preregistered
  them. The instrument shares no code with holon/, but it was written by the same author as the contract. The
  instrument check TestInstrument.test_the_chain_instrument_runs_on_the_real_contract ran at the prereg: the real
  Rollup's behaviour on the hand-built O25 chain and Z pair is therefore known; the predictions are about holon's rules,
  model, search, kernel and replay.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests._util import ROOT, copy_repo, load_json, run_bend, run_holon  # frozen helpers
from tests.reference import mini_schema
from tests_m3 import _i26 as X

M3 = "M3"
DOC_REL = X.DOC_REL
MODEL = "morph_rollup.extracted"
CONTRACT = "Rollup"
FACT_SIDECAR = X.SIDECAR_REL
BASIS_REL = "spec/M3/lib/fact_basis.json"
CATALOG = "holon-rules/1.5"
SUBFORMS = ("kernel", "attribution")
LAWS3 = ROOT / "laws" / M3
RESULTS3 = ROOT / "results" / M3
GEN3 = ROOT / "gen" / M3
ANALYSIS = GEN3 / "fact" / f"{MODEL}.json"
CLASSIFICATION = RESULTS3 / "fact" / "classification.json"
BACKTEST = RESULTS3 / "fact" / "backtest.json"
REPLAY3 = ROOT / "replay" / M3 / "fact" / "report.json"
ZVH = X.ZVH
OWNER = X.owner_address()
SUBMITTERS = X.STANDIN_SUBMITTERS
CHALLENGER = X.CHALLENGER

K_BATCH = "L_fact_kernel_Rollup_commitBatch_committedBatches_blobhash"            # the L_fact_Z analogue
K_PROOF = "L_fact_kernel_Rollup_commitBatchWithProof_committedBatches_blobhash"
K_STATE = "L_fact_kernel_Rollup_commitState_committedBatches_blobhash"
A_STATE = "L_fact_attr_Rollup_commitState_batchBlobVersionedHashes_batchDataStore_submitter"   # O25/N3
A_PROOF = "L_fact_attr_Rollup_commitBatchWithProof_batchBlobVersionedHashes_batchDataStore_submitter"
PREDICTED = dict(X.PREDICTED)
BITS = {K_BATCH: 1.0, K_PROOF: 1.0, K_STATE: 0.0}
M1_FACT_Z_HASH = "sha256:5b3e051df5bfc68545307bd43c5c2ac7ec9bf9be54c6c9851f7757b25b5a512e"
M1_FACT_Z_WITNESS = {"c1": {"blobs": [], "lbn": 1, "n": 0, "op": "commitBatch", "parent": 0, "post": 110, "prev": 100,
                            "ver": 1, "who": 2},
                     "c2": {"blobs": [1], "lbn": 1, "n": 0, "op": "commitBatch", "parent": 0, "post": 110, "prev": 100,
                            "ver": 1, "who": 2},
                     "p": []}
SLASH = X.selector("slash(address)").hex()
HYP_SUBMITTER = {"id": "Hyp-ISubmitter", "result": "fail", "finding": "F-M2-40"}
HYP_Z0 = {"id": "Hyp-Z0-kzg", "result": "pass", "finding": None}
HYP_Z = {"id": "HypZ", "result": "fail", "finding": "F-M2-41"}
HYP_V = {"id": "HypV-proof1", "result": "untestable", "finding": None}
RENAME = {"commitBatch": "zActA", "commitState": "zActB", "commitBatchWithProof": "zActC", "proveState": "zActD",
          "revertBatch": "zActE", "importGenesisBatch": "zActF", "finalizeBatch": "zActG",
          "committedBatches": "zFamA", "batchBlobVersionedHashes": "zFamB", "batchDataStore": "zFamC",
          "submitter": "zMemA", "Rollup": "ZCon"}


# ======================================================================================== shared test helpers
def need(p: Path) -> dict:
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT) if p.is_relative_to(ROOT) else p} is missing")
    return load_json(p)


def built() -> None:
    """Fail fast, before a repository copy, while the I26 modules do not exist."""
    for rel in ("holon/rules/fact.py", "holon/measures_fact.py"):
        if not (ROOT / rel).is_file():
            raise AssertionError(f"{rel} is missing")
    import importlib
    mp = importlib.import_module("holon.gen.mproofs")
    if not callable(getattr(mp, "product", None)):
        raise AssertionError("holon.gen.mproofs.product is missing")


def sidecar() -> dict:
    return load_json(ROOT / FACT_SIDECAR)


def num(v) -> int:
    """A number of a witness or report: an int, or a 0x-hex (or decimal) string."""
    if isinstance(v, bool):
        raise AssertionError(f"a boolean where a number is expected: {v}")
    if isinstance(v, int):
        return v
    s = str(v)
    return int(s, 16) if s.lower().startswith("0x") else int(s)


def hexbytes(v) -> bytes:
    s = str(v)
    if not s.lower().startswith("0x"):
        raise AssertionError(f"not 0x-hex bytes: {s[:40]}")
    return bytes.fromhex(s[2:])


TERM_SIDECAR = ROOT / "spec" / "M3" / "lib" / "term_size.json"


def _strip_bend(text: str) -> str:
    keep = []
    for line in text.splitlines():
        s = line.lstrip()
        if s.startswith("#") or s.startswith("import "):
            continue
        keep.append(line.split("#", 1)[0])
    return "\n".join(keep)


def terms(text: str) -> int:
    """spec/M3/lib/term_size.json measure (I30's): comments and imports removed, literal lists collapsed to one
    placeholder each, then tokens plus placeholders."""
    side = load_json(TERM_SIDECAR)
    ph, lit, tok = side["placeholder"], re.compile(side["literal_list"]), re.compile(side["tokenizer"])
    t, prev = _strip_bend(text), None
    while prev != t:
        prev, t = t, lit.sub(ph, t)
    return len(tok.findall(t)) + t.count(ph)


def law_blocks(text: str) -> str:
    parts = re.split(r"(?m)^(?=\S)", _strip_bend(text))
    return "".join(q for q in parts if q.startswith("law "))


def discharging(lid: str) -> list:
    """The PROOF.bend files that discharge a FACT law (repo-relative, sorted)."""
    out = sorted(str(q.relative_to(ROOT)) for q in (GEN3 / "proofs" / lid).rglob("PROOF.bend"))
    nv = GEN3 / lid / "nonvac" / "PROOF.bend"
    if nv.is_file():
        out.append(str(nv.relative_to(ROOT)))
    return out


def check_law_terms(test: unittest.TestCase, lid: str, rec: dict) -> None:
    """A PROVED FACT law's term_size is the sidecar measure (1) recomputed from its files, within the budget, and its
    proof files import nothing that the measure would not count."""
    ts = rec["fact"]["term_size"]
    test.assertIsNotNone(ts, f"{lid}: a PROVED law records its term size")
    budget = load_json(TERM_SIDECAR)["budget"]
    test.assertEqual(ts["budget"], budget, lid)
    files = discharging(lid)
    test.assertTrue(files, f"{lid} is PROVED with no proof file")
    laws_file = GEN3 / "laws" / lid / "LAWS.bend"
    allowed = {(GEN3 / "fact" / "models" / f"{MODEL}.fact.bend").resolve(),
               (GEN3 / "sorts" / "models" / f"{MODEL}.bend").resolve(),
               (GEN3 / "core" / "PROOF.bend").resolve(), (GEN3 / "core" / "LAWS.bend").resolve(),
               laws_file.resolve(), (GEN3 / lid / "nonvac" / "LAWS.bend").resolve()}
    for f in files:
        text = (ROOT / f).read_text(encoding="utf-8")
        for target in re.findall(r"(?m)^import\s+(\S+)", text):
            if target != "Base":
                test.assertIn(((ROOT / f).parent / target).resolve(), allowed, f"{f} imports {target}")
    other = sorted(str(q.relative_to(ROOT)) for q in (GEN3 / "proofs" / lid).rglob("*.bend") if q.name != "PROOF.bend")
    test.assertEqual(other, [], f"{lid}: Bend files beside the proofs that the measure would not count")
    want = (terms(law_blocks(laws_file.read_text(encoding="utf-8")))
            + max(terms((ROOT / f).read_text(encoding="utf-8")) for f in files))
    test.assertEqual(ts["law_terms"], want, lid)
    test.assertLessEqual(ts["law_terms"], budget, lid)


def basis() -> dict:
    return load_json(ROOT / BASIS_REL)


def doc_basis() -> dict:
    return basis()["documents"][DOC_REL]


def fact_laws(root: Path = ROOT, milestone: str = M3) -> dict:
    return {p.stem: load_json(p) for p in sorted((root / "laws" / milestone).glob("L_fact_*.json"))}


def fact_records(root: Path = ROOT, milestone: str = M3) -> dict:
    return {p.stem: load_json(p) for p in sorted((root / "results" / milestone).glob("L_fact_*.json"))}


def derivation(root: Path = ROOT, milestone: str = M3) -> dict:
    return {e["law_id"]: e for e in need(root / "laws" / milestone / "DERIVATION.json")["laws"]}


def run_ok(test: unittest.TestCase, args: list, cwd: Path | None = None, timeout: int = 7200):
    p = run_holon([str(a) for a in args], cwd=cwd, timeout=timeout)
    test.assertEqual(p.returncode, 0, f"holon {' '.join(map(str, args))}: {(p.stdout + p.stderr)[-3000:]}")
    return p


def m3_catalog() -> str:
    """The catalog M3 derives with: holon-rules/1.5, or a later version holding every producer of 1.5 (the same
    objects), so that a later rule does not turn these tests red."""
    import importlib
    rules = importlib.import_module("holon.rules")
    v = rules.catalog_version("M3")
    if v != CATALOG:
        base, cat = rules.CATALOGS[CATALOG], rules.CATALOGS[v]
        for rule, subs in base.items():
            for sub, prod in subs.items():
                if (cat.get(rule) or {}).get(sub) is not prod:
                    raise AssertionError(f"M3 derives with {v}, which drops {rule}/{sub} of {CATALOG}")
    return v


def hash_binders_of_sort_laws(root: Path = ROOT) -> list | None:
    """The hash binders of I30's laws over the rollup document (the Fn binders), or None."""
    for p in sorted((root / "laws" / M3).glob("L_sort_*.json")):
        law = load_json(p)
        if law.get("facts") == DOC_REL:
            return [b for b in law["statement"]["binders"] if str(b.get("type", "")).startswith("Fn<")]
    return None


def premises_of(lid: str, hb: list) -> list:
    """F8: the instrument's fixed premises plus cf/nz per hash binder."""
    fixed = doc_basis()["laws"][lid]["premises_fixed"]
    return sorted(fixed + [f"cf:{b['name']}" for b in hb] + [f"nz:{b['name']}" for b in hb])


def h1(lid: str, rec: dict, side: dict) -> list:
    """Rule H1 applied to a record (its premises, status and witness)."""
    calls = set()
    w = rec.get("witness") or {}
    steps = []
    if "runs" in w:
        for r in w["runs"]:
            steps += list(r.get("prefix") or []) + [r["x"]]
    elif w:
        steps = list(w.get("prefix") or []) + [w["y"]] + list(w.get("t") or [])
    for s in steps:
        for c in (s.get("env") or {}).get("calls") or []:
            calls.add(c.get("fn"))
    b = doc_basis()["laws"][lid]
    consumer = "blobhash" if b["subform"] == "kernel" else b["basis"]["consumer"]["fn"]
    out = []
    for hid, h in sorted(side["hypotheses"].items()):
        roles = []
        if f"hyp:{hid}" in (rec.get("premises") or []):
            roles.append("premise")
        if rec.get("status") == "REFUTED" and calls & set(h.get("functions") or []):
            roles.append("witness")
        if consumer in (h.get("interpretation") or []):
            roles.append("interpretation")
        if roles:
            out.append({"id": hid, "roles": sorted(roles), "result": h["result"], "finding": h["finding"]})
    return out


def batch_input(st: dict) -> dict:
    return st["args"][0] if isinstance(st["args"], list) else st["args"]["batchDataInput"]


def kernel_key(st: dict) -> int:
    """The commitment key of a commit step: the parent header's index (bytes 1..8, big-endian) + 1."""
    return int.from_bytes(hexbytes(batch_input(st)["parentBatchHeader"])[1:9], "big") + 1


def obs_of(real_step: dict) -> dict:
    """The replay report's observation of a real step (calls as {to, data})."""
    return {"status": real_step["status"], "ret": real_step["ret"], "logs": real_step["logs"],
            "calls": [{"to": c["to"], "data": c["data"]} for c in real_step["calls"]]}


def rename_doc(obj, mp: dict):
    if isinstance(obj, str):
        return mp.get(obj, obj)
    if isinstance(obj, list):
        return [rename_doc(x, mp) for x in obj]
    if isinstance(obj, dict):
        return {k: rename_doc(v, mp) for k, v in obj.items()}
    return obj


def replace_literal(obj, old: int, new: int):
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return new if obj == old else obj
    if isinstance(obj, list):
        return [replace_literal(x, old, new) for x in obj]
    if isinstance(obj, dict):
        return {k: replace_literal(v, old, new) for k, v in obj.items()}
    return obj


def strip_copy(v, C):
    """A value with the ? branches equal to C removed (the other branch kept, without its condition)."""
    if X.is_op(v, "?") and len(v) == 4:
        if v[2] == C:
            return strip_copy(v[3], C)
        if v[3] == C:
            return strip_copy(v[2], C)
        return ["?", v[1], strip_copy(v[2], C), strip_copy(v[3], C)]
    return v


def holon_analysis(test: unittest.TestCase, doc_obj: dict, tmp: Path, name: str = "morph_rollup.extracted.json") -> tuple:
    """holon fact --facts on a planted variant, and the instrument's analysis of the same file."""
    d = tmp / "doc"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(json.dumps(doc_obj, indent=2, sort_keys=True) + "\n")
    out = tmp / "out"
    run_ok(test, ["fact", "--milestone", M3, "--facts", str(p), "--out", str(out)])
    return load_json(out / name), X.analyse(p, sidecar(), str(p))


def compare_analysis(test: unittest.TestCase, got: dict, exp: dict, label: str) -> None:
    for key in ("commitments", "kernel", "attribution_consumers", "pins", "writers", "attribution"):
        test.assertEqual(X.ck(got[key]), X.ck(exp[key]), f"{label}: {key}")
    test.assertEqual(sorted(got["laws"]), sorted(exp["laws"]), label)
    for lid, e in exp["laws"].items():
        g = got["laws"][lid]
        test.assertEqual((g["subform"], g["fact_id"]), (e["subform"], e["fact_id"]), f"{label} {lid}")
        test.assertEqual(X.ck(g["basis"]), X.ck(e["basis"]), f"{label} {lid}")
        test.assertTrue(set(e["premises_fixed"]) <= set(g["premises"]), f"{label} {lid}: {g['premises']}")
        test.assertEqual(sorted(p for p in g["premises"] if p.startswith("hyp:")),
                         sorted(p for p in e["premises_fixed"] if p.startswith("hyp:")), f"{label} {lid}")
        test.assertEqual(X.ck(g["measure"]), X.ck(e["measure"]), f"{label} {lid}: measure")


# =========================================================================================== the tests
class TestInstrument(unittest.TestCase):
    """Construction checks of the instruments fixed at this prereg (not predictions)."""

    def test_the_basis_sidecar_is_the_computation(self):
        """I26-R4 (part): spec/M3/lib/fact_basis.json equals fact_basis_doc over the committed inputs, whose sha256 it
        lists; its totals are the contract's numbers."""
        b = basis()
        for x in b["inputs"]:
            self.assertEqual(X.sha256_file(ROOT / x["path"]), x["sha256"], x["path"])
        self.assertEqual(X.ck({k: v for k, v in b.items() if k != "doc"}), X.ck(X.fact_basis_doc(ROOT)))
        self.assertEqual(b["totals"], {"attribution": 2, "attribution_consumers": 1, "commitments": 1, "kernel": 3,
                                       "laws": {"attribution": 2, "kernel": 3}, "pins": 2,
                                       "predicted": {"PROVED": 1, "REFUTED": 4, "UNKNOWN": 0}, "sites": 4})
        self.assertEqual({lid: (x["subform"], x["predicted"]) for lid, x in doc_basis()["laws"].items()}, PREDICTED)

    def test_the_fact_sidecar_transcribes_its_sources(self):
        """I26-R4 (part): the sidecar's hypothesis verdicts are I21's (audit/rounds/M2/round2/a4.json), Hyp-Z0-kzg's
        value is the document's constant and the computed one of results/M2/hypotheses.json; the move transcribes the
        binding (who2addr, EPOCH, blobEnc, the M1 initial clock) and the M1 model's agg."""
        s = sidecar()
        a4 = load_json(ROOT / s["verdicts"])["hypotheses"]
        for hid, h in s["hypotheses"].items():
            want = a4[hid]["result"] if a4[hid]["verdict"] == "tested" else a4[hid]["verdict"]
            self.assertEqual((h["result"], h["finding"]), (want, a4[hid]["finding"]), hid)
        doc = load_json(ROOT / DOC_REL)
        z = s["hypotheses"]["Hyp-Z0-kzg"]
        self.assertEqual(z["value"], doc["constants"][z["constant"]])
        self.assertEqual(z["value"], load_json(ROOT / "results" / "M2" / "hypotheses.json")["Hyp-Z0-kzg"]["computed"])
        harness = (X.HARNESS_DIR / "HolonTraceReplay.t.sol.txt").read_text()
        self.assertIn("uint256 internal constant EPOCH = 1_700_000_000;", harness)
        self.assertIn("return who == 1 ? address(this) : address(uint160(0x1000 + who));", harness)
        self.assertIn("if (v == 1) return ZVH;", harness)
        mv = s["backtest"]["move"]
        self.assertEqual(mv["clock_offset"], X.EPOCH)
        self.assertEqual(mv["m1_clock0"], load_json(ROOT / "spec" / "M1" / "facts" / "morph_rollup.json")["initial"]["t"])
        self.assertEqual({k: v for k, v in mv["principals"].items()},
                         {"0x" + format(0x1000 + w, "040x"): w for w in (2, 3, 4, 5)})
        self.assertEqual(mv["blob_tokens"], {ZVH: 1})
        m1 = (ROOT / "gen" / "M1" / "model" / "morph_rollup.bend").read_text()
        self.assertIn("ite(Nat, Nat.is_eq(ver, 2n), Nat.add(1000n, b_enc(blobs))", m1)
        self.assertEqual(s["backtest"]["rows"][0]["new"], K_BATCH)

    def test_the_harness_copies_are_the_binding_harness(self):
        """I26-R4 (part): tests_m3/fixtures/fact/harness/*.txt are byte copies of the I20 step harness the binding
        names, pinned by sha256."""
        src = {"HolonStepBase.sol": "replay/M2/solidity/HolonStepBase.sol",
               "HolonTraceReplay.t.sol": "replay/M1/solidity/HolonTraceReplay.t.sol",
               "HolonExtractedStep.t.sol": "replay/M2/solidity/HolonExtractedStep.t.sol"}
        for name, pin in X.HARNESS.items():
            self.assertEqual(X.sha256_file(X.HARNESS_DIR / f"{name}.txt"), pin, name)
            self.assertEqual(X.sha256_file(ROOT / src[name]), pin, src[name])

    def test_the_chain_instrument_runs_on_the_real_contract(self):
        """I26-R4 (part): the raw-call instrument works on the pinned Rollup as the I20 binding deploys it. The O25 chain
        built by hand (tests_m3/_i26.py::o25_chain: S1 commits batch 1 with one blob, the owner reverts it, S2 recommits
        it with commitState and no blob, the challenger challenges it, S1 proves it after the proof window) succeeds at
        every step; the harness (the owner) is the address the instrument assumes; committedBatches[1] after the recommit
        is the original commit's; batchDataStore[1].submitter is S1, then S1 after the revert, then S2; the timed-out
        proof's ISubmitter.slash call passes S2. The Z pair (z_pair) commits the same committedBatches[1] with no blob
        and with [ZERO_VERSIONED_HASH], both storing batchBlobVersionedHashes[1] = ZERO_VERSIONED_HASH."""
        doc = X.Doc(ROOT / DOC_REL)
        cb, bvh, sub = (X.family_slot(doc, "committedBatches", 1), X.family_slot(doc, "batchBlobVersionedHashes", 1),
                        X.family_slot(doc, "batchDataStore", 1, "submitter"))
        tr, info = X.o25_chain()
        r1, r2, zinfo = X.z_pair()
        out = X.realized([tr, r1, r2], [cb, bvh, sub])
        o25 = out[0]
        self.assertEqual(o25["harness"], OWNER)
        self.assertEqual([s["status"] for s in o25["steps"]], ["ok"] * 5, [s["ret"] for s in o25["steps"]])
        h = int(info["hash"], 16)
        self.assertEqual([s["slots"][cb] for s in o25["steps"]], [h, 0, h, h, h])
        self.assertEqual([s["slots"][sub] for s in o25["steps"]],
                         [int(info["s1"], 16), int(info["s1"], 16), int(info["s2"], 16), int(info["s2"], 16),
                          int(info["s2"], 16)])
        slash = [c for c in o25["steps"][4]["calls"] if c["data"].startswith("0x" + SLASH)]
        self.assertEqual(len(slash), 1)
        self.assertEqual(int(slash[0]["data"][10:], 16), int(info["s2"], 16))
        for run in out[1:]:
            self.assertEqual(run["steps"][0]["status"], "ok")
            self.assertEqual(run["steps"][0]["slots"][cb], int(zinfo["hash"], 16))
            self.assertEqual(run["steps"][0]["slots"][bvh], int(ZVH, 16))


class TestAnalysis(unittest.TestCase):
    """holon fact over the extracted rollup document (F1-F9)."""

    @classmethod
    def setUpClass(cls):
        built()
        cls.an = need(ANALYSIS)

    def test_the_analysis_document(self):
        """I26-R4 (part): gen/M3/fact/morph_rollup.extracted.json has the contract's keys and inputs and reads no hand
        document; two runs of holon fact are byte-identical and equal the committed file."""
        self.assertEqual((self.an["document"], self.an["fact_version"]), ("fact", "holon-fact/0.1"))
        self.assertEqual((self.an["milestone"], self.an["model"], self.an["contract"], self.an["facts"]),
                         (M3, MODEL, CONTRACT, DOC_REL))
        self.assertEqual(self.an["facts_sha256"], X.sha256_file(ROOT / DOC_REL))
        paths = [x["path"] for x in self.an["inputs"]]
        self.assertEqual(paths, sorted(paths))
        self.assertIn(DOC_REL, paths)
        self.assertIn(FACT_SIDECAR, paths)
        self.assertFalse([p for p in paths if p.startswith(("spec/M1/", "facts/", "gen/M2/"))], paths)
        tmp = Path(tempfile.mkdtemp(prefix="holon-i26-fact-"))
        try:
            run_ok(self, ["fact", "--milestone", M3, "--out", str(tmp / "a")])
            run_ok(self, ["fact", "--milestone", M3, "--out", str(tmp / "b")])
            a = (tmp / "a" / f"{MODEL}.json").read_bytes()
            self.assertEqual(a, (tmp / "b" / f"{MODEL}.json").read_bytes())
            self.assertEqual(a, ANALYSIS.read_bytes())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_commitments_consumers_pins_and_basis(self):
        """I26-P1: exactly one commitment, committedBatches, with 4 commitment sites (commitBatch, commitBatchWithProof,
        commitState and importGenesisBatch writes[0]) and 7 authenticating guard reaches; the delivered-data consumer for
        commitBatch, commitBatchWithProof and commitState (importGenesisBatch reads no blob hash); one attribution
        consumer, batchDataStore.submitter, the argument of proveState calls[1] ISubmitter.slash; two pins of
        batchBlobVersionedHashes (commitState writes[2] copy, commitBatchWithProof writes[2] branch); its writers
        commitBatch fresh, commitBatchWithProof branch, commitState copy, finalizeBatch clear, importGenesisBatch fresh;
        two attribution basis elements recording the caller (commitState) and 0 (commitBatchWithProof). Exactly
        spec/M3/lib/fact_basis.json."""
        exp = doc_basis()
        compare_analysis(self, self.an, exp, "rollup")
        c = self.an["commitments"]
        self.assertEqual([x["family"] for x in c], ["committedBatches"])
        self.assertEqual([(s["action"], s["at"]) for s in c[0]["sites"]],
                         [("commitBatch", "writes[0]"), ("commitBatchWithProof", "writes[0]"),
                          ("commitState", "writes[0]"), ("importGenesisBatch", "writes[0]")])
        self.assertEqual([(x["action"], x["at"]) for x in c[0]["authenticated_by"]],
                         [("commitBatch", "guards[16]"), ("commitBatchWithProof", "guards[16]"),
                          ("commitState", "guards[15]"), ("finalizeBatch", "guards[6]"),
                          ("proveCommittedBatchState", "guards[4]"), ("proveState", "guards[7]"),
                          ("revertBatch", "guards[6]")])
        self.assertEqual([k["action"] for k in self.an["kernel"]], ["commitBatch", "commitBatchWithProof", "commitState"])
        self.assertEqual(self.an["attribution_consumers"],
                         [{"action": "proveState", "at": "calls[1]", "commitment": "committedBatches",
                           "family": "batchDataStore", "fn": "ISubmitter.slash", "member": "submitter"}])
        self.assertEqual([(p["action"], p["at"], p["family"], p["how"]) for p in self.an["pins"]],
                         [("commitBatchWithProof", "writes[2]", "batchBlobVersionedHashes", "branch"),
                          ("commitState", "writes[2]", "batchBlobVersionedHashes", "copy")])
        self.assertEqual([(w["action"], w["kind"]) for w in self.an["writers"]["batchBlobVersionedHashes"]],
                         [("commitBatch", "fresh"), ("commitBatchWithProof", "branch"), ("commitState", "copy"),
                          ("finalizeBatch", "clear"), ("importGenesisBatch", "fresh")])
        self.assertEqual({a["action"]: a["recorded"] for a in self.an["attribution"]},
                         {"commitBatchWithProof": 0, "commitState": ["caller"]})
        self.assertEqual(sorted(self.an["laws"]), sorted(PREDICTED))

    def test_the_measure(self):
        """I26-P3: F(Z, derivation) = 1 bit. The commitBatch kernel basis element's measure is 1 bit (max fiber 2: at
        versions 0 and 1 the committed blob word ZERO_VERSIONED_HASH comes from [] and from [ZERO_VERSIONED_HASH]; every
        other fiber, and every fiber at version 2, holds one list); commitBatchWithProof 1 bit (its fresh branch, the
        stored word 0; its header-hash check guards[19].reaches[0] unevaluated); commitState 0 bits (Rollup.sol:276
        admits only []). Exactly fact_basis.json's computation."""
        for lid, bits in BITS.items():
            m = self.an["laws"][lid]["measure"]
            e = doc_basis()["laws"][lid]["measure"]
            self.assertEqual(X.ck(m), X.ck(e), lid)
            self.assertEqual(m["bits"], bits, lid)
        m = self.an["laws"][K_BATCH]["measure"]
        self.assertEqual(m["max_fiber"], 2)
        self.assertEqual([f["lists"] for f in m["max_fibers"]], [[[], [ZVH]], [[], [ZVH]]])
        self.assertEqual([dict(f["context"]) for f in m["max_fibers"]],
                         [{X.ck(["member", ["param", "batchDataInput"], "version"]): v} for v in (0, 1)])
        self.assertEqual(self.an["laws"][K_PROOF]["measure"]["unevaluated"], ["guards[19].reaches[0]"])
        self.assertEqual(self.an["laws"][K_STATE]["measure"]["max_fibers"], [{"context": [], "lists": [[]]}])
        for lid in (A_STATE, A_PROOF):
            self.assertIsNone(self.an["laws"][lid]["measure"], lid)


class TestRegistry(unittest.TestCase):
    """The catalog, the producers and the generic code (construction checks)."""

    def test_catalogs(self):
        """I26-R4 (part): holon-rules/1.5 holds FACT's two producers and every producer of each earlier M3 catalog
        (holon-rules/1.1 to 1.4, those that exist), the same objects; M3 derives with it; M2's catalog is unchanged."""
        built()
        import importlib
        rules = importlib.import_module("holon.rules")
        fact = importlib.import_module("holon.rules.fact")
        m3_catalog()
        self.assertEqual(tuple(fact.SUBFORMS), SUBFORMS)
        self.assertEqual(rules.catalog_version("M2"), "holon-rules/1.0")
        cat = rules.CATALOGS[CATALOG]
        self.assertEqual(dict(cat["FACT"]), dict(fact.PRODUCERS))
        self.assertEqual(sorted(cat["FACT"]), sorted(SUBFORMS))
        self.assertTrue({"PAR", "SORT"} <= set(cat))
        earlier = [v for v in rules.CATALOGS if re.fullmatch(r"holon-rules/1\.[1-4]", v)]
        self.assertIn("holon-rules/1.1", earlier)
        for v in earlier:
            for rule, subs in rules.CATALOGS[v].items():
                for sub, prod in subs.items():
                    self.assertIs(cat[rule][sub], prod, f"{v}: {rule}/{sub}")

    def test_new_code_names_no_target(self):
        """I26-R4 (part, AGENTS rules 2 and 4): holon/rules/fact.py and holon/measures_fact.py hold no action, family,
        member, contract or law id of the documents they read; no file under holon/ names an I26 law id or fact id."""
        built()
        d = load_json(ROOT / DOC_REL)
        names = {a["name"] for a in d["actions"]} | {f["name"] for f in d["storage"]} | {d["contract"]}
        names |= {m["name"] for f in d["storage"] for m in f.get("fields") or []}
        names |= {"Rollup.sol", "L_fact_", "morph", "ISubmitter", "ZERO_VERSIONED_HASH"}
        names -= {"owner", "paused", "receive", "initialize", "verifier", "finished"}
        for rel in ("holon/rules/fact.py", "holon/measures_fact.py"):
            text = (ROOT / rel).read_text()
            hits = sorted(n for n in names if re.search(r"(?<![A-Za-z0-9_])" + re.escape(n) + r"(?![A-Za-z0-9_])", text))
            self.assertEqual(hits, [], rel)
        bad = set(PREDICTED) | {x["fact_id"] for x in doc_basis()["laws"].values()}
        for p in sorted((ROOT / "holon").rglob("*")):
            if p.suffix not in (".py", ".mjs", ".js", ".json") or not p.is_file():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            self.assertEqual(sorted(b for b in bad if b in text), [], str(p.relative_to(ROOT)))


class TestDerivation(unittest.TestCase):
    """laws/M3 L_fact_* (F4, F7, F8)."""

    @classmethod
    def setUpClass(cls):
        built()
        cls.laws = fact_laws()
        cls.der = derivation()

    def test_the_fact_laws(self):
        """I26-P2: holon derive --milestone M3 emits exactly the five FACT laws fact_basis.json lists, all over the
        extracted rollup document: the kernel laws of commitBatch, commitBatchWithProof and commitState, and the
        attribution laws of the commitState and commitBatchWithProof pins; law IR, bases, binders, claim, premises
        (hyp:Hyp-Z0-kzg exactly on the commitBatch and commitBatchWithProof kernel laws) and DERIVATION entries as the
        contract states; refs "fact:<id>" hash the template, version, subform, basis and premises."""
        exp = doc_basis()["laws"]
        self.assertEqual(sorted(self.laws), sorted(exp))
        hb = hash_binders_of_sort_laws()
        self.assertIsNotNone(hb, f"no laws/M3/L_sort_*.json over {DOC_REL}: I30's hash binders are unknown")
        cv = m3_catalog()
        import importlib
        refs = importlib.import_module("holon.gen.refs")
        for lid, law in self.laws.items():
            e = exp[lid]
            self.assertEqual((law["ir_version"], law["rule"], law["subform"], law["milestone"],
                              law["rule_catalog_version"], law["facts"]),
                             ("holon-ir/0.3", "FACT", e["subform"], M3, cv, DOC_REL), lid)
            self.assertEqual(law["facts_sha256"], X.sha256_file(ROOT / DOC_REL))
            self.assertNotIn("evidence", law)
            self.assertNotIn("predicted", law)
            st = law["statement"]
            head = ([("s1", "Reach"), ("x1", "Act"), ("s2", "Reach"), ("x2", "Act")] if e["subform"] == "kernel"
                    else [("p", "Trace"), ("y", "Act")])
            self.assertEqual([(b["name"], b["type"]) for b in st["binders"][:len(head)]], head, lid)
            self.assertEqual(st["binders"][len(head):], hb, lid)
            self.assertEqual(st["assume"], [])
            self.assertEqual(st["claim"], {"eq": [{"fact": e["fact_id"], "on": [{"var": b["name"]}
                                                                                for b in st["binders"]]},
                                                  {"bool": True}]})
            self.assertEqual(st["scope"], {"kind": "unbounded"})
            prem = premises_of(lid, hb)
            d = self.der[lid]
            self.assertEqual((d["rule"], d["subform"], d["facts"]), ("FACT", e["subform"], DOC_REL))
            self.assertEqual(X.ck(d["basis"]), X.ck(e["basis"]), lid)
            self.assertEqual(d["premises"], prem, lid)
            self.assertEqual(d["measure"], None if e["measure"] is None else
                             {"bits": e["measure"]["bits"], "max_fiber": e["measure"]["max_fiber"]}, lid)
            self.assertEqual(refs.refs(law, load_json(ROOT / DOC_REL)).get(f"fact:{e['fact_id']}"),
                             X.fact_ref(e["subform"], e["basis"], prem), lid)
        self.assertEqual(sorted(lid for lid in exp if "hyp:Hyp-Z0-kzg" in exp[lid]["premises_fixed"]),
                         sorted([K_BATCH, K_PROOF]))

    def test_derive_reproduces_the_committed_m3_laws(self):
        """I26-R4 (part): holon derive --milestone M3 in a repository copy reproduces laws/M3 (every file) byte for byte
        and reads no hand-written fact document."""
        repo = copy_repo()
        try:
            shutil.rmtree(repo / "laws" / M3)
            run_ok(self, ["derive", "--milestone", M3], cwd=repo)
            for p in sorted(LAWS3.glob("*.json")):
                self.assertEqual((repo / "laws" / M3 / p.name).read_bytes(), p.read_bytes(), p.name)
            self.assertEqual(sorted(x.name for x in (repo / "laws" / M3).glob("*.json")),
                             sorted(x.name for x in LAWS3.glob("*.json")))
            ins = [x["path"] for x in load_json(repo / "laws" / M3 / "DERIVATION.json").get("inputs", [])]
            self.assertIn(FACT_SIDECAR, ins)
            self.assertFalse([p for p in ins if p.startswith(("spec/M1/facts", "facts/"))], ins)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


class TestOutcomes(unittest.TestCase):
    """holon run, records, the replay report and the independent real-side replay."""

    @classmethod
    def setUpClass(cls):
        built()
        cls.rec = fact_records()

    def _status(self, lid):
        r = self.rec.get(lid)
        self.assertIsNotNone(r, f"results/M3/{lid}.json is missing")
        return r["status"]

    def _entry(self, lid):
        rep = (need(REPLAY3).get("laws") or {}).get(lid)
        self.assertIsNotNone(rep, f"replay/M3/fact/report.json has no entry {lid}")
        self.assertEqual(rep["status"], "passed", rep)
        self.assertIs(rep["calls_agree"], True)
        return rep

    def _attribution(self, lid, fresh_action="commitBatch"):
        self.assertEqual(self._status(lid), "REFUTED", self.rec[lid].get("attempts"))
        w = self.rec[lid]["witness"] or {}
        for k in ("prefix", "y", "t", "k", "chooser", "bonded", "hashes"):
            self.assertIn(k, w, lid)
        pre = w["prefix"]
        self.assertEqual(len(pre), 2, f"{lid}: {[s['action'] for s in pre]}")
        self.assertEqual((pre[0]["action"], pre[1]["action"]), (fresh_action, "revertBatch"), lid)
        s1 = str(pre[0]["env"]["caller"]).lower()
        self.assertIn(s1, SUBMITTERS, lid)
        self.assertEqual(kernel_key(pre[0]), num(w["k"]), lid)
        self.assertEqual(str(pre[1]["env"]["caller"]).lower(), OWNER, lid)
        self.assertEqual(num(w["chooser"]), num(s1), lid)
        rep = self._entry(lid)
        self.assertEqual(rep["trace"], pre + [w["y"]] + list(w["t"]))
        self.assertEqual(rep["model"], rep["real"])
        self.assertEqual([o["status"] for o in rep["real"]], ["ok"] * len(rep["trace"]), lid)
        self.assertEqual(rep["y_at"], 2)
        self.assertEqual(num(rep["chooser"]), num(s1))
        self.assertEqual(num(rep["bonded"]["model"]), num(rep["bonded"]["real"]))
        self.assertEqual(num(rep["bonded"]["real"]), num(w["bonded"]))
        self.assertNotEqual(num(rep["bonded"]["real"]), num(s1))
        return w, rep, s1

    def test_the_l_fact_z_analogue_is_refuted(self):
        """I26-R2 (part; the plan's regression): the parametric analogue of L_fact_Z, L_fact_kernel_Rollup_commitBatch_
        committedBatches_blobhash (premises blobs_wf, cf:<h>, hyp:Hyp-Z0-kzg, nz:<h>), is REFUTED, as L_fact_Z is in M1.
        Witness: one shared prefix, empty (Reach's initial state); x1 and x2 calls of commitBatch with identical calldata
        at version 0 or 1, by one active submitter of the binding's stand-in, at one block.timestamp, with the blob-hash
        lists [] and [ZERO_VERSIONED_HASH] (in either order); both succeed and commit equal committedBatches[k]."""
        self.assertEqual(self._status(K_BATCH), "REFUTED", self.rec[K_BATCH].get("attempts"))
        w = self.rec[K_BATCH]["witness"]
        r1, r2 = w["runs"]
        self.assertEqual((r1["prefix"], r2["prefix"]), ([], []))
        self.assertEqual((r1["x"]["action"], r2["x"]["action"]), ("commitBatch", "commitBatch"))
        self.assertEqual(r1["x"]["calldata"], r2["x"]["calldata"])
        for k in ("caller", "msg.value", "block.timestamp"):
            self.assertEqual(str(r1["x"]["env"][k]).lower(), str(r2["x"]["env"][k]).lower(), k)
        self.assertIn(str(r1["x"]["env"]["caller"]).lower(), SUBMITTERS)
        self.assertIn(num(batch_input(r1["x"])["version"]), (0, 1))
        self.assertEqual(sorted([[str(h).lower() for h in r["x"]["env"]["blobhash"]] for r in (r1, r2)]), [[], [ZVH]])
        rep = self._entry(K_BATCH)
        self.assertEqual(rep["commitment"]["model"], rep["commitment"]["real"])
        self.assertEqual(rep["commitment"]["real"][0], rep["commitment"]["real"][1])
        self.assertNotEqual(rep["consumers"][0], rep["consumers"][1])

    def test_the_proof_backed_kernel_law_is_refuted_and_the_recommit_kernel_law_is_proved(self):
        """I26-P4: L_fact_kernel_Rollup_commitBatchWithProof_committedBatches_blobhash is REFUTED by two
        commitBatchWithProof calls of its fresh branch (the stored word 0) with identical calldata at version 0 or 1 and
        the blob-hash lists [] and [ZERO_VERSIONED_HASH], both succeeding (after the rollup delay, with a proof the
        binding's verifier stand-in accepts) with equal committedBatches[k]; L_fact_kernel_Rollup_commitState_
        committedBatches_blobhash is PROVED by the guard route (Rollup.sol:276 'commitState must not carry blob' fixes
        both lists to []), with a checked reachable inhabitant and law_terms within the budget 1000 (recomputed here from
        the law and proof files with spec/M3/lib/term_size.json's measure)."""
        self.assertEqual(self._status(K_PROOF), "REFUTED", self.rec[K_PROOF].get("attempts"))
        w = self.rec[K_PROOF]["witness"]
        r1, r2 = w["runs"]
        self.assertEqual(r1["prefix"], r2["prefix"])
        self.assertEqual((r1["x"]["action"], r2["x"]["action"]), ("commitBatchWithProof", "commitBatchWithProof"))
        self.assertEqual(r1["x"]["calldata"], r2["x"]["calldata"])
        self.assertEqual(sorted([[str(h).lower() for h in r["x"]["env"]["blobhash"]] for r in (r1, r2)]), [[], [ZVH]])
        self.assertIn(num(batch_input(r1["x"])["version"]), (0, 1))
        rep = self._entry(K_PROOF)
        self.assertEqual(rep["commitment"]["model"], rep["commitment"]["real"])
        self.assertEqual(rep["commitment"]["real"][0], rep["commitment"]["real"][1])
        self.assertEqual(self._status(K_STATE), "PROVED", self.rec[K_STATE].get("attempts"))
        nv = self.rec[K_STATE].get("non_vacuity") or {}
        self.assertEqual((nv.get("status"), nv.get("reachable")), ("inhabited", True), nv)
        self.assertEqual(self.rec[K_STATE]["fact"]["route"], "guard")
        check_law_terms(self, K_STATE, self.rec[K_STATE])

    def test_the_o25_attribution_law_is_refuted_by_the_chain(self):
        """I26-P5 (O25/N3): L_fact_attr_Rollup_commitState_batchBlobVersionedHashes_batchDataStore_submitter is REFUTED.
        Witness: prefix exactly [commitBatch of batch k by S1, revertBatch by the owner covering k] (S1 one of the
        binding's two active submitters), y = commitState of k by the other active submitter S2 (no blob: the pinned
        content, chooser S1), bonded S2; t = [challengeState of k by the binding's challenger, proveState of k at or after
        the challenge's startTime + proofWindow], whose real ISubmitter.slash call passes S2, not S1. The replay on the
        real Rollup passes. The record lists Hyp-ISubmitter with roles interpretation and witness (result fail, F-M2-40)
        and is not unconditional; its impact is conditional on Hyp-ISubmitter."""
        w, rep, s1 = self._attribution(A_STATE)
        self.assertEqual(w["y"]["action"], "commitState")
        self.assertEqual(list(w["y"]["env"]["blobhash"]), [])
        s2 = str(w["y"]["env"]["caller"]).lower()
        self.assertIn(s2, SUBMITTERS)
        self.assertNotEqual(s2, s1)
        self.assertEqual(kernel_key(w["y"]), num(w["k"]))
        self.assertEqual(num(w["bonded"]), num(s2))
        self.assertEqual([s["action"] for s in w["t"]], ["challengeState", "proveState"])
        self.assertEqual(str(w["t"][0]["env"]["caller"]).lower(), CHALLENGER)
        cc = rep["consumer_call"]
        self.assertEqual((cc["step"], cc["fn"]), (len(rep["trace"]) - 1, "ISubmitter.slash"))
        self.assertEqual(num(cc["argument"]), num(s2))
        last = rep["real"][-1]
        slash = [c for c in last["calls"] if c["data"].startswith("0x" + SLASH)]
        self.assertEqual(len(slash), 1)
        self.assertEqual(int(slash[0]["data"][10:], 16), int(s2, 16))
        f = self.rec[A_STATE]["fact"]
        self.assertEqual(f["hypotheses"], [dict(HYP_SUBMITTER, roles=["interpretation", "witness"])])
        self.assertIs(f["unconditional"], False)
        self.assertEqual(f["impact_conditional_on"], ["Hyp-ISubmitter"])
        self.assertEqual(f["consumer_continuation"]["steps"], 2)

    def test_the_proof_backed_recommit_attribution_is_refuted(self):
        """I26-P6 (O20 under the pin): L_fact_attr_Rollup_commitBatchWithProof_batchBlobVersionedHashes_batchDataStore_
        submitter is REFUTED. Witness: prefix exactly [commitBatch of k by S1, revertBatch by the owner], y =
        commitBatchWithProof of k taking the stored branch (no blob), bonded 0 (address(0) is recorded), chooser S1;
        t = [] (no consumer continuation within the depth: the proof-backed batch is outside its challenge window); the
        replay on the real Rollup passes with batchDataStore[k].submitter 0. Hyp-ISubmitter (interpretation, witness;
        fail) and HypV-proof1 (witness; untestable) are listed; not unconditional."""
        w, rep, s1 = self._attribution(A_PROOF)
        self.assertEqual(w["y"]["action"], "commitBatchWithProof")
        self.assertEqual(list(w["y"]["env"]["blobhash"]), [])
        self.assertEqual(num(w["bonded"]), 0)
        self.assertEqual(num(rep["bonded"]["real"]), 0)
        self.assertEqual(w["t"], [])
        self.assertIsNone(rep["consumer_call"])
        f = self.rec[A_PROOF]["fact"]
        self.assertEqual(f["hypotheses"], [dict(HYP_SUBMITTER, roles=["interpretation", "witness"]),
                                           dict(HYP_V, roles=["witness"])])
        self.assertIs(f["unconditional"], False)
        self.assertEqual(f["consumer_continuation"]["steps"], 0)

    def test_refuted_witnesses_replay_on_the_real_contract(self):
        """I26-P7 (exit: witnesses replay): replay/M3/fact/report.json has a passed entry (calls agree, model == real at
        every step) for exactly the 4 REFUTED FACT laws, its traces the records' witnesses; and every REFUTED FACT
        witness, replayed independently of holon on the real Rollup at the pinned commit (the harness copies taken at
        this prereg, the binding's deployment), gives the report's real observations at every step; kernel: both x
        succeed and the real committedBatches[k] after them are equal; attribution: every step succeeds, and the real
        batchDataStore[k].submitter after y is the bonded value and differs from the chooser."""
        refuted = sorted(lid for lid, r in self.rec.items() if r["status"] == "REFUTED")
        self.assertEqual(refuted, sorted(lid for lid, (_, st) in PREDICTED.items() if st == "REFUTED"))
        rep = need(REPLAY3)["laws"]
        self.assertEqual(sorted(rep), refuted, "replay/M3/fact/report.json has exactly the REFUTED FACT laws")
        for lid in refuted:
            e = self._entry(lid)
            if "runs" in self.rec[lid]["witness"]:
                self.assertEqual(len(e["runs"]), 2, lid)
                w = self.rec[lid]["witness"]
                for j, run in enumerate(e["runs"]):
                    self.assertEqual(run["trace"], list(w["runs"][j]["prefix"]) + [w["runs"][j]["x"]], lid)
                    self.assertEqual(run["model"], run["real"], lid)
                    self.assertEqual(run["real"][-1]["status"], "ok", lid)
                self.assertEqual(e["commitment"]["model"], e["commitment"]["real"], lid)
                self.assertEqual(num(e["commitment"]["real"][0]), num(e["commitment"]["real"][1]), lid)
                self.assertNotEqual(e["consumers"][0], e["consumers"][1], lid)
            else:
                self.assertEqual(e["model"], e["real"], lid)
        doc = X.Doc(ROOT / DOC_REL)
        traces, meta, slots = [], [], []
        for lid in refuted:
            w = self.rec[lid]["witness"]
            if "runs" in w:
                k = kernel_key(w["runs"][0]["x"])
                s = X.family_slot(doc, "committedBatches", k)
                for r in w["runs"]:
                    traces.append(list(r["prefix"]) + [r["x"]])
                meta.append((lid, "kernel", s, len(traces) - 2))
            else:
                s = X.family_slot(doc, "batchDataStore", int(w["k"]), "submitter")
                traces.append(list(w["prefix"]) + [w["y"]] + list(w["t"]))
                meta.append((lid, "attribution", s, len(traces) - 1))
            slots.append(s)
        real = X.realized(traces, sorted(set(slots)))
        for lid, kind, s, i in meta:
            if kind == "kernel":
                ws = []
                for j, run in enumerate(real[i:i + 2]):
                    self.assertEqual([obs_of(o) for o in run["steps"]], rep[lid]["runs"][j]["real"], lid)
                    self.assertEqual(run["steps"][-1]["status"], "ok", lid)
                    ws.append(run["steps"][-1]["slots"][s])
                self.assertEqual(ws[0], ws[1], lid)
                self.assertEqual([num(v) for v in rep[lid]["commitment"]["real"]], ws, lid)
            else:
                run = real[i]
                w = self.rec[lid]["witness"]
                self.assertEqual([obs_of(o) for o in run["steps"]], rep[lid]["real"], lid)
                self.assertEqual([o["status"] for o in run["steps"]], ["ok"] * len(run["steps"]), lid)
                bonded = run["steps"][len(w["prefix"])]["slots"][s]
                self.assertEqual(bonded, num(w["bonded"]), lid)
                self.assertNotEqual(bonded, num(w["chooser"]), lid)

    def test_measure_and_status_agree(self):
        """I26-P8 (Thm 6.8: F = 0 iff the factorization holds): results/M3/fact/classification.json has the five FACT
        laws; the kernel laws' bits [1, 1, 0] agree with their statuses [REFUTED, REFUTED, PROVED]; no disagreement.
        Totals over the five laws: 1 PROVED, 4 REFUTED, 0 UNKNOWN."""
        c = need(CLASSIFICATION)
        self.assertEqual(c["document"], "fact_classification")
        self.assertEqual(sorted(c["laws"]), sorted(PREDICTED))
        for lid, x in c["laws"].items():
            if PREDICTED[lid][0] == "kernel":
                self.assertEqual((x["bits"], x["kernel"], x["agree"]), (BITS[lid], PREDICTED[lid][1], True), lid)
            else:
                self.assertEqual((x["bits"], x["agree"]), (None, None), lid)
        self.assertEqual(c["disagreements"], [])
        self.assertEqual({lid: r["status"] for lid, r in self.rec.items()},
                         {lid: st for lid, (_, st) in PREDICTED.items()})

    def test_hypotheses_in_records(self):
        """I26-P9 (rule H1; a law resting on a failed hypothesis is never presented as unconditional): every FACT
        record's hypotheses are H1 applied to its premises, status and witness. In particular the L_fact_Z analogue lists
        Hyp-ISubmitter (witness: its commits ask the stand-in isActive; fail, F-M2-40), Hyp-Z0-kzg (premise; pass) and
        HypZ (interpretation; fail, F-M2-41), is not unconditional and its impact is conditional on HypZ; the
        commitBatchWithProof kernel law lists HypV-proof1 (witness: its proof is accepted by the verifier stand-in;
        untestable), Hyp-Z0-kzg (premise) and HypZ (interpretation), is not unconditional (an untestable witness
        hypothesis), impact conditional on HypZ; the PROVED commitState kernel law lists HypZ only (interpretation), is
        unconditional, impact conditional on HypZ."""
        side = sidecar()
        for lid, r in self.rec.items():
            f = r["fact"]
            self.assertEqual(f["hypotheses"], h1(lid, r, side), lid)
            listed = {h["id"]: h for h in f["hypotheses"]}
            self.assertIsInstance(f["unconditional"], bool, lid)
            self.assertEqual(f["unconditional"], not any(h["result"] != "pass" and set(h["roles"]) & {"premise", "witness"}
                                                         for h in listed.values()), lid)
            self.assertEqual(f["impact_conditional_on"], sorted(i for i, h in listed.items() if h["result"] == "fail"
                                                                and "interpretation" in h["roles"]), lid)
        f = self.rec[K_BATCH]["fact"]
        self.assertEqual(f["hypotheses"], [dict(HYP_SUBMITTER, roles=["witness"]), dict(HYP_Z0, roles=["premise"]),
                                           dict(HYP_Z, roles=["interpretation"])])
        self.assertEqual((f["unconditional"], f["impact_conditional_on"]), (False, ["HypZ"]))
        f = self.rec[K_PROOF]["fact"]
        listed = {h["id"]: h for h in f["hypotheses"]}
        self.assertEqual(listed.get("HypV-proof1"), dict(HYP_V, roles=["witness"]))
        self.assertEqual(listed.get("Hyp-Z0-kzg"), dict(HYP_Z0, roles=["premise"]))
        self.assertEqual(listed.get("HypZ"), dict(HYP_Z, roles=["interpretation"]))
        self.assertEqual((f["unconditional"], f["impact_conditional_on"]), (False, ["HypZ"]))
        f = self.rec[K_STATE]["fact"]
        self.assertEqual(f["hypotheses"], [dict(HYP_Z, roles=["interpretation"])])
        self.assertEqual((f["unconditional"], f["impact_conditional_on"]), (True, ["HypZ"]))

    def test_every_fact_law_has_a_valid_record(self):
        """I26-R4 (part): every FACT law has a record valid under v1 and v2, with its registry hash, the fact field, the
        premises of F8, a witness exactly when REFUTED, the measure of its DERIVATION entry and coverage; a PROVED law
        names its route and its term size is the sidecar measure recomputed from its files, within the budget; an
        UNKNOWN law that records a term size is over the budget."""
        self.assertEqual(sorted(self.rec), sorted(PREDICTED))
        reg = need(LAWS3 / "REGISTRY.json")["statements"]
        v1 = load_json(ROOT / "schemas" / "result_record.schema.json")
        v2 = load_json(ROOT / "spec" / "schemas" / "result_record_v2.schema.json")
        hb = hash_binders_of_sort_laws()
        der = derivation()
        for lid, r in self.rec.items():
            self.assertEqual(mini_schema.errors(r, v1), [], lid)
            self.assertEqual(mini_schema.errors(r, v2), [], lid)
            self.assertEqual(r["statement_hash"], reg.get(lid), lid)
            f = r["fact"]
            self.assertEqual((f["subform"], f["fact_id"]), (PREDICTED[lid][0], doc_basis()["laws"][lid]["fact_id"]))
            self.assertEqual(f["measure"], der[lid]["measure"], lid)
            self.assertEqual(r["premises"], premises_of(lid, hb), lid)
            self.assertEqual(r["witness"] is None, r["status"] != "REFUTED", lid)
            self.assertIn("coverage", r)
            routes = {"kernel": ("guard", "injective"), "attribution": ("provenance",)}[f["subform"]]
            if r["status"] == "PROVED":
                self.assertIn(f["route"], routes, lid)
                check_law_terms(self, lid, r)
            else:
                self.assertIsNone(f["route"], lid)
            if r["status"] == "UNKNOWN" and f["term_size"] is not None:
                self.assertGreater(f["term_size"]["law_terms"], f["term_size"]["budget"], lid)

    def test_fact_proofs_check_independently(self):
        """I26-R4 (part; AGENTS rule 6): for every FACT record, Bend run here on a copy of gen/M3 accepts the files that
        decide it (a PROVED law's proof and nonvac proof, a REFUTED law's counter-law under witness/); each imports its
        one-law LAWS.bend naming fact_<x> (fhit_<x> for nonvac); no hole, @unsafe, def f? or foreign import; the FACT
        section exists and no definition above its ghost marker names a chooser companion."""
        self.assertEqual(sorted(self.rec), sorted(PREDICTED))
        hatch = re.compile(r"\?[A-Za-z_]|@unsafe|def\s+\w+\?|import\s+\"[^\"]*\.c\"")
        sec = GEN3 / "fact" / "models" / f"{MODEL}.fact.bend"
        self.assertTrue(sec.is_file(), "the FACT section is missing")
        work = Path(tempfile.mkdtemp(prefix="holon-i26-bend-"))
        try:
            shutil.copytree(GEN3, work / "M3")
            for lid, r in self.rec.items():
                x = lid[len("L_fact_"):]
                files = [(f"laws/{lid}/LAWS.bend",
                          f"proofs/{lid}/" + ("PROOF.bend" if r["status"] == "PROVED" else "witness/PROOF.bend"),
                          f"fact_{x}")]
                if r["status"] == "PROVED":
                    files.append((f"{lid}/nonvac/LAWS.bend", f"{lid}/nonvac/PROOF.bend", f"fhit_{x}"))
                for law_rel, proof_rel, name in files:
                    law_f, proof_f = work / "M3" / law_rel, work / "M3" / proof_rel
                    self.assertTrue(law_f.is_file() and proof_f.is_file(), f"{lid}: gen/M3/{proof_rel}")
                    lt, pt = law_f.read_text(), proof_f.read_text()
                    self.assertEqual(len(re.findall(r"(?m)^law\s+\w+", lt)), 1, f"gen/M3/{law_rel}")
                    self.assertRegex(lt, r"\b" + re.escape(name) + r"\(", f"gen/M3/{law_rel}")
                    imp = os.path.relpath(law_f, proof_f.parent)
                    self.assertRegex(pt, r"(?m)^import\s+(\./)?" + re.escape(imp) + r"\s", f"gen/M3/{proof_rel}")
                    for t, rel in ((lt, law_rel), (pt, proof_rel)):
                        self.assertIsNone(hatch.search(re.sub(r"#[^\n]*", "", t)), f"gen/M3/{rel}")
                    code, out = run_bend([proof_f.name], cwd=proof_f.parent, timeout=3600)
                    self.assertEqual(code, 0, f"{lid} gen/M3/{proof_rel}: {out[-2000:]}")
                    self.assertIn("ALL PROOFS CHECK", out, f"{lid} gen/M3/{proof_rel}")
        finally:
            shutil.rmtree(work, ignore_errors=True)
        text = sec.read_text()
        marker = re.search(r"(?m)^# .*GHOST.*$", text)
        self.assertIsNotNone(marker, "the FACT section has no ghost marker")
        above = text[:marker.start()]
        self.assertNotRegex(above, r"chooser_", "a real definition names a chooser companion")


class TestBacktest(unittest.TestCase):
    """results/M3/fact/backtest.json against M1 (FB1-FB4)."""

    @classmethod
    def setUpClass(cls):
        built()
        cls.bt = need(BACKTEST)

    def test_backtest_row_and_bridges(self):
        """I26-R2 (part; the plan's regression): the analogue's implication to L_fact_Z checks. The row L_fact_Z ->
        L_fact_kernel_Rollup_commitBatch_committedBatches_blobhash: both REFUTED (same_status), the moved witness is
        move_kernel_witness of the analogue's witness, the M1 counter-law cl_l_fact_z at it is accepted by Bend
        (witness transfer) and CF(agg, S) over its blob-token lists is checked by computation (S = {[], [1]}: agg 1000
        and 1002 differ); acceptance "witness", implication "accepted", no gap, complete."""
        bt = self.bt
        self.assertEqual((bt["document"], bt["milestone"], bt["against"]), ("fact_backtest", M3, "M1"))
        self.assertEqual(bt["map"], {"path": FACT_SIDECAR, "sha256": X.sha256_file(ROOT / FACT_SIDECAR)})
        self.assertEqual([x["old"] for x in bt["rows"]], ["L_fact_Z"])
        row = bt["rows"][0]
        self.assertEqual((row["old_status"], row["old_statement_hash"], row["new"], row["new_status"],
                          row["same_status"]), ("REFUTED", M1_FACT_Z_HASH, K_BATCH, "REFUTED", True))
        rec = need(RESULTS3 / f"{K_BATCH}.json")
        mv = X.move_kernel_witness(rec["witness"], sidecar()["backtest"]["move"], OWNER)
        self.assertIsNotNone(mv, "the analogue's witness does not move to the M1 inputs")
        self.assertEqual(row["moved"], mv)
        self.assertEqual(sorted([mv["c1"]["blobs"], mv["c2"]["blobs"]]), [[], [1]])
        S = sorted({X.ck(a["blobs"]) for a in mv["p"] + [mv["c1"], mv["c2"]] if a.get("op", "").startswith("commit")})
        S = [json.loads(s) for s in S]
        self.assertEqual(row["cf_bridge"]["fn"], "agg")
        self.assertEqual(row["cf_bridge"]["set"], S)
        self.assertEqual(len({X.agg_m1(s) for s in S}), len(S))
        self.assertEqual((row["witness_transfer"]["status"], row["cf_bridge"]["status"]), ("checked", "checked"))
        self.assertEqual((row["acceptance"], row["implication"], row["gap"]), ("witness", "accepted", None))
        self.assertEqual((bt["gaps"], bt["complete"], bt["exit_blockers"]), ([], True, []))
        for d, name in (("W_L_fact_Z", "cl_l_fact_z"), ("CF_agg_L_fact_Z", None)):
            proof = GEN3 / "fact" / "backtest" / d / "PROOF.bend"
            laws = GEN3 / "fact" / "backtest" / d / "LAWS.bend"
            self.assertTrue(proof.is_file() and laws.is_file(), d)
            lt = laws.read_text()
            self.assertRegex(lt, r"(?m)^import\s+\S*M1/model/morph_rollup\.bend\s+as\s+M\s*$", d)
            if name:
                self.assertRegex(lt, r"(?m)^law\s+" + name + r"\s*:", d)
            else:
                self.assertEqual(len(re.findall(r"M\.d_blob_hash\(2n,", lt)), 2 * (len(S) * (len(S) - 1) // 2), d)
            work = Path(tempfile.mkdtemp(prefix="holon-i26-bt-"))
            try:
                shutil.copytree(ROOT / "gen", work / "gen")
                p = work / proof.relative_to(ROOT)
                code, out = run_bend([p.name], cwd=p.parent, timeout=3600)
                self.assertEqual(code, 0, f"{d}: {out[-2000:]}")
                self.assertIn("ALL PROOFS CHECK", out, d)
            finally:
                shutil.rmtree(work, ignore_errors=True)


class TestSensitivity(unittest.TestCase):
    """The rule reads the code, not the names (S1-S3; static, on variants the test builds)."""

    def test_renaming_the_document_renames_the_basis(self):
        """I26-R4 (part, S1): on a copy of the document with actions, families, the attribution member and the contract
        renamed, holon fact gives the instrument's analysis of the copy: the same basis under the new names."""
        built()
        tmp = Path(tempfile.mkdtemp(prefix="holon-i26-s1-"))
        try:
            got, exp = holon_analysis(self, rename_doc(load_json(ROOT / DOC_REL), RENAME), tmp)
            compare_analysis(self, got, exp, "renamed")
            self.assertEqual(len(exp["laws"]), 5)
            self.assertIn("L_fact_attr_ZCon_zActB_zFamB_zFamC_zMemA", exp["laws"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_without_the_pins_there_is_no_attribution_law(self):
        """I26-R4 (part, S2): with commitState's write of batchBlobVersionedHashes deleted and commitBatchWithProof's
        copy branch removed, holon fact finds no pin and no attribution law; the kernel basis and its measures are
        unchanged."""
        built()
        d = load_json(ROOT / DOC_REL)
        for a in d["actions"]:
            if a["name"] == "commitState":
                a["writes"] = [w for w in a["writes"] if w["family"] != "batchBlobVersionedHashes"]
            if a["name"] == "commitBatchWithProof":
                for w in a["writes"]:
                    if w["family"] == "batchBlobVersionedHashes" and len(w["path"]) == 1:
                        w["value"] = strip_copy(w["value"], ["map", ["storage", w["family"]], w["path"][0][1]])
        tmp = Path(tempfile.mkdtemp(prefix="holon-i26-s2-"))
        try:
            got, exp = holon_analysis(self, d, tmp)
            compare_analysis(self, got, exp, "unpinned")
            self.assertEqual((got["pins"], got["attribution"]), ([], []))
            self.assertEqual(sorted(got["laws"]), sorted([K_BATCH, K_PROOF, K_STATE]))
            for lid in (K_BATCH, K_PROOF, K_STATE):
                self.assertEqual(got["laws"][lid]["measure"]["bits"], BITS[lid], lid)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_zero_sentinel_has_no_freedom(self):
        """I26-R4 (part, S3): with the literal ZERO_VERSIONED_HASH replaced by 0 in commitBatch's and
        commitBatchWithProof's records, both kernel measures are 0 bits and neither kernel law carries hyp:Hyp-Z0-kzg."""
        built()
        d = load_json(ROOT / DOC_REL)
        z = int(ZVH, 16)
        d["actions"] = [replace_literal(a, z, 0) if a["name"] in ("commitBatch", "commitBatchWithProof") else a
                        for a in d["actions"]]
        tmp = Path(tempfile.mkdtemp(prefix="holon-i26-s3-"))
        try:
            got, exp = holon_analysis(self, d, tmp)
            compare_analysis(self, got, exp, "sentinel")
            for lid in (K_BATCH, K_PROOF):
                self.assertEqual(got["laws"][lid]["measure"]["bits"], 0.0, lid)
                self.assertNotIn("hyp:Hyp-Z0-kzg", got["laws"][lid]["premises"], lid)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestGate(unittest.TestCase):
    """The M3 gate's FACT checks on a copy (construction)."""

    def test_partial_gate_on_a_copy(self):
        """I26-R4 (part): holon gate --milestone M3 --checks G1,G6,G11V passes on a copy of the tree (G1 regenerates the
        FACT outputs, G6 binds every REFUTED FACT record to a passed replay entry, G11V covers the PROVED one)."""
        built()
        repo = copy_repo()
        try:
            rep = repo.parent / "gate_report_i26.json"
            p = run_holon(["gate", "--milestone", M3, "--root", str(repo), "--report", str(rep), "--checks",
                           "G1,G6,G11V"], cwd=repo, timeout=7200)
            self.assertTrue(rep.is_file(), f"holon gate wrote no report: {(p.stdout + p.stderr)[-3000:]}")
            r = load_json(rep)
            self.assertEqual(p.returncode, 0, json.dumps(r.get("checks"), indent=1)[-3000:])
            for g in ("G1", "G6", "G11V"):
                self.assertTrue(r["checks"][g]["passed"], (g, r["checks"][g]))
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


class TestRegressions(unittest.TestCase):
    """Outcomes already recorded that I26 must not change."""

    def test_m1_fact_record_and_differential_unchanged(self):
        """I26-R1 (part): results/M1/L_fact_Z.json stays REFUTED with its statement hash and witness (c1: commitBatch
        version 1 with no blob, c2: the same with the zero-blob token 1, after the empty trace); laws/M1 lists the
        hash; I20's differential still records L_fact_Z REFUTED on M1 and on the window view (not re-decided)."""
        r = load_json(ROOT / "results" / "M1" / "L_fact_Z.json")
        self.assertEqual((r["status"], r["statement_hash"], r["witness"]), ("REFUTED", M1_FACT_Z_HASH, M1_FACT_Z_WITNESS))
        self.assertIn(M1_FACT_Z_HASH, json.dumps(load_json(ROOT / "laws" / "M1" / "REGISTRY.json")))
        diff = load_json(ROOT / "results" / "M2" / "differential.json")["laws"]["L_fact_Z"]
        self.assertEqual((diff["m1"], diff["extracted"], diff["deltas"]), ("REFUTED", "REFUTED", []))

    def test_outcome_commits_touch_no_earlier_milestone(self):
        """I26-R1 (part): no commit that writes an I26 outcome path (spec/M3/predictions.json, key I26) changes a path
        under spec/M1/, spec/M2/facts/, spec/M2/lib/, laws/M0-M2, gen/M0-M2, results/M0-M2, replay/M1, replay/M2,
        gen/M3/sorts/ or a frozen root. Needs the real checkout's history and at least one such commit: a missing .git,
        or no outcome commit yet, is a failure, never a skip."""
        def git(*args):
            p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                               env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
            if p.returncode != 0:
                raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
            return p.stdout
        outs = load_json(ROOT / "spec" / M3 / "predictions.json")["iterations"]["I26"]["outcome_paths"]
        forbidden = ("spec/M1/", "spec/M2/facts/", "spec/M2/lib/", "laws/M0/", "laws/M1/", "laws/M2/", "gen/M0/",
                     "gen/M1/", "gen/M2/", "results/M0/", "results/M1/", "results/M2/", "replay/M1/", "replay/M2/",
                     "gen/M3/sorts/", "facts/", "predictions/", "schemas/", "tests/", "bend/probes/", "AGENTS.md",
                     "tools/freeze.py", "docs/M0_SPEC.md", "docs/BEND_PRIMER.md", "FROZEN.sha256")
        commits, cur = [], None
        for line in git("log", "--no-merges", "--format=@%H", "--name-only", "HEAD").splitlines():
            if line.startswith("@"):
                cur = (line[1:], [])
                commits.append(cur)
            elif line.strip() and cur is not None:
                cur[1].append(line.strip())
        commits = [(c, names) for c, names in commits if any(n.startswith(tuple(outs)) for n in names)]
        self.assertTrue(commits, "no commit writes an I26 outcome path")
        for c, names in commits:
            self.assertEqual([n for n in names if n.startswith(forbidden)], [], f"commit {c[:12]}")

    def test_pre_i26_m3_records_keep_their_status(self):
        """I26-R3: every M3 record that is not a FACT law keeps the status it had before I26's first outcome commit (read
        from git: the parent of the oldest commit adding results/M3/L_fact_*); those laws change only in
        rule_catalog_version. Needs the real checkout's history: a missing .git is a failure, never a skip."""
        def git(*args):
            p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                               env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
            if p.returncode != 0:
                raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
            return p.stdout
        first = git("log", "--diff-filter=A", "--format=%H", "--reverse", "--", "results/M3/L_fact_*").split()
        self.assertTrue(first, "no commit adds results/M3/L_fact_*")
        base = first[0] + "^"
        names = [n for n in git("ls-tree", "--name-only", f"{base}:results/M3").split()
                 if n.startswith("L") and n.endswith(".json") and not n.startswith("L_fact_")]
        self.assertTrue(names, "no M3 record before I26's first outcome commit")
        for n in names:
            old = json.loads(git("show", f"{base}:results/M3/{n}"))
            self.assertEqual(need(RESULTS3 / n)["status"], old["status"], n)
            ol = json.loads(git("show", f"{base}:laws/M3/{n}"))
            nl = need(LAWS3 / n)
            self.assertEqual({k: v for k, v in nl.items() if k != "rule_catalog_version"},
                             {k: v for k, v in ol.items() if k != "rule_catalog_version"}, n)


if __name__ == "__main__":
    unittest.main()
