"""python -m holon games <command> (I56):

  flows [--root DIR] [--check]   gen/M5/games/value_flows.json and results/M5/games/v9.json (holon.games.flows)
  run   [--root DIR] [--check]   every game: the control and witness games, their Bend modules (checked), the econ
                                 laws (laws/M5/games/), the game and econ records, attempts.json, l6.json, summary.json

Exit 0 written or unchanged, 1 a --check difference or a failed run, 2 a usage error or a missing input.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .. import bend as B
from ..m5 import metrics as M5
from . import bendgen as BG
from . import econ, engine, flows, metric, target
from .common import FLOWS_PIN, ROOT, SIDECAR, Target, canon, dumps, sha256_file, sha256_text
from .run import Ledger, Runner

KEY = "I56"
OUT = ("gen/M5/games", "laws/M5/games", "results/M5/games")


class RunError(RuntimeError):
    pass


def _key(root: Path) -> dict:
    return json.loads((root / "spec" / "M5" / "predictions.json").read_text())["iterations"][KEY]


class Out:
    """Files to write (rel path -> text); write() or check() at the end."""

    def __init__(self, root: Path):
        self.root = root
        self.files: dict[str, str] = {}

    def put(self, rel: str, obj) -> None:
        self.files[rel] = obj if isinstance(obj, str) else dumps(obj)

    def problems(self, dirs: tuple) -> list[str]:
        probs = []
        for rel, text in sorted(self.files.items()):
            p = self.root / rel
            if not p.is_file() or p.read_text(encoding="utf-8") != text:
                probs.append(f"{rel}: differs")
        for d in dirs:
            base = self.root / d
            if base.is_dir():
                for p in sorted(base.rglob("*")):
                    if p.is_file() and p.relative_to(self.root).as_posix() not in self.files:
                        probs.append(f"{p.relative_to(self.root).as_posix()}: not generated")
        return probs

    def write(self, dirs: tuple) -> list[str]:
        done = []
        for rel, text in sorted(self.files.items()):
            p = self.root / rel
            if not p.is_file() or p.read_text(encoding="utf-8") != text:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
                done.append(rel)
        for d in dirs:
            base = self.root / d
            if base.is_dir():
                for p in sorted(base.rglob("*"), reverse=True):
                    if p.is_file() and p.relative_to(self.root).as_posix() not in self.files:
                        p.unlink()
                        done.append(f"removed {p.relative_to(self.root).as_posix()}")
        return done


# ------------------------------------------------------------------ flows
def flows_files(root: Path, t: Target, out: Out) -> dict:
    doc = flows.document(t)
    out.put("gen/M5/games/value_flows.json", doc)
    v9 = flows.coverage(doc, flows.detected(t))
    out.put("results/M5/games/v9.json", v9)
    return {"doc": doc, "v9": v9, "sha256": sha256_text(dumps(doc))}


# ------------------------------------------------------------------ Bend
class Checker:
    def __init__(self, root: Path):
        self.root = root
        self.verdict = B.verdict_enabled()
        self.kernels: dict = {}

    def check(self, rel_dir: str, files: dict, laws: dict, out: Out) -> str:
        """Write the module's files to a scratch copy under build/, check them, record BendTT; return the marker."""
        build = self.root / "build" / "games" / rel_dir
        build.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (build / name).write_text(text, encoding="utf-8")
            out.put(f"{rel_dir}/{name}", text)
        out.put(f"{rel_dir}/laws.json", {n: laws[n] for n in sorted(laws)})
        r = B.check(build / "PROOF.bend")
        first = (r.out or "").strip().splitlines()[0] if (r.out or "").strip() else ""
        if r.code != 0 or first != B.MARK_OK:
            raise RunError(f"{rel_dir}: Bend refused the module the engine generated (B5): {(r.out or '')[:1500]}")
        if self.verdict:
            v = B.check_verdict(build / "PROOF.bend")
            vf = (v.out or "").strip().splitlines()[0] if (v.out or "").strip() else ""
            self.kernels[rel_dir] = "checked" if v.code == 0 and vf == B.MARK_OK else "failed"
        else:
            self.kernels[rel_dir] = "not_run"
        return first


def present(laws_text: str, names: list[str]) -> bool:
    import re
    got = re.findall(r"^law (\S+):", laws_text, re.M)
    return sorted(got) == sorted(names)


# ------------------------------------------------------------------ controls
def control_record(doc: dict, chk: Checker, out: Out) -> dict:
    sol = engine.solve(doc)
    text, info = BG.complete_module(doc)
    actors = info["actors"]
    verdicts = [sol["classes"][x]["verdict"] for x in actors]
    strategies = {k: [info["act_index"][a] for a in sol["classes"][x]["strategy"]]
                  for k, x in enumerate(actors) if sol["classes"][x]["verdict"] == "rational"}
    gid = doc["id"]
    lt, pt, names = BG.complete_laws(gid, verdicts, strategies)
    rel = f"gen/M5/games/bend/{BG.bend_name(gid)}"
    marker = chk.check(rel, {"game.bend": text, "LAWS.bend": lt, "PROOF.bend": pt}, names, out)
    law = f"l_game_{BG.bend_name(gid)}"
    trusted = {a["id"]: a["trusted"] for a in doc["actors"]}
    classes = [{"class": x, "trusted": trusted[x], "verdict": sol["classes"][x]["verdict"],
                "payoff": sol["classes"][x]["payoff"], "strategy_length": sol["classes"][x]["strategy_length"]}
               for x in actors]
    return {"finding": gid, "kind": "control", "verdict": sol["verdict"], "classes": classes,
            "horizon": sol["horizon"], "witness_length": len(doc["witness"]), "witness_in_space": True,
            "evidence": {"law": law, "marker": marker, "law_present": present(lt, list(names))},
            "value_flows_sha256": M5.flows_sha256(doc),
            "notes": "complete game: every schedule of distinct actions searched in the module (G-K1, B1)"}


# ------------------------------------------------------------------ targets
def target_record(fid: str, rec: dict, runner: Runner, flows_sha: str, chk: Checker, out: Out, att: dict):
    game, why = target.witness_game(rec, runner)
    if game is None:
        att["findings"][fid] = {"reason": why, "tried": "the witness-form table (G-W1..G-W5) and a run of its "
                                                         "schedule on the run member's model (G-R2)"}
        return None
    lg: Ledger = game["ledger"]
    assets = lg.assets()
    deltas = [[s.get(a).nat6() if a in s else (0, 0, 0, 0, 0, 0) for a in assets] for s in lg.steps]
    classes = [c["class"] for c in game["classes"]]
    try:
        text = BG.witness_module(game["groups"], classes, deltas, len(assets))
    except BG.Range as e:
        att["findings"][fid] = {"reason": str(e), "tried": "the witness game's module"}
        return None
    verdicts = [c["verdict"] for c in game["classes"]]
    rational = [k for k, c in enumerate(game["classes"]) if c["verdict"] == "rational"]
    lt, pt, names = BG.witness_laws(fid, verdicts, rational)
    rel = f"gen/M5/games/bend/{BG.bend_name(fid)}"
    marker = chk.check(rel, {"game.bend": text, "LAWS.bend": lt, "PROOF.bend": pt}, names, out)
    out.put(f"gen/M5/games/games/{fid}.json",
            {"game": fid, "scope": "witness", "form": game["form"],
             "steps": [{"action": s["action"], "caller": str(s["env"].get("caller", "")).lower()}
                       for s in game["steps"]],
             "groups": game["groups"], "callers": game["callers"], "assets": assets, "deltas": deltas,
             "flows": lg.log, "payoff": game["payoff"], "legal": game["legal"]})
    for c in game["classes"]:
        if c["verdict"] == "UNKNOWN":
            why_c = (f"the class may run the witness, but the payoff of its callers is {game['payoff']} (G-T3)"
                     if c["class"] in game["legal"] else
                     "a step of the witness is not callable by the class or by anyone (G-T2)")
            att["classes"].setdefault(fid, {})[c["class"]] = (
                why_c + "; tried: the witness game only; the bounded universal search over the target's schedules "
                        "is not attempted (G-T3)")
    n = len(game["steps"])
    return {"finding": fid, "kind": "target", "verdict": game["verdict"], "classes": game["classes"],
            "horizon": n, "witness_length": n, "witness_in_space": True,
            "evidence": {"law": f"l_game_{BG.bend_name(fid)}", "marker": marker,
                         "law_present": present(lt, list(names))},
            "value_flows_sha256": flows_sha,
            "notes": f"witness game ({game['form']}): {n} steps, callers {game['callers']}, payoff {game['payoff']}"}


# ------------------------------------------------------------------ econ
def law_ir(law_id: str, kind: str, source: str, statement: dict, premises: list[str]) -> dict:
    body = {"ir_version": "holon-game-law/0.1", "law_id": law_id, "kind": kind, "source": source,
            "statement": statement, "premises": premises}
    return dict(body, statement_hash="sha256:" + sha256_text(canon(body)))


def econ_record(law: dict, status: str, marker, present_, values: dict, reason: str | None = None) -> dict:
    r = {"law_id": law["law_id"], "statement_hash": law["statement_hash"], "status": status,
         "premises": law["premises"], "checker": {"marker": marker, "law_present": present_}, "values": values}
    if reason:
        r["reason"] = reason
    return r


def n3_laws(t: Target, runner: Runner, chk: Checker, out: Out, results: dict) -> None:
    bond = t.sc["n3"]["bond_family"]
    for src in t.sc["n3"]["laws"]:
        rec = json.loads((t.root / "results" / "M3" / f"{src}.json").read_text())
        rd = econ.n3(rec, runner, bond)
        lr = law_ir(f"L_econ_n3_recommit_{src}", "n3_recommit", src,
                    {"deviators": "the witness's bonded address", "schedule": "G-W2: prefix + [y] + t",
                     "claim": "the payoff over the full schedule is negative and the payoff over the prefix alone is "
                              "nonneg"}, ["P-bond", "P-gas"])
        lc = law_ir(f"L_econ_n3_continuation_{src}", "n3_continuation", src,
                    {"deviators": "each caller of t other than the bonded address, alone",
                     "schedule": "G-W2: prefix + [y] + t", "claim": "each payoff over the full schedule is nonneg"},
                    ["P-gas"])
        for law in (lr, lc):
            out.put(f"laws/M5/games/{law['law_id']}.json", law)
        if rd["status"] == "UNKNOWN":
            for law in (lr, lc):
                results[law["law_id"]] = econ_record(law, "UNKNOWN", None, False, {}, rd["reason"])
            continue
        runs = {"full": rd["full"], "refuse": rd["refuse"]}
        adv = sorted(rd["adversaries"])
        for i, x in enumerate(adv):
            runs[f"adv{i}"] = rd["adversaries"][x]

        def rows(lg: Ledger):
            a = lg.assets()
            return [[s[x].nat6() if x in s else (0, 0, 0, 0, 0, 0) for x in a] for s in lg.steps], len(a)
        data, nas = {}, {}
        for k, lg in runs.items():
            data[k], nas[k] = rows(lg)
        try:
            text = BG.n3_module(data, nas, [f"adv{i}" for i in range(len(adv))])
        except BG.Range as e:
            for law in (lr, lc):
                results[law["law_id"]] = econ_record(law, "UNKNOWN", None, False, {}, str(e))
            continue
        vals_r = {"recommit": rd["recommit"], "refuse": rd["refuse_pay"], "bonded": rd["bonded"]}
        vals_c = {"adversaries": rd["adversary_pay"]}
        holds_r = rd["recommit"] == "negative" and rd["refuse_pay"] == "nonneg"
        und_r = "undetermined" in (rd["recommit"], rd["refuse_pay"])
        advp = list(rd["adversary_pay"].values())
        holds_c = bool(advp) and all(v == "nonneg" for v in advp)
        und_c = "undetermined" in advp
        for law, fn, holds, und, vals in ((lr, "n3_recommit", holds_r, und_r, vals_r),
                                          (lc, "n3_continuation", holds_c, und_c, vals_c)):
            st = econ.status(holds, und)
            if st == "UNKNOWN":
                results[law["law_id"]] = econ_record(law, "UNKNOWN", None, False, vals,
                                                     "a classification the claim reads is undetermined")
                continue
            name = BG.bend_name(law["law_id"])
            lt, pt, names = BG.bool_law(name, fn, holds)
            rel = f"gen/M5/games/bend/{name}"
            marker = chk.check(rel, {"game.bend": text, "LAWS.bend": lt, "PROOF.bend": pt}, names, out)
            results[law["law_id"]] = econ_record(law, st, marker, present(lt, list(names)), vals)


def o35_laws(t: Target, fdoc: dict, chk: Checker, out: Out, results: dict) -> list[str]:
    writers = econ.backlog_writers(t)
    member = t.sc["o35"]["member"]
    entries = {e["action"]: e for e in fdoc["entries"]}
    for b in writers:
        e = entries.get(f"{member}.{b}")
        cons = e["constructs"] if e else []
        law = law_ir(f"L_econ_o35_backlog_{b}", "o35_backlog", t.sc["o35"]["law"],
                     {"action": b, "claim": "for every k, k calls at msg.value 0 move no value to or from any party"},
                     ["P-gas"])
        out.put(f"laws/M5/games/{law['law_id']}.json", law)
        if not set(cons) <= {"VM1"}:
            results[law["law_id"]] = econ_record(law, "UNKNOWN", None, False, {"constructs": cons},
                                                 "the writer has a construct other than VM1")
            continue
        assets = sorted({f["asset"] for f in (e["flows"] if e else [])})
        name = BG.bend_name(law["law_id"])
        lt, pt, names = BG.o35_laws(name)
        rel = f"gen/M5/games/bend/{name}"
        marker = chk.check(rel, {"game.bend": BG.o35_module(len(assets)), "LAWS.bend": lt, "PROOF.bend": pt},
                           names, out)
        results[law["law_id"]] = econ_record(law, "PROVED" if marker == B.MARK_OK else "UNKNOWN", marker,
                                             present(lt, list(names)), {"constructs": cons, "assets": assets})
    return writers


# ------------------------------------------------------------------ run
def run_all(root: Path, out: Out) -> dict:
    t = Target(root)
    t.classes()
    fl = flows_files(root, t, out)
    pin = json.loads((root / FLOWS_PIN).read_text()) if (root / FLOWS_PIN).is_file() else None
    if pin is None or pin.get("value_flows_sha256") != fl["sha256"]:
        raise RunError(f"{FLOWS_PIN} does not pin the value-flow document's sha256 {fl['sha256']} (V8): commit the "
                       "pin before any game record")
    chk = Checker(root)
    key = _key(root)
    att = {"findings": {}, "classes": {}}
    records = []
    ctl_docs = [json.loads((root / p).read_text()) for p in sorted(key["thresholds"]["pins"]["controls"])]
    for doc in ctl_docs:
        records.append(control_record(doc, chk, out))
    runner = Runner(t, fl["doc"])
    pop = sorted(json.loads((root / "spec" / "M5" / "preregistration.json").read_text())["base"]["l6_findings"])
    expect = {}
    for fid in pop:
        rec = json.loads((root / "results" / "M3" / f"{fid}.json").read_text())
        r = target_record(fid, rec, runner, fl["sha256"], chk, out, att)
        expect[fid] = {"classes": dict(sorted(t.trusted.items())),
                       "witness_length": r["witness_length"] if r else None, "value_flows_sha256": fl["sha256"]}
        if r:
            records.append(r)
    for r in records:
        out.put(f"results/M5/games/records/{r['finding']}.json", r)
    econ_res: dict = {}
    n3_laws(t, runner, chk, out, econ_res)
    writers = o35_laws(t, fl["doc"], chk, out, econ_res)
    for lid, r in sorted(econ_res.items()):
        out.put(f"results/M5/games/econ/{lid}.json", r)
    out.put("results/M5/games/attempts.json", att)
    inputs = {"population": pop, "expect": expect, "records": records, "controls": ctl_docs, "corpus_truth": None,
              "corpus_expect": {}}
    l6 = metric.l6_v9(inputs, fl["v9"])
    out.put("results/M5/games/l6.json", l6)
    summary = {"key": KEY, "sidecar": SIDECAR, "flows_sha256": fl["sha256"], "v9": l6["v9"],
               "controls": len(ctl_docs), "target_records": sum(1 for r in records if r["kind"] == "target"),
               "decided": l6["decided"], "verdicts": l6["verdicts"], "o35_writers": writers,
               "econ": {k: v["status"] for k, v in sorted(econ_res.items())},
               "bendtt": dict(sorted(chk.kernels.items())), "l6_overall": l6["overall"]}
    out.put("results/M5/games/summary.json", summary)
    return summary


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="holon games", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("command", choices=["flows", "run"])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = a.root.resolve()
    out = Out(root)
    try:
        if a.command == "flows":
            flows_files(root, Target(root), out)
            dirs: tuple = ()
        else:
            s = run_all(root, out)
            print(f"games run: {s['controls']} controls, {s['target_records']} target records, decided "
                  f"{s['decided']['numerator']}/{s['decided']['denominator']}, V9 {s['v9']}, L6 overall "
                  f"{s['l6_overall']}")
            dirs = OUT
    except (RunError, ValueError) as e:
        print(f"games {a.command}: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"games {a.command}: {e}", file=sys.stderr)
        return 2
    if a.check:
        probs = out.problems(dirs)
        for p in probs:
            print(f"games {a.command}: {p}")
        print(f"games {a.command}: {'CHECK OK' if not probs else 'CHECK FAILED'}")
        return 1 if probs else 0
    done = out.write(dirs)
    for p in done:
        print(f"games {a.command}: wrote {p}")
    print(f"games {a.command}: {len(done)} file(s) written")
    return 0
