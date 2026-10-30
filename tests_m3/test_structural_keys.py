"""I68: structural storage keys in the M3 model (the Q21 fix: docs/HUMAN_ANSWERS.md, Q21, I30's Question 1; BUILD_PLAN
row I68). This docstring is the contract.

Scope. The M3 model (holon.sorts.model3) keeps the contract's storage as raw slots, and computes a mapping value's
slot as h_get(kh, key ++ slot), a lookup in the law's keccak256 table parameter. Every M3 typed law quantifies that
table (binder keccak256: Fn<Bytes,Word>), so a law must hold for every finite table, including the empty one, where
every mapping slot is 0 + member and aliases slot 0. That makes true laws false (I30 Q1: the toy's tag_exact law) and
leaves frames over mapping state with no proof route (I31's 14 UNKNOWN blocking laws). The human's answer to Q21: the M3
model keys compiler-generated mapping storage structurally, as (base slot, key path); the evaluator maps a structural
key to its real slot with the real keccak256 only where it compares with real traces (R5) and in replay; a raw
sload/sstore at a computed slot stays a raw slot; a generated check tests every raw slot against the real-slot image of
every structural key the model touches, a collision being a finding; the idealisation is the named model assumption
A-keccak-structural, validated by every R5 storage comparison; the law statements do not change. I68 implements that
answer through the model, its evaluator, its deployment, its search and its sections, and the proof routes it opens:
the SK frame library, the DISCH routes' key split and convoy over SK, loop frames, bit-field lemmas, and the tag_exact
proof class for SORT tag laws.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl): tests_m3/_i68.py (rule S2's real-slot mapping, S5's classification and S7's keys check,
independently of holon/).

S1 The store. holon.sorts.prelude3 gives PRELUDE_SK, the structural store, which every structural model holds:
     type SP is Data: SP_m{k: W, o: W}                one hashed step: the mapping key word, then the slot offset;
     type SK is Data: SK{b: W, o: W, p: List<&2, SP>}  a location: base slot, offset in the top-level variable, path;
     sp_eq(a, b) (offsets first, then keys), sps_eq, sk_eq(a, b) (base first, then offset, then path);
     type KV is Data: KV{k: SK, v: W};  HSt{sl: List<&2, KV>};
     sload(s: HSt, +k: SK) -> W, the first entry whose key sk_eq's k, else w0(); sstore(s, +k: SK, +v: W) -> HSt, the
     A30 shape of kw_put/kw_set over KV; HOut's touched list tw: List<&2, SK>.
   PRELUDE_SK differs from PRELUDE (the raw store, unchanged: I28's versioned layer embeds it and F32's test reads it)
   in its storage block alone: W, w_eq, KW and kw_get/kw_put/kw_set (the environment's balance table), HKB and h_get
   (code-level hashes) keep their text, so F32's eight pinned helpers keep theirs (tests_m3/test_eqprove.py). A
   structural model's header names model_version holon-model-m3/0.3 (holon.sorts.model3.MODEL3_SK_VERSION) and its
   storage: "structural keys (A-keccak-structural)"; MODEL3_VERSION stays holon-model-m3/0.2, the raw mode's version,
   which I28's versioned modules name in their headers.
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
   storage key of any M3 model (the typed model, its untyped twin, the DISCH, UNDO and FACT sections) goes through
   h_get. The real slot of SK{b, o, p}: s = b + o, then for each step SP_m{k, o2}: s = keccak256(pad32(k) ++
   pad32(s)) + o2, all mod 2**256 (holon.sorts.skeys.real_slot, and the instrument's real_slot).
S3 Raw slots. A raw ["sload", r] or sstore at r compiles to SK{r, w0(), Nil}, the key of a scalar at literal slot r.
   On the Rollup the only raw access is initialize4's read of the EIP-1967 admin slot.
S4 Storage modes (option A1 of the Q21 design). holon.sorts.model3 compiles storage in one of two modes: structural,
   which holon.sorts.model3.generate passes (the typed model, its untyped twin, and every section, gate check and
   intake check built from them), and raw, the mode it has today and the default of model3.build_text and Model3, which
   I28's versioned generator (holon/versions) calls. I28's versioned machine therefore stays on the raw store byte for
   byte, and its records carry no A-keccak-structural. I28's contract (tests_m3/test_versions.py, rule V6) says the
   versioned model follows the storage representation of the adopted document's model; its versioned layer converts
   the raw store's values (KW) and reads locations through the hash table, so converting it is left to a later key
   (Question H2), and after I68 that sentence of V6 does not hold: the report says so.
S5 The deployment. s0 is converted from the deployment's captured raw slots (gen/M3/sorts/models/*.init.json, from
   holon.sorts.deploy3) with the preimages the capture records: a captured slot of a top-level variable becomes its
   literal key, a slot that is keccak256(k ++ b) + o2 for a recorded 64-byte preimage k ++ b whose b is a mapping
   family's base becomes SK{W{b}, w0(), [SP_m{k, W{o2}}]}, and any other captured slot stays raw (SK{r, w0(), Nil}).
   On the Rollup's capture: 9 literal, 7 structural, 2 raw (the EIP-1967 implementation and admin slots). The real
   image of s0 (every key mapped by real_slot) is the captured storage exactly: holon.sorts.skeys.s0_keys(model_text)
   gives the model's s0 entries as ((b, o, path), value) and real_state(entries) the {real slot: value} they denote.
S6 The evaluator (holon.sorts.evaluate3, holon/js/eval3.mjs) maps keys to real slots with the real keccak256 only: in
   R5's pre-state fixpoint and write comparison; in the replays (holon.disch.run's, holon.refute_m3's direct tests,
   which read real words at B's slots); in the deployment conversion (S5); and in the search's heuristics (candidates
   only). The model and its proofs never use it. The search offers the structural keys' key words where it offered
   slot preimages.
S7 The keys check. `holon keys --milestone M3` writes gen/M3/sorts/keys.json: every raw slot, every literal slot and
   the real image of every structural key that the deployment, the R5 corpus and every committed witness and
   inhabitant of an M3 typed record touch, as {"raw": [slot], "literal": [slot], "structural": [{"b", "o", "p": [{"k",
   "o"}], "real"}], "collisions": [...], "sources": ["deployment", "r5", "witnesses", "inhabitants"]} (every number a
   0x-prefixed hex string). A raw or literal slot equal to a structural image, or two different structural keys with one
   image, is a collision: a finding, listed, never an assumption.
S8 The ledger. A-keccak-structural enters the ledger through spec/M3/ledger.json, introduced by SK, sk_eq and the
   store's definitions (sload, sstore, kv_*), for records of milestone M3 over the structural model.
   spec/M2/ledger.json does not change. Every record over a structural model lists it (SORT and DISCH records in
   model_assumptions, UNDO and FACT records in ledger_assumptions); no M0-M2 record, no PAR record and no record over
   I28's raw versioned machine does.
S9 Proof routes over SK (holon/disch/lemmas.py, order.py, proofs.py, section.py, mirror.py; fixed library text emitted
   and checked with each proof file): sp_self, sps_self, sk_self (sk_eq is reflexive), sp_refl, sps_refl, sk_refl
   (sk_eq true implies equal keys), sst_same (a store at k is read back at k) and sst_frame (a store at k1 leaves k2 when
   sk_eq is false both ways), and the ghost-map twins. The DISCH routes prove frames over SK: by evaluation across
   families and members; by a key split on w_eq of the program's own key words within a family; carrying each passed
   check's equation down an action's chain (the convoy); through loops whose stores avoid B's keys (loop frames); and
   across a packed slot's byte fields (bit-field lemmas: a masked write of one field leaves the others). The refusals
   "B reads a slot that is not a literal" and "a store goes through the law's keccak256 parameter" are gone; a route
   that does not apply leaves its law UNKNOWN, naming what it lacks.
S10 tag_exact (holon/sorts/tag_exact.py): a SORT tag law (I30) whose coercion follows from an invariant "for every key
   k, F[k] != 0 implies companion[k] == member_fn(V[k])" over the structural store is proved by a Reach induction (the
   invariant at s0 by computation; one step lemma per action, a key split for the actions that write F or V and a
   frame by evaluation for the others; the coercion at the hit from the guard's equation and the invariant), with a
   checked reachable inhabitant. A law whose invariant is not inductive stays UNKNOWN, naming the failing step lemma.
S11 The lifecycle (Q21's H1). The M3 typed laws bound to the typed model or its sections at the outcome run (51 at
   the prereg: SORT 3, DISCH 35, UNDO 8, FACT 5; a typed law another key adds before the run is remade and remodelled
   with them, I71's UNDO cancel law being the one expected) keep their statements, law files, REGISTRY.json,
   DERIVATION.json and LAWS.bend; only their bound models' cones change, and no extensional equivalence can exist (the
   store's type and its aliasing differ by design). holon.statement_diff gains the kind remodel, accepted unsigned only
   when all of these hold mechanically: (a) the law file, the emitted statement and counter-law and the model path are
   unchanged, only the cone differs; (b) the entry names the human answer that licenses the remodel (Q21), the model
   versions (holon-model-m3/0.2 to holon-model-m3/0.3) and the ledger entry it adds (A-keccak-structural); (c) the new
   model regenerates byte for byte from the pinned generators and inputs; (d) the new model's R5 record on the frozen
   I20 corpus has I20's counts and 0 disagreements, and the keys check lists no collision; (e) the law's record is
   remade on the new model (a status change is an outcome, never a statement change). An entry is {"kind": "remodel",
   "law_id", "milestone": "M3", "license": "Q21", "old_model_version": "holon-model-m3/0.2", "new_model_version":
   "holon-model-m3/0.3", "assumption": "A-keccak-structural", "bound_commit", "reason", "old", "new"} ("old" and "new"
   the law's IR, identical); holon.statement_diff.check_entry(entry, root) checks (a)-(e) and returns its usual
   {"ok", "reason", ..}. `holon bind` rebinds those laws through remodel entries,
   and G2 accepts them. Whether this channel stands is the human's to confirm (Question H1).
S12 Regenerated, never hand-written, by this recipe, after I28's build is on the lead and merged into I68's branch:
   - holon types --milestone M3 (the typed model and its untyped twin, types.json, taint.json, term_size.json) and
     holon keys --milestone M3 (gen/M3/sorts/keys.json);
   - holon fragments with the typed model as its evaluator: results/M3/sorts/refinement.json (R5, on the frozen I20
     corpus and binding);
   - holon run --milestone M3 --laws <the typed laws of S11> (51 at the prereg: SORT 3, DISCH 35, UNDO 8, FACT 5):
     their sections, records and replays; holon bind --milestone M3 (one remodel line per law); holon refute
     --milestone M3 --only filter; holon metrics --milestone M3;
   - every M1, M2, T32 and PAR record in generator_sha256 and seconds alone (holon run --milestone M1 and M2, holon
     profile --milestone T32, holon run --milestone M3 --laws <every PAR law>, then the filter stage), since the
     holon-ir/0.2 and 0.3 closures and I32's hold holon/sorts and holon/disch.
   The outcome run is long (about 15-25 machine-hours, sharded by law on CI runners, Q24); each record is made by holon
   run, never assembled by hand.
S13 Earlier tests. None is amended at this prereg. I43-R1 (tests_m3/test_lean_promoted.py, the statuses and pinned
   files of every record) is red at the base (F40's bend files, I26's Question 5) and stays red until I43's sidecar is
   re-baselined once, after I28, I72, I71 and I68 land; I68's status changes are then part of that baseline, logged with
   it. I32-R2 judges I32's own commits since I66's amendment and does not see I68's. I30-R6's toy clause
   (tests_m3/test_sort_types.py::TestToy) expects tag_exact to prove the kept register, which I68 predicts (I68-P3).
   I30-P8 (the typed cone at most 1.5 times the untyped one) keeps passing: both models change their storage alike
   (I68-R8). I30-P7 (law_terms <= 1000) is red at the base on :363 (1107) and stays red: the counter-law's literal
   states hold SK keys, which count more terms than raw words, so its law_terms grows (not predicted further). An
   earlier test that fails on I68's outcomes is a miss, reported.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KEY = "I68"
DOC = "spec/M2/facts/morph_rollup.extracted.json"
MODEL = ROOT / "gen" / "M3" / "sorts" / "models" / "morph_rollup.extracted.bend"
INIT = ROOT / "gen" / "M3" / "sorts" / "models" / "morph_rollup.extracted.init.json"
UNTYPED = ROOT / "gen" / "M3" / "sorts" / "untyped" / "models" / "morph_rollup_extracted.bend"
KEYS = ROOT / "gen" / "M3" / "sorts" / "keys.json"
REFINE = ROOT / "results" / "M3" / "sorts" / "refinement.json"
INSTRUMENT = "tests_m3/_i68.py"
SECTIONS = ("gen/M3/disch/models", "gen/M3/undo/models", "gen/M3/fact/models")
M3_LEDGER = ROOT / "spec" / "M3" / "ledger.json"


def load_json(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def file_sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(*args) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


def key() -> dict:
    return load_json(ROOT / "spec" / "M3" / "predictions.json")["iterations"][KEY]


def item(kid: str) -> dict:
    k = key()
    for x in k["predictions"] + k["regressions"]:
        if x["id"] == kid:
            return x
    raise AssertionError(f"{kid} is not in the key")


def instrument():
    import tests_m3._i68 as I
    return I


def prereg_commit() -> str:
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(doc, dict) and KEY in (doc.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I68")


def _is_ancestor(a: str, b: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=ROOT).returncode == 0


def _merge() -> str | None:
    added = git("log", "--full-history", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--",
                "docs/iterations/I68.md").split()
    if not added:
        return None
    r = added[0]
    for line in git("rev-list", "--ancestry-path", "--merges", "--reverse", "--parents", f"{r}..HEAD").splitlines():
        c, *parents = line.split()
        if len(parents) > 1 and _is_ancestor(r, parents[1]) and not _is_ancestor(r, parents[0]):
            return c
    return None


def own_commits() -> dict[str, list[str]]:
    """I68's own non-merge commits after its prereg (along the first-parent line of the merge's second parent once
    merged, else prereg..HEAD), each with the paths it changes; another key's commits merged in never count."""
    pre, m = prereg_commit(), _merge()
    revs = [git("rev-parse", f"{m}^2").strip(), f"^{git('rev-parse', f'{m}^1').strip()}", f"^{pre}"] if m else \
        [f"{pre}..HEAD"]
    out = {}
    for c in git("log", "--first-parent", "--no-merges", "--format=%H", *revs).split():
        out[c] = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--no-renames", c).split()
    return out


def at(commit: str, rel: str):
    try:
        return json.loads(git("show", f"{commit}:{rel}"))
    except AssertionError:
        return None


def record(lid: str) -> dict:
    return load_json(ROOT / "results" / "M3" / f"{lid}.json")


def built() -> bool:
    return MODEL.exists() and "model_version: holon-model-m3/0.3" in MODEL.read_text(encoding="utf-8")[:2000]


STRUCTURAL_MODELS = ("gen/M3/sorts/models/morph_rollup.extracted.bend", "gen/M3/undo/models/morph_rollup.extracted.bend",
                     "gen/M3/fact/models/morph_rollup.extracted.fact.bend")


def typed_records() -> dict:
    """{law id: record} of every M3 record bound to the typed model or one of its sections (its artifacts' model; a
    DISCH record names the typed model and its DISCH section): the typed laws of rule S11."""
    out = {}
    for q in sorted((ROOT / "results" / "M3").glob("L*.json")):
        r = load_json(q)
        if (r.get("artifacts") or {}).get("model") in STRUCTURAL_MODELS:
            out[r["law_id"]] = r
    return out


def added_laws() -> set:
    """The typed laws of S11 that another key added after I68's prereg (no law file at the prereg commit)."""
    pre = prereg_commit()
    have = set(git("ls-tree", "--name-only", f"{pre}:laws/M3").split())
    return {lid for lid in typed_records() if f"{lid}.json" not in have}


def need_built(test) -> None:
    if not built():
        test.fail(f"{MODEL.relative_to(ROOT)} is not the structural model (no build)")


def _unstamped(rec: dict) -> dict:
    def walk(v):
        if isinstance(v, dict):
            return {k: walk(w) for k, w in v.items() if k != "seconds"}
        if isinstance(v, list):
            return [walk(w) for w in v]
        return v
    return {k: v for k, v in walk(rec).items() if k != "generator_sha256"}


# ------------------------------------------------------------------------------------------------ prereg
class TestPrereg(unittest.TestCase):
    def test_the_key_pins_the_instrument(self):
        th = key()["thresholds"]
        self.assertEqual(file_sha256(ROOT / INSTRUMENT), th["instrument_sha256"])
        self.assertEqual(hashlib.sha256(sys.modules[__name__].__doc__.encode("utf-8")).hexdigest(),
                         th["contract_docstring_sha256"])

    def test_r6_the_instrument_on_the_capture(self):
        """I68-R6 (construction): the instrument classifies the Rollup's captured deployment as thresholds.s0 pins (9
        literal, 7 structural, 2 raw slots; each structural slot's family, key word and offset), each structural slot is
        the real slot of its key, and the keys check over the capture lists nothing."""
        I = instrument()
        th = key()["thresholds"]["s0"]
        c = I.classify(load_json(INIT), load_json(ROOT / DOC))
        self.assertEqual(sorted(hex(s) for s in c["literal"]), th["literal"])
        self.assertEqual(sorted(hex(s) for s in c["raw"]), th["raw"])
        got = {hex(s): [f, hex(k), o] for s, (f, k, o) in c["structural"].items()}
        self.assertEqual(got, th["structural"])
        fams = {f["name"]: f for f in I.families(load_json(ROOT / DOC))}
        keys = []
        for s, (f, k, o) in c["structural"].items():
            sk = (fams[f]["slot"], 0, (("m", k, o),))
            self.assertEqual(I.real_slot(*sk), s)
            keys.append(sk)
        self.assertEqual(I.keys_check(keys, c["raw"], list(c["literal"])), [])


# ------------------------------------------------------------------------------------------------ construction
class TestStore(unittest.TestCase):
    def test_s1_s4_the_store_and_the_modes(self):
        """S1, S2, S4 (construction): the typed model and its untyped twin are holon-model-m3/0.3 (MODEL3_SK_VERSION;
        MODEL3_VERSION stays the raw mode's holon-model-m3/0.2) with the structural store (SP, SK, KV, sk_eq,
        sload/sstore over SK); no sload or sstore in any M3 typed model or section takes a key that goes through h_get;
        I28's versioned machine, when present, keeps the raw store."""
        need_built(self)
        from holon.sorts import model3 as M3
        self.assertEqual((M3.MODEL3_SK_VERSION, M3.MODEL3_VERSION), ("holon-model-m3/0.3", "holon-model-m3/0.2"))
        for p in (MODEL, UNTYPED):
            self.assertIn("model_version: holon-model-m3/0.3", p.read_text(encoding="utf-8")[:2000], p)
        for p in [MODEL, UNTYPED] + sorted(f for d in SECTIONS for f in (ROOT / d).glob("*.bend")):
            with self.subTest(model=p.relative_to(ROOT).as_posix()):
                t = p.read_text(encoding="utf-8")
                for d in ("type SP is Data:", "type SK is Data:", "type KV is Data:", "def sk_eq(",
                          "def sload(s: HSt, +k: SK) -> W:", "def sstore(s: HSt, +k: SK, +v: W) -> HSt:"):
                    self.assertIn(d, t)
                self.assertEqual(re.findall(r"s(?:load|store)\([^,()]+, h_get\(", t), [])
                self.assertEqual(re.findall(r"List\.append\(&2, U32, [^;\n]{0,400}b_of_w\(W\{", t), [],
                                 "a slot hashed through the table")
        vroot = ROOT / "gen" / "M3" / "versions" / "models"
        for p in sorted(vroot.glob("*.bend")) if vroot.exists() else []:
            with self.subTest(versioned=p.name):
                self.assertNotIn("type SK is Data:", p.read_text(encoding="utf-8"))

    def test_s5_s0_is_the_capture(self):
        """S5: the typed model's s0 holds one entry per non-zero captured slot, keyed as the instrument classifies it
        (literal SK{W{b}, o, Nil}, structural SK{W{b}, w0(), [SP_m{k, W{o2}}]}, raw SK{W{r}, w0(), Nil}), and its real
        image is the captured storage."""
        need_built(self)
        from holon.sorts import skeys as SK
        I = instrument()
        init = load_json(INIT)
        doc = load_json(ROOT / DOC)
        c = I.classify(init, doc)
        image = SK.real_state(SK.s0_keys(MODEL.read_text(encoding="utf-8")))
        want = {int(k, 16): int(v, 16) for k, v in init["storage"].items() if int(v, 16)}
        self.assertEqual(image, want)
        self.assertEqual(len(c["literal"]) + len(c["structural"]) + len(c["raw"]), len(init["storage"]))


# ------------------------------------------------------------------------------------------------ predictions
class TestPredictions(unittest.TestCase):
    def test_p1_r5_agrees(self):
        """I68-P1: results/M3/sorts/refinement.json, holon fragments with the structural typed model as its step
        evaluator, compares I20's corpus (460 traces, 3013 steps, 8894 storage comparisons) with 0 disagreements and 0
        unexplained, I20's statuses per action and panics (as I30-R5 pins them), its evaluator_sha256 the committed typed
        model's."""
        item("I68-P1")
        need_built(self)
        r = load_json(REFINE)
        th = key()["thresholds"]["r5"]
        self.assertEqual((r["traces"], r["steps"], r["storage_slots"]), (th["traces"], th["steps"], th["storage_slots"]))
        self.assertEqual((r["disagreements"], r["unexplained"]), ([], 0))
        self.assertEqual(r["by_action"], th["by_action"])
        self.assertEqual(sorted(r["panics"], key=lambda p: p["src"]), th["panics"])
        self.assertEqual(r["evaluator_sha256"], file_sha256(MODEL))

    def test_p2_the_keys_check_is_clean(self):
        """I68-P2: gen/M3/sorts/keys.json is what `holon keys --milestone M3` writes; it lists the two raw slots
        (EIP-1967 implementation and admin), the 9 literal and 7 structural s0 entries, and every structural key the R5
        corpus and the committed witnesses and inhabitants of the M3 typed records touch, each with its real slot equal
        to the instrument's; and no collision: the instrument's keys check over those keys and slots lists nothing."""
        item("I68-P2")
        need_built(self)
        I = instrument()
        k = load_json(KEYS)
        th = key()["thresholds"]["s0"]
        self.assertEqual(sorted(k["raw"]), sorted(th["raw"]))
        structural = [(int(e["b"], 16), int(e["o"], 16), tuple(("m", int(x["k"], 16), int(x["o"], 16)) for x in e["p"]))
                      for e in k["structural"]]
        for e, sk in zip(k["structural"], structural):
            self.assertEqual(int(e["real"], 16), I.real_slot(*sk))
        self.assertEqual(I.keys_check(structural, [int(x, 16) for x in k["raw"]], [int(x, 16) for x in k["literal"]]),
                         [])
        self.assertEqual(k["collisions"], [])
        self.assertTrue(set(k["sources"]) >= {"deployment", "r5", "witnesses", "inhabitants"}, k["sources"])

    def test_p3_the_toys_tag_exact_law(self):
        """I68-P3: on the toy T30, L_sort_tag_toytypes_83_33f98e53 is PROVED by tag_exact with a checked, reachable
        inhabitant, and the other four toy laws and the guard mutation are decided as I30 designed: I30's
        TestToy.test_toy_statuses and test_toy_kept_register_without_its_version_guard_is_refuted pass."""
        item("I68-P3")
        need_built(self)
        p = subprocess.run([sys.executable, "-m", "unittest",
                            "tests_m3.test_sort_types.TestToy.test_toy_statuses",
                            "tests_m3.test_sort_types.TestToy.test_toy_kept_register_without_its_version_guard_is_refuted"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr[-4000:])

    def test_p4_disch_statuses(self):
        """I68-P4: the 14 DISCH laws of thresholds.flips are PROVED (I31's 13 UNKNOWN blocking laws but
        blk_rollup_363_anyone, with TI2 by the bit-field lemmas, and rev_rollup_363), each record's accepted attempt
        a proof checked by bend and BendTT; L_disch_blk_rollup_363_e11d8bb2_anyone stays UNKNOWN, its bound naming a
        monotone transport; L_disch_blk_rollup_363_e11d8bb2_onlyActiveSubmitter stays REFUTED. DISCH totals 27 PROVED, 7
        REFUTED, 1 UNKNOWN."""
        item("I68-P4")
        need_built(self)
        th = key()["thresholds"]
        for lid in th["flips"]:
            with self.subTest(law=lid):
                r = record(lid)
                self.assertEqual(r["status"], "PROVED")
                ks = {k.get("name"): k.get("result") for k in r.get("kernels") or []}
                self.assertEqual((ks.get("bend2"), ks.get("bendtt")), ("checked", "checked"), r.get("kernels"))
        r = record("L_disch_blk_rollup_363_e11d8bb2_anyone")
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertIn("monotone", json.dumps([r.get("bound"), r.get("attempts")]))
        self.assertEqual(record("L_disch_blk_rollup_363_e11d8bb2_onlyActiveSubmitter")["status"], "REFUTED")
        from collections import Counter
        disch = Counter(record(l)["status"] for l, v in th["statuses_at_prereg"].items() if v[0] == "DISCH")
        self.assertEqual(dict(disch), {"PROVED": 27, "REFUTED": 7, "UNKNOWN": 1})

    def test_p5_non_vacuity(self):
        """I68-P5: every law of thresholds.flips has a checked, reachable inhabitant (non_vacuity status inhabited, reachable
        true), TI4's (L_disch_blk_initializable_120_d9a34b48_caller_rollup_210) included: since F40, initialize4 succeeds
        in one step from s0 and leaves _initialized == 4, as its rev twin's inhabitant at the prereg shows."""
        item("I68-P5")
        need_built(self)
        for lid in key()["thresholds"]["flips"]:
            with self.subTest(law=lid):
                nv = record(lid).get("non_vacuity") or {}
                self.assertEqual((nv.get("status"), nv.get("reachable")), ("inhabited", True), nv.get("bound"))

    def test_p6_g4_writer_canaries(self):
        """I68-P6: the M3 gate's G4 holds disch_writer canaries (I31's exit criterion: adding one non-X writer to a
        PROVED blocking law's class is rejected), one per PROVED DISCH blocking law with a named class, every one
        rejected (holon.disch.gate's G4 check passes)."""
        item("I68-P6")
        need_built(self)
        from types import SimpleNamespace
        from holon.disch import gate as G
        g = G.DischGate(SimpleNamespace(m="M3", root=ROOT, gen=ROOT / "gen" / "M3", results=ROOT / "results" / "M3"))
        g.g4()
        self.assertTrue(g.checks["G4"]["passed"], g.checks["G4"])
        can = [c for c in g.canaries if c["kind"] == "disch_writer"]
        self.assertTrue(can)
        self.assertEqual([c["source_law"] for c in can if not c["rejected"]], [])

    def test_p7_kernels_within_budget(self):
        """I68-P7: every proof and counter-law of the 51 remade records checks in bend2 and BendTT within the
        sidecar's per-file budget: no checker run of an attempt, kernel entry, witness or inhabitant stops on fuel or on
        a time box (the runners' markers: budget_exhausted, "out of fuel", "[timeout]", "time box")."""
        item("I68-P7")
        need_built(self)
        def stops(v, under="") -> list:
            out = []
            if isinstance(v, dict):
                if "budget_exhausted" in v:
                    out.append(f"{under}.budget_exhausted: {v['budget_exhausted']}")
                for k, w in v.items():
                    out += stops(w, f"{under}.{k}")
            elif isinstance(v, list):
                for i, w in enumerate(v):
                    out += stops(w, f"{under}[{i}]")
            elif isinstance(v, str) and under.rsplit(".", 1)[-1] in ("verdict", "result", "marker", "error", "detail") \
                    and re.search(r"out of fuel|\[timeout\]|time box", v):
                out.append(f"{under}: {v[:120]}")
            return out
        for lid in key()["thresholds"]["statuses_at_prereg"]:
            with self.subTest(law=lid):
                r = record(lid)
                self.assertEqual(stops({k: r.get(k) for k in ("attempts", "kernels", "witnesses", "non_vacuity")}), [])


# ------------------------------------------------------------------------------------------------ regressions
class TestRegressions(unittest.TestCase):
    def test_r1_statements_unchanged(self):
        """I68-R1: no own commit changes a law file, REGISTRY.json or DERIVATION.json under laws/, a file under
        gen/M3/laws/, a LAWS.bend or the rule catalog (holon/rules/__init__.py); laws/STATEMENT_DIFF.jsonl only gains
        lines, each of kind remodel (R7), so no catalog_rederivation line is needed."""
        item("I68-R1")
        for c, paths in sorted(own_commits().items()):
            with self.subTest(commit=c[:12]):
                self.assertEqual([f for f in paths if (f.startswith(("laws/", "gen/M3/laws/")) or f.endswith("LAWS.bend")
                                                       or f == "holon/rules/__init__.py")
                                  and f != "laws/STATEMENT_DIFF.jsonl"], [])
                if "laws/STATEMENT_DIFF.jsonl" in paths:
                    old = git("show", f"{c}^1:laws/STATEMENT_DIFF.jsonl").splitlines()
                    new = git("show", f"{c}:laws/STATEMENT_DIFF.jsonl").splitlines()
                    self.assertEqual(new[:len(old)], old, "the statement-change log is append-only")
                    self.assertEqual(sorted({json.loads(x).get("kind") for x in new[len(old):] if x.strip()}),
                                     ["remodel"])

    def test_r2_every_other_status_unchanged(self):
        """I68-R2: every typed M3 law outside thresholds.flips keeps its status at the prereg (SORT 279 and 363 REFUTED,
        406 UNKNOWN; DISCH ext x6 PROVED, noext x6 REFUTED, rev x7 PROVED, blk_363_onlyActiveSubmitter REFUTED,
        blk_363_anyone UNKNOWN; UNDO 3 REFUTED, 5 UNKNOWN; FACT 4 REFUTED, 1 PROVED), and every REFUTED one carries a
        replay that passed; a typed law another key added before the run (S11) keeps the status its record had before
        I68's first own commit that remade it."""
        item("I68-R2")
        need_built(self)
        th = key()["thresholds"]
        for lid, (rule, sub, st) in th["statuses_at_prereg"].items():
            if lid in th["flips"]:
                continue
            with self.subTest(law=lid):
                r = record(lid)
                self.assertEqual(r["status"], st)
                if st == "REFUTED":
                    self.assertEqual((r.get("replay") or {}).get("status"), "passed", lid)
        own = own_commits()
        for lid in sorted(added_laws()):
            rel = f"results/M3/{lid}.json"
            first = next((c for c in reversed(list(own)) if rel in own[c]), None)
            with self.subTest(added=lid):
                self.assertIsNotNone(first, f"{lid}: no own commit remade it (rule S11)")
                before = at(git("rev-parse", f"{first}^1").strip(), rel) or {}
                r = record(lid)
                self.assertEqual(r["status"], before.get("status"), "a typed law another key added keeps its status")
                if r["status"] == "REFUTED":
                    self.assertEqual((r.get("replay") or {}).get("status"), "passed", lid)

    def test_r3_other_records_stamps_only(self):
        """I68-R3: each own commit that changes a record of results/M0, results/M1, results/M2, results/T32 or a PAR
        record of results/M3 leaves it equal to its parent's version but for generator_sha256 and keys named seconds;
        no own commit changes gen/M0, gen/M1, gen/M2 or gen/M3/model/."""
        item("I68-R3")
        par = re.compile(r"^results/M3/L_par[^/]*\.json$|^results/(M0|M1|M2|T32)/L[^/]*\.json$")
        for c, paths in sorted(own_commits().items()):
            parent = git("rev-parse", f"{c}^1").strip()
            with self.subTest(commit=c[:12]):
                self.assertEqual([f for f in paths if f.startswith(("gen/M0/", "gen/M1/", "gen/M2/", "gen/M3/model/"))],
                                 [])
                for f in paths:
                    if par.match(f):
                        o, n = at(parent, f), at(c, f)
                        if o is not None and n is not None:
                            self.assertEqual(_unstamped(n), _unstamped(o), f)

    def test_r4_helpers_and_ledger(self):
        """I68-R4: F32's eight helpers (tests_m3/test_eqprove.py's HELPERS) have, in every structural model and section
        file, exactly the text of the prelude at the prereg (holon.sorts.prelude3's PRELUDE, assembled as the module
        assembles it), and spec/M2/ledger.json is unchanged."""
        item("I68-R4")
        need_built(self)
        pre = prereg_commit()
        self.assertEqual(git("show", f"{pre}:spec/M2/ledger.json"), (ROOT / "spec/M2/ledger.json").read_text())
        ns: dict = {}
        exec(compile(git("show", f"{pre}:holon/sorts/prelude3.py"), "prelude3_at_prereg", "exec"), ns)
        old = ns["PRELUDE"]

        def block(text: str, h: str) -> str | None:
            m = re.search(rf"(?ms)^def {h}\(.*?(?=^def |^type |\Z)", text)
            return m.group(0).rstrip() if m else None
        for h in ("w_eq", "w_add", "w_add_ok", "w_sub", "u_b4", "u_be4", "h_get", "kw_set"):
            want = block(old, h)
            self.assertIsNotNone(want, h)
            for p in [MODEL, UNTYPED] + sorted(f for d in SECTIONS for f in (ROOT / d).glob("*.bend")):
                with self.subTest(helper=h, model=p.relative_to(ROOT).as_posix()):
                    self.assertEqual(block(p.read_text(encoding="utf-8"), h), want)

    def test_r5_the_assumption_where_it_belongs(self):
        """I68-R5: every record over the typed model or a section (the 51 among them, and any typed law of S11 another key
        added) lists A-keccak-structural (SORT and DISCH records in model_assumptions, UNDO and FACT records in
        ledger_assumptions); no other record of results/M0-M3 or T32 does (PAR laws, I28's records over its raw versioned
        machine); spec/M3/ledger.json introduces it by SK, sk_eq and the store's definitions."""
        item("I68-R5")
        need_built(self)
        th = key()["thresholds"]
        typed = typed_records()
        self.assertTrue(set(th["statuses_at_prereg"]) <= set(typed), sorted(set(th["statuses_at_prereg"]) - set(typed)))
        for lid, r in typed.items():
            with self.subTest(law=lid):
                where = "ledger_assumptions" if r["rule"] in ("UNDO", "FACT") else "model_assumptions"
                self.assertIn("A-keccak-structural", r.get(where) or [], where)
        for d in ("M0", "M1", "M2", "T32"):
            for p in sorted((ROOT / "results" / d).glob("L*.json")):
                self.assertNotIn("A-keccak-structural", p.read_text(), p.name)
        for p in sorted((ROOT / "results" / "M3").glob("L*.json")):
            if p.stem not in typed:
                self.assertNotIn("A-keccak-structural", p.read_text(), p.name)
        led = load_json(M3_LEDGER)
        ents = [e for b in led.get("extends") or [] for e in b.get("entries") or [] if e.get("id") == "A-keccak-structural"]
        self.assertEqual(len(ents), 1)
        self.assertTrue({"SK", "sk_eq", "sload", "sstore"} <= set(ents[0]["introduced_by"]), ents[0])

    def test_r7_the_remodel_lines(self):
        """I68-R7 (rule S11): laws/STATEMENT_DIFF.jsonl gains one remodel entry per typed law of S11 (the 51, and any
        typed law another key added before the run), each accepted by holon.statement_diff.check_entry, naming Q21, the
        model versions and A-keccak-structural; G2 on M3 accepts them (the M3 gate's G2 runs on CI)."""
        item("I68-R7")
        need_built(self)
        from holon import statement_diff as SD
        lines = [json.loads(l) for l in (ROOT / "laws" / "STATEMENT_DIFF.jsonl").read_text().splitlines() if l.strip()]
        rem = [e for e in lines if e.get("kind") == "remodel"]
        want = set(key()["thresholds"]["statuses_at_prereg"]) | added_laws()
        self.assertEqual(sorted(e["law_id"] for e in rem), sorted(want))
        for e in rem:
            with self.subTest(law=e["law_id"]):
                self.assertEqual((e.get("license"), e.get("old_model_version"), e.get("new_model_version"),
                                  e.get("assumption")),
                                 ("Q21", "holon-model-m3/0.2", "holon-model-m3/0.3", "A-keccak-structural"))
                self.assertTrue(SD.check_entry(e, ROOT)["ok"])

    def test_r8_i30s_term_ratio_holds(self):
        """I68-R8: I30-P8 keeps passing on the structural models: tests_m3/test_sort_types.py's
        TestTermSize.test_nominal_types_cost_at_most_the_frozen_ratio (the typed cone of the :363 realize law at most 1.5
        times the untyped one), run as it stands."""
        item("I68-R8")
        need_built(self)
        p = subprocess.run([sys.executable, "-m", "unittest",
                            "tests_m3.test_sort_types.TestTermSize.test_nominal_types_cost_at_most_the_frozen_ratio"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr[-4000:])


if __name__ == "__main__":
    unittest.main()
