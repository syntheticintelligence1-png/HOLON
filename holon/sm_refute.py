"""Deterministic BFS refuter evaluated only by the compiled Bend model."""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

from . import model_eval
from .sm_emit import _assignments, _action_domains, emit_laws, parameter_assignments
from .sm_gen import _state_fields, _tag_ids, bend_model


def _compiled_checker_source(law, facts, facts_path, root):
    model = bend_model(facts)
    law_src = emit_laws(law, facts)
    body = law_src.split("\n", 3)[3]
    body = body.split(f"\nlaw {law['law_id'].lower()}:", 1)[0]
    body = body.replace("M.", "")
    return model + "\n" + body


def _state_key(state):
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def find_witness(law: dict, facts: dict, facts_path=None, root=None, max_depth=None) -> dict | None:
    """Find the shortest all-Ok trace reaching a state that falsifies the law."""
    root = Path(root) if root else model_eval.ROOT
    statement = law["statement"]
    k = int(max_depth if max_depth is not None else statement["bound"]["K"])
    source = _compiled_checker_source(law, facts, facts_path, root)
    model = model_eval.compile_sm_model(source, _state_fields(facts), root=root,
                                        cache_key=f"M1-{law['law_id']}")
    init = model_eval.eval_sm_jobs(model, [{"op": "init"}])[0]["state"]
    tags = _tag_ids(facts)
    tag_names = {value: name for name, value in tags.items()}
    queue = [(init, [])]
    visited = {_state_key(init)}
    sizes = [1]
    assignments = parameter_assignments(law, facts)
    actions = []
    for action in sorted(facts["actions"]):
        for params in _assignments(_action_domains(facts, action)):
            actions.append((action, params))

    for depth in range(k + 1):
        check_jobs = [{"op": "check", "fn": f"check_{law['law_id'].lower()}", "state": s}
                      for s, _ in queue]
        checks = model_eval.eval_sm_jobs(model, check_jobs)
        for ix, (state, trace) in enumerate(queue):
            if checks[ix]["value"] is True:
                continue
            assignment_jobs = [{"op": "check_assignment", "fn": f"check_{law['law_id'].lower()}_assignment",
                                "state": state, "index": j} for j in range(len(assignments))]
            evaluated = model_eval.eval_sm_jobs(model, assignment_jobs)
            failed = next((j for j, result in enumerate(evaluated) if result["value"] is False), None)
            if failed is None:
                raise RuntimeError(f"{law['law_id']}: check() false but no forall_params assignment fails")
            return {"witness": {"trace": trace, "forall_params": assignments[failed],
                                "final_state": state},
                    "depth": depth, "reach_sizes": sizes,
                    "model": model["artifact"]}
        if depth >= k:
            break
        jobs = []
        job_meta = []
        for state, trace in queue:
            for action, params in actions:
                jobs.append({"op": "step", "action": f"act_{action}", "state": state,
                             "params": list(params.values())})
                job_meta.append((state, trace, action, params))
        outcomes = model_eval.eval_sm_jobs(model, jobs)
        following = []
        layer_seen = set()
        for (state, trace, action, params), outcome in zip(job_meta, outcomes):
            if outcome["tag"] != "Ok":
                continue
            new_state = outcome["state"]
            key = _state_key(new_state)
            if key in visited or key in layer_seen:
                continue
            layer_seen.add(key)
            next_trace = trace + [{"action": action, "params": params, "outcome": "Ok"}]
            following.append((new_state, next_trace))
        visited.update(layer_seen)
        queue = following
        sizes.append(len(queue))
    return None


def measure_reach(facts: dict, depth: int, root=None) -> dict:
    """Measure exact unique-layer sizes using the compiled Bend reach function."""
    root = Path(root) if root else model_eval.ROOT
    source = bend_model(facts)
    cache = hashlib.sha256(source.encode()).hexdigest()[:16]
    model = model_eval.compile_sm_model(source, _state_fields(facts), root=root,
                                        cache_key=f"M1-reach-{cache}")
    jobs = [{"op": "reach", "depth": k} for k in range(depth + 1)]
    counts = [item["count"] for item in model_eval.eval_sm_jobs(model, jobs)]
    layers = [counts[0], *(counts[i] - counts[i - 1] for i in range(1, len(counts)))]
    return {"method": "compiled_bend_reach_k", "cumulative": counts, "per_layer": layers}
