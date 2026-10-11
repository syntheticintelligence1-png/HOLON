"""holon.sorts: refined semantic sorts (whitepaper §5-§7) over holon-facts.

grammar   the sort grammar (§7.1) and parser/printer
rules     affine rules (§7.2), union formation (§7.4), principal/amount (§7.5), width (§7.6)
infer     inference over facts (§7.7): seeds -> assignment, writer provenance (§7.3), obligations
bendgen   sorts compiled to Bend nominal types with coercion obligations (§7.8), checked by bend
factsgen  the sorted facts: the inferred assignment plus ghost observers and the tau action, generated
lawgen    the SORT law class: obligations -> holon-ir/0.2 laws (spec/M3/sorts/laws), registry, predictions
canary    SORT canaries that Bend must reject semantically
"""
