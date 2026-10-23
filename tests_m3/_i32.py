"""I32 prereg instrument: discharge profiles on the test milestone T32, and the M3 classification (the contract is the
docstring of tests_m3/test_disch_profile.py; the inputs are spec/M3/lib/disch_profile.json).

Written without holon's profile code (holon/analysis/abstraction.py, holon/js/profile.mjs, holon/rules/disch_profile.py):
- side(): the sidecar.
- model_module(): the compiled M1 machine, built by holon.mpipeline.CompiledMachine from the sidecar's facts (M1's
  own model; the instrument only evaluates it).
- run(task, **inputs): tests_m3/fixtures/disch_profile/i32.mjs on that model under node, its JSON answer. Tasks:
  sstar, frontier, outcomes, persistent, check, alphabet, abstraction (the .mjs header says what each returns).
- frontier(), outcomes(), persistent(): the one-occurrence frontier (label-correcting), every outcome (exhaustive),
  and the persistent frontier, each within the sidecar's strategy_moves.
- check(table, ae, cost, delay): every schedule of at most H moves over ae against a strategy table; the failures.
- alphabet(): the E-alphabet: the hints' E-moves at every state reachable from s* by at most H E-moves.
- abstraction(ax, ae): the time abstraction's soundness at s* within the horizon; the mismatches.
- classify(root): the M3 classification of I31's DISCH basis (the sidecar's classes.doc), from gen/M3/disch/
  conjuncts.json and results/M3.
"""
from __future__ import annotations

import json
import subprocess
from functools import lru_cache
from pathlib import Path

from tests_m3._m3 import ROOT, holon_module, load_json

SIDECAR = ROOT / "spec" / "M3" / "lib" / "disch_profile.json"
JS = ROOT / "tests_m3" / "fixtures" / "disch_profile" / "i32.mjs"
CLASSES = ("immediate", "cost-bearing", "delay", "mixed", "external-dependent", "non-dischargeable")


def side() -> dict:
    return load_json(SIDECAR)


@lru_cache(maxsize=None)
def model_module() -> str:
    mp = holon_module("holon.mpipeline")
    return str(mp.CompiledMachine.build(ROOT / side()["facts"]).artifact)


def run(task: str, **inputs) -> dict:
    s = side()
    req = {"module": model_module(), "hints": str(ROOT / s["candidates"]["source"]),
           "facts": load_json(ROOT / s["facts"]), "sidecar": s, "task": task, **inputs}
    p = subprocess.run(["node", str(JS)], input=json.dumps(req), capture_output=True, text=True, timeout=3600)
    if p.returncode != 0:
        raise RuntimeError(f"i32.mjs {task} failed: {p.stderr[-3000:]}")
    return json.loads(p.stdout)


@lru_cache(maxsize=None)
def _frontier() -> str:
    return json.dumps(run("frontier", moves=side()["search"]["strategy_moves"]))


def frontier() -> dict:
    return json.loads(_frontier())


@lru_cache(maxsize=None)
def _outcomes() -> str:
    return json.dumps(run("outcomes", moves=side()["dominance"]["strategy_moves"]))


def outcomes() -> list[list[int]]:
    return json.loads(_outcomes())["outcomes"]


@lru_cache(maxsize=None)
def _persistent() -> str:
    return json.dumps(run("persistent", moves=side()["persistent"]["strategy_moves"]))


def persistent() -> dict:
    return json.loads(_persistent())


def check(table: list[dict], ae: list[dict], cost: int, delay: int) -> dict:
    s = side()
    return run("check", table=table, ae=ae, H=s["schedule"]["H"], moves=s["search"]["strategy_moves"],
               cost=cost, delay=delay)


@lru_cache(maxsize=None)
def _alphabet() -> str:
    return json.dumps(run("alphabet", H=side()["schedule"]["H"]))


def alphabet() -> list[dict]:
    return json.loads(_alphabet())["ae"]


def abstraction(ax: list[dict], ae: list[dict]) -> dict:
    return run("abstraction", ax=ax, ae=ae, horizon=side()["abstraction"]["horizon_s"])


def pareto(points) -> list[list[int]]:
    pts = sorted({(int(c), int(d)) for c, d in points})
    return [list(p) for p in pts if not any(q != p and q[0] <= p[0] and q[1] <= p[1] for q in pts)]


def classify_points(points) -> str | None:
    """Whitepaper §5.7's class of a non-empty profile; None when empty."""
    pts = pareto(points)
    if not pts:
        return None
    if [0, 0] in pts:
        return "immediate"
    if all(d == 0 and c > 0 for c, d in pts):
        return "cost-bearing"
    if all(c == 0 and d > 0 for c, d in pts):
        return "delay"
    return "mixed"


def classify(root: Path = ROOT) -> list[dict]:
    """The M3 classification: for every basis element of every model in gen/M3/disch/conjuncts.json and every class
    it names, from results/M3: blk PROVED and some L_disch_ext_<tag>_<Y> PROVED (Y another class) ->
    external-dependent by those Y; blk PROVED and none -> non-dischargeable; blk REFUTED -> dischargeable (no cost
    model on M3, so no profile); otherwise (no blk record, or UNKNOWN) undecided. Sorted by (tag, class)."""
    doc = load_json(root / "gen" / "M3" / "disch" / "conjuncts.json")
    status = {}
    for p in sorted((root / "results" / "M3").glob("L_disch_*.json")):
        status[p.stem] = load_json(p).get("status")
    out = []
    for _m, md in sorted(doc["models"].items()):
        for b in md["basis"]:
            tag = b["tag"]
            for cls in sorted(b["classes"]):
                blk = f"L_disch_blk_{tag}_{cls}"
                ext = sorted(k for k, v in status.items() if k.startswith(f"L_disch_ext_{tag}_") and v == "PROVED"
                             and k != f"L_disch_ext_{tag}_{cls}")
                by = [k[len(f"L_disch_ext_{tag}_"):] for k in ext]
                st = status.get(blk)
                if st == "PROVED":
                    c = "external-dependent" if by else "non-dischargeable"
                elif st == "REFUTED":
                    c, by = "dischargeable", []
                else:
                    c, by = "undecided", []
                out.append({"tag": tag, "class": cls, "disch_class": c, "by": by, "blk": blk, "blk_status": st})
    return sorted(out, key=lambda e: (e["tag"], e["class"]))
