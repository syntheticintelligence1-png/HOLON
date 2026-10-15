You are adjudicating one label of an evaluation corpus (HOLON, I48). Two labellers, working independently from the same text, gave different primary rules for the defect below. You have no tools and no repository access: use only the text of this prompt. You cannot open the URLs below.

Your task: name the minimal rule that exposes the defect, using the rule sheet below. Read its "minimal" field first: the rule whose obligation, stated over the pre-fix code, the defect falsifies with the defect's own trigger as witness; when several rules apply, the one whose obligation names the fewest components, carriers and edges, ties broken in the sheet's tie order; "none" only when no rule's obligation is falsified. You may choose either labeller's rule or a third one; weigh their justifications against the sheet, not against each other's confidence.

## Rule sheet (spec/M4/lib/rule_sheet.json, verbatim)

{{RULE_SHEET}}

## The defect

Entry: {{ENTRY}}

Title (verbatim from its first source): {{TITLE}}

Description (a verbatim excerpt of its first source):

{{DESCRIPTION}}

Sources (URLs only):

{{SOURCES}}

## The fix (git diff from the pre-fix commit to the fix commit, over the changed source files)

```diff
{{DIFF}}
```

## The two labels

Labeller a:

{{LABEL_A}}

Labeller b:

{{LABEL_B}}

## Your answer

Answer with exactly one JSON object and nothing else, in the rule sheet's output form:

{"primary": "<one of the nine categories>", "secondary": "<another category, or null>", "subform": "<the sub-form>", "justification": "<two to five sentences>"}
