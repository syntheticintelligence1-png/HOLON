import Base
import ../model/Cacd06a.bend as M

law cl_l_intent_116d44eab1f4176c:
  exs s: M.St
  exs x: M.X_fee
  {Bool.or(Bool.not(U32.is_eq(M.chk_fee(s, x), 0)), M.ip_le_pct(M.ret_fee(s, x), 1, M.x_fee_p_amount(x))) != True{} : Bool}
