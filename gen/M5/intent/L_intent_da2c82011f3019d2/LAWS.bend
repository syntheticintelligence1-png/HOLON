import Base
import ../model/C61fc01.bend as M

law cl_l_intent_da2c82011f3019d2:
  exs s: M.St
  exs x: M.X_step
  {Bool.or(Bool.not(U32.is_eq(M.chk_step(s, x), 0)), M.w_ge(M.st_count(M.post_step(s, x)), M.st_count(s))) != True{} : Bool}
