"""I42: theory core I (whitepaper §3.1-3.3, §6: Lemma 6.2, Thm 6.3, Thm 6.4, Cor 6.5; §10.3 steps 1-3 and its last
sentence; App. H core/; BUILD_PLAN I42; docs/HUMAN_ANSWERS.md Q14b and the delegated Q19). This docstring is the contract
that tests_m3/test_theory_core.py checks.

Instruments fixed at the prereg: tests_m3/_i42.py (rules T1-T8 written out a second time, independently of holon/: the
frozen core texts, the instance graphs, trees, cycles and their derivations, coverage, certificates, and the exact text
of every instance's statements and of its canary's) and the frozen sidecar spec/M3/lib/theory_core.json (every value
this contract predicts, computed at the prereg by tests_m3/_i42.py::theory_doc from the inputs it lists).

What the plan asks and what the tree holds
  BUILD_PLAN I42: generic Graph, Walk and holonomy; Thm 6.4 ((iii) => (i) => (ii)), Cor 6.5, Lemma 6.2 and Thm 6.3;
  instantiate basis_sufficient_header by application; deliverables a core law family, holon/gen/basis.py and the
  congruence proof class; predictions: the core laws PROVED under bend and --verdict within budget, the header
  instantiation PROVED, a canary that drops one cycle law rejected. BUILD_PLAN I42 "waits for Q14b, since these are
  hand-proved meta-theorems"; Q14b: "Thm 6.4, 6.6 and 6.7 may be proved once, by hand, in Lean, and kernel-checked"
  (6.6 and 6.7 are I43's). §10.3: "The meta-theorems are formalized once in the core library and instantiated per
  target, so basis sufficiency is itself kernel-checked."
  Bend 2 makes every function value affine (bend/notes/p_ir03_fn_verdict: a Type is used at most once; only top-level
  defs are called freely), so a law cannot apply a hypothesis such as "every fundamental cycle is the identity" at
  every step of an arbitrary walk. The Bend core therefore states its results over per-step bundles: a type-level def
  (Cons, LInv, Pres, Onto, WalkOk) that unfolds, along the walk, to one hypothesis per step, which a proof consumes
  once. An instance builds its bundles from top-level lemmas, which it may call any number of times. The Lean core
  states the results in their textbook form (hypotheses quantified once, used freely). Which result is checked where:
    result                          Lean theorem (textbook form)     Bend law (the form an instance applies)
    Lemma 6.2 (congruence)          lemma_6_2                        core_cong_sym, core_cong_trans, core_whisker_post,
                                                                     core_whisker_pre (instances use Base's Equal.*)
    Thm 6.3 into / onto             thm_6_3_into / thm_6_3_onto      core_domain_into / core_domain_onto
    Thm 6.3 localization            thm_6_3_local                    (Lean only)
    Thm 6.4 (iii) => (i)            thm_6_4_iii_i                    core_fundamental_potential, core_bwd_cons,
                                                                     core_transport, core_cycle_identity
    Thm 6.4 (i) => (ii)             thm_6_4_i_ii                     core_holonomy_parallel
    Thm 6.4 (ii) => (iii)           thm_6_4_ii_iii                   (Lean only)
    Cor 6.5 (=>) / (<=)             cor_6_5_potentials / cor_6_5_flat  core_fundamental_potential / core_transport,
                                                                     core_cycle_identity, core_parallel_agree
    walk algebra, non-vacuity       (definitional in Lean)           core_runto_*, core_cons_inhabited
  The header: I24 derived over the linked component header_length (gen/M3/codec/header_length.json) 80 PAR laws, 73
  PROVED: 70 round trips and the 3 pinned cross-component laws. I24's cycle basis over the whole diagram (rank 4) does
  not satisfy Thm 6.4's hypothesis (its edges are lossy decoders, I25 rule L1) and none of its 4 cycle laws is PROVED.
  I42 applies the theory where its potential form holds: per version v, the forward-path diagram rooted at the Go
  record of the PROVED pinned cross-component law at v, with both encoders, the decoders at v and the product
  structure (projections, Some), so that the 73 PROVED laws are its available equations (rules T3-T5). An instance
  states Thm 6.4 (ii) for forward walks from its root, proved from potentials (Cor 6.5 (<=), core_parallel_agree): its
  maps need not be invertible, because a potential here is a value (the root path's image of one start), not a map.

Gaps preregistered
  T-G1 Walks of an instance are forward only and its maps are not invertible: no edge of header_length is modelled
       with an inverse function (I25 rule L1: its invertible fragment per version is a forest, rank 0, so Thm 6.4
       holds there with zero checks). An instance applies Thm 6.4 (ii) in potential form, which needs no inverse; the
       Bend core covers backward steps (core_bwd_cons, core_runto_rev, core_holonomy_parallel, LInv) and the Lean core
       states Thm 6.4 for walks of an invertible fragment; no instance exercises a backward step.
  T-G2 Certificates hold on the pinned region (the image of the root law's pins and correspondence), not on every
       record: e.g. SequencerSetVerifyHash(enc_sol(k)) == Some(0) is certified for k = sigma(pin_h(h)), the Go side's
       constant reads only for Go records whose fields pin_h fixes. A direct law per constant read (open the record,
       reflexivity) would cover every record; the certificates are narrower than I25's obligations, and counting them
       as coverage would be a downgrade. Whether the pinned image is all of a version's records is argued in the
       report, not kernel-checked.
  T-G3 No result record changes. "Records label basis sufficiency" (BUILD_PLAN I42 fallback) is carried by
       <out>/report.json (rule T9), not by results/M3/*.json; a v2 record field needs a schema change (I43/I45).
  T-G4 The cycle count |E| - |V| + kappa is computed by holon.gen.basis and by the instrument; it is not a kernel
       theorem (no spanning-forest combinatorics is formalized).
  T-G5 Placement (stated deviations): the theory core lives in gen/M3/theory/, not in holon.gen.core's catalog
       (gen/<M>/core/, I8) whose Nat/Bool lemmas are emitted for every M2+ milestone; and the congruence proof class
       lives in holon/gen/congruence.py, not in holon/gen/mproofs.py, because mproofs.py is a root of the holon-ir/0.2
       and 0.3 generator closures (holon.records.GENERATORS): editing it would change generator_sha256 in every M1,
       M2 and M3 record. holon/gen/basis.py, theory.py and congruence.py are imported by no closure module.
  T-G6 Gate integration (G1 regeneration of gen/M3/theory/, a G4 canary entry, G5 re-checks) is not added: the M3
       gate is partial (I24-I25). G3's Bend scan covers the .bend files under gen/M3/theory/; Theory.lean is checked
       only by this contract (holon.lean's forbidden list and rule T2's command rules), since Lean G3 scans gen/M3/lean.
  T-G7 Hand proofs (Q14b's reading): BUILD_PLAN I42 names Lemma 6.2, Thm 6.3, Thm 6.4 and Cor 6.5 as the hand-proved
       meta-theorems that wait for Q14b; Q14b names Thm 6.4 in Lean. I42 hand-writes, once and generically, the Lean
       proofs of all four and the Bend core's proofs (their per-step forms), each emitted as fixed text by
       holon.gen.theory; every instance proof comes from generators (holon.gen.basis, holon.gen.congruence). This
       reading is raised in the prompt's questions; a "no" makes I43 replace the fixed text by per-class generators.

CLI (every JSON file: json.dumps(obj, indent=2, sort_keys=True) + "\\n"; deterministic, no timestamps)
  python -m holon basis --milestone M3 [--root DIR] [--out DIR] [--kernels] [--check]
    Writes under <out, default <root>/gen/M3/theory>: core/LAWS.bend and core/PROOF.bend (rule T1), lean/Theory.lean
    (T2), basis/<role>.json for every linked component (T9), and, for every covered instance, basis/<role>_v<v>/
    LAWS.bend and PROOF.bend (T7) and basis/<role>_v<v>/canary/LAWS.bend and PROOF.bend (T8); with --kernels it also
    checks every written proof file and writes report.json (T9). It owns <out>/core, <out>/lean, <out>/basis and
    <out>/report.json: any other file under those three directories is removed, and report.json only with --kernels;
    nothing else under <out> is touched. Exit 0 written; 1 (--check) a file differs from a fresh build (report.json
    compared only with --kernels), nothing written; 2 refused, nothing written, the message starting "holon basis:
    refused:": an input missing, malformed or stale (named); 3 a construct the rules refuse (named). An input is stale
    when a law the instance uses has, at its record's artifacts (gen/M3/laws/<id>/LAWS.bend, the proof file), a
    statement_hash header different from laws/M3/REGISTRY.json's, or when the codec document or the diagram is not
    what holon codecs and holon diagram write now.

Rules (holon/gen/theory.py, holon/gen/basis.py, holon/gen/congruence.py; tests_m3/_i42.py writes each one out again)
  T0 Inputs. The linked codec components of M3 (gen/M3/codec/<role>.json with gen/M3/diagram/<role>.json), the law
     statements laws/M3/*.json with the versions of their PAR basis elements (laws/M3/DERIVATION.json), the records'
     statuses results/M3/*.json (an equation is available only when its law is PROVED), and the generated files the
     records' artifacts name. No hand-written document is read (Q19).
  T1 The Bend core. <out>/core/LAWS.bend is exactly tests_m3/_i42.py::CORE_LAWS_TEXT: the definitions (Edge, Step,
     step_inv, the edge helpers, step_ok, next_v, walk_last, walk_rev, WalkOk, RunTo, Cons, LInv, Pres, Onto, Valid)
     and the 19 laws of CORE_LAWS in that order. <out>/core/PROOF.bend imports ./LAWS.bend, fills every law with a def
     of the same name, declares no law and has no escape hatch. It is written by holon.gen.theory as fixed text (T-G7;
     generic, no target named). bend and bend --verdict each accept it (ALL PROOFS CHECK) within
     bend.budget_s_per_file seconds (120, wall clock on an otherwise idle machine).
  T2 The Lean core. <out>/lean/Theory.lean starts with the definitions block of tests_m3/_i42.py::LEAN_TEXT (up to and
     including the line "-- holon:theorems"; no namespace, autoImplicit off). After the marker, comments removed:
     every line that starts in column 0 starts with "theorem ", "def ", "example ", "|", "termination_by",
     "decreasing_by" or "set_option maxRecDepth|maxHeartbeats <n> [in]"; no "@[" and no double quote appears; and none
     of the words instance, attribute, deriving, variable, include, omit, universe, open, export, namespace, section,
     end, local, scoped, private, protected, noncomputable, mutual, class, abbrev, structure, inductive appears. Each
     theorem of LEAN_THEOREMS is declared exactly once with exactly LEAN_TEXT's statement (from "theorem <name>" to
     ":=", comments removed, whitespace normalized). holon.lean.check_text accepts it: result "checked" (every
     declared theorem audited by its bare name, axioms within {propext, Quot.sound}), within lean.budget_s_per_file
     seconds (120). Q14b's hand proof in Lean of Lemma 6.2, Thm 6.3 (into, onto, localization), Thm 6.4 ((iii) =>
     (i), (i) => (ii), (ii) => (iii)) and Cor 6.5 (both directions).
  T3 Instances. One per PROVED cross-component law (subform cross_component_codec, two record binders h and k, claim
     p(h) == q(k)) of each component: the root law, at the version v of its basis element. Vertices, in this order:
     0 h's record carrier, 1 k's record carrier, 2 the linked byte carrier, then the slots (targets of the decoders at
     v: diagram CODEC edges of fn_kind decoder whose version label holds v, a null label holding every version),
     sorted; then the root fields (the fields of h's record recovered by a round trip of p at v in laws/M3, whatever
     its status: claim d(p(x)) == Some(field F of x), d a decoder at v; the graph is the basis's, fixed before any
     outcome), in record order; then the other fields (recovered by a round trip of q at v), in record order. Edges,
     in this order: 0 sigma (0 -> 1, the root law's correspondence), 1 p (0 -> 2), 2 q (1 -> 2), the decoders at v
     sorted by diagram edge id (2 -> their slot), then per root field its projection (0 -> the field) and its Some
     edge (the field -> the slot of the decoders whose round trips recover it), then the same for the other fields
     (from 1). A field recovered at two slots is refused (exit 3).
  T4 The spanning tree. Breadth-first from vertex 0 over forward edges; a dequeued vertex scans its outgoing edges in
     id order; the edge that first reaches a vertex is a tree edge. Every vertex must be reached (else exit 3). The
     non-tree edges are the others; rank = |E| - |V| + 1 (kappa 1: the graph is connected).
  T5 Coverage. The available equations, in this order: the root law (lhs [1], rhs [0, 2]: p == q . sigma), each
     PROVED round trip of p at v ([1, d] vs [pi_F, some_F]) and each PROVED round trip of q at v ([0, 2, d] vs
     [0, pi_F', some_F']), law id order within each kind; each is a pair of paths from vertex 0; "laws_used" is the
     sorted set of their laws. A rewrite replaces a prefix lhs by rhs, or rhs by lhs. The fundamental cycle of
     non-tree edge e (u -> w) is covered when the tree path of u followed by e rewrites to the tree path of w in at
     most 6 rewrites; "derivation" is the shortest one found breadth-first (equations in order, "lr" before "rl"),
     "steps" its length; "needed" is the sorted set of the laws some derivation uses. An instance with an uncovered
     cycle is reported (status "uncovered") and gets no files.
  T6 Certificates. Per instance and side s in (p, q): constant_read for each decoder d at v whose read range holds
     only constants in s's layout at v (bytes: those constants) when a field vertex whose Some edge reaches d's slot is
     equated to the same bytes by a premise of the root law (a pin, or k's version); weak_image for each pair of
     decoders d1 < d2 at v reading one slot. Names const_read_<s>_<d lower>_v<v> and
     weak_image_<s>_<d1 lower>_<d2 lower>_v<v>, sorted by name.
  T7 Instance files. <out>/basis/<role>_v<v>/LAWS.bend is exactly tests_m3/_i42.py::instance_laws_text: the carriers
     (Car), zero, sigma (the root law's pin_k at zero), graph, fwd, act, run, start (K0 of the root law's pin_h), the
     law basis_sufficient_<role>_v<v> (for every h and every two walks p and q of the graph from vertex 0 (WalkOk) that
     end at one vertex: run(p, start(h)) == run(q, start(h))) and the certificates' laws (each over L0.pin_h(h) for
     side p and sigma(L0.pin_h(h)) for side q). Its PROOF.bend proves them by application:
     - imports exactly Base, ./LAWS.bend, ../../core/LAWS.bend, ../../core/PROOF.bend, the model, and the LAWS.bend
       and PROOF.bend of every law in laws_used (the records' artifacts, relative paths); declares no law; fills every
       law of its LAWS.bend; has no escape hatch;
     - defines avail_<i> for each available equation i, of type {run(lhs_i, start(h)) == run(rhs_i, start(h)) : Car},
       whose body applies equation i's law (names <alias of its LAWS.bend>.<the record's law_name>);
     - defines edge_<k> for every edge k, of type {act(C.Fwd{<k>n}, phi(h, <src>n)) == phi(h, <tgt>n) : Car} with
       phi(h, v) = run of v's tree path from start(h), as a one-line signature followed by its indented body with no
       blank line: a tree edge's body is {==}; a non-tree edge's body names avail_<i> for every equation i of its
       cycle's derivation (holon.gen.congruence: Equal.trans and Equal.sym over the steps, each lifted into Car with
       Equal.cong);
     - the instance law's def applies the core's core_parallel_agree; each certificate's def applies the instance law;
     - a model record is written (a pattern, a destructuring or a construction: "R_<name>{" with or without an alias)
       only inside defs named bridge_*. A bridge_* def has a one-line signature whose type is either a record equation
       {L == R : <alias>.R_<name>} with L and R built only from <alias>.pin_<x>(..), <alias>.sigma(..),
       <alias>.zero() and h, or a getter equation {<alias>.get_<x>(t) == [<decimal literals>] : List<&2, U32>}, t such
       a term; it equates two pins of one record, or a pinned field to its constant.
     bend and bend --verdict each accept it within 120 seconds.
  T8 Canaries. (a) Construction canary (BUILD_PLAN: "a canary that drops one cycle law is rejected"): the instance's
     PROOF.bend with the body of edge_<k>, k = tests_m3/_i42.py::canary(inst) (the lowest-id non-tree edge whose cycle
     is covered), replaced by {==} (the cycle law dropped, the fact claimed by computation), is rejected by bend: exit
     code not 0, and the first error is an expected/observed mismatch located in edge_<k>. (b) Semantic canary:
     <out>/basis/<role>_v<v>/canary/LAWS.bend is exactly tests_m3/_i42.py::canary_laws_text (the instance's carriers,
     zero, sigma and fwd verbatim, no core import, and the counter-law canary_unpinned_<role>_v<v>: some root record
     h with an unpinned start K0{h} separates the root cycle's walks, edge 1 against edges 0 then 2). Its PROOF.bend
     imports exactly Base, ./LAWS.bend, the model and the root law's LAWS.bend and PROOF.bend; fills the law with a
     witness found on the model (holon.gen.basis evaluates the two sides with bend on candidate records, in a fixed
     order, never with an oracle: AGENTS rule 5); writes a model record only inside defs named witness_*, each a
     nullary def whose body is one constructor of integer literals; has no escape hatch; and bend and bend --verdict
     each accept it within 120 seconds. No candidate separating the sides is a result: the canary PROOF.bend is not
     written and report.json says "no_witness".
  T9 The document and the report. <out>/basis/<role>.json: {"basis_version": "holon-basis/0.1", "document": "basis",
     "milestone", "component", "facts": the codec document, "inputs": tests_m3/_i42.py::inputs(root, role) (each file
     with its sha256, each record of the component's laws with its status), "instances": [one per root law, the
     instrument's keys: "name", "component", "version", "root_law", "root", "other", "p", "q", "vertices", "edges",
     "tree", "non_tree", "rank", "kappa", "available", "cycles", "uncovered", "certificates", "dir", "status",
     "laws_used", "needed", "canary_edge", "canary_law"] sorted by (version, root_law)}. <out>/report.json (written
     with --kernels; no timings): {"report_version": "holon-basis/0.1", "files": {path under <out>: {"sha256", "bend":
     "checked"|"rejected", "verdict": "checked"|"rejected"|"not_run"} for core/PROOF.bend, every instance PROOF.bend
     and every canary PROOF.bend; lean/Theory.lean: {"sha256", "lean": the check_text result, "axioms"}},
     "basis_sufficiency": {instance name: "kernel_checked" (the core, the Lean core and the instance pass every
     kernel) | "paper_proof_only" (some kernel fails) | "uncovered"}, "canary": {instance name: "refuted" (its canary
     PROOF passes both kernels) | "not_refuted" | "no_witness"}}.

Rules for the build
  - AGENTS.md is binding. Never edit facts/, spec/M1/, spec/M2/, laws/M0-M3, gen/M0-M2, results/M0-M3, or any file of
    gen/M3 outside gen/M3/theory/. No law is added and no record changes (T-G3).
  - holon/gen/basis.py, holon/gen/theory.py and holon/gen/congruence.py name no target or fixture identifier, no law id
    and no target source file, import neither tests_m3 nor tests.reference; no module of the holon-ir/0.1-0.3
    generator closures imports them (T-G5).
  - No skips. Predictions are never tuned; a miss is a Surprise.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from tests_m3 import _i24x as X
from tests_m3 import _i42 as T
from tests_m3._m3 import ROOT, canonical_json, copy_repo, file_sha256, holon_module, load_json, run_bend, run_holon

SIDECAR = ROOT / T.SIDECAR
OUT = ROOT / T.OUT
COMPONENT = "header_length"
BUDGET_S = 120
OK, FAIL = "ALL PROOFS CHECK", "SOME PROOFS FAIL"
ESCAPES = (re.compile(r"@unsafe"), re.compile(r"^\s*def\s+[\w.]+\?\s*\(", re.M), re.compile(r"\?[A-Za-z_]\w*"),
           re.compile(r"^\s*import\s+\"", re.M))
# rule T2: what may follow the Lean marker (comments removed)
LEAN_LINE_OK = re.compile(r"(theorem|def|example)\s|\||termination_by\b|decreasing_by\b|"
                          r"set_option\s+(maxRecDepth|maxHeartbeats)\s+\d+(\s+in)?\s*$")
LEAN_WORDS = re.compile(r"\b(instance|attribute|deriving|variable|include|omit|universe|open|export|namespace|section|"
                        r"end|local|scoped|private|protected|noncomputable|mutual|class|abbrev|structure|"
                        r"inductive)\b")
DOC_KEYS = ("name", "component", "version", "root_law", "root", "other", "p", "q", "vertices", "edges", "tree",
            "non_tree", "rank", "kappa", "available", "cycles", "uncovered", "certificates", "dir", "status",
            "laws_used", "needed", "canary_edge", "canary_law")
MODULES = ("holon/gen/basis.py", "holon/gen/theory.py", "holon/gen/congruence.py")
RECORD = re.compile(r"\bR_\w+\{")   # a model record written in a proof (pattern, destructuring or construction)


def side() -> dict:
    return load_json(SIDECAR)


def need(p: Path):
    p = Path(p)
    if not p.exists():
        raise AssertionError(f"{p.relative_to(ROOT) if p.is_relative_to(ROOT) else p} is missing (I42 builds it)")
    return p


def law_blocks(text: str) -> dict[str, str]:
    """law NAME: blocks of a Bend file, each as its lines with trailing whitespace stripped (comments removed)."""
    lines = [re.sub(r"#.*$", "", ln).rstrip() for ln in text.splitlines()]
    out, cur = {}, None
    for ln in lines:
        m = re.match(r"^law\s+(\w+)\s*:\s*$", ln)
        if m:
            cur = m.group(1)
            out[cur] = [ln]
        elif cur is not None and ln.startswith((" ", "\t")) and ln.strip():
            out[cur].append(ln)
        elif ln.strip():
            cur = None
    return {k: "\n".join(v) for k, v in out.items()}


def defs(text: str) -> dict[str, tuple[str, str]]:
    """Top-level defs of a Bend file: name -> (signature line, body: the lines after it up to the next line that starts
    in column 0, comments removed)."""
    out, cur, sig, buf = {}, None, None, []
    for ln in text.splitlines() + ["#end"]:
        code = re.sub(r"#.*$", "", ln).rstrip()
        if ln[:1] not in (" ", "\t", "") or (ln and not ln[0].isspace() and ln.strip()):
            if cur is not None:
                out[cur] = (sig, "\n".join(buf))
            cur = None
            m = re.match(r"^def ([\w.]+)\(", ln)
            if m:
                cur, sig, buf = m.group(1), code, []
        elif cur is not None and code.strip():
            buf.append(code)
    return out


def imports(text: str) -> tuple[bool, dict[str, str]]:
    """(whether `import Base` is present, {imported path: alias}); any other import line is an AssertionError."""
    base, out = False, {}
    for ln in text.splitlines():
        if not ln.startswith("import"):
            continue
        if ln.strip() == "import Base":
            base = True
            continue
        m = re.fullmatch(r"import (\S+) as (\w+)", ln.strip())
        if not m:
            raise AssertionError(f"an import that is neither Base nor `path as alias`: {ln!r}")
        out[m.group(1)] = m.group(2)
    return base, out


def no_escape(test: unittest.TestCase, text: str, what: str) -> None:
    for rx in ESCAPES:
        test.assertIsNone(rx.search(text), f"{what}: escape hatch {rx.pattern}")


def timed_bend(test: unittest.TestCase, proof: Path, verdict: bool = False) -> float:
    """Check one PROOF.bend with bend (or bend --verdict) from its own directory; returns the wall-clock seconds."""
    t0 = time.monotonic()
    if verdict:
        bend = holon_module("holon.bend")
        test.assertTrue(bend.verdict_available(), "bend --verdict needs Lean (BEND_NOTES 1); it is never skipped")
        r = bend.check_verdict(proof)
        code, out = r.code, r.out
    else:
        code, out = run_bend([proof.name], cwd=proof.parent, timeout=900)
    secs = time.monotonic() - t0
    test.assertEqual(code, 0, f"{proof}{' --verdict' if verdict else ''}: {out[-3000:]}")
    test.assertIn(OK, out, f"{proof}: {out[-3000:]}")
    return secs


def edge_def_span(text: str, k: int) -> tuple[int, int]:
    """(start, end) of the body of def edge_<k> in a PROOF.bend (rule T7: a one-line signature, then the indented body
    with no blank line): the lines after its signature up to the next line that is blank or not indented."""
    m = re.search(rf"(?m)^def edge_{k}\(.*\n", text)
    if not m:
        raise AssertionError(f"no def edge_{k}( in the instance PROOF.bend (rule T7)")
    i = m.end()
    j = i
    for ln in text[i:].splitlines(keepends=True):
        if not ln.strip() or not ln.startswith((" ", "\t")):
            break
        j += len(ln)
    return i, j


def canary_text(proof_text: str, k: int) -> str:
    i, j = edge_def_span(proof_text, k)
    return proof_text[:i] + "  {==}\n" + proof_text[j:]


def first_error_def(out: str) -> str | None:
    m = re.search(r"Location:\s*([\w.]+)", out)
    return m.group(1) if m else None


def basis(args: list, cwd: Path | None = None, timeout: int = 3600):
    return run_holon(["basis", *[str(a) for a in args]], cwd=cwd, timeout=timeout)


def tree_files(d: Path, skip=("report.json",)) -> dict[str, bytes]:
    d = Path(d)
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*"))
            if p.is_file() and p.name not in skip}


def record_of(lid: str) -> dict:
    return load_json(ROOT / "results" / "M3" / f"{lid}.json")


def rel_from(d: Path, rel: str) -> str:
    return os.path.relpath(ROOT / rel, d)


def pin_term(s: str) -> bool:
    """A term built only from <alias>.pin_<x>(..), <alias>.sigma(..), <alias>.zero() and h (rule T7's bridges)."""
    rest = re.sub(r"\b\w+\.pin_\w+\(|\b\w+\.sigma\(|\b\w+\.zero\(\)|\bh\b|[(), ]", "", s)
    return rest == "" and "h" in s


def split_eq(ty: str) -> tuple[str, str, str] | None:
    """{L == R : T} -> (L, R, T), splitting at the top-level ` == ` and the last ` : `."""
    if not (ty.startswith("{") and ty.endswith("}")):
        return None
    inner = ty[1:-1]
    depth, eq = 0, None
    for i, ch in enumerate(inner):
        depth += ch in "([{<"
        depth -= ch in ")]}>"
        if depth == 0 and inner.startswith(" == ", i):
            eq = i
            break
    if eq is None:
        return None
    lhs, rest = inner[:eq], inner[eq + 4:]
    j = rest.rfind(" : ")
    if j < 0:
        return None
    return lhs.strip(), rest[:j].strip(), rest[j + 3:].strip()


def bridge_ok(sig: str) -> bool:
    """Rule T7: a bridge_* signature is one line, a record equation of pin terms, or a getter equation of a pin term
    and a list of decimal literals."""
    m = re.fullmatch(r"def bridge_\w+\([^)]*\) -> (\{.*\}):", sig.strip())
    if not m:
        return False
    parts = split_eq(m.group(1))
    if parts is None:
        return False
    lhs, rhs, ty = parts
    if re.fullmatch(r"\w+\.R_\w+", ty):
        return pin_term(lhs) and pin_term(rhs)
    if ty == "List<&2, U32>":
        g = re.fullmatch(r"\w+\.get_\w+\((.*)\)", lhs)
        return bool(g) and pin_term(g.group(1)) and re.fullmatch(r"\[\d+(, \d+)*\]", rhs) is not None
    return False


# ---------------------------------------------------------------------------------------------- the prereg's inputs
class TestPreregInstruments(unittest.TestCase):
    """Construction checks of the instruments fixed at the prereg (I42-R2; they hold before and after the build)."""

    def test_sidecar_is_the_computation(self):
        """Construction (I42-R2): spec/M3/lib/theory_core.json is tests_m3/_i42.py::theory_doc over unchanged inputs:
        every input file's sha256 and every record's status match, and recomputing gives the same document."""
        s = side()
        for i in s["inputs"]:
            with self.subTest(input=i["path"]):
                if "sha256" in i:
                    self.assertEqual(file_sha256(ROOT / i["path"]), i["sha256"], f"{i['path']} changed since the prereg")
                else:
                    self.assertEqual(load_json(ROOT / i["path"]).get("status"), i["status"], i["path"])
        self.assertEqual(canonical_json(T.theory_doc(ROOT)), canonical_json(s))

    def test_core_statements_are_well_typed_open_laws(self):
        """Construction (rule T1): the frozen core text type-checks under the pinned bend as 19 open laws (bend reports
        exactly 19 TODOs and no other error). No proof is attempted here."""
        tmp = Path(tempfile.mkdtemp(prefix="i42_core_"))
        try:
            (tmp / "LAWS.bend").write_text(side()["core"]["laws_text"])
            (tmp / "PROOF.bend").write_text("import Base\nimport ./LAWS.bend as Laws\n")
            code, out = run_bend(["PROOF.bend"], cwd=tmp)
            self.assertNotEqual(code, 0)
            self.assertIn(FAIL, out)
            self.assertRegex(out, r"Error: 19 TODOs found", out[-2000:])
            self.assertNotIn("- expected", out)
            self.assertEqual(list(law_blocks(side()["core"]["laws_text"])), T.CORE_LAWS)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_lean_statements_are_well_typed(self):
        """Construction (rule T2): the frozen Lean text, each proof a placeholder, elaborates under the pinned Lean
        4.34.0 with no error and exactly one "declaration uses `sorry`" warning per theorem (9), and the axiom audit
        that holon.lean appends (`#print axioms <bare name>`) prints all 9. No proof is attempted here; the
        placeholder never enters a committed file."""
        lean = holon_module("holon.lean")
        b = lean.toolchain_bin()
        tmp = Path(tempfile.mkdtemp(prefix="i42_lean_"))
        try:
            text = side()["lean"]["text"] + "".join(f"\n#print axioms {n}" for n in T.LEAN_THEOREMS) + "\n"
            (tmp / "Statements.lean").write_text(text)
            p = subprocess.run([str(b / "lean"), "Statements.lean"], cwd=tmp, capture_output=True, text=True,
                               timeout=600, env={**os.environ, "PATH": f"{b}:{os.environ.get('PATH', '')}"})
            out = p.stdout + p.stderr
            self.assertNotRegex(out, r"(^|\n)[^\n]*error", out[-3000:])
            self.assertEqual(len(re.findall(r"declaration uses `sorry`", out)), len(T.LEAN_THEOREMS), out[-3000:])
            self.assertEqual(sorted(lean.parse_axioms(out)), sorted(T.LEAN_THEOREMS), out[-3000:])
            self.assertEqual(lean.theorems(side()["lean"]["text"]), T.LEAN_THEOREMS)
            for name in T.LEAN_THEOREMS:
                self.assertIsNotNone(T.lean_statement(side()["lean"]["text"], name), name)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_instance_statements_are_well_typed_open_laws(self):
        """Construction (rules T7, T8): each instance's frozen LAWS.bend, placed in a copy of gen/M3's model and laws
        beside the frozen core, type-checks as open laws: bend reports exactly 19 (core) + 1 (the root law's file) + 1
        + the certificates TODOs and no other error; its canary's LAWS.bend reports 1 (the root law's file) + 1. No
        proof is attempted here."""
        tmp = Path(tempfile.mkdtemp(prefix="i42_inst_"))
        try:
            g = tmp / "gen" / "M3"
            shutil.copytree(ROOT / "gen" / "M3" / "model", g / "model")
            shutil.copytree(ROOT / "gen" / "M3" / "laws", g / "laws")
            core = g / "theory" / "core"
            core.mkdir(parents=True)
            (core / "LAWS.bend").write_text(side()["core"]["laws_text"])
            (core / "PROOF.bend").write_text("import Base\nimport ./LAWS.bend as Laws\n")
            for inst in side()["instances"]:
                d = g / "theory" / inst["dir"]
                (d / "canary").mkdir(parents=True)
                for sub, text, n in (("", inst["laws_text"], 19 + 1 + 1 + len(inst["certificates"])),
                                     ("canary", inst["canary_laws_text"], 2)):
                    with self.subTest(instance=inst["name"], file=f"{sub or '.'}/LAWS.bend"):
                        dd = d / sub if sub else d
                        (dd / "LAWS.bend").write_text(text)
                        (dd / "PROOF.bend").write_text("import Base\nimport ./LAWS.bend as Laws\n")
                        code, out = run_bend(["PROOF.bend"], cwd=dd)
                        self.assertNotEqual(code, 0)
                        self.assertRegex(out, rf"Error: {n} TODOs found", out[-2000:])
                        self.assertNotIn("- expected", out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_instance_values_the_predictions_name(self):
        """Construction (the values I42-R6 names, computed at the prereg): three instances of header_length, rooted at
        the three PROVED pinned cross-component laws, with (|V|, |E|, rank) (34, 55, 22), (37, 60, 24), (37, 60, 24),
        every cycle covered, 23 + 25 + 25 laws available, together exactly the 73 PROVED PAR laws of M3, each in one
        instance; 22 + 24 + 24 of them needed by a shortest derivation; canary edge 2 in each."""
        s = side()
        got = [(i["version"], i["root_law"], len(i["vertices"]), len(i["edges"]), i["rank"], i["uncovered"],
                len(i["laws_used"]), len(i["needed"]), i["canary_edge"]) for i in s["instances"]]
        self.assertEqual(got, [
            (0, "L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0_pinned", 34, 55, 22, [], 23, 22, 2),
            (1, "L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned", 37, 60, 24, [], 25, 24, 2),
            (2, "L_par_cc_BatchCache_createBatchHeaderWithSequencerSetHash_enc_sol_v2_pinned", 37, 60, 24, [], 25, 24,
             2)])
        used = [lid for i in s["instances"] for lid in i["laws_used"]]
        self.assertEqual(len(used), len(set(used)))
        proved_par = sorted(p.stem for p in (ROOT / "results" / "M3").glob("L_par_*.json")
                            if load_json(p).get("status") == "PROVED")
        self.assertEqual(sorted(used), proved_par)


# ---------------------------------------------------------------------------------------------- P1: the Bend core
class TestCore(unittest.TestCase):
    def test_core_laws_are_the_frozen_text(self):
        """I42-P1 (statements): gen/M3/theory/core/LAWS.bend is exactly the frozen text (rule T1)."""
        self.assertEqual(need(OUT / "core" / "LAWS.bend").read_text(), side()["core"]["laws_text"])

    def test_core_proof_fills_every_law(self):
        """I42-P1 (shape): core/PROOF.bend imports ./LAWS.bend, declares no law, fills each of the 19 laws with a def of
        the same name, and has no escape hatch."""
        pt = need(OUT / "core" / "PROOF.bend").read_text()
        m = re.search(r"(?m)^import \./LAWS\.bend as (\w+)$", pt)
        self.assertIsNotNone(m, "core/PROOF.bend must import ./LAWS.bend")
        alias = m.group(1)
        self.assertEqual(law_blocks(pt), {})
        for name in T.CORE_LAWS:
            self.assertRegex(pt, rf"(?m)^def {alias}\.{name}\(", name)
        no_escape(self, (OUT / "core" / "LAWS.bend").read_text() + pt, "core")

    def test_core_checks_under_bend_within_budget(self):
        """I42-P1: bend accepts gen/M3/theory/core/PROOF.bend (ALL PROOFS CHECK) within 120 s."""
        secs = timed_bend(self, need(OUT / "core" / "PROOF.bend"))
        self.assertLessEqual(secs, BUDGET_S)

    def test_core_checks_under_verdict_within_budget(self):
        """I42-P1: bend --verdict (BendTT) accepts gen/M3/theory/core/PROOF.bend within 120 s."""
        secs = timed_bend(self, need(OUT / "core" / "PROOF.bend"), verdict=True)
        self.assertLessEqual(secs, BUDGET_S)


# ---------------------------------------------------------------------------------------------- P2: the Lean core
class TestLean(unittest.TestCase):
    def test_lean_definitions_and_statements_are_frozen(self):
        """I42-P2 (statements, rule T2): Theory.lean starts with the frozen definitions block; after the marker
        (comments removed) every column-0 line is a theorem, def, example, match alternative, termination clause or an
        allowed set_option, with no attribute, no string and none of the words that change how a statement
        elaborates; and each frozen theorem is declared once, with exactly its frozen statement."""
        src = need(OUT / "lean" / "Theory.lean").read_text()
        self.assertTrue(src.startswith(T.lean_definitions()), "Theory.lean must start with the frozen definitions")
        self.assertNotIn("\u00ab", src[len(T.lean_definitions()):], "no escaped identifier after the marker")
        rest = T.lean_code(src[len(T.lean_definitions()):])
        self.assertEqual(sorted(set(m.group(0) for m in holon_module("holon.lean").FORBIDDEN.finditer(rest))), [])
        self.assertNotIn("@[", rest)
        self.assertNotIn('"', rest)
        bad = LEAN_WORDS.search(rest)
        self.assertIsNone(bad, bad and bad.group(0))
        for ln in rest.splitlines():
            if ln.strip() and not ln[0].isspace():
                self.assertIsNotNone(LEAN_LINE_OK.match(ln), f"a column-0 line rule T2 does not allow: {ln[:120]!r}")
        for name in T.LEAN_THEOREMS:
            with self.subTest(theorem=name):
                got = T.lean_statement(src, name)
                self.assertIsNotNone(got, f"theorem {name} is not declared exactly once")
                self.assertEqual(got, T.lean_statement(side()["lean"]["text"], name))

    def test_lean_elaborated_types_are_the_frozen_ones(self):
        """Construction (rule T2; added after the build review, not preregistered): each frozen theorem's elaborated
        type in Theory.lean (`#check @<name>` under pp.all) equals its type elaborated from the frozen statements, so
        nothing after the marker changes what a statement means."""
        lean = holon_module("holon.lean")
        b = lean.toolchain_bin()

        def types(text: str) -> dict[str, str]:
            tmp = Path(tempfile.mkdtemp(prefix="i42_types_"))
            try:
                (tmp / "T.lean").write_text(text.rstrip("\n") + "\n\nset_option pp.all true\n"
                                            + "".join(f"#check @{n}\n" for n in T.LEAN_THEOREMS))
                p = subprocess.run([str(b / "lean"), "T.lean"], cwd=tmp, capture_output=True, text=True,
                                   timeout=600, env={**os.environ, "PATH": f"{b}:{os.environ.get('PATH', '')}"})
                out = p.stdout + p.stderr
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            self.assertNotRegex(out, r"(^|\n)[^\n]*error", out[-3000:])
            got = {}
            for n in T.LEAN_THEOREMS:
                m = re.search(rf"(?ms)^@{re.escape(n)} :(.*?)(?=^@\w+ :|^\S+:\d+:\d+: |\Z)", out)
                self.assertIsNotNone(m, f"#check @{n}: {out[-2000:]}")
                got[n] = " ".join(m.group(1).split())
            return got

        want = types(side()["lean"]["text"])
        have = types(need(OUT / "lean" / "Theory.lean").read_text())
        for n in T.LEAN_THEOREMS:
            with self.subTest(theorem=n):
                self.assertEqual(have[n], want[n])

    def test_lean_core_checks(self):
        """I42-P2: holon.lean.check_text accepts Theory.lean under the pinned toolchain: result checked, every frozen
        theorem among the audited ones, axioms within {propext, Quot.sound}, within 120 s (wall clock)."""
        lean = holon_module("holon.lean")
        src = need(OUT / "lean" / "Theory.lean").read_text()
        tmp = Path(tempfile.mkdtemp(prefix="i42_leancheck_"))
        try:
            res = lean.check_text(src, tmp, expect=T.LEAN_THEOREMS)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(res["result"], "checked", res["out"][-4000:])
        self.assertLessEqual(set(res["axioms"]), {"propext", "Quot.sound"})
        for name in T.LEAN_THEOREMS:
            self.assertIn(name, res["theorems"])
        self.assertLessEqual(res["seconds"], BUDGET_S)


# ---------------------------------------------------------------------------------------------- P3: the instances
class TestInstances(unittest.TestCase):
    def test_instance_laws_are_the_frozen_statements(self):
        """I42-P3 (statements): each instance's LAWS.bend is exactly its frozen text (rule T7)."""
        for inst in side()["instances"]:
            with self.subTest(instance=inst["name"]):
                self.assertEqual(need(OUT / inst["dir"] / "LAWS.bend").read_text(), inst["laws_text"])

    def test_instance_proofs_apply_the_laws(self):
        """I42-P3 (by application, rule T7): each instance PROOF.bend imports exactly its LAWS, the core LAWS and
        PROOF, the model and the LAWS and PROOF of every law it uses; declares no law and fills every law of its
        LAWS.bend; defines avail_<i> applying equation i's law, edge_<k> for every edge (a tree edge by {==}, a non-tree
        edge naming the avail_<i> of its cycle's derivation); applies core_parallel_agree in the instance law and the
        instance law in each certificate; writes a model record only in bridge_* defs, each a pin or getter
        equation; and has no escape hatch."""
        for inst in side()["instances"]:
            with self.subTest(instance=inst["name"]):
                d = OUT / inst["dir"]
                pt = need(d / "PROOF.bend").read_text()
                base, imp = imports(pt)
                self.assertTrue(base, "import Base")
                want = {"./LAWS.bend", "../../core/LAWS.bend", "../../core/PROOF.bend",
                        f"../../../model/{inst['component']}.bend"}
                law_alias = {}
                for lid in inst["laws_used"]:
                    art = record_of(lid)["artifacts"]
                    want |= {rel_from(d, art["laws"]), rel_from(d, art["proof"])}
                    law_alias[lid] = (imp.get(rel_from(d, art["laws"])), art["law_name"])
                self.assertEqual(sorted(imp), sorted(want), "rule T7: exactly these imports")
                alias, core = imp["./LAWS.bend"], imp["../../core/LAWS.bend"]
                self.assertEqual(law_blocks(pt), {})
                ds = defs(pt)
                for name in law_blocks(inst["laws_text"]):
                    self.assertIn(f"{alias}.{name}", ds, name)
                for i, a in enumerate(inst["available"]):
                    self.assertIn(f"avail_{i}", ds, f"avail_{i}")
                    la, ln = law_alias[a["law"]]
                    self.assertIn(f"{la}.{ln}(", ds[f"avail_{i}"][1], f"avail_{i} must apply {a['law']}")
                cyc = {c["edge"]: c for c in inst["cycles"]}
                for e in inst["edges"]:
                    k = e["id"]
                    self.assertIn(f"edge_{k}", ds, f"edge_{k}")
                    i, j = edge_def_span(pt, k)
                    span = re.sub(r"#.*$", "", pt[i:j], flags=re.M).strip()
                    if k in inst["tree"]:
                        self.assertEqual(span, "{==}", f"tree edge {k}")
                    else:
                        for n, _ in cyc[k]["derivation"]:
                            self.assertRegex(span, rf"\bavail_{n}\(", f"edge_{k} must name avail_{n}")
                self.assertIn(f"{core}.core_parallel_agree(", ds[f"{alias}.{inst['name']}"][1])
                for c in inst["certificates"]:
                    self.assertIn(f"{alias}.{inst['name']}(", ds[f"{alias}.{c['name']}"][1], c["name"])
                no_escape(self, pt, inst["name"])
                self.assertNotIn('"', pt, "no string literal: a # in one would hide code from these checks")
                self.assertNotIn("'", pt, "no char literal")
                for name, (sig, bod) in ds.items():
                    if RECORD.search(sig + "\n" + bod):
                        self.assertTrue(name.startswith("bridge_"), f"a model record is written in {name}")
                    if name.startswith("bridge_"):
                        self.assertTrue(bridge_ok(sig), f"{name}: not a pin or getter equation: {sig[:300]}")
                        lines = [ln.strip() for ln in bod.splitlines() if ln.strip()]
                        self.assertEqual(len(lines), 3, f"{name}: open h, then reflexivity")
                        self.assertEqual(lines[0], "match h:", name)
                        self.assertRegex(lines[1], r"^case \w+\.R_\w+\{[^}]*\}:$", name)
                        self.assertEqual(lines[2], "{==}", name)
                outside = [ln for ln in pt.splitlines() if RECORD.search(re.sub(r"#.*$", "", ln))
                           and not ln.startswith((" ", "\t", "def bridge_"))]
                self.assertEqual(outside, [])

    def test_instances_check_under_bend_within_budget(self):
        """I42-P3: bend accepts each instance's PROOF.bend within 120 s: basis_sufficient_header_length_v0, v1, v2
        and their 12 certificates are PROVED (the header instantiation, by application)."""
        for inst in side()["instances"]:
            with self.subTest(instance=inst["name"]):
                self.assertLessEqual(timed_bend(self, need(OUT / inst["dir"] / "PROOF.bend")), BUDGET_S)

    def test_instances_check_under_verdict_within_budget(self):
        """I42-P3: bend --verdict accepts each instance's PROOF.bend within 120 s."""
        for inst in side()["instances"]:
            with self.subTest(instance=inst["name"]):
                self.assertLessEqual(timed_bend(self, need(OUT / inst["dir"] / "PROOF.bend"), verdict=True), BUDGET_S)


# ---------------------------------------------------------------------------------------------- P4: the semantic canary
class TestSemanticCanary(unittest.TestCase):
    def test_canary_laws_are_the_frozen_statements(self):
        """I42-P4 (statements, rule T8b): each canary's LAWS.bend is exactly its frozen text, and its carriers, zero,
        sigma and fwd are the instance's, verbatim."""
        for inst in side()["instances"]:
            with self.subTest(instance=inst["name"]):
                text = need(OUT / inst["dir"] / "canary" / "LAWS.bend").read_text()
                self.assertEqual(text, inst["canary_laws_text"])
                mine, theirs = defs(text), defs(inst["laws_text"])
                for name in ("zero", "sigma", "fwd"):
                    self.assertEqual(mine[name], theirs[name], name)
                self.assertIn(text[text.index("type Car"):text.index("def zero")],
                              inst["laws_text"][inst["laws_text"].index("type Car"):])

    def test_canary_proofs_refute_by_a_model_witness(self):
        """I42-P4 (shape, rule T8b): each canary PROOF.bend imports exactly ./LAWS.bend, the model and the root law's
        LAWS and PROOF; fills the counter-law; writes a model record only in witness_* defs, each one constructor of
        integer literals; declares no law; has no escape hatch."""
        for inst in side()["instances"]:
            with self.subTest(instance=inst["name"]):
                d = OUT / inst["dir"] / "canary"
                pt = need(d / "PROOF.bend").read_text()
                base, imp = imports(pt)
                self.assertTrue(base)
                art = record_of(inst["root_law"])["artifacts"]
                want = {"./LAWS.bend", f"../../../../model/{inst['component']}.bend", rel_from(d, art["laws"]),
                        rel_from(d, art["proof"])}
                self.assertEqual(sorted(imp), sorted(want))
                alias = imp["./LAWS.bend"]
                ds = defs(pt)
                self.assertIn(f"{alias}.{inst['canary_law']}", ds)
                self.assertEqual(law_blocks(pt), {})
                no_escape(self, pt, inst["name"] + " canary")
                self.assertNotIn('"', pt, "no string literal")
                self.assertNotIn("'", pt, "no char literal")
                for name, (sig, bod) in ds.items():
                    if RECORD.search(sig + "\n" + bod):
                        self.assertTrue(name.startswith("witness_"), f"a model record is written in {name}")
                    if name.startswith("witness_"):
                        self.assertRegex(sig, rf"^def witness_\w*\(\) -> \w+\.R_{inst['root']}:$")
                        self.assertRegex(bod.strip(), rf"^\w+\.R_{inst['root']}\{{\d+(, \d+)*\}}$")

    def test_canaries_check_under_bend_within_budget(self):
        """I42-P4: bend accepts each canary PROOF.bend within 120 s: the root cycle is refuted at an unpinned start,
        so the instance law needs its pins (the instantiation is not vacuous)."""
        for inst in side()["instances"]:
            with self.subTest(instance=inst["name"]):
                self.assertLessEqual(timed_bend(self, need(OUT / inst["dir"] / "canary" / "PROOF.bend")), BUDGET_S)

    def test_canaries_check_under_verdict_within_budget(self):
        """I42-P4: bend --verdict accepts each canary PROOF.bend within 120 s."""
        for inst in side()["instances"]:
            with self.subTest(instance=inst["name"]):
                self.assertLessEqual(timed_bend(self, need(OUT / inst["dir"] / "canary" / "PROOF.bend"),
                                                verdict=True), BUDGET_S)


# ---------------------------------------------------------------------------------------------- R6: the document
class TestBasisDocument(unittest.TestCase):
    def test_document_is_the_instrument(self):
        """Construction (I42-R6): gen/M3/theory/basis/header_length.json holds the instrument's instances (rules T3-T6,
        T9) key for key, and the instrument's inputs."""
        doc = load_json(need(OUT / "basis" / f"{COMPONENT}.json"))
        self.assertEqual(doc["basis_version"], T.BASIS_VERSION)
        self.assertEqual((doc["document"], doc["milestone"], doc["component"], doc["facts"]),
                         ("basis", "M3", COMPONENT, f"gen/M3/codec/{COMPONENT}.json"))
        want = [{k: i[k] for k in DOC_KEYS} for i in side()["instances"]]
        got = [{k: i.get(k) for k in DOC_KEYS} for i in doc["instances"]]
        self.assertEqual(canonical_json(got), canonical_json(want))
        self.assertEqual(canonical_json(doc["inputs"]), canonical_json(T.inputs(ROOT, COMPONENT)))


# ---------------------------------------------------------------------------------------------- R7: the construction canary
class TestConstructionCanary(unittest.TestCase):
    def test_dropping_one_cycle_law_is_rejected(self):
        """Construction (I42-R7, rule T8a): for each instance, its PROOF.bend with edge_<k> (k the canary edge: the
        lowest-id covered non-tree edge, edge 2, whose cycle is the root cross-component law) proved by {==} instead of
        its derivation is rejected by bend, first error an expected/observed mismatch located in edge_<k>."""
        for inst in side()["instances"]:
            with self.subTest(instance=inst["name"]):
                k = inst["canary_edge"]
                self.assertEqual(k, 2)
                src = need(OUT / inst["dir"] / "PROOF.bend").read_text()
                canary = canary_text(src, k)
                self.assertNotEqual(canary, src)
                tmp = Path(tempfile.mkdtemp(prefix="i42_canary_"))
                try:
                    g = tmp / "gen" / "M3"
                    for sub in ("model", "laws", "proofs", "theory"):
                        shutil.copytree(ROOT / "gen" / "M3" / sub, g / sub)
                    probe = g / "theory" / inst["dir"]
                    (probe / "PROOF.bend").write_text(canary)
                    code, out = run_bend(["PROOF.bend"], cwd=probe, timeout=900)
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
                self.assertNotEqual(code, 0, out[-2000:])
                self.assertIn(FAIL, out)
                self.assertIn("- expected", out, out[-2000:])
                self.assertIn("- observed", out, out[-2000:])
                self.assertEqual(first_error_def(out), f"edge_{k}", out[-2000:])


# ---------------------------------------------------------------------------------------------- R8: the certificates
class TestCertificates(unittest.TestCase):
    def test_certificates_cover_i25s_constant_reads(self):
        """Construction (I42-R8): in the built document, the constant_read certificates are exactly I25's six
        uncovered constant_read elements (gen/M3/par_lossy/header_length.json: reason no_rule): (writer encoder,
        decoder, version, bytes) for the Go encoders' Version byte and enc_sol's SequencerSetVerifyHash at versions 0,
        1 and 2; the weak_image certificates are the decoder pairs of I24's three PAR-weak laws, on both encoders'
        images; each is a law of the built instance LAWS.bend."""
        doc = load_json(need(OUT / "basis" / f"{COMPONENT}.json"))
        lossy = load_json(ROOT / "gen" / "M3" / "par_lossy" / f"{COMPONENT}.json")
        i25 = sorted((e["p"], e["q"], e["version"], e["bytes"]) for e in lossy["elements"]
                     if e["kind"] == "constant_read")
        mine, weak = [], []
        for inst in doc["instances"]:
            laws = law_blocks(need(OUT / inst["dir"] / "LAWS.bend").read_text())
            for c in inst["certificates"]:
                self.assertIn(c["name"], laws)
                enc = inst["p"] if c["side"] == "p" else inst["q"]
                if c["kind"] == "constant_read":
                    mine.append((f"CODEC.{enc}", f"CODEC.{c['decoders'][0]}", inst["version"], c["bytes"]))
                else:
                    weak.append((inst["version"], c["side"], tuple(c["decoders"])))
        self.assertEqual(sorted(mine), i25)
        self.assertEqual(len(weak), 6)
        weak_laws = sorted(p.stem for p in (ROOT / "results" / "M3").glob("L_par_weak_*.json"))
        self.assertEqual(len(weak_laws), 3)
        for v, s, (d1, d2) in weak:
            self.assertIn(f"L_par_weak_{d1}_{d2}_v{v}", weak_laws, (v, s, d1, d2))


# ---------------------------------------------------------------------------------------------- R9: the report
class TestReport(unittest.TestCase):
    def test_report_binds_every_kernel_result(self):
        """Construction (I42-R9): gen/M3/theory/report.json lists core/PROOF.bend, lean/Theory.lean, each instance
        PROOF.bend and each canary PROOF.bend with the sha256 of the committed file and every kernel's result (bend and
        verdict checked; lean checked, axioms within {propext, Quot.sound}), labels each instance kernel_checked and
        each canary refuted (rule T9)."""
        rep = load_json(need(OUT / "report.json"))
        self.assertEqual(rep["report_version"], T.BASIS_VERSION)
        files = rep["files"]
        want = ["core/PROOF.bend", "lean/Theory.lean"] + [f"{i['dir']}/PROOF.bend" for i in side()["instances"]] + \
               [f"{i['dir']}/canary/PROOF.bend" for i in side()["instances"]]
        self.assertEqual(sorted(files), sorted(want))
        for f in want:
            with self.subTest(file=f):
                self.assertEqual(files[f]["sha256"], file_sha256(OUT / f))
                if f.endswith(".lean"):
                    self.assertEqual(files[f]["lean"], "checked")
                    self.assertLessEqual(set(files[f]["axioms"]), {"propext", "Quot.sound"})
                else:
                    self.assertEqual((files[f]["bend"], files[f]["verdict"]), ("checked", "checked"))
        self.assertEqual(rep["basis_sufficiency"], {i["name"]: "kernel_checked" for i in side()["instances"]})
        self.assertEqual(rep["canary"], {i["name"]: "refuted" for i in side()["instances"]})


# ---------------------------------------------------------------------------------------------- R3: the CLI
class TestCLI(unittest.TestCase):
    def test_two_runs_are_byte_identical_and_equal_the_committed_files(self):
        """Construction (I42-R3): holon basis --milestone M3 --out DIR (no kernels) writes, twice, byte-identical
        files equal to gen/M3/theory/ (report.json aside) and leaves a file outside core/, lean/ and basis/ alone;
        --check on the committed tree exits 0."""
        need(OUT / "basis" / f"{COMPONENT}.json")
        tmp = Path(tempfile.mkdtemp(prefix="i42_cli_"))
        try:
            outs = []
            for n in (1, 2):
                o = tmp / f"out{n}"
                o.mkdir()
                (o / "keep.txt").write_text("not holon's\n")
                p = basis(["--milestone", "M3", "--out", o])
                self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
                self.assertEqual((o / "keep.txt").read_text(), "not holon's\n")
                outs.append(tree_files(o, skip=("report.json", "keep.txt")))
            self.assertEqual(outs[0], outs[1])
            self.assertEqual(outs[0], tree_files(OUT))
            p = basis(["--milestone", "M3", "--check"])
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_stale_law_file_is_refused(self):
        """Construction (I42-R3): in a copy, a used law's generated LAWS.bend whose statement_hash header no longer
        matches laws/M3/REGISTRY.json makes holon basis exit 2 with "holon basis: refused:", naming that law, and
        write nothing."""
        repo = copy_repo()
        try:
            lid = side()["instances"][0]["laws_used"][-1]
            f = repo / "gen" / "M3" / "laws" / lid / "LAWS.bend"
            f.write_text(re.sub(r"statement_hash: sha256:[0-9a-f]{64}", "statement_hash: sha256:" + "0" * 64,
                                f.read_text(), count=1))
            out = repo / "out_stale"
            p = basis(["--milestone", "M3", "--root", repo, "--out", out], cwd=repo)
            self.assertEqual(p.returncode, 2, p.stdout[-2000:] + p.stderr[-2000:])
            self.assertIn("holon basis: refused:", p.stderr)
            self.assertIn(lid, p.stderr)
            self.assertFalse(out.exists() and any(out.rglob("*")))
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- R4: honesty
class TestHonesty(unittest.TestCase):
    def test_generic_code(self):
        """Construction (I42-R4; AGENTS rules 2, 4 and 5, T-G5): holon/gen/basis.py, theory.py and congruence.py name no
        identifier of the Morph component or of the linked fixtures (I24's target_names), no law id and no target
        source file, import neither tests_m3 nor tests.reference; no module of the generator closures imports them."""
        names = X.target_names(ROOT)
        compound = {n for n in names if len(n) >= 5 and ("_" in n or any(c.isupper() for c in n[1:]))}
        quoted = {n for n in names if len(n) >= 3} - X.GENERIC_WORDS
        for rel in MODULES:
            with self.subTest(module=rel):
                f = ROOT / rel
                self.assertTrue(f.exists(), f"{rel} is missing")
                text = f.read_text(encoding="utf-8")
                self.assertEqual(sorted(n for n in compound
                                        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", text)), [])
                self.assertEqual(sorted(n for n in quoted if re.search(rf"[\"']{re.escape(n)}[\"']", text)), [])
                self.assertNotRegex(text, r"L_par_\w*(v[0-9]|pinned)\b")
                self.assertNotRegex(text, r"(?i)\bmorph\b|Rollup\.sol|header_length", "no target name or source file")
                self.assertNotRegex(text, r"(?m)^\s*(from|import)\s+tests(_m\d)?\b", "the instruments are not holon's")
        records = holon_module("holon.records")
        for v in ("holon-ir/0.1", "holon-ir/0.2", "holon-ir/0.3"):
            closure = records.generator_files(v, ROOT)
            for rel in MODULES:
                self.assertNotIn(rel, closure, f"{rel} entered the {v} generator closure")

    def test_a_missing_round_trip_leaves_its_cycle_uncovered(self):
        """Construction (I42-R4): in a copy whose record of L_par_rt_BatchHeaderV1_Bytes_BatchHeaderBytes_DataHash_v1
        says UNKNOWN, holon basis reports the v1 instance uncovered (exactly the cycle of the root field DataHash's
        Some edge, as the instrument computes on the copy), writes no file for it (no canary either), and leaves v0
        and v2 unchanged."""
        repo = copy_repo()
        try:
            rec = repo / "results" / "M3" / "L_par_rt_BatchHeaderV1_Bytes_BatchHeaderBytes_DataHash_v1.json"
            r = load_json(rec)
            r["status"] = "UNKNOWN"
            rec.write_text(json.dumps(r, indent=2, sort_keys=True) + "\n")
            want = T.theory_doc(repo)["instances"]
            v1 = next(i for i in want if i["version"] == 1)
            self.assertEqual(len(v1["uncovered"]), 1)
            e = v1["edges"][v1["uncovered"][0]]
            self.assertEqual((e["kind"], e["field"], e["side"]), ("some", "BatchHeaderV0.DataHash", "root"))
            out = repo / "out_honest"
            p = basis(["--milestone", "M3", "--root", repo, "--out", out], cwd=repo)
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
            doc = load_json(out / "basis" / f"{COMPONENT}.json")
            got = {i["version"]: i for i in doc["instances"]}
            self.assertEqual((got[1]["status"], got[1]["uncovered"]), ("uncovered", v1["uncovered"]))
            self.assertFalse((out / v1["dir"]).exists())
            for v in (0, 2):
                for f in ("LAWS.bend", "canary/LAWS.bend"):
                    self.assertEqual((out / f"basis/{COMPONENT}_v{v}" / f).read_text(),
                                     (OUT / f"basis/{COMPONENT}_v{v}" / f).read_text())
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_without_its_root_law_a_version_has_no_instance(self):
        """Construction (I42-R4): in a copy whose record of the v1 pinned cross-component law says UNKNOWN, there is no
        v1 instance (no document entry, no files); v0 and v2 are as committed."""
        repo = copy_repo()
        try:
            rec = repo / "results" / "M3" / "L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned.json"
            r = load_json(rec)
            r["status"] = "UNKNOWN"
            rec.write_text(json.dumps(r, indent=2, sort_keys=True) + "\n")
            out = repo / "out_noroot"
            p = basis(["--milestone", "M3", "--root", repo, "--out", out], cwd=repo)
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
            doc = load_json(out / "basis" / f"{COMPONENT}.json")
            self.assertEqual([i["version"] for i in doc["instances"]], [0, 2])
            self.assertFalse((out / f"basis/{COMPONENT}_v1").exists())
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- R1, R5
class TestRegressions(unittest.TestCase):
    def test_i42_outcome_commits_touch_nothing_else(self):
        """I42-R1: every commit that changes gen/M3/theory/ or holon/gen/{basis,theory,congruence}.py changes no file
        under laws/, results/, facts/, spec/M1/, spec/M2/, replay/, gen/M0-M2, or gen/M3 outside gen/M3/theory/ (no law
        is added, no record changes). Needs the real checkout's history: a missing .git is a failure, never a skip."""
        def git(*args):
            p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                               env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
            if p.returncode != 0:
                raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
            return p.stdout
        commits = set(git("log", "--format=%H", "--", "gen/M3/theory", *MODULES).split())
        self.assertTrue(git("log", "--format=%H", "--", "gen/M3/theory").split(), "no commit writes gen/M3/theory/")
        never = ("laws/", "results/", "facts/", "spec/M1/", "spec/M2/", "replay/", "gen/M0/", "gen/M1/", "gen/M2/")
        for c in sorted(commits):
            touched = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", c).split()
            self.assertEqual([f for f in touched if f.startswith(never)
                              or (f.startswith("gen/M3/") and not f.startswith("gen/M3/theory/"))], [], c)

    def test_partial_gate_m3_passes(self):
        """I42-R5: holon gate --milestone M3 --checks G3,G5,G9,GEVID passes on a copy of the built tree (G3 scans
        gen/M3/theory/'s .bend files: no escape hatch, no bare core LAWS import). G2 and G11 fail at the prereg for
        reasons outside I42 (solc 0.8.24 is not installed in this environment; I30's record
        L_sort_realize_rollup_363_4a64383b is missing, as I25 reported), so they are not part of this check."""
        need(OUT / "core" / "PROOF.bend")
        repo = copy_repo()
        try:
            rep = repo.parent / "gate_report_i42.json"
            p = run_holon(["gate", "--milestone", "M3", "--root", str(repo), "--report", str(rep), "--checks",
                           "G3,G5,G9,GEVID"], cwd=repo, timeout=3600)
            self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-3000:])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
