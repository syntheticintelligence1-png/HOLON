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

from . import emit, ir, model_eval, refute
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
        if lf is None:
            return False, f"{lid}: no LAWS.bend artifact recorded"
        if not lf.is_file():
            return False, f"{lid}: LAWS.bend missing at {lf}"
        names = emit.law_names(lf)
        want = [lid.lower()] if r["status"] == "PROVED" else ["cl_" + lid.lower()]
        if names != want:
            return False, f"{lid}: LAWS.bend states {names}, expected {want}"
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


def _g4(root: Path, milestone: str, cfg: dict) -> tuple[bool, str, list]:
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
    if not env_ok:
        for g in CHECKS:
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
        ok, detail, canaries = _g4(root, milestone, cfg)
        checks["G4"] = {"passed": ok, "detail": detail}

    passed = all(c["passed"] for c in checks.values())
    report = {"milestone": milestone, "passed": passed, "bend_version": version,
              "checks": checks, "canaries": canaries}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for g in ("GENV", "G2", "G1", "G3", "G5", "G11", "G4"):
        c = checks[g]
        print(f"{g}: {'PASS' if c['passed'] else 'FAIL'} - {c['detail'][:200]}")
    return 0 if passed else 1
