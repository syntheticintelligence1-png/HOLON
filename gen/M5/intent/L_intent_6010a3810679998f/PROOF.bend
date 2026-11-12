import Base
import ../model/C71e7a3.bend as M
import ./LAWS.bend as Laws

def ip_val() -> {Bool.or(Bool.not(U32.is_eq(M.chk_step(M.St{M.W{2, 0, 0, 0, 0, 0, 0, 0}}, M.X_step{M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}}), 0)), M.w_ge(M.st_count(M.post_step(M.St{M.W{2, 0, 0, 0, 0, 0, 0, 0}}, M.X_step{M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}})), M.st_count(M.St{M.W{2, 0, 0, 0, 0, 0, 0, 0}}))) == False{} : Bool}:
  {==}

def ip_flip(e: {Bool.or(Bool.not(U32.is_eq(M.chk_step(M.St{M.W{2, 0, 0, 0, 0, 0, 0, 0}}, M.X_step{M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}}), 0)), M.w_ge(M.st_count(M.post_step(M.St{M.W{2, 0, 0, 0, 0, 0, 0, 0}}, M.X_step{M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}})), M.st_count(M.St{M.W{2, 0, 0, 0, 0, 0, 0, 0}}))) == True{} : Bool}) -> {True{} == False{} : Bool}:
  (%e : {_ == False{} : Bool}
  ip_val())

def ip_absurd(r: {True{} == False{} : Bool}) -> Empty:
  (%r : M.ip_is_true(_)
  Unit{})

def Laws.cl_l_intent_6010a3810679998f():
  (M.St{M.W{2, 0, 0, 0, 0, 0, 0, 0}}, (M.X_step{M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}}, e => ip_absurd(ip_flip(e))))
