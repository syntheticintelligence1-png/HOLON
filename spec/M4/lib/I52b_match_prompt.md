A function of a smart contract is named below, with five properties the function is expected to satisfy, followed by
findings that a tool reported in that function's code. For each property, decide which findings claim that the function
violates that property: the finding states (or directly implies) a wrong behaviour of this function that breaks the
property. A finding about a different problem, a style issue, a gas issue, or a pattern that is merely risky without a
stated wrong behaviour does not claim a violation. A finding may claim violations of several properties, or of none.

The function: {{ACTION}}

The properties:
{{OBLIGATIONS}}

The findings (JSON, one per line):
{{FINDINGS}}

Answer with exactly one JSON object and nothing else:
{"violates": {"DISCH": ["<finding id>", ...], "FACT": [...], "SORT": [...], "SYM": [...], "UNDO": [...]}}
listing, for each property, the ids of the findings that claim a violation of it (an empty list if none does).
