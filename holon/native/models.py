"""Model descriptors for the native harness: one per generated Bend model.

Each declares the .bend model file, any driver-local helpers, and the op tables
consumed by drivergen.emit_driver. Op bodies are Bend expressions returning
List<Nat>; `args`/`tr` are the dispatcher parameters.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

M0_FACTS = ROOT / "facts" / "morph_header.json"
M1_FACTS = ROOT / "spec" / "M1" / "facts"


def _header_fields() -> list[tuple[str, int]]:
    f = json.loads(M0_FACTS.read_text())
    return [(x["name"], x["width"]) for x in f["types"]["Header"]["fields"]]


def _hdr_ctor() -> str:
    """Positional Hdr{...} construction from a flat 257-cell Nat list."""
    fields = _header_fields()
    args, i = [], 0
    for name, w in fields:
        for k in range(w):
            args.append(f"U32.from_nat(at(args, {i}n, 0n))")
            i += 1
    return "M.Hdr{" + ", ".join(args) + "}"


# ---------------------------------------------------------------- M0 codec

M0_HELPERS = """\
def hdr_of(+args: List<&2, Nat>) -> M.Hdr:
  {HDR}

def fs2nats(+fs: List<&2, List<&2, U32>>) -> List<&2, Nat>:
  match fs:
    case Nil{}:
      Nil{}
    case Con{f, t}:
      Con{List.length(&2, U32, f), List.append(&2, Nat, u2nats(f), fs2nats(t))}

def show_dec(+m: Maybe<&2, List<&2, List<&2, U32>>>) -> List<&2, Nat>:
  match m:
    case None{}:
      Con{0n, Nil{}}
    case Some{fs}:
      Con{1n, fs2nats(fs)}
"""

M0_FLAT_OPS = [
    {"name": "enc_go_v0", "body": "u2nats(M.enc_go_v0(hdr_of(args)))"},
    {"name": "enc_go_v1", "body": "u2nats(M.enc_go_v1(hdr_of(args)))"},
    {"name": "enc_sol",   "body": "u2nats(M.enc_sol(hdr_of(args)))"},
    {"name": "ok_go",     "body": "u2bool(M.ok_go(nats2u(args)))"},
    {"name": "ok_sol",    "body": "u2bool(M.ok_sol(nats2u(args)))"},
    {"name": "dec_go",    "body": "show_dec(M.dec_go(nats2u(args)))"},
]

# ------------------------------------------------------------- M1 state machines

# A trace step word layout mirrors holon/mreplay.py:encode_step (WIDTH = 13).
ROLLUP_HELPERS = """\
def blobs_of(n: Nat, b0: Nat, b1: Nat) -> List<&2, Nat>:
  match n:
    case 0n:
      Nil{}
    case 1n:
      Con{b0, Nil{}}
    case 2n+p:
      Con{b0, Con{b1, Nil{}}}

def act_sel(op: Nat, +w: List<&2, Nat>) -> M.HAct:
  match op:
    case 0n:
      M.A_wait{0n}
    case 1n:
      M.A_commitBatch{at(w, 1n, 0n), at(w, 2n, 0n), at(w, 3n, 0n), at(w, 4n, 0n), at(w, 5n, 0n), at(w, 6n, 0n), at(w, 7n, 0n), blobs_of(at(w, 8n, 0n), at(w, 9n, 0n), at(w, 10n, 0n))}
    case 2n:
      M.A_commitState{at(w, 1n, 0n), at(w, 2n, 0n), at(w, 3n, 0n), at(w, 4n, 0n), at(w, 5n, 0n), at(w, 6n, 0n), at(w, 7n, 0n), blobs_of(at(w, 8n, 0n), at(w, 9n, 0n), at(w, 10n, 0n))}
    case 3n:
      M.A_commitBatchWithProof{at(w, 1n, 0n), at(w, 2n, 0n), at(w, 3n, 0n), at(w, 4n, 0n), at(w, 5n, 0n), at(w, 6n, 0n), at(w, 7n, 0n), blobs_of(at(w, 8n, 0n), at(w, 9n, 0n), at(w, 10n, 0n)), at(w, 11n, 0n)}
    case 4n:
      M.A_revertBatch{at(w, 1n, 0n), at(w, 2n, 0n), at(w, 3n, 0n)}
    case 5n:
      M.A_challengeState{at(w, 1n, 0n), at(w, 2n, 0n), at(w, 3n, 0n)}
    case 6n:
      M.A_proveState{at(w, 1n, 0n), at(w, 2n, 0n), at(w, 3n, 0n)}
    case 7n:
      M.A_finalizeBatch{at(w, 1n, 0n), at(w, 2n, 0n)}
    case 8n:
      M.A_setPause{at(w, 1n, 0n), bool_of(at(w, 2n, 0n))}
    case 9n:
      M.A_sendMessage{at(w, 1n, 0n)}
    case 10n:
      M.A_wait{at(w, 1n, 0n)}
    case 11n+p:
      M.A_wait{0n}

def act_of(+w: List<&2, Nat>) -> M.HAct:
  match w:
    case Nil{}:
      M.A_wait{0n}
    case Con{op, t}:
      act_sel(op, w)


def code_of(+o: M.HObs) -> Nat:
  match o:
    case M.O_Ok{}:
      0n
    case M.O_Rev{c}:
      (1n + c : Nat)

def log_head(+l: List<&2, M.HObs>) -> Nat:
  match l:
    case Nil{}:
      0n
    case Con{h, t}:
      code_of(h)

def head_code(+s: M.HSt) -> Nat:
  # the machine log is newest-first: the head obs is the one this step emitted
  log_head(M.log_of(s))

def fold(tr: List<&2, List<&2, Nat>>, +s: M.HSt) -> List<&2, Nat>:
  match tr:
    case Nil{}:
      Nil{}
    case Con{w, rest}:
      match w:
        case Nil{}:
          Con{254n, fold(rest, s)}
        case Con{op, t}:
          match op:
            case 11n:
              Con{255n, fold(rest, M.mig_eta2(M.mig_legacy(s), at(w, 1n, 0n)))}
            case n:
              +s2 = M.step(act_of(w), s)
              Con{head_code(s2), fold(rest, s2)}
"""

ROLLUP_TRACE_OPS = [
    {"name": "run", "body": "fold(tr, M.s0())"},
]

BATCHDATA_HELPERS = """\
def bd_span(+w: List<&2, Nat>, n: Nat, +off: Nat) -> List<&2, Nat>:
  match n:
    case 0n:
      Nil{}
    case 1n+p:
      Con{at(w, off, 0n), bd_span(w, p, (off + 1n : Nat))}

def bd_act_of(+w: List<&2, Nat>) -> M.HAct:
  match w:
    case Nil{}:
      M.A_txsPayloadV2{}
    case Con{op, t}:
      match op:
        case 0n:
          M.A_txsPayloadV2{}
        case 1n:
          M.A_append{bd_span(w, at(w, 1n, 0n), 2n), bd_span(w, at(w, (2n + at(w, 1n, 0n) : Nat), 0n), (3n + at(w, 1n, 0n) : Nat))}
        case 2n+p:
          M.A_txsPayloadV2{}

def bd_code_of(+o: M.HObs) -> Nat:
  match o:
    case M.O_Ok{}:
      0n
    case M.O_Rev{c}:
      (1n + c : Nat)

def bd_log_head(+l: List<&2, M.HObs>) -> Nat:
  match l:
    case Nil{}:
      0n
    case Con{h, t}:
      bd_code_of(h)

def bd_head_code(+s: M.HSt) -> Nat:
  # newest-first log: head obs is this step's observation
  bd_log_head(M.log_of(s))

def bd_fold(tr: List<&2, List<&2, Nat>>, +s: M.HSt) -> List<&2, Nat>:
  match tr:
    case Nil{}:
      Nil{}
    case Con{w, rest}:
      +s2 = M.step(bd_act_of(w), s)
      Con{bd_head_code(s2), bd_fold(rest, s2)}

def bd_view(+s: M.HSt) -> List<&2, Nat>:
  match s:
    case M.HSt{+heap, +ctx, +txp, +view, +snap, +live, +classes, +log}:
      snap

def bd_state(tr: List<&2, List<&2, Nat>>, +s: M.HSt) -> M.HSt:
  match tr:
    case Nil{}:
      s
    case Con{w, rest}:
      bd_state(rest, M.step(bd_act_of(w), s))
"""

BATCHDATA_TRACE_OPS = [
    {"name": "run",      "body": "bd_fold(tr, M.s0())"},
    {"name": "run_view", "body": "bd_view(bd_state(tr, M.s0()))"},
]

MODELS = {
    "m0": {
        "model": ROOT / "gen" / "M0" / "model" / "morph_header.bend",
        "flat_ops": M0_FLAT_OPS,
        "trace_ops": [],
        "helpers": M0_HELPERS.replace("{HDR}", _hdr_ctor()),
    },
    "rollup": {
        "model": ROOT / "gen" / "M1" / "model" / "morph_rollup.bend",
        "flat_ops": [],
        "trace_ops": ROLLUP_TRACE_OPS,
        "helpers": ROLLUP_HELPERS,
    },
    "batchdata": {
        "model": ROOT / "gen" / "M1" / "model" / "morph_batchdata.bend",
        "flat_ops": [],
        "trace_ops": BATCHDATA_TRACE_OPS,
        "helpers": BATCHDATA_HELPERS,
    },
}
