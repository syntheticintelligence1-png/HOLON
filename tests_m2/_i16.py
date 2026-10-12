"""I16 helpers: the instruments fixed at the I16 prereg (BUILD_PLAN §0.1, "instruments are inputs").

Nothing here imports holon/. The tests use these helpers to decide what I16's outputs must say,
independently of the code that writes them:

- `ref_output` evaluates an edge's model semantics with the frozen reference interpreter
  tests/reference/ref_model.py (the test oracle; holon/ never imports it);
- `required_boundary` is the sort-boundary rule of whitepaper §8.7 ("0, 1, max, max - 1, and every
  sentinel constant"), computed from facts/morph_header.json;
- `m0_witnesses` lists every REFUTED M0 witness of an edge's input sort that lies in its domain;
- `expected_class` is the mechanical disagreement classification (the rules in the test_refinement.py
  docstring), written out here so that "0 unexplained" is decided by an instrument fixed at the prereg;
- `run_go_instrument` runs tests_m2/fixtures/refinement/holon_prereg_instrument.go.txt, a Go test
  written at this prereg, on the real morph common/batch at the pinned commit. It is independent of
  the I16 harness (replay/M2/go/holon_codec_test.go) and gives the real outputs of the four
  Go-implemented functions, so the tests can check the refinement records' real-output digests;
- `run_sol_instrument` does the same for the two Solidity-implemented functions (enc_sol, ok_sol) with
  tests_m2/fixtures/refinement/HolonPreregInstrument.t.sol.txt, a Foundry test written at this prereg,
  on the real morph contracts/ at the pinned commit with the pinned forge, solc and dependencies. It is
  independent of the I16 harness (replay/M2/solidity/HolonCodec.t.sol).

Canonical forms (shared with holon: the contract in tests_m2/test_refinement.py):
  inputs   Header: {field: "0x" + lowercase hex of exactly the field's width}, all 12 fields;
           Bytes: "0x" + lowercase hex
  outputs  ref_model.value_to_json: Bytes "0x..", Bool true/false, Maybe<Fields> null | ["0x..", ..]
  digest   sha256 hex of canonical_json(list in corpus order)
  canonical_json(x) = json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False) as UTF-8
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from tests._util import config
from tests.reference import ref_model as RM
from tests_m2._m2 import ROOT, laws, load_json, records

FACTS = ROOT / "facts" / "morph_header.json"
REF_DIR = ROOT / "results" / "M2" / "refinement"
CROSS = ROOT / "results" / "M2" / "cross_edge.json"
NATIVE = ROOT / "results" / "M2" / "native.json"
DISAGREEMENTS = ROOT / "spec" / "M2" / "disagreements.json"
DIAGRAM = ROOT / "gen" / "M2" / "diagram" / "morph_header.json"
FIX = ROOT / "tests_m2" / "fixtures" / "refinement"
INSTRUMENT = FIX / "holon_prereg_instrument.go.txt"
SOL_INSTRUMENT = FIX / "HolonPreregInstrument.t.sol.txt"
C_PROBE = ROOT / "bend" / "notes" / "c_probe"

CODEC_EDGES = ("dec_go", "enc_go_v0", "enc_go_v1", "enc_sol")    # the 4 CODEC edges of the I11 M0 diagram
DOMAIN_EDGES = ("ok_go", "ok_sol")                               # the decoder domains (Bytes carrier domains)
EDGES = CODEC_EDGES + DOMAIN_EDGES
GO_EDGES = ("dec_go", "enc_go_v0", "enc_go_v1", "ok_go")
SOL_EDGES = ("enc_sol", "ok_sol")
HARNESS = {"go": "replay/M2/go/holon_codec_test.go", "solidity": "replay/M2/solidity/HolonCodec.t.sol"}
GRAMMAR_SAMPLES = 2000
SOURCES = ("grammar", "boundary", "witness")
CLASSES = ("extraction_defect", "real_defect", "oracle_mismatch", "unexplained")
PIN_KEYS = ("forge_sha256", "solc_sha256", "sol_deps_sha256", "go_version")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")

# Escape hatches (BEND_PRIMER §3.2), the same textual rules G3 applies, written out here independently.
ESCAPES = {
    "unsafe": re.compile(r"@unsafe"),
    "unsafe_sugar": re.compile(r"^\s*def\s+[\w.]+\?\s*\(", re.M),
    "hole": re.compile(r"\?[A-Za-z_][\w]*"),
    "foreign_import": re.compile(r"^\s*import\s+\"", re.M),
}


def escape_hatches(text: str) -> list[str]:
    return sorted(k for k, rx in ESCAPES.items() if rx.search(text))


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(obj) -> str:
    return hashlib.sha256(canonical_json(obj)).hexdigest()


def facts() -> dict:
    return RM.load_facts(FACTS)


def input_type(edge: str) -> str:
    """'Header' for the encoders, 'Bytes' for the decoder and the domain predicates (from the facts)."""
    return facts()["functions"][edge]["from"]


def edge_record(edge: str) -> dict:
    return load_json(REF_DIR / f"{edge}.json")


def ref_arg(fx: dict, edge: str, x):
    return RM.header_from_json(fx, x) if input_type(edge) == "Header" else RM.unhex(x)


def ref_output(fx: dict, edge: str, x):
    """The edge's model semantics on input x, in canonical JSON. Raises RM.DomainError outside the domain."""
    return RM.value_to_json(RM.call(fx, edge, [ref_arg(fx, edge, x)]))


def in_domain(fx: dict, edge: str, x) -> bool:
    try:
        ref_output(fx, edge, x)
    except RM.DomainError:
        return False
    return True


def well_formed(fx: dict, edge: str, x) -> bool:
    if input_type(edge) == "Header":
        w = RM.widths(fx)
        return (isinstance(x, dict) and set(x) == set(w)
                and all(isinstance(v, str) and re.fullmatch(r"0x(?:[0-9a-f]{2})*", v) and len(v) == 2 + 2 * w[k]
                        for k, v in x.items()))
    return isinstance(x, str) and re.fullmatch(r"0x(?:[0-9a-f]{2})*", x) is not None


# ------------------------------------------------------------------ sort-boundary values (§8.7)
def version_sentinels(fx: dict) -> set[int]:
    """Every version constant the facts compare against: rule version_in lists, domain version_le,
    and the version_ge conditions of ops, getters and the view."""
    ks: set[int] = set()
    for f in fx["functions"].values():
        for r in f.get("rules", []):
            if isinstance(r.get("if"), dict):
                ks.update(r["if"].get("version_in", []))
        if isinstance(f.get("domain"), dict) and "version_le" in f["domain"]:
            ks.add(f["domain"]["version_le"])
        conds = [o.get("when") for o in f.get("ops", [])] + [g.get("when") for g in f.get("getters", [])]
        conds += list(f.get("when", {}).values()) if isinstance(f.get("when"), dict) else []
        for w in conds:
            if isinstance(w, dict) and "version_ge" in w:
                ks.add(w["version_ge"])
    return ks


def length_sentinels(fx: dict) -> set[int]:
    """Every byte-length constant of the facts: rule len_eq / len_ge, encoder length, length_by_version."""
    ks: set[int] = set()
    for f in fx["functions"].values():
        for r in f.get("rules", []):
            if isinstance(r.get("then"), dict):
                ks.update(v for k, v in r["then"].items() if k in ("len_eq", "len_ge"))
        if "length" in f:
            ks.add(f["length"])
        ks.update(f.get("length_by_version", {}).values())
    return ks


def required_boundary(edge: str) -> list[tuple[str, object]]:
    """(description, predicate over one corpus input) pairs; each must hold for some boundary input.

    Header edges: every field of width w at 0, 1, max = 2^(8w) - 1 and max - 1, plus the version field
    at every version sentinel; a value no header in the edge's domain can carry (enc_sol: version > 2)
    is not required. Bytes edges: the lengths 0, 1 and every length sentinel; the first byte at 0, 1,
    254, 255 and every version sentinel (the Bytes sort has no maximum length)."""
    fx = facts()
    out: list[tuple[str, object]] = []
    if input_type(edge) == "Header":
        w = RM.widths(fx)
        for name, width in w.items():
            mx = (1 << (8 * width)) - 1
            vals = {0, 1, mx, mx - 1} | (version_sentinels(fx) if name == "version" else set())
            for v in sorted(vals):
                hv = "0x" + v.to_bytes(width, "big").hex()
                probe = {n: "0x" + bytes(k).hex() for n, k in w.items()}
                probe[name] = hv
                if not in_domain(fx, edge, probe):
                    continue
                out.append((f"{name}={hv}", lambda x, name=name, hv=hv: x[name] == hv))
        return out
    for n in sorted({0, 1} | length_sentinels(fx)):
        out.append((f"len={n}", lambda x, n=n: len(RM.unhex(x)) == n))
    for v in sorted({0, 1, 254, 255} | version_sentinels(fx)):
        out.append((f"byte0={v}", lambda x, v=v: len(RM.unhex(x)) >= 1 and RM.unhex(x)[0] == v))
    return out


def m0_witnesses(edge: str) -> list:
    """Every binder value of every REFUTED M0 record whose binder sort is the edge's input sort and
    which lies in the edge's domain, in law order, without duplicates."""
    fx, t, out = facts(), input_type(edge), []
    recs = records("M0")
    for lid, law in laws("M0").items():
        rec = recs.get(lid)
        if not rec or rec["status"] != "REFUTED":
            continue
        for b in law["statement"]["forall"]:
            if b["type"] == t:
                x = rec["witness"][b["name"]]
                if in_domain(fx, edge, x) and x not in out:
                    out.append(x)
    return out


def claim_calls(law: dict) -> set[str]:
    return {t["call"] for t in law["statement"]["claim"]["eq"] if "call" in t}


def satisfies_premises(law: dict, x) -> bool:
    """M0 premises are field pins `field(var) == bytes`; any other premise form fails loudly."""
    for p in law["statement"]["assume"]:
        a, b = p["eq"]
        if not ("field" in a and "bytes" in b and "var" in a["of"]):
            raise AssertionError(f"{law['law_id']}: premise form not handled by the test: {p}")
        if x[a["field"]] != b["bytes"]:
            return False
    return True


# ------------------------------------------------------------------ mechanical disagreement classes
LINK_KINDS = {"extraction_defect": {"fix_commit", "rerun"}, "real_defect": {"law"}, "oracle_mismatch": {"hypothesis"}}


def _load(p: Path):
    try:
        return load_json(p)
    except (OSError, ValueError):
        return None


def _extraction_ok(entry: dict, links: dict, root: Path) -> bool:
    commit, rerun = links["fix_commit"], links["rerun"]
    if not (isinstance(commit, str) and HEX40.match(commit) and isinstance(rerun, str)):
        return False
    parts = rerun.split("/")
    if rerun.startswith("/") or "\\" in rerun or any(x in ("", ".", "..") for x in parts) \
            or parts[:3] != ["results", "M2", "refinement"] or len(parts) < 4:
        return False
    rec = _load(root / rerun)
    return (isinstance(rec, dict) and rec.get("edge") == entry.get("edge") and rec.get("disagreements") == 0
            and commit in (rec.get("fixes") or []))


def _real_ok(entry: dict, links: dict, root: Path) -> bool:
    m = re.fullmatch(r"(M[0-9]+)/(L_[A-Za-z0-9_]+)", links["law"]) if isinstance(links["law"], str) else None
    if not m:
        return False
    ms, lid = m.groups()
    rec, rep = _load(root / "results" / ms / f"{lid}.json"), _load(root / "replay" / ms / "report.json")
    if not (isinstance(rec, dict) and isinstance(rep, dict)):
        return False
    if rec.get("status") != "REFUTED" or (rec.get("replay") or {}).get("status") != "passed" \
            or entry.get("edge") not in (rec.get("cone") or []):
        return False
    if (rep.get("witness_sha256") or {}).get(lid) != sha256_json(rec.get("witness")):
        return False
    lr = (rep.get("laws") or {}).get(lid)
    sides = lr.get("sides") if isinstance(lr, dict) and "sides" in lr else lr
    return (isinstance(sides, dict) and bool(sides)
            and all(isinstance(v, dict) and v.get("obstruction_observed") is True for v in sides.values()))


def _oracle_ok(entry: dict, links: dict, root: Path) -> bool:
    hyp = _load(root / "results" / "M2" / "hypotheses.json")
    h = hyp.get(links["hypothesis"]) if isinstance(hyp, dict) and isinstance(links["hypothesis"], str) else None
    return isinstance(h, dict) and h.get("status") == "failed"


def expected_class(entry: dict, root: Path = ROOT) -> str:
    """The class an entry's links give; its label (entry["class"]) is never read. links must hold exactly
    the keys of one kind; anything else is unexplained."""
    links = entry.get("links")
    if not isinstance(links, dict):
        return "unexplained"
    for cls, ok in (("extraction_defect", _extraction_ok), ("real_defect", _real_ok), ("oracle_mismatch", _oracle_ok)):
        if set(links) == LINK_KINDS[cls]:
            return cls if ok(entry, links, Path(root)) else "unexplained"
    return "unexplained"


# ------------------------------------------------------------------ the independent Go instrument
def morph_checkout() -> Path:
    """The pinned morph checkout (config replay.morph), at the facts' target commit. Pinned, so a
    missing checkout is a failure, never a skip."""
    cfg = config().get("replay") or {}
    if not cfg.get("morph"):
        raise AssertionError("config/holon.json replay.morph is not pinned")
    morph = Path(cfg["morph"])
    if not (morph / "common" / "batch").is_dir():
        raise AssertionError(f"pinned morph checkout {morph} is missing common/batch")
    head = subprocess.run(["git", "-C", str(morph), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    commit = facts()["target"]["commit"]
    if not (HEX40.match(head) and head.startswith(commit)):
        raise AssertionError(f"{morph} is at {head!r}, not at the facts' commit {commit}")
    # the instruments copy these trees whole: an uncommitted, untracked or ignored file would run too
    dirty = subprocess.run(["git", "-C", str(morph), "status", "--porcelain", "--untracked-files=all",
                            "--ignored=matching", "--", "bindings", "common", "contracts"],
                           capture_output=True, text=True, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if dirty.returncode != 0 or dirty.stdout.strip():
        raise AssertionError(f"{morph} has uncommitted changes in the instrumented trees: {dirty.stdout.strip()[:500]}")
    return morph


def run_go_instrument(inputs: dict[str, list]) -> dict[str, list]:
    """Real Go outputs for each edge in GO_EDGES, from the prereg instrument, on the given inputs."""
    cfg = config().get("replay") or {}
    gv = subprocess.run(["go", "version"], capture_output=True, text=True).stdout.strip()
    if gv != cfg.get("go_version"):
        raise AssertionError(f"`go version` is {gv!r}, pinned {cfg.get('go_version')!r}")
    morph = morph_checkout()
    ws = Path(tempfile.mkdtemp(prefix="holon-i16-go-"))
    try:
        for d in ("bindings", "common"):
            shutil.copytree(morph / d, ws / d, symlinks=True)
        (ws / "go.work").write_text("go 1.24.0\n\nuse (\n\t./bindings\n\t./common\n)\n")
        shutil.copy(INSTRUMENT, ws / "common" / "batch" / "holon_prereg_instrument_test.go")
        doc = {"headers": {e: xs for e, xs in inputs.items() if input_type(e) == "Header"},
               "bytes": {e: xs for e, xs in inputs.items() if input_type(e) == "Bytes"}}
        (ws / "in.json").write_text(json.dumps(doc))
        env = {**os.environ, "HOLON_PREREG_IN": str(ws / "in.json"), "HOLON_PREREG_OUT": str(ws / "out.json")}
        p = subprocess.run(["go", "test", "./batch", "-run", "^TestHolonPreregInstrument$", "-count=1", "-v"],
                           cwd=ws / "common", env=env, capture_output=True, text=True, timeout=1500)
        if p.returncode != 0 or not (ws / "out.json").exists():
            raise AssertionError(f"prereg Go instrument failed (exit {p.returncode}): {(p.stdout + p.stderr)[-2000:]}")
        return json.loads((ws / "out.json").read_text())
    finally:
        shutil.rmtree(ws, ignore_errors=True)


# ------------------------------------------------------------------ the independent Solidity instrument
def file_sha256(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def tree_sha256(d: Path) -> str:
    """The definition behind config replay.sol_deps_sha256, written out here: sha256 over
    (relative path, file sha256) of every file under d in sorted order, skipping .git and npm's
    .package-lock.json."""
    h = hashlib.sha256()
    files = sorted(f for f in Path(d).rglob("*")
                   if f.is_file() and ".git" not in f.relative_to(d).parts and f.name != ".package-lock.json")
    for f in files:
        h.update(f"{f.relative_to(d).as_posix()}\0{file_sha256(f)}\n".encode())
    return h.hexdigest()


def header_concat(fx: dict, x: dict) -> str:
    """A Header input as the instrument reads it: its fields concatenated in facts types.Header.fields order."""
    return "0x" + "".join(x[f["name"]][2:] for f in RM.header_fields(fx))


def run_sol_instrument(inputs: dict[str, list]) -> dict[str, list]:
    """Real Solidity outputs for each edge in SOL_EDGES, from the prereg instrument, on the given inputs:
    enc_sol "0x.." (the header the build block writes), ok_sol true/false (_loadBatchHeader does not revert).
    The toolchain is pinned (config replay): a missing or different forge, solc or dependency tree is a
    failure, never a skip."""
    cfg = config().get("replay") or {}
    for name, pin in (("forge", "forge_sha256"), ("solc", "solc_sha256")):
        path = cfg.get(name)
        if not path or not Path(path).is_file():
            raise AssertionError(f"config/holon.json replay.{name} is not a file: {path!r}")
        if file_sha256(path) != cfg.get(pin):
            raise AssertionError(f"{path} does not match the pinned replay.{pin}")
    nm = Path(cfg.get("sol_deps") or "/nonexistent") / "node_modules"
    if not nm.is_dir() or tree_sha256(nm) != cfg.get("sol_deps_sha256"):
        raise AssertionError(f"{nm} does not match the pinned replay.sol_deps_sha256")
    morph = morph_checkout()
    fx = facts()
    proj = Path(tempfile.mkdtemp(prefix="holon-i16-sol-"))
    try:
        shutil.copytree(morph / "contracts" / "contracts", proj / "contracts")
        for d in ("mock", "test"):  # as replay_solidity: the repo's mocks and tests pull extra dependencies
            shutil.rmtree(proj / "contracts" / d, ignore_errors=True)
        for f in ("foundry.toml", "remappings.txt"):
            shutil.copy(morph / "contracts" / f, proj / f)
        shutil.copytree(nm, proj / "node_modules", symlinks=False, ignore=shutil.ignore_patterns(".git"))
        (proj / "test").mkdir()
        shutil.copy(SOL_INSTRUMENT, proj / "test" / "HolonPreregInstrument.t.sol")
        edges = [e for e in SOL_EDGES if e in inputs]
        lines = []
        for e in edges:
            lines.append(e)
            lines += [header_concat(fx, x) if e == "enc_sol" else x for x in inputs[e]]
        lines.append("end")
        (proj / "holon_prereg_in.txt").write_text("\n".join(lines) + "\n")
        env = {**os.environ, "HOLON_PREREG_IN": "holon_prereg_in.txt", "HOLON_PREREG_OUT": "holon_prereg_out.txt"}
        p = subprocess.run([cfg["forge"], "test", "--match-contract", "HolonPreregInstrument", "--offline",
                            "--use", cfg["solc"], "-vv"], cwd=proj, env=env, capture_output=True, text=True,
                           timeout=3000)
        out = proj / "holon_prereg_out.txt"
        if p.returncode != 0 or not out.exists():
            raise AssertionError(f"prereg Solidity instrument failed (exit {p.returncode}): {(p.stdout + p.stderr)[-2000:]}")
        got = out.read_text().splitlines()
        n = sum(len(inputs[e]) for e in edges)
        if len(got) != n + 1 or got[-1] != f"end {n}":
            raise AssertionError(f"prereg Solidity instrument wrote {len(got)} lines for {n} inputs: {got[-1:]}")
        res, i = {}, 0
        for e in edges:
            vals = got[i:i + len(inputs[e])]
            i += len(inputs[e])
            if e == "ok_sol":
                if not set(vals) <= {"true", "false"}:
                    raise AssertionError(f"ok_sol outputs must be true/false: {sorted(set(vals))[:5]}")
                res[e] = [v == "true" for v in vals]
            else:
                res[e] = vals
        return res
    finally:
        shutil.rmtree(proj, ignore_errors=True)
