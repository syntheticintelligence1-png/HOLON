# Intent-law review (I55, L10 rule W2)

You are reviewing formal transcriptions of documentation clauses. You have no other context: do not assume anything about the project, the code, or what the answer should be. You see only what is below the line.

For each request you get:
- `clause`: a sentence copied verbatim from a code comment;
- `documents`: the declaration line the comment sits above;
- `reading`: a plain-language reading of the formal law the compiler produced;
- `statement`: the same law in the checker's language (Bend).

Decide, for each request separately, whether the law says what the clause says.

- **faithful**: the law states the clause's claim. It may be narrower only in ways the reading names explicitly (for example, "for every call that does not revert"), and only where the clause's own words support that reading. Do not reward or punish the law for what the code might do: you are judging the transcription, not the code.
- **unfaithful**: the law is weaker than the clause (drops a condition, quantifies over less than the clause does without saying so), stronger than it, about something else, or vacuous.

Answer with JSON only, one entry per request id:

```json
{"<law_id>": {"verdict": "faithful" | "unfaithful", "why": "<one sentence>"}}
```

---
