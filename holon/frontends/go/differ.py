"""Compare extracted go facts against the hand-written targets.

This is the ONLY component of holon/frontends/go that reads hand-written
facts; it reads them solely as the comparison target (docs/M2_SPEC.md §2).
Used by tests_m2/s3_go_ssa.

Report shape: {"items": [{"hand": id, "status": status, "detail": str}...],
               "extra": [...], "unresolved": [...]}  where status is one of
"match" (recovered identically), "recovered" (semantically equivalent after
documented normalization), "extra" (extracted coverage beyond the hand
model), "missing" (hand element not reproduced -> must be recorded as debt).
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
HAND_CODECS = REPO / "facts" / "morph_header.json"
HAND_BATCH = REPO / "spec" / "M1" / "facts" / "morph_batchdata.json"


def _load(p):
    return json.loads(Path(p).read_text())


# ---------- field-name mapping (hand Header record -> go names) ----------

def go_field_map(hand):
    m = {}
    for f in hand["types"]["Header"]["fields"]:
        go = (f.get("go") or "").strip()
        if go and go != "—":
            m[f["name"]] = go.split()[0]
    m["version"] = "Version"  # virtual field: the version byte getter
    return m


def _norm_src(src, gmap):
    """Hand src -> go-side src for comparison."""
    if isinstance(src, list):
        src = src[0] if src else {}
    if "field" in src and src["field"] in gmap:
        return {"field": gmap[src["field"]]}
    return src


def _op_key(op, gmap):
    return (op["op"], op.get("offset"),
            json.dumps(_norm_src(op.get("src"), gmap), sort_keys=True))


def _enc_of(ext, suffix):
    for k, e in ext["encoders"].items():
        if k.endswith(suffix):
            return k, e
    return None, None


def diff_codecs(hand_path=HAND_CODECS, extracted=None):
    hand = _load(hand_path)
    if extracted is None:
        extracted = _load(REPO / "spec" / "M2" / "extracted" / "go_codecs.json")
    gmap = go_field_map(hand)
    items, extra = [], []

    # ---- encoders: enc_go_v0 -> BatchHeaderV0.Bytes, enc_go_v1 -> V1 ----
    for hid, suffix in (("enc_go_v0", "BatchHeaderV0.Bytes"),
                        ("enc_go_v1", "BatchHeaderV1.Bytes")):
        hf = hand["functions"][hid]
        label, enc = _enc_of(extracted, suffix)
        if enc is None:
            items.append({"hand": hid, "status": "missing",
                          "detail": f"no extracted encoder *.{suffix}"})
            continue
        got = [(_o["op"], _o.get("offset"),
                json.dumps(_norm_src(_o.get("src"), gmap), sort_keys=True))
               for _o in enc["ops"]]
        want = [_op_key(o, gmap) for o in hf["ops"]]
        detail = []
        if enc.get("length") != hf["length"]:
            detail.append(f"length {enc.get('length')} != {hf['length']}")
        if enc.get("memory_init") != hf["memory_init"]:
            detail.append("memory_init differs")
        if got != want:
            only_got = [g for g in got if g not in want]
            only_want = [w for w in want if w not in got]
            detail.append(f"ops differ: extracted-only={only_got} "
                          f"hand-only={only_want}")
        items.append({"hand": hid, "extracted": label,
                      "status": "match" if not detail else "differs",
                      "detail": "; ".join(detail)})

    # ---- predicate: ok_go -> BatchHeaderBytes.validate ----
    hf = hand["functions"]["ok_go"]
    pred = extracted["predicates"].get("batch.BatchHeaderBytes.validate")
    if pred is None:
        items.append({"hand": "ok_go", "status": "missing",
                      "detail": "no extracted validate predicate"})
    else:
        want = [{"if": r["if"], "then": r["then"]} for r in hf["rules"]]
        got = [{"if": r["if"], "then": r["then"]} for r in pred["rules"]]
        items.append({"hand": "ok_go",
                      "extracted": "batch.BatchHeaderBytes.validate",
                      "status": "match" if got == want else "differs",
                      "detail": "" if got == want else
                      f"rules got={got} want={want}"})

    # ---- decoder: dec_go getters vs extracted getters (common/batch) ----
    hf = hand["functions"]["dec_go"]
    getters = extracted["decoders"]["getters"]
    cb = [g for g in getters if g["pkg"].endswith("common/batch")]
    by_off = {}
    for g in cb:
        for a in g["accessors"]:
            if a["offset"] is not None and a["width"]:
                by_off.setdefault((a["offset"], a["width"]), []).append(
                    (g["function"], a))
    for hg in hf["getters"]:
        key = (hg["offset"], hg["width"])
        hits = by_off.get(key, [])
        if not hits:
            items.append({"hand": f"dec_go.{hg['name']}",
                          "status": "missing",
                          "detail": f"no getter for {key}"})
            continue
        when_got = [a.get("when") for _n, a in hits]
        when_want = hg.get("when")
        ok_when = (when_want is None) or any(w == when_want
                                             for w in when_got)
        items.append({"hand": f"dec_go.{hg['name']}",
                      "extracted": ",".join(n for n, _a in hits),
                      "status": "match" if ok_when else "differs",
                      "detail": "" if ok_when else
                      f"when got={when_got} want={when_want}"})

    # ---- view: field order by offset ----
    order = [k for k, _v in sorted(
        by_off.items(), key=lambda kv: kv[0][0])]
    want_order = []
    cur = 0
    for name in hand["functions"]["view"]["order"]:
        fld = next(f for f in hand["types"]["Header"]["fields"]
                   if f["name"] == name)
        want_order.append((cur, fld["width"]))
        cur += fld["width"]
    order_match = all(w in set(order) for w in want_order)
    items.append({"hand": "view", "status":
                  "match" if order_match else "differs",
                  "detail": "" if order_match else
                  f"getter offsets {order} miss {want_order}"})

    # ---- extra extracted coverage (informational, not failures) ----
    hand_pkg_funcs = {"BatchHeaderV0.Bytes", "BatchHeaderV1.Bytes"}
    for k in sorted(extracted["encoders"]):
        if not any(k.endswith(s) for s in hand_pkg_funcs):
            extra.append(f"encoder {k}")
    for g in getters:
        if not g["pkg"].endswith("common/batch"):
            extra.append(f"getter {g['function']} ({g['pkg']})")

    # ---- node/types duplicates: identical ops to common/batch? ----
    dup = _dup_check(extracted)
    if dup:
        items.append({"hand": "(node/types duplicate)",
                      "status": "recovered" if dup["identical"] else "differs",
                      "detail": dup["detail"]})

    return {"items": items, "extra": extra,
            "unresolved": [i for i in items
                           if i["status"] in ("missing", "differs")]}


def _dup_check(extracted):
    """Compare the two validate predicates (common/batch vs node/types)."""
    ps = extracted["predicates"]
    a = ps.get("batch.BatchHeaderBytes.validate")
    b = ps.get("types.BatchHeaderBytes.validate")
    if a and b:
        return {"identical": a["rules"] == b["rules"],
                "detail": "validate rules identical across packages"
                if a["rules"] == b["rules"] else "rules differ"}
    return None


# ---------- batchdata machine ----------

def _field_var_map(hand):
    """hand state var -> morph field (from its doc string)."""
    m = {}
    for name, _t, doc in hand["state"]:
        if "BatchData." in (doc or ""):
            m[name] = doc.split("BatchData.", 1)[1].split()[0]
    return m


def _let_sig(let, fmap):
    """Normalize a let to (helper, dst-field, src-role)."""
    e = let["expr"]
    if e[0] != "call":
        return None
    fn = e[1]
    if fn == "go_read":
        return ("read", fmap.get(e[3], e[3]))
    if fn in ("go_append_heap", "go_append_slice"):
        src = e[4]
        if isinstance(src, str) and src in fmap:
            role = fmap[src]
        elif isinstance(src, list):
            role = src[0]
        else:
            role = src
        return (fn, fmap.get(e[3], e[3]), role)
    return (fn,)


def diff_batchdata(hand_path=HAND_BATCH, extracted=None):
    hand = _load(hand_path)
    if extracted is None:
        extracted = _load(REPO / "spec" / "M2" / "extracted"
                          / "go_batchdata.json")
    items = []
    mach = next((m for m in extracted["machines"]
                 if m["type"] == "BatchData"), None)
    if mach is None:
        return {"items": [{"hand": "machine", "status": "missing",
                           "detail": "no BatchData machine"}],
                "extra": [], "unresolved": [True]}
    fmap = _field_var_map(hand)  # ctx->blockContexts, txp->txsPayload
    rmap = {v: k for k, v in fmap.items()}  # field->hand var

    # state cone
    got_fields = [s[0] for s in mach["state"]
                  if s[1] == "Sl" and s[0] not in ("view",)]
    want_fields = sorted(rmap.keys() - {"view"})
    items.append({"hand": "state cone",
                  "status": "match" if sorted(got_fields) ==
                  sorted(want_fields) else "differs",
                  "detail": f"got {sorted(got_fields)} "
                            f"want {sorted(want_fields)}"})

    # initial
    init_ok = all(
        mach["initial"].get(f) == hand["initial"][hv]
        for hv, f in fmap.items() if hv in hand["initial"])
    items.append({"hand": "initial",
                  "status": "match" if init_ok else "differs",
                  "detail": "" if init_ok else
                  f"got={mach['initial']} want={hand['initial']}"})

    # actions
    got = {a["name"]: a for a in mach["actions"]}
    for ha in hand["actions"]:
        ga = got.get(ha["name"])
        if ga is None:
            items.append({"hand": f"action.{ha['name']}", "status": "missing",
                          "detail": "not extracted"})
            continue
        def norm_lets(guards, fmap_, param_names):
            pos = {l["let"]: f"l{i}" for i, l in enumerate(guards)}
            out = []
            for i, l in enumerate(guards):
                e = l["expr"]
                if e[0] != "call":
                    continue
                fn = e[1]
                if fn == "go_read":
                    out.append((f"l{i}", "read",
                                fmap_.get(e[3], e[3])))
                elif fn in ("go_append_heap", "go_append_slice"):
                    src = e[4]
                    if isinstance(src, str) and src in pos:
                        role = pos[src]
                    elif isinstance(src, str) and src in param_names:
                        role = "param"
                    elif isinstance(src, list):
                        role = src[0]
                    else:
                        role = src
                    out.append((f"l{i}", fn, fmap_.get(e[3], e[3]), role))
                else:
                    out.append((f"l{i}", fn))
            return out

        w2 = norm_lets(ha["guards"], fmap,
                       {i[0] for i in ha["inputs"]})
        g2 = norm_lets(ga["guards"], {},
                       {i[0] for i in ga["inputs"]})
        items.append({"hand": f"action.{ha['name']}", "extracted":
                      ga["function"],
                      "status": "match" if g2 == w2 else "differs",
                      "detail": "" if g2 == w2 else
                      f"lets got={g2} want={w2}"})

    # observers
    go = mach["observers"].get("view_intact")
    items.append({"hand": "view_intact",
                  "status": "match" if go and
                  go["body"] == hand["observers"]["view_intact"]["body"]
                  else "differs",
                  "detail": "" if go and go["body"] ==
                  hand["observers"]["view_intact"]["body"] else
                  "body differs or missing"})

    extra = [f"action {n}" for n in got if n not in
             {a["name"] for a in hand["actions"]}]
    return {"items": items, "extra": extra,
            "unresolved": [i for i in items
                           if i["status"] in ("missing", "differs")]}


def _map_back(sig, rmap):
    """extracted field name -> hand var for comparison."""
    out = []
    for x in sig:
        out.append(rmap.get(x, x) if isinstance(x, str) else x)
    return tuple(out)


def run_all():
    return {
        "codecs": diff_codecs(),
        "batchdata": diff_batchdata(),
    }


if __name__ == "__main__":
    print(json.dumps(run_all(), indent=1))
