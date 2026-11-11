"""I57's instrument (pinned at the I57 prereg): what I57's tests need, written apart from holon/.

It assembles L9's inputs on its own (records from the working tree, the module records, the admitted observation
sets, the sensitivity pairs with their replay recomputed from the observations) and hands them to tests_m5/_i54.py's
reference l9, which is I54's definition. Nothing here imports holon/.

  admitted(doc, tool)        the lead's condition G3: (bool, why) for one observation set
  replay(law, params, items) definitions.replay of the key I57: 'passed', 'failed' or 'absent'
  l9_inputs(root)            the inputs document of definitions.L9, assembled from files
  hatches(text)              the Bend escape hatches a generated file must not hold (AGENTS rule 3)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from tests_m5._m5 import ROOT, file_sha256, load_json

KEY = "I57"
LIB = ROOT / "spec" / "M5" / "lib"
OBS_DIR = ROOT / "results" / "M5" / "env" / "observations"
SETS = ("obs-da-beacon", "obs-fetch-archive", "obs-l1-depth")
LAW_IDS = ("L_env_fact_da_always", "L_env_fact_da_window", "L_env_fact_fetch", "L_env_undo_reorg")
CHECKED = "ALL PROOFS CHECK"


def modules() -> list[dict]:
    return load_json(LIB / "I57_modules.json")["modules"]


def laws() -> list[dict]:
    return load_json(LIB / "I57_laws.json")["classes"]


def plan() -> dict:
    return load_json(LIB / "I57_observe_plan.json")


def read_set(name: str, root: Path = ROOT) -> dict | None:
    p = root / "results" / "M5" / "env" / "observations" / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def _allowed_reads(pl: dict) -> list[re.Pattern]:
    src = "|".join(re.escape(u) for u in sorted(pl["sources"].values()))
    return [re.compile(r"^FILE [A-Za-z0-9_./-]+(#[A-Za-z0-9_,]+)?$"),
            re.compile(rf"^GET ({src})/\S+$"),
            re.compile(rf"^RPC ({src}) eth_[A-Za-z]+$")]


def admitted(doc: dict | None, tool: dict) -> tuple[bool, str]:
    """The key's observation_tool.rule for one set document."""
    if doc is None:
        return False, "absent"
    if doc.get("producer") != tool["producer"]:
        return False, f"producer {doc.get('producer')!r} is not the pinned tool's"
    if doc.get("source_sha256") != tool["sha256"]:
        return False, "source_sha256 is not the pinned tool's"
    pats = _allowed_reads(plan())
    bad = [r for r in doc.get("reads") or [] if not any(p.match(r) for p in pats)]
    if bad or not doc.get("reads"):
        return False, f"reads outside the tool's forms: {bad or 'none recorded'}"
    if "FILE spec/M5/lib/I57_modules.json" in doc["reads"]:
        return False, "the set read the module records"
    return True, "admitted"


def replay(law: str, params: dict, items: list[dict]) -> str:
    if law == "L_env_fact_da_window":
        reg = [o for o in items if o["q"] - o["t"] <= params["W"]]
        return "absent" if not reg else ("passed" if all(o["observed"] for o in reg) else "failed")
    if law == "L_env_fact_da_always":
        reg = [o for o in items if o["q"] - o["t"] > params["W"]]
        return "absent" if not reg else ("passed" if any(not o["observed"] for o in reg) else "failed")
    if law == "L_env_fact_fetch":
        reg = [o for o in items if o["committed"]]
        return "absent" if not reg else ("passed" if all(o["observed"] for o in reg) else "failed")
    if law == "L_env_undo_reorg":
        reg = [o for o in items if o["head"] - o["t"] >= params["d"]]
        return "absent" if not reg else ("passed" if all(o["observed"] for o in reg) else "failed")
    raise KeyError(law)


def records(root: Path = ROOT, milestones=("M2", "M3", "M5")) -> list[dict]:
    out = []
    for m in milestones:
        for p in sorted((root / "results" / m).glob("L_*.json")):
            out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def checked(ev) -> bool:
    return isinstance(ev, dict) and ev.get("marker") == CHECKED and ev.get("law_present") is True


def sensitivity(root: Path, tool: dict) -> list[dict]:
    """One pair per I57 law, from its record's two forms; replay from the admitted sets of its module."""
    mods = {m["id"]: m for m in modules()}
    pairs = []
    for cls in laws():
        p = root / "results" / "M5" / f"{cls['id']}.json"
        if not p.is_file():
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        m = mods[cls["module"]]
        items = []
        for s in m["observations"]:
            doc = read_set(s, root)
            if admitted(doc, tool)[0]:
                items.extend(doc["items"])
        pairs.append({"law": cls["id"], "module": m["id"], "status_axiom": rec["axiom_form"]["status"],
                      "status_module": rec["status"], "replay": replay(cls["id"], m["parameters"], items),
                      "evidence": rec["evidence"]})
    return pairs


def l9_inputs(root: Path, key: dict) -> dict:
    tool = key["thresholds"]["observation_tool"]
    sets = []
    for s in SETS:
        doc = read_set(s, root)
        if admitted(doc, tool)[0]:
            sets.append(doc)
    prereg = load_json(root / "spec" / "M5" / "preregistration.json")
    return {"records": records(root), "classification": load_json(LIB / "environment_classes.json"),
            "modules": modules(), "observation_sets": sets, "sensitivity": sensitivity(root, tool),
            "base_dependent": prereg["base"]["l9_dependent"],
            "pinned_parameters": key["thresholds"]["pinned_parameters"]}


HATCHES = (re.compile(r"\?[A-Za-z_]"), re.compile(r"@unsafe"), re.compile(r"\bdef\s+[A-Za-z_.]+\?\s*\("),
           re.compile(r"import\s+\"[^\"]*\.(c|js)\""))


def hatches(text: str) -> list[str]:
    return [p.pattern for p in HATCHES if p.search(text)]


def tool_sha() -> str:
    return file_sha256(LIB / "I57_observe.py")
