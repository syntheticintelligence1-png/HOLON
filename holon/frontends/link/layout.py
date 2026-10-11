"""Storage-layout extraction and diffing for solc --storage-layout output."""

import hashlib
import json


def normalize_layout(solc_json):
    """solc --storage-layout output -> deterministic field list.

    Returns {"fields": [{label, slot, offset, type, contract}...], "sha256": str}
    sorted by (slot, offset). `type` is the human-readable solc type label when
    available, else the raw type id.
    """
    types = solc_json.get("types") or {}
    fields = []
    for e in solc_json.get("storage", []):
        tid = e.get("type", "")
        label = tid
        info = types.get(tid)
        if isinstance(info, dict) and info.get("label"):
            label = info["label"]
        fields.append({
            "label": e.get("label", ""),
            "contract": (e.get("contract") or "").split(":")[-1],
            "slot": int(e.get("slot", 0)),
            "offset": int(e.get("offset", 0)),
            "type": label,
            "type_id": tid,
        })
    fields.sort(key=lambda f: (f["slot"], f["offset"], f["label"]))
    digest = hashlib.sha256(
        json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {"fields": fields, "sha256": "0x" + digest}


def diff_layouts(from_norm, to_norm):
    """Field-level diff between two normalized layouts.

    Keyed by (label): added/removed (label only in one), moved (slot or offset
    changed), retyped (type label changed). Each entry carries both ends.
    """
    def key(f):
        return f["label"]

    fm = {key(f): f for f in from_norm["fields"]}
    tm = {key(f): f for f in to_norm["fields"]}
    added, removed, moved, retyped = [], [], [], []
    for label in sorted(set(tm) - set(fm)):
        f = tm[label]
        added.append({"label": label, "slot": f["slot"], "offset": f["offset"], "type": f["type"]})
    for label in sorted(set(fm) - set(tm)):
        f = fm[label]
        removed.append({"label": label, "slot": f["slot"], "offset": f["offset"], "type": f["type"]})
    for label in sorted(set(fm) & set(tm)):
        a, b = fm[label], tm[label]
        if a["slot"] != b["slot"] or a["offset"] != b["offset"]:
            moved.append({"label": label,
                          "from": {"slot": a["slot"], "offset": a["offset"]},
                          "to": {"slot": b["slot"], "offset": b["offset"]}})
        if a["type"] != b["type"]:
            retyped.append({"label": label, "from_type": a["type"], "to_type": b["type"]})
    return {"added": added, "removed": removed, "moved": moved, "retyped": retyped}
