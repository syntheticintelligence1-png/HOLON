import Base
import ../model/Cf10237.bend as M
import ./LAWS.bend as Laws

def ip_val() -> {Bool.or(Bool.not(U32.is_eq(M.chk_fee(M.St{M.W{0, 0, 0, 0, 0, 0, 0, 0}}, M.X_fee{M.W{35, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{36, 0, 0, 0, 0, 0, 0, 0}}), 0)), M.ip_le_pct(M.ret_fee(M.St{M.W{0, 0, 0, 0, 0, 0, 0, 0}}, M.X_fee{M.W{35, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{36, 0, 0, 0, 0, 0, 0, 0}}), 2, M.x_fee_p_amount(M.X_fee{M.W{35, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{36, 0, 0, 0, 0, 0, 0, 0}}))) == False{} : Bool}:
  {==}

def ip_flip(e: {Bool.or(Bool.not(U32.is_eq(M.chk_fee(M.St{M.W{0, 0, 0, 0, 0, 0, 0, 0}}, M.X_fee{M.W{35, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{36, 0, 0, 0, 0, 0, 0, 0}}), 0)), M.ip_le_pct(M.ret_fee(M.St{M.W{0, 0, 0, 0, 0, 0, 0, 0}}, M.X_fee{M.W{35, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{36, 0, 0, 0, 0, 0, 0, 0}}), 2, M.x_fee_p_amount(M.X_fee{M.W{35, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{36, 0, 0, 0, 0, 0, 0, 0}}))) == True{} : Bool}) -> {True{} == False{} : Bool}:
  (%e : {_ == False{} : Bool}
  ip_val())

def ip_absurd(r: {True{} == False{} : Bool}) -> Empty:
  (%r : M.ip_is_true(_)
  Unit{})

def Laws.cl_l_intent_9df661f22096f75c():
  (M.St{M.W{0, 0, 0, 0, 0, 0, 0, 0}}, (M.X_fee{M.W{35, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{36, 0, 0, 0, 0, 0, 0, 0}}, e => ip_absurd(ip_flip(e))))
