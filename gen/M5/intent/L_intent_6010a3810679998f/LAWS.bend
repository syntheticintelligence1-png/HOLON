import Base
import ../model/C71e7a3.bend as M

law cl_l_intent_6010a3810679998f:
  exs s: M.St
  exs x: M.X_step
  {Bool.or(Bool.not(U32.is_eq(M.chk_step(s, x), 0)), M.w_ge(M.st_count(M.post_step(s, x)), M.st_count(s))) != True{} : Bool}
