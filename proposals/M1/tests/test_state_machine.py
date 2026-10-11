from __future__ import annotations

import hashlib
import itertools
import json
import random
import unittest
from pathlib import Path

from holon import model_eval, sm_emit, sm_gen
from holon.facts import load_facts
from holon.ir import statement_hash
from proposals.M1.tests.reference import rollup_ref

ROOT = Path(__file__).resolve().parents[3]
FACTS_PATH = ROOT / "proposals/M1/facts/rollup_sm.json"


class StateMachineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = load_facts(FACTS_PATH)
        cls.source = sm_gen.bend_model(cls.facts)
        cls.model = model_eval.compile_sm_model(
            cls.source, sm_gen._state_fields(cls.facts), root=ROOT,
            cache_key="M1-oracle-tests",
        )
        cls.tag_names = {value: name for name, value in sm_gen._tag_ids(cls.facts).items()}

    @staticmethod
    def _key(state):
        return json.dumps(state, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _actions():
        return {
            "addSubmitter": [{}],
            "challengeState": [{"i": i} for i in range(1, rollup_ref.N + 1)],
            "commitBatch": [{"numL1": n, "post": p} for n in (0, 1) for p in (1, 2)],
            "commitBatchWithProof": [{"numL1": n, "post": p} for n in (0, 1) for p in (1, 2)],
            "commitState": [{"numL1": n, "post": p} for n in (0, 1) for p in (1, 2)],
            "enqueue": [{}],
            "finalizeBatch": [{}],
            "proveState": [{"i": i} for i in range(1, rollup_ref.N + 1)],
            "revertBatch": [{"count": count, "idx": idx}
                            for count in range(1, rollup_ref.N + 1)
                            for idx in range(1, rollup_ref.N + 1)],
            "setPause": [{"b": b} for b in (0, 1)],
            "tick": [{"d": d} for d in (1, 2)],
        }

    def _assert_step_matches(self, state, oracle_state, action, params, actual):
        expected_tag, expected_state, revert_tag = rollup_ref.step(action, oracle_state, params)
        self.assertEqual(actual["tag"], expected_tag, (action, params, state))
        if expected_tag == "Ok":
            self.assertEqual(actual["state"], expected_state, (action, params))
            return actual["state"], expected_state
        if expected_tag == "Revert":
            self.assertEqual(self.tag_names[actual["id"]], revert_tag, (action, params))
            return state, expected_state
        return None

    def test_compiled_model_matches_independent_oracle_through_depth_three(self):
        init_model = model_eval.eval_sm_jobs(self.model, [{"op": "init"}])[0]["state"]
        init_oracle = rollup_ref.initial_state()
        self.assertEqual(init_model, init_oracle)
        actions = self._actions()
        frontier = [(init_model, init_oracle)]
        checked = 0
        for _depth in range(3):
            jobs = []
            edges = []
            for model_state, oracle_state in frontier:
                for action in sorted(actions):
                    for params in actions[action]:
                        jobs.append({"op": "step", "action": f"act_{action}",
                                     "state": model_state,
                                     "params": list(params.values())})
                        edges.append((model_state, oracle_state, action, params))
            outcomes = []
            for start in range(0, len(jobs), 400):
                outcomes.extend(model_eval.eval_sm_jobs(self.model, jobs[start:start + 400]))
            next_by_state = {}
            for edge, actual in zip(edges, outcomes):
                result = self._assert_step_matches(*edge, actual)
                checked += 1
                if result is not None:
                    next_by_state[self._key(result[0])] = result
            frontier = [next_by_state[key] for key in sorted(next_by_state)]
        self.assertGreater(checked, 100)

    def test_three_hundred_fixed_seed_random_traces(self):
        rng = random.Random(51838)
        actions = self._actions()
        names = sorted(actions)
        traces = []
        for _ in range(300):
            length = rng.randint(0, 12)
            traces.append([(name, rng.choice(actions[name]))
                           for name in (rng.choice(names) for _ in range(length))])
        model_states = [model_eval.eval_sm_jobs(self.model, [{"op": "init"}])[0]["state"]
                        for _ in traces]
        oracle_states = [rollup_ref.initial_state() for _ in traces]
        for depth in range(12):
            active = [(ix, trace[depth]) for ix, trace in enumerate(traces) if len(trace) > depth]
            if not active:
                break
            jobs = [{"op": "step", "action": f"act_{action}", "state": model_states[ix],
                     "params": list(params.values())}
                    for ix, (action, params) in active]
            outcomes = []
            for start in range(0, len(jobs), 400):
                outcomes.extend(model_eval.eval_sm_jobs(self.model, jobs[start:start + 400]))
            for (ix, (action, params)), actual in zip(active, outcomes):
                result = self._assert_step_matches(model_states[ix], oracle_states[ix],
                                                   action, params, actual)
                if result is not None:
                    model_states[ix], oracle_states[ix] = result

    def test_action_generation_registry_bounds_and_determinism(self):
        action_fns = sm_gen.action_functions(self.facts)
        self.assertEqual(action_fns, {f"act_{name}" for name in self.facts["actions"]})
        self.assertEqual(self.source, sm_gen.bend_model(self.facts))
        generated_model = ROOT / "gen/M1/model/rollup_sm.bend"
        if generated_model.exists():
            self.assertEqual(generated_model.read_text(), self.source)

        registry = json.loads((ROOT / "proposals/M1/laws/REGISTRY.json").read_text())
        laws = sorted((ROOT / "proposals/M1/laws").glob("L_*.json"))
        self.assertEqual({json.loads(path.read_text())["law_id"] for path in laws},
                         set(registry["laws"]))
        for law_path in laws:
            law = json.loads(law_path.read_text())
            self.assertEqual(statement_hash(law), registry["laws"][law["law_id"]])
        for relative, digest in registry["facts"].items():
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), digest)

        summary_path = ROOT / "results/M1/summary.json"
        if summary_path.exists():
            summary = json.loads(summary_path.read_text())
            for law_path in laws:
                law = json.loads(law_path.read_text())
                if law["statement"].get("kind") != "sm":
                    continue
                record = json.loads((ROOT / "results/M1" / f"{law['law_id']}.json").read_text())
                self.assertIn(record["status"], {"PROVED", "REFUTED", "UNKNOWN"})
                self.assertEqual(summary[law["law_id"]], record["status"])
                self.assertEqual(record["bound"]["N"], self.facts["config"]["N"])
                self.assertEqual(record["bound"]["K"], law["statement"]["bound"]["K"])
                self.assertEqual(record["revert_tag_ids"], sm_gen._tag_ids(self.facts))
                artifact = record["artifacts"]["laws"]
                if artifact:
                    emitted = Path(ROOT / artifact).read_text()
                    if record["status"] == "REFUTED":
                        self.assertEqual(emitted, sm_emit.emit_laws(
                            law, self.facts, counter_trace=record["witness"]["trace"]))
                    elif record["status"] == "PROVED":
                        self.assertEqual(emitted, sm_emit.emit_laws(law, self.facts))


if __name__ == "__main__":
    unittest.main()
