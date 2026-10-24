"""I14: the evidence calculus E1-E6 over the protocol diagram, the frozen evidence set, GEVID, evidence_triage
(whitepaper Def 4.5, §5.1, §10.2 getter recovery, Prop 6.11 and L3; BUILD_PLAN I14, V7). This docstring is the
contract every tests_m2/test_evidence*.py module reads; tests_m2/_evidence.py holds the shared helpers and
tests_m2/fixtures/evidence/ the planted fixtures (instruments fixed at the I14 prereg).

Names. holon/evidence.py already exists with another meaning (what a replay side's logged values show, I4) and is
not touched. The calculus lives in holon/diagram/evidence.py (module holon.diagram.evidence); getter recovery is
added to holon/layout.py (recovers, evidence).

CLI
  python -m holon evidence [--milestone M2] [--root DIR] [--out PATH]
    Reads, from --root only (default: this checkout): the milestone's fact documents
    (holon.diagram.fact_documents), the committed diagrams gen/<M>/diagram/<stem>.json (I11), the frozen sorts
    assignment gen/<M>/sorts/assignment.json (I13), the target libraries of each fact document
    (holon.gen.targetlib.lib_files) and the E6 vocabulary spec/M2/lib/evidence_lexical.json (frozen at this
    prereg; the only target vocabulary of the pass). Writes exactly one file, PATH (default
    <root>/gen/<M>/evidence.json), as render(doc) = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False)
    + "\n". Exit 0 on success; nonzero, writing nothing, when an input is missing, unreadable or holds a construct
    the pass cannot map (no silent drops). Two runs write identical bytes. Commit gen/M2/evidence.json.

API (holon.diagram.evidence)
  EVIDENCE_VERSION == "holon-evidence/0.1";  LEVELS == ("E1", "E2", "E3", "E4", "E5", "E6");
  STRENGTH == {"E1": "strong", "E2": "strong", "E3": "strong", "E4": "strong", "E5": "medium", "E6": "weak"}
  build(fact_paths, root, diagrams=None, assignment=None, milestone=None) -> doc
      The evidence document of the given fact documents (paths inside root). diagrams: {model stem: diagram JSON}
      (default: root/gen/M2/diagram/<stem>.json); assignment: a document shaped like gen/M2/sorts/assignment.json,
      of which only models[<stem>]["assignment"], "sites" (absent: none) and "sorts_sha256" are read (default:
      root/gen/M2/sorts/assignment.json). The document does not depend on the order of fact_paths. The CLI writes
      render(build(<the milestone's documents>, root, milestone=M)).
  render(doc) -> str                       the file text above
  law_evidence(law, doc) -> dict           rules L1-L4 below; a pure function of the law and the document
  evidence_triage(status, max_level) -> "finding" | "intent_question" | "none"
  gevid(milestone, root) -> dict           the GEVID check entry below; holon.gate runs it as check "GEVID"
  holon.layout.recovers(layout, getter) -> bool and holon.layout.evidence(facts, encoder, decoder, version) ->
  {"fields": [...], "not_recovered": [...]}: rule E1 for one encoder and decoder (facts function names) and version.

gen/M2/evidence.json (validates against spec/schemas/evidence.schema.json, which the builder writes: top level
required keys below, one schema per via shape, the level enum E1..E6; it must reject {"document": "evidence"})
  {"document": "evidence", "evidence_version": "holon-evidence/0.1", "milestone": "M2",
   "inputs": [{"path": repo-relative, "sha256": hex}]   every file read, sorted by path,
   "levels": STRENGTH,
   "sorts_sha256": the assignment's "sorts_sha256" (null when it has none),
   "models": {<stem>: {"facts": repo-relative path, "facts_sha256", "facts_version",
                       "diagram": "gen/M2/diagram/<stem>.json" (null when the diagram was passed in),
                       "anchors": anchors}},
   "atoms": [atom] sorted by id,  "unresolved": [entry] sorted by id,
   "evidence_sha256": sha256 of the canonical JSON (sorted keys, separators (",", ":"), UTF-8, no ASCII escaping)
                      of the document without "evidence_sha256" and "inputs" (computed like I13's sorts_sha256)}
  atom  = {"id": "<model>:<level>:<p>:<q>:<first 8 hex of sha256(canonical JSON of via)>", "model", "level",
           "p": edge id, "q": edge id, "via": per level below, "src": span | null}
  entry = {"id": "<model>:unresolved:<p>:<q>:<carrier>", "model", "p", "q", "carrier",
           "imprecise": ["read"] | ["write"] | ["read", "write"]}
  anchors (from the model's diagram; every list sorted, empty maps and lists when the model has none) =
    {"codec": {model_fn: CODEC edge id}, "domains": {every predicate of the diagram: [ids of CODEC edges whose
     "domain" is it]},
     "actions": {action: "TRANS.<action>"}, "reasons": {"<r>": [ids of TRANS edges with a guard of reason r]},
     "permissionless": [ids of TRANS edges with "permissionless": true],
     "observers": {name: "LOAD.obs.<name>"}, "migrations": {name: "MIG.<name>"}, "consumers": {model_fn: CONS id},
     "carriers": {carrier: {"writers": STORE.<carrier>.writers, "readers": LOAD.<carrier>.readers}},
     "trans": [ids of every TRANS edge],
     "sites": {site id: [anchors.actions[x] for every action x that an occurrence of the site names, sorted, distinct]}
              for every site of the assignment's "sites" whose "model" is this one (an occurrence in a definition,
              observer or migration names no edge: which actions reach a definition is I15's derivation, and laws/ is
              never an input of the set)}
  Atom endpoints are edges of kind CODEC, TRANS, MIG or CONS, or observer edges (LOAD with "observer": true).
  The per-carrier STORE and LOAD edges are aggregates of those edges' access sets and are never endpoints.
  A span is the leading "<path>:<line>[-<line>]" of a facts src string (I13's convention).

The six levels (Def 4.5: for parallel paths, the highest level supported; strong E1-E4, medium E5, weak E6)
  E1 layout inversion (§10.2: "Getters recover a field iff its positions map to it in order"). Facts 0.1.
     versions(edge) reads the diagram "version" label as integers ("a..b" a range, "a,b" a list, "a" one, null
     none). For every CODEC encoder e (fn_kind "encoder") and decoder d (fn_kind "decoder") with e.tgt == d.src,
     and every v in versions(e) ∩ versions(d): Λ = holon.layout.layout(facts, <e's model_fn>, v); the getters of d
     (facts functions[<d's model_fn>].getters) active at v
     are those whose "when" holds at v (holon.facts.when_ok); getter g is recovered iff
     g.offset + g.width <= len(Λ) and Λ[g.offset + k] == ["field", g.name, k] for every k < g.width (a constant,
     an unknown byte or another field's byte breaks it). If some active getter is recovered: atom p = e, q = d,
     via {"kind": "inverse", "version": v, "fields": recovered getters in getter order, "not_recovered": the other
     active getters in getter order}. Common decoder: for encoders e1 < e2 (by id) with equal src and tgt that
     both have an inverse atom with one decoder d at one version v, and whose "fields" intersect: atom p = e1,
     q = e2, via {"kind": "common_decoder", "version": v, "decoder": d, "fields": the intersection in getter order}.
     src null. (A Go encoder's version label is the constant it writes at the version slot, I11.)
  E2 written via p, read via q. Every ordered pair of endpoints (p, q) of one model, p == q allowed, and carrier
     c that p writes and q reads (diagram access). Index terms overlap when either is "*", or both are numeric
     ("n" or "a..b", inclusive) and intersect, or one is symbolic (any other term; index expressions are evaluated
     in the states of different steps, so their syntax cannot separate them). A term is imprecise when it is "*"
     on a carrier whose diagram key_space is not null (a sequence) and holon.diagram.access produces it only at its
     kindless-builtin fallback: the carrier passed directly as an argument of a library builtin that declares no
     access kind (the builtins the diagram lists as ACCESS coverage debt), whether read (Walker.read) or updated by
     an effect (Walker.write with role "opaque"). Every other term is precise (the whole of a scalar is exact;
     F-M2-30 in audit/M2_findings.jsonl). If a precise write term of p overlaps a precise read term of q: atom
     via {"carrier": c, "writes": p's precise write terms on c that overlap a precise read term of q, sorted,
     "reads": q's precise read terms on c that overlap a precise write term of p, sorted}, src null. Else, if any
     write term overlaps any read term: an unresolved entry, never evidence; "imprecise" holds "write" iff every
     write term of p on c that overlaps a read term of q is imprecise, and "read" iff every read term of q on c
     that overlaps a write term of p is imprecise.
  E3 the system compares the outputs of two paths itself. Facts 0.2 TRANS edges. Every "==" node, at any depth,
     of a guard's "require" (never lets or effects) whose two operands are path terms: a path term mentions a
     state field, an action input or a let of the action (directly, through lets, or in call arguments); literals
     and facts params are not, so a comparison with a constant (rri == 0, who == OWNER, proof == 1) is not E3.
     "!=", mem and eq_nats are not E3. Atom p = q = the TRANS edge, via {"where": "guards[<i>].require" (i: the
     guard's index in the facts action), "reason": the guard's reason or null, "operands": [left, right] exactly as
     written in the facts}, src = span of the guard's src.
  E4 q recomputes a value stored via p. Facts 0.2. A qualifying call: ["call", f, a1, ..., an] with f a facts def
     or a library builtin (never a generic builtin of holon.diagram.access.GENERIC_ROLES, never a shadow projection
     es_<field>), n >= 1, no argument mentioning a state field and at least one mentioning an action input (the
     edge's lets substituted). A TRANS or MIG edge p stores f when one of its effects, lets substituted, contains a
     qualifying call of f; a TRANS edge q recomputes f when a guard (require or let expression) or an effect of q,
     as written, contains one. For p != q: atom via {"fn": f, "stored": p's positions "effects.<field>", sorted,
     "recomputed": q's positions "guards[<i>].require" | "guards[<i>].expr" | "effects.<field>", sorted}, src null.
  E5 identical refined sorts at the endpoints, from I13's frozen assignment (gen/M2/sorts/assignment.json
     models[<model>].assignment). Every node with op in {"+", "-", "==", "!=", "<", "<=", ">", ">="}, at any depth,
     in a TRANS edge's guards (require and let expressions) and effects, a MIG edge's effects, or an observer's
     body (definition bodies are not walked). Operand sort: a name is its assignment key (a let or input x of the
     action or migration as "<name>.<x>", else a state field "<x>", else a param "<x>"; no key: no sort); ["get", X, g] is
     the key "<T>.<g>" when X's record type T is known (a call of a facts def or library builtin whose declared type
     is T, an element of a state list of T, or a let bound to one); ["call", "nth", c, i] with c a state list of Nat
     is the key "<c>"; ["+" | "-", a, b] is holon.sorts.grammar.affine(op, sort(a), sort(b)) when both are known;
     ["?", c, a, b] is sort(a) when sort(a) == sort(b); anything else has no sort. A sort is refined unless it is
     "Nat (unrefined)", "Bool", a "Mach(<w>)" or a union (" + "): a union records writers that deliver distinct
     sorts (§7.4), the opposite of identical. Atom when both operand sorts are known, refined and equal: p = q = the
     edge, via {"where": "guards[<i>].require" | "guards[<i>].expr" | "effects.<field>" | "body", "op", "operands":
     [left, right] as written, "sort": the common sort}, src = span of the guard's src (an effect: the action's
     effects_src, else its src; a MIG effect: the migration's src; an observer: null).
  E6 lexical only (names): spec/M2/lib/evidence_lexical.json verbatim (which names, the tokenizer, the stopwords,
     the rule): for two distinct parallel endpoints p < q (same kind, src and tgt) whose name tokens intersect,
     via {"tokens": the intersection, sorted}, src null. Comments, docs, notes and model-author names are not read.

Law evidence: law_evidence(law, doc) = {"model", "covered", "named", "context", "version", "atoms", "levels", "max"}
  L1 model: the stem of doc's model whose "facts" equals law["facts"] (null if none). covered iff there is one and
     law["facts_sha256"] is empty, absent, or equal to that model's facts_sha256. Not covered: named, context, atoms
     and levels are [], version and max null.
  L2 named: edges the law's hashed statement (assume and claim) names, through the model's anchors.
     holon-ir/0.1: {"call": f} -> anchors.codec[f], and anchors.domains[f] when f is a predicate.
     holon-ir/0.2, 0.3: {"act": a} and {"fn": "is_<a>"} -> anchors.actions[a]; {"fn": "perm"} ->
     anchors.permissionless; {"fn": "no_code", "args": [_, {"nat": r}]} -> anchors.reasons["<r>"]; {"fn": f} with
     f in anchors.consumers -> that edge; {"obsv": o} -> anchors.observers[o]; {"mig": m} -> anchors.migrations[m];
     {"proj": [c, ...]} -> anchors.carriers[c] writers and readers.
     holon-ir/0.3 also: {"site": ID, "on": _, "from": _} (I15's SORT-site term) -> anchors.sites[ID] (no entry:
     nothing). Every other term names nothing.
  L3 context: anchors.trans when some binder ("binders", 0.2/0.3) has type Trace, State, Act or Reach (the law
     ranges over the machine's own steps); else []. N = named ∪ context.
  L4 version (holon-ir/0.1 only): v when the premises fix the record field "version" by exactly one value
     ({"eq": [{"field": "version", "of": {"var": _}}, {"bytes": hex}]}, either order); else null.
  Relevant atoms: same model, p ∈ N and q ∈ N, p ∈ named or q ∈ named, and (version null, or no "version" in the
  atom's via, or via.version == version). atoms: their ids, sorted; levels: their levels, sorted, distinct;
  max: the first of LEVELS present (null when none). Unresolved entries are never evidence.

evidence_triage(status, max_level): "none" unless status is REFUTED; then "intent_question" iff max_level is "E6",
  else "finding" (also when nothing is computed: BUILD_PLAN I14, "finding otherwise").

Records (v2, additive; spec/schemas/result_record_v2.schema.json requires the three fields)
  evidence_levels    law_evidence(law, gen/M2/evidence.json)["levels"] when covered, else null
  evidence_triage    evidence_triage(status, that max)
  evidence_override  null, or config/evidence_overrides.json[<M>][<law_id>], exactly
                     {"evidence_triage": "finding" | "intent_question", "why": non-empty string}
  The v1 "triage" never changes. Effective evidence triage: the override's value when there is one, else
  evidence_triage. Records over facts the evidence set does not cover (planted mutation runs, toy targets) get
  null levels and the computed triage; nothing fails. config/evidence_overrides.json is absent or holds no entry
  in I14 (an override is a human's recorded judgment).

GEVID (holon.gate.CHECK_ORDER holds "GEVID" right after "GREF"; it runs for every milestone, reads no git and runs
no tool). Evidence file: gen/M2/evidence.json for M0, M1 and M2 (gen/<M>/evidence.json from M3 on).
  problems (strings; each names what failed: the law id, the record field, "evidence_sha256", "sorts_sha256" or the
  file concerned; every one fails the check in every mode):
    the evidence file is missing, unreadable, invalid against its schema, or its evidence_sha256 is not the hash
    of its body; its sorts_sha256 differs from gen/M2/sorts/assignment.json's; a fresh build from the committed
    inputs does not render to the file's exact bytes; from M2 on, laws/<M>/REGISTRY.json lacks "evidence_sha256" or
    holds another value; a record (results/<M>/<law_id>.json, where one exists) whose evidence_levels,
    evidence_triage or evidence_override differs from the recomputation; a malformed override, one that names no
    law of the milestone, or one on a law whose record is not REFUTED; from M2 on, a law the set does not cover.
  mismatches: laws whose metadata evidence (law["evidence"], unhashed; absent means []) is not a subset of
    law_evidence(law)["levels"]. Laws are never edited to agree with GEVID: a mismatch is a finding about the
    metadata.
  mode: "report-only" for M0 and M1 (passed iff there is no problem; mismatches are reported), "enforcing" from M2
    on (passed iff there is no problem and no mismatch).
  entry = {"passed", "detail" (names the mode), "mode", "milestone", "evidence_sha256",
           "laws": {law_id: {"metadata", "computed", "missing", "max", "covered", "evidence_triage", "override",
                             "effective", "v1_triage"}},
           "mismatches": [{"law", "missing"}], "uncovered": [law ids],
           "divergences": [{"law", "v1_triage", "evidence_triage", "effective"}]  laws with a record whose effective
                          evidence triage differs from its v1 triage,
           "overrides": [{"law", "evidence_triage", "why"}], "problems": [str]}   lists sorted by law.
  computed = law_evidence levels, missing = sorted(metadata - computed), v1_triage = the record's "triage" (null
  without a record).

Registry: laws/M2/REGISTRY.json belongs to I15 (holon derive). Whenever it exists, its "evidence_sha256" equals
gen/M2/evidence.json's, as its "sorts_sha256" equals the frozen assignment's (I13).
"""
import hashlib
import json
import re
import unittest

from tests_m2._evidence import (ASSIGNMENT, BATCHDATA, DOCS, ENDPOINT_KINDS, EVIDENCE_VERSION, HEADER, ID_RE, LEVELS,
                                LEXICAL, OUT, ROLLUP, SCHEMA, STRENGTH, Run, action, at_where, atoms, canonical_sha256,
                                diagram, edge_tokens, edges, facts, find, has_node, morph_identifiers,
                                quoted_target_names, recovered, touches, versions, without)
from tests_m2._m2 import ROOT, holon_module, load_json, validate

CONTRACT = __doc__
COMMITS = ("commitBatch", "commitState", "commitBatchWithProof")
V01 = ["version", "batchIndex", "l1MessagePopped", "totalL1MessagePopped", "dataHash", "blobVersionedHash",
       "prevStateHash", "postStateHash", "withdrawRootHash", "sequencerSetVerifyHash", "parentBatchHash"]
LBN = "lastBlockNumber"
SSVH = "sequencerSetVerifyHash"


def minus(fields, *drop):
    return [f for f in fields if f not in drop]


def window_views() -> dict:
    """{stem: repo path} of M2's window views (I66, tests_m3/test_view_evidence.py rule V2), read here without holon/:
    every holon-facts/0.2 document directly under gen/M2/extracted/ whose extraction block names, in "declaration", a
    window declaration spec/M2/lib/window_*.json with window_version holon-window/0.1 and an existing abstraction."""
    decls = set()
    for p in sorted((ROOT / "spec" / "M2" / "lib").glob("window_*.json")):
        x = load_json(p)
        if (isinstance(x, dict) and x.get("window_version") == "holon-window/0.1"
                and isinstance(x.get("abstraction"), str) and (ROOT / x["abstraction"]).is_file()):
            decls.add(p.relative_to(ROOT).as_posix())
    out = {}
    for p in sorted((ROOT / "gen" / "M2" / "extracted").glob("*.json")):
        x = load_json(p)
        if (isinstance(x, dict) and x.get("facts_version") == "holon-facts/0.2"
                and (x.get("extraction") or {}).get("declaration") in decls):
            out[p.stem] = p.relative_to(ROOT).as_posix()
    return out


def at_where_in(doc: dict, model: str, edge: str, where: str):
    """at_where for any model of the document: the facts of a fact document from DOCS, of any other model (a window
    view, I66) from the document's own model entry."""
    if model in DOCS:
        return at_where(model, edge, where)
    f = load_json(ROOT / doc["models"][model]["facts"])
    if edge.startswith("LOAD.obs."):
        assert where == "body", where
        return f["observers"][edge[len("LOAD.obs."):]]["body"]
    kind, name = edge.split(".", 1)
    owner = next(a for a in f["actions"] if a["name"] == name) if kind == "TRANS" else f["migrations"][name]
    m = re.fullmatch(r"guards\[(\d+)\]\.(require|expr)", where)
    if m:
        return owner["guards"][int(m.group(1))][m.group(2)]
    m = re.fullmatch(r"effects\.(.+)", where)
    if m:
        return owner["effects"][m.group(1)]
    raise AssertionError(f"unknown position {where!r}")


class _Shared(unittest.TestCase):
    run_: Run = None

    @classmethod
    def setUpClass(cls):
        if _Shared.run_ is None:
            _Shared.run_ = Run(["--milestone", "M2"])

    @property
    def doc(self) -> dict:
        return _Shared.run_.need()


# ---------------------------------------------------------------- the frozen evidence set (construction)
class TestEvidenceFile(_Shared):
    def test_cli_writes_the_document_with_its_header(self):
        r = _Shared.run_
        self.assertEqual(r.code, 0, r.log)
        d = self.doc
        self.assertEqual(d["document"], "evidence")
        self.assertEqual(d["evidence_version"], EVIDENCE_VERSION)
        self.assertEqual(d["milestone"], "M2")
        self.assertEqual(d["levels"], STRENGTH)
        self.assertEqual(r.text, json.dumps(d, indent=2, sort_keys=True, ensure_ascii=False) + "\n", "render(doc)")
        # amended (I20, spec/M2/amendments.jsonl): besides the fact documents, one model per transitions document the
        # milestone adopts for derivation (spec/M2/lib/derive_extracted.json), with no diagram (anchors only)
        side = ROOT / "spec" / "M2" / "lib" / "derive_extracted.json"
        adopted = {}
        for rel in (load_json(side).get("documents") or []) if side.exists() else []:
            x = load_json(ROOT / rel)
            if x.get("facts_version") == "holon-facts/0.3" and (x.get("extraction") or {}).get("kind") == "transitions":
                adopted[rel.rsplit("/", 1)[-1][:-len(".json")]] = rel
        # amended (I66, spec/M2/amendments.jsonl; tests_m3/test_view_evidence.py rule V8): a window view of the
        # milestone (rule V2) may also have a model, keyed by its file stem, over its own diagram gen/M2/diagram/<stem>
        views = {m: rel for m, rel in window_views().items() if m in d["models"]}
        self.assertEqual(sorted(d["models"]), sorted([*DOCS, *adopted, *views]))
        for m, rel in adopted.items():
            with self.subTest(model=m):
                self.assertEqual((d["models"][m]["facts"], d["models"][m]["diagram"],
                                  d["models"][m]["facts_version"]), (rel, None, "holon-facts/0.3"))
                self.assertEqual([a for a in d["atoms"] if a["model"] == m], [])
        for m, rel in views.items():
            with self.subTest(model=m):
                mo = d["models"][m]
                self.assertEqual((mo["facts"], mo["facts_sha256"], mo["facts_version"], mo["diagram"]),
                                 (rel, hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), "holon-facts/0.2",
                                  f"gen/M2/diagram/{m}.json"))
        for m, rel in DOCS.items():
            with self.subTest(model=m):
                mo = d["models"][m]
                self.assertEqual(mo["facts"], rel)
                self.assertEqual(mo["facts_sha256"], hashlib.sha256((ROOT / rel).read_bytes()).hexdigest())
                self.assertEqual(mo["diagram"], f"gen/M2/diagram/{m}.json")

    def test_inputs_are_hashed_and_the_only_vocabulary_is_the_lexical_sidecar(self):
        d = self.doc
        paths = [i["path"] for i in d["inputs"]]
        self.assertEqual(paths, sorted(paths))
        got = {i["path"]: i["sha256"] for i in d["inputs"]}
        want = [*DOCS.values(), *(f"gen/M2/diagram/{m}.json" for m in DOCS), "gen/M2/sorts/assignment.json",
                "spec/M2/lib/evidence_lexical.json"]
        for rel in want:
            with self.subTest(input=rel):
                self.assertEqual(got.get(rel), hashlib.sha256((ROOT / rel).read_bytes()).hexdigest())
        # amended (I20, spec/M2/amendments.jsonl): the adoption sidecar and the extracted documents it lists
        allowed = re.compile(r"^(facts/[^/]+\.json|spec/M1/facts/[^/]+\.json|gen/M2/diagram/[^/]+\.json|"
                             r"gen/M2/sorts/assignment\.json|spec/(M[0-9]+/)?lib/[^/]+\.lib\.json|"
                             r"spec/M2/lib/evidence_lexical\.json|spec/M2/lib/derive_extracted\.json|"
                             r"spec/M2/facts/[^/]+\.extracted\.json)$")
        # amended (I66, spec/M2/amendments.jsonl; tests_m3/test_view_evidence.py rule V8): a window view the document
        # models, and its window declaration, which names the abstraction whose libraries it takes (rule V3)
        views = [rel for m, rel in window_views().items() if m in d["models"]]
        extra = set(views) | {load_json(ROOT / rel)["extraction"]["declaration"] for rel in views}
        self.assertEqual([p for p in paths if not allowed.match(p) and p not in extra], [],
                         "an input outside the frozen set")

    def test_evidence_and_sorts_hashes(self):
        d = self.doc
        self.assertRegex(d["evidence_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(d["evidence_sha256"], canonical_sha256(without(d, "evidence_sha256", "inputs")))
        self.assertEqual(d["sorts_sha256"], load_json(ROOT / "gen" / "M2" / "sorts" / "assignment.json")["sorts_sha256"])

    def test_document_validates_against_the_evidence_schema(self):
        self.assertTrue(SCHEMA.exists(), SCHEMA)
        self.assertEqual(validate(self.doc, SCHEMA), [])
        self.assertNotEqual(validate({"document": "evidence"}, SCHEMA), [], "the schema must reject a bare header")
        bad = json.loads(json.dumps(self.doc))
        bad["atoms"][0]["level"] = "E7"
        self.assertNotEqual(validate(bad, SCHEMA), [], "the schema must reject a level outside E1..E6")

    def test_atom_ids_endpoints_and_order(self):
        d = self.doc
        ids = [a["id"] for a in d["atoms"]]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), len(set(ids)))
        for a in d["atoms"]:
            with self.subTest(atom=a["id"]):
                m = ID_RE.match(a["id"])
                self.assertIsNotNone(m, a["id"])
                self.assertEqual((m["model"], m["level"], m["p"], m["q"]), (a["model"], a["level"], a["p"], a["q"]))
                self.assertEqual(m["h"], canonical_sha256(a["via"])[:8])
                es = edges(a["model"])
                for end in (a["p"], a["q"]):
                    self.assertIn(end, es)
                    e = es[end]
                    self.assertTrue(e["kind"] in ENDPOINT_KINDS or (e["kind"] == "LOAD" and e.get("observer")),
                                    f"{end} is not an endpoint (STORE/LOAD aggregates never are)")
                if a["level"] in ("E3", "E5"):
                    self.assertEqual(a["p"], a["q"], "located levels have p == q")
                if a["level"] in ("E4", "E6") or (a["level"] == "E1" and a["via"]["kind"] == "common_decoder"):
                    self.assertNotEqual(a["p"], a["q"])
                if a["level"] == "E6" or (a["level"] == "E1" and a["via"]["kind"] == "common_decoder"):
                    self.assertLess(a["p"], a["q"])
        uids = [u["id"] for u in d["unresolved"]]
        self.assertEqual(uids, sorted(uids))
        self.assertEqual(len(uids), len(set(uids)))
        for u in d["unresolved"]:
            self.assertEqual(u["id"], f"{u['model']}:unresolved:{u['p']}:{u['q']}:{u['carrier']}")
            self.assertIn(u["imprecise"], (["read"], ["write"], ["read", "write"]))

    def test_anchors_follow_the_diagrams(self):
        for m in DOCS:
            with self.subTest(model=m):
                an = self.doc["models"][m]["anchors"]
                es = edges(m)
                trans = sorted(i for i, e in es.items() if e["kind"] == "TRANS")
                self.assertEqual(an["trans"], trans)
                self.assertEqual(an["codec"], {e["model_fn"]: i for i, e in es.items() if e["kind"] == "CODEC"})
                self.assertEqual(an["actions"], {es[i]["component"]: i for i in trans})
                self.assertEqual(an["permissionless"], sorted(i for i in trans if es[i].get("permissionless")))
                self.assertEqual(an["observers"], {i[len("LOAD.obs."):]: i for i, e in es.items()
                                                   if e["kind"] == "LOAD" and e.get("observer")})
                reasons = {}
                for i in trans:
                    for g in es[i].get("guards", []):
                        if g.get("reason") is not None:
                            reasons.setdefault(str(g["reason"]), set()).add(i)
                self.assertEqual(an["reasons"], {k: sorted(v) for k, v in reasons.items()})
                acts = {es[i]["component"]: i for i in trans}
                sites = {s["id"]: sorted({acts[o["action"]] for o in s["occurrences"] if o["action"] in acts})
                         for s in load_json(ASSIGNMENT).get("sites", []) if s["model"] == m}
                self.assertEqual(an["sites"], sites, "anchors.sites follows the frozen assignment's sites")

    def test_two_runs_are_byte_identical_and_match_the_committed_file(self):
        """Exit (construction check): byte-identical regeneration, equal to the committed frozen set."""
        r = _Shared.run_
        self.assertEqual(r.code, 0, r.log)
        again = Run(["--milestone", "M2"])
        try:
            self.assertEqual(again.code, 0, again.log)
            self.assertEqual(r.text, again.text, "two runs differ")
            self.assertTrue(OUT.exists(), f"{OUT} is not committed")
            self.assertEqual(r.text, OUT.read_text(encoding="utf-8"), "the committed gen/M2/evidence.json is stale")
        finally:
            again.cleanup()

    def test_the_pass_holds_no_target_name(self):
        """Generic code: holon/diagram/evidence.py names no Morph identifier, even in docstrings; its only target
        vocabulary is spec/M2/lib/evidence_lexical.json (audit F-M2-14: names derived from the facts, not listed)."""
        src = (ROOT / "holon" / "diagram" / "evidence.py").read_text(encoding="utf-8")
        found = sorted(n for n in morph_identifiers() if re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", src))
        self.assertEqual(found, [])

    def test_the_pass_quotes_no_target_name(self):
        """Generic code, short names included (I13's rule for holon/sorts carried over): holon/diagram/evidence.py holds
        no target name as a string literal ("win", "lfi", "csr", "s_bvh", ...), so it cannot key a level on a carrier,
        field or action. The names are derived from the fact documents and libraries, minus the contract's own
        vocabulary (every identifier quoted in this module's docstring) and generic words (tests_m2/_evidence.py)."""
        src = (ROOT / "holon" / "diagram" / "evidence.py").read_text(encoding="utf-8")
        found = sorted(n for n in quoted_target_names(CONTRACT) if re.search(rf"[\"']{re.escape(n)}[\"']", src))
        self.assertEqual(found, [])

    def test_build_api_equals_the_cli(self):
        E = holon_module("holon.diagram.evidence")
        paths = [ROOT / rel for rel in sorted(DOCS.values())]
        self.assertEqual(E.render(E.build(paths, ROOT, milestone="M2")), _Shared.run_.text)
        self.assertEqual(E.EVIDENCE_VERSION, EVIDENCE_VERSION)
        self.assertEqual(tuple(E.LEVELS), LEVELS)
        self.assertEqual(E.STRENGTH, STRENGTH)


# ---------------------------------------------------------------- soundness on the Morph documents (construction)
class TestSoundness(_Shared):
    """Each atom is re-derived from the frozen inputs by an independent instrument (tests_m2/_evidence.py)."""

    def test_e1_atoms_equal_the_layout_algebra(self):
        d = self.doc
        fx = facts(HEADER)
        es = edges(HEADER)
        want = {}
        for e, ee in es.items():
            if ee.get("fn_kind") != "encoder":
                continue
            for dd, de in es.items():
                if de.get("fn_kind") != "decoder" or de["src"] != ee["tgt"]:
                    continue
                for v in sorted(set(versions(ee["version"])) & set(versions(de["version"]))):
                    rec, rest = recovered(fx, ee["model_fn"], de["model_fn"], v)
                    if rec:
                        want[(e, dd, v)] = {"kind": "inverse", "version": v, "fields": rec, "not_recovered": rest}
        got = {(a["p"], a["q"], a["via"]["version"]): a["via"] for a in atoms(d, "E1")
               if a["via"]["kind"] == "inverse"}
        self.assertEqual(got, want)
        for m in (ROLLUP, BATCHDATA):
            self.assertEqual(atoms(d, "E1", m), [], f"{m} has no CODEC edge")

    def test_e2_atoms_use_terms_of_the_diagram(self):
        for a in atoms(self.doc, "E2"):
            with self.subTest(atom=a["id"]):
                es = edges(a["model"])
                c = a["via"]["carrier"]
                w = {k for cc, k in es[a["p"]]["access"]["writes"] if cc == c}
                r = {k for cc, k in es[a["q"]]["access"]["reads"] if cc == c}
                self.assertTrue(a["via"]["writes"] and set(a["via"]["writes"]) <= w)
                self.assertTrue(a["via"]["reads"] and set(a["via"]["reads"]) <= r)
                self.assertEqual(a["via"]["writes"], sorted(a["via"]["writes"]))
                self.assertEqual(a["via"]["reads"], sorted(a["via"]["reads"]))

    def test_e3_and_e5_atoms_point_at_their_nodes(self):
        """Amended (I66, spec/M2/amendments.jsonl; tests_m3/test_view_evidence.py rule V8): an atom's facts are read
        through the document's model (at_where_in), so a window view's atoms are checked against the view too."""
        for a in atoms(self.doc, "E3") + atoms(self.doc, "E5"):
            with self.subTest(atom=a["id"]):
                v = a["via"]
                expr = at_where_in(self.doc, a["model"], a["p"], v["where"])
                op = "==" if a["level"] == "E3" else v["op"]
                self.assertTrue(has_node(expr, op, *v["operands"]), f"no {op} node {v['operands']} at {v['where']}")
                if a["level"] == "E3":
                    self.assertTrue(v["where"].endswith(".require"))
                else:
                    self.assertNotIn(" + ", v["sort"])
                    self.assertNotIn(v["sort"], ("Nat (unrefined)", "Bool"))
                    self.assertFalse(v["sort"].startswith("Mach("))

    def test_e6_atoms_equal_the_frozen_tokenizer(self):
        """Amended (I66, spec/M2/amendments.jsonl; tests_m3/test_view_evidence.py rule V8): the window views the
        document models are recomputed too, from their diagrams gen/M2/diagram/<stem>.json."""
        lex = load_json(LEXICAL)
        want = set()
        for m in [*DOCS, *(v for v in window_views() if v in self.doc["models"])]:
            es = edges(m)
            ids = sorted(i for i, e in es.items() if e["kind"] in ("CODEC", "TRANS"))
            for i, p in enumerate(ids):
                for q in ids[i + 1:]:
                    ep, eq = es[p], es[q]
                    if (ep["kind"], ep["src"], ep["tgt"]) != (eq["kind"], eq["src"], eq["tgt"]):
                        continue
                    shared = sorted(edge_tokens(ep, lex) & edge_tokens(eq, lex))
                    if shared:
                        want.add((m, p, q, tuple(shared)))
        got = {(a["model"], a["p"], a["q"], tuple(a["via"]["tokens"])) for a in atoms(self.doc, "E6")}
        self.assertEqual(got, want)


# ---------------------------------------------------------------- predictions on the Morph diagrams
class TestPredictions(_Shared):
    def inverse(self, enc: str, v: int) -> dict:
        hits = [a for a in find(self.doc, "E1", f"CODEC.{enc}", "CODEC.dec_go", HEADER) if a["via"]["version"] == v]
        self.assertEqual(len(hits), 1, f"one E1 inverse atom ({enc}, dec_go) at version {v}")
        return hits[0]["via"]

    def test_e1_on_the_codec_pairs_field_by_field(self):
        """I14-P1: (enc_sol, dec_go) and (enc_go_v1, dec_go) have E1 on all v0/v1 fields, operationalized per
        version: enc_sol is inverted by dec_go at versions 0, 1 and 2 on every active field except
        sequencerSetVerifyHash (enc_sol stores 32 zero bytes at 185); enc_go_v1 at version 1 and enc_go_v0 at version
        0 on every active field except version (Go writes the constant version byte)."""
        self.assertEqual(self.inverse("enc_sol", 0), {"kind": "inverse", "version": 0, "fields": minus(V01, SSVH),
                                                      "not_recovered": [SSVH]})
        for v in (1, 2):
            with self.subTest(version=v):
                self.assertEqual(self.inverse("enc_sol", v), {"kind": "inverse", "version": v,
                                                              "fields": minus(V01, SSVH) + [LBN],
                                                              "not_recovered": [SSVH]})
        self.assertEqual(self.inverse("enc_go_v1", 1), {"kind": "inverse", "version": 1,
                                                        "fields": minus(V01, "version") + [LBN],
                                                        "not_recovered": ["version"]})
        self.assertEqual(self.inverse("enc_go_v0", 0), {"kind": "inverse", "version": 0,
                                                        "fields": minus(V01, "version"), "not_recovered": ["version"]})

    def test_e1_common_decoder_atoms_and_none_at_version_2(self):
        """I14-P2: exactly 7 E1 atoms, all in morph_header: the 5 inverse atoms of I14-P1 and two common-decoder
        atoms, (enc_go_v0, enc_sol) at version 0 on the 9 fields both recover and (enc_go_v1, enc_sol) at version 1 on
        10; no E1 atom relates enc_sol and enc_go_v1 at version 2 (enc_go_v1 only writes version-1 headers)."""
        e1 = atoms(self.doc, "E1")
        self.assertEqual(len(e1), 7, [(a["p"], a["q"], a["via"]["version"]) for a in e1])
        self.assertTrue(all(a["model"] == HEADER for a in e1))
        common = {(a["p"], a["q"], a["via"]["version"]): a["via"] for a in e1 if a["via"]["kind"] == "common_decoder"}
        self.assertEqual(common, {
            ("CODEC.enc_go_v0", "CODEC.enc_sol", 0): {"kind": "common_decoder", "version": 0, "decoder": "CODEC.dec_go",
                                                      "fields": minus(V01, "version", SSVH)},
            ("CODEC.enc_go_v1", "CODEC.enc_sol", 1): {"kind": "common_decoder", "version": 1, "decoder": "CODEC.dec_go",
                                                      "fields": minus(V01, "version", SSVH) + [LBN]}})
        pair = {"CODEC.enc_sol", "CODEC.enc_go_v1"}
        self.assertEqual([a["id"] for a in e1 if {a["p"], a["q"]} == pair and a["via"]["version"] == 2], [])

    def test_e2_on_the_bvh_residue(self):
        """I14-P3: (commit*, revertBatch) have E2 on the BVH residue s_bvh: written via revertBatch (s_bvh := concat(
        es_bvh(moved), s_bvh), a precise whole write) and read via each commit (bvh_at at parent + 1): for each commit
        a, an E2 atom p = TRANS.revertBatch, q = TRANS.<a>, via {carrier s_bvh, writes ["*"], reads ["parent+1"]};
        none of these pairs is unresolved, and no E2 atom runs from a commit to revertBatch through s_bvh."""
        d = self.doc
        for a in COMMITS:
            with self.subTest(commit=a):
                hits = [x for x in find(d, "E2", "TRANS.revertBatch", f"TRANS.{a}", ROLLUP)
                        if x["via"]["carrier"] == "s_bvh"]
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0]["via"], {"carrier": "s_bvh", "writes": ["*"], "reads": ["parent+1"]})
                self.assertFalse([u for u in d["unresolved"] if (u["p"], u["q"], u["carrier"])
                                  == ("TRANS.revertBatch", f"TRANS.{a}", "s_bvh")])
                self.assertEqual([x["id"] for x in find(d, "E2", f"TRANS.{a}", "TRANS.revertBatch", ROLLUP)
                                  if x["via"]["carrier"] == "s_bvh"], [])

    def e3(self, act: str, where: str) -> list[dict]:
        return [a for a in find(self.doc, "E3", f"TRANS.{act}", f"TRANS.{act}", ROLLUP) if a["via"]["where"] == where]

    def test_previous_state_root_guards_give_e3(self):
        """I14-P4: the previous-state-root guards give E3: one atom at each reason-14 guard, in commitBatch
        (guards[19]), commitState (guards[18]) and commitBatchWithProof (guards[23]) at Rollup.sol:314, comparing
        w(lfi, win, parent).csr with prev, and in finalizeBatch (guards[9]) at Rollup.sol:635-638, comparing
        nth(fsr, idx - 1) with w(lfi, win, idx).prev."""
        prev314 = [["get", ["call", "w", "lfi", "win", "parent"], "csr"], "prev"]
        for act, i in (("commitBatch", 19), ("commitState", 18), ("commitBatchWithProof", 23)):
            with self.subTest(action=act):
                hits = self.e3(act, f"guards[{i}].require")
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0]["via"], {"where": f"guards[{i}].require", "reason": 14, "operands": prev314})
                self.assertEqual(hits[0]["src"], "contracts/contracts/l1/rollup/Rollup.sol:314")
        hits = self.e3("finalizeBatch", "guards[9].require")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["via"], {"where": "guards[9].require", "reason": 14, "operands": [
            ["call", "nth", "fsr", ["-", "idx", 1]], ["get", ["call", "w", "lfi", "win", "idx"], "prev"]]})
        self.assertEqual(hits[0]["src"], "contracts/contracts/l1/rollup/Rollup.sol:635-638")

    def test_the_e3_inventory(self):
        """I14-P5: exactly 9 E3 atoms, all in morph_rollup: the 4 of I14-P4; parent == lci at Rollup.sol:312 in the
        three commits; lfi + 1 == idx at :643 and qpend == btot - bn at L1MessageQueueWithGasPriceOracle.sol:325 in
        finalizeBatch. Comparisons with a literal or a parameter give none. Amended (I66, spec/M2/amendments.jsonl;
        tests_m3/test_view_evidence.py rule V8): the inventory is the fact documents' (DOCS), so "exactly 9" counts the
        fact documents' E3 atoms; once I66 models the window view the set holds 17 (I66-P2 predicts the view's 8 and
        checks them exactly)."""
        e3 = [a for a in atoms(self.doc, "E3") if a["model"] in DOCS]
        got = sorted((a["p"], a["via"]["where"], json.dumps(a["via"]["operands"]), a["src"]) for a in e3)
        r = "contracts/contracts/l1/rollup/Rollup.sol"
        prev314 = json.dumps([["get", ["call", "w", "lfi", "win", "parent"], "csr"], "prev"])
        want = sorted([
            ("TRANS.commitBatch", "guards[18].require", json.dumps(["parent", "lci"]), f"{r}:312"),
            ("TRANS.commitBatch", "guards[19].require", prev314, f"{r}:314"),
            ("TRANS.commitState", "guards[17].require", json.dumps(["parent", "lci"]), f"{r}:312"),
            ("TRANS.commitState", "guards[18].require", prev314, f"{r}:314"),
            ("TRANS.commitBatchWithProof", "guards[22].require", json.dumps(["parent", "lci"]), f"{r}:312"),
            ("TRANS.commitBatchWithProof", "guards[23].require", prev314, f"{r}:314"),
            ("TRANS.finalizeBatch", "guards[9].require", json.dumps(
                [["call", "nth", "fsr", ["-", "idx", 1]], ["get", ["call", "w", "lfi", "win", "idx"], "prev"]]),
             f"{r}:635-638"),
            ("TRANS.finalizeBatch", "guards[11].require", json.dumps([["+", "lfi", 1], "idx"]), f"{r}:643"),
            ("TRANS.finalizeBatch", "guards[14].require", json.dumps(["qpend", ["-", "btot", "bn"]]),
             "contracts/contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol:325")])
        self.assertEqual(got, want)
        self.assertTrue(all(a["model"] == ROLLUP for a in e3))

    def test_the_e4_inventory(self):
        """I14-P6: exactly 2 E4 atoms: commitBatch and commitBatchWithProof each recompute blob_hash(ver, blobs), a
        value the other stores in its new window entry (effects.win). Amended (I66, spec/M2/amendments.jsonl;
        tests_m3/test_view_evidence.py rule V8): the inventory is the fact documents' (DOCS), so "exactly 2" counts the
        fact documents' E4 atoms; once I66 models the window view the set holds 4 (I66-P2 predicts the view's 2 and
        checks them exactly)."""
        got = sorted((a["model"], a["p"], a["q"], a["via"]["fn"], tuple(a["via"]["stored"])) for a in atoms(self.doc, "E4")
                     if a["model"] in DOCS)
        self.assertEqual(got, [(ROLLUP, "TRANS.commitBatch", "TRANS.commitBatchWithProof", "blob_hash", ("effects.win",)),
                               (ROLLUP, "TRANS.commitBatchWithProof", "TRANS.commitBatch", "blob_hash", ("effects.win",))])

    def test_e5_at_the_signed_duration_site_and_not_at_the_ghost_tag_observer(self):
        """I14-P7: in each commit, E5 at the reason-16 guard (t <= W + cstart, both Time; Rollup.sol:363) and at the
        let prt (W + cstart - t, both Time; Rollup.sol:360-364), from I13's frozen assignment (t: Time, W: Dur,
        <commit>.cstart: Time); no E5 atom is located at LOAD.obs.tags_ok."""
        wplus = ["+", "W", "cstart"]
        for act, g, let in (("commitBatch", 23, 24), ("commitState", 22, 23), ("commitBatchWithProof", 27, 28)):
            with self.subTest(action=act):
                e5 = {a["via"]["where"]: a for a in find(self.doc, "E5", f"TRANS.{act}", f"TRANS.{act}", ROLLUP)}
                a = e5.get(f"guards[{g}].require")
                self.assertIsNotNone(a, sorted(e5))
                self.assertEqual(a["via"], {"where": f"guards[{g}].require", "op": "<=", "operands": ["t", wplus],
                                            "sort": "Time"})
                self.assertEqual(a["src"], "contracts/contracts/l1/rollup/Rollup.sol:363")
                b = e5.get(f"guards[{let}].expr")
                self.assertIsNotNone(b, sorted(e5))
                self.assertEqual(b["via"], {"where": f"guards[{let}].expr", "op": "-", "operands": [wplus, "t"],
                                            "sort": "Time"})
                self.assertEqual(b["src"], "contracts/contracts/l1/rollup/Rollup.sol:360-364")
        self.assertEqual([a["id"] for a in atoms(self.doc, "E5") if touches(a, "LOAD.obs.tags_ok")], [])

    def test_e6_between_the_header_encoders(self):
        """I14-P8: exactly 3 E6 atoms in morph_header, between the three encoders (parallel Header -> Bytes edges
        whose cited code names share tokens): (enc_go_v0, enc_go_v1) on batch, bytes, header; (enc_go_v0, enc_sol)
        and (enc_go_v1, enc_sol) on batch, header. dec_go has no parallel edge."""
        got = sorted((a["p"], a["q"], tuple(a["via"]["tokens"])) for a in atoms(self.doc, "E6", HEADER))
        self.assertEqual(got, [("CODEC.enc_go_v0", "CODEC.enc_go_v1", ("batch", "bytes", "header")),
                               ("CODEC.enc_go_v0", "CODEC.enc_sol", ("batch", "header")),
                               ("CODEC.enc_go_v1", "CODEC.enc_sol", ("batch", "header"))])

    def test_observer_reads_through_kindless_builtins_are_unresolved(self):
        """I14-P11 (part): no E2 atom ends at LOAD.obs.tags_ok, LOAD.obs.csr_last or LOAD.obs.new_hdr (each reads
        win only through a builtin that declares no access kind: tags_exact, win_last), and the unresolved list holds
        (TRANS.commitBatch, LOAD.obs.tags_ok, win) with imprecise ["read"]."""
        d = self.doc
        for o in ("LOAD.obs.tags_ok", "LOAD.obs.csr_last", "LOAD.obs.new_hdr"):
            with self.subTest(observer=o):
                self.assertEqual([a["id"] for a in atoms(d, "E2", ROLLUP) if a["q"] == o], [])
        hit = [u for u in d["unresolved"] if (u["model"], u["p"], u["q"], u["carrier"])
               == (ROLLUP, "TRANS.commitBatch", "LOAD.obs.tags_ok", "win")]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["imprecise"], ["read"])


def tearDownModule():
    if _Shared.run_ is not None:
        _Shared.run_.cleanup()
        _Shared.run_ = None


if __name__ == "__main__":
    unittest.main()
