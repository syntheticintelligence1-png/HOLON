import Base
import ./LAWS.bend as Laws

def efq(-P: Type, x: Empty) -> P:
  match x:

def is_t(b: Bool) -> Type:
  match b:
    case True{}:
      Unit
    case False{}:
      Empty

def core_false_ne_true(e: {False{} == True{} : Bool}) -> Empty:
  (%Equal.sym(Bool, False{}, True{}, e) : is_t(_)
  Unit{})

def core_is_eq_false(a: Nat, b: Nat, ne: {a == b : Nat} -> Empty) -> {Nat.is_eq(a, b) == False{} : Bool}:
  match a b:
    case 0n 0n:
      efq({Nat.is_eq(0n, 0n) == False{} : Bool}, ne({==}))
    case 0n 1n+bp:
      {==}
    case 1n+ap 0n:
      {==}
    case 1n+ap 1n+bp:
      core_is_eq_false(ap, bp, e => ne((%e : {1n+ap == 1n+_ : Nat}
      {==})))

def core_is_eq_refl(a: Nat) -> {Nat.is_eq(a, a) == True{} : Bool}:
  match a:
    case 0n:
      {==}
    case 1n+p:
      core_is_eq_refl(p)

def Laws.cf_sep(h, cf0):
  cf0

def Laws.cf_sym(h, cf0):
  e => cf0(Equal.sym(Nat, h(2n), h(1n), e))

def Laws.nat_is_eq_false_of_ne(a, b, ne):
  core_is_eq_false(a, b, ne)

def core_is_eq_at(+a: Nat, b: Nat, ab: {a == b : Nat}, e: {Nat.is_eq(a, b) == False{} : Bool}) -> {Nat.is_eq(a, a) == False{} : Bool}:
  (%Equal.sym(Nat, a, b, ab) : {Nat.is_eq(a, _) == False{} : Bool}
  e)

def Laws.nat_ne_of_is_eq_false(a, b, e):
  ab => core_false_ne_true((%core_is_eq_at(a, b, ab, e) : {_ == True{} : Bool}
  core_is_eq_refl(a)))
