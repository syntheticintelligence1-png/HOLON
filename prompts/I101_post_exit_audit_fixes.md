# I101: the post-exit fixes of F-M3-37, F-M3-38 and F-M3-42

The lead's brief for I101 (2026-11-12), on the lead's `a3666ec5` (#164, the M4 stack's landing). The M3 exit
(docs/M3_EXIT.md) left 17 medium and 6 low findings open. The lead's triage of three of them says they are fixed after
the exit:
- F-M3-37 (round 8, medium, gate_evasion): the counted-round evidence rule reads headers only;
- F-M3-38 (round 8, low, gate_evasion): the rendered audit prompts state Q9's old counting rule;
- F-M3-42 (round 9, low, determinism): a subset `holon run --laws` deletes other laws' models and rewrites
  summary.json and deps.json to the subset.

## Rules for this key

- Read each finding's reproduction and suggested fix in `audit/M3_findings.jsonl`, and round 8's probe
  `audit/rounds/M3/round8/a7_hollow_round.py`. `audit/` files may be read, never edited: auditors' round files stay as
  their auditors wrote them, and the lead's triage lines change only in their status, fix_iteration and test fields.
- No generator closure changes. The pipeline's bytes are in committed records' generator_sha256
  (holon.records.generator_files, holon.profile.generator_files, the bundle-law closure). F-M3-42's fix wraps the run
  from outside them, as I47's holon/parallel.py does. No record and no law moves.
- F-M3-37:
  - (a) The evidence rule (spec/M3/lib/audit_evidence.json) gains each record's content: a ran A1 mutant, a ran A2 case,
    a4.json and packet.json valid against their schemas, the a4 laws exactly the packet's, the a4 counts their tally,
    and a non-empty packet. The two schemas are inputs of the prereg.
  - (b) A rebuild command, `holon audit evidence --rebuild`, checks the streak's a4.json and packet.json byte for byte
    against their targets, and CI runs it. Never `holon audit mutation --check` or `hostile-input --check`
    unattended: the A1 and A2 records are not rebuilt.
- F-M3-38: render the counting rule, the auditor fields and the evidence from the milestone's sidecars, and keep I87's
  rule where a milestone has none.
- F-M3-42: a run with `--laws` keeps every gen/<M>/model and gen/<M>/core file it does not regenerate, and merges
  summary.json and deps.json; a run without `--laws` is unchanged.
- Generated, target-agnostic (no target names in holon/), deterministic.
- The report, docs/iterations/I101.md, states each prediction's outcome; a miss is a result.
