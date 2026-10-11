"""M2 fact assembly: compose a holon-facts/0.1 document purely from extraction output.

The assembler never reads facts/, spec/M1/facts/, links.json or any other
hand-written artefact (docs/M2_SPEC.md). Every fact key comes from an
extractor or is recorded as debt in the coverage document.
"""
