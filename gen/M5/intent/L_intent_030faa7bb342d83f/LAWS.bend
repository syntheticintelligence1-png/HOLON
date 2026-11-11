import Base
import ../model/Cf2d128.bend as M

law cl_l_intent_030faa7bb342d83f:
  exs s: M.St
  exs x: M.X_pause
  {Bool.or(Bool.not(U32.is_eq(M.chk_pause(s, x), 0)), M.w_eq(M.x_pause_caller(x), M.st_owner(s))) != True{} : Bool}
