"""The M0 gate: GENV, G2, G1, G3, G5, G11, G4 (M0_SPEC section 7)."""
from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import emit, ir, model_eval, refute, sm_gen
from .facts import DEFAULT_FACTS, ROOT, facts_sha256, load_facts

MARK_OK = model_eval.MARK_OK
CHECKS = ("G2", "G1", "G3", "G5", "G11", "G4")

_ESCAPE = [
    (re.compile(r"@unsafe"), "@unsafe"),
    (re.compile(r"def\s+[\w.]+\?\s*\("), "def name?("),
    (re.compile(r"\?TODO|\?[A-Za-z_]"), "?hole"),
    (re.compile(r'^\s*import\s+"', re.M), "foreign import"),
]


def _scan_bend_files(gen_dir: Path):
    bad = []
    for p in sorted(gen_dir.rglob("*.bend")):
        src = p.read_text()
        for rx, label in _ESCAPE:
            for m in rx.finditer(src):
                bad.append(f"{p}: {label}")
    return bad


def _env_scan(root: Path) -> list:
    bad = []
    for p in root.rglob("*"):
        if ".git" in p.parts:
            continue
        if p.name in ("bunfig.toml", ".env"):
            bad.append(str(p.relative_to(root)))
    return bad


def _genv(root: Path, cfg: dict) -> tuple[bool, str, str]:
    bad = _env_scan(root)
    if bad:
        return False, f"unsafe files present: {bad}", ""
    try:
        v = model_eval.bend_version(cfg)
    except Exception as e:
        return False, f"bend unavailable: {e}", ""
    if v != cfg["bend"]["pinned_version"]:
        return False, f"bend version {v} != pinned {cfg['bend']['pinned_version']}", v
    return True, f"bend {v}, no bunfig.toml/.env", v


def _g2(root: Path, milestone: str) -> tuple[bool, str]:
    reg = ir.load_registry(milestone, root=root)
    laws = ir.load_laws(milestone, root=root)
    ids = {l["law_id"] for l in laws}
    if "laws" in reg:
        hashes = reg["laws"]
        if ids != set(hashes):
            return False, f"law set {sorted(ids)} != registry {sorted(hashes)}"
        for l in laws:
            if ir.statement_hash(l) != hashes[l["law_id"]]:
                return False, f"{l['law_id']}: statement hash differs from registry"
        for rel, expected in sorted(reg["facts"].items()):
            path = root / rel
            if not path.exists() or facts_sha256(path) != expected:
                return False, f"facts hash differs from registry: {rel}"
    else:
        if ids != set(reg["statements"]):
            return False, f"law set {sorted(ids)} != registry {sorted(reg['statements'])}"
        for l in laws:
            if ir.statement_hash(l) != reg["statements"][l["law_id"]]:
                return False, f"{l['law_id']}: statement hash differs from registry"
        facts_path = root / DEFAULT_FACTS
        if not facts_path.exists() or facts_sha256(facts_path) != reg["facts_sha256"]:
            return False, "facts hash differs from registry"
    return True, f"{len(ids)} laws and facts match the registry"


def _g1(root: Path, milestone: str, cfg: dict) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="holon-g1-") as td:
        out, gen = Path(td) / "results", Path(td) / "gen"
        p = subprocess.run([sys.executable, "-m", "holon", "run", "--milestone", milestone,
                            "--out", str(out), "--gen-dir", str(gen)],
                           cwd=root, capture_output=True, text=True, timeout=1800,
                           env={**__import__("os").environ, "PYTHONPATH": str(root)})
        if p.returncode != 0:
            return False, "regeneration failed: " + (p.stdout + p.stderr)[-1000:]
        want = sorted((root / "gen" / milestone).rglob("*.bend"))
        got = sorted(gen.rglob("*.bend"))
        wnames = [str(p.relative_to(root / "gen" / milestone)) for p in want]
        gnames = [str(p.relative_to(gen)) for p in got]
        if wnames != gnames:
            return False, f"generated file set differs: {wnames} vs {gnames}"
        for w, g in zip(want, got):
            if w.read_bytes() != g.read_bytes():
                return False, f"{w.relative_to(root)} differs when regenerated"
        s1 = json.loads((root / "results" / milestone / "summary.json").read_text())
        s2 = json.loads((out / "summary.json").read_text())
        if s1 != s2:
            return False, f"summary differs: {s1} vs {s2}"
    return True, f"{len(wnames)} .bend files and summary.json are byte-identical"


def _g3(root: Path, milestone: str) -> tuple[bool, str]:
    bad = _scan_bend_files(root / "gen" / milestone)
    if bad:
        return False, "; ".join(bad[:20])
    return True, "no escape hatches in generated .bend files"


def _records(root: Path, milestone: str) -> dict:
    out = {}
    d = root / "results" / milestone
    if d.is_dir():
        for p in sorted(d.glob("L_*.json")):
            out[p.stem] = json.loads(p.read_text())
    return out


def _resolve(root: Path, p):
    if p is None:
        return None
    p = Path(p)
    return p if p.is_absolute() else root / p


def _g5(root: Path, milestone: str, cfg: dict) -> tuple[bool, str]:
    recs = _records(root, milestone)
    detail = []
    for lid, r in recs.items():
        if r["status"] not in ("PROVED", "REFUTED"):
            continue
        proof = _resolve(root, r["artifacts"]["proof"])
        if proof is None or not proof.is_file():
            return False, f"{lid}: proof artifact missing"
        code, out, _ = model_eval.run_bend([proof.name], cwd=proof.parent, cfg=cfg)
        if code != 0 or model_eval.first_marker(out) != MARK_OK:
            return False, f"{lid}: re-check failed: {out[:400]}"
        if cfg["bend"].get("verdict"):
            code, out, _ = model_eval.run_bend([proof.name, "--verdict"], cwd=proof.parent, cfg=cfg)
            if code != 0 or model_eval.first_marker(out) != MARK_OK:
                return False, f"{lid}: --verdict re-check failed: {out[:400]}"
        detail.append(lid)
    return True, f"re-checked {len(detail)} proofs ({', '.join(detail)})"


def _g11(root: Path, milestone: str) -> tuple[bool, str]:
    recs = _records(root, milestone)
    laws = ir.load_laws(milestone, root=root)
    for l in laws:
        lid = l["law_id"]
        if lid not in recs:
            return False, f"{lid}: no result record"
        r = recs[lid]
        lf = _resolve(root, r["artifacts"].get("laws"))
        if r["status"] == "UNKNOWN" and lf is None:
            continue
        if lf is None:
            return False, f"{lid}: no LAWS.bend artifact recorded"
        if not lf.is_file():
            return False, f"{lid}: LAWS.bend missing at {lf}"
        names = emit.law_names(lf)
        allowed = (([lid.lower()],) if r["status"] == "PROVED" else
                   (["cl_" + lid.lower()],) if r["status"] == "REFUTED" else
                   ([lid.lower()], ["cl_" + lid.lower()]))
        if names not in allowed:
            return False, f"{lid}: LAWS.bend states {names}, expected one of {allowed}"
    return True, f"{len(laws)} laws: records present, LAWS.bend states exactly the expected law"


def _call_terms(t, path=()):
    """Yield (path, term) for every call term inside a claim term."""
    if "call" in t:
        yield path, t
        for i, a in enumerate(t["args"]):
            yield from _call_terms(a, path + ("args", i))
    if "some" in t:
        yield from _call_terms(t["some"], path + ("some",))


def _set_at(term, path, value):
    cur = term
    for p in path[:-1]:
        cur = cur[int(p)] if isinstance(p, int) else cur[p]
    cur[path[-1]] = value


def _canary_variants(law: dict, facts: dict) -> list:
    """Mutated law IRs (kind, law_ir) for the canary kinds pin_const/swap_fn."""
    out = []
    st = law["statement"]
    # pin_const: bump one pinned constant's first byte (one variant per premise).
    for i, prem in enumerate(st.get("assume", [])):
        a, b = prem["eq"]
        if "bytes" in b and len(b["bytes"]) > 2:
            bs = bytearray.fromhex(b["bytes"][2:])
            bs[0] = (bs[0] + 1) % 256
            m = copy.deepcopy(law)
            m["statement"]["assume"][i]["eq"][1]["bytes"] = "0x" + bytes(bs).hex()
            out.append(("pin_const", m))
    # swap_fn: replace one call in the claim with another function of the same signature.
    for side_i, side in enumerate(st["claim"]["eq"]):
        for path, t in _call_terms(side):
            sig = (facts["functions"][t["call"]]["from"], facts["functions"][t["call"]]["to"])
            for alt, af in sorted(facts["functions"].items()):
                if alt != t["call"] and (af["from"], af["to"]) == sig:
                    m = copy.deepcopy(law)
                    _set_at(m["statement"]["claim"]["eq"][side_i], path + ("call",), alt)
                    out.append(("swap_fn", m))
                    break
            if out and out[-1][0] == "swap_fn":
                break
        if out and out[-1][0] == "swap_fn":
            break
    return out


def _evaluate_canary(claw: dict, facts: dict, facts_path, root):
    """Find a witness where the canary claim is false (or true, for negated)."""
    return refute.find_witness(claw, facts, facts_path=facts_path, root=root)


def _check_bend(dirp: Path, cfg) -> bool:
    code, out, _ = model_eval.run_bend(["PROOF.bend"], cwd=dirp, cfg=cfg)
    return code == 0 and model_eval.first_marker(out) == MARK_OK


def _g12(root: Path, milestone: str) -> tuple[bool, str]:
    recs = _records(root, milestone)
    laws = {law["law_id"]: law for law in ir.load_laws(milestone, root=root)}
    checked = 0
    for lid, law in laws.items():
        if law.get("statement", {}).get("kind") != "sm":
            continue
        rec = recs.get(lid)
        if rec is None:
            return False, f"{lid}: no result record"
        if rec.get("status") not in ("PROVED", "REFUTED"):
            continue
        bound = rec.get("bound")
        want_n = int(load_facts(root / law["facts"])["config"]["N"])
        want_k = int(law["statement"]["bound"]["K"])
        if not isinstance(bound, dict) or bound.get("N") != want_n or bound.get("K") != want_k:
            return False, f"{lid}: bound {bound!r} != {{'N': {want_n}, 'K': {want_k}}}"
        checked += 1
    return True, f"{checked} PROVED/REFUTED SM records carry their N,K bounds"


def _sm_mutations(facts: dict) -> list[tuple[str, str, dict]]:
    """Return deterministic single-site mutations over req, comparison, and set."""
    import copy
    mutations = []

    def visit_statements(action, stmts, path):
        for ix, stmt in enumerate(stmts):
            here = path + (ix,)
            if "req" in stmt:
                mutations.append(("drop_req", f"{action}:{here}", (action, path, ix)))
            if "set" in stmt:
                mutations.append(("drop_set", f"{action}:{here}", (action, path, ix)))
            for key in ("then", "else", "body"):
                if isinstance(stmt.get(key), list):
                    visit_statements(action, stmt[key], path + (ix, key))

    for action in sorted(facts["actions"]):
        visit_statements(action, facts["actions"][action].get("body", []), ("body",))

    def comparison_sites(x, path=()):
        if isinstance(x, dict):
            for key, value in x.items():
                if key in ("lt", "le", "eq", "ne") and isinstance(value, list):
                    yield path + (key,), key
                yield from comparison_sites(value, path + (key,))
        elif isinstance(x, list):
            for ix, value in enumerate(x):
                yield from comparison_sites(value, path + (ix,))

    comps = []
    for action in sorted(facts["actions"]):
        for path, op in comparison_sites(facts["actions"][action].get("body", []), ("body",)):
            if op in ("lt", "le", "eq", "ne"):
                comps.append((action, path, op))

    def at_path(obj, path):
        for key in path:
            obj = obj[key]
        return obj

    def set_path(obj, path, value):
        parent = at_path(obj, path[:-1])
        parent[path[-1]] = value

    for kind, label, loc in [x for x in mutations if x[0] == "drop_req"][:4]:
        action, path, ix = loc
        changed = copy.deepcopy(facts)
        parent = at_path(changed["actions"][action], path)
        del parent[ix]
        mutations.append((kind, label, changed))
    for ix, (action, path, op) in enumerate(comps[:4]):
        changed = copy.deepcopy(facts)
        newop = {"lt": "le", "le": "lt", "eq": "ne", "ne": "eq"}[op]
        value = at_path(changed["actions"][action], path)
        set_path(changed["actions"][action], path[:-1] + (newop,), value)
        del at_path(changed["actions"][action], path[:-1])[op]
        mutations.append(("flip_cmp", f"{action}:{path}:{op}->{newop}", changed))
    for kind, label, loc in [x for x in mutations if x[0] == "drop_set"][:4]:
        action, path, ix = loc
        changed = copy.deepcopy(facts)
        parent = at_path(changed["actions"][action], path)
        del parent[ix]
        mutations.append((kind, label, changed))
    return [m for m in mutations if isinstance(m[2], dict) and "actions" in m[2]]


def _g4_m1(root: Path, cfg: dict) -> tuple[bool, str, list]:
    import copy
    from . import sm_emit

    base_facts_path = root / "proposals" / "M1" / "facts" / "rollup_sm.json"
    base_facts = load_facts(base_facts_path)
    recs = _records(root, "M1")
    laws = {law["law_id"]: law for law in ir.load_laws("M1", root=root)}
    artifacts = []
    for lid in sorted(recs):
        record = recs[lid]
        paths = record.get("artifacts", {})
        law_file, proof_file = _resolve(root, paths.get("laws")), _resolve(root, paths.get("proof"))
        if law_file and proof_file and law_file.is_file() and proof_file.is_file():
            artifacts.append((lid, law_file, proof_file))

    canaries = []
    mutations = _sm_mutations(base_facts)
    with tempfile.TemporaryDirectory(prefix="holon-g4-m1-") as td:
        td = Path(td)
        for ix, (kind, label, mutated) in enumerate(mutations):
            case = td / f"sm_{ix:02d}"
            model_dir = case / "gen" / "M1" / "model"
            model_dir.mkdir(parents=True)
            facts_copy = case / "rollup_sm.json"
            facts_copy.write_text(json.dumps(mutated, indent=2, sort_keys=True) + "\n")
            (model_dir / "rollup_sm.bend").write_text(sm_gen.bend_model(mutated))
            detected_by = None
            for lid, law_file, proof_file in artifacts:
                law_dir = case / "gen" / "M1" / lid
                law_dir.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(law_file, law_dir / "LAWS.bend")
                shutil.copyfile(proof_file, law_dir / "PROOF.bend")
                if not _check_bend(law_dir, cfg):
                    detected_by = lid
                    break
            canaries.append({"id": f"{kind}:{label}", "kind": kind,
                             "detected": detected_by is not None,
                             "detected_by": detected_by,
                             "mutated_facts": f"{kind}:{label}"})

        # Ordinary M0-style statement canaries for each PAR law.
        header_laws = [law for law in laws.values() if law.get("rule") == "PAR"]
        for law in header_laws:
            facts_path = root / law["facts"]
            law_facts = load_facts(facts_path)
            model_dir = td / "model"
            model_dir.mkdir(exist_ok=True)
            shutil.copyfile(root / "gen" / "M1" / "model" / f"{facts_path.stem}.bend",
                            model_dir / f"{facts_path.stem}.bend")
            for vi, (kind, claw) in enumerate(_canary_variants(law, law_facts)):
                hit = _evaluate_canary(claw, law_facts, facts_path, root)
                if not hit:
                    continue
                d = td / f"statement_{law['law_id']}_{vi}"
                d.mkdir(parents=True, exist_ok=True)
                (d / "LAWS.bend").write_text(
                    emit.emit_laws(claw, law_facts, model_name=facts_path.stem))
                (d / "PROOF.bend").write_text(
                    emit.emit_proof(claw, law_facts, model_name=facts_path.stem))
                rejected = not _check_bend(d, cfg)
                canaries.append({"id": f"{law['law_id']}:{kind}:{vi}", "kind": kind,
                                 "detected": rejected,
                                 "detected_by": "checker" if rejected else None,
                                 "mutated_facts": "law-statement",
                                 "counterexample": hit["witness"]})

    kinds = {c["kind"] for c in canaries}
    survivors = [c["id"] for c in canaries if not c["detected"]]
    ok = len(mutations) >= 12 and len(kinds) >= 3 and not survivors
    detail = (f"{len(canaries)} canaries ({len(mutations)} SM mutations) across {len(kinds)} kinds; "
              f"detected: {len(canaries) - len(survivors)}/{len(canaries)}; survivors: {survivors}")
    return ok, detail, canaries


def _g4(root: Path, milestone: str, cfg: dict) -> tuple[bool, str, list]:
    if milestone == "M1":
        return _g4_m1(root, cfg)
    recs = _records(root, milestone)
    facts_path = root / DEFAULT_FACTS
    facts = load_facts(facts_path)
    laws = {l["law_id"]: l for l in ir.load_laws(milestone, root=root)}
    canaries = []
    with tempfile.TemporaryDirectory(prefix="holon-g4-") as td:
        td = Path(td)
        (td / "model").mkdir()
        (td / "model" / "morph_header.bend").write_text((root / "gen" / milestone / "model" / "morph_header.bend").read_text())
        for lid in sorted(recs):
            r = recs[lid]
            if r["status"] != "PROVED":
                continue
            law = laws[lid]
            # pin_const + swap_fn mutants.
            for vi, (kind, claw) in enumerate(_canary_variants(law, facts)):
                hit = _evaluate_canary(claw, facts, facts_path, root)
                if not hit:
                    continue
                d = td / f"can_{lid}_{kind}_{vi}"
                d.mkdir(parents=True)
                (d / "LAWS.bend").write_text(emit.emit_laws(claw, facts))
                (d / "PROOF.bend").write_text(emit.emit_proof(claw, facts))
                rejected = not _check_bend(d, cfg)
                canaries.append({"id": f"{lid}:{kind}:{vi}", "kind": kind, "source_law": lid,
                                 "law": claw, "negated": False,
                                 "counterexample": hit["witness"], "rejected": rejected})
            # negated: a counter-law of the true law at a point where it holds.
            hold = None
            for w, res in zip(_canary_hold_candidates(law, facts),
                              model_eval.eval_claim(law, _canary_hold_candidates(law, facts), facts_path, root)):
                if res["eq"] is True:
                    hold = {b["name"]: w[b["name"]] for b in law["statement"]["forall"]}
                    break
            if hold is None:
                continue
            d = td / f"can_{lid}_negated"
            d.mkdir(parents=True)
            (d / "LAWS.bend").write_text(emit.emit_counter_laws(law, facts, hold))
            (d / "PROOF.bend").write_text(emit.emit_counter_proof(law, facts, hold))
            rejected = not _check_bend(d, cfg)
            canaries.append({"id": f"{lid}:negated", "kind": "negated", "source_law": lid,
                             "law": law, "negated": True,
                             "counterexample": hold, "rejected": rejected})
    kinds = {c["kind"] for c in canaries}
    ok = (len(canaries) >= 10 and len(kinds) >= 3 and all(c["rejected"] for c in canaries))
    detail = f"{len(canaries)} canaries of {len(kinds)} kinds; rejected: {sum(c['rejected'] for c in canaries)}/{len(canaries)}"
    return ok, detail, canaries


def _canary_hold_candidates(law: dict, facts: dict) -> list:
    """Canonical-JSON binder assignments covering the deterministic candidates."""
    from .emit import pins_of
    pins_map = pins_of(law)
    b = law["statement"]["forall"][0]
    out = []
    if b["type"] == "Header":
        for h in refute.header_candidates(facts, pins_map.get(b["name"], {})):
            out.append({b["name"]: {k: "0x" + v.hex() for k, v in h.items()}})
            if len(out) >= 60:
                break
    else:
        for x in refute.bytes_candidates():
            out.append({b["name"]: "0x" + x.hex()})
            if len(out) >= 60:
                break
    return out


def main(args) -> int:
    root = Path(args.root) if args.root else ROOT
    root = root.resolve()
    milestone = args.milestone
    report_path = Path(args.report) if args.report else root / "results" / milestone / "gate_report.json"
    cfg = model_eval.config(root)

    checks = {}
    canaries = []
    version = ""
    env_ok, env_detail, version = _genv(root, cfg)
    checks["GENV"] = {"passed": env_ok, "detail": env_detail}
    gate_checks = ("G2", "G1", "G3", "G5", "G11", "G12", "G4") if milestone == "M1" else CHECKS
    if not env_ok:
        for g in gate_checks:
            checks[g] = {"passed": False, "detail": "skipped: unsafe environment"}
    else:
        ok, detail = _g2(root, milestone)
        checks["G2"] = {"passed": ok, "detail": detail}
        if ok:
            ok, detail = _g1(root, milestone, cfg)
            checks["G1"] = {"passed": ok, "detail": detail}
        else:
            checks["G1"] = {"passed": False, "detail": "skipped: registry mismatch"}
        ok, detail = _g3(root, milestone)
        checks["G3"] = {"passed": ok, "detail": detail}
        ok, detail = _g5(root, milestone, cfg)
        checks["G5"] = {"passed": ok, "detail": detail}
        ok, detail = _g11(root, milestone)
        checks["G11"] = {"passed": ok, "detail": detail}
        if milestone == "M1":
            ok, detail = _g12(root, milestone)
            checks["G12"] = {"passed": ok, "detail": detail}
        ok, detail, canaries = _g4(root, milestone, cfg)
        checks["G4"] = {"passed": ok, "detail": detail}

    passed = all(c["passed"] for c in checks.values())
    report = {"milestone": milestone, "passed": passed, "bend_version": version,
              "checks": checks, "canaries": canaries}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print_order = ("GENV", *gate_checks)
    for g in print_order:
        c = checks[g]
        print(f"{g}: {'PASS' if c['passed'] else 'FAIL'} - {c['detail'][:200]}")
    return 0 if passed else 1
