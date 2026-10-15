"""The compiled M3 model as a step evaluator (I30; the contract is the docstring of tests_m3/test_sort_types.py, the
"Refinement of the typed model" section and R5): `bend <model>.bend -o <model>.mjs`, run by holon/js/eval3.mjs in one
node process. Python only moves values in and out; nothing is evaluated here.

  Evaluator(model_bend, doc_model)        the compiled model of one document (holon.machine.ExtractedModel)
  .run(action, state, args, env, kh=None, sh=None) -> Run   one run_<action> of the model, with the hash tables given
  .step(state, action, args, env) -> dict     holon.extracted_eval.step's interface (I20's A/B interface): the hash
                                              tables are the real keccak256 / sha256 of every key the run looks up
                                              (a fixpoint: a run that looks up a new key runs again with it)
  load_extracted(doc_path, source=None) / step(model, state, action, args, env)
        the --evaluator interface of holon.replay_fragments (holon fragments --evaluator <model>.bend)

The compiled module is cached under ~/.holon/cache/m3eval/<sha256 of the model text>/ (outside the repository).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .. import extracted_eval as EV
from ..keccak import keccak256

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "holon" / "js" / "eval3.mjs"
CALL_CODE = 4294967294
FUEL_CODE = 4294967295
MASK = (1 << 256) - 1


class EvalError(RuntimeError):
    pass


def cache_dir() -> Path:
    return Path(os.environ.get("HOLON_CACHE") or (Path.home() / ".holon" / "cache")) / "m3eval"


def h32(v: int) -> str:
    return "0x%064x" % (int(v) & MASK)


def _hex(b: bytes) -> str:
    return "0x" + bytes(b).hex()


def word(v) -> dict:
    return {"$w": "0x%064x" % (EV.to_int(v) & MASK)}


def byts(v) -> dict:
    return {"$b": _hex(EV.to_bytes(v) if not isinstance(v, (bytes, bytearray)) else bytes(v))}


_REC = re.compile(r"(?m)^type (\w+) is Data:\n  \1\{(.*)\}$")
_ENVF = re.compile(r"(?m)^# HEnv\.(\w+): (.*)$")


def records(text: str) -> dict:
    """{record name: [(field, Bend type)]} of every single-constructor type of a model text."""
    out = {}
    for name, body in _REC.findall(text):
        fs = []
        depth, cur = 0, ""
        for ch in body + ",":
            if ch == "," and depth == 0:
                if cur.strip():
                    f, _, ty = cur.strip().partition(":")
                    fs.append((f.strip(), ty.strip()))
                cur = ""
                continue
            depth += ch == "<"
            depth -= ch == ">"
            cur += ch
        out[name] = fs
    return out


def hashes_of(text: str) -> list[str]:
    """The hash tables a model text's steps take as parameters (its law's hash binders): keccak256, sha256."""
    sig = re.search(r"(?m)^def run_\w+\(\+st: HSt, \+ar: \w+, \+en: HEnv(.*)\) -> HOut:", text)
    hs = sig.group(1) if sig else ""
    return [h for h, n in (("keccak256", "+kh"), ("sha256", "+sh")) if n in hs]


@dataclass
class Run:
    out: dict
    kh: list
    sh: list
    calls: list


@dataclass
class Evaluator:
    model_path: Path
    doc: object                      # holon.machine.ExtractedModel
    text: str = ""
    recs: dict = field(default_factory=dict)
    env_keys: dict = field(default_factory=dict)
    proc: object = None
    checks: dict = field(default_factory=dict)
    starts: int = 0                  # node processes started (a restart forgets the native tables: holon.sorts.search3)

    @classmethod
    def build(cls, model_path, doc) -> "Evaluator":
        model_path = Path(model_path)
        text = model_path.read_text(encoding="utf-8")
        e = cls(model_path, doc, text, records(text), {f: k for f, k in _ENVF.findall(text)})
        e.checks = {a: [c.id for c in doc.program(a).checks()] for a in doc.actions}
        e.start()
        return e

    def all_reaches(self):
        return self.doc.all_reaches()

    def compiled(self) -> Path:
        sha = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        d = cache_dir() / sha[:32]
        mjs = d / "model.mjs"
        if mjs.is_file():
            return mjs
        d.mkdir(parents=True, exist_ok=True)
        # compile in a private directory and publish model.mjs by an atomic rename: a concurrent run must never see a
        # partly written module (two `holon run` processes started together crashed on a half-written model.mjs)
        import shutil
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="build-", dir=d))
        try:
            src = tmp / "model.bend"
            src.write_text(self.text, encoding="utf-8")
            from .. import bend
            r = bend.run([src.name, "-o", mjs.name], cwd=tmp)
            if r.code != 0 or not (tmp / mjs.name).is_file():
                raise EvalError(f"bend failed to compile {self.model_path}: {r.out[-2000:]}")
            os.replace(tmp / mjs.name, mjs)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return mjs

    def start(self) -> None:
        from .. import bend
        node = bend.config().get("node", "node")
        self.starts += 1
        self.proc = subprocess.Popen([node, "--stack-size=65500", str(DRIVER), str(self.compiled())],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                     bufsize=1)

    def close(self) -> None:
        if self.proc is not None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=10)
            except Exception:  # noqa: BLE001
                self.proc.kill()
            self.proc = None

    def call(self, fn: str, args: list) -> dict:
        return self.req({"fn": fn, "args": args})

    def req(self, request: dict) -> dict:
        if self.proc is None or self.proc.poll() is not None:
            self.start()
        self.proc.stdin.write(json.dumps(request) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            err = self.proc.stderr.read()[-2000:] if self.proc.stderr else ""
            self.proc = None
            raise EvalError(f"the model's evaluator stopped: {err}")
        ans = json.loads(line)
        if "error" in ans:
            raise EvalError(ans["error"])
        return ans

    # ---------------------------------------------------------- values in
    def enc(self, ty: str, v):
        ty = ty.strip()
        if ty == "W":
            return word(v if v is not None else 0)
        if ty == "Bool":
            return bool(EV.to_int(v)) if not isinstance(v, bool) else v
        if ty == "U32":
            return int(v)
        if ty == "List<&2, U32>":
            return byts(v if v is not None else b"")
        m = re.fullmatch(r"List<&2, (.+)>", ty)
        if m:
            return [self.enc(m.group(1), x) for x in (v or [])]
        if ty in self.recs:
            fs = self.recs[ty]
            if not isinstance(v, dict):
                raise EvalError(f"a {ty} value from {type(v).__name__}")
            return {"$r": ty, "f": {f: self.enc(t, v.get(f)) for f, t in fs}}
        raise EvalError(f"no encoding of a {ty}")

    def state_in(self, state: dict) -> dict:
        items = sorted((EV.to_int(k), EV.to_int(v)) for k, v in (state or {}).items())
        return {"$r": "HSt", "f": {"sl": [{"$r": "KW", "f": {"k": word(k), "v": word(v)}} for k, v in items if v]}}

    def args_in(self, action: str, args: dict) -> dict:
        from ..machine_bend import bname
        rec = f"AR_{bname(action)}"
        params = self.doc.params(action) or []
        vals = {}
        for p in params:
            vals[bname(p["name"])] = self.arg_value(p, (args or {}).get(p["name"]))
        fs = self.recs.get(rec) or []
        return {"$r": rec, "f": {f: self.enc_arg(t, vals.get(f)) for f, t in fs}}

    def arg_value(self, p: dict, v):
        """An argument as the model's record holds it (structs by field name)."""
        from ..machine_bend import bname
        t = p.get("type", "")
        if v is None:
            return None
        if t == "tuple":
            return {bname(c["name"]): self.arg_value(c, (v or {}).get(c["name"]) if isinstance(v, dict) else None)
                    for c in p.get("components") or []}
        if t.endswith("]"):
            inner = dict(p, type=re.sub(r"\[\d*\]$", "", t))
            return [self.arg_value(inner, x) for x in v]
        if t in ("bytes", "string"):
            return v.encode() if isinstance(v, str) and not v.startswith("0x") else EV.to_bytes(v)
        return EV.to_int(v) if not isinstance(v, bool) else int(v)

    def enc_arg(self, ty: str, v):
        if ty in self.recs and isinstance(v, dict):
            return {"$r": ty, "f": {f: self.enc_arg(t, v.get(f)) for f, t in self.recs[ty]}}
        m = re.fullmatch(r"List<&2, (.+)>", ty)
        if m and m.group(1) != "U32":
            return [self.enc_arg(m.group(1), x) for x in (v or [])]
        if v is None:
            return self.enc(ty, None) if ty in ("W", "List<&2, U32>") else self.zero(ty)
        return self.enc(ty, v)

    def zero(self, ty: str):
        if ty == "W":
            return word(0)
        if ty == "Bool":
            return False
        if ty == "U32":
            return 0
        if ty.startswith("List<"):
            return []
        if ty in self.recs:
            return {"$r": ty, "f": {f: self.zero(t) for f, t in self.recs[ty]}}
        raise EvalError(f"no zero of a {ty}")

    def env_in(self, env: dict) -> dict:
        fs = self.recs.get("HEnv") or []
        out = {}
        env = env or {}
        for f, ty in fs:
            key = self.env_keys.get(f)
            if key is None:
                out[f] = self.zero(ty)
                continue
            if key == "blobs":
                out[f] = [word(x) for x in env.get("blobhash") or []]
            elif key == "calls":
                cs = []
                for c in env.get("calls") or []:
                    to = c.get("to")
                    cs.append({"$r": "HCall", "f": {"to": word(EV.to_int(to) if to is not None else 0),
                                                    "d": byts(c.get("data") or "0x"), "ok": bool(c.get("ok")),
                                                    "ret": byts(c.get("ret") or "0x")}})
                out[f] = cs
            elif key == "code":
                out[f] = [{"$r": "KB", "f": {"k": word(k), "b": byts(v)}} for k, v in sorted((env.get("code") or {}).items())]
            elif key == "balance":
                out[f] = [{"$r": "KW", "f": {"k": word(k), "v": word(v)}}
                          for k, v in sorted((env.get("balance") or {}).items())]
            elif key.startswith("immutable."):
                out[f] = word((env.get("immutable") or {}).get(key[len("immutable."):], 0))
            else:
                v = env.get(key)
                out[f] = word(v if v is not None else 0)
        return {"$r": "HEnv", "f": out}

    @staticmethod
    def table(entries: dict) -> list:
        return [{"$r": "HKB", "f": {"b": {"$b": k}, "v": word(v)}} for k, v in sorted(entries.items())]

    # ---------------------------------------------------------- runs
    def hashes(self) -> list[str]:
        return hashes_of(self.text)

    def run(self, action: str, state: dict, args: dict, env: dict, kh: dict | None = None,
            sh: dict | None = None) -> Run:
        from ..machine_bend import bname
        a = [self.state_in(state), self.args_in(action, args), self.env_in(env)]
        hs = self.hashes()
        if "keccak256" in hs:
            a.append(self.table(kh or {}))
        if "sha256" in hs:
            a.append(self.table(sh or {}))
        ans = self.call(f"run_{bname(action)}", a)
        return Run(ans["out"], ans["keys"].get("kh") or [], ans["keys"].get("sh") or [], ans.get("calls") or [])

    def run_fix(self, action: str, state: dict, args: dict, env: dict, kh: dict | None = None,
                sh: dict | None = None, rounds: int = 64) -> tuple[Run, dict, dict]:
        """A run whose hash tables hold the real hash of every key it looks up (adding them until none is new)."""
        kh = dict(kh or {})
        sh = dict(sh or {})
        for _ in range(rounds):
            r = self.run(action, state, args, env, kh, sh)
            new = False
            for k in r.kh:
                if k not in kh:
                    kh[k] = int.from_bytes(keccak256(bytes.fromhex(k[2:])), "big")
                    new = True
            for k in r.sh:
                if k not in sh:
                    sh[k] = int.from_bytes(hashlib.sha256(bytes.fromhex(k[2:])).digest(), "big")
                    new = True
            if not new:
                return r, kh, sh
        raise EvalError(f"{action}: the hash lookups did not settle in {rounds} rounds")

    def outcome(self, action: str, out: dict, state: dict) -> dict:
        f = out["f"]
        c = int(f["c"])
        rv = (f["rv"] or {}).get("$b", "0x") if isinstance(f["rv"], dict) else "0x"
        if c == 0:
            post = {}
            for kv in f["po"]["f"]["sl"]:
                post[int(kv["f"]["k"], 16)] = int(kv["f"]["v"], 16)
            touched = sorted({int(x, 16) for x in f["tw"]})
            writes = {h32(k): h32(post.get(k, 0)) for k in touched}
            events = []
            for lg in f["lg"]:
                topics = lg["f"]["t"]
                d = lg["f"]["d"]
                events.append({"topics": [h32(int(t, 16)) for t in topics],
                               "data": d.get("$b", "0x") if isinstance(d, dict) else "0x"})
            return {"status": "ok", "revert": None, "writes": writes, "events": events, "guard": None}
        if c == FUEL_CODE:
            return {"status": "unsupported", "revert": None, "writes": {}, "events": [], "guard": None,
                    "reason": f"{action}: a loop ran past the model's fuel"}
        guard = None
        if c != CALL_CODE:
            ids = self.checks.get(action) or []
            guard = ids[c - 1] if 0 < c <= len(ids) else None
        return {"status": "revert", "revert": rv, "writes": {}, "events": [], "guard": guard}

    def step(self, state: dict, action: str, args: dict, env: dict) -> dict:
        if action not in self.doc.actions:
            return {"status": "unsupported", "revert": None, "writes": {}, "events": [], "guard": None,
                    "reason": f"no action {action} in the document"}
        r, _kh, _sh = self.run_fix(action, state, args, env)
        return self.outcome(action, r.out, state)


# ------------------------------------------------------------------------------------------------ --evaluator
_MODEL = {}


def evaluator_for(model_bend: str | Path, doc_path, root: Path | None = None, source=None) -> Evaluator:
    from ..machine import load_extracted
    key = (str(model_bend), str(doc_path))
    if key not in _MODEL:
        doc = load_extracted(doc_path, root or ROOT, source=source)
        _MODEL[key] = Evaluator.build(model_bend, doc)
    return _MODEL[key]


def step(model: Evaluator, state, action, args, env) -> dict:
    return model.step(state, action, args, env)
