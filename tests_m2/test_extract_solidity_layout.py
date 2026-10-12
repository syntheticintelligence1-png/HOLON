"""I17: Solidity frontend I, compile, AST/Yul walk, layouts (whitepaper §10.1, §10.2 calldatacopy, §8.3 facts 0.3;
BUILD_PLAN I17; parts of V10 and V17). This docstring is the contract that tests_m2/test_extract_solidity_layout.py
(Morph), tests_m2/test_extract_solidity_toy.py (the planted fixture), tests_m2/test_extract_solidity_honesty.py and
tests_m2/test_extract_toolchain.py read. tests_m2/_i17.py, tests_m2/fixtures/extract_solidity/ and
spec/M2/lib/extract_solidity.json are instruments fixed at the prereg.

Goal: the header layout of the Solidity commit path, derived from the compiler's AST and the Yul of its inline assembly
(the compiler's own parse and analysis of it, with external references resolved by the compiler), not transcribed.
Output: spec/M2/facts/morph_header.extracted.json (holon-facts/0.3), byte-identical across runs and covered by G1.

CLI (shared with I18: `python -m holon extract <frontend> ...`, the frontend named by the first argument)
  python -m holon extract solidity [--milestone M2] [--sidecar PATH] [--root DIR] [--source DIR] [--out PATH] [--check]
    Dispatch: holon/__main__.py sends argv[:1] == ["extract"] to holon.frontends.main(argv[1:]) before argparse (like
    `holon sorts`). holon.frontends.main(argv) takes argv[0] as the frontend name (it must match [a-z][a-z0-9_]*),
    imports holon.frontends.<name> and returns that module's main(argv[1:]); a missing argument, an argument starting
    with "-", a bad name or a module that does not exist (or has no main) is exit 2 with "unknown frontend <name>"
    on stderr, nothing written. No registry: I18's `holon extract go ...` reaches holon.frontends.go.main the same
    way, and holon/frontends/__init__.py names no frontend. Importing holon.frontends and dispatching open no file
    (the frontend's own main reads its inputs), so another frontend's audit hook sees nothing of the Solidity one.
    --sidecar  default <root>/spec/<M>/lib/extract_<frontend>.json; its "frontend" must equal the frontend argument.
    --root     the HOLON checkout (default: this one): config/holon.json and the default sidecar and output are read and
               written there. Paths in the output are relative to it ("<outside>/<file name>" for a sidecar outside it).
    --source   the target source tree; default config/holon.json extract.sources[<sidecar target.repo>].
    --out      default <root>/<sidecar "output">. --check writes nothing: it extracts in memory and exits 0 iff the file
               at --out (or the default output) holds exactly those bytes, 1 otherwise.
    Exit 0 written; 1 (--check only) differs or missing; 2 refused, nothing written: unknown frontend, malformed sidecar,
    solc missing or its sha256 differs from config replay.solc_sha256, solc --version not the sidecar's
    compiler.version, a source tree that is not a git checkout whose HEAD is the sidecar's target.commit (40 hex) or
    whose files that solc read from it carry uncommitted changes (commit null: no check, wherever the sidecar lives; it
    is used by the planted fixture and by scratch mutation copies, never by a committed target sidecar); 3 extraction
    error, named, nothing written: compile errors, entry not found or ambiguous, selected sink never reached, more than
    thresholds.max_paths_per_walk paths, an encoder length or a field-condition that is not expressible (J4), two ok paths
    with the same condition and different bytes (J4), a written field with two widths, or with two underlying terms on
    one path (N1). Output bytes: json.dumps(doc, indent=2, sort_keys=True) + "\\n"; no timestamp, no absolute path,
    no host name.

Sidecar (spec/<M>/lib/extract_<frontend>.json, the format of every sidecar G1 regenerates: sidecar_version, frontend,
doc, target {repo, commit (40 hex or null), scope}, output (repo-relative, ending ".extracted.json"); I18's Go sidecar
spec/M2/lib/go_frontend.json has its own format and is not one of these). Solidity keys: sources (source unit
names relative to --source), compiler {version, settings} (settings passed to solc verbatim, outputSelection added),
edges {name: {kind: "encoder" | "loader", from: the input type name ("Bytes" for a loader), input (loaders: the entry
parameter, as written), entry: {contract, function}, sink: [span, ...] (W10)}}. The frontend reads nothing else about
the target from HOLON: no fact document, no law, no result.

W. The walk (holon/frontends/solidity/{compile, ast, layout_extract}.py)
  W1 Compile. solc at config replay.solc (sha256 = replay.solc_sha256), `--standard-json`, base path = the source tree,
     include path = <config replay.sol_deps>/node_modules when that directory exists; input sources = the sidecar's
     units; settings = the sidecar's compiler.settings plus outputSelection {"*": {"": ["ast"]}} (AST only: no IR, no
     bytecode, no optimizer influence). The walker reads only solc's compact JSON AST of every unit (InlineAssembly nodes
     carry the Yul AST and externalReferences) and the bytes of every unit (spans, hashes). Not Slither, not z3.
  W2 Spans. "<unit>:<line>" or "<unit>:<lo>-<hi>": unit = solc's source unit name (repo-relative for the target:
     contracts/contracts/l1/rollup/Rollup.sol; the import path for an included dependency); lines 1-based, lo the line
     of the node's first byte and hi of its last (src "start:length:file", last byte start + max(length, 1) - 1). A
     stack is the list of spans of the FunctionCall nodes inlined from the entry's body down to the function that holds
     the node, then the node's own span.
  W3 Entry. The FunctionDefinition named by the edge's entry inside that contract (by name, declared there, exactly
     one, with a body). Its parameters are input terms ["param", name]; calldata struct members, `.length` of calldata
     bytes and constant-index access `x[k]` of calldata bytes are terms of their base (member, ["len", x],
     ["byte", x, k]); `x.offset` in Yul is the calldata offset of x.
  W4 Terms. Integer literals, hex literals, booleans (1/0), constants (a VariableDeclaration with constant: true and a
     constant initial value) and type conversions of constants fold to integers mod 2^256 (bytes32(0) is 0). A
     conversion between elementary types of the same or a larger size, and any implicit conversion, is the identity on
     terms; a narrowing conversion is ["trunc", bits, t]. State variables (and mappings, struct fields, array elements
     of storage), block/msg/tx members, blobhash, and the results of external calls are fresh environment terms. An
     operator on terms builds a term (constants folded with EVM semantics). Values of locals and parameters are
     immutable terms (assignment rebinds).
  W5 Memory. Every evaluation of mload(0x40) returns a pointer (r, 0) to a NEW region r whose cells are all unknown
     (Solidity memory at the free pointer is dirty: A-dirty); add/sub of a pointer and a constant is a pointer into the
     same region. mstore(p, v) writes 32 cells, mstore8(p, v) one (the low byte of v), calldatacopy(p, cdoffset(x) + k,
     n) writes n cells ["input", x, k..]; mstore(0x40, e) (the free-pointer update) writes no cell; mload(p) of a region
     is an opaque term; keccak256(p, n) is a sink event (W10) whose value is an opaque term. A write whose address is
     neither such a pointer nor 0x40 is debt "address" and havocs every region.
  W6 Solidity statements. Block, UncheckedBlock, ExpressionStatement, VariableDeclarationStatement (single or tuple, an
     uninitialized local is 0), Assignment (=, op=; to locals, return variables and tuples; an assignment to storage is
     evaluated for its right-hand side and writes nothing), IfStatement, Return, InlineAssembly, EmitStatement (no
     effect). Expressions: Identifier, Literal, MemberAccess, IndexAccess, BinaryOperation, UnaryOperation,
     TupleExpression, FunctionCall (require, revert, type conversions, struct constructors, internal and
     library-internal calls with a body, external calls). Anything else (loops, try, the conditional operator, inline
     assembly not covered by W7, modifiers on an inlined function, ...) is debt (D1).
  W7 Yul (InlineAssembly.AST). YulBlock, YulVariableDeclaration, YulAssignment, YulExpressionStatement, YulIdentifier
     (a Yul local, or an external reference to a Solidity local, parameter or return variable, `.offset`, `.length`),
     YulLiteral, YulFunctionCall of add, sub, mul, div, mod, and, or, xor, not, shl, shr, iszero, eq, lt, gt, mload,
     mstore, mstore8, calldatacopy, keccak256. Anything else (YulIf, YulSwitch, YulForLoop, YulFunctionDefinition,
     YulLeave/Break/Continue, other builtins) is debt (D1).
  W8 Calls. An internal or library-internal call with a body is inlined: arguments evaluated left to right, parameters
     bound by value, named return variables start at 0, a Return or the end of the body returns. Depth above
     thresholds.max_call_depth, or recursion, is debt "call". An external call returns a fresh environment term (no
     debt) unless it lies inside a store sequence (D2), where it is debt "call".
  W9 Branches. A condition is evaluated to a term (operands of && and || are evaluated as terms, without forking).
     It is decided when it folds to a constant, when it or its negation (["!", c], or c's operand when c = ["!", d]) is
     already a conjunct of the path, or when adding it makes the path infeasible (a conjunct and its negation, a
     constant-false conjunct, or the comparisons of one atom term with integer constants, ==, !=, <, <=, >, >= and
     their negations, admitting no integer in [0, 2^256)). Otherwise the path forks: IfStatement then-branch (c added)
     before else-branch (["!", c] added); require(c, msg) first forks a revert path (["!", c] added, outcome revert,
     reason msg, src the require call's span) and continues with c added; revert(msg) ends the path (outcome revert).
     The reason is the string literal argument, "" when absent.
  W10 Sinks. Every keccak256 evaluation is a sink event, recorded with its stack. The edge's selected sink is the event
     whose stack equals the sidecar's sink. A path that reaches the selected sink ends there, outcome ok; statements
     after it are not walked. A path that ends without reaching it, and without a revert, is "other".
  W11 Store sequence. The store sequence of an ok path is everything the path evaluates after the mload(0x40) that
     created the sink's region; its ops are the writes into that region in that interval, in order, with offsets
     relative to the sink pointer, each {"op", "offset", "width", "src", "origin": {"fn": "<Contract>.<function>" of the
     function whose Yul writes, "src": the Yul call's span, "stack"}}. The free-pointer update is not an op.
  W12 Budget. More than thresholds.max_paths_per_walk paths in one walk is exit 3.

N. Naming (fields come from the code, never from a fact document)
  N1 Field cells. A value bound to a formal parameter p of an inlined call is that formal's field value, named p with
     its leading underscores removed (the innermost formal wins when a formal is passed on), unless the argument folds
     to a constant (then it is that constant). A write of a field value v, of shl(8k, v) with 1 <= k <= 31, or of a
     constant gives cells; anything else written into a store sequence is debt "value" (the cells become unknown).
     mstore of v: field bytes 0..31 (width 32); mstore of shl(8k, v): field bytes 0..(31-k) then k zero bytes (width
     32 - k); mstore8 of v: field byte 0 (width 1); a constant: its big-endian bytes (the low byte for mstore8). The
     uniqueness checks concern written fields only (names some ok path's ops write into the sink's region; a formal
     that is never written there, such as a pointer or a length, is no field): one written name with two widths in one
     edge, or with two structurally different underlying terms on one path, is exit 3. Across paths one name may stand
     for different terms (a hash computed on two branches, a value read through two loader paths). A field value stays
     one through identity conversions and argument passing (re-named by each formal it reaches); everywhere else
     (conditions, lengths, offsets, operators other than a written shl) it is its underlying term, so the field
     identity never changes what a condition or length means.
  N2 The record. An encoder's input record (types[edge "from"]) lists every field that some ok path's ops write, in
     order of first appearance (paths in J order, ops in program order): {"name", "width", "value_type", "value_bits",
     "truncates"}. value_type is the typeString of the argument expression at the outermost call of the chain that binds
     the field's formal (an argument that is itself a formal of the calling function is followed out to that function's
     own call site, up to the entry); value_bits its bit size (uintN, intN: N; bytesN: 8N; address: 160; bool: 8; else
     null); truncates = value_bits > 8 * width.
  N3 Condition atoms. In an encoder edge, a term equal (structurally) to the underlying term of a written field on some
     ok path of the edge is that field's name (when a term underlies two names, the first in record order, N2); in a
     loader edge, ["len", x] and ["byte", x, k] of the edge's input are ["len", name] and
     ["byte", name, k] with name = the input parameter without leading underscores. Any other term is an environment
     atom.
  N4 Inputs. Loader cells and ops name the input the same way: {"input": name, "from", "len"}.

J. From walk to edge
  J1 Projection. A conjunct is an input conjunct iff all its atoms are field names (encoder) or the input's len/byte
     atoms (loader). An ok path keeps its input conjuncts, in walk order. A revert path belongs to the edge iff its
     failing conjunct (the one its require or branch added last) is an input conjunct; it keeps its input conjuncts.
     Other revert paths belong to the transition (I19), not to the edge (A-env).
  J2 Merging. Paths with equal (outcome, cond, reason, src, length, ops) are one path (first position kept). Two ok
     paths with equal ops and length whose conds are equal except at one position, where one holds c and the other
     ["!", c], merge into one without that conjunct (first position kept); repeat until nothing merges.
  J3 Order. Paths in walk order: depth first, then-branch before else-branch, a require's revert path before its
     continuation. "to" is "Maybe<Bytes>" iff the edge has a revert path, else "Bytes".
  J4 Well-formedness. The selected sink's address is a region pointer, every ok path's length is an integer or an
     input-only DSL expression and every op offset is an integer, else exit 3; two ok paths with equal cond and
     different (ops, length) is exit 3 (the bytes depend on the environment).
  J5 DSL. expr = integer | field name | ["len", name] | ["byte", name, k] | [op, expr, ...], op one of ==, !=, <, <=,
     >, >=, !, &&, ||, +, -, *, /, %, &, |, ^, <<, >> (Solidity operand order); comparisons keep the source's operand
     order; negation is ["!", c]; no other simplification.

D. Debt (§10.1: unsupported fragments are coverage debt, never approximated silently)
  D1 Every unsupported statement, expression or Yul construct is a debt entry {"kind": "loop" (For/While/DoWhile,
     YulForLoop) | "construct" | "address" | "value" | "call", "construct": the AST nodeType or Yul builtin, "src": its
     span, "fn": "<Contract>.<function>", "stack"} and havoc: every local, return variable or Yul variable it may
     assign becomes a fresh environment term, every region's cells become unknown; the path continues. The walk's debt
     (edge "walk"."debt") is every entry of every path, deduplicated, sorted by (stack, kind).
  D2 An edge's own debt ("debt") is the walk debt recorded inside the store sequence (W11) of one of its ok paths.
     "exact" is true iff it is empty.
  D3 The unsupported-Yul debt list of the plan is "debt" (store sequences) and "walk"."debt" (whole walk).

holon-facts/0.3 (spec/schemas/facts_0_3.schema.json: I17 writes it; this is its shape)
  {"facts_version": "holon-facts/0.3",
   "target": {"repo", "commit", "scope"} (the sidecar's),
   "extraction": {"method": "extracted", "frontend": "solidity", "frontend_version": "holon-frontend-solidity/0.1",
                  "sidecar": {"path", "sha256"}, "toolchain": {"solc": {"version": the text after "Version: " in
                  solc --version, "sha256"}}, "settings": the settings passed (outputSelection included),
                  "inputs": [{"unit", "sha256"}] for every unit in solc's output, sorted by unit},
   "types": {"Bytes": {"kind": "bytes"}, and per encoder edge its record: {"kind": "record", "fields": [N2]}},
   "functions": {<edge>: {"kind": "encoder" | "loader", "from", "to", "lang": "solidity-evm-memory",
                          "entry": {"fn", "src": the FunctionDefinition's span}, "sink": {"op": "keccak256",
                          "stack"}, "memory_init": "dirty",
                          "paths": [{"cond": [expr], "outcome": "ok", "length": expr, "ops": [op]} |
                                    {"cond": [expr], "outcome": "revert", "reason": str, "src": span}],
                          "debt": [debt], "exact": bool,
                          "walk": {"functions": [sorted "<Contract>.<function>" whose body was entered],
                                   "paths": {"ok", "revert", "other"} (counts before J1), "sinks": [{"op", "stack",
                                   "selected"}] sorted by stack, "debt": [debt]}}},
   "assumptions": [{"id": "A-dirty" | "A-env" | "A-implicit" | "A-width:<record>", "text"[, "record", "fields"]}]
     sorted by id: A-dirty when an edge has memory_init dirty; A-env and A-implicit always (implicit reverts of checked
     arithmetic, array bounds and ABI decoding are not partiality); A-width:<record> when fields of it truncate, with
     their names in record order}
  op = {"op": "mstore" | "mstore8" | "calldatacopy", "offset": int, "width": expr, "src": [item], "origin"};
  item = {"field": name, "from": int, "len": int} | {"zeros": int} | {"const": 0..255} | {"input": name, "from": int,
  "len": expr}, canonical: a run of zero bytes is one {"zeros": n}, a non-zero constant byte is one {"const": b}.
  Path, op, origin, item and debt objects admit no other key (the schema says additionalProperties false for them).
  The shared envelope (agreed with I18 at the prereg; this schema validates every holon-facts/0.3 document, Solidity
  and Go). Its top level is a oneOf of one branch per frontend, told apart by extraction.frontend (const), using only
  the mini-schema keywords:
    every branch: required facts_version (const "holon-facts/0.3"), target {repo, commit, scope}, extraction {method
    (const "extracted"), frontend, frontend_version, inputs (array)}; assumptions, when present, an array of objects
    with at least id and text (strings).
    "solidity": exactly the keys above plus types and functions, closed as described above (target.commit 40 hex or
    null; extraction exactly {method, frontend, frontend_version, sidecar, toolchain, settings, inputs}).
    "go" (I18's documents): exactly the keys facts_version, target, extraction, assumptions and go; target.commit 40
    hex; extraction admits further keys (I18's tool, config); inputs items are objects; "go" is an object this schema
    leaves open (I18's spec/schemas/facts_0_3_go.schema.json closes it). A frontend's content lives under its own
    keys, never in another frontend's ("functions" here means Solidity edges; Go functions live in go.functions).
    Any other frontend value is rejected; a later frontend adds its branch (additive).

Where it plugs in
  - holon/frontends/__init__.py (I17): FACTS_VERSION; Refused (exit 2) and ExtractionError (exit 3); main(argv) (the
    generic dispatch of the CLI section; holon.frontends.solidity.main parses the Solidity options); load_sidecar;
    sidecars(m, root) = sorted spec/<m>/lib/extract_*.json; extract(sidecar_path, root, source) -> document,
    dispatched on the sidecar's "frontend" to holon.frontends.<frontend>.extract_document(sidecar, sidecar_path, root,
    source) (named so that it cannot collide with I18's submodule holon/frontends/go/extract.py); render(doc) -> bytes;
    regenerate(m, root, tmp) -> (diffs, note): every sidecar of m extracted and compared byte for byte with
    <root>/<output>; a diff names the output path; the note names every output compared.
  - G1 (holon/gate.py regenerate_m2_outputs) calls holon.frontends.regenerate for M2+ and reports its diffs and note.
    It covers the extract_*.json sidecars, which in I17 is the Solidity one. I18's Go frontend has its own CLI and
    sidecar (spec/M2/lib/go_frontend.json, not an extract_*.json) and five outputs; its documents are not regenerated by
    G1 in I18 (lead decision at the prereg: G1 covers them from the first iteration that reads them as inputs).
  - holon.diagram.fact_documents(M) skips every spec/M*/facts/*.extracted.json: an extracted document is compared with
    the frozen facts and becomes a fact document only when a later iteration adopts it (I20); gen/M2/diagram,
    gen/M2/sorts, gen/M2/evidence.json and laws/M2 do not change because of it.
  - config/holon.json gains extract.sources {"morph-l2/morph": the replay.morph checkout} (generic key; the frontend
    code names no target).
  - tools/setup_env.sh --extract installs thresholds.tool_pins (slither-analyzer, crytic-compile, z3-solver) into a
    venv at ${HOLON_PREFIX:-~/.holon}/tools/extract from tools/extract-requirements.txt (every line name==version with
    --hash=sha256:..., installed with --require-hashes --only-binary=:all:), never into the repo. I17's extraction uses
    none of them (W1); the fallback if they cannot be installed is the plan's: I19 uses this AST walker without SlithIR.

Honesty (construction checks; AGENTS rules 2, 4, 5): no target identifier, revert text, span or layout constant in
holon/frontends (tests_m2/test_extract_solidity_honesty.py); the extraction opens no fact document, law, result or
generated file, and a copy whose frozen fact documents are poisoned extracts the same bytes; a scratch copy of the
pinned contracts with a store offset, a library length constant, the version bound and a store formal changed
(tests_m2/_i17.py MUTATION_EDITS, MUTATION_RENAME; its sidecar copy has commit null) extracts with exactly those
changes and nothing else; the sidecar states no field, offset, width or length.

Ownership: I17 owns holon/frontends/__init__.py, holon/frontends/solidity/, the extract dispatch in holon/__main__.py,
spec/schemas/facts_0_3.schema.json, the fact_documents skip, the frontends hook in G1, config extract.sources,
tools/setup_env.sh --extract, tools/extract-requirements.txt and spec/M2/facts/morph_header.extracted.json. I18 owns
holon/frontends/go/ (whose __init__.py exposes main), spec/schemas/facts_0_3_go.schema.json, spec/M2/lib/go_frontend.json
and the five spec/M2/facts/morph_*.go.extracted.json; it edits nothing I17 owns (if I17 has not landed in its worktree
it adds the minimal dispatch and skip its contract gives, and the lead keeps I17's at the merge). holon/gate.py is also
edited by I15 (derive regeneration in G1): expect a hand merge, additive on both sides.
"""
import hashlib
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2 import _i17 as H
from tests_m2._i16 import morph_checkout
from tests_m2._m2 import ROOT, copy_repo, holon_module, load_json, predictions, validate

R, V0, V1 = H.ROLLUP, H.V0, H.V1


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def thresholds() -> dict:
    return predictions("I17")["thresholds"]


class _Shared(unittest.TestCase):
    shared: H.Extract = None

    @classmethod
    def setUpClass(cls):
        if _Shared.shared is None:
            _Shared.shared = H.Extract(H.morph_args())

    @property
    def r(self) -> H.Extract:
        return _Shared.shared

    @property
    def doc(self) -> dict:
        self.assertEqual(self.r.code, 0, self.r.log)
        return self.r.doc()

    def edge(self, name: str) -> dict:
        e = self.doc.get("functions", {}).get(name)
        self.assertIsNotNone(e, f"the document has no edge {name}")
        return e


def spans_in(obj):
    """Every span-valued string of a document: entry src, sink and origin stacks, origin src, path src, debt."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("src",) and isinstance(v, str):
                yield v
            elif k == "stack" and isinstance(v, list):
                yield from v
            else:
                yield from spans_in(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from spans_in(v)


# ---------------------------------------------------------------------------------------------- construction
class TestDocument(_Shared):
    def test_cli_writes_the_document(self):
        self.assertEqual(self.r.code, 0, self.r.log)
        self.assertEqual(self.doc["facts_version"], H.FACTS_VERSION)
        self.assertEqual(sorted(self.doc["functions"]), ["enc_sol", "load_sol"])

    def test_header_toolchain_and_inputs(self):
        d, side, cfg = self.doc, load_json(H.SIDECAR), load_json(ROOT / "config" / "holon.json")
        self.assertEqual(d["target"], side["target"])
        x = d["extraction"]
        self.assertEqual((x["method"], x["frontend"], x["frontend_version"]), ("extracted", "solidity", H.FRONTEND_VERSION))
        self.assertEqual(x["sidecar"], {"path": H.SIDECAR_REL, "sha256": sha(H.SIDECAR)})
        self.assertEqual(x["toolchain"]["solc"]["sha256"], cfg["replay"]["solc_sha256"])
        self.assertTrue(x["toolchain"]["solc"]["version"].startswith(side["compiler"]["version"] + "+commit."),
                        x["toolchain"]["solc"])
        want_settings = dict(side["compiler"]["settings"], outputSelection={"*": {"": ["ast"]}})
        self.assertEqual(x["settings"], want_settings)
        units = [i["unit"] for i in x["inputs"]]
        self.assertEqual(units, sorted(units))
        morph = morph_checkout()
        for u in (R, V0, V1):
            self.assertIn(u, units)
        for i in x["inputs"]:
            if not i["unit"].startswith("@"):
                with self.subTest(unit=i["unit"]):
                    self.assertEqual(i["sha256"], sha(morph / i["unit"]))

    def test_document_validates_against_the_0_3_schema(self):
        self.assertTrue(H.SCHEMA.exists(), "spec/schemas/facts_0_3.schema.json is missing")
        self.assertEqual(validate(self.doc, H.SCHEMA), [])
        try:
            import jsonschema  # noqa: F401
        except ImportError:
            jsonschema = None
        if jsonschema is not None:
            jsonschema.validate(self.doc, load_json(H.SCHEMA))
        bad = json.loads(json.dumps(self.doc))
        bad["functions"]["enc_sol"]["paths"][0]["outcome"] = "maybe"
        self.assertNotEqual(validate(bad, H.SCHEMA), [], "the schema admits an unknown path outcome")
        bad = json.loads(json.dumps(self.doc))
        del bad["facts_version"]
        self.assertNotEqual(validate(bad, H.SCHEMA), [], "the schema admits a document without facts_version")
        bad = json.loads(json.dumps(self.doc))
        ok = next(p for p in bad["functions"]["enc_sol"]["paths"] if p["outcome"] == "ok")
        ok["ops"][0]["src"] = [{"bytes": "0x00"}]
        self.assertNotEqual(validate(bad, H.SCHEMA), [], "the schema admits an unknown src item")

    def test_the_0_3_schema_is_the_shared_envelope(self):
        """The schema is the envelope I18's Go documents validate against (agreed at the prereg): a Go-shaped document
        validates; the same document with another frontend, without its "go" object, with a top-level "functions"
        key, or without facts_version does not; an unknown frontend is rejected."""
        self.assertTrue(H.SCHEMA.exists(), "spec/schemas/facts_0_3.schema.json is missing")
        go = H.go_envelope_example()
        self.assertEqual(validate(go, H.SCHEMA), [], "the shared envelope rejects a Go-shaped document")
        for what, mutate in (("frontend solidity", lambda d: d["extraction"].update(frontend="solidity")),
                             ("unknown frontend", lambda d: d["extraction"].update(frontend="rust")),
                             ("no go object", lambda d: d.pop("go")),
                             ("a top-level functions key", lambda d: d.update(functions={})),
                             ("no facts_version", lambda d: d.pop("facts_version"))):
            with self.subTest(case=what):
                bad = json.loads(json.dumps(go))
                mutate(bad)
                self.assertNotEqual(validate(bad, H.SCHEMA), [], f"the schema admits a Go document with {what}")

    def test_canonical_bytes_no_absolute_path_no_time(self):
        b = self.r.bytes()
        self.assertEqual(b, H.canonical_bytes(json.loads(b)), "not json.dumps(indent=2, sort_keys=True) + newline")
        text = b.decode()
        for bad in ("/root/", "/home/", "/tmp/", "/usr/"):
            self.assertNotIn(bad, text)
        self.assertIsNone(re.search(r"\b20[0-9]{2}-[01][0-9]-[0-3][0-9]", text), "a date in the output")

    def test_two_runs_are_byte_identical_and_match_the_committed_file(self):
        """Exit (construction check): byte-identical across two runs; equal to the committed file."""
        again = H.Extract(H.morph_args())
        try:
            self.assertEqual(again.code, 0, again.log)
            self.assertEqual(self.r.bytes(), again.bytes(), "two extraction runs differ")
            self.assertTrue(H.OUTPUT.exists(), f"{H.OUTPUT_REL} is not committed")
            self.assertEqual(H.OUTPUT.read_bytes(), self.r.bytes(), f"the committed {H.OUTPUT_REL} is stale")
        finally:
            again.cleanup()

    def test_check_mode(self):
        p = H.run_holon(["extract", *H.morph_args(), "--check"])
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
        tmp = Path(tempfile.mkdtemp(prefix="holon-i17-check-"))
        try:
            stale = tmp / "x.json"
            stale.write_bytes(self.r.bytes()[:-2] + b"\n")
            q = H.run_holon(["extract", *H.morph_args(), "--check", "--out", str(stale)])
            self.assertEqual(q.returncode, 1, q.stdout[-2000:] + q.stderr[-2000:])
            self.assertEqual(stale.read_bytes(), self.r.bytes()[:-2] + b"\n", "--check wrote")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_edge_shapes_and_spans(self):
        d, morph = self.doc, morph_checkout()
        lines = {}
        for i in d["extraction"]["inputs"]:
            if not i["unit"].startswith("@"):
                lines[i["unit"]] = (morph / i["unit"]).read_text(encoding="utf-8").count("\n") + 1
        for name, e in d["functions"].items():
            with self.subTest(edge=name):
                self.assertEqual(e["lang"], "solidity-evm-memory")
                self.assertEqual(e["memory_init"], "dirty")
                self.assertEqual(e["exact"], e["debt"] == [])
                self.assertEqual(e["sink"], {"op": "keccak256", "stack": load_json(H.SIDECAR)["edges"][name]["sink"]})
                self.assertEqual(e["to"], "Maybe<Bytes>" if any(p["outcome"] == "revert" for p in e["paths"]) else "Bytes")
                for p in e["paths"]:
                    self.assertIn(p["outcome"], ("ok", "revert"))
                    if p["outcome"] == "ok":
                        self.assertEqual(sorted(p), ["cond", "length", "ops", "outcome"])
                    else:
                        self.assertEqual(sorted(p), ["cond", "outcome", "reason", "src"])
                sinks = [s["stack"] for s in e["walk"]["sinks"]]
                self.assertEqual(sinks, sorted(sinks))
                self.assertEqual([s["stack"] for s in e["walk"]["sinks"] if s["selected"]], [e["sink"]["stack"]])
                self.assertEqual(e["walk"]["functions"], sorted(set(e["walk"]["functions"])))
        for s in spans_in(d["functions"]):
            m = H.SPAN.match(s)
            self.assertIsNotNone(m, f"not a span: {s!r}")
            if m["unit"] in lines:
                self.assertLessEqual(int(m["hi"] or m["lo"]), lines[m["unit"]], s)
                self.assertLessEqual(int(m["lo"]), int(m["hi"] or m["lo"]), s)

    def test_assumptions(self):
        a = {x["id"]: x for x in self.doc["assumptions"]}
        self.assertEqual([x["id"] for x in self.doc["assumptions"]], sorted(a))
        self.assertEqual(set(a), {"A-dirty", "A-env", "A-implicit", "A-width:Header"})
        trunc = [f["name"] for f in self.doc["types"]["Header"]["fields"] if f["truncates"]]
        self.assertEqual((a["A-width:Header"]["record"], a["A-width:Header"]["fields"]), ("Header", trunc))


class TestDispatch(unittest.TestCase):
    """The shared CLI (agreed with I18 at the prereg): `holon extract <frontend> ...` goes to
    holon.frontends.<frontend>.main, with no registry, so I18's `holon extract go` works against I17's dispatch."""

    def test_the_dispatch_is_generic(self):
        import sys
        import types
        fe = holon_module("holon.frontends")
        name = "holon.frontends.zzi17probe"
        seen = []
        probe = types.ModuleType(name)
        probe.main = lambda argv: (seen.append(list(argv)), 7)[1]
        sys.modules[name] = probe
        try:
            self.assertEqual(fe.main(["zzi17probe", "--x", "1"]), 7)
            self.assertEqual(seen, [["--x", "1"]])
        finally:
            sys.modules.pop(name, None)

    def test_an_unknown_or_missing_frontend_is_refused(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i17-fe-"))
        try:
            for args in (["nosuchfrontend"], ["--frontend", "solidity"], []):
                with self.subTest(args=args):
                    p = H.run_holon(["extract", *args, "--out", str(tmp / "o.json")] if args else ["extract"])
                    self.assertEqual(p.returncode, 2, p.stdout[-1000:] + p.stderr[-1000:])
                    self.assertIn("unknown frontend", p.stderr)
                    self.assertFalse((tmp / "o.json").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestRefusals(unittest.TestCase):
    """Exit 2 (refused) and 3 (extraction error) write nothing."""

    def test_a_solc_whose_sha_differs_from_the_pin_is_refused(self):
        repo = copy_repo()
        try:
            cfg = repo / "config" / "holon.json"
            c = load_json(cfg)
            c["replay"]["solc_sha256"] = "0" * 64
            cfg.write_text(json.dumps(c, indent=2) + "\n")
            run = H.Extract(H.morph_args(), cwd=repo)
            self.assertEqual(run.code, 2, run.log)
            self.assertNotIn("usage:", run.stderr, "the CLI rejected the arguments: not a refusal")
            self.assertFalse(run.out.exists(), "a refused extraction wrote")
            run.cleanup()
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_a_source_tree_not_at_the_target_commit_is_refused(self):
        empty = Path(tempfile.mkdtemp(prefix="holon-i17-src-"))
        try:
            run = H.Extract([*H.morph_args(), "--source", str(empty)])
            self.assertEqual(run.code, 2, run.log)
            self.assertNotIn("usage:", run.stderr)
            self.assertFalse(run.out.exists())
            run.cleanup()
        finally:
            shutil.rmtree(empty, ignore_errors=True)

    def test_a_sink_never_reached_is_an_extraction_error_naming_the_edge(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i17-sink-"))
        try:
            side = load_json(H.SIDECAR)
            side["edges"]["enc_sol"]["sink"] = [f"{R}:358", f"{V0}:242"]
            p = tmp / "extract_solidity.json"
            p.write_text(json.dumps(side, indent=2) + "\n")
            run = H.Extract(["solidity", "--sidecar", str(p)])
            self.assertEqual(run.code, 3, run.log)
            self.assertIn("enc_sol", run.stdout + run.stderr)
            self.assertFalse(run.out.exists())
            run.cleanup()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestG1Coverage(unittest.TestCase):
    """G1 regenerates the extracted document and compares it byte for byte (BUILD_PLAN I17: covered by G1)."""

    def test_g1_regenerates_and_compares_the_extracted_facts(self):
        gate = holon_module("holon.gate")
        repo = copy_repo()
        try:
            tmp = repo.parent / "g1"
            diffs, note = gate.regenerate_m2_outputs("M2", repo, tmp)
            self.assertIn(H.OUTPUT_REL, note, f"G1 does not name the extracted facts: {note}")
            self.assertEqual([d for d in diffs if H.OUTPUT_REL in d], [], diffs)
            p = repo / H.OUTPUT_REL
            p.write_bytes(p.read_bytes().replace(b'"exact": true', b'"exact": false', 1))
            diffs2, _ = gate.regenerate_m2_outputs("M2", repo, repo.parent / "g1b")
            self.assertTrue(any(H.OUTPUT_REL in d for d in diffs2), f"a tampered extraction passes G1: {diffs2}")
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_frontends_regenerate_and_sidecars(self):
        fe = holon_module("holon.frontends")
        self.assertEqual(fe.FACTS_VERSION, H.FACTS_VERSION)
        self.assertIn(H.SIDECAR, [Path(p).resolve() for p in fe.sidecars("M2", ROOT)])
        tmp = Path(tempfile.mkdtemp(prefix="holon-i17-regen-"))
        try:
            diffs, note = fe.regenerate("M2", ROOT, tmp)
            self.assertEqual(diffs, [])
            self.assertIn(H.OUTPUT_REL, note)
            self.assertEqual(fe.render(load_json(H.OUTPUT)), H.OUTPUT.read_bytes())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestFactDocuments(unittest.TestCase):
    def test_extracted_documents_are_not_fact_documents(self):
        """holon.diagram.fact_documents skips *.extracted.json (I17's and I18's), so the diagram, sorts, evidence
        and derive inputs do not change."""
        diagram = holon_module("holon.diagram")
        repo = copy_repo()
        try:
            d = repo / "spec" / "M2" / "facts"
            d.mkdir(parents=True, exist_ok=True)
            for n in ("zz_planted.extracted.json", "zz_planted.go.extracted.json"):
                (d / n).write_text('{"facts_version": "holon-facts/0.3"}\n')
            docs = [p.relative_to(repo).as_posix() for p in diagram.fact_documents("M2", repo)]
            self.assertFalse([p for p in docs if p.endswith(".extracted.json")], docs)
            for want in ("facts/morph_header.json", "spec/M1/facts/morph_rollup.json", "spec/M1/facts/morph_batchdata.json"):
                self.assertIn(want, docs)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- predictions
VERSION_OPS = [  # (op, offset, src items, store function, call line, Yul line in its library)
    ("mstore8", 0, [{"field": "version", "from": 0, "len": 1}], "BatchHeaderCodecV0.storeVersion", 342, (V0, 133)),
    ("mstore", 1, [{"field": "batchIndex", "from": 0, "len": 8}, {"zeros": 24}], "BatchHeaderCodecV0.storeBatchIndex", 343, (V0, 144)),
    ("mstore", 9, [{"field": "l1MessagePopped", "from": 0, "len": 8}, {"zeros": 24}], "BatchHeaderCodecV0.storeL1MessagePopped", 344, (V0, 155)),
    ("mstore", 17, [{"field": "totalL1MessagePopped", "from": 0, "len": 8}, {"zeros": 24}], "BatchHeaderCodecV0.storeTotalL1MessagePopped", 345, (V0, 166)),
    ("mstore", 25, [{"field": "dataHash", "from": 0, "len": 32}], "BatchHeaderCodecV0.storeDataHash", 346, (V0, 175)),
    ("mstore", 57, [{"field": "blobVersionedHash", "from": 0, "len": 32}], "BatchHeaderCodecV0.storeBlobVersionedHash", 347, (V0, 184)),
    ("mstore", 89, [{"field": "prevStateHash", "from": 0, "len": 32}], "BatchHeaderCodecV0.storePrevStateHash", 348, (V0, 193)),
    ("mstore", 121, [{"field": "postStateHash", "from": 0, "len": 32}], "BatchHeaderCodecV0.storePostStateHash", 349, (V0, 202)),
    ("mstore", 153, [{"field": "withdrawRootHash", "from": 0, "len": 32}], "BatchHeaderCodecV0.storeWithdrawRootHash", 350, (V0, 211)),
    ("mstore", 185, [{"zeros": 32}], "BatchHeaderCodecV0.storeSequencerSetVerifyHash", 351, (V0, 220)),
    ("mstore", 217, [{"field": "parentBatchHash", "from": 0, "len": 32}], "BatchHeaderCodecV0.storeParentBatchHash", 352, (V0, 229)),
    ("mstore", 249, [{"field": "lastBlockNumber", "from": 0, "len": 8}, {"zeros": 24}], "BatchHeaderCodecV1.storeLastBlockNumber", 354, (V1, 56)),
]
ENC_FUNCTIONS = sorted(
    ["Rollup._commitBatchWithBatchData", "Rollup._loadBatchHeader", "Rollup._getBatchVersion", "Rollup._commitBatch",
     "Rollup._loadL1MessageHashes", "BatchHeaderCodecV0.loadAndValidate", "BatchHeaderCodecV1.loadAndValidate",
     "BatchHeaderCodecV0.computeBatchHash", "BatchHeaderCodecV0.getBatchIndex", "BatchHeaderCodecV0.getTotalL1MessagePopped"]
    + sorted({f for _, _, _, f, _, _ in VERSION_OPS}))
LOAD_FUNCTIONS = sorted(["Rollup._loadBatchHeader", "Rollup._getBatchVersion", "BatchHeaderCodecV0.loadAndValidate",
                         "BatchHeaderCodecV1.loadAndValidate", "BatchHeaderCodecV0.computeBatchHash"])
HEADER = [("version", 1, "uint8", 8, False), ("batchIndex", 8, "uint256", 256, True),
          ("l1MessagePopped", 8, "uint16", 16, False), ("totalL1MessagePopped", 8, "uint256", 256, True),
          ("dataHash", 32, "bytes32", 256, False), ("blobVersionedHash", 32, "bytes32", 256, False),
          ("prevStateHash", 32, "bytes32", 256, False), ("postStateHash", 32, "bytes32", 256, False),
          ("withdrawRootHash", 32, "bytes32", 256, False), ("parentBatchHash", 32, "bytes32", 256, False),
          ("lastBlockNumber", 8, "uint64", 64, False)]
LEN = ["len", "batchHeader"]
B0 = ["byte", "batchHeader", 0]


def version_ops(n: int) -> list[dict]:
    return [{"op": op, "offset": off, "width": 32 if op == "mstore" else 1, "src": src,
             "origin": {"fn": fn, "src": f"{u}:{y}", "stack": [f"{R}:{call}", f"{u}:{y}"]}}
            for op, off, src, fn, call, (u, y) in VERSION_OPS[:n]]


def canon_set(paths) -> list[str]:
    return sorted(json.dumps(p, sort_keys=True) for p in paths)


class TestPredictions(_Shared):
    def _selector_and_widths(self, e: dict) -> tuple[str, dict]:
        heads = set()
        for p in e["paths"]:
            if p["outcome"] == "ok":
                c = H.path_layout(p)[0]
                heads.add(c[1] if c[0] == "field" and c[2] == 0 else None)
        self.assertEqual(len(heads), 1, f"byte 0 is not the same field on every ok path: {heads}")
        sel = heads.pop()
        self.assertIsNotNone(sel, "byte 0 of enc_sol is not a field")
        return sel, H.field_widths(self.doc, e["from"])

    def test_enc_sol_layout_equals_the_frozen_layout_per_version_modulo_field_names(self):
        """I17-P1: for versions 0, 1 and 2 the extracted enc_sol layout has the frozen layout's length and, cell for cell,
        the same state: a constant where the frozen facts hold that constant (the 32 zero bytes at 185, the
        sequencerSetVerifyHash obstruction of L_par_hdr_ssvh), no unknown byte, and a field byte where they hold a
        field byte, with the same byte index, under a bijective renaming of field names."""
        e = self.edge("enc_sol")
        sel, w = self._selector_and_widths(e)
        mapping = {}
        for v in (0, 1, 2):
            with self.subTest(version=v):
                got, want = H.layout_at(e, w, sel, v), H.frozen_layout(v)
                self.assertIsNotNone(got, f"no ok path at version {v}")
                self.assertEqual(len(got), len(want), f"version {v}: length")
                for i, (g, f) in enumerate(zip(got, want)):
                    if g[0] == "field" and f[0] == "field":
                        self.assertEqual(g[2], f[2], f"version {v}, byte {i}: {g} vs {f}")
                        self.assertEqual(mapping.setdefault(g[1], f[1]), f[1], f"version {v}, byte {i}: renaming")
                    else:
                        self.assertEqual(g, f, f"version {v}, byte {i}")
        self.assertEqual(len(set(mapping.values())), len(mapping), f"not a bijection: {mapping}")
        self.assertEqual([c for c in H.frozen_layout(0)[185:217]], [["const", 0]] * 32)

    def test_extracted_field_names_are_the_frozen_names(self):
        """I17-P2: the renaming of I17-P1 is the identity: naming a field after the store function's formal parameter
        without its leading underscore (N1) gives exactly the frozen field names, so the layouts are equal as written."""
        e = self.edge("enc_sol")
        w = H.field_widths(self.doc, e["from"])
        for v in (0, 1, 2):
            with self.subTest(version=v):
                self.assertEqual(H.layout_at(e, w, "version", v), H.frozen_layout(v))

    def test_enc_sol_is_partial_exactly_on_three_field_conditions(self):
        """I17-P3: enc_sol is a Maybe<Bytes> encoder whose revert paths are exactly the three field-only requires before
        the sink: version <= 2 ("invalid version", :293), prevStateHash != 0 (:294) and postStateHash != 0 (:295). For
        every version byte 3..255 it is None (the frozen domain version_le 2 agrees); for versions 0..2 it is None when
        either state root is zero, which the frozen enc_sol (defined for every header of version <= 2) does not state:
        the frozen M0 witness of L_par_hdr_v2 (both roots zero) lies outside the extracted domain, the witness of
        L_par_hdr_ssvh (all bytes 0xff) inside."""
        e = self.edge("enc_sol")
        self.assertEqual(e["to"], "Maybe<Bytes>")
        want = [
            {"cond": [["!", ["<=", "version", 2]]], "outcome": "revert", "reason": "invalid version", "src": f"{R}:293"},
            {"cond": [["<=", "version", 2], ["!", ["!=", "prevStateHash", 0]]], "outcome": "revert",
             "reason": "previous state root is zero", "src": f"{R}:294"},
            {"cond": [["<=", "version", 2], ["!=", "prevStateHash", 0], ["!", ["!=", "postStateHash", 0]]],
             "outcome": "revert", "reason": "new state root is zero", "src": f"{R}:295"}]
        self.assertEqual(canon_set(p for p in e["paths"] if p["outcome"] == "revert"), canon_set(want))
        w = H.field_widths(self.doc, e["from"])
        fz = H.frozen()
        zero = {f["name"]: bytes(f["width"]) for f in fz["types"]["Header"]["fields"]}
        for v in range(3, 256):
            self.assertTrue(H.reverts_at(e, "version", v), f"version {v} does not revert")
            self.assertIsNone(H.layout_at(e, w, "version", v), f"version {v} has an ok path")
            self.assertFalse(H.frozen_encodes(dict(zero, version=bytes([v]))), f"frozen enc_sol defined at {v}")
        reverts = [p for p in e["paths"] if p["outcome"] == "revert"]
        for v in (0, 1, 2):
            for root in ("prevStateHash", "postStateHash"):
                vals = {f: 1 for f in w}
                vals.update(version=v, **{root: 0})
                self.assertTrue(any(H.holds(p["cond"], vals) for p in reverts), (v, root))
                hdr = {f["name"]: bytes([1]) * f["width"] for f in fz["types"]["Header"]["fields"]}
                hdr.update(version=bytes([v]), **{root: bytes(32)})
                self.assertTrue(H.frozen_encodes(hdr), "the frozen enc_sol is defined on a zero root")
        v2 = H.m0_witness("L_par_hdr_v2")
        ss = H.m0_witness("L_par_hdr_ssvh")
        self.assertTrue(any(H.holds(p["cond"], H.fields_env(w, v2)) for p in reverts), "the v2 witness is in the domain")
        self.assertFalse(any(H.holds(p["cond"], H.fields_env(w, ss)) for p in reverts), "the ssvh witness reverts")
        self.assertTrue(any(H.holds(p["cond"], H.fields_env(w, ss)) for p in e["paths"] if p["outcome"] == "ok"))

    def test_store_sequences_carry_no_debt(self):
        """I17-P4 (the plan's prediction): the unsupported-Yul debt list is empty for the store sequences: enc_sol and
        load_sol each have debt [] and exact true."""
        for name in ("enc_sol", "load_sol"):
            with self.subTest(edge=name):
                e = self.edge(name)
                self.assertEqual(e["debt"], [])
                self.assertIs(e["exact"], True)

    def test_walk_debt_is_exactly_the_message_hash_loop(self):
        """I17-P5: the whole enc_sol walk records exactly one debt entry, the for loop of _loadL1MessageHashes
        (Rollup.sol:936-943, reached through _commitBatch at :318-322 and :879), outside the store sequence; the
        load_sol walk records none."""
        self.assertEqual(self.edge("enc_sol")["walk"]["debt"], [
            {"kind": "loop", "construct": "ForStatement", "src": f"{R}:936-943", "fn": "Rollup._loadL1MessageHashes",
             "stack": [f"{R}:318-322", f"{R}:879", f"{R}:936-943"]}])
        self.assertEqual(self.edge("load_sol")["walk"]["debt"], [])

    def test_walk_inventory(self):
        """I17-P6: the enc_sol walk enters exactly 22 functions (the entry, the parent-header loader chain, the two
        getters, _commitBatch and _loadL1MessageHashes, and the 12 store functions of BatchHeaderCodecV0/V1), reaches
        exactly 3 keccak256 sinks (the parent header's hash via :309 and :849, the data hash at :883 via :318-322, and
        the selected one via :357) and counts 8 ok, 15 revert and 0 other paths before projection; the load_sol walk
        enters 5 functions, reaches 1 sink and counts 2 ok, 4 revert, 0 other."""
        enc, load = self.edge("enc_sol")["walk"], self.edge("load_sol")["walk"]
        self.assertEqual(enc["functions"], ENC_FUNCTIONS)
        self.assertEqual(len(enc["functions"]), 22)
        self.assertEqual(canon_set(enc["sinks"]), canon_set([
            {"op": "keccak256", "stack": [f"{R}:309", f"{R}:849", f"{V0}:242"], "selected": False},
            {"op": "keccak256", "stack": [f"{R}:318-322", f"{R}:883"], "selected": False},
            {"op": "keccak256", "stack": [f"{R}:357", f"{V0}:242"], "selected": True}]))
        self.assertEqual(enc["paths"], {"ok": 8, "revert": 15, "other": 0})
        self.assertEqual(load["functions"], LOAD_FUNCTIONS)
        self.assertEqual(load["sinks"], [{"op": "keccak256", "stack": [f"{R}:849", f"{V0}:242"], "selected": True}])
        self.assertEqual(load["paths"], {"ok": 2, "revert": 4, "other": 0})

    def test_enc_sol_ok_paths_and_their_ops(self):
        """I17-P7: enc_sol has exactly two ok paths after J1-J2, told apart by version >= 1 alone (the :333 and :353
        conditions coincide; the l1MessagePopped == 0 early return of _loadL1MessageHashes merges away; no environment
        conjunct survives): version >= 1 with length 257 and 12 ops (one mstore8, eleven mstore: the 11 BatchHeaderCodecV0
        store functions called at :342-352, then BatchHeaderCodecV1.storeLastBlockNumber at :354), and !(version >= 1)
        with length 249 and the first 11 of them; the constant zeros at 185 come from bytes32(0) at :351; the free-pointer
        update at :338 is no op."""
        e = self.edge("enc_sol")
        oks = [p for p in e["paths"] if p["outcome"] == "ok"]
        pre = [["<=", "version", 2], ["!=", "prevStateHash", 0], ["!=", "postStateHash", 0]]
        self.assertEqual(canon_set(oks), canon_set([
            {"cond": pre + [[">=", "version", 1]], "outcome": "ok", "length": 257, "ops": version_ops(12)},
            {"cond": pre + [["!", [">=", "version", 1]]], "outcome": "ok", "length": 249, "ops": version_ops(11)}]))

    def test_load_sol_partiality_equals_the_frozen_ok_sol(self):
        """I17-P8: load_sol (Rollup._loadBatchHeader) has exactly 2 ok and 4 revert paths ("Empty batch header" :825,
        "batch header length too small" V0:32, "batch header length is incorrect" V1:35, "Unsupported batch version"
        :844), and on every first byte 0..255 and length in thresholds.loader_grid_lengths it is defined exactly where the
        frozen ok_sol is true."""
        e = self.edge("load_sol")
        self.assertEqual(e["to"], "Maybe<Bytes>")
        rev = {(p["reason"], p["src"]) for p in e["paths"] if p["outcome"] == "revert"}
        self.assertEqual(rev, {("Empty batch header", f"{R}:825"), ("batch header length too small", f"{V0}:32"),
                               ("batch header length is incorrect", f"{V1}:35"), ("Unsupported batch version", f"{R}:844")})
        self.assertEqual(sum(p["outcome"] == "revert" for p in e["paths"]), 4)
        self.assertEqual(sum(p["outcome"] == "ok" for p in e["paths"]), 2)
        for length in thresholds()["loader_grid_lengths"]:
            for b0 in (range(256) if length else [0]):
                b = (bytes([b0]) + bytes(length - 1)) if length else b""
                got = H.loader_outcome(e, "batchHeader", b0, length)["outcome"] == "ok"
                self.assertEqual(got, H.frozen_ok_sol(b), f"first byte {b0}, length {length}")

    def test_load_sol_layout_is_the_calldata_copy(self):
        """I17-P9: each load_sol ok path holds exactly one op, a calldatacopy at offset 0 of the whole input
        (width and length ["len", "batchHeader"]), from BatchHeaderCodecV0.loadAndValidate (V0:36 via :839) for
        first byte 0 and BatchHeaderCodecV1.loadAndValidate (V1:39 via :842) for first byte 1 or 2; on the grid its
        cells are ["input", "batchHeader", k] for every k < length (§10.2: positions map to calldata)."""
        e = self.edge("load_sol")
        ops = {}
        for p in e["paths"]:
            if p["outcome"] == "ok":
                self.assertEqual(p["length"], LEN)
                self.assertEqual(len(p["ops"]), 1, p["ops"])
                ops[p["ops"][0]["origin"]["fn"]] = p["ops"][0]
        mk = lambda fn, y, call: {"op": "calldatacopy", "offset": 0, "width": LEN,  # noqa: E731
                                  "src": [{"input": "batchHeader", "from": 0, "len": LEN}],
                                  "origin": {"fn": fn, "src": y, "stack": [call, y]}}
        self.assertEqual(ops, {"BatchHeaderCodecV0.loadAndValidate": mk("BatchHeaderCodecV0.loadAndValidate", f"{V0}:36", f"{R}:839"),
                               "BatchHeaderCodecV1.loadAndValidate": mk("BatchHeaderCodecV1.loadAndValidate", f"{V1}:39", f"{R}:842")})
        for length in thresholds()["loader_grid_lengths"]:
            for b0 in (0, 1, 2, 3, 255):
                if not length:
                    continue
                p = H.loader_outcome(e, "batchHeader", b0, length)
                if p["outcome"] == "ok":
                    self.assertEqual(H.path_layout(p, {("len", "batchHeader"): length}),
                                     [["input", "batchHeader", k] for k in range(length)], (b0, length))

    def test_header_record_and_width_obligations(self):
        """I17-P10: the Header record holds 11 fields, the frozen Header fields in the frozen order with the frozen
        widths minus sequencerSetVerifyHash (the code stores the constant bytes32(0), so no input reaches byte 185); the
        fields whose value type is wider than the stored width (A-width:Header) are exactly batchIndex and
        totalL1MessagePopped (uint256 locals), while version (uint8), l1MessagePopped (uint16) and lastBlockNumber
        (uint64) fit: the frozen A-width/A-version name five fields."""
        got = [(f["name"], f["width"], f["value_type"], f["value_bits"], f["truncates"])
               for f in self.doc["types"]["Header"]["fields"]]
        self.assertEqual(got, HEADER)
        fz = [(f["name"], f["width"]) for f in H.frozen()["types"]["Header"]["fields"] if f["name"] != "sequencerSetVerifyHash"]
        self.assertEqual([(n, w) for n, w, *_ in got], fz)
        a = next(x for x in self.doc["assumptions"] if x["id"] == "A-width:Header")
        self.assertEqual(a["fields"], ["batchIndex", "totalL1MessagePopped"])


def tearDownModule():
    if _Shared.shared is not None:
        _Shared.shared.cleanup()
        _Shared.shared = None


if __name__ == "__main__":
    unittest.main()
