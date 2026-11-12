"""roles_source of a law, and the class of its outcome (I104; the soundness argument of holon.roles).

roles_source(law, manifest, milestone) is the provenance of the role a law was derived through:
  facts gen/<M>/codec/<role>.json     the link role <role>
  facts gen/<M>/goops/<component>.json the Go-op component <component> (a count component, not a role sidecar's: hand)
  subform go_round_trip, go_branch    the gox document role
  subform go_recompute                the recompute role whose id the law id carries (L_par_gorc_<role>_...)
  anything else                       no generated role: "hand" when the manifest says the milestone's typed sidecars are
                                      hand ones, else the typed role's source
A role absent from the manifest (a hand sidecar the run kept) is "hand".

classify(status, replay, source) is the outcome's class. Only a REFUTED law derived through hand roles whose replay
confirms on the real code is a finding. A REFUTED law through a generated role is a role_defect unless its replay
confirms (then candidate_role_unconfirmed: a real behaviour on an input the role chose, which a person must judge);
a REFUTED law through hand roles whose replay does not confirm is a model_defect. PROVED and UNKNOWN are never
findings.
"""
from __future__ import annotations

import re

GORC = re.compile(r"^L_par_gorc_(.+)_[^_]+_[^_]+$")


def index(manifest: dict | None) -> dict:
    out = {}
    for r in (manifest or {}).get("roles") or []:
        out[(r["sidecar"], r["id"])] = r["roles_source"]
    return out


def roles_source(law: dict, manifest: dict | None, milestone: str, typed: str = "hand") -> str:
    ix = index(manifest)
    facts = str(law.get("facts") or "")
    sub = law.get("subform")
    m = re.match(rf"^gen/{re.escape(milestone)}/(codec|goops)/([^/]+)\.json$", facts)
    if m:
        side = "link" if m.group(1) == "codec" else "go_ops"
        return ix.get((side, m.group(2)), "hand")
    if sub in ("go_round_trip", "go_branch"):
        return ix.get(("go_laws", "document"), "hand")
    if sub == "go_recompute":
        lid = str(law.get("law_id") or "")
        for (side, rid), src in sorted(ix.items()):
            if side == "go_laws" and lid.startswith(f"L_par_gorc_{rid}_"):
                return src
        return "hand"
    return typed


def classify(status: str | None, replay: str | None, source: str) -> str:
    if status != "REFUTED":
        return {"PROVED": "proved", "UNKNOWN": "unknown"}.get(str(status), "undecided")
    confirmed = replay == "confirmed"
    if source == "hand":
        return "finding" if confirmed else "model_defect"
    return "candidate_role_unconfirmed" if confirmed else "role_defect"
