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
        for rel, sha in th["inputs_sha256"].items():
            with self.subTest(input=rel):
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
