"""Calibrate App. D's cost model of Bundle II's state-indexed cost site against forge gas (BUILD_PLAN I37's
deliverable; row I84 = I37b; rules K1-K5 of tests_m3/test_bundle2_laws.py). The work is holon.bundle2.laws_calibrate:

  python tools/calibrate_gas.py [--check] [--jobs N] [--work DIR]

Exit codes: 0 written (or --check reproduced), 1 --check differs, 2 refused, 3 a harness error.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from holon.bundle2.laws_calibrate import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
