"""I43 instrument, fixed at the I43 prereg (BUILD_PLAN §0.1, "instruments are inputs"); revised at the prereg's two
review folds (before any build), as the commit message records.

Two contracts read it: tests_m3/test_theory_core2.py (part A, theory core II: rules C1-C5) and
tests_m3/test_lean_promoted.py (part B, Lean for the promoted set: rules L0-L10). It writes their rules out a second
time, independently of holon/ (no holon module is imported here, at module level or inside a function), so that the
tests can decide what holon must write:

Part A
- CORE2_LAWS_TEXT: theory core II's Bend statements (rule C1), the exact text of gen/M3/theory2/core/LAWS.bend;
- LEAN2_TEXT: the Lean statements of Thm 6.6 and 6.7 in their textbook form (rule C2), each proof a placeholder here;
  gen/M3/theory2/lean/TheoryII.lean starts with LEAN2_TEXT's definitions block and states every theorem as written;
- lean_code(src), lean_statement(src, name): the contracts' own comment-free reading of a Lean source;
- theory2_doc(): the frozen sidecar spec/M3/lib/theory_core2.json.

The instrument's readers (review B1, M3, M4): nothing the tests judge with is taken from holon/ (I43 edits
holon/lean.py)
- lean_toolchain, run_lean, lean_check: the pinned Lean (LEAN_TOOLCHAIN, LEAN_VERSION and LEAN_FINGERPRINT, frozen
  here), and the check every Lean file a test accepts must pass: exit code 0, no error, no sorry, and a final
  sentinel theorem with a random name whose axiom audit, with the checked theorems', ends the output;
- LEAN_BANNED, INDENTED_COMMAND, core_file_violations, file_violations: the banned words and file rules (no #
  anywhere, no indented command);
- parse_axioms, semantic_rejection, resource_limit_reproduces: the axiom audit, the canaries' semantic-rejection
  reading and the resource-limit reading, pinned by SEMANTIC_PROBES and RESOURCE_PROBES;
- replace_statement: a law file's statement replaced in its raw source (rule L9's canary);
- import_closure, independence_violations: rule L1's reading of Python imports (transitive, every form, attribute
  chains and reflection);
- CHEATS, CLEAN_LAW: the independent review's cheat files, which the construction tests require rejected.

Part B
- scope(root): rule L0, every PROVED law (the promoted set, Q8) and every REFUTED law of results/M1, results/M2,
  results/M2/extracted_m1 and results/M3, with its law file, registry statement hash, rule, sub-form, Bend proof class,
  facts document, Bend model and model kind;
- interface(kind, facts, ...): rule L2, the Lean names and types every emitted model of a kind must provide: the
  frozen data-type declarations (verbatim), the frozen statement-level declarations (views, Reach) and the frozen
  signatures of the model functions, the sites' raw obligations ro_<x> among them (obligation_vars);
- Render: rule L3, the exact Lean statement of every in-scope law (and the counter-law and refutation statements of
  every REFUTED law whose IR forms and model kind it covers), rendered from the law's IR alone;
- machine_differential, linked_differential: rule L7, sample inputs and the values the COMPILED BEND MODELS compute
  on them (bend evaluates a main that returns a list; nothing is computed by an oracle), which every Lean model must
  reproduce; diff_lean renders them as Lean theorems over the interface; action_successes and site_coverage say how
  much the samples exercise;
- perturb_canaries: rule L9's perturb canary per milestone gate, with its Bend evidence;
- site_mutation, site_canaries, site_canary_lean: rule L11's mutation canary of the PROVED SORT sites (the mutated
  Bend model built by holon's own Bend side in a separate process; no holon module is imported here);
- file_violations, shadow_violations, site_reach_violations, model_decls, required_names: rule L4's reading of an
  emitted Lean file; stub_text: the interface stub rules L3 and L5 elaborate the frozen statements against
  (test-only, never committed);
- promoted_doc(root): the frozen sidecar spec/M3/lib/lean_promoted.json; sidecar_text: the sidecars' file format.

Inputs only: the law files, registries and derivations (laws/M1, laws/M2, laws/M3), the records' statuses,
witnesses, attempts and artifacts (results/...), the facts documents the records' models were generated from, the
oracle sidecar spec/M2/lib/oracles.json (which Fn binders are model parameters), config/holon.json (bend and its budget)
and, for the differential values and the canaries' evidence, the committed Bend models (gen/<M>/model/*.bend,
gen/M2/extracted/m1/model/m1_view.bend) run by the pinned bend, and for the site canaries the mutated instrumented
model holon.sorts.sites builds from a mutated copy of the facts document.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from tests._util import bend_cmd, config
from tests_m3._m3 import ROOT, file_sha256, load_json

LEAN_MARKER = "-- holon:theorems"

# ============================================================================================== part A: theory core II
THEORY2_VERSION = "holon-theory2/0.1"
THEORY2_SIDECAR = Path("spec") / "M3" / "lib" / "theory_core2.json"
THEORY2_OUT = Path("gen") / "M3" / "theory2"

# ---------------------------------------------------------------------------------------------- rule C1: Bend core II
CORE2_LAWS_TEXT = '''# GENERATED by holon.gen.theory2 (I43): theory core II's statements, frozen at the I43 prereg.
# Import core/PROOF.bend beside this file, never this file alone (I8).
import Base

# ---------------------------------------------------------------- traces over an erased step (Data actions)
# RunA(S, A, st, tr, x, y): the trace tr carries x to y, each action a acting by st(a). The step is erased: an
# instance reasons about its model step through equations only (I42's RunTo, over actions instead of walk steps).
def RunA(-S: Type, -A: Data, -st: A -> S -> S, tr: List<&2, A>, -x: S, -y: S) -> Type:
  match tr:
    case Nil{}:
      {x == y : S}
    case Con{+a, t}:
      RunA(S, A, st, t, st(a, x), y)

# MapA(A, ga, tr, tr2): tr2 is tr with ga applied to every action (one equation per action).
def MapA(-A: Data, -ga: A -> A, tr: List<&2, A>, tr2: List<&2, A>) -> Type:
  match tr tr2:
    case Nil{} Nil{}:
      Unit
    case Con{+a, t} Con{+b, t2}:
      {b == ga(a) : A} & MapA(A, ga, t, t2)
    case Nil{} Con{b, t2}:
      Empty
    case Con{a, t} Nil{}:
      Empty

# WordTo(X, G, gx, w, x, y): the word w of generators carries x to y, its letters applied in order, head first
# (a relational word: a def cannot apply an erased function, so the image is named, as RunA names a run's end).
def WordTo(-X: Type, -G: Data, -gx: G -> X -> X, w: List<&2, G>, -x: X, -y: X) -> Type:
  match w:
    case Nil{}:
      {x == y : X}
    case Con{+g, t}:
      WordTo(X, G, gx, t, gx(g, x), y)

# IterTo(X, g, n, x, y): g iterated n times carries x to y.
def IterTo(-X: Type, -g: X -> X, n: Nat, -x: X, -y: X) -> Type:
  match n:
    case 0n:
      {x == y : X}
    case 1n+p:
      IterTo(X, g, p, g(x), y)

# ---------------------------------------------------------------- Thm 6.6 (generators suffice for equivariance)
# EqvAlong: along tr from x, every action commutes with the transform (g on states, ga on actions), one equation per
# step: the per-action equivariance laws of an instance, applied at the states the trace visits.
def EqvAlong(-S: Type, -A: Data, -st: A -> S -> S, -g: S -> S, -ga: A -> A, tr: List<&2, A>, -x: S) -> Type:
  match tr:
    case Nil{}:
      Unit
    case Con{+a, t}:
      {st(ga(a), g(x)) == g(st(a, x)) : S} & EqvAlong(S, A, st, g, ga, t, st(a, x))

# EqvWord: along the word w, applied to the action a and the state x, every letter commutes with the step at the
# action and state it meets (gs on states, ga on actions, per letter): one equation per letter.
def EqvWord(-S: Type, -A: Data, -G: Data, -st: A -> S -> S, -gs: G -> S -> S, -ga: G -> A -> A, w: List<&2, G>, -a: A, -x: S) -> Type:
  match w:
    case Nil{}:
      Unit
    case Con{+g, t}:
      {st(ga(g, a), gs(g, x)) == gs(g, st(a, x)) : S} & EqvWord(S, A, G, st, gs, ga, t, ga(g, a), gs(g, x))

# EqvPow: along n iterations of (g, ga) from the action a and the state x, each iteration commutes with the step at
# the action and state it meets: one equation per iteration.
def EqvPow(-S: Type, -A: Data, -st: A -> S -> S, -g: S -> S, -ga: A -> A, n: Nat, -a: A, -x: S) -> Type:
  match n:
    case 0n:
      Unit
    case 1n+p:
      {st(ga(a), g(x)) == g(st(a, x)) : S} & EqvPow(S, A, st, g, ga, p, ga(a), g(x))

# the identity is in the stabiliser (pointwise form): a transform that fixes the action and the two states the step
# meets commutes with the step there
law core_eqv_id:
  for -S: Type
  for -A: Data
  for -st: A -> S -> S
  for -g: S -> S
  for -ga: A -> A
  for -a: A
  for -x: S
  for ea: {ga(a) == a : A}
  for ex: {g(x) == x : S}
  for ey: {g(st(a, x)) == st(a, x) : S}
  {st(ga(a), g(x)) == g(st(a, x)) : S}

# the stabiliser is closed under composition (pointwise form)
law core_eqv_comp:
  for -S: Type
  for -A: Data
  for -st: A -> S -> S
  for -g: S -> S
  for -h: S -> S
  for -ga: A -> A
  for -ha: A -> A
  for -a: A
  for -x: S
  for e1: {st(ha(a), h(x)) == h(st(a, x)) : S}
  for e2: {st(ga(ha(a)), g(h(x))) == g(st(ha(a), h(x))) : S}
  {st(ga(ha(a)), g(h(x))) == g(h(st(a, x))) : S}

# the stabiliser is closed under inverses (pointwise form): gi undoes g on the two states involved
law core_eqv_inv:
  for -S: Type
  for -A: Data
  for -st: A -> S -> S
  for -g: S -> S
  for -gi: S -> S
  for -ga: A -> A
  for -gai: A -> A
  for -a: A
  for -x: S
  for ea: {ga(gai(a)) == a : A}
  for ex: {g(gi(x)) == x : S}
  for e: {st(ga(gai(a)), g(gi(x))) == g(st(gai(a), gi(x))) : S}
  for l: {gi(g(st(gai(a), gi(x)))) == st(gai(a), gi(x)) : S}
  {st(gai(a), gi(x)) == gi(st(a, x)) : S}

# a word of equivariant generators is equivariant (pointwise, at the action and state the word meets)
law core_eqv_word:
  for -S: Type
  for -A: Data
  for -G: Data
  for -st: A -> S -> S
  for -gs: G -> S -> S
  for -ga: G -> A -> A
  for w: List<&2, G>
  for -a: A
  for -x: S
  for -b: A
  for -y: S
  for -z: S
  for H: EqvWord(S, A, G, st, gs, ga, w, a, x)
  for wa: WordTo(A, G, ga, w, a, b)
  for wx: WordTo(S, G, gs, w, x, y)
  for wz: WordTo(S, G, gs, w, st(a, x), z)
  {st(b, y) == z : S}

# powers of an equivariant generator are equivariant (pointwise, along the iterations)
law core_eqv_pow:
  for -S: Type
  for -A: Data
  for -st: A -> S -> S
  for -g: S -> S
  for -ga: A -> A
  for n: Nat
  for -a: A
  for -x: S
  for -b: A
  for -y: S
  for -z: S
  for H: EqvPow(S, A, st, g, ga, n, a, x)
  for ia: IterTo(A, ga, n, a, b)
  for ix: IterTo(S, g, n, x, y)
  for iz: IterTo(S, g, n, st(a, x), z)
  {st(b, y) == z : S}

# per-action equivariance lifts to traces
law core_eqv_trace:
  for -S: Type
  for -A: Data
  for -st: A -> S -> S
  for -g: S -> S
  for -ga: A -> A
  for tr: List<&2, A>
  for tr2: List<&2, A>
  for -x: S
  for -y: S
  for -z: S
  for m: MapA(A, ga, tr, tr2)
  for H: EqvAlong(S, A, st, g, ga, tr, x)
  for r: RunA(S, A, st, tr, x, y)
  for r2: RunA(S, A, st, tr2, g(x), z)
  {z == g(y) : S}

# non-vacuity (L21): the identity transform's bundles are inhabited along every trace, word and iteration
law core_eqv_inhabited:
  for -S: Type
  for -A: Data
  for -st: A -> S -> S
  for +tr: List<&2, A>
  for -x: S
  EqvAlong(S, A, st, y => y, b => b, tr, x)

law core_word_inhabited:
  for -S: Type
  for -A: Data
  for -G: Data
  for -st: A -> S -> S
  for +w: List<&2, G>
  for -a: A
  for -x: S
  EqvWord(S, A, G, st, g => y => y, g => b => b, w, a, x)

law core_pow_inhabited:
  for -S: Type
  for -A: Data
  for -st: A -> S -> S
  for +n: Nat
  for -a: A
  for -x: S
  EqvPow(S, A, st, y => y, b => b, n, a, x)

# ---------------------------------------------------------------- Thm 6.7 (naturality)
# Sq: along tr from x (an in-flight state of version k), each action's naturality square holds at the state the
# trace visits: eta(st_k(a, x)) == st_k1(a, eta(x)). One equation per step.
def Sq(-S: Type, -T: Type, -A: Data, -stk: A -> S -> S, -stk1: A -> T -> T, -eta: S -> T, tr: List<&2, A>, -x: S) -> Type:
  match tr:
    case Nil{}:
      Unit
    case Con{+a, t}:
      {eta(stk(a, x)) == stk1(a, eta(x)) : T} & Sq(S, T, A, stk, stk1, eta, t, stk(a, x))

# SqObs: naturality up to an observation. Along tr, from x (version k) and u (version k+1), each step gives the
# naturality square under the observation ob only (ob(eta(stk(a, x))) == ob(stk1(a, eta(x)))), and a congruence step:
# version k+1's step keeps the observation equal from eta(x) and from u (the unobservable residue stays
# unobservable, as UNDO's noninterference step lemma states). One square and one congruence step per step.
def SqObs(-S: Type, -T: Type, -O: Type, -A: Data, -stk: A -> S -> S, -stk1: A -> T -> T, -eta: S -> T, -ob: T -> O, tr: List<&2, A>, -x: S, -u: T) -> Type:
  match tr:
    case Nil{}:
      Unit
    case Con{+a, t}:
      {ob(eta(stk(a, x))) == ob(stk1(a, eta(x))) : O} & ({ob(eta(x)) == ob(u) : O} -> {ob(stk1(a, eta(x))) == ob(stk1(a, u)) : O}) & SqObs(S, T, O, A, stk, stk1, eta, ob, t, stk(a, x), stk1(a, u))

# (a) pasting: the squares of a1 at x and of a2 at stk(a1, x) give the square of the composite
law core_nat_paste:
  for -S: Type
  for -T: Type
  for -A: Data
  for -stk: A -> S -> S
  for -stk1: A -> T -> T
  for -eta: S -> T
  for -a1: A
  for -a2: A
  for -x: S
  for e1: {eta(stk(a1, x)) == stk1(a1, eta(x)) : T}
  for e2: {eta(stk(a2, stk(a1, x))) == stk1(a2, eta(stk(a1, x))) : T}
  {eta(stk(a2, stk(a1, x))) == stk1(a2, stk1(a1, eta(x))) : T}

# (b) vertical composition: natural eta1 (k -> k+1) and eta2 (k+1 -> k+2) compose, pointwise
law core_nat_vcomp:
  for -S: Type
  for -T: Type
  for -U: Type
  for -A: Data
  for -stk: A -> S -> S
  for -stk1: A -> T -> T
  for -stk2: A -> U -> U
  for -eta1: S -> T
  for -eta2: T -> U
  for -a: A
  for -x: S
  for e1: {eta1(stk(a, x)) == stk1(a, eta1(x)) : T}
  for e2: {eta2(stk1(a, eta1(x))) == stk2(a, eta2(eta1(x))) : U}
  {eta2(eta1(stk(a, x))) == stk2(a, eta2(eta1(x))) : U}

# (c) consequence: squares for the entry points along a trace give the square of the trace
law core_nat_trace:
  for -S: Type
  for -T: Type
  for -A: Data
  for -stk: A -> S -> S
  for -stk1: A -> T -> T
  for -eta: S -> T
  for tr: List<&2, A>
  for -x: S
  for -y: S
  for -z: T
  for H: Sq(S, T, A, stk, stk1, eta, tr, x)
  for r: RunA(S, A, stk, tr, x, y)
  for r2: RunA(T, A, stk1, tr, eta(x), z)
  {z == eta(y) : T}

# (c) up to an observation: squares under ob, with the congruence steps, give the trace's square under ob, from any
# u that eta(x) and ob cannot tell apart
law core_nat_obs:
  for -S: Type
  for -T: Type
  for -O: Type
  for -A: Data
  for -stk: A -> S -> S
  for -stk1: A -> T -> T
  for -eta: S -> T
  for -ob: T -> O
  for tr: List<&2, A>
  for -x: S
  for -u: T
  for -y: S
  for -z: T
  for e0: {ob(eta(x)) == ob(u) : O}
  for H: SqObs(S, T, O, A, stk, stk1, eta, ob, tr, x, u)
  for r: RunA(S, A, stk, tr, x, y)
  for r2: RunA(T, A, stk1, tr, u, z)
  {ob(z) == ob(eta(y)) : O}

# non-vacuity (L21): the identity migration's squares are inhabited along every trace, exactly and under any
# observation
law core_sq_inhabited:
  for -S: Type
  for -A: Data
  for -stk: A -> S -> S
  for +tr: List<&2, A>
  for -x: S
  Sq(S, S, A, stk, stk, y => y, tr, x)

law core_sqobs_inhabited:
  for -S: Type
  for -O: Type
  for -A: Data
  for -stk: A -> S -> S
  for -ob: S -> O
  for +tr: List<&2, A>
  for -x: S
  SqObs(S, S, O, A, stk, stk, y => y, ob, tr, x, x)
'''

CORE2_LAWS = ["core_eqv_id", "core_eqv_comp", "core_eqv_inv", "core_eqv_word", "core_eqv_pow", "core_eqv_trace",
              "core_eqv_inhabited", "core_word_inhabited", "core_pow_inhabited", "core_nat_paste", "core_nat_vcomp",
              "core_nat_trace", "core_nat_obs", "core_sq_inhabited", "core_sqobs_inhabited"]

# the laws the I43 design survey checked (bend and --verdict, hand proofs, before this prereg; nothing of it is
# committed): the others are unprobed, so their PROVED outcome is a genuine prediction (I43-P1 scores only those)
CORE2_PROBED = ["core_eqv_comp", "core_eqv_inv", "core_eqv_trace", "core_nat_paste", "core_nat_vcomp", "core_nat_trace"]
CORE2_UNPROBED = [n for n in CORE2_LAWS if n not in CORE2_PROBED]

# what each law realizes (whitepaper §5.3, §5.4, §6 Thm 6.6 and 6.7, §10.3 steps 4-5, §10.8)
CORE2_RESULTS = {
    "core_eqv_id": "Thm 6.6: the identity is in the stabiliser (pointwise: a transform fixing the action and the "
                   "states the step meets commutes with it there)",
    "core_eqv_comp": "Thm 6.6: the stabiliser is closed under composition (pointwise)",
    "core_eqv_inv": "Thm 6.6: the stabiliser is closed under inverses (pointwise): a subgroup",
    "core_eqv_word": "Thm 6.6, generators suffice: a word of equivariant generators (a family indexed by Data) is "
                     "equivariant, one letter's equation per letter (the pi family: products of transpositions)",
    "core_eqv_pow": "Thm 6.6: powers of an equivariant generator are equivariant (the tau family: tau_d = tau_1^d)",
    "core_eqv_trace": "Thm 6.6 lifted to traces: per-action equivariance carries runs to runs (§10.3 step 4, SYM)",
    "core_eqv_inhabited": "non-vacuity (L21) of core_eqv_trace's EqvAlong premise (the identity symmetry)",
    "core_word_inhabited": "non-vacuity (L21) of core_eqv_word's EqvWord premise (identity generators)",
    "core_pow_inhabited": "non-vacuity (L21) of core_eqv_pow's EqvPow premise (the identity generator)",
    "core_nat_paste": "Thm 6.7 (a): pasting two squares gives the composite's square",
    "core_nat_vcomp": "Thm 6.7 (b): natural migrations compose vertically (pointwise)",
    "core_nat_trace": "Thm 6.7 (c): the entry points' squares along a trace give the trace's square (§5.3, §10.3 "
                      "step 5, NAT)",
    "core_nat_obs": "Thm 6.7 (c) up to an observation: squares under ob and congruence steps (an unobservable residue "
                    "stays unobservable) give the trace's square under ob (NAT (a) compares observations)",
    "core_sq_inhabited": "non-vacuity (L21) of core_nat_trace's Sq premise (the identity migration)",
    "core_sqobs_inhabited": "non-vacuity (L21) of core_nat_obs's SqObs premise (the identity migration)",
}

# ---------------------------------------------------------------------------------------------- rule C2: Lean core II
LEAN2_TEXT = '''/-
  HOLON theory core II (whitepaper §5.3, §5.4, §6: Thm 6.6, Thm 6.7; §10.3 steps 4-5; §10.8), in textbook form:
  hypotheses quantified once and used freely. Hand-proved once (human answer Q14b names Thm 6.6 and 6.7).
  GENERATED by holon.gen.theory2 (I43); the definitions and theorem statements are frozen at the I43 prereg.
  No namespace: an axiom audit prints each theorem by its bare name.
-/
set_option autoImplicit false

/-- A trace run by a step function, left to right. -/
def runA {S A : Type} (st : A → S → S) : List A → S → S
  | [], x => x
  | a :: t, x => runA st t (st a x)

/-- (g, ga) is a symmetry of the step: transforming the action and the state commutes with stepping. -/
def Equivariant {S A : Type} (st : A → S → S) (g : S → S) (ga : A → A) : Prop :=
  ∀ a x, st (ga a) (g x) = g (st a x)

/-- The same on a set of states D (partial actions: a submonoid, §6 Thm 6.6). -/
def EquivariantOn {S A : Type} (D : S → Prop) (st : A → S → S) (g : S → S) (ga : A → A) : Prop :=
  ∀ a x, D x → st (ga a) (g x) = g (st a x)

/-- The composite of a word of generators on states, applied right to left (the last generator acts first). -/
def wordS {S A : Type} : List ((S → S) × (A → A)) → S → S
  | [], x => x
  | p :: w, x => p.1 (wordS w x)

/-- The composite of a word of generators on actions, in the same order as wordS. -/
def wordA {S A : Type} : List ((S → S) × (A → A)) → A → A
  | [], a => a
  | p :: w, a => p.2 (wordA w a)

/-- g iterated n times. -/
def iter {α : Type} (g : α → α) : Nat → α → α
  | 0, x => x
  | n + 1, x => iter g n (g x)

/-- The migrations eta k, .., eta (k + n - 1), applied in order. -/
def migs {S : Type} (eta : Nat → S → S) (k : Nat) : Nat → S → S
  | 0, x => x
  | n + 1, x => eta (k + n) (migs eta k n x)

/-- A naturality square for every action on the in-flight set D (§5.3 (b)). -/
def NaturalOn {S T A : Type} (D : S → Prop) (stk : A → S → S) (stk1 : A → T → T) (eta : S → T) : Prop :=
  ∀ a x, D x → eta (stk a x) = stk1 a (eta x)

-- holon:theorems

/-- Thm 6.6: the identity is a symmetry. -/
theorem thm_6_6_id {S A : Type} (st : A → S → S) : Equivariant st id id := by
  sorry

/-- Thm 6.6: symmetries compose (Stab is closed under composition). -/
theorem thm_6_6_comp {S A : Type} (st : A → S → S) (g h : S → S) (ga ha : A → A)
    (hg : Equivariant st g ga) (hh : Equivariant st h ha) : Equivariant st (g ∘ h) (ga ∘ ha) := by
  sorry

/-- Thm 6.6: the inverse of a symmetry is a symmetry (Stab is closed under inverses: a subgroup). -/
theorem thm_6_6_inv {S A : Type} (st : A → S → S) (g gi : S → S) (ga gai : A → A)
    (hl : ∀ x, gi (g x) = x) (hr : ∀ x, g (gi x) = x) (har : ∀ a, ga (gai a) = a)
    (hg : Equivariant st g ga) : Equivariant st gi gai := by
  sorry

/-- Thm 6.6: generators suffice: a word of symmetries is a symmetry. -/
theorem thm_6_6_word {S A : Type} (st : A → S → S) :
    ∀ (w : List ((S → S) × (A → A))), (∀ p, p ∈ w → Equivariant st p.1 p.2) → Equivariant st (wordS w) (wordA w) := by
  sorry

/-- Thm 6.6: powers of a symmetry are symmetries (τ_d = τ_1^d). -/
theorem thm_6_6_pow {S A : Type} (st : A → S → S) (g : S → S) (ga : A → A) (hg : Equivariant st g ga) :
    ∀ n : Nat, Equivariant st (iter g n) (iter ga n) := by
  sorry

/-- Thm 6.6 lifted to traces: a symmetry maps runs to runs (§10.3 step 4: per generator and per action suffices). -/
theorem thm_6_6_run {S A : Type} (st : A → S → S) (g : S → S) (ga : A → A) (hg : Equivariant st g ga) :
    ∀ (tr : List A) (x : S), runA st (tr.map ga) (g x) = g (runA st tr x) := by
  sorry

/-- Thm 6.6 for partial actions: the identity is a symmetry on every set of states. -/
theorem thm_6_6_id_on {S A : Type} (D : S → Prop) (st : A → S → S) : EquivariantOn D st id id := by
  sorry

/-- Thm 6.6 for partial actions: symmetries on D compose when the inner one keeps D (with thm_6_6_id_on, the
symmetries on D that keep D form a submonoid). -/
theorem thm_6_6_comp_on {S A : Type} (D : S → Prop) (st : A → S → S) (g h : S → S) (ga ha : A → A)
    (hg : EquivariantOn D st g ga) (hh : EquivariantOn D st h ha) (hD : ∀ x, D x → D (h x)) :
    EquivariantOn D st (g ∘ h) (ga ∘ ha) := by
  sorry

/-- Thm 6.6 for partial actions: a symmetry on a set D that every step keeps maps runs from D to runs. -/
theorem thm_6_6_run_on {S A : Type} (D : S → Prop) (st : A → S → S) (g : S → S) (ga : A → A)
    (hg : EquivariantOn D st g ga) (hD : ∀ a x, D x → D (st a x)) :
    ∀ (tr : List A) (x : S), D x → runA st (tr.map ga) (g x) = g (runA st tr x) := by
  sorry

/-- Thm 6.7 (a), pasting: the squares of two actions give the square of their composite. -/
theorem thm_6_7_a {S T A : Type} (stk : A → S → S) (stk1 : A → T → T) (eta : S → T) (a1 a2 : A) (x : S)
    (e1 : eta (stk a1 x) = stk1 a1 (eta x)) (e2 : eta (stk a2 (stk a1 x)) = stk1 a2 (eta (stk a1 x))) :
    eta (stk a2 (stk a1 x)) = stk1 a2 (stk1 a1 (eta x)) := by
  sorry

/-- Thm 6.7 (b), vertical composition: natural migrations compose. -/
theorem thm_6_7_b {S T U A : Type} (D1 : S → Prop) (D2 : T → Prop) (stk : A → S → S) (stk1 : A → T → T)
    (stk2 : A → U → U) (eta1 : S → T) (eta2 : T → U) (h1 : NaturalOn D1 stk stk1 eta1) (h2 : NaturalOn D2 stk1 stk2 eta2)
    (hm : ∀ x, D1 x → D2 (eta1 x)) : NaturalOn D1 stk stk2 (fun x => eta2 (eta1 x)) := by
  sorry

/-- Thm 6.7 (c), consequence: the squares of the entry points on the in-flight set, which every step keeps, give the
square of every trace (§5.3 (a)-(b), §10.3 step 5). -/
theorem thm_6_7_c {S T A : Type} (D : S → Prop) (stk : A → S → S) (stk1 : A → T → T) (eta : S → T)
    (h : NaturalOn D stk stk1 eta) (hD : ∀ a x, D x → D (stk a x)) :
    ∀ (tr : List A) (x : S), D x → eta (runA stk tr x) = runA stk1 tr (eta x) := by
  sorry

/-- Thm 6.7, migration sequences (§5.3 (c), (b) iterated): migrations eta k .. eta (k+n-1), each natural from its
version's in-flight set into the next one's, compose to one natural migration from version k to version k + n. -/
theorem thm_6_7_seq {S A : Type} (D : Nat → S → Prop) (st : Nat → A → S → S) (eta : Nat → S → S) (k : Nat) :
    ∀ n : Nat, (∀ i, i < n → NaturalOn (D (k + i)) (st (k + i)) (st (k + i + 1)) (eta (k + i))) →
      (∀ i x, i < n → D (k + i) x → D (k + i + 1) (eta (k + i) x)) →
      NaturalOn (D k) (st k) (st (k + n)) (migs eta k n) ∧ (∀ x, D k x → D (k + n) (migs eta k n x)) := by
  sorry

/-- Thm 6.7 (c) up to an observation (§5.3 (a): versions agree on what is observed). If every action's square holds
under ob on the in-flight set D, D is kept, and the new version's steps respect ob's kernel (a residue ob forgets
stays unobservable), then every trace's square holds under ob, from any u that ob cannot tell from eta x. -/
theorem thm_6_7_obs {S T O A : Type} (D : S → Prop) (stk : A → S → S) (stk1 : A → T → T) (eta : S → T) (ob : T → O)
    (hsq : ∀ a x, D x → ob (eta (stk a x)) = ob (stk1 a (eta x)))
    (hcong : ∀ a u v, ob u = ob v → ob (stk1 a u) = ob (stk1 a v))
    (hD : ∀ a x, D x → D (stk a x)) :
    ∀ (tr : List A) (x : S) (u : T), D x → ob (eta x) = ob u → ob (eta (runA stk tr x)) = ob (runA stk1 tr u) := by
  sorry
'''

LEAN2_THEOREMS = ["thm_6_6_id", "thm_6_6_comp", "thm_6_6_inv", "thm_6_6_word", "thm_6_6_pow", "thm_6_6_run",
                  "thm_6_6_id_on", "thm_6_6_comp_on", "thm_6_6_run_on", "thm_6_7_a", "thm_6_7_b", "thm_6_7_c",
                  "thm_6_7_seq", "thm_6_7_obs"]
LEAN2_PROBED = ["thm_6_6_id", "thm_6_6_comp", "thm_6_6_inv", "thm_6_6_word", "thm_6_6_pow", "thm_6_6_run",
                "thm_6_6_run_on", "thm_6_7_a", "thm_6_7_b", "thm_6_7_c", "thm_6_7_seq"]
LEAN2_UNPROBED = [n for n in LEAN2_THEOREMS if n not in LEAN2_PROBED]
LEAN2_RESULTS = {
    "thm_6_6_id": "Thm 6.6: the identity is in Stab",
    "thm_6_6_comp": "Thm 6.6: Stab is closed under composition",
    "thm_6_6_inv": "Thm 6.6: Stab is closed under inverses (with id and comp: a subgroup)",
    "thm_6_6_word": "Thm 6.6: generators suffice (a word of symmetries is a symmetry)",
    "thm_6_6_pow": "Thm 6.6: powers of a symmetry",
    "thm_6_6_run": "Thm 6.6 on traces (§10.3 step 4)",
    "thm_6_6_id_on": "Thm 6.6 for partial actions: the identity is a symmetry on every set of states",
    "thm_6_6_comp_on": "Thm 6.6 for partial actions: symmetries on D compose when the inner one keeps D (with "
                       "thm_6_6_id_on: the symmetries on D that keep D form a submonoid)",
    "thm_6_6_run_on": "Thm 6.6 for partial actions: a symmetry on a domain every step keeps maps runs to runs",
    "thm_6_7_a": "Thm 6.7 (a) pasting",
    "thm_6_7_b": "Thm 6.7 (b) vertical composition",
    "thm_6_7_c": "Thm 6.7 (c) consequence: entry points x in-flight types suffice (§5.3 (a)-(b))",
    "thm_6_7_seq": "Thm 6.7 for reachable migration sequences (§5.3 (c))",
    "thm_6_7_obs": "Thm 6.7 (c) up to an observation (§5.3 (a): versions agree on what is observed)",
}


def lean_definitions(text: str = LEAN2_TEXT) -> str:
    """The frozen definitions block: the text up to and including the marker line."""
    i = text.index(LEAN_MARKER)
    return text[:i + len(LEAN_MARKER)] + "\n"


def lean_code(src: str) -> str:
    """A Lean source without its comments (line comments, and block comments, which nest), string literals blanked
    to "", an escaped identifier «...» kept whole (so a comment opener inside one hides nothing): what the statement
    and command rules read. Written here independently of holon.lean."""
    return _lean_code_map(src)[0]


def _lean_code_map(src: str) -> tuple[str, list[int]]:
    """lean_code(src) and, for each of its characters, the index in src it comes from (a blanked string's two
    quotes map to the string's own quotes)."""
    out, pos, i, depth, n = [], [], 0, 0, len(src)
    while i < n:
        if depth == 0 and src[i] == "«":
            j = src.find("»", i + 1)
            j = n if j < 0 else j + 1
            out.append(src[i:j])
            pos += list(range(i, j))
            i = j
        elif depth == 0 and src[i] == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            out.append('""')
            pos += [i, min(j, n - 1)]
            i = j + 1
        elif depth == 0 and src.startswith("--", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif src.startswith("/-", i):
            depth += 1
            i += 2
        elif depth and src.startswith("-/", i):
            depth -= 1
            i += 2
        elif depth:
            i += 1
        else:
            out.append(src[i])
            pos.append(i)
            i += 1
    return "".join(out), pos


def replace_statement(src: str, name: str, text: str) -> str:
    """src with theorem `name`'s statement (from `theorem name` to its first `:=`, both found in the comment-free
    reading, where the theorem must be declared exactly once at a line start) replaced by text, everything else of the
    raw source kept (its comments and the marker line among them): rule L9's canary (review 2, B1)."""
    code, pos = _lean_code_map(src)
    hits = [m.start() for m in re.finditer(rf"(?m)^theorem {re.escape(name)}(?=\s)", code)]
    if len(hits) != 1:
        raise AssertionError(f"theorem {name} is not declared exactly once at a line start")
    j = code.find(":=", hits[0])
    if j < 0:
        raise AssertionError(f"theorem {name} has no :=")
    return src[:pos[hits[0]]] + text + " " + src[pos[j]:]


def lean_statement(src: str, name: str) -> str | None:
    """The statement of theorem `name` in a Lean source, comments removed: from `theorem name` up to the first `:=`,
    whitespace normalized; None unless the source, comments removed, declares `theorem name` exactly once (at a line
    start)."""
    code = lean_code(src)
    hits = [m.start() for m in re.finditer(rf"(?m)^theorem {re.escape(name)}(?=\s)", code)]
    if len(hits) != 1:
        return None
    i = hits[0]
    j = code.find(":=", i)
    if j < 0:
        return None
    return " ".join(code[i:j].split())


def theory2_doc() -> dict:
    """The content of spec/M3/lib/theory_core2.json (rules C1, C2): pure texts, no repository input."""
    return {
        "doc": ("I43 prereg sidecar (frozen), part A: theory core II (whitepaper §6 Thm 6.6 and 6.7; §5.3, §5.4, §10.3 "
                "steps 4-5, §10.8). core: the Bend statements (rule C1), checked at the prereg as well-typed open laws "
                "(bend reports exactly 15 TODOs and no other error; no proof attempted). lean: the Lean statements "
                "(rule C2), checked at the prereg with placeholder proofs (Lean reports only one 'declaration uses "
                "sorry' warning per theorem, 14, and the axiom audit prints every theorem by its bare name). probed: "
                "what the read-only I43 design survey checked before this prereg (nothing of it is committed): the "
                "six Bend laws of the survey's form and eleven Lean theorems. unprobed (by the survey): core_eqv_id, "
                "core_eqv_word, core_eqv_pow, core_nat_obs and the five inhabitation laws; thm_6_6_id_on, "
                "thm_6_6_comp_on and thm_6_7_obs. All were proved before the prereg all the same (the first draft's "
                "review proved its 14 Bend laws and 12 Lean theorems, the drafter the three added at the first fold, "
                "the second review all 15 and 14; nothing of it is committed), so part A predicts nothing: its "
                "outcome is construction check I43-R12. The frozen texts name no sidecar (review 2, B2). Recompute: "
                "python "
                "-c 'import json; from tests_m3 import _i43; print(json.dumps(_i43.theory2_doc(), indent=2, "
                "sort_keys=True))'"),
        "theory2_version": THEORY2_VERSION,
        "out": THEORY2_OUT.as_posix(),
        "core": {"laws_text": CORE2_LAWS_TEXT, "laws": CORE2_LAWS, "results": CORE2_RESULTS, "probed": CORE2_PROBED,
                 "unprobed": CORE2_UNPROBED},
        "lean": {"text": LEAN2_TEXT, "theorems": LEAN2_THEOREMS, "results": LEAN2_RESULTS, "probed": LEAN2_PROBED,
                 "unprobed": LEAN2_UNPROBED, "marker": LEAN_MARKER},
    }


# ============================================================================================== the instrument's readers
# Frozen here at the first review fold (review B1, M3, M4): the Lean toolchain resolution, the banned words, the axiom
# parser, the sentinel check and the semantic-rejection reading the tests use, and the Python import reader of rule
# R4. Nothing is taken from holon/ (I43 edits holon/lean.py); each is written again here, once.
ALLOWED_AXIOMS = ("Quot.sound", "propext")
# the pinned Lean, frozen here (review 2, m4: not read from config/holon.json, which the build may edit): the
# toolchain under ~/.elan/toolchains, its version, and the sha256 fingerprint over the executables and the shared
# libraries that hold the elaborator, the kernel and Lake (the files below, links resolved, as holon/lean.py computes
# it at the prereg; equal to config/holon.json's lean.pinned_fingerprint there)
LEAN_TOOLCHAIN = "leanprover/lean4:v4.34.0"
LEAN_VERSION = "4.34.0"
LEAN_FINGERPRINT = "sha256:01f7cb356f975fddb682edbdcad59f1dfd14a7acce12ca9b76e1fa35c8f345e0"
LEAN_FINGERPRINT_FILES = ("bin/lean", "bin/lake", "lib/lean/libleanshared.so", "lib/lean/libLake_shared.so")
# words no Lean file a test checks may hold (comment- and string-free reading, whole words): proof escapes, axioms,
# code that runs at elaboration time or changes how later text elaborates (macros, syntax, notations, attributes,
# instances, initializers, simprocs), the IO and process API, and Lean's own meta namespace
LEAN_BANNED = re.compile(
    r"\b(sorry|admit|sorryAx|native_decide|bv_decide|native|ofReduceBool|ofReduceNat|trustCompiler|axiom|unsafe\w*|"
    r"implemented_by|extern|export|opaque|partial|macro|macro_rules|syntax|elab|elab_rules|notation|infix|infixl|"
    r"infixr|prefix|postfix|declare_syntax_cat|binder_predicate|attribute|instance|import|run_cmd|run_tac|run_elab|"
    r"run_meta|initialize|builtin_initialize|simproc|dsimproc|unif_hint|IO|EIO|BaseIO|Process|System|Lean|dbg_trace|"
    r"dbgTrace)\b")
LEAN_ERROR = re.compile(r"(^|: )error(\(|:)")
LEAN_SORRY = re.compile(r"declaration uses [`']sorry[`']")
AXIOM_LINE = re.compile(r"'([^'\n]+)' (does not depend on any axioms|depends on axioms: \[([^\]]*)\])")
SENTINEL_PREFIX = "holon_i43_sentinel_"
# a canary counts as rejected only for a semantic reason: its first error says the kernel decided the claim false or
# found the two sides different, and no parse, name or goal-shape error appears anywhere. Lean 4.34.0's wordings
# (review 2, M1): "Tactic `decide` proved that the proposition ... is false" (decide), "Not a definitional equality:
# the left-hand side ... is not definitionally equal to the right-hand side" (rfl on a closed term), "Tactic `rfl`
# failed: The left-hand side ..." (the rfl tactic), "Type mismatch ..." (a term proof: fun _ => rfl, exact rfl,
# Eq.refl ..); SEMANTIC_PROBES pins them
SEMANTIC_REJECTION = re.compile(r"Tactic `decide` proved that the proposition|Not a definitional equality|"
                                r"is not definitionally equal|Tactic `rfl` failed: The left-hand side|"
                                r"(?i:type mismatch)")
NON_SEMANTIC = re.compile(r"(?i:unexpected token|unexpected identifier|unknown identifier|unknown constant|"
                          r"unknown tactic|expected term|unterminated|invalid syntax|"
                          r"Expected the goal to be a binary relation)")
# construction probes of the reading (review 2's probes/msgs2.lean and the non-semantic failures beside them): a
# false claim each proof style must be rejected for (True), and failures that are not semantic (False)
# Lean's own messages for the resource limits a not_run entry may claim (review 2, M3): rerun under the budget, the
# committed file must hit the claimed limit again (timeout: no verdict within the budget)
RESOURCE_LIMITS = {"recursion_depth": re.compile(r"maximum recursion depth has been reached"),
                   "heartbeats": re.compile(r"\(deterministic\) timeout at .*maximum number of heartbeats \(\d+\) "
                                            r"has been reached")}
RESOURCE_PROBES = {
    "heartbeats": "set_option maxHeartbeats 1 in\ntheorem p : (List.range 200).length = 200 := by decide",
    "recursion_depth": "set_option maxRecDepth 20 in\ntheorem p : (List.range 200).length = 200 := by decide",
}
SEMANTIC_PROBES = {
    "fun_rfl": ("theorem p : ∀ (x : Nat), [x, x+1] = [x+1, x] := fun _ => rfl", True),
    "exact_rfl": ("theorem p : ∀ (x : Nat), [x, x+1] = [x+1, x] := by intro x; exact rfl", True),
    "eq_refl": ("theorem p : ∀ (x : Nat), [x, x+1] = [x+1, x] := fun x => Eq.refl [x, x+1]", True),
    "closed_rfl": ("theorem p : (2:Nat) + 2 = 5 := rfl", True),
    "decide": ("theorem p : (2:Nat) + 2 = 5 := by decide", True),
    "rfl_tactic": ("theorem p : ∀ (x : Nat), [x, x+1] = [x+1, x] := by intros; rfl", True),
    "simp_goals": ("theorem p : (2:Nat) + 2 = 5 := by simp", False),
    "unknown_identifier": ("theorem p : (2:Nat) + 2 = 5 := foo", False),
    "unknown_tactic": ("theorem p : (2:Nat) + 2 = 5 := by frob", False),
    "parse_error": ("theorem p : (2:Nat) + 2 = := rfl", False),
    "omega": ("theorem p : (2:Nat) + 2 = 5 := by omega", False),
}
_LEAN: dict = {}
_LEAN_LOCK = threading.Lock()


def _lean_env(bin_dir: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("LEAN", "LAKE", "ELAN"))}
    env["PATH"] = os.pathsep.join([str(bin_dir), env.get("PATH", "")])
    return env


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def lean_toolchain() -> Path:
    """The pinned Lean toolchain's bin directory, resolved by the instrument (review M4, review 2 m4): LEAN_TOOLCHAIN
    under ~/.elan/toolchains (never a PATH lookup); the sha256 fingerprint over LEAN_FINGERPRINT_FILES equal to
    LEAN_FINGERPRINT; `lean --version` LEAN_VERSION. Anything else fails the test that needs Lean, named (never a
    skip)."""
    with _LEAN_LOCK:
        if "bin" in _LEAN:
            return _LEAN["bin"]
        tc, pin_v, pin_fp = LEAN_TOOLCHAIN, LEAN_VERSION, LEAN_FINGERPRINT
        d = Path.home() / ".elan" / "toolchains" / tc.replace("/", "--").replace(":", "---") / "bin"
        if not (d / "lean").is_file():
            raise AssertionError(f"the Lean toolchain {tc} is not installed (no {d / 'lean'})")
        home = Path(os.path.realpath(d)).parent
        h = hashlib.sha256()
        for rel in LEAN_FINGERPRINT_FILES:
            p = home / rel
            if not p.is_file():
                raise AssertionError(f"the Lean toolchain file {p} is missing")
            h.update(rel.encode() + b"\0" + _sha256_file(p).encode() + b"\n")
        fp = "sha256:" + h.hexdigest()
        if fp != pin_fp:
            raise AssertionError(f"the Lean toolchain at {home} has fingerprint {fp}, not the pinned {pin_fp}")
        p = subprocess.run([str(d / "lean"), "--version"], capture_output=True, text=True, timeout=120,
                           env=_lean_env(d))
        m = re.match(r"Lean \(version (\d+\.\d+\.\d+)", p.stdout.strip())
        if p.returncode != 0 or not m or m.group(1) != pin_v:
            raise AssertionError(f"lean --version says {p.stdout.strip() or p.stderr.strip()!r}, not {pin_v}")
        _LEAN["bin"] = d
        return d


def run_lean(text: str, timeout: int = 900) -> dict:
    """Elaborate one Lean text with the pinned lean (lean_toolchain) in a fresh temporary directory, no lake, no
    LEAN*/LAKE*/ELAN* environment: {"code": exit code (None on timeout), "out": stdout and stderr, "seconds"}."""
    b = lean_toolchain()
    tmp = Path(tempfile.mkdtemp(prefix="i43_lean_"))
    try:
        (tmp / "T.lean").write_text(text, encoding="utf-8")
        t0 = time.monotonic()
        try:
            p = subprocess.run([str(b / "lean"), "T.lean"], cwd=tmp, capture_output=True, text=True, timeout=timeout,
                               env=_lean_env(b))
            code, out = p.returncode, p.stdout + p.stderr
        except subprocess.TimeoutExpired:
            code, out = None, f"(lean timed out after {timeout} s)"
        return {"code": code, "out": out, "seconds": time.monotonic() - t0}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def lean_errors(out: str) -> list[str]:
    return [ln for ln in out.splitlines() if LEAN_ERROR.search(ln)]


def parse_axioms(out: str) -> list[tuple[str, list[str]]]:
    """Lean's `#print axioms` lines, in output order: [(theorem, sorted axioms)]."""
    return [(m.group(1), sorted(a.strip() for a in (m.group(3) or "").replace("\n", " ").split(",") if a.strip()))
            for m in AXIOM_LINE.finditer(out)]


def first_error_block(out: str) -> str:
    """The text of Lean's first error, up to the next error or warning."""
    lines = out.splitlines()
    i = next((k for k, ln in enumerate(lines) if LEAN_ERROR.search(ln)), None)
    if i is None:
        return ""
    j = next((k for k in range(i + 1, len(lines)) if re.search(r"(^|: )(error|warning)(\(|:)", lines[k])), len(lines))
    return "\n".join(lines[i:j])


def semantic_rejection(out: str) -> bool:
    """Was a text rejected for a semantic reason (SEMANTIC_REJECTION in its first error, no NON_SEMANTIC error)?"""
    return bool(SEMANTIC_REJECTION.search(first_error_block(out))) and not NON_SEMANTIC.search(out)


def resource_limit_reproduces(text: str, reason: str, budget: int) -> tuple[bool, str]:
    """(does Lean, run on text within `budget` seconds, hit the limit `reason` names, the output's tail): timeout: no
    verdict within the budget; recursion_depth and heartbeats: Lean's own error for that limit (RESOURCE_LIMITS)."""
    r = run_lean(text, timeout=budget)
    if reason == "timeout":
        return r["code"] is None, f"lean ended with exit code {r['code']} after {r['seconds']:.1f} s"
    rx = RESOURCE_LIMITS.get(reason)
    return bool(rx and rx.search(r["out"])), r["out"][-500:]


def lean_check(text: str, names: list[str], timeout: int = 900, allow_sorry: bool = False, extra: str = "",
               allowed: tuple | None = ALLOWED_AXIOMS) -> dict:
    """The instrument's Lean check of one text (review B1): the text, then a final sentinel theorem with a fresh random
    name, then `#print axioms` for each of names and for the sentinel, then extra (e.g. `#check`s under pp.all), run
    by run_lean. run_lean's result plus "problems" (empty when accepted): the exit code is not 0; an error line; a
    "declaration uses sorry" warning (unless allow_sorry); the output's axiom-audit lines do not end with exactly
    names and the sentinel, in that order (so elaboration reached the end of the text and nothing cut it short or
    printed audit lines of its own); a printed axiom outside `allowed` (ALLOWED_AXIOMS; the instruments' own
    placeholder checks pass sorryAx too, or None over an interface stub, whose signatures are axioms). "axioms":
    {name: axioms}."""
    s = SENTINEL_PREFIX + secrets.token_hex(8)
    want = list(names) + [s]
    full = (text.rstrip("\n") + f"\n\ntheorem {s} : True := trivial\n\n"
            + "".join(f"#print axioms {n}\n" for n in want) + extra)
    r = run_lean(full, timeout)
    out, probs = r["out"], []
    if r["code"] != 0:
        probs.append(f"lean exit code {r['code']}")
    errs = lean_errors(out)
    if errs:
        probs.append(f"{len(errs)} error lines, first: {errs[0][:300]}")
    if not allow_sorry and LEAN_SORRY.search(out):
        probs.append("a declaration uses sorry")
    ax = parse_axioms(out)
    tail = ax[-len(want):] if len(ax) >= len(want) else ax
    if [n for n, _ in tail] != want:
        probs.append(f"the axiom audit does not end with the {len(names)} checked names and the sentinel "
                     f"({len(ax)} audit lines; the sentinel {'is' if s in dict(ax) else 'is not'} among them)")
    elif allowed is not None:
        bad = {n: a for n, a in tail if not set(a) <= set(allowed)}
        if bad:
            probs.append(f"axioms outside {list(allowed)}: {dict(list(bad.items())[:5])}")
    r.update(problems=probs, axioms={n: a for n, a in tail}, sentinel=s)
    return r


# ---------------------------------------------------------------------------------------------- R4: Python imports
BEND_SIDE = re.compile(r"^holon\.gen\.(machine|mlaws|mproofs|linked|coercion|core|refs|model|laws|proofs|oracles)$|"
                       r"^holon\.sorts(\.|$)")
INSTRUMENTS = re.compile(r"^tests(_m\d+)?(\.|$)")
DYNAMIC_NAMES = {"__import__", "importlib", "runpy", "exec", "eval", "__builtins__", "pkgutil", "imp",
                 "getattr", "vars", "globals"}   # review 2, m2: reflective access reaches a module by a computed name
DYNAMIC_ATTRS = {"import_module", "__import__", "exec_module", "load_module", "module_from_spec",
                 "spec_from_file_location", "spec_from_loader", "SourceFileLoader", "find_spec", "load_source",
                 "run_path", "run_module", "__dict__"}


def _module_file(root: Path, mod: str) -> str | None:
    p = Path(*mod.split("."))
    for cand in (p.with_suffix(".py"), p / "__init__.py"):
        if (root / cand).is_file():
            return cand.as_posix()
    return None


def module_imports(root: Path, rel: str) -> tuple[list[str], list[str]]:
    """(the dotted modules a Python file imports, its dynamic-import constructs), read from its AST (every import
    statement, at any depth). `import a.b.c` imports a, a.b and a.b.c; `from X import y` imports X and X.y (y may be
    a submodule); a relative import at level n is resolved against the file's package (its own package for an
    __init__.py), n - 1 levels up. An attribute chain from a name an import binds (`import holon.gen` then
    holon.gen.mlaws.X; `from holon import gen as g` then g.mlaws) imports every module its prefixes name (review 2,
    m2). Dynamic constructs: a name in DYNAMIC_NAMES (getattr, vars and globals among them), an attribute in
    DYNAMIC_ATTRS (__dict__ among them), sys.modules, an import of importlib, runpy, imp, pkgutil or builtins."""
    import ast
    root = Path(root)
    pkg = list(Path(rel).with_suffix("").parts)[:-1]   # a module's package; an __init__.py's own package
    mods, dyn, binds = [], [], {}
    tree = ast.parse((root / rel).read_text(encoding="utf-8"))
    for n in ast.walk(tree):   # the names imports bind, to their dotted modules
        if isinstance(n, ast.Import):
            for a in n.names:
                binds[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
        elif isinstance(n, ast.ImportFrom) and not (n.level and n.level - 1 > len(pkg)):
            base = pkg[:len(pkg) - (n.level - 1)] if n.level else []
            b = ".".join(base + ((n.module or "").split(".") if n.module else []))
            for a in n.names:
                if a.name != "*":
                    binds[a.asname or a.name] = f"{b}.{a.name}" if b else a.name
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute):   # an attribute chain rooted at an imported name
            chain, x = [], n
            while isinstance(x, ast.Attribute):
                chain.append(x.attr)
                x = x.value
            if isinstance(x, ast.Name) and x.id in binds:
                ps = binds[x.id].split(".") + chain[::-1]
                mods += [".".join(ps[:i]) for i in range(1, len(ps) + 1)]
        if isinstance(n, ast.Import):
            for a in n.names:
                ps = a.name.split(".")
                mods += [".".join(ps[:i]) for i in range(1, len(ps) + 1)]
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                if n.level - 1 > len(pkg):
                    dyn.append(f"a relative import beyond the top package (level {n.level})")
                    continue
                base = pkg[:len(pkg) - (n.level - 1)]
            else:
                base = []
            b = ".".join(base + ((n.module or "").split(".") if n.module else []))
            if b:
                mods.append(b)
            mods += [f"{b}.{a.name}" if b else a.name for a in n.names if a.name != "*"]
        elif isinstance(n, ast.Name) and n.id in DYNAMIC_NAMES:
            dyn.append(n.id)
        elif isinstance(n, ast.Attribute):
            if n.attr in DYNAMIC_ATTRS:
                dyn.append(n.attr)
            if n.attr == "modules" and isinstance(n.value, ast.Name) and n.value.id == "sys":
                dyn.append("sys.modules")
    for m in mods:
        if m.split(".")[0] in ("importlib", "runpy", "imp", "pkgutil", "builtins"):
            dyn.append(f"import {m}")
    return sorted(set(mods)), sorted(set(dyn))


def import_closure(root: Path, starts: list[str]) -> dict[str, dict]:
    """The transitive closure of Python imports from the files `starts` (repo-relative), following every imported
    module that is a file under holon/ (and the package __init__.py of each dotted prefix it names):
    {file: {"imports": [...], "dynamic": [...]}}."""
    root = Path(root)
    out, todo = {}, list(starts)
    while todo:
        rel = todo.pop()
        if rel in out or not (root / rel).is_file():
            continue
        mods, dyn = module_imports(root, rel)
        out[rel] = {"imports": mods, "dynamic": dyn}
        for m in mods:
            if m.split(".")[0] != "holon":
                continue
            f = _module_file(root, m)
            if f and f not in out:
                todo.append(f)
    return dict(sorted(out.items()))


def independence_violations(root: Path, starts: list[str]) -> list[str]:
    """Rule L1's independence over the import closure of `starts` (import_closure): no file of it imports a Bend-side
    module (BEND_SIDE: holon/gen/{machine,mlaws,mproofs,linked,coercion,core,refs,model,laws,proofs,oracles}.py,
    holon/sorts/*) or an instrument (tests, tests_m*), and none uses a dynamic-import construct."""
    out = []
    for f, info in import_closure(root, starts).items():
        out += [f"{f} imports {m} (the Bend side)" for m in info["imports"] if BEND_SIDE.match(m)]
        out += [f"{f} imports {m} (an instrument)" for m in info["imports"] if INSTRUMENTS.match(m)]
        out += [f"{f} uses {d} (a dynamic import)" for d in info["dynamic"]]
    return out


# ---------------------------------------------------------------------------------------------- B1: the cheats
# The independent review's cheat files (scratchpad review_i43/esc/, first review of the I43 prereg), kept verbatim:
# each must be rejected by the instrument (file rules and lean_check). "lean_alone": lean_check rejects it even without
# the file rules (it cuts elaboration short, forges audit lines or turns decide into sorry).
_FAKE_BATCHDATA = '''set_option autoImplicit false
set_option maxRecDepth 20000

namespace Model

inductive Obs where
  | ok
  | rev (code : Nat)
deriving DecidableEq

structure T_Sl where
  f_b : Nat
  f_off : Nat
  f_len : Nat
  f_cap : Nat
deriving DecidableEq

structure T_Arr where
  f_cells : List Nat
deriving DecidableEq

structure St where
  f_heap : List T_Arr
  f_ctx : T_Sl
  f_txp : T_Sl
  f_view : T_Sl
  f_snap : List Nat
  f_live : Bool
  f_classes : List Nat
  f_log : List Obs
deriving DecidableEq

inductive Act where
  | a_append (i_bctx : List Nat) (i_payload : List Nat)
  | a_txsPayloadV2
deriving DecidableEq

def s0 : St := { f_heap := [], f_ctx := { f_b := 0, f_off := 0, f_len := 0, f_cap := 0 }, f_txp := { f_b := 0, f_off := 0, f_len := 0, f_cap := 0 }, f_view := { f_b := 0, f_off := 0, f_len := 0, f_cap := 0 }, f_snap := [], f_live := false, f_classes := [], f_log := [] }
def step (a : Act) (s : St) : St := s
def run (tr : List Act) (s : St) : St := s
def obs (tr : List Act) (s : St) : List Obs := []
def fn_last_ok (s : St) : Bool := true
def fn_runs_ok (tr : List Act) (s : St) : Bool := true
def fn_no_code (l : List Obs) (k : Nat) : Bool := true
def fn_perm (a : Act) : Bool := true
def fn_is_append (a : Act) : Bool := true
def fn_is_txsPayloadV2 (a : Act) : Bool := true
def ob_view_intact (s : St) : Bool := true
@@CHEAT@@

end Model
'''
CHEATS = {
    "E1": {"file": "law", "lean_alone": False, "names": ["t"], "text": (
        "set_option autoImplicit false\n"
        "def x : Nat := 1 #eval IO.println (String.mk ['p','w','n','e','d'])\n"
        "theorem t : x = 1 := rfl\n")},
    "E2": {"file": "law", "lean_alone": True, "names": ["t"], "text": (
        "set_option autoImplicit false\n"
        "def pr (s : List Char) : IO Unit := IO.println (String.ofList s)\n"
        "def q : Char := Char.ofNat 39\n"
        "def x : Nat := 1 #eval do pr ([q] ++ ['t'] ++ [q] ++ [(Char.ofNat 32)] ++ [(Char.ofNat 100)]); "
        "(IO.Process.exit 0 : IO Unit)\n"
        "theorem t : 1 = 2 := by\n  exact rfl\n")},
    "E3": {"file": "law", "lean_alone": True, "names": ["bad"], "text": (
        "set_option autoImplicit false\n"
        "namespace Model\n"
        "def zz : Nat := 0\n"
        "  macro_rules | `(tactic| decide) => `(tactic| exact sorryAx _ false)\n"
        "end Model\n"
        "theorem bad : 1 = 2 := by decide\n")},
    "E4": {"file": "law", "lean_alone": True, "names": ["t"], "text": (
        "set_option autoImplicit false\n"
        "def q : Char := Char.ofNat 39\n"
        "def zz : Nat := 0 #eval do IO.println (String.ofList ([q, 't', q, ' '] ++ ['d','e','p','e','n','d','s',' ',"
        "'o','n',' ','a','x','i','o','m','s',':',' ','[','p','r','o','p','e','x','t',']'])); (← IO.getStdout).flush; "
        "(IO.Process.exit 0 : IO Unit)\n"
        "theorem t : 1 = 2 := by decide\n")},
    "E5": {"file": "law", "lean_alone": True, "names": ["t"], "text": (
        "set_option autoImplicit false\n"
        "def q : Char := Char.ofNat 39\n"
        "def msg : String := String.ofList ([q, 't', q, ' '] ++ ['d','e','p','e','n','d','s',' ','o','n',' ','a','x',"
        "'i','o','m','s',':',' ','[','p','r','o','p','e','x','t',']', Char.ofNat 10])\n"
        "def dev : String := String.ofList ['/','d','e','v','/','s','t','d','o','u','t']\n"
        "def zz : Nat := 0 #eval do let h ← IO.FS.Handle.mk dev IO.FS.Mode.append; h.putStr msg; h.flush; "
        "(IO.Process.exit 0 : IO Unit)\n"
        "theorem t : 1 = 2 := by decide\n")},
    # a deliberately wrong model of M1's morph_batchdata (every frozen type verbatim, every function trivial) whose
    # differential would pass if Lean stopped early or decide meant sorry
    "fake_model_eval": {"file": "model", "lean_alone": True, "model": "M1:morph_batchdata",
                        "text": _FAKE_BATCHDATA.replace("@@CHEAT@@",
                                                        "def zz : Nat := 0 #eval (IO.Process.exit 0 : IO Unit)")},
    "fake_model_macro": {"file": "model", "lean_alone": True, "model": "M1:morph_batchdata",
                         "text": _FAKE_BATCHDATA.replace(
                             "@@CHEAT@@", "def zz : Nat := 0\n  macro_rules | `(tactic| decide) => "
                                          "`(tactic| exact sorryAx _ false)")},
    # the same wrong model without a trick: the differential itself rejects it
    "fake_model_plain": {"file": "model", "lean_alone": True, "model": "M1:morph_batchdata",
                         "text": _FAKE_BATCHDATA.replace("@@CHEAT@@\n", "")},
}
# a clean file both readings accept (the construction tests' control)
CLEAN_LAW = ("set_option autoImplicit false\n\nnamespace Model\n\ndef x : Nat := 1\n\nend Model\n\n" + LEAN_MARKER
             + "\n\ntheorem t : Model.x = 1 := rfl\n")


def file_check(src: str, kind: str, model: dict | None = None) -> list[str]:
    """Rule L4's reading of a Lean file a test checks (kind "law", "model" or "core"): file_violations (law and model
    files) or core_file_violations (the core file), plus shadow_violations when the model is given."""
    if kind == "core":
        return core_file_violations(src)
    v = file_violations(src, law_file=(kind == "law"))
    if model is not None:
        v += shadow_violations(src, model)
    return v


# ============================================================================================== part B: Lean for Q8's set
PROMOTED_VERSION = "holon-lean-promoted/0.1"
PROMOTED_SIDECAR = Path("spec") / "M3" / "lib" / "lean_promoted.json"
ORACLES = "spec/M2/lib/oracles.json"
# rule L0: (directory key, records, law files, Lean output directory, the facts document of every record there, or
# None for the law file's own "facts")
DIRS = (("M1", "results/M1", "laws/M1", "gen/M1/lean", None),
        ("M2", "results/M2", "laws/M2", "gen/M2/lean", None),
        ("M2/extracted_m1", "results/M2/extracted_m1", "laws/M1", "gen/M2/extracted/m1/lean",
         "gen/M2/extracted/m1_view.json"),
        ("M3", "results/M3", "laws/M3", "gen/M3/lean", None))
KINDS = ("machine", "machine_oracle", "linked")     # the model kinds the Lean emitters cover (rule L1)
ALLOWED_REASONS = ("timeout", "recursion_depth", "heartbeats", "unsupported_form", "no_report", "toolchain_unavailable")
# the final states a REFUTED attempted law may keep instead of checked (review M2): the resource limits only (every
# counter-law is rendered, so never unsupported_form; no_report and toolchain_unavailable are transient)
REFUTED_REASONS = ("timeout", "recursion_depth", "heartbeats")
UNDEF = 57005           # the Bend models' undefined byte (BEND_PRIMER §4); a Lean undefined cell is `none`


class Unsupported(Exception):
    """An IR form, a binder type or a model kind the rules L1-L3 do not render (named in the message)."""


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha_json(obj) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def _ident(s: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", s):
        raise Unsupported(f"{s!r} is not a plain identifier")
    return s


# ---------------------------------------------------------------------------------------------- rule L0: the scope
def _proof_class(rec: dict) -> str | None:
    """The Bend class that produced the record's verdict: the generator of its successful proof attempt (PROVED) or
    counter-law attempt (REFUTED)."""
    want = "proof" if rec.get("status") == "PROVED" else "counter-law"
    for a in rec.get("attempts") or []:
        if a.get("kind") == want and a.get("exit_code") == 0:
            return a.get("generator")
    return None


def oracle_params(root: Path, facts_rel: str) -> dict[str, str]:
    """The modelled oracle parameters of the M2+ machine models compiled from facts_rel: {name: Fn type}."""
    doc = load_json(Path(root) / ORACLES)
    return {o["parameter"]["name"]: o["parameter"]["type"] for o in doc["oracles"]
            if o.get("status") == "modelled" and facts_rel in doc.get("facts", [])}


def model_kind(facts_doc: dict, law: dict) -> str:
    if facts_doc.get("linked_version"):
        return "linked"
    if facts_doc.get("facts_version") == "holon-facts/0.2":
        if law.get("ir_version") == "holon-ir/0.2":
            return "machine"
        if law.get("ir_version") == "holon-ir/0.3":
            return "machine_oracle"
    return "other"


def scope(root: Path = ROOT) -> list[dict]:
    """Rule L0: every PROVED and REFUTED record of the four directories, in (directory, law id) order."""
    root = Path(root)
    out = []
    for dkey, rdir, ldir, odir, facts_override in DIRS:
        reg = load_json(root / ldir / "REGISTRY.json")["statements"]
        for p in sorted((root / rdir).glob("L*.json")):
            rec = load_json(p)
            if rec.get("status") not in ("PROVED", "REFUTED"):
                continue
            lid = p.stem
            law = load_json(root / ldir / f"{lid}.json")
            facts_rel = facts_override or law["facts"]
            facts_doc = load_json(root / facts_rel)
            art = rec.get("artifacts") or {}
            model = art.get("model")
            kind = model_kind(facts_doc, law)
            out.append({
                "dir": dkey, "law_id": lid, "status": rec["status"], "ir_version": law["ir_version"],
                "rule": law["rule"], "subform": law.get("subform"), "law_file": f"{ldir}/{lid}.json",
                "statement_hash": reg[lid], "proof_class": _proof_class(rec), "facts": facts_rel,
                "facts_sha256": file_sha256(root / facts_rel), "model": model, "kind": kind,
                "model_key": f"{dkey}:{Path(model).stem}" if model else None,
                "lean_source": f"{odir}/{lid}.lean", "lean_dir": odir,
                "lean_model": f"{odir}/models/{Path(model).stem}.lean" if model else None,
                "record": f"{rdir}/{lid}.json",
                "theorem": lid if rec["status"] == "PROVED" else f"{lid}_counter",
            })
    return out


# ---------------------------------------------------------------------------------------------- rule L2: interfaces
def _lt_machine(t: str, records: dict) -> str:
    """A facts type as a Lean type, unqualified (inside namespace Model)."""
    if t in ("Nat", "Bool"):
        return t
    if t == "Obs":
        return "Obs"
    m = re.fullmatch(r"List<(.+)>", t)
    if m:
        return f"List {_lt_machine(m.group(1), records)}" if m.group(1) in ("Nat", "Bool", "Obs") or \
            m.group(1) in records else f"List ({_lt_machine(m.group(1), records)})"
    if t in records:
        return f"T_{_ident(t)}"
    raise Unsupported(f"facts type {t}")


def _calls(e, names: set, out: set) -> set:
    if isinstance(e, list) and e:
        if e[0] == "call" and len(e) > 1 and e[1] in names:
            out.add(e[1])
        for x in e[1:]:
            _calls(x, names, out)
    elif isinstance(e, dict):
        for x in e.values():
            _calls(x, names, out)
    return out


def _reaches_param(e, facts: dict, params: dict) -> bool:
    """Does facts expression e evaluate a call of a modelled oracle parameter (directly or through definitions)?"""
    defs = facts.get("defs", {})
    seen, todo = set(), [e]
    while todo:
        x = todo.pop()
        if _calls(x, set(params), set()):
            return True
        for d in _calls(x, set(defs), set()) - seen:
            seen.add(d)
            todo.append(defs[d].get("body"))
    return False


def site_name(site_id: str) -> str:
    """The site predicate of an I15 site id "<model>:<span>:<x8>" (holon.sorts.sites rule R7, written again here):
    <where>_<x8>, <where> = slug(file stem)_<lo>[_<hi>] for a source span, def_<slug(def)> for a definition."""
    head, x8 = site_id.rsplit(":", 1)
    model, span = head.split(":", 1)
    slug = lambda s: re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")  # noqa: E731
    m = re.match(r"^(?P<path>\S+?):(?P<lo>\d+)(?:-(?P<hi>\d+))?$", span)
    if m:
        where = slug(Path(m["path"]).stem) + f"_{m['lo']}" + (f"_{m['hi']}" if m["hi"] else "")
    elif span.startswith(model + ":"):
        where = "def_" + slug(span.split(":", 1)[1])
    else:
        raise Unsupported(f"site {site_id}: span {span!r}")
    return _ident(f"site_{where}_{x8}")


def view_name(fields: list[str]) -> str:
    return "__".join(_ident(f) for f in sorted(fields))


def ro_name(site: str) -> str:
    """The raw obligation function of site predicate site_<x>: ro_<x>."""
    return "ro_" + site[len("site_"):]


def obligation_vars(expr, facts: dict) -> list[tuple[str, str]]:
    """The free variables of a site's subtraction ["-", minuend, subtrahend], in order of first occurrence (pre-order,
    left to right), each with its facts type: Nat for an operand of + or -, the parameter's type for an argument of a
    facts definition call. Literals are Nat; any other form is unsupported."""
    defs = facts.get("defs") or {}
    out: dict[str, str] = {}

    def go(e, want: str):
        if isinstance(e, bool) or e is None:
            raise Unsupported(f"obligation term {e!r}")
        if isinstance(e, int):
            if want != "Nat":
                raise Unsupported(f"a literal where {want} is expected")
            return
        if isinstance(e, str):
            if out.setdefault(e, want) != want:
                raise Unsupported(f"variable {e} used at {out[e]} and {want}")
            return
        if isinstance(e, list) and len(e) == 3 and e[0] in ("+", "-"):
            if want != "Nat":
                raise Unsupported(f"{e[0]} where {want} is expected")
            go(e[1], "Nat")
            go(e[2], "Nat")
            return
        if isinstance(e, list) and len(e) >= 2 and e[0] == "call" and e[1] in defs:
            d = defs[e[1]]
            ps = d.get("params") or []
            if d.get("type") != want or len(ps) != len(e) - 2:
                raise Unsupported(f"call of {e[1]}")
            for (_, pt), a in zip(ps, e[2:]):
                go(a, pt)
            return
        raise Unsupported(f"obligation term {canonical(e)[:80]}")

    if not (isinstance(expr, list) and len(expr) == 3 and expr[0] == "-"):
        raise Unsupported(f"a site expression that is not a subtraction: {canonical(expr)[:80]}")
    go(expr, "Nat")
    return list(out.items())


def bend_obligation(expr, env: dict[str, str]) -> str:
    """A Bend term (the compiled model imported as M) for a site's raw obligation, subtrahend <= minuend, with each
    free variable replaced by env's Bend literal: + and - as Nat.add and Nat.sub (the facts' Nat arithmetic), a call
    of facts definition f as the model's M.d_<f>."""
    def go(e) -> str:
        if isinstance(e, int):
            return f"{e}n"
        if isinstance(e, str):
            return env[e]
        if e[0] in ("+", "-"):
            return f"Nat.{'add' if e[0] == '+' else 'sub'}({go(e[1])}, {go(e[2])})"
        return f"M.d_{e[1]}(" + ", ".join(go(a) for a in e[2:]) + ")"
    return f"Nat.is_le({go(expr[2])}, {go(expr[1])})"


def site_ids(e, out: list) -> list:
    """Every site id of an IR statement (its {"site": id, ...} terms), in pre-order."""
    if isinstance(e, dict):
        if "site" in e and isinstance(e["site"], str):
            out.append(e["site"])
        for v in e.values():
            site_ids(v, out)
    elif isinstance(e, list):
        for x in e:
            site_ids(x, out)
    return out


def interface(kind: str, facts: dict, params: dict | None = None, views: list | None = None,
              sites: list | None = None, obligations: dict | None = None) -> dict:
    """Rule L2: {"types": [[name, text]], "decls": [[name, text]], "signatures": [[name, type]]}, every text and
    type unqualified, as written inside `namespace Model`. types and decls are frozen verbatim (decls are part of the
    statements: a view, Reach); a signature is the elaborated type the model's definition of that name must have.
    obligations: {site predicate: the site's subtraction (laws/<M>/DERIVATION.json basis.expr)}, which gives each
    site its raw obligation ro_<x> (obligation_vars)."""
    if kind == "linked":
        types = [["Cell", "abbrev Cell : Type := Option (BitVec 8)"], ["Bytes", "abbrev Bytes : Type := List Cell"]]
        for cid, c in facts["carriers"].items():
            if c["kind"] != "record":
                continue
            cells = [f"  f_{_ident(f['name'].replace('.', '__'))}_{k} : BitVec 8" for f in c["fields"]
                     for k in range(f["width"])]
            types.append([f"R_{_ident(cid)}", f"structure R_{cid} where\n" + "\n".join(cells)])
        sigs = []
        for n, f in facts["functions"].items():
            k = f["kind"]
            if k == "encoder":
                sigs.append([f"c_{_ident(n)}", f"R_{f['from']} → Bytes"])
            elif k == "decoder":
                sigs.append([f"c_{_ident(n)}", "Bytes → Option Bytes"])
            elif k == "predicate":
                sigs.append([f"c_{_ident(n)}", "Bytes → Bool"])
            elif k == "loader":
                sigs += [[f"c_{_ident(n)}", "Bytes → Option Bytes"], [f"c_ok_{_ident(n)}", "Bytes → Bool"]]
            else:
                raise Unsupported(f"linked function kind {k}")
        return {"types": types, "decls": [], "signatures": sorted(sigs)}
    if kind not in ("machine", "machine_oracle"):
        raise Unsupported(f"model kind {kind}")
    params = params or {}
    records = facts.get("types", {})
    types = [["Obs", "inductive Obs where\n  | ok\n  | rev (code : Nat)\nderiving DecidableEq"]]
    for t, td in records.items():
        fl = "\n".join(f"  f_{_ident(fn)} : {_lt_machine(ft, records)}" for fn, ft in td["fields"])
        types.append([f"T_{_ident(t)}", f"structure T_{t} where\n{fl}\nderiving DecidableEq"])
    st = [(s[0], s[1]) for s in facts["state"]]
    fl = "\n".join(f"  f_{_ident(n)} : {_lt_machine(t, records)}" for n, t in st)
    types.append(["St", f"structure St where\n{fl}\nderiving DecidableEq"])
    alts = []
    for a in facts["actions"]:
        ins = "".join(f" (i_{_ident(n)} : {_lt_machine(t, records)})" for n, t in a["inputs"])
        alts.append(f"  | a_{_ident(a['name'])}{ins}")
    types.append(["Act", "inductive Act where\n" + "\n".join(alts) + "\nderiving DecidableEq"])
    pre = "".join(f"({_lt_fn(t)}) → " for t in params.values())   # the oracle parameters, in sidecar order
    sigs = [["step", f"{pre}Act → St → St"], ["run", f"{pre}List Act → St → St"], ["s0", "St"],
            ["obs", f"{pre}List Act → St → List Obs"], ["fn_last_ok", "St → Bool"],
            ["fn_runs_ok", f"{pre}List Act → St → Bool"], ["fn_no_code", "List Obs → Nat → Bool"],
            ["fn_perm", "Act → Bool"]]
    disch = facts.get("disch") or {}
    if disch.get("cost") is not None:
        sigs.append(["fn_cost", "List Act → Nat"])
    if disch.get("delay") is not None:
        sigs.append(["fn_elapsed", "List Act → Nat"])
    for a in facts["actions"]:
        sigs.append([f"fn_is_{_ident(a['name'])}", "Act → Bool"])
    for c in facts.get("consumers", {}):
        sigs.append([f"fn_{_ident(c)}", "Act → List Nat"])
    for o, od in facts.get("observers", {}).items():
        if [p[1] for p in od.get("params", [])] != ["State"]:
            raise Unsupported(f"observer {o} with parameters {od.get('params')}")
        p = pre if _reaches_param(od.get("body"), facts, params) else ""
        sigs.append([f"ob_{_ident(o)}", f"{p}St → {_lt_machine(od['type'], records)}"])
    for mg, md in facts.get("migrations", {}).items():
        p = pre if _reaches_param(md.get("effects"), facts, params) else ""
        ins = "".join(f"{_lt_machine(t, records)} → " for _, t in md.get("inputs", []))
        sigs.append([f"mig_{_ident(mg)}", f"{p}St → {ins}St"])
    for s in sites or []:
        sigs += [[s, f"{pre}Act → St → Bool"], ["hit_" + s[len("site_"):], f"{pre}Act → St → Bool"]]
        if obligations is not None:
            ex = obligations[s]
            p = pre if _reaches_param(ex, facts, params) else ""
            vs = "".join(f"{_lt_machine(t, records)} → " for _, t in obligation_vars(ex, facts))
            sigs.append([ro_name(s), f"{p}{vs}Bool"])
    decls = []
    for v in views or []:
        erased = v.split("__")
        kept = [(n, t) for n, t in st if n not in erased]
        fl = "\n".join(f"  f_{n} : {_lt_machine(t, records)}" for n, t in kept)
        body = ", ".join(f"f_{n} := s.f_{n}" for n, _ in kept)
        decls.append([f"V_{v}", f"structure V_{v} where\n{fl}"])
        decls.append([f"view_{v}", f"def view_{v} (s : St) : V_{v} :=\n  {{ {body} }}"])
    if kind == "machine_oracle":
        if not params:
            raise Unsupported("a machine_oracle model without a modelled oracle parameter")
        pb = " ".join(f"(p_{_ident(n)} : {_lt_fn(t)})" for n, t in params.items())
        pa = " ".join(f"p_{n}" for n in params)
        decls.append(["Reach", f"inductive Reach {pb} : St → Prop where\n  | r0 : Reach {pa} s0\n"
                               f"  | rstep (a : Act) (s : St) : Reach {pa} s → Reach {pa} (step {pa} a s)"])
    return {"types": types, "decls": decls, "signatures": sorted(sigs)}


def _lt_fn(t: str) -> str:
    """An IR Fn<A,B> over Nat, Bool and List<Nat> as a Lean function type."""
    m = re.fullmatch(r"Fn<(.+),(.+)>", t.replace(" ", ""))
    if not m:
        raise Unsupported(f"function type {t}")
    base = {"Nat": "Nat", "Bool": "Bool", "List<Nat>": "List Nat"}
    if m.group(1) not in base or m.group(2) not in base:
        raise Unsupported(f"function type {t}")
    return f"{base[m.group(1)]} → {base[m.group(2)]}"


# ---------------------------------------------------------------------------------------------- rule L3: statements
def _strip(s: str) -> str:
    """Drop one pair of outer parentheses that encloses a whole application (never a type ascription `(x : T)`)."""
    if not (s.startswith("(") and s.endswith(")")):
        return s
    depth = 0
    for i, ch in enumerate(s):
        depth += ch in "([{"
        depth -= ch in ")]}"
        if depth == 0 and i < len(s) - 1:
            return s
        if depth == 1 and s.startswith(" : ", i):
            return s
    return s[1:-1]


class Render:
    """Rule L3: an IR statement as a Lean proposition over the model interface (names qualified Model.<name>)."""

    def __init__(self, kind: str, facts: dict, params: dict | None = None):
        if kind not in KINDS:
            raise Unsupported(f"model kind {kind}")
        self.kind, self.f, self.params = kind, facts, params or {}
        self.views: set[str] = set()
        self.sites: set[str] = set()
        self.used: set[str] = set()
        self.parametric: set[str] = set()
        if kind != "linked":
            self.records = facts.get("types", {})
            self.actions = {a["name"]: a for a in facts["actions"]}
            sig = interface(kind, facts, self.params)["signatures"]
            self.sig = dict(sig)
            pre = "".join(f"({_lt_fn(t)}) → " for t in self.params.values())
            self.parametric = {n for n, t in sig if pre and t.startswith(pre)}

    # -- types
    def ty(self, t: str) -> str:
        if self.kind == "linked":
            if t == "Bytes":
                return "Model.Bytes"
            c = self.f["carriers"].get(t)
            if c and c["kind"] == "record":
                return f"Model.R_{_ident(t)}"
            raise Unsupported(f"binder type {t}")
        if t.startswith("Fn<"):
            return _lt_fn(t)
        base = {"State": "Model.St", "Trace": "List Model.Act", "Act": "Model.Act", "Nat": "Nat", "Bool": "Bool",
                "List<Nat>": "List Nat"}
        if t in base:
            return base[t]
        if t in self.records:
            return f"Model.T_{_ident(t)}"
        raise Unsupported(f"binder type {t}")

    def pargs(self, name: str, env: dict) -> str:
        """The oracle-parameter arguments a parametric model function takes first (the law's binders)."""
        if name not in self.parametric and not name.startswith("site_"):
            return ""
        out = ""
        for p in self.params:
            if p not in env or env[p][1] != "Fn":
                raise Unsupported(f"{name} runs the parametric model, but the statement binds no parameter {p}")
            out += f" {env[p][0]}"
        return out

    def call(self, name: str, args: list[str], env: dict) -> str:
        self.used.add(name)
        return "(" + " ".join([f"Model.{name}{self.pargs(name, env)}"] + args) + ")"

    # -- terms: (text, IR type)
    def term(self, t: dict, env: dict) -> tuple[str, str]:
        if not isinstance(t, dict):
            raise Unsupported(f"term {t!r}")
        if "var" in t:
            v = env.get(t["var"])
            if v is None:
                raise Unsupported(f"unbound {t['var']}")
            return v[0], v[1]
        if self.kind == "linked":
            return self.lterm(t, env)
        if "nat" in t and len(t) == 1:
            return str(int(t["nat"])), "Nat"
        if "bool" in t and len(t) == 1:
            return ("true" if t["bool"] else "false"), "Bool"
        if "nats" in t and len(t) == 1:
            xs = [str(int(x)) for x in t["nats"]]
            return ("[" + ", ".join(xs) + "]" if xs else "([] : List Nat)"), "List<Nat>"
        if "s0" in t and len(t) == 1:
            self.used.add("s0")
            return "Model.s0", "State"
        if set(t) == {"run", "from"}:
            tr, s = self.expect(t["run"], "Trace", env), self.expect(t["from"], "State", env)
            return self.call("run", [tr, s], env), "State"
        if set(t) == {"step", "from"}:
            a, s = self.expect(t["step"], "Act", env), self.expect(t["from"], "State", env)
            return self.call("step", [a, s], env), "State"
        if set(t) == {"obs", "from"}:
            tr, s = self.expect(t["obs"], "Trace", env), self.expect(t["from"], "State", env)
            return self.call("obs", [tr, s], env), "Obs"
        if set(t) == {"trace"}:
            xs = [_strip(self.expect(a, "Act", env)) for a in t["trace"]]
            return ("[" + ", ".join(xs) + "]" if xs else "([] : List Model.Act)"), "Trace"
        if set(t) == {"cat"}:
            if len(t["cat"]) != 2:
                raise Unsupported("cat of other than two traces")
            x, y = (self.expect(z, "Trace", env) for z in t["cat"])
            return f"({x} ++ {y})", "Trace"
        if set(t) == {"act", "args"}:
            a = self.actions.get(t["act"])
            if a is None or set(t["args"]) != {n for n, _ in a["inputs"]}:
                raise Unsupported(f"action term {t['act']}")
            args = [self.expect(t["args"][n], ity, env) for n, ity in a["inputs"]]
            head = f"Model.Act.a_{_ident(a['name'])}"
            return (f"({head} {' '.join(args)})" if args else head), "Act"
        if set(t) == {"proj", "of"}:
            st = {s[0] for s in self.f["state"]}
            if not t["proj"] or any(x not in st or x == "log" for x in t["proj"]):
                raise Unsupported(f"proj {t['proj']}")
            v = view_name(t["proj"])
            self.views.add(v)
            s = self.expect(t["of"], "State", env)
            self.used.add(f"view_{v}")
            return f"(Model.view_{v} {s})", f"V_{v}"
        if set(t) == {"obsv", "of"}:
            o = self.f.get("observers", {}).get(t["obsv"])
            if o is None:
                raise Unsupported(f"observer {t['obsv']}")
            s = self.expect(t["of"], "State", env)
            return self.call(f"ob_{_ident(t['obsv'])}", [s], env), o["type"]
        if set(t) <= {"mig", "of", "args"} and "mig" in t:
            md = self.f.get("migrations", {}).get(t["mig"])
            if md is None or len(t.get("args", [])) != len(md.get("inputs", [])):
                raise Unsupported(f"migration {t['mig']}")
            s = self.expect(t["of"], "State", env)
            args = [self.expect(x, ity, env) for (n, ity), x in zip(md.get("inputs", []), t.get("args", []))]
            return self.call(f"mig_{_ident(t['mig'])}", [s] + args, env), "State"
        if set(t) == {"fn", "args"}:
            return self.fn(t["fn"], t["args"], env)
        if set(t) == {"plus"}:
            x, y = (self.expect(z, "Nat", env) for z in t["plus"])
            return f"({x} + {y})", "Nat"
        if set(t) == {"app", "args"}:
            h = env.get(t["app"])
            if h is None or h[1] != "Fn" or len(t["args"]) != 1:
                raise Unsupported(f"application of {t['app']}")
            a, b = h[2]
            return f"({h[0]} {self.expect(t['args'][0], a, env)})", b
        if set(t) == {"site", "on", "from"}:
            if self.kind != "machine_oracle":
                raise Unsupported("a site term over a model without oracle parameters")
            n = site_name(t["site"])
            self.sites.add(n)
            a, s = self.expect(t["on"], "Act", env), self.expect(t["from"], "State", env)
            return self.call(n, [a, s], env), "Bool"
        raise Unsupported(f"term {sorted(t)}")

    def fn(self, name: str, args: list, env: dict) -> tuple[str, str]:
        acts = [a["name"] for a in self.f["actions"]]
        sig = {"last_ok": (["State"], "Bool"), "runs_ok": (["Trace", "State"], "Bool"),
               "no_code": (["Obs", "Nat"], "Bool"), "perm": (["Act"], "Bool"), "cost": (["Trace"], "Nat"),
               "elapsed": (["Trace"], "Nat")}
        sig |= {f"is_{a}": (["Act"], "Bool") for a in acts}
        sig |= {c: (["Act"], "List<Nat>") for c in self.f.get("consumers", {})}
        if name not in sig or f"fn_{name}" not in self.sig or len(args) != len(sig[name][0]):
            raise Unsupported(f"model function {name}")
        xs = [self.expect(x, ty, env) for x, ty in zip(args, sig[name][0])]
        return self.call(f"fn_{_ident(name)}", xs, env), sig[name][1]

    def lterm(self, t: dict, env: dict) -> tuple[str, str]:
        fs = self.f["functions"]
        if set(t) == {"field", "of"}:
            v, vt = self.term(t["of"], env)
            c = self.f["carriers"].get(vt)
            fld = next((f for f in (c or {}).get("fields", []) if f["name"] == t["field"]), None)
            if fld is None:
                raise Unsupported(f"field {t['field']} of {vt}")
            g = _ident(fld["name"].replace(".", "__"))
            cells = ", ".join(f"some {v}.f_{g}_{k}" for k in range(fld["width"]))
            return f"([{cells}] : Model.Bytes)", "Bytes"
        if set(t) == {"bytes"}:
            h = t["bytes"]
            if not re.fullmatch(r"0x(?:[0-9a-fA-F]{2})*", h):
                raise Unsupported(f"bytes {h}")
            cells = ", ".join(f"some 0x{h[i:i + 2].lower()}" for i in range(2, len(h), 2))
            return f"([{cells}] : Model.Bytes)", "Bytes"
        if set(t) == {"some"}:
            x, xt = self.term(t["some"], env)
            return f"(some {x})", f"Maybe<{xt}>"
        if set(t) == {"call", "args"}:
            n = t["call"]
            loaders = {f"ok_{m}": m for m, f in fs.items() if f["kind"] == "loader"}
            if n in fs:
                k = fs[n]["kind"]
                arg_t = fs[n]["from"] if k == "encoder" else "Bytes"
                res = {"encoder": "Bytes", "decoder": "Maybe<Bytes>", "predicate": "Bool", "loader": "Maybe<Bytes>"}[k]
            elif n in loaders:
                arg_t, res = "Bytes", "Bool"
            else:
                raise Unsupported(f"call {n}")
            if len(t["args"]) != 1:
                raise Unsupported(f"call {n} arity")
            x = self.expect(t["args"][0], arg_t, env)
            self.used.add(f"c_{n}")
            return f"(Model.c_{_ident(n)} {x})", res
        raise Unsupported(f"term {sorted(t)}")

    def expect(self, t: dict, want: str, env: dict) -> str:
        x, xt = self.term(t, env)
        if xt != want:
            raise Unsupported(f"a {xt} where {want} is expected: {canonical(t)[:120]}")
        return x

    # -- propositions
    def prop(self, p: dict, env: dict, negate: bool = False) -> str:
        if set(p) == {"eq"} or set(p) == {"neq"}:
            op = "eq" if "eq" in p else "neq"
            a, b = p[op]
            x, xt = self.term(a, env)
            y, yt = self.term(b, env)
            if xt != yt:
                raise Unsupported(f"{op} of {xt} and {yt}")
            rel = "=" if (op == "eq") != negate else "≠"
            return f"{_strip(x)} {rel} {_strip(y)}"
        raise Unsupported(f"premise or claim {sorted(p)}")

    def claim(self, c: dict, env: dict, negate: bool = False) -> str:
        if set(c) == {"all"}:
            parts = [self.prop(p, env) for p in c["all"]]
            body = " ∧ ".join(parts)
            return f"¬ ({body})" if negate else body
        return self.prop(c, env, negate)

    # -- binders
    def binders(self, law: dict) -> tuple[list, dict]:
        """[(q, lean name, Lean type, reach hypothesis or None)] in rule L3's order (oracle parameters first), and the
        environment {IR name: (Lean name, IR type, (A, B) for a Fn)}."""
        st = law["statement"]
        bs = st["binders"]
        if any(b["q"] not in ("forall", "exists") for b in bs):
            raise Unsupported("binder quantifier")
        if len({b["q"] for b in bs}) > 1:
            raise Unsupported("mixed quantifiers")
        params = [b for b in bs if b["name"] in self.params and b["type"].replace(" ", "") ==
                  self.params[b["name"]].replace(" ", "")]
        order = params + [b for b in bs if b not in params]
        env, out = {}, []
        for b in order:
            name = f"v_{_ident(b['name'])}"
            t = b["type"]
            if t.startswith("Fn<"):
                m = re.fullmatch(r"Fn<(.+),(.+)>", t.replace(" ", ""))
                env[b["name"]] = (name, "Fn", (m.group(1), m.group(2)))
                out.append((b["q"], name, _lt_fn(t), None))
            elif t == "Reach":
                if self.kind != "machine_oracle":
                    raise Unsupported("a Reach binder over a model without oracle parameters")
                env[b["name"]] = (name, "State")
                pa = " ".join(env[p][0] for p in self.params if p in env)
                if len(pa.split()) != len(self.params):
                    raise Unsupported("a Reach binder without the oracle parameters bound")
                self.used.add("Reach")
                out.append((b["q"], name, "Model.St", f"Model.Reach {pa} {name}"))
            else:
                env[b["name"]] = (name, t)
                out.append((b["q"], name, self.ty(t), None))
        return out, env

    def body(self, law: dict, counter: bool = False) -> str:
        st = law["statement"]
        sc = (st.get("scope") or {"kind": "unbounded"}).get("kind", "unbounded")
        if sc != "unbounded":
            raise Unsupported(f"scope {sc}")
        bs, env = self.binders(law)
        prem = [self.prop(p, env) for p in st.get("assume", [])]
        q = bs[0][0] if bs else "forall"
        if q == "exists":
            if counter:
                raise Unsupported("the counter-law of an existential law (never REFUTED)")
            inner = " ∧ ".join(prem + [self.claim(st["claim"], env)])
            return self.quant("∃", bs, inner, "∧")
        if counter:
            inner = " ∧ ".join(prem + [self.claim(st["claim"], env, negate=True)])
            return self.quant("∃", bs, inner, "∧")
        claim = self.claim(st["claim"], env)
        inner = " → ".join(prem + [claim])
        return self.quant("∀", bs, inner, "→")

    @staticmethod
    def quant(q: str, bs: list, inner: str, conn: str) -> str:
        """q (b1 : T1) .. (bk : Tk), H_k conn q ..: one binder group up to each Reach hypothesis."""
        groups, cur = [], []
        for _, name, ty, hyp in bs:
            cur.append(f"({name} : {ty})")
            if hyp:
                groups.append((cur, hyp))
                cur = []
        out = []
        for g, hyp in groups:
            out.append(f"{q} {' '.join(g)}, {hyp} {conn} ")
        if cur:
            out.append(f"{q} {' '.join(cur)}, ")
        return "".join(out) + inner

    def statements(self, entry: dict, law: dict) -> list[dict]:
        """[{"theorem", "text"}]: a PROVED law's theorem; a REFUTED law's counter-law and refutation."""
        lid = entry["law_id"]
        if entry["status"] == "PROVED":
            return [{"theorem": lid, "text": f"theorem {lid} : {self.body(law)}"}]
        return [{"theorem": f"{lid}_counter", "text": f"theorem {lid}_counter : {self.body(law, counter=True)}"},
                {"theorem": f"{lid}_refuted", "text": f"theorem {lid}_refuted : ¬ ({self.body(law)})"}]


DISCH_NOT_ATTEMPTED = ("not_attempted: rule DISCH over a holon-facts/0.3 document, outside every Lean emitter's model kind "
                       "(I31's laws, merged after the prereg 84c185f; carved out at the move onto be95d6d)")
FACT_NOT_ATTEMPTED = ("not_attempted: rule FACT over a holon-facts/0.3 document, outside every Lean emitter's model kind "
                      "(I26's laws, merged after the prereg; carved out as I31's DISCH laws are: spec/M3/amendments.jsonl)")


def rendered(root: Path = ROOT) -> tuple[list[dict], dict]:
    """Rules L0-L3 over the tree: (the scope, each entry with its frozen statements or the reason it has none; the
    models: {model key: kind, facts, Bend model, Lean model file, parameters, views, sites and interface})."""
    root = Path(root)
    entries, models, derivs = [], {}, {}
    for e in scope(root):
        e = dict(e)
        law = load_json(root / e["law_file"])
        if e["kind"] == "other" and law.get("rule") in ("DISCH", "FACT"):
            # I31's DISCH laws (merged at be95d6d, after the prereg 84c185f) state their claims over a holon-facts/0.3
            # document, which no Lean emitter reads: not attempted, PROVED or REFUTED (the human's answer at the move
            # onto be95d6d). I26's FACT laws (merged later) state theirs over the same document and are carved out the
            # same way (amendment). Any other PROVED law outside the emitters' kinds still raises below.
            e["statements"], e["attempt"] = [], DISCH_NOT_ATTEMPTED if law["rule"] == "DISCH" else FACT_NOT_ATTEMPTED
            entries.append(e)
            continue
        facts = load_json(root / e["facts"])
        params = oracle_params(root, e["facts"]) if e["kind"] == "machine_oracle" else {}
        try:
            r = Render(e["kind"], facts, params)
            e["statements"] = r.statements(e, law)
            e["attempt"] = "lean"
        except Unsupported as x:
            if e["status"] == "PROVED":   # a PROVED law no rule renders would be a hole in the promoted set: refuse
                raise
            e["statements"], e["attempt"] = [], f"unsupported_form: {x}"
            entries.append(e)
            continue
        m = models.setdefault(e["model_key"], {
            "kind": e["kind"], "facts": e["facts"], "facts_sha256": e["facts_sha256"], "bend_model": e["model"],
            "bend_model_sha256": file_sha256(root / e["model"]), "lean_model": e["lean_model"],
            "params": params, "views": set(), "sites": set(), "obligations": {}, "entry_points": {}, "laws": []})
        m["views"] |= r.views
        m["sites"] |= r.sites
        for sid in site_ids(law["statement"], []):   # each site's subtraction, from the law's DERIVATION.json
            dp = (Path(e["law_file"]).parent / "DERIVATION.json").as_posix()
            if dp not in derivs:
                derivs[dp] = {d["basis"]["site_id"]: d for d in load_json(root / dp)["laws"]
                              if (d.get("basis") or {}).get("kind") == "site"}
            m["obligations"][site_name(sid)] = derivs[dp][sid]["basis"]["expr"]
            m["entry_points"][site_name(sid)] = sorted(derivs[dp][sid]["entry_points"])
            m.setdefault("derivation", dp)
        m["laws"].append(e["law_id"])
        entries.append(e)
    for key, m in models.items():
        m["views"], m["sites"] = sorted(m["views"]), sorted(m["sites"])
        m["obligations"] = dict(sorted(m["obligations"].items()))
        m["entry_points"] = dict(sorted(m["entry_points"].items()))
        m["interface"] = interface(m["kind"], load_json(root / m["facts"]), m["params"], m["views"], m["sites"],
                                   m["obligations"])
    return entries, dict(sorted(models.items()))


def stub_text(model: dict, statements: list[dict], check_names: list[str] = ()) -> str:
    """Test-only Lean text (never committed): the interface of one model, its functions as axioms, then the given
    frozen statements with placeholder proofs, then `#check @<name>` for check_names. It elaborates the statements
    against the interface (rule L3's well-typedness) and gives the reference elaborated types (rule L5)."""
    i = model["interface"]
    out = ["set_option autoImplicit false", "set_option maxRecDepth 20000", "", "namespace Model", ""]
    out += [t for _, t in i["types"] for t in (t, "")]
    out += [f"axiom {n} : {ty}" for n, ty in i["signatures"]] + [""]
    out += [t for _, t in i["decls"] for t in (t, "")]
    out += ["end Model", ""]
    for s in statements:
        out += [s["text"] + " := by", "  sorry", ""]
    if check_names:
        out += ["set_option pp.all true"] + [f"#check @{n}" for n in check_names]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------------------------- rule L7: differential
_TOK = re.compile(r"\s*(?:(?P<ctor>[^\s{}\[\](),]*?(?P<cname>[A-Za-z_][A-Za-z0-9_]*)\{)|(?P<num>\d+)(?P<n>n?)|"
                  r"(?P<p>[\[\]{}(),]))")


def parse_bend(out: str):
    """A value as `bend` prints it (BEND_PRIMER §2): constructors Name{..} (a module path before the name is dropped),
    lists [..], Nat literals 5n, U32 literals 5, tuples (a, b). Returns ("C", name, [args]), lists, or ints."""
    s = out.strip()
    pos = 0

    def tok():
        nonlocal pos
        m = _TOK.match(s, pos)
        if not m:
            raise ValueError(f"cannot parse bend output at {pos}: {s[pos:pos + 80]!r}")
        pos = m.end()
        return m

    def value():
        m = tok()
        if m["cname"]:
            args = []
            m2 = _TOK.match(s, pos)
            if m2 and m2["p"] == "}":
                tok()
                return ("C", m["cname"], args)
            while True:
                args.append(value())
                c = tok()
                if c["p"] == "}":
                    return ("C", m["cname"], args)
                if c["p"] != ",":
                    raise ValueError(f"expected , or }} at {pos}")
        if m["num"] is not None:
            return int(m["num"])
        if m["p"] in "[(":
            close = "]" if m["p"] == "[" else ")"
            items = []
            m2 = _TOK.match(s, pos)
            if m2 and m2["p"] == close:
                tok()
                return items if close == "]" else ("T", items)
            while True:
                items.append(value())
                c = tok()
                if c["p"] == close:
                    return items if close == "]" else ("T", items)
                if c["p"] != ",":
                    raise ValueError(f"expected , or {close} at {pos}")
        raise ValueError(f"unexpected {m.group(0)!r} at {pos}")

    v = value()
    if s[pos:].strip():
        raise ValueError(f"trailing output: {s[pos:pos + 80]!r}")
    return v


def _bend_env() -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in ("BUN_OPTIONS", "BEND_LIB", "BEND_HUB") and not k.startswith("BUN_CONFIG_")}
    env["BEND_NO_TELEMETRY"] = "1"   # no daily version check (a network GET)
    return env


def bend_eval(model: Path, ret_type: str, terms: list[str], chunk: int = 150) -> list:
    """Evaluate Bend terms over the compiled model (imported as M) with the pinned bend: a main that returns the list
    of the terms' values, printed and parsed. Every term must have type ret_type."""
    out = []
    for i in range(0, len(terms), chunk):
        part = terms[i:i + chunk]
        tmp = Path(tempfile.mkdtemp(prefix="i43_eval_"))
        try:
            shutil.copyfile(model, tmp / "model.bend")
            body = ",\n    ".join(part)
            (tmp / "Main.bend").write_text(f"import Base\nimport ./model.bend as M\n\n"
                                           f"def main() -> List<&2, {ret_type}>:\n  [\n    {body}\n  ]\n")
            p = subprocess.run(bend_cmd() + ["Main.bend"], cwd=tmp, capture_output=True, text=True,
                               timeout=int(config()["bend"].get("timeout_s", 180)) * 4, env=_bend_env())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        lines = [ln for ln in p.stdout.splitlines() if ln.strip().startswith("[")]
        if p.returncode != 0 or len(lines) != 1:
            raise AssertionError(f"bend could not evaluate {len(part)} terms over {model}: "
                                 f"{(p.stdout + p.stderr)[-2000:]}")
        vals = parse_bend(lines[0])
        if not isinstance(vals, list) or len(vals) != len(part):
            raise AssertionError(f"bend returned {len(vals) if isinstance(vals, list) else vals!r} values for "
                                 f"{len(part)} terms over {model}")
        out += vals
    return out


class MachineSamples:
    """Rule L7 for the machine kinds: sample inputs from the laws and records, Bend terms for them, and the decoding
    of Bend values into JSON (Nat: int; Bool: bool; list: list; record: {field: value}; Obs: "ok" or {"rev": code};
    St: {field: value})."""

    def __init__(self, kind: str, facts: dict, params: dict):
        self.kind, self.f, self.params = kind, facts, params
        self.records = facts.get("types", {})
        self.actions = {a["name"]: a for a in facts["actions"]}
        self.state = [(s[0], s[1]) for s in facts["state"]]

    # inputs as Bend literals
    def bv(self, t: str, v) -> str:
        if t == "Nat":
            return f"{int(v)}n"
        if t == "Bool":
            return "True{}" if v else "False{}"
        if t == "Obs":
            return "M.O_Ok{}" if v == "ok" else f"M.O_Rev{{{int(v['rev'])}n}}"
        m = re.fullmatch(r"List<(.+)>", t)
        if m:
            return "[" + ", ".join(self.bv(m.group(1), x) for x in v) + "]" if v else "Nil{}"
        if t in self.records:
            return f"M.H{t}{{" + ", ".join(self.bv(ft, v[fn]) for fn, ft in self.records[t]["fields"]) + "}"
        raise Unsupported(f"type {t}")

    def act(self, a: dict) -> str:
        d = self.actions[a["op"]]
        args = ", ".join(self.bv(t, a[n]) for n, t in d["inputs"])
        return f"M.A_{a['op']}{{{args}}}"

    def trace(self, tr: list) -> str:
        return "[" + ", ".join(self.act(a) for a in tr) + "]" if tr else "Nil{}"

    def st(self, s: dict) -> str:
        return "M.HSt{" + ", ".join(self.bv(t, s[n]) for n, t in self.state) + "}"

    # decoding
    def dec(self, t: str, v):
        if t == "Nat":
            return int(v)
        if t == "Bool":
            if v not in (("C", "True", []), ("C", "False", [])):
                raise AssertionError(f"not a Bool: {v!r}")
            return v[1] == "True"
        if t == "Obs":
            if v[1] == "O_Ok":
                return "ok"
            return {"rev": int(v[2][0])}
        m = re.fullmatch(r"List<(.+)>", t)
        if m:
            return [self.dec(m.group(1), x) for x in v]
        if t in self.records:
            return {fn: self.dec(ft, x) for (fn, ft), x in zip(self.records[t]["fields"], v[2])}
        if t == "State":
            return {n: self.dec(tt, x) for (n, tt), x in zip(self.state, v[2])}
        raise Unsupported(f"type {t}")


def _ir_act(t: dict) -> dict | None:
    """An IR action term with literal arguments, in the records' witness form {"op": name, input: value}."""
    if set(t) != {"act", "args"}:
        return None
    out = {"op": t["act"]}
    for n, x in t["args"].items():
        if set(x) == {"nat"}:
            out[n] = int(x["nat"])
        elif set(x) == {"bool"}:
            out[n] = bool(x["bool"])
        elif set(x) == {"nats"}:
            out[n] = [int(y) for y in x["nats"]]
        else:
            return None
    return out


def _ir_traces(e, out: list) -> list:
    """Every trace literal of an IR statement whose actions all have literal arguments."""
    if isinstance(e, dict):
        if set(e) == {"trace"}:
            acts = [_ir_act(a) for a in e["trace"]]
            if all(a is not None for a in acts):
                out.append(acts)
        for v in e.values():
            _ir_traces(v, out)
    elif isinstance(e, list):
        for x in e:
            _ir_traces(x, out)
    return out


def _witness_values(law: dict, w: dict | None) -> tuple[list, list, list]:
    """(traces, actions, state runs) among a witness's binder values, by the binders' IR types."""
    trs, acts, runs = [], [], []
    if not isinstance(w, dict):
        return trs, acts, runs
    types = {b["name"]: b["type"] for b in law["statement"]["binders"]}
    for n, v in w.items():
        t = types.get(n)
        if t == "Trace" and isinstance(v, list):
            trs.append(v)
        elif t == "Act" and isinstance(v, dict) and "op" in v:
            acts.append(v)
        elif t in ("State", "Reach") and isinstance(v, dict) and isinstance(v.get("run"), list):
            runs.append(v["run"])
    return trs, acts, runs


def _default_act(d: dict) -> dict:
    out = {"op": d["name"]}
    for n, t in d["inputs"]:
        out[n] = {"Nat": 1, "Bool": False, "List<Nat>": [1]}.get(t, None)
        if out[n] is None:
            raise Unsupported(f"default input of type {t}")
    return out


NAT_PROBES = (0, 1, 2, 3, 4, 100)   # rule L7: the values a raw obligation's Nat variable takes when it is no state field


def _perturb(s: dict, state: list) -> dict:
    """Rule L7's perturbed state: every top-level Nat field plus one (an unreachable neighbour of a sample state)."""
    return {n: (v + 1 if t == "Nat" else v) for (n, t), v in zip(state, [s[n] for n, _ in state])}


def _dedup(xs: list) -> list:
    seen, out = set(), []
    for x in xs:
        k = canonical(x)
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def machine_differential(root: Path, key: str, model: dict, entries: list[dict]) -> dict:
    """Rule L7 (machine kinds). The laws read: every attempted law of this model and, since the first review fold,
    every attempted law over the same facts document (so the M1 laws' traces feed M2's instrumented model). Inputs:
    the traces T (the empty trace; every literal trace of a law's IR; every Trace value and every State/Reach run of
    its record's witness, of its non-vacuity witness and of each entry of its record's "witnesses" map (the REFUTED
    site laws' per-entry-point witnesses); each literal trace of a law followed by each witness trace of that law),
    the actions A (every action of T and every Act value of those witnesses), one representative per action
    constructor R (the first of A in canonical order, or the constructor with every Nat input 1, Bool input false and
    List<Nat> input [1]), the sample states S (the end state of each literal trace, of each witness trace and of each
    witness run, each also perturbed: every top-level Nat field plus one) and, for a model with an oracle parameter,
    the tables T0 (empty) and T1 (the union of the tables the non-vacuity witnesses of its own laws name, first value
    per key, keys sorted). Values: for each trace of T: run (from s0; under T1, and also T0), obs, fn_runs_ok,
    fn_cost, fn_elapsed, fn_last_ok and every observer and migration (Nat inputs 1) at its end state, fn_no_code of
    its log at code 1 and at every code the log holds; for each state of S and action of R: step; for each action of
    A: fn_perm, every fn_is_<a> and every consumer; for each site predicate and each action of R and of its own site
    law's witnesses: the site and its hit predicate under T1, at every state of S when the action's constructor is
    one of the site's entry points (DERIVATION.json), else at the first state of S; for each site's raw obligation
    ro_<x> (obligation_vars): its value at every combination of its free variables' values, a variable named like a
    state field of its type taking that field's value in each state of S, any other Nat variable each of
    NAT_PROBES (combinations deduplicated, in canonical order)."""
    root = Path(root)
    facts = load_json(root / model["facts"])
    ms = MachineSamples(model["kind"], facts, model["params"])
    if len(model["params"]) > 1:
        raise Unsupported("more than one oracle parameter")
    pname = next(iter(model["params"]), None)
    lit, wtr, acts, runs, tables, site_acts = [], [], [], [], [], {}
    for e in entries:
        if e["attempt"] != "lean":
            continue
        own = e.get("model_key") == key
        if not own and e["facts"] != model["facts"]:   # the laws over the same facts document feed its traces too
            continue
        law, rec = load_json(root / e["law_file"]), load_json(root / e["record"])
        ws = [rec.get("witness"), (rec.get("non_vacuity") or {}).get("witness")]
        ws += [v.get("witness") for _, v in sorted((rec.get("witnesses") or {}).items()) if isinstance(v, dict)]
        P = _ir_traces(law["statement"], [])
        lit += P
        W = []
        for w in ws:
            t, a, r = _witness_values(law, w)
            W += t
            acts += a
            runs += r
            if own and pname and isinstance(w, dict) and isinstance(w.get(pname), dict) and "table" in w[pname]:
                tables += [tuple(map(canonical, kv)) for kv in w[pname]["table"]]
            if own and e["rule"] == "SORT":
                site_acts.setdefault(e["law_id"], []).extend(a)
        wtr += W
        lit_w = [p + w for p in P for w in W]
        wtr += lit_w
    srcs = _dedup(lit + runs + wtr)
    T = sorted(_dedup([[]] + lit + wtr + runs), key=lambda tr: (len(tr), canonical(tr)))
    A = sorted(_dedup([a for tr in T for a in tr] + acts), key=canonical)
    R = []
    for d in facts["actions"]:
        R.append(next((a for a in A if a["op"] == d["name"]), None) or _default_act(d))
    A = sorted(_dedup(A + R), key=canonical)
    t_idx = {canonical(tr): i for i, tr in enumerate(T)}
    a_idx = {canonical(a): i for i, a in enumerate(A)}
    sig = dict(model["interface"]["signatures"])
    model_path = root / model["bend_model"]
    tabs = {}
    if pname:
        seen = {}
        for k, v in tables:
            seen.setdefault(k, v)
        tabs = {"T0": [], "T1": [[json.loads(k), json.loads(v)] for k, v in sorted(seen.items())]}

    def btab(name: str) -> str:
        rows = tabs[name]
        return "[" + ", ".join(f"M.HO_{pname}{{{ms.bv('List<Nat>', k)}, {int(v)}n}}" for k, v in rows) + "]" \
            if rows else "Nil{}"

    def targ(name: str) -> str:
        return f", {btab(name)}" if pname else ""

    samples = []
    tbl = "T1" if pname else None
    tab_arg = [{"table": tbl}] if pname else []

    # phase 1: runs from s0 (and the state values S is built from)
    run_terms = [f"M.run({ms.trace(tr)}, M.s0(){targ('T1')})" for tr in T]
    ends = [ms.dec("State", v) for v in bend_eval(model_path, "M.HSt", run_terms)]
    for i, v in enumerate(ends):
        samples.append({"fn": "run", "args": tab_arg + [{"trace": i}, {"s0": True}], "value": v})
    if pname:
        vs = bend_eval(model_path, "M.HSt", [f"M.run({ms.trace(tr)}, M.s0(){targ('T0')})" for tr in T])
        for i, v in enumerate(vs):
            samples.append({"fn": "run", "args": [{"table": "T0"}, {"trace": i}, {"s0": True}],
                            "value": ms.dec("State", v)})
    logs = [ms.dec("List<Obs>", v) for v in
            bend_eval(model_path, "List<&2, M.HObs>", [f"M.obs({ms.trace(tr)}, M.s0(){targ('T1')})" for tr in T])]
    for i, v in enumerate(logs):
        samples.append({"fn": "obs", "args": tab_arg + [{"trace": i}, {"s0": True}], "value": v})
    states = []
    for tr in srcs:
        states.append({"run": t_idx[canonical(tr)]})
    for tr in srcs:
        states.append({"lit": _perturb(ends[t_idx[canonical(tr)]], ms.state)})
    states = _dedup(states)

    def sterm(s: dict) -> str:
        return f"M.run({ms.trace(T[s['run']])}, M.s0(){targ('T1')})" if "run" in s else ms.st(s["lit"])

    # phase 2: every other value, grouped by Bend result type
    jobs: dict[str, list] = {}

    def add(rt: str, dec_t: str, fn: str, args: list, term: str):
        jobs.setdefault(rt, []).append((dec_t, fn, args, term))

    for i, tr in enumerate(T):
        add("Bool", "Bool", "fn_runs_ok", tab_arg + [{"trace": i}, {"s0": True}],
            f"M.runs_ok({ms.trace(tr)}, M.s0(){targ('T1')})")
        if "fn_cost" in sig:
            add("Nat", "Nat", "fn_cost", [{"trace": i}], f"M.cost({ms.trace(tr)})")
        if "fn_elapsed" in sig:
            add("Nat", "Nat", "fn_elapsed", [{"trace": i}], f"M.elapsed({ms.trace(tr)})")
        end = f"M.run({ms.trace(tr)}, M.s0(){targ('T1')})"
        add("Bool", "Bool", "fn_last_ok", [{"run_end": i}], f"M.last_ok({end})")
        for o, od in facts.get("observers", {}).items():
            par = sig[f"ob_{o}"].startswith("(")
            bt = {"Nat": "Nat", "Bool": "Bool", "List<Nat>": "List<&2, Nat>"}.get(od["type"])
            if bt is None:
                raise Unsupported(f"observer type {od['type']}")
            add(bt, od["type"], f"ob_{o}", (tab_arg if par else []) + [{"run_end": i}],
                f"M.{o}({end}{targ('T1') if par else ''})")
        for mg, md in facts.get("migrations", {}).items():
            par = sig[f"mig_{mg}"].startswith("(")
            ins = md.get("inputs", [])
            if any(t != "Nat" for _, t in ins):
                raise Unsupported(f"migration {mg} inputs")
            add("M.HSt", "State", f"mig_{mg}", (tab_arg if par else []) + [{"run_end": i}] + [{"nat": 1}] * len(ins),
                f"M.mig_{mg}({', '.join([end] + ['1n'] * len(ins))}{targ('T1') if par else ''})")
        codes = sorted({1} | {o["rev"] for o in logs[i] if o != "ok"})
        for k in codes:
            add("Bool", "Bool", "fn_no_code", [{"log": logs[i]}, {"nat": k}],
                f"M.no_code({ms.bv('List<Obs>', logs[i])}, {k}n)")
    for j, s in enumerate(states):
        for a in R:
            add("M.HSt", "State", "step", tab_arg + [{"act": a_idx[canonical(a)]}, {"state": j}],
                f"M.step({ms.act(a)}, {sterm(s)}{targ('T1')})")
    for i, a in enumerate(A):
        add("Bool", "Bool", "fn_perm", [{"act": i}], f"M.perm({ms.act(a)})")
        for d in facts["actions"]:
            add("Bool", "Bool", f"fn_is_{d['name']}", [{"act": i}], f"M.is_{d['name']}({ms.act(a)})")
        for c in facts.get("consumers", {}):
            add("List<&2, Nat>", "List<Nat>", f"fn_{c}", [{"act": i}], f"M.{c}({ms.act(a)})")
    for sname in model["sites"]:
        lid = "L_sort_" + sname
        sa = sorted(_dedup(R + site_acts.get(lid, [])), key=canonical)
        hname = "hit_" + sname[len("site_"):]
        entry = set(model["entry_points"][sname])
        for j, s in enumerate(states):
            for a in sa:
                if a["op"] not in entry and j > 0:   # an action that is no entry point: at the first state only
                    continue
                for fn in (sname, hname):
                    add("Bool", "Bool", fn, tab_arg + [{"act": a_idx[canonical(a)]}, {"state": j}],
                        f"M.{fn}({ms.act(a)}, {sterm(s)}{targ('T1')})")
    svals = [ends[s["run"]] if "run" in s else s["lit"] for s in states]
    fields = dict(ms.state)
    for sname, ex in model.get("obligations", {}).items():   # the raw obligations ro_<x> (review M1)
        if _reaches_param(ex, facts, model["params"]):
            raise Unsupported(f"the obligation of {sname} reaches an oracle parameter")
        vs = obligation_vars(ex, facts)
        tuples = []
        for sv in svals:
            choices = []
            for n, ty in vs:
                if fields.get(n) == ty:
                    choices.append([sv[n]])
                elif ty == "Nat":
                    choices.append(list(NAT_PROBES))
                else:
                    raise Unsupported(f"obligation variable {n} : {ty} of {sname} is no state field")
            combos = [[]]
            for c in choices:
                combos = [x + [y] for x in combos for y in c]
            tuples += combos
        for tup in sorted(_dedup(tuples), key=canonical):
            env = {n: ms.bv(ty, v) for (n, ty), v in zip(vs, tup)}
            add("Bool", "Bool", ro_name(sname), [{"val": [ty, v]} for (_, ty), v in zip(vs, tup)],
                bend_obligation(ex, env))
    for rt in sorted(jobs):
        js = jobs[rt]
        vals = bend_eval(model_path, rt, [j[3] for j in js])
        for (dec_t, fn, args, _), v in zip(js, vals):
            samples.append({"fn": fn, "args": args, "value": ms.dec(dec_t, v)})
    out = {"traces": T, "actions": A, "states": states, "samples": samples}
    if pname:
        out["tables"] = tabs
        out["parameter"] = pname
    return out


def _stream(label: str, n: int) -> list[int]:
    """n deterministic pseudo-random bytes (sha256 of label:i, concatenated): rule L7's seeded samples."""
    out, i = [], 0
    while len(out) < n:
        out += list(hashlib.sha256(f"{label}:{i}".encode()).digest())
        i += 1
    return out[:n]


def linked_differential(root: Path, key: str, model: dict, entries: list[dict]) -> dict:
    """Rule L7 (linked kind). Records, per record carrier C (cells in field order): all 0x00, all 0xff, two seeded
    ones (_stream("C:<cid>:<i>")); for a carrier an encoder dispatches on (several layouts, keyed by version, whose
    cell at the document's tag_index is a field cell of C): the all-0x00 and the first seeded record with that tag
    cell set to each layout version, to the largest plus one and to 255; and every C-typed witness value of the
    attempted laws' records. Byte strings: the empty one; for each first byte v in 0, 1, 2, 3, 255 and each length
    1, 248, 249, 250, 256, 257, 258: v followed by seeded bytes (_stream("B:<v>:<n>")); two strings of length 249 and
    257 whose cell 5 is undefined (57005) and one whose cell 0 is; and every Bytes-typed witness value. Values: every
    encoder on every record of its carrier; every decoder, predicate, loader and loader condition (c_ok_<loader>) on
    every byte string. A Bend cell 57005 is a Lean `none`."""
    root = Path(root)
    facts = load_json(root / model["facts"])
    carriers = {cid: c for cid, c in facts["carriers"].items() if c["kind"] == "record"}
    width = {cid: sum(f["width"] for f in c["fields"]) for cid, c in carriers.items()}
    tag = facts.get("tag_index")
    recs: dict[str, list] = {}
    for cid, c in carriers.items():
        w = width[cid]
        rs = [[0] * w, [255] * w, _stream(f"C:{cid}:0", w), _stream(f"C:{cid}:1", w)]
        for n, f in facts["functions"].items():
            lays = f.get("layouts") or {}
            if f["kind"] != "encoder" or f["from"] != cid or len(lays) < 2 or tag is None:
                continue
            cells = {canonical(lay[tag]) for lay in lays.values() if len(lay) > tag}
            if len(cells) != 1:
                continue
            cell = json.loads(cells.pop())
            if cell[0] != "field":
                continue
            pos, k = 0, None
            for fld in c["fields"]:
                if fld["name"] == cell[1]:
                    k = pos + cell[2]
                pos += fld["width"]
            vs = sorted(int(v) for v in lays)
            for base in (rs[0], rs[2]):
                for v in vs + [vs[-1] + 1, 255]:
                    r = list(base)
                    r[k] = v
                    rs.append(r)
        recs[cid] = rs
    strs = [[]]
    for v in (0, 1, 2, 3, 255):
        for n in (1, 248, 249, 250, 256, 257, 258):
            strs.append([v] + _stream(f"B:{v}:{n}", n - 1))
    for n in (249, 257):
        s = [0] + _stream(f"U:{n}", n - 1)
        s[5] = UNDEF
        strs.append(s)
    strs.append([UNDEF] + _stream("U:0", 248))
    for e in entries:
        if e.get("model_key") != key or e["attempt"] != "lean":
            continue
        law, rec = load_json(root / e["law_file"]), load_json(root / e["record"])
        types = {b["name"]: b["type"] for b in law["statement"]["binders"]}
        w = rec.get("witness") or {}
        for n, v in sorted(w.items()) if isinstance(w, dict) else []:
            t = types.get(n)
            if t == "Bytes" and isinstance(v, str):
                strs.append(list(bytes.fromhex(v[2:])))
            elif t in carriers and isinstance(v, dict):
                cells = []
                for fld in carriers[t]["fields"]:
                    hx = v[fld["name"]]
                    cells += list(bytes.fromhex(hx[2:]))
                recs[t].append(cells)
    recs = {cid: _dedup(rs) for cid, rs in recs.items()}
    strs = _dedup(strs)
    model_path = root / model["bend_model"]

    def blist(xs: list[int]) -> str:
        return "[" + ", ".join(str(x) for x in xs) + "]" if xs else "Nil{}"

    def dmaybe(v):
        if v == ("C", "None", []):
            return None
        if isinstance(v, tuple) and v[1] == "Some":
            return list(v[2][0])
        raise AssertionError(f"not a Maybe: {v!r}")

    samples = []
    enc = [(n, f) for n, f in facts["functions"].items() if f["kind"] == "encoder"]
    jobs = [("List<&2, U32>", list, n, [{"record": [f["from"], i]}], f"M.{n}(M.R_{f['from']}{{"
             + ", ".join(map(str, recs[f["from"]][i])) + "})") for n, f in enc for i in range(len(recs[f["from"]]))]
    for n, f in facts["functions"].items():
        for j, s in enumerate(strs):
            if f["kind"] in ("decoder", "loader"):
                jobs.append(("Maybe<&2, List<&2, U32>>", dmaybe, n, [{"bytes": j}], f"M.{n}({blist(s)})"))
            if f["kind"] == "predicate":
                jobs.append(("Bool", None, n, [{"bytes": j}], f"M.{n}({blist(s)})"))
            if f["kind"] == "loader":
                jobs.append(("Bool", None, f"ok_{n}", [{"bytes": j}], f"M.ok_{n}({blist(s)})"))
    by_rt: dict[str, list] = {}
    for j in jobs:
        by_rt.setdefault(j[0], []).append(j)
    for rt in sorted(by_rt):
        js = by_rt[rt]
        vals = bend_eval(model_path, rt, [j[4] for j in js], chunk=60)
        for (_, conv, n, args, _), v in zip(js, vals):
            if conv is None:
                val = v[1] == "True"
            elif conv is list:
                val = list(v)
            else:
                val = conv(v)
            samples.append({"fn": f"c_{n}", "args": args, "value": val})
    return {"records": {cid: [bytes([x for x in r]).hex() for r in rs] for cid, rs in recs.items()},
            "strings": [[x for x in s] for s in strs], "samples": samples}


# ---------------------------------------------------------------------------------------------- rule L7, Lean side
class LeanValues:
    """Lean literals for rule L7's samples over the model interface (names qualified Model.<name>)."""

    def __init__(self, kind: str, facts: dict):
        self.kind, self.f = kind, facts
        if kind == "linked":
            self.carriers = {cid: c for cid, c in facts["carriers"].items() if c["kind"] == "record"}
        else:
            self.records = facts.get("types", {})
            self.actions = {a["name"]: a for a in facts["actions"]}
            self.state = [(s[0], s[1]) for s in facts["state"]]

    def lty(self, t: str) -> str:
        if t in ("Nat", "Bool"):
            return t
        if t == "Obs":
            return "Model.Obs"
        m = re.fullmatch(r"List<(.+)>", t)
        if m:
            inner = self.lty(m.group(1))
            return f"List {inner}" if " " not in inner else f"List ({inner})"
        if t in self.records:
            return f"Model.T_{t}"
        if t == "State":
            return "Model.St"
        raise Unsupported(f"type {t}")

    def val(self, t: str, v) -> str:
        if t == "Nat":
            return str(int(v))
        if t == "Bool":
            return "true" if v else "false"
        if t == "Obs":
            return "Model.Obs.ok" if v == "ok" else f"(Model.Obs.rev {int(v['rev'])})"
        m = re.fullmatch(r"List<(.+)>", t)
        if m:
            return "[" + ", ".join(self.val(m.group(1), x) for x in v) + "]" if v else f"([] : {self.lty(t)})"
        if t in self.records:
            return "({ " + ", ".join(f"f_{fn} := {self.val(ft, v[fn])}" for fn, ft in self.records[t]["fields"]) + \
                f" }} : Model.T_{t})"
        if t == "State":
            return "({ " + ", ".join(f"f_{n} := {self.val(tt, v[n])}" for n, tt in self.state) + " } : Model.St)"
        raise Unsupported(f"type {t}")

    def act(self, a: dict) -> str:
        d = self.actions[a["op"]]
        args = "".join(" " + self.val(t, a[n]) for n, t in d["inputs"])
        return f"(Model.Act.a_{a['op']}{args})" if args else f"Model.Act.a_{a['op']}"

    def cells(self, xs: list[int]) -> str:
        return "([" + ", ".join("none" if x == UNDEF else f"some 0x{x:02x}" for x in xs) + "] : Model.Bytes)"


def diff_lean(model: dict, facts: dict, proof: str = "by decide") -> tuple[str, list[str]]:
    """Rule L7's Lean side: (the definitions of the sample inputs, each a noncomputable def, and the sample theorems),
    to append to a Lean model of the interface. Each sample is one theorem `Model.<fn> <args> = <value>`, which the
    test proves `by decide`."""
    kind, d = model["kind"], model["differential"]
    lv = LeanValues(kind, facts)
    sig = dict(model["interface"]["signatures"])
    out, thms = [], []
    if kind == "linked":
        for cid, rs in d["records"].items():
            c = lv.carriers[cid]
            names = [f"f_{f['name'].replace('.', '__')}_{k}" for f in c["fields"] for k in range(f["width"])]
            for i, hx in enumerate(rs):
                bs = bytes.fromhex(hx)
                body = ", ".join(f"{n} := 0x{b:02x}" for n, b in zip(names, bs))
                out.append(f"noncomputable def holonRec_{cid}_{i} : Model.R_{cid} := {{ {body} }}")
        for j, s in enumerate(d["strings"]):
            out.append(f"noncomputable def holonBytes{j} : Model.Bytes := {lv.cells(s)}")

        def arg(a):
            if "record" in a:
                return f"holonRec_{a['record'][0]}_{a['record'][1]}"
            return f"holonBytes{a['bytes']}"

        for k, s in enumerate(d["samples"]):
            ret = sig[s["fn"]].rsplit("→", 1)[1].strip()
            v = s["value"]
            if ret == "Bytes":
                val = lv.cells(v)
            elif ret == "Option Bytes":
                val = "(none : Option Model.Bytes)" if v is None else f"(some {lv.cells(v)})"
            else:
                val = "true" if v else "false"
            thms.append(f"theorem holon_diff_{k} : Model.{s['fn']} {' '.join(arg(a) for a in s['args'])} = {val} := "
                        f"{proof}")
        return "\n\n".join(out) + "\n", thms
    pname = d.get("parameter")
    if pname:
        out.append("noncomputable def holonTable : List (List Nat × Nat) → List Nat → Nat\n  | [], _ => 0\n"
                   "  | (k, v) :: t, x => if x = k then v else holonTable t x")
        for tn, rows in sorted(d["tables"].items()):
            rs = ", ".join(f"({lv.val('List<Nat>', k)}, {int(v)})" for k, v in rows)
            out.append(f"noncomputable def holon{tn} : List Nat → Nat := holonTable [{rs}]")
    for i, tr in enumerate(d["traces"]):
        body = "[" + ", ".join(lv.act(a) for a in tr) + "]" if tr else "[]"
        out.append(f"noncomputable def holonTr{i} : List Model.Act := {body}")
    for i, a in enumerate(d["actions"]):
        out.append(f"noncomputable def holonAct{i} : Model.Act := {lv.act(a)}")
    t1 = " holonT1" if pname else ""
    for j, s in enumerate(d["states"]):
        body = f"Model.run{t1} holonTr{s['run']} Model.s0" if "run" in s else lv.val("State", s["lit"])
        out.append(f"noncomputable def holonSt{j} : Model.St := {body}")
    ret_ir = {"Bool": "Bool", "Nat": "Nat", "St": "State", "List Nat": "List<Nat>", "List Obs": "List<Obs>"}

    def arg(a):
        if "table" in a:
            return f"holon{a['table']}"
        if "trace" in a:
            return f"holonTr{a['trace']}"
        if "s0" in a:
            return "Model.s0"
        if "run_end" in a:
            return f"(Model.run{t1} holonTr{a['run_end']} Model.s0)"
        if "state" in a:
            return f"holonSt{a['state']}"
        if "act" in a:
            return f"holonAct{a['act']}"
        if "nat" in a:
            return str(int(a["nat"]))
        if "log" in a:
            return lv.val("List<Obs>", a["log"])
        if "val" in a:
            return lv.val(a["val"][0], a["val"][1])
        raise Unsupported(f"argument {a}")

    for k, s in enumerate(d["samples"]):
        ret = ret_ir[sig[s["fn"]].rsplit("→", 1)[1].strip()]
        thms.append(f"theorem holon_diff_{k} : Model.{s['fn']} {' '.join(arg(a) for a in s['args'])} = "
                    f"{lv.val(ret, s['value'])} := {proof}")
    return "\n\n".join(out) + "\n", thms


# ---------------------------------------------------------------------------------------------- L7, L9: evidence
def action_successes(model: dict, facts: dict) -> dict[str, int]:
    """Rule L7 (machine kinds; review M1): per action constructor, how many samples show an action of it succeeding:
    an "ok" at its position in the log of a sample trace run from s0 (the obs samples; under T1 when the model has an
    oracle parameter), or a step sample whose result's log is the sample state's log followed by "ok"."""
    d = model["differential"]
    if not any(s[0] == "log" for s in facts["state"]):
        raise Unsupported("a machine model without a log field")
    out = {a["name"]: 0 for a in facts["actions"]}
    runs = {}
    for s in d["samples"]:
        if s["fn"] == "run" and not any(a.get("table") == "T0" for a in s["args"]):
            runs[next(a["trace"] for a in s["args"] if "trace" in a)] = s["value"]
        if s["fn"] == "obs":
            i = next(a["trace"] for a in s["args"] if "trace" in a)
            for a, o in zip(d["traces"][i], s["value"]):
                out[a["op"]] += o == "ok"
    for s in d["samples"]:
        if s["fn"] == "step":
            a = d["actions"][next(x["act"] for x in s["args"] if "act" in x)]
            st = d["states"][next(x["state"] for x in s["args"] if "state" in x)]
            before = runs[st["run"]]["log"] if "run" in st else st["lit"]["log"]
            out[a["op"]] += s["value"]["log"] == before + ["ok"]
    return out


def site_coverage(model: dict) -> dict[str, dict]:
    """Rule L7 (review M1): per site predicate of a model, the values its site, hit and raw-obligation samples take."""
    d = model["differential"]
    out = {}
    for sname in model.get("sites", []):
        x = sname[len("site_"):]
        vals = {k: sorted({s["value"] for s in d["samples"] if s["fn"] == f"{k}_{x}"}) for k in ("site", "hit", "ro")}
        out[sname] = vals
    return out


def _bend_machine_term(t: dict, env: dict, ms: "MachineSamples") -> str:
    """A Bend term (the compiled model imported as M) for an IR term over a machine model without oracle parameters,
    each bound variable replaced by env's Bend literal (rule L9's evidence)."""
    def go(x: dict) -> str:
        if "var" in x:
            return env[x["var"]]
        if set(x) == {"nat"}:
            return f"{int(x['nat'])}n"
        if set(x) == {"s0"}:
            return "M.s0()"
        if set(x) == {"run", "from"}:
            return f"M.run({go(x['run'])}, {go(x['from'])})"
        if set(x) == {"step", "from"}:
            return f"M.step({go(x['step'])}, {go(x['from'])})"
        if set(x) == {"trace"}:
            return "[" + ", ".join(go(a) for a in x["trace"]) + "]" if x["trace"] else "Nil{}"
        if set(x) == {"act", "args"}:
            a = _ir_act(x)
            if a is None:
                raise Unsupported("an action term with non-literal arguments")
            return ms.act(a)
        if set(x) == {"obsv", "of"}:
            return f"M.{x['obsv']}({go(x['of'])})"
        if set(x) == {"fn", "args"}:
            return f"M.{x['fn']}(" + ", ".join(go(a) for a in x["args"]) + ")"
        raise Unsupported(f"term {sorted(x)}")
    return go(t)


def _claim_props(claim: dict) -> list[dict]:
    return list(claim["all"]) if set(claim) == {"all"} else [claim]


def _nat_canary(root: Path, e: dict, model: dict) -> dict | None:
    """Rule L9's perturb canary for a machine law (review B3): the first Nat equation of the claim (its propositions
    in order: the claim itself, or the members of its "all" list in order; the first "eq" whose right side is a Nat
    literal {"nat": k} and whose left side renders as a Nat term) with k replaced by k + 1; evidence: the compiled
    Bend model evaluates the left side to k at the record's witness (review 2, m7: this shows the perturbed claim
    false at that witness, not the perturbed existential false; the canary keeps the law's proof, which fixes the
    witness)."""
    law, rec = load_json(root / e["law_file"]), load_json(root / e["record"])
    facts = load_json(root / e["facts"])
    r = Render(e["kind"], facts, model["params"])
    _, env = r.binders(law)
    props = _claim_props(law["statement"]["claim"])
    for i, p in enumerate(props):
        if set(p) != {"eq"} or set(p["eq"][1]) != {"nat"}:
            continue
        if r.term(p["eq"][0], env)[1] != "Nat":
            continue
        k = int(p["eq"][1]["nat"])
        pert = json.loads(json.dumps(law))
        pprops = _claim_props(pert["statement"]["claim"])
        pprops[i]["eq"][1] = {"nat": k + 1}
        if set(law["statement"]["claim"]) == {"all"}:
            pert["statement"]["claim"] = {"all": pprops}
        else:
            pert["statement"]["claim"] = pprops[0]
        text = Render(e["kind"], facts, model["params"]).statements(e, pert)[0]["text"]
        w = rec.get("witness")
        if not isinstance(w, dict):
            return None
        ms = MachineSamples(e["kind"], facts, model["params"])
        types = {b["name"]: b["type"] for b in law["statement"]["binders"]}
        benv = {}
        for n, v in w.items():
            if types.get(n) != "Trace":
                return None
            benv[n] = ms.trace(v)
        term = _bend_machine_term(p["eq"][0], benv, ms)
        val = bend_eval(root / e["model"], "Nat", [term])[0]
        if val == k + 1 or val != k:
            return None
        return {"law": e["law_id"], "dir": e["dir"], "lean_source": e["lean_source"], "theorem": e["theorem"],
                "kind": "nat_plus_one", "proposition": i, "from": k, "to": k + 1, "text": text,
                "evidence": {"witness": w, "bend_term": term, "value": val}}
    return None


def _swap_canary(root: Path, e: dict, model: dict) -> dict | None:
    """Rule L9's perturb canary for a linked PAR round trip without premise (claim dec(enc(v)) = some <field F of v>):
    the first two cells of the claim's right side swapped; evidence: on the first seeded record of the binder's carrier
    (the differential's records, in order) whose two cells differ, the compiled Bend model evaluates the left side to
    the unswapped cells, so the swapped claim is false there."""
    law = load_json(root / e["law_file"])
    st = law["statement"]
    if st.get("assume") or set(st["claim"]) != {"eq"} or len(st["binders"]) != 1:
        return None
    lhs, rhs = st["claim"]["eq"]
    if set(rhs) != {"some"} or set(rhs["some"]) != {"field", "of"} or rhs["some"]["of"] != {"var": st["binders"][0]["name"]}:
        return None
    if not (set(lhs) == {"call", "args"} and len(lhs["args"]) == 1 and set(lhs["args"][0]) == {"call", "args"}
            and lhs["args"][0]["args"] == [{"var": st["binders"][0]["name"]}]):
        return None
    facts = load_json(root / e["facts"])
    cid = st["binders"][0]["type"]
    c = facts["carriers"][cid]
    off, fld = 0, None
    for f in c["fields"]:
        if f["name"] == rhs["some"]["field"]:
            fld = f
            break
        off += f["width"]
    if fld is None or fld["width"] < 2:
        return None
    v = f"v_{st['binders'][0]['name']}"
    g = fld["name"].replace(".", "__")
    cells = [f"some {v}.f_{g}_{k}" for k in range(fld["width"])]
    orig, swapped = ", ".join(cells), ", ".join([cells[1], cells[0]] + cells[2:])
    text = e["statements"][0]["text"]
    if text.count(orig) != 1:
        return None
    recs = [list(bytes.fromhex(h)) for h in model["differential"]["records"][cid]]
    for rec_cells in recs:
        if rec_cells[off] == rec_cells[off + 1]:
            continue
        term = (f"M.{lhs['call']}(M.{lhs['args'][0]['call']}(M.R_{cid}{{" + ", ".join(map(str, rec_cells)) + "}))")
        val = bend_eval(root / e["model"], "Maybe<&2, List<&2, U32>>", [term], chunk=1)[0]
        if not (isinstance(val, tuple) and val[1] == "Some"):
            return None
        got = list(val[2][0])
        want = rec_cells[off:off + fld["width"]]
        if got != want:
            return None
        return {"law": e["law_id"], "dir": e["dir"], "lean_source": e["lean_source"], "theorem": e["theorem"],
                "kind": "swap_first_two_cells", "field": fld["name"], "text": text.replace(orig, swapped),
                "evidence": {"record": bytes(rec_cells).hex(), "bend_term": term, "value": got,
                             "swapped": [want[1], want[0]] + want[2:]}}
    return None


CANARY_GATES = (("M1", ("M1",)), ("M2", ("M2", "M2/extracted_m1")), ("M3", ("M3",)))


def perturb_canaries(root: Path, entries: list[dict], models: dict) -> dict:
    """Rule L9's perturb canary per milestone gate (review B3): among the gate's directories in order (M1: results/M1;
    M2: results/M2, then results/M2/extracted_m1; M3: results/M3), the PROVED attempted laws in law-id order, the first
    that has one: a law of Bend class evaluate (_nat_canary), or a PAR round trip without premise (_swap_canary)."""
    root = Path(root)
    out = {}
    for gate, dkeys in CANARY_GATES:
        found = None
        for dk in dkeys:
            for e in sorted((x for x in entries if x["dir"] == dk and x["status"] == "PROVED" and x["attempt"] == "lean"),
                            key=lambda x: x["law_id"]):
                model = models[e["model_key"]]
                if e["proof_class"] == "evaluate" and model["kind"] in ("machine",) and not model["params"]:
                    found = _nat_canary(root, e, model)
                elif model["kind"] == "linked" and e["subform"] == "round_trip":
                    found = _swap_canary(root, e, model)
                if found:
                    break
            if found:
                break
        out[gate] = found or {"none": "no PROVED law of the gate's directories has a perturb canary"}
    return out


# ---------------------------------------------------------------------------------------------- L11: the site canary
# Rule L11 (review 2, M2): the mutation canary of the PROVED SORT sites. Per site, a mutated copy of the facts document
# strips the site of its protection (site_mutation); holon's own Bend side builds the mutated instrumented model
# (generate_mutated_model); on it the instrument finds a sample where the site predicate is false (the obligation
# fails at a hit); the build's Lean model re-emitted from the mutated copy must give false there too
# (site_canary_lean).
GENERATE_INSTRUMENTED = r'''
import json, sys
from pathlib import Path
from holon.sorts import sites
root = Path(sys.argv[1]).resolve()
der = json.loads(Path(sys.argv[2]).read_text())
sys.stdout.write(sites.instrumented_model(Path(sys.argv[3]), der, root, anchor=root / sys.argv[4]))
'''


def _ptr(*parts) -> str:
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def _subtraction_paths(e, key: str, at: tuple, conds: tuple, out: list) -> list:
    """Every position of the facts expression whose canonical form is `key` in e (at: e's JSON pointer parts), with the
    conditions evaluation must meet to reach it: [(pointer parts of a condition, the value that reaches it)], as
    holon.sorts.sites rule R10 reads evaluation (a ? branch: its condition true or false; && and ||: the operands
    before it true, respectively false)."""
    if not isinstance(e, list) or not e:
        return out
    if canonical(e) == key:
        out.append((at, conds))
    op = e[0]
    if op == "?" and len(e) == 4:
        _subtraction_paths(e[1], key, at + (1,), conds, out)
        _subtraction_paths(e[2], key, at + (2,), conds + ((at + (1,), True),), out)
        _subtraction_paths(e[3], key, at + (3,), conds + ((at + (1,), False),), out)
        return out
    if op in ("&&", "||"):
        pre = conds
        for i in range(1, len(e)):
            _subtraction_paths(e[i], key, at + (i,), pre, out)
            pre = pre + ((at + (i,), op == "&&"),)
        return out
    if op == "call":
        kids = range(2, len(e))
    elif op == "get":
        kids = [1]
    elif op in ("mk", "with"):
        for i, x in enumerate(e[2:], start=2):
            if isinstance(x, dict):
                for k in sorted(x):
                    _subtraction_paths(x[k], key, at + (i, k), conds, out)
            else:
                _subtraction_paths(x, key, at + (i,), conds, out)
        return out
    elif op == "list":
        kids = range(2, len(e))
    else:
        kids = range(1, len(e))
    for i in kids:
        _subtraction_paths(e[i], key, at + (i,), conds, out)
    return out


CALLER = "who"   # the caller input of a facts-0.2 action (the format's own word): its requires are permissions


def _neutral(e, val: bool) -> list:
    """e made constantly val while still containing e: ["||", true, e] or ["&&", false, e]. A site's span and hits are
    read from the expressions (holon.sorts.assign.site_span looks for the require that checks the subtraction, in its
    subterms too), so the mutation keeps them and the site keeps its id."""
    return ["||", True, e] if val else ["&&", False, e]


def _at(e, at: tuple):
    for k in at:
        e = e[k]
    return e


def _expand(e, lets: dict):
    """A facts expression with every let name replaced by its (expanded) definition."""
    if isinstance(e, str):
        return lets.get(e, e)
    if isinstance(e, list):
        return [_expand(x, lets) for x in e]
    if isinstance(e, dict):
        return {k: _expand(v, lets) for k, v in e.items()}
    return e


def _mentions(e, name: str) -> bool:
    if isinstance(e, str):
        return e == name
    if isinstance(e, list):
        return any(_mentions(x, name) for x in e)
    if isinstance(e, dict):
        return any(_mentions(v, name) for v in e.values())
    return False


def site_mutation(facts: dict, derivation: dict, law_ids: list[str]) -> list[dict]:
    """The canary's mutation of the facts document for the given site laws (rule L11): JSON-pointer edits, as
    spec/M1/mutations.json writes them. For each site: (1) a definition site (its subtraction in defs.<d>.body): every
    condition on the way from d's body to the subtraction is made constantly the value that reaches it (_neutral);
    (2) for each of its DERIVATION hits, every require of the hit's action before the hit (guards[k]: the requires of
    guards[0..k-1]; an effect: every require) is made constantly true, except a permission (a require that names the caller input who,
    its lets expanded: the principal classes the model's dispatch derives stay as they are) and a require that is
    itself a hit of one of the sites (so every site keeps its DERIVATION hits). Edits are merged by pointer, in
    pointer order."""
    entries = {d["law_id"]: d for d in derivation["laws"]}
    acts = {a["name"]: i for i, a in enumerate(facts["actions"])}
    edits: dict[str, object] = {}
    hit_at = {(h["action"], h["at"]) for lid in law_ids for h in entries[lid]["hits"]}   # never removed
    for lid in law_ids:
        d = entries[lid]
        expr = d["basis"]["expr"]
        span = d["basis"]["span"]
        model = d["basis"]["model"]
        if span.startswith(model + ":"):
            dname = span.split(":", 1)[1]
            paths = _subtraction_paths(facts["defs"][dname]["body"], canonical(expr), (), (), [])
            if not paths:
                raise Unsupported(f"{lid}: the subtraction is not in defs.{dname}.body")
            body = facts["defs"][dname]["body"]
            for _, conds in paths:
                for at, val in conds:
                    p = _ptr("defs", dname, "body", *at)
                    v = _neutral(_at(body, at), val)
                    if edits.setdefault(p, v) != v:
                        raise Unsupported(f"{lid}: conflicting edits at {p}")
        for h in d["hits"]:
            ai = acts[h["action"]]
            gs = facts["actions"][ai].get("guards", [])
            m = re.fullmatch(r"guards\[(\d+)\]", h["at"])
            upto = int(m.group(1)) if m else len(gs)
            lets: dict = {}
            for i in range(upto):
                if "let" in gs[i]:
                    lets[gs[i]["let"]] = _expand(gs[i]["expr"], lets)
                elif ("require" in gs[i] and (h["action"], f"guards[{i}]") not in hit_at
                      and not _mentions(_expand(gs[i]["require"], lets), CALLER)):
                    edits[_ptr("actions", ai, "guards", i, "require")] = _neutral(gs[i]["require"], True)
    return [{"pointer": p, "value": v} for p, v in sorted(edits.items())]


def apply_edits(doc, edits: list[dict]):
    """A deep copy of doc with each JSON-pointer edit applied (the pointer must exist)."""
    out = json.loads(json.dumps(doc))
    for ed in edits:
        parts = [p.replace("~1", "/").replace("~0", "~") for p in ed["pointer"].split("/")[1:]]
        cur = out
        for p in parts[:-1]:
            cur = cur[int(p)] if isinstance(cur, list) else cur[p]
        last = parts[-1]
        if isinstance(cur, list):
            cur[int(last)] = ed["value"]
        else:
            if last not in cur:
                raise KeyError(ed["pointer"])
            cur[last] = ed["value"]
    return out


def generate_mutated_model(root: Path, derivation: dict, facts_rel: str, mutated: dict, dest: Path) -> Path:
    """The instrumented Bend model holon builds for a run of the derivation's milestone on the mutated document, with
    the ghost section of the derivation's laws (holon's own Bend side, holon.sorts.sites.instrumented_model, run in a
    separate python process from the root: this module imports no holon code; I43 does not edit the Bend side, and
    regression R1 pins the committed models it produced), written to dest."""
    fp = dest.parent / "mutated_facts.json"
    fp.write_text(json.dumps(mutated, indent=2, sort_keys=True) + "\n")
    dp = dest.parent / "derivation.json"
    dp.write_text(json.dumps(derivation, indent=2, sort_keys=True) + "\n")
    p = subprocess.run([sys.executable, "-c", GENERATE_INSTRUMENTED, str(root), str(dp), str(fp), facts_rel],
                       cwd=root, capture_output=True, text=True, timeout=600, env=_bend_env())
    if p.returncode != 0 or GHOST_MARKER not in p.stdout:
        raise AssertionError(f"the mutated instrumented model could not be built: {p.stderr[-2000:]}")
    dest.write_text(p.stdout)
    return dest


GHOST_MARKER = "# ---- ghost: SORT-site instrumentation (holon.sorts.sites)"


def _variants(a: dict, d: dict) -> list[dict]:
    """An action and each copy of it with one Nat input set to one of NAT_PROBES."""
    out = [a]
    for n, t in d["inputs"]:
        if t == "Nat":
            for v in NAT_PROBES:
                b = dict(a)
                b[n] = v
                out.append(b)
    return out


def site_canaries(root: Path, key: str, model: dict, entries: list[dict]) -> dict:
    """Rule L11: per PROVED site law of the model, {site: canary}. The site's own mutation (site_mutation of that law
    alone) gives a mutated document and holon's mutated instrumented model of it (generate_mutated_model, the
    derivation cut to that law); on it the samples are the mutated model's run of each differential trace from s0
    under T1 and the site's entry-point actions (each action of the differential of an entry-point constructor, and
    its one-input NAT_PROBES variants, in canonical order), traces first; the first sample where the mutated site
    predicate is false is the canary: {"law", "mutation", "trace", "act", "site": false, "hit": the hit predicate
    there}, or {"law", "mutation", "none": reason} when no sample makes it false."""
    root = Path(root)
    facts_rel = model["facts"]
    facts = load_json(root / facts_rel)
    derivation = load_json(root / model["derivation"])
    proved = sorted(e["law_id"] for e in entries if e.get("model_key") == key and e["status"] == "PROVED"
                    and e["subform"] == "site")
    d = model["differential"]
    pname = d["parameter"]
    out = {}
    for lid in proved:
        sname = "site_" + lid[len("L_sort_site_"):]
        edits = site_mutation(facts, derivation, [lid])
        mutated = apply_edits(facts, edits)
        ms = MachineSamples(model["kind"], mutated, model["params"])
        t1 = "[" + ", ".join(f"M.HO_{pname}{{{ms.bv('List<Nat>', k)}, {int(v)}n}}" for k, v in d["tables"]["T1"]) \
            + "]" if d["tables"]["T1"] else "Nil{}"
        acts = {a["name"]: a for a in mutated["actions"]}
        entry = set(model["entry_points"][sname])
        cands = sorted(_dedup([v for a in d["actions"] if a["op"] in entry for v in _variants(a, acts[a["op"]])]),
                       key=canonical)
        samples = [(i, a) for i in range(len(d["traces"])) for a in cands]
        tmp = Path(tempfile.mkdtemp(prefix="i43_mut_"))
        try:
            mpath = generate_mutated_model(root, dict(derivation, laws=[x for x in derivation["laws"]
                                                                        if x["law_id"] == lid]),
                                           facts_rel, mutated, tmp / "model.bend")

            def st(i):
                return f"M.run({ms.trace(d['traces'][i])}, M.s0(), {t1})"
            found = None
            for c in range(0, len(samples), 1200):
                part = samples[c:c + 1200]
                vals = bend_eval(mpath, "Bool", [f"M.{sname}({ms.act(a)}, {st(i)}, {t1})" for i, a in part],
                                 chunk=1200)
                j = next((k for k, v in enumerate(vals) if v == ("C", "False", [])), None)
                if j is not None:
                    found = part[j]
                    break
            if found is None:
                out[sname] = {"law": lid, "mutation": edits,
                              "none": "no sample of the mutated model makes the site predicate false"}
                continue
            i, a = found
            hname = "hit_" + sname[len("site_"):]
            hv = bend_eval(mpath, "Bool", [f"M.{hname}({ms.act(a)}, {st(i)}, {t1})"])[0]
            out[sname] = {"law": lid, "mutation": edits, "trace": i, "act": a, "site": False,
                          "hit": hv == ("C", "True", [])}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return out


def site_canary_lean(model: dict, facts: dict, sname: str, c: dict) -> tuple[str, list[str], list[str]]:
    """Rule L11's Lean side: (the sample's inputs as noncomputable defs, the canary theorems, their names) to append
    to the Lean model emitted from the mutated copy: the site predicate is false at the canary's sample (the mutated
    run of its trace from s0 under T1, its action), and the hit predicate has the value the mutated Bend model gave."""
    lv = LeanValues(model["kind"], facts)
    d = model["differential"]
    rows = ", ".join(f"({lv.val('List<Nat>', k)}, {int(v)})" for k, v in d["tables"]["T1"])
    tr = d["traces"][c["trace"]]
    trace = "[" + ", ".join(lv.act(a) for a in tr) + "]" if tr else "[]"
    pre = ("noncomputable def holonTable : List (List Nat × Nat) → List Nat → Nat\n  | [], _ => 0\n"
           "  | (k, v) :: t, x => if x = k then v else holonTable t x\n\n"
           f"noncomputable def holonT1 : List Nat → Nat := holonTable [{rows}]\n\n"
           f"noncomputable def holonCanTr : List Model.Act := {trace}\n\n"
           f"noncomputable def holonCanAct : Model.Act := {lv.act(c['act'])}\n")
    x = sname[len("site_"):]
    st = "(Model.run holonT1 holonCanTr Model.s0)"
    thms = [f"theorem holon_canary_site : Model.site_{x} holonT1 holonCanAct {st} = false := by decide",
            f"theorem holon_canary_hit : Model.hit_{x} holonT1 holonCanAct {st} = "
            f"{'true' if c['hit'] else 'false'} := by decide"]
    return pre, thms, ["holon_canary_site", "holon_canary_hit"]


# ---------------------------------------------------------------------------------------------- rule L4: the files
_DECL = re.compile(r"^(?:noncomputable\s+)?(?:def|theorem|structure|inductive|abbrev)\s+([A-Za-z_][A-Za-z0-9_]*)")
PREAMBLE_LINE = re.compile(r"set_option\s+(autoImplicit\s+false|(maxRecDepth|maxHeartbeats)\s+\d+)\s*$")
MODEL_LINE = re.compile(r"((noncomputable\s+)?def|theorem|structure|inductive|abbrev)\s|deriving\s|\||"
                        r"termination_by\b|decreasing_by\b|set_option\s+(maxRecDepth|maxHeartbeats)\s+\d+\s+in\s*$")
PROOF_LINE = re.compile(r"(theorem|(noncomputable\s+)?def|example)\s|\||termination_by\b|decreasing_by\b|"
                        r"set_option\s+(maxRecDepth|maxHeartbeats)\s+\d+(\s+in)?\s*$")
WORDS_ANYWHERE = re.compile(r"\b(instance|attribute|variable|include|omit|universe|open|export|section|local|scoped|"
                            r"private|protected|mutual|class|axiom|opaque|unsafe|partial|import|sorry|admit)\b")
WORDS_AFTER_MARKER = re.compile(r"\b(namespace|end|structure|inductive|abbrev|deriving)\b")


def norm(s: str) -> str:
    return " ".join(s.split())


CORE_WORDS_AFTER_MARKER = re.compile(r"\b(instance|attribute|deriving|variable|include|omit|universe|open|export|"
                                     r"namespace|section|end|local|scoped|private|protected|noncomputable|mutual|"
                                     r"class|abbrev|structure|inductive)\b")
CORE_LINE = re.compile(r"(theorem|def|example)\s|\||termination_by\b|decreasing_by\b|"
                       r"set_option\s+(maxRecDepth|maxHeartbeats)\s+\d+(\s+in)?\s*$")


# a command keyword at the start of an indented line (review 2, m1): the column-0 layout rules would not see it.
# set_option followed by `in` on the same line is the tactic form and stays allowed (its option is still restricted)
INDENTED_COMMAND = re.compile(r"^[ \t]+(theorem|lemma|def|abbrev|instance|axiom|axioms|example|opaque|structure|"
                              r"inductive|class|namespace|section|end|open|variable|variables|universe|noncomputable|"
                              r"private|protected|partial|unsafe|mutual|attribute|deriving\s+instance|macro|"
                              r"macro_rules|syntax|notation|elab|elab_rules|initialize|export|import|"
                              r"set_option(?!.*\bin\s*$))\b", re.M)


def _indented_commands(code: str) -> list[str]:
    return [f"an indented command: {m.group(0).strip()[:60]!r}" for m in INDENTED_COMMAND.finditer(code)]


def core_file_violations(src: str) -> list[str]:
    """Rule C2 on gen/M3/theory2/lean/TheoryII.lean, read comment-free by lean_code: no # anywhere and no word of
    LEAN_BANNED in the whole file; after the marker line no escaped identifier, no attribute "@[", no string literal,
    none of CORE_WORDS_AFTER_MARKER, and every column-0 line matches CORE_LINE. (That the file starts with the frozen
    definitions block is checked against the sidecar by the test.)"""
    v = []
    code = lean_code(src)
    if "#" in code:
        v.append("a # in the code (a command such as #eval, #exit or #print, or an array or BitVec literal)")
    v += [f"the banned word {w}" for w in sorted(set(m.group(0) for m in LEAN_BANNED.finditer(code)))]
    v += _indented_commands(code)
    i = src.find("\n" + LEAN_MARKER + "\n")
    if i < 0:
        return v + [f"no marker line {LEAN_MARKER!r}"]
    tail = src[i + len(LEAN_MARKER) + 2:]
    if "«" in tail:
        v.append("an escaped identifier after the marker")
    rest = lean_code(tail)
    if "@[" in rest:
        v.append("an attribute @[...] after the marker")
    if '"' in rest:
        v.append("a string literal after the marker")
    w = CORE_WORDS_AFTER_MARKER.search(rest)
    if w:
        v.append(f"the word {w.group(0)} after the marker")
    v += [f"a column-0 line rule C2 does not allow: {ln[:100]!r}" for ln in rest.splitlines()
          if ln.strip() and not ln[0].isspace() and not CORE_LINE.match(ln)]
    return v


def file_violations(src: str, law_file: bool) -> list[str]:
    """Rule L4 on a Lean file holon emits (a law file, or a model file when law_file is False), read comment-free by
    lean_code. Returns the violations (empty when the file obeys the rule): no # anywhere, no word of LEAN_BANNED or
    WORDS_ANYWHERE, no escaped identifier, attribute or string literal, and the layout below."""
    v = []
    code = lean_code(src)
    if "«" in code:
        v.append("an escaped identifier «...»")
    if "@[" in code:
        v.append("an attribute @[...]")
    if '"' in code:
        v.append("a string literal")
    if "#" in code:
        v.append("a # in the code (a command such as #eval, #exit or #print, or an array or BitVec literal)")
    v += [f"the banned word {w}" for w in sorted(set(m.group(0) for m in LEAN_BANNED.finditer(code)))]
    v += _indented_commands(code)
    w = WORDS_ANYWHERE.search(code)
    if w:
        v.append(f"the word {w.group(0)}")
    for m in re.finditer(r"\bset_option\s+\S+(\s+\S+)?", code):
        if not re.fullmatch(r"set_option\s+(autoImplicit\s+false|(maxRecDepth|maxHeartbeats)\s+\d+)", m.group(0)):
            v.append(f"an option other than autoImplicit false, maxRecDepth or maxHeartbeats: {m.group(0)[:60]!r}")
    lines = [ln.rstrip() for ln in code.splitlines() if ln.strip()]
    col0 = [ln for ln in lines if not ln[0].isspace()]
    try:
        i_ns = col0.index("namespace Model")
        i_end = col0.index("end Model")
    except ValueError:
        return v + ["no `namespace Model` ... `end Model` block"]
    if col0.count("namespace Model") != 1 or col0.count("end Model") != 1 or i_end < i_ns:
        v.append("not exactly one `namespace Model` before exactly one `end Model`")
    pre = col0[:i_ns]
    if not pre or pre[0] != "set_option autoImplicit false":
        v.append("the first line is not `set_option autoImplicit false`")
    v += [f"preamble line {ln[:80]!r}" for ln in pre if not PREAMBLE_LINE.match(ln)]
    v += [f"model line {ln[:80]!r}" for ln in col0[i_ns + 1:i_end] if not MODEL_LINE.match(ln)]
    rest = col0[i_end + 1:]
    if not law_file:
        if rest:
            v.append("a model file declares something after `end Model`")
        return v
    marks = [m.start() for m in re.finditer(rf"(?m)^{re.escape(LEAN_MARKER)}\s*$", src)]
    ends = [m.start() for m in re.finditer(r"(?m)^end Model\s*$", src)]
    if len(marks) != 1 or not ends or marks[0] < ends[-1]:
        v.append(f"not exactly one marker line {LEAN_MARKER!r} after `end Model`")
    v += [f"proof line {ln[:80]!r}" for ln in rest if not PROOF_LINE.match(ln)]
    after = "\n".join(rest)
    w = WORDS_AFTER_MARKER.search(re.sub(r"(?m)^noncomputable\s+def\s", "def ", after))
    if w:
        v.append(f"the word {w.group(0)} after the marker")
    return v


def shadow_violations(src: str, model: dict) -> list[str]:
    """Rule L4: the model section declares no name that the frozen texts use from outside the interface (Nat, Bool,
    List, Option, BitVec, a binder or field name, ...): a Model.Nat declared before St would change what St's frozen
    text means, verbatim as it stays."""
    i = model["interface"]
    own = {n for n, _ in i["types"] + i["decls"] + i["signatures"]}
    used = {w for _, t in i["types"] + i["decls"] + i["signatures"] for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", t)}
    return [f"the model section declares {n}, a name the frozen texts use" for n in sorted(model_decls(src))
            if n in used - own]


def model_decls(src: str) -> dict[str, list[str]]:
    """The top-level declarations between `namespace Model` and `end Model` (comment-free), by name, each
    whitespace-normalized: a declaration runs from its column-0 line to the next column-0 declaration line."""
    code = lean_code(src)
    lines = code.splitlines()
    try:
        a = next(i for i, ln in enumerate(lines) if ln.rstrip() == "namespace Model")
        b = next(i for i, ln in enumerate(lines) if ln.rstrip() == "end Model")
    except StopIteration:
        return {}
    out: dict[str, list[str]] = {}
    cur, buf = None, []
    for ln in lines[a + 1:b] + ["def __end"]:
        m = _DECL.match(ln)
        if m:
            if cur is not None:
                out.setdefault(cur, []).append(norm("\n".join(buf)))
            cur, buf = m.group(1), [ln]
        elif cur is not None:
            buf.append(ln)
    return out


def decl_refs(src: str) -> dict[str, set[str]]:
    """For each top-level declaration of a file's model section (model_decls), the other declarations of that section
    its text names (every identifier part, so Model.x and s.x both name x)."""
    decls = model_decls(src)
    names = set(decls)
    return {n: {w for tx in texts for w in re.findall(r"[A-Za-z_][A-Za-z0-9_']*", tx)} & names - {n}
            for n, texts in decls.items()}


def site_reach_violations(src: str, model: dict) -> list[str]:
    """Rule L4 (review M1): every site predicate site_<x> the model section declares reaches its raw obligation
    ro_<x> through the section's declarations (decl_refs), so the site's reading uses the pinned obligation."""
    refs = decl_refs(src)
    out = []
    for s in model.get("sites", []):
        if s not in refs:
            continue
        seen, todo = set(), [s]
        while todo:
            x = todo.pop()
            if x not in seen:
                seen.add(x)
                todo += sorted(refs.get(x, ()))
        if ro_name(s) not in seen:
            out.append(f"{s} does not reach {ro_name(s)}")
    return out


def required_names(model: dict, texts: list[str]) -> tuple[list[str], list[str]]:
    """(frozen declarations, signatures) a file stating `texts` relies on: the interface names the texts mention as
    Model.<name>, closed under the names the required declarations and signatures mention."""
    i = model["interface"]
    decl = {n: t for n, t in i["types"] + i["decls"]}
    sig = dict(i["signatures"])
    todo = set()
    for t in texts:
        todo |= {m.group(1) for m in re.finditer(r"\bModel\.([A-Za-z_][A-Za-z0-9_]*)", t)}
    seen = set()
    while todo:
        n = todo.pop()
        if n in seen or (n not in decl and n not in sig):
            continue
        seen.add(n)
        body = decl.get(n, "") + " " + sig.get(n, "")
        todo |= {w for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", body) if w in decl or w in sig}
    return sorted(x for x in seen if x in decl), sorted(x for x in seen if x in sig)


# ---------------------------------------------------------------------------------------------- the sidecar
NAMING = {
    "namespace": "every model definition lives in `namespace Model` (one `namespace Model` ... `end Model` block per "
                 "file); every frozen statement refers to it as Model.<name>; no other namespace, no `open`",
    "theorems": "at top level, after the marker line `-- holon:theorems`: a PROVED law's theorem is named exactly its "
                "law id; a REFUTED law's counter-law is <law id>_counter and its refutation <law id>_refuted (I9)",
    "identifiers": "every name taken from a facts or linked document gets a fixed prefix, so no generated identifier "
                   "is a Lean keyword or a word of tests_m3/_i43.py::LEAN_BANNED (whole words only): record type "
                   "T -> T_T, its field x -> f_x; state field x -> St.f_x; action a -> constructor Act.a_a with input "
                   "binders i_<input>; observer o -> ob_o; migration m -> mig_m; model function f (last_ok, runs_ok, "
                   "no_code, perm, cost, elapsed, is_<a>, consumers) -> fn_f; site and hit predicates of a SORT site "
                   "-> site_<x> and hit_<x> (x: the law id after L_sort_site_, holon.sorts.sites rule R7), the site's "
                   "raw obligation -> ro_<x>; linked "
                   "record carrier C -> R_C, its byte k of field F -> f_<F with . written __>_<k>; linked function "
                   "f -> c_f, a loader's condition -> c_ok_<loader>; a view erasing fields F1..Fn -> V_<F sorted, "
                   "joined by __> with its projection view_<..>; statement binders -> v_<IR name>; oracle "
                   "parameters in Reach -> p_<name>. Never an escaped identifier (guillemets).",
    "fixed": "St, Act, Obs, Reach, Cell, Bytes, step, run, s0, obs",
    "files": "one file per attempted law at <lean dir>/<law id>.lean (lean dirs gen/M1/lean, gen/M2/lean, "
             "gen/M2/extracted/m1/lean, gen/M3/lean), one model file per Bend model at <lean dir>/models/<model "
             "stem>.lean, one report.json per lean dir; nothing else in those directories",
}

READINGS = {
    "machine": "Lean reads the holon-facts/0.2 document itself (holon.gen.lean_machine), the target library through "
               "its Lean twin (hand-written target input, like the Bend library: common mode, I9 Question 4); Nat, "
               "Bool and lists as in Bend; premises are hypotheses as in Bend; the statement is the frozen Lean text "
               "of the same IR",
    "machine_oracle": "as machine, and: the Fn<List<Nat>,Nat> oracle parameter is a Lean function (List Nat -> "
                      "Nat) where Bend ranges over finite tables (first matching entry, else 0), each of which is "
                      "such a function, so the Lean theorem implies the Bend one; Reach is the same inductive set; the "
                      "site predicate is Lean's own reading of rules R8-R10 (holon.gen.lean_sites) over the site's raw "
                      "obligation ro_<x>; on every PROVED site the site predicate is constantly true (coercion_guard "
                      "never uses Reach), so rule L7 pins where a site is hit (hit_<x>) and the raw obligation "
                      "(ro_<x>), each taking both values on the samples, and rule L4 requires site_<x> to reach "
                      "ro_<x>",
    "linked": "Lean cells are Option (BitVec 8): a record's byte is a BitVec 8 where Bend's is a U32, so Lean's "
              "theorems cover byte-valued records only (a narrower domain than Bend's, I9 Surprise 5); an undefined "
              "cell (Bend 57005) is none, and the decoders' orderings compare it as 57005; every premise is a "
              "hypothesis where Bend pins a field to a constant or to another record's field (an equivalent "
              "statement)",
}


def _bend_files(root: Path) -> list[dict]:
    """Rule R1's baseline: every .bend file under gen/M0..gen/M3 with its sha256 and the sha256 of its text with every
    statement_hash value masked."""
    out = []
    for m in ("M0", "M1", "M2", "M3"):
        for p in sorted((root / "gen" / m).rglob("*.bend")):
            b = p.read_bytes()
            masked = re.sub(rb"statement_hash: sha256:[0-9a-f]{64}", b"statement_hash: sha256:<masked>", b)
            out.append({"path": p.relative_to(root).as_posix(), "sha256": hashlib.sha256(b).hexdigest(),
                        "masked_sha256": hashlib.sha256(masked).hexdigest()})
    return out


def promoted_doc(root: Path = ROOT) -> dict:
    """The content of spec/M3/lib/lean_promoted.json (rules L0-L3, L7 and the regressions' baselines)."""
    root = Path(root)
    entries, models = rendered(root)
    for key, m in models.items():
        if m["kind"] == "linked":
            m["differential"] = linked_differential(root, key, m, entries)
        else:
            m["differential"] = machine_differential(root, key, m, entries)
            m["action_successes"] = action_successes(m, load_json(root / m["facts"]))
        if m["sites"]:
            m["site_coverage"] = site_coverage(m)
            m["site_canaries"] = site_canaries(root, key, m, entries)
    canaries = perturb_canaries(root, entries, models)
    p5, p5_out = [], {}
    for e in entries:   # I43-P2 scores the PROVED site laws the samples and the mutation canary pin (review M1; 2, M2)
        if e["dir"] != "M2" or e["status"] != "PROVED":
            continue
        m = models[e["model_key"]]
        sn = site_name(site_ids(load_json(root / e["law_file"])["statement"], [])[0])
        cov, can = m["site_coverage"][sn], m["site_canaries"][sn]
        if "none" in can:
            p5_out[e["law_id"]] = f"{sn}: {can['none']}"
        elif cov["ro"] != [False, True] or cov["hit"] != [False, True]:
            p5_out[e["law_id"]] = f"{sn}: raw obligation values {cov['ro']}, hit values {cov['hit']} on the samples"
        else:
            p5.append(e["law_id"])
    files = {ORACLES}
    for m in models.values():
        if m.get("derivation"):
            files.add(m["derivation"])
    statuses, rec_inputs = {}, []
    for dkey, rdir, ldir, odir, facts_override in DIRS:
        files.add(f"{ldir}/REGISTRY.json")
        for p in sorted((root / rdir).glob("L*.json")):
            rec = load_json(p)
            statuses[f"{rdir}/{p.name}"] = rec.get("status")
    for e in entries:
        files |= {e["law_file"], e["facts"]}
        if e["model"]:
            files.add(e["model"])
        rec = load_json(root / e["record"])
        rec_inputs.append({"path": e["record"], "status": rec.get("status"),
                           "witness_sha256": _sha_json(rec.get("witness")),
                           "non_vacuity_witness_sha256": _sha_json((rec.get("non_vacuity") or {}).get("witness")),
                           "witnesses_sha256": _sha_json(rec.get("witnesses"))})
    inputs = [{"path": f, "sha256": file_sha256(root / f)} for f in sorted(files)] + \
        sorted(rec_inputs, key=lambda i: i["path"])
    counts = {"proved": {}, "refuted": {}, "refuted_attempted": {}}
    for d, *_ in DIRS:
        counts["proved"][d] = sum(1 for e in entries if e["dir"] == d and e["status"] == "PROVED")
        counts["refuted"][d] = sum(1 for e in entries if e["dir"] == d and e["status"] == "REFUTED")
        counts["refuted_attempted"][d] = sum(1 for e in entries if e["dir"] == d and e["status"] == "REFUTED"
                                            and e["attempt"] == "lean")
    for e in entries:
        e["reading"] = READINGS.get(e["kind"])
    return {
        "doc": ("I43 prereg sidecar (frozen), part B: Lean for the promoted set (human answer Q8: every PROVED law). "
                "Computed at the prereg by tests_m3/_i43.py::promoted_doc from the inputs listed (each file with its "
                "sha256; each record with its status and the sha256 of its witness, its non-vacuity witness and its "
                "per-entry witnesses) and from the committed Bend models run by the pinned bend (the differential "
                "values). laws: rule L0's scope with each law's frozen Lean statements (rule L3), or, for a REFUTED "
                "law outside the Lean emitters' model kinds and for I31's DISCH laws, the reason it is not attempted. models: per Bend model, "
                "its kind, its frozen interface (rule L2) and its differential samples (rule L7: inputs, and the "
                "values the compiled Bend model computes on them; machine models also their action_successes and, "
                "with sites, their site_coverage and site_canaries: rule L11's mutation per PROVED site, with the "
                "sample where holon's mutated Bend model makes the site predicate false). canaries: rule L9's "
                "perturb canary per milestone gate, with the Bend value of the perturbed equation's left side at the "
                "record's witness (an evaluate law; the kept proof fixes that witness) or on a seeded record (a round "
                "trip). site_laws_scored: the PROVED site laws I43-P2 scores (both values of hit and raw obligation, "
                "and a site canary). unregenerated_records: I30's typed, I27's UNDO and I31's DISCH M3 records, which "
                "I43 does not regenerate (R1 keeps them as they are). Checked at the prereg: every statement elaborates against "
                "its interface (Lean reports one placeholder warning per theorem and no error), and every "
                "differential sample is a well-typed proposition over the interface. bend_files, lean_m0, statuses "
                "and unregenerated_records: the baselines of regressions R1 and R7. Recompute: python -c 'import "
                "json; from tests_m3 import _i43; print(json.dumps(_i43.promoted_doc(), indent=2, sort_keys=True))'"),
        "promoted_version": PROMOTED_VERSION,
        "dirs": [{"dir": d, "records": r, "laws": l, "lean_dir": o, "facts": f} for d, r, l, o, f in DIRS],
        "naming": NAMING,
        "readings": READINGS,
        "allowed_reasons": list(ALLOWED_REASONS),
        "refuted_reasons": list(REFUTED_REASONS),
        "allowed_axioms": list(ALLOWED_AXIOMS),
        "banned_words": LEAN_BANNED.pattern,
        "marker": LEAN_MARKER,
        "inputs": inputs,
        "counts": counts,
        "laws": entries,
        "models": models,
        "canaries": canaries,
        "site_laws_scored": {"laws": p5, "excluded": p5_out},
        "unregenerated_records": [
            {"path": f"results/M3/{p.name}", "status": r.get("status"), "statement_hash": r.get("statement_hash"),
             "generator_sha256": r.get("generator_sha256"), "witness_sha256": _sha_json(r.get("witness")),
             "non_vacuity_witness_sha256": _sha_json((r.get("non_vacuity") or {}).get("witness")),
             "witnesses_sha256": _sha_json(r.get("witnesses")), "kernels_sha256": _sha_json(r.get("kernels"))}
            for p in sorted((root / "results" / "M3").glob("L*.json"))
            if p.name.startswith(("L_sort_", "L_undo_", "L_disch_"))
            for r in [load_json(p)]],
        "statuses": statuses,
        "bend_files": _bend_files(root),
        "lean_m0": [{"path": p.relative_to(root).as_posix(), "sha256": file_sha256(p)}
                    for p in sorted((root / "gen" / "M0" / "lean").iterdir()) if p.is_file()],
    }


def sidecar_text(doc) -> str:
    """The sidecars' file format (the tests compare the parsed JSON, never the text): objects one key per line, sorted,
    indented by two; every list one element per line, each element compact (so a differential sample, a law entry or
    a Bend file entry is one line)."""
    def one(x) -> str:
        return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))

    def go(x, ind: int) -> str:
        pad, pad1 = "  " * ind, "  " * (ind + 1)
        if isinstance(x, dict) and x:
            items = [f"{pad1}{json.dumps(k, ensure_ascii=False)}: {go(x[k], ind + 1)}" for k in sorted(x)]
            return "{\n" + ",\n".join(items) + "\n" + pad + "}"
        if isinstance(x, list) and x:
            return "[\n" + ",\n".join(pad1 + one(e) for e in x) + "\n" + pad + "]"
        return one(x)

    return go(doc, 0) + "\n"
