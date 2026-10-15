You are labelling one historical software defect for an evaluation corpus (HOLON, I48). You have no tools and no repository access: use only the text of this prompt. You cannot open the URLs below; they are listed so that you know where the description comes from. Do not guess what other labellers chose; nobody else's answer is shown to you.

Your task: name the minimal rule that exposes the defect, using the rule sheet below. Read its "minimal" field first: the rule whose obligation, stated over the pre-fix code, the defect falsifies with the defect's own trigger as witness; when several rules apply, the one whose obligation names the fewest components, carriers and edges, ties broken in the sheet's tie order; "none" only when no rule's obligation is falsified.

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

## Your answer

Answer with exactly one JSON object and nothing else, in the rule sheet's output form:

{"primary": "<one of the nine categories>", "secondary": "<another category, or null>", "subform": "<the sub-form>", "justification": "<two to five sentences>"}
