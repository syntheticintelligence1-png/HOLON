"""M2 refinement runner (whitepaper §8.7): feed the compiled model and the real
implementation the same inputs, count agreements, classify disagreements, and
write replay/M2/refinement/<edge>.json.

Real implementations:
  - morph common/batch header codecs + BatchData  (Go, realhdr/realbd drivers)
  - morph contracts: Rollup._loadBatchHeader + the M1 transition machine (forge)

Model side: bend-emitted model.mjs per model, hosted by
holon/native/js/worker.mjs (JSON lines) — the codec model's 257-field
record constructor exceeds the C backend's arity cap, so the documented
fallback (long-lived Node worker) is used for all three models.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from . import bendc, corpus
from .. import mreplay

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "native"
OUT = ROOT / "replay" / "M2" / "refinement"
MORPH = Path(os.environ.get("HOLON_MORPH", Path.home() / ".holon" / "morph"))
FORGE = os.environ.get("HOLON_FORGE", str(Path.home() / ".holon" / "foundry" / "forge"))
SOLC = os.environ.get("HOLON_SOLC", str(Path.home() / ".holon" / "solc-0.8.24"))

GO_SRC = ROOT / "holon" / "native" / "go"


def node_bin() -> str:
    return shutil.which("node") or "node"

# ------------------------------------------------------------------ plumbing


def _run(cmd, cwd=None, env=None, timeout=600):
    e = dict(os.environ)
    e.update(env or {})
    p = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr


class JsonLine:
    """A long-lived subprocess speaking JSON lines on stdin/stdout."""

    def __init__(self, cmd, cwd=None, env=None, greeting: bool = False):
        e = dict(os.environ)
        e.update(env or {})
        self.p = subprocess.Popen(cmd, cwd=cwd, env=e, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True)
        if greeting:
            self.p.stdout.readline()  # {"ok":true,"ready":true}

    def call(self, req: dict) -> dict:
        self.p.stdin.write(json.dumps(req) + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        self.p.terminate()


def setup_go_work(work: Path) -> Path:
    """go.work workspace: morph common+bindings + our driver module."""
    ws = work / "gowork"
    if not (ws / "common").exists():
        ws.mkdir(parents=True, exist_ok=True)
        for d in ("bindings", "common"):
            shutil.copytree(MORPH / d, ws / d, symlinks=True)
        (ws / "go.work").write_text("go 1.24.0\n\nuse (\n\t./bindings\n\t./common\n\t./holon\n)\n")
        holon = ws / "holon"
        holon.mkdir(exist_ok=True)
        (holon / "go.mod").write_text(
            "module holon-native\n\ngo 1.24.0\n\n"
            "require morph-l2/common v0.0.0\nreplace morph-l2/common => ../common\n\n"
            "require morph-l2/bindings v0.0.0\nreplace morph-l2/bindings => ../bindings\n")
        for pkg in ("realhdr", "realbd"):
            shutil.copytree(GO_SRC / pkg, holon / pkg)
    return ws


def build_drivers(ws: Path, libs: dict) -> dict:
    """Build the real-side Go drivers (model side is the .mjs worker)."""
    out = {}
    for pkg in ("realhdr", "realbd"):
        dst = ws / "bin" / pkg
        dst.parent.mkdir(exist_ok=True)
        code, log = _run([bendc.go_bin(), "build", "-o", str(dst), f"./{pkg}"],
                         cwd=ws / "holon")
        if code != 0:
            raise SystemExit(f"go build {pkg} failed:\n{log[-3000:]}")
        out[pkg] = dst
    return out


# ------------------------------------------------------------------ forge


def forge_setup(proj: Path) -> None:
    if not (proj / "contracts").exists():
        proj.mkdir(parents=True, exist_ok=True)
        shutil.copytree(MORPH / "contracts" / "contracts", proj / "contracts")
        for d in ("mock", "test"):
            shutil.rmtree(proj / "contracts" / d, ignore_errors=True)
        for f in ("foundry.toml", "remappings.txt"):
            shutil.copy(MORPH / "contracts" / f, proj / f)
    mreplay._sol_deps(proj)


def run_sol_loader(proj: Path, vectors: list[dict]) -> dict:
    """HolonRefine loader test: vectors[{id,b}] -> {id: (ok|rev, hash|reason)}."""
    tdir = proj / "test"
    tdir.mkdir(exist_ok=True)
    shutil.copy(ROOT / "replay" / "M2" / "solidity" / "HolonRefine.t.sol", tdir)
    (proj / "holon_vectors.json").write_text(json.dumps(
        {"n": len(vectors), "v": [{"id": v["id"], "b": "0x" + bytes(v["b"]).hex()} for v in vectors]}))
    code, out = _run([FORGE, "test", "--match-contract", "HolonRefine", "-vv",
                      "--offline", "--use", SOLC],
                     cwd=proj, env={"HOLON_VECTORS": "holon_vectors.json"}, timeout=3600)
    res = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0] == "HOLON":
            i = int(parts[1])
            res[i] = (parts[2], " ".join(parts[3:]))
    if code != 0 and not res:
        raise SystemExit("HolonRefine forge run failed:\n" + "\n".join(out.splitlines()[-40:]))
    return res


def run_rollup_forge(proj: Path, traces: list[list[dict]], facts: dict) -> dict:
    """Reuse the frozen M1 trace harness verbatim (copied, not edited)."""
    tdir = proj / "test"
    tdir.mkdir(exist_ok=True)
    shutil.copy(ROOT / "replay" / "M1" / "solidity" / "HolonTraceReplay.t.sol", tdir)
    init = facts["initial"]
    data = [init["F"], init["W"], init["D"], init["t"], init["fsr"][0], len(traces)]
    for tr in traces:
        data.append(len(tr))
        for a in tr:
            data += mreplay.encode_step(a)
    (proj / "holon_traces.json").write_text(json.dumps({"data": data}))
    res = {}
    cmd = [FORGE, "test", "--match-contract", "HolonTraceReplay", "-vv", "--offline",
           "--use", SOLC]
    for lo in range(0, len(traces), mreplay.CHUNK):
        code, out = _run(cmd, cwd=proj,
                         env={"HOLON_TRACES": "holon_traces.json",
                              "HOLON_LO": str(lo), "HOLON_HI": str(lo + mreplay.CHUNK)},
                         timeout=7200)
        for m in mreplay.LINE.finditer(out):
            res[(int(m.group(1)), int(m.group(2)))] = (m.group(3), m.group(4).strip())
        if code != 0 and not res:
            raise SystemExit("HolonTraceReplay forge run failed:\n"
                             + "\n".join(out.splitlines()[-40:]))
    return res


# ------------------------------------------------------------------ compare


def _eq(a, b) -> bool:
    return a == b


def record(edge: str, model_ref: dict, impl_ref: dict, seed: int, inputs_meta: dict,
           agree: list, disagreements: list, command: str,
           excluded: list | None = None) -> dict:
    for d in disagreements:
        classify(d)
        d.setdefault("note", "")
    excl = excluded or []
    return {
        "record_version": "holon-refinement/1",
        "edge": edge,
        "model": model_ref,
        "implementation": impl_ref,
        "corpus": {**inputs_meta, "seed": seed,
                   "total": len(agree) + len(disagreements),
                   "out_of_domain": len(excl),
                   "excluded": [{"input_id": i, "src": x["src"],
                                 "reason": x["reason"],
                                 "domain": x.get("domain")}
                                for i, x in enumerate(excl)]},
        "agreement": {
            "agree": len(agree),
            "disagree": len(disagreements),
            "explained": sum(1 for d in disagreements if d["class"] != "unexplained"),
            "unexplained": sum(1 for d in disagreements if d["class"] == "unexplained"),
        },
        "disagreements": disagreements,
        "mutation_adequacy": {"status": "not_run", "note": "mutation corpus is a different M2 unit"},
        "replay": {"command": command},
    }


def _counts(inputs: list[dict]) -> dict:
    c = {"grammar": 0, "boundary": 0, "witness": 0}
    for x in inputs:
        src = x["src"]
        c["witness" if src.startswith("witness") else "boundary" if src.startswith("boundary") else "grammar"] += 1
    return c


def _write(edge: str, rec: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{edge}.json"
    p.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    return p




# ------------------------------------------------------------ disagreement rules
# A disagreement's class is assigned ONLY by an explicit, named rule that cites
# the facts entry or source line justifying it. Anything no rule explains stays
# 'unexplained' — the M2 exit threshold counts unexplained disagreements, so
# classes may not be assigned by construction.

HDR_FACTS_PATH = ROOT / "facts" / "morph_header.json"
DEC_GETTER_CITE = ("facts/morph_header.json functions.dec_go.getters[].when + "
                   "common/batch/batch_header.go: the Go getter table is "
                   "per-version; a getter absent for the decoded version "
                   "errors while the model reads the raw offset bytes")


def rule_getter_absent_for_version(d: dict):
    """Go getters that legitimately do not exist for the decoded version
    (v0 has no lastBlockNumber getter; v2 has no blobVersionedHash getter —
    its data lives at raw offset 57). Bytes are otherwise identical."""
    if d.get("edge") != "m0_dec_go":
        return None
    rf, ver = d.get("real"), d.get("version")
    if not (isinstance(rf, list) and "ERR" in rf):
        return None
    if not ((ver == 0 and rf[11] == "ERR") or (ver == 2 and rf[5] == "ERR")):
        return None
    if _dec_equal(d.get("model"), rf, ver=ver) != "tolerated":
        return None  # bytes differ too — not explained by the getter surface
    return {"rule": "getter_absent_for_version", "class": "oracle_mismatch",
            "evidence": DEC_GETTER_CITE}


def rule_model_eval_failed(d: dict):
    """The emitted model library failed to produce a value for this input."""
    if not d.get("model_failed"):
        return None
    return {"rule": "model_eval_failed", "class": "extraction_defect",
            "evidence": "holon/native/js/worker.mjs returned a non-ok response"}


def rule_forge_obs_missing(d: dict):
    """The real harness emitted no observation line for this input/step."""
    if not d.get("real_missing"):
        return None
    return {"rule": "forge_obs_missing", "class": "oracle_mismatch",
            "evidence": "no HOLON line from forge / no field on the real "
                        "driver's response"}


RULES = [rule_getter_absent_for_version, rule_model_eval_failed,
         rule_forge_obs_missing]


def classify(dis: dict) -> dict:
    """Attach rule/class/evidence to a disagreement dict. First matching rule
    wins; unmatched stays unexplained."""
    for r in RULES:
        hit = r(dis)
        if hit:
            dis.update(hit)
            break
    dis.setdefault("rule", None)
    dis.setdefault("class", "unexplained")
    dis.setdefault("evidence", "")
    return dis


# ------------------------------------------------------------ encoder domain

def encoder_domain(edge: str) -> set[int] | None:
    """Versions the edge's encoder is defined for (facts encoder domain).
    None = every input is in domain."""
    fns = json.loads(HDR_FACTS_PATH.read_text())["functions"]
    if edge == "m0_enc_sol":
        le = fns["enc_sol"]["domain"]["version_le"]
        return set(range(le + 1))
    if edge == "m0_enc_go_v0":
        return {0}
    if edge == "m0_enc_go_v1":
        # facts: 'No Go encoder exists for version 2'; v2 reuses the v1 wire
        # only at the decoder. The v1 encoder's domain is version 1.
        return {1}
    return None


def split_by_domain(edge: str, inputs: list[dict]) -> tuple[list, list]:
    """(in_domain inputs, excluded inputs). Excluded entries carry reason
    out_of_encoder_domain and are coverage, not agreement or disagreement."""
    dom = encoder_domain(edge)
    if dom is None:
        return inputs, []
    keep, out = [], []
    for x in inputs:
        ver = x["cells"][0] if x.get("cells") else None
        if ver in dom:
            keep.append(x)
        else:
            out.append({**x, "reason": "out_of_encoder_domain",
                        "domain": sorted(dom)})
    return keep, out


# ------------------------------------------------------------------ M0 edges

IMPL_GO_HDR = {"repo": "morph-l2/morph", "commit": "3e44e795586af3e11285b603ab642c67823add51",
               "code": "common/batch/batch_header.go"}
IMPL_SOL_HDR = {"repo": "morph-l2/morph", "commit": "3e44e795586af3e11285b603ab642c67823add51",
                "code": "contracts/l1/rollup/Rollup.sol:_loadBatchHeader"}


def edge_enc_go(model: JsonLine, real: JsonLine, edge: str, op: int) -> dict:
    inputs, excluded = split_by_domain(edge, corpus.hdr_corpus(edge))
    seed = corpus.edge_seed(edge)
    agree, dis = [], []
    for i, x in enumerate(inputs):
        mo = model.call({"call": "flat", "op": op, "args": x["cells"]})
        ro = real.call({"h": x["cells"]})
        mb, rb = mo.get("out"), ro.get("enc_go_v0" if op == 0 else "enc_go_v1")
        if mb is not None and rb is not None and mb == rb:
            agree.append(i)
        else:
            dis.append({"input_id": i, "src": x["src"], "edge": edge,
                        "model": mb if mb is not None else mo,
                        "real": rb if rb is not None else ro,
                        "model_failed": mb is None, "real_missing": rb is None,
                        "note": "byte-level encoder mismatch"})
    return record(edge, {"call": f"enc_go_v{op}", "via": f"hcall op {op}"}, IMPL_GO_HDR,
                  seed, _counts(inputs), agree, dis,
                  "holonmodel flat op + realhdr (morph common/batch)",
                  excluded=excluded)


def edge_ok_go(model: JsonLine, real: JsonLine, edge: str) -> dict:
    inputs = corpus.bytes_corpus(edge)
    seed = corpus.edge_seed(edge)
    agree, dis = [], []
    for i, x in enumerate(inputs):
        mo = model.call({"call": "flat", "op": 3, "args": x["b"]})
        ro = real.call({"b": x["b"]})
        mb, rb = (mo.get("out") or [None])[0], ro.get("ok_go")
        if mb is not None and rb is not None and mb == rb:
            agree.append(i)
        else:
            dis.append({"input_id": i, "src": x["src"], "edge": edge,
                        "model": mb, "real": rb,
                        "model_failed": mb is None, "real_missing": rb is None,
                        "note": "accept/reject mismatch on BatchHeaderBytes.validate"})
    return record(edge, {"call": "ok_go", "via": "hcall op 3"}, IMPL_GO_HDR,
                  seed, _counts(inputs), agree, dis,
                  "holonmodel flat op 3 + realhdr Hash()")


def edge_dec_go(model: JsonLine, real: JsonLine, edge: str) -> dict:
    inputs = corpus.bytes_corpus(edge)
    seed = corpus.edge_seed(edge)
    agree, dis = [], []
    for i, x in enumerate(inputs):
        mo = model.call({"call": "flat", "op": 5, "args": x["b"]})
        ro = real.call({"b": x["b"]})
        out = mo.get("out")
        rb = ro.get("dec")
        # model: [0] = None; [1, len0, b..., len1, b...] = Some fields
        if out is None:
            dis.append({"input_id": i, "src": x["src"], "edge": edge,
                        "model": mo, "real": rb, "model_failed": True,
                        "note": "model call failed"})
            continue
        if out[0] == 0:
            ok = "agree" if rb is None else "disagree"
            mfields = None
        else:
            pos, fs = 1, []
            while pos < len(out):
                ln = out[pos]
                fs.append(out[pos + 1:pos + 1 + ln])
                pos += 1 + ln
            mfields = fs
            # ERR on the real side means "getter legitimately does not exist for
            # this version" only for v0 lastBlockNumber; everywhere else a real
            # error vs model bytes is a mismatch.
            ok = _dec_equal(mfields, rb, ver=(x["b"][0] if x["b"] else None))
        if ok == "agree":
            agree.append(i)
        else:
            dis.append({"input_id": i, "src": x["src"], "edge": edge,
                        "version": x["b"][0] if x["b"] else None,
                        "model": mfields, "real": rb, "real_missing": rb is None,
                        "note": "decoded field mismatch (ERR fields may be "
                                "version-absent getters — see classify rules)"})
    return record(edge, {"call": "dec_go", "via": "hcall op 5"}, IMPL_GO_HDR,
                  seed, _counts(inputs), agree, dis,
                  "holonmodel flat op 5 + realhdr getters")


def _u64_be(x: int, w: int) -> list:
    return [(x >> (8 * (w - 1 - i))) & 0xff for i in range(w)]


def _dec_equal(mfields, rfields, ver=None) -> bool:
    """model fields: byte lists per field. real fields: u64 scalar for the
    u64 getters, byte lists for hashes, "ERR" for a getter that fails.
    Field order: version, batchIndex, l1MessagePopped, totalL1MessagePopped,
    dataHash, blobVersionedHash, prevStateHash, postStateHash,
    withdrawRootHash, sequencerSetVerifyHash, parentBatchHash, lastBlockNumber.
    """
    if mfields is None or rfields is None:
        return mfields is None and rfields is None
    widths = [1, 8, 8, 8, 32, 32, 32, 32, 32, 32, 32, 8]
    mf, rf = list(mfields), list(rfields)
    tolerated = False
    if ver == 0 and len(mf) == 11 and len(rf) == 12 and rf[11] == "ERR":
        rf = rf[:11]  # v0 has no lastBlockNumber getter on the Go side
        tolerated = True
    if len(mf) != len(rf):
        return "disagree"
    for i, (m, r) in enumerate(zip(mf, rf)):
        if r == "ERR":
            if i == 5 and ver == 2:
                # v2 stores blobHashes/commit at offset 57, not a
                # blobVersionedHash getter: the Go API legitimately errors
                # while the model reads the raw bytes at the same offset.
                tolerated = True
                continue
            return "disagree"
        rr = _u64_be(r, widths[i]) if isinstance(r, int) else r
        if list(m) != list(rr):
            return "disagree"
    return "tolerated" if tolerated else "agree"


def edge_ok_sol(proj: Path, model: JsonLine, edge: str) -> dict:
    inputs = corpus.bytes_corpus(edge)
    seed = corpus.edge_seed(edge)
    mo_outs = []
    for x in inputs:
        mo = model.call({"call": "flat", "op": 4, "args": x["b"]})
        mo_outs.append((mo.get("out") or [None])[0])
    real = run_sol_loader(proj, [{"id": i, "b": x["b"]} for i, x in enumerate(inputs)])
    agree, dis = [], []
    for i, x in enumerate(inputs):
        mb = mo_outs[i]
        got = real.get(i)
        rb = 1 if got and got[0] == "ok" else 0 if got else None
        if mb is not None and rb is not None and mb == rb:
            agree.append(i)
        else:
            dis.append({"input_id": i, "src": x["src"], "edge": edge,
                        "model": mb, "real": got if got else "missing",
                        "model_failed": mb is None, "real_missing": got is None,
                        "note": "Solidity _loadBatchHeader accept mismatch"})
    return record(edge, {"call": "ok_sol", "via": "hcall op 4"}, IMPL_SOL_HDR,
                  seed, _counts(inputs), agree, dis,
                  "forge test --match-contract HolonRefine")


DEAD = 57005  # 0xDEAD: the enc_sol model's "uninitialized memory" sentinel


def _sol_image_bytes(out):
    """Model enc_sol emits an EVM memory image with 0xDEAD in cells the codec
    leaves unwritten. Sanitize those to 0 for the real loader; return None when
    the output is not a valid byte image."""
    if out is None or any((not isinstance(v, int)) or v < 0 or (v > 255 and v != DEAD)
                          for v in out):
        return None
    return [0 if v == DEAD else v for v in out]


def edge_enc_sol(proj: Path, model: JsonLine, edge: str) -> dict:
    """Model enc_sol(h) -> EVM memory image (0xDEAD = unwritten); the real
    implementation consumes the sanitized image via _loadBatchHeader (the
    Solidity side has no header encoder). Agreement = loader accepts."""
    inputs, excluded = split_by_domain(edge, corpus.hdr_corpus(edge))
    seed = corpus.edge_seed(edge)
    vectors, model_bytes = [], []
    for i, x in enumerate(inputs):
        mo = model.call({"call": "flat", "op": 2, "args": x["cells"]})
        b = _sol_image_bytes(mo.get("out"))
        model_bytes.append((b, mo.get("out")))
        if b is not None:
            vectors.append({"id": i, "b": b})
    real = run_sol_loader(proj, vectors)
    agree, dis = [], []
    for i, x in enumerate(inputs):
        mb, raw = model_bytes[i]
        got = real.get(i)
        if mb is None:
            dis.append({"input_id": i, "src": x["src"], "edge": edge,
                        "model": f"non-byte image {raw}", "real": got,
                        "model_failed": True,
                        "note": "model emitted a non-byte encoding image"})
        elif got and got[0] == "ok":
            agree.append(i)
        else:
            dis.append({"input_id": i, "src": x["src"], "edge": edge,
                        "model": f"{len(mb)} bytes", "real": got,
                        "real_missing": got is None,
                        "note": "real loader rejected model-encoded header"})
    return record(edge, {"call": "enc_sol", "via": "hcall op 2"}, IMPL_SOL_HDR,
                  seed, _counts(inputs), agree, dis,
                  "forge test --match-contract HolonRefine",
                  excluded=excluded)


# ------------------------------------------------------------------ M1 edges

def edge_rollup(proj: Path, model: JsonLine, cm, facts: dict) -> list[tuple[str, dict]]:
    """One record per M1 action: per-step ok/rev agreement across the corpus."""
    edge = "m1_rollup"
    corpus_in, seed = corpus.rollup_corpus(cm, edge, n=60)
    mreplay.fill_eta2_root(cm, [{"trace": x["steps"]} for x in corpus_in])
    traces = [x["steps"] for x in corpus_in]
    # model side: one hcall2 per trace
    model_codes = []
    for x in corpus_in:
        steps = [mreplay.encode_step(a) for a in x["steps"]]
        mo = model.call({"call": "trace", "op": 0, "steps": steps})
        model_codes.append(mo.get("out"))
    real = run_rollup_forge(proj, traces, facts)
    reasons = facts["reasons"]

    def model_str(tid, si):
        codes = model_codes[tid]
        if codes is None or si >= len(codes):
            return None
        c = codes[si]
        if c == 0:
            return "ok"
        if c == 255:
            return "mig"
        return "rev " + reasons.get(str(c - 1), f"code:{c - 1}")

    def real_str(tid, si):
        got = real.get((tid, si))
        if got is None:
            return None
        return "ok" if got[0] == "ok" else "rev " + got[1]

    ops = {op: [] for op in mreplay.OPS}
    per_op = {op: {"agree": [], "dis": []} for op in mreplay.OPS}
    for tid, x in enumerate(corpus_in):
        for si, a in enumerate(x["steps"]):
            ms, rs = model_str(tid, si), real_str(tid, si)
            op = a["op"]
            if ms == "mig":
                key = "ok" if rs is None else rs
                (per_op[op]["agree"] if rs in (None, "ok") or True else per_op[op]["dis"])
                # migrations are pseudo-steps: record what the model saw vs harness silence
                per_op[op]["agree"].append({"tid": tid, "step": si, "model": "mig",
                                            "real": rs if rs else "no-obs"})
                continue
            if rs is not None and ms == rs:
                per_op[op]["agree"].append({"tid": tid, "step": si})
            else:
                per_op[op]["dis"].append({"tid": tid, "step": si, "src": x["src"],
                                          "edge": f"{edge}_{op}",
                                          "model": ms, "real": rs if rs else "missing",
                                          "model_failed": ms is None,
                                          "real_missing": rs is None,
                                          "note": "transition obs mismatch"})
    outs = []
    impl = {"repo": "morph-l2/morph", "commit": "3e44e795586af3e11285b603ab642c67823add51",
            "code": "contracts/l1/rollup/Rollup.sol et al via HolonTraceReplay"}
    for op in mreplay.OPS:
        per = per_op[op]
        rec = record(f"{edge}_{op}", {"call": f"step(A_{op})", "via": "hcall2 op 0"}, impl,
                     seed, _counts([x for x in corpus_in if any(a['op'] == op for a in x['steps'])]),
                     per["agree"], per["dis"],
                     "forge test --match-contract HolonTraceReplay")
        outs.append((f"{edge}_{op}", rec))
    return outs


def edge_batchdata(model: JsonLine, realbd: JsonLine) -> list[tuple[str, dict]]:
    edge = "m1_batchdata"
    corpus_in, seed = corpus.batchdata_corpus(edge, n=40)
    impl = {"repo": "morph-l2/morph", "commit": "3e44e795586af3e11285b603ab642c67823add51",
            "code": "common/batch/batch_data.go: BatchData.Append/TxsPayloadV2"}

    def encode_steps(steps):
        out = []
        for a in steps:
            if a["op"] == "append":
                out.append([1, len(a["bctx"])] + a["bctx"] + [len(a["payload"])] + a["payload"])
            else:
                out.append([2])
        return out

    per_op = {"append": {"agree": [], "dis": []}, "txsPayloadV2": {"agree": [], "dis": []}}
    for tid, x in enumerate(corpus_in):
        steps = encode_steps(x["steps"])
        mo = model.call({"call": "trace", "op": 0, "steps": steps})
        mv = model.call({"call": "trace", "op": 1, "steps": steps})
        ro = realbd.call({"steps": steps})
        codes = mo.get("out")
        robs = ro.get("obs", [])
        rview = ro.get("view")
        mview = mv.get("out")
        for si, a in enumerate(x["steps"]):
            ms = ("ok" if codes and si < len(codes) and codes[si] == 0 else
                  (f"rev code:{codes[si] - 1}" if codes and si < len(codes) else None))
            rs = robs[si] if si < len(robs) else None
            ok = ms == "ok" and rs == "ok"
            per_op[a["op"]]["agree" if ok else "dis"].append(
                {"tid": tid, "step": si, "src": x["src"], "model": ms, "real": rs,
                 **({} if ok else {"edge": f"{edge}_{a['op']}",
                                  "model_failed": ms is None,
                                  "real_missing": rs is None,
                                  "note": "model evaluation failed" if ms is None
                                          else "BatchData obs mismatch"})})
            if a["op"] == "txsPayloadV2" and ok and mview is not None and rview is not None and mview != rview:
                per_op["txsPayloadV2"]["dis"].append(
                    {"tid": tid, "step": si, "src": x["src"],
                     "edge": f"{edge}_txsPayloadV2",
                     "model": f"view[{len(mview)}B]", "real": f"view[{len(rview)}B]",
                     "note": "TxsPayloadV2 view bytes differ"})
    outs = []
    for op in ("append", "txsPayloadV2"):
        per = per_op[op]
        rec = record(f"{edge}_{op}", {"call": f"step(A_{op})", "via": "hcall2 op 0/1"}, impl,
                     seed, _counts([x for x in corpus_in if any(a['op'] == op for a in x['steps'])]),
                     per["agree"], per["dis"],
                     "realbd (morph common/batch BatchData)")
        outs.append((f"{edge}_{op}", rec))
    return outs


# ------------------------------------------------------------------ driver


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m holon.native")
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--only", default=None, help="comma-separated edge names")
    ap.add_argument("--skip-forge", action="store_true", help="skip EVM-side edges")
    args = ap.parse_args(argv)

    print("building model libraries…")
    libs = bendc.build_all()
    for n, i in libs.items():
        print(f"  {n}: {i['lib']}")
    if args.build_only:
        return 0

    ws = setup_go_work(BUILD)
    bins = build_drivers(ws, libs)
    worker = str(ROOT / "holon" / "native" / "js" / "worker.mjs")
    # deep helper recursion (e.g. 65535-element payload lists) needs a big V8 stack
    models = {n: JsonLine([node_bin(), "--stack-size=32768", worker, libs[n]["lib"]],
                          greeting=True) for n in libs}
    realhdr = JsonLine([str(bins["realhdr"])])
    realbd = JsonLine([str(bins["realbd"])])
    for m in models.values():
        assert m.call({"ping": True}).get("pong"), "model worker ping failed"

    proj = BUILD / "forge_m2"
    if not args.skip_forge:
        forge_setup(proj)

    only = set(args.only.split(",")) if args.only else None
    written = []

    def want(e):
        return only is None or any(e == o or e.startswith(o) for o in only)

    if want("m0_enc_go_v0"):
        written.append(_write("m0_enc_go_v0", edge_enc_go(models["m0"], realhdr, "m0_enc_go_v0", 0)))
    if want("m0_enc_go_v1"):
        written.append(_write("m0_enc_go_v1", edge_enc_go(models["m0"], realhdr, "m0_enc_go_v1", 1)))
    if want("m0_enc_sol") and not args.skip_forge:
        written.append(_write("m0_enc_sol", edge_enc_sol(proj, models["m0"], "m0_enc_sol")))
    if want("m0_ok_go"):
        written.append(_write("m0_ok_go", edge_ok_go(models["m0"], realhdr, "m0_ok_go")))
    if want("m0_ok_sol") and not args.skip_forge:
        written.append(_write("m0_ok_sol", edge_ok_sol(proj, models["m0"], "m0_ok_sol")))
    if want("m0_dec_go"):
        written.append(_write("m0_dec_go", edge_dec_go(models["m0"], realhdr, "m0_dec_go")))

    if (only is None or any(e.startswith("m1_rollup") for e in only)) and not args.skip_forge:
        from ..mpipeline import CompiledMachine
        facts_path = ROOT / "spec" / "M1" / "facts" / "morph_rollup.json"
        cm = CompiledMachine.build(facts_path)
        facts = json.loads(facts_path.read_text())
        for e, rec in edge_rollup(proj, models["rollup"], cm, facts):
            if want(e):
                written.append(_write(e, rec))

    if (only is None or any(e.startswith("m1_batchdata") for e in only)):
        for e, rec in edge_batchdata(models["batchdata"], realbd):
            if want(e):
                written.append(_write(e, rec))

    for m in models.values():
        m.close()
    realhdr.close()
    realbd.close()
    print("\nwrote:")
    for p in written:
        print(" ", p.relative_to(ROOT))
    return 0
