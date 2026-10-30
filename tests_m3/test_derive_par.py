"""I24: the rules engine and PAR, all sub-forms; the first M3 laws, derived from the extracted documents (whitepaper
§5.1, §3.2, Thm 6.4 use, §10.3 steps 1-3, §8.4 PAR rows, Def 4.1-4.5, §10.1 Linking, §10.2, App. E PAR row, §11.3
sub-forms; BUILD_PLAN I24 and §2 invariant 3; docs/HUMAN_ANSWERS.md, delegated Q19). This docstring is the contract
that tests_m3/test_derive_par.py (the derivation) and tests_m3/test_par_outcomes.py (outcomes, back-test, gate) read.

Instruments fixed at the prereg: tests_m3/_i24.py (rules P0-P12 written out a second time), tests_m3/_i24x.py (rules
X0-X9 and B1-B5 written out a second time), tests_m3/fixtures/par_<subform>.facts.json (one planted holon-facts 0.1 or
0.2 fixture per sub-form), tests_m3/fixtures/par_linked/ (a planted pair of holon-facts/0.3 documents, Solidity and Go,
with its own adoption and link sidecars), and four sidecars under spec/M3/lib/: derive_extracted.json (the M3
documents), link.json (the link roles), backtest_map.json (the back-test name map, rule B1) and par_basis.json (every
Morph count, law, outcome and level this contract predicts, computed at the prereg by tests_m3/_i24x.py::par_basis_doc).

Why this contract was redrafted. A reviewed draft derived every M3 law from the hand-written fact documents
(facts/morph_header.json, spec/M1/facts/morph_rollup.json, morph_batchdata.json). That violates BUILD_PLAN §2
invariant 3 and the delegated Q19 answer: extracted facts are the input of every M3 law, and a waiver never applies
where an extracted document exists. Every Morph prediction is therefore recomputed over the extracted documents. The
rules P0-P12 and the ten fixtures carry over unchanged. What the extracted side lacked for PAR, a diagram and E1-E6
atoms over holon-facts/0.3 codec documents (docs/iterations/I20.md, Not done), is built here as the generic linked
codec layer (rules X0-X9). The machine side (a 0.3 transitions diagram, Reach, machine terms) is not built here; it is
preregistered as gap G1 below.

M3 documents (Q19)
  spec/M3/lib/derive_extracted.json (holon-derive-extracted/0.1, the format of spec/M2/lib/derive_extracted.json)
  "documents": spec/M2/facts/morph_batch.go.extracted.json (I18), morph_header.extracted.json (I17) and
  morph_rollup.extracted.json (I19/A19): the extracted counterparts of the three hand documents M0-M2 derived from.
  No file under facts/ or spec/M1/facts/ is read by holon codecs, diagram, evidence or derive for M3, and no waiver is
  requested. holon.diagram.fact_documents is unchanged and never lists an extracted document; M3's documents come
  from the adoption sidecar alone. spec/M3/lib/link.json holds I19's link roles (spec/M2/lib/link.json, byte for
  byte). The back-test alone reads the hand document facts/morph_header.json, through rule B1, because every M0 law
  is about it.

What is built here, and the gaps preregistered (nothing falls back to a hand document)
  Built (generic; rules X0-X9): linked codec components, their diagrams (holon-diagram/0.1 vocabulary), E1/E2/E6 atoms
  over them, PAR over them, a Bend model of each component, its proof and refutation, and the back-test across
  documents (rules B1-B5).
  G1  The transitions document spec/M2/facts/morph_rollup.extracted.json has no diagram in M3: there is no 0.3
      transitions adapter, no term language over the extracted machine and no Reach predicate for the extracted
      model (docs/iterations/I20.md, Not done), so a law over it could be neither stated nor decided. PAR's machine
      sub-forms (recompute, consumer, init) therefore have no Morph instance in I24; they are exercised by the 0.2
      fixtures only. The evidence set covers the document with anchors only, as I20 made it.
  G2  Codec functions of the adopted documents outside every linked component (rule X1) are listed under DERIVATION
      "uncovered" and derive no law: the batch-data, block-context, key and integer encoders of the Go document and its
      block-context height decoder. Their components wait for link roles (I38, I39).
  G3  O7 (the lastBlockNumber cycle) needs the header codec linked through HASH edges to the rollup's storage. The
      component's HASH.keccak256 edge leads to a digest carrier that no edge leaves (G1), so no rule instantiates O7.
      It is a rule gap of I25 and later; no HASH link is written by hand.
  G4  E3, E4 and E5 have no atom over a component: E3 and E4 are transition-level, and no sorts assignment covers an
      M3 document until I30 (Sorts III). The evidence set's sorts_sha256 is null for M3.
  G5  The M0 round trips name dec_go and view, which the hand document assembles (the tuple of the getters, a
      projection) and the extraction does not have; L_par_hdr_v2 names enc_go_v1, whose image carries version 1 only.
      They are back-test rule gaps (rule B5). PAR-weak instantiates at common versions only (whitepaper Def 4.5, rule
      P4); it is not widened to close L_par_hdr_v2.
  G6  Whitepaper §8.4 gives PAR-domain the proof route "case split on length and version". No such proof class is
      built here: a law over unbounded byte strings is REFUTED at a probe or UNKNOWN (rule X9), never PROVED. The
      three Morph PAR-weak laws are predicted UNKNOWN for that reason (I24-P5).
  G7  Basis sufficiency is not claimed. Whitepaper §10.3 step 1 (identify the invertible fragment, hashes under CF
      premises) is not built: rule P8 takes every TRANS, CODEC and HASH edge. Thm 6.4 (fundamental cycles are complete)
      needs a connected, domain-coherent invertible fragment; the component's decoders are partial on R^ext and it is
      not domain-coherent (O1, the REFUTED domain law), so its 4 basis elements are obligations, not a completeness
      certificate. Step 2 (domain coherence per edge) is P5 and P6. Instantiating Thm 6.4 is I42's.
  SORT enters M3 with I30, not here: M3's catalog at I24 is PAR only. The tests that read M3-wide values I30 will
  change (the catalog version M3 maps to, sorts_sha256, atoms of levels E3-E5) check I24's values while SORT is
  absent from M3's catalog and only their PAR part once it is present, so a parallel I30 build does not turn them
  red; every PAR value is checked exactly either way.

The rules registry (holon/rules/__init__.py, I15) gains catalog versions
  RULE_CATALOG_VERSION == "holon-rules/1.0" and CATALOG == {"SORT": {"site": ...}} stay what I15 made them: M2's catalog.
  CATALOGS == {"holon-rules/1.0": CATALOG, "holon-rules/1.1": {"PAR": {sub-form: producer, for the ten SUBFORMS}}}.
  catalog_version(milestone) -> "holon-rules/1.0" for M2 and every test milestone T<k>; "holon-rules/1.1" for M3.
  holon/rules/par.py: SUBFORMS == ("round_trip", "cross_component_codec", "branch", "weak", "domain_coherence",
  "totality", "cycle", "recompute", "consumer", "init") (the dedupe order of P11) and one producer per sub-form.
  derive(milestone, ...) runs every producer of the milestone's catalog; rules in sorted order, PAR's sub-forms in
  SUBFORMS order.

CLI (every file written: json.dumps(obj, indent=2, sort_keys=True) + "\\n"; deterministic, no timestamps)
  python -m holon codecs --milestone M [--root DIR] [--adoption PATH] [--link PATH] [--out DIR] [--check]
    Writes <out, default <root>/gen/<M>/codec>/<role>.json, the linked codec document of every component (rule X1)
    of the adoption and link sidecars (defaults spec/<M>/lib/derive_extracted.json and spec/<M>/lib/link.json), and
    removes a stale <role>.json. Exit 0 written; 1 (--check, nothing written) the files differ from a fresh build;
    2 refused, nothing written: a sidecar or document missing or malformed; 3 a construct rule X refuses, named,
    nothing written.
  python -m holon diagram --milestone M [--out DIR] [--root DIR]
    From M3 on: one diagram per linked codec document of gen/<M>/codec (rule X6), written to
    gen/<M>/diagram/<role>.json, and no other file; M2 and earlier: unchanged, byte for byte (I24-R4).
  python -m holon evidence --milestone M [--root DIR] [--out PATH]
    From M3 on: one model per component diagram (atoms of rule X7) and, as I20 made it, one anchors-only model per
    adopted transitions document; "sorts_sha256": null (G4). M2: unchanged, byte for byte (I24-R4).
  python -m holon derive --milestone M [--catalog VERSION] [--root DIR] [--out DIR] [--obstructions PATH]
                         [--facts PATH ...] [--codec PATH ...] [--assignment PATH] [--against DIR --diff PATH]
    As in I15. --catalog VERSION (one of CATALOGS) replaces the milestone's catalog; it is refused (exit 1), writing
    nothing, for an M<k> milestone whose catalog differs. For a catalog with PAR, derive needs each document's diagram
    and the evidence set. For M3 the documents are the linked codec documents gen/M3/codec/*.json; each, each
    gen/M3/diagram/<role>.json and gen/M3/evidence.json must be byte for byte what holon codecs, diagram and evidence
    write now, else derive refuses, exit 2, writing nothing (a stale input). For a test milestone, --facts PATH (a
    holon-facts 0.1/0.2 document) and --codec PATH (a linked codec document) name the documents, and derive builds
    their diagrams and the evidence set in memory (--assignment: the sorts of the --facts documents). Outputs as in
    I15 (one <law_id>.json per law, REGISTRY.json, DERIVATION.json; a stale L*.json removed). A catalog without SORT
    writes no obstructions file. Exit 3 when a basis element cannot be derived (named), e.g. two basis elements
    giving one law id.
  python -m holon run --milestone M3       decides every law of laws/M3 (rule X9 for component laws).
  python -m holon backtest --milestone M3 [--against M0] [--root DIR] [--out PATH]
    writes the back-test table (default results/M3/backtest.json) and the bridge and witness files under
    gen/M3/backtest/ (rules B1-B5).
  python -m holon bind --milestone M3      writes spec/bindings/M3.json (G2), as for M0-M2.

The linked codec layer (holon/diagram/linked.py: rules X1-X7; holon/gen/linked.py: rule X9; tests_m3/_i24x.py writes
each rule out again)
  X0 Scope. The layer reads the adoption sidecar, the link sidecar, the documents they name and, for E6, the I14
     lexicon spec/M2/lib/evidence_lexical.json. It names no target identifier: every name comes from those inputs.
  X1 Components. One component per link role whose "solidity" source has the reader key "edge" (an edge of a
     holon-facts/0.3 Solidity layout document, which must be a loader) and whose "go" source has "function" (the one
     entry of go.codecs.predicates whose function's last name segment is that string), both documents adopted. Other
     roles (constant and global roles compare values) form none. The linked carrier is the loader's input type (its
     Solidity member) taken as one carrier with the predicate's parameter type (its Go member). The component holds:
     every function of the Solidity document whose input or option-stripped output type is the Solidity member; every
     go.codecs.encoders entry whose function's result (index "result") has the Go member's type; every go.codecs
     patches entry of those encoders; every go.codecs.decoders and go.codecs.predicates entry whose parameter has the
     Go member's type. matches and absences are summaries of these and map to nothing. The linked codec document
     gen/<M>/codec/<role>.json: {"linked_version": "holon-linked/0.1", "component": role, "role": role, "tag_index",
     "linked_carrier", "documents": [the two paths, sorted], "inputs": [{"path", "sha256"}: the two sidecars and the two
     documents, sorted], "carriers": {id: carrier}, "functions": {name: function}}, with carriers and functions
     exactly as tests_m3/_i24x.py::component builds them (record {"kind", "document", "type", "fields": [{"name",
     "width"}]}; bytes {"kind", "members": [{"document", "type"}], "domains"}; slot {"kind", "of", "offset", "width"};
     function {"kind", "document", "source", "lang", "from", "to", "partial", "versions"} plus, by kind, encoder
     {"layouts": {"<v>" or "*": cells}, "domain" or "ok", Solidity also "sink", a patch "patch_of"}, decoder {"read",
     "param", "ok"}, predicate {"param", "ok"}, loader {"ok", "sink"}). A construct outside every component is listed
     under DERIVATION "uncovered" (G1, G2): {"document", "function": the code's id or null for a whole transitions
     document, "reason": "transitions" | "outside"}, sorted by (document, function).
  X2 Names. A Go function "(pkg.T).M" or "(*pkg.T).M" is named "T_M", "pkg.F" is "F" (T and F the text after the last
     "."); a Go type is its text without "*" and package path. Solidity functions and types keep their document names.
     The linked carrier takes its Solidity member's name; a decoder's target is the slot carrier "<linked>@<offset>+
     <width>"; a hash sink's target is the digest carrier named by its op. The domain predicate of a loader L is
     "ok_<L>"; a Go predicate is its own domain predicate. A name that is not an identifier, two functions of one
     name, or one carrier id for two carriers is refused (exit 3).
  X3 Layouts and records. A Solidity ok path's store sequence applied in order to dirty memory (later writes
     override earlier ones; an op's cells from its src items: a field's bytes from..from+len-1, zeros, constants), its
     first "length" cells, an unwritten cell ["unknown"]. A Go encoder's cells as extracted, ["byte", <field path of
     its one parameter>, k] read as ["field", "<path joined by '.'>", k]; a cell of any other term, an encoder of more
     than one parameter, or a second layout of one function, is refused. A Go record's fields are the field cells of
     its encoders' layouts in order of first appearance, width 1 + the largest byte index (every smaller index
     occurring). A patch's layout is its encoder's with each write's cell replaced by the constant written.
  X4 Versions. The tag index is the component predicate's tag_index. An encoder's versions: a Go layout whose tag cell
     is the constant v has {v}; a Solidity ok path whose tag cell is byte 0 of a one-byte record field F has the
     values v in 0..255 at which no atom of its condition that mentions only F is false. Two ok paths giving one
     version two layouts are refused. A decoder's, predicate's or loader's versions: the values of the tag byte at
     which some ok path's condition has no false atom among those that mention only that byte; null (unversioned)
     when no ok path's condition mentions the tag byte.
  X5 Values. An encoder's value at version v is its layout at v; the other atoms of its ok conditions (a Solidity
     input check, the Go cache condition len(EncodedBytes) <= 0) are its domain, recorded and not modelled
     (assumption A-codec-domain: PAR compares layouts; a cache path that returns a stored value is OWN's, I35). A
     decoder's value is Some(the read bytes) when an ok path's condition holds on the input's length and tag byte,
     else None; a predicate's and a loader domain predicate's value is whether one does.
  X6 Diagram (gen/<M>/diagram/<role>.json, holon-diagram/0.1 keys): carriers (records with "product", the linked
     carrier with "interface": true iff it has domains, "domains", "key_space": "byte"; slots; digests "cls":
     "digest"); edges CODEC.<name> for every function but predicates ("src", "tgt", "partial", "version": the version
     label, "model_fn": name, "fn_kind", "source": [{"fn": the code's id}], a loader's "domain": "ok_<name>") and one
     HASH.<op> edge per (sink op, source carrier) of the Solidity functions' selected sinks.
  X7 Evidence (I14's levels, I14's via shapes, atoms of the component's model). E1 by position (§10.2): a decoder's
     read (offset, width) recovers field F from a layout iff its cells are ["field", F, 0..width-1] in order; inverse
     atom (encoder e, decoder d, version v in both labels or d unversioned) {"kind": "inverse", "version": v,
     "fields": [F], "not_recovered": []} when d recovers a field; common_decoder atom (encoders p < q with one target,
     version v common to both labels, decoder d recovering F_p from p and F_q from q) {"kind": "common_decoder",
     "version": v, "decoder": d, "fields": [F_p, F_q]}. E2: an encoder writes the non-unknown cells of its layouts, a
     decoder reads its range: {"carrier", "writes", "reads"} over the overlap, as ranges. E6: I14's rule and lexicon
     over parallel CODEC edges, their "source" ids as names. No E3, E4 or E5 atom (G4).
  X8 PAR over a component: rules P1-P12 over its diagram and atoms, with two adaptations for single-read decoders
     (P1, P2) and one for the linked carrier's versions (X8c).
     P1: one law per inverse atom, the projection the field F it recovers (Def 4.1: field projections are the product
     structure): claim [d(e(h)), Some(F(h))], i.e. {"some": {"field": F, "of": {"var": "h"}}}; no pinned law (an
     atom has no unrecovered getter). P2: one basis element per (p, q, version) with common_decoder atoms, key
     {"p", "q"}: binders h over p's source and k over q's (one h when they are one carrier); premises: the version
     premise of each binder whose record has a field named version (P0), then one correspondence premise
     {"eq": [{"field": F_p, "of": h}, {"field": F_q, "of": k}]} per distinct pair of the group's atoms (in decoder id
     order), then (pinned law) P2's pins on either binder's fields; claim [p(h), q(k)]. P3-P6 and P8 as written but
     for X8c; P7, P9 and P10 have no instance over a component (no TRANS or CONS edge).
     X8c (version labels scope byte-string laws too). P0 gives a versioned instance (P3, P4, P8) a version premise
     only over a record with a field named version; over the linked carrier, a byte string whose version is its tag
     byte, an unversioned law would compare the two edges at versions outside their labels, which no rule licenses
     (the lead decision on PAR-weak: common versions only, never widened). So a versioned instance whose source is
     the linked carrier gives one law per common version v, id suffix _v<v>, with the tag premise
       {"eq": [{"call": T, "args": [{"var": "b"}]}, {"some": {"bytes": "0x<v as one byte>"}}]}
     where T, the tag decoder, is the component's one decoder of version label null whose read is (tag_index, 1)
     (Morph: BatchHeaderBytes_Version). With no such decoder, or more than one, the basis element records reason
     no_version_premise and gives no law (a version scope is never dropped). An empty intersection stays
     no_common_version. P5 (domain coherence) is unversioned by definition (whitepaper §5.1: equal domains on R^ext)
     and gets no tag premise. law_evidence reads the tag premise as the version premise (L4).
  X9 Deciding component laws (holon run): the component model gen/<M>/model/<role>.bend (one record type per record
     carrier, one U32 per byte in field order; byte strings List<&2, U32>; encoders per rule X5, an unwritten cell and
     a version without a layout the sentinel 57005 as in M0; decoders Maybe; predicates Bool). Premises by pinning,
     correspondence premises by pinning k's corresponding fields to h's; proofs by opening the records and {==}
     (M0's class); refutation by a Bend-checked counter-law at a concrete witness. Byte-string laws (P4, P5 and P8
     over the linked carrier) are refuted only at probes: lengths and tag bytes from every integer constant k of the
     two sides' ok conditions (k - 1, k, k + 1, and 0), first difference by (length, tag); under a tag premise of
     version v, only the probes of tag byte v and length >= 1; a law no probe refutes is UNKNOWN, its record's
     "bound" naming the probes tried. There is no proof route for a byte-string law (gap G6). A counter-witness of a
     law that names an encoder satisfies every atom of that encoder's ok condition (at the witness's version) that
     mentions only record fields, so the real code reaches its store there (for enc_sol: prevStateHash and
     postStateHash nonzero). Witnesses: {"h": {field: "0x.."}, "k": {...}} and
     {"b": "0x.."}. Records as for codec laws; non_vacuity for every PROVED law with premises.

PAR rules (holon/rules/par.py; tests_m3/_i24.py writes each one out again)
  P0 Conventions. A law is holon-ir/0.3: {"ir_version": "holon-ir/0.3", "law_id", "milestone", "rule": "PAR",
     "subform", "rule_catalog_version", "facts": the document (repo-relative), "facts_sha256": its sha256, "notes",
     "statement": {"binders", "assume", "claim", "scope": {"kind": "unbounded"}}}; no "evidence", no "predicted", no
     "maps_to" key (the obligation comes from the rule; its provenance is DERIVATION.json; GEVID reads a missing
     "evidence" key as the empty set). <name> in an id is the facts name (function, predicate, action, def, consumer,
     state field) of the diagram element (its model_fn); law ids match ^L[0-9]?_[A-Za-z0-9_]+$ and are a
     deterministic function of (rule, sub-form, basis element).
     Reflexive candidates: a candidate whose claim's two sides are equal as canonical JSON (e.g. P9 when p stores the
     very call q recomputes) holds by reflexivity (Lemma 6.2) and states nothing; it is not emitted, and a basis element
     that gives no law and no duplicate for that reason alone records reason reflexive.
     Versions: an edge's diagram "version" label read as integers ("a..b" a range, "a,b" a list, "a" one; null:
     unlabelled). The common versions of a set of edges: the intersection of the labels of those that carry one;
     unversioned when none carries one; an empty intersection gives no law (reason no_common_version). A versioned
     instance gives one law per common version v when the source carrier is a record with a field named version (its
     premise: version = v, the field's width in bytes), else one unversioned law (over a component's linked
     carrier: rule X8c).
     Codec terms (holon-facts/0.1 documents and linked codec documents), added to holon-ir/0.3 additively: the
     holon-ir/0.1 terms {"call": fn, "args": [t]}, {"field": f, "of": t}, {"bytes": "0x.."} (lower-case hex),
     {"some": t}, with {"var": x} and {"bool": b}. The binder of a codec law is {"q": "forall", "name": "h", "type":
     <record base type>} for a record carrier, "b" for a byte-string carrier (type its base type, e.g. "Bytes"). A pin
     is the premise {"eq": [{"field": F, "of": {"var": "h"}}, {"bytes": c}]}; the version premise first, then pins in
     the record's field order. A facts-0.1 decoder is option-valued in the model (holon.facts.KIND_TYPES), whatever its
     declared codomain.
     The expr term (holon-facts/0.2 documents), added to holon-ir/0.3 additively:
       {"expr": E, "from": S [, "action": A, "on": T] [, "bind": {name: term}]}
     the value of the facts expression E evaluated in state S, with the inputs of action A taken from the action T
     (when T is an A; the default value of E's type otherwise), and the names in "bind" bound to those IR terms (they
     shadow inputs). E is written with the action's lets substituted (holon.diagram.access.subst, in guard order: call,
     field, type and key positions are not variables), so it names state fields, inputs, bound names, facts params,
     defs and builtins only. Both sides of a claim have E's facts type. Machine laws (P7, P9, P10) bind
     {"q": "forall", "name": "s", "type": "Reach"} and {"q": "forall", "name": "a", "type": "Act"} (P9, P10 only), then
     one {"q": "forall", "name": p, "type": "Fn<A,B>"} per oracle parameter the document's model threads
     (holon.gen.machine.Machine.threaded, sidecar order), and P9/P10 assume, in this order,
     {"eq": [{"fn": "is_<A>", "args": [{"var": "a"}]}, {"bool": true}]} and
     {"eq": [{"fn": "last_ok", "args": [{"step": {"var": "a"}, "from": {"var": "s"}}]}, {"bool": true}]}.
  P1 round trip (round_trip, id L_par_rt_<e>_<d>_v<v>[_pinned]). Basis: every E1 atom of via kind "inverse"
     (encoder e = p, decoder d = q, version v, not_recovered N). Needs a projection pi of e's source carrier whose
     "to" is d's target (diagram carrier "projections"; else reason no_projection). Full law: version premise; claim
     [d(e(h)), Some(pi(h))]. Pinned law: also a pin for each getter g in N whose positions g.offset..g.offset+width-1
     in holon.layout.layout(facts, e, v) are all constants (the pin's bytes are those constants); a pin on version
     equal to the version premise is that premise; a different one is reason contradictory_pin and no pinned law.
     The pinned law exists only when it has a premise the full law lacks. (Over a component: rule X8.)
  P2 cross-component codec agreement (cross_component_codec, L_par_cc_<p>_<q>_v<v>[_pinned]). Basis: every E1 atom of
     via kind "common_decoder" (p < q, version v). Full law: version premise; claim [p(h), q(h)]. Pinned law: also, for
     each record field F written whole by one encoder's layout at version v (["field", F, k] for every k < width) at
     positions where the other layout holds constants and which the other layout never writes, the pin F = those
     constants (version as in P1). Exists only when it adds a premise. (Over a component: rule X8.)
  P3 branch agreement (branch, L_par_br_<p>_<q>[_v<v>]). Basis: every pair p < q of parallel CODEC edges (same source
     and target carriers) whose diagram "source" citations are equal and non-empty: two paths of one function.
     Versioned instance (P0) of the claim [p(h), q(h)].
  P4 PAR-weak (weak, L_par_weak_<p>_<q>[_v<v>]). Basis: every E6 atom. Between endpoints that are not CODEC or CONS
     edges (TRANS, MIG, observers): reason relation (a TRANS edge is a relation, Def 4.2: two actions are not parallel
     paths of a function). A branch pair: reason branch_pair. Otherwise, per common version (P0), unless an atom of
     level E1-E5 relates p and q (either order) with no version or that version (reason stronger_evidence): the claim
     [p(h), q(h)]. Its records carry the evidence triage of I14 (an E6-only law that is REFUTED is an intent
     question: whitepaper Def 4.5, O10).
  P5 domain coherence (domain_coherence, L_par_dom_<p1>_<p2>). Basis: every pair p1 < p2 (by name) of domain
     predicates of an interface carrier ("interface": true, "domains"). Law: binder over the carrier, no premise,
     claim [p1(b), p2(b)].
  P6 totality (totality, L_par_tot_<e>). Basis: every CODEC or CONS edge whose source carrier is an interface carrier
     (R^ext). A partial edge (option codomain): reason explicit_option. A CONS edge of a holon-facts/0.2 document:
     reason total_by_construction (the generated consumer function is total on Act). A CODEC edge with a domain
     predicate g: the law [g(b), true], no premise (the edge is defined on all of R^ext). Otherwise reason
     no_domain_predicate.
  P7 initialization coherence (init, L_par_init_<a>_g<i>). Basis: every E3 atom (action a, "guards[<i>].require",
     operands [L, R]). With a's lets substituted, an operand that mentions an input of a gives reason mentions_input
     (not an equation over states); else the closed law [{"expr": L, "from": {"s0": {}}}, {"expr": R, "from":
     {"s0": {}}}] (no premise; binders: the oracle parameters only).
  P8 cycles (cycle, L_par_cy_<e>[_v<v>]). Per diagram, the multigraph of its TRANS, CODEC and HASH edges over every
     carrier. Spanning forest: carriers in sorted id order; a root is the smallest unvisited carrier; BFS; a dequeued
     carrier examines its incident edges (either direction, a self-loop once) in sorted edge-id order; an edge reaching
     an unvisited carrier enters the tree; every other edge, when first examined, is a non-tree edge (self-loops
     included). The basis is the non-tree edges; their number is |E| - |V| + kappa (kappa: the number of roots).
     The fundamental cycle of non-tree edge e (u -> w) is e followed by the tree path from w back to u. A cycle with a
     TRANS edge: reason relation; with a HASH edge: reason hash_edge (CF premises arrive with I25). A codec cycle states
     an equation iff, as a closed walk, it has exactly one source and one sink (else not_a_parallel_pair): the two
     walks P (the one through e) and Q from source to sink, each the composition of its edges' functions; a partial
     edge before a walk's last: partial_inner; one walk ending partial and the other not: type_mismatch. Law: binder
     over the source carrier, claim [P(x), Q(x)], versioned instance (P0) over the cycle's edges.
  P9 recomputation (recompute, L_par_rc_<p>_<q>_<f>_<field>[_<n>]). Basis: every E4 atom (p stores f, q recomputes
     f) and each field of its "stored" positions. Stored values: in p's effect on the field (lets substituted), each
     qualifying call k of f (I14's E4: a facts def or library builtin, >= 1 argument, none mentioning a state field, one
     at least an input); descend from the effect through record literals ["mk", T, {..}] and through calls whose
     holon.diagram.access role builds a container (snoc, set_at, concat) into the parts that contain k; the first
     other node that contains k is a stored value V (distinct by canonical JSON, sorted). Recomputations: the
     qualifying calls C of f at q's "recomputed" positions (q's lets substituted; distinct, sorted). For each pair
     (V, C) (n numbers them, in that order, when there is more than one): an input C mentions that is not an input
     of p with the same type gives reason inputs_differ; else the law with claim
     [{"expr": V, "action": p, "on": a, "from": s}, {"expr": C, "action": p, "on": a, "from": s}] (P0 machine binders
     and premises): what p stores is what q recomputes from the same inputs. When V is C itself the candidate is
     reflexive (P0) and gives no law.
  P10 consumer agreement (consumer, L_par_cs_<c>_<p>_<f>_<field>[_<n>]). Basis: every CONS edge c (facts consumer c
     with "input" i) and every action p that has an input i. For each effect field of p (lets substituted), each
     qualifying call k (as in P9, any f) whose arguments mention i, and each stored value V of k (P9's descent): the
     law [{"expr": V, "action": p, "on": a, "from": s}, {"expr": k, "action": p, "on": a, "from": s, "bind": {i:
     {"fn": c, "args": [{"var": "a"}]}}}]: the commitment p stores agrees with the commitment function applied to
     what the consumer receives. An action p with the input whose effects hold no such call: reason no_commitment.
  P11 Alpha-equivalence, dedupe and links. The alpha-normal form of a statement (tests_m3/_i24.py::canonical):
     binders renamed x0, x1, .. in binder order (holon-ir/0.1 "forall" binders are universal), premises as a sorted
     set, each eq/neq with its two sides sorted by canonical JSON, a conjunction as a sorted set, the scope (unbounded
     when absent); two laws are alpha-equivalent iff they are about the same facts file and their normal forms are
     equal (Lemma 6.2: equations are symmetric). Dedupe: a law whose statement is alpha-equivalent to one an earlier
     basis element (SUBFORMS order, then the order each producer lists) already gave is not emitted; the basis element
     records {candidate id: kept id} under "duplicates". Links: for every derived law and every law of an earlier
     milestone (laws/M<j>, j < k; for a test milestone every laws/M<j> that exists) alpha-equivalent to it,
     DERIVATION.json "links" holds {"old", "old_milestone", "new", "new_milestone", "basis": "alpha-equivalent",
     "binder_map": {new binder: old binder}} (I10, F-M2-23), sorted by (old_milestone, old). Pairs come from this
     rule, never from ids or by hand. For M3 no earlier law is about a linked codec document, so "links" is [] and
     laws/STATEMENT_DIFF.jsonl gains no line; the back-test across documents is rules B1-B5.
  P12 DERIVATION.json and REGISTRY.json (laws/M3/). DERIVATION: the I15 keys ("document", "derive_version",
     "milestone": "M3", "rule_catalog_version": "holon-rules/1.1", "sorts_sha256": null, "inputs": every file read,
     "laws", "links"), plus "evidence_sha256" (the set built), "cycle_rank": {model: {"E", "V", "kappa", "rank",
     "tree", "non_tree"}} for every document, "par_basis": [{"subform", "model", "key", "version", "laws",
     "duplicates", "reason"}] with one entry per basis element and version (tests_m3/_i24.py::expected and
     tests_m3/_i24x.py::expected write them), sorted by (SUBFORMS order, canonical JSON of key, version with null
     first), and "uncovered" (rule X1). key: round_trip, weak, init {"atom": id}; cross_component_codec {"atom": id}
     ({"p", "q"} over a component); branch {"p", "q"}; domain_coherence {"carrier", "p", "q"}; totality and cycle
     {"edge"}; recompute {"atom", "field"}; consumer {"consumer", "action", "field"}. reason is one of the reasons
     above, or null when the element gave a law or a duplicate. "laws" entries: {"law_id", "rule": "PAR", "subform",
     "facts", "basis": {"subform", "model", "key", "version"}, "entry_points": [the action a P9/P10 law steps, else
     []], "statement_hash"} sorted by law_id. REGISTRY: as I15 (statements, facts_files, derivation_sha256) with
     "ir_version": "holon-ir/0.3", "rule_catalog_version": "holon-rules/1.1", "sorts_sha256": null and
     "evidence_sha256" = gen/M3/evidence.json's.

Statement hashes (holon.gen.refs, additive): a codec term over a holon-facts/0.1 document refs each function it names
  by the content of its facts entry, transitively (a decoder's guard predicate, the record type), human text removed
  ("meaning", "notes", "source", "preconditions", and the "code" of every op, getter and rule): editing a function a
  law names restales the law; editing another function, or only text, does not. A codec term over a linked codec
  document refs each function it names (a domain predicate ok_<L>: the loader L) by its entry without "document" and
  "source", and the record carriers of its binders: editing a layout cell restales exactly the laws naming that
  function; editing a "source" id restales none. An expr term refs the closure of the defs, builtins, params and
  oracle parameters E names, the state signature and, with an action, the action signature.

Deciding the laws (python -m holon run --milestone M3, and any test milestone)
  Codec laws (holon-facts/0.1 documents) with the M0 machinery: the model of holon.gen.model, emission as
  holon.gen.laws does (premises by pinning; {"bool": b} is True{}/False{} of type Bool), the proof generators of
  holon.gen.proofs, refutation by holon.refute.search with a Bend-checked counter-law. Component laws per rule X9.
  Machine laws with holon.mpipeline: proofs from the existing classes plus one generated class for expr claims (open
  the Act binder by its constructors and the Reach binder's state record, then {==} in every case), the closed P7
  laws by evaluation; refutation by the compiled-model explorer: Reach ranges over the BFS prefixes (prefixDepth,
  maxPrefixes from the document's "search", else 3 and 3000), Act over the search policy's actions of the law's
  action plus, for each of them, I15's S1 boundary variants of every Nat input (v - 1 when v >= 1, v + 1, 0) and,
  new in I24, the empty list for every List<Nat> input (§8.7: sort boundary values); a closed false law gets a closed
  counter-law. A REFUTED law is REFUTED only through a counter-law Bend accepts. Records: results/<M>/<law_id>.json
  valid under v1 and v2 (I1, I14: evidence_levels, evidence_triage), with non_vacuity for every PROVED law with
  premises (an inhabitant of its premises, G11V). holon.diagram.evidence.law_evidence reads the codec terms of a
  holon-ir/0.3 law over a holon-facts/0.1 document or a linked codec document as it reads holon-ir/0.1 (L2: call ->
  codec anchors and domains; L4: the version premise). Witnesses (the I12/I15 record formats): a codec law's
  {binder: {field: "0x.."}} or {binder: "0x.."}; a machine law's {"s": {"run": [action, ..]}, "a": action,
  <oracle parameter>: table}, an action being {"op", <input>: value}.

Back-test across documents (whitepaper §9.4, L22; BUILD_PLAN I10, I24 exit; rules B1-B5, tests_m3/_i24x.py)
  B1 The name map mu: spec/M3/lib/backtest_map.json, fixed at the prereg (its doc field shows the computation:
     tests_m3/_i24x.py::backtest_map_doc). holon backtest reads it and never recomputes it; the derivation never
     reads it.
  B2 Pairing. An M3 law S and an M0 law O are paired iff every binder type, function and field of S has a preimage
     under mu, and the collapse of S is alpha-equivalent (P11's normal form, the facts file aside) to O. The collapse
     renames S into the hand names, then merges two binders of one hand type wherever every premise relating them
     equates one hand field of each (dropping those premises). Pairs come from this rule, never from ids or by hand.
  B3 Bridges. For a paired row and every function g the M0 law names, the bridge B_<old>_<g>: under the M0 law's
     binders and premises, the hand function g (the M0 model gen/M0/model/<hand stem>.bend) equals mu(g) (the
     component model) applied to the hand value moved into the image's carrier by mu. Its LAWS.bend (importing both
     models) and PROOF.bend, a proof or a counter-law, go to gen/M3/backtest/B_<old>_<g>/. An encoder bridge (records,
     one version) is decided by evaluation (open, {==}); a bridge over unbounded byte strings is REFUTED only at a
     probe (rule X9), else UNKNOWN.
  B4 Acceptance. A paired row is accepted "bridges" when every bridge is PROVED (then the M0 statement is the M3
     statement instantiated at the moved hand value, with the functions equal: S_new => S_old), or "witness" when both
     laws are REFUTED and the M3 counter-witness, moved by mu, refutes the M0 law on the hand model by a Bend-checked
     counter-law (gen/M3/backtest/W_<old>/LAWS.bend and PROOF.bend): M3 still finds M0's obstruction. Otherwise its
     implication is missing.
  B5 Table: results/M3/backtest.json
    {"document": "backtest", "milestone": "M3", "against": "M0", "map": {"path", "sha256"},
     "rows": [{"old", "old_status", "new": the paired M3 law or null, "new_status", "same_status": bool | null,
               "bridges": [{"fn", "image", "law", "status"}], "acceptance": "bridges" | "witness" | null,
               "implication": "accepted" | "missing" | null, "gap": gap id | null}] sorted by old,
     "gaps": [{"id": "gap:M0:<law>", "law", "milestone": "M0", "kind": "rule" | "implication", "status": "open",
               "reason": non-empty text, "candidates": [M3 laws]}] sorted by id,
     "complete": true iff every row is accepted or has an open gap,
     "exit_blockers": the sorted ids of the open gaps}
    A row without a paired law is a rule gap (a missed M0 law; it is never added by hand). Its candidates: the M3
    laws of the M0 law's sub-form that name the image of every M0 function that has one, those at the M0 law's
    version (L4) when there are any, sorted. A paired row whose implication is missing is a gap of kind
    "implication". M3 exit cannot be claimed while exit_blockers is non-empty (BUILD_PLAN I24 exit); I45 owns rule
    admission and closing gaps.

Gate (not the full M3 gate: G6 replay of the new witnesses, G7, G4 canaries over PAR laws and G1 are later work)
  python -m holon gate --milestone M3 --checks G2,G3,G5,G9,G11,GEVID passes on a copy of the tree: the registry and
  bindings (G2; no back-test link, no log line), no escape hatch and valid binder types (G3, codec binders name the
  types of the law's facts), proofs re-check (G5), records valid (G9), law files and imports (G11), the evidence set
  (GEVID, its sorts_sha256 null from M3 on when gen/<M>/sorts/assignment.json does not exist).

Rules
  - AGENTS.md is binding: never edit facts/, spec/M1/facts/, spec/M2/facts/, laws/M0/, laws/M1/, laws/M2/; derive
    never copies an earlier law; a missed M0 law is a rule gap; nothing is hand-linked.
  - holon/rules/par.py, holon/diagram/linked.py and holon/gen/linked.py name no target identifier and no fixture
    identifier (no special-casing; tests below).
  - Fixtures are test instruments under tests_m3/fixtures/, never M3 documents (no sidecar of spec/ lists them).
  - No skips. Predictions are never tuned; a miss is a Surprise.
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m3 import _i24 as I
from tests_m3 import _i24x as X
from tests_m3._m3 import (ROOT, SCHEMAS, canonical_json, copy_repo, file_sha256, holon_module, laws,
                          load_json, run_holon, validate, write_json)

SIDECAR = ROOT / "spec" / "M3" / "lib" / "par_basis.json"
MAP = ROOT / "spec" / "M3" / "lib" / "backtest_map.json"
LAWS3 = ROOT / "laws" / "M3"
GEN3 = ROOT / "gen" / "M3"
IR03 = SCHEMAS / "law_ir_0_3.schema.json"
LAW_FILE = re.compile(r"^L[0-9]?_[A-Za-z0-9_]+\.json$")
COMPONENT = "header_length"
CODEC_DOC = f"gen/M3/codec/{COMPONENT}.json"
EXTRACTED = ("spec/M2/facts/morph_batch.go.extracted.json", "spec/M2/facts/morph_header.extracted.json",
             "spec/M2/facts/morph_rollup.extracted.json")
FIXTURES = {s: f"tests_m3/fixtures/par_{s}.facts.json" for s in
            ("round_trip", "cross_component", "branch", "weak", "domain", "totality", "cycle", "recompute",
             "consumer", "init")}
LINKED_FX = {"adoption": "tests_m3/fixtures/par_linked/derive_extracted.json",
             "link": "tests_m3/fixtures/par_linked/link.json", "role": "hdr_len"}

# the facts fixtures' complete law sets (construction: what P1-P11 give on each planted document)
FIXTURE_LAWS = {
    "round_trip": ["L_par_rt_enc_rt_sol_dec_rt_v0", "L_par_rt_enc_rt_sol_dec_rt_v0_pinned"],
    "cross_component": ["L_par_cc_enc_cc_go_enc_cc_sol_v0", "L_par_cc_enc_cc_go_enc_cc_sol_v0_pinned",
                        "L_par_rt_enc_cc_go_dec_cc_v0", "L_par_rt_enc_cc_sol_dec_cc_v0",
                        "L_par_rt_enc_cc_sol_dec_cc_v0_pinned"],
    "branch": ["L_par_br_enc_br_fast_enc_br_slow_v1"],
    "weak": ["L_par_weak_enc_wk_go_enc_wk_sol_v0"],
    "domain": ["L_par_dom_ok_dm_go_ok_dm_sol"],
    "totality": ["L_par_tot_dec_tt"],
    "cycle": ["L_par_cy_dec_cy_sol"],
    "recompute": ["L_par_rc_reput_put_enc_held"],
    "consumer": ["L_par_cs_feed_post_dig_com1", "L_par_cs_feed_post_dig_com2"],
    "init": ["L_par_init_pop_g0", "L_par_init_sync_g0"],
}
FIXTURE_SUBFORM = {"round_trip": "round_trip", "cross_component": "cross_component_codec", "branch": "branch",
                   "weak": "weak", "domain": "domain_coherence", "totality": "totality", "cycle": "cycle",
                   "recompute": "recompute", "consumer": "consumer", "init": "init"}
# the linked fixture's complete law set (construction: what rules X1-X8 give on tests_m3/fixtures/par_linked/)
LINKED_LAWS = {
    "round_trip": sorted(
        [f"L_par_rt_enc_x_HdrBytes_{g}_v{v}" for v, gs in ((0, "A B Version"), (1, "A B D Version"),
                                                           (2, "A B D Version")) for g in gs.split()]
        + [f"L_par_rt_RecV0_Bytes_HdrBytes_{g}_v0" for g in ("A", "B", "Root")]
        + [f"L_par_rt_RecV1_Bytes_HdrBytes_{g}_v1" for g in ("A", "B", "D")]
        + [f"L_par_rt_Cache_makeV2_HdrBytes_{g}_v2" for g in ("A", "B", "D")]),
    "cross_component_codec": ["L_par_cc_Cache_makeV2_enc_x_v2", "L_par_cc_Cache_makeV2_enc_x_v2_pinned",
                              "L_par_cc_RecV0_Bytes_enc_x_v0", "L_par_cc_RecV0_Bytes_enc_x_v0_pinned",
                              "L_par_cc_RecV1_Bytes_enc_x_v1", "L_par_cc_RecV1_Bytes_enc_x_v1_pinned"],
    "weak": ["L_par_weak_HdrBytes_Root_HdrBytes_RootNew_v2"],
    "domain_coherence": ["L_par_dom_HdrBytes_validate_ok_load_x"],
}


class Derive:
    """One `python -m holon derive ...` run into a scratch directory, and what it wrote."""

    def __init__(self, args: list[str], cwd: Path = ROOT):
        self.tmp = Path(tempfile.mkdtemp(prefix="holon-derive-par-"))
        self.laws = self.tmp / "laws"
        self.obs = self.tmp / "obstructions.json"
        p = run_holon(["derive", *args, "--out", str(self.laws), "--obstructions", str(self.obs)], cwd=cwd)
        self.code = p.returncode
        self.log = f"exit {p.returncode}\n--- stdout\n{p.stdout[-3000:]}\n--- stderr\n{p.stderr[-3000:]}"

    def files(self) -> dict[str, bytes]:
        out = {f.name: f.read_bytes() for f in sorted(self.laws.glob("*")) if f.is_file()} if self.laws.is_dir() else {}
        if self.obs.exists():
            out["<obstructions>"] = self.obs.read_bytes()
        return out

    def doc(self, name: str) -> dict:
        p = self.laws / f"{name}.json"
        if not p.exists():
            raise AssertionError(f"holon derive wrote no {p.name}\n{self.log}")
        return load_json(p)

    def law_docs(self) -> dict[str, dict]:
        return {p.stem: load_json(p) for p in sorted(self.laws.glob("*.json")) if LAW_FILE.match(p.name)}

    def cleanup(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


def m3_catalog() -> tuple[str, bool]:
    """The catalog version M3 maps to, and whether SORT is in it. At I24 it is holon-rules/1.1, PAR only; I30 adds SORT
    to M3 under a later catalog version that keeps holon-rules/1.1's PAR (test_catalogs checks both cases), so the
    M3-wide values SORT changes (catalog version, sorts_sha256) are checked against this, never skipped."""
    rules = holon_module("holon.rules")
    cv = rules.catalog_version("M3")
    return cv, "SORT" in rules.CATALOGS[cv]


def morph_component() -> tuple[dict, dict, list, dict]:
    """The Morph component as tests_m3/_i24x.py builds it from the committed inputs: (component, diagram, atoms,
    expected derivation)."""
    comp = X.components()[0]
    diag = X.diagram(comp)
    ats = X.atoms(comp, diag)
    return comp, diag, ats, X.expected(comp, diag, ats)


def linked_fixture(root: Path = ROOT, milestone: str = "T24") -> tuple[dict, dict, list, dict]:
    comp = X.components(root, LINKED_FX["adoption"], LINKED_FX["link"])[0]
    diag = X.diagram(comp)
    ats = X.atoms(comp, diag)
    return comp, diag, ats, X.expected(comp, diag, ats, milestone)


def fixture_assignment(tmp: Path, rels: list[str], cwd: Path = ROOT) -> Path:
    args = ["sorts"]
    for r in rels:
        args += ["--facts", r]
    p = run_holon(args + ["--out", str(tmp / "sorts")], cwd=cwd)
    if p.returncode != 0:
        raise AssertionError(f"holon sorts failed on the fixtures\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}")
    return tmp / "sorts" / "assignment.json"


def fixture_expected(rel: str, assignment: dict) -> dict:
    p = ROOT / rel
    r = I.expected(rel, load_json(p), I.diagram_of(p), I.evidence_of([p], assignment), [], I.lib_builtins_of(p))
    return {"laws": {k: dict(v, facts=rel) for k, v in r["laws"].items()}, "basis": r["basis"], "cycle": r["cycle"]}


def write_codecs(repo: Path, milestone: str, adoption: str, link: str):
    """python -m holon codecs for a test milestone in a copy of the tree; returns the process."""
    return run_holon(["codecs", "--milestone", milestone, "--root", str(repo), "--adoption", adoption,
                      "--link", link], cwd=repo)


def component_semantics(doc: dict) -> dict:
    """The keys of a linked codec document that rule X1 fixes (carriers and functions as _i24x.component builds
    them), for comparing holon's document with the instrument's."""
    return {k: doc.get(k) for k in ("linked_version", "component", "role", "tag_index", "linked_carrier",
                                    "documents", "carriers", "functions")}


def diagram_semantics(d: dict) -> dict:
    """The carrier and edge keys of a component diagram that rules X6 and P0-P12 read."""
    ck = ("id", "cls", "interface", "product", "domains", "key_space")
    ek = ("id", "kind", "model_fn", "src", "tgt", "partial", "version", "fn_kind", "source", "domain")
    return {"model": d["model"],
            "carriers": sorted(({k: c.get(k) for k in ck} for c in d["carriers"]), key=lambda c: c["id"]),
            "edges": sorted(({k: e.get(k) for k in ek} for e in d["edges"]), key=lambda e: e["id"])}


class _Morph(unittest.TestCase):
    d: Derive = None

    @classmethod
    def setUpClass(cls):
        if _Morph.d is None:
            _Morph.d = Derive(["--milestone", "M3"])

    @property
    def r(self) -> Derive:
        return _Morph.d

    def derived(self) -> dict:
        """The PAR laws derive wrote but those of sub-form init_chain (later M3 iterations add laws of other rules, and I28
        a PAR law of the sub-form init_chain over the versioned document; I24's checks are about I24's PAR laws. Amended
        at the I28 prereg, spec/M3/amendments.jsonl), those over a Go-op document (I67's, gen/M3/goops/; amended at
        the I67 prereg) and those of the sub-form push (I86's, over a bundle member's document; amended at I86's
        build)."""
        self.assertEqual(self.r.code, 0, self.r.log)
        return {k: v for k, v in self.r.law_docs().items()
                if v.get("rule") == "PAR" and v.get("subform") not in ("init_chain", "push")
                and not str(v.get("facts") or "").startswith("gen/M3/goops/")}


# ---------------------------------------------------------------------------------------------- the registry
class TestRegistry(unittest.TestCase):
    def test_catalogs(self):
        rules = holon_module("holon.rules")
        par = holon_module("holon.rules.par")
        self.assertEqual(rules.RULE_CATALOG_VERSION, "holon-rules/1.0", "M2's catalog version stays I15's")
        self.assertEqual(sorted(rules.CATALOG), ["SORT"], "M2's catalog stays SORT/site")
        self.assertTrue({"holon-rules/1.0", "holon-rules/1.1"} <= set(rules.CATALOGS))
        self.assertEqual(rules.CATALOGS["holon-rules/1.0"], rules.CATALOG)
        self.assertEqual(sorted(rules.CATALOGS["holon-rules/1.1"]), ["PAR"], "SORT enters M3 with I30")
        self.assertEqual(tuple(par.SUBFORMS), I.SUBFORMS)
        self.assertEqual(sorted(rules.CATALOGS["holon-rules/1.1"]["PAR"]), sorted(I.SUBFORMS))
        self.assertEqual([rules.catalog_version(m) for m in ("M2", "T15", "T24")],
                         ["holon-rules/1.0", "holon-rules/1.0", "holon-rules/1.0"])
        cv, sort = m3_catalog()
        if not sort:   # I24: M3 is holon-rules/1.1 and there is no other catalog
            self.assertEqual(cv, "holon-rules/1.1")
            self.assertEqual(sorted(rules.CATALOGS), ["holon-rules/1.0", "holon-rules/1.1"])
        else:          # from I30 on: a later catalog for M3 that keeps holon-rules/1.1's PAR producers unchanged (the
            #            same objects; I28 adds PAR's sub-form init_chain, and only it, beside them: amended at the I28
            #            prereg, spec/M3/amendments.jsonl; I86 adds PAR's sub-form push: amended at I86's build)
            self.assertNotIn(cv, ("holon-rules/1.0", "holon-rules/1.1"))
            base = rules.CATALOGS["holon-rules/1.1"]["PAR"]
            self.assertEqual({s: p for s, p in rules.CATALOGS[cv]["PAR"].items() if s in base}, base)
            for s, p in base.items():
                self.assertIs(rules.CATALOGS[cv]["PAR"][s], p, s)
            self.assertLessEqual(set(rules.CATALOGS[cv]["PAR"]) - set(base), {"init_chain", "push"})

    def test_m2_derivation_is_unchanged(self):
        """I24-R2: PAR is not in M2's catalog; derive --milestone M2 reproduces laws/M2 and gen/M2/sorts/obstructions.json
        byte for byte (I15-R4)."""
        d = Derive(["--milestone", "M2"])
        try:
            self.assertEqual(d.code, 0, d.log)
            files = d.files()
            want = {p.name: p.read_bytes() for p in sorted((ROOT / "laws" / "M2").glob("*.json"))}
            want["<obstructions>"] = (ROOT / "gen" / "M2" / "sorts" / "obstructions.json").read_bytes()
            self.assertEqual(sorted(files), sorted(want))
            for k in want:
                with self.subTest(file=k):
                    self.assertEqual(files[k], want[k], f"{k} differs from the committed M2 derivation")
        finally:
            d.cleanup()

    def test_catalog_override_is_refused_on_m2(self):
        d = Derive(["--milestone", "M2", "--catalog", "holon-rules/1.1"])
        try:
            self.assertEqual(d.code, 1, d.log)
            self.assertEqual(d.files(), {}, "nothing is written")
        finally:
            d.cleanup()


# ---------------------------------------------------------------------------------------------- prereg sidecars
class TestSidecars(unittest.TestCase):
    """Construction checks of the prereg's own inputs (green at the prereg; they guard against later edits)."""

    def test_the_m3_documents_are_the_extracted_ones(self):
        """Q19: the adoption lists exactly the three extracted documents, each holon-facts/0.3 written by a frontend,
        no hand document; the link roles are I19's, byte for byte."""
        ad = load_json(ROOT / X.ADOPTION)
        self.assertEqual(ad["derive_extracted_version"], "holon-derive-extracted/0.1")
        self.assertEqual(ad["documents"], list(EXTRACTED))
        self.assertEqual((ad["reextraction"], ad["width"]), ([], False), "SORT is not in M3's catalog (I30)")
        for rel in ad["documents"]:
            with self.subTest(document=rel):
                d = load_json(ROOT / rel)
                self.assertEqual((d["facts_version"], d["extraction"]["method"]), ("holon-facts/0.3", "extracted"))
                self.assertFalse(rel.startswith(("facts/", "spec/M1/")))
        self.assertEqual((ROOT / X.LINK).read_bytes(), (ROOT / "spec" / "M2" / "lib" / "link.json").read_bytes())

    def test_par_basis_is_the_computation(self):
        """spec/M3/lib/par_basis.json is tests_m3/_i24x.py::par_basis_doc of its inputs, unchanged since the prereg
        (their sha256 is recorded)."""
        sc = load_json(SIDECAR)
        for inp in sc["inputs"]:
            self.assertEqual(file_sha256(ROOT / inp["path"]), inp["sha256"], f"{inp['path']} changed since the prereg")
        self.assertEqual({k: v for k, v in sc.items() if k != "doc"}, X.par_basis_doc(ROOT))
        self.assertTrue(sc["doc"].strip())

    def test_backtest_map_is_the_computation(self):
        """spec/M3/lib/backtest_map.json is rule B1's computation (tests_m3/_i24x.py::backtest_map_doc)."""
        sc = load_json(MAP)
        for inp in sc["inputs"]:
            self.assertEqual(file_sha256(ROOT / inp["path"]), inp["sha256"], f"{inp['path']} changed since the prereg")
        self.assertEqual({k: v for k, v in sc.items() if k != "doc"}, X.backtest_map_doc(ROOT))
        self.assertTrue(sc["doc"].strip())


# ---------------------------------------------------------------------------------------------- M2 untouched
class TestM2Unchanged(unittest.TestCase):
    def test_m2_diagrams_and_evidence_regenerate_byte_for_byte(self):
        """I24-R4: the linked codec layer adds M3 only; holon diagram and holon evidence --milestone M2 write
        gen/M2/diagram and gen/M2/evidence.json byte for byte."""
        tmp = Path(tempfile.mkdtemp(prefix="holon-m2-unchanged-"))
        try:
            p = run_holon(["diagram", "--milestone", "M2", "--out", str(tmp / "diagram")])
            self.assertEqual(p.returncode, 0, p.stderr[-2000:])
            self.assertEqual({q.name: q.read_bytes() for q in sorted((tmp / "diagram").glob("*.json"))},
                             {q.name: q.read_bytes() for q in sorted((ROOT / "gen" / "M2" / "diagram").glob("*.json"))})
            p = run_holon(["evidence", "--milestone", "M2", "--out", str(tmp / "evidence.json")])
            self.assertEqual(p.returncode, 0, p.stderr[-2000:])
            self.assertEqual((tmp / "evidence.json").read_bytes(), (ROOT / "gen" / "M2" / "evidence.json").read_bytes())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- the linked layer
class TestLinkedLayer(unittest.TestCase):
    def test_codecs_writes_the_component(self):
        """Construction (rule X1): holon codecs --milestone M3 writes exactly gen/M3/codec/header_length.json, with the
        carriers and functions the instrument builds; it is the committed file, and --check passes."""
        tmp = Path(tempfile.mkdtemp(prefix="holon-codecs-"))
        try:
            p = run_holon(["codecs", "--milestone", "M3", "--out", str(tmp)])
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
            self.assertEqual(sorted(q.name for q in tmp.glob("*.json")), [f"{COMPONENT}.json"])
            got = load_json(tmp / f"{COMPONENT}.json")
            self.assertEqual(component_semantics(got), component_semantics(X.components()[0]))
            self.assertEqual(sorted(i["path"] for i in got["inputs"]),
                             sorted([X.ADOPTION.as_posix(), X.LINK.as_posix(), EXTRACTED[0], EXTRACTED[1]]))
            self.assertEqual((tmp / f"{COMPONENT}.json").read_bytes(), (ROOT / CODEC_DOC).read_bytes())
            self.assertEqual(run_holon(["codecs", "--milestone", "M3", "--check"]).returncode, 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_m3_diagram_is_the_component_diagram(self):
        """Construction (rule X6): gen/M3/diagram holds exactly header_length.json, whose carriers and edges are the
        instrument's, and holon diagram --milestone M3 regenerates it."""
        files = sorted(p.name for p in (GEN3 / "diagram").glob("*.json"))
        self.assertIn(f"{COMPONENT}.json", files)
        self.assertFalse([f for f in files if f in ("morph_header.json", "morph_rollup.json", "morph_batchdata.json")],
                         "no diagram of a hand document in M3")
        d = load_json(GEN3 / "diagram" / f"{COMPONENT}.json")
        self.assertEqual(diagram_semantics(d), diagram_semantics(X.diagram(X.components()[0])))
        tmp = Path(tempfile.mkdtemp(prefix="holon-diag3-"))
        try:
            p = run_holon(["diagram", "--milestone", "M3", "--out", str(tmp)])
            self.assertEqual(p.returncode, 0, p.stderr[-2000:])
            self.assertEqual((tmp / f"{COMPONENT}.json").read_bytes(),
                             (GEN3 / "diagram" / f"{COMPONENT}.json").read_bytes())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_m3_evidence(self):
        """Construction (rule X7, G1, G4): gen/M3/evidence.json holds the component's atoms (161: E1 70 inverse and 32
        common_decoder, E2 55, E6 4) and an anchors-only model of the transitions document, no hand document,
        sorts_sha256 null; holon evidence --milestone M3 reproduces it byte for byte."""
        ev = load_json(GEN3 / "evidence.json")
        comp, diag, ats, _ = morph_component()
        sorted_m3 = (GEN3 / "sorts" / "assignment.json").exists()   # I30 (G4)
        self.assertEqual(ev["milestone"], "M3")
        if not sorted_m3:
            self.assertIsNone(ev["sorts_sha256"])
        self.assertTrue({COMPONENT, "morph_rollup.extracted"} <= set(ev["models"]))
        self.assertFalse([m for m, x in ev["models"].items() if x["facts"].startswith(("facts/", "spec/M1/"))], "Q19")
        self.assertEqual(ev["models"][COMPONENT]["facts"], CODEC_DOC)
        self.assertIsNone(ev["models"]["morph_rollup.extracted"]["diagram"])
        mine = [a for a in ev["atoms"] if a["model"] == COMPONENT and a["level"] in ("E1", "E2", "E6")]
        self.assertEqual(sorted(json.dumps(a, sort_keys=True) for a in mine),
                         sorted(json.dumps(a, sort_keys=True) for a in ats))
        self.assertEqual(len(mine), 161)
        if not sorted_m3:
            self.assertEqual([a["id"] for a in ev["atoms"] if a["model"] == COMPONENT and a not in mine], [],
                             "no E3, E4 or E5 atom over the component (G4)")
        self.assertEqual([u for u in ev["unresolved"] if u["model"] == COMPONENT], [])
        self.assertEqual(validate(ev, SCHEMAS / "evidence.schema.json"), [])
        tmp = Path(tempfile.mkdtemp(prefix="holon-ev3-"))
        try:
            p = run_holon(["evidence", "--milestone", "M3", "--out", str(tmp / "evidence.json")])
            self.assertEqual(p.returncode, 0, p.stderr[-2000:])
            self.assertEqual((tmp / "evidence.json").read_bytes(), (GEN3 / "evidence.json").read_bytes())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_no_hand_document_is_read_for_m3(self):
        """Q19: with facts/morph_header.json and spec/M1/facts/ removed from a copy, holon codecs, diagram, evidence and
        derive --milestone M3 write exactly the committed M3 files (the back-test alone reads the hand document)."""
        repo = copy_repo()
        try:
            (repo / "facts" / "morph_header.json").unlink()
            shutil.rmtree(repo / "spec" / "M1" / "facts")
            for args in (["codecs", "--milestone", "M3"], ["diagram", "--milestone", "M3"],
                         ["evidence", "--milestone", "M3"]):
                p = run_holon(args + ["--root", str(repo)], cwd=repo)
                self.assertEqual(p.returncode, 0, f"{args}: {p.stderr[-2000:]}")
            for rel in (CODEC_DOC, f"gen/M3/diagram/{COMPONENT}.json", "gen/M3/evidence.json"):
                self.assertEqual((repo / rel).read_bytes(), (ROOT / rel).read_bytes(), rel)
            d = Derive(["--milestone", "M3", "--root", str(repo)], cwd=repo)
            try:
                self.assertEqual(d.code, 0, d.log)
                self.assertEqual({k: v for k, v in d.files().items() if LAW_FILE.match(k)},
                                 {p.name: p.read_bytes() for p in sorted(LAWS3.glob("*.json")) if LAW_FILE.match(p.name)})
            finally:
                d.cleanup()
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- derive on M3
class TestDeriveM3(_Morph):
    def test_cli_writes_laws_registry_and_derivation(self):
        names = set(self.r.files())
        self.assertEqual(self.r.code, 0, self.r.log)
        self.assertIn("REGISTRY.json", names)
        self.assertIn("DERIVATION.json", names)
        rules = holon_module("holon.rules")
        if "SORT" not in rules.CATALOGS[rules.catalog_version("M3")]:
            self.assertNotIn("<obstructions>", names, "a catalog without SORT writes no obstructions file")
        self.assertEqual(sorted(n[:-5] for n in names if LAW_FILE.match(n)), sorted(self.r.law_docs()))

    def test_two_runs_are_byte_identical_and_match_the_committed_files(self):
        self.assertEqual(self.r.code, 0, self.r.log)
        again = Derive(["--milestone", "M3"])
        try:
            self.assertEqual(again.code, 0, again.log)
            self.assertEqual(again.files(), self.r.files(), "two derive runs differ")
        finally:
            again.cleanup()
        committed = {p.name: p.read_bytes() for p in sorted(LAWS3.glob("*.json"))}
        got = {k: v for k, v in self.r.files().items() if k != "<obstructions>"}
        self.assertEqual(got, committed, "holon derive --milestone M3 does not reproduce laws/M3/")

    def test_law_ir(self):
        ls = self.derived()
        self.assertTrue(ls, "derive --milestone M3 wrote no PAR law")
        cv, _ = m3_catalog()
        for lid, law in ls.items():
            with self.subTest(law=lid):
                self.assertEqual(validate(law, IR03), [])
                self.assertEqual((law["ir_version"], law["milestone"], law["rule"], law["rule_catalog_version"]),
                                 ("holon-ir/0.3", "M3", "PAR", cv))
                self.assertIn(law["subform"], I.SUBFORMS)
                self.assertEqual(law["facts"], CODEC_DOC, "every M3 law is over the linked codec document (Q19)")
                self.assertEqual(law["facts_sha256"], file_sha256(ROOT / law["facts"]))
                self.assertFalse({"evidence", "predicted", "maps_to"} & set(law), "a generator does not predict")
                self.assertEqual(law["statement"]["scope"], {"kind": "unbounded"})
        for lid, law in laws("M2").items():   # the schema change is additive
            with self.subTest(m2_law=lid):
                self.assertEqual(validate(law, IR03), [])

    def test_registry(self):
        reg = self.r.doc("REGISTRY")
        refs = holon_module("holon.gen.refs")
        ls = self.derived()
        cv, sort = m3_catalog()
        self.assertTrue(ls, "derive --milestone M3 wrote no PAR law")
        self.assertEqual((reg["milestone"], reg["ir_version"], reg["rule_catalog_version"]), ("M3", "holon-ir/0.3", cv))
        if not sort:
            self.assertIsNone(reg["sorts_sha256"])
        self.assertTrue(set(ls) <= set(reg["statements"]))
        self.assertEqual(reg["facts_files"][CODEC_DOC], file_sha256(ROOT / CODEC_DOC))
        self.assertFalse([f for f in reg["facts_files"] if f.startswith(("facts/", "spec/M1/"))], "Q19")
        self.assertEqual(reg["evidence_sha256"], load_json(GEN3 / "evidence.json")["evidence_sha256"])
        self.assertEqual(reg["derivation_sha256"], file_sha256(self.r.laws / "DERIVATION.json"))
        for lid, law in ls.items():
            with self.subTest(law=lid):
                self.assertEqual(reg["statements"][lid], refs.law_hash(law, load_json(ROOT / law["facts"])))

    def test_derivation_follows_the_rules(self):
        """Construction: every law, basis element, reason and duplicate of DERIVATION.json is the one rules X8 and
        P0-P12 give over the component, as tests_m3/_i24x.py writes them out; statements exactly (canonical JSON).
        Amended at the I28 prereg (spec/M3/amendments.jsonl): the entries of sub-form init_chain (I28's) are left out.
        Amended at the I67 prereg: the entries and basis rows over a Go-op component (I67's, gen/M3/goops/) are left out."""
        comp, diag, ats, exp = morph_component()
        dv = self.r.doc("DERIVATION")
        ls = self.derived()
        cv, sort = m3_catalog()
        self.assertEqual((dv["document"], dv["milestone"], dv["rule_catalog_version"]), ("derivation", "M3", cv))
        if not sort:
            self.assertIsNone(dv["sorts_sha256"])
        self.assertEqual(dv["evidence_sha256"], load_json(GEN3 / "evidence.json")["evidence_sha256"])
        self.assertEqual(sorted(ls), sorted(exp["laws"]))
        for lid, want in exp["laws"].items():
            with self.subTest(law=lid):
                self.assertEqual(ls[lid]["subform"], want["subform"])
                self.assertEqual(canonical_json(ls[lid]["statement"]), canonical_json(want["statement"]))
        goops = {p.stem for p in (ROOT / "gen" / "M3" / "goops").glob("*.json")}
        self.assertEqual(I.basis_rows([b for b in dv["par_basis"] if b["model"] not in goops]), I.basis_rows(exp["basis"]))
        entries = {e["law_id"]: e for e in dv["laws"] if e["rule"] == "PAR"
                   and e.get("subform") not in ("init_chain", "push")
                   and not str(e.get("facts") or "").startswith("gen/M3/goops/")}
        self.assertEqual(sorted(entries), sorted(ls))
        for lid, e in entries.items():
            with self.subTest(entry=lid):
                self.assertEqual((e["rule"], e["subform"], e["facts"], e["entry_points"]),
                                 ("PAR", ls[lid]["subform"], CODEC_DOC, []))
        self.assertEqual(dv["cycle_rank"][COMPONENT],
                         {k: exp["cycle"][k] for k in ("E", "V", "kappa", "rank", "tree", "non_tree")})
        self.assertFalse([m for m in dv["cycle_rank"] if m.startswith("morph_")], "no diagram of a hand document")

    def test_uncovered_is_listed(self):
        """Construction (rule X1, G1, G2): DERIVATION "uncovered" lists the transitions document and the 7 Go codec
        functions outside the component, exactly as the instrument computes them."""
        dv = self.r.doc("DERIVATION")
        self.assertEqual(dv["uncovered"], X.uncovered(ROOT))
        self.assertEqual(len(dv["uncovered"]), 8)

    def test_no_link_and_no_log_line(self):
        """P11: no earlier law is about the linked codec document, so DERIVATION links is [] and I24 appends no line to
        laws/STATEMENT_DIFF.jsonl (the back-test across documents is rules B1-B5). F30 amendment (spec/M3/
        amendments.jsonl): no line is a link line (a cross_milestone entry, or an entry pairing an M3 law with another
        law: another id or another milestone), and no line states an M3 law under I24's catalog (I.CATALOG_VERSION),
        as every line I24 could append does. A line whose new statement is an M3 law under a later catalog belongs to a
        later key, and G2 checks it."""
        dv = self.r.doc("DERIVATION")
        self.assertEqual(dv["links"], [])
        log = ROOT / "laws" / "STATEMENT_DIFF.jsonl"
        lines = [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
        m3 = [e for e in lines if (e.get("new") or {}).get("milestone") == "M3"]
        self.assertFalse([e for e in m3 if e.get("kind") == "cross_milestone"
                          or (e.get("old") or {}).get("law_id") != e["new"].get("law_id")
                          or (e.get("old") or {}).get("milestone", "M3") != "M3"], "a link line names an M3 law")
        self.assertFalse([e for e in m3 if e["new"].get("rule_catalog_version") == I.CATALOG_VERSION],
                         "a line states an M3 law under I24's catalog")

    def test_stale_inputs_are_refused(self):
        """A tampered linked codec document, component diagram or evidence set: exit 2, nothing written."""
        for rel, edit in ((CODEC_DOC, lambda d: d["functions"].pop(sorted(d["functions"])[0])),
                          (f"gen/M3/diagram/{COMPONENT}.json", lambda d: d["edges"].pop()),
                          ("gen/M3/evidence.json", lambda d: d["atoms"].pop())):
            with self.subTest(tampered=rel):
                repo = copy_repo()
                try:
                    doc = load_json(repo / rel)
                    edit(doc)
                    write_json(repo / rel, doc)
                    d = Derive(["--milestone", "M3", "--root", str(repo)], cwd=repo)
                    try:
                        self.assertEqual(d.code, 2, d.log)
                        self.assertEqual(d.files(), {})
                    finally:
                        d.cleanup()
                finally:
                    shutil.rmtree(repo.parent, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- honesty
class TestGenericCode(unittest.TestCase):
    """No special-casing (AGENTS rules 2 and 4): the PAR code and the linked codec layer name no target and no fixture
    identifier."""

    MODULES = ("holon/rules/par.py", "holon/diagram/linked.py", "holon/gen/linked.py")

    def test_new_code_names_no_target_and_no_fixture_identifier(self):
        names = I.target_names() | X.target_names()
        compound = {n for n in names if len(n) >= 5 and ("_" in n or any(c.isupper() for c in n[1:]))}
        quoted = {n for n in names if len(n) >= 3} - I.GENERIC_WORDS - X.GENERIC_WORDS
        for rel in self.MODULES:
            with self.subTest(module=rel):
                f = ROOT / rel
                self.assertTrue(f.exists(), f"{rel} is missing")
                text = f.read_text(encoding="utf-8")
                self.assertEqual(sorted(n for n in compound
                                        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", text)), [])
                self.assertEqual(sorted(n for n in quoted if re.search(rf"[\"']{re.escape(n)}[\"']", text)), [])
                self.assertNotRegex(text, r"L_par_\w*(v[0-9]|pinned)\b", "no law id is written into the code")
                self.assertNotRegex(text, r"L_(dom|par|rt)_hdr|L_rt_go|L_par_hdr", "no M0 law id")

    def test_laws_do_not_depend_on_earlier_milestones(self):
        """Derive never copies an earlier law: with laws/M0 removed, laws/M3 is byte-identical but for the inputs DERIVATION
        lists."""
        repo = copy_repo()
        try:
            a = Derive(["--milestone", "M3", "--root", str(repo)], cwd=repo)
            shutil.rmtree(repo / "laws" / "M0")
            b = Derive(["--milestone", "M3", "--root", str(repo)], cwd=repo)
            try:
                self.assertEqual((a.code, b.code), (0, 0), a.log + b.log)
                fa = {k: v for k, v in a.files().items() if LAW_FILE.match(k)}
                fb = {k: v for k, v in b.files().items() if LAW_FILE.match(k)}
                self.assertEqual(fa, fb)
                da, db = a.doc("DERIVATION"), b.doc("DERIVATION")
                self.assertEqual({k: v for k, v in da.items() if k != "inputs"},
                                 {k: v for k, v in db.items() if k != "inputs"})
            finally:
                a.cleanup()
                b.cleanup()
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_renaming_fixture_identifiers_renames_the_derivation(self):
        """Renaming a facts fixture's identifiers renames its laws and changes nothing else (a codec and a machine
        fixture)."""
        cases = {"cross_component": {"enc_cc_go": "zq_alpha", "enc_cc_sol": "zq_beta", "dec_cc": "zq_gamma",
                                     "ok_cc": "zq_delta", "view_cc": "zq_eps"},
                 "recompute": {"put": "zq_one", "reput": "zq_two", "enc": "zq_fun", "held": "zq_reg"}}
        for fx, ren in cases.items():
            with self.subTest(fixture=fx):
                repo = copy_repo()
                try:
                    rel = FIXTURES[fx]
                    text = (repo / rel).read_text()
                    for old, new in ren.items():
                        text = re.sub(rf'(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])', new, text)
                    ren_rel = rel.replace(".facts.json", "_renamed.facts.json")
                    (repo / ren_rel).write_text(text)
                    runs = {}
                    for n, r in enumerate((rel, ren_rel)):
                        asg = fixture_assignment(repo.parent / f"sorts{n}", [r], cwd=repo)
                        runs[r] = Derive(["--milestone", "T24", "--catalog", "holon-rules/1.1", "--root", str(repo),
                                          "--facts", r, "--assignment", str(asg)], cwd=repo)
                    a, b = runs[rel], runs[ren_rel]
                    try:
                        self.assertEqual((a.code, b.code), (0, 0), a.log + b.log)

                        def renamed(s: str) -> str:
                            for old, new in ren.items():
                                s = re.sub(rf'(?<![A-Za-z0-9]){re.escape(old)}(?![A-Za-z0-9])', new, s)
                            return s
                        la = {renamed(k): json.loads(renamed(json.dumps(v["statement"])))
                              for k, v in a.law_docs().items()}
                        lb = {k: v["statement"] for k, v in b.law_docs().items()}
                        self.assertTrue(lb, b.log)
                        self.assertEqual(sorted(la), sorted(lb))
                        for k in lb:
                            self.assertEqual(canonical_json(la[k]), canonical_json(lb[k]), k)
                    finally:
                        for r in runs.values():
                            r.cleanup()
                finally:
                    shutil.rmtree(repo.parent, ignore_errors=True)

    def test_renaming_the_linked_fixture_renames_its_derivation(self):
        """Renaming the linked fixture's Solidity functions, record fields and Go methods renames its laws and changes
        nothing else."""
        ren = {"enc_x": "zq_enc", "load_x": "zq_load", "RootNew": "ZqOldNew", "Root": "ZqOld", "makeV2": "zqPatch"}
        repo = copy_repo()
        try:
            fx = repo / "tests_m3" / "fixtures" / "par_linked"
            for f in sorted(fx.glob("*.json")):
                text = f.read_text()
                for old, new in ren.items():
                    text = re.sub(rf'(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])', new, text)
                (fx.parent / "par_linked_renamed").mkdir(exist_ok=True)
                (fx.parent / "par_linked_renamed" / f.name).write_text(text.replace("par_linked/", "par_linked_renamed/"))
            out = {}
            for tag, ms, d in (("a", "T24", "par_linked"), ("b", "T25", "par_linked_renamed")):
                p = write_codecs(repo, ms, f"tests_m3/fixtures/{d}/derive_extracted.json",
                                 f"tests_m3/fixtures/{d}/link.json")
                self.assertEqual(p.returncode, 0, p.stderr[-2000:])
                out[tag] = Derive(["--milestone", ms, "--catalog", "holon-rules/1.1", "--root", str(repo),
                                   "--codec", f"gen/{ms}/codec/{LINKED_FX['role']}.json"], cwd=repo)
            try:
                self.assertEqual((out["a"].code, out["b"].code), (0, 0), out["a"].log + out["b"].log)

                def renamed(s: str) -> str:
                    for old, new in ren.items():
                        s = re.sub(rf'(?<![A-Za-z0-9]){re.escape(old)}(?![A-Za-z0-9])', new, s)
                    return s
                la = {renamed(k): json.loads(renamed(json.dumps(v["statement"]))) for k, v in out["a"].law_docs().items()}
                lb = {k: v["statement"] for k, v in out["b"].law_docs().items()}
                self.assertTrue(lb)
                self.assertEqual(sorted(la), sorted(lb))
                for k in lb:
                    self.assertEqual(canonical_json(la[k]), canonical_json(lb[k]), k)
            finally:
                for d in out.values():
                    d.cleanup()
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- fixtures (derive)
class TestFixtureDerivation(unittest.TestCase):
    """Construction: each planted facts fixture derives, as test milestone T24 under catalog holon-rules/1.1, exactly the
    laws and basis elements the rules give (statements exactly); its outcomes are I24-P3 (tests_m3/test_par_outcomes.py)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-par-fx-"))
        rels = list(FIXTURES.values())
        cls.asg_path = fixture_assignment(cls.tmp, rels)
        cls.asg = load_json(cls.asg_path)
        args = ["--milestone", "T24", "--catalog", "holon-rules/1.1", "--assignment", str(cls.asg_path)]
        for r in rels:
            args += ["--facts", r]
        cls.d = Derive(args)

    @classmethod
    def tearDownClass(cls):
        cls.d.cleanup()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_fixture_laws_and_basis(self):
        self.assertEqual(self.d.code, 0, self.d.log)
        got = self.d.law_docs()
        dv = self.d.doc("DERIVATION")
        self.assertEqual(sorted(got), sorted(x for v in FIXTURE_LAWS.values() for x in v))
        for fx, rel in FIXTURES.items():
            with self.subTest(fixture=fx):
                exp = fixture_expected(rel, self.asg)
                self.assertEqual(sorted(exp["laws"]), FIXTURE_LAWS[fx])
                self.assertIn(FIXTURE_SUBFORM[fx], {exp["laws"][x]["subform"] for x in FIXTURE_LAWS[fx]},
                              f"the {fx} fixture yields a law of its own sub-form")
                for lid, want in exp["laws"].items():
                    self.assertEqual((got[lid]["facts"], got[lid]["subform"], got[lid]["milestone"],
                                      got[lid]["rule_catalog_version"]),
                                     (rel, want["subform"], "T24", "holon-rules/1.1"))
                    self.assertEqual(canonical_json(got[lid]["statement"]), canonical_json(want["statement"]), lid)
                model = Path(rel).stem
                self.assertEqual(I.basis_rows([b for b in dv["par_basis"] if b["model"] == model]),
                                 I.basis_rows(exp["basis"]))
                self.assertEqual(dv["cycle_rank"][model],
                                 {k: exp["cycle"][k] for k in ("E", "V", "kappa", "rank", "tree", "non_tree")})
        self.assertEqual(dv["links"], [], "no earlier law is about a fixture")


class TestLinkedFixtureDerivation(unittest.TestCase):
    """Construction: the linked fixture (tests_m3/fixtures/par_linked/) derives, as T24 under holon-rules/1.1, exactly
    the 28 laws and basis elements rules X1-X8 give; its outcomes are part of I24-P3."""

    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        cls.codecs = write_codecs(cls.repo, "T24", LINKED_FX["adoption"], LINKED_FX["link"])
        cls.d = Derive(["--milestone", "T24", "--catalog", "holon-rules/1.1", "--root", str(cls.repo),
                        "--codec", f"gen/T24/codec/{LINKED_FX['role']}.json"], cwd=cls.repo)

    @classmethod
    def tearDownClass(cls):
        cls.d.cleanup()
        shutil.rmtree(cls.repo.parent, ignore_errors=True)

    def test_the_linked_fixture_component(self):
        self.assertEqual(self.codecs.returncode, 0, self.codecs.stdout[-2000:] + self.codecs.stderr[-2000:])
        got = load_json(self.repo / "gen" / "T24" / "codec" / f"{LINKED_FX['role']}.json")
        comp, *_ = linked_fixture()
        self.assertEqual(component_semantics(got), component_semantics(comp))

    def test_linked_fixture_laws_and_basis(self):
        self.assertEqual(self.d.code, 0, self.d.log)
        comp, diag, ats, exp = linked_fixture()
        got = self.d.law_docs()
        dv = self.d.doc("DERIVATION")
        self.assertEqual({s: sorted(l for l, x in got.items() if x["subform"] == s) for s in LINKED_LAWS},
                         {s: sorted(v) for s, v in LINKED_LAWS.items()})
        self.assertEqual(sorted(got), sorted(exp["laws"]))
        for lid, want in exp["laws"].items():
            with self.subTest(law=lid):
                self.assertEqual(canonical_json(got[lid]["statement"]), canonical_json(want["statement"]))
                self.assertEqual(got[lid]["facts"], f"gen/T24/codec/{LINKED_FX['role']}.json")
        self.assertEqual(I.basis_rows(dv["par_basis"]), I.basis_rows(exp["basis"]))
        self.assertEqual(dv["cycle_rank"][LINKED_FX["role"]],
                         {k: exp["cycle"][k] for k in ("E", "V", "kappa", "rank", "tree", "non_tree")})


# ---------------------------------------------------------------------------------------------- predictions
class TestPredictedMorph(_Morph):
    def test_cycle_basis_count_equals_the_preregistered_rank(self):
        """I24-P1: the M3 diagram gen/M3/diagram/header_length.json has |E| - |V| + kappa = 20 - 17 + 1 = 4 cycle basis
        elements, as spec/M3/lib/par_basis.json computed at the prereg: the non-tree edges CODEC.BatchHeaderBytes_
        BlobHashesHash, CODEC.BatchHeaderBytes_BlobVersionedHash, CODEC.BatchHeaderV1_Bytes and CODEC.load_sol. None
        adds a law: the two blob getters' cycles (against the tree edge BlobCommitHash) restate the three PAR-weak laws
        at their common versions (X8c: BlobHashesHash at 2, BlobVersionedHash at 0 and 1; recorded as duplicates), the
        V1 encoder and the patch share no version ({1}, {2}), and load_sol's self-loop is not a parallel pair. No TRANS
        edge enters the basis (the transitions document has no M3 diagram, G1). Amended at the I67 prereg
        (spec/M3/amendments.jsonl): the cycle rank and basis rows of a Go-op component (I67's) are left out."""
        self.assertEqual(self.r.code, 0, self.r.log)
        sc = load_json(SIDECAR)["components"][COMPONENT]
        dv = self.r.doc("DERIVATION")
        goops = {p.stem for p in (ROOT / "gen" / "M3" / "goops").glob("*.json")}
        self.assertEqual({k: v for k, v in dv["cycle_rank"].items() if k not in goops}, {COMPONENT: sc["cycle"]})
        self.assertEqual({k: sc["cycle"][k] for k in ("E", "V", "kappa", "rank")},
                         {"E": 20, "V": 17, "kappa": 1, "rank": 4})
        cyc = {(b["key"]["edge"], b["version"]): b for b in dv["par_basis"]
               if b["subform"] == "cycle" and b["model"] not in goops}
        self.assertEqual(sorted({e for e, _ in cyc}), sorted(sc["cycle"]["non_tree"]))
        self.assertEqual(sorted(cyc, key=lambda k: (k[0], -1 if k[1] is None else k[1])),
                         [("CODEC.BatchHeaderBytes_BlobHashesHash", 2), ("CODEC.BatchHeaderBytes_BlobVersionedHash", 0),
                          ("CODEC.BatchHeaderBytes_BlobVersionedHash", 1), ("CODEC.BatchHeaderV1_Bytes", None),
                          ("CODEC.load_sol", None)])
        self.assertEqual((cyc[("CODEC.load_sol", None)]["reason"], cyc[("CODEC.BatchHeaderV1_Bytes", None)]["reason"]),
                         ("not_a_parallel_pair", "no_common_version"))
        weak = "L_par_weak_BatchHeaderBytes_BlobCommitHash_BatchHeaderBytes_Blob"
        for (e, v), want in ((("CODEC.BatchHeaderBytes_BlobHashesHash", 2), "HashesHash"),
                             (("CODEC.BatchHeaderBytes_BlobVersionedHash", 0), "VersionedHash"),
                             (("CODEC.BatchHeaderBytes_BlobVersionedHash", 1), "VersionedHash")):
            with self.subTest(cycle=e, version=v):
                self.assertEqual((cyc[(e, v)]["laws"], cyc[(e, v)]["reason"]), ([], None))
                self.assertEqual(cyc[(e, v)]["duplicates"],
                                 {f"L_par_cy_{e.split('.', 1)[1]}_v{v}": f"{weak}{want}_v{v}"})
        self.assertEqual(sc["duplicates"], {d: k for b in cyc.values() for d, k in b["duplicates"].items()})
        self.assertFalse([lid for lid, law in self.derived().items() if law["subform"] == "cycle"])

    def test_the_morph_par_laws(self):
        """I24-P2: derive --milestone M3 emits exactly the 80 PAR laws spec/M3/lib/par_basis.json lists, all over
        gen/M3/codec/header_length.json: 70 round trip (one per E1 inverse atom: enc_sol 11/12/12 at versions 0/1/2,
        BatchHeaderV0_Bytes 11, BatchHeaderV1_Bytes 12, the patch BatchCache_createBatchHeaderWithSequencerSetHash 12),
        6 cross-component (the Go encoder, the V1 encoder and the patch each against enc_sol at its one version, full and
        pinned), 3 PAR-weak (rule X8c: BlobCommitHash with BlobHashesHash at version 2 and with BlobVersionedHash at
        versions 0 and 1, each under the tag premise BatchHeaderBytes_Version(b) = Some(v)) and 1 domain coherence; no
        branch, totality, cycle, recompute, consumer or init law, with these reasons only: totality explicit_option x15,
        weak no_common_version x2 (BlobHashesHash/BlobVersionedHash {2} and {0, 1}; the patch/V1 encoder {2} and {1}),
        cycle no_common_version x1 and not_a_parallel_pair x1 (and the three cycle duplicates)."""
        ls = self.derived()
        sc = load_json(SIDECAR)["components"][COMPONENT]
        self.assertEqual(sorted(ls), sorted(sc["laws"]))
        by = {s: sorted(l for l, x in ls.items() if x["subform"] == s) for s in I.SUBFORMS}
        self.assertEqual({s: len(v) for s, v in by.items() if v},
                         {"round_trip": 70, "cross_component_codec": 6, "weak": 3, "domain_coherence": 1})
        self.assertEqual(by["cross_component_codec"], sorted(
            f"L_par_cc_{p}_enc_sol_v{v}{s}" for p, v in (("BatchHeaderV0_Bytes", 0), ("BatchHeaderV1_Bytes", 1),
                                                          ("BatchCache_createBatchHeaderWithSequencerSetHash", 2))
            for s in ("", "_pinned")))
        self.assertEqual(by["domain_coherence"], ["L_par_dom_BatchHeaderBytes_validate_ok_load_sol"])
        self.assertEqual(by["weak"], ["L_par_weak_BatchHeaderBytes_BlobCommitHash_BatchHeaderBytes_BlobHashesHash_v2",
                                      "L_par_weak_BatchHeaderBytes_BlobCommitHash_BatchHeaderBytes_BlobVersionedHash_v0",
                                      "L_par_weak_BatchHeaderBytes_BlobCommitHash_BatchHeaderBytes_BlobVersionedHash_v1"])
        for lid in by["weak"]:
            with self.subTest(weak=lid):
                v = int(lid.rsplit("_v", 1)[1])
                self.assertEqual(ls[lid]["statement"]["binders"], [{"q": "forall", "name": "b", "type": "Bytes"}])
                self.assertEqual(ls[lid]["statement"]["assume"],
                                 [{"eq": [{"call": "BatchHeaderBytes_Version", "args": [{"var": "b"}]},
                                          {"some": {"bytes": f"0x{v:02x}"}}]}], "the tag premise (X8c)")
        rt = {}
        for lid in by["round_trip"]:
            enc = next(e for e in ("enc_sol", "BatchHeaderV0_Bytes", "BatchHeaderV1_Bytes",
                                   "BatchCache_createBatchHeaderWithSequencerSetHash") if lid.startswith(f"L_par_rt_{e}_"))
            rt[(enc, lid.rsplit("_v", 1)[1])] = rt.get((enc, lid.rsplit("_v", 1)[1]), 0) + 1
        self.assertEqual(rt, {("enc_sol", "0"): 11, ("enc_sol", "1"): 12, ("enc_sol", "2"): 12,
                              ("BatchHeaderV0_Bytes", "0"): 11, ("BatchHeaderV1_Bytes", "1"): 12,
                              ("BatchCache_createBatchHeaderWithSequencerSetHash", "2"): 12})
        dv = self.r.doc("DERIVATION")
        reasons = {}
        for b in dv["par_basis"]:
            if b["reason"]:
                reasons[f"{b['subform']}/{b['reason']}"] = reasons.get(f"{b['subform']}/{b['reason']}", 0) + 1
        self.assertEqual(reasons, sc["reasons"])
        self.assertEqual(reasons, {"totality/explicit_option": 15, "weak/no_common_version": 2,
                                   "cycle/no_common_version": 1, "cycle/not_a_parallel_pair": 1})
        for lid, law in ls.items():
            if law["subform"] == "cross_component_codec" and lid.endswith("_pinned"):
                with self.subTest(law=lid):
                    pins = [a for a in law["statement"]["assume"] if "bytes" in a["eq"][1]
                            and a["eq"][0]["field"] != "version"]
                    self.assertEqual([(a["eq"][0]["field"].rsplit(".", 1)[-1], a["eq"][1]["bytes"]) for a in pins],
                                     [("SequencerSetVerifyHash", "0x" + "00" * 32)])
