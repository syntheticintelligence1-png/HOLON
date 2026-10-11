"""`holon run`: every frozen law ends PROVED, REFUTED or UNKNOWN (whitepaper §8.6, M0_SPEC §6).

For each law, in law_id order:
  1. emit LAWS.bend (one law) and try each proof generator; PROVED iff Bend accepts and
     the expected law is the only law in LAWS.bend;
  2. otherwise search the compiled model for a witness and emit a counter-law;
     REFUTED iff Bend accepts it;
  3. otherwise UNKNOWN, with what was tried.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

from . import bend, ir, refute
from . import facts as F
from .gen import laws as LG
from .gen import model as G
from .gen import proofs as PG
from .model_eval import CompiledModel, model_name

ROOT = Path(__file__).resolve().parents[1]
LAW_RE = re.compile(r"^law\s+([A-Za-z0-9_.]+)\s*:", re.M)


class RegistryMismatch(Exception):
    pass


def law_names(text: str) -> list[str]:
    return LAW_RE.findall(text)


def relpath(p: Path) -> str:
    p = Path(p).resolve()
    try:
        return p.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(p)


def load_triage(milestone: str) -> dict:
    p = ROOT / "config" / "triage.json"
    return json.loads(p.read_text()).get(milestone, {}) if p.exists() else {}


def check_registry(laws: list[dict], milestone: str, facts_sha: str) -> None:
    reg = ir.load_registry(milestone, ROOT)
    problems = []
    if reg["facts_sha256"] != facts_sha:
        problems.append(f"facts hash {facts_sha} != registry {reg['facts_sha256']}")
    if sorted(reg["statements"]) != sorted(l["law_id"] for l in laws):
        problems.append("registry and laws/ list different law ids")
    for law in laws:
        if law["facts_sha256"] != facts_sha:
            problems.append(f"{law['law_id']}: facts_sha256 differs from the facts")
        h = ir.statement_hash(law)
        if reg["statements"].get(law["law_id"]) != h:
            problems.append(f"{law['law_id']}: statement hash {h} != registry")
    if problems:
        raise RegistryMismatch("; ".join(problems))


def _first_error(out: str, n: int = 12) -> str:
    return "\n".join(out.strip().splitlines()[:n])


def prove(law: dict, facts: dict, d: Path, model_import: str, cfg: dict, attempts: list):
    em = LG.emit(law, facts, model_import, header_note=ir.statement_hash(law))
    for gname, gen in PG.GENERATORS:
        text = gen(em, facts, model_import)
        if text is None:
            continue
        d.mkdir(parents=True, exist_ok=True)
        (d / "LAWS.bend").write_text(em.text)
        (d / "PROOF.bend").write_text(text)
        r = bend.check(d / "PROOF.bend", cfg)
        ok = r.ok and law_names(em.text) == [em.name] and not bend.escape_hatches(text + em.text)
        attempts.append({"kind": "proof", "generator": gname, "exit_code": r.code, "marker": r.marker,
                         "seconds": r.seconds, **({} if ok else {"error": _first_error(r.out)})})
        if ok:
            return em, r
    return em, None


def refute_law(law: dict, facts: dict, d: Path, model_import: str, cfg: dict, model: CompiledModel,
               attempts: list):
    s = refute.search(law, facts, model)
    attempts.append({"kind": "refute", "engine": "compiled-model search", "bound": s.bound, "tried": s.tried,
                     "undefined": s.undefined, "hit": s.witness is not None, "notes": s.notes})
    if s.witness is None:
        return None, None, s
    em = LG.emit(law, facts, model_import, counter=True, header_note=ir.statement_hash(law))
    text = PG.counter(em, facts, model_import, s.witness)
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    (d / "LAWS.bend").write_text(em.text)
    (d / "PROOF.bend").write_text(text)
    r = bend.check(d / "PROOF.bend", cfg)
    ok = r.ok and law_names(em.text) == [em.name] and not bend.escape_hatches(text + em.text)
    attempts.append({"kind": "counter-law", "generator": "counter", "exit_code": r.code, "marker": r.marker,
                     "seconds": r.seconds, **({} if ok else {"error": _first_error(r.out)})})
    return (em, r, s) if ok else (None, None, s)


def run(milestone: str = "M0", facts_path: str | None = None, out: str | None = None,
        gen_dir: str | None = None, no_registry: bool = False, log=print) -> dict:
    cfg = bend.config(ROOT)
    facts_path = Path(facts_path or ROOT / "facts" / "morph_header.json")
    out_dir = Path(out or ROOT / "results" / milestone)
    gen = Path(gen_dir or ROOT / "gen" / milestone)
    facts = F.load(facts_path)
    facts_sha = F.sha256_file(facts_path)
    laws = ir.load_laws(milestone, ROOT)
    if no_registry:
        laws = [ir.rebind_facts(l, facts_sha) for l in laws]
    else:
        check_registry(laws, milestone, facts_sha)
    kver = bend.version(cfg)
    if kver != cfg["bend"]["pinned_version"]:
        raise RuntimeError(f"bend {kver} is not the pinned {cfg['bend']['pinned_version']}")
    verdict = bend.verdict_enabled(cfg)
    triage = load_triage(milestone)

    # 1. the model, generated from the facts (and compiled for the refuter)
    name = model_name(facts_path)
    if gen.exists():
        shutil.rmtree(gen)
    model_src = gen / "model" / f"{name}.bend"
    model_src.parent.mkdir(parents=True)
    model_src.write_text(G.generate(facts, facts_sha))
    compiled = CompiledModel.build(facts_path, cfg=cfg)
    model_import = f"../model/{name}.bend"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {}
    for law in laws:
        lid = law["law_id"]
        d = gen / lid
        attempts: list = []
        rec = {"law_id": lid, "statement_hash": ir.statement_hash(law), "facts_sha256": facts_sha,
               "statement": ir.render_statement(law), "premises": ir.premises(law),
               "kernel": {"name": "bend", "version": kver, "verdict": "not_run"},
               "artifacts": {"laws": None, "proof": None, "model": relpath(model_src), "law_name": None},
               "checker": {"exit_code": None, "marker": "not_run"}, "witness": None, "difference": None,
               "triage": "none", "replay": {"status": "not_run", "detail": "replay is milestone P5"}}
        status, em, r = "UNKNOWN", None, None
        try:
            em, r = prove(law, facts, d, model_import, cfg, attempts)
            if r is not None:
                status = "PROVED"
            else:
                em, r, s = refute_law(law, facts, d, model_import, cfg, compiled, attempts)
                if r is not None:
                    status = "REFUTED"
                    rec["witness"], rec["difference"] = s.witness, s.difference
                    t = triage.get(lid, {})
                    rec["triage"] = t.get("triage", "finding")
                    if t.get("why"):
                        rec["triage_why"] = t["why"]
                else:
                    rec["bound"] = s.bound
        except LG.Unsupported as e:
            attempts.append({"kind": "emit", "error": f"unsupported statement form: {e}"})
            rec["bound"] = "not searched: the emitter cannot express this statement faithfully"
        if status == "UNKNOWN":
            shutil.rmtree(d, ignore_errors=True)
            rec["bound"] = rec.get("bound") or "no witness in the searched space"
            rec["scope"] = "bounded"
        else:
            rec["scope"] = "unbounded"
            rec["artifacts"].update({"laws": relpath(d / "LAWS.bend"), "proof": relpath(d / "PROOF.bend"),
                                     "law_name": em.name})
            rec["checker"] = {"exit_code": r.code, "marker": r.marker, "seconds": r.seconds}
            if verdict:
                v = bend.check_verdict(d / "PROOF.bend", cfg)
                rec["kernel"]["verdict"] = "checked" if v.ok else "failed"
                attempts.append({"kind": "verdict", "kernel": "BendTT (Lean-proven)", "exit_code": v.code,
                                 "marker": v.marker, "seconds": v.seconds})
        rec["status"] = status
        rec["attempts"] = attempts
        (out_dir / f"{lid}.json").write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
        summary[lid] = status
        log(f"{lid:16s} {status:8s} {rec['kernel']['verdict']:8s} {rec['triage']}")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main_run(args) -> int:
    try:
        run(args.milestone, args.facts, args.out, args.gen_dir, args.no_registry)
    except RegistryMismatch as e:
        print(f"refusing to run: {e}", file=sys.stderr)
        return 2
    return 0
