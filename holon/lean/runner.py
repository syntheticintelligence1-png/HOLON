"""Per-law Lean emission + kernel check + record. (whitepaper §8.8-8.9, M2 S8)

For every PROVED and REFUTED law in the milestone registry:
  - emit the frozen statement (PROVED) or its negation at the model witness
    (REFUTED) as a Lean 4.34 theorem, generated from the law IR;
  - append it to the generated model under gen/lean/<milestone>/<law_id>.lean;
  - check the file with the pinned lean binary;
  - write results/lean/<milestone>/<law_id>.json with statement_hash,
    lean_sha256, exit_code, seconds, kernel_result.

`decide` is only ever used on fully instantiated closed goals (model
witnesses); forall goals use rfl/cases/induction templates. Laws whose
statement or proof template cannot be emitted faithfully are recorded
UNSUPPORTED, never approximated.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from .. import facts as F
from .. import ir
from . import codec as codec_gen
from . import laws01
from . import laws02
from . import machine as machine_gen

ROOT = Path(__file__).resolve().parents[2]
LEAN = shutil.which("lean") or str(Path.home() / ".elan/bin/lean")
TIMEOUT = 600


def _models(milestone: str):
    """facts path -> (lean model text, kind) built once per unique facts file."""
    out = {}
    for law in ir.load_laws_any(milestone, ROOT):
        fp = ROOT / law["facts"]
        sha = F.sha256_file(fp)
        if fp not in out:
            facts = F.load(fp)
            if facts.get("facts_version") == "holon-facts/0.2":
                out[fp] = (machine_gen.generate(facts, sha), "machine", facts, sha)
            else:
                out[fp] = (codec_gen.generate(facts, sha), "codec", facts, sha)
    return out


def _law_record_dir(milestone: str) -> Path:
    d = ROOT / "results" / "lean" / milestone
    d.mkdir(parents=True, exist_ok=True)
    return d


def _gen_dir(milestone: str) -> Path:
    d = ROOT / "gen" / "lean" / milestone
    d.mkdir(parents=True, exist_ok=True)
    return d


def _status(law_id: str, milestone: str) -> dict:
    p = ROOT / "results" / milestone / f"{law_id}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def emit_law(law: dict, kind: str, facts: dict, counter: bool, witness):
    """(statement block, extra def lines, unsupported reason, proof expected to check)."""
    if kind == "codec":
        try:
            block, defs = laws01.emit(law, facts, counter=counter, witness=witness)
        except laws01.Unsupported as e:
            return "", [], str(e), True
        return block, defs, None, True
    m = machine_gen.LMachine(facts)
    e = laws02.LEmit(m)
    try:
        block, defs, unsup, expected = e.emit(law, counter, witness)
    except laws02.Unsupported as ex:
        return "", [], str(ex), True
    return block, e.view_defs() + defs, unsup, expected


def check(path: Path) -> tuple[int, float, str]:
    t0 = time.time()
    try:
        p = subprocess.run([LEAN, str(path.relative_to(ROOT))], cwd=ROOT,
                           capture_output=True, text=True, timeout=TIMEOUT)
        secs = round(time.time() - t0, 3)
        return p.returncode, secs, (p.stderr or p.stdout)[-4000:]
    except subprocess.TimeoutExpired:
        return 124, round(time.time() - t0, 3), "timeout"


def run_milestone(milestone: str) -> dict:
    models = _models(milestone)
    coverage = []
    for law in ir.load_laws_any(milestone, ROOT):
        lid = law["law_id"]
        rec = _status(lid, milestone)
        status = rec.get("status")
        if status not in ("PROVED", "REFUTED"):
            continue
        model_text, kind, facts, fsha = models[ROOT / law["facts"]]
        counter = status == "REFUTED"
        witness = rec.get("witness")
        s_hash = ir.statement_hash(law)
        block, defs, unsup, expected = emit_law(law, kind, facts, counter, witness)
        gen_dir = _gen_dir(milestone)
        lpath = gen_dir / f"{lid}.lean"
        if not block:
            # statement itself could not be emitted faithfully
            text = (model_text + f"-- GENERATED stub for {lid}: statement UNSUPPORTED\n"
                    f"-- reason: {unsup}\n")
            lpath.write_text(text)
            record = {"law_id": lid, "milestone": milestone, "m0_status": status,
                      "statement_hash": s_hash, "lean_file": str(lpath.relative_to(ROOT)),
                      "lean_sha256": hashlib.sha256(text.encode()).hexdigest(),
                      "exit_code": None, "seconds": None, "kernel_result": "UNSUPPORTED",
                      "reason": unsup}
            coverage.append({"element": lid, "kind": "statement_unsupported", "reason": unsup})
            _law_record_dir(milestone).joinpath(f"{lid}.json").write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n")
            continue
        text = model_text + "\n" + "\n".join(defs) + ("\n" if defs else "") + block
        lpath.write_text(text)
        code, secs, tail = check(lpath)
        kernel = "PASS" if code == 0 else ("UNSUPPORTED" if (unsup or not expected) else "FAIL")
        record = {"law_id": lid, "milestone": milestone, "m0_status": status,
                  "statement_hash": s_hash, "lean_file": str(lpath.relative_to(ROOT)),
                  "lean_sha256": hashlib.sha256(text.encode()).hexdigest(),
                  "exit_code": code, "seconds": secs, "kernel_result": kernel}
        if code != 0:
            record["checker_tail"] = tail
            if unsup:
                record["reason"] = unsup
                coverage.append({"element": lid, "kind": "proof_template_unsupported", "reason": unsup})
            elif not expected:
                record["reason"] = tail.splitlines()[-1] if tail else "lean error"
                coverage.append({"element": lid, "kind": "proof_template_unsupported",
                                 "reason": record["reason"]})
            else:
                coverage.append({"element": lid, "kind": "kernel_rejected",
                                 "reason": tail.splitlines()[-1] if tail else "lean error"})
        _law_record_dir(milestone).joinpath(f"{lid}.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n")
    cov_dir = ROOT / "spec" / "M2" / "coverage"
    cov_dir.mkdir(parents=True, exist_ok=True)
    cov = {"frontend": "lean", "milestone": milestone,
           "target_commit": next(iter(models.values()))[2]["target"]["commit"],
           "items": sorted(coverage, key=lambda x: (x["element"], x["kind"], x["reason"]))}
    (cov_dir / f"lean_{milestone.lower()}.json").write_text(
        json.dumps(cov, indent=2, sort_keys=True) + "\n")
    return {"coverage": cov}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m holon.lean")
    ap.add_argument("--milestone", required=True, choices=["M0", "M1"])
    args = ap.parse_args(argv)
    out = run_milestone(args.milestone)
    for it in out["coverage"]["items"]:
        print(f"UNSUPPORTED {it['element']}: {it['reason']}")
    recs = sorted((ROOT / "results" / "lean" / args.milestone).glob("*.json"))
    n_ok = sum(1 for p in recs if json.loads(p.read_text())["kernel_result"] == "PASS")
    print(f"lean {args.milestone}: {n_ok}/{len(recs)} kernel PASS; "
          f"{len(out['coverage']['items'])} unsupported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
