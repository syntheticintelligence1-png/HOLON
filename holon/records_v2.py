"""holon.records_v2 -- M2 result-record v2 (whitepaper section 8.6).

Reads frozen-format v1 records (results/<m>/<law>.json, schema
schemas/result_record.schema.json) and produces v2 records conforming to
spec/M2/schemas/result_v2.json. The v1 records are read, never rewritten;
conversion is a pure function of (record, law, facts, repo artifacts).

CLI:  python -m holon.records_v2 --milestone M1 [--out DIR]
Writes results/<m>/v2/<law>.json and validates each record against the v2
schema (a stdlib mini-validator covering the features the schema uses).
"""
import json
import subprocess
import sys
from pathlib import Path

from . import ir
from .replay import witness_sha256, load_report

_SCHEMA_PATH = "spec/M2/schemas/result_v2.json"
_COVERAGE_DIR = "spec/M2/coverage"


# ----------------------------------------------------------------- loading
def load_schema(root: Path) -> dict:
    return json.loads((root / _SCHEMA_PATH).read_text())


def load_v1_records(milestone: str, root: Path) -> dict:
    """law_id -> parsed v1 record, sorted by law_id."""
    rdir = root / "results" / milestone
    out = {}
    if rdir.is_dir():
        for p in sorted(rdir.glob("L_*.json")):
            rec = json.loads(p.read_text())
            out[rec.get("law_id", p.stem)] = rec
    return out


def facts_of_law(law: dict) -> str:
    return law.get("facts")


def file_sha256(path: Path):
    import hashlib

    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------ small helpers
def _lean_version(root: Path) -> str:
    lean = root / "config" / "lean.json"
    exe = None
    if lean.is_file():
        exe = json.loads(lean.read_text()).get("cmd", [None])[0]
    for cand in [exe, str(Path.home() / ".elan/bin/lean"), "lean"]:
        if not cand:
            continue
        try:
            out = subprocess.run([cand, "--version"], capture_output=True, text=True, timeout=20)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip().splitlines()[0].rsplit(" ", 1)[-1]
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def _kernels(rec: dict, lean_version) -> list:
    """Per-kernel checker versions and verdict-kernel results."""
    k = rec.get("kernel", {})
    checker = rec.get("checker", {})
    out = [{
        "name": "bend2",
        "version": k.get("version"),
        "role": "primary",
        "result": checker.get("marker", "not_run"),
        "seconds": checker.get("seconds", 0.0),
    }]
    verdict = k.get("verdict")  # v1 kernel.verdict is a bare string: checked/failed/None
    seconds = next((a.get("seconds", 0.0) for a in rec.get("attempts", []) if a.get("kind") == "verdict"), 0.0)
    out.append({
        "name": "bendtt",
        "version": lean_version if verdict is not None else None,
        "role": "verdict",
        "result": verdict if verdict is not None else "not_run",
        "seconds": seconds,
    })
    return out


def _coverage_debt(facts_path: str, root: Path) -> list:
    """Coverage-debt items declared by the law's facts file."""
    p = root / facts_path
    if not p.is_file():
        return []
    debt = json.loads(p.read_text()).get("coverage", {}).get("debt", [])
    return [{"element": d, "source": facts_path} for d in sorted(debt)]


def _replay_evidence(rec: dict, milestone: str, report) -> dict:
    """Pointer at the replay evidence bound to this record's witness, if any."""
    status = (rec.get("replay") or {}).get("status")
    lid = rec.get("law_id")
    if status not in ("passed", "failed") or report is None:
        return None
    wh = report.get("witness_sha256", {}).get(lid)
    entry = (report.get("laws") or {}).get(lid)
    mine = witness_sha256(rec.get("witness"))
    if entry is None or not wh or wh != mine:
        return None
    return {"report": f"replay/{milestone}/report.json", "entry": f"laws.{lid}", "witness_sha256": wh}


def _refinement(milestone: str, report) -> list:
    """Refinement records: what the replay report says about agreement on real code."""
    if report is None:
        return []
    ref = report.get("refinement")
    if not ref:
        return []
    return [{
        "source": f"replay/{milestone}/report.json#refinement",
        "steps": ref.get("steps"),
        "traces": ref.get("traces"),
        "n_disagreements": ref.get("n_disagreements"),
        "per_action": ref.get("per_action"),
    }]


def convert(rec: dict, law: dict, milestone: str, root: Path, lean_version=None) -> dict:
    """v1 record -> v2 record. Pure: does not mutate or write the v1 record."""
    if law is None:
        raise KeyError(f"no law for record {rec.get('law_id')}")
    report = load_report(milestone, root)
    v2 = dict(rec)
    v2["record_version"] = 2
    v2["model_sha256"] = file_sha256(root / (rec.get("artifacts") or {}).get("model", ""))
    v2["witness_sha256"] = witness_sha256(rec.get("witness"))
    v2["kernels"] = _kernels(rec, lean_version if lean_version is not None else _lean_version(root))
    verdict = rec.get("kernel", {}).get("verdict")
    v2["independence_class"] = "I2" if verdict == "checked" else "I1"
    replay = dict(rec.get("replay") or {})
    replay["evidence"] = _replay_evidence(rec, milestone, report)
    if replay.get("status") == "not_run" and "model-only pending replay" in (replay.get("detail") or ""):
        replay["status"] = "model_only_pending_replay"
    v2["replay"] = replay
    v2["refinement"] = _refinement(milestone, report)
    v2["coverage_debt"] = _coverage_debt(facts_of_law(law), root)
    return v2


def convert_milestone(milestone: str, root: Path) -> dict:
    """law_id -> converted v2 record for every v1 record on disk."""
    laws = {l["law_id"]: l for l in ir.load_laws_any(milestone, root)}
    lean = _lean_version(root)
    return {lid: convert(rec, laws.get(lid), milestone, root, lean)
            for lid, rec in sorted(load_v1_records(milestone, root).items())}


# ----------------------------------------------------- mini schema validator
class SchemaError(Exception):
    pass


def _type_ok(val, ty):
    return {
        "object": isinstance(val, dict),
        "array": isinstance(val, list),
        "string": isinstance(val, str),
        "integer": isinstance(val, int) and not isinstance(val, bool),
        "number": isinstance(val, (int, float)) and not isinstance(val, bool),
        "boolean": isinstance(val, bool),
        "null": val is None,
    }[ty]


def validate(value, schema: dict, where: str = "$") -> list:
    """Validate against a JSON-schema subset (stdlib only).

    Covers: type, required, properties, items, enum, const, pattern,
    minItems, additionalProperties (when false), if/then/else, allOf.
    Returns a list of problem strings; empty means valid.
    """
    import re

    problems = []
    tys = schema.get("type")
    if tys is not None:
        for t in [tys] if isinstance(tys, str) else tys:
            if _type_ok(value, t):
                break
        else:
            return [f"{where}: expected type {tys}, got {json.dumps(value)[:80]}"]
    if "const" in schema and value != schema["const"]:
        problems.append(f"{where}: expected const {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{where}: {value!r} not in {schema['enum']}")
    if "pattern" in schema and isinstance(value, str) and not re.search(schema["pattern"], value):
        problems.append(f"{where}: {value!r} does not match {schema['pattern']}")
    if isinstance(value, dict):
        for r in schema.get("required", []):
            if r not in value:
                problems.append(f"{where}: missing required key {r!r}")
        props = schema.get("properties", {})
        for k, v in value.items():
            if k in props:
                problems += validate(v, props[k], f"{where}.{k}")
            elif schema.get("additionalProperties") is False:
                problems.append(f"{where}: unexpected key {k!r}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            problems.append(f"{where}: shorter than minItems {schema['minItems']}")
        for i, x in enumerate(value):
            problems += validate(x, schema.get("items", {}), f"{where}[{i}]")
    for sub in schema.get("allOf", []):
        problems += validate(value, sub, where)
    if "if" in schema:
        cond = validate(value, schema["if"], where)
        branch = schema.get("then") if not cond else schema.get("else")
        if branch:
            problems += validate(value, branch, where)
    return problems


# ----------------------------------------------------------------- cli
def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="holon.records_v2")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--out", default=None, help="output dir (default results/<m>/v2)")
    ap.add_argument("--check", action="store_true", help="validate only, do not write")
    args = ap.parse_args(argv)
    root = Path(__file__).resolve().parent.parent
    schema = load_schema(root)
    recs = convert_milestone(args.milestone, root)
    bad = 0
    for lid, rec in recs.items():
        problems = validate(rec, schema)
        if problems:
            bad += 1
            for p in problems:
                print(f"  INVALID {lid}: {p}")
    print(f"records_v2 {args.milestone}: {len(recs)} converted, {bad} invalid")
    if args.check:
        return 1 if bad else 0
    out = Path(args.out) if args.out else root / "results" / args.milestone / "v2"
    out.mkdir(parents=True, exist_ok=True)
    for lid, rec in recs.items():
        (out / f"{lid}.json").write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(recs)} records to {out}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
