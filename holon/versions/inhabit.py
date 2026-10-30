"""Rule V8: `python -m holon versions inhabit [--check]`, an in-flight inhabitant for every MIG edge a -> b of the
deployed path (G11V's in-flight sets).

An inhabitant is a trace from vr0 whose last two steps are a successful call of a successor site's action (PI1) of
version a (a commit: the batch it commits is in flight at the upgrade) and the successful migration along a -> b (by
upgradeToAndCall with the reinitializer the edge introduces, called with the sidecar's inflight_arguments, else
upgradeTo). Its key is the batch index the last commit writes (the parent header's index plus one); its legacy words
are the words every in-flight entry of the edge of kind retyped or reinterpreted reads that the change touches, at
their real slots and layout coordinates, each nonzero in the state before the migration. Its INHABIT.bend
(holon.versions.proofs.inhabit_text) is checked by Bend, and by BendTT when the verdict is enabled.

The prefix to version a is the sidecar's upgrade path up to a (the entry edge, the deployment record's first calls, the
path's migrations with the upgrade path's arguments). The commit's candidates are the successor-site call candidates of
holon.sorts' search over a's document, which drives I30's typed model (its ghost state); a version's module is model3's
untyped model of its document (the frozen assignment covers the adopted document only), so no candidate generator runs
over it: an edge whose source has a successor action in the versioned model is reported uninhabited with that reason,
and an edge whose source has none (each a model debt of its version) with the compiler's reasons. Nothing is smoothed:
every uninhabited edge is in results/<M>/versions/inflight.json with its reason.
"""
from __future__ import annotations

import json
import shutil

from . import INFLIGHT_VERSION, Ctx, render, write_or_check
from .machine import Machine


def legacy_words(m: Machine, a: str, b: str, key: int | None) -> list:
    """V8's legacy words of edge a -> b at a key: [{"entry", "reads", "slot", "base", "offset", "path"}], sorted by
    (entry, slot, reads)."""
    from ..keccak import keccak256
    lay_a = {f"{e['contract']}.{e['label']}": e for e in m.ctx.version(a)["layout"]}
    lay_b = {f"{e['contract']}.{e['label']}": e for e in m.ctx.version(b)["layout"]}
    edge = m.edges[(a, b)]
    out = []
    for x in edge["in_flight"]:
        if x["kind"] == "unchanged":
            continue
        new = lay_b[x["entry"]]
        for r in x["reads"]:
            old = lay_a[r]
            t = old["type"]
            if t.get("encoding") != "mapping":
                out.append({"entry": x["entry"], "reads": r, "slot": old["slot"], "base": old["slot"], "offset": 0,
                            "path": []})
                continue
            if key is None:
                return []
            base = int.from_bytes(keccak256(int(key).to_bytes(32, "big") + int(old["slot"]).to_bytes(32, "big")), "big")
            ov, nv = t["value"], (new["type"].get("value") or {})
            if "members" in ov:
                have = {(mm["slot"], mm["offset"]): mm for mm in nv.get("members") or []}
                for mm in ov["members"]:
                    n = have.get((mm["slot"], mm["offset"]))
                    if n is None or (n["label"], n["type"]) != (mm["label"], mm["type"]):
                        out.append({"entry": x["entry"], "reads": f"{r}.{mm['label']}",
                                    "slot": (base + mm["slot"]) % (1 << 256), "base": old["slot"], "offset": 0,
                                    "path": [[key, mm["slot"]]]})
            else:
                out.append({"entry": x["entry"], "reads": r, "slot": base, "base": old["slot"], "offset": 0,
                            "path": [[key, 0]]})
    return sorted(out, key=lambda w: (w["entry"], w["slot"], w["reads"]))


def successor_actions(m: Machine, vid: str) -> list:
    """The actions of the version's successor sites (PI1), over every commitment chain of its document."""
    from ..rules.par_init import chains
    p, _rel = m.docs[vid]
    doc = json.loads(p.read_text(encoding="utf-8"))
    return sorted({s["action"] for f in chains(doc)["families"] for s in f["successor_sites"]})


def edge_entry(m: Machine, a: str, b: str) -> dict:
    succ = successor_actions(m, a)
    compiled = [x for x in succ if x in m.actions(a)]
    base = {"edge": f"{a}->{b}", "trace": [], "key": None, "legacy": [], "bend": None, "verdict": None,
            "inhabited": False}
    if not succ:
        return dict(base, reason=f"{a} has no successor site (PI1): no commit puts a batch in flight")
    if not compiled:
        debt = {d["action"]: d for d in m.unit(a).get("debt") or []}
        why = "; ".join(f"{x}: {(debt.get(x) or {}).get('reason', 'not in the model')[:240]}"
                        + (f" (at {debt[x].get('record')}, {debt[x].get('src')})" if x in debt else "")
                        for x in succ)
        return dict(base, reason=f"no successor site action of {a} is in the versioned model (model debt): {why}")
    return dict(base, reason=f"{a}'s successor actions {compiled} are in the versioned model, but their commit "
                             "candidates come from holon.sorts' search, which drives I30's typed model; a version's "
                             "module is untyped (model3 without the sort section), so no candidate was tried")


def inhabitant(ctx: Ctx, m: Machine, a: str, b: str, trace: list, key: int | None) -> tuple[str, list, list]:
    """(INHABIT.bend's text, the legacy words with the values the state before the migration holds, the step outcomes)
    of edge a -> b's trace from vr0 (V8's shape, holon.versions.proofs.inhabit_text)."""
    from .machine import storage_of
    from .model import stem
    from .proofs import inhabit_text, rel_import
    outs, kh, _sh = m.run(trace)
    words = storage_of(outs[-2]["state"]["sl"]) if len(outs) >= 2 else {}
    legacy = [dict(w, word=hex(words.get(w["slot"], 0))) for w in legacy_words(m, a, b, key)]
    d = ctx.root / ctx.out("inflight_dir") / f"{a}_{b}"
    imp = rel_import(d, ctx.root / ctx.out("model_dir") / f"{stem(ctx.model)}.bend")
    return inhabit_text(m, imp, f"{a}->{b}", trace, outs, kh, legacy), legacy, outs


def edge_problems(ctx: Ctx, m: Machine, a: str, b: str, x: dict, cfg=None) -> list:
    """Why an inflight.json entry claiming edge a -> b inhabited is not V8's inhabitant (empty when it is): its last
    two steps are a successful call of a successor site's action of a and the successful migration a -> b, the
    INHABIT.bend is the one its trace and key generate, its legacy words are nonzero, it holds no escape hatch, and Bend
    (and BendTT when the verdict is enabled) accepts it."""
    from .. import bend
    trace = x.get("trace") or []
    if len(trace) < 2:
        return [f"{a}->{b}: the trace has {len(trace)} steps"]
    last, mig = trace[-2], trace[-1]
    bad = []
    if (last.get("kind"), last.get("version"), last.get("ok")) != ("call", a, True) \
            or last.get("action") not in successor_actions(m, a):
        bad.append(f"{a}->{b}: the step before the migration is not a successful successor-site call of {a}")
    if (mig.get("kind"), mig.get("label"), mig.get("version"), mig.get("ok")) != ("migrate", f"{a}->{b}", b, True):
        bad.append(f"{a}->{b}: the last step is not the successful migration along the edge")
    if bad:
        return bad
    f = ctx.root / ctx.out("inflight_dir") / f"{a}_{b}" / "INHABIT.bend"
    if not f.is_file():
        return [f"{a}->{b}: {f.relative_to(ctx.root).as_posix()} missing"]
    try:
        key = None if x.get("key") is None else int(str(x["key"]), 0)
        text, legacy, outs = inhabitant(ctx, m, a, b, trace, key)
    except Exception as e:  # noqa: BLE001  (a trace the machine cannot run is no inhabitant)
        return [f"{a}->{b}: the trace does not run on the versioned machine: {type(e).__name__}: {e}"]
    if any(o.get("status") != "ok" for o in outs[-2:]):
        bad.append(f"{a}->{b}: a step of the trace fails on the versioned machine")
    if f.read_text(encoding="utf-8") != text:
        bad.append(f"{a}->{b}: INHABIT.bend is not the one its trace and key generate")
    if x.get("legacy") != legacy:
        bad.append(f"{a}->{b}: the recorded legacy words are not the trace's")
    if any(int(w["word"], 16) == 0 for w in legacy):
        bad.append(f"{a}->{b}: a legacy word is zero before the migration")
    if bend.escape_hatches(text):
        bad.append(f"{a}->{b}: INHABIT.bend uses an escape hatch")
    if bad:
        return bad
    r = bend.check(f, cfg)
    if not r.ok:
        return [f"{a}->{b}: INHABIT.bend rejected by bend: {r.first_line}"]
    if bend.verdict_enabled(cfg):
        v = bend.check_verdict(f, cfg)
        if not v.ok:
            return [f"{a}->{b}: INHABIT.bend rejected by BendTT: {v.first_line}"]
    return []


def clause(milestone: str, root, cfg=None) -> tuple[bool, str] | None:
    """G11V's in-flight clause over a milestone with a versions sidecar (None without one): every MIG edge of the
    deployed path has an in-flight inhabitant (edge_problems). The detail always names the count."""
    from pathlib import Path
    root = Path(root)
    rel = f"spec/{milestone}/lib/versions.json"
    if not (root / rel).is_file():
        return None
    ctx = Ctx(root, rel)
    m = Machine(ctx)
    try:
        path = list(zip(m.path, m.path[1:]))
        f = root / ctx.out("inflight_results")
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
            got = doc.get("edges") if isinstance(doc, dict) else None
        except (OSError, ValueError):
            got = None
        if not isinstance(got, list):
            return False, f"in-flight: 0 of {len(path)} edges inhabited ({ctx.out('inflight_results')} missing or malformed)"
        bad, n = [], 0
        if [x.get("edge") if isinstance(x, dict) else None for x in got] != [f"{a}->{b}" for a, b in path]:
            bad.append("the in-flight entries are not the path's MIG edges in path order")
        for (a, b), x in zip(path, got):
            if not isinstance(x, dict) or not x.get("inhabited"):
                why = x.get("reason") if isinstance(x, dict) else None
                bad.append(f"{a}->{b} has no in-flight inhabitant" + (f" ({str(why)[:200]})" if why else ""))
                continue
            p = edge_problems(ctx, m, a, b, x, cfg)
            if p:
                bad += p
            else:
                n += 1
        head = f"in-flight: {n} of {len(path)} edges inhabited"
        return not bad, head if not bad else head + ": " + "; ".join(bad)
    finally:
        m.close()


def build(ctx: Ctx, log=None) -> tuple[dict, dict]:
    """(inflight.json's document, {relative path of an INHABIT.bend: text})."""
    m = Machine(ctx)
    try:
        edges, files = [], {}
        for a, b in zip(m.path, m.path[1:]):
            x = edge_entry(m, a, b)
            edges.append(x)
            if log:
                log(f"{a}->{b}: {'inhabited' if x['inhabited'] else 'not inhabited: ' + x['reason'][:160]}")
        return {"inflight_version": INFLIGHT_VERSION, "edges": edges}, files
    finally:
        m.close()


def run(ctx: Ctx, check: bool) -> int:
    doc, files = build(ctx, log=lambda s: print(f"holon versions inhabit: {s}"))
    target = ctx.root / ctx.out("inflight_results")
    out_dir = ctx.root / ctx.out("inflight_dir")
    data = render(doc)
    if check:
        ok = write_or_check(target, data, True)
        have = sorted(p.relative_to(ctx.root).as_posix() for p in out_dir.rglob("INHABIT.bend")) \
            if out_dir.is_dir() else []
        ok = ok and have == sorted(files) and all(write_or_check(ctx.root / r, t.encode("utf-8"), True)
                                                  for r, t in files.items())
        print(f"holon versions inhabit: {'reproduces' if ok else 'differs from a fresh run'}")
        return 0 if ok else 1
    if out_dir.is_dir():
        for p in sorted(out_dir.rglob("INHABIT.bend")):
            if p.relative_to(ctx.root).as_posix() not in files:
                shutil.rmtree(p.parent, ignore_errors=True)
    for r, t in files.items():
        write_or_check(ctx.root / r, t.encode("utf-8"), False)
    write_or_check(target, data, False)
    n = sum(1 for e in doc["edges"] if e["inhabited"])
    print(f"holon versions inhabit: in-flight: {n} of {len(doc['edges'])} edges inhabited -> {ctx.out('inflight_results')}")
    return 0

