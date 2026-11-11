import Base
import ../model/C8031a4.bend as M
import ./LAWS.bend as Laws

def ip_lem_l_intent_a485355f19d5905c(+b0: Bool, +b1: Bool) -> {Bool.or(Bool.not(U32.is_eq(M.ip_ite_u(b0, M.ip_ite_u(b1, 0, 2), 1), 0)), b1) == True{} : Bool}:
  match b0 b1:
    case True{} True{}:
      {==}
    case True{} False{}:
      {==}
    case False{} True{}:
      {==}
    case False{} False{}:
      {==}

def Laws.l_intent_a485355f19d5905c(s, x):
  match s:
    case M.St{+s_f_owner, +s_f_stopped}:
      match x:
        case M.X_pause{+x_caller, +x_e_msg_value}:
          ip_lem_l_intent_a485355f19d5905c(M.w_eq(M.x_pause_e_msg_value(M.X_pause{x_caller, x_e_msg_value}), M.W{0, 0, 0, 0, 0, 0, 0, 0}), M.w_eq(M.x_pause_caller(M.X_pause{x_caller, x_e_msg_value}), M.st_owner(M.St{s_f_owner, s_f_stopped})))
