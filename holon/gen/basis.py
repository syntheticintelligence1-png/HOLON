"""Iteration I42 (Theory core I): spanning-tree cycle-basis sufficiency and congruence-first proofs.

Emits:
  * `gen/<M>/core/{LAWS,PROOF}.bend` (including the 12 `THEORY_CORE_I` laws);
  * `gen/<M>/basis/header/{LAWS,PROOF}.bend` (rank-2 cycle-basis sufficiency on `morph_header`);
  * `gen/<M>/basis/header_length/{LAWS,PROOF}.bend` (rank-4 cycle-basis sufficiency on `header_length`);
  * `gen/<M>/basis/congruence/{LAWS,PROOF}.bend` (34 congruence-first round-trip proofs via `C.core_whisker_post`);
  * `results/<M>/basis.json` (verification record for all 54 positive laws, 7 negative canaries, and line comparison).
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path

from .. import bend
from . import core, mproofs

ROOT = Path(__file__).resolve().parents[2]


def _line_counts(path: Path) -> tuple[int, int, int]:
    lines = path.read_text(encoding="utf-8").splitlines()
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


def discover_congruence_entries(root: Path = ROOT, milestone: str = "M3") -> list[dict]:
    """Discover the 2 M0 and 32 M3 round-trip laws derivable by `core_whisker_post` from parallel + tree laws."""
    root = Path(root).resolve()
    entries: list[dict] = []

    # 1. M0 round-trip laws paired with PROVED cross-component-codec laws sharing the same domain assumptions
    m0_laws_dir = root / "laws" / "M0"
    m0_res_dir = root / "results" / "M0"
    if m0_laws_dir.is_dir() and m0_res_dir.is_dir():
        m0_docs = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(m0_laws_dir.glob("L_*.json"))
            if (m0_res_dir / p.name).is_file()
            and json.loads((m0_res_dir / p.name).read_text(encoding="utf-8")).get("status") == "PROVED"
        ]
        m0_cc = {
            tuple(json.dumps(a, sort_keys=True) for a in d["statement"]["assume"]): d
            for d in m0_docs
            if d.get("subform") == "cross_component_codec"
        }
        m0_rt = {
            tuple(json.dumps(a, sort_keys=True) for a in d["statement"]["assume"]): d
            for d in m0_docs
            if d.get("subform") == "round_trip"
        }
        for key in sorted(set(m0_cc) & set(m0_rt)):
            rt_doc, cc_doc = m0_rt[key], m0_cc[key]
            rt_lid, cc_lid = rt_doc["law_id"], cc_doc["law_id"]
            ver_hex = next(
                a["eq"][1]["bytes"] for a in rt_doc["statement"]["assume"] if a["eq"][0].get("field") == "version"
            )
            ver = f"v{int(ver_hex, 16)}"
            proof_p = root / "gen" / "M0" / rt_lid / "PROOF.bend"
            tot, nb, db = _line_counts(proof_p)
            entries.append({
                "law_id": f"cong_{rt_lid.lower()}",
                "source_law_id": rt_lid,
                "milestone": "M0",
                "version": ver,
                "decoder": "dec_go",
                "encoder_sol": "enc_sol",
                "encoder_go": f"enc_go_{ver}",
                "parallel_generator": cc_lid,
                "tree_rt_generator": None,
                "getter": None,
                "core_lemma": "core_whisker_post",
                "predicted_status": "PROVED",
                "baseline_proof_path": str(proof_p.relative_to(root)),
                "baseline_total_lines": tot,
                "baseline_nonblank_lines": nb,
                "baseline_def_lines": db,
                "congruence_def_lines": 2,
            })

    # 2. M3 cross-language round-trip laws paired with PROVED pinned parallel laws and Go tree round-trip laws
    m3_laws_dir = root / "laws" / milestone
    m3_res_dir = root / "results" / milestone
    if m3_laws_dir.is_dir() and m3_res_dir.is_dir():
        m3_docs = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(m3_laws_dir.glob("L_par_*.json"))
            if (m3_res_dir / p.name).is_file()
            and json.loads((m3_res_dir / p.name).read_text(encoding="utf-8")).get("status") == "PROVED"
        ]
        cc_by_ver: dict[str, tuple[str, str, str, dict[str, str]]] = {}
        rt_go_by_key: dict[tuple[str, str, str], str] = {}
        rt_sol_list: list[tuple[str, str, str, str]] = []
        for d in m3_docs:
            st = d["statement"]
            lhs, rhs = st["claim"]["eq"]
            if "call" in lhs and "call" in rhs and rhs["call"] == "enc_sol" and d["law_id"].endswith("_pinned"):
                ver_hex = next(a["eq"][1]["bytes"] for a in st["assume"] if a["eq"][0].get("field") == "version")
                go_rec = f"R_{st['binders'][0]['type']}"
                fmap = {
                    a["eq"][1]["field"]: a["eq"][0]["field"]
                    for a in st["assume"]
                    if "field" in a["eq"][0] and "field" in a["eq"][1]
                }
                cc_by_ver[ver_hex] = (d["law_id"], lhs["call"], go_rec, fmap)
            elif (
                "call" in lhs
                and isinstance(lhs.get("args"), list)
                and len(lhs["args"]) == 1
                and "call" in lhs["args"][0]
            ):
                dec_fn, enc_fn, fld = lhs["call"], lhs["args"][0]["call"], rhs["some"]["field"]
                if enc_fn == "enc_sol":
                    ver_hex = next(a["eq"][1]["bytes"] for a in st["assume"] if a["eq"][0].get("field") == "version")
                    rt_sol_list.append((d["law_id"], ver_hex, dec_fn, fld))
                else:
                    rt_go_by_key[(enc_fn, dec_fn, fld)] = d["law_id"]

        for sol_lid, ver_hex, dec_fn, sol_fld in sorted(rt_sol_list):
            if ver_hex not in cc_by_ver:
                continue
            cc_lid, go_enc, go_rec, fmap = cc_by_ver[ver_hex]
            go_fld = fmap.get(sol_fld)
            if not go_fld or (go_enc, dec_fn, go_fld) not in rt_go_by_key:
                continue
            tree_lid = rt_go_by_key[(go_enc, dec_fn, go_fld)]
            ver = f"v{int(ver_hex, 16)}"
            rt_laws_txt = (root / "gen" / milestone / "laws" / tree_lid / "LAWS.bend").read_text(encoding="utf-8")
            m = re.search(r"Some\{M\.(get_[A-Za-z0-9_]+)\(h\)\}", rt_laws_txt)
            getter = m.group(1) if m else f"get_{go_rec[2:]}_{go_fld.replace('.', '__')}"
            proof_p = root / "gen" / milestone / "proofs" / sol_lid / "PROOF.bend"
            tot, nb, db = _line_counts(proof_p)
            entries.append({
                "law_id": f"cong_{sol_lid.lower()}",
                "source_law_id": sol_lid,
                "milestone": milestone,
                "version": ver,
                "decoder": dec_fn,
                "encoder_sol": "enc_sol",
                "encoder_go": go_enc,
                "go_carrier": go_rec,
                "parallel_generator": cc_lid,
                "tree_rt_generator": tree_lid,
                "getter": getter,
                "core_lemma": "core_whisker_post",
                "predicted_status": "PROVED",
                "baseline_proof_path": str(proof_p.relative_to(root)),
                "baseline_total_lines": tot,
                "baseline_nonblank_lines": nb,
                "baseline_def_lines": db,
                "congruence_def_lines": 3,
            })

    return entries


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
    w0 = mproofs.whisker_post_call(
        "M.Hdr", "List<&2, U32>", "Maybe<&2, List<&2, List<&2, U32>>>",
        "x => M.enc_sol(PAR0.pin_h(x))", "x => M.enc_go_v0(PAR0.pin_h(x))",
        "b => M.dec_go(b)", "PAR0.l_par_hdr_v0", arg="h",
    )
    w1 = mproofs.whisker_post_call(
        "M.Hdr", "List<&2, U32>", "Maybe<&2, List<&2, List<&2, U32>>>",
        "x => M.enc_sol(PAR1.pin_h(x))", "x => M.enc_go_v1(PAR1.pin_h(x))",
        "b => M.dec_go(b)", "PAR1.l_par_hdr_v1", arg="h",
    )
    cb = mproofs.cycle_basis_2_call(
        "M.Hdr", "M.Hdr", "List<&2, U32>", "Maybe<&2, List<&2, List<&2, U32>>>",
        "x => x", "a => M.enc_sol(RT0.pin_h(a))", "a => M.enc_go_v0(RT0.pin_h(a))",
        "b => M.dec_go(b)", "x => {Some{M.view(RT0.pin_h(x))} : Maybe<&2, List<&2, List<&2, U32>>>}",
        "par_gen", "RT0.l_rt_go_v0",
    )
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
        f"  {w0}",
        "",
        "def Laws.basis_sufficient_header_v1(h):",
        f"  {w1}",
        "",
        "def Laws.basis_sufficient_header(par_gen):",
        f"  {cb}",
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
    g1_call = mproofs.tree_unique_2_call(
        "M.R_BatchHeaderV1", "List<&2, U32>", "Maybe<&2, List<&2, U32>>",
        "x => M.BatchCache_createBatchHeaderWithSequencerSetHash(x)",
        "b => M.BatchHeaderBytes_BlobHashesHash(b)",
        "b => M.BatchHeaderBytes_BlobCommitHash(b)",
        "x => {Some{M.get_BatchHeaderV1__BatchHeaderV0__BlobVersionedHash(x)} : Maybe<&2, List<&2, U32>>}",
        "x => RT_BHH_V2.l_par_rt_batchcache_createbatchheaderwithsequencersethash_batchheaderbytes_blobhasheshash_v2(x)",
        "x => RT_BCH_V2.l_par_rt_batchcache_createbatchheaderwithsequencersethash_batchheaderbytes_blobcommithash_v2(x)",
        arg="h",
    )
    g2_call = mproofs.tree_unique_2_call(
        "M.R_BatchHeaderV0", "List<&2, U32>", "Maybe<&2, List<&2, U32>>",
        "x => M.BatchHeaderV0_Bytes(x)",
        "b => M.BatchHeaderBytes_BlobVersionedHash(b)",
        "b => M.BatchHeaderBytes_BlobCommitHash(b)",
        "x => {Some{M.get_BatchHeaderV0__BlobVersionedHash(x)} : Maybe<&2, List<&2, U32>>}",
        "x => RT_BVH_V0.l_par_rt_batchheaderv0_bytes_batchheaderbytes_blobversionedhash_v0(x)",
        "x => RT_BVH_V0_BCH.l_par_rt_batchheaderv0_bytes_batchheaderbytes_blobcommithash_v0(x)",
        arg="h",
    )
    g3_call = mproofs.whisker_post_call(
        "M.R_BatchHeaderV1", "List<&2, U32>", "Maybe<&2, List<&2, U32>>",
        "x => M.BatchHeaderV1_Bytes(CC1.pin_h(x))",
        "x => M.enc_sol(CC1.pin_k(k, x))",
        "b => M.BatchHeaderBytes_BatchIndex(b)",
        "x => CC1.l_par_cc_batchheaderv1_bytes_enc_sol_v1_pinned(x, k)",
        arg="h",
    )
    g4_call = mproofs.whisker_post_call(
        "X", "B", "Y",
        "x => load_sol(r(x))", "r", "l", "loop_gen",
    )
    suff_call = mproofs.cycle_basis_2_call(
        "M.R_BatchHeaderV1", "M.R_BatchHeaderV1", "Maybe<&2, List<&2, U32>>", "Maybe<&2, List<&2, U32>>",
        "x => x",
        "a => M.BatchHeaderBytes_BlobCommitHash(M.BatchCache_createBatchHeaderWithSequencerSetHash(a))",
        "a => M.BatchHeaderBytes_BlobHashesHash(M.BatchCache_createBatchHeaderWithSequencerSetHash(a))",
        "y => y",
        "x => {Some{M.get_BatchHeaderV1__BatchHeaderV0__BlobVersionedHash(x)} : Maybe<&2, List<&2, U32>>}",
        "a => (%Laws.basis_hl_gen_blob_hashes_hash(a) : {_ == M.BatchHeaderBytes_BlobHashesHash(M.BatchCache_createBatchHeaderWithSequencerSetHash(a)) : Maybe<&2, List<&2, U32>>}; {==})",
        "x => RT_BCH_V2.l_par_rt_batchcache_createbatchheaderwithsequencersethash_batchheaderbytes_blobcommithash_v2(x)",
        arg="h",
    )
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
        "import ../../laws/L_par_rt_BatchHeaderV0_Bytes_BatchHeaderBytes_BlobCommitHash_v0/LAWS.bend as RT_BVH_V0_BCH",
        "import ../../proofs/L_par_rt_BatchHeaderV0_Bytes_BatchHeaderBytes_BlobCommitHash_v0/PROOF.bend as RT_BVH_V0_BCH_P",
        "",
        "def Laws.basis_hl_gen_blob_hashes_hash(h):",
        f"  {g1_call}",
        "",
        "def Laws.basis_hl_gen_blob_versioned_hash(h):",
        f"  {g2_call}",
        "",
        "def Laws.basis_hl_gen_batch_header_v1_bytes(h, k):",
        f"  {g3_call}",
        "",
        "def Laws.basis_hl_gen_load_sol(X, B, Y, r, load_sol, l, loop_gen):",
        f"  {g4_call}",
        "",
        "def Laws.basis_sufficient_header_length(h):",
        f"  {suff_call}",
        "",
    ])


def congruence_laws_bend(entries: list[dict]) -> str:
    cc_alias_by_ver = {"v0": "CC0", "v1": "CC1", "v2": "CC2"}
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
        cc_alias = cc_alias_by_ver[ver]
        go_rec = e["go_carrier"]
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


def congruence_proof_bend(entries: list[dict]) -> str:
    cc_alias_by_ver = {"v0": "CC0", "v1": "CC1", "v2": "CC2"}
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
    defs: list[str] = [""]
    m3_idx = 0
    for e in entries:
        cid = e["law_id"]
        ver = e["version"]
        if e["milestone"] == "M0":
            idx = "0" if ver == "v0" else "1"
            defs.extend(
                mproofs.congruence_roundtrip_proof(
                    law_id=cid,
                    binders="h",
                    arg="h",
                    dom_ty="H0.Hdr",
                    mid_ty="List<&2, U32>",
                    cod_ty="Maybe<&2, List<&2, List<&2, U32>>>",
                    p_fn=f"x => H0.enc_sol(PAR{idx}.pin_h(x))",
                    q_fn=f"x => H0.enc_go_{ver}(PAR{idx}.pin_h(x))",
                    l_fn="b => H0.dec_go(b)",
                    par_law=f"PAR{idx}.l_par_hdr_{ver}",
                )
            )
        else:
            cc_alias = cc_alias_by_ver[ver]
            cc_fn = e["parallel_generator"].lower()
            go_enc = e["encoder_go"]
            go_rec = e["go_carrier"]
            dec_fn = e["decoder"]
            getter = e["getter"]
            rt_lid = e["tree_rt_generator"]
            rt_fn = rt_lid.lower()
            rt_alias = f"RT_{m3_idx}"
            m3_idx += 1
            imports.append(f"import ../../laws/{rt_lid}/LAWS.bend as {rt_alias}")
            imports.append(f"import ../../proofs/{rt_lid}/PROOF.bend as {rt_alias}_P")
            defs.extend(
                mproofs.congruence_roundtrip_proof(
                    law_id=cid,
                    binders="h, k",
                    arg="h",
                    dom_ty=f"M.{go_rec}",
                    mid_ty="List<&2, U32>",
                    cod_ty="Maybe<&2, List<&2, U32>>",
                    p_fn=f"x => M.{go_enc}({cc_alias}.pin_h(x))",
                    q_fn=f"x => M.enc_sol({cc_alias}.pin_k(k, x))",
                    l_fn=f"b => M.{dec_fn}(b)",
                    par_law=f"x => {cc_alias}.{cc_fn}(x, k)",
                    rt_law=f"{rt_alias}.{rt_fn}({cc_alias}.pin_h(h))",
                    rhs_expr=f"{{Some{{M.{getter}({cc_alias}.pin_h(h))}} : Maybe<&2, List<&2, U32>>}}",
                )
            )
    return "\n".join(imports + defs)


CANARY_SPECS: list[dict] = [
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
]


def _verify_group(root: Path, laws_p: Path, proof_p: Path, law_items: list[dict], cfg: dict | None = None) -> dict:
    r_chk = bend.check(proof_p, cfg)
    r_vrd = bend.check_verdict(proof_p, cfg)
    r_laws = bend.check_verdict(laws_p, cfg)
    ok = bool(r_chk.ok and r_vrd.ok and not r_laws.ok)
    status = "PROVED" if ok else "UNKNOWN"
    return {
        "laws_path": str(laws_p.relative_to(root)),
        "proof_path": str(proof_p.relative_to(root)),
        "law_count": len(law_items),
        "bend_check_ok": bool(r_chk.ok),
        "bend_verdict_ok": bool(r_vrd.ok),
        "laws_only_verdict_ok": bool(r_laws.ok),
        "laws": [{**item, "status": status} for item in law_items],
    }


def emit(root: Path = ROOT, milestone: str = "M3", out: Path | None = None, cfg: dict | None = None) -> dict:
    """Emit `gen/<M>/core`, `gen/<M>/basis/**`, and `results/<M>/basis.json`."""
    root = Path(root).resolve()
    gen_dir = root / "gen" / milestone
    core.emit(gen_dir, cfg=cfg, include_theory_core_i=True)

    basis_dir = gen_dir / "basis"
    hdr_dir = basis_dir / "header"
    hl_dir = basis_dir / "header_length"
    cong_dir = basis_dir / "congruence"
    for d in (hdr_dir, hl_dir, cong_dir):
        d.mkdir(parents=True, exist_ok=True)

    (hdr_dir / "LAWS.bend").write_text(header_laws_bend(), encoding="utf-8")
    (hdr_dir / "PROOF.bend").write_text(header_proof_bend(), encoding="utf-8")

    (hl_dir / "LAWS.bend").write_text(header_length_laws_bend(), encoding="utf-8")
    (hl_dir / "PROOF.bend").write_text(header_length_proof_bend(), encoding="utf-8")

    entries = discover_congruence_entries(root, milestone)
    cong_laws_txt = congruence_laws_bend(entries)
    cong_proof_txt = congruence_proof_bend(entries)
    (cong_dir / "LAWS.bend").write_text(cong_laws_txt, encoding="utf-8")
    (cong_dir / "PROOF.bend").write_text(cong_proof_txt, encoding="utf-8")

    core_laws = [{"law_id": e[0], "proof_class": e[4]} for e in core.THEORY_CORE_I]
    hdr_laws = [
        {"law_id": "basis_sufficient_header_v0", "core_lemma": "core_whisker_post"},
        {"law_id": "basis_sufficient_header_v1", "core_lemma": "core_whisker_post"},
        {"law_id": "basis_sufficient_header", "core_lemma": "core_cycle_basis_2"},
    ]
    hl_laws = [
        {"law_id": "basis_hl_gen_blob_hashes_hash", "core_lemma": "core_tree_unique_2"},
        {"law_id": "basis_hl_gen_blob_versioned_hash", "core_lemma": "core_tree_unique_2"},
        {"law_id": "basis_hl_gen_batch_header_v1_bytes", "core_lemma": "core_whisker_post"},
        {"law_id": "basis_hl_gen_load_sol", "core_lemma": "core_whisker_post"},
        {"law_id": "basis_sufficient_header_length", "core_lemma": "core_cycle_basis_2"},
    ]
    cong_laws = [
        {
            "law_id": e["law_id"],
            "source_law_id": e["source_law_id"],
            "milestone": e["milestone"],
            "core_lemma": e["core_lemma"],
        }
        for e in entries
    ]

    groups = {
        "theory_core_i": _verify_group(
            root, gen_dir / "core" / "LAWS.bend", gen_dir / "core" / "PROOF.bend", core_laws, cfg=cfg
        ),
        "header": _verify_group(root, hdr_dir / "LAWS.bend", hdr_dir / "PROOF.bend", hdr_laws, cfg=cfg),
        "header_length": _verify_group(root, hl_dir / "LAWS.bend", hl_dir / "PROOF.bend", hl_laws, cfg=cfg),
        "congruence": _verify_group(root, cong_dir / "LAWS.bend", cong_dir / "PROOF.bend", cong_laws, cfg=cfg),
    }

    canary_results: list[dict] = []
    with tempfile.TemporaryDirectory(dir=basis_dir) as td:
        td_p = Path(td)
        for c in CANARY_SPECS:
            laws_p = td_p / "LAWS.bend"
            proof_p = td_p / "PROOF.bend"
            laws_p.write_text(c["laws_bend"], encoding="utf-8")
            proof_p.write_text(c["proof_bend"], encoding="utf-8")
            r_chk = bend.check(proof_p, cfg)
            r_vrd = bend.check_verdict(proof_p, cfg)
            refuted = not r_chk.ok and not r_vrd.ok
            canary_results.append({
                "canary_id": c["canary_id"],
                "group": c["group"],
                "bend_check_ok": bool(r_chk.ok),
                "bend_verdict_ok": bool(r_vrd.ok),
                "status": "REFUTED" if refuted else "UNEXPECTED_PASS",
                "doc": c["doc"],
            })

    cong_tot, cong_nb, cong_db = _line_counts(cong_dir / "PROOF.bend")
    line_comparison = {
        "law_count": len(entries),
        "m0_count": sum(1 for e in entries if e["milestone"] == "M0"),
        "m3_count": sum(1 for e in entries if e["milestone"] != "M0"),
        "baseline_total_lines": sum(e["baseline_total_lines"] for e in entries),
        "baseline_nonblank_lines": sum(e["baseline_nonblank_lines"] for e in entries),
        "baseline_def_lines": sum(e["baseline_def_lines"] for e in entries),
        "congruence_proof_lines": cong_tot,
        "congruence_nonblank_lines": cong_nb,
        "congruence_def_lines": cong_db,
        "congruence_laws_file_lines": len(cong_laws_txt.splitlines()),
    }

    summary = {
        "theory_core_i_laws": len(core_laws),
        "header_basis_laws": len(hdr_laws),
        "header_length_basis_laws": len(hl_laws),
        "congruence_laws": len(cong_laws),
        "total_proved_laws": sum(
            len(g["laws"]) for g in groups.values() if all(x["status"] == "PROVED" for x in g["laws"])
        ),
        "canaries_refuted": sum(1 for c in canary_results if c["status"] == "REFUTED"),
    }

    result_doc = {
        "schema": "holon-theory-core-i/1.0",
        "iteration": "I42",
        "milestone": milestone,
        "summary": summary,
        "groups": groups,
        "canaries": canary_results,
        "congruence_line_comparison": line_comparison,
    }

    out_path = Path(out) if out is not None else (root / "results" / milestone / "basis.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result_doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon basis", description="Emit Theory core I basis and congruence proofs (I42)")
    ap.add_argument("--milestone", default="M3", help="target milestone (default: M3)")
    ap.add_argument("--root", type=Path, default=ROOT, help="repository root")
    ap.add_argument("--out", type=Path, default=None, help="output JSON path (default: results/<M>/basis.json)")
    args = ap.parse_args(argv)
    doc = emit(root=args.root, milestone=args.milestone, out=args.out)
    s = doc["summary"]
    print(f"BASIS OK: {s['total_proved_laws']} proved laws, {s['canaries_refuted']} canaries refuted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
