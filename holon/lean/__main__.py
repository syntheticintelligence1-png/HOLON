"""python -m holon.lean --milestone M0|M1

`python -m holon lean --milestone ..` cannot be wired: holon/__main__.py is
frozen (M2_SPEC hard rules). This module provides the same entry point.
"""
from .runner import main

raise SystemExit(main())
