"""The intent lane (BUILD_PLAN §4 I55; whitepaper §5.10): normative documentation atomized into clause records with
exact source spans (atomize), reviewed clauses compiled into the INTENT law family over the factory's extracted model
(compile, extract, model), decided by Bend (run), and scored by I54's L10 definition (metrics). The key I55
(spec/M5/predictions/I55.json, thresholds.design) is the specification; tests_m5/test_m5_intent.py is the contract.

  python -m holon intent atomize|compile|requests|run|metrics [--root DIR] [--check] ...

Nothing here names a target or a control: names come from the documents read, and a control's id is an opaque
label taken from its file name.
"""
