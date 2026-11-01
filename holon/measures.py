"""Def 6.13's measures over a milestone's laws (BUILD_PLAN row I81 = I44a; whitepaper Def 6.13, Thm 6.8, Thm 6.9,
Def 6.20; the contract is the docstring of tests_m3/test_ranking.py, rules M-PAR, M-UNDO, M-FACT, M-DISCH, M-NAT and
M-NA). One interface over the five measures: measure_all(ctx) gives every law of laws/<M> one entry

  {rule, measure, unit, kind, value, lower, upper, certified, scope, pending, why, detail}

with kind one of value (the measure is known, within its scope), bound (only bounds are known), pending (the rule or
its input does not exist yet; `pending` names the key that brings it) or not_applicable (Def 6.13 gives the law's rule,
or its subform, no measure).

  PAR    holonomy defect size: the positions where the two paths' values can differ. Lower bound: where the record's
         difference sides differ at the kernel-checked witness. Upper bound: where the claim's two encoder layouts
         differ once the law's premises apply (a correspondence makes two fields one, a pin makes a field constant),
         plus any length difference; one position for a value that is not a byte string. Certified when they agree.
  UNDO   residue liveness distance: the length of the shortest continuation that tells the two states apart. Lower
         bound 1 (an empty continuation observes nothing); upper bound the first step at which the model's
         observations of the witness's two runs differ (replay/<M>/undo/report.json), else the continuation's length.
  FACT   F(m, c) of a kernel law: I26's measure (holon.measures_fact, through holon.rules.fact.analyse), exact over I26's
         domain; 0 for a PROVED law (Thm 6.8).
  DISCH  discharge profile: pending (no cost model; the sidecar's key), with I32's class (holon.profile.classification).
  NAT    naturality defect mass: pending (the sidecar's key).

Ctx loads the committed inputs once and keeps the sha256 of every file it reads, for the document's `inputs`.
Nothing here names a target: every name comes from the laws, the records, the documents and the sidecar.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

RANKING_VERSION = "holon-ranking/0.1"
INFINITE = "infinite"


class MeasureError(ValueError):
    pass


def sidecar_rel(milestone: str) -> str:
    return f"spec/{milestone}/lib/ranking.json"


class Ctx:
    """The committed inputs of one milestone, read once; `inputs` holds {path: sha256} of every file read."""

    def __init__(self, root: Path | str, milestone: str):
        self.root = Path(root)
        self.m = milestone
        self.inputs: dict[str, str] = {}
        self._json: dict[str, object] = {}
        self.sidecar = self.read(sidecar_rel(milestone))
        if self.sidecar.get("ranking_version") != RANKING_VERSION:
            raise MeasureError(f"{sidecar_rel(milestone)}: ranking_version is not {RANKING_VERSION}")
        self.laws = {p.stem: self.read(self.rel(p)) for p in sorted((self.root / "laws" / milestone).glob("L*.json"))}
        self.records = {p.stem: self.read(self.rel(p))
                        for p in sorted((self.root / "results" / milestone).glob("L*.json"))}
        missing = sorted(set(self.laws) - set(self.records))
        if missing:
            raise MeasureError(f"laws without a record in results/{milestone}: {missing[:5]}")
        self._fact: dict[str, dict] = {}
        self._classes: list | None = None

    # ------------------------------------------------------------------ reading
    def rel(self, p: Path) -> str:
        return p.relative_to(self.root).as_posix()

    def read(self, rel: str):
        """The JSON file at rel (cached), its sha256 recorded."""
        if rel not in self._json:
            data = (self.root / rel).read_bytes()
            self.inputs[rel] = hashlib.sha256(data).hexdigest()
            self._json[rel] = json.loads(data)
        return self._json[rel]

    def maybe(self, rel: str):
        return self.read(rel) if (self.root / rel).is_file() else None

    def document(self, law: dict) -> dict:
        """The document a law names (its facts)."""
        return self.read(law["facts"])

    def actions(self, law: dict) -> dict:
        """{action name: action} of the law's document (empty for a document without actions)."""
        return {a["name"]: a for a in self.document(law).get("actions") or [] if isinstance(a, dict) and "name" in a}

    def report(self, sub: str) -> dict:
        """replay/<M>/<sub>/report.json's laws, or {}."""
        d = self.maybe(f"replay/{self.m}/{sub}/report.json")
        return (d or {}).get("laws") or {}

    # ------------------------------------------------------------------ I32's classes and I26's analysis
    def disch_classes(self) -> list:
        """I32's classification entries ({tag, class, disch_class, ...}), regenerated from the records."""
        if self._classes is None:
            self._classes = []
            conj = f"gen/{self.m}/disch/conjuncts.json"
            if self.m == "M3" and (self.root / conj).is_file():
                from .profile import classification
                self.read(conj)
                self._classes = classification(self.root)["entries"]
        return self._classes

    def fact_analysis(self, law: dict) -> dict:
        """I26's analysis (F1-F9) of the law's document, with the milestone's FACT sidecar."""
        rel = law["facts"]
        if rel not in self._fact:
            from .rules import fact as RF
            sc = self.maybe(f"spec/{self.m}/lib/fact.json") or {}
            self._fact[rel] = RF.analyse(self.document(law), RF.model_of(rel), sc)
        return self._fact[rel]

    # ------------------------------------------------------------------ the sidecar's orders
    def tier(self, order: str, name) -> int:
        for i, t in enumerate(self.sidecar[order]):
            if name in t:
                return i
        raise MeasureError(f"{name!r} is in no tier of the sidecar's {order}")


# ====================================================================== helpers
def claim_term(law: dict):
    """The left side of a law's claim."""
    return law["statement"]["claim"]["eq"][0]


def has_reach(law: dict) -> bool:
    return any(b.get("type") == "Reach" for b in law["statement"].get("binders") or [])


def ranges(ps) -> list[list[int]]:
    out: list[list[int]] = []
    for p in sorted(set(ps)):
        if out and out[-1][1] == p - 1:
            out[-1][1] = p
        else:
            out.append([p, p])
    return out


def _bytes(v):
    """A canonical byte string ("0x" + even hex) as bytes, else None."""
    if isinstance(v, str) and v.startswith("0x") and len(v) % 2 == 0:
        try:
            return bytes.fromhex(v[2:])
        except ValueError:
            return None
    return None


def diff_positions(a, b) -> tuple[list[int], str]:
    """(positions where a and b differ, over): over is "bytes" for two byte strings (the differing bytes of their
    common prefix, then every position past the shorter), else "value" (one position, when they differ)."""
    ba, bb = _bytes(a), _bytes(b)
    if ba is not None and bb is not None:
        n = min(len(ba), len(bb))
        return [i for i in range(n) if ba[i] != bb[i]] + list(range(n, max(len(ba), len(bb)))), "bytes"
    return ([] if a == b else [0]), "value"


def _version_pins(assume: list) -> dict:
    out = {}
    for p in assume:
        l, r = (p.get("eq") or [None, None])
        if isinstance(l, dict) and isinstance(r, dict) and l.get("field") == "version" and "of" in l and "bytes" in r:
            out[l["of"].get("var")] = int(r["bytes"], 16)
    return out


def layout_bound(law: dict, doc: dict) -> list[int] | None:
    """The positions where the claim's two encoder layouts can differ under the law's premises, or None when the
    claim is not two encoders of the document with a layout at the versions its premises pin."""
    st = law["statement"]
    sides = st["claim"]["eq"]
    if not all(isinstance(s, dict) and "call" in s and len(s.get("args") or []) == 1 and "var" in s["args"][0]
               for s in sides):
        return None
    fns = doc.get("functions") or {}
    pins_v = _version_pins(st.get("assume") or [])
    law_v = set(pins_v.values())
    lays = []
    for s in sides:
        f = fns.get(s["call"])
        if not isinstance(f, dict) or f.get("kind") != "encoder" or not isinstance(f.get("layouts"), dict):
            return None
        var = s["args"][0]["var"]
        if f.get("versions") is None:
            if len(f["layouts"]) != 1:
                return None
            lay = next(iter(f["layouts"].values()))
        else:
            # the law's version: its own argument's version premise, else the one version the premises pin (an
            # encoder whose source has no version field writes one version; holon.rules.par pairs it at that version)
            v = pins_v.get(var, next(iter(law_v)) if len(law_v) == 1 else None)
            if v is None or str(v) not in f["layouts"]:
                return None
            lay = f["layouts"][str(v)]
        lays.append((var, lay))
    parent: dict = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    consts: dict = {}
    for p in st.get("assume") or []:
        l, r = (p.get("eq") or [None, None])
        if not (isinstance(l, dict) and isinstance(r, dict) and "field" in l and "of" in l):
            continue
        a = (l["of"].get("var"), l["field"])
        if "field" in r and "of" in r:
            x, y = find(a), find((r["of"].get("var"), r["field"]))
            if x != y:
                parent[max(x, y)] = min(x, y)
        elif "bytes" in r:
            consts[a] = bytes.fromhex(r["bytes"][2:])
    pinned = {}
    for k, v in consts.items():
        pinned[find(k)] = v

    def cell(var, c, i, side):
        if isinstance(c, list) and c and c[0] == "field" and len(c) == 3:
            rep = find((var, c[1]))
            if rep in pinned and 0 <= c[2] < len(pinned[rep]):
                return ("const", pinned[rep][c[2]])
            return ("field", rep, c[2])
        if isinstance(c, list) and c and c[0] == "const" and len(c) == 2:
            return ("const", c[1])
        return ("opaque", side, i)
    (va, la), (vb, lb) = lays
    n = min(len(la), len(lb))
    return [i for i in range(n) if cell(va, la[i], i, 0) != cell(vb, lb[i], i, 1)] + list(range(n, max(len(la), len(lb))))


def first_divergence(entry: dict) -> int | None:
    """The first index i of the continuation where the model observes the replay's two runs differently: the run with
    the pair at t_at + i, the run without it at t_at - 2 + i, or at t_at_without + i where the entry carries it (a
    cancel law's run without x keeps y: I71; holon.undo.run.replay_entry)."""
    try:
        w, wo, t_at = entry["with"]["model"], entry["without"]["model"], entry["t_at"]
        t_wo = entry.get("t_at_without", t_at - 2)
        n = len(entry["with"]["trace"]) - t_at
    except (KeyError, TypeError, AttributeError):
        return None
    for i in range(n):
        if t_at + i >= len(w) or t_wo + i >= len(wo):
            return None
        if w[t_at + i] != wo[t_wo + i]:
            return i
    return None


def entry(rule: str, measure, unit, kind: str, *, value=None, lower=None, upper=None, certified=False, scope=None,
          pending=None, why: str = "", detail: dict | None = None) -> dict:
    return {"rule": rule, "measure": measure, "unit": unit, "kind": kind, "value": value, "lower": lower,
            "upper": upper, "certified": certified, "scope": scope, "pending": pending, "why": why,
            "detail": detail or {}}


# ====================================================================== the measures
def par(ctx: Ctx, lid: str, law: dict, rec: dict) -> dict:
    name = ctx.sidecar["measures"]["PAR"]["name"]
    unit = ctx.sidecar["measures"]["PAR"]["unit"]
    st = rec["status"]
    if st == "PROVED":
        return entry("PAR", name, unit, "value", value=0, lower=0, upper=0, certified=True,
                     why="the kernel accepted the proof: the two paths agree on every input of the premises",
                     detail={"positions": []})
    sides = law["statement"]["claim"]["eq"]
    scalar = any(isinstance(s, dict) and "bool" in s for s in sides)
    upos = None
    if not scalar:
        upos = layout_bound(law, ctx.document(law))
    if st == "REFUTED":
        d = rec.get("difference") or {}
        lpos, over = diff_positions(d.get("lhs"), d.get("rhs"))
        if over == "value":
            upos = [0]
        detail = {"over": over, "lower_positions": ranges(lpos),
                  "upper_positions": None if upos is None else ranges(upos)}
        if upos is not None and sorted(set(upos)) == sorted(set(lpos)):
            detail["positions"] = ranges(lpos)
            why = ("the witness's two sides differ at exactly the positions where the two paths can differ"
                   + (" (the layouts under the premises)" if over == "bytes" else " (a single value)"))
            return entry("PAR", name, unit, "value", value=len(lpos), lower=len(lpos), upper=len(upos),
                         certified=True, why=why, detail=detail)
        why = ("the witness's differing positions bound the defect from below"
               + ("" if upos is None else "; the layouts under the premises bound it from above")
               + ("; no upper bound computed (the claim is not two encoders with a layout at a pinned version)"
                  if upos is None else ""))
        return entry("PAR", name, unit, "bound", lower=len(lpos), upper=None if upos is None else len(upos),
                     why=why, detail=detail)
    up = 1 if scalar else (None if upos is None else len(upos))
    detail = {"over": "value" if scalar else ("bytes" if upos is not None else None), "lower_positions": [],
              "upper_positions": [[0, 0]] if scalar else (None if upos is None else ranges(upos))}
    return entry("PAR", name, unit, "bound", lower=0, upper=up,
                 why=f"UNKNOWN: no witness ({rec.get('bound') or 'no bound recorded'})", detail=detail)


def undo(ctx: Ctx, lid: str, law: dict, rec: dict) -> dict:
    name = ctx.sidecar["measures"]["UNDO"]["name"]
    unit = ctx.sidecar["measures"]["UNDO"]["unit"]
    st = rec["status"]
    if st == "PROVED":
        return entry("UNDO", name, unit, "value", value=INFINITE, lower=INFINITE, upper=INFINITE, certified=True,
                     why="the kernel proved the residue unobservable: no continuation tells the states apart")
    if st != "REFUTED":
        return entry("UNDO", name, unit, "bound", lower=1, upper=None,
                     why=("an empty continuation observes nothing; UNKNOWN: no distinguishing continuation found "
                          f"({rec.get('bound') or 'no bound recorded'})"))
    t = list((rec.get("witness") or {}).get("t") or [])
    e = ctx.report("undo").get(lid)
    i = first_divergence(e) if e else None
    if i is not None:
        up, src = i + 1, (f"replay/{ctx.m}/undo/report.json: the model's observations of the two runs first differ "
                          f"at t[{i}]")
    else:
        up, src = len(t), "the kernel-checked witness's continuation (no replay entry gives an earlier divergence)"
    checked = "the counter-law Bend checked has this continuation" if up == len(t) else \
        "a prefix of the continuation Bend checked, by the model's observations"
    detail = {"divergence": i, "t_length": len(t), "upper_from": src}
    if up == 1:
        return entry("UNDO", name, unit, "value", value=1, lower=1, upper=1, certified=True,
                     why=f"minimal: an empty continuation observes nothing, and one step tells the states apart ({checked})",
                     detail=detail)
    return entry("UNDO", name, unit, "bound", lower=1, upper=up,
                 why=f"an empty continuation observes nothing; {up} steps tell the states apart ({checked}); "
                     "shorter continuations were not searched exhaustively", detail=detail)


def fact(ctx: Ctx, lid: str, law: dict, rec: dict) -> dict:
    mc = ctx.sidecar["measures"]["FACT"]
    name, unit = mc["name"], mc["unit"]
    sub = rec.get("subform") or law.get("subform")
    if sub not in mc.get("subforms", []):
        return entry("FACT", None, None, "not_applicable", why=mc.get("why_not", ""), detail={"subform": sub})
    fid = claim_term(law).get("fact")
    an = ctx.fact_analysis(law)
    hit = next((x for x in an["laws"].values() if x.get("fact_id") == fid), None)
    m = (hit or {}).get("measure")
    if not m:
        return entry("FACT", name, unit, "bound", lower=1.0 if rec["status"] == "REFUTED" else None,
                     why="I26's analysis gives this basis element no measure", detail={"fact_id": fid})
    dom = m.get("domain") or {}
    scope = (f"I26's domain: {len(dom.get('alphabet') or [])} admissible words, lists of length 0..{dom.get('max_length')}"
             f", {len(dom.get('atoms') or {})} atoms")
    detail = {"fact_id": fid, "max_fiber": m.get("max_fiber"), "unevaluated": m.get("unevaluated"),
              "record_bits": ((rec.get("fact") or {}).get("measure") or {}).get("bits")}
    if rec["status"] == "PROVED":
        why = "the kernel proved ker(m) within ker(c) (Thm 6.8: F = 0)"
        if m.get("bits") != 0:
            why += f"; I26's enumeration gives {m.get('bits')} bits, which disagrees"
        return entry("FACT", name, unit, "value", value=0.0, lower=0.0, upper=0.0, certified=m.get("bits") == 0,
                     scope=scope, why=why, detail=detail)
    why = "I26's exhaustive enumeration of its domain (rule F9)"
    if rec["status"] == "REFUTED":
        why += "; the kernel-checked witness is one fiber holding two consumer values, so F >= 1 bit beyond the domain"
    return entry("FACT", name, unit, "value", value=m["bits"], lower=m["bits"], upper=m["bits"], certified=True,
                 scope=scope, why=why, detail=detail)


def disch_class(ctx: Ctx, law: dict) -> tuple[str, list]:
    """The I32 class a DISCH law reads (rule PE2): its own class's entry for a blocking law, else the most persistent
    of its basis element's entries; and the entries read."""
    did = claim_term(law).get("disch") or ""
    parts = did.split(":")
    if len(parts) < 4:
        return "undecided", []
    sub, tag, cls = parts[-3], parts[-2], parts[-1]
    mine = [e for e in ctx.disch_classes() if e["tag"] == tag and (sub != "blocking" or e["class"] == cls)]
    if not mine:
        return "undecided", []
    best = min(mine, key=lambda e: (ctx.tier("persistence_order", e["disch_class"]), e["class"]))
    return best["disch_class"], [{"class": e["class"], "disch_class": e["disch_class"]} for e in mine]


def disch(ctx: Ctx, lid: str, law: dict, rec: dict) -> dict:
    mc = ctx.sidecar["measures"]["DISCH"]
    klass, read = disch_class(ctx, law)
    return entry("DISCH", mc["name"], None, "pending", pending=mc["pending"], why=mc.get("why", ""),
                 detail={"class": klass, "entries": read})


def nat(ctx: Ctx, lid: str, law: dict, rec: dict) -> dict:
    mc = ctx.sidecar["measures"]["NAT"]
    return entry("NAT", mc["name"], None, "pending", pending=mc["pending"], why=mc.get("why", ""))


MEASURES = {"PAR": par, "UNDO": undo, "FACT": fact, "DISCH": disch, "NAT": nat}


def measure_of(ctx: Ctx, lid: str) -> dict:
    law, rec = ctx.laws[lid], ctx.records[lid]
    rule = law.get("rule")
    fn = MEASURES.get(rule) if rule in ctx.sidecar["measures"] else None
    if fn is None:
        return entry(rule, None, None, "not_applicable", why=f"Def 6.13 gives rule {rule} no measure")
    return fn(ctx, lid, law, rec)


def measure_all(ctx: Ctx) -> dict:
    return {lid: measure_of(ctx, lid) for lid in sorted(ctx.laws)}


def rules_summary(ctx: Ctx, ms: dict) -> dict:
    """Each Def 6.13 rule's measure and status, and every other rule the laws hold (not applicable)."""
    out = {}
    for rule, mc in sorted(ctx.sidecar["measures"].items()):
        n = sum(1 for m in ms.values() if m["rule"] == rule)
        pending = mc.get("pending")
        out[rule] = {"measure": mc["name"], "laws": n, "status": "pending" if pending else "computed",
                     "pending": pending}
    for m in ms.values():
        if m["rule"] not in out:
            out[m["rule"]] = {"measure": None, "laws": 0, "status": "not_applicable", "pending": None}
        if m["rule"] not in ctx.sidecar["measures"]:
            out[m["rule"]]["laws"] += 1
    return dict(sorted(out.items()))
