"""python -m holon eval label --role a|b|adjudicator --model NAME [--root DIR] (I48 rule C5): one labeller's run.

Prompts. One prompt per (entry, role): the frozen template (spec/M4/lib/labeller_prompt.md, or adjudicator_prompt.md)
with each {{SLOT}} filled in one pass over the template (an inserted value is never scanned again): RULE_SHEET the rule
sheet's text, ENTRY the entry id, TITLE, DESCRIPTION, SOURCES ("- <kind>: <url>" per source), DIFF the entry's fix
diff (gitfacts.fix_diff over commit_facts' diff_files) under the protocol's cap, and for the adjudicator LABEL_A and
LABEL_B (json.dumps(label, indent=2, sort_keys=True, ensure_ascii=False)). The cap: a diff of at most 60000 characters
is kept whole; else its longest prefix of whole lines of at most 60000 characters, then the line
"[diff truncated by the protocol: <k> of <m> lines shown]".

Invocation (the protocol's labelling_invocation). Each prompt runs in one fresh process: the frozen argv with
<system_prompt> and <model> filled in, the prompt on stdin (UTF-8), a fresh empty working directory from
tempfile.mkdtemp(prefix="label-", dir="/tmp") removed afterwards, the build's environment without env_removed, and a
600 s timeout. Each attempt records the CLI's JSON output reduced to is_error, num_turns, result, session_id and subtype
(a missing key is null; every key is null when the output is not one JSON object, as after a timeout) and its outcome:
ok (is_error false, num_turns 1, result parsing to a label), else the first failing of cli_error, turns, unparsable and
invalid. Retry rule: a cli_error attempt is run again after 60 s and does not count, at most 5 of them; a counted
attempt that fails is followed by one more counted attempt; the attempts stop at the first ok one, the second counted
one or the fifth cli_error one. The label is the last attempt's when it is ok, else null.

Model checks (strict: both models are known before any labelling). The model a call used is read from the keys of
the CLI JSON's modelUsage. `python -m holon eval label --observe --tag A|B --model NAME` makes exactly one call of the
frozen invocation with a fixed synthetic prompt (no corpus entry) and records the single model it reports for the tag
in ~/.holon/eval/labellers.json, never in the repository (no model name is printed); it refuses when the call reports
zero or several models, when the tag already holds a different model, or when A and B would be the same model. A
labelling run (--role) refuses to start unless both tags are recorded and differ; every call is then checked against
its role's tag (a and the adjudicator against A, b against B), and the run is refused (nothing written for the prompt
in flight) when a call that answered reports other than exactly one model or a model other than its tag's. The label
file records the checks (one_model_per_role, a_differs_from_b, adjudicator_is_a) as true because both models were
recorded, and differ, before the run, and every call of the run matched its tag.

Order and resumption. a and b label every entry of spec/eval/corpus.json in corpus order; the adjudicator labels exactly
the entries whose a and b labels are both non-null with different primaries (a.json and b.json complete). The label
file is written after every prompt; a run over a partly written file keeps its recorded labels verbatim (their prompts
must render to the recorded sha256) and continues with the next entry; a complete file is never run again.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import common
from .common import Refused, dumps

LABELS = Path("spec") / "eval" / "labels"
CORPUS = Path("spec") / "eval" / "corpus.json"
STORE = common.HOME / "labellers.json"
DIFF_CAP = 60000
CLI_KEYS = ("is_error", "num_turns", "result", "session_id", "subtype")
LABEL_KEYS = ("justification", "primary", "secondary", "subform")
ROLES = ("a", "b", "adjudicator")
LABELLER = {"a": "labeller-a", "b": "labeller-b", "adjudicator": "adjudicator"}
RETRY_WAIT = 60
MAX_CLI_ERRORS = 5
MAX_COUNTED = 2
_SLOT = re.compile(r"\{\{([A-Z_]+)\}\}")


# ---------------------------------------------------------------------------------------------- prompts
def cap_diff(diff: str) -> str:
    if len(diff) <= DIFF_CAP:
        return diff
    lines = _split_lf(diff)
    kept, size = 0, 0
    for line in lines:
        if size + len(line) > DIFF_CAP:
            break
        size += len(line)
        kept += 1
    return "".join(lines[:kept]) + f"[diff truncated by the protocol: {kept} of {len(lines)} lines shown]\n"


def _split_lf(text: str) -> list[str]:
    """Lines split at "\\n" only (each with its newline; a last line without one is a line too)."""
    out, start = [], 0
    while start < len(text):
        i = text.find("\n", start)
        end = len(text) if i < 0 else i + 1
        out.append(text[start:end])
        start = end
    return out


def template(role: str) -> Path:
    return common.LIB / ("adjudicator_prompt.md" if role == "adjudicator" else "labeller_prompt.md")


def render(role: str, entry: dict, diff: str, labels: dict | None = None) -> str:
    values = {
        "RULE_SHEET": (common.LIB / "rule_sheet.json").read_text(encoding="utf-8"),
        "ENTRY": entry["id"], "TITLE": entry["title"], "DESCRIPTION": entry["description"],
        "SOURCES": "\n".join(f"- {s['kind']}: {s['url']}" for s in entry["sources"]),
        "DIFF": cap_diff(diff),
    }
    if role == "adjudicator":
        values["LABEL_A"] = json.dumps(labels["a"], indent=2, sort_keys=True, ensure_ascii=False)
        values["LABEL_B"] = json.dumps(labels["b"], indent=2, sort_keys=True, ensure_ascii=False)

    def fill(m: re.Match) -> str:
        if m.group(1) not in values:
            raise Refused(f"{template(role).name}: unknown slot {m.group(0)}")
        return values[m.group(1)]
    return _SLOT.sub(fill, template(role).read_text(encoding="utf-8"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def entry_diff(entry: dict) -> str:
    from . import gitfacts
    facts = gitfacts.commit_facts(entry["repo"], entry["fix_commit"])
    if not facts.get("found"):
        raise Refused(f"{entry['id']}: {entry['repo']}@{entry['fix_commit']} is not reachable")
    return gitfacts.fix_diff(entry["repo"], entry["prefix_commit"], entry["fix_commit"], facts["diff_files"])


# ---------------------------------------------------------------------------------------------- responses
def parse_response(text: str) -> dict:
    """The JSON object of the whole response (surrounding whitespace aside), or of the text between a first line ```
    (or ```json) and a last line ```."""
    body = text.strip()
    lines = body.split("\n")
    if len(lines) >= 2 and lines[0].strip() in ("```", "```json") and lines[-1].strip() == "```":
        body = "\n".join(lines[1:-1])
    obj = json.loads(body)
    if not isinstance(obj, dict):
        raise ValueError("not a JSON object")
    return obj


def is_label(obj, categories: list[str]) -> bool:
    if not isinstance(obj, dict) or sorted(obj) != sorted(LABEL_KEYS):
        return False
    sec = obj["secondary"]
    return (isinstance(obj["primary"], str) and obj["primary"] in categories
            and (sec is None or (isinstance(sec, str) and sec in categories))
            and isinstance(obj["subform"], str)
            and isinstance(obj["justification"], str) and bool(obj["justification"].strip()))


def reduce_output(stdout: str | None) -> tuple[dict, dict | None]:
    """(the CLI JSON reduced to CLI_KEYS, the whole object or None)."""
    try:
        obj = json.loads(stdout) if stdout is not None else None
    except ValueError:
        obj = None
    if not isinstance(obj, dict):
        return {k: None for k in CLI_KEYS}, None
    return {k: obj.get(k) for k in CLI_KEYS}, obj


def outcome(cli: dict, categories: list[str]) -> str:
    if cli.get("is_error") is not False:
        return "cli_error"
    turns = cli.get("num_turns")
    if type(turns) is not int or turns != 1:
        return "turns"
    if not isinstance(cli.get("result"), str):
        return "unparsable"
    try:
        obj = parse_response(cli["result"])
    except (ValueError, RecursionError):
        return "unparsable"
    return "ok" if is_label(obj, categories) else "invalid"


# ---------------------------------------------------------------------------------------------- the process
def invocation() -> dict:
    return common.protocol()["labelling_invocation"]


def run_cli(argv: list[str], prompt: str, env: dict, cwd: str, timeout: int) -> str | None:
    """One fresh process; its stdout, or None after a timeout. (Replaced by a stub in tests.)"""
    try:
        p = subprocess.run(argv, input=prompt.encode("utf-8"), capture_output=True, cwd=cwd, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    except OSError as e:
        raise Refused(f"cannot start the labelling CLI {argv[0]!r}: {e}") from None
    return p.stdout.decode("utf-8", errors="replace")


def sleep(seconds: float) -> None:   # replaced by a stub in tests
    time.sleep(seconds)


def call(inv: dict, model: str, prompt: str) -> str | None:
    argv = [inv["system_prompt"] if a == "<system_prompt>" else model if a == "<model>" else a for a in inv["argv"]]
    env = {k: v for k, v in os.environ.items() if k not in inv["env_removed"]}
    cwd = tempfile.mkdtemp(prefix="label-", dir="/tmp")
    try:
        return run_cli(argv, prompt, env, cwd, int(inv["timeout_seconds"]))
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- model checks
class Models:
    """The model recorded per tag, kept outside the repository (STORE). Names never leave this object."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.seen = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except ValueError:
            raise Refused(f"{path} is not JSON") from None
        if not isinstance(self.seen, dict):
            raise Refused(f"{path} is not a JSON object")

    @staticmethod
    def reported(raw: dict | None) -> list[str]:
        usage = raw.get("modelUsage") if isinstance(raw, dict) else None
        return sorted(usage) if isinstance(usage, dict) else []

    def record(self, tag: str, raw: dict | None) -> None:
        """--observe: record the one model the call reports for the tag."""
        names = self.reported(raw)
        if len(names) != 1:
            raise Refused(f"the observation call reported {len(names)} models, not exactly one")
        name = names[0]
        if tag in self.seen and self.seen[tag] != name:
            raise Refused(f"tag {tag} already holds a different model")
        if any(t != tag and m == name for t, m in self.seen.items()):
            raise Refused(f"a_differs_from_b: tag {tag} would hold the model of another tag")
        if self.seen.get(tag) != name:
            self.seen[tag] = name
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(dumps(self.seen), encoding="utf-8")
            tmp.replace(self.path)

    def require(self, tags) -> None:
        """A labelling run starts only when every tag is recorded and the tags' models differ."""
        missing = sorted(t for t in set(tags) if t not in self.seen)
        if missing:
            raise Refused(f"no model recorded for tag(s) {missing}: run holon eval label --observe --tag T --model NAME "
                          "for each tag first")
        if len({self.seen[t] for t in set(tags)}) != len(set(tags)):
            raise Refused("a_differs_from_b: the recorded tags hold the same model")

    def check(self, role: str, tag: str, raw: dict | None) -> None:
        """One labelling call against its role's tag."""
        names = self.reported(raw)
        answered = isinstance(raw, dict) and raw.get("is_error") is False
        if not names and not answered:
            return   # a call that failed without reporting a model (cli_error): nothing to check
        if len(names) != 1:
            raise Refused(f"one_model_per_role: a call reported {len(names)} models, not exactly one")
        if names[0] != self.seen[tag]:
            raise Refused(f"one_model_per_role: a call of role {role} reported a model other than tag {tag}'s")


OBSERVE_PROMPT = ('This is a synthetic check of the labelling invocation, not a corpus entry. Answer with exactly '
                  'this JSON object and nothing else: {"primary": "none", "secondary": null, "subform": "observe", '
                  '"justification": "A synthetic observation call."}')


def observe(tag: str, model: str) -> int:
    inv = invocation()
    if tag not in set(inv["roles"].values()):
        raise Refused(f"unknown tag {tag!r}")
    models = Models(STORE)
    cli, raw = reduce_output(call(inv, model, OBSERVE_PROMPT))
    print(f"is_error: {json.dumps(cli['is_error'])}, num_turns: {json.dumps(cli['num_turns'])}")
    models.record(tag, raw)
    tags = sorted(set(inv["roles"].values()))
    known = [t for t in tags if t in models.seen]
    if len(known) == len(tags):
        print(f"recorded tag {tag}; all tags recorded, models differ: "
              f"{len({models.seen[t] for t in tags}) == len(tags)}")
    else:
        print(f"recorded tag {tag}; still unrecorded: {sorted(set(tags) - set(known))}")
    return 0


# ---------------------------------------------------------------------------------------------- one prompt
def attempts_for(prompt: str, inv: dict, model: str, models: Models, role: str,
                 categories: list[str]) -> list[dict]:
    out, cli_errors, counted = [], 0, 0
    while True:
        cli, raw = reduce_output(call(inv, model, prompt))
        models.check(role, inv["roles"][role], raw)
        o = outcome(cli, categories)
        out.append({"cli": cli, "outcome": o})
        if o == "ok":
            return out
        if o == "cli_error":
            cli_errors += 1
            if cli_errors == MAX_CLI_ERRORS:
                return out
            sleep(RETRY_WAIT)
        else:
            counted += 1
            if counted == MAX_COUNTED:
                return out


def label_record(entry_id: str, prompt: str, attempts: list[dict]) -> dict:
    last = attempts[-1]
    response = last["cli"]["result"]
    return {"entry": entry_id, "prompt_sha256": sha256_text(prompt), "attempts": attempts, "response": response,
            "label": parse_response(response) if last["outcome"] == "ok" else None}


# ---------------------------------------------------------------------------------------------- the run
def _labels_of(root: Path, who: str, ids: list[str]) -> dict:
    p = root / LABELS / f"{who}.json"
    if not p.exists():
        raise Refused(f"{p.relative_to(root)} is missing: the adjudicator runs after a and b")
    got = [x["entry"] for x in common.load_json(p)["labels"]]
    if got != ids:
        raise Refused(f"{p.relative_to(root)} does not label every entry in corpus order")
    return {x["entry"]: x["label"] for x in common.load_json(p)["labels"]}


def header(role: str, inv: dict) -> dict:
    return {"labeller": LABELLER[role], "role": role, "model_tag": inv["roles"][role], "family": "same",
            "tools": "none", "invocation": list(inv["argv"]),
            "system_prompt_sha256": sha256_text(inv["system_prompt"]),
            "checks": {"one_model_per_role": True, "a_differs_from_b": True, "adjudicator_is_a": True},
            "rule_sheet_sha256": common.sha256_file(common.LIB / "rule_sheet.json"),
            "prompt_template_sha256": common.sha256_file(template(role)), "labels": []}


def cli_label(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon eval label")
    ap.add_argument("--role", choices=ROLES)
    ap.add_argument("--observe", action="store_true", help="record the model one call reports for --tag")
    ap.add_argument("--tag")
    ap.add_argument("--model", required=True)
    ap.add_argument("--root", type=Path, default=common.ROOT)
    a = ap.parse_args(argv)
    if not a.model.strip():
        raise Refused("--model is empty")
    if a.observe:
        if a.role or not a.tag:
            raise Refused("--observe takes --tag and --model, not --role")
        return observe(a.tag, a.model)
    if not a.role or a.tag:
        raise Refused("a labelling run takes --role and --model (and no --tag)")
    root, role = a.root.resolve(), a.role
    if not (root / CORPUS).exists():
        raise Refused(f"{CORPUS} is missing under {root}: run holon eval select first")
    inv = invocation()
    categories = common.load_json(common.LIB / "rule_sheet.json")["categories"]
    entries = common.load_json(root / CORPUS)["entries"]
    ids = [e["id"] for e in entries]
    both = None
    if role == "adjudicator":
        la, lb = _labels_of(root, "a", ids), _labels_of(root, "b", ids)
        todo = [e for e in entries if la[e["id"]] and lb[e["id"]] and la[e["id"]]["primary"] != lb[e["id"]]["primary"]]
        both = {e["id"]: {"a": la[e["id"]], "b": lb[e["id"]]} for e in todo}
    else:
        todo = list(entries)
    out_path = root / LABELS / f"{role}.json"
    doc = header(role, inv)
    if out_path.exists():
        old = common.load_json(out_path)
        if {k: v for k, v in old.items() if k != "labels"} != {k: v for k, v in doc.items() if k != "labels"}:
            raise Refused(f"{out_path.relative_to(root)} was recorded under another invocation, template or sheet")
        done = [x["entry"] for x in old["labels"]]
        if done != [e["id"] for e in todo[:len(done)]]:
            raise Refused(f"{out_path.relative_to(root)} does not hold a prefix of the entries this role labels")
        if len(done) == len(todo):
            print(f"{out_path.relative_to(root)}: every entry is labelled already (a label is never re-run)")
            return 0
        doc["labels"] = old["labels"]
    models = Models(STORE)
    models.require(inv["roles"].values())
    diffs: dict[str, str] = {}
    for i, e in enumerate(todo):
        if e["id"] not in diffs:
            diffs[e["id"]] = entry_diff(e)
        prompt = render(role, e, diffs[e["id"]], both[e["id"]] if both else None)
        if i < len(doc["labels"]):
            if doc["labels"][i]["prompt_sha256"] != sha256_text(prompt):
                raise Refused(f"{e['id']}: the recorded prompt_sha256 is not the prompt's (inputs changed)")
            continue
        attempts = attempts_for(prompt, inv, a.model, models, role, categories)
        doc["labels"].append(label_record(e["id"], prompt, attempts))
        common.write_or_check(out_path, dumps(doc), False)
        print(f"{role} {e['id']}: {' '.join(t['outcome'] for t in attempts)}")
    from holon.schema import errors
    errs = errors(doc, common.load_json(common.LIB / "labels.schema.json"))
    if errs:
        print("the label file does not validate: " + "; ".join(errs[:10]), file=sys.stderr)
        return 1
    common.write_or_check(out_path, dumps(doc), False)
    print(f"wrote {out_path.relative_to(root)}: {len(doc['labels'])} labels, "
          f"{sum(x['label'] is None for x in doc['labels'])} null")
    return 0
