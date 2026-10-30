"""I83 (= I28b): I28's model debt paid. holon.sorts.model3 compiles the pre-V11 commit actions, so the versioned machine
has in-flight inhabitants (G11V) and the V10->V11 cutover replays; I28's P5 and P6 are re-attempted under this key, as
I62 re-ran I61, and I28 keeps its number and its misses (BUILD_PLAN row I83; docs/iterations/I28.md, Question 1). This
docstring is the contract.

Scope. I28 built the versioned machine of the Rollup's deployed path (V3..V11, 8 MIG edges, the entry edge from the
proxy's placeholder). model3 refused every successor-site (commit) action of V3..V10, each recorded as model debt, so
G11V's in-flight clause found 0 of 8 edges inhabited (I28-P5, missed) and the cutover's inhabitant could not replay
(I28-P6, missed). I83 extends model3's language by generic constructs (L1-L4), so that the versioned model (I28 rule
V6, which follows model3 "whatever it is when the model is built") holds every action of every path version; adds a
candidate generator for the versioned machine's untyped modules (IS1-IS2); writes the in-flight inhabitants under
I28's rule V8 and G11V's clause, unchanged; and replays them under I28's rule V9 (IS3). I28's contract
(tests_m3/test_versions.py), instrument (tests_m3/_i28.py), sidecar (spec/M3/lib/versions.json) and basis
(spec/M3/lib/versions_basis.json) are read and never written; the I28 checks this key re-attempts are run as I28 wrote
them (tests_m3/test_versions.py::TestInflight).

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an instrument_inconsistency line of
spec/M3/amendments.jsonl): tests_m3/_i83.py (no holon import: the in-flight traces' labels, the commit's key, the
binding's stand-in, the real slot of the committed batch, the versions whose commit hashes a memory region the frontend
leaves unsummarised; over I63's history, I28's basis, sidecar, documents and instrument, and the deployment record);
spec/M3/lib/inflight_search.json (the sidecar of the candidate generator: its prefix, migration, actions, callers,
start, moves and budget; no outcome).

Language (L1-L4: holon/sorts/model3.py, each a function or block of its own; generic: nothing names a version, a
contract, an action, a family or a law)
  L1 abi.decode. ["abi.decode", X, ["tuple", T1, .., Tn]], X a bytes value and each Ti a value type (["type",
     "type(<uintN|intN|address|bool|bytesN>)"]) or a dynamic array of one (["index", ["type", ..], null]); ["at", i, D]
     is D's component i: a value type's word at head word i of X, a dynamic array's words at its offset (head word i)
     + 32 + 32 j, for j below its length word. The decoder's checks are solc 0.8.24's tuple decoder's: X holds the
     head (32 n bytes); a dynamic component's offset is at most 2^64 - 1 and leaves room for its length word, and its
     elements end within X; every narrow value or element is clean (an address below 2^160, a bool 0 or 1, a uintN
     below 2^N, an intN sign-extended, a bytesN's low bytes zero). A statement whose terms evaluate an abi.decode term
     reverts, before its own check and before the external calls its terms make, with empty revert data when the
     decoder rejects X: its code is model3's DECODE_CODE, which, like CALL_CODE and FUEL_CODE, is no check of the
     document. A-implicit's exception is kept: the Panic 0x41 of allocating a decoded array in memory is not modelled
     (a length that raises it fails the bounds check in the model: empty revert data where solc panics).
  L2 A dynamic array of value types as an external call's argument: its ABI encoding (its offset in the head; its
     length word, then its words), as abi.encode writes it.
  L3 The memory copy of input bytes. ["mload", ["unknown", s, "memory"], P], P a sum of exactly one input bytes value X
     (a bytes parameter or member of a parameter: a "b" value) and word terms O: the word at offset O of X's memory
     copy (the length word, then X's bytes), zero-padded: the frontend's ["word", X, k] convention. Exact for O up to
     X's length rounded up to 32 (the copy Solidity's conversion allocates and cleans); only in an action with no
     memory write at an unresolved address (no mstores record whose region is null): there the term stays refused.
  L4 calldataload at an input's calldata offset. ["calldataload", P], P a sum of ["cdoff", X] (X an input bytes value)
     and word terms O: the word at offset O of X, zero-padded (the ["word", X, k] convention). Exact for O + 32 up to
     X's length; past X's bytes the calldata that follows X, which the model does not hold, reads zero (stated, not
     modelled).
  Every model model3 wrote before is byte-identical (R1): no prelude definition is added (holon/sorts/prelude3.py does
  not change) and a helper of L1-L4 is emitted only into a model that uses it.

In-flight inhabitants (IS1-IS3)
  IS1 Trace. For every MIG edge a -> b of the deployed path: the upgrade path's prefix up to version a (I28's sidecar
      upgrade_path: the entry edge by upgradeTo; the deployment record's first calls by their recorded callers with their
      recorded calldata; each MIG edge before a with the reinitializer it introduces and upgrade_path.arguments, else
      upgradeTo), then one successful call of a successor-site action of a (PI1), then the migration a -> b
      (upgradeToAndCall with the reinitializer the edge introduces and I28's inflight_arguments, else upgradeTo).
  IS2 Candidate generator (spec/M3/lib/inflight_search.json; holon/versions): the successor-site actions of a in name
      order, by the deployment record's recorded callers in record order (the proxy admin left out); the sidecar's start
      and moves, each candidate run on the versioned machine (holon.versions.machine), within max_evals runs per caller.
      Candidates are proposals; Bend decides (I28's V8).
  IS3 Outputs. I28's V8 unchanged: results/M3/versions/inflight.json and gen/M3/versions/inflight/<a>_<b>/INHABIT.bend
      for every edge, each accepted by Bend and by BendTT when the verdict is enabled; G11V's clause. I28's V9 plus one
      run per inhabited MIG edge: replay/M3/versions/report.json holds, beside the upgrade path and the PAR-init
      witnesses, the run "inflight:<a>-><b>" of every edge's inhabitant, compared step by step as V9 compares every run
      (statuses, revert data, the words of the union of the slots either side writes, the proxy's EIP-1967 slots aside);
      the cutover's run carries V9's legacy reads and getters.

Own commits (LANE_RULES): C_K is the first commit, oldest first, whose spec/M3/predictions.json holds the key I83; end is
the oldest commit reachable from HEAD that adds docs/iterations/I83.md, else HEAD. I83's own commits are the non-merge
commits of `git log --first-parent C_K..end`. The branch reaches the lead only as the second parent of a merge commit and
merges only the lead.

The lifecycle channel (X0-X5: holon/statement_diff.py, the kind model_extension; holon/bindings.py, G2's tie). A model
that gains behaviours changes the cone of every law bound to it under a fixed statement (the PAR-init law over the
versioned layer: VStep gains the commit constructors, vstep and vok their arms, each version module's environment record
the blobs field), and no unsigned kind covered that: a binding_change needs every root unchanged or extensionally equal.
model_extension covers it in the strengthening direction only (more behaviours, never fewer: no claim, statement or
registry hash moves, and a refuted law keeps its witness), mechanically:
  X0 The kind. A line {"kind": "model_extension", "law_id", "milestone", "bound_commit", "defs", "old": IR, "new": IR,
     "reason"} of laws/STATEMENT_DIFF.jsonl, unsigned, accepted by check_entry only when X1-X4 hold, each recomputed by
     the check and never read from the entry; `python -m holon.statement_diff extend --milestone M [--append]` builds
     the entries a milestone's changed bindings need (model_extension_entries). The append records the sha256 of the
     model files and of the proof files the check re-ran, as the other kinds record theirs.
  X1 The statement is fixed: old and new are the same statement (statement_diff.core), and it is the law on the tree.
  X2 Only the cone changes: bound_commit is in HEAD's history and its spec/bindings/<M>.json binds the law; the law's
     binding on the tree (holon.bindings.bind_law) differs from it in its cone alone (the statement hash, the model, the
     emitted statement and counter-law equal); the entry's defs are exactly the changed definitions; each model's
     kernel entries hash to its binding's cone.
  X3 A conservative extension (holon.statement_diff.extension_problems(old_files, new_files) == []), over the binding's
     model file and every module it imports, old (at bound_commit) against new (on the tree), comments and blank lines
     aside: every old top-level definition is in the new file of the same name; an old datatype keeps its header and
     every constructor, in order, each with its old fields as an ordered subsequence of its new ones (same names and
     types); new constructors may be added, and a constructor whose fields grew is extended; in the new text every
     construction and pattern of an extended constructor (K{..} in its own file, A.K{..} where its file is imported as
     A) has its gained fields erased; then every old definition is identical, or both are `match` definitions with the
     same header and match line, every old arm a new arm with the same pattern and body, and every other new arm's
     pattern a constructor that X3 found added. New definitions may be added.
  X4 The verdict is re-established (holon.statement_diff.verdict_problems(old_status, new_record, recheck,
     model_sha256, verdict_available) == []): old_status is the law's record's status at bound_commit; the record on the
     tree names the new model (its model_sha256 is the sha256 of the binding's model file, resolved); the status moves
     only in the honest direction (REFUTED stays REFUTED: its witness survives a conservative extension; PROVED stays
     PROVED or becomes REFUTED; UNKNOWN may become any status); a PROVED or REFUTED record's proof file (artifacts.proof)
     is re-checked by the check itself, by Bend (exit 0, ALL PROOFS CHECK) and by BendTT whenever the verdict is
     available (recheck {"bend": {"exit_code", "marker"}, "bendtt": {..} | null}); no record, no proof file or a missing
     re-check result is a problem.
  X5 G2's tie: holon.bindings.entry_covers accepts an accepted model_extension entry as covering the law's rebinding
     under a fixed statement whose changed definitions are among its defs (as a binding_change), and never a statement
     change.

Shared files, changed only so (not outcome paths): the versioned model's records that read it (the PAR-init record and
its law files, re-decided on the new model: status, witness trace and law unchanged); the M3 records whose generator
closure holds model3 (the typed SORT, DISCH and FACT records: generator_sha256 and keys named seconds only, re-made on
runners); results/M1, results/M2 and results/T32, whose closures hold model3, holon/statement_diff.py and
holon/bindings.py (generator_sha256 and seconds only); results/M3/metrics.json and results/M3/refute/ (re-made); I29's
NAT records when I29's build has merged (re-run on the new model); laws/STATEMENT_DIFF.jsonl (model_extension lines
appended), spec/bindings/M3.json (the bindings of the laws those lines cover, and nothing else) and
spec/bindings/changes.jsonl (appended).

Commit rules: no own commit writes a frozen root, gen/M3/history/, results/M3/history/, gen/M3/versions/documents/,
gen/M3/versions/sidecars/, gen/M3/versions/morph_rollup.versions.json, gen/M3/versions/par_init.json, gen/M3/sorts/,
gen/M3/theory/, a law file, REGISTRY.json or DERIVATION.json under laws/, spec/M1/, spec/M2/, holon/frontends/,
holon/extracted_eval.py, holon/sorts/prelude3.py, holon/rules/, tests_m3/test_versions.py, tests_m3/_i28.py,
tests_m3/_i63.py, spec/M3/lib/versions.json, spec/M3/lib/versions_basis.json, spec/M3/lib/history.json or one of the
six files of the holon-ir/0.1 closure; an own commit that changes laws/STATEMENT_DIFF.jsonl only appends model_extension
lines; one that changes spec/bindings/M3.json changes only the bindings of laws a model_extension line names, and no
other milestone's bindings; an own commit that changes an M3 record changes no status; one that changes a record under
results/M1, results/M2 or results/T32 changes it only in generator_sha256 and keys named seconds.

Commands
  python -m holon versions model|inhabit|replay [--check]
  python -m holon run --milestone M3 --laws L_pinit_Rollup_importGenesisBatch_committedBatches_17_9
  python -m holon.statement_diff extend --milestone M3 [--append]
  python -m holon bind --milestone M3 --laws <ids> --accept-change "<reason>"
  python -m holon gate --milestone M3 --checks G2,G11V
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

import tests_m3._i83 as I
from tests_m3._m3 import ROOT, file_sha256, holon_module, item, load_json, predictions, run_holon

KEY = "I83"
REPORT = "docs/iterations/I83.md"
SIDECAR = "spec/M3/lib/inflight_search.json"
INIT = "gen/M3/versions/models/morph_rollup.versions.init.json"
LAYER_LINK = "gen/M3/versions/models/morph_rollup.versions.bend"
V11_MODULE = "gen/M3/versions/models/morph_rollup_versions_V11.bend"
INFLIGHT = "results/M3/versions/inflight.json"
REPLAY = "replay/M3/versions/report.json"
PINIT = "L_pinit_Rollup_importGenesisBatch_committedBatches_17_9"
LOG = "laws/STATEMENT_DIFF.jsonl"
FROZEN = ("facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/", "docs/M0_SPEC.md",
          "docs/BEND_PRIMER.md", "AGENTS.md", "tools/freeze.py", "FROZEN.sha256")
FORBIDDEN = FROZEN + ("gen/M3/history/", "results/M3/history/", "gen/M3/versions/documents/",
                      "gen/M3/versions/sidecars/", "gen/M3/versions/morph_rollup.versions.json",
                      "gen/M3/versions/par_init.json", "gen/M3/sorts/", "gen/M3/theory/", "spec/M1/", "spec/M2/",
                      "holon/frontends/", "holon/extracted_eval.py", "holon/sorts/prelude3.py", "holon/rules/",
                      "tests_m3/test_versions.py", "tests_m3/_i28.py", "tests_m3/_i63.py", "spec/M3/lib/versions.json",
                      "spec/M3/lib/versions_basis.json", "spec/M3/lib/history.json")
LAW_FILE = re.compile(r"^laws/[^/]+/(L[^/]*\.json|REGISTRY\.json|DERIVATION\.json)$")


# ---------------------------------------------------------------------------------------------- helpers
def need(rel: str) -> Path:
    p = ROOT / rel
    if not p.exists():
        raise AssertionError(f"{rel} is missing (I83 builds it)")
    return p


def git(*args) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), "-c", "core.quotepath=false", *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def num(x) -> int:
    return int(str(x), 0)


def thresholds() -> dict:
    return predictions(KEY)["thresholds"]


def holon_ok(test: unittest.TestCase, args: list, timeout: int = 7200):
    p = run_holon([str(a) for a in args], cwd=ROOT, timeout=timeout)
    test.assertEqual(p.returncode, 0, f"holon {' '.join(map(str, args))}: {(p.stdout + p.stderr)[-3000:]}")
    return p


def i28_tests():
    """I28's contract module, as I28 wrote it (its checks are re-attempted here, never re-written)."""
    import tests_m3.test_versions as T28
    return T28


def prereg_commit() -> str:
    """C_K: the first commit, oldest first, whose spec/M3/predictions.json holds the key I83."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(doc, dict) and KEY in (doc.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I83")


def end_commit() -> str:
    cs = git("log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--", REPORT).split()
    return cs[0] if cs else git("rev-parse", "HEAD").strip()


def own_commits() -> list:
    """I83's own commits (LANE_RULES), oldest first, each with the paths it changes against its parent."""
    c, e = prereg_commit(), end_commit()
    out, cur = [], None
    for ln in git("log", "--first-parent", "--no-merges", "--no-renames", "--reverse", "--format=@%H", "--name-only",
                  f"{c}..{e}").splitlines():
        if ln.startswith("@"):
            cur = (ln[1:], [])
            out.append(cur)
        elif ln.strip() and cur is not None:
            cur[1].append(ln.strip())
    return out


def show_text(commit: str, rel: str) -> str | None:
    try:
        return git("show", f"{commit}:{rel}")
    except AssertionError:
        return None


def show_json(commit: str, rel: str):
    t = show_text(commit, rel)
    try:
        return json.loads(t) if t is not None else None
    except ValueError:
        return None


def run_named(rep: dict, name: str) -> dict:
    runs = [r for r in rep.get("runs") or [] if r.get("name") == name]
    if len(runs) != 1:
        raise AssertionError(f"{REPLAY}: {len(runs)} runs named {name!r}")
    return runs[0]


def layer_sha256() -> str:
    return file_sha256(need(LAYER_LINK).resolve())


# ---------------------------------------------------------------------------------------------- the instruments
class TestInstrument(unittest.TestCase):
    """The instruments are what the key says (construction; green at the prereg)."""

    def test_the_key_pins_the_instruments(self):
        th = thresholds()
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i83.py"), th["instrument_sha256"])
        self.assertEqual(file_sha256(ROOT / SIDECAR), th["sidecar_sha256"])
        self.assertEqual(hashlib.sha256(__doc__.encode("utf-8")).hexdigest(), th["contract_docstring_sha256"])
        # Amended (spec/M3/amendments.jsonl, instrument_inconsistency): a pinned input under one of the key's own
        # outcome_paths is the base's input, which P1 itself changes; it is compared at thresholds.base_commit.
        outcome = tuple(predictions(KEY).get("outcome_paths") or [])
        for rel, sha in th["inputs_sha256"].items():
            with self.subTest(input=rel):
                if rel.startswith(outcome):
                    blob = subprocess.run(["git", "-C", str(ROOT), "show", f"{th['base_commit']}:{rel}"],
                                          capture_output=True, check=True).stdout
                    self.assertEqual(hashlib.sha256(blob).hexdigest(), sha)
                else:
                    self.assertEqual(file_sha256(ROOT / rel), sha)

    def test_the_instrument_states_the_thresholds(self):
        """tests_m3/_i83.py::basis_doc over the committed inputs is the key's basis: the traces' labels and lengths
        (5 .. 12), the key 1, the stand-in, the cutover's legacy reads, the versions V3..V5 whose commit hashes a region
        the frontend leaves unsummarised and the real slot of committedBatches[1]."""
        self.assertEqual(json.loads(json.dumps(I.basis_doc(ROOT))), thresholds()["basis"])


# ---------------------------------------------------------------------------------------------- the lifecycle channel
OLD_M = """# a module
type T is Data:
  A{}
  B{x: W}

type R is Data:
  R{p: W, q: W}

def f(t: T) -> W:
  match t:
    case A{}:
      w0()
    case B{x}:
      x

def g(r: R) -> W:
  match r:
    case R{p, q}:
      p

def h() -> W:
  w0()
"""
OLD_N = """import ./m.bend as M

def mk(a: W, b: W) -> M.R:
  M.R{a, b}
"""
NEW_M = """# a module, extended
type T is Data:
  A{}
  B{x: W}
  C{y: W}

type R is Data:
  R{p: W, z: W, q: W}

def f(t: T) -> W:
  match t:
    case A{}:
      w0()
    case B{x}:
      x
    case C{y}:
      y

def g(r: R) -> W:
  match r:
    case R{p, z, q}:
      p

def h() -> W:
  w0()

def k(r: R) -> W:
  match r:
    case R{p, z, q}:
      z
"""
NEW_N = """import ./m.bend as M

def mk(a: W, b: W) -> M.R:
  M.R{a, w0(), b}
"""
# The renaming variant of X3 (added after C_K): a.bend's field q and definition g renamed, a constructor added.
REN_OLD_A = """# a module
type T is Data:
  A{}
  B{x: W}

type R is Data:
  R{p: W, q: W}

def g(r: R) -> W:
  match r:
    case R{p, q}:
      q

def u(t: T) -> W:
  match t:
    case A{}:
      w0()
    case B{x}:
      g(R{x, x})

def h() -> W:
  w0()
"""
REN_NEW_A = """# a module, extended and renamed
type T is Data:
  A{}
  B{x: W}
  C{y: W}

type R is Data:
  R{p: W, q7: W}

def g7(r: R) -> W:
  match r:
    case R{p, q7}:
      q7

def u(t: T) -> W:
  match t:
    case A{}:
      w0()
    case B{x}:
      g7(R{x, x})
    case C{y}:
      y

def h() -> W:
  w0()
"""
REN_OLD_B = """import ./a.bend as A

def v() -> W:
  A.h()
"""
REN_NEW_B = REN_OLD_B


def sd():
    return holon_module("holon.statement_diff")


class TestLifecycle(unittest.TestCase):
    """X0-X5 (construction of the lifecycle channel; red until I83's build adds it): the coordinator's negative tests
    and their positive controls, over synthetic modules and records."""

    def problems(self, old_m=OLD_M, new_m=NEW_M, old_n=OLD_N, new_n=NEW_N) -> list:
        S = sd()
        self.assertIn("model_extension", S.KINDS)
        return S.extension_problems({"m.bend": old_m, "n.bend": old_n}, {"m.bend": new_m, "n.bend": new_n})

    def test_x3_accepts_a_conservative_extension(self):
        """Positive control: a new constructor with its new arm, a record gaining a field (erased from every pattern and
        construction, in its file and through the importing file's alias), and new definitions."""
        self.assertEqual(self.problems(), [])
        self.assertEqual(self.problems(new_m=OLD_M, new_n=OLD_N), [])

    def test_x3_rejects_a_removed_constructor(self):
        new = NEW_M.replace("  B{x: W}\n", "").replace("    case B{x}:\n      x\n", "")
        self.assertNotEqual(self.problems(new_m=new), [])

    def test_x3_rejects_a_renamed_constructor(self):
        new = NEW_M.replace("  B{x: W}", "  B2{x: W}").replace("case B{x}", "case B2{x}")
        self.assertNotEqual(self.problems(new_m=new), [])

    def test_x3_rejects_a_changed_field(self):
        self.assertNotEqual(self.problems(new_m=NEW_M.replace("  B{x: W}", "  B{x: U32}")), [])
        self.assertNotEqual(self.problems(new_m=NEW_M.replace("R{p: W, z: W, q: W}", "R{p: W, z: W}")), [])

    def test_x3_rejects_a_changed_old_clause(self):
        new = NEW_M.replace("    case A{}:\n      w0()", "    case A{}:\n      w_u(1)")
        self.assertNotEqual(self.problems(new_m=new), [])
        self.assertNotEqual(self.problems(new_n=NEW_N.replace("M.R{a, w0(), b}", "M.R{b, w0(), a}")), [])

    def test_x3_rejects_an_arm_for_no_added_constructor(self):
        new = NEW_M.replace("    case C{y}:\n      y\n", "    case C{y}:\n      y\n    case _:\n      w0()\n")
        self.assertNotEqual(self.problems(new_m=new), [])

    def test_x3_rejects_a_removed_definition(self):
        self.assertNotEqual(self.problems(new_m=NEW_M.replace("def h() -> W:\n  w0()\n", "")), [])

    # Added after C_K (new tests; the C_K tests above are unchanged): the coordinator's condition (a) on the field-gain
    # variant of X3. Erasing the gained fields must leave every old clause byte-identical, and no old clause may read a
    # gained field.
    def test_x3_rejects_an_old_clause_reading_a_gained_field(self):
        """g reads R's gained field z: rejected."""
        old_g = "    case R{p, z, q}:\n      p\n\ndef h"
        self.assertIn(old_g, NEW_M)
        self.assertNotEqual(self.problems(new_m=NEW_M.replace(old_g, "    case R{p, z, q}:\n      z\n\ndef h")), [])

    def test_x3_rejects_a_gained_binder_shadowing_an_old_one(self):
        """g binds the gained position with the name its old body reads (R{p, p, q}): after erasure its text is the old
        text, but the name would read the gained field. Rejected."""
        old_g = "    case R{p, z, q}:\n      p\n\ndef h"
        self.assertIn(old_g, NEW_M)
        problems = self.problems(new_m=NEW_M.replace(old_g, "    case R{p, p, q}:\n      p\n\ndef h"))
        self.assertNotEqual(problems, [])
        self.assertTrue(any("gained field" in p for p in problems), problems)

    # Added after C_K: the renaming variant of X3 (the coordinator's decision, revocable). A module-wide numbering shifts
    # the local names of old clauses when a new action compiles; such a model is accepted only modulo a renaming that
    # is inferred, then verified (kind-preserving, injective, capture-free, fixing roots and cross-file references), with
    # the comparison after it byte for byte. Positive control first, then the coordinator's eight negative tests.
    def renamed(self, a=None, b=None, fixed=frozenset(), renaming=None) -> list:
        S = sd()
        return S.extension_problems({"a.bend": REN_OLD_A, "b.bend": REN_OLD_B},
                                    {"a.bend": REN_NEW_A if a is None else a, "b.bend": REN_NEW_B if b is None else b},
                                    fixed=fixed, renaming=renaming)

    def test_x3_accepts_a_consistent_renaming(self):
        """Positive control: R's field q -> q7 and the definition g -> g7, everywhere in a.bend, with a new constructor
        and its arm; the renaming is inferred as exactly those pairs."""
        S = sd()
        self.assertEqual(S.infer_renaming({"a.bend": REN_OLD_A, "b.bend": REN_OLD_B},
                                          {"a.bend": REN_NEW_A, "b.bend": REN_NEW_B}), {"a.bend": {"g": "g7", "q": "q7"}})
        self.assertEqual(self.renamed(), [])

    def test_x3_renaming_rejects_an_inconsistent_rename(self):
        bad = REN_NEW_A.replace("    case R{p, q7}:\n      q7\n", "    case R{p, q7}:\n      q\n")
        self.assertIn("      q\n", bad)
        self.assertNotEqual(self.renamed(a=bad), [])
        self.assertNotEqual(self.renamed(a=bad, renaming={"a.bend": {"g": "g7", "q": "q7"}}), [])

    def test_x3_renaming_rejects_a_capturing_rename(self):
        problems = self.renamed(renaming={"a.bend": {"g": "h", "q": "q7"}})
        self.assertTrue(any("captures" in p for p in problems), problems)

    def test_x3_renaming_rejects_renaming_a_root(self):
        problems = self.renamed(fixed={"g"})
        self.assertTrue(any("root" in p for p in problems), problems)

    def test_x3_renaming_rejects_renaming_a_cross_file_reference(self):
        a = REN_NEW_A.replace("def h() -> W:", "def h9() -> W:")
        b = REN_NEW_B.replace("A.h()", "A.h9()")
        problems = self.renamed(a=a, b=b)
        self.assertNotEqual(problems, [])
        problems = self.renamed(a=a, b=b, renaming={"a.bend": {"g": "g7", "h": "h9", "q": "q7"}})
        self.assertTrue(any("outside its file" in p for p in problems), problems)

    def test_x3_renaming_rejects_a_rename_that_also_changes_a_clause(self):
        bad = REN_NEW_A.replace("      g7(R{x, x})\n", "      g7(R{x, w0()})\n")
        self.assertNotEqual(bad, REN_NEW_A)
        self.assertNotEqual(self.renamed(a=bad), [])
        self.assertNotEqual(self.renamed(a=bad, renaming={"a.bend": {"g": "g7", "q": "q7"}}), [])

    def test_x3_renaming_rejects_a_non_injective_renaming(self):
        problems = self.renamed(renaming={"a.bend": {"g": "g7", "h": "g7", "q": "q7"}})
        self.assertTrue(any("two names to one" in p for p in problems), problems)

    def test_x3_renaming_rejects_an_image_bound_by_a_new_arm(self):
        bad = REN_NEW_A.replace("    case C{y}:\n      y\n", "    case C{g7}:\n      g7\n")
        self.assertNotEqual(bad, REN_NEW_A)
        problems = self.renamed(a=bad)
        self.assertTrue(any("bound as a local name" in p for p in problems), problems)

    def test_x3_renaming_is_kind_preserving(self):
        problems = self.renamed(renaming={"a.bend": {"g": "q7", "q": "g7"}})
        self.assertTrue(any("maps a" in p for p in problems), problems)

    def test_x4_rejects_a_failing_recheck_on_a_renamed_model(self):
        """The renamed model passes X3, and the law's re-check by the kernels fails on it: the composed gate rejects."""
        S = sd()
        old, new = {"a.bend": REN_OLD_A, "b.bend": REN_OLD_B}, {"a.bend": REN_NEW_A, "b.bend": REN_NEW_B}
        ren = S.infer_renaming(old, new)
        rec = {"status": "REFUTED", "model_sha256": "ab" * 32}
        self.assertEqual(S.extension_verdict_problems(old, new, set(), ren, "REFUTED", rec, self.OK, "ab" * 32, True), [])
        for bad in ({"bend": {"exit_code": 1, "marker": "SOME PROOFS FAIL"}, "bendtt": self.OK["bendtt"]},
                    {"bend": self.OK["bend"], "bendtt": {"exit_code": 1, "marker": "SOME PROOFS FAIL"}}):
            problems = S.extension_verdict_problems(old, new, set(), ren, "REFUTED", rec, bad, "ab" * 32, True)
            self.assertTrue(problems and all(p.startswith("X4: ") for p in problems), problems)

    def test_x1_rejects_a_statement_change(self):
        S = sd()
        self.assertIn("model_extension", S.KINDS)
        law = load_json(ROOT / "laws" / "M3" / f"{PINIT}.json")
        changed = json.loads(json.dumps(law))
        changed["statement"]["claim"]["eq"][1] = {"bool": False}
        r = S.check_entry({"kind": "model_extension", "law_id": PINIT, "milestone": "M3", "bound_commit": "0" * 40,
                           "defs": [], "old": law, "new": changed, "reason": "test"}, ROOT)
        self.assertFalse(r["ok"])
        self.assertNotIn("unknown entry kind", r["reason"])

    def verdict(self, old, rec, recheck, avail=True) -> list:
        S = sd()
        self.assertIn("model_extension", S.KINDS)
        return S.verdict_problems(old, rec, recheck, "ab" * 32, avail)

    OK = {"bend": {"exit_code": 0, "marker": "ALL PROOFS CHECK"}, "bendtt": {"exit_code": 0, "marker": "ALL PROOFS CHECK"}}

    def test_x4_accepts_a_re_established_verdict(self):
        self.assertEqual(self.verdict("REFUTED", {"status": "REFUTED", "model_sha256": "ab" * 32}, self.OK), [])
        self.assertEqual(self.verdict("PROVED", {"status": "REFUTED", "model_sha256": "ab" * 32}, self.OK), [])
        self.assertEqual(self.verdict("UNKNOWN", {"status": "UNKNOWN", "model_sha256": "ab" * 32}, None), [])
        self.assertEqual(self.verdict("REFUTED", {"status": "REFUTED", "model_sha256": "ab" * 32},
                                      dict(self.OK, bendtt=None), avail=False), [])

    def test_x4_rejects_a_refuted_law_whose_counter_law_fails(self):
        bad = {"bend": {"exit_code": 1, "marker": "SOME PROOFS FAIL"}, "bendtt": self.OK["bendtt"]}
        self.assertNotEqual(self.verdict("REFUTED", {"status": "REFUTED", "model_sha256": "ab" * 32}, bad), [])
        bad = {"bend": self.OK["bend"], "bendtt": {"exit_code": 1, "marker": "SOME PROOFS FAIL"}}
        self.assertNotEqual(self.verdict("REFUTED", {"status": "REFUTED", "model_sha256": "ab" * 32}, bad), [])

    def test_x4_rejects_a_missing_recheck(self):
        rec = {"status": "REFUTED", "model_sha256": "ab" * 32}
        self.assertNotEqual(self.verdict("REFUTED", rec, None), [])
        self.assertNotEqual(self.verdict("REFUTED", rec, dict(self.OK, bendtt=None)), [])
        self.assertNotEqual(self.verdict("REFUTED", None, self.OK), [])

    def test_x4_rejects_a_dishonest_move_or_another_model(self):
        self.assertNotEqual(self.verdict("REFUTED", {"status": "PROVED", "model_sha256": "ab" * 32}, self.OK), [])
        self.assertNotEqual(self.verdict("REFUTED", {"status": "UNKNOWN", "model_sha256": "ab" * 32}, None), [])
        self.assertNotEqual(self.verdict("REFUTED", {"status": "REFUTED", "model_sha256": "cd" * 32}, self.OK), [])
        self.assertNotEqual(self.verdict("REFUTED", {"status": "REFUTED"}, self.OK), [])

    def test_x5_the_tie_covers_a_fixed_statement_only(self):
        B = holon_module("holon.bindings")
        self.assertIn("model_extension", sd().KINDS)
        law = load_json(ROOT / "laws" / "M3" / f"{PINIT}.json")
        e = {"kind": "model_extension", "law_id": PINIT, "old": law, "new": law, "defs": ["a", "b"]}
        self.assertTrue(B.entry_covers(e, PINIT, law, False, ["a"]))
        self.assertFalse(B.entry_covers(e, PINIT, law, False, ["a", "c"]))
        self.assertFalse(B.entry_covers(e, PINIT, law, True, ["a"], False))


# ---------------------------------------------------------------------------------------------- the model
class TestModel(unittest.TestCase):
    def test_p1_no_model_debt(self):
        """I83-P1: `holon versions model --check` reproduces the committed versioned model, and its init.json records no
        model debt: every path version's debt and the layer's debt are empty, and every successor-site action of every
        path version (PI1, the instrument's) is among the version's compiled actions."""
        item(KEY, "I83-P1")
        holon_ok(self, ["versions", "model", "--check"])
        init = load_json(need(INIT))
        for v in I.path(ROOT):
            with self.subTest(version=v):
                u = init["versions"][v]
                self.assertEqual(u.get("debt"), [])
                self.assertLessEqual(set(I.successor_actions(ROOT, v)), set(u.get("actions") or []))
        self.assertEqual(init["layer"].get("debt"), [])

    def test_r1_earlier_models_are_byte_identical(self):
        """I83-R1: model3's earlier outputs do not move: `holon model --milestone M3` (typed) and with --untyped write,
        byte for byte, the .bend files of gen/M3/sorts/models/ and gen/M3/sorts/untyped/models/; V11's module (a document
        every action of which compiled before) is the base's; holon/sorts/prelude3.py is the base's."""
        item(KEY, "I83-R1")
        base = thresholds()["base_commit"]
        tmp = Path(tempfile.mkdtemp(prefix="i83-r1-"))
        try:
            for flag, rel in (([], "gen/M3/sorts/models"), (["--untyped"], "gen/M3/sorts/untyped/models")):
                out = tmp / rel.replace("/", "_")
                holon_ok(self, ["model", "--milestone", "M3", *flag, "--out", out])
                for f in sorted((ROOT / rel).glob("*.bend")):
                    with self.subTest(model=f"{rel}/{f.name}"):
                        self.assertTrue((out / f.name).is_file(), f"{f.name} not written")
                        self.assertEqual((out / f.name).read_bytes(), f.read_bytes())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(need(V11_MODULE).read_text(encoding="utf-8"), show_text(base, V11_MODULE))
        self.assertEqual((ROOT / "holon" / "sorts" / "prelude3.py").read_text(encoding="utf-8"),
                         show_text(base, "holon/sorts/prelude3.py"))


class TestL6(unittest.TestCase):
    """L6, found by the build (construction checks added after C_K at the coordinator's request; not predictions): the
    kernel's evaluation shape of a product by a literal c keeps the values.
    - The checked product's test x <= (2^256 - 1) // c is w_mul_ok's for every c >= 1, and a literal 0 never reaches it
      (x * 0 is 0: no check, True{}).
    - w_mulc (zero limbs skipped) is w_mul_small.
    Bend decides both on edge values (0, 1, 2^256 - 1, the boundary q = (2^256 - 1) // c and q + 1) and on
    fixed-seed random words, each side stated against the integer product."""

    MASK = (1 << 256) - 1
    SMALL = [3, 58, 60, (1 << 31) + 1, (1 << 32) - 1]       # w_mulc's literals: below 2^32, no power of two
    BIG = [(1 << 128) + 1, (1 << 256) - 1]                  # checked products by a literal of 2^32 or more

    def xs(self, c: int) -> list:
        import random
        rng = random.Random(83_000_003 + c % 1_000_003)
        q = self.MASK // c
        vals = [0, 1, 2, self.MASK, q, q + 1, (1 << 32) - 1, 1 << 32, (1 << 64) - 1]
        vals += [rng.getrandbits(256) for _ in range(3)] + [rng.getrandbits(40) for _ in range(2)]
        return sorted({v for v in vals if 0 <= v <= self.MASK})

    def test_l6_zero_never_reaches_the_quotient(self):
        M = holon_module("holon.sorts.model3")
        for inner in (["*", ["param", "x"], 0], ["*", 0, ["param", "x"]]):
            with self.subTest(inner=inner):
                ok, _val = M._mul_check(None, inner, "A", "B")
                self.assertEqual(ok, "True{}")
        for c in self.SMALL + self.BIG:
            with self.subTest(c=c):
                ok, _val = M._mul_check(_ShiftStub(M), ["*", ["param", "x"], c], "A", "B")
                self.assertEqual(ok, f"w_le(A, {M.wlit(self.MASK // c)})")
        # the integer identity the comparison rests on, over random factors
        import random
        rng = random.Random(83)
        for _ in range(2000):
            c, x = rng.getrandbits(rng.choice((8, 32, 128, 256))) or 1, rng.getrandbits(rng.choice((8, 64, 200, 256)))
            self.assertEqual(x * c <= self.MASK, x <= self.MASK // c)

    def test_l6_forms_equal_the_old_ones_in_bend(self):
        B, M = holon_module("holon.bend"), holon_module("holon.sorts.model3")
        src = need("gen/M3/versions/models/morph_rollup_versions_V5.bend").read_text(encoding="utf-8")
        for d in ("def w_mulc(", "def w_mul_ok(", "def w_mul_small(", "def w_le("):
            self.assertIn(d, src)
        w = (lambda v: "K." + M.wlit(v))
        lemmas = []
        for c in self.SMALL + self.BIG:
            q = self.MASK // c
            for x in self.xs(c):
                ok = "True{}" if x * c <= self.MASK else "False{}"
                lemmas.append(f"{{K.w_le({w(x)}, {w(q)}) == {ok} : Bool}}")
                lemmas.append(f"{{K.w_mul_ok({w(x)}, {w(c)}) == {ok} : Bool}}")
                if c < (1 << 32):
                    lemmas.append(f"{{K.w_mulc({w(x)}, {c}) == {w(x * c)} : K.W}}")
                    lemmas.append(f"{{K.w_mul_small({w(x)}, {c}) == {w(x * c)} : K.W}}")
        tmp = Path(tempfile.mkdtemp(prefix="i83-l6-"))
        try:
            (tmp / "K.bend").write_text(src, encoding="utf-8")
            body = ["import Base", "import ./K.bend as K", ""]
            body += [f"def l6_{i}() -> {s}:\n  {{==}}\n" for i, s in enumerate(lemmas)]
            (tmp / "P.bend").write_text("\n".join(body), encoding="utf-8")
            r = B.check(tmp / "P.bend", timeout=1800)
            self.assertTrue(r.ok and "ALL PROOFS CHECK" in r.out, r.out[-2000:])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class _ShiftStub:
    """The generator methods _mul_check calls for a literal below 2^32 (its value's code), on no model."""

    def __init__(self, M):
        self.M = M

    def shl(self, k: int) -> str:
        return f"w_shl_{k}"

    def const_mul(self, y: str, c: int) -> str:
        return f"w_mulc({y}, {c})"


# ---------------------------------------------------------------------------------------------- in-flight inhabitants
class TestInflight(unittest.TestCase):
    def test_p2_every_mig_edge_is_inhabited(self):
        """I83-P2 (G11V; I28-P5 re-attempted): I28's own check passes unchanged
        (tests_m3/test_versions.py::TestInflight::test_p5_every_mig_edge_of_the_path_is_inhabited: 8 inhabitants of V8's
        shape, accepted by Bend and BendTT, and `holon gate --milestone M3 --checks G11V` reporting 'in-flight: 8 of 8
        edges inhabited'); and every edge's trace has the instrument's labels (rule IS1, commitBatch the commit at every
        version), its key is 1, and the cutover's legacy words are the bitmap 1 (the labelled stand-in's answer to
        getStakerBitmap) and l1StakingContract, the binding's stand-in."""
        item(KEY, "I83-P2")
        T28 = i28_tests()
        T28.TestInflight("test_p5_every_mig_edge_of_the_path_is_inhabited").test_p5_every_mig_edge_of_the_path_is_inhabited()
        doc = load_json(need(INFLIGHT))
        b = thresholds()["basis"]
        self.assertEqual({x["edge"]: [st["label"] for st in x["trace"]] for x in doc["edges"]}, b["trace_labels"])
        self.assertEqual({x["edge"]: num(x["key"]) for x in doc["edges"]}, {e: b["key"] for e in b["trace_labels"]})
        cut = next(x for x in doc["edges"] if x["edge"] == "V10->V11")
        self.assertEqual({w["reads"]: num(w["word"]) for w in cut["legacy"]},
                         {"Rollup.batchDataStore.signedSequencersBitmap": 1, "Rollup.l1StakingContract": num(b["stand_in"])})

    def test_p3_the_cutover_replays(self):
        """I83-P3 (I28-P6 re-attempted): I28's own check passes unchanged
        (tests_m3/test_versions.py::TestInflight::test_p6_the_cutover_inhabitant_replays): the run inflight:V10->V11 passes
        over the inhabitant's trace, the legacy words read on the real chain are the inhabitant's, and after the real
        upgradeToAndCall(V11, initialize4(..)) batchDataStore(1) returns the bitmap's low 160 bits (1) as its submitter and
        submitterContract() the stand-in."""
        item(KEY, "I83-P3")
        T28 = i28_tests()
        T28.TestInflight("test_p6_the_cutover_inhabitant_replays").test_p6_the_cutover_inhabitant_replays()

    def test_p4_every_inhabitant_replays(self):
        """I83-P4: the replay report holds one run inflight:<a>-><b> per MIG edge, over the edge's inhabitant trace. The
        runs of V6->V7 .. V10->V11 pass. The runs of V3->V4, V4->V5 and V5->V6 agree at every step on the statuses and
        the revert data, and on every compared word but one: at the commit step, the word of committedBatches[1] (the
        real slot keccak256(1 . 161)) differs, the model's batch header carrying model3's hash of the block-context
        region the frontend leaves unsummarised (a havocked region: no table holds its key, so its keccak256 reads 0),
        the chain's the real data hash."""
        item(KEY, "I83-P4")
        rep = load_json(need(REPLAY))
        doc = load_json(need(INFLIGHT))
        b = thresholds()["basis"]
        for x in doc["edges"]:
            e = x["edge"]
            with self.subTest(edge=e):
                r = run_named(rep, f"inflight:{e}")
                self.assertEqual(r["trace"], x["trace"])
                steps = r["steps"]
                self.assertEqual(len(steps), len(x["trace"]))
                for st in steps:
                    self.assertEqual(st["model"], st["real"])
                    self.assertEqual(st["revert"]["model"].lower(), st["revert"]["real"].lower())
                bad = [(i, num(s["slot"])) for i, st in enumerate(steps) for s in st["slots"]
                       if num(s["model"]) != num(s["real"])]
                if e in b["replay_pass_edges"]:
                    self.assertTrue(r["passed"], r)
                    self.assertEqual(bad, [])
                else:
                    a = e.split("->")[0]
                    self.assertIn(e, b["replay_one_slot_edges"])
                    self.assertFalse(r["passed"])
                    self.assertEqual(bad, [(len(steps) - 2, num(b["havoc_slots"][a]))])


# ---------------------------------------------------------------------------------------------- I29's squares
class TestNat(unittest.TestCase):
    def test_p5_i29_cutover_squares_stay_unknown(self):
        """I83-P5 (judged once I29's build has merged into the lead and this branch: its laws are in laws/M3): re-run on
        I83's versioned model, I29's three cutover squares (the key's i29_squares) are UNKNOWN, each record made on the
        versioned model I83 committed (its model_sha256, when it names one, is the layer's)."""
        item(KEY, "I83-P5")
        ids = thresholds()["i29_squares"]
        missing = [lid for lid in ids if not (ROOT / "laws" / "M3" / f"{lid}.json").is_file()]
        self.assertEqual(missing, [], "I29's build has not merged here: I83-P5 is not observed")
        sha = layer_sha256()
        for lid in ids:
            with self.subTest(law=lid):
                rec = load_json(need(f"results/M3/{lid}.json"))
                self.assertEqual(rec.get("status"), "UNKNOWN")
                self.assertEqual(rec.get("model_sha256", sha), sha)


# ---------------------------------------------------------------------------------------------- G2
class TestBindings(unittest.TestCase):
    def test_p6_g2_stays_green_through_model_extension(self):
        """I83-P6: every M3 law bound to the versioned layer (its binding's model is the layer's link) is re-bound by one
        accepted model_extension line that I83's own commits append (laws/STATEMENT_DIFF.jsonl), its verdict re-established
        on the new model; and G2's lifecycle and binding checks over M3 find nothing: every line accepted
        (holon.statement_diff.scan), the statement-change tie, the binding change log (holon.bindings.check_change_log)
        and the bindings re-derived from the committed models (holon.bindings.diff of spec/bindings/M3.json against
        holon.bindings.derive)."""
        item(KEY, "I83-P6")
        S, B = sd(), holon_module("holon.bindings")
        bound = load_json(B.path("M3", ROOT))
        layered = sorted(lid for lid, x in bound["laws"].items() if x.get("model") == LAYER_LINK)
        self.assertIn(PINIT, layered)
        base = show_text(thresholds()["base_commit"], LOG) or ""
        lines = [json.loads(x) for x in (ROOT / LOG).read_text().splitlines()[len(base.splitlines()):] if x.strip()]
        ext = sorted(x["law_id"] for x in lines if x.get("kind") == "model_extension")
        self.assertEqual(ext, layered)
        scan = S.scan(ROOT / S.LOG, ROOT, milestone="M3")
        self.assertEqual(scan["problems"], [])
        tie, _note = S.tie_problems("M3", ROOT, scan)
        self.assertEqual(tie, [])
        log_bad, _note = B.check_change_log("M3", ROOT)
        self.assertEqual(log_bad, [])
        laws, _defs, msgs = B.diff(bound, B.derive("M3", ROOT))
        self.assertEqual(laws, [], msgs)


class TestChangeLog(unittest.TestCase):
    """Added after C_K (the coordinator's decision, revocable): a committed change line's covered_by numbers are read at
    the commit that appended it (holon.bindings.resolve_covered). A lead merge that appends other
    laws/STATEMENT_DIFF.jsonl lines before a branch's own then keeps G2's change log sound: the referenced entry must
    still be present by its exact text, accepted, and an entry covering the law. A line not yet committed reads the
    current numbering, and an unreadable appending commit fails closed."""

    def setUp(self):
        self.B = holon_module("holon.bindings")
        law = load_json(ROOT / "laws" / "M3" / f"{PINIT}.json")
        other_id = sorted(p.stem for p in (ROOT / "laws" / "M3").glob("L_*.json") if p.stem != PINIT)[0]
        other = load_json(ROOT / "laws" / "M3" / f"{other_id}.json")
        self.mine = json.dumps({"kind": "model_extension", "law_id": PINIT, "old": law, "new": law, "defs": ["a", "b"]},
                               sort_keys=True).encode()
        self.other = json.dumps({"kind": "model_extension", "law_id": other_id, "old": other, "new": other,
                                 "defs": ["a", "b"]}, sort_keys=True).encode()
        self.line = {"milestone": "M3", "laws": [PINIT], "law_defs": {PINIT: ["a"]}, "covered_by": {PINIT: 3}}
        self.at_commit = [b'{"x": 1}', b'{"x": 2}', self.mine]   # the log when the change line was committed

    def problems(self, now: list, accepted: set, commit="c" * 40, line=None, at_commit=None, unreadable=False) -> list:
        where: dict = {}
        for k, x in enumerate(now, start=1):
            where.setdefault(x, []).append(k)
        entries = {k: json.loads(x) for k, x in enumerate(now, start=1) if k in accepted}
        at = self.at_commit if at_commit is None else at_commit
        return self.B.change_line_problems(line or self.line, 7, commit, entries, lambda c: None if unreadable else at,
                                           where)

    def test_a_concurrent_branch_appending_before_yours_keeps_the_reference(self):
        """Positive: a lead merge put three lines before the branch's own entry (3 -> 6); position 3 now names one of
        them, and the content still names the entry."""
        now = [b'{"x": 1}', b'{"x": 2}', b'{"y": 1}', b'{"y": 2}', b'{"y": 3}', self.mine]
        self.assertEqual(self.problems(now, {6}), [])
        self.assertNotEqual(self.problems(now, {6}, commit=None), [])   # read by position, it would not be covered

    def test_rejects_the_entry_missing_from_the_current_file(self):
        self.assertNotEqual(self.problems([b'{"x": 1}', b'{"x": 2}', b'{"y": 1}'], {3}), [])

    def test_rejects_the_same_text_but_not_accepted(self):
        self.assertNotEqual(self.problems([b'{"x": 1}', b'{"x": 2}', self.mine], set()), [])

    def test_rejects_an_entry_for_another_law(self):
        at = [b'{"x": 1}', b'{"x": 2}', self.other]
        self.assertNotEqual(self.problems([b'{"x": 1}', b'{"x": 2}', self.other], {3}, at_commit=at), [])

    def test_rejects_a_number_out_of_range_at_the_appending_commit(self):
        line = dict(self.line, covered_by={PINIT: 9})
        problems = self.problems([b'{"x": 1}', b'{"x": 2}', self.mine], {3}, line=line)
        self.assertTrue(any("has no line 9" in p for p in problems), problems)

    def test_rejects_an_uncommitted_line_with_a_wrong_current_number(self):
        now = [b'{"x": 1}', b'{"x": 2}', b'{"y": 1}', self.mine]
        self.assertNotEqual(self.problems(now, {3, 4}, commit=None), [])
        self.assertEqual(self.problems(now, {4}, commit=None, line=dict(self.line, covered_by={PINIT: 4})), [])

    def test_an_unreadable_appending_commit_fails_closed(self):
        problems = self.problems([b'{"x": 1}', b'{"x": 2}', self.mine], {3}, unreadable=True)
        self.assertTrue(any("cannot be read" in p for p in problems), problems)


class TestStore(unittest.TestCase):
    """Added after C_K (the coordinator's decision, revocable): a model_extension line is checkable from the working tree
    alone, as tests/test_40_gate.py checks a copied tree. Every file its acceptance record names (the old and new model
    files, the record, the proof; for a line appended from now on also the law file, the old record and the two
    bindings) is kept, content-addressed, in laws/STATEMENT_DIFF.store/. Off git, G2 checks the line from those files
    (holon.statement_diff._verify_extension_store: X0, X1, X2 when the bindings are named, X3, X4 on the recorded
    re-check); on git the history is a cross-check (_verify_extension_record). A missing file, a file that is no gzip
    and one whose bytes do not hash to its name fail closed. Each case builds a tree holding only the log, the store and
    the config, with no git."""

    @classmethod
    def setUpClass(cls):
        cls.S = sd()
        cls.line = next(json.loads(x) for x in (ROOT / LOG).read_text().splitlines()
                        if '"model_extension"' in x and json.loads(x).get("kind") == "model_extension")
        cls.ext = cls.line["accepted"]["extension"]

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="i83-store-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        shutil.copytree(ROOT / "config", self.root / "config")
        shutil.copytree(ROOT / self.S.STORE, self.root / self.S.STORE)

    def put(self, data: bytes) -> str:
        return self.S.store_write(self.root, data)

    def scan(self, line: dict) -> dict:
        (self.root / LOG).write_text(json.dumps(line, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        self.assertFalse(self.S.in_git(self.root))
        return self.S.scan(self.root / LOG, self.root, milestone="M0")

    def rejected(self, line: dict, needle: str):
        s = self.scan(line)
        self.assertFalse(s["entries"][0]["ok"])
        self.assertTrue(any(needle in p for p in s["problems"]), s["problems"])

    def variant(self, **ext) -> dict:
        line = json.loads(json.dumps(self.line))
        line["accepted"]["extension"].update(ext)
        return line

    def record(self, **changes) -> str:
        rec = json.loads(self.S.store_read(ROOT, self.ext["record"]["sha256"])[0])
        rec.update(changes)
        return self.put(json.dumps(rec, indent=1).encode())

    def test_the_committed_line_checks_off_git(self):
        s = self.scan(self.line)
        self.assertEqual(s["problems"], [])
        self.assertEqual([x["ok"] for x in s["entries"]], [True])
        self.assertEqual(s["stored"], [1])
        self.assertIn("STATEMENT_DIFF.store", s["note"])

    def test_the_store_holds_every_named_file(self):
        """Positive, on the repository: every file the log's model_extension line names is stored and reads back, and the
        store's generator in check mode (`python -m holon.statement_diff store --check`: every file regenerated from git
        and compared byte for byte, writing nothing) finds nothing to write and no problem."""
        for sha, what in self.S.extension_named(self.ext):
            with self.subTest(what=what):
                self.assertIsNone(self.S.store_read(ROOT, sha)[1])
        self.assertEqual(self.S.extension_store_fill(ROOT, check=True), ([], []))

    def test_a_name_is_the_sha256_of_the_content_and_the_bytes_are_its_one_encoding(self):
        """The hash basis: a stored file's name is the sha256 of its decompressed content, never of its gzip bytes, and
        its bytes are store_bytes of that content (gzip level 9, no file name, mtime 0: AGENTS rule 7)."""
        import gzip
        files = sorted((ROOT / self.S.STORE).iterdir())
        self.assertTrue(files)
        for p in files:
            with self.subTest(file=p.name):
                b = p.read_bytes()
                content = gzip.decompress(b)
                self.assertEqual(p.name, hashlib.sha256(content).hexdigest() + ".gz")
                self.assertNotEqual(p.name, hashlib.sha256(b).hexdigest() + ".gz")
                self.assertEqual(b, self.S.store_bytes(content))
                self.assertEqual(b[3] & 0x08, 0)        # FLG: no FNAME
                self.assertEqual(b[4:8], b"\0\0\0\0")   # MTIME 0

    def test_the_check_mode_compares_byte_for_byte(self):
        """Off git the generator's check re-encodes each stored file from its verified content. A file re-encoded at
        another level (a valid gzip of the right content, which G2 still reads) and a file no line names are problems;
        the generator then rewrites the one encoding, and the check passes."""
        import gzip
        (self.root / LOG).write_text(json.dumps(self.line, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        self.assertEqual(self.S.extension_store_fill(self.root, check=True), ([], []))
        sha = self.ext["proof"]["sha256"]
        p = self.root / self.S.STORE / f"{sha}.gz"
        p.write_bytes(gzip.compress(gzip.decompress(p.read_bytes()), compresslevel=1, mtime=0))
        (self.root / self.S.STORE / ("f" * 64 + ".gz")).write_bytes(self.S.store_bytes(b"named by no line"))
        self.assertEqual(self.scan(self.line)["problems"], [])
        done, problems = self.S.extension_store_fill(self.root, check=True)
        self.assertEqual(done, [sha])
        self.assertTrue(any("not store_bytes of its content" in x for x in problems), problems)
        self.assertTrue(any("named by no model_extension line" in x for x in problems), problems)
        (self.root / self.S.STORE / ("f" * 64 + ".gz")).unlink()
        self.assertEqual(self.S.extension_store_fill(self.root), ([sha], []))
        self.assertEqual(self.S.extension_store_fill(self.root, check=True), ([], []))

    def test_a_missing_file_fails_closed(self):
        sha = self.ext["models"]["old"][sorted(self.ext["models"]["old"])[0]]
        (self.root / self.S.STORE / f"{sha}.gz").unlink()
        self.rejected(self.line, "is missing")
        self.assertTrue(any("is missing" in x for x in self.S.extension_store_fill(self.root, check=True)[1]))

    def test_a_valid_gzip_whose_content_is_wrong_fails_closed(self):
        """The file decompresses, and its content hashes to anything but its name: G2 decompresses, then hashes."""
        import gzip
        p = self.root / self.S.STORE / f"{self.ext['proof']['sha256']}.gz"
        p.write_bytes(self.S.store_bytes(gzip.decompress(p.read_bytes()) + b"\n# appended\n"))
        self.assertTrue(gzip.decompress(p.read_bytes()))
        self.rejected(self.line, "not its name")

    def test_a_file_that_is_no_gzip_fails_closed(self):
        (self.root / self.S.STORE / f"{self.ext['record']['sha256']}.gz").write_bytes(b"not a gzip file")
        self.rejected(self.line, "no gzip")

    def test_rejects_a_renaming_that_is_not_the_inferred_one(self):
        """The entry and its acceptance record agree, and both drop one pair of the inferred renaming."""
        line = json.loads(json.dumps(self.line))
        f = sorted(line["renaming"])[0]
        line["renaming"][f].pop(sorted(line["renaming"][f])[0])
        line["accepted"]["extension"]["renaming"] = line["renaming"]
        self.rejected(line, "not the one inferred")

    def test_rejects_an_old_model_the_new_one_does_not_extend(self):
        """The old entry file gains a definition the new model lacks (stored under its own sha256 and named)."""
        models = json.loads(json.dumps(self.ext["models"]))
        top = next(r for r in models["old"] if r.endswith("/morph_rollup_versions.bend"))
        text, _ = self.S.store_read(ROOT, models["old"][top])
        models["old"][top] = self.put(text + b"\ndef holon_store_probe() -> U64:\n  0\n")
        self.rejected(self.variant(models=models), "(X3)")

    def test_rejects_a_record_of_another_law_or_status(self):
        self.rejected(self.variant(record=dict(self.ext["record"], sha256=self.record(law_id="L_none"))), "(X1)")
        self.rejected(self.variant(record=dict(self.ext["record"], sha256=self.record(status="PROVED"))), "(X1)")

    def test_rejects_a_dishonest_status_move(self):
        """REFUTED -> PROVED: the record and its acceptance agree, and a conservative extension keeps the witness."""
        self.rejected(self.variant(record=dict(self.ext["record"], sha256=self.record(status="PROVED"),
                                               new_status="PROVED")), "(X4)")

    def test_rejects_a_record_naming_another_model(self):
        self.rejected(self.variant(record=dict(self.ext["record"], sha256=self.record(model_sha256="0" * 64))), "(X4)")

    def test_rejects_a_recheck_bend_did_not_accept(self):
        rc = json.loads(json.dumps(self.ext["recheck"]))
        rc["bend"]["exit_code"] = 1
        self.rejected(self.variant(recheck=rc), "(X4)")

    def test_rejects_an_acceptance_naming_another_bound_commit(self):
        self.rejected(self.variant(bound_commit="0" * 40), "(X0)")

    def test_the_named_old_record_law_file_and_bindings(self):
        """A line appended from now on also names the old record, the law file and the two bindings: positive, then an
        old status that is not the stored old record's, and defs that are not the bindings' changed definitions."""
        B = holon_module("holon.bindings")
        bc, m = self.ext["bound_commit"], self.line["milestone"]
        self.assertEqual(self.line["law_id"], PINIT)
        rec = json.loads(self.S.store_read(ROOT, self.ext["record"]["sha256"])[0])
        ob = self.S._binding_at(ROOT, bc, m, PINIT)
        rel = B.path(m, ROOT).relative_to(ROOT).as_posix()   # the re-bind: the first later binding that differs
        nb = next(x for x in (self.S._binding_at(ROOT, c, m, PINIT)
                              for c in git("log", "--format=%H", "--reverse", f"{bc}..HEAD", "--", rel).split())
                  if x != ob)
        self.assertEqual(B.changed_defs(ob, nb), sorted(self.line["defs"]))
        named = {"record": dict(self.ext["record"],
                                old_sha256=self.put(git("show", f"{bc}:{self.ext['record']['path']}").encode())),
                 "laws": {"path": rec["artifacts"]["laws"],
                          "sha256": self.put((ROOT / rec["artifacts"]["laws"]).read_bytes())},
                 "bindings": {"old": self.put(self.S.ir.canonical_json(ob)),
                              "new": self.put(self.S.ir.canonical_json(nb))}}
        self.assertEqual(self.scan(self.variant(**named))["problems"], [])
        self.rejected(self.variant(**dict(named, record=dict(named["record"], old_status="UNKNOWN"))), "old status")
        line = self.variant(**named)
        line["defs"] = line["defs"][1:]
        self.rejected(line, "(X2)")

    def test_git_cross_checks_the_history(self):
        """On git the acceptance record is tied to the history: the old model files at bound_commit, the old status."""
        c = git("log", "--format=%H", "-S", '"kind": "model_extension"', "--", LOG).split()[-1]
        self.assertIsNone(self.S._verify_extension_record(self.line, self.ext, c, ROOT))
        models = json.loads(json.dumps(self.ext["models"]))
        models["old"][sorted(models["old"])[0]] = "0" * 64
        why = self.S._verify_extension_record(self.line, dict(self.ext, models=models), c, ROOT)
        self.assertIn(f"is not the file at {self.ext['bound_commit'][:7]}", why or "")
        why = self.S._verify_extension_record(
            self.line, dict(self.ext, record=dict(self.ext["record"], old_status="UNKNOWN")), c, ROOT)
        self.assertIn("old status", why or "")


# ---------------------------------------------------------------------------------------------- generic code
class TestGenericCode(unittest.TestCase):
    def test_new_code_names_no_target(self):
        """Construction (AGENTS rules 2 and 4): every line that commits of I83's own add under holon/ names no action,
        storage family or contract of the head document, no version or edge label, no law id and no interface the gaps
        name; no file under holon/ imports tests_m3 or names tests_m3/_i83.py."""
        head = load_json(ROOT / "spec" / "M2" / "facts" / "morph_rollup.extracted.json")
        names = {a["name"] for a in head["actions"]} | {s["name"] for s in head["storage"]} | {head["contract"]}
        names -= {"owner", "paused", "receive", "initialize", "verifier"}
        names |= {PINIT, "IL1MessageQueue", "IL1Staking", "BatchCodecV0", "morph_rollup"} | set(I.path(ROOT))

        def hits(text: str) -> list:
            return sorted(n for n in names if re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", text))
        for c, _changed in own_commits():
            added = [ln[1:] for ln in git("show", "--format=", "--unified=0", c, "--", "holon/").splitlines()
                     if ln.startswith("+") and not ln.startswith("+++")]
            with self.subTest(commit=c[:12]):
                self.assertEqual(hits("\n".join(added)), [])
        for p in sorted((ROOT / "holon").rglob("*.py")):
            t = p.read_text(encoding="utf-8", errors="replace")
            with self.subTest(file=str(p.relative_to(ROOT))):
                self.assertNotRegex(t, r"(?m)^\s*(from|import)\s+tests_m3\b")
                self.assertNotIn("_i83", t)


# ---------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    def test_r2_i28_outcomes_hold(self):
        """I83-R2: I28's other outcomes hold on I83's tree: `holon versions extract --check` and `holon versions analyze
        --check` reproduce (the documents, the versioned document and the analysis do not move); the PAR-init law is
        REFUTED with the base's witness trace; the replay report's upgrade_path run and the PAR-init witness's run
        pass."""
        item(KEY, "I83-R2")
        holon_ok(self, ["versions", "extract", "--check"])
        holon_ok(self, ["versions", "analyze", "--check"])
        base = show_json(thresholds()["base_commit"], f"results/M3/{PINIT}.json")
        rec = load_json(need(f"results/M3/{PINIT}.json"))
        self.assertEqual(rec["status"], "REFUTED")
        self.assertEqual(rec["witness"]["trace"], base["witness"]["trace"])
        rep = load_json(need(REPLAY))
        self.assertTrue(run_named(rep, "upgrade_path")["passed"])
        self.assertTrue(run_named(rep, PINIT)["passed"])

    def test_r3_own_commits_touch_nothing_forbidden(self):
        """I83-R3 (the contract's commit rules, over I83's own commits)."""
        item(KEY, "I83-R3")
        v01 = set(holon_module("holon.records").generator_files("holon-ir/0.1", ROOT))
        self.assertEqual(len(v01), 6)
        for c, changed in own_commits():
            with self.subTest(commit=c[:12]):
                self.assertEqual([p for p in changed if p.startswith(FORBIDDEN) or LAW_FILE.match(p) or p in v01], [])
                for p in changed:
                    if p == LOG:
                        old, new = show_text(f"{c}^", p) or "", show_text(c, p) or ""
                        self.assertTrue(new.startswith(old), f"{c[:12]}: {LOG} is not appended to")
                        kinds = {json.loads(x).get("kind") for x in new[len(old):].splitlines() if x.strip()}
                        self.assertLessEqual(kinds, {"model_extension"})
                    elif re.match(r"^spec/bindings/[^/]+\.json$", p):
                        self.assertEqual(p, "spec/bindings/M3.json")
                        old, new = show_json(f"{c}^", p) or {}, show_json(c, p) or {}
                        moved = sorted(lid for lid in set(old.get("laws", {})) | set(new.get("laws", {}))
                                       if old.get("laws", {}).get(lid) != new.get("laws", {}).get(lid))
                        lines = [json.loads(x) for x in (show_text(c, LOG) or "").splitlines() if x.strip()]
                        named = {x.get("law_id") for x in lines if x.get("kind") == "model_extension"}
                        self.assertLessEqual(set(moved), named)
                    elif re.match(r"^results/M3/L[^/]*\.json$", p):
                        old, new = show_json(f"{c}^", p), show_json(c, p)
                        if old is not None:
                            self.assertIsNotNone(new, f"{p} deleted")
                            self.assertEqual(old.get("status"), new.get("status"), p)
                    elif re.match(r"^results/(M1|M2|T32)/[^/]+\.json$", p) and not p.endswith(("summary.json",
                                                                                                "metrics.json")):
                        old, new = show_json(f"{c}^", p), show_json(c, p)
                        if old is not None and new is not None:
                            self.assertEqual(_strip_stamps(old), _strip_stamps(new), p)


def _strip_stamps(x):
    if isinstance(x, dict):
        return {k: _strip_stamps(v) for k, v in x.items() if k != "generator_sha256" and "seconds" not in k}
    if isinstance(x, list):
        return [_strip_stamps(v) for v in x]
    return x


if __name__ == "__main__":
    unittest.main()
