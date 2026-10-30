"""The keys check of a typed milestone (I68, the Q21 fix; rule S7 of tests_m3/test_structural_keys.py).

  python -m holon keys --milestone M [--root DIR] [--out PATH]

writes gen/<M>/sorts/keys.json (holon.sorts.skeys.keys_document): every raw slot, every literal slot and the real image
of every structural key that these sources touch:

  deployment   the typed model's s0 (its keys, holon.sorts.skeys.s0_keys)
  r5           the keys R5's corpus took (results/<M>/sorts/refinement/keys.json, written by holon fragments with the
               typed model as its evaluator)
  witnesses    every committed witness of an M3 record over the typed model or a section (results/<M>/L*.json): each
               run it denotes (steps; prefix, x, y, t and the runs without x or y), replayed on the typed model from
               its s0 with the witness's hash tables, each step's sload and sstore keys
  inhabitants  every committed non_vacuity witness of those records, replayed the same way

A key with a path is structural; a key without one is literal when the layout places its (base, offset), else raw. A
raw or literal slot equal to a structural key's real slot, or two structural keys with one real slot, is a collision:
listed in the document, a finding, never an assumption. Exit 0 written (whatever it lists); 2 an input missing.
Deterministic (sorted); nothing here names a target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from . import skeys as SK

ROOT = Path(__file__).resolve().parents[2]
STRUCTURAL_DIRS = ("gen/{m}/sorts/models/", "gen/{m}/undo/models/", "gen/{m}/fact/models/")


class KeysCmdError(RuntimeError):
    pass


def _step_dicts(v) -> list:
    return [x for x in (v or []) if isinstance(x, dict) and "action" in x and "env" in x]


def runs_of(w: dict) -> list[list[dict]]:
    """The runs a witness denotes, each a list of step dicts from the deployment."""
    if not isinstance(w, dict):
        return []
    out = []
    if _step_dicts(w.get("steps")):
        out.append(_step_dicts(w["steps"]))
    pre = _step_dicts(w.get("prefix"))
    t = _step_dicts(w.get("t")) if isinstance(w.get("t"), list) else []
    x = w.get("x") if isinstance(w.get("x"), dict) and "action" in w["x"] else None
    y = w.get("y") if isinstance(w.get("y"), dict) and "action" in w["y"] else None
    if x is not None or y is not None or pre or t:
        mids = [[s for s in (x, y) if s is not None]]
        if x is not None:
            mids.append([y] if y is not None else [])
        if y is not None:
            mids.append([])
        for mid in mids:
            run = pre + mid + t
            if run and run not in out:
                out.append(run)
    return out


def witnesses_of(rec: dict) -> tuple[list, list]:
    """(the record's witnesses, its inhabitants' witnesses)."""
    ws = []
    if isinstance(rec.get("witness"), dict):
        ws.append(rec["witness"])
    for e in (rec.get("witnesses") or {}).values():
        if isinstance(e, dict) and isinstance(e.get("witness"), dict):
            ws.append(e["witness"])
    nv = rec.get("non_vacuity") or {}
    inh = [nv["witness"]] if isinstance(nv.get("witness"), dict) else []
    return ws, inh


def _tables(w: dict) -> tuple[dict, dict]:
    hs = w.get("hashes") or {}

    def tab(name):
        return {k if k.startswith("0x") else "0x" + k: int(v, 16) if isinstance(v, str) else int(v)
                for k, v in (hs.get(name) or [])}
    return tab("keccak256"), tab("sha256")


def replay_keys(model_factory, run: list[dict], w: dict) -> set:
    """The storage keys a run of a witness takes on the typed model (its hash tables, every call answer it holds)."""
    from .search3 import Step
    m = model_factory()
    kh, sh = _tables(w)
    m.kh, m.sh = dict(kh), dict(sh)
    m.kh_sent = m.sh_sent = -1
    seen: set = set()
    orig = m.learn

    def learn(r):
        for x in r.get("sk") or []:
            seen.add(_sk_of_hex(x))
        return orig(r)
    m.learn = learn
    g = m.s0()
    for st in run:
        step = Step(st["action"], st.get("args") or {}, json.loads(json.dumps(st.get("env") or {})))
        _code, g, _calls = m.run_step(g, step, save=True)
    return seen


def _sk_of_hex(x: str) -> tuple:
    from .evaluate3 import sk_of_hex
    return sk_of_hex(x)


def gather(milestone: str, root: Path) -> tuple[dict, list, dict]:
    """({"raw", "literal", "structural"} sets, the sources read, {typed model: sha256}) over the deployment, R5 and the
    committed records."""
    from . import model3 as M3
    from .evaluate3 import Evaluator
    from .search3 import Hints, Model
    from ..machine import load_extracted
    root = Path(root)
    keys = {"raw": set(), "literal": set(), "structural": set()}
    sources, shas = [], {}
    models = sorted((root / "gen" / milestone / "sorts" / "models").glob("*.init.json"))
    if not models:
        raise KeysCmdError(f"gen/{milestone}/sorts/models/ holds no typed model")
    for ip in models:
        name = ip.name[:-len(".init.json")]
        mp = ip.parent / f"{name}.bend"
        text = mp.read_text(encoding="utf-8")
        if "\ntype SK is Data:\n" not in text:
            raise KeysCmdError(f"{mp.relative_to(root)} is not a structural model")
        shas[mp.relative_to(root).as_posix()] = hashlib.sha256(mp.read_bytes()).hexdigest()
        doc_rel = M3.documents_of(milestone, root, None)
        rel = next((d for d in doc_rel if M3.model_name(d) == name), None)
        if rel is None:
            raise KeysCmdError(f"no document of {milestone} gives the model {name}")
        doc = json.loads((root / rel).read_text(encoding="utf-8"))
        lits, _maps = SK.layout(doc)

        def put(key):
            b, o, p = SK.norm_key(key)
            if p:
                keys["structural"].add((b, o, p))
            elif (b + o) in lits and lits[b + o] == (b, o):
                keys["literal"].add(b + o)
            else:
                keys["raw"].add((b + o) & SK.MASK)
        for key, _v in SK.s0_keys(text):
            put(key)
        sources.append("deployment")
        rk = root / "results" / milestone / "sorts" / "refinement" / "keys.json"
        if rk.is_file():
            for e in json.loads(rk.read_text(encoding="utf-8")).get("keys") or []:
                put((int(e["b"], 16), int(e["o"], 16), tuple(("m", int(s["k"], 16), int(s["o"], 16)) for s in e["p"])))
            sources.append("r5")
        init = json.loads(ip.read_text(encoding="utf-8"))
        ev = Evaluator.build(mp, load_extracted(root / rel, root))
        try:
            def factory():
                return Model(ev, {k: v for k, v in init.items() if k != "preimages"}, Hints(None), root / rel,
                             native=False)
            rels = {f.format(m=milestone) for f in STRUCTURAL_DIRS}
            for q in sorted((root / "results" / milestone).glob("L*.json")):
                rec = json.loads(q.read_text(encoding="utf-8"))
                art = (rec.get("artifacts") or {}).get("model") or ""
                if not any(art.startswith(r) for r in rels):
                    continue
                ws, inh = witnesses_of(rec)
                for kind, group in (("witnesses", ws), ("inhabitants", inh)):
                    for w in group:
                        for run in runs_of(w):
                            for key in replay_keys(factory, run, w):
                                put(key)
                        if kind not in sources:
                            sources.append(kind)
        finally:
            ev.close()
    return keys, sources, shas


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon keys", description="the keys check of a typed milestone (I68, rule S7)")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root")
    ap.add_argument("--out", help="default gen/<M>/sorts/keys.json")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        keys, sources, shas = gather(a.milestone, root)
    except (KeysCmdError, SK.KeysError, OSError) as e:
        print(f"holon keys: {e}", file=sys.stderr)
        return 2
    doc = SK.keys_document(a.milestone, keys, sources, shas)
    out = Path(a.out) if a.out else root / "gen" / a.milestone / "sorts" / "keys.json"
    SK.write_json(out, doc)
    print(f"holon keys: {len(doc['raw'])} raw, {len(doc['literal'])} literal, {len(doc['structural'])} structural "
          f"keys from {', '.join(doc['sources'])}; {len(doc['collisions'])} collisions -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
