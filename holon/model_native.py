"""The native C model (whitepaper §8.7: "the model compiles to a C library"; BUILD_PLAN I16).

`NativeModel.build(facts_path)` writes the model and its generated driver (holon.gen.cdriver) under
`holon.bend.build_dir()/native/`, emits C with the pinned Bend (`bend driver.bend -o driver.c`) and
builds that C source with clang, with the flags Bend's own native build uses. `run_jobs` follows the
contract and value encoding of `holon.model_eval.CompiledModel.run_jobs`: the jobs become the driver's
instruction stream, the binary evaluates them on the compiled model, and Python decodes the values it
writes. `run_jobs` executes only the built binary (no node, no bend).

A failure of bend or of the C compiler raises NativeBuildError carrying the captured output, with the
build directory replaced by "<build>". `holon native` records the outcome in results/M2/native.json:
status "native" with agreement counts over every refuter candidate, or status "fallback" with the
captured error (BUILD_PLAN I16 risks: then the .mjs model stays the engine).

    python -m holon native --milestone M0 [--out PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import bend
from . import facts as F
from .gen import cdriver as D
from .gen import model as G

ROOT = Path(__file__).resolve().parents[1]
NATIVE_JSON = ROOT / "results" / "M2" / "native.json"
EMIT_C = ["bend", D.DRIVER, "-o", "driver.c"]           # as recorded (the checker runs by absolute path)
CFLAGS = ["-std=c11", "-O3", "driver.c", "-lpthread", "-lm", "-o", "driver"]   # bend2 main.ts cli_build (CPU)
CHUNK = 512


class NativeBuildError(RuntimeError):
    """bend or the C compiler failed; str() holds the captured output with the build dir as <build>."""

    def __init__(self, command: str, exit_code: int | None, output: str):
        self.command, self.exit_code, self.output = command, exit_code, output
        super().__init__(f"{command} failed (exit {exit_code}):\n{output}")


class NativeEvalError(RuntimeError):
    pass


def normalize(text: str, build: Path) -> str:
    out = text
    for p in sorted({str(build), str(Path(build).resolve())}, key=len, reverse=True):
        out = out.replace(p, "<build>")
    return out


def compiler() -> str | None:
    """The C compiler bend2 would pick for a CPU build: $CC, else clang (first line of --version)."""
    cc = os.environ.get("CC") or shutil.which("clang")
    if not cc:
        return None
    try:
        p = subprocess.run([cc, "--version"], capture_output=True, text=True, timeout=60)
    except OSError:
        return None
    first = (p.stdout.strip().splitlines() or [""])[0]
    return first if p.returncode == 0 and first else None


class NativeModel:
    def __init__(self, binary: Path, c_source: Path, facts: dict, directory: Path):
        self.binary, self.c_source, self.facts, self.directory = Path(binary), Path(c_source), facts, Path(directory)
        self.fns = {f: i for i, f in enumerate(D.functions(facts))}
        self.flds = {f: i for i, f in enumerate(D.fields(facts))}
        self.cells = G.cell_names(facts)

    @property
    def c_source_sha256(self) -> str:
        return hashlib.sha256(self.c_source.read_bytes()).hexdigest()

    @classmethod
    def build(cls, facts_path, cfg: dict | None = None) -> "NativeModel":
        facts_path = Path(facts_path)
        facts = F.load(facts_path)
        files = D.generate(facts_path)
        digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:16]
        d = bend.build_dir(ROOT) / "native" / digest
        d.mkdir(parents=True, exist_ok=True)
        for name, text in sorted(files.items()):
            p = d / name
            if not p.exists() or p.read_text() != text:
                p.write_text(text)
        for stale in ("driver.c", "driver"):
            (d / stale).unlink(missing_ok=True)
        r = bend.run([D.DRIVER, "-o", "driver.c"], cwd=d, cfg=cfg, timeout=1800)
        if r.code != 0 or not (d / "driver.c").exists():
            raise NativeBuildError(" ".join(EMIT_C), r.code, normalize(r.out, d).strip())
        cc = os.environ.get("CC") or shutil.which("clang")
        if not cc:
            raise NativeBuildError("clang " + " ".join(CFLAGS), None, "no C compiler: neither $CC nor clang on PATH")
        try:
            p = subprocess.run([cc, *CFLAGS], cwd=d, capture_output=True, text=True, timeout=3600)
            code, out = p.returncode, p.stdout + p.stderr
        except (OSError, subprocess.SubprocessError) as e:
            code, out = None, f"{type(e).__name__}: {e}"
        if code != 0 or not (d / "driver").exists():
            raise NativeBuildError(f"{Path(cc).name} " + " ".join(CFLAGS), code, normalize(out, d).strip())
        return cls(d / "driver", d / "driver.c", facts, d)

    # ------------------------------------------------------------ jobs -> instruction stream
    def _lit(self, data: list[int]) -> list[int]:
        out = []
        for b in data:
            if not (isinstance(b, int) and 0 <= b <= 255):
                raise NativeEvalError(f"a literal byte must be 0..255, got {b!r}")
            out += [D.OP_BYTE, b]
        return out

    def _value(self, v) -> list[int]:
        if isinstance(v, dict) and "$hdr" in v:
            cells = v["$hdr"]
            if set(cells) != set(self.cells):
                raise NativeEvalError("a header value must name every cell")
            return self._lit([cells[c] for c in self.cells]) + [D.OP_HDR, 0]
        if isinstance(v, list):
            return self._lit(v) + [D.OP_BYTES, 0]
        raise NativeEvalError(f"the native driver takes Header and Bytes inputs only, got {v!r:.80}")

    def _term(self, t: dict, slots: dict) -> list[int]:
        if "var" in t:
            if t["var"] not in slots:
                raise NativeEvalError(f"unbound variable {t['var']}")
            return [D.OP_LOAD, slots[t["var"]]]
        if "bytes" in t:
            return self._lit(list(bytes.fromhex(t["bytes"][2:]))) + [D.OP_BYTES, 0]
        if "field" in t:
            return self._term(t["of"], slots) + [D.OP_FIELD, self.flds.get(t["field"], 255)]
        if "call" in t:
            if len(t.get("args", [])) != 1:
                raise NativeEvalError(f"{t['call']}: the fact functions take one argument")
            return self._term(t["args"][0], slots) + [D.OP_CALL, self.fns.get(t["call"], 255)]
        if "some" in t:
            return self._term(t["some"], slots) + [D.OP_SOME, 0]
        raise NativeEvalError(f"unknown term {t!r:.80}")

    def program(self, jobs: list[dict]) -> bytes:
        out: list[int] = []
        for job in jobs:
            names = sorted(job["env"])
            if len(names) > 255:
                raise NativeEvalError("more than 255 variables")
            slots = {n: i for i, n in enumerate(names)}
            for n in names:
                out += self._value(job["env"][n]) + [D.OP_STORE, 0]
            for t in job["terms"]:
                out += self._term(t, slots) + [D.OP_EMIT, 0]
            out += [D.OP_END, 0]
        return bytes(out)

    # ------------------------------------------------------------ output -> values
    @staticmethod
    def _cells(buf: bytes, i: int) -> tuple[list[int], int]:
        xs = []
        while True:
            b = buf[i]
            if b == D.EOL:
                return xs, i + 1
            if b == D.ESC:
                xs.append(int.from_bytes(buf[i + 1:i + 5], "big"))
                i += 5
            else:
                xs.append(b)
                i += 1

    def _fields(self, buf: bytes, i: int) -> tuple[list, int]:
        fs = []
        while buf[i] == D.T_ITEM:
            f, i = self._cells(buf, i + 1)
            fs.append(f)
        if buf[i] != D.T_CLOSE:
            raise NativeEvalError(f"malformed field list at byte {i}")
        return fs, i + 1

    def decode(self, buf: bytes, shape: list[int]) -> list[list]:
        """The values of each job (shape[k] = number of terms of job k), in eval.mjs's encoding."""
        res, i = [], 0
        for n in shape:
            vals = []
            while buf[i] != D.T_END:
                tag = buf[i]
                if tag == D.T_BYTES:
                    v, i = self._cells(buf, i + 1)
                elif tag == D.T_BOOL:
                    v, i = buf[i + 1] == 1, i + 2
                elif tag == D.T_FIELDS:
                    v, i = self._fields(buf, i + 1)
                elif tag == D.T_NONE:
                    v, i = None, i + 1
                elif tag == D.T_SOME:
                    fs, i = self._fields(buf, i + 1)
                    v = {"$some": fs}
                elif tag == D.T_HDR:
                    _, i = self._cells(buf, i + 1)
                    v = {"error": "native: a Header value has no output encoding (eval.mjs cannot decode Hdr either)"}
                elif tag == D.T_ERR:
                    v, i = {"error": "native: ill-shaped argument, unknown function or field"}, i + 1
                else:
                    raise NativeEvalError(f"unknown output tag {tag} at byte {i}")
                vals.append(v)
            i += 1
            if len(vals) != n:
                raise NativeEvalError(f"a job produced {len(vals)} values for {n} terms")
            res.append(vals)
        if i != len(buf):
            raise NativeEvalError(f"{len(buf) - i} trailing output bytes")
        return res

    def run_jobs(self, jobs: list[dict], timeout: int = 3600) -> list[list]:
        out: list[list] = []
        for k in range(0, len(jobs), CHUNK):
            chunk = jobs[k:k + CHUNK]
            tmp = Path(tempfile.mkdtemp(prefix="holon-native-run-"))
            try:
                (tmp / "jobs.bin").write_bytes(self.program(chunk))
                p = subprocess.run([str(self.binary), str(tmp / "jobs.bin"), str(tmp / "out.bin")], cwd=tmp,
                                   capture_output=True, text=True, timeout=timeout)
                if p.returncode != 0 or not (tmp / "out.bin").exists():
                    raise NativeEvalError(f"native evaluation failed (exit {p.returncode}): {(p.stdout + p.stderr)[-2000:]}")
                out += self.decode((tmp / "out.bin").read_bytes(), [len(j["terms"]) for j in chunk])
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        return out


# ---------------------------------------------------------------- results/M2/native.json
def refuter_jobs(facts: dict, laws: list[dict]) -> list[tuple[str, dict]]:
    """(law id, job) for every candidate holon.refute.candidates yields for every law, every claim term
    (both sides and every subterm) as holon.refute evaluates them: the whole candidate space."""
    from . import refute as R
    from .gen import laws as LG
    from .model_eval import value_in
    out = []
    for law in laws:
        types = LG.binder_types(law)
        a, b = law["statement"]["claim"]["eq"]
        terms = [a, b] + [x for side in (a, b) for x in R.subterms(side)]
        pins = LG.collect_pins(law, facts)
        for _, env in R.candidates(law, facts, pins):
            out.append((law["law_id"], {"terms": terms, "env": {v: value_in(types[v], env[v], facts) for v in types}}))
    return out


def _norm(vals: list) -> list:
    return [{"error": True} if isinstance(v, dict) and "error" in v else v for v in vals]


def record(milestone: str = "M0", root: Path = ROOT) -> dict:
    """The native.json record: build natively; on success compare with .mjs on every refuter candidate."""
    from . import ir
    from .model_eval import CompiledModel
    reg = ir.load_registry(milestone, root)
    facts_path = Path(root) / reg.get("facts", "facts/morph_header.json")
    mjs = CompiledModel.build(facts_path)
    laws = sorted(ir.load_laws_any(milestone, root), key=lambda l: l["law_id"])
    jobs = refuter_jobs(mjs.facts, laws)
    try:
        nat = NativeModel.build(facts_path)
    except NativeBuildError as e:
        return {"milestone": milestone, "status": "fallback", "reason": e.output, "command": e.command,
                "exit_code": e.exit_code if isinstance(e.exit_code, int) else -1,
                "bend_version": bend.version(), "engine": "mjs",
                "note": "the native C build failed, so the .mjs model stays the engine (BUILD_PLAN I16 fallback); "
                        "every refinement record runs on .mjs. "
                        + ("The failure and a minimal reproduction are in bend/notes/c_probe/RESULT.json (arity_limit)"
                           if "arity over" in (e.output or "") else "See reason for the captured build error"),
                "driver_on_bend_lane": driver_on_bend_lane(facts_path, mjs, jobs, len(laws))}
    a = mjs.run_jobs([j for _, j in jobs])
    b = nat.run_jobs([j for _, j in jobs])
    agree = sum(1 for x, y in zip(a, b) if _norm(x) == _norm(y))
    return {"milestone": milestone, "status": "native", "c_source_sha256": nat.c_source_sha256,
            "compiler": compiler() or "unknown", "bend_version": bend.version(), "laws": len(laws),
            "candidates": len(jobs), "agree": agree, "disagree": len(jobs) - agree}


def driver_on_bend_lane(facts_path: Path, mjs, jobs: list[tuple[str, dict]], n_laws: int) -> dict:
    """Not a native engine: the same generated driver run by `bend driver.bend JOBS OUT` (Bend checks it,
    then runs main on its own JavaScript lane), on every refuter candidate, compared with .mjs. It tells a
    driver defect apart from a C backend limit when the native build fails."""
    files = D.generate(facts_path)
    d = Path(tempfile.mkdtemp(prefix="holon-native-lane-"))
    try:
        for name, text in files.items():
            (d / name).write_text(text)
        nat = NativeModel(d / "driver", d / "driver.c", mjs.facts, d)
        (d / "jobs.bin").write_bytes(nat.program([j for _, j in jobs]))
        r = bend.run([D.DRIVER, "jobs.bin", "out.bin"], cwd=d, timeout=3600)
        if r.code != 0 or not (d / "out.bin").exists():
            return {"engine": "bend driver.bend JOBS OUT (not native)", "ran": False,
                    "output": normalize(r.out, d).strip()[-2000:]}
        b = nat.decode((d / "out.bin").read_bytes(), [len(j["terms"]) for _, j in jobs])
    finally:
        shutil.rmtree(d, ignore_errors=True)
    a = mjs.run_jobs([j for _, j in jobs])
    agree = sum(1 for x, y in zip(a, b) if _norm(x) == _norm(y))
    return {"engine": "bend driver.bend JOBS OUT: Bend's own JavaScript lane, not native", "ran": True,
            "laws": n_laws, "candidates": len(jobs), "agree": agree, "disagree": len(jobs) - agree}


def write_record(rec: dict, out: Path = NATIVE_JSON) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
    return out


def load_record(root: Path = ROOT) -> dict | None:
    p = Path(root) / "results" / "M2" / "native.json"
    return json.loads(p.read_text()) if p.exists() else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon native")
    ap.add_argument("--milestone", default="M0")
    ap.add_argument("--out", help="output path (default: results/M2/native.json)")
    a = ap.parse_args(argv)
    rec = record(a.milestone)
    p = write_record(rec, Path(a.out) if a.out else NATIVE_JSON)
    print(json.dumps(rec, indent=2, sort_keys=True))
    print(f"wrote {p}")
    return 0 if rec["status"] == "native" and rec["disagree"] == 0 else 1
