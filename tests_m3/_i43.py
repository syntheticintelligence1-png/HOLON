"""I43 prereg computation: Theory core II (equivariance, 2-cell pasting) and Lean 4 promotion for the promoted set.

Independently computes the preregistration sidecar
``spec/M3/lib/theory_core_ii.json`` from the frozen M0/M1/M2/M3 inputs and registries:
  - the 10 polymorphic Bend 2 laws in ``THEORY_CORE_II`` (5 equivariance laws:
    ``core_equivar_compose``, ``core_equivar_whisker``, ``core_equivar_obs``,
    ``core_equivar_pred``, ``core_equivar_homotopy``; 5 2-cell pasting laws:
    ``core_paste_grid_2x2``, ``core_paste_h_3``, ``core_paste_v_obs``,
    ``core_paste_square_trans``, ``core_paste_whisker_interchange``),
  - the 4 concrete M3 ``equivariance`` basis laws in
    ``gen/M3/basis/equivariance/{LAWS,PROOF}.bend`` over the M1 ``morph_rollup``
    migration morphisms ``mig_legacy`` and ``mig_eta2`` and step transitions
    ``step_wait`` and ``step_sendMessage``,
  - the 4 concrete M3 ``pasting`` basis laws in
    ``gen/M3/basis/pasting/{LAWS,PROOF}.bend`` over ``lci_of`` and ``tags_ok``
    along the composed migration chain ``mig_eta2(mig_legacy(s), root)``,
  - the 92 promoted ``PROVED`` laws across M0..M3 (5 M0 + 8 M1 + 6 M2 + 73 M3)
    targeted for ``I2`` dual-kernel promotion in ``gen/M3/lean/`` and
    ``results/M3/lean.json`` under Lean 4.34.0 (where ``gen/M3/lean/lakefile.toml``
    uses ``[[lean_lib]]`` with ``name = "Holon"`` and ``globs = ["Holon.*"]``,
    every ``.lean`` file under ``gen/M3/lean/`` is self-contained with no
    ``import`` statements so ``holon.lean.forbidden(txt)`` is empty, zero
    ``sorry``/``admit``/``axiom``/``native_decide``/``unsafe``, and axioms
    within ``{propext, Quot.sound}``),
  - the 5 negative canaries across ``theory_core_ii``, ``equivariance``,
    ``pasting``, and ``lean`` (4 Bend canaries predicted ``REFUTED`` under both
    ``bend`` and ``bend --verdict``, plus ``canary_lean_flipped_claim``
    predicted ``REFUTED`` / semantically rejected by ``holon.lean.check_text``).

Must not import ``holon.gen.core``, ``holon.gen.basis``, or ``holon.lean``, or
read ``gen/M3/lean/`` or ``results/M3/lean.json``.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


THEORY_CORE_II_VERSION = "holon-i43-theory-core-ii/0.1"
LEAN_TOOLCHAIN_VERSION = "4.34.0"
ALLOWED_AXIOMS: tuple[str, ...] = ("Quot.sound", "propext")

INPUT_PATHS: tuple[str, ...] = (
    "facts/morph_header.json",
    "gen/M0/lean/report.json",
    "gen/M1/model/morph_rollup.bend",
    "gen/M3/model/header_length.bend",
    "laws/M0/REGISTRY.json",
    "laws/M1/REGISTRY.json",
    "laws/M2/REGISTRY.json",
    "laws/M3/REGISTRY.json",
    "spec/M1/facts/morph_rollup.json",
    "spec/M2/facts/morph_header.extracted.json",
    "spec/M2/facts/morph_rollup.extracted.json",
    "spec/M3/lib/theory_core_i.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# 1. THEORY_CORE_II: 10 polymorphic Bend 2 laws (5 equivariance + 5 pasting)
# ---------------------------------------------------------------------------

THEORY_CORE_II_SPECS: tuple[dict[str, Any], ...] = (
    {
        "law_id": "core_equivar_compose",
        "group": "equivariance",
        "proof_class": "core_equivar",
        "predicted_status": "PROVED",
        "doc": "equivariance under step composition: if f(s1(x)) == t1(f(x)) and f(s2(x)) == t2(f(x)), then f(s1(s2(a))) == t1(t2(f(a)))",
        "binders": [
            ("-A", "Data"),
            ("-B", "Type"),
            ("-f", "A -> B"),
            ("-s1", "A -> A"),
            ("s2", "A -> A"),
            ("-t1", "B -> B"),
            ("-t2", "B -> B"),
        ],
        "hyps": [
            ("h1", "@x:A -> {f(s1(x)) == t1(f(x)) : B}"),
            ("h2", "@x:A -> {f(s2(x)) == t2(f(x)) : B}"),
        ],
        "claim": "@+a:A -> {f(s1(s2(a))) == t1(t2(f(a))) : B}",
        "proof": "+a => (%h2(a) : {f(s1(s2(a))) == t1(_) : B}; h1(s2(a)))",
    },
    {
        "law_id": "core_equivar_whisker",
        "group": "equivariance",
        "proof_class": "core_equivar",
        "predicted_status": "PROVED",
        "doc": "equivariance under morphism composition (whiskering): if f(s(x)) == t(f(x)) and g(t(y)) == u(g(y)), then g(f(s(a))) == u(g(f(a)))",
        "binders": [
            ("-A", "Data"),
            ("-B", "Type"),
            ("-C", "Type"),
            ("f", "A -> B"),
            ("-g", "B -> C"),
            ("-s", "A -> A"),
            ("-t", "B -> B"),
            ("-u", "C -> C"),
        ],
        "hyps": [
            ("hf", "@x:A -> {f(s(x)) == t(f(x)) : B}"),
            ("hg", "@y:B -> {g(t(y)) == u(g(y)) : C}"),
        ],
        "claim": "@+a:A -> {g(f(s(a))) == u(g(f(a))) : C}",
        "proof": "+a => (%hg(f(a)) : {g(f(s(a))) == _ : C}; (%hf(a) : {g(f(s(a))) == g(_) : C}; {==}))",
    },
    {
        "law_id": "core_equivar_obs",
        "group": "equivariance",
        "proof_class": "core_equivar",
        "predicted_status": "PROVED",
        "doc": "equivariant observation transport: if f(s(a)) == t(f(a)), obs_B(t(b)) == obs_B(b), and obs_B(f(a)) == obs_A(a), then obs_B(f(s(a))) == obs_A(a)",
        "binders": [
            ("-A", "Data"),
            ("-B", "Type"),
            ("-V", "Type"),
            ("f", "A -> B"),
            ("-s", "A -> A"),
            ("-t", "B -> B"),
            ("-obs_A", "A -> V"),
            ("-obs_B", "B -> V"),
        ],
        "hyps": [
            ("heq", "@a:A -> {f(s(a)) == t(f(a)) : B}"),
            ("hobs", "@b:B -> {obs_B(t(b)) == obs_B(b) : V}"),
            ("hnat", "@a:A -> {obs_B(f(a)) == obs_A(a) : V}"),
        ],
        "claim": "@+a:A -> {obs_B(f(s(a))) == obs_A(a) : V}",
        "proof": "+a => (%hnat(a) : {obs_B(f(s(a))) == _ : V}; (%hobs(f(a)) : {obs_B(f(s(a))) == _ : V}; (%heq(a) : {obs_B(f(s(a))) == obs_B(_) : V}; {==})))",
    },
    {
        "law_id": "core_equivar_pred",
        "group": "equivariance",
        "proof_class": "core_equivar",
        "predicted_status": "PROVED",
        "doc": "equivariant Boolean invariant preservation: if f(s(a)) == t(f(a)), Q(t(b)) == Q(b), Q(f(a)) == P(a), and P(a) == True{}, then Q(f(s(a))) == True{}",
        "binders": [
            ("-A", "Data"),
            ("-B", "Type"),
            ("f", "A -> B"),
            ("-s", "A -> A"),
            ("-t", "B -> B"),
            ("-P", "A -> Bool"),
            ("-Q", "B -> Bool"),
        ],
        "hyps": [
            ("heq", "@a:A -> {f(s(a)) == t(f(a)) : B}"),
            ("hq", "@b:B -> {Q(t(b)) == Q(b) : Bool}"),
            ("hnat", "@a:A -> {Q(f(a)) == P(a) : Bool}"),
            ("hp", "@a:A -> {P(a) == True{} : Bool}"),
        ],
        "claim": "@+a:A -> {Q(f(s(a))) == True{} : Bool}",
        "proof": "+a => (%hp(a) : {Q(f(s(a))) == _ : Bool}; (%hnat(a) : {Q(f(s(a))) == _ : Bool}; (%hq(f(a)) : {Q(f(s(a))) == _ : Bool}; (%heq(a) : {Q(f(s(a))) == Q(_) : Bool}; {==}))))",
    },
    {
        "law_id": "core_equivar_homotopy",
        "group": "equivariance",
        "proof_class": "core_equivar",
        "predicted_status": "PROVED",
        "doc": "2-cell homotopy transport of equivariance across a pointwise equal source step: if s1(a) == s2(a) and f(s2(a)) == t(f(a)), then f(s1(a)) == t(f(a))",
        "binders": [
            ("-A", "Data"),
            ("-B", "Type"),
            ("-f", "A -> B"),
            ("-s1", "A -> A"),
            ("s2", "A -> A"),
            ("-t", "B -> B"),
        ],
        "hyps": [
            ("hs", "@a:A -> {s1(a) == s2(a) : A}"),
            ("heq", "@a:A -> {f(s2(a)) == t(f(a)) : B}"),
        ],
        "claim": "@+a:A -> {f(s1(a)) == t(f(a)) : B}",
        "proof": "+a => (%heq(a) : {f(s1(a)) == _ : B}; (%hs(a) : {f(s1(a)) == f(_) : B}; {==}))",
    },
    {
        "law_id": "core_paste_grid_2x2",
        "group": "pasting",
        "proof_class": "core_paste_ii",
        "predicted_status": "PROVED",
        "doc": "2x2 grid pasting of four 2-cells: horizontal f1 == f2 == f3 and vertical g1 == g2 == g3 compose to g1(f1(a)) == g3(f3(a))",
        "binders": [
            ("-A", "Data"),
            ("-B", "Type"),
            ("-C", "Type"),
            ("-f1", "A -> B"),
            ("f2", "A -> B"),
            ("f3", "A -> B"),
            ("-g1", "B -> C"),
            ("-g2", "B -> C"),
            ("-g3", "B -> C"),
        ],
        "hyps": [
            ("hf12", "@a:A -> {f1(a) == f2(a) : B}"),
            ("hf23", "@a:A -> {f2(a) == f3(a) : B}"),
            ("hg12", "@b:B -> {g1(b) == g2(b) : C}"),
            ("hg23", "@b:B -> {g2(b) == g3(b) : C}"),
        ],
        "claim": "@+a:A -> {g1(f1(a)) == g3(f3(a)) : C}",
        "proof": "+a => (%hg23(f3(a)) : {g1(f1(a)) == _ : C}; (%hf23(a) : {g1(f1(a)) == g2(_) : C}; (%hg12(f2(a)) : {g1(f1(a)) == _ : C}; (%hf12(a) : {g1(f1(a)) == g1(_) : C}; {==}))))",
    },
    {
        "law_id": "core_paste_h_3",
        "group": "pasting",
        "proof_class": "core_paste_ii",
        "predicted_status": "PROVED",
        "doc": "3-stage horizontal pasting: f1 == f2, g1 == g2, and h1 == h2 along A -> B -> C -> D compose to h1(g1(f1(a))) == h2(g2(f2(a)))",
        "binders": [
            ("-A", "Data"),
            ("-B", "Type"),
            ("-C", "Type"),
            ("-D", "Type"),
            ("-f1", "A -> B"),
            ("f2", "A -> B"),
            ("-g1", "B -> C"),
            ("-g2", "B -> C"),
            ("-h1", "C -> D"),
            ("-h2", "C -> D"),
        ],
        "hyps": [
            ("hf", "@a:A -> {f1(a) == f2(a) : B}"),
            ("hg", "@b:B -> {g1(b) == g2(b) : C}"),
            ("hh", "@a:A -> {h1(g2(f2(a))) == h2(g2(f2(a))) : D}"),
        ],
        "claim": "@+a:A -> {h1(g1(f1(a))) == h2(g2(f2(a))) : D}",
        "proof": "+a => (%hh(a) : {h1(g1(f1(a))) == _ : D}; (%hg(f2(a)) : {h1(g1(f1(a))) == h1(_) : D}; (%hf(a) : {h1(g1(f1(a))) == h1(g1(_)) : D}; {==})))",
    },
    {
        "law_id": "core_paste_v_obs",
        "group": "pasting",
        "proof_class": "core_paste_ii",
        "predicted_status": "PROVED",
        "doc": "vertical observation pasting across two refinement legs: obs_B(f(a)) == obs_A(a) and obs_C(g(b)) == obs_B(b) compose to obs_C(g(f(a))) == obs_A(a)",
        "binders": [
            ("-A", "Data"),
            ("-B", "Type"),
            ("-C", "Type"),
            ("-V", "Type"),
            ("f", "A -> B"),
            ("-g", "B -> C"),
            ("-obs_A", "A -> V"),
            ("-obs_B", "B -> V"),
            ("-obs_C", "C -> V"),
        ],
        "hyps": [
            ("h1", "@a:A -> {obs_B(f(a)) == obs_A(a) : V}"),
            ("h2", "@b:B -> {obs_C(g(b)) == obs_B(b) : V}"),
        ],
        "claim": "@+a:A -> {obs_C(g(f(a))) == obs_A(a) : V}",
        "proof": "+a => (%h1(a) : {obs_C(g(f(a))) == _ : V}; h2(f(a)))",
    },
    {
        "law_id": "core_paste_square_trans",
        "group": "pasting",
        "proof_class": "core_paste_ii",
        "predicted_status": "PROVED",
        "doc": "adjacent commutative-square pasting: v(f(a)) == f1(u(a)) and w(g(b)) == g1(v(b)) paste to w(g(f(a))) == g1(f1(u(a)))",
        "binders": [
            ("-A", "Data"),
            ("-B", "Type"),
            ("-C", "Type"),
            ("-A1", "Type"),
            ("-B1", "Type"),
            ("-C1", "Type"),
            ("f", "A -> B"),
            ("-g", "B -> C"),
            ("-u", "A -> A1"),
            ("-v", "B -> B1"),
            ("-w", "C -> C1"),
            ("-f1", "A1 -> B1"),
            ("-g1", "B1 -> C1"),
        ],
        "hyps": [
            ("h_left", "@a:A -> {v(f(a)) == f1(u(a)) : B1}"),
            ("h_right", "@b:B -> {w(g(b)) == g1(v(b)) : C1}"),
        ],
        "claim": "@+a:A -> {w(g(f(a))) == g1(f1(u(a))) : C1}",
        "proof": "+a => (%h_left(a) : {w(g(f(a))) == g1(_) : C1}; h_right(f(a)))",
    },
    {
        "law_id": "core_paste_whisker_interchange",
        "group": "pasting",
        "proof_class": "core_paste_ii",
        "predicted_status": "PROVED",
        "doc": "Eckmann-Hilton interchange path (pre-whisker along f1 then post-whisker along g2): g1(f1(a)) == g2(f1(a)) and f1(a) == f2(a) compose to g1(f1(a)) == g2(f2(a))",
        "binders": [
            ("-A", "Data"),
            ("-B", "Type"),
            ("-C", "Type"),
            ("-f1", "A -> B"),
            ("-f2", "A -> B"),
            ("-g1", "B -> C"),
            ("-g2", "B -> C"),
        ],
        "hyps": [
            ("hg1", "@a:A -> {g1(f1(a)) == g2(f1(a)) : C}"),
            ("hf", "@a:A -> {f1(a) == f2(a) : B}"),
        ],
        "claim": "@+a:A -> {g1(f1(a)) == g2(f2(a)) : C}",
        "proof": "+a => (%hf(a) : {g1(f1(a)) == g2(_) : C}; hg1(a))",
    },
)


def render_theory_core_ii_laws() -> str:
    lines = ["import Base", ""]
    for spec in THEORY_CORE_II_SPECS:
        lines.append(f"law {spec['law_id']}:")
        for b_name, b_ty in spec["binders"]:
            lines.append(f"  for {b_name}: {b_ty}")
        for h_name, h_ty in spec["hyps"]:
            lines.append(f"  for {h_name}: {h_ty}")
        lines.append(f"  {spec['claim']}")
        lines.append("")
    return "\n".join(lines)


def render_theory_core_ii_proofs() -> str:
    lines = ["import Base", "import ./LAWS.bend as Laws", ""]
    for spec in THEORY_CORE_II_SPECS:
        lines.append(f"# class {spec['proof_class']}")
        b_names = [b_name.lstrip("+-") for b_name, _ in spec["binders"]]
        h_names = [h_name for h_name, _ in spec["hyps"]]
        params = ", ".join(b_names + h_names)
        lines.append(f"def Laws.{spec['law_id']}({params}):")
        lines.append(f"  {spec['proof']}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. Concrete M3 equivariance & pasting basis specifications
# ---------------------------------------------------------------------------

EQUIVARIANCE_BASIS_LAWS: tuple[dict[str, Any], ...] = (
    {
        "law_id": "basis_equivar_mig_legacy_wait",
        "predicted_status": "PROVED",
        "core_lemma": None,
        "morphism": "M.mig_legacy",
        "step": "M.step_wait",
        "doc": "legacy CSR zeroing migration mig_legacy commutes with step_wait(s, dt)",
    },
    {
        "law_id": "basis_equivar_mig_legacy_send_msg",
        "predicted_status": "PROVED",
        "core_lemma": None,
        "morphism": "M.mig_legacy",
        "step": "M.step_sendMessage",
        "doc": "legacy CSR zeroing migration mig_legacy commutes with step_sendMessage(s, who)",
    },
    {
        "law_id": "basis_equivar_mig_eta2_wait",
        "predicted_status": "PROVED",
        "core_lemma": None,
        "morphism": "M.mig_eta2",
        "step": "M.step_wait",
        "doc": "eta2 last-entry CSR backfill migration mig_eta2(_, root) commutes with step_wait(s, dt)",
    },
    {
        "law_id": "basis_equivar_mig_compose_wait",
        "predicted_status": "PROVED",
        "core_lemma": "core_equivar_whisker",
        "morphism": "M.mig_eta2(M.mig_legacy(_), root)",
        "step": "M.step_wait",
        "doc": "composed migration mig_eta2(mig_legacy(_), root) commutes with step_wait(s, dt) via core_equivar_whisker",
    },
)

PASTING_BASIS_LAWS: tuple[dict[str, Any], ...] = (
    {
        "law_id": "basis_paste_lci_mig_legacy",
        "predicted_status": "PROVED",
        "core_lemma": None,
        "observer": "M.lci_of",
        "morphism": "M.mig_legacy",
        "doc": "last committed index observer lci_of is preserved by mig_legacy(s)",
    },
    {
        "law_id": "basis_paste_lci_mig_eta2",
        "predicted_status": "PROVED",
        "core_lemma": None,
        "observer": "M.lci_of",
        "morphism": "M.mig_eta2",
        "doc": "last committed index observer lci_of is preserved by mig_eta2(s, root)",
    },
    {
        "law_id": "basis_paste_lci_mig_chain",
        "predicted_status": "PROVED",
        "core_lemma": "core_paste_v_obs",
        "observer": "M.lci_of",
        "morphism": "M.mig_eta2(M.mig_legacy(_), root)",
        "doc": "vertical observation pasting (core_paste_v_obs) preserves lci_of across mig_eta2(mig_legacy(s), root)",
    },
    {
        "law_id": "basis_paste_tags_mig_chain",
        "predicted_status": "PROVED",
        "core_lemma": "core_paste_v_obs",
        "observer": "M.tags_ok",
        "morphism": "M.mig_eta2(M.mig_legacy(_), root)",
        "doc": "vertical observation pasting (core_paste_v_obs) preserves tags_ok across mig_eta2(mig_legacy(s), root)",
    },
)


def equivariance_laws_bend() -> str:
    return "\n".join([
        "# GENERATED by holon.gen.basis for M3 equivariance basis; do not edit.",
        "import Base",
        "import ../../../M1/model/morph_rollup.bend as M",
        "",
        "law basis_equivar_mig_legacy_wait:",
        "  for s: M.HSt",
        "  for +dt: Nat",
        "  {M.mig_legacy(M.step_wait(s, dt)) == M.step_wait(M.mig_legacy(s), dt) : M.HSt}",
        "",
        "law basis_equivar_mig_legacy_send_msg:",
        "  for s: M.HSt",
        "  for +who: Nat",
        "  {M.mig_legacy(M.step_sendMessage(s, who)) == M.step_sendMessage(M.mig_legacy(s), who) : M.HSt}",
        "",
        "law basis_equivar_mig_eta2_wait:",
        "  for s: M.HSt",
        "  for +dt: Nat",
        "  for +root: Nat",
        "  {M.mig_eta2(M.step_wait(s, dt), root) == M.step_wait(M.mig_eta2(s, root), dt) : M.HSt}",
        "",
        "law basis_equivar_mig_compose_wait:",
        "  for +s: M.HSt",
        "  for +dt: Nat",
        "  for +root: Nat",
        "  {M.mig_eta2(M.mig_legacy(M.step_wait(s, dt)), root) == M.step_wait(M.mig_eta2(M.mig_legacy(s), root), dt) : M.HSt}",
        "",
    ])


def equivariance_proof_bend() -> str:
    return "\n".join([
        "# GENERATED by holon.gen.basis; untrusted, accepted only if Bend checks it.",
        "import Base",
        "import ./LAWS.bend as Laws",
        "import ../../core/PROOF.bend as CP",
        "import ../../core/LAWS.bend as C",
        "import ../../../M1/model/morph_rollup.bend as M",
        "",
        "def Laws.basis_equivar_mig_legacy_wait(s, dt):",
        "  match s:",
        "    case M.HSt{t, lfi, inch, bc, rri, paused, W, F, D, qlen, qpend, enq, active, chals, fsr, chs, win, s_csr, s_bd, s_bvh, s_tag, log}:",
        "      {==}",
        "",
        "def Laws.basis_equivar_mig_legacy_send_msg(s, who):",
        "  match s:",
        "    case M.HSt{t, lfi, inch, bc, rri, paused, W, F, D, qlen, qpend, enq, active, chals, fsr, chs, win, s_csr, s_bd, s_bvh, s_tag, log}:",
        "      {==}",
        "",
        "def Laws.basis_equivar_mig_eta2_wait(s, dt, root):",
        "  match s:",
        "    case M.HSt{t, lfi, inch, bc, rri, paused, W, F, D, qlen, qpend, enq, active, chals, fsr, chs, win, s_csr, s_bd, s_bvh, s_tag, log}:",
        "      {==}",
        "",
        "def Laws.basis_equivar_mig_compose_wait(s, dt, root):",
        "  C.core_equivar_whisker(M.HSt, M.HSt, M.HSt, x => M.mig_legacy(x), y => M.mig_eta2(y, root), x => M.step_wait(x, dt), y => M.step_wait(y, dt), z => M.step_wait(z, dt), x => Laws.basis_equivar_mig_legacy_wait(x, dt), y => Laws.basis_equivar_mig_eta2_wait(y, dt, root))(s)",
        "",
    ])


def pasting_laws_bend() -> str:
    return "\n".join([
        "# GENERATED by holon.gen.basis for M3 pasting basis; do not edit.",
        "import Base",
        "import ../../../M1/model/morph_rollup.bend as M",
        "",
        "law basis_paste_lci_mig_legacy:",
        "  for s: M.HSt",
        "  {M.lci_of(M.mig_legacy(s)) == M.lci_of(s) : Nat}",
        "",
        "law basis_paste_lci_mig_eta2:",
        "  for s: M.HSt",
        "  for +root: Nat",
        "  {M.lci_of(M.mig_eta2(s, root)) == M.lci_of(s) : Nat}",
        "",
        "law basis_paste_lci_mig_chain:",
        "  for +s: M.HSt",
        "  for +root: Nat",
        "  {M.lci_of(M.mig_eta2(M.mig_legacy(s), root)) == M.lci_of(s) : Nat}",
        "",
        "law basis_paste_tags_mig_chain:",
        "  for +s: M.HSt",
        "  for +root: Nat",
        "  {M.tags_ok(M.mig_eta2(M.mig_legacy(s), root)) == M.tags_ok(s) : Bool}",
        "",
    ])


def pasting_proof_bend() -> str:
    return "\n".join([
        "# GENERATED by holon.gen.basis; untrusted, accepted only if Bend checks it.",
        "import Base",
        "import ./LAWS.bend as Laws",
        "import ../../core/PROOF.bend as CP",
        "import ../../core/LAWS.bend as C",
        "import ../../../M1/model/morph_rollup.bend as M",
        "",
        "def len_zero_csr(es: List<&2, M.HEntry>) -> {List.length(&2, M.HEntry, M.b_zero_csr(es)) == List.length(&2, M.HEntry, es) : Nat}:",
        "  match es:",
        "    case Nil{}:",
        "      {==}",
        "    case Con{e, t}:",
        "      match e:",
        "        case M.HEntry{ver, tot, n, hb, prev, post, lbn, csr, bvh, tag, bdo, bdf, bdn, bds}:",
        "          (%len_zero_csr(t) : {1n+List.length(&2, M.HEntry, M.b_zero_csr(t)) == 1n+_ : Nat}; {==})",
        "",
        "def len_set_last_csr(es: List<&2, M.HEntry>, +r: Nat) -> {List.length(&2, M.HEntry, M.b_set_last_csr(es, r)) == List.length(&2, M.HEntry, es) : Nat}:",
        "  match es:",
        "    case Nil{}:",
        "      {==}",
        "    case Con{e, t}:",
        "      match e:",
        "        case M.HEntry{ver, tot, n, hb, prev, post, lbn, csr, bvh, tag, bdo, bdf, bdn, bds}:",
        "          match t:",
        "            case Nil{}:",
        "              {==}",
        "            case Con{e2, t2}:",
        "              (%len_set_last_csr(Con{e2, t2}, r) : {1n+List.length(&2, M.HEntry, M.b_set_last_csr(Con{e2, t2}, r)) == 1n+_ : Nat}; {==})",
        "",
        "def len_ite_set_last_csr(c: Bool, +es: List<&2, M.HEntry>, +r: Nat) -> {List.length(&2, M.HEntry, M.ite(List<&2, M.HEntry>, c, M.b_set_last_csr(es, r), es)) == List.length(&2, M.HEntry, es) : Nat}:",
        "  match c:",
        "    case True{}:",
        "      len_set_last_csr(es, r)",
        "    case False{}:",
        "      {==}",
        "",
        "def tags_zero_csr(es: List<&2, M.HEntry>) -> {M.b_tags_exact(M.b_zero_csr(es)) == M.b_tags_exact(es) : Bool}:",
        "  match es:",
        "    case Nil{}:",
        "      {==}",
        "    case Con{e, t}:",
        "      match e:",
        "        case M.HEntry{+ver, tot, n, hb, prev, post, lbn, csr, bvh, +tag, bdo, bdf, bdn, bds}:",
        "          (%tags_zero_csr(t) : {Bool.and(M.eq_bool(Nat.is_eq(ver, 2n), Nat.is_eq(tag, 2n)), M.b_tags_exact(M.b_zero_csr(t))) == Bool.and(M.eq_bool(Nat.is_eq(ver, 2n), Nat.is_eq(tag, 2n)), _) : Bool}; {==})",
        "",
        "def tags_set_last_csr(es: List<&2, M.HEntry>, +r: Nat) -> {M.b_tags_exact(M.b_set_last_csr(es, r)) == M.b_tags_exact(es) : Bool}:",
        "  match es:",
        "    case Nil{}:",
        "      {==}",
        "    case Con{e, t}:",
        "      match e:",
        "        case M.HEntry{+ver, tot, n, hb, prev, post, lbn, csr, bvh, +tag, bdo, bdf, bdn, bds}:",
        "          match t:",
        "            case Nil{}:",
        "              {==}",
        "            case Con{e2, t2}:",
        "              (%tags_set_last_csr(Con{e2, t2}, r) : {Bool.and(M.eq_bool(Nat.is_eq(ver, 2n), Nat.is_eq(tag, 2n)), M.b_tags_exact(M.b_set_last_csr(Con{e2, t2}, r))) == Bool.and(M.eq_bool(Nat.is_eq(ver, 2n), Nat.is_eq(tag, 2n)), _) : Bool}; {==})",
        "",
        "def tags_ite_set_last_csr(c: Bool, +es: List<&2, M.HEntry>, +r: Nat) -> {M.b_tags_exact(M.ite(List<&2, M.HEntry>, c, M.b_set_last_csr(es, r), es)) == M.b_tags_exact(es) : Bool}:",
        "  match c:",
        "    case True{}:",
        "      tags_set_last_csr(es, r)",
        "    case False{}:",
        "      {==}",
        "",
        "def tags_mig_legacy(s: M.HSt) -> {M.tags_ok(M.mig_legacy(s)) == M.tags_ok(s) : Bool}:",
        "  match s:",
        "    case M.HSt{t, lfi, inch, bc, rri, paused, W, F, D, qlen, qpend, enq, active, chals, fsr, chs, win, s_csr, s_bd, s_bvh, s_tag, log}:",
        "      tags_zero_csr(win)",
        "",
        "def tags_mig_eta2(s: M.HSt, +root: Nat) -> {M.tags_ok(M.mig_eta2(s, root)) == M.tags_ok(s) : Bool}:",
        "  match s:",
        "    case M.HSt{t, lfi, inch, bc, rri, paused, W, F, D, qlen, qpend, enq, active, chals, fsr, chs, +win, s_csr, s_bd, s_bvh, s_tag, log}:",
        "      tags_ite_set_last_csr(Nat.is_eq(M.g_Entry_csr(M.last_d(M.HEntry, win, M.empty_entry())), 0n), win, root)",
        "",
        "def Laws.basis_paste_lci_mig_legacy(s):",
        "  match s:",
        "    case M.HSt{t, +lfi, inch, bc, rri, paused, W, F, D, qlen, qpend, enq, active, chals, fsr, chs, +win, s_csr, s_bd, s_bvh, s_tag, log}:",
        "      (%len_zero_csr(win) : {Nat.sub(Nat.add(lfi, List.length(&2, M.HEntry, M.b_zero_csr(win))), 1n) == Nat.sub(Nat.add(lfi, _), 1n) : Nat}; {==})",
        "",
        "def Laws.basis_paste_lci_mig_eta2(s, root):",
        "  match s:",
        "    case M.HSt{t, +lfi, inch, bc, rri, paused, W, F, D, qlen, qpend, enq, active, chals, fsr, chs, +win, s_csr, s_bd, s_bvh, s_tag, log}:",
        "      (%len_ite_set_last_csr(Nat.is_eq(M.g_Entry_csr(M.last_d(M.HEntry, win, M.empty_entry())), 0n), win, root) : {Nat.sub(Nat.add(lfi, List.length(&2, M.HEntry, M.ite(List<&2, M.HEntry>, Nat.is_eq(M.g_Entry_csr(M.last_d(M.HEntry, win, M.empty_entry())), 0n), M.b_set_last_csr(win, root), win))), 1n) == Nat.sub(Nat.add(lfi, _), 1n) : Nat}; {==})",
        "",
        "def Laws.basis_paste_lci_mig_chain(s, root):",
        "  C.core_paste_v_obs(M.HSt, M.HSt, M.HSt, Nat, x => M.mig_legacy(x), y => M.mig_eta2(y, root), x => M.lci_of(x), y => M.lci_of(y), z => M.lci_of(z), x => Laws.basis_paste_lci_mig_legacy(x), y => Laws.basis_paste_lci_mig_eta2(y, root))(s)",
        "",
        "def Laws.basis_paste_tags_mig_chain(s, root):",
        "  C.core_paste_v_obs(M.HSt, M.HSt, M.HSt, Bool, x => M.mig_legacy(x), y => M.mig_eta2(y, root), x => M.tags_ok(x), y => M.tags_ok(y), z => M.tags_ok(z), x => tags_mig_legacy(x), y => tags_mig_eta2(y, root))(s)",
        "",
    ])


# ---------------------------------------------------------------------------
# 3. Promoted PROVED laws across M0..M3 (92 total: 5 M0 + 8 M1 + 6 M2 + 73 M3)
# ---------------------------------------------------------------------------

def promoted_laws_by_milestone(root: Path) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for ms in ("M0", "M1", "M2", "M3"):
        reg = _load_json(root / "laws" / ms / "REGISTRY.json")
        entries: list[dict[str, Any]] = []
        for lid in sorted(reg["statements"]):
            rec_p = root / "results" / ms / f"{lid}.json"
            if not rec_p.is_file():
                continue
            rec = _load_json(rec_p)
            if rec.get("status") != "PROVED":
                continue
            law = _load_json(root / "laws" / ms / f"{lid}.json")
            gen_name = None
            for att in rec.get("attempts") or []:
                if att.get("result") in ("PROVED", "accepted") or (
                    att.get("kind") == "proof" and att.get("exit_code") == 0
                ):
                    gen_name = att.get("generator") or att.get("kind")
                    break
            lean_mod = (
                f"gen/M0/lean/{lid}.lean"
                if ms == "M0"
                else f"gen/M3/lean/Holon/{ms}/{lid}.lean"
            )
            entries.append({
                "law_id": lid,
                "milestone": ms,
                "ir_version": law.get("ir_version", "holon-ir/0.1"),
                "rule": law.get("rule"),
                "facts": law.get("facts"),
                "statement_hash": rec["statement_hash"],
                "bend_generator": gen_name,
                "prior_independence_class": rec.get("independence_class"),
                "target_independence_class": "I2",
                "target_kernel": {
                    "name": "lean4",
                    "version": LEAN_TOOLCHAIN_VERSION,
                    "role": "second-independent",
                    "result": "checked",
                },
                "lean_module": lean_mod,
                "lean_theorem": lid,
            })
        out[ms] = entries
    return out


# ---------------------------------------------------------------------------
# 4. Negative canaries (5 total across theory_core_ii, equivariance, pasting, lean)
# ---------------------------------------------------------------------------

CANARY_LEAN_SOURCE: str = "\n".join([
    "/-!",
    "Canary: flipped claim on core_equivar_compose in Lean 4.",
    "Lean 4 core only, no imports.",
    "-/",
    "theorem canary_lean_flipped_claim",
    "    (A B : Type) (f : A → B) (s1 s2 : A → A) (t1 t2 : B → B)",
    "    (h1 : ∀ x : A, f (s1 x) = t1 (f x))",
    "    (h2 : ∀ x : A, f (s2 x) = t2 (f x)) :",
    "    ∀ a : A, f (s1 (s2 a)) = t2 (t1 (f a)) -- holon:claim",
    "    := by",
    "  intro a",
    "  rw [h1 (s2 a), h2 a]",
    "  rfl",
    "",
])


def canary_lean_source() -> str:
    return CANARY_LEAN_SOURCE


CANARY_SPECS: tuple[dict[str, Any], ...] = (
    {
        "canary_id": "canary_equivar_compose_swapped",
        "group": "theory_core_ii",
        "predicted_status": "REFUTED",
        "doc": "swapping the target step composition order t1(t2(f(a))) to t2(t1(f(a))) in core_equivar_compose without commutativity of t1 and t2 must fail both Bend kernels",
        "laws_bend": "\n".join([
            "import Base",
            "law canary_equivar_compose_swapped:",
            "  for -A: Data",
            "  for -B: Type",
            "  for -f: A -> B",
            "  for -s1: A -> A",
            "  for s2: A -> A",
            "  for -t1: B -> B",
            "  for -t2: B -> B",
            "  for h1: @x:A -> {f(s1(x)) == t1(f(x)) : B}",
            "  for h2: @x:A -> {f(s2(x)) == t2(f(x)) : B}",
            "  @+a:A -> {f(s1(s2(a))) == t2(t1(f(a))) : B}",
            "",
        ]),
        "proof_bend": "\n".join([
            "import Base",
            "import ./LAWS.bend as Laws",
            "def Laws.canary_equivar_compose_swapped(A, B, f, s1, s2, t1, t2, h1, h2):",
            "  +a => (%h2(a) : {f(s1(s2(a))) == t1(_) : B}; h1(s2(a)))",
            "",
        ]),
    },
    {
        "canary_id": "canary_paste_grid_2x2_missing_v",
        "group": "theory_core_ii",
        "predicted_status": "REFUTED",
        "doc": "dropping the second vertical 2-cell hg23 (g2 == g3) in core_paste_grid_2x2 while still claiming g1(f1(a)) == g3(f3(a)) must fail both Bend kernels",
        "laws_bend": "\n".join([
            "import Base",
            "law canary_paste_grid_2x2_missing_v:",
            "  for -A: Data",
            "  for -B: Type",
            "  for -C: Type",
            "  for -f1: A -> B",
            "  for f2: A -> B",
            "  for -f3: A -> B",
            "  for -g1: B -> C",
            "  for -g2: B -> C",
            "  for -g3: B -> C",
            "  for hf12: @a:A -> {f1(a) == f2(a) : B}",
            "  for hf23: @a:A -> {f2(a) == f3(a) : B}",
            "  for hg12: @b:B -> {g1(b) == g2(b) : C}",
            "  @+a:A -> {g1(f1(a)) == g3(f3(a)) : C}",
            "",
        ]),
        "proof_bend": "\n".join([
            "import Base",
            "import ./LAWS.bend as Laws",
            "def Laws.canary_paste_grid_2x2_missing_v(A, B, C, f1, f2, f3, g1, g2, g3, hf12, hf23, hg12):",
            "  +a => (%hf23(a) : {g1(f1(a)) == g2(_) : C}; (%hg12(f2(a)) : {g1(f1(a)) == _ : C}; (%hf12(a) : {g1(f1(a)) == g1(_) : C}; {==})))",
            "",
        ]),
    },
    {
        "canary_id": "canary_equivar_mig_eta2_unmigrated_rhs",
        "group": "equivariance",
        "predicted_status": "REFUTED",
        "doc": "omitting mig_eta2 on the RHS of step_wait equivariance (claiming mig_eta2(step_wait(s, dt), root) == step_wait(s, dt)) must fail both Bend kernels",
        "laws_bend": "\n".join([
            "import Base",
            "import ../../../M1/model/morph_rollup.bend as M",
            "law canary_equivar_mig_eta2_unmigrated_rhs:",
            "  for s: M.HSt",
            "  for +dt: Nat",
            "  for +root: Nat",
            "  {M.mig_eta2(M.step_wait(s, dt), root) == M.step_wait(s, dt) : M.HSt}",
            "",
        ]),
        "proof_bend": "\n".join([
            "import Base",
            "import ./LAWS.bend as Laws",
            "import ../../../M1/model/morph_rollup.bend as M",
            "def Laws.canary_equivar_mig_eta2_unmigrated_rhs(s, dt, root):",
            "  match s:",
            "    case M.HSt{t, lfi, inch, bc, rri, paused, W, F, D, qlen, qpend, enq, active, chals, fsr, chs, win, s_csr, s_bd, s_bvh, s_tag, log}:",
            "      {==}",
            "",
        ]),
    },
    {
        "canary_id": "canary_paste_csr_last_mig_legacy",
        "group": "pasting",
        "predicted_status": "REFUTED",
        "doc": "claiming csr_last(mig_legacy(s)) == csr_last(s) (false because mig_legacy zeros all entry CSRs) must fail both Bend kernels",
        "laws_bend": "\n".join([
            "import Base",
            "import ../../../M1/model/morph_rollup.bend as M",
            "law canary_paste_csr_last_mig_legacy:",
            "  for s: M.HSt",
            "  {M.csr_last(M.mig_legacy(s)) == M.csr_last(s) : Nat}",
            "",
        ]),
        "proof_bend": "\n".join([
            "import Base",
            "import ./LAWS.bend as Laws",
            "import ../../../M1/model/morph_rollup.bend as M",
            "def Laws.canary_paste_csr_last_mig_legacy(s):",
            "  match s:",
            "    case M.HSt{t, lfi, inch, bc, rri, paused, W, F, D, qlen, qpend, enq, active, chals, fsr, chs, win, s_csr, s_bd, s_bvh, s_tag, log}:",
            "      {==}",
            "",
        ]),
    },
    {
        "canary_id": "canary_lean_flipped_claim",
        "group": "lean",
        "family": "lean",
        "kind": "flipped_claim",
        "predicted_status": "REFUTED",
        "expected_verdict": "REJECTED",
        "doc": "Mutate a promoted Lean 4 theorem's #holon:claim equality to a false equality while keeping its proof script; Lean 4 must reject with a semantic type/tactic failure, not a syntax/parse error.",
        "lean_source": CANARY_LEAN_SOURCE,
    },
)


def theory_core_ii_doc(root: Path) -> dict[str, Any]:
    inputs = [
        {"path": rel, "sha256": _sha256(root / rel)}
        for rel in sorted(INPUT_PATHS)
    ]
    promoted = promoted_laws_by_milestone(root)
    m0_cnt = len(promoted["M0"])
    m1_cnt = len(promoted["M1"])
    m2_cnt = len(promoted["M2"])
    m3_cnt = len(promoted["M3"])
    total_promoted = m0_cnt + m1_cnt + m2_cnt + m3_cnt

    return {
        "doc": (
            "I43 prereg sidecar (BUILD_PLAN I43 'Theory core II; Lean for the "
            "promoted set' and whitepaper sections 6.1-6.2, 6.4, 8.8, Q14c). "
            "Computed at prereg by tests_m3/_i43.py::theory_core_ii_doc "
            "independently of holon/ from the frozen inputs listed with their "
            "sha256. Records: (1) the 10 polymorphic Bend 2 laws in "
            "THEORY_CORE_II (5 equivariance laws and 5 2-cell pasting laws); "
            "(2) the 4 concrete M3 equivariance basis laws in "
            "gen/M3/basis/equivariance/ and 4 concrete M3 pasting basis laws in "
            "gen/M3/basis/pasting/ over the M1 morph_rollup model; (3) the 92 "
            "PROVED laws across M0..M3 (5 M0 + 8 M1 + 6 M2 + 73 M3) promoted "
            "to independence_class I2 via Lean 4.34.0 verification in "
            "gen/M3/lean/ and results/M3/lean.json with axioms within "
            "{propext, Quot.sound}; (4) the 5 negative canaries across "
            "theory_core_ii, equivariance, pasting, and lean, all predicted "
            "REFUTED under bend / bend --verdict or holon.lean.check_text. "
            "The build never reads this file; the tests recompute and compare "
            "against it."
        ),
        "theory_core_ii_version": THEORY_CORE_II_VERSION,
        "lean_toolchain_version": LEAN_TOOLCHAIN_VERSION,
        "allowed_axioms": list(ALLOWED_AXIOMS),
        "inputs": inputs,
        "theory_core_ii": {
            "count": len(THEORY_CORE_II_SPECS),
            "groups": {
                "equivariance": [
                    s["law_id"]
                    for s in THEORY_CORE_II_SPECS
                    if s["group"] == "equivariance"
                ],
                "pasting": [
                    s["law_id"]
                    for s in THEORY_CORE_II_SPECS
                    if s["group"] == "pasting"
                ],
            },
            "laws": [
                {
                    "law_id": s["law_id"],
                    "group": s["group"],
                    "proof_class": s["proof_class"],
                    "predicted_status": s["predicted_status"],
                    "doc": s["doc"],
                    "binders": [[b_name, b_ty] for b_name, b_ty in s["binders"]],
                    "hyps": [[h_name, h_ty] for h_name, h_ty in s["hyps"]],
                    "claim": s["claim"],
                    "proof": s["proof"],
                }
                for s in THEORY_CORE_II_SPECS
            ],
        },
        "basis_families": {
            "equivariance": {
                "model_path": "gen/M1/model/morph_rollup.bend",
                "laws_path": "gen/M3/basis/equivariance/LAWS.bend",
                "proof_path": "gen/M3/basis/equivariance/PROOF.bend",
                "count": len(EQUIVARIANCE_BASIS_LAWS),
                "laws": [dict(x) for x in EQUIVARIANCE_BASIS_LAWS],
            },
            "pasting": {
                "model_path": "gen/M1/model/morph_rollup.bend",
                "laws_path": "gen/M3/basis/pasting/LAWS.bend",
                "proof_path": "gen/M3/basis/pasting/PROOF.bend",
                "count": len(PASTING_BASIS_LAWS),
                "laws": [dict(x) for x in PASTING_BASIS_LAWS],
            },
        },
        "lean_promotion": {
            "project_dir": "gen/M3/lean",
            "report_path": "results/M3/lean.json",
            "toolchain": f"leanprover/lean4:v{LEAN_TOOLCHAIN_VERSION}",
            "allowed_axioms": list(ALLOWED_AXIOMS),
            "counts_by_milestone": {
                "M0": m0_cnt,
                "M1": m1_cnt,
                "M2": m2_cnt,
                "M3": m3_cnt,
            },
            "total_promoted_laws": total_promoted,
            "theory_core_ii_lean_theorems": [
                s["law_id"] for s in THEORY_CORE_II_SPECS
            ],
            "basis_lean_theorems": [
                *(s["law_id"] for s in EQUIVARIANCE_BASIS_LAWS),
                *(s["law_id"] for s in PASTING_BASIS_LAWS),
            ],
            "milestones": promoted,
        },
        "canaries": [
            {
                "canary_id": c["canary_id"],
                "group": c["group"],
                "predicted_status": c["predicted_status"],
                "doc": c["doc"],
            }
            for c in CANARY_SPECS
        ],
        "summary": {
            "m2_core_laws": 31,
            "theory_core_i_laws": 12,
            "theory_core_ii_laws": len(THEORY_CORE_II_SPECS),
            "m3_core_total_laws": 31 + 12 + len(THEORY_CORE_II_SPECS),
            "equivariance_basis_laws": len(EQUIVARIANCE_BASIS_LAWS),
            "pasting_basis_laws": len(PASTING_BASIS_LAWS),
            "total_new_bend_laws": (
                len(THEORY_CORE_II_SPECS)
                + len(EQUIVARIANCE_BASIS_LAWS)
                + len(PASTING_BASIS_LAWS)
            ),
            "promoted_m0_laws": m0_cnt,
            "promoted_m1_laws": m1_cnt,
            "promoted_m2_laws": m2_cnt,
            "promoted_m3_laws": m3_cnt,
            "total_promoted_i2_laws": total_promoted,
            "canaries_refuted": len(CANARY_SPECS),
        },
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = root / "spec/M3/lib/theory_core_ii.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = theory_core_ii_doc(root)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
