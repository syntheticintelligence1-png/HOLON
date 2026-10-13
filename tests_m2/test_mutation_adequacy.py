"""I22: A1 mutation adequacy on real code (whitepaper §9.5 auditor A1, §12.1 L1 "Sensitivity", §13 metric "mutation
adequacy", §15.2 M2 exit (b); BUILD_PLAN I22, closes V14). This docstring is the contract.

Plant misimplementations in the real Solidity and Go of the pinned Morph checkout, re-extract them with the M2
frontends, decide the laws on what was extracted, and measure the kill rate against the threshold the human fixed in
advance (0.80 of non-equivalent mutants, docs/HUMAN_ANSWERS.md Q6). The threshold never moves.

Dependencies. The build starts after I20 is merged (holon differential, gen/M2/extracted/, the SORT-width rule,
holon fragments and its binding replay/M2/fragments.json, the re-derivation of the site laws on the extracted facts)
and after I21's exit (zero open high-severity findings). It uses I17 and I19 (with the I19 follow-up A19) and I18 as
they stand at the merge, unchanged.

Frozen inputs (the prereg commit; the instrument's sha256 is pinned below as PREREG_SHA256)
  spec/M2/lib/mutation_preregistration.json  the instrument: threshold, seed, target, in-scope list, operators with
        their rewrite rules and predicted obstructions, cursor pairs, the kill criterion, the equivalence definition,
        the detection channels, the projection roles, the law sets with their decided inputs, and the 110 mutants
        M001-M110 (file, byte offset, length, original text, replacement, line, col, function, edges, actions,
        mutant_sha256). Its "computation" field says how every value was computed from the pinned checkout and the
        committed documents. BUILD_PLAN names spec/M2/preregistration.json; a prereg commit may only add files under
        spec/M2/lib/ (holon/audit/prereg.py), hence the path.
  spec/M2/lib/mutation_diff_sheet.md          what the human signs off and adjudicates: render_sheet() below applied
        to the instrument and the pinned files. No prediction and no outcome appears in it.
  The pinned checkout: config/holon.json replay.morph at the instrument's target.commit, read only. Nothing is ever
  written to it; every mutant lives in a scratch copy.

Human step, after the prereg and before any mutant runs
  spec/M2/equivalent_mutants.json, written from the human's sign-off and verdicts on the diff sheet and committed
  alone (a commit that changes no other file):
    {"adjudication_version": "holon-equivalent-mutants/0.1", "mutants_sha256": <the instrument's>,
     "diff_sheet_sha256": <the instrument's diff_sheet.sha256>, "adjudicator": "human", "catalog_signed_off": true,
     "verdicts": {"M001": {"equivalent": false}, ..., "Mnnn": {"equivalent": true, "reason": "<non-empty>"}}}
  Every mutant id exactly once. The first commit that adds the file must descend from the commit that added the
  instrument and be a proper ancestor of the first commit that adds results/M2/mutation_adequacy.json; the summary's
  pipeline_commit descends from it. `python -m holon mutate run` runs no mutant (exit 2, nothing written) while the
  file is missing, does not parse, misses an id, names another catalog or sheet, or lacks "catalog_signed_off": true.
  Before the file exists the pipeline may run only on the baseline (run --baseline-only) and on fixtures outside the
  catalog. If the human rejects the catalog, nothing runs and a replacement is preregistered under a new key.

Deliverables
  holon/mutate/__init__.py, operators.py, project.py, run.py (helpers may be added under holon/mutate/), the dispatch
  `python -m holon mutate ...` in holon/__main__.py, harness sources under replay/M2/mutation/ when needed. holon/mutate
  names no file, function, variable, type or field of the target: everything target-facing comes from the instrument.
    holon.mutate.operators.catalog(instrument: dict, source: Path) -> list[dict]
        Matches the instrument's operator patterns on the in-scope files of the source tree (Solidity through solc's
        AST, as computation item 3 says; Go on batch_header.go) and returns the mutants with exactly the instrument's
        keys and values, in the instrument's order.
    holon.mutate.operators.apply(mutant: dict, data: bytes) -> bytes
        The mutated file: data[:offset] + replacement + data[offset + length:], after checking that
        data[offset:offset + length] is the mutant's original text (ValueError otherwise).
  CLI (exit 0 ok; 1 --check found a difference; 2 refused, nothing written)
    python -m holon mutate list                                 the catalog from the pinned checkout, as JSON
    python -m holon mutate sheet [--out PATH] [--check]         the diff sheet (default spec/M2/lib/mutation_diff_sheet.md)
    python -m holon mutate project [--documents DIR] [--out PATH] [--check]
                                                                the projected header document (default
                                                                gen/M2/mutation/header.projected.json, from spec/M2/facts)
    python -m holon mutate run --milestone M2 [--only M001,...] [--baseline-only] [--work DIR] [--jobs N]
                               [--no-carry] [--dry-run] [--check]
    python -m holon mutate rate [--check]                       results/M2/mutation_adequacy.json from the records
  --dry-run checks every input (instrument hash, pinned files, adjudication) and exits without running anything.
  run refuses when the pinned checkout is dirty or not at target.commit, when a pinned in-scope file's sha256 differs
  from the instrument's, or (unless --baseline-only) when the adjudication is missing or incomplete.
  --check of run materializes the tree of the records' pipeline_commit (git archive into a scratch directory), reruns
  there the baseline and the listed mutants with --no-carry, and exits 0 iff the rerun's records equal the committed
  ones byte for byte except each law's "decided" field. It checks determinism and that carrying was sound.

The pipeline, per mutant and for the baseline (the null mutant: the unmutated pinned files)
  1. Source. A scratch copy of the pinned checkout (git archive of target.commit, or a copy without .git) with the
     mutant applied (operators.apply). Its sha256 must be the mutant's mutant_sha256.
  2. Re-extraction with the M2 frontends, unchanged: I17 and I19 (with A19) through `holon extract solidity --sidecar
     <copy of spec/M2/lib/extract_solidity.json | extract_rollup.json with target.commit null> --source <scratch>`,
     and I18 through `holon extract go --config <copy of spec/M2/lib/go_frontend.json> --src <scratch>`. The
     documents go to scratch, never to spec/M2/facts/.
  3. A scratch copy of the HOLON tree at pipeline_commit (tests._util.copy_repo semantics) whose
     spec/M2/facts/*.extracted.json are the step-2 documents. Every law set is decided there:
       M0   the projected header document (section Projection) of the step-2 documents, and
            `python -m holon run --milestone M0 --facts <projected> --no-registry` on the 8 statements of laws/M0;
       M1x  `python -m holon differential --milestone M2` (I20): the 15 laws/M1 laws over spec/M1/facts/morph_rollup.json
            decided on the window view of the mutant's transitions document (gen/M2/extracted/m1_view.json);
       M2   `python -m holon derive --milestone M2` over the mutant's documents, then
            `python -m holon run --milestone M2 --no-registry`.
     A set's decided input is what its decision reads that a mutant can change (the instrument's law_sets.<set>.
     decided_input): M0 the projected document; M1x m1_view.json; M2 every file `holon derive --milestone M2` writes
     (laws/M2/ but REGISTRY.json, and gen/M2/sorts/obstructions.json) plus every document a law of laws/M2 names in
     "facts". It is normalized by removing provenance only (law_sets.normalization): a document's top-level
     "extraction" block, a law file's "facts_sha256", DERIVATION.json's "inputs". Statement hashes, refs and site
     specs stay. When a set's normalized decided input is byte-identical to the baseline's, its statuses are the
     baseline's by determinism ("decided": "carried"); --no-carry decides every set anyway.
     Hashing (law_sets.hashing): a normalized document's sha256 is that of its canonical JSON (json.dumps(obj,
     sort_keys=True, separators=(",", ":")), UTF-8); the M2 input, several files, hashes the canonical JSON of
     {repo-relative path: normalized object}. "changed" always means: this sha256 differs from the baseline record's.
  4. Replay (kill_criterion.replay). For every law whose mutant status is REFUTED and whose baseline status is not,
     the refuter's counterexample candidates are tried in its deterministic order, at most
     kill_criterion.replay_candidates of them, on the mutant scratch code and on the unmutated scratch code with the
     replay harness of the law's set (holon/replay.py and holon.mreplay's commit path for M0, holon/mreplay.py for
     M1x, the I15 M2 replay). The recorded witness is the first candidate that replays on the mutant code and not on
     the unmutated code, or the first candidate when none does. A witness replays when running it on the code shows
     the law's claim false; a call of the claim that panics, or returns an error where the claim needs its value,
     makes the claim false (the replay harness recovers the panic and records it).
  5. Detection channels (the instrument's channels; they never decide a kill). Each record lists exactly its runs:
       i20_step  the baseline and every Solidity mutant: I20's step harness (holon fragments, I20's binding,
                 --disagreements in scratch) runs I20's corpus on the mutant contract; its observables are compared
                 with the mutant's extracted model (new_disagreements: those the baseline's i20_step run does not have)
                 and with the unmutated contract's (corpus_differences: the step ids where they differ). A completed
                 run covers at least 2432 steps (I20's m1 source alone, the instrument's computation item 9).
       i16_edge  the baseline, every Go mutant and every Solidity mutant whose edges are non-empty: I16's per-edge
                 refinement of the mutant's projected document against the mutant code on I16's per-edge corpus
                 (new_disagreements as above; corpus_differences null). A completed run covers at least one step.
     The harnesses are I16's and I20's, unchanged; a panic of the mutant code or a build failure ends a channel run
     without a result (its "error" is the message; incomplete).
  6. The kill decision (next section). A step of 1-4 that fails for a reason other than the law is retried once,
     then the outcome is "error". An incomplete channel changes no outcome.
  No step writes a committed file outside the outcome paths (spec/M2/disagreements.json included).

Kill criterion (BUILD_PLAN I22, verbatim): "A mutant is killed iff the obstruction predicted for its operator appears,
localized to the mutated edge: a law moves to REFUTED, with a witness that replays on the mutant code, or a PROVED law
loses its proof. A replay disagreement alone is recorded as 'extraction defect detected', not as a kill." Read as the
instrument's kill_criterion says, and recomputed by TestResults from the records:
  predicted  the operator's predicted_obstruction.laws present in the baseline set ("any": all of them);
  K1         baseline PROVED or UNKNOWN, mutant REFUTED, replay.mutant true and replay.original false (a law moves to
             REFUTED with a witness that replays on the mutant code; that it does not replay on the original
             localizes it to the mutation);
  K2         baseline PROVED, mutant UNKNOWN, and inputs[set].changed (a PROVED law loses its proof; the changed
             decided input attributes the loss to the mutation);
  killed     some predicted law satisfies K1 or K2; the others that do are "unpredicted" (recorded, not counted).
A law that moves to REFUTED (baseline PROVED or UNKNOWN) without replay.mutant true and replay.original false is a
replay disagreement: listed in the record's "replay_disagreements", it makes extraction_defect_detected true and is
never a kill (whitepaper §9.6: a witness that fails on the real code is a model defect). A law REFUTED in the baseline
cannot move to REFUTED; "absent" (not derived in the mutant run) and "error" decide nothing.

Projection (holon/mutate/project.py): the holon-facts/0.1 header document the laws/M0 statements are decided on.
  - types.Header is the instrument's projection.header_type (the laws' binder type) and functions.view its
    projection.view (the specification of what a correct decoder recovers): copied from facts/morph_header.json. No
    other value is read from a frozen fact document.
  - Every other function comes from its role's extracted document (projection.roles): enc_sol from the enc_sol edge,
    ok_sol from the load_sol edge, enc_go_v0 and enc_go_v1 from the Go encoders, ok_go from the Go predicate's paths
    (true exactly where some nil-error path's conditions admit the input; a panicking path is not one), dec_go from
    the Go decoders' reads (getter offset and width; a getter's "when" from the version condition of its function's
    nil-error paths), guarded by ok_go. Go struct fields are named by projection.go_fields; Solidity fields keep their
    extracted names (I17 N1).
  - Cells. A byte of an integer field written with width w (I17 N1: shl(8k, v) gives w = 32 - k; Go put/copy give the
    field's own width) is aligned big-endian onto the Header field of width W: byte j of the w-byte value is byte
    W - w + j of the W-byte value, and a byte with W - w + j < 0 is the constant 0 (the Header field is < 2^(8W)). A
    Solidity byte no op writes stays unknown (A-dirty); a Go byte no op writes is 0.
  - enc_sol keeps the extracted version bound as domain.version_le; its per-version length and ops come from the ok
    paths evaluated at each version 0..version_le. A revert condition on a field other than the version is not
    projected (the frozen M0 domain has none, I17 Question 1): each one is listed in the document's assumptions as
    {"id": "P-unprojected:<edge>", "text", "conds"}.
  - An encoder role whose function has no nil-error ok path (every path panics or errs) projects to an encoder that is
    undefined on every input.
  - Format: holon-facts/0.1 with only additive extensions the M0 model generator accepts (for example a field item
    {"field", "from", "len"} or a "version_in" when), so that facts/morph_header.json compiles to the same bytes as
    before (G1 of gate M0 unchanged). The document's "extraction" block lists the source documents and their sha256.
  - gen/M2/mutation/header.projected.json is the projection of the committed spec/M2/facts documents; `holon mutate
    project --check` reproduces it.

Outputs (canonical JSON: json.dumps(obj, indent=2, sort_keys=True) + "\\n"; no timestamps, no scratch paths, no
process ids; timings stay in scratch)
  results/M2/mutation/baseline.json and results/M2/mutation/<id>.json (one per mutant):
    {"id": "baseline" | "Mnnn", "operator": null | op, "pipeline_commit": "<40 hex>",
     "documents": {"<spec/M2/facts/... path>": {"sha256", "normalized_sha256", "changed": bool}},
                                    every document step 2 writes; sha256 of its bytes, normalized_sha256 of the document
                                    normalized as in step 3 (hashing as in step 3), changed as in step 3
     "extraction": {"status": "ok" | "error", "error": null | "<message>"},
     "inputs": {"M0" | "M1x" | "M2": {"sha256": "<normalized decided input>", "changed": bool, "normalization": [keys]}},
     "laws": {"<law id>": {"set": "M0" | "M1x" | "M2", "baseline": status, "mutant": status | "absent" | "error",
                           "decided": "run" | "carried", "witness_sha256": null | "<hex>",
                           "replay": null | {"mutant": bool, "original": bool, "tried": n}}},
                                    replay is non-null exactly for the laws step 4 replays
     "new_laws": {"<law id>": status},                laws only the mutant run derives (never counted)
     "kill": {"killed": bool, "by": [{"law", "how": "K1" | "K2"}], "unpredicted": [{"law", "how"}]},
     "replay_disagreements": [law ids],
     "refuted_law_new_witness": [law ids],
     "refinement": {"channels": [{"harness": "i20_step" | "i16_edge", "steps": n, "new_disagreements": [ids],
                                  "corpus_differences": [step ids] | null, "error": null | "<message>"}]},
     "extraction_defect_detected": bool | null, "corpus_detected": bool | null,
     "outcome": "killed" | "survived" | "error",
     "class": null | "equivalent" | "error" | "extraction_gap" | "rule_gap",
     "gap_stage": null | "frontend" | "model"}
    The baseline record's statuses ("mutant") fill every mutant's "baseline" field; the baseline decides every set
    ("decided": "run") and reproduces the committed statuses (results/M0, I20's results/M2/differential.json
    "extracted", results/M2 over the committed laws/M2); its documents and inputs are all unchanged, and its own normalized documents are those of the committed spec/M2/facts documents (re-extraction is
    deterministic). extraction_defect_detected is true when replay_disagreements is non-empty or some channel run
    reports a new disagreement, null when neither holds and some channel run is incomplete, false otherwise.
    corpus_detected: for a Solidity mutant, whether the completed i20_step run's corpus_differences is non-empty; null
    when that run is incomplete and for Go mutants. The lists are sorted.
    Classes of mutants that are not killed (whitepaper §9.5: "A miss is an extraction gap or a rule gap"):
    equivalent (adjudicated so), error, extraction_gap (no law set's decided input changed: the mutation never reached
    a law), rule_gap (some decided input changed and no predicted law moved). An extraction gap has gap_stage
    "frontend" when no extracted document changed (the frontends did not see the mutation) and "model" when one did
    (it was lost between the documents and the inputs the laws are decided on); every other record has gap_stage
    null. A killed mutant has class null.
  results/M2/mutation_adequacy.json:
    {"version": "holon-mutation/0.1", "milestone": "M2", "pipeline_commit": "<40 hex>",
     "instrument": {"path", "sha256"}, "mutants_sha256", "adjudication": {"path", "sha256"},
     "threshold": 0.8, "seed": 20261022,
     "mutants": 110, "killed": n, "equivalent": n, "killed_equivalent": n, "errors": n,
     "rate_all": {"num", "den", "value"}, "rate_non_equivalent": {"num", "den", "value"}, "meets_threshold": bool,
     "by_operator": {"<op>": {"mutants", "killed", "equivalent"}},
     "survivors": [{"id", "class", "gap_stage", "why"}], "extraction_defects": [ids], "corpus_detected": [ids],
     "unpredicted": [{"id", "law", "how"}]}
    rate_all = killed / 110; rate_non_equivalent = (killed and not equivalent) / (not equivalent); value =
    num / den as a float; meets_threshold = 5 * num >= 4 * den for rate_non_equivalent (exact integers).
  gen/M2/mutation/header.projected.json (section Projection).
  results/M2/metrics.json (whitepaper §13 metric "mutation adequacy", §12.1 "Sensitivity": certificates report it).
    holon/metrics.py reads the summary: "mutation_adequacy": {"source": "results/M2/mutation_adequacy.json",
    "threshold": 0.8, "rate_all": <the summary's>, "rate_non_equivalent": <the summary's>, "meets_threshold": <the
    summary's>}, and "mutation_adequacy" leaves "not_applicable". The gate regenerates the file as before; it is not
    one of I22's outcome paths because other iterations' commits on parallel branches change it too.

Rules
  - AGENTS.md is binding. Never edit facts/, spec/M1/facts/, laws/M0/ or laws/M1/; never write to the pinned checkout.
  - The extractors, the M0 pipeline, holon differential, holon derive, holon fragments and the I16 and I20 harnesses
    run unchanged. A defect found in them during I22 is a Surprise; a fix needs a new run of all 110 mutants from
    scratch, and the first run's records are reported.
  - Survivors are filed, never explained away: each is a rule gap or an extraction gap (whitepaper §9.5), with its why.
  - No skips. Predictions are never tuned, the catalog never changes after the sign-off, and the threshold never moves.
"""
import difflib
import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, holon_module, load_json, predictions

SPEC2 = ROOT / "spec" / "M2"
PREREG = SPEC2 / "lib" / "mutation_preregistration.json"
PREREG_SHA256 = "e34d53f638c4d994c4156fa4a9a0d7428a86ffc2c39cea0fe862808864d04f04"
SHEET = SPEC2 / "lib" / "mutation_diff_sheet.md"
ADJ = SPEC2 / "equivalent_mutants.json"
RESULTS = ROOT / "results" / "M2"
SUMMARY = RESULTS / "mutation_adequacy.json"
RECORDS = RESULTS / "mutation"
PROJECTED = ROOT / "gen" / "M2" / "mutation" / "header.projected.json"
STATUSES = ("PROVED", "REFUTED", "UNKNOWN")
M0_BASELINE = {"L_par_hdr_v0": "PROVED", "L_par_hdr_v1": "PROVED", "L_rt_go_v0": "PROVED", "L_rt_go_v1": "PROVED",
               "L_rt_go_v2": "PROVED", "L_par_hdr_v2": "REFUTED", "L_par_hdr_ssvh": "REFUTED", "L_dom_hdr": "REFUTED"}
# the Rollup.sol mutants outside the header edges' store sequences and loader (P8, P13)
ROLLUP_ONLY = (["M%03d" % i for i in range(31, 49)] + ["M050", "M051"] + ["M%03d" % i for i in range(54, 63)]
               + ["M064"])
GO_MUTANTS = ["M%03d" % i for i in range(65, 111)]
# the Go mutants whose code panics on I16's per-edge corpus (computation item 10)
GO_PANICS = ["M078", "M107", "M108", "M109", "M110"]


def ids(a: int, b: int) -> list:
    return ["M%03d" % i for i in range(a, b + 1)]


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canon(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def instrument() -> dict:
    return load_json(PREREG)


def need(p: Path):
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing")
    return load_json(p)


def morph() -> Path:
    return Path(load_json(ROOT / "config" / "holon.json")["replay"]["morph"])


def pinned(path: str, commit: str) -> bytes:
    """A file of the pinned checkout at the target commit, read with git show (read only). Missing: a failure."""
    p = subprocess.run(["git", "-C", str(morph()), "show", f"{commit}:{path}"], capture_output=True)
    if p.returncode != 0:
        raise AssertionError(f"cannot read {path} at {commit} from {morph()}: {p.stderr.decode()[-300:]}")
    return p.stdout


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed (this check needs the real checkout's history): "
                             f"{p.stderr[-300:]}")
    return p.stdout.strip()


def is_ancestor(a: str, b: str) -> bool:
    p = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", a, b], capture_output=True)
    if p.returncode not in (0, 1):
        raise AssertionError(f"git merge-base failed: {p.stderr.decode()[-300:]}")
    return p.returncode == 0


def first_add(path: str) -> str:
    out = git("log", "--diff-filter=A", "--format=%H", "--", path).splitlines()
    if not out:
        raise AssertionError(f"{path} was never committed")
    return out[-1]


def apply(m: dict, data: bytes) -> bytes:
    return data[:m["offset"]] + m["replacement"].encode() + data[m["offset"] + m["length"]:]


def render_sheet(inst: dict, sources: dict) -> str:
    """The reference rendering of the diff sheet (computation item 7 of the instrument)."""
    out = "\n".join(inst["diff_sheet"]["header"]) + "\n"
    for m in inst["mutants"]:
        b = sources[m["file"]]
        diff = list(difflib.unified_diff(b.decode().splitlines(), apply(m, b).decode().splitlines(),
                                         "a/" + m["file"], "b/" + m["file"], n=3, lineterm=""))
        out += (f"\n## {m['id']} {m['operator']} {m['variant']} {m['file']}:{m['line']}:{m['col']} {m['function']}\n\n"
                "```diff\n" + "\n".join(diff) + "\n```\n")
    return out


def sources(inst: dict) -> dict:
    return {f: pinned(f, inst["target"]["commit"]) for f in inst["in_scope"]["files"]}


def run_holon(args, cwd=ROOT, timeout=3600):
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=cwd, capture_output=True, text=True,
                          timeout=timeout)


def records() -> dict:
    inst = instrument()
    out = {}
    for m in inst["mutants"]:
        out[m["id"]] = need(RECORDS / f"{m['id']}.json")
    return out


def predicted_laws(inst: dict, op: str, baseline_laws) -> set:
    laws = inst["operators"][op]["predicted_obstruction"]["laws"]
    return set(baseline_laws) if laws == "any" else set(laws) & set(baseline_laws)


def k_how(entry: dict, input_changed: bool):
    """K1 / K2 of the contract for one law entry; input_changed is inputs[<the law's set>].changed of the record."""
    b, m, r = entry["baseline"], entry["mutant"], entry.get("replay") or {}
    if b in ("PROVED", "UNKNOWN") and m == "REFUTED" and r.get("mutant") is True and r.get("original") is False:
        return "K1"
    if b == "PROVED" and m == "UNKNOWN" and input_changed is True:
        return "K2"
    return None


def recompute_kill(inst: dict, rec: dict) -> dict:
    pred = predicted_laws(inst, rec["operator"], rec["laws"])
    by, un = [], []
    for law in sorted(rec["laws"]):
        e = rec["laws"][law]
        how = k_how(e, rec["inputs"][e["set"]]["changed"])
        if how:
            (by if law in pred else un).append({"law": law, "how": how})
    return {"killed": bool(by), "by": by, "unpredicted": un}


def replay_disagreements(rec: dict) -> list:
    """The laws that move to REFUTED without a witness that replays on the mutant code and not on the original."""
    out = []
    for law, e in sorted(rec["laws"].items()):
        if e["baseline"] in ("PROVED", "UNKNOWN") and e["mutant"] == "REFUTED":
            r = e.get("replay") or {}
            if not (r.get("mutant") is True and r.get("original") is False):
                out.append(law)
    return out


def channel_runs(rec: dict) -> list:
    ref = rec.get("refinement")
    if not isinstance(ref, dict) or not isinstance(ref.get("channels"), list):
        raise AssertionError(f"{rec.get('id')}: no refinement channel runs recorded")
    return ref["channels"]


def defect_flag(rec: dict):
    """extraction_defect_detected as the contract defines it from the record's replay disagreements and channel runs."""
    runs = channel_runs(rec)
    if replay_disagreements(rec) or any(r["new_disagreements"] for r in runs):
        return True
    if any(r["error"] for r in runs):
        return None
    return False


def corpus_flag(rec: dict, go: bool):
    """corpus_detected as the contract defines it from the record's i20_step run."""
    if go:
        return None
    runs = [r for r in channel_runs(rec) if r["harness"] == "i20_step"]
    if len(runs) != 1 or runs[0]["error"]:
        return None
    return bool(runs[0]["corpus_differences"])


def normalized_sha256(doc: dict) -> str:
    """The sha256 of a document normalized as step 3 says (its top-level "extraction" block removed), canonical JSON."""
    return sha256(canon({k: v for k, v in doc.items() if k != "extraction"}).encode())


# ======================================================================================== the frozen instrument
class TestInstrument(unittest.TestCase):
    """Integrity of the frozen instrument and the diff sheet (green from the prereg on: they read only frozen inputs
    and the pinned checkout)."""

    def test_the_instrument_is_the_frozen_one(self):
        self.assertEqual(sha256(PREREG.read_bytes()), PREREG_SHA256)
        inst = instrument()
        self.assertEqual(inst["iteration"], "I22")
        self.assertEqual(inst["mutants_sha256"], sha256(canon(inst["mutants"]).encode()))
        self.assertEqual(inst["diff_sheet"]["sha256"], sha256(SHEET.read_bytes()))

    def test_threshold_seed_and_catalog_counts(self):
        inst = instrument()
        self.assertEqual(inst["threshold"]["kill_rate_non_equivalent"], 0.8)
        self.assertEqual(predictions("I22")["thresholds"]["kill_rate_non_equivalent"], 0.8)
        self.assertEqual(inst["seed"], 20261022)
        want = {"mstore_offset": 22, "shl_width": 12, "drop_delete": 6, "swap_cursor": 8, "cmp_boundary": 16,
                "putuint64_offset": 14, "copy_offset": 28, "drop_len_check": 4}
        got = {}
        for m in inst["mutants"]:
            got[m["operator"]] = got.get(m["operator"], 0) + 1
        self.assertEqual(got, want)
        self.assertEqual([m["id"] for m in inst["mutants"]], ids(1, 110))
        self.assertEqual(inst["counts"], dict(want, total=110))

    def test_in_scope_files_are_the_pinned_bytes_the_extractions_read(self):
        inst = instrument()
        src = sources(inst)
        recorded = {}
        for doc in ("morph_header.extracted.json", "morph_rollup.extracted.json", "morph_batch.go.extracted.json"):
            for x in load_json(SPEC2 / "facts" / doc)["extraction"]["inputs"]:
                recorded[x.get("unit") or x.get("path")] = x["sha256"]
        for f, v in inst["in_scope"]["files"].items():
            with self.subTest(file=f):
                self.assertEqual(sha256(src[f]), v["sha256"])
                self.assertEqual(recorded.get(f), v["sha256"])

    def test_each_mutant_is_its_operators_rewrite(self):
        inst = instrument()
        src = sources(inst)
        pair = {a: b for a, b in inst["cursor_pairs"]} | {b: a for a, b in inst["cursor_pairs"]}
        for m in inst["mutants"]:
            with self.subTest(mutant=m["id"]):
                b = src[m["file"]]
                self.assertEqual(b[m["offset"]:m["offset"] + m["length"]].decode(), m["original"])
                nb = apply(m, b)
                self.assertEqual(nb.count(b"\n"), b.count(b"\n"))
                self.assertEqual(sha256(nb), m["mutant_sha256"])
                self.assertEqual(b.count(b"\n", 0, m["offset"]) + 1, m["line"])
                op, o, r = m["operator"], m["original"], m["replacement"]
                if op in ("mstore_offset", "putuint64_offset", "copy_offset"):
                    self.assertEqual(int(r) - int(o), int(m["variant"]))
                elif op == "shl_width":
                    self.assertEqual(int(r) - int(o), int(m["variant"]))
                elif op == "cmp_boundary":
                    self.assertEqual({o: r}, {">=": ">"} if o == ">=" else {">": ">="})
                elif op == "swap_cursor":
                    self.assertEqual(pair[o], r)
                elif op == "drop_delete":
                    self.assertTrue(o.startswith("delete ") and o.endswith(";") and r == "{}")
                else:
                    self.assertTrue(o.startswith("if len(") and r == "{}" + "\n" * o.count("\n"))

    def test_the_diff_sheet_is_the_rendering_of_the_catalog(self):
        inst = instrument()
        self.assertEqual(render_sheet(inst, sources(inst)), SHEET.read_text())


# ======================================================================================== construction
class TestOperators(unittest.TestCase):
    def test_operators_enumerate_exactly_the_catalog(self):
        """I22-R3: holon.mutate.operators matches the instrument's patterns on the pinned checkout and finds exactly the
        110 mutants, with the same keys and values in the same order."""
        ops = holon_module("holon.mutate.operators")
        inst = instrument()
        self.assertEqual(ops.catalog(inst, morph()), inst["mutants"])

    def test_apply_checks_the_original_text(self):
        ops = holon_module("holon.mutate.operators")
        inst = instrument()
        m = inst["mutants"][0]
        data = pinned(m["file"], inst["target"]["commit"])
        self.assertEqual(ops.apply(m, data), apply(m, data))
        with self.assertRaises(ValueError):
            ops.apply(dict(m, original="#"), data)

    def test_the_sheet_cli_reproduces_the_frozen_sheet(self):
        p = run_holon(["mutate", "sheet", "--check"], timeout=600)
        self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])

    def test_mutate_code_holds_no_target_vocabulary(self):
        """holon/mutate names nothing of the target: no in-scope file, function, cursor, projection role value or Go
        field name appears in its code (identifiers and string literals; comments and docstrings may cite them)."""
        import io
        import tokenize
        inst = instrument()
        words = set()
        for f, v in inst["in_scope"]["files"].items():
            words.add(Path(f).name)
            for fn in v["functions"]:
                words.add(re.split(r"[.)]", fn["function"])[-1])
        words |= {c for p in inst["cursor_pairs"] for c in p}
        words |= set(inst["projection"]["go_fields"])
        for role in inst["projection"]["roles"].values():
            names = [role[k] for k in ("encoder", "predicate") if k in role]
            names += [g["decoder"] for g in role.get("getters", [])]
            for n in names:
                words.add(n.split(".")[-1])
                words |= {t.split(".")[-1] for t in re.findall(r"\(([^)]*)\)", n)}
        words -= {"Bytes", "Hash", "Version", "validate"}   # ordinary words of generic code; their qualified names stay
        files = sorted((ROOT / "holon" / "mutate").glob("*.py"))
        self.assertTrue(files, "holon/mutate/ has no module")
        for f in files:
            toks = []
            for t in tokenize.generate_tokens(io.StringIO(f.read_text()).readline):
                if t.type == tokenize.NAME:
                    toks.append(t.string)
                elif t.type == tokenize.STRING and not t.string.startswith(('"""', "'''", 'r"""')):
                    toks += re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", t.string)
            hits = sorted({w for w in words if any(w == x or x.endswith("." + w) or x.startswith(w + ".")
                                                   for x in toks)})
            with self.subTest(module=f.name):
                self.assertEqual(hits, [])

    def test_run_refuses_without_a_complete_adjudication(self):
        """The order rule is mechanical: with spec/M2/equivalent_mutants.json missing, unparsable, missing one id,
        naming another catalog or sheet, or without the catalog sign-off, run --dry-run exits 2, names the file and
        writes nothing; with a complete, signed-off adjudication of this catalog (a synthetic one, in a scratch copy:
        the control that the refusal is not unconditional) it exits 0 and writes nothing. The variants never depend on
        whether the human's file exists yet."""
        import shutil
        from tests_m2._m2 import copy_repo
        holon_module("holon.mutate.run")
        inst = instrument()
        good = {"adjudication_version": "holon-equivalent-mutants/0.1", "mutants_sha256": inst["mutants_sha256"],
                "diff_sheet_sha256": inst["diff_sheet"]["sha256"], "adjudicator": "human", "catalog_signed_off": True,
                "verdicts": {m["id"]: {"equivalent": False} for m in inst["mutants"]}}
        incomplete = json.loads(json.dumps(good))
        del incomplete["verdicts"]["M110"]
        variants = [("missing", None, 2), ("unparsable", "{", 2), ("incomplete", json.dumps(incomplete), 2),
                    ("not_signed_off", json.dumps(dict(good, catalog_signed_off=False)), 2),
                    ("other_catalog", json.dumps(dict(good, mutants_sha256="0" * 64)), 2),
                    ("other_sheet", json.dumps(dict(good, diff_sheet_sha256="0" * 64)), 2),
                    ("complete", json.dumps(good), 0)]
        repo = copy_repo()
        try:
            adj = repo / "spec" / "M2" / "equivalent_mutants.json"
            for name, v, code in variants:
                with self.subTest(adjudication=name):
                    if v is None:
                        adj.unlink(missing_ok=True)
                    else:
                        adj.write_text(v)
                    before = sorted(p.relative_to(repo).as_posix() for p in (repo / "results" / "M2").rglob("*"))
                    p = run_holon(["mutate", "run", "--milestone", "M2", "--dry-run"], cwd=repo, timeout=600)
                    self.assertEqual(p.returncode, code, p.stdout[-800:] + p.stderr[-800:])
                    if code == 2:
                        self.assertIn("equivalent_mutants.json", p.stderr)
                    after = sorted(p.relative_to(repo).as_posix() for p in (repo / "results" / "M2").rglob("*"))
                    self.assertEqual(before, after)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


class TestProjection(unittest.TestCase):
    def test_the_committed_projection_is_reproduced(self):
        need(PROJECTED)
        p = run_holon(["mutate", "project", "--check"], timeout=900)
        self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])

    def test_the_projection_of_the_pinned_code_equals_the_frozen_facts(self):
        """I22-R2: on the committed extracted documents the projection equals the frozen header facts where I17 and
        I18 already compared them: the layouts of enc_sol (versions 0, 1, 2), enc_go_v0 (0) and enc_go_v1 (1) cell for
        cell, the dec_go getters (name, offset, width, when), and ok_sol, ok_go on I17's loader grid."""
        L = holon_module("holon.layout")
        proj = need(PROJECTED)
        frozen = load_json(ROOT / "facts" / "morph_header.json")
        self.assertEqual(proj["facts_version"], "holon-facts/0.1")
        self.assertEqual(proj["types"]["Header"], frozen["types"]["Header"])
        for fn, versions in (("enc_sol", (0, 1, 2)), ("enc_go_v0", (0,)), ("enc_go_v1", (1,))):
            for v in versions:
                with self.subTest(fn=fn, version=v):
                    self.assertEqual(L.layout(proj, fn, v), L.layout(frozen, fn, v))
        strip = lambda gs: [{k: g[k] for k in ("name", "offset", "width", "when") if k in g} for g in gs]
        self.assertEqual(strip(proj["functions"]["dec_go"]["getters"]), strip(frozen["functions"]["dec_go"]["getters"]))
        self.assertEqual(proj["functions"]["view"], frozen["functions"]["view"])
        for fn in ("ok_sol", "ok_go"):
            bad = [(b0, n) for b0 in range(256) for n in (0, 1, 2, 248, 249, 250, 256, 257, 258, 300)
                   if rule_ok(proj["functions"][fn]["rules"], b0, n) != rule_ok(frozen["functions"][fn]["rules"], b0, n)]
            with self.subTest(fn=fn):
                self.assertEqual(bad, [])


def rule_ok(rules: list, b0: int, n: int) -> bool:
    """The holon-facts/0.1 predicate rules (empty / version_in / otherwise; false, true, len_eq, len_ge) on an input of
    length n whose first byte is b0. Projected rules may use only these forms."""
    for r in rules:
        c, then = r["if"], r["then"]
        if c == "empty":
            hit = n == 0
        elif c == "otherwise":
            hit = True
        else:
            hit = n > 0 and b0 in c["version_in"]
        if not hit:
            continue
        if then is False or then is True:
            return then
        if "len_eq" in then:
            return n == then["len_eq"]
        if "len_ge" in then:
            return n >= then["len_ge"]
        raise AssertionError(f"unknown rule form {r}")
    return False


# ======================================================================================== adjudication and order
class TestAdjudication(unittest.TestCase):
    def test_every_mutant_is_adjudicated_once_against_this_catalog(self):
        inst = instrument()
        a = need(ADJ)
        self.assertEqual(a["adjudication_version"], "holon-equivalent-mutants/0.1")
        self.assertEqual(a["adjudicator"], "human")
        self.assertIs(a["catalog_signed_off"], True)
        self.assertEqual(a["mutants_sha256"], inst["mutants_sha256"])
        self.assertEqual(a["diff_sheet_sha256"], inst["diff_sheet"]["sha256"])
        self.assertEqual(sorted(a["verdicts"]), ids(1, 110))
        for i, v in a["verdicts"].items():
            with self.subTest(mutant=i):
                self.assertIsInstance(v["equivalent"], bool)
                if v["equivalent"]:
                    self.assertTrue(isinstance(v.get("reason"), str) and v["reason"].strip())

    def test_the_adjudication_was_committed_alone_before_any_result(self):
        c_inst = first_add("spec/M2/lib/mutation_preregistration.json")
        c_adj = first_add("spec/M2/equivalent_mutants.json")
        c_res = first_add("results/M2/mutation_adequacy.json")
        self.assertTrue(is_ancestor(c_inst, c_adj) and c_inst != c_adj)
        self.assertTrue(is_ancestor(c_adj, c_res) and c_adj != c_res)
        self.assertEqual(git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", c_adj).splitlines(),
                         ["spec/M2/equivalent_mutants.json"])
        s = need(SUMMARY)
        self.assertTrue(is_ancestor(c_adj, s["pipeline_commit"]), "the run started before the adjudication")


# ======================================================================================== results (construction)
class TestResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inst = instrument()
        cls.s = need(SUMMARY)
        cls.base = need(RECORDS / "baseline.json")
        cls.r = records()
        cls.adj = need(ADJ)

    def test_summary_names_its_inputs(self):
        s = self.s
        self.assertEqual(s["version"], "holon-mutation/0.1")
        self.assertEqual(s["instrument"], {"path": "spec/M2/lib/mutation_preregistration.json", "sha256": PREREG_SHA256})
        self.assertEqual(s["mutants_sha256"], self.inst["mutants_sha256"])
        self.assertEqual(s["adjudication"], {"path": "spec/M2/equivalent_mutants.json", "sha256": sha256(ADJ.read_bytes())})
        self.assertEqual((s["threshold"], s["seed"], s["mutants"]), (0.8, 20261022, 110))
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", s["pipeline_commit"]))
        self.assertTrue(is_ancestor(s["pipeline_commit"], "HEAD"))
        for rec in [self.base, *self.r.values()]:
            self.assertEqual(rec["pipeline_commit"], s["pipeline_commit"])

    def test_every_record_covers_the_baseline_law_set(self):
        laws = set(self.base["laws"])
        self.assertEqual({k for k, v in self.base["laws"].items() if v["set"] == "M0"}, set(M0_BASELINE))
        self.assertEqual(len([k for k, v in self.base["laws"].items() if v["set"] == "M1x"]), 15)
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                self.assertEqual(rec["id"], i)
                self.assertEqual(set(rec["laws"]), laws)
                for law, e in rec["laws"].items():
                    self.assertEqual(e["baseline"], self.base["laws"][law]["mutant"])
                    self.assertIn(e["mutant"], STATUSES + ("absent", "error"))
                    if e["decided"] == "carried":
                        self.assertFalse(rec["inputs"][e["set"]]["changed"])
                        self.assertEqual(e["mutant"], e["baseline"])

    def test_kill_decisions_follow_the_criterion(self):
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                want = recompute_kill(self.inst, rec)
                self.assertEqual(rec["kill"], want)
                outcome = "error" if rec["extraction"]["status"] == "error" or (
                    not want["killed"] and any(e["mutant"] == "error" for e in rec["laws"].values())) else (
                    "killed" if want["killed"] else "survived")
                self.assertEqual(rec["outcome"], outcome)

    def test_channel_flags_follow_their_runs(self):
        """replay_disagreements, extraction_defect_detected and corpus_detected are exactly what the laws and the
        channel runs say; Go mutants have no corpus channel."""
        go = set(GO_MUTANTS)
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                self.assertEqual(rec["replay_disagreements"], replay_disagreements(rec))
                self.assertIs(rec["extraction_defect_detected"], defect_flag(rec))
                self.assertIs(rec["corpus_detected"], corpus_flag(rec, i in go))

    def test_every_record_holds_exactly_its_channel_runs(self):
        """The channels are never vacuous: the baseline and every mutant whose extraction succeeded list exactly the
        runs the contract names (i20_step for the baseline and each Solidity mutant; i16_edge for the baseline, each Go
        mutant and each Solidity mutant with edges), and a completed run covers its corpus (i20_step at least 2432
        steps, i16_edge at least one)."""
        go = set(GO_MUTANTS)
        edges = {m["id"]: m["edges"] for m in self.inst["mutants"]}
        for i, rec in [("baseline", self.base), *self.r.items()]:
            if rec["extraction"]["status"] != "ok":
                continue
            with self.subTest(record=i):
                want = (["i16_edge", "i20_step"] if i == "baseline" else ["i16_edge"] if i in go
                        else sorted((["i16_edge"] if edges[i] else []) + ["i20_step"]))
                runs = channel_runs(rec)
                self.assertEqual(sorted(r["harness"] for r in runs), want)
                for r in runs:
                    self.assertTrue(r["error"] is None or (isinstance(r["error"], str) and r["error"].strip()), r)
                    self.assertEqual(r["new_disagreements"], sorted(r["new_disagreements"]))
                    if i == "baseline":
                        self.assertIsNone(r["error"], r)
                        self.assertEqual(r["new_disagreements"], [])
                    if r["harness"] == "i20_step":
                        self.assertIsInstance(r["corpus_differences"], list)
                        if i == "baseline":
                            self.assertEqual(r["corpus_differences"], [])
                        if r["error"] is None:
                            self.assertGreaterEqual(r["steps"], 2432, r)
                    else:
                        self.assertIsNone(r["corpus_differences"])
                        if r["error"] is None:
                            self.assertGreaterEqual(r["steps"], 1, r)

    def test_changed_flags_are_recomputed_from_the_hashes(self):
        """Every "changed" flag is the comparison of the record's sha256 with the baseline record's: documents by
        normalized_sha256, inputs by sha256. The baseline changes nothing, its normalized documents are the committed
        spec/M2/facts documents' (re-extraction is deterministic), and its M0 input is the normalized committed
        projection gen/M2/mutation/header.projected.json."""
        b = self.base
        self.assertTrue({"spec/M2/facts/morph_header.extracted.json", "spec/M2/facts/morph_rollup.extracted.json",
                         "spec/M2/facts/morph_batch.go.extracted.json"} <= set(b["documents"]), sorted(b["documents"]))
        self.assertEqual(sorted(b["inputs"]), ["M0", "M1x", "M2"])
        for path, d in b["documents"].items():
            with self.subTest(baseline_document=path):
                self.assertIs(d["changed"], False)
                self.assertEqual(d["normalized_sha256"], normalized_sha256(load_json(ROOT / path)))
        for k, v in b["inputs"].items():
            self.assertIs(v["changed"], False, k)
        self.assertEqual(b["inputs"]["M0"]["sha256"], normalized_sha256(need(PROJECTED)))
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                if rec["extraction"]["status"] != "ok":
                    continue
                self.assertEqual(set(rec["documents"]), set(b["documents"]))
                self.assertEqual(set(rec["inputs"]), set(b["inputs"]))
                for path, d in rec["documents"].items():
                    self.assertIs(d["changed"], d["normalized_sha256"] != b["documents"][path]["normalized_sha256"], path)
                for k, v in rec["inputs"].items():
                    self.assertIs(v["changed"], v["sha256"] != b["inputs"][k]["sha256"], k)

    def test_the_baseline_reproduces_the_committed_statuses(self):
        """The null mutant decides every set as the committed results do: M0 as results/M0, M1x as I20's
        results/M2/differential.json ("extracted"), and M2 over exactly the committed laws/M2 laws as results/M2."""
        base = {law: e for law, e in self.base["laws"].items()}
        for law, e in base.items():
            with self.subTest(law=law):
                self.assertEqual(e["decided"], "run")
                self.assertIn(e["mutant"], STATUSES)
        m0 = {law: load_json(ROOT / "results" / "M0" / f"{law}.json")["status"] for law in M0_BASELINE}
        self.assertEqual({k: v["mutant"] for k, v in base.items() if v["set"] == "M0"}, m0)
        diff = need(RESULTS / "differential.json")["laws"]
        self.assertEqual({k: v["mutant"] for k, v in base.items() if v["set"] == "M1x"},
                         {k: v["extracted"] for k, v in diff.items()})
        m2 = sorted(p.stem for p in (ROOT / "laws" / "M2").glob("L_*.json"))
        self.assertTrue(m2)
        self.assertEqual({k: v["mutant"] for k, v in base.items() if v["set"] == "M2"},
                         {k: load_json(RESULTS / f"{k}.json")["status"] for k in m2})

    def test_metrics_report_mutation_adequacy(self):
        """Whitepaper §13 metric "mutation adequacy" and §12.1 "Sensitivity": results/M2/metrics.json reports both
        rates from the summary, and the metric is no longer listed as not applicable."""
        m = need(RESULTS / "metrics.json")
        s = self.s
        self.assertEqual(m["mutation_adequacy"], {"source": "results/M2/mutation_adequacy.json", "threshold": 0.8,
                                                  "rate_all": s["rate_all"],
                                                  "rate_non_equivalent": s["rate_non_equivalent"],
                                                  "meets_threshold": s["meets_threshold"]})
        self.assertNotIn("mutation_adequacy", m.get("not_applicable") or {})

    def test_survivors_are_classified(self):
        eq = {i for i, v in self.adj["verdicts"].items() if v["equivalent"]}
        listed = {x["id"]: x for x in self.s["survivors"]}
        self.assertEqual([x["id"] for x in self.s["survivors"]],
                         sorted(i for i, rec in self.r.items() if rec["outcome"] != "killed"))
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                if rec["outcome"] == "killed":
                    self.assertIsNone(rec["class"])
                    self.assertIsNone(rec["gap_stage"])
                    self.assertNotIn(i, listed)
                    continue
                stage = None
                if i in eq:
                    want = "equivalent"
                elif rec["outcome"] == "error":
                    want = "error"
                elif not any(v["changed"] for v in rec["inputs"].values()):
                    want = "extraction_gap"
                    stage = "model" if any(v["changed"] for v in rec["documents"].values()) else "frontend"
                else:
                    want = "rule_gap"
                self.assertEqual((rec["class"], rec["gap_stage"]), (want, stage))
                self.assertEqual((listed[i]["class"], listed[i]["gap_stage"]), (want, stage))
                self.assertTrue(listed[i]["why"].strip())

    def test_the_rates_are_recomputed(self):
        """BUILD_PLAN I22 Exit: the rate, recomputed by test. Both rates are reported."""
        eq = {i for i, v in self.adj["verdicts"].items() if v["equivalent"]}
        killed = {i for i, rec in self.r.items() if rec["outcome"] == "killed"}
        ne = set(self.r) - eq
        s = self.s
        self.assertEqual((s["killed"], s["equivalent"], s["killed_equivalent"]),
                         (len(killed), len(eq), len(killed & eq)))
        self.assertEqual(s["errors"], sum(1 for rec in self.r.values() if rec["outcome"] == "error"))
        self.assertEqual((s["rate_all"]["num"], s["rate_all"]["den"]), (len(killed), 110))
        self.assertEqual((s["rate_non_equivalent"]["num"], s["rate_non_equivalent"]["den"]), (len(killed & ne), len(ne)))
        for k in ("rate_all", "rate_non_equivalent"):
            self.assertAlmostEqual(s[k]["value"], s[k]["num"] / s[k]["den"])
        self.assertEqual(s["meets_threshold"], 5 * len(killed & ne) >= 4 * len(ne))
        self.assertEqual(s["extraction_defects"], sorted(i for i, rec in self.r.items() if rec["extraction_defect_detected"]))
        self.assertEqual(s["corpus_detected"], sorted(i for i, rec in self.r.items() if rec["corpus_detected"]))
        self.assertEqual(s["unpredicted"], [dict(x, id=i) for i, rec in sorted(self.r.items())
                                            for x in rec["kill"]["unpredicted"]])
        for op in self.inst["operators"]:
            mine = [m["id"] for m in self.inst["mutants"] if m["operator"] == op]
            with self.subTest(operator=op):
                self.assertEqual(s["by_operator"][op], {"mutants": len(mine), "killed": len(killed & set(mine)),
                                                        "equivalent": len(eq & set(mine))})
        p = run_holon(["mutate", "rate", "--check"], timeout=600)
        self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])

    def test_m2_exit_b_the_rate_meets_the_threshold(self):
        """BUILD_PLAN I22 Exit and §15.2 M2 exit (b): rate_non_equivalent >= 0.80 (Q6). The drafter's forecast is that
        this fails (I22-P12); it stays here, unchanged, as the exit check."""
        self.assertTrue(self.s["meets_threshold"], self.s["rate_non_equivalent"])

    def test_the_pinned_checkout_is_untouched(self):
        """I22-R4."""
        p = subprocess.run(["git", "-C", str(morph()), "status", "--porcelain"], capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout), (0, ""))
        p = subprocess.run(["git", "-C", str(morph()), "rev-parse", "HEAD"], capture_output=True, text=True)
        self.assertEqual(p.stdout.strip(), self.inst["target"]["commit"])


class TestDeterminism(unittest.TestCase):
    def test_a_sample_reruns_identically_at_the_pipeline_commit(self):
        """run --check: the baseline and one mutant per frontend shape (a codec store, a rollup statement, a Go encoder,
        a Go check) rerun at the records' pipeline_commit with --no-carry and reproduce their records byte for byte,
        each law's "decided" field aside."""
        need(SUMMARY)
        p = run_holon(["mutate", "run", "--milestone", "M2", "--only", "M001,M035,M065,M107", "--check"], timeout=7200)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])


# ======================================================================================== predictions
class TestPredictions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inst = instrument()
        cls.base = need(RECORDS / "baseline.json")
        cls.r = records()
        cls.s = need(SUMMARY)

    def _killed_by(self, i, law):
        rec = self.r[i]
        self.assertEqual(rec["outcome"], "killed", (i, rec["kill"]))
        self.assertIn(law, {x["law"] for x in rec["kill"]["by"]}, (i, rec["kill"]))

    def _survived(self, i):
        self.assertEqual(self.r[i]["outcome"], "survived", (i, self.r[i]["kill"]))

    def test_the_baseline_reproduces_the_m0_statuses(self):
        """I22-P1: the null mutant, re-extracted from scratch and projected, decides the 8 laws/M0 statements exactly as
        results/M0 does: L_par_hdr_v0, L_par_hdr_v1, L_rt_go_v0, L_rt_go_v1, L_rt_go_v2 PROVED; L_par_hdr_v2,
        L_par_hdr_ssvh, L_dom_hdr REFUTED."""
        got = {law: e["mutant"] for law, e in self.base["laws"].items() if e["set"] == "M0"}
        self.assertEqual(got, M0_BASELINE)
        self.assertEqual(self.base["extraction"]["status"], "ok")

    def test_every_mstore_offset_mutant_is_killed(self):
        """I22-P2: all 22 mstore_offset mutants are killed (K1 or K2): M001-M020 (the BatchHeaderCodecV0 stores) with
        L_par_hdr_v0 among the killing laws, M021-M022 (storeLastBlockNumber) with L_par_hdr_v1."""
        for i in ids(1, 20):
            with self.subTest(mutant=i):
                self._killed_by(i, "L_par_hdr_v0")
        for i in ids(21, 22):
            with self.subTest(mutant=i):
                self._killed_by(i, "L_par_hdr_v1")

    def test_shl_width_kills_the_codec_stores_and_not_the_data_hash(self):
        """I22-P3: the 8 shl_width mutants of the codec stores are killed (K1 or K2) (M023-M028 with L_par_hdr_v0, M029-M030
        with L_par_hdr_v1); the 4 in Rollup._commitBatch (M031-M034, the data-hash preimage) survive."""
        for i in ids(23, 28):
            with self.subTest(mutant=i):
                self._killed_by(i, "L_par_hdr_v0")
        for i in ids(29, 30):
            with self.subTest(mutant=i):
                self._killed_by(i, "L_par_hdr_v1")
        for i in ids(31, 34):
            with self.subTest(mutant=i):
                self._survived(i)

    def test_cmp_boundary_kills_exactly_the_two_header_length_sites(self):
        """I22-P4: of the 16 cmp_boundary mutants exactly M052 and M053 (Rollup.sol:333 and :353, version >= 1 of the
        header build) are killed, each with L_par_hdr_v1 among its killing laws (K1 or K2); the other 14 survive."""
        for i in ("M052", "M053"):
            with self.subTest(mutant=i):
                self._killed_by(i, "L_par_hdr_v1")
        for i in ["M049", "M050", "M051"] + ids(54, 64):
            with self.subTest(mutant=i):
                self._survived(i)

    def test_no_dropped_delete_is_killed(self):
        """I22-P5: none of the 6 drop_delete mutants (M035 revertBatch :453, M036 setPause :580, M037-M040
        finalizeBatch :657-660) is killed. The plan expected the UNDO laws to kill M035."""
        for i in ids(35, 40):
            with self.subTest(mutant=i):
                self._survived(i)

    def test_no_swapped_cursor_is_killed_and_the_corpus_sees_seven(self):
        """I22-P6: none of the 8 swap_cursor mutants (M041-M048) is killed by a law; the corpus detects M041, M043,
        M044, M045, M046, M047 and M048 (corpus_detected true; grounding: the instrument's computation item 9).
        Nothing is predicted for M042's corpus."""
        for i in ids(41, 48):
            with self.subTest(mutant=i):
                self._survived(i)
        for i in ["M041"] + ids(43, 48):
            with self.subTest(corpus=i):
                self.assertIs(self.r[i]["corpus_detected"], True)

    def test_the_differential_view_never_changes(self):
        """I22-P7: for all 110 mutants the normalized decided input of the M1x set (I20's window view) is byte-identical
        to the baseline's, so every one of the 15 rollup laws keeps its baseline status in every mutant run."""
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                self.assertIs(rec["inputs"]["M1x"]["changed"], False)
                for law, e in rec["laws"].items():
                    if e["set"] == "M1x":
                        self.assertEqual(e["mutant"], e["baseline"])

    def test_rollup_only_mutants_leave_the_projection_unchanged(self):
        """I22-P8: for the 30 Rollup.sol mutants outside the header edges' store sequences and loader (M031-M048, M050,
        M051, M054-M062, M064) the normalized projected header document is byte-identical to the baseline's."""
        for i in ROLLUP_ONLY:
            with self.subTest(mutant=i):
                self.assertIs(self.r[i]["inputs"]["M0"]["changed"], False)

    def test_every_putuint64_offset_mutant_is_killed(self):
        """I22-P9: all 14 putuint64_offset mutants are killed (K1 or K2): M065-M070 (BatchHeaderV0.Bytes) with L_par_hdr_v0,
        M071-M078 (BatchHeaderV1.Bytes) with L_par_hdr_v1, M078 (PutUint64 at 250 of a 257-byte buffer, which panics)
        included."""
        for i in ids(65, 70):
            with self.subTest(mutant=i):
                self._killed_by(i, "L_par_hdr_v0")
        for i in ids(71, 78):
            with self.subTest(mutant=i):
                self._killed_by(i, "L_par_hdr_v1")

    def test_copy_offset_kills_all_but_the_two_shifted_sequencer_set_hashes(self):
        """I22-P10: 26 of the 28 copy_offset mutants are killed (K1 or K2) (M079-M092 but M090 with L_par_hdr_v0, M093-M106 but
        M104 with L_par_hdr_v1). M090 and M104 (the sequencerSetVerifyHash copy shifted to 186) survive: every PROVED
        codec law pins sequencerSetVerifyHash to zero, and L_par_hdr_ssvh is REFUTED in the baseline."""
        for i in [x for x in ids(79, 92) if x != "M090"]:
            with self.subTest(mutant=i):
                self._killed_by(i, "L_par_hdr_v0")
        for i in [x for x in ids(93, 106) if x != "M104"]:
            with self.subTest(mutant=i):
                self._killed_by(i, "L_par_hdr_v1")
        for i in ("M090", "M104"):
            with self.subTest(mutant=i):
                self._survived(i)

    def test_no_dropped_length_check_is_killed(self):
        """I22-P11: none of the 4 drop_len_check mutants (M107-M110) is killed: the domain law L_dom_hdr is REFUTED in
        the baseline (the 250-byte version-0 header), so it cannot move, and the round-trip laws decode only
        exact-length encodings. The plan expected the domain law to kill them."""
        for i in ids(107, 110):
            with self.subTest(mutant=i):
                self._survived(i)

    def test_totals(self):
        """I22-P12: 72 of the 110 mutants are killed (rate_all 72/110), no mutant ends in error, no unpredicted
        obstruction occurs, and rate_non_equivalent is below 0.80: M2 exit (b) is not met at this pipeline."""
        s = self.s
        self.assertEqual((s["killed"], s["rate_all"]["num"], s["rate_all"]["den"]), (72, 72, 110))
        self.assertEqual(s["errors"], 0)
        self.assertEqual(s["unpredicted"], [])
        self.assertLess(5 * s["rate_non_equivalent"]["num"], 4 * s["rate_non_equivalent"]["den"])
        self.assertIs(s["meets_threshold"], False)

    def test_extraction_defect_channel_on_rollup_only_and_go_mutants(self):
        """I22-P13: no Rollup-only mutant (P8's 30) and no Go mutant whose code runs on I16's per-edge corpus without a
        panic (M065-M077, M079-M106) shows an extraction defect: no law is a replay disagreement and every channel run
        completes with no disagreement the baseline run does not have (false). M078 and M107-M110 panic on that corpus
        (computation item 10): their i16_edge run is incomplete, no law is a replay disagreement and no run reports a
        new disagreement (null)."""
        for i in ROLLUP_ONLY + [x for x in GO_MUTANTS if x not in GO_PANICS]:
            with self.subTest(mutant=i):
                self.assertIs(self.r[i]["extraction_defect_detected"], False)
        for i in GO_PANICS:
            with self.subTest(mutant=i):
                self.assertIsNone(self.r[i]["extraction_defect_detected"])
                self.assertTrue([c for c in channel_runs(self.r[i]) if c["harness"] == "i16_edge" and c["error"]])

    def test_the_frontends_see_every_mutant(self):
        """I22-P14: every one of the 110 mutants changes at least one extracted document (normalized: its top-level
        "extraction" block removed), so no survivor is an extraction gap at the frontend stage: each miss is lost after
        extraction (gap_stage "model") or is a rule gap."""
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                self.assertTrue(any(v["changed"] for v in rec["documents"].values()), rec["documents"])
                self.assertNotEqual(rec["gap_stage"], "frontend")


if __name__ == "__main__":
    unittest.main()
