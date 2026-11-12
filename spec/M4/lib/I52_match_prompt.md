A known software defect is described below, followed by findings that a tool reported near the defect's code. Decide
which findings describe this defect: the finding states (or directly implies) the same wrong behaviour at the same
place, not merely some other issue in the same code. A finding about a different problem nearby does not describe it.

The defect:
{{DEFECT}}

The findings (JSON, one per line):
{{FINDINGS}}

Answer with exactly one JSON object and nothing else: {"describes": ["<finding id>", ...]} listing the ids of the
findings that describe the defect (an empty list if none does).
