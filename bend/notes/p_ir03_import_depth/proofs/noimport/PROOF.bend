# no law imported (audit F-M2-07): apart from its LAWS.bend, Bend's "PROOF.bend must import ./LAWS.bend" rule does
# not apply, so this file checks vacuously; holon.mpipeline.law_import_problem is what rejects it
import Base
import ../../model/m.bend as M

def helper() -> Nat:
  0n
