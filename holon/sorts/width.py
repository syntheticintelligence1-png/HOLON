"""Rule SORT, subform width: one law per store that narrows a value into a field of smaller width (I20; whitepaper §7.6
"a sum of k width-w terms, realized in width w, generates an overflow obligation", §5.6, App. E; contract clause 3 of
the docstring of tests_m2/test_extracted_refinement.py).

Basis. The narrowing stores of the extracted documents a milestone adopts for derivation (holon.sorts.reextract:
spec/<M>/lib/derive_extracted.json with "width": true):

  * a layout document (I17): an op of an encoder path whose source segments write a field of a record type that
    "truncates" (value_bits > 8 * width): the op stores only the low 8 * width bits of the field's value. The store is
    the op's origin span (origin.src), reached through origin.stack.
  * a transitions document of the planned I19 follow-up shape: a memory store ("mstores") whose value is
    ["<<", v, 256 - 8k] (a k-byte field at the top of the word) with v wider than 8k bits. A memory store at the span
    of a layout store is the same store (one law); the actions holding it are its entry points. A Solidity storage
    write never narrows by itself: the type checker makes the value's type the field's (an explicit conversion is
    the programmer's narrowing, not the store's), checked arithmetic reverts (a panic record) and unchecked
    arithmetic wraps at the type's width.

A value's width (width_of): a parameter's declared width ("params", and its "fields" for a member of a struct
parameter), a family's width, the left
operand's width for a right shift by a constant (minus the shift), 8k for ["byte", ..] / a k-byte mask, max of the
operands (+1 for +) for arithmetic, 256 otherwise.

Law. id L_sort_width_<where>_<x8>: <where> is slug(file stem) + "_<line>" (+ "_<hi>") of the store's span, x8 the
first 8 hex digits of sha256 of the canonical {record, field, width}. Statement (holon-ir/0.3, facts: the document
holding the store):
    forall s: Reach, a: Act.  width_site[ID](a, s) == true
"every evaluation of the store while action a runs from a reachable state s stores a value that fits the field's
width". DERIVATION entry: {law_id, rule, subform, facts, basis: {kind: "width", record, field, width, value_bits,
span, stack, document}, entry_points, stores: [{document, action?, src, stack}]}. Record extras (holon.mpipeline):
"width_site": {span, field, width}.

Decision (decide). No proof generator applies to a width obligation over an extracted model (it has no reachability
predicate), so a width law is PROVED by nothing here. The refutation search is bounded and evaluates the store on the
model (holon.extracted_eval) at the corpus steps the sidecar names ("width_corpus": the step refinement's evaluation of
each site, {"sites": {site id: {"steps", "reaching", "max", "over"}}}, which holon fragments writes beside its record
(holon.replay_fragments.WidthValues, store_values below on every compared step of an entry point); or a steps file
of the extracted model's inputs, {"steps": [{"id", "state", "action", "args", "env"}]}, evaluated here): a step that
reaches the store with a value that does not fit is a witness candidate. A reachability-backed counter-law needs the model's Reach (not compiled
yet), so a candidate is recorded as such and the status stays UNKNOWN, never REFUTED by a guess; with no candidate the
law is UNKNOWN with its bound (what was evaluated), and no witness.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULE, SUBFORM = "SORT", "width"
LAW_PREFIX = "L_sort_width_"
TEMPLATE = "holon.sorts.width/width_ok"
TEMPLATE_VERSION = 1


class WidthError(ValueError):
    pass


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def x8(record, field, width) -> str:
    return hashlib.sha256(json.dumps({"record": record, "field": field, "width": width}, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()[:8]


def law_id(span: str, record, field, width) -> str:
    from ..machine import source_span
    sp = source_span(span)
    if sp is None:
        raise WidthError(f"store span {span!r} is not a source span")
    unit, lo, hi = sp
    where = slug(Path(unit).stem) + f"_{lo}" + (f"_{hi}" if hi != lo else "")
    return f"{LAW_PREFIX}{where}_{x8(record, field, width)}"


def site_id(span: str, record, field) -> str:
    return f"width:{span}:{record or '-'}.{field}"


# ------------------------------------------------------------------------------------------------ widths of terms
def width_of(t, params: dict, fams: dict) -> int:
    """The bit width of a term's values (module docstring); 256 when nothing narrower is known."""
    if isinstance(t, bool):
        return 1
    if isinstance(t, int):
        return max(1, t.bit_length())
    if not isinstance(t, list) or not t:
        return 256
    h = t[0]
    if h == "param" and isinstance(params.get(t[1]), int):
        return params[t[1]]
    if h == "member" and len(t) == 3 and isinstance(t[1], list) and t[1][:1] == ["param"] and len(t[1]) == 2 \
            and isinstance(params.get((t[1][1], t[2])), int):    # a member of a struct parameter: its field's width
        return params[(t[1][1], t[2])]
    if h == "storage" and isinstance(fams.get(t[1]), int):
        return fams[t[1]]
    if h == "trunc" and isinstance(t[1], int):
        return min(t[1], width_of(t[2], params, fams))
    if h == ">>" and isinstance(t[2], int):
        return max(0, width_of(t[1], params, fams) - t[2])
    if h == "&" and isinstance(t[2], int) and t[2] & (t[2] + 1) == 0:
        return t[2].bit_length()
    if h in ("==", "!=", "<", "<=", ">", ">=", "!", "&&", "||"):
        return 1
    if h == "byte":
        return 8
    if h == "+" and len(t) == 3:
        return min(256, max(width_of(t[1], params, fams), width_of(t[2], params, fams)) + 1)
    if h == "*" and len(t) == 3:
        return min(256, width_of(t[1], params, fams) + width_of(t[2], params, fams))
    if h in ("/", "%") and len(t) == 3:
        return width_of(t[1], params, fams)
    if h == "?" and len(t) == 4:
        return max(width_of(t[2], params, fams), width_of(t[3], params, fams))
    return 256


# ------------------------------------------------------------------------------------------------ basis
def layout_stores(rel: str, doc: dict) -> list[dict]:
    """The narrowing stores of a layout document (module docstring)."""
    types = doc.get("types") or {}
    out = {}
    for fname, fn in sorted((doc.get("functions") or {}).items()):
        rec = fn.get("from")
        fields = {f["name"]: f for f in (types.get(rec) or {}).get("fields") or []} if isinstance(rec, str) else {}
        for path in fn.get("paths") or []:
            for op in path.get("ops") or []:
                for seg in op.get("src") or []:
                    f = fields.get(seg.get("field")) if isinstance(seg, dict) else None
                    if not f or not f.get("truncates"):
                        continue
                    origin = op.get("origin") or {}
                    span = origin.get("src")
                    if not isinstance(span, str):
                        continue
                    key = (span, rec, f["name"])
                    s = out.setdefault(key, {"document": rel, "record": rec, "field": f["name"], "width": 8 * int(f["width"]),
                                             "value_bits": int(f.get("value_bits") or 256), "span": span,
                                             "stack": list(origin.get("stack") or []), "fn": fname, "stores": []})
                    st = {"document": rel, "function": fname, "src": span, "stack": list(origin.get("stack") or [])}
                    if st not in s["stores"]:
                        s["stores"].append(st)
    return [out[k] for k in sorted(out)]


def transitions_stores(rel: str, doc: dict) -> list[dict]:
    """The narrowing memory stores and storage writes of a transitions document of the follow-up shape."""
    from .. import machine
    fams = {s["name"]: s.get("width") for s in (doc.get("storage") or []) + (doc.get("inherited_storage") or [])}
    out = []
    for a in sorted(doc.get("actions") or [], key=lambda a: a["name"]):
        params: dict = {}
        for p in a.get(machine.FORMAT["params"]) or []:
            if isinstance(p, dict):
                params[p["name"]] = p.get("width")
                for f in p.get("fields") or []:   # a struct parameter's members: (parameter, member) -> width
                    if isinstance(f, dict):
                        params[(p["name"], f.get("name"))] = f.get("width")
        for sec, r in machine.ExtractedModel.program_records(a):
            if sec == "mstores" and r.get("op", "mstore") == "mstore":
                v = r.get("value")
                if isinstance(v, list) and len(v) == 3 and v[0] == "<<" and isinstance(v[2], int) and v[2] % 8 == 0 \
                        and 0 < v[2] < 256:
                    w = 256 - v[2]
                    vb = width_of(v[1], params, fams)
                    if vb > w:
                        out.append({"document": rel, "record": None, "field": None, "width": w, "value_bits": vb,
                                    "span": r.get("src"), "stack": list(r.get("stack") or []), "action": a["name"],
                                    "offset": r.get("offset")})
    return out


def basis_elements(milestone: str, root) -> list[dict]:
    """Every width site of the milestone's adopted documents, one per store span and field (module docstring)."""
    from . import reextract
    root = Path(root)
    sc = reextract.sidecar(milestone, root)
    if not sc or not sc.get("width"):
        return []
    sites: dict = {}
    trans = []
    for rel in sorted(sc["documents"]):
        doc = json.loads((root / rel).read_text(encoding="utf-8"))
        kind = (doc.get("extraction") or {}).get("kind")
        if kind == "transitions":
            trans += transitions_stores(rel, doc)
        elif doc.get("functions"):
            for s in layout_stores(rel, doc):
                sites[(s["span"], s["record"], s["field"])] = dict(s, entry_points=[])
    for t in trans:
        hit = next((k for k in sites if k[0] == t["span"]), None)
        if hit is not None:   # the layout's store, reached by this action: an entry point, and the model's document
            s = sites[hit]
            s["entry_points"] = sorted(set(s["entry_points"]) | {t["action"]})
            s["document"] = t["document"]
            st = {"document": t["document"], "action": t["action"], "src": t["span"], "stack": t["stack"]}
            if st not in s["stores"]:
                s["stores"].append(st)
            continue
        if not isinstance(t["span"], str):
            continue
        field = t["field"] or f"mem@{t.get('offset')}"
        key = (t["span"], t["record"], field)
        s = sites.setdefault(key, {"document": t["document"], "record": t["record"], "field": field,
                                   "width": t["width"], "value_bits": t["value_bits"], "span": t["span"],
                                   "stack": t["stack"], "entry_points": [], "stores": []})
        s["entry_points"] = sorted(set(s["entry_points"]) | {t["action"]})
        s["stores"].append({"document": t["document"], "action": t["action"], "src": t["span"], "stack": t["stack"]})
    out = []
    for k in sorted(sites, key=lambda k: (k[0], str(k[1]), str(k[2]))):
        s = sites[k]
        s["stores"] = sorted(s["stores"], key=lambda x: json.dumps(x, sort_keys=True))
        out.append(s)
    return out


def width_spec(site: dict) -> dict:
    """What the ref "width:<id>" hashes: the template and the basis element (the store, its field and widths)."""
    return {"template": TEMPLATE, "template_version": TEMPLATE_VERSION,
            "basis": {k: site.get(k) for k in ("record", "field", "width", "value_bits", "span", "stack")},
            "entry_points": site.get("entry_points") or [], "stores": site.get("stores") or []}


def law_ir(site: dict, milestone: str, facts_sha: str, rule_catalog_version: str) -> dict:
    lid = law_id(site["span"], site["record"], site["field"], site["width"])
    what = f"{site['record']}.{site['field']}" if site.get("record") else site["field"]
    return {
        "ir_version": "holon-ir/0.3", "law_id": lid, "milestone": milestone, "rule": RULE, "subform": SUBFORM,
        "rule_catalog_version": rule_catalog_version, "facts": site["document"], "facts_sha256": facts_sha,
        "notes": (f"SORT-width law (holon.sorts.width): every store at {site['span']} of {what} (a {site['value_bits']}-bit "
                  f"value into {site['width']} bits) while action a runs from a reachable state s stores a value that "
                  f"fits {site['width']} bits; entry points: {', '.join(site.get('entry_points') or []) or 'none known'}. "
                  "Provenance: DERIVATION.json."),
        "statement": {"binders": [{"q": "forall", "name": "s", "type": "Reach"}, {"q": "forall", "name": "a", "type": "Act"}],
                      "assume": [],
                      "claim": {"eq": [{"width_site": site_id(site["span"], site["record"], site["field"]),
                                        "on": {"var": "a"}, "from": {"var": "s"}}, {"bool": True}]},
                      "scope": {"kind": "unbounded"}},
    }


def produce(ctx) -> list[tuple[dict, dict]]:
    """The SORT-width producer (holon.rules.CATALOG["SORT"]["width"]): nothing unless the milestone adopts extracted
    documents with "width": true (holon.sorts.reextract)."""
    out = []
    for s in basis_elements(ctx.milestone, ctx.root):
        data = (Path(ctx.root) / s["document"]).read_bytes()
        law = law_ir(s, ctx.milestone, hashlib.sha256(data).hexdigest(), ctx.rule_catalog_version)
        entry = {"law_id": law["law_id"], "rule": RULE, "subform": SUBFORM, "facts": s["document"],
                 "basis": {"kind": "width", **{k: s.get(k) for k in ("record", "field", "width", "value_bits", "span",
                                                                      "stack")}},
                 "entry_points": s.get("entry_points") or [], "stores": s["stores"]}
        out.append((law, entry))
    return out


def width_ref(sid: str, law: dict, root=None) -> dict:
    """The object the ref "width:<id>" hashes, recomputed from the adopted documents (G2 needs no derive output)."""
    for s in basis_elements(str(law.get("milestone") or "M2"), Path(root or ROOT)):
        if site_id(s["span"], s["record"], s["field"]) == sid:
            return width_spec(s)
    return {"absent": sid}


def width_law(law: dict) -> str | None:
    """The width site id of a SORT-width law, else None."""
    if law.get("rule") != RULE or law.get("subform") != SUBFORM:
        return None
    eq = (law.get("statement") or {}).get("claim", {}).get("eq")
    if isinstance(eq, list) and eq and isinstance(eq[0], dict) and isinstance(eq[0].get("width_site"), str):
        return eq[0]["width_site"]
    return None


# ------------------------------------------------------------------------------------------------ decision
def store_values(model, step: dict, site: dict) -> list[int]:
    """The values the model stores at the site's span during one corpus step (memory stores and writes)."""
    from .. import extracted_eval as X
    from ..machine import MStore, Write
    a = step.get("action")
    if a not in model.actions:
        return []
    prog = model.program(a)
    e = X.Eval(model, step.get("state") or {}, a, step.get("args") or {}, step.get("env") or {})
    out = []
    hits = [s for s in prog.records((MStore, Write)) if s.src == site["span"]]
    if not hits:
        return []
    for s in hits:
        try:
            if not e.truth(s.cond):
                continue
            v = s.value
            if isinstance(s, MStore) and isinstance(v, list) and v[:1] == ["<<"]:
                v = v[1]
            out.append(e.iv(v))
        except (X.Unsupported, X.CallReverted):
            continue
    return out


def model_path(milestone: str, root) -> Path:
    """The extracted model (holon model's gen/<M>/extracted/model.bend) a width law's record is computed over."""
    return Path(root) / "gen" / str(milestone) / "extracted" / "model.bend"


def roots_text(law: dict, root) -> str:
    """The extracted model's definitions a width law is about, as `M.<name>` roots of its cone (holon.records.cone):
    the step definition step_<a> of each entry point (holon.machine_bend), which reaches its checks and its writes."""
    from ..machine_bend import bname
    site = next((s for s in basis_elements(str(law.get("milestone") or "M2"), Path(root))
                 if site_id(s["span"], s["record"], s["field"]) == width_law(law)), None)
    return " ".join(f"M.step_{bname(a)}" for a in sorted((site or {}).get("entry_points") or []))


def compiled_model(model: Path, cfg: dict | None = None) -> Path:
    """The extracted model compiled to an ES module in the build dir (cached by the text's sha256)."""
    from .. import bend
    text = Path(model).read_text()
    h = hashlib.sha256(text.encode()).hexdigest()
    src = bend.build_dir(ROOT) / "extracted" / "mjs" / h[:16] / "model.bend"
    src.parent.mkdir(parents=True, exist_ok=True)
    art = src.with_suffix(".mjs")
    if not art.exists():
        src.write_text(text)
        r = bend.run([src.name, "-o", art.name], cwd=src.parent, cfg=cfg or bend.config(ROOT))
        if r.code != 0 or not art.exists():
            raise WidthError(f"bend failed to compile {model}: {r.out[:1000]}")
    return art


def v2_fields(law: dict, rec: dict, milestone: str, root, cfg: dict | None = None) -> dict:
    """The v2 fields of a width record (holon.records.v2_fields) over the extracted model gen/<M>/extracted/model.bend:
    its cone from the entry points' step definitions (roots_text), its facts' ledger bundle (spec/<M>/ledger.json
    "bundles"), the compiled model's sha256 (the width search itself evaluates the document with holon.extracted_eval,
    which agrees with the model's chk_/step_ on the toy, tests_m2/test_i20_model_unit.py), and, as for every M2+ record,
    ledger_assumptions (the ledger entries meeting the cone) beside model_assumptions (the hypothesis premises: none)."""
    from .. import records as R
    from .. import inhabit
    root = Path(root)
    model = model_path(milestone, root)
    if not model.is_file():
        raise WidthError(f"{model} does not exist: run `python -m holon model --facts {law['facts']} --out "
                         f"{model.parent.relative_to(root)}/` first")
    out = R.v2_fields(law, rec, roots_text(law, root), model, law["facts"], compiled_model(model, cfg), root)
    out["ledger_assumptions"] = list(out["model_assumptions"])
    out["model_assumptions"] = []
    out["non_vacuity"] = inhabit.inhabit(law, milestone, root, root / "build" / "width_nonvac", cfg or {},
                                         rec=dict(rec, **out))
    return out


def corpus_of(milestone: str, root) -> dict | None:
    """The width corpus the adoption sidecar names ("width_corpus"), when it exists."""
    from . import reextract
    sc = reextract.sidecar(milestone, root) or {}
    rel = sc.get("width_corpus")
    p = Path(root) / rel if isinstance(rel, str) else None
    return json.loads(p.read_text(encoding="utf-8")) if p is not None and p.is_file() else None


def record(law: dict, milestone: str, root, kernel_version: str, statement_hash: str, facts_sha: str) -> dict:
    """The result record of a width law (holon.mpipeline dispatches SORT-width laws here): the v1 fields, the
    decision (status, bound, attempts, a witness candidate if any) and "width_site" {span, field, width}."""
    from .. import ir
    root = Path(root)
    site = next((s for s in basis_elements(milestone, root)
                 if site_id(s["span"], s["record"], s["field"]) == width_law(law)), None)
    d = decide(law, root, corpus_of(milestone, root))
    field = (site or {}).get("field")
    rec = {"law_id": law["law_id"], "statement_hash": statement_hash, "facts_sha256": facts_sha, "rule": RULE,
           "subform": SUBFORM, "maps_to": law.get("maps_to"), "statement": ir.render_statement(law),
           "premises": ir.premises(law) or ["(none: every reachable state and action)"],
           "kernel": {"name": "bend", "version": kernel_version, "verdict": "not_run"},
           "artifacts": {"laws": None, "proof": None, "law_name": None},
           "checker": {"exit_code": None, "marker": "not_run"}, "witness": None, "difference": None,
           "triage": "none", "replay": {"status": "not_run", "detail": "no witness"},
           "status": d["status"], "bound": d["bound"], "attempts": d["attempts"],
           "scope": "bounded",
           "width_site": {"span": (site or {}).get("span"), "field": field, "width": (site or {}).get("width")}}
    if "witness_candidate" in d:
        rec["witness_candidate"] = d["witness_candidate"]
    return rec


def decide(law: dict, root=None, corpus=None, model=None) -> dict:
    """{"status", "bound", "attempts", "witness_candidate"?} of a width law (module docstring). model: the loaded
    extracted model of the law's document (holon.machine.load_extracted), when the caller has it."""
    from .. import machine
    root = Path(root or ROOT)
    sid = width_law(law)
    site = next((s for s in basis_elements(str(law.get("milestone") or "M2"), root)
                 if site_id(s["span"], s["record"], s["field"]) == sid), None)
    attempts = [{"kind": "proof", "engine": "none", "detail": "no proof generator applies to a width obligation over "
                                                            "an extracted model (it has no reachability predicate)"}]
    if site is None:
        return {"status": "UNKNOWN", "bound": "the width site is not in the adopted documents", "attempts": attempts}
    ev = ((corpus or {}).get("sites") or {}).get(sid) if isinstance((corpus or {}).get("sites"), dict) else None
    if ev is not None:   # the refinement run's evaluation of the site on its corpus (holon.replay_fragments.WidthValues)
        bound = (f"corpus evaluation (holon fragments, {(corpus or {}).get('facts')}): {ev['steps']} steps of the entry "
                 f"points, {ev['reaching']} reaching {site['span']}, largest value stored {ev['max']} "
                 f"(width {site['width']} bits)")
        attempts.append({"kind": "refute", "engine": "corpus evaluation (holon.extracted_eval)", "tried": ev["steps"],
                         "hit": bool(ev.get("over")), "detail": bound})
        out = {"status": "UNKNOWN", "bound": bound, "attempts": attempts}
        if ev.get("over"):
            c = ev["over"][0]
            out["witness_candidate"] = {"step": f"trace {c['trace']} step {c['step']}", "value": c["value"],
                                        "note": "a corpus step stores a value wider than the field; no Reach-backed "
                                                "counter-law is generated (the extracted model has no Reach yet)"}
        return out
    steps = (corpus or {}).get("steps") or []
    doc = json.loads((root / law["facts"]).read_text())
    if (doc.get("extraction") or {}).get("kind") != "transitions" or not steps:
        why = "no corpus of the extracted model's steps" if not steps else \
            "the store's document gives no written values (a layout document)"
        attempts.append({"kind": "refute", "engine": "corpus evaluation (holon.extracted_eval)", "tried": 0,
                         "detail": why})
        return {"status": "UNKNOWN", "bound": f"no witness search: {why}", "attempts": attempts}
    model = model if model is not None else machine.load_extracted(law["facts"], root)
    n, reached, top, cand = 0, 0, 0, None
    for st in steps:
        n += 1
        vals = store_values(model, st, site)
        if vals:
            reached += 1
            top = max(top, max(vals))
            bad = [v for v in vals if v >> site["width"]]
            if bad and cand is None:
                cand = {"step": st.get("id"), "value": hex(bad[0])}
    bound = (f"corpus evaluation: {n} steps, {reached} reaching {site['span']}, largest value stored {hex(top)} "
             f"(width {site['width']} bits)")
    attempts.append({"kind": "refute", "engine": "corpus evaluation (holon.extracted_eval)", "tried": n,
                     "hit": cand is not None, "detail": bound})
    out = {"status": "UNKNOWN", "bound": bound, "attempts": attempts}
    if cand is not None:
        out["witness_candidate"] = dict(cand, note="a corpus step stores a value wider than the field; no Reach-backed "
                                                   "counter-law is generated (the extracted model has no Reach yet)")
    return out
