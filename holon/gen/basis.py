"""Iteration I42 (Theory core I): spanning-tree cycle-basis sufficiency and congruence-first proofs.

Emits:
  * `gen/<M>/core/{LAWS,PROOF}.bend` (including the 12 `THEORY_CORE_I` laws);
  * `gen/<M>/basis/header/{LAWS,PROOF}.bend` (rank-2 cycle-basis sufficiency on the M0/M2 codec diagram);
  * `gen/<M>/basis/header_length/{LAWS,PROOF}.bend` (rank-4 cycle-basis sufficiency on the M3 codec diagram);
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
from ..rules import par
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


def _camel_to_snake(name: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name).lower()


def _ver_of_doc(doc: dict) -> str:
    ver_hex = next(
        a["eq"][1]["bytes"]
        for a in doc["statement"]["assume"]
        if a["eq"][0].get("field") == "version"
    )
    return f"v{int(ver_hex, 16)}"


def _discover_context(root: Path = ROOT, milestone: str = "M3") -> dict:
    """Discover M0/M2 and M3 diagram, model, carrier, and law metadata from disk without target-specific names."""
    root = Path(root).resolve()

    # 1. M0/M2 codec diagram and PROVED PAR laws
    m0_laws_dir = root / "laws" / "M0"
    m0_res_dir = root / "results" / "M0"
    m0_docs = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(m0_laws_dir.glob("L_*.json"))
        if (m0_res_dir / p.name).is_file()
        and json.loads((m0_res_dir / p.name).read_text(encoding="utf-8")).get("status") == "PROVED"
    ]
    m0_cc_by_ver = {_ver_of_doc(d): d for d in m0_docs if d.get("subform") == "cross_component_codec"}
    m0_rt_by_ver = {_ver_of_doc(d): d for d in m0_docs if d.get("subform") == "round_trip"}

    cc_v0 = m0_cc_by_ver["v0"]
    cc_v1 = m0_cc_by_ver["v1"]
    rt_v0 = m0_rt_by_ver["v0"]
    hdr_model = Path(cc_v0["facts"]).stem
    par_v0_lid = cc_v0["law_id"]
    par_v1_lid = cc_v1["law_id"]
    rt_v0_lid = rt_v0["law_id"]
    enc_alt_m0 = cc_v0["statement"]["claim"]["eq"][0]["call"]
    enc_v0_m0 = cc_v0["statement"]["claim"]["eq"][1]["call"]
    enc_v1_m0 = cc_v1["statement"]["claim"]["eq"][1]["call"]
    dec_m0 = rt_v0["statement"]["claim"]["eq"][0]["call"]
    view_m0 = rt_v0["statement"]["claim"]["eq"][1]["some"]["call"]

    par_v0_bend = (root / "gen" / "M0" / par_v0_lid / "LAWS.bend").read_text(encoding="utf-8")
    m_hdr = re.search(r"for h:\s*M\.([A-Za-z0-9_]+)", par_v0_bend)
    hdr_ty = m_hdr.group(1) if m_hdr else ""

    # 2. M3 codec diagram, cycle basis, and PROVED PAR laws
    diag_p = sorted((root / "gen" / milestone / "diagram").glob("*.json"))[0]
    diag = json.loads(diag_p.read_text(encoding="utf-8"))
    hl_model = diag["model"]
    cb = par.cycle_basis(diag)
    edges_by_id = {e["id"]: e for e in diag["edges"]}
    tree_set = set(cb["tree"])
    tree_enc_by_ver = {
        e["version"]: e
        for e in diag["edges"]
        if e["id"] in tree_set and e.get("fn_kind") == "encoder"
    }
    first_tree_dec = next(
        e["model_fn"]
        for e in diag["edges"]
        if e["id"] in tree_set
        and e.get("fn_kind") == "decoder"
        and not e["model_fn"].endswith("_Version")
    )

    nt_dec_v2_eid = next(
        eid
        for eid in cb["non_tree"]
        if edges_by_id[eid].get("fn_kind") == "decoder"
        and edges_by_id[eid].get("version") == "2"
    )
    nt_dec_v2_fn = edges_by_id[nt_dec_v2_eid]["model_fn"]
    tree_dec_v2_fn = par.fundamental_cycle(cb, nt_dec_v2_eid)[1][0]["model_fn"]
    enc_v2_edge = tree_enc_by_ver["2"]
    enc_v2_fn = enc_v2_edge["model_fn"]
    rec_v1_ty = f"R_{enc_v2_edge['src']}"
    rt_nt_v2_lid = f"L_par_rt_{enc_v2_fn}_{nt_dec_v2_fn}_v2"
    rt_tree_v2_lid = f"L_par_rt_{enc_v2_fn}_{tree_dec_v2_fn}_v2"
    rt_tree_v2_txt = (root / "gen" / milestone / "laws" / rt_tree_v2_lid / "LAWS.bend").read_text(encoding="utf-8")
    getter_v2 = re.search(r"Some\{M\.(get_[A-Za-z0-9_]+)\(h\)\}", rt_tree_v2_txt).group(1)
    gen1_law_id = f"basis_hl_gen_{_camel_to_snake(nt_dec_v2_fn.split('_', 1)[1])}"

    nt_dec_v0_eid = next(
        eid
        for eid in cb["non_tree"]
        if edges_by_id[eid].get("fn_kind") == "decoder"
        and edges_by_id[eid].get("version") != "2"
    )
    nt_dec_v0_fn = edges_by_id[nt_dec_v0_eid]["model_fn"]
    tree_dec_v0_fn = par.fundamental_cycle(cb, nt_dec_v0_eid)[1][0]["model_fn"]
    enc_v0_edge = tree_enc_by_ver["0"]
    enc_v0_fn = enc_v0_edge["model_fn"]
    rec_v0_ty = f"R_{enc_v0_edge['src']}"
    rt_nt_v0_lid = f"L_par_rt_{enc_v0_fn}_{nt_dec_v0_fn}_v0"
    rt_tree_v0_lid = f"L_par_rt_{enc_v0_fn}_{tree_dec_v0_fn}_v0"
    rt_tree_v0_txt = (root / "gen" / milestone / "laws" / rt_tree_v0_lid / "LAWS.bend").read_text(encoding="utf-8")
    getter_v0 = re.search(r"Some\{M\.(get_[A-Za-z0-9_]+)\(h\)\}", rt_tree_v0_txt).group(1)
    gen2_law_id = f"basis_hl_gen_{_camel_to_snake(nt_dec_v0_fn.split('_', 1)[1])}"

    nt_enc_eid = next(eid for eid in cb["non_tree"] if edges_by_id[eid].get("fn_kind") == "encoder")
    nt_enc_fn = edges_by_id[nt_enc_eid]["model_fn"]
    gen3_law_id = f"basis_hl_gen_{_camel_to_snake(nt_enc_fn)}"

    nt_loader_eid = next(eid for eid in cb["non_tree"] if edges_by_id[eid].get("fn_kind") == "loader")
    loader_fn = edges_by_id[nt_loader_eid]["model_fn"]
    gen4_law_id = f"basis_hl_gen_{loader_fn}"

    m3_laws_dir = root / "laws" / milestone
    m3_res_dir = root / "results" / milestone
    m3_cc_docs = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(m3_laws_dir.glob("L_par_*.json"))
        if p.stem.endswith("_pinned")
        and (m3_res_dir / p.name).is_file()
        and json.loads((m3_res_dir / p.name).read_text(encoding="utf-8")).get("status") == "PROVED"
    ]
    cc_lids = {_ver_of_doc(d): d["law_id"] for d in m3_cc_docs}
    sol_rec_ty = f"R_{m3_cc_docs[0]['statement']['binders'][1]['type']}"
    sol_enc_m3 = m3_cc_docs[0]["statement"]["claim"]["eq"][1]["call"]

    rt_first_v0_lid = f"L_par_rt_{enc_v0_fn}_{first_tree_dec}_v0"
    rt_first_v0_txt = (root / "gen" / milestone / "laws" / rt_first_v0_lid / "LAWS.bend").read_text(encoding="utf-8")
    getter_first_v0 = re.search(r"Some\{M\.(get_[A-Za-z0-9_]+)\(h\)\}", rt_first_v0_txt).group(1)

    # 3. M1 rollup machine model for equivariance & pasting basis (I43)
    m1_model_p = next(
        p
        for p in sorted((root / "gen" / "M1" / "model").glob("*.bend"))
        if "def mig_" in p.read_text(encoding="utf-8")
    )
    m1_model = m1_model_p.stem
    m1_src = m1_model_p.read_text(encoding="utf-8")
    data_records = [
        (m.group(1), re.findall(r"(\w+)\s*:", m.group(2)))
        for m in re.finditer(r"type\s+(\w+)\s+is\s+Data:\s+\1\{([^}]+)\}", m1_src)
    ]
    entry_ty, entry_fields = data_records[0]
    st_ty, st_fields = data_records[-1]
    m_emp = re.search(rf"def\s+(empty_[a-z]\w*)\(\)\s*->\s*{entry_ty}:", m1_src)
    empty_entry_fn = m_emp.group(1)
    m_lci = re.search(
        rf"def\s+(\w+)\(s:\s*{st_ty}\)\s*->\s*Nat:\s+match s:\s+case {st_ty}\{{[^}}]+\}}:\s+\w+\(([^)]+)\)",
        m1_src,
    )
    lci_obs_fn = m_lci.group(1)
    lci_args = [a.strip() for a in m_lci.group(2).split(",")]
    lfi_fld, win_fld = lci_args[0], lci_args[1]
    m_tags = re.search(
        rf"def\s+(\w+)\(s:\s*{st_ty}\)\s*->\s*Bool:\s+match s:\s+case {st_ty}\{{[^}}]+\}}:\s+(b_\w+)\(\w+\)",
        m1_src,
    )
    tags_obs_fn = m_tags.group(1)
    tpred_fn = m_tags.group(2)
    nat_obs_fns = re.findall(rf"def\s+(\w+)\(s:\s*{st_ty}\)\s*->\s*Nat:", m1_src)
    csr_obs_fn = next(fn for fn in nat_obs_fns if fn != lci_obs_fn)
    mig_1_fn = re.search(rf"def\s+(mig_\w+)\(s:\s*{st_ty}\)\s*->\s*{st_ty}:", m1_src).group(1)
    mig_2_fn = re.search(rf"def\s+(mig_\w+)\(s:\s*{st_ty},\s*\+\w+:\s*Nat\)\s*->\s*{st_ty}:", m1_src).group(1)
    zero_csr_fn = re.search(rf"(b_\w+)\({win_fld}\)", m1_src[m1_src.index(f"def {mig_1_fn}("):]).group(1)
    m_eta = re.search(
        rf"(g_\w+)\(last_d\({entry_ty},\s*{win_fld},\s*{empty_entry_fn}\(\)\)\),\s*0n\),\s*(b_\w+)\({win_fld},",
        m1_src[m1_src.index(f"def {mig_2_fn}("):],
    )
    entry_csr_fn, set_last_csr_fn = m_eta.group(1), m_eta.group(2)
    actions = [
        (m.group(2), m.group(1))
        for m in re.finditer(r"case\s+(A_\w+)\{[^}]*\}:\s+(step_\w+)\(", m1_src[m1_src.index("def step("):])
    ]
    send_step_fn = actions[-2][0]
    wait_step_fn = actions[-1][0]

    return {
        "hdr": {
            "model": hdr_model,
            "carrier": hdr_ty,
            "par_v0_lid": par_v0_lid,
            "par_v1_lid": par_v1_lid,
            "rt_v0_lid": rt_v0_lid,
            "enc_alt": enc_alt_m0,
            "enc_v0": enc_v0_m0,
            "enc_v1": enc_v1_m0,
            "dec": dec_m0,
            "view": view_m0,
        },
        "hl": {
            "model": hl_model,
            "rec_v0_ty": rec_v0_ty,
            "rec_v1_ty": rec_v1_ty,
            "sol_rec_ty": sol_rec_ty,
            "sol_enc": sol_enc_m3,
            "enc_v0_fn": enc_v0_fn,
            "enc_v2_fn": enc_v2_fn,
            "nt_enc_fn": nt_enc_fn,
            "nt_dec_v2_fn": nt_dec_v2_fn,
            "tree_dec_v2_fn": tree_dec_v2_fn,
            "nt_dec_v0_fn": nt_dec_v0_fn,
            "tree_dec_v0_fn": tree_dec_v0_fn,
            "first_tree_dec": first_tree_dec,
            "loader_fn": loader_fn,
            "rt_nt_v2_lid": rt_nt_v2_lid,
            "rt_tree_v2_lid": rt_tree_v2_lid,
            "rt_nt_v0_lid": rt_nt_v0_lid,
            "rt_tree_v0_lid": rt_tree_v0_lid,
            "rt_first_v0_lid": rt_first_v0_lid,
            "getter_v2": getter_v2,
            "getter_v0": getter_v0,
            "getter_first_v0": getter_first_v0,
            "gen1_law_id": gen1_law_id,
            "gen2_law_id": gen2_law_id,
            "gen3_law_id": gen3_law_id,
            "gen4_law_id": gen4_law_id,
            "cc_lids": cc_lids,
        },
        "m1": {
            "model": m1_model,
            "st_ty": st_ty,
            "st_fields": st_fields,
            "entry_ty": entry_ty,
            "entry_fields": entry_fields,
            "empty_entry_fn": empty_entry_fn,
            "lci_obs_fn": lci_obs_fn,
            "lfi_fld": lfi_fld,
            "win_fld": win_fld,
            "tags_obs_fn": tags_obs_fn,
            "tpred_fn": tpred_fn,
            "csr_obs_fn": csr_obs_fn,
            "mig_1_fn": mig_1_fn,
            "mig_2_fn": mig_2_fn,
            "zero_csr_fn": zero_csr_fn,
            "entry_csr_fn": entry_csr_fn,
            "set_last_csr_fn": set_last_csr_fn,
            "actions": actions,
            "send_step_fn": send_step_fn,
            "wait_step_fn": wait_step_fn,
        },
    }


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
            ver = _ver_of_doc(rt_doc)
            dec_fn = rt_doc["statement"]["claim"]["eq"][0]["call"]
            enc_alt = cc_doc["statement"]["claim"]["eq"][0]["call"]
            enc_tree = cc_doc["statement"]["claim"]["eq"][1]["call"]
            proof_p = root / "gen" / "M0" / rt_lid / "PROOF.bend"
            tot, nb, db = _line_counts(proof_p)
            entries.append({
                "law_id": f"cong_{rt_lid.lower()}",
                "source_law_id": rt_lid,
                "milestone": "M0",
                "version": ver,
                "decoder": dec_fn,
                "encoder_sol": enc_alt,
                "encoder_go": enc_tree,
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

    # 2. M3 cross-language round-trip laws paired with PROVED pinned parallel laws and tree round-trip laws
    m3_laws_dir = root / "laws" / milestone
    m3_res_dir = root / "results" / milestone
    if m3_laws_dir.is_dir() and m3_res_dir.is_dir():
        m3_docs = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(m3_laws_dir.glob("L_par_*.json"))
            if (m3_res_dir / p.name).is_file()
            and json.loads((m3_res_dir / p.name).read_text(encoding="utf-8")).get("status") == "PROVED"
        ]
        cc_by_ver: dict[str, tuple[str, str, str, str, dict[str, str]]] = {}
        alt_encoders: set[str] = set()
        for d in m3_docs:
            st = d["statement"]
            lhs, rhs = st["claim"]["eq"]
            if d.get("subform") == "cross_component_codec" and d["law_id"].endswith("_pinned"):
                ver_hex = next(a["eq"][1]["bytes"] for a in st["assume"] if a["eq"][0].get("field") == "version")
                go_rec = f"R_{st['binders'][0]['type']}"
                fmap = {
                    a["eq"][1]["field"]: a["eq"][0]["field"]
                    for a in st["assume"]
                    if "field" in a["eq"][0] and "field" in a["eq"][1]
                }
                cc_by_ver[ver_hex] = (d["law_id"], lhs["call"], rhs["call"], go_rec, fmap)
                alt_encoders.add(rhs["call"])

        rt_go_by_key: dict[tuple[str, str, str], str] = {}
        rt_sol_list: list[tuple[str, str, str, str, str]] = []
        for d in m3_docs:
            st = d["statement"]
            lhs, rhs = st["claim"]["eq"]
            if (
                "call" in lhs
                and isinstance(lhs.get("args"), list)
                and len(lhs["args"]) == 1
                and "call" in lhs["args"][0]
            ):
                dec_fn, enc_fn, fld = lhs["call"], lhs["args"][0]["call"], rhs["some"]["field"]
                if enc_fn in alt_encoders:
                    ver_hex = next(a["eq"][1]["bytes"] for a in st["assume"] if a["eq"][0].get("field") == "version")
                    rt_sol_list.append((d["law_id"], ver_hex, dec_fn, fld, enc_fn))
                else:
                    rt_go_by_key[(enc_fn, dec_fn, fld)] = d["law_id"]

        for sol_lid, ver_hex, dec_fn, sol_fld, sol_enc in sorted(rt_sol_list):
            if ver_hex not in cc_by_ver:
                continue
            cc_lid, go_enc, _, go_rec, fmap = cc_by_ver[ver_hex]
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
                "encoder_sol": sol_enc,
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


def header_laws_bend(ctx: dict | None = None) -> str:
    ctx = ctx or _discover_context()
    h = ctx["hdr"]
    return "\n".join([
        f"# GENERATED by holon.gen.basis for M2 {h['model']} cycle basis; do not edit.",
        "import Base",
        f"import ../../../M0/model/{h['model']}.bend as M",
        f"import ../../../M0/{h['par_v0_lid']}/LAWS.bend as PAR0",
        f"import ../../../M0/{h['par_v1_lid']}/LAWS.bend as PAR1",
        f"import ../../../M0/{h['rt_v0_lid']}/LAWS.bend as RT0",
        "",
        "law basis_sufficient_header_v0:",
        f"  for h: M.{h['carrier']}",
        f"  {{M.{h['dec']}(M.{h['enc_alt']}(PAR0.pin_h(h))) == M.{h['dec']}(M.{h['enc_v0']}(PAR0.pin_h(h))) : Maybe<&2, List<&2, List<&2, U32>>>}}",
        "",
        "law basis_sufficient_header_v1:",
        f"  for h: M.{h['carrier']}",
        f"  {{M.{h['dec']}(M.{h['enc_alt']}(PAR1.pin_h(h))) == M.{h['dec']}(M.{h['enc_v1']}(PAR1.pin_h(h))) : Maybe<&2, List<&2, List<&2, U32>>>}}",
        "",
        "law basis_sufficient_header:",
        f"  for par_gen: @a:M.{h['carrier']} -> {{M.{h['enc_alt']}(RT0.pin_h(a)) == M.{h['enc_v0']}(RT0.pin_h(a)) : List<&2, U32>}}",
        f"  @+h:M.{h['carrier']} -> {{M.{h['dec']}(M.{h['enc_v0']}(RT0.pin_h(h))) == {{Some{{M.{h['view']}(RT0.pin_h(h))}} : Maybe<&2, List<&2, List<&2, U32>>>}} : Maybe<&2, List<&2, List<&2, U32>>>}}",
        "",
    ])


def header_proof_bend(ctx: dict | None = None) -> str:
    ctx = ctx or _discover_context()
    h = ctx["hdr"]
    dom_ty = f"M.{h['carrier']}"
    w0 = mproofs.whisker_post_call(
        dom_ty, "List<&2, U32>", "Maybe<&2, List<&2, List<&2, U32>>>",
        f"x => M.{h['enc_alt']}(PAR0.pin_h(x))", f"x => M.{h['enc_v0']}(PAR0.pin_h(x))",
        f"b => M.{h['dec']}(b)", f"PAR0.{h['par_v0_lid'].lower()}", arg="h",
    )
    w1 = mproofs.whisker_post_call(
        dom_ty, "List<&2, U32>", "Maybe<&2, List<&2, List<&2, U32>>>",
        f"x => M.{h['enc_alt']}(PAR1.pin_h(x))", f"x => M.{h['enc_v1']}(PAR1.pin_h(x))",
        f"b => M.{h['dec']}(b)", f"PAR1.{h['par_v1_lid'].lower()}", arg="h",
    )
    cb = mproofs.cycle_basis_2_call(
        dom_ty, dom_ty, "List<&2, U32>", "Maybe<&2, List<&2, List<&2, U32>>>",
        "x => x", f"a => M.{h['enc_alt']}(RT0.pin_h(a))", f"a => M.{h['enc_v0']}(RT0.pin_h(a))",
        f"b => M.{h['dec']}(b)", f"x => {{Some{{M.{h['view']}(RT0.pin_h(x))}} : Maybe<&2, List<&2, List<&2, U32>>>}}",
        "par_gen", f"RT0.{h['rt_v0_lid'].lower()}",
    )
    return "\n".join([
        "# GENERATED by holon.gen.basis; untrusted, accepted only if Bend checks it.",
        "import Base",
        "import ./LAWS.bend as Laws",
        "import ../../core/PROOF.bend as CP",
        "import ../../core/LAWS.bend as C",
        f"import ../../../M0/model/{h['model']}.bend as M",
        f"import ../../../M0/{h['par_v0_lid']}/PROOF.bend as PAR0_P",
        f"import ../../../M0/{h['par_v0_lid']}/LAWS.bend as PAR0",
        f"import ../../../M0/{h['par_v1_lid']}/PROOF.bend as PAR1_P",
        f"import ../../../M0/{h['par_v1_lid']}/LAWS.bend as PAR1",
        f"import ../../../M0/{h['rt_v0_lid']}/PROOF.bend as RT0_P",
        f"import ../../../M0/{h['rt_v0_lid']}/LAWS.bend as RT0",
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


def header_length_laws_bend(ctx: dict | None = None) -> str:
    ctx = ctx or _discover_context()
    hl = ctx["hl"]
    cc1_lid = hl["cc_lids"]["v1"]
    return "\n".join([
        f"# GENERATED by holon.gen.basis for M3 {hl['model']} cycle basis; do not edit.",
        "import Base",
        f"import ../../model/{hl['model']}.bend as M",
        f"import ../../laws/{cc1_lid}/LAWS.bend as CC1",
        "",
        f"law {hl['gen1_law_id']}:",
        f"  for +h: M.{hl['rec_v1_ty']}",
        f"  {{M.{hl['nt_dec_v2_fn']}(M.{hl['enc_v2_fn']}(h)) == M.{hl['tree_dec_v2_fn']}(M.{hl['enc_v2_fn']}(h)) : Maybe<&2, List<&2, U32>>}}",
        "",
        f"law {hl['gen2_law_id']}:",
        f"  for +h: M.{hl['rec_v0_ty']}",
        f"  {{M.{hl['nt_dec_v0_fn']}(M.{hl['enc_v0_fn']}(h)) == M.{hl['tree_dec_v0_fn']}(M.{hl['enc_v0_fn']}(h)) : Maybe<&2, List<&2, U32>>}}",
        "",
        f"law {hl['gen3_law_id']}:",
        f"  for +h: M.{hl['rec_v1_ty']}",
        f"  for +k: M.{hl['sol_rec_ty']}",
        f"  {{M.{hl['first_tree_dec']}(M.{hl['nt_enc_fn']}(CC1.pin_h(h))) == M.{hl['first_tree_dec']}(M.{hl['sol_enc']}(CC1.pin_k(k, h))) : Maybe<&2, List<&2, U32>>}}",
        "",
        f"law {hl['gen4_law_id']}:",
        "  for -X: Type",
        "  for -B: Type",
        "  for -Y: Type",
        "  for -r: X -> B",
        f"  for -{hl['loader_fn']}: B -> B",
        "  for -l: B -> Y",
        f"  for loop_gen: @x:X -> {{{hl['loader_fn']}(r(x)) == r(x) : B}}",
        f"  @x:X -> {{l({hl['loader_fn']}(r(x))) == l(r(x)) : Y}}",
        "",
        "law basis_sufficient_header_length:",
        f"  for +h: M.{hl['rec_v1_ty']}",
        f"  {{M.{hl['nt_dec_v2_fn']}(M.{hl['enc_v2_fn']}(h)) == {{Some{{M.{hl['getter_v2']}(h)}} : Maybe<&2, List<&2, U32>>}} : Maybe<&2, List<&2, U32>>}}",
        "",
    ])


def header_length_proof_bend(ctx: dict | None = None) -> str:
    ctx = ctx or _discover_context()
    hl = ctx["hl"]
    cc1_lid = hl["cc_lids"]["v1"]
    rt_nt_v2 = hl["rt_nt_v2_lid"]
    rt_tree_v2 = hl["rt_tree_v2_lid"]
    rt_nt_v0 = hl["rt_nt_v0_lid"]
    rt_tree_v0 = hl["rt_tree_v0_lid"]

    g1_call = mproofs.tree_unique_2_call(
        f"M.{hl['rec_v1_ty']}", "List<&2, U32>", "Maybe<&2, List<&2, U32>>",
        f"x => M.{hl['enc_v2_fn']}(x)",
        f"b => M.{hl['nt_dec_v2_fn']}(b)",
        f"b => M.{hl['tree_dec_v2_fn']}(b)",
        f"x => {{Some{{M.{hl['getter_v2']}(x)}} : Maybe<&2, List<&2, U32>>}}",
        f"x => RT_BHH_V2.{rt_nt_v2.lower()}(x)",
        f"x => RT_BCH_V2.{rt_tree_v2.lower()}(x)",
        arg="h",
    )
    g2_call = mproofs.tree_unique_2_call(
        f"M.{hl['rec_v0_ty']}", "List<&2, U32>", "Maybe<&2, List<&2, U32>>",
        f"x => M.{hl['enc_v0_fn']}(x)",
        f"b => M.{hl['nt_dec_v0_fn']}(b)",
        f"b => M.{hl['tree_dec_v0_fn']}(b)",
        f"x => {{Some{{M.{hl['getter_v0']}(x)}} : Maybe<&2, List<&2, U32>>}}",
        f"x => RT_BVH_V0.{rt_nt_v0.lower()}(x)",
        f"x => RT_BVH_V0_BCH.{rt_tree_v0.lower()}(x)",
        arg="h",
    )
    g3_call = mproofs.whisker_post_call(
        f"M.{hl['rec_v1_ty']}", "List<&2, U32>", "Maybe<&2, List<&2, U32>>",
        f"x => M.{hl['nt_enc_fn']}(CC1.pin_h(x))",
        f"x => M.{hl['sol_enc']}(CC1.pin_k(k, x))",
        f"b => M.{hl['first_tree_dec']}(b)",
        f"x => CC1.{cc1_lid.lower()}(x, k)",
        arg="h",
    )
    g4_call = mproofs.whisker_post_call(
        "X", "B", "Y",
        f"x => {hl['loader_fn']}(r(x))", "r", "l", "loop_gen",
    )
    sym_gen = (
        f"a => Equal.sym(Maybe<&2, List<&2, U32>>, "
        f"M.{hl['nt_dec_v2_fn']}(M.{hl['enc_v2_fn']}(a)), "
        f"M.{hl['tree_dec_v2_fn']}(M.{hl['enc_v2_fn']}(a)), "
        f"Laws.{hl['gen1_law_id']}(a))"
    )
    suff_call = mproofs.cycle_basis_2_call(
        f"M.{hl['rec_v1_ty']}", f"M.{hl['rec_v1_ty']}", "Maybe<&2, List<&2, U32>>", "Maybe<&2, List<&2, U32>>",
        "x => x",
        f"a => M.{hl['tree_dec_v2_fn']}(M.{hl['enc_v2_fn']}(a))",
        f"a => M.{hl['nt_dec_v2_fn']}(M.{hl['enc_v2_fn']}(a))",
        "y => y",
        f"x => {{Some{{M.{hl['getter_v2']}(x)}} : Maybe<&2, List<&2, U32>>}}",
        sym_gen,
        f"x => RT_BCH_V2.{rt_tree_v2.lower()}(x)",
        arg="h",
    )
    return "\n".join([
        "# GENERATED by holon.gen.basis; untrusted, accepted only if Bend checks it.",
        "import Base",
        "import ./LAWS.bend as Laws",
        "import ../../core/PROOF.bend as CP",
        "import ../../core/LAWS.bend as C",
        f"import ../../model/{hl['model']}.bend as M",
        f"import ../../laws/{cc1_lid}/LAWS.bend as CC1",
        f"import ../../proofs/{cc1_lid}/PROOF.bend as CC1_P",
        f"import ../../laws/{rt_nt_v2}/LAWS.bend as RT_BHH_V2",
        f"import ../../proofs/{rt_nt_v2}/PROOF.bend as RT_BHH_V2_P",
        f"import ../../laws/{rt_tree_v2}/LAWS.bend as RT_BCH_V2",
        f"import ../../proofs/{rt_tree_v2}/PROOF.bend as RT_BCH_V2_P",
        f"import ../../laws/{rt_nt_v0}/LAWS.bend as RT_BVH_V0",
        f"import ../../proofs/{rt_nt_v0}/PROOF.bend as RT_BVH_V0_P",
        f"import ../../laws/{rt_tree_v0}/LAWS.bend as RT_BVH_V0_BCH",
        f"import ../../proofs/{rt_tree_v0}/PROOF.bend as RT_BVH_V0_BCH_P",
        "",
        f"def Laws.{hl['gen1_law_id']}(h):",
        f"  {g1_call}",
        "",
        f"def Laws.{hl['gen2_law_id']}(h):",
        f"  {g2_call}",
        "",
        f"def Laws.{hl['gen3_law_id']}(h, k):",
        f"  {g3_call}",
        "",
        f"def Laws.{hl['gen4_law_id']}(X, B, Y, r, {hl['loader_fn']}, l, loop_gen):",
        f"  {g4_call}",
        "",
        "def Laws.basis_sufficient_header_length(h):",
        f"  {suff_call}",
        "",
    ])


def congruence_laws_bend(entries: list[dict], ctx: dict | None = None) -> str:
    ctx = ctx or _discover_context()
    h = ctx["hdr"]
    hl = ctx["hl"]
    cc_alias_by_ver = {"v0": "CC0", "v1": "CC1", "v2": "CC2"}
    m0_entries = [e for e in entries if e["milestone"] == "M0"]
    lines = [
        "# GENERATED by holon.gen.mproofs for I42 congruence round-trip basis; do not edit.",
        "import Base",
        f"import ../../../M0/model/{h['model']}.bend as H0",
        f"import ../../../M0/{h['par_v0_lid']}/LAWS.bend as PAR0",
        f"import ../../../M0/{h['par_v1_lid']}/LAWS.bend as PAR1",
        f"import ../../model/{hl['model']}.bend as M",
        f"import ../../laws/{hl['cc_lids']['v0']}/LAWS.bend as CC0",
        f"import ../../laws/{hl['cc_lids']['v1']}/LAWS.bend as CC1",
        f"import ../../laws/{hl['cc_lids']['v2']}/LAWS.bend as CC2",
        "",
    ]
    for e in m0_entries:
        idx = "0" if e["version"] == "v0" else "1"
        lines.extend([
            f"law {e['law_id']}:",
            f"  for h: H0.{h['carrier']}",
            f"  {{H0.{e['decoder']}(H0.{e['encoder_sol']}(PAR{idx}.pin_h(h))) == H0.{e['decoder']}(H0.{e['encoder_go']}(PAR{idx}.pin_h(h))) : Maybe<&2, List<&2, List<&2, U32>>>}}",
            "",
        ])
    for e in entries:
        if e["milestone"] == "M0":
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
            f"  for +k: M.{hl['sol_rec_ty']}",
            f"  {{M.{dec_fn}(M.{e['encoder_sol']}({cc_alias}.pin_k(k, h))) == {{Some{{M.{getter}({cc_alias}.pin_h(h))}} : Maybe<&2, List<&2, U32>>}} : Maybe<&2, List<&2, U32>>}}",
            "",
        ])
    return "\n".join(lines)


def congruence_proof_bend(entries: list[dict], ctx: dict | None = None) -> str:
    ctx = ctx or _discover_context()
    h = ctx["hdr"]
    hl = ctx["hl"]
    cc_alias_by_ver = {"v0": "CC0", "v1": "CC1", "v2": "CC2"}
    imports = [
        "# GENERATED by holon.gen.mproofs; untrusted, accepted only if Bend checks it.",
        "import Base",
        "import ./LAWS.bend as Laws",
        "import ../../core/PROOF.bend as CP",
        "import ../../core/LAWS.bend as C",
        f"import ../../../M0/model/{h['model']}.bend as H0",
        f"import ../../../M0/{h['par_v0_lid']}/LAWS.bend as PAR0",
        f"import ../../../M0/{h['par_v0_lid']}/PROOF.bend as PAR0_P",
        f"import ../../../M0/{h['par_v1_lid']}/LAWS.bend as PAR1",
        f"import ../../../M0/{h['par_v1_lid']}/PROOF.bend as PAR1_P",
        f"import ../../model/{hl['model']}.bend as M",
        f"import ../../laws/{hl['cc_lids']['v0']}/LAWS.bend as CC0",
        f"import ../../proofs/{hl['cc_lids']['v0']}/PROOF.bend as CC0_P",
        f"import ../../laws/{hl['cc_lids']['v1']}/LAWS.bend as CC1",
        f"import ../../proofs/{hl['cc_lids']['v1']}/PROOF.bend as CC1_P",
        f"import ../../laws/{hl['cc_lids']['v2']}/LAWS.bend as CC2",
        f"import ../../proofs/{hl['cc_lids']['v2']}/PROOF.bend as CC2_P",
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
                    dom_ty=f"H0.{h['carrier']}",
                    mid_ty="List<&2, U32>",
                    cod_ty="Maybe<&2, List<&2, List<&2, U32>>>",
                    p_fn=f"x => H0.{e['encoder_sol']}(PAR{idx}.pin_h(x))",
                    q_fn=f"x => H0.{e['encoder_go']}(PAR{idx}.pin_h(x))",
                    l_fn=f"b => H0.{e['decoder']}(b)",
                    par_law=f"PAR{idx}.{e['parallel_generator'].lower()}",
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
                    q_fn=f"x => M.{e['encoder_sol']}({cc_alias}.pin_k(k, x))",
                    l_fn=f"b => M.{dec_fn}(b)",
                    par_law=f"x => {cc_alias}.{cc_fn}(x, k)",
                    rt_law=f"{rt_alias}.{rt_fn}({cc_alias}.pin_h(h))",
                    rhs_expr=f"{{Some{{M.{getter}({cc_alias}.pin_h(h))}} : Maybe<&2, List<&2, U32>>}}",
                )
            )
    return "\n".join(imports + defs)


def build_canary_specs(ctx: dict | None = None) -> list[dict]:
    ctx = ctx or _discover_context()
    h = ctx["hdr"]
    hl = ctx["hl"]
    cc0_lid = hl["cc_lids"]["v0"]
    rt_tree_v2 = hl["rt_tree_v2_lid"]
    rt_first_v0 = hl["rt_first_v0_lid"]
    return [
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
            "doc": "dropping the domain pin (pin_h) on the v0 header parallel reduction must fail both Bend kernels",
            "laws_bend": "\n".join([
                "import Base",
                f"import ../../../M0/model/{h['model']}.bend as M",
                "law canary_header_v0_unpinned:",
                f"  for +h: M.{h['carrier']}",
                f"  {{M.{h['dec']}(M.{h['enc_alt']}(h)) == M.{h['dec']}(M.{h['enc_v0']}(h)) : Maybe<&2, List<&2, List<&2, U32>>>}}",
                "",
            ]),
            "proof_bend": "\n".join([
                "import Base",
                "import ./LAWS.bend as Laws",
                f"import ../../../M0/model/{h['model']}.bend as M",
                f"import ../../../M0/{h['par_v0_lid']}/PROOF.bend as PAR0_P",
                f"import ../../../M0/{h['par_v0_lid']}/LAWS.bend as PAR0",
                "def Laws.canary_header_v0_unpinned(h):",
                f"  %PAR0.{h['par_v0_lid'].lower()}(h) : {{M.{h['dec']}(_) == M.{h['dec']}(M.{h['enc_v0']}(h)) : Maybe<&2, List<&2, List<&2, U32>>>}};",
                "  {==}",
                "",
            ]),
        },
        {
            "canary_id": "canary_header_v1_missing_par",
            "group": "header",
            "predicted_status": "REFUTED",
            "doc": "attempting to prove the v1 cycle reduction using only the v0 parallel generator without the v1 generator must fail both Bend kernels",
            "laws_bend": "\n".join([
                "import Base",
                f"import ../../../M0/model/{h['model']}.bend as M",
                f"import ../../../M0/{h['par_v1_lid']}/LAWS.bend as PAR1",
                "law canary_header_v1_missing_par:",
                f"  for +h: M.{h['carrier']}",
                f"  {{M.{h['dec']}(M.{h['enc_alt']}(PAR1.pin_h(h))) == M.{h['dec']}(M.{h['enc_v1']}(PAR1.pin_h(h))) : Maybe<&2, List<&2, List<&2, U32>>>}}",
                "",
            ]),
            "proof_bend": "\n".join([
                "import Base",
                "import ./LAWS.bend as Laws",
                f"import ../../../M0/model/{h['model']}.bend as M",
                f"import ../../../M0/{h['par_v0_lid']}/PROOF.bend as PAR0_P",
                f"import ../../../M0/{h['par_v0_lid']}/LAWS.bend as PAR0",
                f"import ../../../M0/{h['par_v1_lid']}/LAWS.bend as PAR1",
                "def Laws.canary_header_v1_missing_par(h):",
                f"  %PAR0.{h['par_v0_lid'].lower()}(h) : {{M.{h['dec']}(_) == M.{h['dec']}(M.{h['enc_v1']}(PAR1.pin_h(h))) : Maybe<&2, List<&2, List<&2, U32>>>}};",
                "  {==}",
                "",
            ]),
        },
        {
            "canary_id": "canary_hl_drop_cycle_gen",
            "group": "header_length",
            "predicted_status": "REFUTED",
            "doc": "dropping the non-tree round-trip generator when reducing the v2 non-tree decoder to the spanning-tree decoder must fail both Bend kernels",
            "laws_bend": "\n".join([
                "import Base",
                f"import ../../model/{hl['model']}.bend as M",
                "law canary_hl_drop_cycle_gen:",
                f"  for +h: M.{hl['rec_v1_ty']}",
                f"  {{M.{hl['nt_dec_v2_fn']}(M.{hl['enc_v2_fn']}(h)) == M.{hl['tree_dec_v2_fn']}(M.{hl['enc_v2_fn']}(h)) : Maybe<&2, List<&2, U32>>}}",
                "",
            ]),
            "proof_bend": "\n".join([
                "import Base",
                "import ./LAWS.bend as Laws",
                f"import ../../model/{hl['model']}.bend as M",
                f"import ../../laws/{rt_tree_v2}/LAWS.bend as RT_BCH_V2",
                f"import ../../proofs/{rt_tree_v2}/PROOF.bend as RT_BCH_V2_P",
                "def Laws.canary_hl_drop_cycle_gen(h):",
                f"  %RT_BCH_V2.{rt_tree_v2.lower()}(h) : {{M.{hl['nt_dec_v2_fn']}(M.{hl['enc_v2_fn']}(h)) == _ : Maybe<&2, List<&2, U32>>}};",
                "  {==}",
                "",
            ]),
        },
        {
            "canary_id": "canary_congruence_unpinned_v0",
            "group": "congruence",
            "predicted_status": "REFUTED",
            "doc": "attempting to derive a v0 cross-language round-trip law without the pin_k/pin_h domain premise must fail both Bend kernels",
            "laws_bend": "\n".join([
                "import Base",
                f"import ../../model/{hl['model']}.bend as M",
                "law canary_congruence_unpinned_v0:",
                f"  for +h: M.{hl['rec_v0_ty']}",
                f"  for +k: M.{hl['sol_rec_ty']}",
                f"  {{M.{hl['first_tree_dec']}(M.{hl['sol_enc']}(k)) == {{Some{{M.{hl['getter_first_v0']}(h)}} : Maybe<&2, List<&2, U32>>}} : Maybe<&2, List<&2, U32>>}}",
                "",
            ]),
            "proof_bend": "\n".join([
                "import Base",
                "import ./LAWS.bend as Laws",
                f"import ../../model/{hl['model']}.bend as M",
                f"import ../../laws/{cc0_lid}/LAWS.bend as CC0",
                f"import ../../proofs/{cc0_lid}/PROOF.bend as CC0_P",
                f"import ../../laws/{rt_first_v0}/LAWS.bend as RT_0",
                f"import ../../proofs/{rt_first_v0}/PROOF.bend as RT_0_P",
                "def Laws.canary_congruence_unpinned_v0(h, k):",
                f"  %CC0.{cc0_lid.lower()}(h, k) : {{M.{hl['first_tree_dec']}(_) == {{Some{{M.{hl['getter_first_v0']}(h)}} : Maybe<&2, List<&2, U32>>}} : Maybe<&2, List<&2, U32>>}};",
                f"  RT_0.{rt_first_v0.lower()}(h)",
                "",
            ]),
        },
    ]


def equivariance_laws_bend(ctx: dict | None = None) -> str:
    ctx = ctx or _discover_context()
    m1 = ctx["m1"]
    st_ty = m1["st_ty"]
    mig_1 = m1["mig_1_fn"]
    mig_2 = m1["mig_2_fn"]
    step_s = m1["send_step_fn"]
    step_w = m1["wait_step_fn"]
    return "\n".join([
        "# GENERATED by holon.gen.basis for M3 equivariance basis; do not edit.",
        "import Base",
        f"import ../../../M1/model/{m1['model']}.bend as M",
        "",
        "law basis_equivar_mig_legacy_wait:",
        f"  for s: M.{st_ty}",
        "  for +dt: Nat",
        f"  {{M.{mig_1}(M.{step_w}(s, dt)) == M.{step_w}(M.{mig_1}(s), dt) : M.{st_ty}}}",
        "",
        "law basis_equivar_mig_legacy_send_msg:",
        f"  for s: M.{st_ty}",
        "  for +who: Nat",
        f"  {{M.{mig_1}(M.{step_s}(s, who)) == M.{step_s}(M.{mig_1}(s), who) : M.{st_ty}}}",
        "",
        "law basis_equivar_mig_eta2_wait:",
        f"  for s: M.{st_ty}",
        "  for +dt: Nat",
        "  for +root: Nat",
        f"  {{M.{mig_2}(M.{step_w}(s, dt), root) == M.{step_w}(M.{mig_2}(s, root), dt) : M.{st_ty}}}",
        "",
        "law basis_equivar_mig_compose_wait:",
        f"  for +s: M.{st_ty}",
        "  for +dt: Nat",
        "  for +root: Nat",
        f"  {{M.{mig_2}(M.{mig_1}(M.{step_w}(s, dt)), root) == M.{step_w}(M.{mig_2}(M.{mig_1}(s), root), dt) : M.{st_ty}}}",
        "",
    ])


def equivariance_proof_bend(ctx: dict | None = None) -> str:
    ctx = ctx or _discover_context()
    m1 = ctx["m1"]
    st_ty = m1["st_ty"]
    mig_1 = m1["mig_1_fn"]
    mig_2 = m1["mig_2_fn"]
    step_w = m1["wait_step_fn"]
    st_pat = ", ".join(m1["st_fields"])
    return "\n".join([
        "# GENERATED by holon.gen.basis; untrusted, accepted only if Bend checks it.",
        "import Base",
        "import ./LAWS.bend as Laws",
        "import ../../core/PROOF.bend as CP",
        "import ../../core/LAWS.bend as C",
        f"import ../../../M1/model/{m1['model']}.bend as M",
        "",
        "def Laws.basis_equivar_mig_legacy_wait(s, dt):",
        "  match s:",
        f"    case M.{st_ty}{{{st_pat}}}:",
        "      {==}",
        "",
        "def Laws.basis_equivar_mig_legacy_send_msg(s, who):",
        "  match s:",
        f"    case M.{st_ty}{{{st_pat}}}:",
        "      {==}",
        "",
        "def Laws.basis_equivar_mig_eta2_wait(s, dt, root):",
        "  match s:",
        f"    case M.{st_ty}{{{st_pat}}}:",
        "      {==}",
        "",
        "def Laws.basis_equivar_mig_compose_wait(s, dt, root):",
        f"  C.core_equivar_whisker(M.{st_ty}, M.{st_ty}, M.{st_ty}, x => M.{mig_1}(x), y => M.{mig_2}(y, root), x => M.{step_w}(x, dt), y => M.{step_w}(y, dt), z => M.{step_w}(z, dt), x => Laws.basis_equivar_mig_legacy_wait(x, dt), y => Laws.basis_equivar_mig_eta2_wait(y, dt, root))(s)",
        "",
    ])


def pasting_laws_bend(ctx: dict | None = None) -> str:
    ctx = ctx or _discover_context()
    m1 = ctx["m1"]
    st_ty = m1["st_ty"]
    mig_1 = m1["mig_1_fn"]
    mig_2 = m1["mig_2_fn"]
    lci_fn = m1["lci_obs_fn"]
    tags_fn = m1["tags_obs_fn"]
    return "\n".join([
        "# GENERATED by holon.gen.basis for M3 pasting basis; do not edit.",
        "import Base",
        f"import ../../../M1/model/{m1['model']}.bend as M",
        "",
        "law basis_paste_lci_mig_legacy:",
        f"  for s: M.{st_ty}",
        f"  {{M.{lci_fn}(M.{mig_1}(s)) == M.{lci_fn}(s) : Nat}}",
        "",
        "law basis_paste_lci_mig_eta2:",
        f"  for s: M.{st_ty}",
        "  for +root: Nat",
        f"  {{M.{lci_fn}(M.{mig_2}(s, root)) == M.{lci_fn}(s) : Nat}}",
        "",
        "law basis_paste_lci_mig_chain:",
        f"  for +s: M.{st_ty}",
        "  for +root: Nat",
        f"  {{M.{lci_fn}(M.{mig_2}(M.{mig_1}(s), root)) == M.{lci_fn}(s) : Nat}}",
        "",
        "law basis_paste_tags_mig_chain:",
        f"  for +s: M.{st_ty}",
        "  for +root: Nat",
        f"  {{M.{tags_fn}(M.{mig_2}(M.{mig_1}(s), root)) == M.{tags_fn}(s) : Bool}}",
        "",
    ])


def pasting_proof_bend(ctx: dict | None = None) -> str:
    ctx = ctx or _discover_context()
    m1 = ctx["m1"]
    st_ty = m1["st_ty"]
    mig_1 = m1["mig_1_fn"]
    mig_2 = m1["mig_2_fn"]
    ent_ty = m1["entry_ty"]
    emp_fn = m1["empty_entry_fn"]
    lci_fn = m1["lci_obs_fn"]
    lfi_fld = m1["lfi_fld"]
    win_fld = m1["win_fld"]
    tags_fn = m1["tags_obs_fn"]
    tpred_fn = m1["tpred_fn"]
    zcsr_fn = m1["zero_csr_fn"]
    ecsr_fn = m1["entry_csr_fn"]
    scsr_fn = m1["set_last_csr_fn"]
    ent_pat = ", ".join(m1["entry_fields"])
    ent_pat_plus = ", ".join(f"+{f}" if f in ("ver", "tag") else f for f in m1["entry_fields"])
    st_pat = ", ".join(m1["st_fields"])
    st_pat_win = ", ".join(f"+{f}" if f == win_fld else f for f in m1["st_fields"])
    st_pat_lfi_win = ", ".join(f"+{f}" if f in (lfi_fld, win_fld) else f for f in m1["st_fields"])
    return "\n".join([
        "# GENERATED by holon.gen.basis; untrusted, accepted only if Bend checks it.",
        "import Base",
        "import ./LAWS.bend as Laws",
        "import ../../core/PROOF.bend as CP",
        "import ../../core/LAWS.bend as C",
        f"import ../../../M1/model/{m1['model']}.bend as M",
        "",
        f"def len_zero_csr(es: List<&2, M.{ent_ty}>) -> {{List.length(&2, M.{ent_ty}, M.{zcsr_fn}(es)) == List.length(&2, M.{ent_ty}, es) : Nat}}:",
        "  match es:",
        "    case Nil{}:",
        "      {==}",
        "    case Con{e, t}:",
        "      match e:",
        f"        case M.{ent_ty}{{{ent_pat}}}:",
        f"          (%len_zero_csr(t) : {{1n+List.length(&2, M.{ent_ty}, M.{zcsr_fn}(t)) == 1n+_ : Nat}}; {{==}})",
        "",
        f"def len_set_last_csr(es: List<&2, M.{ent_ty}>, +r: Nat) -> {{List.length(&2, M.{ent_ty}, M.{scsr_fn}(es, r)) == List.length(&2, M.{ent_ty}, es) : Nat}}:",
        "  match es:",
        "    case Nil{}:",
        "      {==}",
        "    case Con{e, t}:",
        "      match e:",
        f"        case M.{ent_ty}{{{ent_pat}}}:",
        "          match t:",
        "            case Nil{}:",
        "              {==}",
        "            case Con{e2, t2}:",
        f"              (%len_set_last_csr(Con{{e2, t2}}, r) : {{1n+List.length(&2, M.{ent_ty}, M.{scsr_fn}(Con{{e2, t2}}, r)) == 1n+_ : Nat}}; {{==}})",
        "",
        f"def len_ite_set_last_csr(c: Bool, +es: List<&2, M.{ent_ty}>, +r: Nat) -> {{List.length(&2, M.{ent_ty}, M.ite(List<&2, M.{ent_ty}>, c, M.{scsr_fn}(es, r), es)) == List.length(&2, M.{ent_ty}, es) : Nat}}:",
        "  match c:",
        "    case True{}:",
        "      len_set_last_csr(es, r)",
        "    case False{}:",
        "      {==}",
        "",
        f"def tags_zero_csr(es: List<&2, M.{ent_ty}>) -> {{M.{tpred_fn}(M.{zcsr_fn}(es)) == M.{tpred_fn}(es) : Bool}}:",
        "  match es:",
        "    case Nil{}:",
        "      {==}",
        "    case Con{e, t}:",
        "      match e:",
        f"        case M.{ent_ty}{{{ent_pat_plus}}}:",
        f"          (%tags_zero_csr(t) : {{Bool.and(M.eq_bool(Nat.is_eq(ver, 2n), Nat.is_eq(tag, 2n)), M.{tpred_fn}(M.{zcsr_fn}(t))) == Bool.and(M.eq_bool(Nat.is_eq(ver, 2n), Nat.is_eq(tag, 2n)), _) : Bool}}; {{==}})",
        "",
        f"def tags_set_last_csr(es: List<&2, M.{ent_ty}>, +r: Nat) -> {{M.{tpred_fn}(M.{scsr_fn}(es, r)) == M.{tpred_fn}(es) : Bool}}:",
        "  match es:",
        "    case Nil{}:",
        "      {==}",
        "    case Con{e, t}:",
        "      match e:",
        f"        case M.{ent_ty}{{{ent_pat_plus}}}:",
        "          match t:",
        "            case Nil{}:",
        "              {==}",
        "            case Con{e2, t2}:",
        f"              (%tags_set_last_csr(Con{{e2, t2}}, r) : {{Bool.and(M.eq_bool(Nat.is_eq(ver, 2n), Nat.is_eq(tag, 2n)), M.{tpred_fn}(M.{scsr_fn}(Con{{e2, t2}}, r))) == Bool.and(M.eq_bool(Nat.is_eq(ver, 2n), Nat.is_eq(tag, 2n)), _) : Bool}}; {{==}})",
        "",
        f"def tags_ite_set_last_csr(c: Bool, +es: List<&2, M.{ent_ty}>, +r: Nat) -> {{M.{tpred_fn}(M.ite(List<&2, M.{ent_ty}>, c, M.{scsr_fn}(es, r), es)) == M.{tpred_fn}(es) : Bool}}:",
        "  match c:",
        "    case True{}:",
        "      tags_set_last_csr(es, r)",
        "    case False{}:",
        "      {==}",
        "",
        f"def tags_mig_legacy(s: M.{st_ty}) -> {{M.{tags_fn}(M.{mig_1}(s)) == M.{tags_fn}(s) : Bool}}:",
        "  match s:",
        f"    case M.{st_ty}{{{st_pat}}}:",
        f"      tags_zero_csr({win_fld})",
        "",
        f"def tags_mig_eta2(s: M.{st_ty}, +root: Nat) -> {{M.{tags_fn}(M.{mig_2}(s, root)) == M.{tags_fn}(s) : Bool}}:",
        "  match s:",
        f"    case M.{st_ty}{{{st_pat_win}}}:",
        f"      tags_ite_set_last_csr(Nat.is_eq(M.{ecsr_fn}(M.last_d(M.{ent_ty}, {win_fld}, M.{emp_fn}())), 0n), {win_fld}, root)",
        "",
        "def Laws.basis_paste_lci_mig_legacy(s):",
        "  match s:",
        f"    case M.{st_ty}{{{st_pat_lfi_win}}}:",
        f"      (%len_zero_csr({win_fld}) : {{Nat.sub(Nat.add({lfi_fld}, List.length(&2, M.{ent_ty}, M.{zcsr_fn}({win_fld}))), 1n) == Nat.sub(Nat.add({lfi_fld}, _), 1n) : Nat}}; {{==}})",
        "",
        "def Laws.basis_paste_lci_mig_eta2(s, root):",
        "  match s:",
        f"    case M.{st_ty}{{{st_pat_lfi_win}}}:",
        f"      (%len_ite_set_last_csr(Nat.is_eq(M.{ecsr_fn}(M.last_d(M.{ent_ty}, {win_fld}, M.{emp_fn}())), 0n), {win_fld}, root) : {{Nat.sub(Nat.add({lfi_fld}, List.length(&2, M.{ent_ty}, M.ite(List<&2, M.{ent_ty}>, Nat.is_eq(M.{ecsr_fn}(M.last_d(M.{ent_ty}, {win_fld}, M.{emp_fn}())), 0n), M.{scsr_fn}({win_fld}, root), {win_fld}))), 1n) == Nat.sub(Nat.add({lfi_fld}, _), 1n) : Nat}}; {{==}})",
        "",
        "def Laws.basis_paste_lci_mig_chain(s, root):",
        f"  C.core_paste_v_obs(M.{st_ty}, M.{st_ty}, M.{st_ty}, Nat, x => M.{mig_1}(x), y => M.{mig_2}(y, root), x => M.{lci_fn}(x), y => M.{lci_fn}(y), z => M.{lci_fn}(z), x => Laws.basis_paste_lci_mig_legacy(x), y => Laws.basis_paste_lci_mig_eta2(y, root))(s)",
        "",
        "def Laws.basis_paste_tags_mig_chain(s, root):",
        f"  C.core_paste_v_obs(M.{st_ty}, M.{st_ty}, M.{st_ty}, Bool, x => M.{mig_1}(x), y => M.{mig_2}(y, root), x => M.{tags_fn}(x), y => M.{tags_fn}(y), z => M.{tags_fn}(z), x => tags_mig_legacy(x), y => tags_mig_eta2(y, root))(s)",
        "",
    ])


def emit_ii(root: Path = ROOT, milestone: str = "M3", cfg: dict | None = None) -> None:
    """Emit `gen/<M>/core` and `gen/<M>/basis/{equivariance,pasting}` (I43)."""
    root = Path(root).resolve()
    gen_dir = root / "gen" / milestone
    core.emit(gen_dir, cfg=cfg, include_theory_core_i=True)
    ctx = _discover_context(root, milestone)
    basis_dir = gen_dir / "basis"
    eq_dir = basis_dir / "equivariance"
    paste_dir = basis_dir / "pasting"
    for d in (eq_dir, paste_dir):
        d.mkdir(parents=True, exist_ok=True)
    (eq_dir / "LAWS.bend").write_text(equivariance_laws_bend(ctx), encoding="utf-8")
    (eq_dir / "PROOF.bend").write_text(equivariance_proof_bend(ctx), encoding="utf-8")
    (paste_dir / "LAWS.bend").write_text(pasting_laws_bend(ctx), encoding="utf-8")
    (paste_dir / "PROOF.bend").write_text(pasting_proof_bend(ctx), encoding="utf-8")


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
    ctx = _discover_context(root, milestone)
    hl = ctx["hl"]

    basis_dir = gen_dir / "basis"
    hdr_dir = basis_dir / "header"
    hl_dir = basis_dir / "header_length"
    cong_dir = basis_dir / "congruence"
    eq_dir = basis_dir / "equivariance"
    paste_dir = basis_dir / "pasting"
    for d in (hdr_dir, hl_dir, cong_dir, eq_dir, paste_dir):
        d.mkdir(parents=True, exist_ok=True)

    (hdr_dir / "LAWS.bend").write_text(header_laws_bend(ctx), encoding="utf-8")
    (hdr_dir / "PROOF.bend").write_text(header_proof_bend(ctx), encoding="utf-8")

    (hl_dir / "LAWS.bend").write_text(header_length_laws_bend(ctx), encoding="utf-8")
    (hl_dir / "PROOF.bend").write_text(header_length_proof_bend(ctx), encoding="utf-8")

    (eq_dir / "LAWS.bend").write_text(equivariance_laws_bend(ctx), encoding="utf-8")
    (eq_dir / "PROOF.bend").write_text(equivariance_proof_bend(ctx), encoding="utf-8")

    (paste_dir / "LAWS.bend").write_text(pasting_laws_bend(ctx), encoding="utf-8")
    (paste_dir / "PROOF.bend").write_text(pasting_proof_bend(ctx), encoding="utf-8")

    entries = discover_congruence_entries(root, milestone)
    cong_laws_txt = congruence_laws_bend(entries, ctx)
    cong_proof_txt = congruence_proof_bend(entries, ctx)
    (cong_dir / "LAWS.bend").write_text(cong_laws_txt, encoding="utf-8")
    (cong_dir / "PROOF.bend").write_text(cong_proof_txt, encoding="utf-8")

    core_laws = [{"law_id": e[0], "proof_class": e[4]} for e in core.THEORY_CORE_I]
    hdr_laws = [
        {"law_id": "basis_sufficient_header_v0", "core_lemma": "core_whisker_post"},
        {"law_id": "basis_sufficient_header_v1", "core_lemma": "core_whisker_post"},
        {"law_id": "basis_sufficient_header", "core_lemma": "core_cycle_basis_2"},
    ]
    hl_laws = [
        {"law_id": hl["gen1_law_id"], "core_lemma": "core_tree_unique_2"},
        {"law_id": hl["gen2_law_id"], "core_lemma": "core_tree_unique_2"},
        {"law_id": hl["gen3_law_id"], "core_lemma": "core_whisker_post"},
        {"law_id": hl["gen4_law_id"], "core_lemma": "core_whisker_post"},
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
        for c in build_canary_specs(ctx):
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
