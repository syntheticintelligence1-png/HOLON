"""Unsolved control obligations: unassisted UNKNOWN calibration and ground-truth verification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from holon import bend, ir, mpipeline
from holon.gen import machine, mlaws, mproofs, refs

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIDECAR = ROOT / "spec" / "M4" / "lib" / "corpus_controls.json"
DEFAULT_CONTROLS_DIR = ROOT / "spec" / "eval" / "controls"

UNASSISTED_GENERATORS: tuple[str, ...] = (
    "refl",
    "case_split_guard",
    "nat_ind",
    "list_ind",
    "eq_chain",
    "evaluate",
)

_CM_CACHE: dict[tuple[str, str], mpipeline.CompiledMachine] = {}
_EXPLORE_CACHE: dict[tuple[str, str, str], dict] = {}
_BEND_CHECK_CACHE: dict[tuple[str, str, str], bend.RunResult] = {}


def _strip_sha256_prefix(h: str) -> str:
    return h.split(":", 1)[1] if h.startswith("sha256:") else h


def _cached_bend_check(proof_file: Path, laws_text: str, proof_text: str, model_sha: str, cfg: bend.BendConfig) -> bend.RunResult:
    key = (
        hashlib.sha256(laws_text.encode("utf-8")).hexdigest(),
        hashlib.sha256(proof_text.encode("utf-8")).hexdigest(),
        model_sha,
    )
    cached = _BEND_CHECK_CACHE.get(key)
    if cached is not None:
        return cached
    rr = bend.check(proof_file, cfg)
    _BEND_CHECK_CACHE[key] = rr
    return rr


def _refl_candidate(em: mlaws.EmittedM, m: machine.Machine, model_import: str) -> str | None:
    state_binders = [n for _, n, t in em.binders if t in ("State", "Reach")]
    if not state_binders:
        return None
    s_var = state_binders[0]
    params = ", ".join(mproofs.law_params(em) + [f"h{i}" for i in range(len(em.assume))])
    fields = ", ".join(f"+{n}" for n, _ in m.state)
    return (
        f"import Base\n"
        f"import {model_import} as M\n"
        f"import ./LAWS.bend as Laws\n\n"
        f"def Laws.{em.name}({params}):\n"
        f"  match {s_var}:\n"
        f"    case M.HSt{{{fields}}}:\n"
        f"      {{==}}\n"
    )


def _run_unassisted_tactic(
    gname: str,
    em: mlaws.EmittedM,
    m: machine.Machine,
    model_import: str,
) -> tuple[str | None, str]:
    if gname == "refl":
        cand = _refl_candidate(em, m, model_import)
        return cand, "no State/Reach binder for HSt reflexivity"
    if gname == "case_split_guard":
        cand = mproofs.chain_revert(em, m, model_import) or mproofs.deadline(em, m, model_import)
        return cand, "guard shape does not reduce to a single guard case-split"
    if gname == "nat_ind":
        cand = mproofs.nat_split(em, m, model_import)
        return cand, "requires custom inductive lemma or composite Nat witness beyond depth-3 split"
    if gname == "list_ind":
        cand = mproofs.noninterference(em, m, model_import)
        return cand, "requires custom list/trace structural lemma"
    if gname == "eq_chain":
        cand = (
            mproofs.hyp(em, m, model_import)
            or mproofs.act_split(em, m, model_import)
            or mproofs.expr_open(em, m, model_import)
        )
        return cand, "claim does not close by direct premise or single-step equality chain"
    if gname == "evaluate":
        cand = mproofs.evaluate(em, m, model_import, None)
        return cand, "universal binders present; closed evaluation inapplicable"
    raise ValueError(f"unknown tactic generator: {gname!r}")


def load_controls_manifest(controls_dir_or_path: Path | str | None = None) -> dict:
    p = Path(controls_dir_or_path or DEFAULT_CONTROLS_DIR)
    if p.is_dir():
        p = p / "controls_manifest.json"
    return json.loads(p.read_text(encoding="utf-8"))


def materialize_controls(
    sidecar_path: Path | str | None = None,
    controls_dir: Path | str | None = None,
    root: Path | str | None = None,
) -> dict:
    """Materialize `spec/eval/controls/` facts, law JSONs, and manifest from sidecar."""
    base_root = Path(root or ROOT)
    s_path = Path(sidecar_path or (base_root / "spec" / "M4" / "lib" / "corpus_controls.json"))
    c_dir = Path(controls_dir or (base_root / "spec" / "eval" / "controls"))
    laws_dir = c_dir / "laws"
    laws_dir.mkdir(parents=True, exist_ok=True)

    sidecar = json.loads(s_path.read_text(encoding="utf-8"))
    facts = sidecar["control_facts"]
    facts_text = json.dumps(facts, indent=2) + "\n"
    facts_sha = hashlib.sha256(facts_text.encode("utf-8")).hexdigest()
    if facts_sha != sidecar["control_facts_sha256"]:
        raise ValueError(f"control_facts_sha256 mismatch: {facts_sha} != {sidecar['control_facts_sha256']}")

    facts_file = c_dir / f"{facts['model']}.facts.json"
    facts_file.write_text(facts_text, encoding="utf-8")

    manifest_controls: list[dict] = []
    for ctrl in sidecar["controls"]:
        lid = ctrl["law_id"]
        law_doc = ctrl["law"]
        ir.check_premises(law_doc)
        ir.check_binder_types(law_doc, facts)
        law_path = laws_dir / f"{lid}.json"
        law_path.write_text(json.dumps(law_doc, indent=2) + "\n", encoding="utf-8")
        entry = {
            "control_id": ctrl["control_id"],
            "law_id": lid,
            "category": ctrl["category"],
            "rule": ctrl["rule"],
            "subform": ctrl["subform"],
            "limitation_class": ctrl["limitation_class"],
            "description": ctrl["description"],
            "expected_status": ctrl.get("unassisted_expected_status", "UNKNOWN"),
            "ground_truth_kind": (
                "COUNTER_LAW_ACCEPTED"
                if ctrl["category"] == "FALSE_BEYOND_BOUND"
                else "PROOF_ACCEPTED"
            ),
            "law_file": f"spec/eval/controls/laws/{lid}.json",
        }
        if "ground_truth_witness" in ctrl:
            entry["ground_truth_witness"] = ctrl["ground_truth_witness"]
        if "ground_truth_proof" in ctrl:
            entry["ground_truth_proof"] = ctrl["ground_truth_proof"]
        manifest_controls.append(entry)

    cspec = sidecar["controls_spec"]
    manifest = {
        "schema": "holon-controls-manifest/0.1",
        "iteration": sidecar["iteration"],
        "milestone": sidecar["milestone"],
        "total_count": cspec["total_count"],
        "total_controls": cspec["total_count"],
        "false_beyond_bound_count": cspec["false_beyond_bound_count"],
        "true_unproved_count": cspec["true_unproved_count"],
        "evaluation_budget": dict(cspec["evaluation_budget"]),
        "facts_file": f"spec/eval/controls/{facts_file.name}",
        "control_facts_file": facts_file.name,
        "control_facts_sha256": facts_sha,
        "controls": manifest_controls,
    }
    (c_dir / "controls_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def compute_calibration(records: list[dict]) -> dict:
    """Compute UNKNOWN calibration and sound-abstention metrics over control result records."""
    total = len(records)
    unknown_count = sum(1 for r in records if r.get("status") == "UNKNOWN")
    false_positive_proofs = sum(
        1
        for r in records
        if r.get("category") == "FALSE_BEYOND_BOUND" and r.get("status") == "PROVED"
    )
    false_negative_refutations = sum(
        1
        for r in records
        if r.get("category") == "TRUE_UNPROVED" and r.get("status") == "REFUTED"
    )
    confidently_wrong = false_positive_proofs + false_negative_refutations
    missing_bound_count = sum(
        1
        for r in records
        if r.get("status") == "UNKNOWN" and not str(r.get("bound") or "").strip()
    )
    calibration_ok = (
        total > 0
        and unknown_count == total
        and confidently_wrong == 0
        and missing_bound_count == 0
    )
    return {
        "total_controls": total,
        "unknown_count": unknown_count,
        "false_positive_proofs": false_positive_proofs,
        "false_negative_refutations": false_negative_refutations,
        "confidently_wrong": confidently_wrong,
        "missing_bound_count": missing_bound_count,
        "calibration_ok": calibration_ok,
    }


def run_controls_evaluation(
    controls_dir: Path | str | None = None,
    sidecar_path: Path | str | None = None,
    root: Path | str | None = None,
) -> dict:
    """Run unassisted HOLON and ground-truth Bend verification on all 12 control obligations."""
    base_root = Path(root or ROOT)
    s_path = Path(sidecar_path or (base_root / "spec" / "M4" / "lib" / "corpus_controls.json"))
    c_dir = Path(controls_dir or (base_root / "spec" / "eval" / "controls"))

    sidecar = json.loads(s_path.read_text(encoding="utf-8"))
    facts = sidecar["control_facts"]
    facts_sha = hashlib.sha256((json.dumps(facts, indent=2) + "\n").encode("utf-8")).hexdigest()
    facts_path = c_dir / f"{facts['model']}.facts.json"
    if not facts_path.is_file():
        materialize_controls(sidecar_path=s_path, controls_dir=c_dir, root=base_root)

    cfg = bend.config(base_root)
    cm_key = (str(facts_path.resolve()), facts_sha)
    cm = _CM_CACHE.get(cm_key)
    if cm is None:
        cm = mpipeline.CompiledMachine.build(facts_path, cfg, reach=True)
        _CM_CACHE[cm_key] = cm

    gen_ctrl_dir = base_root / "gen" / "M4" / "controls"
    model_dir = gen_ctrl_dir / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_bend = model_dir / f"{facts['model']}.bend"
    model_bytes = cm.source.read_bytes()
    model_sha = hashlib.sha256(model_bytes).hexdigest()
    compiled_sha = hashlib.sha256(cm.artifact.read_bytes()).hexdigest()
    model_text = model_bytes.decode("utf-8")
    if not model_bend.is_file() or model_bend.read_text(encoding="utf-8") != model_text:
        model_bend.write_text(model_text, encoding="utf-8")
    model_rr = _cached_bend_check(model_bend, "", model_text, model_sha, cfg)
    if not model_rr.ok:
        raise RuntimeError(f"control model failed bend check: {model_rr.out}")

    results_dir = base_root / "results" / "M4" / "controls"
    results_dir.mkdir(parents=True, exist_ok=True)

    budget = dict(sidecar["controls_spec"]["evaluation_budget"])
    budget_key = json.dumps(budget, sort_keys=True)
    model_import = f"../../model/{facts['model']}.bend"

    control_summaries: list[dict] = []
    full_records: list[dict] = []
    false_beyond_bound_verified = 0
    true_unproved_verified = 0

    for ctrl in sidecar["controls"]:
        cid = ctrl["control_id"]
        lid = ctrl["law_id"]
        cat = ctrl["category"]
        law = ctrl["law"]
        shash_raw = refs.law_hash(law, facts)
        shash_hex = _strip_sha256_prefix(shash_raw)

        # 1. Emit unassisted law and run unassisted proof tactics.
        em = mlaws.Emitter(cm.m).emit(law, model_import, note=shash_raw)
        unassisted_law_dir = gen_ctrl_dir / "laws" / lid
        unassisted_law_dir.mkdir(parents=True, exist_ok=True)
        laws_file = unassisted_law_dir / "LAWS.bend"
        laws_file.write_text(em.text, encoding="utf-8")

        attempts: list[dict] = []
        proved_by: str | None = None
        for gname in UNASSISTED_GENERATORS:
            cand, reason = _run_unassisted_tactic(gname, em, cm.m, model_import)
            if cand is None:
                attempts.append(
                    {
                        "kind": "proof",
                        "generator": gname,
                        "applied": False,
                        "ok": False,
                        "reason": reason,
                    }
                )
            else:
                pf = unassisted_law_dir / "_probe_PROOF.bend"
                try:
                    pf.write_text(cand, encoding="utf-8")
                    rr = _cached_bend_check(pf, em.text, cand, model_sha, cfg)
                    ok, why = mpipeline.accepted(rr, pf, laws_file, em, cand)
                finally:
                    pf.unlink(missing_ok=True)
                attempts.append(
                    {
                        "kind": "proof",
                        "generator": gname,
                        "applied": True,
                        "ok": bool(ok),
                        "marker": rr.marker,
                        "reason": why or "rejected by Bend typechecker",
                    }
                )
                if ok:
                    proved_by = gname
                    break

        # 2. Run bounded compiled-model trace search under evaluation_budget.
        ex_key = (facts_sha, shash_hex, budget_key)
        explore_res = _EXPLORE_CACHE.get(ex_key)
        if explore_res is None:
            explore_res = cm.explore(law, budget=budget)
            _EXPLORE_CACHE[ex_key] = explore_res

        hit = explore_res["witness"] is not None
        bound_str = explore_res["bound"]
        attempts.append(
            {
                "kind": "refute",
                "engine": "compiled-model trace search",
                "bound": bound_str,
                "tried": int(explore_res["tried"]),
                "hit": bool(hit),
            }
        )

        if proved_by is not None:
            unassisted_status = "PROVED"
        elif hit:
            unassisted_status = "REFUTED"
        else:
            unassisted_status = "UNKNOWN"

        # 3. Emit and verify ground-truth artifact in gen/M4/controls/ground_truth/<law_id>/.
        gt_dir = gen_ctrl_dir / "ground_truth" / lid
        gt_dir.mkdir(parents=True, exist_ok=True)
        gt_laws_path = gt_dir / "LAWS.bend"
        gt_proof_path = gt_dir / "PROOF.bend"

        if cat == "FALSE_BEYOND_BOUND":
            witness = ctrl["ground_truth_witness"]
            em_gt = mlaws.Emitter(cm.m).emit(law, model_import, counter=True, note=shash_raw)
            wr = mlaws.resolve_witness(cm.m, em_gt.binders, witness, {})
            tabs = mlaws.witness_tabs(cm.m, em_gt.binders, wr)
            env = {n: mlaws.value_literal(cm.m, t, wr[n], tabs) for _, n, t in em_gt.binders}
            e_claim = mlaws.Emitter(cm.m)
            lhs, _, ty = e_claim.claims(
                law["statement"],
                env,
                {n: ("State" if t == "Reach" else t) for _, n, t in em_gt.binders},
            )[0]
            gt_proof_text = mproofs.counter(em_gt, cm.m, model_import, wr, lhs, ty)
            gt_laws_text = em_gt.text
            gt_kind = "COUNTER_LAW_ACCEPTED"
            gt_symbol = f"Laws.cl_{lid.lower()}"
        elif cat == "TRUE_UNPROVED":
            em_gt = em
            gt_laws_text = em_gt.text
            gt_proof_text = ctrl["ground_truth_proof"]
            gt_kind = "PROOF_ACCEPTED"
            gt_symbol = f"Laws.{lid.lower()}"
        else:
            raise ValueError(f"unsupported control category: {cat!r}")

        if not gt_laws_path.is_file() or gt_laws_path.read_text(encoding="utf-8") != gt_laws_text:
            gt_laws_path.write_text(gt_laws_text, encoding="utf-8")
        if not gt_proof_path.is_file() or gt_proof_path.read_text(encoding="utf-8") != gt_proof_text:
            gt_proof_path.write_text(gt_proof_text, encoding="utf-8")

        gt_rr = _cached_bend_check(gt_proof_path, gt_laws_text, gt_proof_text, model_sha, cfg)
        gt_ok, gt_why = mpipeline.accepted(gt_rr, gt_proof_path, gt_laws_path, em_gt, gt_proof_text)
        if not gt_ok:
            raise RuntimeError(f"ground-truth verification failed for {cid} ({lid}): {gt_why}\n{gt_rr.out}")

        if cat == "FALSE_BEYOND_BOUND":
            false_beyond_bound_verified += 1
        else:
            true_unproved_verified += 1

        rec = {
            "schema": "holon-control-result/0.1",
            "control_id": cid,
            "law_id": lid,
            "category": cat,
            "rule": ctrl["rule"],
            "subform": ctrl["subform"],
            "limitation_class": ctrl["limitation_class"],
            "description": ctrl["description"],
            "status": unassisted_status,
            "bound": bound_str,
            "tried_generators": list(UNASSISTED_GENERATORS),
            "attempts": attempts,
            "facts_sha256": facts_sha,
            "model_sha256": model_sha,
            "compiled_sha256": compiled_sha,
            "statement_hash": shash_hex,
            "ground_truth_kind": gt_kind,
            "ground_truth_symbol": gt_symbol,
            "ground_truth_verified": True,
            "ground_truth_laws_file": f"gen/M4/controls/ground_truth/{lid}/LAWS.bend",
            "ground_truth_proof_file": f"gen/M4/controls/ground_truth/{lid}/PROOF.bend",
        }
        (results_dir / f"{lid}.json").write_text(
            json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        full_records.append(rec)
        control_summaries.append(
            {
                "control_id": cid,
                "law_id": lid,
                "category": cat,
                "rule": ctrl["rule"],
                "subform": ctrl["subform"],
                "limitation_class": ctrl["limitation_class"],
                "description": ctrl["description"],
                "unassisted_status": unassisted_status,
                "bound": bound_str,
                "tried_generators": list(UNASSISTED_GENERATORS),
                "ground_truth_kind": gt_kind,
                "ground_truth_symbol": gt_symbol,
                "ground_truth_verified": True,
            }
        )

    calibration = compute_calibration(full_records)
    return {
        "total_controls": len(control_summaries),
        "unassisted_unknown_count": calibration["unknown_count"],
        "false_positive_proofs": calibration["false_positive_proofs"],
        "false_negative_refutations": calibration["false_negative_refutations"],
        "false_beyond_bound_verified_count": false_beyond_bound_verified,
        "true_unproved_verified_count": true_unproved_verified,
        "evaluation_budget": budget,
        "calibration": calibration,
        "controls": control_summaries,
    }
