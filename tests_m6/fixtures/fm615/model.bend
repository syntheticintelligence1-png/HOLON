# F-M6-15 planted model (tests_m6/test_fm615_unbound_precheck.py): a synthetic codec-shaped model. It defines the
# record carrier R_Rec (as holon.gen.linked writes R_<carrier>), and a reader get0 over it. It intentionally
# defines no type named `Rec`: a pre-check that binds `R_Rec` (the name the emitter writes) resolves, one that binds
# `Rec` (a name no model defines) does not. Not a target; never extracted or replayed.
import Base

type R_Rec is Data:
  R_Rec{a_0: U32, a_1: U32}

def get0(r: R_Rec) -> U32:
  match r:
    case R_Rec{a_0, a_1}:
      a_0

def eq0(x: R_Rec, y: R_Rec) -> Bool:
  U32.is_eq(get0(x), get0(y))
