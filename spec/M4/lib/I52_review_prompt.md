Review the source code in your working directory for defects: bugs that make the code behave wrongly, crash, lose
funds, halt or stall, accept what it should reject, reject what it should accept, or disagree with another part of the
same code. Read only files in your working directory. You have about {{MINUTES}} minutes of wall-clock time; the
process is stopped at the deadline and anything not yet answered is lost, so answer well before it.

The files under review:
{{FILES}}

Answer with exactly one JSON object and nothing else:
{"findings": [{"file": "<path as listed above>", "lines": [<first line>, <last line>], "kind": "<a short class name>",
"message": "<one or two sentences: what is wrong and how it shows>"}]}
List at most 20 findings, the most serious first. Line numbers are 1-based, of the files as they are in your working
directory. An empty list is a valid answer.
