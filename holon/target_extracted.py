"""Targets with extracted documents (I49): `python -m holon target extract|coverage|diagram|sizes|gate ...`.

  holon target extract  --target NAME [--check]   the target's extract method into its documents (target.json
                                                  extract.documents) and, for each Solidity document, the extraction
                                                  report gen/targets/NAME/extraction.json (dependency_version debt)
  holon target coverage --target NAME [--check]   gen/targets/NAME/coverage.json, holon.coverage's format, from the
                                                  frontend's coverage walk over each extraction sidecar of the target
  holon target diagram  --target NAME [--check]   one diagram per document: holon-facts/0.3 transitions documents by
                                                  holon.diagram.transitions_diagram, 0.1/0.2 by holon.diagram.build,
                                                  at gen/diagrams/NAME/<stem_>.json
  holon target sizes [--check]                    results/targets/sizes.json (spec/M4/lib/sizes.schema.json): the
                                                  rows of spec/M4/lib/heldout_protocol.json sizes.rows
  holon target gate     --target NAME [--checks ID,..]   GENV, X1, X2, G8, D1, S1: results/targets/NAME/gate_report.json

--check writes nothing and exits 0 iff every file the command writes holds exactly the bytes of a fresh run.

A target's checkout is the config/holon.json value at its checkout.config key path. `extract` writes only documents
under gen/targets/NAME/: a document a committed milestone owns (the development target's) is only ever --check'ed.
Which target is which is read from targets/<name>/target.json and the protocol sidecar; nothing here names a target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from . import targets as T

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "spec/M4/lib/heldout_protocol.json"
SIZES = "results/targets/sizes.json"
SIZES_SCHEMA = "spec/M4/lib/sizes.schema.json"
DIAGRAM_SCHEMA = "spec/M4/lib/diagram_transitions.schema.json"
SIZES_VERSION = "holon-sizes/0.1"
LINEARITY = ("not claimed: four diagrams and one held-out target support no claim about how obligation counts grow "
             "with |E| or |V|")
I49_CHECKS = ["GENV", "X1", "X2", "G8", "D1", "S1"]


class TargetFailure(RuntimeError):
    pass


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def config(root: Path) -> dict:
    return load(Path(root) / "config" / "holon.json")


def checkout(t: dict, root: Path) -> Path:
    co = t.get("checkout") or {}
    if not co.get("config"):
        raise TargetFailure(f"target {t['name']}: checkout.config names no config key")
    try:
        return Path(T.config_value(config(root), co["config"]))
    except (KeyError, TypeError):
        raise TargetFailure(f"target {t['name']}: config/holon.json has no {'.'.join(co['config'])}") from None


def documents(t: dict) -> dict[str, str]:
    """{output file name: repo-relative path} of the target's documents."""
    return dict(sorted((t.get("extract") or {}).get("documents", {}).items()))


def own_prefix(t: dict) -> str:
    return f"gen/targets/{t['name']}/"


def extraction_report_path(t: dict) -> str:
    return f"gen/targets/{t['name']}/extraction.json"


def coverage_path(t: dict) -> str:
    return f"gen/targets/{t['name']}/coverage.json"


def diagram_path(t: dict, doc_rel: str) -> str:
    from .diagram.transitions_diagram import model_name
    return f"gen/diagrams/{t['name']}/{model_name(doc_rel)}.json"


def sidecars(t: dict, root: Path) -> list[Path]:
    """The extraction sidecars the target's commands name (--sidecar), repo-relative under root."""
    out = []
    for cmd in (t.get("extract") or {}).get("commands") or []:
        for i, x in enumerate(cmd):
            if x == "--sidecar" and i + 1 < len(cmd):
                out.append(Path(root) / cmd[i + 1])
    return out


# ------------------------------------------------------------------ extract
def _run_commands(t: dict, root: Path, co: Path, out: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    for cmd in (t.get("extract") or {}).get("commands") or []:
        argv = [c.replace("{checkout}", str(co)).replace("{out}", str(out)).replace("{python}", sys.executable)
                .replace("{root}", str(root)) for c in cmd]
        p = subprocess.run(argv, cwd=root, env=env, capture_output=True, text=True)
        if p.returncode != 0:
            raise TargetFailure(f"extraction command {' '.join(cmd[:5])} exited {p.returncode}: "
                                f"{(p.stdout + p.stderr)[-1500:]}")


def _dep_dirs(co: Path) -> list[tuple[str, Path]]:
    """(unit prefix, directory) pairs where the target keeps its own copies of dependencies: foundry remappings
    (remappings.txt, prefix=path lines) and node_modules."""
    import re
    out, lines = [], []
    rm = co / "remappings.txt"
    if rm.is_file():
        lines += rm.read_text(encoding="utf-8").splitlines()
    ft = co / "foundry.toml"
    if ft.is_file():
        for block in re.findall(r"remappings\s*=\s*\[(.*?)\]", ft.read_text(encoding="utf-8"), re.S):
            lines += re.findall(r"[\"']([^\"']+=[^\"']+)[\"']", block)
    for line in lines:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            pre, path = line.split("=", 1)
            pre = pre.split(":")[-1]
            if (pre, co / path) not in out:
                out.append((pre, co / path))
    if (co / "node_modules").is_dir():
        out.append(("", co / "node_modules"))
    return out


def dependency_report(t: dict, doc_rel: str, doc: dict, co: Path, root: Path) -> dict:
    """Rule S6: every unit the extraction read that is not in the checkout came from the pinned sol_deps; it is debt
    when the target holds its own copy with other bytes, or holds none."""
    deps = (config(root).get("replay") or {}).get("sol_deps")
    debt, units = [], []
    for u in sorted((doc.get("extraction") or {}).get("inputs") or [], key=lambda x: x["unit"]):
        unit, sha = u["unit"], u["sha256"]
        if (co / unit).is_file():
            units.append({"unit": unit, "from": "checkout", "sha256": sha})
            continue
        units.append({"unit": unit, "from": "sol_deps", "sha256": sha})
        own = [d / unit[len(pre):].lstrip("/") for pre, d in _dep_dirs(co) if unit.startswith(pre)]
        own = [p for p in own if p.is_file()]
        if not own:
            debt.append({"unit": unit, "kind": "dependency_version",
                         "detail": f"solc read this unit from the pinned sol_deps ({sha[:12]}); the target checkout "
                                   "holds no copy of it under its own dependency directories, so the target's own "
                                   "version is unknown"})
            continue
        mine = sha256_file(own[0])
        if mine != sha:
            rel = own[0].relative_to(co).as_posix()
            debt.append({"unit": unit, "kind": "dependency_version",
                         "detail": f"solc read this unit from the pinned sol_deps ({sha[:12]}); the target's own copy "
                                   f"{rel} differs ({mine[:12]})"})
    return {"report_version": "holon-target-extraction/0.1", "document": doc_rel, "sol_deps": deps,
            "units": units, "debt": debt,
            "doc": "rule S6 of spec/M4/lib/heldout_protocol.json: units solc read from the pinned sol_deps instead of "
                   "the target's own dependency copies are extraction debt (dependency_version)."}


def extract(name: str, root: Path, check: bool) -> int:
    t = T.load(name, root)
    if (t.get("extract") or {}).get("method") != "commands":
        print(f"holon target extract: target {name}: extract.method is not commands (nothing is extracted here)")
        return 0
    co = checkout(t, root)
    docs = documents(t)
    with tempfile.TemporaryDirectory(prefix="holon-target-extract-") as td:
        out = Path(td)
        _run_commands(t, root, co, out)
        writes: dict[str, bytes] = {}
        for fname, rel in docs.items():
            f = out / fname
            if not f.is_file():
                raise TargetFailure(f"the extraction wrote no {fname}")
            b = f.read_bytes()
            writes[rel] = b
            doc = json.loads(b.decode("utf-8"))
            if (doc.get("extraction") or {}).get("frontend") == "solidity" and rel.startswith(own_prefix(t)):
                writes[extraction_report_path(t)] = dumps(dependency_report(t, rel, doc, co, root)).encode()
    return _write_or_check("extract", root, writes, check, t)


def _write_or_check(cmd: str, root: Path, writes: dict[str, bytes], check: bool, t: dict | None = None) -> int:
    bad = []
    for rel, b in sorted(writes.items()):
        p = Path(root) / rel
        if check:
            if not p.is_file() or p.read_bytes() != b:
                bad.append(rel)
            continue
        if t is not None and cmd == "extract" and not rel.startswith(own_prefix(t)):
            if not p.is_file() or p.read_bytes() != b:
                raise TargetFailure(f"{rel} is a committed milestone document: target extract only --check's it, and "
                                    "a fresh extraction differs")
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_bytes(b)
        os.replace(tmp, p)
        print(f"holon target {cmd}: wrote {rel}")
    if check:
        for rel in bad:
            print(f"holon target {cmd}: {rel} differs from a fresh run")
        if not bad:
            print(f"holon target {cmd}: up to date ({len(writes)} files)")
        return 1 if bad else 0
    return 0


# ------------------------------------------------------------------ coverage
def coverage_data(t: dict, root: Path) -> bytes:
    from . import frontends
    from .coverage import render
    co = checkout(t, root)
    docs = []
    for sp in sidecars(t, root):
        side = frontends.load_sidecar(sp)
        mod = frontends._frontend(side["frontend"])
        if mod is None or not callable(getattr(mod, "coverage_document", None)):
            continue
        cov = mod.coverage_document(side, sp, root, co)
        if cov is not None:
            docs.append(dict(cov, document=side["output"]))
    docs.sort(key=lambda d: d["document"])
    return render({"documents": docs, "unaccounted": sum(len(d["unaccounted"]) for d in docs)})


def coverage(name: str, root: Path, check: bool) -> int:
    t = T.load(name, root)
    return _write_or_check("coverage", root, {coverage_path(t): coverage_data(t, root)}, check)


# ------------------------------------------------------------------ diagram
def _diagram_bytes(doc_rel: str, root: Path) -> bytes:
    p = Path(root) / doc_rel
    facts = load(p)
    if facts.get("facts_version") == "holon-facts/0.3":
        from .diagram.transitions_diagram import build_file, dumps as tdumps
        return tdumps(build_file(p, root)).encode()
    from .diagram import build
    from .diagram.model import dumps as ddumps
    return ddumps(build(p, root).to_json()).encode()


def diagram_writes(t: dict, root: Path) -> dict[str, bytes]:
    return {diagram_path(t, rel): _diagram_bytes(rel, root) for rel in documents(t).values()}


def diagram(name: str, root: Path, check: bool) -> int:
    t = T.load(name, root)
    return _write_or_check("diagram", root, diagram_writes(t, root), check)


# ------------------------------------------------------------------ sizes
def _law_entries(source: str, root: Path) -> list[dict]:
    p = Path(root) / source
    if p.name == "DERIVATION.json":
        return [{"rule": x["rule"], "subform": x.get("subform"), "facts": x.get("facts")} for x in load(p)["laws"]]
    out = []
    for f in sorted(p.glob("L*.json")):
        law = load(f)
        out.append({"rule": law["rule"], "subform": law.get("subform"), "facts": law.get("facts")})
    return out


def _obligations(source: str | None, document: str, root: Path, pending: str | None) -> dict:
    if pending is not None or source is None:
        return {"source": source or "", "pending": pending or "I50", "total": None, "by_rule": None,
                "by_rule_subform": None, "law_set_total": None}
    laws = _law_entries(source, root)
    mine = [x for x in laws if x["facts"] == document]
    return {"source": source, "pending": None, "total": len(mine), "law_set_total": len(laws),
            "by_rule": dict(sorted(Counter(x["rule"] for x in mine).items())),
            "by_rule_subform": dict(sorted(Counter(f"{x['rule']}/{x['subform']}" for x in mine).items()))}


def heldout(root: Path) -> dict:
    proto = load(Path(root) / PROTOCOL)
    seal = proto["seal"]["file"]
    hits = [T.load(n, root) for n in T.names(root) if (T.load(n, root).get("checkout") or {}).get("sealed") == seal]
    if len(hits) != 1:
        raise TargetFailure(f"exactly one target must name the seal {seal} in checkout.sealed, found {len(hits)}")
    return hits[0]


def _source_of(row_laws: str) -> str:
    """The law-set path a protocol row's laws description starts with (its first token)."""
    tok = row_laws.split()[0]
    return tok[:-len("/*.json")] if tok.endswith("/*.json") else tok


def sizes_data(root: Path) -> bytes:
    proto = load(Path(root) / PROTOCOL)
    rows = []
    for r in proto["sizes"]["rows"]:
        if r["id"] == "heldout":
            t = heldout(root)
            doc = next(iter(documents(t).values()))
            dia = diagram_path(t, doc)
            law_src = ((t.get("run") or {}).get("law_set"))
            ob = _obligations(law_src, doc, root, None if law_src else "I50")
            target = t["name"]
        else:
            doc, dia = r["document"], r["diagram"]
            ob = _obligations(_source_of(r["laws"]), doc, root, None)
            target = next(n for n in T.names(root) if doc in documents(T.load(n, root)).values())
        d = load(Path(root) / dia)
        cls = Counter(c["cls"] for c in d["carriers"])
        kinds = Counter(e["kind"] for e in d["edges"])
        rows.append({"id": r["id"], "target": target, "document": doc,
                     "document_sha256": sha256_file(Path(root) / doc), "diagram": dia,
                     "diagram_sha256": sha256_file(Path(root) / dia), "adapter": r["adapter"],
                     "V": len(d["carriers"]), "E": len(d["edges"]), "carriers_by_kind": dict(sorted(cls.items())),
                     "edges_by_kind": dict(sorted(kinds.items())), "obligations": ob})
    rep = {"sizes_version": SIZES_VERSION, "linearity": LINEARITY, "rows": rows,
           "doc": "BUILD_PLAN I49/I50 exit: obligation counts against |E| and |V| across the four diagrams of "
                  "spec/M4/lib/heldout_protocol.json sizes.rows (holon target sizes). |V| is the number of carriers and "
                  "|E| the number of edges of each row's diagram; obligations are the laws of the row's law set over "
                  "the row's document. No linearity claim is made."}
    return dumps(rep).encode()


def sizes(root: Path, check: bool) -> int:
    return _write_or_check("sizes", root, {SIZES: sizes_data(root)}, check)


# ------------------------------------------------------------------ gate
def _res(ok: bool, detail: str) -> dict:
    return {"passed": bool(ok), "detail": detail}


def _validate(obj, schema_rel: str, root: Path) -> list[str]:
    from .schema import errors
    return errors(obj, load(Path(root) / schema_rel))


def _check_same(writes: dict[str, bytes], root: Path) -> list[str]:
    return [rel for rel, b in sorted(writes.items()) if not (Path(root) / rel).is_file()
            or (Path(root) / rel).read_bytes() != b]


def gate(name: str, root: Path, only: list[str] | None = None) -> int:
    t = T.load(name, root)
    checks: dict[str, dict] = {}
    order = I49_CHECKS if not only else ["GENV"] + [c for c in I49_CHECKS[1:] if c in only]
    from .gate import Gate
    g = Gate("M0", root)
    if g.genv():
        checks["GENV"] = _res(True, f"no unsafe Bun or env files; bend {g.bend_version} is the pinned version and the "
                                    "pinned checker fingerprint")
        skip = None
    else:
        checks["GENV"] = _res(False, g.checks["GENV"]["detail"])
        skip = g.genv_skip
    for c in order[1:]:
        if skip:
            checks[c] = _res(False, skip)
            continue
        try:
            checks[c] = getattr(sys.modules[__name__], f"_check_{c.lower()}")(t, root)
        except (TargetFailure, T.TargetError, OSError, ValueError, KeyError) as e:
            checks[c] = _res(False, f"{type(e).__name__}: {e}")
        except Exception as e:  # noqa: BLE001  (a crash of a check is a failure of that check, never a pass)
            checks[c] = _res(False, f"crashed: {type(e).__name__}: {e}")
    passed = all(v["passed"] for v in checks.values())
    rep = {"target": name, "passed": passed, "checks": checks, "partial": bool(only),
           "doc": "holon target gate (I49; spec/M4/lib/heldout_protocol.json gate.checks)"}
    out = Path(root) / "results" / "targets" / name / "gate_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(rep, indent=2) + "\n"    # check order kept
    out.write_text(text, encoding="utf-8")
    for c, v in checks.items():
        print(f"  {c}: {'PASS' if v['passed'] else 'FAIL'}  {v['detail'][:300]}")
    print(f"holon target gate: {name}: {'PASSED' if passed else 'FAILED'} ({out.relative_to(root)})")
    return 0 if passed else 1


def _check_x1(t: dict, root: Path) -> dict:
    co = checkout(t, root)
    head = subprocess.run(["git", "-C", str(co), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    pin = t["upstream"]["pinned_commit"]
    if head != pin:
        return _res(False, f"the checkout's HEAD is {head or 'unknown'}, not the pinned commit {pin}")
    with tempfile.TemporaryDirectory(prefix="holon-target-x1-") as td:
        out = Path(td)
        _run_commands(t, root, co, out)
        writes = {}
        for fname, rel in documents(t).items():
            if not (out / fname).is_file():
                return _res(False, f"the extraction wrote no {fname}")
            b = (out / fname).read_bytes()
            writes[rel] = b
            doc = json.loads(b.decode("utf-8"))
            if (doc.get("extraction") or {}).get("frontend") == "solidity" and rel.startswith(own_prefix(t)):
                writes[extraction_report_path(t)] = dumps(dependency_report(t, rel, doc, co, root)).encode()
    bad = _check_same(writes, root)
    if bad:
        return _res(False, f"a fresh extraction at {pin[:12]} differs from the committed {', '.join(bad)}")
    return _res(True, f"the checkout is at {pin[:12]}; a fresh extraction reproduces {', '.join(sorted(writes))} "
                      "byte for byte")


def _check_x2(t: dict, root: Path) -> dict:
    from . import frontends
    docs = documents(t)
    fdir = Path(root) / own_prefix(t) / "facts"
    have = sorted(p.relative_to(root).as_posix() for p in fdir.rglob("*") if p.is_file()) if fdir.is_dir() else []
    want = sorted(r for r in docs.values() if r.startswith(own_prefix(t) + "facts/"))
    if have != want:
        return _res(False, f"{own_prefix(t)}facts/ holds {have}, not exactly the extracted documents {want}")
    sides = {sp.relative_to(root).as_posix() for sp in sidecars(t, root)}
    for rel in docs.values():
        d = load(Path(root) / rel)
        ex = d.get("extraction") or {}
        if d.get("facts_version") != "holon-facts/0.3":
            return _res(False, f"{rel} is not a holon-facts/0.3 extracted document")
        if frontends._frontend(ex.get("frontend") or "") is None:
            return _res(False, f"{rel}: extraction.frontend {ex.get('frontend')!r} is not a HOLON frontend")
        if ex.get("sidecar") not in sides:
            return _res(False, f"{rel}: extraction.sidecar {ex.get('sidecar')!r} is not the target's {sorted(sides)}")
        if "hand_written" in json.dumps(d):
            return _res(False, f"{rel} carries a hand_written waiver")
    tdir = Path(root) / "targets" / t["name"]
    allowed = {"target.json"} | {Path(s).name for s in sides}
    extra = sorted(p.relative_to(tdir).as_posix() for p in tdir.rglob("*") if p.is_file()
                   and p.relative_to(tdir).as_posix() not in allowed
                   and not p.relative_to(tdir).as_posix().startswith("laws/"))
    if extra:
        return _res(False, f"targets/{t['name']}/ holds files other than target.json and the scope sidecar: {extra}")
    return _res(True, f"{len(docs)} document(s), each extracted by a HOLON frontend under the target's sidecar; no "
                      "hand-written fact and no waiver")


def _check_g8(t: dict, root: Path) -> dict:
    data = coverage_data(t, root)
    p = Path(root) / coverage_path(t)
    if not p.is_file() or p.read_bytes() != data:
        return _res(False, f"{coverage_path(t)} differs from a fresh coverage walk")
    rep = json.loads(data)
    if rep["unaccounted"]:
        return _res(False, f"{rep['unaccounted']} statement(s) unaccounted")
    for d in rep["documents"]:
        for item in d["debt"]:
            if not str(item.get("kind", "")).strip() or not str(item.get("detail", "")).strip():
                return _res(False, f"{d['document']}: a debt entry without a kind or a reason: {item}")
    n = sum(len(d["debt"]) for d in rep["documents"])
    return _res(True, f"{coverage_path(t)} regenerates; 0 unaccounted; {n} debt entries, each with a kind and a reason")


def _check_d1(t: dict, root: Path) -> dict:
    writes = diagram_writes(t, root)
    bad = _check_same(writes, root)
    if bad:
        return _res(False, f"diagram(s) differ from a fresh build: {bad}")
    for rel, b in writes.items():
        d = json.loads(b)
        if d.get("diagram_version") == "holon-diagram-transitions/0.1":
            errs = _validate(d, DIAGRAM_SCHEMA, root)
            if errs:
                return _res(False, f"{rel}: {errs[:3]}")
    return _res(True, f"{len(writes)} diagram(s) regenerate byte for byte and validate")


def _check_s1(t: dict, root: Path) -> dict:
    data = sizes_data(root)
    p = Path(root) / SIZES
    if not p.is_file() or p.read_bytes() != data:
        return _res(False, f"{SIZES} differs from a fresh run")
    errs = _validate(json.loads(data), SIZES_SCHEMA, root)
    if errs:
        return _res(False, f"{SIZES}: {errs[:3]}")
    return _res(True, f"{SIZES} regenerates byte for byte and validates")


# ------------------------------------------------------------------ CLI
def main(command: str, argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog=f"holon target {command}")
    ap.add_argument("--target")
    ap.add_argument("--root")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--checks")
    a = ap.parse_args(argv)
    root = Path(a.root or ROOT).resolve()
    if command != "sizes" and not a.target:
        ap.error("--target is required")
    try:
        if command == "extract":
            return extract(a.target, root, a.check)
        if command == "coverage":
            return coverage(a.target, root, a.check)
        if command == "diagram":
            return diagram(a.target, root, a.check)
        if command == "sizes":
            return sizes(root, a.check)
        if command == "gate":
            return gate(a.target, root, [x for x in (a.checks or "").split(",") if x] or None)
    except (TargetFailure, T.TargetError) as e:
        print(f"holon target {command}: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        from .frontends import ExtractionError, Refused
        if isinstance(e, Refused):
            print(f"holon target {command}: refused: {e}", file=sys.stderr)
            return 2
        if isinstance(e, ExtractionError):
            print(f"holon target {command}: extraction error: {e}", file=sys.stderr)
            return 3
        raise
    raise SystemExit(f"unknown command {command}")
