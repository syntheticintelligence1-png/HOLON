# I7-P1 probe (hand-written, not generated): function-typed binders with pairwise collision-freedom
# premises over a finite set, checked under bend and BendTT --verdict.
#
# Finding: a Bend function value is Type, so it can never be copied, and a law binder of function type
# is affine (`for h`) or erased (`for -h`); `for +h` is rejected ("its type must be Data"). A statement
# that applies h at two points can only reason through equations about h, never by running h twice.
# So the IR 0.3 emitter erases Fn binders and renders CF(h, S) per pair {a, b} in its decidable form
# `eq(h(a), h(b)) == False`; the two laws nat_ne_* below show the decidable form and h(a) != h(b)
# agree on every pair of Nat values, and cf_sym shows the `!=` form also checks with an erased binder.
import Base

# the IR 0.3 rendering of fixture L3_cf: CF(h, {1, 2}) => eq_nat(h(1), h(2)) == false
law cf_sep:
  for -h: Nat -> Nat
  for cf0: {Nat.is_eq(h(1n), h(2n)) == False{} : Bool}
  {Nat.is_eq(h(1n), h(2n)) == False{} : Bool}

# the `!=` form, erased binder: collision-freedom is symmetric
law cf_sym:
  for -h: Nat -> Nat
  for cf0: {h(1n) != h(2n) : Nat}
  {h(2n) != h(1n) : Nat}

# the two renderings of a CF pair agree on Nat
law nat_is_eq_false_of_ne:
  for +a: Nat
  for +b: Nat
  for ne: {a != b : Nat}
  {Nat.is_eq(a, b) == False{} : Bool}

law nat_ne_of_is_eq_false:
  for +a: Nat
  for +b: Nat
  for e: {Nat.is_eq(a, b) == False{} : Bool}
  {a != b : Nat}
