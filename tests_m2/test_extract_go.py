"""I18: the Go frontend. Codecs with their partiality, slice backing identities, call-chain skeletons from producers
to consumers, and loop bounds as fuel annotations, extracted from go/ssa (whitepaper §10.1 Go, all four bullets;
§8.3; BUILD_PLAN I18; part of V10). This docstring is the contract every tests_m2/test_extract_go*.py module reads;
tests_m2/_i18.py, tests_m2/fixtures/go_frontend/ and spec/M2/lib/go_frontend.json are instruments and inputs fixed
at the I18 prereg.

Ownership (I17 and I18 are built in parallel; the lead merges)
  I18 owns holon/frontends/go/ (ssadump/{main.go, go.mod, go.sum}, __init__.py, extract.py and any further module of
  its own), spec/schemas/facts_0_3_go.schema.json, the five outputs spec/M2/facts/morph_{batch, blob, derivation,
  genesis, nodetypes}.go.extracted.json and docs/iterations/I18.md.
  I17 owns spec/schemas/facts_0_3.schema.json (the shared holon-facts/0.3 envelope), holon/frontends/__init__.py,
  the `extract` dispatch in holon/__main__.py and the one-line exclusion in holon.diagram.fact_documents (below).
  If I17's part has not landed when I18 builds, the I18 builder adds exactly these, each in its own hunk (the lead
  keeps I17's versions at the merge; they behave the same way):
    holon/__main__.py: `if argv[:1] == ["extract"]: from .frontends import main as frontends_main;
                        return frontends_main(argv[1:])` (early dispatch, next to "evidence"), one docstring line;
    holon/frontends/__init__.py: main(argv) that takes argv[0] as the frontend name ([a-z][a-z0-9_]*), imports
                        holon.frontends.<name> and returns its main(argv[1:]); a missing, option-like or unknown name
                        (no such module, or no main) is exit 2 with "unknown frontend <name>" on stderr. No registry,
                        no frontend named, no file opened before the dispatch (agreed with I17 at the prereg);
    holon/diagram/__init__.py fact_documents: files whose name ends in ".extracted.json" are not fact documents
                        (frontend outputs are linked into the model by I19/I20, never read as hand-shaped facts).
  So holon/frontends/go/__init__.py exposes main (re-exported from extract.py): `holon extract go ...` reaches it.
  Shared holon-facts/0.3 envelope (agreed with I17 at the prereg; I17's spec/schemas/facts_0_3.schema.json has a "go"
  branch for it): required keys facts_version == "holon-facts/0.3", target {repo, commit (40 hex), scope}, extraction
    {method: "extracted", frontend: "go", frontend_version, inputs: [objects], plus I18's own tool and config}; assumptions
    [{id, text}]; and all Go content under the one top-level key "go", an object the envelope leaves open and the
    frontend's own schema closes. A Go document has exactly the keys facts_version, target, extraction, assumptions and
    go (no top-level "functions": that key is Solidity's codec edges). Whenever spec/schemas/facts_0_3.schema.json
    exists, every Go document validates against it. G1 does not regenerate the Go documents in I18 (lead decision at
    the prereg; G1 covers them from the first iteration that reads them as inputs); TestExtraction compares them with
    the committed files.

CLI
  python -m holon extract go [--milestone M2] [--root DIR] [--config PATH] [--src DIR] [--out-dir DIR]
                             [--doc STEM ...]
    --root     repository root (default: this checkout). Inputs read from it: --config and, when the config's
               "source" names one, the JSON file holding the source path. Nothing else under the root is read.
    --config   default <root>/spec/<milestone>/lib/go_frontend.json (format below).
    --src      the Go source tree. Default: the config's "source": {"path": P} is <root>/P; {"config": C, "key":
               [k1, ...]} is the value at that key path in the JSON file <root>/C.
    --out-dir  default <root>/spec/<milestone>/facts. Writes <out-dir>/<stem>.go.extracted.json for every document
               of the config, or only for the --doc stems, as render(doc) = json.dumps(doc, indent=1,
               sort_keys=True, ensure_ascii=False) + "\n". Every package of every document is loaded and analyzed
               in every run, so a document's bytes do not depend on --doc.
    Exit 0 on success. Exit 2, writing nothing (all documents are rendered before any is written), when the go
    toolchain is missing or is not the pinned version (config/holon.json replay.go_version), the helper cannot be
    built, a package does not load or type-check, or an input is missing or malformed. Two runs on the same inputs
    write identical bytes. Commit the five Morph documents.
  API (holon.frontends.go.extract): FRONTEND_VERSION == "holon-go/0.1"; main(argv) -> int; extract(config_path,
  src, root=None) -> {stem: doc}; render(doc) -> str.

Config (spec/M2/lib/go_frontend.json; the toy's is tests_m2/fixtures/go_frontend/toy_config.json)
  {"config_version": "holon-go-frontend/0.1", "doc", "target": {"repo", "commit"}, "source": {"path"} | {"config",
   "key"}, "documents": {stem: [import path, ...]}, "primitives": {qualified Go name: {"kind": "to_array" | "hash" |
   "array_bytes", "width"?: n, "text"}}, "limits": {"max_paths", "inline_depth", "flow_depth"}}
  It is the only target vocabulary of the frontend. A primitive is a function outside the analyzed packages whose
  semantics the config declares: to_array (the result is an n-byte array; for an n-byte argument, element k is
  argument byte k), hash (an opaque digest; a HASH sink), array_bytes (a value-receiver method returning a fresh
  n-byte slice of its receiver's bytes).

Toolchain
  holon/frontends/go/ssadump holds exactly main.go, go.mod and go.sum: a generic Go program (module path of the
  builder's choice, `go 1.24.0`) requiring golang.org/x/tools v0.36.0 directly, whose go.sum holds exactly the
  hashes fixed in tests_m2/_i18.py (verified at the prereg through the network proxy into a scratch module cache:
  x/tools v0.36.0 resolves, so there is no vendored tree; a vendor/ directory anywhere under holon/frontends/go is
  a failure). The extractor builds it with `go build -trimpath` (GOWORK=off, GOFLAGS=-mod=readonly,
  GOTOOLCHAIN=local) into ~/.holon/tools/ssadump/<first 16 hex of sha256(main.go + go.mod + go.sum)>/ssadump, never
  inside the repo; module downloads go to the user's module cache. The go toolchain is the `go` on PATH, else
  /usr/local/go/bin/go, and `go version` must print config/holon.json replay.go_version ("go version go1.24.7
  linux/amd64"), else exit 2.
  `ssadump -dir DIR PATTERN...` loads the packages with golang.org/x/tools/go/packages (type information of
  dependencies from export data), builds go/ssa for the matched packages and prints one deterministic JSON document
  on stdout: functions, blocks (with dominators), instructions with operands, types, constants and positions
  relative to DIR, plus the For/Range statements of each function body. It names no target and reads nothing but
  the packages. Its format is the builder's, versioned "holon-ssadump/0.1".
  Workspace: the extractor copies --src to a fresh temporary directory outside the repo (when --src/go.work exists:
  go.work, go.work.sum and every directory its `use` directives name; else the whole tree), skipping .git,
  node_modules, .env* and bunfig.toml, and runs ssadump there (GOWORK unset, GOFLAGS=-mod=readonly,
  GOTOOLCHAIN=local). Paths in the output are relative to that root with "/" separators, so they equal paths in
  the source tree. --src itself is never written.

Document (holon-facts/0.3, frontend "go")
  facts_version  "holon-facts/0.3"
  target         {"repo": config target repo, "commit": config target commit, "scope": "go packages: " + the
                 document's import paths joined by ", "}
  extraction     {"method": "extracted", "frontend": "go", "frontend_version": "holon-go/0.1",
                  "tool": {"go": "go1.24.7", "x_tools": "v0.36.0", "ssadump_sha256": sha256(main.go + go.mod +
                           go.sum)},
                  "config": {"path": the config path relative to --root ("/" separators), "sha256"},
                  "inputs": [{"path": source-relative path, "sha256"}] every compiled non-test .go file of the
                            document's packages, sorted by path}
  assumptions    [{"id", "text"}] sorted by id: always go-append-growth (the capacity append chooses when it grows
                 is not modelled: ["unknown", "growth"]), go-errors-nonnil (errors.New and fmt.Errorf return non-nil
                 errors, and so does a package variable of an error type that the package initializer assigns from
                 one of them), go-nil-deref-not-modelled (nil pointer dereferences are not partiality sites),
                 go-opaque-calls (calls outside the analyzed packages that are not primitives are opaque); plus
                 go-prim:<name> (text from the config) for every primitive whose name occurs as a string anywhere
                 in the document's "go" section.
  go             {"packages": [{"path": import path, "dir": source-relative directory, "files": [source-relative
                               paths]}] sorted by path,
                  "functions": {fid: function}, "codecs": {...}, "slices": {...}, "calls": {...},
                  "loops": [...], "coverage": {...}}   (each below)
  fid: go/ssa Function.String() with full package paths: "pkg.F", "(pkg.T).M", "(*pkg.T).M", closures "...$1".
  span: "<path>:<line>"; a site, call, allocation or append position: "<path>:<line>:<col>" (go/ssa Pos; for calls
  the "("). ["fresh", ...] and ["alloc", ...] carry positions.
  Every function of the document's packages that is not synthetic (go/ssa Synthetic == "") is in "functions":
  methods, closures and package-level functions, not package initializers, wrappers, thunks or bound methods.

Terms (values; JSON arrays, first element the tag)
  ["const", int] | ["bool", b] | ["str", s] | ["nil"] | ["zero", type]          constants (zero: a composite zero value)
  ["param", name]                     a parameter (methods: the receiver is the first parameter)
  ["global", qualified name]          a package-level variable, its address or its value
  ["field", T, name]                  field selection through values or pointers; embedded fields by their type name
  ["len", T] | ["cap", T]             builtins
  ["index", T, I]                     an element of a slice, array or string
  ["slice", T, LO|null, HI|null, MAX|null]
  ["op", op, A, B]                    arithmetic or bitwise operator of Go (+ - * / % & | ^ << >> &^)
  ["unop", op, A]                     - ^ ! (dereference is never a term: loads become field/index/global terms)
  ["convert", type, T]                numeric conversion; changetype, named-type and slice<->named-slice conversions
                                      are transparent (no term)
  ["iface", type, T]                  an interface value made from a concrete T
  ["call", callee, [args]]            an opaque call result; callee = static fid, "builtin:<name>" or
                                      "dynamic:<method or value>"; methods take the receiver as first argument
  ["result", CALLTERM, i]             component i of a tuple-valued call
  ["append", DST, SRC]                append(DST, SRC...) where it is not resolved further
  ["alloc", span, LEN|null]           a fresh allocation (make, new, composite literal, varargs array); LEN for
                                      arrays and slices
  ["var", ssa name, source name|null] an SSA phi left unresolved (functions with loops, loop induction variables)
  ["unknown", why]
  Folding: an op over constants is a constant; len(s[lo:hi]) and len of a fixed allocation or array are constants
  when lo, hi and the length are; types are go/types strings with full package paths.
Atoms (path conditions, guards, bounds): [op, A, B] with op in == != < <= > >= | ["true", T] | ["false", T] (a
  boolean that is not a comparison). A branch on c contributes c on its true edge and the negation on its false edge,
  negation flipping the operator (== !=, < >=, > <=) or true/false.
Cells (layouts; whitepaper §10.2): ["const", v] | ["byte", T, k] (byte k of T: for integers big-endian, k = 0 the
  most significant byte of its width; for arrays, slices and strings element k) | ["byte_le", T, k] (little-endian)
  | ["unknown"]. A byte of a constant is folded to ["const", v]; fresh Go memory is zero, so an unwritten byte of a
  fresh buffer is ["const", 0].

Analysis
  Paths. A function is loop_free when its CFG has no back edge. For a loop-free function the paths are enumerated
  from entry, depth first, true successor first. A branch whose atom the reasoner implies (refutes) on the current
  path follows only its true (false) edge; otherwise the path splits and each side appends its atom. Static calls to
  loop-free, non-recursive functions of the analyzed packages are inlined to inline_depth: their paths are spliced
  in with parameters substituted, and their returned terms replace the call; other calls stay opaque terms. Memory
  allocated by the function or an inlined callee is modelled per path: arrays as cells (initially zero), structs
  as fields (a copy of a by-value parameter reads as ["field", ["param", p], f] until stored; a composite literal's
  unset field reads as ["zero", type]). Loads from other memory are terms; stores to it are recorded (slices.stores)
  and change no term. At each bounds site every bound atom the reasoner does not imply splits off a panic path
  (cond + its negation, end "panic", site the site's id) and the continuing path appends the atom. More than
  max_paths paths: "paths": null, "paths_reason": "path_limit" and a coverage debt entry.
  function = {"span", "package", "params": [{"name", "type"}], "results": [type], "loop_free": bool,
              "paths": [path] | null, "paths_reason": null | "loop" | "path_limit" | "recursion" | "not_codec",
              "sites": [site] sorted by id}
    Paths are listed for loop-free functions with a parameter (receiver included) or a result whose type's
    underlying type is []byte or [N]byte, within max_paths; the other functions have "paths": null with the reason
    ("not_codec" for the rest).
  path = {"cond": [atom] in program order, "end": "return" | "panic", "returns": [term] | null, "site": site id |
          null, "error": null (no error-typed last result, or a panic) | "nil" | "nonnil" | "unknown"}
    error: "nil" for ["nil"]; "nonnil" for a call of errors.New or fmt.Errorf, an ["iface", ...], a package error
    variable the initializer assigns from errors.New or fmt.Errorf, or a term X with [!=, X, ["nil"]] in cond;
    "unknown" otherwise.
  site = {"id": "<path>:<line>:<col>:<kind>", "kind": "index" | "slice" | "prim" | "convert" | "panic" | "assert",
          "bound": [atom] | null, "status": "safe" | "open", "witness": null | {"var", "min", "max"}}
    index x[i]: 0 <= i, i < len(x) (arrays, pointers to arrays: their length); slice x[lo:hi:max]: 0 <= lo,
    lo <= hi, hi <= max, max <= cap(x) (absent bounds as Go defines them; arrays and pointers to arrays: their
    length, strings: len); prim: the encoding/binary {Big,Little}Endian.{Put,}Uint{16,32,64} argument has
    len >= 2, 4, 8; convert (slice to array): len >= N; panic (a panic call) and assert (a type assertion without
    comma-ok): bound null, always "open". Atoms that fold to true are dropped, and an index, slice, prim or convert
    whose whole bound folds to true is not a site (it is not listed). A site of a loop-free function is "open" iff a
    path of the function ends at it; of another function, "open" iff the reasoner does not imply its bound from the
    atoms on the dominator-tree edges into its block (an edge counts when its target has the branch block as only
    predecessor) and the loop facts. witness: when a non-implied bound atom is linear in the induction variable of a
    counted loop with constant init and limit and holds no other variable, the variable's source name and the least
    and greatest values in its range that violate the atom; else null.
  Reasoner. Facts: the assumed atoms; 0 <= len(x) <= cap(x); the lengths of fixed allocations, arrays and constant
    strings; for a counted or range loop with step 1 and constant effective init whose in-loop header successor
    dominates the point: init <= X (X the compared induction expression), and, when the limit is constant too,
    X <= limit - 1 ("<") or X <= limit ("<="). Atoms are normalized over the integers to a linear form (each maximal
    non-linear or non-constant subterm a variable) compared with 0, "<" becoming "<= -1". An atom is implied when an
    assumed atom has the same normalized form, or when its form has one variable and holds over the whole interval
    the facts give that variable (cap(x) at least len(x)'s lower bound; a variable with a one-point interval is a
    constant; an atom v != c removes c from v's interval when c is an endpoint of it); it is refuted when it holds
    nowhere in that interval. Other atoms are neither. Nil: an atom comparing a term with ["nil"] folds when the term
    is ["nil"] or one the error rule below calls "nonnil".
  Codecs (codecs = {"encoders", "decoders", "predicates", "matches", "absences", "patches"})
    encoders: for a loop-free function with paths, every return path whose slice result is (a changetype or
      full-length slice of) a fixed-length allocation made in the function's own body (not in an inlined callee)
      gives the layout of that allocation at the return. Entries {"function", "result": i, "length": L, "cells":
      [cell] (L of them), "conds": [cond of each path giving this layout, in path order], "exact": no ["unknown"]
      cell}, one per distinct (function, result, length, cells), sorted by function, length, cells. Writes: an
      index store; encoding/binary Put* into a constant-offset sub-slice; copy into a constant-offset sub-slice when
      the count n = min(len(dst), len(src)) is a constant; source cells: the cells of local memory (local memory
      holding a whole value T, such as an unstored array field of a parameter copy or a stored call result, gives
      ["byte", T, k]); for ["slice", A, lo, ...] of a non-local array or slice A (a parameter, field, global or call
      result) ["byte", A, lo + k]; for a to_array primitive's result ["byte", <its call term>, k]; for a string
      constant its bytes. When
      n is not constant, every destination position from the offset to the end of the destination becomes
      ["unknown"]. A Put* writes N/8 cells ["byte", V, k] (["byte_le", ...] for LittleEndian) of its value V.
    decoders: loop-free functions with paths and exactly one parameter (receiver included) P of a byte-slice type
      (underlying []byte) whose return paths with error "nil" (or no error result) return as first result a read of
      P: ["index", P, ["const", k]] (width 1, via "index"), an encoding/binary BigEndian / LittleEndian UintN of
      ["slice", P, lo, hi, _] with hi - lo == N/8 (via "be_uint" / "le_uint") or a to_array primitive of such a slice
      with hi - lo == its width (via "to_array"). {"function", "param", "reads": [{"offset", "width", "via"}]
      distinct, sorted}, sorted by function.
    predicates: loop-free functions with paths, exactly one parameter P of a byte-slice type and results exactly
      (error) or (bool). An ok path (error "nil", or returning ["bool", true]) is pinned when its cond holds
      ["==", ["len", P], ["const", L]] and ["==", ["index", P, ["const", k]], ["const", v]]. When every ok path is
      pinned with one k: {"function", "param", "tag_index": k, "accepts": [{"value": v, "length": L}] distinct,
      sorted by value, length}; else tag_index and accepts are null. Sorted by function.
    matches: for every predicate with a tag and every accepted point: {"predicate", "index": k, "value": v,
      "length": L, "encoders": [functions of any analyzed package with an encoder layout of length L whose cell k
      is ["const", v]] sorted}; listed in the predicate's document.
    absences: the matches whose encoders hold no function of the predicate's own package: {"predicate", "index",
      "value", "length", "elsewhere": that match's encoders}. (O2: "no v2 encoder", recorded as an absence.)
    patches: a static call of an encoder function whose slice result r (through changetypes) receives index
      stores of constants r[k] = v and is then returned by the caller: {"function", "encoder", "site": call
      position, "writes": [{"index", "value", "site"}], "guards": [atoms on the dominator-tree edges into the call's
      block], "returned": true}. Sorted by function, site.
  Slices (slices = {"results", "writes", "stores", "lost_writes"}; whitepaper "slice headers become backing-identity
  facts for OWN"; one flow-insensitive def-use pass over every function. Values are built as in path enumeration,
  without inlining, except that a load from the function's own memory reads the value of the one store that
  dominates it with no other store to that address on the way (the copy of a by-value parameter is such a store of
  the parameter), else ["unknown", "memory"]; a phi is ["var", ...] when a term is needed)
    results: for every function and every result of a slice type: {"function", "result": i, "cases": [{"cond",
      "backing", "offset", "len", "cap"}]}: the backing tuple of the value each Return returns, Returns in go/ssa
      block order and each Return's cases in the order the rules give, cond = the atoms on the dominator-tree edges
      into the Return's block followed by the case's own atoms. backing = ["fresh", span of
      the allocation or append] | ["of", T] (the backing array of slice T; offset, len and cap relative to T's
      start) | ["none"] (a nil slice) | ["unknown", why]. Rules: a fixed or made allocation is fresh (offset 0,
      its len and cap); a load of a slice from a parameter, a field, an index or a global, or a slice parameter,
      is ["of", T] with offset 0, len ["len", T], cap ["cap", T]; x[lo:hi:max] keeps x's backing, offset + lo,
      len hi - lo, cap (max or cap) - lo; append(x, y...) gives two cases, in place (own atom ["<=", S, ["cap",
      x]], x's backing, len S, cap x's cap) then grow (own atom [">", S, ["cap", x]], fresh at the append, len S,
      cap ["unknown", "growth"]) with S = ["op", "+", ["len", x], ["len", y]]; a phi is the union of its
      incoming values' cases (a cycle gives ["unknown", "cycle"]); a call of an analyzed function substitutes its
      result's cases; an array_bytes primitive is fresh; any other call is ["unknown", "call"].
    writes: in-place byte writes into a backing ["of", T] whose T is rooted at a parameter or a global:
      {"function", "site", "via": "append" | "copy" | "index" | "prim", "backing", "from", "to" (exclusive),
      "cond"}: an append's in-place case writes [len(x), S) of x (cond: dominator-tree atoms, then the in-place
      atom); a copy, an index store or an encoding/binary Put* into a sub-slice of such a slice writes its range.
    stores: every store whose address is rooted at a parameter or a global (not memory the function allocated):
      {"function", "site", "target": the term a load of that address reads, "value": term}.
    lost_writes: stores into a field of the function's own copy of a by-value parameter when that copy does not
      escape (its address and addresses derived from it reach only loads, stores into it, field and index
      addressing, and slices used as copy or len arguments) and no load of that field can execute after the
      store: {"function", "site", "param", "field": [field names from the parameter], "value"} (O37's shape).
    All three sorted by function, site.
  Calls (calls = {"edges", "flows"}; "pipelines become consumers")
    edges: every call, go and defer instruction of the document's functions except builtins: {"caller", "callee",
      "kind": "call" | "go" | "defer", "site", "callee_kind": "analyzed" | "external" | "primitive" | "dynamic",
      "in_loops": [spans of the loops containing the call's block, outermost first]}, sorted by caller, site,
      callee. A closure is called statically when go/ssa gives a static callee (MakeClosure included).
    flows: producers are the functions with a slice result having a case whose backing is ["of", T], T rooted at a
      parameter (views). For every static call of a producer in the document's functions: {"producer", "caller",
      "site", "uses", "held_across", "opaque_between", "into"}.
      uses: the result's transitive uses through changetypes, phis and sub-slices (a sub-slice is listed as kind
        "slice" and its uses are included): {"kind": "arg" | "len" | "cap" | "index" | "index_store" | "slice" |
        "store" | "return" | "append_dst" | "append_src" | "copy_dst" | "copy_src" | "compare" | "other", "callee":
        fid | null, "index": argument index (receiver 0) or result index | null, "callee_kind": as in edges | null,
        "site"} distinct, sorted by kind, callee, index, site.
      held_across: calls c reachable from the producer call from which a use is reachable (c not the producer call,
        not itself a use) whose callee is analyzed and has a write whose backing, with c's arguments for the
        callee's parameters, equals a non-fresh backing of the producer's result with the call's arguments for the
        producer's parameters: [{"callee", "site"}] sorted.
      opaque_between: calls in the same position whose callee is external or dynamic and one of whose arguments is
        the result, a value derived from it, or a term of which such a backing's T is an extension (T or a prefix of
        its field chain): [{"callee", "site"}] sorted.
      into: for each "arg" use whose callee is analyzed: {"callee", "param", "uses", "into"} for that parameter in
        the callee, flow_depth levels deep (the call site is level 0), sorted by callee, param.
      Sorted by producer, caller, site.
  Loops (go.loops; "loop bounds become cost terms" / fuel, §8.3): one entry per natural loop of every function
    {"function", "span": the For or Range statement (the innermost whose source range holds the positions of all
     positioned non-phi instructions of the loop's blocks), "depth": 1 + enclosing loops, "kind": "counted" |
     "range" | "unbounded", "iv": the header phi's go/ssa comment for a counted loop, null otherwise, "init": term |
     null, "step": int | null, "cmp": op | null, "limit": term | null, "fuel": term | null, "exits": [kinds]}.
    A loop is counted (ForStmt) or range (RangeStmt) when its header ends in a branch with one successor inside
    the loop on [cmp, X, L] (normalized to put the induction side left),
    X = iv or iv + c with iv a header phi whose incoming values are init (from outside) and iv + step (constant,
    from the back edge), and L built from values defined outside the loop or computed in the header. Effective init =
    init + c (a range loop's -1 + 1 is 0). fuel: L when cmp is "<", step 1 and init is ["const", 0]; ["op", "-",
    L, init] for other inits; ["op", "+", ["op", "-", L, init], ["const", 1]] for "<="; null otherwise.
    Otherwise "unbounded" with nulls. exits: distinct sorted kinds of the edges leaving the loop other than the
    header's own exit: "break" (to the header's exit successor), "return" / "panic" (the target reaches a Return /
    a panic without re-entering the loop), else "other". In functions with loops, phis are ["var", ...] terms and
    other values are built from their definitions. Sorted by function, span.
  Coverage (go.coverage): {"functions": count, "with_paths": count, "debt": [{"function", "kind": "loop_bound" (a
    loop with fuel null) | "path_limit" | "inexact_layout" | "unsupported" (an SSA construct path enumeration does
    not model, at a site), "where": span or site, "what": text}] sorted}. Fragments are never approximated
    silently (§10.1 translators).

Honesty (tests_m2/test_extract_go_honesty.py and TestHonesty here)
  The extraction reads the config, the file the config's "source" names, the source tree and the ssadump output
  only; it never reads facts/, spec/M1/, spec/M2/facts/, laws/, results/, gen/, replay/, docs/ or tests*/ (checked
  with an audit hook on the Morph run). holon/frontends/go/ holds no name from the config, no Morph identifier,
  span or header constant. A run on a mutated copy of the source follows the mutation; renaming identifiers
  renames the output and changes nothing else.
"""
import json
import re
import unittest

from tests_m2 import _i18 as H

CONTRACT = __doc__
CB, NT, GEN, BLOB, ZSTD, DER = ("morph-l2/common/batch", "morph-l2/node/types",
                                "morph-l2/morph-deployer/morph-chain-ops/genesis", "morph-l2/common/blob",
                                "morph-l2/common/codec/zstd", "morph-l2/node/derivation")
V0, V1 = f"({CB}.BatchHeaderV0).Bytes", f"({CB}.BatchHeaderV1).Bytes"
VALIDATE = f"({CB}.BatchHeaderBytes).validate"
GENESIS = f"{GEN}.GenesisBatchHeader"
BATCHDATA = f"(*{CB}.BatchData)"
TXSV2 = f"{BATCHDATA}.TxsPayloadV2"
APPEND = f"{BATCHDATA}.Append"
STEMS = ("morph_batch", "morph_blob", "morph_derivation", "morph_genesis", "morph_nodetypes")


class _Shared(unittest.TestCase):
    """One audited Morph run (python -m holon extract go --milestone M2 under an audit hook) shared by the module."""
    run_: "H.Run" = None

    @classmethod
    def setUpClass(cls):
        if _Shared.run_ is None:
            _Shared.run_ = H.Run.morph(audit=True)

    @property
    def docs(self) -> dict:
        return _Shared.run_.need()

    def doc(self, stem: str) -> dict:
        return self.docs[stem]

    def fn(self, fid: str) -> dict:
        return H.function(self.docs, fid)


# --------------------------------------------------------------------------------------- construction checks
class TestExtraction(_Shared):
    def test_cli_writes_one_document_per_config_entry(self):
        r = _Shared.run_
        self.assertEqual(r.code, 0, r.log)
        self.assertEqual(sorted(r.docs), sorted(H.load_json(H.CONFIG)["documents"]))
        self.assertEqual(sorted(r.docs), list(STEMS))
        for stem, text in r.texts.items():
            with self.subTest(doc=stem):
                self.assertEqual(text, json.dumps(r.docs[stem], indent=1, sort_keys=True, ensure_ascii=False) + "\n")

    def test_envelope_and_provenance(self):
        cfg = H.load_json(H.CONFIG)
        morph = H.morph_checkout()
        for stem, d in self.docs.items():
            with self.subTest(doc=stem):
                self.assertEqual(sorted(d), ["assumptions", "extraction", "facts_version", "go", "target"])
                self.assertEqual(d["facts_version"], "holon-facts/0.3")
                pk = cfg["documents"][stem]
                self.assertEqual(d["target"], {"repo": cfg["target"]["repo"], "commit": cfg["target"]["commit"],
                                               "scope": "go packages: " + ", ".join(pk)})
                ex = d["extraction"]
                self.assertEqual((ex["method"], ex["frontend"], ex["frontend_version"]),
                                 ("extracted", "go", "holon-go/0.1"))
                self.assertEqual(ex["tool"], {"go": "go1.24.7", "x_tools": "v0.36.0",
                                              "ssadump_sha256": H.ssadump_sha256()})
                self.assertEqual(ex["config"], {"path": "spec/M2/lib/go_frontend.json",
                                                "sha256": H.sha256_file(H.CONFIG)})
                paths = [i["path"] for i in ex["inputs"]]
                self.assertEqual(paths, sorted(paths))
                self.assertTrue(paths)
                for i in ex["inputs"]:
                    self.assertEqual(i["sha256"], H.sha256_file(morph / i["path"]), i["path"])
                self.assertEqual([p["path"] for p in d["go"]["packages"]], sorted(pk))
                dirs = {p["dir"] for p in d["go"]["packages"]}
                for p in paths:
                    self.assertIn(p.rsplit("/", 1)[0], dirs)
                    self.assertFalse(p.endswith("_test.go"))
                for dd in dirs:
                    want = sorted(f"{dd}/{f.name}" for f in (morph / dd).glob("*.go")
                                  if not f.name.endswith("_test.go") and not H.has_build_constraint(f))
                    self.assertEqual(sorted(p for p in paths if p.rsplit("/", 1)[0] == dd), want)

    def test_assumptions(self):
        cfg = H.load_json(H.CONFIG)
        for stem, d in self.docs.items():
            with self.subTest(doc=stem):
                ids = [a["id"] for a in d["assumptions"]]
                self.assertEqual(ids, sorted(ids))
                for g in H.GENERIC_ASSUMPTIONS:
                    self.assertIn(g, ids)
                used = H.primitives_named(d["go"], cfg["primitives"])
                self.assertEqual(sorted(i for i in ids if i.startswith("go-prim:")),
                                 sorted(f"go-prim:{p}" for p in used))
                for a in d["assumptions"]:
                    if a["id"].startswith("go-prim:"):
                        self.assertEqual(a["text"], cfg["primitives"][a["id"][len("go-prim:"):]]["text"])

    def test_documents_validate_against_the_go_schema(self):
        self.assertTrue(H.GO_SCHEMA.exists(), H.GO_SCHEMA)
        for stem, d in self.docs.items():
            with self.subTest(doc=stem):
                self.assertEqual(H.validate(d, H.GO_SCHEMA), [])
        self.assertNotEqual(H.validate({"facts_version": "holon-facts/0.3"}, H.GO_SCHEMA), [],
                            "the schema must reject a bare envelope")
        bad = json.loads(json.dumps(self.doc("morph_batch")))
        bad["extraction"]["frontend"] = "solidity"
        self.assertNotEqual(H.validate(bad, H.GO_SCHEMA), [], "the schema must reject another frontend")

    def test_documents_validate_against_the_shared_envelope_whenever_it_exists(self):
        """The holon-facts/0.3 envelope is I17's; checked here whenever its schema exists (after the merge)."""
        docs = self.docs
        if not H.SHARED_SCHEMA.exists():
            self.assertEqual(sorted(docs), list(STEMS))
            return
        for stem, d in docs.items():
            with self.subTest(doc=stem):
                self.assertEqual(H.validate(d, H.SHARED_SCHEMA), [])

    def test_terms_atoms_cells_and_sections_follow_the_grammar(self):
        for stem, d in self.docs.items():
            with self.subTest(doc=stem):
                self.assertEqual(H.grammar_problems(d), [])

    def test_two_runs_are_byte_identical_and_match_the_committed_files(self):
        """Exit (construction check): byte-identical extraction across two runs, equal to the committed files."""
        r1 = _Shared.run_
        self.assertEqual(r1.code, 0, r1.log)
        r2 = H.Run.morph(audit=False)
        try:
            self.assertEqual(r2.code, 0, r2.log)
            self.assertEqual(r1.texts, r2.texts)
            for stem in STEMS:
                p = H.FACTS_DIR / f"{stem}.go.extracted.json"
                self.assertTrue(p.exists(), p)
                self.assertEqual(p.read_text(encoding="utf-8"), r1.texts[stem], f"committed {p.name} is stale")
        finally:
            r2.cleanup()

    def test_extracted_documents_are_not_fact_documents_of_m2(self):
        """No extracted document is a fact document of M2, and the three hand documents still are (gen/M2/{diagram,
        sorts, evidence.json} regenerate byte for byte: I14-R4, I15-R10). Checked as a property, not as the exact list,
        so that a later fact document does not need an amendment here."""
        missing = [s for s in STEMS if not (H.FACTS_DIR / f"{s}.go.extracted.json").exists()]
        self.assertEqual(missing, [], "the Go documents are not committed")
        diagram = H.holon_module("holon.diagram")
        got = [p.relative_to(H.ROOT).as_posix() for p in diagram.fact_documents("M2", H.ROOT)]
        self.assertEqual([p for p in got if p.endswith(".extracted.json")], [], got)
        for want in ("facts/morph_header.json", "spec/M1/facts/morph_batchdata.json", "spec/M1/facts/morph_rollup.json"):
            self.assertIn(want, got)


class TestHonesty(_Shared):
    def test_the_extraction_reads_no_frozen_fact_and_no_outcome(self):
        """The audited run opened, listed and executed nothing under the repository outside the allowlist: the
        config, config/holon.json (the source path), spec/schemas/ and holon/ (BUILD_PLAN I18: the extractor's inputs
        are the compiler/SSA outputs and the source tree only)."""
        r = _Shared.run_
        self.assertEqual(r.code, 0, r.log)
        self.assertEqual(H.audit_violations(r.events), [])
        self.assertTrue(any(e[0] == "exec" for e in r.events), "the audit saw no subprocess: ssadump did not run")


# ---------------------------------------------------------------------------------------------- predictions
class TestPredictedCodecs(_Shared):
    def test_encoder_layouts_equal_the_frozen_layouts(self):
        """I18-P1: enc_go_v0 / enc_go_v1 (frozen facts source BatchHeaderV0.Bytes / BatchHeaderV1.Bytes) are extracted
        from (morph-l2/common/batch.BatchHeaderV0).Bytes and (...V1).Bytes. Each has exactly two return paths: the
        cache path, cond [[">", len(b.EncodedBytes), 0]], returning a view of b.EncodedBytes (V1 reads its own
        EncodedBytes, not the embedded V0's), and the layout path, cond [["<=", len(b.EncodedBytes), 0]], returning a
        fresh 249- / 257-byte buffer. That layout is the encoder's only one, exact, and equals the frozen layout
        cell for cell under the field map of the frozen facts' types.Header (frozen field -> the Go field named
        first in its "go" text): cell 0 is ["const", 0] / ["const", 1]; every other cell is byte k of a field of the
        receiver, reached through the embedded BatchHeaderV0 in V1 except LastBlockNumber; no path panics."""
        frozen = H.frozen_facts()
        for fid, fname, version, length, size_line in ((V0, "enc_go_v0", 0, 249, "common/batch/batch_header.go:216"),
                                                       (V1, "enc_go_v1", 1, 257, "common/batch/batch_header.go:244")):
            with self.subTest(encoder=fname):
                f = self.fn(fid)
                recv = f["params"][0]["name"]
                cache = ["field", ["param", recv], "EncodedBytes"]
                self.assertEqual([(p["end"], p["cond"]) for p in f["paths"]],
                                 [("return", [[">", ["len", cache], ["const", 0]]]),
                                  ("return", [["<=", ["len", cache], ["const", 0]]])])
                encs = [e for e in H.section(self.docs, "codecs", "encoders") if e["function"] == fid]
                self.assertEqual(len(encs), 1, encs)
                e = encs[0]
                self.assertEqual((e["result"], e["length"], e["exact"]), (0, length, True))
                self.assertEqual(e["conds"], [[["<=", ["len", cache], ["const", 0]]]])
                self.assertEqual(H.to_frozen_cells(e["cells"], recv, frozen), H.frozen_layout(frozen, fname, version))
                emb = {H.field_chain(c[1], recv)[0] for c in e["cells"] if c[0] == "byte"}
                if version == 1:
                    self.assertEqual(emb, {"BatchHeaderV0", "LastBlockNumber"})
                res = H.result_entry(self.docs, fid, 0)
                self.assertEqual([c["backing"][0] for c in res["cases"]], ["of", "fresh"])
                self.assertEqual(res["cases"][0]["backing"], ["of", cache])
                self.assertTrue(res["cases"][1]["backing"][1].startswith(size_line + ":"), res["cases"][1])
                self.assertEqual((res["cases"][1]["len"], res["cases"][1]["cap"]),
                                 (["const", length], ["const", length]))

    def test_decoder_partiality_equals_ok_go_on_every_length_constant_plus_minus_one(self):
        """I18-P2: dec_go's partiality is ok_go. On every probe of tests_m2/_i18.probes (lengths: every getter offset
        and offset + width of the frozen dec_go and every ok_go length, each -1, 0, +1, plus 0, 1, 2; byte 0 in
        0, 1, 2, 3, 255; cap = len and len + 16), exactly one extracted path of each function holds; for validate,
        Hash and each of the 12 frozen getters (mapped to the BatchHeaderBytes method named by the "<Name>():" its
        frozen "code" starts with: Version, BatchIndex, ..., BlobCommitHash, ..., LastBlockNumber) that path returns
        a nil error iff the frozen ok_go holds and the getter's frozen "when" holds (lastBlockNumber: version >= 1;
        Version: length >= 1, as its frozen getter reads b[0] only), else a non-nil error; no path that holds ends in
        a panic. Each frozen getter's extracted reads are exactly [(offset, width)] of the frozen getter."""
        frozen = H.frozen_facts()
        probes = H.probes(frozen)
        self.assertGreaterEqual(len(probes), 300)
        for method, expect in H.frozen_decoder_expectations(frozen).items():
            fid = f"({CB}.BatchHeaderBytes).{method}"
            with self.subTest(method=method):
                f = self.fn(fid)
                self.assertIsNotNone(f["paths"], f"{fid}: {f['paths_reason']}")
                bad = [(p, got, want) for p in probes
                       for got, want in [(H.outcome(f, p), "ok" if expect(p) else "err")] if got != want]
                self.assertEqual(bad[:5], [], f"{len(bad)} probes differ")
        for g in frozen["functions"]["dec_go"]["getters"]:
            with self.subTest(getter=g["name"]):
                fid = f"({CB}.BatchHeaderBytes).{H.getter_method(g)}"
                self.assertEqual(H.reads(self.docs, fid), [(g["offset"], g["width"])])

    def test_the_other_header_getters(self):
        """I18-P3: BatchHeaderBytes in common/batch has exactly 14 decoders: Version (0, 1), the 12 frozen getters'
        methods, BlobVersionedHash and BlobHashesHash (both (57, 32)). On every probe BlobVersionedHash is ok iff
        ok_go and byte 0 < 2, BlobHashesHash iff ok_go and byte 0 >= 2, and BlobCommitHash, which dispatches to one of
        them on Version(), iff ok_go; no probe panics."""
        frozen = H.frozen_facts()
        probes = H.probes(frozen)
        decs = sorted(d["function"] for d in H.section(self.docs, "codecs", "decoders")
                      if d["function"].startswith(f"({CB}.BatchHeaderBytes)."))
        names = sorted(H.getter_method(g) for g in frozen["functions"]["dec_go"]["getters"])
        self.assertEqual(decs, sorted(f"({CB}.BatchHeaderBytes).{m}"
                                      for m in set(names) | {"BlobVersionedHash", "BlobHashesHash"}))
        ok = lambda p: H.frozen_ok(frozen, p)  # noqa: E731
        for m, want in (("BlobVersionedHash", lambda p: ok(p) and p.b0 < 2),
                        ("BlobHashesHash", lambda p: ok(p) and p.b0 >= 2), ("BlobCommitHash", ok)):
            with self.subTest(method=m):
                fid = f"({CB}.BatchHeaderBytes).{m}"
                self.assertEqual(H.reads(self.docs, fid), [(57, 32)])
                f = self.fn(fid)
                bad = [p for p in probes if H.outcome(f, p) != ("ok" if want(p) else "err")]
                self.assertEqual(bad[:5], [], f"{len(bad)} probes differ")

    def test_no_v2_encoder_in_the_codec_package(self):
        """I18-P4 (O2, recorded as an absence): validate is a tagged predicate, tag_index 0, accepting (0, 249),
        (1, 257), (2, 257); the matches are V0.Bytes, V1.Bytes and, for (2, 257), only GenesisBatchHeader of
        morph-l2/morph-deployer/morph-chain-ops/genesis; so morph_batch's absences are exactly one, version 2 at 257
        with elsewhere [GenesisBatchHeader]. The deprecated duplicate decoder in morph-l2/node/types has no encoder
        in its package: three absences, elsewhere [V0.Bytes], [V1.Bytes], [GenesisBatchHeader]."""
        b = self.doc("morph_batch")["go"]["codecs"]
        pred = [p for p in b["predicates"] if p["function"] == VALIDATE]
        self.assertEqual(pred, [{"function": VALIDATE, "param": self.fn(VALIDATE)["params"][0]["name"], "tag_index": 0,
                                 "accepts": [{"value": 0, "length": 249}, {"value": 1, "length": 257},
                                             {"value": 2, "length": 257}]}])
        self.assertEqual([(m["value"], m["length"], m["encoders"]) for m in b["matches"] if m["predicate"] == VALIDATE],
                         [(0, 249, [V0]), (1, 257, [V1]), (2, 257, [GENESIS])])
        self.assertEqual(b["absences"], [{"predicate": VALIDATE, "index": 0, "value": 2, "length": 257,
                                          "elsewhere": [GENESIS]}])
        nt = self.doc("morph_nodetypes")["go"]["codecs"]
        vnt = f"({NT}.BatchHeaderBytes).validate"
        self.assertEqual([(a["predicate"], a["value"], a["length"], a["elsewhere"]) for a in nt["absences"]],
                         [(vnt, 0, 249, [V0]), (vnt, 1, 257, [V1]), (vnt, 2, 257, [GENESIS])])

    def test_a_standalone_version_2_encoder_exists_outside_the_codec_package(self):
        """I18-P5 (new; narrows O2's "no v2 encoder" to the codec package): GenesisBatchHeader writes its own
        257-byte buffer with cell 0 = ["const", 2]; each of its layouts has: cells 1..24 ["const", 0] (PutUint64 of 0),
        25..56 bytes 0..31 of a call of go-ethereum crypto.Keccak256Hash, 57..88 bytes 0..31 of the package variable
        emptyBlobVersionedHash, 89..120 ["const", 0], 121..152 bytes 0..31 of field Root of the parameter genesisHeader,
        153..248 ["const", 0], 249..256 bytes 0..7 of a call of (*math/big.Int).Uint64 on genesisHeader.Number; its
        return paths all return a nil error."""
        encs = [e for e in H.section(self.docs, "codecs", "encoders") if e["function"] == GENESIS]
        self.assertTrue(encs)
        f = self.fn(GENESIS)
        self.assertTrue(f["paths"] and all(p["end"] == "return" and p["error"] == "nil" for p in f["paths"]))
        gh = ["param", f["params"][0]["name"]]
        for e in encs:
            c = e["cells"]
            self.assertEqual(e["length"], 257)
            self.assertEqual(c[0], ["const", 2])
            for rng in (range(1, 25), range(89, 121), range(153, 249)):
                self.assertTrue(all(c[i] == ["const", 0] for i in rng), rng)
            self.assertEqual([H.cell_callee(c[25 + k], k) for k in range(32)],
                             ["github.com/morph-l2/go-ethereum/crypto.Keccak256Hash"] * 32)
            self.assertEqual(c[57:89], [["byte", ["global", f"{GEN}.emptyBlobVersionedHash"], k] for k in range(32)])
            self.assertEqual(c[121:153], [["byte", ["field", gh, "Root"], k] for k in range(32)])
            for k in range(8):
                self.assertEqual(c[249 + k][0:1] + c[249 + k][2:], ["byte", k])
                t = c[249 + k][1]
                self.assertEqual((t[0], t[1], t[2]), ("call", "(*math/big.Int).Uint64", [["field", gh, "Number"]]))

    def test_block_context_codec(self):
        """I18-P6 (D3, block-context encode and height decode): HeightFromBlockContextBytes (common/batch) is a decoder
        reading [(0, 8, be_uint)], ok iff len == 60 (lengths 0, 7, 8, 9, 59, 60, 61). BuildBlockContext (common/batch)
        and BlockContextBytes (node/types) write 60-byte layouts: 0..7 the block number (header.Number.Uint64() /
        wb.Number), 8..15 header.Time / wb.Timestamp, 48..55 the GasLimit field, 56..57 and 58..59 bytes of
        uint16(txsNum) and uint16(l1MsgNum); on the path where the BaseFee field is nil, 16..47 are ["const", 0]."""
        hfid = f"{CB}.HeightFromBlockContextBytes"
        self.assertEqual(H.reads(self.docs, hfid, via=True), [(0, 8, "be_uint")])
        f = self.fn(hfid)
        for n in (0, 7, 8, 9, 59, 60, 61):
            self.assertEqual(H.outcome(f, H.Probe(n, n, 1)), "ok" if n == 60 else "err", n)
        encoders = ((f"{CB}.BuildBlockContext", "call", "Time", "BaseFee"),
                    (f"(*{NT}.WrappedBlock).BlockContextBytes", "field", "Timestamp", "BaseFee"))
        for fid, recv_number, time, base in encoders:
            with self.subTest(encoder=fid):
                f = self.fn(fid)
                p0 = ["param", f["params"][0]["name"]]
                encs = [e for e in H.section(self.docs, "codecs", "encoders") if e["function"] == fid]
                self.assertTrue(encs)
                nil_seen = False
                for e in encs:
                    c = e["cells"]
                    self.assertEqual(e["length"], 60)
                    num = ["field", p0, "Number"]
                    for k in range(8):
                        if recv_number == "call":
                            self.assertEqual(c[k], ["byte", ["call", "(*math/big.Int).Uint64", [num]], k])
                        else:
                            self.assertEqual(c[k], ["byte", num, k])
                        self.assertEqual(c[8 + k], ["byte", ["field", p0, time], k])
                        self.assertEqual(c[48 + k], ["byte", ["field", p0, "GasLimit"], k])
                    params = [x["name"] for x in f["params"]]
                    for k in range(2):
                        self.assertEqual(c[56 + k], ["byte", ["convert", "uint16", ["param", params[1]]], k])
                        self.assertEqual(c[58 + k], ["byte", ["convert", "uint16", ["param", params[2]]], k])
                    if any(["==", ["field", p0, base], ["nil"]] in cond for cond in e["conds"]):
                        nil_seen = True
                        self.assertTrue(all(x == ["const", 0] for x in c[16:48]))
                self.assertTrue(nil_seen, "no layout on the nil-BaseFee path")

    def test_node_types_decodes_like_common_batch(self):
        """I18-P7: the deprecated duplicate in morph-l2/node/types decodes exactly like common/batch: for the 16 methods
        of BatchHeaderBytes both packages define (validate, Bytes, Hash, Version and the 12 getters other than
        BlobCommitHash), the extracted paths are equal once the package path is replaced and spans are blanked."""
        methods = H.NODE_TYPES_METHODS
        self.assertEqual(len(methods), 16)
        for m in methods:
            with self.subTest(method=m):
                a = self.fn(f"({CB}.BatchHeaderBytes).{m}")["paths"]
                b = self.fn(f"({NT}.BatchHeaderBytes).{m}")["paths"]
                self.assertIsNotNone(a)
                self.assertEqual(H.normalize_package(b, NT, CB), H.normalize_package(a, CB, CB))


class TestPredictedSlices(_Shared):
    def test_txspayloadv2_result_shares_the_spare_capacity_of_block_contexts(self):
        """I18-P8 (O36's precondition): TxsPayloadV2's result has exactly two backing cases. In place (own atom
        len(X) + len(Y) <= cap(X), X = cks.blockContexts, Y = cks.txsPayload): backing ["of", X], offset 0,
        len len(X) + len(Y), cap cap(X). Grow: fresh at batch_data.go:119, cap ["unknown", "growth"]. TxsPayloadV2
        writes [len(X), len(X) + len(Y)) of X's backing in place and stores nothing, so the view's tail is X's spare
        capacity; Append's in-place append to the same field writes from len(X) of the same backing and stores the
        result back to the field (O36: a later Append overwrites the held view)."""
        f = self.fn(TXSV2)
        cks = ["param", f["params"][0]["name"]]
        x, y = ["field", cks, "blockContexts"], ["field", cks, "txsPayload"]
        s = ["op", "+", ["len", x], ["len", y]]
        res = H.result_entry(self.docs, TXSV2, 0)
        self.assertEqual(len(res["cases"]), 2, res)
        inplace, grow = res["cases"]
        self.assertEqual((inplace["backing"], inplace["offset"], inplace["len"], inplace["cap"]),
                         (["of", x], ["const", 0], s, ["cap", x]))
        self.assertEqual(inplace["cond"][-1], ["<=", s, ["cap", x]])
        self.assertEqual(grow["backing"][0], "fresh")
        self.assertTrue(grow["backing"][1].startswith("common/batch/batch_data.go:119:"), grow)
        self.assertEqual((grow["len"], grow["cap"], grow["cond"][-1]), (s, ["unknown", "growth"], [">", s, ["cap", x]]))
        w = [w for w in H.section(self.docs, "slices", "writes") if w["function"] == TXSV2]
        self.assertEqual([(v["via"], v["backing"], v["from"], v["to"]) for v in w],
                         [("append", ["of", x], ["len", x], s)])
        self.assertEqual([st for st in H.section(self.docs, "slices", "stores") if st["function"] == TXSV2], [])
        a = self.fn(APPEND)
        acks = ["param", a["params"][0]["name"]]
        ax = ["field", acks, "blockContexts"]
        aw = [w for w in H.section(self.docs, "slices", "writes")
              if w["function"] == APPEND and w["backing"] == ["of", ax]]
        self.assertEqual(len(aw), 1, aw)
        self.assertEqual((aw[0]["via"], aw[0]["from"]), ("append", ["len", ax]))
        self.assertTrue(aw[0]["site"].startswith("common/batch/batch_data.go:35:"))
        self.assertEqual(H.rename_param(aw[0]["backing"], acks[1], cks[1]), ["of", x])
        self.assertTrue(any(st["target"] == ax and st["site"].startswith("common/batch/batch_data.go:35:")
                            for st in H.section(self.docs, "slices", "stores") if st["function"] == APPEND))

    def test_batch_data_write_inventory(self):
        """I18-P9: the in-place writes into parameter-rooted backings in common/batch/batch_data.go are exactly five
        appends: Append at :35 (blockContexts), :36 (txsPayload), :39 (l1TxHashes, in the loop), TxsPayloadV2 at :119
        (blockContexts) and EstimateCompressedSizeWithNewPayload at :126 (txsPayload, a second write into a field's
        spare capacity without a store). DataHash, Encode, calculateHash and combinePayloads write only fresh
        buffers."""
        got = sorted((w["function"].rsplit(".", 1)[1], int(w["site"].split(":")[1]), H.backing_label(w["backing"]),
                      w["via"])
                     for w in H.section(self.docs, "slices", "writes")
                     if w["site"].startswith("common/batch/batch_data.go:"))
        self.assertEqual(got, [("Append", 35, "blockContexts", "append"), ("Append", 36, "txsPayload", "append"),
                               ("Append", 39, "l1TxHashes", "append"),
                               ("EstimateCompressedSizeWithNewPayload", 126, "txsPayload", "append"),
                               ("TxsPayloadV2", 119, "blockContexts", "append")])

    def test_value_receiver_cache_writes_are_lost(self):
        """I18-P10 (O37): morph_batch's lost writes are exactly the two cache stores b.EncodedBytes = batchBytes in
        BatchHeaderV0.Bytes (batch_header.go:228) and BatchHeaderV1.Bytes (:258), each into the method's own copy of
        its value receiver."""
        lw = self.doc("morph_batch")["go"]["slices"]["lost_writes"]
        self.assertEqual([(x["function"], x["site"].split(":")[1], x["param"], x["field"]) for x in lw],
                         [(V0, "228", self.fn(V0)["params"][0]["name"], ["EncodedBytes"]),
                          (V1, "258", self.fn(V1)["params"][0]["name"], ["EncodedBytes"])])


class TestPredictedPartiality(_Shared):
    def test_the_blob_retrieval_error_path_indexes_past_the_buffer_from_word_3968(self):
        """I18-P11 (O4 / F3, localized): morph-l2/common/batch.RetrieveBlobBytes has four bounds sites; exactly one is
        open: the index data[i*32] in the error branch at common/batch/blob.go:49, with witness {"var": "i", "min":
        3968, "max": 4095} (data has 4096 * 31 = 126976 bytes; i ranges over 0..4095). blob[i*32] (:48) and the two
        slices of the copy (:51) are safe. The fixed copy morph-l2/common/blob.RetrieveBlobBytes (payload.go:43-52)
        indexes the 131072-byte blob instead: its four sites are all safe."""
        own = self.fn(f"{CB}.RetrieveBlobBytes")["sites"]
        self.assertEqual(len(own), 4, own)
        opened = [s for s in own if s["status"] == "open"]
        self.assertEqual(len(opened), 1, opened)
        s = opened[0]
        self.assertEqual((s["kind"], s["id"].split(":")[:2]), ("index", ["common/batch/blob.go", "49"]))
        self.assertEqual(s["witness"], {"var": "i", "min": 3968, "max": 4095})
        self.assertEqual(sorted(int(x["id"].split(":")[1]) for x in own if x["status"] == "safe"), [48, 51, 51])
        fixed = self.fn(f"{BLOB}.RetrieveBlobBytes")["sites"]
        self.assertEqual(len(fixed), 4, fixed)
        self.assertEqual([x["status"] for x in fixed], ["safe"] * 4)


class TestPredictedCalls(_Shared):
    def test_the_derivation_loop_reaches_the_open_site(self):
        """I18-P12 (O4's consumer chain): the call edges include Start -go-> Start$1 (derivation.go:200),
        Start$1 -> derivationBlock (:207), derivationBlock -> fetchRollupDataByTxHash (:380, :428, :456),
        fetchRollupDataByTxHash -> parseBatch (:599), parseBatch -> (*BatchInfo).ParseBatch (:715) and ParseBatch ->
        morph-l2/common/batch.RetrieveBlobBytes (batch_info.go:116) inside the range loop over batch.Sidecar.Blobs
        (batch_info.go:114); ParseBatch calls no morph-l2/common/blob.RetrieveBlobBytes."""
        d = f"(*{DER}.Derivation)"
        want = [(f"{d}.Start", f"{d}.Start$1", "go", "node/derivation/derivation.go:200"),
                (f"{d}.Start$1", f"{d}.derivationBlock", "call", "node/derivation/derivation.go:207"),
                *[(f"{d}.derivationBlock", f"{d}.fetchRollupDataByTxHash", "call", f"node/derivation/derivation.go:{n}")
                  for n in (380, 428, 456)],
                (f"{d}.fetchRollupDataByTxHash", f"{d}.parseBatch", "call", "node/derivation/derivation.go:599"),
                (f"{d}.parseBatch", f"(*{DER}.BatchInfo).ParseBatch", "call", "node/derivation/derivation.go:715"),
                (f"(*{DER}.BatchInfo).ParseBatch", f"{CB}.RetrieveBlobBytes", "call",
                 "node/derivation/batch_info.go:116")]
        edges = H.section(self.docs, "calls", "edges")
        have = {(e["caller"], e["callee"], e["kind"], e["site"].rsplit(":", 1)[0]): e for e in edges}
        for w in want:
            with self.subTest(edge=w):
                self.assertIn(w, have)
        last = have[want[-1]]
        self.assertEqual((last["callee_kind"], last["in_loops"]), ("analyzed", ["node/derivation/batch_info.go:114"]))
        self.assertFalse([e for e in edges if e["caller"] == f"(*{DER}.BatchInfo).ParseBatch"
                          and e["callee"] == f"{BLOB}.RetrieveBlobBytes"])

    def test_txspayloadv2_consumers(self):
        """I18-P13: TxsPayloadV2 has exactly two call sites in the analyzed packages: (*BatchCache).handleBatchSealing
        (batch_cache.go:1581), where the result's only use is argument 0 of morph-l2/common/blob.CompressBatchBytes
        (not common/batch's own copy), and (*Derivation).rebuildBlob (verify_local.go:186), where its uses are argument
        0 of morph-l2/common/blob.CompressBatchBytes (:189) and len. Into CompressBatchBytes, the parameter's uses are
        len and argument 0 of morph-l2/common/codec/zstd.CompressBatchBytes, whose parameter's uses are len and
        argument 0 of the external github.com/morph-l2/morph-da-codec/bindings/codec/zstd.CompressMorphDABatch."""
        flows = [f for f in H.section(self.docs, "calls", "flows") if f["producer"] == TXSV2]
        self.assertEqual([(f["caller"], f["site"].rsplit(":", 1)[0]) for f in flows],
                         [(f"(*{CB}.BatchCache).handleBatchSealing", "common/batch/batch_cache.go:1581"),
                          (f"(*{DER}.Derivation).rebuildBlob", "node/derivation/verify_local.go:186")])
        comp = f"{BLOB}.CompressBatchBytes"
        self.assertEqual(H.use_kinds(flows[0]["uses"]), [("arg", comp, 0)])
        self.assertEqual(H.use_kinds(flows[1]["uses"]), [("arg", comp, 0), ("len", None, None)])
        for fl in flows:
            with self.subTest(caller=fl["caller"]):
                into = [i for i in fl["into"] if i["callee"] == comp]
                self.assertEqual([(i["param"], H.use_kinds(i["uses"])) for i in into],
                                 [(0, [("arg", f"{ZSTD}.CompressBatchBytes", 0), ("len", None, None)])])
                z = [i for i in into[0]["into"] if i["callee"] == f"{ZSTD}.CompressBatchBytes"]
                self.assertEqual([(i["param"], H.use_kinds(i["uses"])) for i in z],
                                 [(0, [("arg", "github.com/morph-l2/morph-da-codec/bindings/codec/zstd."
                                               "CompressMorphDABatch", 0), ("len", None, None)])])
                ext = [u for u in z[0]["uses"] if u["kind"] == "arg"]
                self.assertEqual([u["callee_kind"] for u in ext], ["external"])


class TestPredictedLoops(_Shared):
    def test_loop_bounds(self):
        """I18-P14: in these functions the loops are exactly these (span, kind, iv, init, step, cmp, limit, fuel,
        exits), tests_m2/_i18.EXPECTED_LOOPS: Append range over l1TxHashes (fuel len); DataHash i < int(cks.blockNum);
        both MakeBlobCanonical and RetrieveBlobBytes i < 4096 (exits break / return); both MakeBlobTxSidecar
        i < (len(blobBytes) + 126976 - 1) / 126976 (exits return); DecodeTxsFromBytes `for {}` unbounded, fuel null,
        exits return, with a loop_bound coverage debt; ParsingTxs and aggregateBlobHashes range loops; ParseBatch's
        range over batch.Sidecar.Blobs and i < int(blockCount) (blockCount a phi); rebuildBlob n from
        batchInfo.firstBlockNumber while n <= batchInfo.lastBlockNumber, fuel last - first + 1."""
        loops = H.section(self.docs, "loops")
        for fid, want in H.EXPECTED_LOOPS.items():
            with self.subTest(function=fid):
                got = [l for l in loops if l["function"] == fid]
                f = self.fn(fid)
                self.assertEqual([H.loop_shape(l, f) for l in got], want)
        debt = H.section(self.docs, "coverage", "debt")
        self.assertIn((f"{CB}.DecodeTxsFromBytes", "loop_bound", "common/batch/blob.go:120"),
                      {(d["function"], d["kind"], d["where"]) for d in debt})


# ------------------------------------------------------------------------------------------------- replay
class TestReplay(_Shared):
    """The prereg Go instrument (tests_m2/fixtures/go_frontend/holon_i18_instrument.go.txt) runs the real code."""
    out_: dict = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if TestReplay.out_ is None:
            TestReplay.out_ = H.run_go_instrument(H.probes(H.frozen_facts()), H.O4_WORDS)

    def test_the_real_retrieval_panics_from_word_3968(self):
        """I18-R9 (regression, not counted: O4 / F3 as recorded in whitepaper.md App. A and
        docs/build_plan/gap_map.json, observed on the real code): on blobs whose field element e has a non-zero
        high-order byte, the real
        common/batch RetrieveBlobBytes returns an error for e = 0 and 3967 and panics for e = 3968 ("index out of
        range [126976] with length 126976") and 4095 ("[131040] with length 126976"); the real common/blob
        RetrieveBlobBytes returns an error for all four."""
        r = TestReplay.out_["retrieve"]
        self.assertEqual(H.O4_WORDS, [0, 3967, 3968, 4095])
        own = r["common/batch"]
        self.assertEqual(own[:2], ["err", "err"])
        self.assertRegex(own[2], r"^panic: .*index out of range \[126976\] with length 126976")
        self.assertRegex(own[3], r"^panic: .*index out of range \[131040\] with length 126976")
        self.assertEqual(r["common/blob"], ["err"] * 4)

    def test_extracted_decoder_partiality_agrees_with_the_real_code(self):
        """Construction check (I18-R8): on every probe, every BatchHeaderBytes method the instrument calls has the
        outcome (ok, err, panic) the extracted paths give."""
        probes = H.probes(H.frozen_facts())
        for method, outs in sorted(TestReplay.out_["decoders"].items()):
            with self.subTest(method=method):
                f = self.fn(f"({CB}.BatchHeaderBytes).{method}")
                bad = [(p, o) for p, o in zip(probes, outs) if H.outcome(f, p) != o.split(":", 1)[0]]
                self.assertEqual(bad[:5], [], f"{len(bad)} probes differ")


# --------------------------------------------------------------------------------------------- regressions
class TestRegressions(_Shared):
    def test_version_2_headers_are_patched_v1_encodings(self):
        """I18-R2 (recorded in docs/CASESTUDY.md, L_par_hdr_v2): morph_batch has exactly one patch:
        createBatchHeaderWithSequencerSetHash calls BatchHeaderV1.Bytes, stores 2 at index 0 (batch_cache.go:1730)
        and returns the result, under a guard naming isBatchV2Upgraded."""
        p = self.doc("morph_batch")["go"]["codecs"]["patches"]
        self.assertEqual([(x["function"], x["encoder"], [(w["index"], w["value"], w["site"].split(":")[1])
                                                         for w in x["writes"]], x["returned"]) for x in p],
                         [(f"(*{CB}.BatchCache).createBatchHeaderWithSequencerSetHash", V1, [(0, 2, "1730")], True)])
        self.assertTrue(any(a[0] == "true" and a[1][0] == "call" and a[1][1].endswith(").isBatchV2Upgraded")
                            for a in p[0]["guards"]), p[0]["guards"])

    def test_txspayloadv2_views_are_not_held_across_a_write(self):
        """I18-R3 (recorded in results/M1/L_own_txspayload.json triage_why: both in-repo callers consume the view
        immediately): held_across and opaque_between are empty at both TxsPayloadV2 call sites."""
        flows = [f for f in H.section(self.docs, "calls", "flows") if f["producer"] == TXSV2]
        self.assertEqual(len(flows), 2)
        for fl in flows:
            self.assertEqual((fl["held_across"], fl["opaque_between"]), ([], []), fl["caller"])


if __name__ == "__main__":
    unittest.main()
