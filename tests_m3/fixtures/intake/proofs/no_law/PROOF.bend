# I41 fixture: a proof file that checks but lacks the expected law. It carries the same Reach induction as
# valid/PROOF.bend, as a plain def ag_main, but it never imports ../../laws/L_i41_x_any_act/LAWS.bend as Laws,
# so the law l_i41_x_any_act is not in the file Bend accepts (BEND_PRIMER 3.1: a file with no law checks
# vacuously; audit F-M2-07). The intake must refuse it (missing_expected_law), although Bend says ALL PROOFS CHECK.
import Base
import ../../model/toy_intake_facts.bend as M

def ag_x(s: M.HSt) -> Nat:
  match s:
    case M.HSt{+x, +y, +k, +flag, +log}:
      x

def ag_y(s: M.HSt) -> Nat:
  match s:
    case M.HSt{+x, +y, +k, +flag, +log}:
      y

def ag_goal(s: M.HSt) -> Type:
  {M.x_zero(s) == True{} : Bool}

def ag_inv(s: M.HSt) -> Type:
  ag_goal(s) & ({ag_x(s) == 0n : Nat} & {ag_y(s) == 0n : Nat})

def ag_app(-A: Type, -B: Type, f: A -> B, x: A) -> B:
  f(x)

def ag_tick(dd: M.Dec_tick, +k: Nat, +flag: Bool, +log: List<&2, M.HObs>, +d: Nat, h: ag_goal(M.HSt{0n, 0n, k, flag, log})) -> ag_inv(M.exec_tick(dd, 0n, 0n, k, flag, log, d)):
  match dd:
    case M.D_tick_Rev{cc}:
      (h, ({==}, {==}))
    case M.D_tick_Ok{}:
      (h, ({==}, {==}))

def ag_copy(dd: M.Dec_copy, +k: Nat, +flag: Bool, +log: List<&2, M.HObs>, h: ag_goal(M.HSt{0n, 0n, k, flag, log})) -> ag_inv(M.exec_copy(dd, 0n, 0n, k, flag, log)):
  match dd:
    case M.D_copy_Rev{cc}:
      (h, ({==}, {==}))
    case M.D_copy_Ok{}:
      (h, ({==}, {==}))

def ag_clear(dd: M.Dec_clear, +k: Nat, +flag: Bool, +log: List<&2, M.HObs>, h: ag_goal(M.HSt{0n, 0n, k, flag, log})) -> ag_inv(M.exec_clear(dd, 0n, 0n, k, flag, log)):
  match dd:
    case M.D_clear_Rev{cc}:
      (h, ({==}, {==}))
    case M.D_clear_Ok{}:
      (h, ({==}, {==}))

def ag_raise(dd: M.Dec_raise, +k: Nat, +flag: Bool, +log: List<&2, M.HObs>, h: ag_goal(M.HSt{0n, 0n, k, flag, log})) -> ag_inv(M.exec_raise(dd, 0n, 0n, k, flag, log)):
  match dd:
    case M.D_raise_Rev{cc}:
      (h, ({==}, {==}))
    case M.D_raise_Ok{}:
      (h, ({==}, {==}))

def ag_step(+a: M.HAct, s1: M.HSt, ih: ag_inv(s1)) -> ag_inv(M.step(a, s1)):
  match a s1:
    case M.A_tick{+d} M.HSt{+x, +y, +k, +flag, +log}:
      (h0, hr) = ih
      (hx, hy) = hr
      ag_app(ag_goal(M.HSt{x, y, k, flag, log}), ag_inv(M.step(M.A_tick{d}, M.HSt{x, y, k, flag, log})), (%Equal.sym(Nat, x, 0n, hx) : (ag_goal(M.HSt{_, y, k, flag, log}) -> ag_inv(M.step(M.A_tick{d}, M.HSt{_, y, k, flag, log}))); (%Equal.sym(Nat, y, 0n, hy) : (ag_goal(M.HSt{0n, _, k, flag, log}) -> ag_inv(M.step(M.A_tick{d}, M.HSt{0n, _, k, flag, log}))); j => ag_tick(M.decide_tick(d), k, flag, log, d, j))), h0)
    case M.A_copy{} M.HSt{+x, +y, +k, +flag, +log}:
      (h0, hr) = ih
      (hx, hy) = hr
      ag_app(ag_goal(M.HSt{x, y, k, flag, log}), ag_inv(M.step(M.A_copy{}, M.HSt{x, y, k, flag, log})), (%Equal.sym(Nat, x, 0n, hx) : (ag_goal(M.HSt{_, y, k, flag, log}) -> ag_inv(M.step(M.A_copy{}, M.HSt{_, y, k, flag, log}))); (%Equal.sym(Nat, y, 0n, hy) : (ag_goal(M.HSt{0n, _, k, flag, log}) -> ag_inv(M.step(M.A_copy{}, M.HSt{0n, _, k, flag, log}))); j => ag_copy(M.decide_copy(k), k, flag, log, j))), h0)
    case M.A_clear{} M.HSt{+x, +y, +k, +flag, +log}:
      (h0, hr) = ih
      (hx, hy) = hr
      ag_app(ag_goal(M.HSt{x, y, k, flag, log}), ag_inv(M.step(M.A_clear{}, M.HSt{x, y, k, flag, log})), (%Equal.sym(Nat, x, 0n, hx) : (ag_goal(M.HSt{_, y, k, flag, log}) -> ag_inv(M.step(M.A_clear{}, M.HSt{_, y, k, flag, log}))); (%Equal.sym(Nat, y, 0n, hy) : (ag_goal(M.HSt{0n, _, k, flag, log}) -> ag_inv(M.step(M.A_clear{}, M.HSt{0n, _, k, flag, log}))); j => ag_clear(M.decide_clear(), k, flag, log, j))), h0)
    case M.A_raise{} M.HSt{+x, +y, +k, +flag, +log}:
      (h0, hr) = ih
      (hx, hy) = hr
      ag_app(ag_goal(M.HSt{x, y, k, flag, log}), ag_inv(M.step(M.A_raise{}, M.HSt{x, y, k, flag, log})), (%Equal.sym(Nat, x, 0n, hx) : (ag_goal(M.HSt{_, y, k, flag, log}) -> ag_inv(M.step(M.A_raise{}, M.HSt{_, y, k, flag, log}))); (%Equal.sym(Nat, y, 0n, hy) : (ag_goal(M.HSt{0n, _, k, flag, log}) -> ag_inv(M.step(M.A_raise{}, M.HSt{0n, _, k, flag, log}))); j => ag_raise(M.decide_raise(), k, flag, log, j))), h0)

def ag_reach(-s: M.HSt, r: M.Reach<s>) -> ag_inv(s):
  match r:
    case M.R0{e}:
      (%Equal.sym(M.HSt, s, M.s0(), e) : ag_inv(_)
      ({==}, ({==}, {==})))
    case M.RStep{+b, +p, r1, e}:
      (%Equal.sym(M.HSt, s, M.step(b, p), e) : ag_inv(_)
      ag_step(b, p, ag_reach(p, r1)))

def ag_first(-s: M.HSt, i: ag_inv(s)) -> ag_goal(s):
  (t0, tr) = i
  t0

def ag_main(+s: M.HSt, r_s: M.Reach<s>, +a: M.HAct) -> ag_goal(s):
  ag_first(s, ag_reach(s, r_s))
