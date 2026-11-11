import Base
import ../model/Cf2d128.bend as M
import ./LAWS.bend as Laws

def ip_val() -> {Bool.or(Bool.not(U32.is_eq(M.chk_pause(M.St{M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}}, M.X_pause{M.W{1, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}}), 0)), M.w_eq(M.x_pause_caller(M.X_pause{M.W{1, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}}), M.st_owner(M.St{M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}}))) == False{} : Bool}:
  {==}

def ip_flip(e: {Bool.or(Bool.not(U32.is_eq(M.chk_pause(M.St{M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}}, M.X_pause{M.W{1, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}}), 0)), M.w_eq(M.x_pause_caller(M.X_pause{M.W{1, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}}), M.st_owner(M.St{M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}}))) == True{} : Bool}) -> {True{} == False{} : Bool}:
  (%e : {_ == False{} : Bool}
  ip_val())

def ip_absurd(r: {True{} == False{} : Bool}) -> Empty:
  (%r : M.ip_is_true(_)
  Unit{})

def Laws.cl_l_intent_030faa7bb342d83f():
  (M.St{M.W{0, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}}, (M.X_pause{M.W{1, 0, 0, 0, 0, 0, 0, 0}, M.W{0, 0, 0, 0, 0, 0, 0, 0}}, e => ip_absurd(ip_flip(e))))
