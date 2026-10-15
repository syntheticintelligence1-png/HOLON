"""I42 prereg computation: Theory core I (whiskering, domain locality, spanning-tree basis sufficiency).

Independently computes the preregistration sidecar
``spec/M3/lib/theory_core_i.json`` from the frozen M0/M2/M3 inputs and diagrams:
  - the 12 polymorphic Bend 2 laws in ``THEORY_CORE_I`` (whiskering, 2-cell
    pasting, domain-locality lifting, and spanning-tree cycle-basis
    reduction),
  - the M2 ``morph_header`` cycle-basis sufficiency specification
    (``E = 4, V = 3, kappa = 1, rank = 2``; tree edges ``CODEC.dec_go``,
    ``CODEC.enc_go_v0``; non-tree edges ``CODEC.enc_go_v1``, ``CODEC.enc_sol``;
    3 basis laws ``basis_sufficient_header_v0``, ``basis_sufficient_header_v1``,
    ``basis_sufficient_header``),
  - the M3 ``header_length`` cycle-basis sufficiency specification
    (``E = 20, V = 17, kappa = 1, rank = 4``; 16 spanning-tree edges and 4
    fundamental-cycle non-tree edges; 5 basis laws
    ``basis_hl_gen_blob_hashes_hash``, ``basis_hl_gen_blob_versioned_hash``,
    ``basis_hl_gen_batch_header_v1_bytes``, ``basis_hl_gen_load_sol``,
    ``basis_sufficient_header_length``),
  - the 34 congruence-derived round-trip laws (2 M0 ``L_rt_go_v{0,1}`` on the
    pinned ``sequencerSetVerifyHash == 0`` domain + 32 M3 ``L_par_rt_enc_sol_*``
    laws that factor through ``L_par_cc_*_pinned`` + tree-basis ``L_par_rt_*``
    via ``core_whisker_post``), and their baseline ``open_refl`` line-count
    comparison,
  - the 7 negative canaries across the 4 theorem groups, all predicted
    ``REFUTED`` under both ``bend`` and ``bend --verdict``.

Must not import ``holon.gen.basis`` or read ``gen/M3/basis/`` or
``results/M3/basis.json``.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tests_m3 import _i24


THEORY_CORE_I_VERSION = "holon-i42-theory-core-i/0.1"

INPUT_PATHS: tuple[str, ...] = (
    "gen/M0/model/morph_header.bend",
    "gen/M0/L_par_hdr_v0/LAWS.bend",
    "gen/M0/L_par_hdr_v1/LAWS.bend",
    "gen/M0/L_rt_go_v0/LAWS.bend",
    "gen/M0/L_rt_go_v1/LAWS.bend",
    "gen/M2/diagram/morph_header.json",
    "gen/M3/diagram/header_length.json",
    "gen/M3/model/header_length.bend",
    "spec/M3/lib/par_basis.json",
    "spec/M3/lib/par_lossy.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# 1. THEORY_CORE_I: 12 polymorphic Bend 2 laws (whiskering, pasting, locality,
#    spanning-tree basis sufficiency)
# ---------------------------------------------------------------------------

THEORY_CORE_I_SPECS: tuple[dict[str, Any], ...] = (
    {
        "law_id": "core_whisker_pre",
        "group": "whisker",
        "proof_class": "core_whisker",
        "predicted_status": "PROVED",
        "doc": "pre-whiskering: if p(a) == q(a) for all a:A, then p(r(x)) == q(r(x)) for all x:X",
        "binders": [
            ("-X", "Type"),
            ("-A", "Type"),
            ("-B", "Type"),
            ("r", "X -> A"),
            ("-p", "A -> B"),
            ("-q", "A -> B"),
        ],
        "hyps": [
            ("e", "@a:A -> {p(a) == q(a) : B}"),
        ],
        "claim": "@x:X -> {p(r(x)) == q(r(x)) : B}",
        "proof": "x => e(r(x))",
    },
    {
        "law_id": "core_whisker_post",
        "group": "whisker",
        "proof_class": "core_whisker",
        "predicted_status": "PROVED",
        "doc": "post-whiskering: if p(a) == q(a) for all a:A, then l(p(a)) == l(q(a)) for all a:A",
        "binders": [
            ("-A", "Type"),
            ("-B", "Type"),
            ("-Y", "Type"),
            ("-p", "A -> B"),
            ("-q", "A -> B"),
            ("-l", "B -> Y"),
        ],
        "hyps": [
            ("e", "@a:A -> {p(a) == q(a) : B}"),
        ],
        "claim": "@a:A -> {l(p(a)) == l(q(a)) : Y}",
        "proof": "a => (%e(a) : {l(p(a)) == l(_) : Y}; {==})",
    },
    {
        "law_id": "core_whisker_both",
        "group": "whisker",
        "proof_class": "core_whisker",
        "predicted_status": "PROVED",
        "doc": "two-sided whiskering: if p(a) == q(a) for all a:A, then l(p(r(x))) == l(q(r(x))) for all x:X",
        "binders": [
            ("-X", "Type"),
            ("-A", "Type"),
            ("-B", "Type"),
            ("-Y", "Type"),
            ("r", "X -> A"),
            ("-p", "A -> B"),
            ("-q", "A -> B"),
            ("-l", "B -> Y"),
        ],
        "hyps": [
            ("e", "@a:A -> {p(a) == q(a) : B}"),
        ],
        "claim": "@x:X -> {l(p(r(x))) == l(q(r(x))) : Y}",
        "proof": "x => (%e(r(x)) : {l(p(r(x))) == l(_) : Y}; {==})",
    },
    {
        "law_id": "core_walk_2",
        "group": "pasting",
        "proof_class": "core_paste",
        "predicted_status": "PROVED",
        "doc": "2-step walk pasting: step 2-cells f1(a) == f2(a) and g1(f2(a)) == g2(f2(a)) along a 2-step walk compose to g1(f1(a)) == g2(f2(a))",
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
            ("e1", "@a:A -> {f1(a) == f2(a) : B}"),
            ("e2", "@a:A -> {g1(f2(a)) == g2(f2(a)) : C}"),
        ],
        "claim": "@+a:A -> {g1(f1(a)) == g2(f2(a)) : C}",
        "proof": "+a => (%e2(a) : {g1(f1(a)) == _ : C}; (%e1(a) : {g1(f1(a)) == g1(_) : C}; {==}))",
    },
    {
        "law_id": "core_walk_3",
        "group": "pasting",
        "proof_class": "core_paste",
        "predicted_status": "PROVED",
        "doc": "3-step walk pasting: step 2-cells along a 3-step walk compose to h1(g1(f1(a))) == h2(g2(f2(a)))",
        "binders": [
            ("-A", "Data"),
            ("-B", "Type"),
            ("-C", "Type"),
            ("-D", "Type"),
            ("-f1", "A -> B"),
            ("-f2", "A -> B"),
            ("-g1", "B -> C"),
            ("-g2", "B -> C"),
            ("-h1", "C -> D"),
            ("-h2", "C -> D"),
        ],
        "hyps": [
            ("e1", "@a:A -> {f1(a) == f2(a) : B}"),
            ("e2", "@a:A -> {g1(f2(a)) == g2(f2(a)) : C}"),
            ("e3", "@a:A -> {h1(g2(f2(a))) == h2(g2(f2(a))) : D}"),
        ],
        "claim": "@+a:A -> {h1(g1(f1(a))) == h2(g2(f2(a))) : D}",
        "proof": "+a => (%e3(a) : {h1(g1(f1(a))) == _ : D}; (%e2(a) : {h1(g1(f1(a))) == h1(_) : D}; (%e1(a) : {h1(g1(f1(a))) == h1(g1(_)) : D}; {==})))",
    },
    {
        "law_id": "core_square_paste_h",
        "group": "pasting",
        "proof_class": "core_paste",
        "predicted_status": "PROVED",
        "doc": "horizontal 2-cell pasting: if f1 == f2 on A and g1 == g2 on B, then g1(f1(a)) == g2(f2(a))",
        "binders": [
            ("-A", "Data"),
            ("-B", "Type"),
            ("-C", "Type"),
            ("f1", "A -> B"),
            ("-f2", "A -> B"),
            ("-g1", "B -> C"),
            ("-g2", "B -> C"),
        ],
        "hyps": [
            ("e1", "@a:A -> {f1(a) == f2(a) : B}"),
            ("e2", "@b:B -> {g1(b) == g2(b) : C}"),
        ],
        "claim": "@+a:A -> {g1(f1(a)) == g2(f2(a)) : C}",
        "proof": "+a => (%e1(a) : {g1(f1(a)) == g2(_) : C}; e2(f1(a)))",
    },
    {
        "law_id": "core_square_paste_v",
        "group": "pasting",
        "proof_class": "core_paste",
        "predicted_status": "PROVED",
        "doc": "vertical 2-cell pasting (transitivity of parallel walks): if p == q and q == s on A, then p == s on A",
        "binders": [
            ("-A", "Data"),
            ("-B", "Type"),
            ("-p", "A -> B"),
            ("-q", "A -> B"),
            ("-s", "A -> B"),
        ],
        "hyps": [
            ("e1", "@a:A -> {p(a) == q(a) : B}"),
            ("e2", "@a:A -> {q(a) == s(a) : B}"),
        ],
        "claim": "@+a:A -> {p(a) == s(a) : B}",
        "proof": "+a => (%e2(a) : {p(a) == _ : B}; e1(a))",
    },
    {
        "law_id": "core_domain_local_pre",
        "group": "domain_locality",
        "proof_class": "core_domain_local",
        "predicted_status": "PROVED",
        "doc": "domain-local pre-restriction: a law on domain r(x) lifts along any refinement u: Z -> X",
        "binders": [
            ("-Z", "Type"),
            ("-X", "Type"),
            ("-A", "Type"),
            ("-B", "Type"),
            ("u", "Z -> X"),
            ("-r", "X -> A"),
            ("-p", "A -> B"),
            ("-q", "A -> B"),
        ],
        "hyps": [
            ("e", "@x:X -> {p(r(x)) == q(r(x)) : B}"),
        ],
        "claim": "@z:Z -> {p(r(u(z))) == q(r(u(z))) : B}",
        "proof": "z => e(u(z))",
    },
    {
        "law_id": "core_domain_local_post",
        "group": "domain_locality",
        "proof_class": "core_domain_local",
        "predicted_status": "PROVED",
        "doc": "domain-local post-whiskering: if p(r(x)) == q(r(x)) on domain r, then l(p(r(x))) == l(q(r(x))) on domain r",
        "binders": [
            ("-X", "Type"),
            ("-A", "Type"),
            ("-B", "Type"),
            ("-Y", "Type"),
            ("-r", "X -> A"),
            ("-p", "A -> B"),
            ("-q", "A -> B"),
            ("-l", "B -> Y"),
        ],
        "hyps": [
            ("e", "@x:X -> {p(r(x)) == q(r(x)) : B}"),
        ],
        "claim": "@x:X -> {l(p(r(x))) == l(q(r(x))) : Y}",
        "proof": "x => (%e(x) : {l(p(r(x))) == l(_) : Y}; {==})",
    },
    {
        "law_id": "core_domain_local_paste",
        "group": "domain_locality",
        "proof_class": "core_domain_local",
        "predicted_status": "PROVED",
        "doc": "domain-local vertical pasting: two parallel laws on the same domain r compose on r",
        "binders": [
            ("-X", "Data"),
            ("-A", "Type"),
            ("-B", "Type"),
            ("-r", "X -> A"),
            ("-p", "A -> B"),
            ("-q", "A -> B"),
            ("-s", "A -> B"),
        ],
        "hyps": [
            ("e1", "@x:X -> {p(r(x)) == q(r(x)) : B}"),
            ("e2", "@x:X -> {q(r(x)) == s(r(x)) : B}"),
        ],
        "claim": "@+x:X -> {p(r(x)) == s(r(x)) : B}",
        "proof": "+x => (%e2(x) : {p(r(x)) == _ : B}; e1(x))",
    },
    {
        "law_id": "core_tree_unique_2",
        "group": "basis_sufficiency",
        "proof_class": "core_basis",
        "predicted_status": "PROVED",
        "doc": "spanning-tree path reduction: two edges g1, g2 reducing to the same tree path t on f(a) are equal on f(a)",
        "binders": [
            ("-A", "Data"),
            ("-B", "Type"),
            ("-C", "Type"),
            ("-f", "A -> B"),
            ("-g1", "B -> C"),
            ("-g2", "B -> C"),
            ("-t", "A -> C"),
        ],
        "hyps": [
            ("e1", "@a:A -> {g1(f(a)) == t(a) : C}"),
            ("e2", "@a:A -> {g2(f(a)) == t(a) : C}"),
        ],
        "claim": "@+a:A -> {g1(f(a)) == g2(f(a)) : C}",
        "proof": "+a => (%{(%e2(a) : {_ == g2(f(a)) : C}; {==}) : {t(a) == g2(f(a)) : C}} : {g1(f(a)) == _ : C}; e1(a))",
    },
    {
        "law_id": "core_cycle_basis_2",
        "group": "basis_sufficiency",
        "proof_class": "core_basis",
        "predicted_status": "PROVED",
        "doc": "fundamental-cycle basis sufficiency: a non-tree edge e with cycle generator t == e and tree round-trip law l(t(r(x))) == obs(x) satisfies l(e(r(x))) == obs(x)",
        "binders": [
            ("-X", "Data"),
            ("-A", "Type"),
            ("-B", "Type"),
            ("-Y", "Type"),
            ("r", "X -> A"),
            ("-t", "A -> B"),
            ("-e", "A -> B"),
            ("-l", "B -> Y"),
            ("-obs", "X -> Y"),
        ],
        "hyps": [
            ("cyc", "@a:A -> {t(a) == e(a) : B}"),
            ("tree_law", "@x:X -> {l(t(r(x))) == obs(x) : Y}"),
        ],
        "claim": "@+x:X -> {l(e(r(x))) == obs(x) : Y}",
        "proof": "+x => (%cyc(r(x)) : {l(_) == obs(x) : Y}; tree_law(x))",
    },
)


def render_theory_core_i_laws() -> str:
    lines = ["import Base", ""]
    for s in THEORY_CORE_I_SPECS:
        lines.append(f"law {s['law_id']}:")
        for b_name, b_ty in s["binders"]:
            lines.append(f"  for {b_name}: {b_ty}")
        for h_name, h_ty in s["hyps"]:
            lines.append(f"  for {h_name}: {h_ty}")
        lines.append(f"  {s['claim']}")
        lines.append("")
    return "\n".join(lines)


def render_theory_core_i_proofs() -> str:
    lines = ["import Base", "import ./LAWS.bend as Laws", ""]
    for s in THEORY_CORE_I_SPECS:
        args = [b[0].lstrip("+-") for b in s["binders"]] + [
            h[0].lstrip("+-") for h in s["hyps"]
        ]
        lines.append(f"def Laws.{s['law_id']}({', '.join(args)}):")
        lines.append(f"  {s['proof']}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. Spanning-tree basis sufficiency specs for `header` (M2) and `header_length` (M3)
# ---------------------------------------------------------------------------

HEADER_BASIS_LAWS: tuple[dict[str, Any], ...] = (
    {
        "law_id": "basis_sufficient_header_v0",
        "family": "header",
        "predicted_status": "PROVED",
        "core_lemma": "core_whisker_post",
        "basis_generators": ["L_par_hdr_v0"],
        "doc": "non-tree walk dec_go(enc_sol(pin_h(h))) reduces to spanning-tree walk dec_go(enc_go_v0(pin_h(h))) via L_par_hdr_v0 and core_whisker_post",
    },
    {
        "law_id": "basis_sufficient_header_v1",
        "family": "header",
        "predicted_status": "PROVED",
        "core_lemma": "core_whisker_post",
        "basis_generators": ["L_par_hdr_v1"],
        "doc": "parallel walk dec_go(enc_sol(pin_h(h))) reduces to dec_go(enc_go_v1(pin_h(h))) via L_par_hdr_v1 and core_whisker_post",
    },
    {
        "law_id": "basis_sufficient_header",
        "family": "header",
        "predicted_status": "PROVED",
        "core_lemma": "core_cycle_basis_2",
        "basis_generators": ["L_par_hdr_v0", "L_par_hdr_v1", "L_rt_go_v0"],
        "doc": "any parallel encoder walk enc_alt in the M2 header diagram reduces along the unique spanning-tree path dec_go o enc_tree to the cycle-basis generator par_gen and tree round-trip law rt_gen",
    },
)


HEADER_LENGTH_BASIS_LAWS: tuple[dict[str, Any], ...] = (
    {
        "law_id": "basis_hl_gen_blob_hashes_hash",
        "family": "header_length",
        "non_tree_edge": "CODEC.BatchHeaderBytes_BlobHashesHash",
        "tree_path": ["CODEC.BatchHeaderBytes_BlobCommitHash"],
        "cycle_length": 2,
        "predicted_status": "PROVED",
        "core_lemma": "core_tree_unique_2",
        "basis_generators": [
            "L_par_rt_BatchCache_createBatchHeaderWithSequencerSetHash_BatchHeaderBytes_BlobHashesHash_v2",
            "L_par_rt_BatchCache_createBatchHeaderWithSequencerSetHash_BatchHeaderBytes_BlobCommitHash_v2",
        ],
        "doc": "non-tree edge CODEC.BatchHeaderBytes_BlobHashesHash reduces on the v2 domain to tree edge CODEC.BatchHeaderBytes_BlobCommitHash via core_tree_unique_2",
    },
    {
        "law_id": "basis_hl_gen_blob_versioned_hash",
        "family": "header_length",
        "non_tree_edge": "CODEC.BatchHeaderBytes_BlobVersionedHash",
        "tree_path": ["CODEC.BatchHeaderBytes_BlobCommitHash"],
        "cycle_length": 2,
        "predicted_status": "PROVED",
        "core_lemma": "core_tree_unique_2",
        "basis_generators": [
            "L_par_rt_BatchHeaderV0_Bytes_BatchHeaderBytes_BlobVersionedHash_v0",
            "L_par_rt_BatchHeaderV0_Bytes_BatchHeaderBytes_BlobCommitHash_v0",
        ],
        "doc": "non-tree edge CODEC.BatchHeaderBytes_BlobVersionedHash reduces on the v0 domain to tree edge CODEC.BatchHeaderBytes_BlobCommitHash via core_tree_unique_2",
    },
    {
        "law_id": "basis_hl_gen_batch_header_v1_bytes",
        "family": "header_length",
        "non_tree_edge": "CODEC.BatchHeaderV1_Bytes",
        "tree_path": ["CODEC.BatchCache_createBatchHeaderWithSequencerSetHash"],
        "cycle_length": 2,
        "predicted_status": "PROVED",
        "core_lemma": "core_whisker_post",
        "basis_generators": [
            "L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned",
        ],
        "doc": "non-tree edge CODEC.BatchHeaderV1_Bytes post-whiskers with downstream decoders on the pinned v1 domain via core_whisker_post",
    },
    {
        "law_id": "basis_hl_gen_load_sol",
        "family": "header_length",
        "non_tree_edge": "CODEC.load_sol",
        "tree_path": [],
        "cycle_length": 1,
        "predicted_status": "PROVED",
        "core_lemma": "core_whisker_post",
        "basis_generators": ["load_sol_id"],
        "doc": "self-loop non-tree edge CODEC.load_sol (tree_path = []) reduces under any downstream decoder via core_whisker_post when load_sol acts as identity on the domain",
    },
    {
        "law_id": "basis_sufficient_header_length",
        "family": "header_length",
        "non_tree_edge": "*",
        "tree_path": ["*"],
        "cycle_length": 2,
        "predicted_status": "PROVED",
        "core_lemma": "core_cycle_basis_2",
        "basis_generators": [
            "CODEC.BatchHeaderBytes_BlobHashesHash",
            "CODEC.BatchHeaderBytes_BlobVersionedHash",
            "CODEC.BatchHeaderV1_Bytes",
            "CODEC.load_sol",
        ],
        "doc": "spanning-tree cycle-basis sufficiency for the M3 header_length diagram: any walk through a non-tree edge reduces to the unique spanning-tree path plus the 4 fundamental-cycle generators via core_cycle_basis_2",
    },
)


def header_laws_bend() -> str:
    return "\n".join([
        "# GENERATED by holon.gen.basis for M2 morph_header cycle basis; do not edit.",
        "import Base",
        "import ../../../M0/model/morph_header.bend as M",
        "import ../../../M0/L_par_hdr_v0/LAWS.bend as PAR0",
        "import ../../../M0/L_par_hdr_v1/LAWS.bend as PAR1",
        "import ../../../M0/L_rt_go_v0/LAWS.bend as RT0",
        "",
        "law basis_sufficient_header_v0:",
        "  for h: M.Hdr",
        "  {M.dec_go(M.enc_sol(PAR0.pin_h(h))) == M.dec_go(M.enc_go_v0(PAR0.pin_h(h))) : Maybe<&2, List<&2, List<&2, U32>>>}",
        "",
        "law basis_sufficient_header_v1:",
        "  for h: M.Hdr",
        "  {M.dec_go(M.enc_sol(PAR1.pin_h(h))) == M.dec_go(M.enc_go_v1(PAR1.pin_h(h))) : Maybe<&2, List<&2, List<&2, U32>>>}",
        "",
        "law basis_sufficient_header:",
        "  for par_gen: @a:M.Hdr -> {M.enc_sol(RT0.pin_h(a)) == M.enc_go_v0(RT0.pin_h(a)) : List<&2, U32>}",
        "  @+h:M.Hdr -> {M.dec_go(M.enc_go_v0(RT0.pin_h(h))) == {Some{M.view(RT0.pin_h(h))} : Maybe<&2, List<&2, List<&2, U32>>>} : Maybe<&2, List<&2, List<&2, U32>>>}",
        "",
    ])


def header_proof_bend() -> str:
    return "\n".join([
        "# GENERATED by holon.gen.basis; untrusted, accepted only if Bend checks it.",
        "import Base",
        "import ./LAWS.bend as Laws",
        "import ../../core/PROOF.bend as CP",
        "import ../../core/LAWS.bend as C",
        "import ../../../M0/model/morph_header.bend as M",
        "import ../../../M0/L_par_hdr_v0/PROOF.bend as PAR0_P",
        "import ../../../M0/L_par_hdr_v0/LAWS.bend as PAR0",
        "import ../../../M0/L_par_hdr_v1/PROOF.bend as PAR1_P",
        "import ../../../M0/L_par_hdr_v1/LAWS.bend as PAR1",
        "import ../../../M0/L_rt_go_v0/PROOF.bend as RT0_P",
        "import ../../../M0/L_rt_go_v0/LAWS.bend as RT0",
        "",
        "def Laws.basis_sufficient_header_v0(h):",
        "  C.core_whisker_post(M.Hdr, List<&2, U32>, Maybe<&2, List<&2, List<&2, U32>>>, x => M.enc_sol(PAR0.pin_h(x)), x => M.enc_go_v0(PAR0.pin_h(x)), b => M.dec_go(b), PAR0.l_par_hdr_v0)(h)",
        "",
        "def Laws.basis_sufficient_header_v1(h):",
        "  C.core_whisker_post(M.Hdr, List<&2, U32>, Maybe<&2, List<&2, List<&2, U32>>>, x => M.enc_sol(PAR1.pin_h(x)), x => M.enc_go_v1(PAR1.pin_h(x)), b => M.dec_go(b), PAR1.l_par_hdr_v1)(h)",
        "",
        "def Laws.basis_sufficient_header(par_gen):",
        "  C.core_cycle_basis_2(M.Hdr, M.Hdr, List<&2, U32>, Maybe<&2, List<&2, List<&2, U32>>>, x => x, a => M.enc_sol(RT0.pin_h(a)), a => M.enc_go_v0(RT0.pin_h(a)), b => M.dec_go(b), x => {Some{M.view(RT0.pin_h(x))} : Maybe<&2, List<&2, List<&2, U32>>>}, par_gen, RT0.l_rt_go_v0)",
        "",
    ])


def header_length_laws_bend() -> str:
    return "\n".join([
        "# GENERATED by holon.gen.basis for M3 header_length cycle basis; do not edit.",
        "import Base",
        "import ../../model/header_length.bend as M",
        "import ../../laws/L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned/LAWS.bend as CC1",
        "",
        "law basis_hl_gen_blob_hashes_hash:",
        "  for +h: M.R_BatchHeaderV1",
        "  {M.BatchHeaderBytes_BlobHashesHash(M.BatchCache_createBatchHeaderWithSequencerSetHash(h)) == M.BatchHeaderBytes_BlobCommitHash(M.BatchCache_createBatchHeaderWithSequencerSetHash(h)) : Maybe<&2, List<&2, U32>>}",
        "",
        "law basis_hl_gen_blob_versioned_hash:",
        "  for +h: M.R_BatchHeaderV0",
        "  {M.BatchHeaderBytes_BlobVersionedHash(M.BatchHeaderV0_Bytes(h)) == M.BatchHeaderBytes_BlobCommitHash(M.BatchHeaderV0_Bytes(h)) : Maybe<&2, List<&2, U32>>}",
        "",
        "law basis_hl_gen_batch_header_v1_bytes:",
        "  for +h: M.R_BatchHeaderV1",
        "  for +k: M.R_Header",
        "  {M.BatchHeaderBytes_BatchIndex(M.BatchHeaderV1_Bytes(CC1.pin_h(h))) == M.BatchHeaderBytes_BatchIndex(M.enc_sol(CC1.pin_k(k, h))) : Maybe<&2, List<&2, U32>>}",
        "",
        "law basis_hl_gen_load_sol:",
        "  for -X: Type",
        "  for -B: Type",
        "  for -Y: Type",
        "  for -r: X -> B",
        "  for -load_sol: B -> B",
        "  for -l: B -> Y",
        "  for loop_gen: @x:X -> {load_sol(r(x)) == r(x) : B}",
        "  @x:X -> {l(load_sol(r(x))) == l(r(x)) : Y}",
        "",
        "law basis_sufficient_header_length:",
        "  for +h: M.R_BatchHeaderV1",
        "  {M.BatchHeaderBytes_BlobHashesHash(M.BatchCache_createBatchHeaderWithSequencerSetHash(h)) == {Some{M.get_BatchHeaderV1__BatchHeaderV0__BlobVersionedHash(h)} : Maybe<&2, List<&2, U32>>} : Maybe<&2, List<&2, U32>>}",
        "",
    ])


def header_length_proof_bend() -> str:
    return "\n".join([
        "# GENERATED by holon.gen.basis; untrusted, accepted only if Bend checks it.",
        "import Base",
        "import ./LAWS.bend as Laws",
        "import ../../core/PROOF.bend as CP",
        "import ../../core/LAWS.bend as C",
        "import ../../model/header_length.bend as M",
        "import ../../laws/L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned/LAWS.bend as CC1",
        "import ../../proofs/L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned/PROOF.bend as CC1_P",
        "import ../../laws/L_par_rt_BatchCache_createBatchHeaderWithSequencerSetHash_BatchHeaderBytes_BlobHashesHash_v2/LAWS.bend as RT_BHH_V2",
        "import ../../proofs/L_par_rt_BatchCache_createBatchHeaderWithSequencerSetHash_BatchHeaderBytes_BlobHashesHash_v2/PROOF.bend as RT_BHH_V2_P",
        "import ../../laws/L_par_rt_BatchCache_createBatchHeaderWithSequencerSetHash_BatchHeaderBytes_BlobCommitHash_v2/LAWS.bend as RT_BCH_V2",
        "import ../../proofs/L_par_rt_BatchCache_createBatchHeaderWithSequencerSetHash_BatchHeaderBytes_BlobCommitHash_v2/PROOF.bend as RT_BCH_V2_P",
        "import ../../laws/L_par_rt_BatchHeaderV0_Bytes_BatchHeaderBytes_BlobVersionedHash_v0/LAWS.bend as RT_BVH_V0",
        "import ../../proofs/L_par_rt_BatchHeaderV0_Bytes_BatchHeaderBytes_BlobVersionedHash_v0/PROOF.bend as RT_BVH_V0_P",
        "import ../../laws/L_par_rt_BatchHeaderV0_Bytes_BatchHeaderBytes_BlobCommitHash_v0/LAWS.bend as RT_BCH_V0",
        "import ../../proofs/L_par_rt_BatchHeaderV0_Bytes_BatchHeaderBytes_BlobCommitHash_v0/PROOF.bend as RT_BCH_V0_P",
        "",
        "def Laws.basis_hl_gen_blob_hashes_hash(h):",
        "  C.core_tree_unique_2(M.R_BatchHeaderV1, List<&2, U32>, Maybe<&2, List<&2, U32>>, x => M.BatchCache_createBatchHeaderWithSequencerSetHash(x), b => M.BatchHeaderBytes_BlobHashesHash(b), b => M.BatchHeaderBytes_BlobCommitHash(b), x => {Some{M.get_BatchHeaderV1__BatchHeaderV0__BlobVersionedHash(x)} : Maybe<&2, List<&2, U32>>}, x => RT_BHH_V2.l_par_rt_batchcache_createbatchheaderwithsequencersethash_batchheaderbytes_blobhasheshash_v2(x), x => RT_BCH_V2.l_par_rt_batchcache_createbatchheaderwithsequencersethash_batchheaderbytes_blobcommithash_v2(x))(h)",
        "",
        "def Laws.basis_hl_gen_blob_versioned_hash(h):",
        "  C.core_tree_unique_2(M.R_BatchHeaderV0, List<&2, U32>, Maybe<&2, List<&2, U32>>, x => M.BatchHeaderV0_Bytes(x), b => M.BatchHeaderBytes_BlobVersionedHash(b), b => M.BatchHeaderBytes_BlobCommitHash(b), x => {Some{M.get_BatchHeaderV0__BlobVersionedHash(x)} : Maybe<&2, List<&2, U32>>}, x => RT_BVH_V0.l_par_rt_batchheaderv0_bytes_batchheaderbytes_blobversionedhash_v0(x), x => RT_BCH_V0.l_par_rt_batchheaderv0_bytes_batchheaderbytes_blobcommithash_v0(x))(h)",
        "",
        "def Laws.basis_hl_gen_batch_header_v1_bytes(h, k):",
        "  C.core_whisker_post(M.R_BatchHeaderV1, List<&2, U32>, Maybe<&2, List<&2, U32>>, x => M.BatchHeaderV1_Bytes(CC1.pin_h(x)), x => M.enc_sol(CC1.pin_k(k, x)), b => M.BatchHeaderBytes_BatchIndex(b), x => CC1.l_par_cc_batchheaderv1_bytes_enc_sol_v1_pinned(x, k))(h)",
        "",
        "def Laws.basis_hl_gen_load_sol(X, B, Y, r, load_sol, l, loop_gen):",
        "  C.core_whisker_post(X, B, Y, x => load_sol(r(x)), r, l, loop_gen)",
        "",
        "def Laws.basis_sufficient_header_length(h):",
        "  C.core_cycle_basis_2(M.R_BatchHeaderV1, M.R_BatchHeaderV1, Maybe<&2, List<&2, U32>>, Maybe<&2, List<&2, U32>>, x => x, a => M.BatchHeaderBytes_BlobCommitHash(M.BatchCache_createBatchHeaderWithSequencerSetHash(a)), a => M.BatchHeaderBytes_BlobHashesHash(M.BatchCache_createBatchHeaderWithSequencerSetHash(a)), y => y, x => {Some{M.get_BatchHeaderV1__BatchHeaderV0__BlobVersionedHash(x)} : Maybe<&2, List<&2, U32>>}, a => (%Laws.basis_hl_gen_blob_hashes_hash(a) : {_ == M.BatchHeaderBytes_BlobHashesHash(M.BatchCache_createBatchHeaderWithSequencerSetHash(a)) : Maybe<&2, List<&2, U32>>}; {==}), x => RT_BCH_V2.l_par_rt_batchcache_createbatchheaderwithsequencersethash_batchheaderbytes_blobcommithash_v2(x))(h)",
        "",
    ])


# ---------------------------------------------------------------------------
# 3. Congruence-first proof emission for 2 M0 + 32 M3 round-trip laws (34 total)
# ---------------------------------------------------------------------------

GO_ENC_BY_VER: dict[str, tuple[str, str, str, str]] = {
    "v0": (
        "BatchHeaderV0_Bytes",
        "R_BatchHeaderV0",
        "CC0",
        "L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0_pinned",
    ),
    "v1": (
        "BatchHeaderV1_Bytes",
        "R_BatchHeaderV1",
        "CC1",
        "L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned",
    ),
    "v2": (
        "BatchCache_createBatchHeaderWithSequencerSetHash",
        "R_BatchHeaderV1",
        "CC2",
        "L_par_cc_BatchCache_createBatchHeaderWithSequencerSetHash_enc_sol_v2_pinned",
    ),
}


def _line_counts(path: Path) -> tuple[int, int, int]:
    lines = path.read_text().splitlines()
    total = len(lines)
    nonblank = sum(1 for ln in lines if ln.strip() and not ln.strip().startswith("#"))
    def_body = sum(
        1
        for ln in lines
        if ln.strip()
        and not ln.strip().startswith("#")
        and not ln.strip().startswith("import ")
    )
    return total, nonblank, def_body


def congruence_entries(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for ver, par_lid in (("v0", "L_par_hdr_v0"), ("v1", "L_par_hdr_v1")):
        src_lid = f"L_rt_go_{ver}"
        base_p = root / f"gen/M0/{src_lid}/PROOF.bend"
        tot, nb, db = _line_counts(base_p)
        entries.append({
            "law_id": f"cong_l_rt_go_{ver}",
            "source_law_id": src_lid,
            "milestone": "M0",
            "version": ver,
            "decoder": "dec_go",
            "encoder_sol": "enc_sol",
            "encoder_go": f"enc_go_{ver}",
            "parallel_generator": par_lid,
            "tree_rt_generator": None,
            "getter": None,
            "core_lemma": "core_whisker_post",
            "predicted_status": "PROVED",
            "baseline_proof_path": f"gen/M0/{src_lid}/PROOF.bend",
            "baseline_total_lines": tot,
            "baseline_nonblank_lines": nb,
            "baseline_def_lines": db,
            "congruence_def_lines": 2,
        })

    enc_sol_laws = sorted(
        p
        for p in (root / "gen/M3/laws").glob("L_par_rt_enc_sol_*/LAWS.bend")
        if "_Version_" not in p.parent.name
    )
    for p in enc_sol_laws:
        src_lid = p.parent.name
        rest = src_lid[len("L_par_rt_enc_sol_BatchHeaderBytes_"):]
        field, ver = rest.rsplit("_", 1)
        go_enc, go_rec, _cc_alias, cc_lid = GO_ENC_BY_VER[ver]
        dec_fn = f"BatchHeaderBytes_{field}"
        rt_lid = f"L_par_rt_{go_enc}_{dec_fn}_{ver}"
        rt_laws_txt = (root / f"gen/M3/laws/{rt_lid}/LAWS.bend").read_text()
        m = re.search(r"Some\{M\.(get_[A-Za-z0-9_]+)\(h\)\}", rt_laws_txt)
        assert m is not None, f"getter not found in {rt_lid}"
        getter = m.group(1)
        base_p = root / f"gen/M3/proofs/{src_lid}/PROOF.bend"
        tot, nb, db = _line_counts(base_p)
        entries.append({
            "law_id": f"cong_{src_lid.lower()}",
            "source_law_id": src_lid,
            "milestone": "M3",
            "version": ver,
            "decoder": dec_fn,
            "encoder_sol": "enc_sol",
            "encoder_go": go_enc,
            "go_carrier": go_rec,
            "parallel_generator": cc_lid,
            "tree_rt_generator": rt_lid,
            "getter": getter,
            "core_lemma": "core_whisker_post",
            "predicted_status": "PROVED",
            "baseline_proof_path": f"gen/M3/proofs/{src_lid}/PROOF.bend",
            "baseline_total_lines": tot,
            "baseline_nonblank_lines": nb,
            "baseline_def_lines": db,
            "congruence_def_lines": 3,
        })
    return entries


def congruence_laws_bend(root: Path) -> str:
    entries = congruence_entries(root)
    lines = [
        "# GENERATED by holon.gen.mproofs for I42 congruence round-trip basis; do not edit.",
        "import Base",
        "import ../../../M0/model/morph_header.bend as H0",
        "import ../../../M0/L_par_hdr_v0/LAWS.bend as PAR0",
        "import ../../../M0/L_par_hdr_v1/LAWS.bend as PAR1",
        "import ../../model/header_length.bend as M",
        "import ../../laws/L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0_pinned/LAWS.bend as CC0",
        "import ../../laws/L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned/LAWS.bend as CC1",
        "import ../../laws/L_par_cc_BatchCache_createBatchHeaderWithSequencerSetHash_enc_sol_v2_pinned/LAWS.bend as CC2",
        "",
        "law cong_l_rt_go_v0:",
        "  for h: H0.Hdr",
        "  {H0.dec_go(H0.enc_sol(PAR0.pin_h(h))) == H0.dec_go(H0.enc_go_v0(PAR0.pin_h(h))) : Maybe<&2, List<&2, List<&2, U32>>>}",
        "",
        "law cong_l_rt_go_v1:",
        "  for h: H0.Hdr",
        "  {H0.dec_go(H0.enc_sol(PAR1.pin_h(h))) == H0.dec_go(H0.enc_go_v1(PAR1.pin_h(h))) : Maybe<&2, List<&2, List<&2, U32>>>}",
        "",
    ]
    for e in entries:
        if e["milestone"] != "M3":
            continue
        ver = e["version"]
        _go_enc, go_rec, cc_alias, _cc_lid = GO_ENC_BY_VER[ver]
        dec_fn = e["decoder"]
        getter = e["getter"]
        cong_fn = e["law_id"]
        lines.extend([
            f"law {cong_fn}:",
            f"  for +h: M.{go_rec}",
            "  for +k: M.R_Header",
            f"  {{M.{dec_fn}(M.enc_sol({cc_alias}.pin_k(k, h))) == {{Some{{M.{getter}({cc_alias}.pin_h(h))}} : Maybe<&2, List<&2, U32>>}} : Maybe<&2, List<&2, U32>>}}",
            "",
        ])
    return "\n".join(lines)


def congruence_proof_bend(root: Path) -> str:
    entries = congruence_entries(root)
    imports = [
        "# GENERATED by holon.gen.mproofs; untrusted, accepted only if Bend checks it.",
        "import Base",
        "import ./LAWS.bend as Laws",
        "import ../../core/PROOF.bend as CP",
        "import ../../core/LAWS.bend as C",
        "import ../../../M0/model/morph_header.bend as H0",
        "import ../../../M0/L_par_hdr_v0/LAWS.bend as PAR0",
        "import ../../../M0/L_par_hdr_v0/PROOF.bend as PAR0_P",
        "import ../../../M0/L_par_hdr_v1/LAWS.bend as PAR1",
        "import ../../../M0/L_par_hdr_v1/PROOF.bend as PAR1_P",
        "import ../../model/header_length.bend as M",
        "import ../../laws/L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0_pinned/LAWS.bend as CC0",
        "import ../../proofs/L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0_pinned/PROOF.bend as CC0_P",
        "import ../../laws/L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned/LAWS.bend as CC1",
        "import ../../proofs/L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned/PROOF.bend as CC1_P",
        "import ../../laws/L_par_cc_BatchCache_createBatchHeaderWithSequencerSetHash_enc_sol_v2_pinned/LAWS.bend as CC2",
        "import ../../proofs/L_par_cc_BatchCache_createBatchHeaderWithSequencerSetHash_enc_sol_v2_pinned/PROOF.bend as CC2_P",
    ]
    defs = [
        "",
        "def Laws.cong_l_rt_go_v0(h):",
        "  C.core_whisker_post(H0.Hdr, List<&2, U32>, Maybe<&2, List<&2, List<&2, U32>>>, x => H0.enc_sol(PAR0.pin_h(x)), x => H0.enc_go_v0(PAR0.pin_h(x)), b => H0.dec_go(b), PAR0.l_par_hdr_v0)(h)",
        "",
        "def Laws.cong_l_rt_go_v1(h):",
        "  C.core_whisker_post(H0.Hdr, List<&2, U32>, Maybe<&2, List<&2, List<&2, U32>>>, x => H0.enc_sol(PAR1.pin_h(x)), x => H0.enc_go_v1(PAR1.pin_h(x)), b => H0.dec_go(b), PAR1.l_par_hdr_v1)(h)",
        "",
    ]
    m3_idx = 0
    for e in entries:
        if e["milestone"] != "M3":
            continue
        ver = e["version"]
        go_enc, go_rec, cc_alias, cc_lid = GO_ENC_BY_VER[ver]
        cc_fn = cc_lid.lower()
        dec_fn = e["decoder"]
        getter = e["getter"]
        rt_lid = e["tree_rt_generator"]
        rt_fn = rt_lid.lower()
        rt_alias = f"RT_{m3_idx}"
        m3_idx += 1
        imports.append(f"import ../../laws/{rt_lid}/LAWS.bend as {rt_alias}")
        imports.append(f"import ../../proofs/{rt_lid}/PROOF.bend as {rt_alias}_P")
        cong_fn = e["law_id"]
        defs.extend([
            f"def Laws.{cong_fn}(h, k):",
            f"  %C.core_whisker_post(M.{go_rec}, List<&2, U32>, Maybe<&2, List<&2, U32>>, x => M.{go_enc}({cc_alias}.pin_h(x)), x => M.enc_sol({cc_alias}.pin_k(k, x)), b => M.{dec_fn}(b), x => {cc_alias}.{cc_fn}(x, k))(h) : {{_ == {{Some{{M.{getter}({cc_alias}.pin_h(h))}} : Maybe<&2, List<&2, U32>>}} : Maybe<&2, List<&2, U32>>}}",
            f"  {rt_alias}.{rt_fn}({cc_alias}.pin_h(h))",
            "",
        ])
    return "\n".join(imports + defs)


# ---------------------------------------------------------------------------
# 4. Negative canaries (7 total across the 4 theorem groups)
# ---------------------------------------------------------------------------

CANARY_SPECS: tuple[dict[str, Any], ...] = (
    {
        "canary_id": "canary_whisker_direction_mismatch",
        "group": "theory_core_i",
        "predicted_status": "REFUTED",
        "doc": "swapping post-whisker observers l1 != l2 without an equality hypothesis between l1 and l2 must fail both Bend kernels",
        "laws_bend": "\n".join([
            "import Base",
            "law canary_whisker_direction_mismatch:",
            "  for -A: Type",
            "  for -B: Type",
            "  for -Y: Type",
            "  for -p: A -> B",
            "  for -q: A -> B",
            "  for -l1: B -> Y",
            "  for -l2: B -> Y",
            "  for e: @a:A -> {p(a) == q(a) : B}",
            "  @a:A -> {l1(p(a)) == l2(q(a)) : Y}",
            "",
        ]),
        "proof_bend": "\n".join([
            "import Base",
            "import ./LAWS.bend as Laws",
            "def Laws.canary_whisker_direction_mismatch(A, B, Y, p, q, l1, l2, e):",
            "  a => (%e(a) : {l1(p(a)) == l2(_) : Y}; {==})",
            "",
        ]),
    },
    {
        "canary_id": "canary_domain_local_without_premise",
        "group": "theory_core_i",
        "predicted_status": "REFUTED",
        "doc": "claiming full-carrier equality @a:A -> {p(a) == q(a)} from a domain-restricted hypothesis @x:X -> {p(r(x)) == q(r(x))} must fail both Bend kernels",
        "laws_bend": "\n".join([
            "import Base",
            "law canary_domain_local_without_premise:",
            "  for -X: Type",
            "  for -A: Type",
            "  for -B: Type",
            "  for -r: X -> A",
            "  for -p: A -> B",
            "  for -q: A -> B",
            "  for e: @x:X -> {p(r(x)) == q(r(x)) : B}",
            "  @a:A -> {p(a) == q(a) : B}",
            "",
        ]),
        "proof_bend": "\n".join([
            "import Base",
            "import ./LAWS.bend as Laws",
            "def Laws.canary_domain_local_without_premise(X, A, B, r, p, q, e):",
            "  a => e(a)",
            "",
        ]),
    },
    {
        "canary_id": "canary_basis_missing_generator",
        "group": "theory_core_i",
        "predicted_status": "REFUTED",
        "doc": "attempting to reduce a non-tree walk l(e(r(x))) == obs(x) from the tree law l(t(r(x))) == obs(x) without the cycle-basis generator t == e must fail both Bend kernels",
        "laws_bend": "\n".join([
            "import Base",
            "law canary_basis_missing_generator:",
            "  for -X: Data",
            "  for -A: Type",
            "  for -B: Type",
            "  for -Y: Type",
            "  for r: X -> A",
            "  for -t: A -> B",
            "  for -e: A -> B",
            "  for -l: B -> Y",
            "  for -obs: X -> Y",
            "  for tree_law: @x:X -> {l(t(r(x))) == obs(x) : Y}",
            "  @+x:X -> {l(e(r(x))) == obs(x) : Y}",
            "",
        ]),
        "proof_bend": "\n".join([
            "import Base",
            "import ./LAWS.bend as Laws",
            "def Laws.canary_basis_missing_generator(X, A, B, Y, r, t, e, l, obs, tree_law):",
            "  +x => tree_law(x)",
            "",
        ]),
    },
    {
        "canary_id": "canary_header_v0_unpinned",
        "group": "header",
        "predicted_status": "REFUTED",
        "doc": "dropping the sequencerSetVerifyHash == 0 domain pin (pin_h) on dec_go(enc_sol(h)) == dec_go(enc_go_v0(h)) while rewriting with L_par_hdr_v0 must fail both Bend kernels",
        "laws_bend": "\n".join([
            "import Base",
            "import ../../../M0/model/morph_header.bend as M",
            "law canary_header_v0_unpinned:",
            "  for +h: M.Hdr",
            "  {M.dec_go(M.enc_sol(h)) == M.dec_go(M.enc_go_v0(h)) : Maybe<&2, List<&2, List<&2, U32>>>}",
            "",
        ]),
        "proof_bend": "\n".join([
            "import Base",
            "import ./LAWS.bend as Laws",
            "import ../../../M0/model/morph_header.bend as M",
            "import ../../../M0/L_par_hdr_v0/PROOF.bend as PAR0_P",
            "import ../../../M0/L_par_hdr_v0/LAWS.bend as PAR0",
            "def Laws.canary_header_v0_unpinned(h):",
            "  %PAR0.l_par_hdr_v0(h) : {M.dec_go(_) == M.dec_go(M.enc_go_v0(h)) : Maybe<&2, List<&2, List<&2, U32>>>};",
            "  {==}",
            "",
        ]),
    },
    {
        "canary_id": "canary_header_v1_missing_par",
        "group": "header",
        "predicted_status": "REFUTED",
        "doc": "attempting to prove the v1 cycle reduction dec_go(enc_sol(PAR1.pin_h(h))) == dec_go(enc_go_v1(PAR1.pin_h(h))) using only the v0 generator L_par_hdr_v0 without L_par_hdr_v1 must fail both Bend kernels",
        "laws_bend": "\n".join([
            "import Base",
            "import ../../../M0/model/morph_header.bend as M",
            "import ../../../M0/L_par_hdr_v1/LAWS.bend as PAR1",
            "law canary_header_v1_missing_par:",
            "  for +h: M.Hdr",
            "  {M.dec_go(M.enc_sol(PAR1.pin_h(h))) == M.dec_go(M.enc_go_v1(PAR1.pin_h(h))) : Maybe<&2, List<&2, List<&2, U32>>>}",
            "",
        ]),
        "proof_bend": "\n".join([
            "import Base",
            "import ./LAWS.bend as Laws",
            "import ../../../M0/model/morph_header.bend as M",
            "import ../../../M0/L_par_hdr_v0/PROOF.bend as PAR0_P",
            "import ../../../M0/L_par_hdr_v0/LAWS.bend as PAR0",
            "import ../../../M0/L_par_hdr_v1/LAWS.bend as PAR1",
            "def Laws.canary_header_v1_missing_par(h):",
            "  %PAR0.l_par_hdr_v0(h) : {M.dec_go(_) == M.dec_go(M.enc_go_v1(PAR1.pin_h(h))) : Maybe<&2, List<&2, List<&2, U32>>>};",
            "  {==}",
            "",
        ]),
    },
    {
        "canary_id": "canary_hl_drop_cycle_gen",
        "group": "header_length",
        "predicted_status": "REFUTED",
        "doc": "dropping the non-tree round-trip generator RT_BHH_V2 when reducing BatchHeaderBytes_BlobHashesHash to the spanning-tree edge BatchHeaderBytes_BlobCommitHash must fail both Bend kernels",
        "laws_bend": "\n".join([
            "import Base",
            "import ../../model/header_length.bend as M",
            "law canary_hl_drop_cycle_gen:",
            "  for +h: M.R_BatchHeaderV1",
            "  {M.BatchHeaderBytes_BlobHashesHash(M.BatchCache_createBatchHeaderWithSequencerSetHash(h)) == M.BatchHeaderBytes_BlobCommitHash(M.BatchCache_createBatchHeaderWithSequencerSetHash(h)) : Maybe<&2, List<&2, U32>>}",
            "",
        ]),
        "proof_bend": "\n".join([
            "import Base",
            "import ./LAWS.bend as Laws",
            "import ../../model/header_length.bend as M",
            "import ../../laws/L_par_rt_BatchCache_createBatchHeaderWithSequencerSetHash_BatchHeaderBytes_BlobCommitHash_v2/LAWS.bend as RT_BCH_V2",
            "import ../../proofs/L_par_rt_BatchCache_createBatchHeaderWithSequencerSetHash_BatchHeaderBytes_BlobCommitHash_v2/PROOF.bend as RT_BCH_V2_P",
            "def Laws.canary_hl_drop_cycle_gen(h):",
            "  %RT_BCH_V2.l_par_rt_batchcache_createbatchheaderwithsequencersethash_batchheaderbytes_blobcommithash_v2(h) : {M.BatchHeaderBytes_BlobHashesHash(M.BatchCache_createBatchHeaderWithSequencerSetHash(h)) == _ : Maybe<&2, List<&2, U32>>};",
            "  {==}",
            "",
        ]),
    },
    {
        "canary_id": "canary_congruence_unpinned_v0",
        "group": "congruence",
        "predicted_status": "REFUTED",
        "doc": "attempting to derive L_par_rt_enc_sol_BatchHeaderBytes_BatchIndex_v0 without the pin_k/pin_h domain premise must fail both Bend kernels",
        "laws_bend": "\n".join([
            "import Base",
            "import ../../model/header_length.bend as M",
            "law canary_congruence_unpinned_v0:",
            "  for +h: M.R_BatchHeaderV0",
            "  for +k: M.R_Header",
            "  {M.BatchHeaderBytes_BatchIndex(M.enc_sol(k)) == {Some{M.get_BatchHeaderV0__BatchIndex(h)} : Maybe<&2, List<&2, U32>>} : Maybe<&2, List<&2, U32>>}",
            "",
        ]),
        "proof_bend": "\n".join([
            "import Base",
            "import ./LAWS.bend as Laws",
            "import ../../model/header_length.bend as M",
            "import ../../laws/L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0_pinned/LAWS.bend as CC0",
            "import ../../proofs/L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0_pinned/PROOF.bend as CC0_P",
            "import ../../laws/L_par_rt_BatchHeaderV0_Bytes_BatchHeaderBytes_BatchIndex_v0/LAWS.bend as RT_0",
            "import ../../proofs/L_par_rt_BatchHeaderV0_Bytes_BatchHeaderBytes_BatchIndex_v0/PROOF.bend as RT_0_P",
            "def Laws.canary_congruence_unpinned_v0(h, k):",
            "  %CC0.l_par_cc_batchheaderv0_bytes_enc_sol_v0_pinned(h, k) : {M.BatchHeaderBytes_BatchIndex(_) == {Some{M.get_BatchHeaderV0__BatchIndex(h)} : Maybe<&2, List<&2, U32>>} : Maybe<&2, List<&2, U32>>};",
            "  RT_0.l_par_rt_batchheaderv0_bytes_batchheaderbytes_batchindex_v0(h)",
            "",
        ]),
    },
)


def _diagram_summary(root: Path, rel_path: str) -> dict[str, Any]:
    d = json.loads((root / rel_path).read_text())
    cb = _i24.cycle_basis(d)
    non_tree_details = []
    for nt in cb["non_tree"]:
        walk = _i24.fundamental_cycle(cb, nt)
        edge_obj = cb["_edges"][nt]
        non_tree_details.append({
            "edge": nt,
            "src": edge_obj["src"],
            "dst": edge_obj["tgt"],
            "tree_path": [e_tree["id"] for e_tree, _fwd in walk[1:]],
            "cycle_length": len(walk),
        })
    return {
        "diagram_path": rel_path,
        "E": cb["E"],
        "V": cb["V"],
        "kappa": cb["kappa"],
        "rank": cb["rank"],
        "tree_edges": cb["tree"],
        "non_tree_edges": cb["non_tree"],
        "fundamental_cycles": non_tree_details,
    }


def theory_core_i_doc(root: Path) -> dict[str, Any]:
    inputs = [
        {"path": rel, "sha256": _sha256(root / rel)}
        for rel in sorted(INPUT_PATHS)
    ]
    hdr_diag = _diagram_summary(root, "gen/M2/diagram/morph_header.json")
    hl_diag = _diagram_summary(root, "gen/M3/diagram/header_length.json")
    cong = congruence_entries(root)
    cong_laws_txt = congruence_laws_bend(root)
    cong_proof_txt = congruence_proof_bend(root)
    cong_proof_lines = len(cong_proof_txt.splitlines())
    cong_nonblank_lines = sum(
        1
        for ln in cong_proof_txt.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    )
    cong_def_lines = sum(e["congruence_def_lines"] for e in cong)
    base_total_lines = sum(e["baseline_total_lines"] for e in cong)
    base_nonblank_lines = sum(e["baseline_nonblank_lines"] for e in cong)
    base_def_lines = sum(e["baseline_def_lines"] for e in cong)

    return {
        "doc": (
            "I42 prereg sidecar (BUILD_PLAN I42 'Theory core I: whiskering, "
            "domain locality, spanning-tree basis sufficiency' and whitepaper "
            "section 6.1-6.2). Computed at prereg by "
            "tests_m3/_i42.py::theory_core_i_doc independently of holon/ from "
            "the frozen inputs listed with their sha256. Records: (1) the 12 "
            "polymorphic Bend 2 laws in THEORY_CORE_I (3 whiskering, 4 2-cell "
            "walk/square pasting, 3 domain-locality lifting, 2 spanning-tree "
            "cycle-basis reduction); (2) the spanning-tree cycle-basis "
            "sufficiency specifications for the M2 morph_header diagram "
            "(E = 4, V = 3, kappa = 1, rank = 2; 3 laws) and the M3 "
            "header_length diagram (E = 20, V = 17, kappa = 1, rank = 4; 5 "
            "laws); (3) the 34 congruence-derived round-trip laws (2 M0 + 32 "
            "M3) proved via core_whisker_post without record unpacking, and "
            "their line-count reduction against the open_refl baseline; "
            "(4) the 7 negative canaries across all 4 theorem groups, all "
            "predicted REFUTED under both bend and bend --verdict. The build "
            "never reads this file; the tests recompute and compare against it."
        ),
        "theory_core_i_version": THEORY_CORE_I_VERSION,
        "inputs": inputs,
        "theory_core_i": {
            "count": len(THEORY_CORE_I_SPECS),
            "groups": {
                "whisker": [
                    s["law_id"] for s in THEORY_CORE_I_SPECS if s["group"] == "whisker"
                ],
                "pasting": [
                    s["law_id"] for s in THEORY_CORE_I_SPECS if s["group"] == "pasting"
                ],
                "domain_locality": [
                    s["law_id"]
                    for s in THEORY_CORE_I_SPECS
                    if s["group"] == "domain_locality"
                ],
                "basis_sufficiency": [
                    s["law_id"]
                    for s in THEORY_CORE_I_SPECS
                    if s["group"] == "basis_sufficiency"
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
                for s in THEORY_CORE_I_SPECS
            ],
        },
        "basis_families": {
            "header": {
                "diagram": hdr_diag,
                "basis_generators": ["L_par_hdr_v0", "L_par_hdr_v1", "L_rt_go_v0"],
                "laws": list(HEADER_BASIS_LAWS),
            },
            "header_length": {
                "diagram": hl_diag,
                "basis_generators": [
                    "CODEC.BatchHeaderBytes_BlobHashesHash",
                    "CODEC.BatchHeaderBytes_BlobVersionedHash",
                    "CODEC.BatchHeaderV1_Bytes",
                    "CODEC.load_sol",
                ],
                "laws": list(HEADER_LENGTH_BASIS_LAWS),
            },
        },
        "congruence": {
            "total": len(cong),
            "m0_count": sum(1 for e in cong if e["milestone"] == "M0"),
            "m3_count": sum(1 for e in cong if e["milestone"] == "M3"),
            "baseline_total_lines": base_total_lines,
            "baseline_nonblank_lines": base_nonblank_lines,
            "baseline_def_lines": base_def_lines,
            "congruence_file_lines": cong_proof_lines,
            "congruence_nonblank_lines": cong_nonblank_lines,
            "congruence_def_lines": cong_def_lines,
            "congruence_laws_file_lines": len(cong_laws_txt.splitlines()),
            "laws": cong,
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
            "theory_core_i_laws": len(THEORY_CORE_I_SPECS),
            "header_basis_laws": len(HEADER_BASIS_LAWS),
            "header_length_basis_laws": len(HEADER_LENGTH_BASIS_LAWS),
            "congruence_laws": len(cong),
            "total_proved_laws": (
                len(THEORY_CORE_I_SPECS)
                + len(HEADER_BASIS_LAWS)
                + len(HEADER_LENGTH_BASIS_LAWS)
                + len(cong)
            ),
            "canaries_refuted": len(CANARY_SPECS),
        },
    }
