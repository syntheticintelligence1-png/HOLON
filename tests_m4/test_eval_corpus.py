"""I48 corpus and blind-classification acceptance, red until acquisition."""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

from tests_m4._i48 import SHA, check_bundle_syntax, corpus, git, inside, instrument, lex_source, load


def code_lines(diff: str) -> list[str]:
    """Exclude patch headers, empty and comment-only changes."""
    return [line for line in diff.splitlines()
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
            and line[1:].strip() and not line[1:].lstrip().startswith(
                ("//", "/*", "*", "*/", "#"))]


class TestCorpusInstrument(unittest.TestCase):
    def test_preregistered_contract(self):
        prediction = load("spec/M4/predictions.json")["iterations"]["I48"]
        self.assertEqual(prediction["tests"], [
            "tests_m4/test_eval_corpus.py", "tests_m4/test_eval_renaming.py",
            "tests_m4/test_eval_controls.py"
        ])
        self.assertEqual(prediction["outcome_paths"], [
            "spec/eval/corpus.json", "spec/eval/controls.json", "spec/eval/I48/",
            "gen/M4/I48/", "results/M4/I48/", "holon/eval/",
            "docs/iterations/I48.md"
        ])
        self.assertEqual(prediction["instrument"], "spec/M4/lib/I48/instrument.json")
        rules = instrument()["corpus_rules"]
        self.assertEqual((rules["min_defects"], rules["min_systems"]), (20, 3))
        self.assertTrue(rules["require_non_rollup_system"])
        self.assertEqual(rules["allowed_languages"], ["go", "solidity"])
        self.assertEqual(rules["external_clone_cache_dir"],
                         "/home/factory-user/.holon/corpus_m4/clones")
        systems = {x["system_id"]: x for x in rules["candidate_systems"]}
        self.assertEqual(set(systems), {"morph-l2/morph", "ethereum/go-ethereum",
                                        "Vectorized/solady", "OpenZeppelin/openzeppelin-contracts"})
        self.assertTrue(systems["ethereum/go-ethereum"]["is_non_rollup"])
        self.assertEqual(rules["distinctness_key"], ["repo_url", "fix_sha", "primary_file"])
        selection = instrument()["corpus_protocol"]["deterministic_selection"]
        self.assertEqual(selection["target_count"], 20)
        self.assertEqual(selection["system_quotas"], {
            "morph-l2/morph": 8, "ethereum/go-ethereum": 6,
            "Vectorized/solady": 3, "OpenZeppelin/openzeppelin-contracts": 3})
        self.assertEqual((selection["min_non_rollup_systems"],
                          selection["min_non_rollup_defects"]), (2, 12))
        self.assertNotIn("candidate_specification_table", rules)
        for command in ("git cat-file -e", "git rev-parse <fix_sha>^1",
                        "parseable", "gen/M4/I48/bundles/<defect_id>/"):
            self.assertIn(command, rules["sampling_and_stopping_rule"])
        self.assertIn("source_files", rules["required_entry_fields"])


class TestCorpusOutcome(unittest.TestCase):
    def test_verified_corpus(self):
        rules = instrument()["corpus_rules"]
        selection = instrument()["corpus_protocol"]["deterministic_selection"]
        entries = corpus()
        report = load(selection["verification_path"])
        self.assertGreaterEqual(len(entries), selection["target_count"])
        self.assertEqual(entries, sorted(entries, key=lambda x: (x["system"], x["defect_id"])))
        self.assertGreaterEqual(len({e["system"] for e in entries}), rules["min_systems"])
        non_rollup = [e for e in entries if e["system"] != "morph-l2/morph"]
        self.assertGreaterEqual(len({e["system"] for e in non_rollup}), 2)
        self.assertGreaterEqual(len(non_rollup), 12)
        for system, quota in selection["system_quotas"].items():
            self.assertGreaterEqual(sum(e["system"] == system for e in entries), quota)
        evaluated = report["evaluated_candidates"]
        self.assertTrue(evaluated)
        self.assertEqual(sum(bool(c["accepted"]) for c in evaluated), len(entries))
        self.assertEqual({(c["system"], c["fix_sha"]) for c in evaluated if c["accepted"]},
                         {(e["system"], e["fix_sha"]) for e in entries})
        accepted = {(c["system"], c["fix_sha"]): c for c in evaluated if c["accepted"]}
        for candidate in evaluated:
            if not candidate["accepted"]:
                self.assertIn(candidate["disqualification_reason"],
                              selection["disqualification_reasons"])
            else:
                self.assertNotIn("disqualification_reason", candidate)
        # Compare the recorded traversal prefix with the actual pinned history.
        for system in selection["system_quotas"]:
            sample = next(e for e in entries if e["system"] == system)
            history = report["repositories"][system]
            repo = Path(sample["clone_path"])
            head = history["resolved_head_sha"]
            self.assertEqual(git(repo, "rev-parse", history["pinned_ref"]).stdout.strip().decode(), head)
            log = git(repo, "log", "--topo-order", "--date-order", "--format=%H", head)
            self.assertEqual(log.returncode, 0)
            commits = log.stdout.decode().splitlines()
            candidates = [c for c in evaluated if c["system"] == system]
            indices = [commits.index(c["fix_sha"]) for c in candidates]
            self.assertEqual(indices, sorted(indices), system)
            self.assertEqual(len(indices), len(set(indices)))
            self.assertTrue(candidates or history.get("exhausted"), system)
            pattern = re.compile(selection["defect_fix_regex"], re.IGNORECASE)
            stop = indices[-1] if indices else len(commits) - 1
            matching = []
            for sha in commits[:stop + 1]:
                message = git(repo, "show", "-s", "--format=%B", sha)
                self.assertEqual(message.returncode, 0)
                if pattern.search(message.stdout.decode(errors="replace")):
                    matching.append(sha)
            self.assertEqual([c["fix_sha"] for c in candidates], matching,
                             f"Unlogged eligible commits in {system}")
            self.assertEqual(sum(c["accepted"] for c in candidates),
                             selection["system_quotas"][system] if not history.get("exhausted")
                             else sum(e["system"] == system for e in entries))
            if history.get("exhausted"):
                self.assertEqual(stop, len(commits) - 1)
        self.assertEqual(len({e["defect_id"] for e in entries}), len(entries))
        self.assertEqual(len({(e["repo_url"], e["fix_sha"]) for e in entries}), len(entries))
        self.assertEqual(len({tuple(e[k] for k in rules["distinctness_key"]) for e in entries}),
                         len(entries))
        candidates = {s["system_id"]: s for s in rules["candidate_systems"]}
        for e in entries:
            with self.subTest(defect=e["defect_id"]):
                self.assertEqual(accepted[(e["system"], e["fix_sha"])]["pre_fix_sha"],
                                 e["pre_fix_sha"])
                self.assertTrue(set(rules["required_entry_fields"]) <= e.keys())
                self.assertIn(e["system"], candidates)
                self.assertEqual((e["repo_url"], e["is_non_rollup"]),
                                 (candidates[e["system"]]["repo_url"],
                                  candidates[e["system"]]["is_non_rollup"]))
                self.assertIn(e["language"], candidates[e["system"]]["languages"])
                self.assertTrue(e["public_evidence"])
                self.assertTrue(e["defect_summary"])
                self.assertTrue(e["repo_url"].startswith("https://github.com/"))
                self.assertTrue(e["primary_file"].endswith(
                    ".go" if e["language"] == "go" else ".sol"))
                repo = Path(e["clone_path"]).resolve()
                permitted = Path(rules["external_clone_cache_dir"]).resolve()
                local = candidates[e["system"]].get("local_reference")
                self.assertTrue(repo.is_relative_to(permitted) or
                                (local and repo == Path(local).resolve()), repo)
                self.assertEqual(git(repo, "rev-parse", "--is-inside-work-tree").stdout.strip(), b"true")
                for rev in ("pre_fix_sha", "fix_sha"):
                    self.assertRegex(e[rev], SHA)
                    self.assertEqual(git(repo, "cat-file", "-e", f"{e[rev]}^{{commit}}").returncode, 0)
                self.assertEqual(git(repo, "rev-parse", f"{e['fix_sha']}^1").stdout.strip().decode(),
                                 e["pre_fix_sha"])
                self.assertIn(e["primary_file"], e["source_files"])
                self.assertTrue(1 <= len(e["source_files"]) <= 3)
                self.assertTrue(all(f.endswith(".go" if e["language"] == "go" else ".sol")
                                    and not re.search(r"(_test\.go|Test\.sol|\.t\.sol|mock)", f,
                                                      re.IGNORECASE)
                                    for f in e["source_files"]))
                diff = git(repo, "diff", "--unified=0", e["pre_fix_sha"], e["fix_sha"],
                           "--", *e["source_files"])
                self.assertEqual(diff.returncode, 0)
                self.assertTrue(code_lines(diff.stdout.decode(errors="replace")),
                                "No non-comment source change")
                bundle = inside(e["source_bundle"], f"gen/M4/I48/bundles/{e['defect_id']}")
                renamed_bundle = inside(e["renamed_bundle_dir"],
                                        f"gen/M4/I48/renamed/{e['defect_id']}")
                self.assertTrue(bundle.is_dir())
                self.assertTrue(any(
                    [token for token in lex_source((bundle / "pre_fix" / file).read_text(),
                                                   e["language"]) if token[0] not in {"space", "comment"}]
                    != [token for token in lex_source((bundle / "fix" / file).read_text(),
                                                      e["language"]) if token[0] not in {"space", "comment"}]
                    for file in e["source_files"]), "Comment/whitespace-only bundle diff")
                for rev, name in (("pre_fix_sha", "pre_fix"), ("fix_sha", "fix")):
                    files = []
                    for relative in e["source_files"]:
                        source = bundle / name / relative
                        self.assertTrue(source.is_file(), f"Missing source: {source}")
                        actual = git(repo, "show", f"{e[rev]}:{relative}")
                        self.assertEqual(actual.returncode, 0)
                        self.assertEqual(source.read_bytes(), actual.stdout)
                        files.append(source)
                    check_bundle_syntax(e["language"], files)
                    check_bundle_syntax(e["language"],
                                        [renamed_bundle / name / file for file in e["source_files"]])
        # Parser evidence is required for both revisions, not merely a file suffix.
        self.assertEqual(set(report["defects"]), {e["defect_id"] for e in entries})
        for e in entries:
            checks = report["defects"][e["defect_id"]]
            for rev in ("pre_fix", "fix"):
                self.assertTrue(checks[rev]["parse_ok"])
                self.assertTrue(checks[rev]["parser"])
                bundle = inside(e["source_bundle"], f"gen/M4/I48/bundles/{e['defect_id']}")
                self.assertEqual(checks[rev]["source_sha256"],
                                 {f: hashlib.sha256((bundle / rev / f).read_bytes()).hexdigest()
                                  for f in e["source_files"]})

    def test_blind_classification(self):
        entries = corpus()
        rules = instrument()["blind_labeling_rules"]
        ids = {e["defect_id"] for e in entries}
        digests = []
        for e in sorted(entries, key=lambda row: row["defect_id"]):
            defect_id = e["defect_id"]
            packet = load(f"spec/eval/I48/packets/{defect_id}.json")
            packet_path = inside(f"spec/eval/I48/packets/{defect_id}.json", "spec/eval/I48/packets")
            digests.append(hashlib.sha256(packet_path.read_bytes()).hexdigest())
            self.assertEqual(set(packet), set(rules["packet_fields_only"]))
            for key in ("defect_id", "pre_fix_sha", "fix_sha", "language", "source_files"):
                self.assertEqual(packet["defect_metadata"][key], e[key])
            self.assertTrue(packet["commit_message"])
            bundle = inside(e["source_bundle"], f"gen/M4/I48/bundles/{defect_id}")
            source = "\n".join((bundle / "pre_fix" / file).read_text()
                               for file in e["source_files"])
            self.assertTrue(packet["pre_fix_source_excerpt"])
            self.assertIn(packet["pre_fix_source_excerpt"], source)
            actual = git(Path(e["clone_path"]), "diff", e["pre_fix_sha"], e["fix_sha"],
                         "--", *e["source_files"])
            self.assertEqual(actual.returncode, 0)
            self.assertTrue(code_lines(packet["fix_diff"]))
            self.assertEqual(packet["fix_diff"].strip(), actual.stdout.decode().strip())
            payload = json.dumps(packet)
            def keys(value):
                if isinstance(value, dict):
                    for key, nested in value.items():
                        yield key
                        yield from keys(nested)
                elif isinstance(value, list):
                    for nested in value:
                        yield from keys(nested)
            for forbidden in rules["forbidden_packet_tokens"]:
                self.assertFalse(any(forbidden.lower() in key.lower() for key in keys(packet)),
                                 (defect_id, forbidden))
                self.assertIsNone(re.search(r"(?<![A-Za-z_])" + re.escape(forbidden) +
                                            r"(?![A-Za-z_])", payload, re.IGNORECASE),
                                  (defect_id, forbidden))
            self.assertEqual(packet["neutral_classification_rubric"], rules["neutral_packet_rubric"])
        digest = hashlib.sha256("".join(sorted(digests)).encode()).hexdigest()
        raters = [load(p) for p in rules["raw_paths"]]
        self.assertNotEqual(raters[0]["session_id"], raters[1]["session_id"])
        required = set(rules["raw_session_fields"])
        for raw in raters:
            metadata = raw["session_metadata"]
            self.assertTrue(set(rules["session_metadata_fields"]) <= metadata.keys())
            self.assertEqual(metadata["packet_manifest_sha256"], digest)
            self.assertEqual(metadata["completed_defect_count"], len(entries))
            self.assertTrue(metadata["isolation_mode"])
            self.assertTrue(required <= raw.keys())
            self.assertTrue(all(raw[k] for k in ("session_id", "model", "reasoning_effort",
                                                "provider_family")))
            self.assertIsInstance(raw["same_family_limitation_disclosed"], bool)
            self.assertEqual(set(raw["labels"]), ids)
            for vote in raw["labels"].values():
                self.assertIn(vote["label"], rules["allowed_labels"])
                self.assertIn(vote["confidence"], rules["confidence_levels"])
        self.assertNotEqual(raters[0]["session_metadata"]["rater_id"],
                            raters[1]["session_metadata"]["rater_id"])
        if raters[0]["provider_family"] == raters[1]["provider_family"]:
            self.assertTrue(all(r["same_family_limitation_disclosed"] for r in raters))
        result = load(rules["adjudication_path"])
        self.assertEqual(set(result["defects"]), ids)
        pairs = [(raters[0]["labels"][i]["label"], raters[1]["labels"][i]["label"])
                 for i in sorted(ids)]
        n = len(pairs)
        observed = sum(a == b for a, b in pairs) / n
        chance = sum(sum(a == c for a, _ in pairs) * sum(b == c for _, b in pairs)
                     for c in rules["allowed_labels"]) / (n * n)
        kappa = 1.0 if chance == 1 and observed == 1 else (observed - chance) / (1 - chance)
        self.assertAlmostEqual(result["raw_agreement_rate"], observed)
        self.assertAlmostEqual(result["cohen_kappa"], kappa)
        for i, (a, b) in zip(sorted(ids), pairs):
            row = result["defects"][i]
            self.assertEqual((row["rater_a_label"], row["rater_b_label"], row["agreement"]),
                             (a, b, a == b))
            self.assertTrue(row["adjudication_rationale"])
            self.assertEqual(row["final_label"], row["primary_rule"])
            if a != b and "low" in (raters[0]["labels"][i]["confidence"],
                                    raters[1]["labels"][i]["confidence"]):
                self.assertEqual(row["primary_rule"], "UNCERTAIN")
            else:
                self.assertIn(row["primary_rule"], rules["allowed_labels"])
            if all(r["labels"][i]["confidence"] in {"high", "medium"} for r in raters):
                if row["primary_rule"] not in {a, b}:
                    self.assertTrue(any(clause in row["adjudication_rationale"]
                                        for clause in instrument()["labeling_rubric"]["tie_break_clauses"]),
                                    i)


if __name__ == "__main__":
    unittest.main()
