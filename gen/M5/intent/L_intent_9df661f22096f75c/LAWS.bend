import Base
import ../model/Cf10237.bend as M

law cl_l_intent_9df661f22096f75c:
  exs s: M.St
  exs x: M.X_fee
  {Bool.or(Bool.not(U32.is_eq(M.chk_fee(s, x), 0)), M.ip_le_pct(M.ret_fee(s, x), 2, M.x_fee_p_amount(x))) != True{} : Bool}
